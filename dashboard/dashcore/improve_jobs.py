"""Tâches de fond de la boucle d'amélioration (module claude-team).

Un job = un thread démon qui construit un `EngineContext`
(dashcore/improve_engine.py) et appelle UNE fonction du moteur :

  iteration -> run_iteration      (phase 2 seule si une `pending` existe)
  resolve   -> verdict_phase      (verdict d'une `pending` existante)
  measure   -> measure            (mesure de la configuration courante)
  abandon   -> abandon_pending    (restauration de la `pending`)

Un seul job à la fois sur tout le poste : le quota d'abonnement Claude est
partagé entre workspaces. Refus 409 si un job tourne déjà (ici ou
ailleurs) ou si une session Claude est probablement ouverte sur le
workspace (`session_busy`, contournable par `force`).

État persistant : IMPROVE_JOBS_DIR/<ws>.json = {"current", "history"}
(20 jobs au plus), écrit de façon atomique sous verrou à chaque
progression. Aucune donnée d'identification (compte, e-mail, jeton) n'y
figure : seulement compteurs, coût, statut, ids de session `claude -p`.

Journaux : IMPROVE_LOGS_DIR/<ws>/<job_id>.jsonl (événements du job) et
IMPROVE_LOGS_DIR/<ws>/<job_id>/ (flux bruts des appels, `log_dir` du
moteur) ; 20 jobs gardés par workspace.

Suivi de l'enfant `claude -p` : le moteur transmet `Job.on_spawn` à
`claude_runner.run_claude` (rappel `on_spawn`), qui mémorise le `Popen` (PID
et date de création, pour `cancel_job` et `recover_jobs`).

Stdlib only.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from pathlib import Path

from dashcore import active_sessions
from dashcore import claude_runner as cr
from dashcore import improve_engine as ie
from dashcore.config import (
    IMPROVE_CALL_TIMEOUT, IMPROVE_JOB_TIMEOUT, IMPROVE_JOBS_DIR, IMPROVE_LOGS_DIR,
    IMPROVE_MAX_USD_PER_ITERATION, log,
)
from dashcore.helpers import _remove_dir_or_link, project_dir_for_path

KINDS = ("iteration", "resolve", "measure", "abandon")
STATUSES = ("running", "succeeded", "failed", "cancelled", "interrupted", "quota", "budget",
            "timeout")
HISTORY_MAX = 20
LOGS_KEEP = 20
RECENT_ACTIVITY_S = 600          # transcript modifié il y a moins de 10 min = session ouverte
ERROR_MAX = 300
_WS_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_SESSION_RE = re.compile(r'"session_id"\s*:\s*"([A-Za-z0-9_.-]{1,128})"')

_LOCK = threading.RLock()              # registre en mémoire + fichiers d'état
_ACTIVE: dict[str, _Job] = {}          # ws_id -> job en cours (un seul au plus)


# --- Utilitaires ---------------------------------------------------------------------------

def _now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _valid_ws_id(ws_id) -> bool:
    return isinstance(ws_id, str) and bool(_WS_ID_RE.fullmatch(ws_id)) and ".." not in ws_id


def _state_path(ws_id: str) -> Path:
    return IMPROVE_JOBS_DIR / f"{ws_id}.json"


def _short_error(e: BaseException | str) -> str:
    """Message court sur une ligne, jamais de pile."""
    msg = str(e) if not isinstance(e, str) else e
    msg = " ".join(msg.split())
    if not isinstance(e, (str, ie.EngineError)):
        msg = f"{type(e).__name__} : {msg}" if msg else type(e).__name__
    return msg[:ERROR_MAX] or "erreur inconnue"


def _load_state(ws_id: str) -> dict:
    p = _state_path(ws_id)
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {"current": None, "history": []}
    except (OSError, ValueError, UnicodeDecodeError) as e:
        log.warning("état des jobs illisible %s : %s", p, e)
        return {"current": None, "history": []}
    if not isinstance(data, dict):
        return {"current": None, "history": []}
    cur = data.get("current") if isinstance(data.get("current"), dict) else None
    hist = [h for h in data.get("history") or [] if isinstance(h, dict)][:HISTORY_MAX]
    return {"current": cur, "history": hist}


def _save_state(ws_id: str, state: dict) -> None:
    p = _state_path(ws_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            # Windows : lecteur concurrent (antivirus, autre lecture) ; on réessaie.
            if attempt == 4:
                raise
            time.sleep(0.05)


def _pid_alive(pid: int) -> bool:
    return active_sessions.is_pid_alive(int(pid))


def _kill_pid(pid: int) -> None:
    """Tue un arbre de processus par PID (orphelin d'un serveur arrêté)."""
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                           capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, OSError) as e:
            log.warning("taskkill %s : %s", pid, e)
        return
    import signal
    try:
        os.killpg(os.getpgid(int(pid)), signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def _session_ids_from_logs(log_dir: Path) -> list[str]:
    """Ids de session des appels `claude -p` du job (flux bruts du moteur)."""
    out: list[str] = []
    try:
        files = sorted(log_dir.glob("*.jsonl"))
    except OSError:
        return out
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                head = fh.read(65536)
        except OSError:
            continue
        for m in _SESSION_RE.finditer(head):
            if m.group(1) not in out:
                out.append(m.group(1))
            break
    return out


def _rotate_logs(ws_id: str, keep: int = LOGS_KEEP) -> None:
    """Garde les `keep` jobs les plus récents (fichier .jsonl + dossier)."""
    base = IMPROVE_LOGS_DIR / ws_id
    if not base.is_dir():
        return
    jobs: dict[str, float] = {}
    for p in base.iterdir():
        name = p.stem if p.is_file() and p.suffix == ".jsonl" else p.name
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        jobs[name] = max(jobs.get(name, 0.0), mt)
    old = sorted(jobs, key=lambda k: (jobs[k], k), reverse=True)[keep:]
    for name in old:
        for p in (base / f"{name}.jsonl", base / name):
            try:
                if p.is_dir():
                    _remove_dir_or_link(p)
                elif p.exists():
                    p.unlink()
            except OSError as e:
                log.warning("rotation des journaux improve %s : %s", p, e)


# --- Job ----------------------------------------------------------------------------------

def _new_record(job_id: str, ws_id: str, kind: str) -> dict:
    return {"job_id": job_id, "ws_id": ws_id, "kind": kind, "status": "running",
            "step": "démarrage", "cases_done": 0, "cases_total": 0,
            "started_at": _now_iso(), "ended_at": None, "pid": None, "pid_ctime": None,
            "cost_usd": 0.0,
            "tokens": {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0},
            "calls": 0, "iteration": None, "verdict": None, "score": None,
            "quota_reset": None, "error": None, "session_ids": []}


class _Job:
    def __init__(self, ws_id: str, ws_dir: Path, kind: str, max_usd: float):
        self.ws_id = ws_id
        self.ws_dir = Path(ws_dir)
        self.kind = kind
        self.job_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
        self.cancel = threading.Event()
        self.record = _new_record(self.job_id, ws_id, kind)
        self.proc = None
        self.log_dir = IMPROVE_LOGS_DIR / ws_id / self.job_id
        self.events_path = IMPROVE_LOGS_DIR / ws_id / f"{self.job_id}.jsonl"
        self.max_usd = max_usd
        self.ctx: ie.EngineContext | None = None
        self.thread: threading.Thread | None = None
        self._first_case: str | None = None
        self._critic_seen = False

    # -- persistance ------------------------------------------------------------
    def persist(self) -> None:
        with _LOCK:
            state = _load_state(self.ws_id)
            state["current"] = dict(self.record)
            _save_state(self.ws_id, state)

    def finish(self) -> None:
        with _LOCK:
            state = _load_state(self.ws_id)
            state["current"] = None
            hist = [h for h in state["history"] if h.get("job_id") != self.job_id]
            state["history"] = [dict(self.record), *hist][:HISTORY_MAX]
            _save_state(self.ws_id, state)
            if _ACTIVE.get(self.ws_id) is self:
                _ACTIVE.pop(self.ws_id, None)

    def event(self, **info) -> None:
        line = {"t": _now_iso(), **info}
        try:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError as e:
            log.warning("journal du job %s : %s", self.job_id, e)

    # -- suivi ----------------------------------------------------------------------
    def on_spawn(self, proc) -> None:
        self.proc = proc
        with _LOCK:
            self.record["pid"] = int(proc.pid)
            self.record["pid_ctime"] = active_sessions.process_creation_time(proc.pid)
        self.persist()

    def sync_spend(self) -> None:
        if self.ctx is None:
            return
        s = self.ctx.spend
        with _LOCK:
            self.record["cost_usd"] = round(float(s.get("cost_usd") or 0.0), 6)
            self.record["calls"] = int(s.get("calls") or 0)
            tok = s.get("tokens") or {}
            self.record["tokens"] = {k: int(tok.get(k) or 0) for k in self.record["tokens"]}
            self.record["session_ids"] = _session_ids_from_logs(self.log_dir)
            if self.proc is not None and self.proc.poll() is not None:
                self.proc = None
                self.record["pid"] = None
                self.record["pid_ctime"] = None

    def on_progress(self, info: dict) -> None:
        ev = info.get("event")
        with _LOCK:
            if ev == "case":
                cid = str(info.get("id") or "")
                if self._first_case is None or cid == self._first_case:
                    self._first_case = self._first_case or cid
                    self.record["cases_done"] = 0
                self.record["cases_done"] += 1
                if self.kind == "iteration":
                    self.record["step"] = "mesure candidat" if self._critic_seen else "mesure baseline"
                elif self.kind == "resolve":
                    self.record["step"] = "mesure candidat"
                else:
                    self.record["step"] = "mesure"
            elif ev == "call" and str(info.get("label") or "") == "critic":
                self._critic_seen = True
                self.record["step"] = "critique"
        self.sync_spend()
        self.event(**{k: v for k, v in info.items() if isinstance(v, (str, int, float))})
        self.persist()

    # -- exécution ----------------------------------------------------------------
    def _cases_total(self) -> int:
        try:
            return len(ie.load_cases(self.ws_dir, ie.load_manifest(self.ws_dir) or {}))
        except Exception:  # noqa: BLE001 - simple indication d'avancement
            return 0

    def _call_engine(self, ctx: ie.EngineContext) -> dict:
        if self.kind == "iteration":
            return ie.run_iteration(ctx)
        if self.kind == "abandon":
            return ie.abandon_pending(ctx, "abandonné depuis Nebula")
        lock = ie._ws_lock(self.ws_dir)
        if not lock.acquire(blocking=False):
            raise ie.ConflictError("une itération est déjà en cours sur ce workspace")
        try:
            return ie.verdict_phase(ctx) if self.kind == "resolve" else ie.measure(ctx)
        finally:
            lock.release()

    def _apply_result(self, res) -> None:
        r = res if isinstance(res, dict) else {}
        if self.kind == "iteration":
            part = r.get("verdict") or r.get("candidate") or {}
        else:
            part = r
        if isinstance(part, dict):
            if part.get("iteration") is not None:
                self.record["iteration"] = part.get("iteration")
            if part.get("dirty_paths"):
                # Refus avant toute mesure : configuration de l'équipe non commitée.
                self.record["verdict"] = "refused"
                self.record["reason"] = str(part.get("reason") or "")[:ERROR_MAX]
                self.record["dirty_paths"] = [str(x) for x in part["dirty_paths"]][:20]
            elif part.get("status") in ("accepted", "rejected", "pending"):
                self.record["verdict"] = part.get("status")
            rep = part.get("report") if isinstance(part.get("report"), dict) else None
            if self.kind == "measure" and "score" in part:
                self.record["score"] = part.get("score")
            elif rep is not None:
                self.record["score"] = rep.get("score")

    def run(self) -> None:
        status, error, reset = "succeeded", None, None
        try:
            self.record["cases_total"] = self._cases_total()
            self.persist()
            self.ctx = ie.EngineContext(
                ws_dir=self.ws_dir, ws_id=self.ws_id, job_id=self.job_id, max_usd=self.max_usd,
                call_timeout=IMPROVE_CALL_TIMEOUT, job_timeout=IMPROVE_JOB_TIMEOUT,
                cancel=self.cancel, cmd=None, log_dir=self.log_dir, progress=self.on_progress,
                on_spawn=self.on_spawn)
            self.event(event="start", kind=self.kind)
            res = self._call_engine(self.ctx)
            self._apply_result(res)
        except ie.QuotaReached as e:
            status, error, reset = "quota", _short_error(e), e.reset
        except ie.BudgetExceeded as e:
            status, error = "budget", _short_error(e)
        except ie.Cancelled as e:
            status, error = "cancelled", _short_error(e)
        except ie.JobTimeout as e:
            status, error = "timeout", _short_error(e)
        except ie.EngineError as e:
            status, error = "failed", _short_error(e)
        except Exception as e:  # noqa: BLE001 - un job ne fait jamais tomber le serveur
            log.exception("job improve %s (%s) en échec", self.job_id, self.ws_id)
            status, error = "failed", _short_error(e)
        finally:
            self.sync_spend()
            with _LOCK:
                self.record.update(status=status, error=error, quota_reset=reset,
                                   ended_at=_now_iso(), pid=None, pid_ctime=None,
                                   step="terminé")
            self.event(event="end", status=status, error=error or "")
            self.finish()


# --- API ----------------------------------------------------------------------------------

def is_running(ws_id: str | None = None) -> bool:
    """Un job tourne-t-il (pour ce workspace, ou sur tout le poste) ?"""
    with _LOCK:
        if ws_id is None:
            return bool(_ACTIVE)
        return ws_id in _ACTIVE


def session_busy(ws_id: str, ws_dir: Path, exclude_session_ids=()) -> tuple[bool, str]:
    """(occupé, raison) : session lancée par Nebula en cours (`running`), ou
    transcript du projet modifié depuis moins de 10 min et absent de
    `exclude_session_ids` (sessions du job lui-même)."""
    try:
        sess = (active_sessions.list_active() or {}).get(ws_id)
    except Exception as e:  # noqa: BLE001 - registre illisible : on continue sur les transcripts
        log.warning("sessions actives illisibles : %s", e)
        sess = None
    if isinstance(sess, dict) and sess.get("state") == "running":
        return True, "session lancée par Nebula en cours"
    try:
        pdir = project_dir_for_path(Path(ws_dir))
    except OSError:
        pdir = None
    if pdir is None:
        return False, ""
    exclude = {str(s) for s in exclude_session_ids or ()}
    now = time.time()
    try:
        transcripts = list(pdir.glob("*.jsonl"))
    except OSError:
        return False, ""
    for f in transcripts:
        if f.stem in exclude:
            continue
        try:
            age = now - f.stat().st_mtime
        except OSError:
            continue
        if age < RECENT_ACTIVITY_S:
            return True, "activité récente dans ce projet (session ouverte à la main ?)"
    return False, ""


def start_job(ws_id: str, ws_dir: Path, kind: str, *, max_usd: float | None = None,
              force: bool = False, exclude_session_ids: Iterable[str] = ()) -> tuple[int, dict]:
    """Lance un job en tâche de fond. 202 + état du job ; 400 `kind` ou
    paramètre invalide ; 409 `running` (un job tourne sur le poste) ou
    `session` (session Claude probablement ouverte, sauf `force`).
    `exclude_session_ids` : transcripts connus (jobs précédents) ignorés par
    le contrôle d'activité récente."""
    if kind not in KINDS:
        return 400, {"ok": False, "error": f"kind invalide : {kind!r} (attendu : {', '.join(KINDS)})",
                     "reason": "kind"}
    if not _valid_ws_id(ws_id):
        return 400, {"ok": False, "error": "identifiant de workspace invalide", "reason": "ws_id"}
    if max_usd is None:
        max_usd = IMPROVE_MAX_USD_PER_ITERATION
    try:
        max_usd = float(max_usd)
    except (TypeError, ValueError):
        return 400, {"ok": False, "error": "max_usd invalide", "reason": "max_usd"}
    if not (0 < max_usd < 1000):
        return 400, {"ok": False, "error": "max_usd hors bornes (0 à 1000 USD)", "reason": "max_usd"}
    ws_dir = Path(ws_dir)
    if not ws_dir.is_dir():
        return 404, {"ok": False, "error": "dossier du workspace introuvable", "reason": "ws_dir"}
    with _LOCK:
        if _ACTIVE:
            other = next(iter(_ACTIVE.values()))
            same = other.ws_id == ws_id
            return 409, {"ok": False, "reason": "running",
                         "error": ("un job tourne déjà pour ce workspace" if same else
                                   f"un job tourne déjà sur le poste (workspace {other.ws_id}) : "
                                   "un seul à la fois, quota partagé"),
                         "job": dict(other.record)}
        if not force:
            busy, why = session_busy(ws_id, ws_dir, exclude_session_ids)
            if busy:
                return 409, {"ok": False, "reason": "session", "error": why}
        job = _Job(ws_id, ws_dir, kind, max_usd)
        _ACTIVE[ws_id] = job
        try:
            job.persist()
        except OSError as e:
            _ACTIVE.pop(ws_id, None)
            return 500, {"ok": False, "error": _short_error(e), "reason": "state"}
        _rotate_logs(ws_id, keep=LOGS_KEEP - 1)
        t = threading.Thread(target=job.run, name=f"improve-{ws_id}-{job.job_id}", daemon=True)
        job.thread = t
        t.start()
        return 202, {"ok": True, "job": dict(job.record)}


def get_job(ws_id: str) -> dict | None:
    """Job en cours du workspace, sinon le dernier terminé, sinon None."""
    with _LOCK:
        job = _ACTIVE.get(ws_id)
        if job is not None:
            return dict(job.record)
        if not _valid_ws_id(ws_id):
            return None
        state = _load_state(ws_id)
    return state["current"] or (state["history"][0] if state["history"] else None)


def list_history(ws_id: str, limit: int = 20) -> list[dict]:
    """Jobs terminés du workspace, du plus récent au plus ancien."""
    if not _valid_ws_id(ws_id):
        return []
    with _LOCK:
        hist = _load_state(ws_id)["history"]
    return hist[:max(0, int(limit))]


def cancel_job(ws_id: str) -> tuple[int, dict]:
    """Annule le job du workspace : drapeau d'annulation + arrêt de l'arbre
    de l'enfant `claude` en cours. 404 si rien ne tourne."""
    with _LOCK:
        job = _ACTIVE.get(ws_id)
        if job is None:
            return 404, {"ok": False, "error": "aucun job en cours pour ce workspace"}
        job.cancel.set()
        proc = job.proc
    if proc is not None:
        try:
            cr.kill_tree(proc)
        except Exception as e:  # noqa: BLE001 - le drapeau suffit, le moteur s'arrêtera
            log.warning("arrêt de l'enfant claude %s : %s", getattr(proc, "pid", "?"), e)
    job.event(event="cancel_requested")
    return 202, {"ok": True, "job": dict(job.record)}


def _record_day(rec: dict) -> dt.date | None:
    try:
        return dt.datetime.fromisoformat(str(rec.get("started_at"))).date()
    except (TypeError, ValueError):
        return None


def spent_today(day: dt.date | None = None) -> float:
    """Somme des `cost_usd` des jobs démarrés `day` (aujourd'hui par défaut),
    tous workspaces confondus, job en cours compris."""
    day = day or dt.date.today()
    seen: dict[str, float] = {}
    with _LOCK:
        files = sorted(IMPROVE_JOBS_DIR.glob("*.json")) if IMPROVE_JOBS_DIR.is_dir() else []
        for f in files:
            state = _load_state(f.stem)
            for rec in [state["current"], *state["history"]]:
                if isinstance(rec, dict) and _record_day(rec) == day:
                    try:
                        seen[str(rec.get("job_id"))] = float(rec.get("cost_usd") or 0.0)
                    except (TypeError, ValueError):
                        continue
        for job in _ACTIVE.values():
            if _record_day(job.record) == day:
                seen[job.job_id] = float(job.record.get("cost_usd") or 0.0)
    return round(sum(seen.values()), 6)


def recover_jobs() -> list[str]:
    """Au démarrage du serveur : tout job `running` laissé sur disque devient
    `interrupted` ; son enfant orphelin est tué s'il vit encore et que sa
    date de création correspond. Renvoie les workspaces concernés."""
    out: list[str] = []
    with _LOCK:
        if not IMPROVE_JOBS_DIR.is_dir():
            return out
        for f in sorted(IMPROVE_JOBS_DIR.glob("*.json")):
            ws_id = f.stem
            if ws_id in _ACTIVE or not _valid_ws_id(ws_id):
                continue
            state = _load_state(ws_id)
            cur = state["current"]
            if not cur or cur.get("status") != "running":
                continue
            pid, ctime = cur.get("pid"), cur.get("pid_ctime")
            if pid and ctime is not None:
                try:
                    if _pid_alive(int(pid)) and active_sessions.process_creation_time(int(pid)) == ctime:
                        _kill_pid(int(pid))
                        log.info("job improve %s : enfant orphelin %s tué", cur.get("job_id"), pid)
                except (TypeError, ValueError, OSError) as e:
                    log.warning("enfant orphelin %s : %s", pid, e)
            cur.update(status="interrupted", ended_at=cur.get("ended_at") or _now_iso(),
                       pid=None, pid_ctime=None,
                       error=cur.get("error") or "serveur arrêté pendant le job")
            hist = [h for h in state["history"] if h.get("job_id") != cur.get("job_id")]
            state["current"] = None
            state["history"] = [cur, *hist][:HISTORY_MAX]
            _save_state(ws_id, state)
            out.append(ws_id)
    return out
