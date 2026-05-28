#!/usr/bin/env python3
"""PreToolUse hook (matcher Bash) : intercepte les `git commit` et valide
le format des registres `.claude/improvements.md`, `.claude/backlog.md`,
`.claude/ideas.md` et `.claude/digests/*.md` si ces fichiers sont staged.

Vérifications :
  - Statuts entre [ ] dans la whitelist : TODO, IN PROGRESS, BLOCKED,
    DONE, ABANDONED, DONE YYYY-MM-DD, NEW, DEFERRED, REJECTED,
    PROMOTED -> backlog, PROMOTED -> roadmap, PROMOTED -> improvements
  - Priorités entre ( ) : P0, P1, P2
  - Format de date : YYYY-MM-DD
  - Champ `par <author>` présent sur tout item daté (mode équipe).
    Désactivable en mode solo via .claude/settings.local.json ->
    `validate_author: false`.

Bloque le commit (exit 2) si format invalide détecté.
Best-effort : silencieux si git absent ou si les fichiers concernés ne
sont pas staged.

`roadmap.md` est exclu (format libre vision/axes/jalons, pas de
[STATUT] obligatoire sur chaque ligne).

Réécrit en Python stdlib (portabilité Windows/Unix sans bash).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

# Whitelist des statuts (regex). Couvre cycle de vie, idea-funnel, promoted.
STATUS_WHITELIST = re.compile(
    r"\[TODO\]|\[IN PROGRESS\]|\[BLOCKED\]|\[DONE\]|\[ABANDONED\]"
    r"|\[DONE \d{4}-\d{2}-\d{2}\]|\[NEW\]|\[DEFERRED\]|\[REJECTED\]"
    r"|\[PROMOTED -> (?:backlog|roadmap|improvements)\]"
)
PRIORITY_WHITELIST = re.compile(r"\(P[0-2]")
PRIORITY_PRESENT = re.compile(r"\(P[^,)]")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
DATED_FIELD = re.compile(r"(ajouté|proposée) ")
DATED_FIELD_OK = re.compile(r"(ajouté|proposée) \d{4}-\d{2}-\d{2}")
AUTHOR_PATTERN = re.compile(r"par [a-zA-Z0-9._@-]+")
# Ligne d'item : commence (après éventuels espaces) par "- **["
ITEM_LINE = re.compile(r"^\s*-\s+\*\*\[")
FENCE = re.compile(r"^```")

TARGET_REGISTRIES = (
    ".claude/improvements.md",
    ".claude/backlog.md",
    ".claude/ideas.md",
)
DIGEST_RE = re.compile(r"^\.claude/digests/[^/]+\.md$")


def _git(*args: str) -> tuple[int, str]:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except (OSError, ValueError):
        return 1, ""
    return out.returncode, (out.stdout or "")


def _read_validate_author() -> bool:
    """Lit .claude/settings.local.json. Par défaut True (mode équipe).
    False si `"validate_author": false` présent (parsing tolérant)."""
    path = os.path.join(".claude", "settings.local.json")
    if not os.path.isfile(path):
        return True
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return True
    # Parsing JSON propre d'abord ; fallback regex si JSON cassé.
    try:
        data = json.loads(content)
        if isinstance(data, dict) and data.get("validate_author") is False:
            return False
        return True
    except (ValueError, TypeError):
        if re.search(r'"validate_author"\s*:\s*false', content):
            return False
        return True


def _item_lines(path: str) -> list[tuple[int, str]]:
    """Lignes d'item hors blocs fenced ```, numérotées (1-based)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    out: list[tuple[int, str]] = []
    in_fence = False
    for i, line in enumerate(lines, start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence and ITEM_LINE.match(line):
            out.append((i, line))
    return out


def _validate_file(path: str, validate_author: bool) -> list[str]:
    problems: list[str] = []
    for lineno, content in _item_lines(path):
        # Statut présent et valide ?
        if not STATUS_WHITELIST.search(content):
            problems.append(
                path + ":" + str(lineno)
                + " : statut invalide ou manquant entre [ ]"
            )
            problems.append(
                "  Whitelist : TODO, IN PROGRESS, BLOCKED, DONE, "
                "ABANDONED, DONE YYYY-MM-DD,"
            )
            problems.append(
                "             NEW, DEFERRED, REJECTED, "
                "PROMOTED -> {backlog,roadmap,improvements}"
            )
            problems.append("  Ligne : " + content + "\n")

        # Si la ligne mentionne une priorité (P_), vérifier qu'elle est valide.
        if PRIORITY_PRESENT.search(content):
            if not PRIORITY_WHITELIST.search(content):
                problems.append(
                    path + ":" + str(lineno)
                    + " : priorité invalide (attendu : P0, P1 ou P2)"
                )
                problems.append("  Ligne : " + content + "\n")

        # Si la ligne mentionne "ajouté <date>" ou "proposée <date>".
        if DATED_FIELD.search(content):
            if not DATED_FIELD_OK.search(content):
                problems.append(
                    path + ":" + str(lineno)
                    + " : date invalide (attendu : YYYY-MM-DD)"
                )
                problems.append("  Ligne : " + content + "\n")

            if validate_author and not AUTHOR_PATTERN.search(content):
                problems.append(
                    path + ":" + str(lineno)
                    + " : champ `par <author>` manquant (mode équipe)"
                )
                problems.append(
                    "  Format attendu : (Pn, ajouté YYYY-MM-DD par <author>)"
                )
                problems.append(
                    "  Pour désactiver en mode solo : "
                    ".claude/settings.local.json :"
                )
                problems.append('     { "validate_author": false }')
                problems.append("  Ligne : " + content + "\n")
    return problems


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

    if shutil.which("git") is None:
        return 0

    rc, staged_out = _git("diff", "--cached", "--name-only")
    if rc != 0:
        return 0
    staged = {f.strip() for f in staged_out.splitlines() if f.strip()}
    if not staged:
        return 0

    targets = [f for f in TARGET_REGISTRIES if f in staged]
    targets += [f for f in staged if DIGEST_RE.match(f)]
    if not targets:
        return 0

    validate_author = _read_validate_author()

    problems: list[str] = []
    for f in targets:
        if not os.path.isfile(f):
            continue
        problems.extend(_validate_file(f, validate_author))

    if not problems:
        return 0

    sys.stderr.write(
        "⛔ Format invalide détecté dans les registres `.claude/`:\n\n"
    )
    for line in problems:
        sys.stderr.write(line + "\n")
    sys.stderr.write(
        "\nRéférence du format attendu :\n"
        "  - **[STATUT] <titre>** (Pn, ajouté YYYY-MM-DD par <author>)\n"
        "  - **[DONE YYYY-MM-DD] <titre>** (Pn, ajouté YYYY-MM-DD par "
        "<author>, livré par <author>)\n\n"
        "Conventions : "
        "`.claude/memory/conventions/{backlog,self-improvement,digests}.md`\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
