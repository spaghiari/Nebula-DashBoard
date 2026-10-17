"""Planificateur du mode automatique de la boucle d'amélioration.

Un fil démon appelle `tick` à intervalle régulier. Pour chaque workspace
dont le mode automatique est activé, `tick` décide s'il faut lancer un job
(`improve_jobs.start_job`), avec au plus UN job sur tout le poste (quota
d'abonnement partagé). Désactivé par défaut.

État persistant `IMPROVE_AUTO_FILE` :
  {ws_id: {enabled, daily_budget, campaign_start_iteration, paused_until,
           pause_reason, ack_rejects_at, handled_job}}
Écriture atomique (`helpers.write_json`) sous verrou ; fichier absent ou
corrompu = valeurs par défaut sûres, jamais d'exception.

Ordre des gardes de `tick` (premier qui s'applique, rien n'est lancé) :
job en cours -> pause active -> dernier job `quota` (pause jusqu'à
`quota_reset`, sinon +1 h) -> dernier job `budget` ou plafond de coût du
jour (pause jusqu'à minuit) -> budget d'itérations du jour -> plafond de
campagne -> arrêt après rejets consécutifs non acquittés -> session ouverte
-> `resolve` resté non tranché (pause `undecidable`, reprise explicite)
-> `pending` (job `resolve`) -> sinon job `iteration`.

Les heures sont naïves, en heure locale. Stdlib only.
"""
from __future__ import annotations

import datetime as dt
import threading

from dashcore import api_team, improve_jobs
from dashcore.config import (
    IMPROVE_AUTO_FILE, IMPROVE_AUTO_ITERATIONS_PER_DAY, IMPROVE_MAX_USD_PER_DAY,
    IMPROVE_MAX_USD_PER_ITERATION, log,
)
from dashcore.helpers import read_json, write_json

DAILY_BUDGET_MAX = 10
DEFAULT_REJECT_STOP = 3
QUOTA_FALLBACK = dt.timedelta(hours=1)
UNDECIDABLE_PAUSE = dt.timedelta(days=3650)  # reprise explicite seulement (`resume`)

_LOCK = threading.RLock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()


def _defaults() -> dict:
    return {"enabled": False, "daily_budget": IMPROVE_AUTO_ITERATIONS_PER_DAY,
            "campaign_start_iteration": 1, "paused_until": None, "pause_reason": None,
            "ack_rejects_at": 0, "handled_job": None}


def _load_all() -> dict:
    data = read_json(IMPROVE_AUTO_FILE, {})
    return data if isinstance(data, dict) else {}


def _clean(raw) -> dict:
    out = _defaults()
    if not isinstance(raw, dict):
        return out
    out["enabled"] = raw.get("enabled") is True
    b = raw.get("daily_budget")
    if isinstance(b, int) and not isinstance(b, bool) and 1 <= b <= DAILY_BUDGET_MAX:
        out["daily_budget"] = b
    for k in ("campaign_start_iteration", "ack_rejects_at"):
        v = raw.get(k)
        if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
            out[k] = v
    for k in ("paused_until", "pause_reason", "handled_job"):
        if isinstance(raw.get(k), str) and raw[k]:
            out[k] = raw[k]
    return out


def get_auto(ws_id: str) -> dict:
    """État persistant du workspace (défauts sûrs si absent ou corrompu)."""
    with _LOCK:
        return _clean(_load_all().get(ws_id))


def _save(ws_id: str, auto: dict) -> None:
    with _LOCK:
        data = _load_all()
        data[ws_id] = auto
        try:
            write_json(IMPROVE_AUTO_FILE, data)
        except OSError as e:
            log.warning("improve_auto : écriture impossible (%s)", e)


def _safe_state(ws_id: str, state_fn=None) -> dict:
    try:
        status, st = (state_fn or api_team.improvement_state)(ws_id)
    except Exception as e:  # noqa: BLE001 - le planificateur ne doit jamais tomber
        log.warning("improve_auto : état illisible pour %s (%s)", ws_id, e)
        return {}
    return st if status == 200 and isinstance(st, dict) else {}


def _next_iteration(st: dict) -> int:
    nums = [j.get("iteration") for j in st.get("journal") or []
            if isinstance(j, dict) and isinstance(j.get("iteration"), int)]
    if nums:
        return max(nums) + 1
    return int((st.get("stats") or {}).get("iterations") or 0) + 1


def _parse(s) -> dt.datetime | None:
    """ISO -> datetime naïve locale (un décalage horaire est converti)."""
    try:
        d = dt.datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return d.astimezone().replace(tzinfo=None) if d.tzinfo else d


def _today_iterations(st: dict) -> int:
    v = (st.get("stats") or {}).get("today_iterations")
    return v if isinstance(v, int) else 0


def _streak(st: dict) -> int:
    v = (st.get("stats") or {}).get("consecutive_rejects")
    return v if isinstance(v, int) else 0


def auto_view(ws_id: str, state: dict | None = None) -> dict:
    """Vue pour l'API et `api_team.next_step`. `state` = résultat de
    `improvement_state` (ou au moins sa clé `stats`) ; lu si absent."""
    auto = get_auto(ws_id)
    if state is None:
        state = _safe_state(ws_id)
    spent = improve_jobs.spent_today()
    return {
        "enabled": auto["enabled"],
        "paused_until": auto["paused_until"],
        "pause_reason": auto["pause_reason"],
        "campaign_start_iteration": auto["campaign_start_iteration"],
        "daily_budget": auto["daily_budget"],
        "ack_rejects_at": auto["ack_rejects_at"],
        "daily_limit": auto["daily_budget"],
        "budget_reached": (_today_iterations(state) >= auto["daily_budget"]
                           or spent >= IMPROVE_MAX_USD_PER_DAY),
        "spent_today": spent,
    }


def set_auto(ws_id: str, *, enabled: bool | None = None, daily_budget: int | None = None,
             resume: bool = False) -> tuple[int, dict]:
    """Modifie le mode automatique. 400 si `daily_budget` hors 1..10."""
    if daily_budget is not None and (
            isinstance(daily_budget, bool) or not isinstance(daily_budget, int)
            or not 1 <= daily_budget <= DAILY_BUDGET_MAX):
        return 400, {"ok": False, "error": f"daily_budget hors bornes (1 à {DAILY_BUDGET_MAX})"}
    st = _safe_state(ws_id)
    with _LOCK:
        auto = get_auto(ws_id)
        if daily_budget is not None:
            auto["daily_budget"] = daily_budget
        if enabled is not None:
            if enabled and not auto["enabled"]:
                auto["campaign_start_iteration"] = _next_iteration(st)
                auto["paused_until"] = auto["pause_reason"] = None
                auto["ack_rejects_at"] = _streak(st)
            auto["enabled"] = bool(enabled)
        if resume:
            auto["ack_rejects_at"] = _streak(st)
            if auto["pause_reason"] in ("budget", "undecidable", "dirty_config"):
                auto["paused_until"] = auto["pause_reason"] = None
        _save(ws_id, auto)
    return 200, auto_view(ws_id, st)


def _next_midnight(now: dt.datetime) -> dt.datetime:
    return (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _pause(ws_id: str, auto: dict, until: dt.datetime, reason: str, job_id=None) -> None:
    auto["paused_until"] = until.isoformat(timespec="seconds")
    auto["pause_reason"] = reason
    if job_id:
        auto["handled_job"] = job_id
    _save(ws_id, auto)


def day_capped_max_usd(spent: float | None = None) -> float:
    """Plafond d'un job : `IMPROVE_MAX_USD_PER_ITERATION` borné par le reste
    du plafond du jour (peut être <= 0 : l'appelant refuse alors de lancer)."""
    if spent is None:
        spent = improve_jobs.spent_today()
    return min(IMPROVE_MAX_USD_PER_ITERATION, IMPROVE_MAX_USD_PER_DAY - spent)


def recent_job_session_ids(ws_id: str, last_job: dict | None = None,
                           now: dt.datetime | None = None) -> tuple[str, ...]:
    """`session_ids` des jobs du workspace terminés (ou démarrés) dans la
    fenêtre d'activité récente : leurs transcripts ne sont pas une session
    étrangère. Partagé par le planificateur et les lancements manuels."""
    now = now or dt.datetime.now()
    if last_job is None:
        last_job = improve_jobs.get_job(ws_id) or {}
    ids: list[str] = []
    for rec in [last_job, *improve_jobs.list_history(ws_id)]:
        if not isinstance(rec, dict):
            continue
        when = _parse(rec.get("ended_at")) or _parse(rec.get("started_at"))
        if when is not None and (now - when).total_seconds() > improve_jobs.RECENT_ACTIVITY_S:
            continue
        ids.extend(str(s) for s in rec.get("session_ids") or () if str(s) not in ids)
    return tuple(ids)


_recent_session_ids = recent_job_session_ids


def _decide(ws_id: str, auto: dict, now: dt.datetime, start_job, state_fn) -> dict | None:
    """Une décision pour un workspace actif ; None = rien à faire."""
    until = _parse(auto["paused_until"])
    if auto["paused_until"] and until is None:
        until = now  # valeur illisible : pause considérée expirée
    if until is not None:
        if until > now:
            return None
        auto["paused_until"] = auto["pause_reason"] = None
        _save(ws_id, auto)
    job = improve_jobs.get_job(ws_id) or {}
    jid = job.get("job_id")
    if job.get("status") == "quota" and jid and jid != auto["handled_job"]:
        reset = _parse(job.get("quota_reset"))
        _pause(ws_id, auto, reset if reset and reset > now else now + QUOTA_FALLBACK, "quota", jid)
        return None
    if jid and jid != auto["handled_job"] and job.get("status") == "budget":
        _pause(ws_id, auto, _next_midnight(now), "budget", jid)
        return None
    if jid and jid != auto["handled_job"] and job.get("verdict") == "refused":
        # Configuration de l'équipe non commitée : relancer serait refusé à
        # chaque tick. Reprise explicite après commit ou annulation.
        _pause(ws_id, auto, now + UNDECIDABLE_PAUSE, "dirty_config", jid)
        return None
    if improve_jobs.spent_today(now.date()) >= IMPROVE_MAX_USD_PER_DAY:
        _pause(ws_id, auto, _next_midnight(now), "budget")
        return None
    st = _safe_state(ws_id, state_fn)
    if not st:
        return None
    if _today_iterations(st) >= auto["daily_budget"]:
        return None
    loop = st.get("loop") or {}
    cap = loop.get("max_iterations")
    if isinstance(cap, int) and _next_iteration(st) - auto["campaign_start_iteration"] >= cap:
        return None
    stop = loop.get("stop_after_consecutive_rejects")
    stop = stop if isinstance(stop, int) and stop > 0 else DEFAULT_REJECT_STOP
    streak = _streak(st)
    ack = auto["ack_rejects_at"] if auto["ack_rejects_at"] <= streak else 0
    if streak - ack >= stop:
        return None
    from dashcore.workspace_io import resolve_ws_dir
    ws_dir = resolve_ws_dir(ws_id)
    if (st.get("pending") and jid and jid != auto["handled_job"]
            and job.get("kind") == "resolve" and job.get("status") == "succeeded"
            and job.get("verdict") not in ("accepted", "rejected")):
        # Verdict non tranché : relancer resolve à chaque tick tournerait en rond.
        _pause(ws_id, auto, now + UNDECIDABLE_PAUSE, "undecidable", jid)
        return None
    exclude = recent_job_session_ids(ws_id, job, now)
    busy, _why = improve_jobs.session_busy(ws_id, ws_dir, exclude_session_ids=exclude)
    if busy:
        return None
    if st.get("pending"):
        action, kwargs = "resolve", {"max_usd": day_capped_max_usd()}
    else:
        action, kwargs = "iteration", {"max_usd": day_capped_max_usd()}
    if exclude:
        kwargs["exclude_session_ids"] = exclude
    status, _res = start_job(ws_id, ws_dir, action, **kwargs)
    return {"ws_id": ws_id, "action": action, "status": status}


def tick(now: dt.datetime | None = None, *, start_job=improve_jobs.start_job,
         state_fn=api_team.improvement_state) -> list[dict]:
    """Un passage du planificateur. Lance au plus un job sur le poste."""
    now = now or dt.datetime.now()
    out: list[dict] = []
    if improve_jobs.is_running():
        return out
    with _LOCK:
        data = _load_all()
        ids = [k for k, v in data.items() if isinstance(v, dict) and v.get("enabled") is True]
    for ws_id in ids:
        try:
            r = _decide(ws_id, get_auto(ws_id), now, start_job, state_fn)
        except Exception as e:  # noqa: BLE001
            log.warning("improve_auto : %s ignoré (%s)", ws_id, e)
            continue
        if r:
            out.append(r)
            if r["status"] == 202:
                break
    return out


def _loop(interval_s: int) -> None:
    while not _STOP.wait(interval_s):
        try:
            tick()
        except Exception as e:  # noqa: BLE001
            log.warning("improve_auto : tick en erreur (%s)", e)


def start(interval_s: int = 60) -> None:
    """Démarre le fil démon (idempotent : un seul fil)."""
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _STOP.clear()
        _THREAD = threading.Thread(target=_loop, args=(max(1, int(interval_s)),),
                                   name="improve-scheduler", daemon=True)
        _THREAD.start()


def stop() -> None:
    """Arrête le fil démon."""
    global _THREAD
    with _LOCK:
        t, _THREAD = _THREAD, None
    _STOP.set()
    if t is not None:
        t.join(timeout=5)
