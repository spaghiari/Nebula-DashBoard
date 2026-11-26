"""Migration d'environnement : jobs asynchrones et routes (`/api/migration/*`).

Une opération (estimation, export, aperçu, import) peut durer plusieurs minutes
sur des gigaoctets de sessions : elle tourne dans un thread et l'interface
l'interroge (`GET /api/migration/jobs/<id>`). Un seul job à la fois ; une
estimation en cours cède la place à toute autre opération.

Secrets : la phrase de passe n'est lue que dans le corps de la requête de
démarrage, passée au thread et jamais stockée dans le job, les plans, les
journaux ni les messages d'erreur. Les erreurs renvoyées sont celles, déjà
sans secret, de `MigrationError` ; toute autre exception devient un message
générique (le détail va au journal serveur, sans valeur).
"""
from __future__ import annotations

import secrets
import threading
import time

from dashcore.config import (
    BACKUPS_DIR, MIGRATION_EXT, MIGRATION_JOB_TTL, MIGRATION_KDF_ITERATIONS,
    MIGRATION_MIN_PASSPHRASE, MIGRATION_PLAN_TTL, log,
)
from dashcore.env_local import EnvStoreUnreadable
from dashcore.helpers import CorruptJsonError, safe_id
from dashcore.migration import (
    estimate, list_source_workspaces, run_export, source_info, validate_passphrase,
)
from dashcore.migration_crypto import MigrationCancelled, MigrationError
from dashcore.migration_import import (
    PlanStale, archive_info, find_archives, normalize_options, preview_archive, run_import,
)

_LOCK = threading.Lock()
_JOBS: dict[str, "_Job"] = {}
_PLANS: dict[str, dict] = {}
_MAX_PLANS = 8


class _Job:
    def __init__(self, kind: str):
        self.id = secrets.token_urlsafe(12)
        self.kind = kind
        self.status = "running"
        self.phase = "start"
        self.label = ""
        self.done = 0
        self.total = 0
        self.started = time.time()
        self.finished: float | None = None
        self.result: dict | None = None
        self.error: str | None = None
        self.error_code: str | None = None
        self.cancel = threading.Event()
        self.thread: threading.Thread | None = None

    def progress(self, phase: str, done: int, total: int, label: str = "") -> None:
        self.phase, self.done, self.total, self.label = phase, int(done), int(total), label or ""

    def snapshot(self) -> dict:
        end = self.finished or time.time()
        return {
            "id": self.id, "kind": self.kind, "status": self.status, "phase": self.phase,
            "label": self.label, "done": self.done, "total": self.total,
            "elapsed": round(end - self.started, 1),
            "result": self.result, "error": self.error, "error_code": self.error_code,
        }


def _prune() -> None:
    now = time.time()
    for jid in [j for j, job in _JOBS.items()
                if job.finished and now - job.finished > MIGRATION_JOB_TTL]:
        del _JOBS[jid]
    for pid in [p for p, pl in _PLANS.items() if now - pl["created"] > MIGRATION_PLAN_TTL]:
        del _PLANS[pid]
    while len(_PLANS) > _MAX_PLANS:
        del _PLANS[min(_PLANS, key=lambda p: _PLANS[p]["created"])]


def _store_plan(fingerprint: dict, options: dict, digest: str) -> str:
    plan_id = secrets.token_urlsafe(12)
    _PLANS[plan_id] = {"archive": fingerprint, "options": options, "digest": digest,
                       "created": time.time()}
    return plan_id


def get_info() -> tuple[int, dict]:
    """Données de la page : workspaces exportables, valeurs par défaut."""
    ws = [{k: w[k] for k in ("id", "label", "emoji", "path", "exists", "in_workspaces_dir")}
          for w in list_source_workspaces()]
    return 200, {
        "workspaces": ws, "default_dest": str(BACKUPS_DIR), "ext": MIGRATION_EXT,
        "min_passphrase": MIGRATION_MIN_PASSPHRASE, "kdf_iterations": MIGRATION_KDF_ITERATIONS,
        "local": source_info(),
    }


def inspect_archive(body: dict) -> tuple[int, dict]:
    try:
        info = archive_info(body.get("path"))
    except MigrationError as e:
        return 400, {"error": str(e), "error_code": e.code}
    info.pop("tag", None)
    info.pop("mtime_ns", None)
    return 200, info


def list_archives(body: dict) -> tuple[int, dict]:
    try:
        return 200, {"archives": find_archives(body.get("folder"))}
    except MigrationError as e:
        return 400, {"error": str(e)}


def _ws_selection(body: dict):
    sel = body.get("workspaces")
    if sel is None:
        return None, None
    if not isinstance(sel, list) or not all(isinstance(x, str) and safe_id(x) for x in sel):
        return None, "liste de workspaces invalide"
    return set(sel), None


def _runner(job: _Job, fn) -> None:
    try:
        result = fn(job.progress, job.cancel.is_set)
        job.result = result
        job.status = "done"
    except MigrationCancelled:
        job.status = "cancelled"
        job.error, job.error_code = "Opération annulée.", "cancelled"
    except PlanStale as e:
        job.status = "error"
        job.error, job.error_code = str(e), e.code
        job.result = e.plan if isinstance(e.plan, dict) and "plan_id" in e.plan else {"plan": e.plan}
    except MigrationError as e:
        job.status = "error"
        job.error, job.error_code = str(e), e.code
    except (CorruptJsonError, EnvStoreUnreadable) as e:
        job.status = "error"
        job.error, job.error_code = str(e), "state_unreadable"
    except OSError as e:
        job.status = "error"
        job.error, job.error_code = f"Erreur système : {e.strerror or type(e).__name__}", "os_error"
        log.error("migration %s: erreur systeme %s", job.kind, type(e).__name__)
    except Exception as e:  # noqa: BLE001 - jamais le message brut (peut contenir un chemin ou une valeur)
        job.status = "error"
        job.error, job.error_code = "Erreur interne (voir les journaux du serveur).", "internal"
        log.error("migration %s: echec inattendu (%s)", job.kind, type(e).__name__, exc_info=True)
    finally:
        job.finished = time.time()


def start_job(body: dict) -> tuple[int, dict]:
    kind = body.get("kind")
    if kind not in ("estimate", "export", "preview", "import"):
        return 400, {"error": "type d'opération inconnu"}
    passphrase = body.get("passphrase")

    # -- validation des paramètres (aucune écriture) -------------------------
    if kind in ("estimate", "export"):
        selected, err = _ws_selection(body)
        if err:
            return 400, {"error": err}
    if kind == "export":
        err = validate_passphrase(passphrase)
        if err:
            return 400, {"error": err}
        if body.get("passphrase_confirm") != passphrase:
            return 400, {"error": "La confirmation ne correspond pas à la phrase de passe."}
        dest = body.get("dest_dir") or str(BACKUPS_DIR)
        if not isinstance(dest, str):
            return 400, {"error": "dossier de destination invalide"}
    if kind == "preview":
        if not isinstance(passphrase, str) or not passphrase:
            return 400, {"error": "Phrase de passe requise."}
        if not isinstance(body.get("archive_path"), str):
            return 400, {"error": "chemin de l'archive requis"}
        options = normalize_options(body.get("options"))
    if kind == "import":
        if not isinstance(passphrase, str) or not passphrase:
            return 400, {"error": "Phrase de passe requise."}

    with _LOCK:
        _prune()
        if kind == "import":
            stored = _PLANS.get(body.get("plan_id"))
            if stored is None:
                return 409, {"error": "Aperçu expiré ou inconnu : relance l'aperçu.",
                             "error_code": "plan_expired"}
        running = [j for j in _JOBS.values() if j.status == "running"]
        for j in running:
            if j.kind == "estimate":
                j.cancel.set()
        for j in running:
            if j.kind == "estimate" and j.thread is not None:
                j.thread.join(timeout=5)
        if any(j.status == "running" for j in _JOBS.values()):
            return 409, {"error": "Une opération de migration est déjà en cours.",
                         "error_code": "busy"}
        job = _Job(kind)
        _JOBS[job.id] = job

    if kind == "estimate":
        def fn(progress, cancel):
            return estimate(selected, progress, cancel)
    elif kind == "export":
        def fn(progress, cancel):
            return run_export(passphrase, dest, selected, progress, cancel)
    elif kind == "preview":
        def fn(progress, cancel):
            plan, fingerprint = preview_archive(body["archive_path"], passphrase, options,
                                                progress, cancel)
            with _LOCK:
                plan_id = _store_plan(fingerprint, options, plan["digest"])
            return {"plan_id": plan_id, "plan": plan, "expires_in": MIGRATION_PLAN_TTL}
    else:
        plan_id = body.get("plan_id")

        def fn(progress, cancel):
            try:
                result = run_import(stored, passphrase, progress, cancel)
            except PlanStale as e:
                with _LOCK:
                    new_id = _store_plan(stored["archive"], stored["options"], e.plan["digest"])
                e.plan = {"plan_id": new_id, "plan": e.plan}
                raise
            with _LOCK:
                _PLANS.pop(plan_id, None)
            return result

    log.info("migration: job %s demarre (%s)", job.id, kind)
    t = threading.Thread(target=_runner, args=(job, fn), name=f"migration-{kind}", daemon=True)
    job.thread = t
    t.start()
    return 202, {"job_id": job.id, "kind": kind}


def get_job(job_id: str) -> tuple[int, dict]:
    with _LOCK:
        _prune()
        job = _JOBS.get(job_id)
        if job is None:
            return 404, {"error": "opération inconnue"}
        return 200, job.snapshot()


def cancel_job(job_id: str) -> tuple[int, dict]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return 404, {"error": "opération inconnue"}
        if job.status == "running":
            job.cancel.set()
        return 200, {"ok": True, "status": job.status}
