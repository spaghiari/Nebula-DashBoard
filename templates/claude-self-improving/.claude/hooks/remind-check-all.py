#!/usr/bin/env python3
"""Stop hook : à la fin d'un turn Claude, si des modifications
non-committées existent dans application/, library/ ou public/, rappelle
de lancer /check-all avant commit.

Best-effort : ne bloque jamais (exit 0), juste informer (stdout est
renvoyé à Claude en system reminder).

À configurer selon la stack du projet : adapter la liste WATCHED_DIRS
et le corps du message aux dossiers de code réels du projet.

Réécrit en Python stdlib (portabilité Windows/Unix sans bash).
"""
from __future__ import annotations

import shutil
import subprocess
import sys

# Dossiers de code surveillés. À adapter à la stack du projet
# (ex. src/, dashcore/, js/...).
WATCHED_DIRS = ("application/", "library/", "public/")


def _git(*args: str) -> tuple[int, str]:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except (OSError, ValueError):
        return 1, ""
    return out.returncode, (out.stdout or "")


def main() -> int:
    if shutil.which("git") is None:
        return 0
    rc, _ = _git("rev-parse", "--git-dir")
    if rc != 0:
        return 0

    rc, porcelain = _git("status", "--porcelain")
    if rc != 0 or not porcelain.strip():
        return 0

    # Une entrée porcelain = "XY <path>" (XY = 2 colonnes de statut).
    modified = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # Gestion des renommages "old -> new".
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path.startswith(WATCHED_DIRS):
            modified.append(line)

    if not modified:
        return 0

    count = len(modified)
    sys.stdout.write(
        "📋 Rappel : " + str(count) + " fichier(s) du module "
        "modifié(s) sans commit.\n"
        "Avant commit, lance /check-all pour valider :\n"
        "  - linters selon la stack du projet\n"
        "  - check-pitfalls (registre des pièges)\n"
        "  - readme-sync (cohérence READMEs sous-dossiers)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
