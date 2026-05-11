"""Endpoints REST pour la boucle Reflexive.

Pattern aligné sur les autres modules `api_*` : fonctions pures retournant
`tuple[int, dict]`, exceptions catchées par le dispatcher. La DB est ouverte
paresseusement (cf. dashcore/reflexive/db.py).

CSRF : toutes les routes POST `/api/reflexive/*` exigent le header
`X-Nebula-XHR: 1` — la vérification est faite dans `server.py` via un check
par préfixe (voir `_SENSITIVE_PREFIXES`).
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from dashcore.config import WORKSPACES_JSON, log, _MUTATION_LOCK
from dashcore.helpers import read_json, safe_id, write_json
from dashcore.reflexive import connect
from dashcore.reflexive.install import install_hooks, uninstall_hooks


# ─── Utilitaires ────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for k in ("tools_used", "files_touched", "flags"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _parse_int(value, default: int, lo: int = 1, hi: int = 10_000) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _workspace_exists(ws_id: str) -> bool:
    data = read_json(WORKSPACES_JSON, {"workspaces": []})
    return any(w.get("id") == ws_id for w in data.get("workspaces", []))


# ─── Stats / vue d'ensemble ────────────────────────────────────────────────

def stats(query: dict) -> tuple[int, dict]:
    """Agrégats globaux ou filtrés par workspace, sur N jours (défaut 30)."""
    ws_id = (query.get("workspace_id", [""])[0] or "").strip() or None
    days = _parse_int(query.get("days", ["30"])[0], 30, 1, 365)

    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat(timespec="seconds")

    where = ["i.started_at >= ?"]
    params: list = [since]
    if ws_id:
        if not safe_id(ws_id):
            return 400, {"error": "workspace_id invalide"}
        where.append("i.workspace_id = ?")
        params.append(ws_id)
    where_sql = " AND ".join(where)

    with connect() as c:
        row = c.execute(f"""
            SELECT COUNT(*) AS n_inter,
                   AVG(e.total) AS avg_total,
                   AVG(e.correctness) AS avg_corr,
                   AVG(e.efficiency) AS avg_eff,
                   AVG(e.alignment) AS avg_align,
                   AVG(e.learning) AS avg_learn
              FROM interactions i
              LEFT JOIN evals e ON e.interaction_id = i.id
             WHERE {where_sql}
        """, params).fetchone()

        # Tendance : moyenne sur les `days` précédents (période double)
        since_prev = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days * 2)
        ).isoformat(timespec="seconds")
        params_prev = [since_prev, since] + ([ws_id] if ws_id else [])
        ws_prev = ws_id and " AND i.workspace_id = ?" or ""
        prev = c.execute(f"""
            SELECT AVG(e.total) AS avg_prev
              FROM interactions i
              LEFT JOIN evals e ON e.interaction_id = i.id
             WHERE i.started_at >= ? AND i.started_at < ?{ws_prev}
        """, params_prev).fetchone()

        # Série temporelle : moyenne quotidienne sur la période
        series = c.execute(f"""
            SELECT substr(i.started_at, 1, 10) AS day,
                   AVG(e.total) AS avg_total,
                   COUNT(*) AS n
              FROM interactions i
              LEFT JOIN evals e ON e.interaction_id = i.id
             WHERE {where_sql}
             GROUP BY day
             ORDER BY day
        """, params).fetchall()

        pending = c.execute(
            "SELECT COUNT(*) FROM proposals WHERE status = 'pending'"
            + (" AND (workspace_id = ? OR workspace_id IS NULL)" if ws_id else ""),
            ([ws_id] if ws_id else []),
        ).fetchone()[0]

    ws_data = read_json(WORKSPACES_JSON, {"workspaces": []})
    workspaces = ws_data.get("workspaces", [])
    n_enabled = sum(1 for w in workspaces if w.get("reflexive_enabled"))

    return 200, {
        "days": days,
        "workspace_id": ws_id,
        "interactions": row["n_inter"] or 0,
        "avg_total": row["avg_total"],
        "avg_total_prev": prev["avg_prev"],
        "dimensions": {
            "correctness": row["avg_corr"],
            "efficiency":  row["avg_eff"],
            "alignment":   row["avg_align"],
            "learning":    row["avg_learn"],
        },
        "series": [{"day": r["day"], "avg_total": r["avg_total"], "n": r["n"]} for r in series],
        "proposals_pending": pending,
        "workspaces_enabled": n_enabled,
        "workspaces_total": len(workspaces),
    }


# ─── Interactions ──────────────────────────────────────────────────────────

def list_interactions(query: dict) -> tuple[int, dict]:
    ws_id = (query.get("workspace_id", [""])[0] or "").strip() or None
    limit = _parse_int(query.get("limit", ["50"])[0], 50, 1, 500)
    offset = _parse_int(query.get("offset", ["0"])[0], 0, 0, 100_000)

    where = ""
    params: list = []
    if ws_id:
        if not safe_id(ws_id):
            return 400, {"error": "workspace_id invalide"}
        where = "WHERE i.workspace_id = ?"
        params.append(ws_id)

    with connect() as c:
        rows = c.execute(f"""
            SELECT i.*, e.total AS eval_total, e.flags AS eval_flags
              FROM interactions i
              LEFT JOIN evals e ON e.interaction_id = i.id
              {where}
             ORDER BY i.started_at DESC
             LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()
        total = c.execute(
            f"SELECT COUNT(*) FROM interactions i {where}", params
        ).fetchone()[0]

    return 200, {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_interaction(interaction_id: str) -> tuple[int, dict]:
    try:
        iid = int(interaction_id)
    except ValueError:
        return 400, {"error": "id invalide"}
    with connect() as c:
        i = c.execute("SELECT * FROM interactions WHERE id = ?", (iid,)).fetchone()
        if not i:
            return 404, {"error": "interaction inconnue"}
        e = c.execute("SELECT * FROM evals WHERE interaction_id = ?", (iid,)).fetchone()
    return 200, {
        "interaction": _row_to_dict(i),
        "eval": _row_to_dict(e) if e else None,
    }


# ─── Proposals ─────────────────────────────────────────────────────────────

def list_proposals(query: dict) -> tuple[int, dict]:
    status = (query.get("status", [""])[0] or "").strip() or None
    where = ""
    params: list = []
    if status:
        if status not in ("pending", "applied", "rejected", "reverted"):
            return 400, {"error": "status invalide"}
        where = "WHERE status = ?"
        params.append(status)
    with connect() as c:
        rows = c.execute(
            f"SELECT * FROM proposals {where} ORDER BY created_at DESC LIMIT 200",
            params,
        ).fetchall()
    return 200, {"items": [_row_to_dict(r) for r in rows]}


def get_proposal(proposal_id: str) -> tuple[int, dict]:
    try:
        pid = int(proposal_id)
    except ValueError:
        return 400, {"error": "id invalide"}
    with connect() as c:
        p = c.execute("SELECT * FROM proposals WHERE id = ?", (pid,)).fetchone()
        if not p:
            return 404, {"error": "proposition inconnue"}
        plans = c.execute(
            "SELECT * FROM measurement_plans WHERE proposal_id = ?", (pid,)
        ).fetchall()
    return 200, {
        "proposal": _row_to_dict(p),
        "measurement_plans": [_row_to_dict(r) for r in plans],
    }


def apply_proposal(proposal_id: str, body: dict) -> tuple[int, dict]:
    try:
        pid = int(proposal_id)
    except ValueError:
        return 400, {"error": "id invalide"}
    now = _now_iso()
    with connect() as c:
        p = c.execute("SELECT * FROM proposals WHERE id = ?", (pid,)).fetchone()
        if not p:
            return 404, {"error": "proposition inconnue"}
        if p["status"] != "pending":
            return 409, {"error": f"déjà au statut '{p['status']}'"}
        c.execute(
            "UPDATE proposals SET status = 'applied', applied_at = ? WHERE id = ?",
            (now, pid),
        )
        c.commit()
    log.info("Reflexive: proposition %s appliquée", pid)
    return 200, {"ok": True, "id": pid, "status": "applied", "applied_at": now}


def reject_proposal(proposal_id: str, body: dict) -> tuple[int, dict]:
    try:
        pid = int(proposal_id)
    except ValueError:
        return 400, {"error": "id invalide"}
    reason = (body.get("reason") or "").strip()
    if not reason:
        return 400, {"error": "raison de rejet requise"}
    if len(reason) > 2000:
        return 400, {"error": "raison trop longue (max 2000)"}
    with connect() as c:
        p = c.execute("SELECT status FROM proposals WHERE id = ?", (pid,)).fetchone()
        if not p:
            return 404, {"error": "proposition inconnue"}
        if p["status"] != "pending":
            return 409, {"error": f"déjà au statut '{p['status']}'"}
        c.execute(
            "UPDATE proposals SET status = 'rejected', rejection_reason = ? WHERE id = ?",
            (reason, pid),
        )
        c.commit()
    log.info("Reflexive: proposition %s rejetée", pid)
    return 200, {"ok": True, "id": pid, "status": "rejected"}


# ─── Workspace opt-in ──────────────────────────────────────────────────────

def _toggle_workspace(ws_id: str, enabled: bool) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "workspace_id invalide"}
    with _MUTATION_LOCK:
        data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
        ws = next((w for w in data.get("workspaces", []) if w.get("id") == ws_id), None)
        if not ws:
            return 404, {"error": "workspace inconnu"}
        ws_path = ws.get("path") or ""
        if not ws_path:
            return 400, {"error": "workspace sans chemin"}
        ws["reflexive_enabled"] = bool(enabled)
        write_json(WORKSPACES_JSON, data)

    # Mutation settings.json en dehors du lock workspaces.json (le module
    # install a son propre verrouillage).
    try:
        info = install_hooks(ws_path) if enabled else uninstall_hooks(ws_path)
    except Exception as exc:
        log.exception("Reflexive: hooks I/O failed for %s", ws_id)
        return 500, {"error": f"hooks I/O: {exc}"}
    return 200, {"ok": True, "id": ws_id, "reflexive_enabled": enabled, **info}


def enable_workspace(ws_id: str, body: dict) -> tuple[int, dict]:
    return _toggle_workspace(ws_id, True)


def disable_workspace(ws_id: str, body: dict) -> tuple[int, dict]:
    return _toggle_workspace(ws_id, False)


# ─── Diagnostician (stub commit 2, implémentation commit 5) ────────────────

def run_diagnostician(body: dict) -> tuple[int, dict]:
    return 501, {"error": "diagnostician non encore implémenté (commit 5)"}


# ─── Measurement plans ─────────────────────────────────────────────────────

def list_measurement_plans(query: dict) -> tuple[int, dict]:
    status = (query.get("status", [""])[0] or "").strip() or None
    where = ""
    params: list = []
    if status:
        if status not in ("active", "met", "failed"):
            return 400, {"error": "status invalide"}
        where = "WHERE status = ?"
        params.append(status)
    with connect() as c:
        rows = c.execute(
            f"SELECT * FROM measurement_plans {where} ORDER BY created_at DESC LIMIT 200",
            params,
        ).fetchall()
    return 200, {"items": [_row_to_dict(r) for r in rows]}
