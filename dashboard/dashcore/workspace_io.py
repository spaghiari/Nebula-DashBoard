"""I/O et chemins liés aux workspaces : résolution de path, stats, lancement.

Centralise la traduction id workspace → chemin disque (`resolve_ws_dir`),
la génération du `.bat` de lancement, le calcul des stats de session,
et la cohérence registre vs fichiers `.mcp.json` (`sanity_check`).
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from dashcore.config import (
    BAT_UNSAFE, CLAUDE_PROJECTS, DASHBOARD_DIR, MCP_REGISTRY, SCRIPTS_DIR,
    WORKSPACES_DIR, WORKSPACES_JSON, log,
)
from dashcore.env_local import load_env_local
from dashcore.helpers import read_json


def list_workspaces() -> list[dict]:
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    return data.get("workspaces", [])


def cleanup_orphan_bats() -> dict:
    """Retire les .bat qui ne correspondent à aucun workspace du registre."""
    ws_ids = {w["id"] for w in list_workspaces()}
    removed = []
    for bat in SCRIPTS_DIR.glob("launch-*.bat"):
        wid = bat.stem[len("launch-"):]
        if wid not in ws_ids:
            bat.unlink()
            removed.append(bat.name)
    return {"removed": removed}


def project_dir_for_path(path: Path) -> Path | None:
    """Trouve le dossier ~/.claude/projects/<encodé> qui correspond à `path`.

    Claude encode le chemin en remplaçant `:` et `\\` par `-`. On encode
    directement le path cible plutôt que d'essayer de décoder les noms
    de dossier (décodage ambigu dès qu'un segment contient un `-`).
    """
    if not CLAUDE_PROJECTS.exists():
        return None
    target = str(path.resolve())
    encoded = target.replace(":", "-").replace("\\", "-").replace("/", "-").replace(" ", "-")
    candidate = CLAUDE_PROJECTS / encoded
    if candidate.is_dir():
        return candidate
    enc_lower = encoded.lower()
    for d in CLAUDE_PROJECTS.iterdir():
        if d.is_dir() and d.name.lower() == enc_lower:
            return d
    return None


def resolve_ws_dir(ws_id: str) -> Path:
    """Retourne le chemin disque réel d'un workspace.

    Cherche d'abord le path dans workspaces.json (workspaces importés peuvent
    pointer hors de WORKSPACES_DIR). Fallback : WORKSPACES_DIR/ws_id.
    Point d'accès UNIQUE — toute fonction qui touche au disque d'un workspace
    DOIT passer par ici, sinon les workspaces importés sont cassés.
    """
    data = read_json(WORKSPACES_JSON, {"workspaces": []})
    w = next((x for x in data.get("workspaces", []) if x.get("id") == ws_id), None)
    if w and w.get("path"):
        return Path(w["path"])
    return WORKSPACES_DIR / ws_id


def validate_ws_path(path: str) -> tuple[bool, str]:
    """Valide un chemin saisi par l'utilisateur (import / update workspace).

    Refuse : vide, relatif, UNC, caractères incompatibles avec un .bat.
    """
    p = (path or "").strip()
    if not p:
        return False, "chemin vide"
    if p.startswith("\\\\"):
        return False, "chemins UNC non supportés"
    pp = Path(p)
    if not pp.is_absolute():
        return False, "chemin absolu requis"
    if BAT_UNSAFE.search(p):
        return False, "caractères interdits dans le chemin (& | < > ^ \" %)"
    return True, ""


def write_launch_bat(ws_id: str, label: str, path: str) -> Path:
    """Écrit le script de lancement Claude Code pour un workspace."""
    bat_path = SCRIPTS_DIR / f"launch-{ws_id}.bat"
    safe_label = (label or ws_id).replace("\n", " ").replace("\r", " ")
    bat_path.write_text(
        f"@echo off\n"
        f"echo.\n"
        f"echo  +======================================+\n"
        f"echo  ^|   Claude Code -- {safe_label}\n"
        f"echo  +======================================+\n"
        f"echo.\n"
        f'cd /d "{path}"\n'
        f"claude\n",
        encoding="utf-8",
    )
    return bat_path


def launch_script(bat_name: str) -> tuple[int, dict]:
    bat = SCRIPTS_DIR / bat_name
    if not bat.exists():
        return 404, {"ok": False, "error": f"Script introuvable : {bat}"}
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(bat)],
            cwd=str(SCRIPTS_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            shell=False,
        )
        return 200, {"ok": True, "message": f"Lancé : {bat.name}"}
    except OSError as e:
        return 500, {"ok": False, "error": f"Erreur : {e}"}


def workspace_stats(ws: dict) -> dict:
    pdir = project_dir_for_path(Path(ws["path"]))
    if not pdir:
        return {
            "sessions": 0, "messages": 0, "last": None,
            "input_tokens": 0, "output_tokens": 0,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
        }
    sessions = 0
    messages = 0
    last_mtime = 0.0
    inp = out = cc = cr = 0

    for jsonl in pdir.glob("*.jsonl"):
        sessions += 1
        try:
            mtime = jsonl.stat().st_mtime
            if mtime > last_mtime:
                last_mtime = mtime
            with jsonl.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") in ("user", "assistant"):
                        messages += 1
                    msg = entry.get("message") or {}
                    usage = msg.get("usage") or entry.get("usage") or {}
                    if not usage:
                        continue
                    inp += int(usage.get("input_tokens") or 0)
                    out += int(usage.get("output_tokens") or 0)
                    cc += int(usage.get("cache_creation_input_tokens") or 0)
                    cr += int(usage.get("cache_read_input_tokens") or 0)
        except OSError as e:
            log.warning("workspace_stats: skip %s (%s)", jsonl, e)
            continue

    last_iso = dt.datetime.fromtimestamp(last_mtime).isoformat(timespec="seconds") if last_mtime else None
    return {
        "sessions": sessions,
        "messages": messages,
        "last": last_iso,
        "input_tokens": inp,
        "output_tokens": out,
        "cache_creation_tokens": cc,
        "cache_read_tokens": cr,
    }


def all_stats() -> dict:
    out = {}
    for w in list_workspaces():
        out[w["id"]] = workspace_stats(w)
    return out


def sanity_check() -> dict:
    """Compare registre ↔ .mcp.json effectivement écrits dans chaque workspace."""
    # Import tardif pour éviter le cycle workspace_io ↔ api_mcps
    from dashcore.api_mcps import build_mcp_server_entry, mcp_applies_to

    env_local = load_env_local()
    registry = read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", [])
    ws_list = list_workspaces()

    findings = []
    for w in ws_list:
        ws_id = w["id"]
        expected_ids = {
            m["id"] for m in registry
            if mcp_applies_to(m, ws_id) and m.get("status") != "désactivé"
        }
        mcp_path = Path(w["path"]) / ".mcp.json"
        actual_ids = set()
        if mcp_path.exists():
            data = read_json(mcp_path, {})
            actual_ids = set((data.get("mcpServers") or {}).keys())

        missing_sync = expected_ids - actual_ids
        stale = actual_ids - expected_ids
        if missing_sync or stale:
            findings.append({
                "workspace": ws_id,
                "missing_sync": sorted(missing_sync),
                "stale": sorted(stale),
            })

    missing_env = {}
    for m in registry:
        _, miss = build_mcp_server_entry(m, env_local)
        if miss:
            missing_env[m["id"]] = miss

    return {"findings": findings, "missing_env": missing_env}
