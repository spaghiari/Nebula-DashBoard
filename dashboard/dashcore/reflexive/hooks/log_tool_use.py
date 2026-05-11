"""PostToolUse hook — agrège les tool uses dans l'interaction courante.

Une "interaction" = série de tool uses dans une même session. On rattache
chaque PostToolUse à la dernière interaction ouverte pour cette session ;
si aucune, on en crée une nouvelle.
"""
from __future__ import annotations

import json
import sys

from _common import db_conn, log_error, now_iso, read_payload, workspace_id_for_cwd


def main() -> int:
    try:
        payload = read_payload()
        session_id = payload.get("session_id") or "unknown"
        tool_name = payload.get("tool_name") or payload.get("tool") or "unknown"
        # Path éventuellement touché (best-effort)
        tinput = payload.get("tool_input") or {}
        file_touched = tinput.get("file_path") or tinput.get("path") or None

        with db_conn() as conn:
            if conn is None:
                return 0
            ws = workspace_id_for_cwd() or "unknown"
            row = conn.execute("""
                SELECT id, tools_used, files_touched FROM interactions
                 WHERE session_id = ? AND ended_at IS NULL
                 ORDER BY started_at DESC LIMIT 1
            """, (session_id,)).fetchone()

            if row is None:
                conn.execute("""
                    INSERT INTO interactions(workspace_id, session_id, started_at, tools_used, files_touched)
                    VALUES(?, ?, ?, ?, ?)
                """, (ws, session_id, now_iso(),
                      json.dumps([tool_name]),
                      json.dumps([file_touched] if file_touched else [])))
            else:
                tools = []
                files = []
                try:
                    tools = json.loads(row["tools_used"] or "[]")
                    files = json.loads(row["files_touched"] or "[]")
                except json.JSONDecodeError:
                    pass
                tools.append(tool_name)
                if file_touched and file_touched not in files:
                    files.append(file_touched)
                conn.execute(
                    "UPDATE interactions SET tools_used = ?, files_touched = ? WHERE id = ?",
                    (json.dumps(tools), json.dumps(files), row["id"]),
                )
            conn.commit()
    except Exception as exc:
        log_error("log_tool_use", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
