#!/usr/bin/env python3
"""PreToolUse hook (matcher Bash) : intercepte les `git commit` et bloque
si le message contient le trailer `Co-Authored-By: Claude`
(case-insensitive). Convention projet (CLAUDE.md règle ALWAYS-ON git) :
aucun trailer Co-Authored-By Claude dans aucun commit.

Symétrique à em-dash-precommit.py.

Approche : recherche tolérante directement sur le JSON brut stdin
(couvre les escapes JSON \\n / \\" présents dans les heredocs
sérialisés). Le pré-filtre s'appuie quand même sur l'extraction du
command field pour n'agir que sur les `git commit`.

Bloque le commit (exit 2) si violation détectée.

Réécrit en Python stdlib (portabilité Windows/Unix sans bash).
"""
from __future__ import annotations

import json
import re
import sys

# Forcer UTF-8 sur stderr : un message accentué/emoji peut sinon lever
# UnicodeEncodeError (Windows cp1252) AVANT le `return 2`, dégradant le
# blocage (exit 2) en simple avertissement non bloquant (exit 1).
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# co-authored-by / coauthoredby / co-authored by ... claude
# (n'importe quel séparateur non-alphabétique entre `by` et `claude`).
PATTERN = re.compile(r"co-?authored-?by[^a-z]+claude", re.IGNORECASE)


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0

    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") or ""
    if not command or "git commit" not in command:
        return 0

    # Grep tolérant sur le JSON brut (et non sur le command extrait) :
    # les heredocs sérialisés gardent le message complet dans la chaîne.
    if PATTERN.search(raw):
        sys.stderr.write(
            "⛔ Trailer Co-Authored-By Claude détecté dans le message "
            "de commit.\n\n"
            "Convention projet (CLAUDE.md règle ALWAYS-ON git) :\n"
            "  Pas de trailer \"Co-Authored-By: Claude\" dans aucun "
            "commit.\n\n"
            "Pour corriger : retirer le trailer du message et relancer\n"
            "le git commit. Le message s'arrête au corps utile.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
