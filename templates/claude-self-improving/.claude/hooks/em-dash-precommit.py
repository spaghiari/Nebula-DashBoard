#!/usr/bin/env python3
"""PreToolUse hook (matcher Bash) : intercepte les `git commit` et vérifie
que le diff staged ne contient pas d'em-dash (—) hors les fichiers
d'exception autorisés (CLAUDE.md, CONTRIBUTING.md,
.claude/commands/check-pitfalls.md).

Bloque le commit (exit 2) si violation détectée.
Best-effort : silencieux si git absent ou si la commande n'est pas un
`git commit`.

Réécrit en Python stdlib (portabilité Windows/Unix sans bash).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

EM_DASH = "—"  # — (caractère unicode, jamais écrit en littéral ici)

# Fichiers où l'em-dash est toléré (prose éditoriale assumée).
EXCEPTIONS = {
    "CLAUDE.md",
    "CONTRIBUTING.md",
    ".claude/commands/check-pitfalls.md",
}


def _extract_command(data: dict) -> str:
    tool_input = data.get("tool_input") or {}
    return tool_input.get("command") or ""


def _git(*args: str) -> str:
    """Lance git, retourne stdout (str) ou '' en cas d'échec."""
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except (OSError, ValueError):
        return ""
    return out.stdout or ""


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0

    command = _extract_command(data)
    if not command or "git commit" not in command:
        return 0

    if shutil.which("git") is None:
        return 0

    # Liste des fichiers staged contenant un ajout (+) avec em-dash.
    names = _git("diff", "--cached", "--name-only").splitlines()
    problem_files = []
    for f in names:
        f = f.strip()
        if not f:
            continue
        diff = _git("diff", "--cached", "--no-color", "--", f)
        has_em = any(
            line.startswith("+") and EM_DASH in line
            for line in diff.splitlines()
        )
        if has_em and f not in EXCEPTIONS:
            problem_files.append(f)

    if not problem_files:
        return 0

    sys.stderr.write(
        "⛔ Em-dash (" + EM_DASH + ") détecté dans le diff staged hors "
        "fichiers d'exception :\n"
    )
    for f in problem_files:
        sys.stderr.write("  - " + f + "\n")
    sys.stderr.write(
        "\nConvention projet : remplacer par \"-\" ou \":\". "
        "Exceptions autorisées :\n"
        "  CLAUDE.md, CONTRIBUTING.md, "
        ".claude/commands/check-pitfalls.md\n\n"
        "Pour voir les lignes : git diff --cached | "
        "grep -n \"" + EM_DASH + "\"\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
