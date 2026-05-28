#!/usr/bin/env python3
"""PreToolUse hook : refuse toute Edit/Write/MultiEdit ciblant un fichier
user-local protégé : CLAUDE.local.md, .claude/settings.local.json.

Ces fichiers contiennent des notes/préférences user-locales qui ne doivent
jamais être touchées par Claude (consigne projet).

Protocole hook Claude Code : lit un JSON sur stdin, exit 2 pour bloquer
(PreToolUse), exit 0 pour laisser passer.

Réécrit en Python stdlib (portabilité Windows/Unix sans bash).
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    # Normaliser les séparateurs Windows pour le test de suffixe.
    norm = file_path.replace("\\", "/")

    if norm.endswith("CLAUDE.local.md"):
        sys.stderr.write(
            "⛔ Modification de CLAUDE.local.md interdite "
            "(notes user-locales gitignored).\n"
            "Si tu as besoin de mettre à jour la mémoire projet, "
            "édite CLAUDE.md à la racine.\n"
        )
        return 2

    if norm.endswith("settings.local.json"):
        sys.stderr.write(
            "⛔ Modification de .claude/settings.local.json interdite "
            "(préférences user-locales).\n"
            "Pour ajouter une permission projet, édite "
            ".claude/settings.json à la place.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
