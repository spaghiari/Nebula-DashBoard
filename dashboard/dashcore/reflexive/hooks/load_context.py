"""SessionStart hook — injecte le contexte Reflexive pour ce workspace.

Lit les propositions appliquées récemment + les plans de mesure actifs et
écrit un résumé court sur stdout, que Claude Code ingère en début de session.
"""
from __future__ import annotations

import sys

from _common import db_conn, log_error, workspace_id_for_cwd, read_payload


def main() -> int:
    try:
        _ = read_payload()  # ignoré pour SessionStart (compat futur)
        ws = workspace_id_for_cwd()
        lines: list[str] = []
        with db_conn() as conn:
            if conn is None or ws is None:
                return 0
            applied = conn.execute("""
                SELECT title, applied_at FROM proposals
                 WHERE status = 'applied'
                   AND (workspace_id = ? OR workspace_id IS NULL)
                 ORDER BY applied_at DESC LIMIT 5
            """, (ws,)).fetchall()
            active_plans = conn.execute("""
                SELECT criteria, threshold_dimension, threshold_value, sample_size
                  FROM measurement_plans WHERE status = 'active'
                 ORDER BY created_at DESC LIMIT 5
            """).fetchall()

        if applied:
            lines.append("**Reflexive — leçons appliquées récemment :**")
            for r in applied:
                lines.append(f"- {r['title'] or '(sans titre)'} ({r['applied_at']})")
        if active_plans:
            lines.append("")
            lines.append("**Mesures en cours :**")
            for p in active_plans:
                lines.append(
                    f"- {p['criteria']} (seuil {p['threshold_dimension']} ≥ "
                    f"{p['threshold_value']} sur {p['sample_size']} interactions)"
                )

        if lines:
            sys.stdout.write("\n".join(lines) + "\n")
    except Exception as exc:
        log_error("load_context", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
