"""
Status line pour Claude Code.
Reçoit un JSON sur stdin (session info), écrit une ligne compacte sur stdout.

Format visé :
  📁 homeassistant · main · Opus 4.7 · 2 MCPs
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Force stdout UTF-8 pour les emojis + ANSI (Windows cp1252 par défaut)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

WORKSPACES_ROOT = Path(r"C:\claude-workspace\workspaces")

# Couleurs ANSI (Claude Code les affiche correctement)
RESET = "\x1b[0m"
DIM   = "\x1b[2m"
CYAN  = "\x1b[36m"
GREEN = "\x1b[32m"
YELLOW= "\x1b[33m"
PURPLE= "\x1b[35m"


def read_session():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def detect_workspace(cwd: Path) -> str | None:
    try:
        rel = cwd.resolve().relative_to(WORKSPACES_ROOT.resolve())
        return rel.parts[0] if rel.parts else None
    except Exception:
        return None


def git_branch(cwd: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(cwd), capture_output=True, text=True, timeout=1.5,
        )
        if r.returncode == 0:
            return r.stdout.strip() or None
    except Exception:
        pass
    return None


def count_active_mcps(cwd: Path) -> int:
    mcp_file = cwd / ".mcp.json"
    if not mcp_file.exists():
        return 0
    try:
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
        return len(data.get("mcpServers", {}))
    except Exception:
        return 0


def main():
    session = read_session()
    cwd_str = (session.get("workspace") or {}).get("current_dir") \
              or session.get("cwd") \
              or os.getcwd()
    cwd = Path(cwd_str)

    model = (session.get("model") or {}).get("display_name") or "?"

    parts = []

    ws = detect_workspace(cwd)
    if ws:
        parts.append(f"{CYAN}📁 {ws}{RESET}")
    else:
        parts.append(f"{DIM}📁 {cwd.name}{RESET}")

    branch = git_branch(cwd)
    if branch:
        parts.append(f"{GREEN}⎇ {branch}{RESET}")

    parts.append(f"{PURPLE}{model}{RESET}")

    n_mcp = count_active_mcps(cwd)
    if n_mcp:
        parts.append(f"{YELLOW}{n_mcp} MCP{'s' if n_mcp > 1 else ''}{RESET}")

    print(f"{DIM} · {RESET}".join(parts), end="")


if __name__ == "__main__":
    main()
