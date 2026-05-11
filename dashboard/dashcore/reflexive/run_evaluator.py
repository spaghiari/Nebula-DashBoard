"""Background worker — score une interaction Reflexive via `claude -p`.

Lance le scoring d'une session, parse le JSON renvoye et l'insere dans la
table `evals`. Toute exception est ravalee et loggee dans
`dashboard/data/reflexive_hook_errors.log`. Sortie systematique avec code 0.

Usage : python run_evaluator.py <interaction_id> <transcript_path> <workspace_path>
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "dashboard" / "data" / "reflexive.db"
ERR_LOG = ROOT / "dashboard" / "data" / "reflexive_hook_errors.log"
AGENT_MD = ROOT / "reflexive_agents" / "evaluator.md"

CLAUDE_TIMEOUT_S = 180
TRANSCRIPT_MAX_CHARS = 30_000
CLAUDE_MD_MAX_CHARS = 8_000


def log_err(where: str, exc) -> None:
    try:
        ERR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ERR_LOG.open("a", encoding="utf-8") as f:
            ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            f.write(f"[{ts}] evaluator/{where}: {exc!r}\n")
            if isinstance(exc, BaseException):
                f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass


def read_transcript(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    lines: list[str] = []
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message") or {}
                role = msg.get("role") or entry.get("type") or "?"
                content = msg.get("content")
                if isinstance(content, list):
                    parts: list[str] = []
                    for c in content:
                        if isinstance(c, dict):
                            t = c.get("text") or c.get("name") or ""
                            parts.append(str(t))
                    content = " ".join(parts)
                lines.append(f"[{role}] {content}")
    except Exception as exc:
        log_err("read_transcript", exc)
    return "\n".join(lines)


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        return re.sub(r"^---.*?---\s*\n", "", text, count=1, flags=re.DOTALL)
    return text


def build_prompt(transcript: str, workspace_path: str) -> str:
    instructions = ""
    if AGENT_MD.exists():
        instructions = strip_frontmatter(AGENT_MD.read_text(encoding="utf-8")).strip()

    claude_md = Path(workspace_path) / "CLAUDE.md"
    conventions = ""
    if claude_md.exists():
        try:
            conventions = claude_md.read_text(encoding="utf-8", errors="replace")[:CLAUDE_MD_MAX_CHARS]
        except Exception as exc:
            log_err("read_claude_md", exc)

    return (
        f"{instructions}\n\n"
        f"## CLAUDE.md du workspace\n\n"
        f"{conventions or '(aucun CLAUDE.md trouve)'}\n\n"
        f"## Transcription de l'interaction a evaluer\n\n"
        f"{transcript[:TRANSCRIPT_MAX_CHARS]}\n\n"
        f"---\n\n"
        f"Produis maintenant l'objet JSON d'evaluation. Aucun texte autour."
    )


def parse_eval_json(stdout: str):
    if not stdout:
        return None
    stripped = stdout.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _clamp_score(v) -> int:
    try:
        return max(0, min(10, int(v)))
    except (TypeError, ValueError):
        return 0


def insert_score(interaction_id: int, data: dict) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        with conn:
            conn.execute(
                "INSERT INTO evals(interaction_id, evaluated_at, correctness,"
                " efficiency, alignment, learning, flags, justification)"
                " VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    interaction_id,
                    dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    _clamp_score(data.get("correctness")),
                    _clamp_score(data.get("efficiency")),
                    _clamp_score(data.get("alignment")),
                    _clamp_score(data.get("learning")),
                    json.dumps(data.get("flags") or [], ensure_ascii=False),
                    str(data.get("justification") or "")[:2000],
                ),
            )
        conn.close()
        return True
    except Exception as exc:
        log_err("insert_score", exc)
        return False


def run(interaction_id: int, transcript_path: str, workspace_path: str) -> None:
    transcript = read_transcript(transcript_path)
    if not transcript:
        log_err("run", f"transcript vide ou illisible pour interaction {interaction_id}")
        return

    prompt = build_prompt(transcript, workspace_path)

    claude_bin = shutil.which("claude") or "claude"
    try:
        r = subprocess.run(
            [claude_bin, "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CLAUDE_TIMEOUT_S,
            shell=False,
            cwd=workspace_path or None,
        )
    except subprocess.TimeoutExpired:
        log_err("run", f"timeout claude -p pour interaction {interaction_id}")
        return
    except FileNotFoundError:
        log_err("run", "claude CLI introuvable dans le PATH")
        return
    except Exception as exc:
        log_err("subprocess", exc)
        return

    if r.returncode != 0:
        log_err("run", f"claude rc={r.returncode} stderr={r.stderr[:500]!r}")
        return

    data = parse_eval_json(r.stdout or "")
    if not isinstance(data, dict):
        log_err("run", f"JSON non parsable interaction={interaction_id} stdout={r.stdout[:500]!r}")
        return

    if insert_score(interaction_id, data):
        total = sum(_clamp_score(data.get(k)) for k in ("correctness", "efficiency", "alignment", "learning"))
        log_err("run", f"OK score interaction {interaction_id} total~{total}/40")


def main(argv) -> int:
    if len(argv) < 4:
        log_err("main", f"argv invalides: {argv!r}")
        return 0
    try:
        interaction_id = int(argv[1])
    except ValueError:
        log_err("main", f"interaction_id invalide: {argv[1]!r}")
        return 0
    try:
        run(interaction_id, argv[2], argv[3])
    except Exception as exc:
        log_err("main", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
