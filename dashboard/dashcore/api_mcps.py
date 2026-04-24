"""Module extrait de server.py — ne pas éditer le script _split.py."""
from __future__ import annotations

import datetime as dt
import glob
import io
import json
import logging
import logging.handlers
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

from dashcore.config import (
    ROOT, USER_HOME, CLAUDE_HOME, CLAUDE_JSON, CLAUDE_SETTINGS, CLAUDE_PROJECTS,
    BACKUPS_DIR, JOURNAL_FILE, TEMPLATES_DIR, DASHBOARD_DIR, WORKSPACES_DIR,
    SCRIPTS_DIR, SNIPPETS_DIR, WORKSPACES_JSON, MCP_REGISTRY, ENV_FILE, LOGS_DIR,
    TEXT_EXTENSIONS, SAFE_ID, SAFE_PLUGIN_SPEC, ENV_VAR_PATTERN, BAT_UNSAFE,
    PATH_UNSAFE, STATIC_TYPES, ENV_KEY_RE, _MUTATION_LOCK, log,
    ALLOWED_TRANSPORTS, ALLOWED_STATUS,
)


from dashcore.helpers import *
from dashcore.api_workspaces import list_workspaces


def mcp_live_check(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    w = next((x for x in list_workspaces() if x["id"] == ws_id), None)
    if not w:
        return 404, {"error": "workspace absent"}
    try:
        r = subprocess.run(
            [resolve_cli("claude"), "mcp", "list"],
            cwd=w["path"], capture_output=True, text=True, timeout=10,
        )
        output = (r.stdout or "") + (r.stderr or "")
        # Parsing basique : lignes avec "name: ..."
        seen = set()
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # formats possibles : "name (transport)", "- name", "name: ..."
            m = re.match(r"^[-*]?\s*([a-zA-Z0-9_-]+)\s*[:(]", line)
            if m:
                seen.add(m.group(1))
            elif re.match(r"^[a-zA-Z0-9_-]+$", line):
                seen.add(line)

        mcp_file = Path(w["path"]) / ".mcp.json"
        expected = set()
        if mcp_file.exists():
            data = read_json(mcp_file, {})
            expected = set((data.get("mcpServers") or {}).keys())

        return 200, {
            "cli_output": output,
            "seen_by_claude": sorted(seen),
            "expected_from_mcp_json": sorted(expected),
            "only_in_claude": sorted(seen - expected),
            "only_in_file": sorted(expected - seen),
        }
    except FileNotFoundError:
        return 200, {"error": "Claude Code CLI introuvable dans le PATH"}
    except subprocess.TimeoutExpired:
        return 200, {"error": "claude mcp list a timeout (10s)"}
    except Exception as e:
        return 500, {"error": str(e)}


_INVISIBLE = re.compile(r"[​‌‍‪‫‬‭‮⁠  ﻿]")

def _si(s: str) -> str:
    """Strip invisible Unicode directional/zero-width characters from a string."""
    return _INVISIBLE.sub("", s)

def _si_list(lst: list) -> list:
    return [_si(x) if isinstance(x, str) else x for x in lst]


def clean_mcp_payload(payload: dict) -> tuple[dict, str | None]:
    mcp_id = (payload.get("id") or "").strip()
    if not safe_id(mcp_id):
        return {}, "id invalide"

    clean = {
        "id": mcp_id,
        "name": (payload.get("name") or mcp_id).strip(),
        "description": (payload.get("description") or "").strip(),
        "transport": (payload.get("transport") or "stdio").strip(),
        "command": _si((payload.get("command") or "").strip()),
        "args": _si_list(payload.get("args") or []),
        "env": payload.get("env") or {},
        "url": (payload.get("url") or "").strip(),
        "workspaces": payload.get("workspaces") or [],
        "status": (payload.get("status") or "à configurer").strip(),
        "notes": (payload.get("notes") or "").strip(),
        "author": (payload.get("author") or "").strip(),
        "source_url": (payload.get("source_url") or "").strip(),
    }
    if clean["transport"] not in ALLOWED_TRANSPORTS:
        return {}, f"transport invalide ({'/'.join(ALLOWED_TRANSPORTS)})"
    if clean["status"] not in ALLOWED_STATUS:
        return {}, f"status invalide"
    if not isinstance(clean["args"], list):
        return {}, "args doit être une liste"
    if not isinstance(clean["env"], dict):
        return {}, "env doit être un objet"
    if not isinstance(clean["workspaces"], list):
        return {}, "workspaces doit être une liste"

    clean = {k: v for k, v in clean.items() if v not in ("", [], {}, None)}
    clean["id"] = mcp_id
    return clean, None


def _workspaces_affected_by_mcp(mcp: dict) -> set:
    """Ids de workspaces visés par un MCP (gère '*' et 'all')."""
    ws = mcp.get("workspaces") or []
    all_ids = {w["id"] for w in list_workspaces()}
    if "*" in ws or "all" in ws:
        return all_ids
    return {x for x in ws if x in all_ids}


def _auto_sync(workspace_ids: set) -> dict:
    """Régénère les .mcp.json pour chaque workspace donné."""
    results = {}
    for ws_id in workspace_ids:
        try:
            _, r = sync_workspace_mcps(ws_id)
            results[ws_id] = r
        except Exception as e:
            results[ws_id] = {"error": str(e)}
    return results


def add_or_update_mcp(payload: dict) -> tuple[int, dict]:
    clean, err = clean_mcp_payload(payload)
    if err:
        return 400, {"error": err}
    data = read_json(MCP_REGISTRY, {"version": "1.0", "mcps": []})
    mcps = data.setdefault("mcps", [])
    idx = next((i for i, m in enumerate(mcps) if m.get("id") == clean["id"]), None)

    # Union des workspaces impactés (avant + après) pour ne rien oublier
    before_scopes = _workspaces_affected_by_mcp(mcps[idx]) if idx is not None else set()
    after_scopes = _workspaces_affected_by_mcp(clean)
    affected = before_scopes | after_scopes

    if idx is None:
        mcps.append(clean)
    else:
        mcps[idx] = clean
    write_json(MCP_REGISTRY, data)

    synced = _auto_sync(affected)
    return 200, {"ok": True, "id": clean["id"], "synced": sorted(synced.keys())}


def delete_mcp(mcp_id: str) -> tuple[int, dict]:
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
    data = read_json(MCP_REGISTRY, {"version": "1.0", "mcps": []})
    existing = next((m for m in data.get("mcps", []) if m.get("id") == mcp_id), None)
    if existing is None:
        return 404, {"error": "MCP absent"}

    affected = _workspaces_affected_by_mcp(existing)
    data["mcps"] = [m for m in data.get("mcps", []) if m.get("id") != mcp_id]
    write_json(MCP_REGISTRY, data)
    synced = _auto_sync(affected)
    return 200, {"ok": True, "synced": sorted(synced.keys())}


def mcp_applies_to(mcp: dict, ws_id: str) -> bool:
    ws = mcp.get("workspaces") or []
    return "*" in ws or "all" in ws or ws_id in ws


def build_mcp_server_entry(mcp: dict, env_local: dict) -> tuple[dict, list[str]]:
    """Formate une entrée `mcpServers[x]` conforme à Claude Code + liste env manquants."""
    transport = mcp.get("transport", "stdio")
    entry = {}
    missing_total = []

    if transport in ("http", "sse"):
        url, miss = substitute_env(mcp.get("url", ""), env_local)
        entry["type"] = transport
        entry["url"] = url
        missing_total.extend(miss)
    else:
        cmd, miss = substitute_env(mcp.get("command", ""), env_local)
        args, miss2 = substitute_env(mcp.get("args", []), env_local)
        if cmd and not args:
            parts = shlex.split(cmd, posix=False)
            if parts:
                cmd = parts[0]
                args = parts[1:]
        entry["command"] = cmd
        if args:
            entry["args"] = args
        missing_total.extend(miss + miss2)

    env_dict, miss3 = substitute_env(mcp.get("env", {}), env_local)
    if env_dict:
        entry["env"] = env_dict
    missing_total.extend(miss3)
    return entry, sorted(set(missing_total))


def sync_workspace_mcps(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = WORKSPACES_DIR / ws_id
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}

    env_local = load_env_local()
    registry = read_json(MCP_REGISTRY, {"mcps": []})
    mcp_servers = {}
    missing = {}
    applied = []

    for m in registry.get("mcps", []):
        if not mcp_applies_to(m, ws_id):
            continue
        if m.get("status") == "désactivé":
            continue
        entry, miss = build_mcp_server_entry(m, env_local)
        mcp_servers[m["id"]] = entry
        applied.append(m["id"])
        if miss:
            missing[m["id"]] = miss

    out_path = ws_dir / ".mcp.json"
    if mcp_servers:
        write_json(out_path, {"mcpServers": mcp_servers})
    elif out_path.exists():
        out_path.unlink()

    return 200, {"ok": True, "applied": applied, "missing_env": missing, "path": str(out_path)}


def sync_all_workspaces() -> tuple[int, dict]:
    results = {}
    for w in list_workspaces():
        _, r = sync_workspace_mcps(w["id"])
        results[w["id"]] = r
    return 200, {"ok": True, "results": results}


def workspace_mcp_status(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = WORKSPACES_DIR / ws_id
    mcp_file = ws_dir / ".mcp.json"
    data = read_json(mcp_file, None)
    active = list((data or {}).get("mcpServers", {}).keys())
    return 200, {"active": active, "has_file": mcp_file.exists()}


def test_mcp(mcp_id: str) -> tuple[int, dict]:
    registry = read_json(MCP_REGISTRY, {"mcps": []})
    mcp = next((m for m in registry.get("mcps", []) if m.get("id") == mcp_id), None)
    if not mcp:
        return 404, {"error": "MCP inconnu"}

    env_local = load_env_local()
    transport = mcp.get("transport", "stdio")

    if transport in ("http", "sse"):
        url, miss = substitute_env(mcp.get("url", ""), env_local)
        if not url:
            return 200, {"ok": False, "message": "Pas d'URL"}
        if miss:
            return 200, {"ok": False, "message": f"Variables manquantes : {', '.join(miss)}"}
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as r:
                return 200, {"ok": True, "message": f"HTTP {r.status}"}
        except Exception as e:
            return 200, {"ok": False, "message": f"Échec : {e}"}

    cmd, miss = substitute_env(mcp.get("command", ""), env_local)
    args, miss2 = substitute_env(mcp.get("args", []), env_local)
    if not cmd:
        return 200, {"ok": False, "message": "Pas de commande"}
    if miss or miss2:
        return 200, {"ok": False, "message": f"Variables manquantes : {', '.join(set(miss+miss2))}"}
    if cmd and not args:
        parts = shlex.split(cmd, posix=False)
        if parts:
            cmd, args = parts[0], parts[1:]

    # Résolution Windows : shutil.which gère .cmd/.bat/.exe
    resolved = shutil.which(cmd)
    if resolved:
        cmd = resolved
    full = [cmd] + list(args)
    try:
        start = time.time()
        # shell=True pour que Windows résolve .cmd/.bat correctement si pas déjà résolu
        use_shell = sys.platform == "win32" and not resolved
        p = subprocess.Popen(
            full if not use_shell else subprocess.list2cmdline(full),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=use_shell,
        )
        try:
            out, err = p.communicate(timeout=2.5)
            code = p.returncode
            msg = f"exit={code} ({time.time()-start:.1f}s)"
            if err:
                msg += " | stderr: " + err.decode("utf-8", "replace")[:160].replace("\n", " ")
            return 200, {"ok": code == 0, "message": msg}
        except subprocess.TimeoutExpired:
            p.kill()
            return 200, {"ok": True, "message": "Processus démarré (timeout 2.5s) — probablement OK pour un serveur MCP stdio"}
    except FileNotFoundError:
        return 200, {"ok": False, "message": f"Commande introuvable : {cmd} (npx sur Windows est 'npx.cmd' — normalement détecté, vérifie que Node.js est dans le PATH)"}
    except Exception as e:
        return 200, {"ok": False, "message": f"Erreur : {e}"}


