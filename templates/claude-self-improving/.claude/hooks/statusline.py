#!/usr/bin/env python3
"""Statusline : affiche dans la barre de statut Claude Code

  <module> v<version>[next <jalon>] · <branch>[↑N ↓N] · <state>

où :
  [next <jalon>]  apparaît si au moins un jalon du cycle de release est
                  en attente. <jalon> ∈ {tag, push, prod, release}
                  indique le PROCHAIN jalon à atteindre, en cascade
                  (tag -> push -> prod -> release).
                  Source prod/release : .git/am-release-state.txt
                  (lignes <tag>:<jalon>=<date>). Si tous atteints,
                  segment omis (release close).
  ↑N ↓N           commits ahead/behind vs upstream (silencieux si pas
                  d'upstream ou si à jour).
  state           clean (vert) | dirty (X code · Y doc)
                  code = hors .claude/, hors *.md, hors module.info ;
                  doc = le reste (rouge si code, orange si doc seul).

Couleurs ANSI : module bold cyan, version magenta, branche cyan,
markers yellow, clean green, dirty-code red, dirty-doc yellow.

Best-effort : si git absent, repo invalide, upstream absent ou aucun
tag, fallback silencieux (pas d'erreur affichée).

Réécrit en Python stdlib (portabilité Windows/Unix sans bash).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

# Forcer UTF-8 sur stdout : la statusline écrit des glyphes non-ASCII
# (↑ ↓ ·) qui lèveraient UnicodeEncodeError en environnement cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# Codes ANSI (palette riche)
RST = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"

MODULE_NAME = "{{label}}"


def _git(*args: str) -> tuple[int, str]:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except (OSError, ValueError):
        return 1, ""
    return out.returncode, (out.stdout or "")


def _have_git() -> bool:
    if shutil.which("git") is None:
        return False
    rc, _ = _git("rev-parse", "--git-dir")
    return rc == 0


def _read_version() -> str:
    """Version depuis module.info (ligne `Version: x.y.z`)."""
    if not os.path.isfile("module.info"):
        return "?"
    try:
        with open("module.info", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("Version:"):
                    return line[len("Version:"):].strip()
    except OSError:
        pass
    return "?"


def _release_segment(version: str) -> str:
    """Prochain jalon manquant en cascade (tag -> push -> prod -> release)."""
    if not _have_git() or version == "?":
        return ""

    tag_done = push_done = prod_done = release_done = False

    rc, tags = _git("tag", "--sort=-v:refname")
    last_tag = ""
    if rc == 0:
        lines = [t for t in tags.splitlines() if t.strip()]
        if lines:
            last_tag = lines[0].strip()
    if last_tag and last_tag == version:
        tag_done = True

    if tag_done:
        rc, remote = _git("ls-remote", "--tags", "origin",
                          "refs/tags/" + version)
        if rc == 0 and ("refs/tags/" + version) in remote:
            push_done = True

    cache_file = os.path.join(".git", "am-release-state.txt")
    if os.path.isfile(cache_file):
        try:
            with open(cache_file, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            content = ""
        for line in content.splitlines():
            if line.startswith(version + ":prod="):
                if line.split("=", 1)[1].strip():
                    prod_done = True
            elif line.startswith(version + ":release="):
                if line.split("=", 1)[1].strip():
                    release_done = True

    if not tag_done:
        return " [next tag]"
    if not push_done:
        return " [next push]"
    if not prod_done:
        return " [next prod]"
    if not release_done:
        return " [next release]"
    return ""


def _diverge() -> str:
    """Segment ahead/behind vs upstream (vide si pas d'upstream / à jour)."""
    rc, counts = _git("rev-list", "--left-right", "--count", "HEAD...@{u}")
    if rc != 0 or not counts.strip():
        return ""
    parts = counts.split()
    if len(parts) < 2:
        return ""
    try:
        ahead = int(parts[0])
        behind = int(parts[1])
    except ValueError:
        return ""
    if ahead > 0 and behind > 0:
        return " ↓" + str(behind) + " ↑" + str(ahead)
    if ahead > 0:
        return " ↑" + str(ahead)
    if behind > 0:
        return " ↓" + str(behind)
    return ""


def _state() -> str:
    """Dirty décomposé code vs doc, ou 'clean'."""
    rc, porcelain = _git("status", "--porcelain")
    if rc != 0:
        return "?"
    if not porcelain.strip():
        return "clean"

    code = doc = 0
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if (path.startswith(".claude/")
                or path.endswith(".md")
                or path == "module.info"):
            doc += 1
        else:
            code += 1

    if code > 0 and doc > 0:
        return "dirty (" + str(code) + " code · " + str(doc) + " doc)"
    if code > 0:
        return "dirty (" + str(code) + " code)"
    return "dirty (" + str(doc) + " doc)"


def main() -> int:
    version = _read_version()
    release_seg = _release_segment(version)

    branch = "?"
    diverge = ""
    state = "?"
    if _have_git():
        rc, b = _git("rev-parse", "--abbrev-ref", "HEAD")
        branch = b.strip() if rc == 0 and b.strip() else "?"
        diverge = _diverge()
        state = _state()

    module_disp = BOLD + CYAN + MODULE_NAME + RST
    version_disp = MAGENTA + "v" + version + RST
    branch_disp = CYAN + branch + RST
    marker_disp = (YELLOW + release_seg + RST) if release_seg else ""
    diverge_disp = (YELLOW + diverge + RST) if diverge else ""

    if state == "clean":
        state_disp = GREEN + state + RST
    elif "code" in state:
        state_disp = RED + state + RST
    else:
        state_disp = YELLOW + state + RST

    sys.stdout.write(
        module_disp + " " + version_disp + marker_disp
        + " · " + branch_disp + diverge_disp
        + " · " + state_disp
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
