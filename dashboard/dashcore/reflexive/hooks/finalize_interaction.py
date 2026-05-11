"""Stop hook — clôt l'interaction courante.

Met `ended_at` et marque `outcome = unknown`. L'invocation de l'évaluateur
(via `claude` CLI en subprocess) est laissée pour les commits ultérieurs ;
on se contente ici de fermer proprement pour que les stats reflètent
la fin de session.
"""
from __future__ import annotations

import json
import sys

from _common import db_conn, log_error, now_iso, read_payload


MIN_TOOLS_FOR_EVAL = 3  # seuil heuristique "non trivial"


def main() -> int:
    try:
        payload = read_payload()
        session_id = payload.get("session_id") or "unknown"
        with db_conn() as conn:
            if conn is None:
                return 0
            row = conn.execute("""
                SELECT id, tools_used FROM interactions
                 WHERE session_id = ? AND ended_at IS NULL
                 ORDER BY started_at DESC LIMIT 1
            """, (session_id,)).fetchone()
            if row is None:
                return 0
            tools = []
            try:
                tools = json.loads(row["tools_used"] or "[]")
            except json.JSONDecodeError:
                pass
            outcome = "unknown" if len(tools) >= MIN_TOOLS_FOR_EVAL else "unknown"
            conn.execute(
                "UPDATE interactions SET ended_at = ?, outcome = ? WHERE id = ?",
                (now_iso(), outcome, row["id"]),
            )
            conn.commit()
            # TODO commit 5/6 : si non-trivial, invoquer l'agent evaluator
            # via `claude -p` en subprocess (timeout 30s, échec silencieux).
    except Exception as exc:
        log_error("finalize_interaction", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
