#!/usr/bin/env python3
"""PreToolUse hook (matcher Edit|Write|MultiEdit) : verrou du jeu d'évals.

Refuse (exit 2) toute écriture sous `.claude/evals/` du projet quand
`improvement_loop.eval_set_locked` est vrai dans `.claude/team.json`,
SAUF si `.claude/settings.local.json` contient `"evals_unlocked": true`
(déverrouillage explicite par l'utilisateur, même pattern que
`validate_author`). Le journal `.claude/journal/` n'est jamais verrouillé.

Pourquoi : la boucle d'amélioration (`/improve`) ne doit jamais pouvoir
modifier ce qui la mesure, sinon elle apprend à tricher.

Protocole hook Claude Code : JSON sur stdin, exit 2 pour bloquer, exit 0
pour laisser passer. Best-effort : tout fichier manquant ou illisible
laisse passer (un verrou cassé ne doit pas rendre le workspace
inutilisable). Python stdlib, portable Windows/Unix.
"""
from __future__ import annotations

import json
import os
import re
import sys

# Forcer UTF-8 sur stderr : un message accentué peut sinon lever
# UnicodeEncodeError (Windows cp1252) AVANT le `return 2`, dégradant le
# blocage (exit 2) en simple avertissement non bloquant (exit 1).
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def _read_json(path: str):
    """JSON du fichier, ou None s'il est absent / illisible."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _project_root() -> str:
    """Racine du projet : CLAUDE_PROJECT_DIR (injectée par Claude Code),
    sinon le dossier courant."""
    root = (os.environ.get("CLAUDE_PROJECT_DIR") or "").strip() or os.getcwd()
    return os.path.normcase(os.path.abspath(root))


def _under(path: str, folder: str) -> bool:
    """Vrai si `path` est dans `folder` (ou est `folder`), séparateurs normalisés."""
    p = os.path.normcase(os.path.abspath(path))
    d = os.path.normcase(os.path.abspath(folder))
    return p == d or p.startswith(d.rstrip("\\/") + os.sep)


_EVALS_DIR_RE = re.compile(r"\.claude[\\/]+evals(?![\w.-])", re.IGNORECASE)
# Jetons qui écrivent, déplacent ou suppriment via le shell (bash, cmd,
# PowerShell). Volontairement large : un faux positif se contourne par
# `evals_unlocked`, un faux négatif casse la mesure.
_WRITE_TOKEN_RE = re.compile(
    r"(\btee\b|\bcp\b|\bmv\b|\brm\b|\brmdir\b|\bdel\b|\bcopy\b|\bmove\b|\bren\b"
    r"|\btouch\b|\bsed\s+-i|\bmkdir\b|\btruncate\b|\bdd\b"
    r"|Set-Content|Out-File|Add-Content|Remove-Item|Move-Item|Copy-Item|New-Item"
    r"|\bopen\([^)]*['\"][wax]\+?['\"])",
    re.IGNORECASE,
)
# Une redirection ne compte que si SA CIBLE est sous les évals : un `>`
# ailleurs dans la commande (`echo "a -> b"`, `print(1>0)`) n'écrit rien là.
_REDIRECT_TO_EVALS_RE = re.compile(
    r">>?\s*[\"']?[^\s\"'|&;]*\.claude[\\/]+evals(?![\w.-])", re.IGNORECASE)


def _bash_writes_evals(command: str) -> bool:
    """Vrai si une commande shell semble écrire sous `.claude/evals/`."""
    if not command or not _EVALS_DIR_RE.search(command):
        return False
    return bool(_REDIRECT_TO_EVALS_RE.search(command) or _WRITE_TOKEN_RE.search(command))


def is_locked(root: str) -> bool:
    """Vrai si le jeu d'évals est verrouillé ET non déverrouillé localement."""
    team = _read_json(os.path.join(root, ".claude", "team.json"))
    if not isinstance(team, dict):
        return False
    loop = team.get("improvement_loop") or {}
    if not isinstance(loop, dict) or not loop.get("eval_set_locked"):
        return False
    local = _read_json(os.path.join(root, ".claude", "settings.local.json"))
    if isinstance(local, dict) and local.get("evals_unlocked") is True:
        return False
    return True


def main() -> int:
    # stdin lu en UTF-8 explicite : sous Windows, sys.stdin décode en cp1252
    # (mojibake, UnicodeDecodeError -> hook inerte en silence).
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0

    tool_input = data.get("tool_input") or {}
    root = _project_root()

    if (data.get("tool_name") or "") == "Bash":
        # Un `echo >> .claude/evals/x`, `cp`, `sed -i`... contournerait le
        # verrou posé sur Edit/Write. Heuristique : la commande cite le
        # dossier des évals ET contient un jeton d'écriture. Les lectures
        # (`cat`, `python .claude/evals/checks/x.py`) passent.
        if not _bash_writes_evals(tool_input.get("command") or ""):
            return 0
    else:
        file_path = tool_input.get("file_path") or ""
        if not file_path:
            return 0
        target = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
        if not _under(target, os.path.join(root, ".claude", "evals")):
            return 0
    if not is_locked(root):
        return 0

    sys.stderr.write(
        "⛔ Jeu d'évals verrouillé : aucune écriture sous .claude/evals/ "
        "(improvement_loop.eval_set_locked dans .claude/team.json).\n"
        "La boucle d'amélioration ne doit jamais modifier ce qui la mesure.\n"
        "Pour ajouter ou corriger un cas, l'utilisateur pose "
        "\"evals_unlocked\": true dans .claude/settings.local.json le temps de "
        "l'édition (cf. /eval-add et .claude/evals/README.md).\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
