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


from dashcore.helpers import (
    load_env_local, read_json, resolve_cli, resolve_ws_dir, safe_id,
    substitute_env, write_json,
)
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
            encoding="utf-8", errors="replace",
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
        "cwd": _si((payload.get("cwd") or "").strip()),
        "url": (payload.get("url") or "").strip(),
        "headers": payload.get("headers") or {},
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
    if not isinstance(clean["headers"], dict):
        return {}, "headers doit être un objet"
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
    with _MUTATION_LOCK:
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
    with _MUTATION_LOCK:
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
        # Headers HTTP/SSE (Authorization, X-API-Key, etc.) avec interpolation ${VAR}
        headers_dict, miss_h = substitute_env(mcp.get("headers", {}), env_local)
        if headers_dict:
            entry["headers"] = headers_dict
        missing_total.extend(miss_h)
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
        # cwd : working directory du process MCP (avec interpolation ${VAR})
        cwd_val, miss_cwd = substitute_env(mcp.get("cwd", ""), env_local)
        if cwd_val:
            entry["cwd"] = cwd_val
        missing_total.extend(miss + miss2 + miss_cwd)

    env_dict, miss3 = substitute_env(mcp.get("env", {}), env_local)
    if env_dict:
        entry["env"] = env_dict
    missing_total.extend(miss3)
    return entry, sorted(set(missing_total))


def sync_workspace_mcps(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = resolve_ws_dir(ws_id)
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
    ws_dir = resolve_ws_dir(ws_id)
    mcp_file = ws_dir / ".mcp.json"
    data = read_json(mcp_file, None)
    active = list((data or {}).get("mcpServers", {}).keys())
    return 200, {"active": active, "has_file": mcp_file.exists()}


def test_mcp(mcp_id: str) -> tuple[int, dict]:
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
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
    if not resolved:
        return 200, {"ok": False, "message": f"Commande introuvable : {cmd} (npx sur Windows est 'npx.cmd' — vérifie que Node.js est dans le PATH)"}
    full = [resolved] + list(args)
    try:
        start = time.time()
        # shell=False systématique : args en liste, pas d'interprétation shell
        p = subprocess.Popen(
            full,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False,
        )
        try:
            _out, err = p.communicate(timeout=2.5)
            code = p.returncode
            msg = f"exit={code} ({time.time()-start:.1f}s)"
            if err:
                msg += " | stderr: " + err.decode("utf-8", "replace")[:160].replace("\n", " ")
            return 200, {"ok": code == 0, "message": msg}
        except subprocess.TimeoutExpired:
            p.kill()
            return 200, {"ok": True, "message": "Processus démarré (timeout 2.5s) — probablement OK pour un serveur MCP stdio"}
    except Exception as e:
        return 200, {"ok": False, "message": f"Erreur : {e}"}


# ── Setup / Import wizard ─────────────────────────────────────────────────────

def _read_cwd_from_sessions(proj_dir: Path) -> str | None:
    """Lit le `cwd` d'un message dans les fichiers .jsonl du projet.

    Source de vérité : Claude Code stocke le chemin original (`cwd`) dans
    chaque message utilisateur. Plus fiable que tout décodage du nom de dossier,
    et fonctionne même si le dossier source a été supprimé/renommé/déplacé.
    """
    for jl in proj_dir.glob("*.jsonl"):
        try:
            with jl.open("r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i > 50:  # cwd se trouve quasi-toujours dans les 5 premières lignes
                        break
                    line = line.strip()
                    if not line or '"cwd"' not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cwd = obj.get("cwd")
                    if isinstance(cwd, str) and cwd:
                        return cwd
        except OSError:
            continue
    return None


def _decode_project_path(name: str) -> tuple[str, bool]:
    """Décode best-effort un nom de dossier ~/.claude/projects/ en chemin Windows.

    Fallback uniquement : utilisé quand aucune session ne contient de `cwd`.
    Le décodage est ambigu (`:`, `\\`, espaces tous encodés en `-`) — on tente
    un DFS avec vérification d'existence pour résoudre l'ambiguïté.
    Retourne (chemin, existe_sur_disque).
    """
    m = re.match(r'^([A-Za-z])--(.*)$', name)
    if not m:
        return "", False
    drive = m.group(1).upper() + ":\\"
    parts = [p for p in m.group(2).split('-') if p]
    if not parts:
        base = drive.rstrip("\\")
        return base, Path(base).exists()

    def dfs(idx: int, segs: list[str]) -> list[str] | None:
        if idx == len(parts):
            return segs if Path(drive + "\\".join(segs)).exists() else None
        seg = parts[idx]
        # Option A : nouveau segment de chemin
        r = dfs(idx + 1, segs + [seg])
        if r is not None:
            return r
        if segs:
            # Option B : tiret littéral (ex: reverse-engineering)
            r = dfs(idx + 1, segs[:-1] + [segs[-1] + "-" + seg])
            if r is not None:
                return r
            # Option C : espace littéral (Claude encode aussi les espaces en -)
            r = dfs(idx + 1, segs[:-1] + [segs[-1] + " " + seg])
            if r is not None:
                return r
        return None

    found = dfs(1, [parts[0]])
    if found:
        return drive + "\\".join(found), True
    # Fallback naïf (chemin probablement incorrect mais utile comme point de départ)
    return drive + "\\".join(parts), False


CLAUDE_GLOBAL_SOURCES = (
    USER_HOME / ".claude.json",
    CLAUDE_SETTINGS,
    CLAUDE_HOME / "settings.local.json",
)


def find_global_mcp_conflicts() -> dict:
    """Détecte les MCPs présents à la fois dans la config Claude globale et dans le registre Atelier.

    Pour chaque MCP du registre, on regarde s'il existe une entrée homonyme dans
    `~/.claude.json`, `~/.claude/settings.json` ou `~/.claude/settings.local.json`.
    Les doublons créent une config zombie : Atelier sync vers le `.mcp.json` du
    workspace, mais l'entrée globale reste et peut diverger silencieusement.
    """
    registry = read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", [])
    registry_ids = {m["id"]: m for m in registry}

    conflicts = []
    for src in CLAUDE_GLOBAL_SOURCES:
        if not src.exists():
            continue
        try:
            data = read_json(src, {})
        except Exception:
            continue
        servers = (data.get("mcpServers") or {})
        if not isinstance(servers, dict):
            continue
        for name, cfg in servers.items():
            if name in registry_ids:
                conflicts.append({
                    "id": name,
                    "source": str(src),
                    "source_label": src.name,
                    "registry_status": registry_ids[name].get("status", "à configurer"),
                    "registry_workspaces": registry_ids[name].get("workspaces", []),
                    "global_command": cfg.get("command", ""),
                    "global_url": cfg.get("url", ""),
                    "global_transport": cfg.get("type") or cfg.get("transport") or ("http" if cfg.get("url") else "stdio"),
                })

    # MCPs uniquement dans la config globale (jamais importés dans Atelier)
    orphans = []
    for src in CLAUDE_GLOBAL_SOURCES:
        if not src.exists():
            continue
        try:
            data = read_json(src, {})
        except Exception:
            continue
        servers = (data.get("mcpServers") or {})
        if not isinstance(servers, dict):
            continue
        for name, cfg in servers.items():
            if name not in registry_ids:
                orphans.append({
                    "id": name,
                    "source": str(src),
                    "source_label": src.name,
                    "transport": cfg.get("type") or cfg.get("transport") or ("http" if cfg.get("url") else "stdio"),
                    "command": cfg.get("command", ""),
                    "url": cfg.get("url", ""),
                })

    return {
        "conflicts": conflicts,
        "orphans": orphans,
        "sources": [str(s) for s in CLAUDE_GLOBAL_SOURCES if s.exists()],
    }


def remove_mcp_from_claude_global(mcp_id: str, source: str) -> tuple[int, dict]:
    """Retire un MCP d'un fichier de config Claude globale (avec backup automatique)."""
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
    # Vérifie que le source est bien un des fichiers autorisés (anti-traversal)
    src_path = Path(source).resolve()
    allowed = [s.resolve() for s in CLAUDE_GLOBAL_SOURCES]
    if src_path not in allowed:
        return 400, {"error": "source non autorisée"}
    if not src_path.exists():
        return 404, {"error": "fichier introuvable"}

    with _MUTATION_LOCK:
        try:
            data = read_json(src_path, {}) or {}
        except Exception as e:
            return 500, {"error": f"lecture impossible : {e}"}
        servers = data.get("mcpServers") or {}
        if mcp_id not in servers:
            return 404, {"error": f"MCP '{mcp_id}' absent de {src_path.name}"}
        # Backup
        bak = src_path.with_suffix(src_path.suffix + ".bak")
        bak.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")
        # Retrait
        del servers[mcp_id]
        if servers:
            data["mcpServers"] = servers
        else:
            data.pop("mcpServers", None)
        write_json(src_path, data)
        log.info("global mcp cleanup: removed %s from %s", mcp_id, src_path.name)
        return 200, {"ok": True, "backup": str(bak)}


def migrate_global_mcp_to_registry(mcp_id: str, source: str, workspaces: list | None = None) -> tuple[int, dict]:
    """Importe un MCP de la config globale dans le registre Atelier puis le retire de la source.

    Pour les "orphelins" — MCPs présents dans ~/.claude/settings.json mais pas
    dans le registre. Évite la double action import + cleanup manuel.
    """
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
    src_path = Path(source).resolve()
    allowed = [s.resolve() for s in CLAUDE_GLOBAL_SOURCES]
    if src_path not in allowed:
        return 400, {"error": "source non autorisée"}
    if not src_path.exists():
        return 404, {"error": "fichier introuvable"}

    data = read_json(src_path, {}) or {}
    servers = data.get("mcpServers") or {}
    if mcp_id not in servers:
        return 404, {"error": f"MCP '{mcp_id}' absent de {src_path.name}"}
    cfg = servers[mcp_id]

    payload = {
        "id": mcp_id,
        "name": cfg.get("name", mcp_id),
        "transport": cfg.get("transport") or cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
        "command": cfg.get("command", ""),
        "args": cfg.get("args", []),
        "env": cfg.get("env", {}),
        "cwd": cfg.get("cwd", ""),
        "url": cfg.get("url", ""),
        "headers": cfg.get("headers", {}),
        "workspaces": workspaces or [],
        "status": "disponible",
    }
    s, r = add_or_update_mcp(payload)
    if s >= 400:
        return s, r
    # Retire de la source seulement après import OK
    s2, r2 = remove_mcp_from_claude_global(mcp_id, source)
    if s2 >= 400:
        return s2, {"warning": "MCP importé mais nettoyage source échoué", **r2}
    return 200, {"ok": True, "imported": mcp_id, "removed_from": str(src_path.name)}


def scan_claude_config() -> tuple[int, dict]:
    """Scanne ~/.claude/ pour détecter MCPs et projets existants.

    Utilisé par le wizard d'import initial : permet à un nouvel utilisateur
    de pré-remplir le dashboard depuis sa config Claude Code existante.
    """
    result: dict = {"mcps": [], "projects": []}

    # ── MCPs ─────────────────────────────────────────────────────────────────
    existing_ids = {m["id"] for m in read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", [])}
    seen: set[str] = set()

    for sf in (CLAUDE_SETTINGS, CLAUDE_HOME / "settings.local.json"):
        if not sf.exists():
            continue
        servers = (read_json(sf, {}).get("mcpServers") or {})
        for name, cfg in servers.items():
            if name in seen:
                continue
            seen.add(name)
            result["mcps"].append({
                "id": name,
                "name": name,
                "transport": cfg.get("transport") or cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "env": cfg.get("env", {}),
                "cwd": cfg.get("cwd", ""),
                "url": cfg.get("url", ""),
                "headers": cfg.get("headers", {}),
                "already_registered": name in existing_ids,
            })

    # ── Projets ───────────────────────────────────────────────────────────────
    if not CLAUDE_PROJECTS.exists():
        return 200, result

    existing_paths = {
        w.get("path", "").lower()
        for w in read_json(WORKSPACES_JSON, {"workspaces": []}).get("workspaces", [])
    }

    for proj_dir in sorted(CLAUDE_PROJECTS.iterdir()):
        if not proj_dir.is_dir():
            continue
        sessions = list(proj_dir.glob("*.jsonl"))
        if not sessions:
            continue
        # Source de vérité prioritaire : le cwd stocké dans les sessions
        path = _read_cwd_from_sessions(proj_dir)
        source = "session"
        if not path:
            # Fallback : DFS sur le nom de dossier (ambigu mais souvent correct)
            path, _ = _decode_project_path(proj_dir.name)
            source = "decoded"
        path_exists = bool(path) and Path(path).exists()
        last_mod = max(s.stat().st_mtime for s in sessions)
        result["projects"].append({
            "encoded": proj_dir.name,
            "path": path or "",
            "path_exists": path_exists,
            "path_source": source,
            "sessions": len(sessions),
            "already_registered": (path or "").lower() in existing_paths,
            "last_modified": last_mod,
        })

    result["projects"].sort(key=lambda x: x["last_modified"], reverse=True)
    return 200, result
