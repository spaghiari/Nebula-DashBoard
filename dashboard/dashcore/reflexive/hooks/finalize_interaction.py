"""Stop hook — clôt l'interaction courante.

Met `ended_at` et marque `outcome = unknown`. L'invocation de l'évaluateur
(via `claude` CLI en subprocess) est laissée pour les commits ultérieurs ;
on se contente ici de fermer proprement pour que les stats reflètent
la fin de session.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _common import db_conn, log_error, now_iso, read_payload


MIN_TOOLS_FOR_EVAL = 3  # seuil heuristique "non trivial"

# Chemin du worker autonome qui appelle `claude -p`.
WORKER_SCRIPT = Path(__file__).resolve().parent.parent / "run_evaluator.py"


def spawn_evaluator(interaction_id: int, transcript_path: str, workspace_path: str) -> None:
    """Lance le worker en arrière-plan détaché. Ne bloque PAS la fin de session.

    Le worker se débrouille seul : timeout, gestion d'erreur, INSERT.
    Si quelque chose plante côté spawn, on log silencieusement.
    """
    if not WORKER_SCRIPT.exists():
        log_error("spawn_evaluator", f"worker absent: {WORKER_SCRIPT}")
        return
    try:
        kwargs = {
            "stdin":  subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
            "cwd": workspace_path or None,
            "env": os.environ.copy(),
        }
        if sys.platform == "win32":
            # DETACHED_PROCESS | CREATE_NO_WINDOW : pas de console, pas de wait
            kwargs["creationflags"] = 0x00000008 | 0x08000000
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(
            [sys.executable, str(WORKER_SCRIPT),
             str(interaction_id), transcript_path, workspace_path],
            **kwargs,
        )
    except Exception as exc:
        log_error("spawn_evaluator", exc)


def extract_first_user_prompt(transcript_path: str) -> str:
    """Récupère le premier message user du transcript pour un résumé court."""
    if not transcript_path:
        return ""
    p = Path(transcript_path)
    if not p.exists():
        return ""
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message") or {}
                if msg.get("role") != "user":
                    continue
                content = msg.get("content")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            t = (c.get("text") or "").strip()
                            if t:
                                return t[:200]
                elif isinstance(content, str):
                    t = content.strip()
                    if t:
                        return t[:200]
    except Exception as exc:
        log_error("extract_first_user_prompt", exc)
    return ""


def main() -> int:
    try:
        payload = read_payload()
        session_id = payload.get("session_id") or "unknown"
        transcript_path = payload.get("transcript_path") or ""
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
            non_trivial = len(tools) >= MIN_TOOLS_FOR_EVAL
            outcome = "unknown"  # affiné par l'évaluation
            summary = extract_first_user_prompt(transcript_path)
            conn.execute(
                "UPDATE interactions SET ended_at = ?, outcome = ?, task_summary = ? WHERE id = ?",
                (now_iso(), outcome, summary or None, row["id"]),
            )
            conn.commit()
            interaction_id = row["id"]

        # Hors du lock DB : spawn détaché du worker si non trivial
        if non_trivial and transcript_path:
            spawn_evaluator(interaction_id, transcript_path, os.getcwd())
    except Exception as exc:
        log_error("finalize_interaction", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
