"""
Dashboard Claude Workspace — point d'entrée.

- Bind 127.0.0.1 uniquement (aucune exposition réseau).
- Sert dashboard/index.html et expose /api/* pour piloter le workspace.
- Aucune dépendance externe (stdlib only).

Lancement :
    python server.py                # port 4777 par défaut
    python server.py --port 4800    # port custom
    python server.py --debug        # logs DEBUG
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dashcore.config import (
    HOST, DEFAULT_PORT, DASHBOARD_DIR, WORKSPACES_JSON, MCP_REGISTRY,
    ENV_FILE, ENV_ENC_FILE, BACKUPS_DIR, SNIPPETS_DIR, LOGS_DIR, STATIC_TYPES, log,
)
from dashcore.helpers import (
    setup_logging, read_json, safe_id, load_env_local, port_free, find_port,
    set_env_var, delete_env_var, launch_script, open_target,
    is_encrypted_mode, enable_encryption, disable_encryption, env_health,
    backup_claude_config, list_backups, read_journal, append_journal, clear_journal,
    all_stats, sanity_check, global_search, cleanup_orphan_bats,
)
from dashcore.api_workspaces import (
    list_templates, duplicate_template, delete_template,
    get_template_detail, get_template_file, write_template_file,
    delete_template_file, update_template_meta,
    create_template, analyze_template_quality, preview_template_file,
    create_workspace, update_workspace, delete_workspace, duplicate_workspace,
    read_workspace_config, write_workspace_file, export_workspace, launch_resume,
    list_sessions_for_workspace, read_session_messages, read_session_tail,
    get_workspace_settings, save_workspace_settings, patch_workspace_settings,
    get_global_hooks, set_global_hooks, register_existing_workspace,
    get_hooks_errors,
)
from dashcore.api_files import (
    list_tree as fs_list_tree,
    read_file as fs_read_file,
    write_file as fs_write_file,
    delete_file as fs_delete_file,
    search_workspace as fs_search_workspace,
)
from dashcore.active_sessions import (
    list_active as list_active_sessions,
    kill as kill_active_session,
)
from dashcore.workspace_io import list_workspaces
from dashcore.api_mcps import (
    add_or_update_mcp, delete_mcp, sync_workspace_mcps, sync_all_workspaces,
    workspace_mcp_status, mcp_live_check, scan_claude_config,
    find_global_mcp_conflicts, remove_mcp_from_claude_global, migrate_global_mcp_to_registry,
    list_mcp_recipes, ensure_local_recipes_file,
    add_or_update_local_recipe, delete_local_recipe, list_mcps_with_computed_status,
)
from dashcore.system_update import system_version_info, system_apply_update, system_reset_to_upstream
from dashcore.api_ui_state import get_ui_state, patch_ui_state
from dashcore.api_reflexive import (
    stats as reflexive_stats,
    list_interactions, get_interaction,
    list_proposals, get_proposal, apply_proposal, reject_proposal,
    enable_workspace as reflexive_enable_ws,
    disable_workspace as reflexive_disable_ws,
    run_diagnostician, list_measurement_plans,
)
from dashcore.api_plugins import (
    list_plugins, list_marketplace_plugins, read_plugin_readme,
    list_installed_plugins, uninstall_plugin,
    install_plugin_cli, enable_plugin_cli, disable_plugin_cli, uninstall_plugin_cli,
    get_workspace_plugins, set_workspace_plugin,
    list_skills_global, list_skills_for_workspace,
    create_skill, delete_skill, get_skill_content, save_skill_content,
    copy_skill_to_workspace,
    preview_github_skills, import_github_skills,
    get_skill_detail, get_skill_file, write_skill_file, delete_skill_file,
    list_skill_workspace_usage,
    list_agents, list_commands,
    create_fileitem, delete_fileitem, get_fileitem_content, save_fileitem_content,
)
from dashcore.api_skills_library import (
    list_library, get_distribution, distribute, create_library_skill,
    delete_library_skill, get_library_skill_content, save_library_skill_content,
    migrate_existing_to_library,
)


# ────────────────────────────────────────────────────────────────────────────
# Helpers de handler — chaque fonction prend (query, body, *path_groups) et
# renvoie soit (status, dict), soit ('raw', headers, bytes) pour les réponses
# binaires (export ZIP).
# ────────────────────────────────────────────────────────────────────────────

# ── Workspaces ──────────────────────────────────────────────────────────────
def h_get_workspaces(q, b):       return 200, read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
def h_get_ws_mcps(q, b, ws):      return workspace_mcp_status(ws)
def h_get_ws_config(q, b, ws):    return read_workspace_config(ws)
def h_get_ws_settings(q, b, ws):  return get_workspace_settings(ws)
def h_get_ws_sessions(q, b, ws):  return 200, {"sessions": list_sessions_for_workspace(ws)}
def h_get_ws_session(q, b, ws, f): return read_session_messages(ws, f)
def h_get_ws_session_tail(q, b, ws, f):
    try: offset = int(q.get("offset", ["0"])[0])
    except (ValueError, TypeError): offset = 0
    return read_session_tail(ws, f, offset=offset)
def h_get_ws_skills(q, b, ws):    return 200, list_skills_for_workspace(ws)
def h_get_ws_plugins(q, b, ws):   return 200, {"plugins": get_workspace_plugins(ws)}
def h_get_ws_mcp_check(q, b, ws): return mcp_live_check(ws)
def h_get_ws_export(q, b, ws):
    status, data = export_workspace(ws)
    if status != 200:
        return status, data
    return 'raw', {
        "Content-Type": "application/zip",
        "Content-Disposition": f'attachment; filename="{ws}.zip"',
    }, data

def h_post_create_ws(q, b):              return create_workspace(b)
def h_post_update_ws(q, b, ws):          return update_workspace(ws, b)
def h_post_duplicate_ws(q, b):           return duplicate_workspace(b)
def h_post_sync_mcps(q, b, ws):          return sync_workspace_mcps(ws)
def h_post_save_settings(q, b, ws):      return save_workspace_settings(ws, b.get("content", "{}"))
def h_post_patch_settings(q, b, ws, sec): return patch_workspace_settings(ws, sec, b.get("value"))
def h_post_write_ws_file(q, b, ws):      return write_workspace_file(ws, b.get("filename", ""), b.get("content", ""))

# Workspace file explorer (sous-namespace /fs/ pour isoler de l'API
# scope-restreinte ci-dessus, qui ne gère que certains fichiers nommés).
# Backend api_files.py : sécurité path (_safe_resolve), backup .bak
# automatique avant write, validation JSON sur .json, mutation lock,
# tmp+replace atomique.
def h_get_ws_fs_tree(q, b, ws):
    path = (q.get("path", [""])[0] or "")
    try: depth = int(q.get("depth", ["1"])[0])
    except (ValueError, TypeError): depth = 1
    return fs_list_tree(ws, path, depth)
def h_get_ws_fs_file(q, b, ws):
    return fs_read_file(ws, q.get("path", [""])[0] or "")
def h_get_ws_fs_search(q, b, ws):
    query = q.get("q", [""])[0] or ""
    try: max_hits = int(q.get("max", ["200"])[0])
    except (ValueError, TypeError): max_hits = 200
    return fs_search_workspace(ws, query, max_hits)
def h_post_ws_fs_file(q, b, ws):
    return fs_write_file(ws, b.get("path", ""), b.get("content", ""))
def h_del_ws_fs_file(q, b, ws):
    return fs_delete_file(ws, q.get("path", [""])[0] or "")
def h_post_set_ws_plugin(q, b, ws):      return set_workspace_plugin(ws, b.get("plugin_id", ""), b.get("enabled"))
def h_post_launch(q, b, ws):
    if not safe_id(ws): return 400, {"error": "id invalide"}
    # On passe ws_id + label pour permettre le tracking dans active_sessions
    # (l'utilisateur pourra Stop la session depuis Nebula).
    ws_obj = next((x for x in list_workspaces() if x["id"] == ws), None)
    label = ws_obj.get("label") if ws_obj else None
    return launch_script(f"launch-{ws}.bat", ws_id=ws, ws_label=label)
def h_post_launch_resume(q, b, ws):      return launch_resume(ws)
def h_get_sessions_active(q, b):         return 200, {"sessions": list_active_sessions()}
def h_get_hooks_errors(q, b):
    try: tail = int(q.get("tail", ["200"])[0])
    except (ValueError, TypeError): tail = 200
    return get_hooks_errors(tail_lines=tail)
def h_post_stop_ws_session(q, b, ws):
    if not safe_id(ws): return 400, {"error": "id invalide"}
    ok, msg = kill_active_session(ws)
    return (200 if ok else 400), {"ok": ok, "message": msg}

def h_del_ws(q, b, ws):
    purge = (q.get("purge", [""])[0] or "").lower() in ("1", "true", "yes")
    return delete_workspace(ws, purge=purge)

# ── MCPs ────────────────────────────────────────────────────────────────────
def h_get_mcps(q, b):           return 200, list_mcps_with_computed_status()
def h_get_mcp_recipes(q, b):    return list_mcp_recipes()
def h_post_ensure_local_recipes(q, b):
    p = ensure_local_recipes_file()
    return 200, {"ok": True, "path": str(p), "created": True}
def h_post_local_recipe(q, b):       return add_or_update_local_recipe(b or {})
def h_del_local_recipe(q, b, rid):   return delete_local_recipe(rid)
def h_post_add_mcp(q, b):       return add_or_update_mcp(b)
def h_post_sync_all(q, b):      return sync_all_workspaces()
def h_del_mcp(q, b, mid):       return delete_mcp(mid)

# ── Conflits Claude global ─────────────────────────────────────────────────
def h_get_mcp_conflicts(q, b):  return 200, find_global_mcp_conflicts()
def h_post_remove_global_mcp(q, b):
    return remove_mcp_from_claude_global(b.get("id", ""), b.get("source", ""))
def h_post_migrate_global_mcp(q, b):
    return migrate_global_mcp_to_registry(
        b.get("id", ""), b.get("source", ""),
        b.get("workspaces") if isinstance(b.get("workspaces"), list) else None,
    )

def h_post_import_mcps(q, b):
    """Import en lot : registre direct OU format Claude {mcpServers:{...}}."""
    results = []
    ws_override = b.get("workspaces", [])
    if "id" in b:
        entries = [b]
    elif isinstance(b.get("mcps"), list):
        entries = b["mcps"]
    else:
        entries = None

    if entries is not None:
        for cfg in entries:
            mcp_id = cfg.get("id", "")
            if not safe_id(mcp_id):
                results.append({"id": mcp_id, "ok": False, "error": "id invalide"}); continue
            mcp = dict(cfg)
            if ws_override:
                mcp["workspaces"] = ws_override
            mcp.setdefault("status", "disponible")
            s, r = add_or_update_mcp(mcp)
            results.append({"id": mcp_id, "ok": s < 400, **r})
        return 200, {"ok": True, "results": results}

    servers = b.get("mcpServers") or b.get("servers") or {}
    if not isinstance(servers, dict):
        return 400, {"error": 'Format non reconnu. Coller soit un objet MCP direct (avec "id"), soit {"mcpServers":{...}}'}
    for name, cfg in servers.items():
        if not safe_id(name):
            results.append({"id": name, "ok": False, "error": "id invalide"}); continue
        mcp = {
            "id": name,
            "name": cfg.get("name", name),
            "transport": cfg.get("transport") or cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
            "command": cfg.get("command", ""),
            "args": cfg.get("args", []),
            "env": cfg.get("env", {}),
            "cwd": cfg.get("cwd", ""),
            "url": cfg.get("url", ""),
            "headers": cfg.get("headers", {}),
            "workspaces": ws_override or cfg.get("workspaces", []),
            "status": "disponible",
        }
        s, r = add_or_update_mcp(mcp)
        results.append({"id": name, "ok": s < 400, **r})
    return 200, {"ok": True, "results": results}

# ── Templates ───────────────────────────────────────────────────────────────
def h_get_templates(q, b):                  return 200, {"templates": list_templates()}
def h_get_template_detail(q, b, tid):       return get_template_detail(tid)
def h_get_template_file(q, b, tid):
    rel = q.get("path", [""])[0]
    return get_template_file(tid, rel)

def h_post_dup_template(q, b):              return duplicate_template(b)
def h_post_create_template(q, b):           return create_template(b)
def h_get_template_quality(q, b, tpl_id):   return analyze_template_quality(tpl_id)
def h_get_template_preview(q, b, tpl_id):
    rel = q.get("path", [""])[0]
    return preview_template_file(tpl_id, rel)
def h_post_template_meta(q, b, tid):        return update_template_meta(tid, b)
def h_post_template_file(q, b, tid):        return write_template_file(tid, b.get("path", ""), b.get("content", ""))

def h_del_template(q, b, tid):              return delete_template(tid)
def h_del_template_file(q, b, tid):
    rel = q.get("path", [""])[0]
    return delete_template_file(tid, rel)

# ── Skills ──────────────────────────────────────────────────────────────────
def h_get_skills(q, b):                     return 200, {"global": list_skills_global()}
def h_get_skill_detail(q, b, scope, name):  return get_skill_detail(scope, name)
def h_get_skill_content(q, b, scope, name): return get_skill_content(scope, name)
def h_get_skill_file(q, b, scope, name):
    rel = q.get("path", [""])[0]
    return get_skill_file(scope, name, rel)
def h_get_skill_usage(q, b, name):          return 200, {"workspaces": list_skill_workspace_usage(name)}

def h_post_create_skill(q, b):              return create_skill(b)
def h_post_copy_skill(q, b):                return copy_skill_to_workspace(b)
def h_post_skills_import_preview(q, b):     return preview_github_skills(b)
def h_post_skills_import(q, b):             return import_github_skills(b)

# ── Skills library (magasin) ────────────────────────────────────────────────
def h_get_skills_library(q, b):              return 200, {"skills": list_library()}
def h_get_skill_distribution(q, b, name):    return get_distribution(name)
def h_post_library_distribute(q, b, name):   return distribute(name, b.get("targets") or [])
def h_post_library_create(q, b):             return create_library_skill(b)
def h_get_library_content(q, b, name):       return get_library_skill_content(name)
def h_post_library_content(q, b, name):      return save_library_skill_content(name, b.get("content", ""))
def h_del_library_skill(q, b, name):
    also = (q.get("also_remove_distributed", ["0"])[0] == "1")
    return delete_library_skill(name, also_remove_distributed=also)
def h_post_library_migrate(q, b):            return 200, migrate_existing_to_library()
def h_post_skill_content(q, b, scope, name): return save_skill_content(scope, name, b.get("content", ""))
def h_post_skill_file(q, b, scope, name):   return write_skill_file(scope, name, b.get("path", ""), b.get("content", ""))

def h_del_skill(q, b, scope, name):         return delete_skill(scope, name)
def h_del_skill_file(q, b, scope, name):
    rel = q.get("path", [""])[0]
    return delete_skill_file(scope, name, rel)

# ── Plugins ─────────────────────────────────────────────────────────────────
def h_get_plugins(q, b):                    return 200, list_plugins()
def h_get_plugins_installed(q, b):          return 200, list_installed_plugins()
def h_get_marketplace(q, b, mid):           return 200, list_marketplace_plugins(mid)
def h_get_marketplace_readme(q, b, mid, kind, pid): return read_plugin_readme(mid, kind, pid)

def h_post_install_plugin(q, b):    return install_plugin_cli(b.get("spec", ""))
def h_post_enable_plugin(q, b):     return enable_plugin_cli(b.get("plugin_id", ""))
def h_post_disable_plugin(q, b):    return disable_plugin_cli(b.get("plugin_id", ""))
def h_post_uninstall_plugin(q, b):  return uninstall_plugin_cli(b.get("plugin_id", ""))
def h_post_uninstall_soft(q, b):    return uninstall_plugin(b.get("plugin_id", ""), remove_files=bool(b.get("remove_files")))

# ── Agents & Commands ──────────────────────────────────────────────────────
def h_get_agents(q, b):                  return 200, list_agents(None)
def h_get_commands(q, b):                return 200, list_commands(None)
def h_get_agents_ws(q, b, ws):           return 200, list_agents(ws)
def h_get_commands_ws(q, b, ws):         return 200, list_commands(ws)
def h_get_fileitem_content(q, b, kind, scope, name): return get_fileitem_content(kind, scope, name)

def h_post_create_agent(q, b):           return create_fileitem("agents", b)
def h_post_create_command(q, b):         return create_fileitem("commands", b)
def h_post_fileitem_content(q, b, kind, scope, name): return save_fileitem_content(kind, scope, name, b.get("content", ""))

def h_del_fileitem(q, b, kind, scope, name): return delete_fileitem(kind, scope, name)

# ── Système (env, journal, backups, snippets, hooks, search, stats) ─────────
def h_get_env(q, b):
    env = load_env_local()
    health = env_health()
    enc = health["encrypted"]
    active_file = str(ENV_ENC_FILE) if enc else str(ENV_FILE)
    exists = ENV_ENC_FILE.exists() if enc else ENV_FILE.exists()
    return 200, {"keys": sorted(env.keys()), "file": active_file, "exists": exists,
                 "encrypted": enc, "decryption_error": health.get("error")}
def h_get_env_values(q, b):
    env = load_env_local()
    health = env_health()
    enc = health["encrypted"]
    active_file = str(ENV_ENC_FILE) if enc else str(ENV_FILE)
    exists = ENV_ENC_FILE.exists() if enc else ENV_FILE.exists()
    return 200, {"values": env, "file": active_file, "exists": exists,
                 "encrypted": enc, "decryption_error": health.get("error")}
def h_get_snippets(q, b):
    out = {}
    if SNIPPETS_DIR.exists():
        for f in SNIPPETS_DIR.glob("*.md"):
            out[f.stem] = f.read_text(encoding="utf-8")
    return 200, out
def h_get_stats(q, b):           return 200, all_stats()
def h_get_sanity(q, b):          return 200, sanity_check()
def h_get_backups(q, b):         return 200, {"dir": str(BACKUPS_DIR), "items": list_backups()}
def h_get_journal(q, b):         return 200, {"entries": read_journal()[-100:]}
def h_get_hooks_global(q, b):    return 200, {"hooks": get_global_hooks()}
def h_get_search(q, b):
    return 200, global_search(q.get("q", [""])[0])
def h_get_setup_scan(q, b):      return scan_claude_config()
def h_get_ui_state(q, b):        return get_ui_state()
def h_post_ui_state(q, b):       return patch_ui_state(b)
# ── Reflexive ───────────────────────────────────────────────────────────────
def h_get_reflexive_stats(q, b):                 return reflexive_stats(q)
def h_get_reflexive_interactions(q, b):          return list_interactions(q)
def h_get_reflexive_interaction(q, b, iid):      return get_interaction(iid)
def h_get_reflexive_proposals(q, b):             return list_proposals(q)
def h_get_reflexive_proposal(q, b, pid):         return get_proposal(pid)
def h_get_reflexive_measurement_plans(q, b):     return list_measurement_plans(q)
def h_post_reflexive_apply(q, b, pid):           return apply_proposal(pid, b or {})
def h_post_reflexive_reject(q, b, pid):          return reject_proposal(pid, b or {})
def h_post_reflexive_ws_enable(q, b, ws):        return reflexive_enable_ws(ws, b or {})
def h_post_reflexive_ws_disable(q, b, ws):       return reflexive_disable_ws(ws, b or {})
def h_post_reflexive_diagnostician(q, b):        return run_diagnostician(b or {})

def h_get_system_version(q, b):
    check = (q.get("check", ["0"])[0] or "0") == "1"
    return 200, system_version_info(check_remote=check)
def h_post_system_update(q, b):  return system_apply_update()
def h_post_system_reset(q, b):   return system_reset_to_upstream()

def h_post_set_env(q, b):        return set_env_var(b.get("key", ""), b.get("value", ""))
def h_post_env_encrypt(q, b):    return enable_encryption()
def h_post_env_decrypt(q, b):    return disable_encryption()
def h_post_open(q, b):           return open_target(b.get("target", ""))
def h_post_backup(q, b):         return backup_claude_config()
def h_post_cleanup_bats(q, b):   return 200, cleanup_orphan_bats()
def h_post_journal(q, b):
    text = (b.get("text", "") or "").strip()
    if not text:
        return 400, {"error": "texte vide"}
    append_journal(text)
    return 200, {"ok": True}
def h_post_hooks_global(q, b):   return set_global_hooks(b.get("hooks") or {})

def h_post_setup_import(q, b):
    """Import combiné MCPs + workspaces (depuis le wizard d'onboarding)."""
    mcps = b.get("mcps", [])
    projects = b.get("projects", [])
    mcp_results, ws_results = [], []
    for mcp in mcps:
        mcp.setdefault("status", "disponible")
        s, r = add_or_update_mcp(mcp)
        mcp_results.append({"id": mcp.get("id"), "ok": s < 400, **r})
    for proj in projects:
        requested = proj.get("id")
        s, r = register_existing_workspace(proj)
        ws_results.append({"requested_id": requested, "ok": s < 400, **r})
    return 200, {"ok": True, "mcps": mcp_results, "workspaces": ws_results}

def h_del_env(q, b, key):        return delete_env_var(key)
def h_del_journal(q, b):
    clear_journal()
    return 200, {"ok": True}


# ────────────────────────────────────────────────────────────────────────────
# Table de routes — l'ordre compte pour les regex qui se chevauchent (le plus
# spécifique d'abord, ex. /content avant /<name>).
# Format : (regex compilée, handler)
# ────────────────────────────────────────────────────────────────────────────

_ID = r"[a-zA-Z0-9_-]+"
_SCOPE = r"global|workspace:[a-zA-Z0-9_-]+"
_KIND_FILEITEM = r"agents|commands"

ROUTES_GET = [
    # Workspaces
    (re.compile(rf"^/api/workspaces$"),                                                     h_get_workspaces),
    (re.compile(rf"^/api/workspaces/({_ID})/mcps$"),                                        h_get_ws_mcps),
    (re.compile(rf"^/api/workspaces/({_ID})/config$"),                                      h_get_ws_config),
    (re.compile(rf"^/api/workspaces/({_ID})/settings$"),                                    h_get_ws_settings),
    (re.compile(rf"^/api/workspaces/({_ID})/sessions$"),                                    h_get_ws_sessions),
    (re.compile(rf"^/api/workspaces/({_ID})/sessions/([^/]+)/tail$"),                       h_get_ws_session_tail),
    (re.compile(rf"^/api/workspaces/({_ID})/sessions/([^/]+)$"),                            h_get_ws_session),
    (re.compile(rf"^/api/workspaces/({_ID})/skills$"),                                      h_get_ws_skills),
    (re.compile(rf"^/api/workspaces/({_ID})/plugins$"),                                     h_get_ws_plugins),
    (re.compile(rf"^/api/workspaces/({_ID})/mcp-check$"),                                   h_get_ws_mcp_check),
    (re.compile(rf"^/api/workspaces/({_ID})/export$"),                                      h_get_ws_export),
    # Sessions actives (registre PID des cmd lancees depuis Nebula)
    (re.compile(rf"^/api/sessions/active$"),                                                h_get_sessions_active),
    # Workspace file explorer (lecture)
    (re.compile(rf"^/api/workspaces/({_ID})/fs/tree$"),                                     h_get_ws_fs_tree),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/file$"),                                     h_get_ws_fs_file),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/search$"),                                   h_get_ws_fs_search),
    # MCPs
    (re.compile(rf"^/api/mcps$"),                                                           h_get_mcps),
    (re.compile(rf"^/api/mcps/recipes$"),                                                   h_get_mcp_recipes),
    (re.compile(rf"^/api/mcps/conflicts$"),                                                 h_get_mcp_conflicts),
    # Templates
    (re.compile(rf"^/api/templates$"),                                                      h_get_templates),
    (re.compile(rf"^/api/templates/({_ID})/file$"),                                         h_get_template_file),
    (re.compile(rf"^/api/templates/({_ID})/quality$"),                                      h_get_template_quality),
    (re.compile(rf"^/api/templates/({_ID})/preview$"),                                      h_get_template_preview),
    (re.compile(rf"^/api/templates/({_ID})$"),                                              h_get_template_detail),
    # Skills
    (re.compile(rf"^/api/skills$"),                                                         h_get_skills),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/content$"),                              h_get_skill_content),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/file$"),                                 h_get_skill_file),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})$"),                                      h_get_skill_detail),
    (re.compile(rf"^/api/skills/({_ID})/usage$"),                                           h_get_skill_usage),
    # Skills library (magasin)
    (re.compile(rf"^/api/skills-library$"),                                                 h_get_skills_library),
    (re.compile(rf"^/api/skills-library/({_ID})/distribution$"),                            h_get_skill_distribution),
    (re.compile(rf"^/api/skills-library/({_ID})/content$"),                                 h_get_library_content),
    # Plugins
    (re.compile(rf"^/api/plugins$"),                                                        h_get_plugins),
    (re.compile(rf"^/api/plugins/installed$"),                                              h_get_plugins_installed),
    (re.compile(rf"^/api/plugins/marketplace/({_ID})/(plugins|external_plugins)/({_ID})/readme$"), h_get_marketplace_readme),
    (re.compile(rf"^/api/plugins/marketplace/({_ID})$"),                                    h_get_marketplace),
    # Agents & commands
    (re.compile(rf"^/api/agents$"),                                                         h_get_agents),
    (re.compile(rf"^/api/commands$"),                                                       h_get_commands),
    (re.compile(rf"^/api/agents/workspace/({_ID})$"),                                       h_get_agents_ws),
    (re.compile(rf"^/api/commands/workspace/({_ID})$"),                                     h_get_commands_ws),
    (re.compile(rf"^/api/({_KIND_FILEITEM})/({_SCOPE})/({_ID})/content$"),                  h_get_fileitem_content),
    # Système
    (re.compile(rf"^/api/env$"),                                                            h_get_env),
    (re.compile(rf"^/api/env/values$"),                                                     h_get_env_values),
    (re.compile(rf"^/api/snippets$"),                                                       h_get_snippets),
    (re.compile(rf"^/api/stats$"),                                                          h_get_stats),
    (re.compile(rf"^/api/sanity-check$"),                                                   h_get_sanity),
    (re.compile(rf"^/api/backups$"),                                                        h_get_backups),
    (re.compile(rf"^/api/journal$"),                                                        h_get_journal),
    (re.compile(rf"^/api/hooks/global$"),                                                   h_get_hooks_global),
    (re.compile(rf"^/api/hooks/errors$"),                                                   h_get_hooks_errors),
    (re.compile(rf"^/api/search$"),                                                         h_get_search),
    (re.compile(rf"^/api/setup/scan$"),                                                     h_get_setup_scan),
    (re.compile(rf"^/api/ui-state$"),                                                       h_get_ui_state),
    (re.compile(rf"^/api/system/version$"),                                                 h_get_system_version),
    # Reflexive
    (re.compile(rf"^/api/reflexive/stats$"),                                                h_get_reflexive_stats),
    (re.compile(rf"^/api/reflexive/interactions$"),                                         h_get_reflexive_interactions),
    (re.compile(rf"^/api/reflexive/interactions/(\d+)$"),                                   h_get_reflexive_interaction),
    (re.compile(rf"^/api/reflexive/proposals$"),                                            h_get_reflexive_proposals),
    (re.compile(rf"^/api/reflexive/proposals/(\d+)$"),                                      h_get_reflexive_proposal),
    (re.compile(rf"^/api/reflexive/measurement-plans$"),                                    h_get_reflexive_measurement_plans),
]

ROUTES_POST = [
    # Workspaces
    (re.compile(rf"^/api/workspaces$"),                                                     h_post_create_ws),
    (re.compile(rf"^/api/workspaces/duplicate$"),                                           h_post_duplicate_ws),
    (re.compile(rf"^/api/workspaces/({_ID})/update$"),                                      h_post_update_ws),
    (re.compile(rf"^/api/workspaces/({_ID})/sync-mcps$"),                                   h_post_sync_mcps),
    (re.compile(rf"^/api/workspaces/({_ID})/settings$"),                                    h_post_save_settings),
    (re.compile(rf"^/api/workspaces/({_ID})/settings/([a-zA-Z]+)$"),                        h_post_patch_settings),
    (re.compile(rf"^/api/workspaces/({_ID})/file$"),                                        h_post_write_ws_file),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/file$"),                                     h_post_ws_fs_file),
    (re.compile(rf"^/api/workspaces/({_ID})/plugins$"),                                     h_post_set_ws_plugin),
    (re.compile(rf"^/api/launch/({_ID})$"),                                                 h_post_launch),
    (re.compile(rf"^/api/launch-resume/({_ID})$"),                                          h_post_launch_resume),
    (re.compile(rf"^/api/workspaces/({_ID})/stop$"),                                        h_post_stop_ws_session),
    # MCPs
    (re.compile(rf"^/api/mcps$"),                                                           h_post_add_mcp),
    (re.compile(rf"^/api/mcps/import$"),                                                    h_post_import_mcps),
    (re.compile(rf"^/api/mcps/recipes/ensure-local$"),                                      h_post_ensure_local_recipes),
    (re.compile(rf"^/api/mcps/recipes/local$"),                                             h_post_local_recipe),
    (re.compile(rf"^/api/mcps/conflicts/remove$"),                                          h_post_remove_global_mcp),
    (re.compile(rf"^/api/mcps/conflicts/migrate$"),                                         h_post_migrate_global_mcp),
    (re.compile(rf"^/api/sync-all$"),                                                       h_post_sync_all),
    # Templates
    (re.compile(rf"^/api/templates/duplicate$"),                                            h_post_dup_template),
    (re.compile(rf"^/api/templates$"),                                                      h_post_create_template),
    (re.compile(rf"^/api/templates/({_ID})/meta$"),                                         h_post_template_meta),
    (re.compile(rf"^/api/templates/({_ID})/file$"),                                         h_post_template_file),
    # Skills
    (re.compile(rf"^/api/skills$"),                                                         h_post_create_skill),
    (re.compile(rf"^/api/skills/copy$"),                                                    h_post_copy_skill),
    (re.compile(rf"^/api/skills/import/preview$"),                                          h_post_skills_import_preview),
    (re.compile(rf"^/api/skills/import$"),                                                  h_post_skills_import),
    # Skills library (magasin)
    (re.compile(rf"^/api/skills-library$"),                                                 h_post_library_create),
    (re.compile(rf"^/api/skills-library/migrate$"),                                         h_post_library_migrate),
    (re.compile(rf"^/api/skills-library/({_ID})/distribute$"),                              h_post_library_distribute),
    (re.compile(rf"^/api/skills-library/({_ID})/content$"),                                 h_post_library_content),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/content$"),                              h_post_skill_content),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/file$"),                                 h_post_skill_file),
    # Plugins
    (re.compile(rf"^/api/plugins/install$"),                                                h_post_install_plugin),
    (re.compile(rf"^/api/plugins/enable$"),                                                 h_post_enable_plugin),
    (re.compile(rf"^/api/plugins/disable$"),                                                h_post_disable_plugin),
    (re.compile(rf"^/api/plugins/uninstall$"),                                              h_post_uninstall_plugin),
    (re.compile(rf"^/api/plugins/uninstall-soft$"),                                         h_post_uninstall_soft),
    # Agents & commands
    (re.compile(rf"^/api/agents$"),                                                         h_post_create_agent),
    (re.compile(rf"^/api/commands$"),                                                       h_post_create_command),
    (re.compile(rf"^/api/({_KIND_FILEITEM})/({_SCOPE})/({_ID})/content$"),                  h_post_fileitem_content),
    # Système
    (re.compile(rf"^/api/env$"),                                                            h_post_set_env),
    (re.compile(rf"^/api/env/encrypt$"),                                                    h_post_env_encrypt),
    (re.compile(rf"^/api/env/decrypt$"),                                                    h_post_env_decrypt),
    (re.compile(rf"^/api/open$"),                                                           h_post_open),
    (re.compile(rf"^/api/backup$"),                                                         h_post_backup),
    (re.compile(rf"^/api/cleanup/orphan-bats$"),                                            h_post_cleanup_bats),
    (re.compile(rf"^/api/journal$"),                                                        h_post_journal),
    (re.compile(rf"^/api/hooks/global$"),                                                   h_post_hooks_global),
    (re.compile(rf"^/api/setup/import$"),                                                   h_post_setup_import),
    (re.compile(rf"^/api/ui-state$"),                                                       h_post_ui_state),
    (re.compile(rf"^/api/system/update$"),                                                  h_post_system_update),
    (re.compile(rf"^/api/system/reset$"),                                                   h_post_system_reset),
    # Reflexive
    (re.compile(rf"^/api/reflexive/proposals/(\d+)/apply$"),                                h_post_reflexive_apply),
    (re.compile(rf"^/api/reflexive/proposals/(\d+)/reject$"),                               h_post_reflexive_reject),
    (re.compile(rf"^/api/reflexive/workspace/({_ID})/enable$"),                             h_post_reflexive_ws_enable),
    (re.compile(rf"^/api/reflexive/workspace/({_ID})/disable$"),                            h_post_reflexive_ws_disable),
    (re.compile(rf"^/api/reflexive/diagnostician/run$"),                                    h_post_reflexive_diagnostician),
]

ROUTES_DELETE = [
    (re.compile(rf"^/api/workspaces/({_ID})$"),                                             h_del_ws),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/file$"),                                     h_del_ws_fs_file),
    (re.compile(rf"^/api/mcps/recipes/local/({_ID})$"),                                     h_del_local_recipe),
    (re.compile(rf"^/api/mcps/({_ID})$"),                                                   h_del_mcp),
    (re.compile(rf"^/api/env/(.+)$"),                                                       h_del_env),
    (re.compile(rf"^/api/journal$"),                                                        h_del_journal),
    (re.compile(rf"^/api/templates/({_ID})/file$"),                                         h_del_template_file),
    (re.compile(rf"^/api/templates/({_ID})$"),                                              h_del_template),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/file$"),                                 h_del_skill_file),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})$"),                                      h_del_skill),
    (re.compile(rf"^/api/skills-library/({_ID})$"),                                         h_del_library_skill),
    (re.compile(rf"^/api/({_KIND_FILEITEM})/({_SCOPE})/({_ID})$"),                          h_del_fileitem),
]

ROUTES_BY_METHOD = {
    "GET": ROUTES_GET,
    "POST": ROUTES_POST,
    "DELETE": ROUTES_DELETE,
}


# ────────────────────────────────────────────────────────────────────────────
# Handler HTTP — dispatch via la table, fallback static pour les fichiers.
# ────────────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            # Le client a fermé la connexion avant la fin de la réponse
            # (refresh navigateur, navigation, fetch annulé). Pas un vrai
            # bug — log en debug pour ne pas polluer.
            log.debug("Client a fermé la connexion : %s", e)
        except Exception:
            log.exception("Unhandled exception in request handler")
            try:
                self._send_json(500, {"error": "internal server error"})
            except Exception:
                pass

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_raw(self, headers: dict, data: bytes):
        self.send_response(200)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self._send_json(404, {"error": "not found"}); return
        try:
            path.resolve().relative_to(DASHBOARD_DIR.resolve())
        except ValueError:
            self._send_json(403, {"error": "forbidden"}); return
        ct = STATIC_TYPES.get(path.suffix.lower(), "application/octet-stream")
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length < 0 or length > self.MAX_BODY_BYTES:
            return None
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    # Routes qui exposent des données sensibles : exigent un header custom
    # qui ne peut pas être posé par <form>, <img>, <link>… (anti-CSRF basique
    # même si on est sur 127.0.0.1).
    _SENSITIVE_ROUTES = {"/api/env/values", "/api/env/encrypt", "/api/env/decrypt"}
    # Préfixes dont les mutations (POST/DELETE) exigent X-Nebula-XHR.
    # Les GET restent libres (lectures inoffensives).
    _SENSITIVE_PREFIXES = ("/api/reflexive/",)

    def _dispatch(self, method: str, body=None):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        needs_csrf = path in self._SENSITIVE_ROUTES or (
            method in ("POST", "DELETE")
            and any(path.startswith(p) for p in self._SENSITIVE_PREFIXES)
        )
        if needs_csrf and self.headers.get("X-Nebula-XHR") != "1":
            self._send_json(403, {"error": "header X-Nebula-XHR requis"}); return

        for pat, handler in ROUTES_BY_METHOD.get(method, []):
            mat = pat.match(path)
            if not mat:
                continue
            try:
                result = handler(query, body, *mat.groups())
            except Exception:
                log.exception("Erreur handler %s %s", method, path)
                self._send_json(500, {"error": "internal error"}); return
            # Réponse "raw" (export ZIP) : ('raw', headers_dict, bytes)
            if isinstance(result, tuple) and len(result) == 3 and result[0] == 'raw':
                self._send_raw(result[1], result[2]); return
            # Réponse standard (status, payload)
            status, payload = result
            self._send_json(status, payload); return

        # Aucune route ne correspond
        if method == "GET":
            self._serve_static(path); return
        self._send_json(404, {"error": "route inconnue"})

    def _serve_static(self, path: str):
        if path in ("/", "/index.html"):
            self._send_file(DASHBOARD_DIR / "index.html"); return
        rel = path.lstrip("/")
        if not rel or ".." in rel.split("/") or "\\" in rel:
            self._send_json(404, {"error": "not found"}); return
        self._send_file(DASHBOARD_DIR / rel)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        body = self._read_json_body()
        if body is None:
            self._send_json(400, {"error": "JSON invalide"}); return
        self._dispatch("POST", body)

    def do_DELETE(self):
        self._dispatch("DELETE")


# ────────────────────────────────────────────────────────────────────────────
# Lancement
# ────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--debug", action="store_true", help="Active le niveau DEBUG")
    args = ap.parse_args()

    setup_logging(logging.DEBUG if args.debug else logging.INFO)

    port = args.port
    if not port_free(HOST, port):
        new = find_port(HOST, port + 1)
        log.warning("Port %d occupé → fallback sur %d", port, new)
        port = new

    server = ThreadingHTTPServer((HOST, port), Handler)
    url = f"http://{HOST}:{port}/"
    log.info("Dashboard Claude Workspace — %s", url)
    log.info("  registry : %s", MCP_REGISTRY)
    log.info("  .env.local : %s  (%s)", ENV_FILE, "présent" if ENV_FILE.exists() else "absent")
    log.info("  logs : %s", LOGS_DIR / "dashboard.log")
    log.info("Ctrl+C pour arrêter.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Arrêt demandé (Ctrl+C).")
        server.shutdown()


if __name__ == "__main__":
    main()
