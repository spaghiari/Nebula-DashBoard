"""
Dashboard Claude Workspace — point d'entrée.

- Bind 127.0.0.1 par défaut (aucune exposition réseau) ; NEBULA_HOST /
  --host pour un autre hôte (avertissement au démarrage).
- Sert dashboard/index.html et expose /api/* pour piloter le workspace.
- Aucune dépendance externe (stdlib only).

Lancement :
    python server.py                # port 4777 par défaut
    python server.py --port 4800    # port custom
    python server.py --debug        # logs DEBUG
    python3 server.py               # Linux / macOS (lancement de console = Windows)

Variables d'environnement : NEBULA_PORT, NEBULA_HOST, NEBULA_ALLOWED_HOSTS,
NEBULA_DATA_DIR, ATELIER_ROOT (cf. dashcore/config.py et README).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import socket
import socketserver
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dashcore.config import (
    HOST, DEFAULT_PORT, DASHBOARD_DIR, MCP_REGISTRY,
    EXTRA_ALLOWED_HOSTS, CONFIG_WARNINGS, DATA_DIR, DATA_DIR_IS_CUSTOM, is_loopback_host,
    ENV_FILE, ENV_ENC_FILE, BACKUPS_DIR, SNIPPETS_DIR, LOGS_DIR, STATIC_TYPES, log,
)
from dashcore.helpers import CorruptJsonError
from dashcore.env_local import EnvStoreUnreadable
from dashcore.helpers import (
    setup_logging, safe_id, load_env_local, port_free, find_port,
    set_env_var, delete_env_var, launch_script, open_target,
    enable_encryption, disable_encryption, env_health,
    export_plain_text,
    backup_claude_config, list_backups, restore_backup, read_journal, append_journal, clear_journal,
    all_stats, sanity_check, cleanup_orphan_bats,
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
    get_hooks_errors, get_hooks_backup, restore_hooks_backup,
    inspect_workspace_path, adopt_workspace,
    inspect_parent_folder, adopt_workspaces_bulk,
)
from dashcore.folder_picker import picker_capability, pick_folder
from dashcore.api_overlays import (
    list_overlays, apply_overlay, overlay_is_active, overlays_usage,
    overlay_vars, remove_overlay,
)
from dashcore.api_team import team_state, improvement_state
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
from dashcore.workspace_io import (
    list_workspaces, list_workspaces_with_status, workspaces_overview,
    record_stats_history, stats_history,
)
from dashcore.api_mcps import (
    add_or_update_mcp, delete_mcp, sync_workspace_mcps, sync_all_workspaces,
    workspace_mcp_status, mcp_live_check, diagnose_mcp, scan_claude_config,
    find_global_mcp_conflicts, remove_mcp_from_claude_global, migrate_global_mcp_to_registry,
    list_mcp_recipes, ensure_local_recipes_file,
    add_or_update_local_recipe, delete_local_recipe, list_mcps_with_computed_status,
    export_mcps_claude_format, resolve_scanned_mcp,
)
from dashcore.system_update import (
    system_version_info, system_apply_update, system_reset_to_upstream,
    system_recover_stash, system_drop_stash, system_prune_stashes,
    _list_nebula_stashes,
)
from dashcore.api_ui_state import get_ui_state, patch_ui_state
from dashcore.plugin_updates import plugin_updates, refresh_marketplaces
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
    get_library_skill_detail, get_library_skill_file,
    write_library_skill_file, delete_library_skill_file,
)


# ────────────────────────────────────────────────────────────────────────────
# Helpers de handler — chaque fonction prend (query, body, *path_groups) et
# renvoie soit (status, dict), soit ('raw', headers, bytes) pour les réponses
# binaires (export ZIP).
# ────────────────────────────────────────────────────────────────────────────

# ── Workspaces ──────────────────────────────────────────────────────────────
def h_get_workspaces(q, b):       return 200, list_workspaces_with_status()
def h_get_overview(q, b):         return 200, workspaces_overview()
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
def h_post_ws_export(q, b, ws):
    """ZIP du workspace (contient des secrets) : servi uniquement en POST,
    donc derrière le garde anti-CSRF (X-Nebula-XHR + Origin)."""
    status, data = export_workspace(ws)
    if status != 200:
        return status, data
    return 'raw', {
        "Content-Type": "application/zip",
        "Content-Disposition": f'attachment; filename="{ws}.zip"',
        "Cache-Control": "no-store",
    }, data

def h_post_create_ws(q, b):              return create_workspace(b)
def h_post_update_ws(q, b, ws):          return update_workspace(ws, b)
def h_post_duplicate_ws(q, b):           return duplicate_workspace(b)
def h_post_inspect_path(q, b):           return inspect_workspace_path(b or {})
def h_post_adopt_ws(q, b):               return adopt_workspace(b or {})
def h_post_inspect_parent(q, b):         return inspect_parent_folder(b or {})
def h_post_adopt_bulk(q, b):             return adopt_workspaces_bulk(b or {})
def h_get_pick_folder(q, b):             return picker_capability()
def h_post_pick_folder(q, b):            return pick_folder(b or {})
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
    ws_path = ws_obj.get("path") if ws_obj else None
    return launch_script(f"launch-{ws}.bat", ws_id=ws, ws_label=label, ws_path=ws_path)
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
def h_get_mcp_export(q, b):     return export_mcps_claude_format()
def h_get_mcp_diagnose(q, b, mid): return diagnose_mcp(mid)
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

    # Récap created/overwritten : un import bulk écrasait un id existant en
    # silence (audit UX Lot G item 2). On distingue désormais explicitement
    # les ids créés des ids écrasés pour que le front prévienne l'utilisateur.
    def _summary(rs):
        return {
            "ok": True,
            "results": rs,
            "created": sorted(x["id"] for x in rs if x.get("ok") and x.get("action") == "created"),
            "overwritten": sorted(x["id"] for x in rs if x.get("ok") and x.get("action") == "overwritten"),
        }

    if entries is not None:
        for cfg in entries:
            # F6.1 : une entrée non-dict (string, nombre, null...) ferait planter
            # cfg.get() en 500 opaque. On rejette explicitement par entrée (400).
            if not isinstance(cfg, dict):
                results.append({"id": None, "ok": False, "error": "entrée invalide (objet attendu)"}); continue
            mcp_id = cfg.get("id", "")
            if not safe_id(mcp_id):
                results.append({"id": mcp_id, "ok": False, "error": "id invalide"}); continue
            mcp = dict(cfg)
            if ws_override:
                mcp["workspaces"] = ws_override
            mcp.setdefault("status", "disponible")
            s, r = add_or_update_mcp(mcp)
            results.append({"id": mcp_id, "ok": s < 400, **r})
        return 200, _summary(results)

    servers = b.get("mcpServers") or b.get("servers") or {}
    if not isinstance(servers, dict):
        return 400, {"error": 'Format non reconnu. Coller soit un objet MCP direct (avec "id"), soit {"mcpServers":{...}}'}
    for name, cfg in servers.items():
        if not safe_id(name):
            results.append({"id": name, "ok": False, "error": "id invalide"}); continue
        # F6.1 : même garde sur le format Claude {mcpServers:{"x": <non-dict>}}.
        if not isinstance(cfg, dict):
            results.append({"id": name, "ok": False, "error": "config invalide (objet attendu)"}); continue
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
    return 200, _summary(results)

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

# -- Overlays ----------------------------------------------------------------
# Un overlay est un paquet de fichiers applique PAR-DESSUS un template
# (ex. claude-self-improving). Cf. dashcore/api_overlays.py pour le marker
# `.nebula-overlay.json` et la logique d'idempotence.
def h_get_overlays(q, b):
    """Liste les overlays disponibles + usage {overlay_id: [ws_id actifs]}
    (section « Modules » de la page Templates)."""
    return 200, {"overlays": list_overlays(), "usage": overlays_usage()}

# Module claude-team (cf. dashcore/api_team.py) : manifeste + agents
# generes, et etat de la boucle d'amelioration (onglet « Amelioration »).
def h_get_ws_team(q, b, ws):        return team_state(ws)

def h_post_ws_team_routing(q, b, ws):
    """Routage always-on du module claude-team : `{"mode": "manuel|assiste|auto",
    "review_gate": "always|from_3_files|never"}` (chaque cle optionnelle),
    ecrit dans `.claude/team.json` (section `routing`, posee par defaut si
    absente). Reponse : `routing` a jour. Aucune regeneration des agents."""
    if not safe_id(ws):
        return 400, {"error": "id invalide"}
    from dashcore.helpers import resolve_ws_dir as _resolve
    ws_dir = _resolve(ws)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}
    b = b or {}
    from dashcore.api_team import set_routing
    return set_routing(ws_dir, mode=b.get("mode"), review_gate=b.get("review_gate"))

def h_get_ws_overlays(q, b, ws):
    """Pour un workspace donne, indique pour chaque overlay s'il est deja
    actif (heuristique via signature_file). Sert au front a savoir s'il
    affiche un bouton « Activer » ou un badge « Active »."""
    if not safe_id(ws):
        return 400, {"error": "id invalide"}
    from dashcore.helpers import resolve_ws_dir as _resolve
    ws_dir = _resolve(ws)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}
    out = []
    for ov in list_overlays():
        entry = {**ov, "active": overlay_is_active(ws_dir, ov)}
        # Module claude-team actif : prefixe des agents generes (team.prefix
        # persiste, sinon id du workspace) pour pre-remplir la modale.
        if entry["active"] and "team_agents" in (ov.get("generators") or []):
            from dashcore.api_team import effective_prefix, load_manifest, routing_state
            manifest = load_manifest(ws_dir)
            entry["prefix"] = effective_prefix(manifest, {"name": ws})
            # Routage always-on : mode / gate affiches et modifiables sur la
            # ligne du module (onglet Configuration), sans requete en plus.
            entry["routing"] = routing_state(manifest)
        out.append(entry)
    return 200, {"overlays": out}

def h_post_apply_overlay(q, b, ws, ov_id):
    """Applique un overlay sur un workspace existant (idempotent).

    Le corps POST porte les choix de bootstrap (cf. modale front) :
      { "mode": "solo|equipe|equipe-hierarchique",
        "depth": "minimal|complete",
        "language": "fr|en|...",
        "author": "<identifiant>" }
    Tous optionnels : apply_overlay normalise/defaute (cf.
    _normalize_options). Le mode-gating et la profondeur sont ensuite
    appliques cote api_overlays a partir du marker .nebula-overlay.json.
    """
    if not safe_id(ws):
        return 400, {"error": "id invalide"}
    # On reutilise les memes vars que create_workspace pour que les
    # placeholders ({{name}}, {{label}}, etc.) soient substitues coherament.
    ws_obj = next((x for x in list_workspaces() if x["id"] == ws), None)
    if not ws_obj:
        return 404, {"error": "workspace absent du registre"}
    vars = overlay_vars(ws_obj)
    b = b or {}
    options = {
        "mode": b.get("mode"),
        "depth": b.get("depth"),
        "language": b.get("language"),
        "author": b.get("author"),
        # Generateur team_agents (claude-team) : modele par role, defaut,
        # regeneration des agents generes (cf. api_team.normalize_team_options).
        "models": b.get("models"),
        "default_model": b.get("default_model"),
        "regenerate": b.get("regenerate"),
        # Prefixe des agents generes (safe_id, defaut = id du workspace,
        # persiste dans .claude/team.json `team.prefix`).
        "prefix": b.get("prefix"),
    }
    return apply_overlay(ws, ov_id, vars, options)

def h_post_remove_overlay(q, b, ws, ov_id):
    """Retire un module d'un workspace (cf. api_overlays.remove_overlay) :
    `{"dry_run": bool, "plan_id": str|null, "keep_living": bool, "force": bool}`.
    Apercu d'abord (dry_run, aucune ecriture, rend `plan_id`), puis execution
    avec ce `plan_id` (409 s'il est absent ou perime). Rien n'est supprime :
    tout part dans `.claude/.nebula-removed/<module>-<horodatage>/`."""
    if not safe_id(ws):
        return 400, {"error": "id invalide"}
    ws_obj = next((x for x in list_workspaces() if x["id"] == ws), None)
    if not ws_obj:
        return 404, {"error": "workspace absent du registre"}
    b = b or {}
    plan_id = b.get("plan_id")
    options = {
        "dry_run": b.get("dry_run") is True,
        "plan_id": plan_id if isinstance(plan_id, str) else None,
        "keep_living": b.get("keep_living") is True,
        "force": b.get("force") is True,
    }
    return remove_overlay(ws, ov_id, overlay_vars(ws_obj), options)

def h_post_ws_team_agents_config(q, b, ws):
    """Modele et effort par agent claude-team : `{"agents": {"<id>": {"model":
    "...", "effort": "...|null"}}}` ecrit dans `.claude/team.json` puis
    regeneration des agents generes (jamais un agent edite a la main)."""
    if not safe_id(ws):
        return 400, {"error": "id invalide"}
    ws_obj = next((x for x in list_workspaces() if x["id"] == ws), None)
    if not ws_obj:
        return 404, {"error": "workspace absent du registre"}
    from dashcore.api_team import set_agents_config
    return set_agents_config(ws, (b or {}).get("agents"), overlay_vars(ws_obj))

# ── Boucle d'amélioration automatique (Nebula 2.6.0) ─────────────────────────
# Jobs de fond (dashcore/improve_jobs.py) et mode automatique
# (dashcore/improve_scheduler.py). Les POST passent par la garde CSRF
# globale de `_dispatch` (aucune exemption).
_IMPROVE_RUN_KINDS = ("iteration", "measure", "resolve")
_IMPROVE_HISTORY_POLL = 5


def _improve_scheduler():
    """Module du planificateur, ou None s'il est absent ou ne s'importe pas
    (le reste de la boucle reste utilisable : jobs manuels)."""
    try:
        from dashcore import improve_scheduler
    except Exception as e:  # noqa: BLE001 - planificateur optionnel
        log.warning("planificateur de la boucle indisponible : %s", e)
        return None
    return improve_scheduler


def _improve_target(ws):
    """(ws_dir, None) si le workspace existe et que claude-team y est actif,
    sinon (None, (status, payload))."""
    if not safe_id(ws):
        return None, (400, {"error": "id invalide"})
    from dashcore.helpers import resolve_ws_dir as _resolve
    from dashcore.api_team import load_manifest
    ws_dir = _resolve(ws)
    if not ws_dir.exists():
        return None, (404, {"error": "workspace absent sur disque"})
    if load_manifest(ws_dir) is None:
        return None, (404, {"error": "module claude-team inactif sur ce workspace"})
    return ws_dir, None


def _improve_live(ws, state=None):
    """(job, auto, job_en_cours) : dernier job, vue du mode automatique
    (None si le planificateur est indisponible), job si en cours."""
    from dashcore import improve_jobs
    job = improve_jobs.get_job(ws)
    sched = _improve_scheduler()
    auto = None
    if sched is not None:
        try:
            auto = sched.auto_view(ws, state)
        except Exception:  # noqa: BLE001 - vue dégradée plutôt qu'un 500
            log.exception("auto_view %s", ws)
    running = job if isinstance(job, dict) and job.get("status") == "running" else None
    return job, auto, running


def h_get_ws_improvement(q, b, ws):
    """État de la boucle (cf. api_team.improvement_state) enrichi du job
    (`job`), du mode automatique (`auto`) et de `next_step` recalculé."""
    status, payload = improvement_state(ws)
    if status != 200:
        return status, payload
    from dashcore.api_team import next_step
    job, auto, running = _improve_live(ws, payload)
    payload["job"] = job
    payload["auto"] = auto
    payload["next_step"] = next_step(payload, running, auto)
    return 200, payload


def h_get_ws_improvement_job(q, b, ws):
    """Vue légère pour un polling (3 s) : job, 5 derniers jobs, auto, next_step."""
    if not safe_id(ws):
        return 400, {"error": "id invalide"}
    status, state = improvement_state(ws)
    if status != 200:
        return status, state
    from dashcore import improve_jobs
    from dashcore.api_team import next_step
    job, auto, running = _improve_live(ws, state)
    return 200, {"job": job, "history": improve_jobs.list_history(ws, _IMPROVE_HISTORY_POLL),
                 "auto": auto, "next_step": next_step(state, running, auto)}


def _force_session(b) -> bool:
    """Passe outre la garde de session : `force_session`, ou `force` (ancien nom)."""
    b = b or {}
    return b.get("force_session") is True or b.get("force") is True


def h_post_ws_improvement_run(q, b, ws):
    """`{"kind": "iteration|measure|resolve", "force_session"?: bool}` : lance
    un job de fond (plafond IMPROVE_MAX_USD_PER_ITERATION borné par le reste du
    jour, jamais contournable). `force_session` (ou `force`, ancien nom) passe
    seulement outre la garde de session. Codes de start_job."""
    ws_dir, err = _improve_target(ws)
    if err:
        return err
    b = b or {}
    kind = b.get("kind")
    if kind not in _IMPROVE_RUN_KINDS:
        return 400, {"ok": False, "reason": "kind",
                     "error": f"kind invalide (attendu : {', '.join(_IMPROVE_RUN_KINDS)})"}
    from dashcore import improve_jobs
    from dashcore.config import IMPROVE_MAX_USD_PER_DAY, IMPROVE_MAX_USD_PER_ITERATION
    force = _force_session(b)
    if improve_jobs.spent_today() >= IMPROVE_MAX_USD_PER_DAY:
        return 409, {"ok": False, "reason": "daily_budget",
                     "error": (f"plafond de coût du jour atteint ({IMPROVE_MAX_USD_PER_DAY:g} $ estimés) : "
                               "réessaie demain")}
    from dashcore import improve_scheduler
    max_usd = min(IMPROVE_MAX_USD_PER_ITERATION, improve_scheduler.day_capped_max_usd())
    return improve_jobs.start_job(
        ws, ws_dir, kind, max_usd=max_usd, force=force,
        exclude_session_ids=improve_scheduler.recent_job_session_ids(ws))


def h_post_ws_improvement_abandon(q, b, ws):
    """Abandonne l'itération en attente de verdict (job `abandon`)."""
    ws_dir, err = _improve_target(ws)
    if err:
        return err
    from dashcore import improve_jobs
    from dashcore.config import IMPROVE_MAX_USD_PER_ITERATION
    from dashcore import improve_scheduler
    return improve_jobs.start_job(
        ws, ws_dir, "abandon", max_usd=IMPROVE_MAX_USD_PER_ITERATION,
        force=_force_session(b),
        exclude_session_ids=improve_scheduler.recent_job_session_ids(ws))


def h_post_ws_improvement_stop(q, b, ws):
    """Arrêt : annule le job en cours et désactive le mode automatique.
    200 même si rien ne tournait (`cancelled: false`)."""
    _, err = _improve_target(ws)
    if err:
        return err
    from dashcore import improve_jobs
    status, res = improve_jobs.cancel_job(ws)
    cancelled = status == 202
    out = {"ok": True, "cancelled": cancelled, "job": res.get("job") if cancelled else improve_jobs.get_job(ws)}
    sched = _improve_scheduler()
    if sched is None:
        out["auto"] = None
        out["auto_error"] = "planificateur indisponible"
        return 200, out
    a_status, a_res = sched.set_auto(ws, enabled=False)
    if a_status != 200:
        out["auto_error"] = str((a_res or {}).get("error") or "désactivation impossible")
    # Un seul improvement_state : auto_view le relirait sinon.
    st_status, state = improvement_state(ws)
    try:
        out["auto"] = sched.auto_view(ws, state if st_status == 200 else {})
    except Exception:  # noqa: BLE001
        log.exception("auto_view %s", ws)
        out["auto"] = None
    return 200, out


def h_post_ws_improvement_auto(q, b, ws):
    """`{"enabled"?, "daily_budget"?, "resume"?}` : réglage du mode automatique."""
    _, err = _improve_target(ws)
    if err:
        return err
    b = b or {}
    enabled = b.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        return 400, {"ok": False, "error": "enabled : booléen attendu"}
    budget = b.get("daily_budget")
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int)):
        return 400, {"ok": False, "error": "daily_budget : entier attendu (1 à 10)"}
    sched = _improve_scheduler()
    if sched is None:
        return 503, {"ok": False, "error": "planificateur de la boucle indisponible"}
    return sched.set_auto(ws, enabled=enabled, daily_budget=budget, resume=b.get("resume") is True)


def h_get_claude_subscription(q, b):
    """Abonnement Claude détecté (champs de subscription_info seulement, jamais
    de jeton) + avertissements de consommation pour les agents du workspace
    `?ws=<id>` (liste vide sans `ws`) + table CONSUMPTION_RULES."""
    from dashcore import claude_account
    from dashcore.config import CONSUMPTION_RULES
    ws = (q.get("ws") or [""])[0]
    if ws and not safe_id(ws):
        return 400, {"error": "id invalide"}
    info = claude_account.subscription_info()
    warnings = []
    if ws:
        status, team = team_state(ws)
        if status != 200:
            return status, team
        agents = [{"id": a.get("id"), "model": a.get("effective_model") or a.get("model"),
                   "effort": a.get("effective_effort")} for a in team.get("agents") or []]
        auto_on = False
        sched = _improve_scheduler()
        if sched is not None and team.get("active"):
            try:
                auto_on = bool((sched.get_auto(ws) or {}).get("enabled"))
            except Exception:  # noqa: BLE001
                log.exception("get_auto %s", ws)
        warnings = claude_account.consumption_warnings(
            info.get("plan") or "unknown", agents, auto=auto_on, conflict=bool(info.get("conflict")))
    return 200, {**info, "warnings": warnings, "rules": [dict(r) for r in CONSUMPTION_RULES]}

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
def h_get_library_detail(q, b, name):        return get_library_skill_detail(name)
def h_get_library_file(q, b, name):
    rel = q.get("path", [""])[0]
    return get_library_skill_file(name, rel)
def h_post_library_file(q, b, name):         return write_library_skill_file(name, b.get("path", ""), b.get("content", ""))
def h_del_library_file(q, b, name):
    rel = q.get("path", [""])[0]
    return delete_library_skill_file(name, rel)
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
# Installé vs clone local du marketplace (aucun réseau) ; rafraîchissement du
# clone à la demande via `claude plugin marketplace update`.
def h_get_plugins_outdated(q, b):   return 200, plugin_updates()
def h_post_refresh_marketplaces(q, b): return refresh_marketplaces(b.get("name") or None)

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
def h_get_stats(q, b):
    stats = all_stats()
    # Historique quotidien (sparklines de l'Accueil) : best-effort, ne doit
    # jamais faire échouer /api/stats.
    try:
        record_stats_history(stats)
    except OSError as e:
        log.warning("Historique des stats non enregistré : %s", e)
    return 200, stats
def h_get_stats_history(q, b):   return 200, stats_history()
def h_get_sanity(q, b):          return 200, sanity_check()
def h_get_backups(q, b):         return 200, {"dir": str(BACKUPS_DIR), "items": list_backups()}
def h_get_journal(q, b):         return 200, {"entries": read_journal()[-100:]}
def h_get_hooks_global(q, b):    return 200, {"hooks": get_global_hooks()}
def h_get_hooks_backup(q, b):            return get_hooks_backup(None)
def h_get_ws_hooks_backup(q, b, ws):     return get_hooks_backup(ws)
def h_get_setup_scan(q, b):      return scan_claude_config()
def h_get_ui_state(q, b):        return get_ui_state()
def h_post_ui_state(q, b):       return patch_ui_state(b)

def h_get_system_version(q, b):
    check = (q.get("check", ["0"])[0] or "0") == "1"
    return 200, system_version_info(check_remote=check)
def h_post_system_update(q, b):  return system_apply_update()
def h_post_system_reset(q, b):   return system_reset_to_upstream()
def h_get_system_stashes(q, b):  return 200, {"stashes": _list_nebula_stashes()}
def h_post_system_stash_recover(q, b): return system_recover_stash()
def h_post_system_stash_drop(q, b): return system_drop_stash((b or {}).get("ref", ""))
def h_post_system_stash_prune(q, b):
    b = b or {}
    return system_prune_stashes(refs=b.get("refs"), keep=int(b.get("keep", 3)))

def h_post_set_env(q, b):        return set_env_var(b.get("key", ""), b.get("value", ""))
def h_post_env_encrypt(q, b):    return enable_encryption()
def h_post_env_decrypt(q, b):    return disable_encryption()
def h_get_env_export_plain(q, b):
    """Sert le contenu env courant en clair en pièce jointe (filet anti-perte
    de clé DPAPI). Route SENSIBLE : exige X-Nebula-XHR (cf. _SENSITIVE_ROUTES).
    Le téléchargement est toujours déclenché explicitement par l'utilisateur,
    jamais automatique."""
    status, payload = export_plain_text()
    if status != 200:
        return status, payload
    ts = time.strftime("%Y%m%d-%H%M%S")
    return 'raw', {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": f'attachment; filename="env.local.clair.{ts}.txt"',
        "Cache-Control": "no-store",
    }, payload.encode("utf-8")
def h_post_open(q, b):           return open_target(b.get("target", ""))
def h_post_backup(q, b):         return backup_claude_config()
def h_post_backup_restore(q, b): return restore_backup(b.get("name", ""))
def h_post_cleanup_bats(q, b):   return 200, cleanup_orphan_bats()
def h_post_journal(q, b):
    text = (b.get("text", "") or "").strip()
    if not text:
        return 400, {"error": "texte vide"}
    append_journal(text)
    return 200, {"ok": True}
def h_post_hooks_global(q, b):   return set_global_hooks(b.get("hooks") or {})
def h_post_hooks_restore(q, b):          return restore_hooks_backup(None)
def h_post_ws_hooks_restore(q, b, ws):   return restore_hooks_backup(ws)

def h_post_setup_import(q, b):
    """Import combiné MCPs + workspaces (depuis le wizard d'onboarding).

    F3.2 : le scan ne renvoie plus les valeurs sensibles (env/headers/url) au
    front. Quand un MCP porte un champ `source` (fichier de config Claude
    d'origine, validé anti-traversal par resolve_scanned_mcp), on RE-LIT ses
    valeurs réelles côté serveur -- elles n'ont jamais transité par le client.
    Sans `source` (import manuel direct), comportement historique conservé.
    """
    mcps = b.get("mcps", [])
    projects = b.get("projects", [])
    mcp_results, ws_results = [], []
    for mcp in mcps:
        source = mcp.get("source")
        if source:
            cfg = resolve_scanned_mcp(mcp.get("id", ""), source)
            if cfg is None:
                mcp_results.append({"id": mcp.get("id"), "ok": False,
                                    "error": "source introuvable ou non autorisée"})
                continue
            mcp = {
                "id": mcp.get("id", ""),
                "name": mcp.get("name") or mcp.get("id", ""),
                "transport": cfg.get("transport") or cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "env": cfg.get("env", {}),
                "cwd": cfg.get("cwd", ""),
                "url": cfg.get("url", ""),
                "headers": cfg.get("headers", {}),
                "workspaces": mcp.get("workspaces", []),
            }
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
    (re.compile(r"^/api/workspaces$"),                                                     h_get_workspaces),
    (re.compile(r"^/api/overview$"),                                                       h_get_overview),
    (re.compile(rf"^/api/workspaces/({_ID})/mcps$"),                                        h_get_ws_mcps),
    (re.compile(rf"^/api/workspaces/({_ID})/config$"),                                      h_get_ws_config),
    (re.compile(rf"^/api/workspaces/({_ID})/settings$"),                                    h_get_ws_settings),
    (re.compile(rf"^/api/workspaces/({_ID})/sessions$"),                                    h_get_ws_sessions),
    (re.compile(rf"^/api/workspaces/({_ID})/sessions/([^/]+)/tail$"),                       h_get_ws_session_tail),
    (re.compile(rf"^/api/workspaces/({_ID})/sessions/([^/]+)$"),                            h_get_ws_session),
    (re.compile(rf"^/api/workspaces/({_ID})/skills$"),                                      h_get_ws_skills),
    (re.compile(rf"^/api/workspaces/({_ID})/plugins$"),                                     h_get_ws_plugins),
    (re.compile(rf"^/api/workspaces/({_ID})/mcp-check$"),                                   h_get_ws_mcp_check),
    # Sessions actives (registre PID des cmd lancees depuis Nebula)
    (re.compile(r"^/api/sessions/active$"),                                                h_get_sessions_active),
    # Workspace file explorer (lecture)
    (re.compile(rf"^/api/workspaces/({_ID})/fs/tree$"),                                     h_get_ws_fs_tree),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/file$"),                                     h_get_ws_fs_file),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/search$"),                                   h_get_ws_fs_search),
    # MCPs
    (re.compile(r"^/api/mcps$"),                                                           h_get_mcps),
    (re.compile(r"^/api/mcps/export$"),                                                    h_get_mcp_export),
    (re.compile(r"^/api/mcps/recipes$"),                                                   h_get_mcp_recipes),
    (re.compile(r"^/api/mcps/conflicts$"),                                                 h_get_mcp_conflicts),
    (re.compile(rf"^/api/mcps/({_ID})/diagnose$"),                                          h_get_mcp_diagnose),
    # Templates
    (re.compile(r"^/api/templates$"),                                                      h_get_templates),
    (re.compile(rf"^/api/templates/({_ID})/file$"),                                         h_get_template_file),
    (re.compile(rf"^/api/templates/({_ID})/quality$"),                                      h_get_template_quality),
    (re.compile(rf"^/api/templates/({_ID})/preview$"),                                      h_get_template_preview),
    (re.compile(rf"^/api/templates/({_ID})$"),                                              h_get_template_detail),
    # Overlays (paquets de fichiers appliques par-dessus un template, cf.
    # dashcore/api_overlays.py)
    (re.compile(r"^/api/overlays$"),                                                       h_get_overlays),
    (re.compile(rf"^/api/workspaces/({_ID})/overlays$"),                                    h_get_ws_overlays),
    # Module claude-team (dashcore/api_team.py)
    (re.compile(rf"^/api/workspaces/({_ID})/team$"),                                        h_get_ws_team),
    (re.compile(rf"^/api/workspaces/({_ID})/improvement$"),                                 h_get_ws_improvement),
    (re.compile(rf"^/api/workspaces/({_ID})/improvement/job$"),                             h_get_ws_improvement_job),
    (re.compile(r"^/api/claude/subscription$"),                                            h_get_claude_subscription),
    # Skills
    (re.compile(r"^/api/skills$"),                                                         h_get_skills),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/content$"),                              h_get_skill_content),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/file$"),                                 h_get_skill_file),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})$"),                                      h_get_skill_detail),
    (re.compile(rf"^/api/skills/({_ID})/usage$"),                                           h_get_skill_usage),
    # Skills library (magasin)
    (re.compile(r"^/api/skills-library$"),                                                 h_get_skills_library),
    (re.compile(rf"^/api/skills-library/({_ID})/distribution$"),                            h_get_skill_distribution),
    (re.compile(rf"^/api/skills-library/({_ID})/content$"),                                 h_get_library_content),
    (re.compile(rf"^/api/skills-library/({_ID})/file$"),                                    h_get_library_file),
    (re.compile(rf"^/api/skills-library/({_ID})/detail$"),                                  h_get_library_detail),
    # Plugins
    (re.compile(r"^/api/plugins$"),                                                        h_get_plugins),
    (re.compile(r"^/api/plugins/installed$"),                                              h_get_plugins_installed),
    (re.compile(r"^/api/plugins/outdated$"),                                               h_get_plugins_outdated),
    (re.compile(rf"^/api/plugins/marketplace/({_ID})/(plugins|external_plugins)/({_ID})/readme$"), h_get_marketplace_readme),
    (re.compile(rf"^/api/plugins/marketplace/({_ID})$"),                                    h_get_marketplace),
    # Agents & commands
    (re.compile(r"^/api/agents$"),                                                         h_get_agents),
    (re.compile(r"^/api/commands$"),                                                       h_get_commands),
    (re.compile(rf"^/api/agents/workspace/({_ID})$"),                                       h_get_agents_ws),
    (re.compile(rf"^/api/commands/workspace/({_ID})$"),                                     h_get_commands_ws),
    (re.compile(rf"^/api/({_KIND_FILEITEM})/({_SCOPE})/({_ID})/content$"),                  h_get_fileitem_content),
    # Système
    (re.compile(r"^/api/env$"),                                                            h_get_env),
    (re.compile(r"^/api/env/values$"),                                                     h_get_env_values),
    (re.compile(r"^/api/env/export-plain$"),                                               h_get_env_export_plain),
    (re.compile(r"^/api/snippets$"),                                                       h_get_snippets),
    (re.compile(r"^/api/stats$"),                                                          h_get_stats),
    (re.compile(r"^/api/stats/history$"),                                                  h_get_stats_history),
    (re.compile(r"^/api/sanity-check$"),                                                   h_get_sanity),
    (re.compile(r"^/api/backups$"),                                                        h_get_backups),
    (re.compile(r"^/api/journal$"),                                                        h_get_journal),
    (re.compile(r"^/api/hooks/global$"),                                                   h_get_hooks_global),
    (re.compile(r"^/api/hooks/backup$"),                                                   h_get_hooks_backup),
    (re.compile(rf"^/api/workspaces/({_ID})/hooks/backup$"),                                h_get_ws_hooks_backup),
    (re.compile(r"^/api/hooks/errors$"),                                                   h_get_hooks_errors),
    (re.compile(r"^/api/setup/scan$"),                                                     h_get_setup_scan),
    (re.compile(r"^/api/ui-state$"),                                                       h_get_ui_state),
    (re.compile(r"^/api/system/version$"),                                                 h_get_system_version),
    (re.compile(r"^/api/system/pick-folder$"),                                             h_get_pick_folder),
    (re.compile(r"^/api/system/stashes$"),                                                 h_get_system_stashes),
]

ROUTES_POST = [
    # Workspaces
    (re.compile(r"^/api/workspaces$"),                                                     h_post_create_ws),
    (re.compile(r"^/api/workspaces/inspect-path$"),                                        h_post_inspect_path),
    (re.compile(r"^/api/workspaces/adopt$"),                                               h_post_adopt_ws),
    (re.compile(r"^/api/workspaces/inspect-parent$"),                                      h_post_inspect_parent),
    (re.compile(r"^/api/workspaces/adopt-bulk$"),                                          h_post_adopt_bulk),
    # Sélecteur de dossier natif (ouvre une fenêtre sur le poste du serveur)
    (re.compile(r"^/api/system/pick-folder$"),                                             h_post_pick_folder),
    (re.compile(r"^/api/workspaces/duplicate$"),                                           h_post_duplicate_ws),
    (re.compile(rf"^/api/workspaces/({_ID})/update$"),                                      h_post_update_ws),
    (re.compile(rf"^/api/workspaces/({_ID})/sync-mcps$"),                                   h_post_sync_mcps),
    # Export ZIP en POST : le zip contient des secrets (.mcp.json résolus,
    # settings…). POST = X-Nebula-XHR + Origin exigés, donc ni un <a href>,
    # ni une navigation cross-site ne peuvent le déclencher.
    (re.compile(rf"^/api/workspaces/({_ID})/export$"),                                      h_post_ws_export),
    (re.compile(rf"^/api/workspaces/({_ID})/settings$"),                                    h_post_save_settings),
    (re.compile(rf"^/api/workspaces/({_ID})/settings/([a-zA-Z]+)$"),                        h_post_patch_settings),
    (re.compile(rf"^/api/workspaces/({_ID})/file$"),                                        h_post_write_ws_file),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/file$"),                                     h_post_ws_fs_file),
    (re.compile(rf"^/api/workspaces/({_ID})/plugins$"),                                     h_post_set_ws_plugin),
    (re.compile(rf"^/api/launch/({_ID})$"),                                                 h_post_launch),
    (re.compile(rf"^/api/launch-resume/({_ID})$"),                                          h_post_launch_resume),
    (re.compile(rf"^/api/workspaces/({_ID})/stop$"),                                        h_post_stop_ws_session),
    # MCPs
    (re.compile(r"^/api/mcps$"),                                                           h_post_add_mcp),
    (re.compile(r"^/api/mcps/import$"),                                                    h_post_import_mcps),
    (re.compile(r"^/api/mcps/recipes/ensure-local$"),                                      h_post_ensure_local_recipes),
    (re.compile(r"^/api/mcps/recipes/local$"),                                             h_post_local_recipe),
    (re.compile(r"^/api/mcps/conflicts/remove$"),                                          h_post_remove_global_mcp),
    (re.compile(r"^/api/mcps/conflicts/migrate$"),                                         h_post_migrate_global_mcp),
    (re.compile(r"^/api/sync-all$"),                                                       h_post_sync_all),
    # Templates
    (re.compile(r"^/api/templates/duplicate$"),                                            h_post_dup_template),
    (re.compile(r"^/api/templates$"),                                                      h_post_create_template),
    (re.compile(rf"^/api/templates/({_ID})/meta$"),                                         h_post_template_meta),
    (re.compile(rf"^/api/templates/({_ID})/file$"),                                         h_post_template_file),
    # Overlays : application sur un workspace existant (idempotent)
    (re.compile(rf"^/api/workspaces/({_ID})/overlays/({_ID})$"),                            h_post_apply_overlay),
    # Overlays : retrait (aperçu dry_run puis exécution avec plan_id)
    (re.compile(rf"^/api/workspaces/({_ID})/overlays/({_ID})/remove$"),                     h_post_remove_overlay),
    # Module claude-team : routage always-on (mode / gate de relecture)
    (re.compile(rf"^/api/workspaces/({_ID})/team/routing$"),                                h_post_ws_team_routing),
    # Module claude-team : modèle et effort par agent (+ régénération)
    (re.compile(rf"^/api/workspaces/({_ID})/team/agents-config$"),                          h_post_ws_team_agents_config),
    # Boucle d'amélioration automatique : jobs de fond + mode automatique.
    (re.compile(rf"^/api/workspaces/({_ID})/improvement/run$"),                             h_post_ws_improvement_run),
    (re.compile(rf"^/api/workspaces/({_ID})/improvement/abandon$"),                         h_post_ws_improvement_abandon),
    (re.compile(rf"^/api/workspaces/({_ID})/improvement/stop$"),                            h_post_ws_improvement_stop),
    (re.compile(rf"^/api/workspaces/({_ID})/improvement/auto$"),                            h_post_ws_improvement_auto),
    # Skills
    (re.compile(r"^/api/skills$"),                                                         h_post_create_skill),
    (re.compile(r"^/api/skills/copy$"),                                                    h_post_copy_skill),
    (re.compile(r"^/api/skills/import/preview$"),                                          h_post_skills_import_preview),
    (re.compile(r"^/api/skills/import$"),                                                  h_post_skills_import),
    # Skills library (magasin)
    (re.compile(r"^/api/skills-library$"),                                                 h_post_library_create),
    (re.compile(r"^/api/skills-library/migrate$"),                                         h_post_library_migrate),
    (re.compile(rf"^/api/skills-library/({_ID})/distribute$"),                              h_post_library_distribute),
    (re.compile(rf"^/api/skills-library/({_ID})/content$"),                                 h_post_library_content),
    (re.compile(rf"^/api/skills-library/({_ID})/file$"),                                    h_post_library_file),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/content$"),                              h_post_skill_content),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/file$"),                                 h_post_skill_file),
    # Plugins
    (re.compile(r"^/api/plugins/install$"),                                                h_post_install_plugin),
    (re.compile(r"^/api/plugins/enable$"),                                                 h_post_enable_plugin),
    (re.compile(r"^/api/plugins/disable$"),                                                h_post_disable_plugin),
    (re.compile(r"^/api/plugins/uninstall$"),                                              h_post_uninstall_plugin),
    (re.compile(r"^/api/plugins/uninstall-soft$"),                                         h_post_uninstall_soft),
    (re.compile(r"^/api/plugins/marketplaces/refresh$"),                                   h_post_refresh_marketplaces),
    # Agents & commands
    (re.compile(r"^/api/agents$"),                                                         h_post_create_agent),
    (re.compile(r"^/api/commands$"),                                                       h_post_create_command),
    (re.compile(rf"^/api/({_KIND_FILEITEM})/({_SCOPE})/({_ID})/content$"),                  h_post_fileitem_content),
    # Système
    (re.compile(r"^/api/env$"),                                                            h_post_set_env),
    (re.compile(r"^/api/env/encrypt$"),                                                    h_post_env_encrypt),
    (re.compile(r"^/api/env/decrypt$"),                                                    h_post_env_decrypt),
    (re.compile(r"^/api/open$"),                                                           h_post_open),
    (re.compile(r"^/api/backup$"),                                                         h_post_backup),
    (re.compile(r"^/api/backups/restore$"),                                                h_post_backup_restore),
    (re.compile(r"^/api/cleanup/orphan-bats$"),                                            h_post_cleanup_bats),
    (re.compile(r"^/api/journal$"),                                                        h_post_journal),
    (re.compile(r"^/api/hooks/global$"),                                                   h_post_hooks_global),
    (re.compile(r"^/api/hooks/restore$"),                                                  h_post_hooks_restore),
    (re.compile(rf"^/api/workspaces/({_ID})/hooks/restore$"),                               h_post_ws_hooks_restore),
    (re.compile(r"^/api/setup/import$"),                                                   h_post_setup_import),
    (re.compile(r"^/api/ui-state$"),                                                       h_post_ui_state),
    (re.compile(r"^/api/system/update$"),                                                  h_post_system_update),
    (re.compile(r"^/api/system/reset$"),                                                   h_post_system_reset),
    (re.compile(r"^/api/system/stash-recover$"),                                           h_post_system_stash_recover),
    (re.compile(r"^/api/system/stash-drop$"),                                              h_post_system_stash_drop),
    (re.compile(r"^/api/system/stash-prune$"),                                             h_post_system_stash_prune),
]

ROUTES_DELETE = [
    (re.compile(rf"^/api/workspaces/({_ID})$"),                                             h_del_ws),
    (re.compile(rf"^/api/workspaces/({_ID})/fs/file$"),                                     h_del_ws_fs_file),
    (re.compile(rf"^/api/mcps/recipes/local/({_ID})$"),                                     h_del_local_recipe),
    (re.compile(rf"^/api/mcps/({_ID})$"),                                                   h_del_mcp),
    (re.compile(r"^/api/env/(.+)$"),                                                       h_del_env),
    (re.compile(r"^/api/journal$"),                                                        h_del_journal),
    (re.compile(rf"^/api/templates/({_ID})/file$"),                                         h_del_template_file),
    (re.compile(rf"^/api/templates/({_ID})$"),                                              h_del_template),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})/file$"),                                 h_del_skill_file),
    (re.compile(rf"^/api/skills/({_SCOPE})/({_ID})$"),                                      h_del_skill),
    (re.compile(rf"^/api/skills-library/({_ID})/file$"),                                    h_del_library_file),
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

# Fichiers statiques servis (liste blanche). Tout le reste de dashboard/
# (data/, dashcore/, tools/, *.py, *.bak, *.json...) n'est JAMAIS servi.
_STATIC_TOP_FILES = {"index.html", "app.js", "app.css", "prototype.html"}
_STATIC_DIRS = {"js", "css", "assets"}
_STATIC_EXTS = (".js", ".css", ".woff2", ".woff", ".svg", ".png", ".ico")

# Routes GET à effet de bord (spawn de process, appel réseau sortant) :
# exigent aussi le header anti-CSRF (le front le pose toujours via API._req).
_SIDE_EFFECT_GET = (
    re.compile(r"^/api/mcps/[a-zA-Z0-9_-]+/diagnose$"),        # lance le serveur MCP / requête HTTP
    re.compile(r"^/api/workspaces/[a-zA-Z0-9_-]+/mcp-check$"),  # `claude mcp list` (démarre les MCPs)
)
# /api/system/version n'a d'effet de bord (git fetch) qu'avec ?check=1 :
# gardé seulement dans ce cas (la lecture simple reste libre).
_FETCH_GET = "/api/system/version"

# En-têtes de sécurité posés sur TOUTES les réponses. Pas de CSP stricte :
# index.html contient un <script> inline (thème anti-flash) et les vues
# utilisent des styles inline ; seul frame-ancestors est imposé.
_SECURITY_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
    ("Content-Security-Policy", "frame-ancestors 'none'"),
)


def _host_header_name(host: str) -> str:
    """Forme de `host` dans un en-tête Host (IPv6 entre crochets)."""
    h = host.strip().lower()
    return f"[{h}]" if ":" in h and not h.startswith("[") else h


def allowed_host_headers(bind_host: str, port: int, extra=()) -> set:
    """Valeurs acceptées pour l'en-tête Host (anti DNS-rebinding).

    Toujours 127.0.0.1 / localhost (et [::1]) ; plus l'hôte d'écoute s'il
    est explicite (pas une adresse joker 0.0.0.0 / ::), plus les noms de
    NEBULA_ALLOWED_HOSTS. Chaque nom est accepté avec le port d'écoute.
    """
    names = {"127.0.0.1", "localhost", "[::1]"}
    b = (bind_host or "").strip().strip("[]").lower()
    if b and b not in ("0.0.0.0", "::"):
        names.add(_host_header_name(b))
    names.update(_host_header_name(x) for x in extra if x and x.strip())
    return {f"{n}:{port}" for n in names}


class Handler(BaseHTTPRequestHandler):
    MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB
    # Timeout socket (s) : une connexion muette (client lent / malveillant)
    # ne bloque plus un thread indéfiniment. N'affecte pas la durée de
    # traitement d'un handler (git pull...), seulement les I/O socket.
    timeout = 60

    def end_headers(self):
        for k, v in _SECURITY_HEADERS:
            self.send_header(k, v)
        super().end_headers()

    def _allowed_hosts(self) -> set:
        return allowed_host_headers(
            getattr(self.server, "nebula_host", HOST),
            self.server.server_address[1], EXTRA_ALLOWED_HOSTS)

    def _host_ok(self) -> bool:
        """Anti DNS-rebinding : Host doit être 127.0.0.1/localhost:<port>
        (ou l'hôte configuré / NEBULA_ALLOWED_HOSTS, cf. allowed_host_headers).

        Un domaine attaquant re-résolu vers 127.0.0.1 arrive avec SON nom
        dans Host -> refusé, même s'il est « same-origin » pour le navigateur
        (et pourrait donc poser X-Nebula-XHR).
        """
        host = (self.headers.get("Host") or "").strip().lower()
        return host in self._allowed_hosts()

    def _origin_ok(self) -> bool:
        """Requêtes mutantes : Origin (si présent) doit être l'UI elle-même."""
        origin = (self.headers.get("Origin") or "").strip().lower()
        if origin:
            return origin in {f"http://{h}" for h in self._allowed_hosts()}
        # Pas d'Origin (client non navigateur) : Sec-Fetch-Site s'il existe,
        # sinon on s'appuie sur X-Nebula-XHR (exigé de toute façon).
        return (self.headers.get("Sec-Fetch-Site") or "same-origin").lower() in (
            "same-origin", "none")

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
        """Corps JSON -> (dict | None, (status, message) | None).

        413 si trop gros, 400 si illisible ou si ce n'est pas un objet JSON
        (tous les handlers font `b.get(...)` : une liste / un scalaire
        provoquait un 500 opaque).
        """
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, (400, "Content-Length invalide")
        if length < 0:
            return None, (400, "Content-Length invalide")
        if length > self.MAX_BODY_BYTES:
            return None, (413, f"corps trop volumineux (max {self.MAX_BODY_BYTES // (1024 * 1024)} Mo)")
        if length == 0:
            return {}, None
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, (400, "JSON invalide")
        if not isinstance(body, dict):
            return None, (400, "corps JSON invalide : objet attendu")
        return body, None

    # Routes GET qui exposent des données sensibles : exigent aussi le header
    # (les GET ne sont pas gatés par défaut, ceux-ci le sont explicitement).
    _SENSITIVE_ROUTES = {"/api/env/values", "/api/env/encrypt", "/api/env/decrypt",
                         "/api/env/export-plain"}

    def _dispatch(self, method: str, body=None):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Anti DNS-rebinding sur TOUTES les requêtes (lectures comprises).
        if not self._host_ok():
            self._send_json(403, {"error": "Host non autorisé"}); return
        # Anti-CSRF par Origin sur les mutations (en plus de X-Nebula-XHR).
        if method in ("POST", "DELETE", "PUT", "PATCH") and not self._origin_ok():
            self._send_json(403, {"error": "Origine non autorisée"}); return

        # Anti-CSRF en DÉFAUT-REFUS : TOUTE mutation (POST/DELETE) exige le
        # header custom X-Nebula-XHR, qu'un <form>/<img> ou un fetch cross-origin
        # « simple » ne peut pas poser (le poser force un preflight CORS que le
        # serveur ne satisfait pas -> requête bloquée). Un site malveillant
        # ouvert pendant que le dashboard tourne ne peut donc pas déclencher
        # reset / purge / launch / env… (cf. review #1 : auparavant seul
        # /api/mcps* était protégé, laissant toutes les autres routes exposées).
        # Le front pose toujours le header via API._req (js/api.js) -> aucune
        # mutation légitime cassée. Allowlist d'exemption uniquement, jamais
        # d'inclusion à maintenir à la main.
        needs_csrf = (
            method in ("POST", "DELETE", "PUT", "PATCH")
            or path in self._SENSITIVE_ROUTES
            or (method == "GET" and any(p.match(path) for p in _SIDE_EFFECT_GET))
            or (method == "GET" and path == _FETCH_GET
                and (query.get("check", ["0"])[0] or "0") == "1")
        )
        if needs_csrf and self.headers.get("X-Nebula-XHR") != "1":
            self._send_json(403, {"error": "header X-Nebula-XHR requis"}); return

        for pat, handler in ROUTES_BY_METHOD.get(method, []):
            mat = pat.match(path)
            if not mat:
                continue
            try:
                result = handler(query, body, *mat.groups())
            except (CorruptJsonError, EnvStoreUnreadable) as e:
                # Donnée illisible sur un chemin lecture-modif-écriture : refus
                # (rien n'a été écrit) avec un message actionnable.
                log.error("Refus %s %s : %s", method, path, e)
                self._send_json(409, {"error": str(e)}); return
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
        parts = rel.split("/")
        if (not rel or ".." in parts or "" in parts or "\\" in rel or ":" in rel
                or not self._static_allowed(parts)):
            self._send_json(404, {"error": "not found"}); return
        self._send_file(DASHBOARD_DIR / rel)

    @staticmethod
    def _static_allowed(parts: list) -> bool:
        """Liste blanche : fichiers front de 1er niveau + js/, css/, assets/."""
        if len(parts) == 1:
            return parts[0] in _STATIC_TOP_FILES
        if parts[0] not in _STATIC_DIRS:
            return False
        name = parts[-1].lower()
        return name.endswith(_STATIC_EXTS) and not name.startswith(".")

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        body, err = self._read_json_body()
        if err:
            # Corps non (entièrement) lu : fermer la connexion plutôt que de
            # lire la suite comme une nouvelle requête.
            self.close_connection = True
            self._send_json(err[0], {"error": err[1]}); return
        self._dispatch("POST", body)

    def do_DELETE(self):
        self._dispatch("DELETE")


# ────────────────────────────────────────────────────────────────────────────
# Lancement
# ────────────────────────────────────────────────────────────────────────────

class _NebulaHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer.server_bind appelle socket.getfqdn(hôte) : résolution DNS
        # inverse, ~5 s de blocage au démarrage sur une IP sans PTR (127.0.0.2,
        # IP de réseau local). Le nom n'est utilisé nulle part : on s'en passe.
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port


def _start_improve_loop():
    """Reprise des jobs interrompus puis démarrage du planificateur de la
    boucle d'amélioration. Jamais bloquant : une erreur est journalisée et le
    serveur démarre quand même. `NEBULA_DISABLE_SCHEDULER=1` (tests) : pas de
    planificateur (la reprise des jobs a lieu)."""
    try:
        from dashcore import improve_jobs
        recovered = improve_jobs.recover_jobs()
        if recovered:
            log.info("Boucle d'amélioration : %d job(s) interrompu(s) repris en compte", len(recovered))
    except Exception:  # noqa: BLE001 - ne doit jamais empêcher le démarrage
        log.exception("Reprise des jobs de la boucle d'amélioration impossible")
    if (os.environ.get("NEBULA_DISABLE_SCHEDULER") or "").strip() == "1":
        log.info("Planificateur de la boucle désactivé (NEBULA_DISABLE_SCHEDULER=1)")
        return
    sched = _improve_scheduler()
    if sched is None:
        return
    try:
        sched.start()
    except Exception:  # noqa: BLE001
        log.exception("Démarrage du planificateur de la boucle impossible")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port d'écoute (défaut : NEBULA_PORT ou 4777, ici {DEFAULT_PORT})")
    ap.add_argument("--host", default=HOST,
                    help=f"hôte d'écoute (défaut : NEBULA_HOST ou 127.0.0.1, ici {HOST})")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--debug", action="store_true", help="Active le niveau DEBUG")
    ap.add_argument("--migrate-data", action="store_true",
                    help="Recopie vers NEBULA_DATA_DIR les données absentes (sans écraser)")
    args = ap.parse_args()

    setup_logging(logging.DEBUG if args.debug else logging.INFO)
    for msg in CONFIG_WARNINGS:
        log.warning("Configuration : %s", msg)

    host = (args.host or HOST).strip().strip("[]")
    ipv6 = ":" in host
    port = args.port
    if not port_free(host, port):
        new = find_port(host, port + 1)
        log.warning("Port %d occupé → fallback sur %d", port, new)
        port = new

    if not is_loopback_host(host):
        # API d'administration SANS authentification (secrets .env, lancement
        # de process, écriture de fichiers) : l'exposer au réseau donne ces
        # pouvoirs à quiconque l'atteint. Avertissement explicite.
        log.warning("!" * 72)
        log.warning("ATTENTION : écoute sur %s (hors boucle locale).", host)
        log.warning("L'API n'a AUCUNE authentification : toute machine qui atteint")
        log.warning("ce port peut lire tes secrets et lancer des commandes.")
        log.warning("Réserve cet usage à un réseau de confiance (ou un tunnel SSH).")
        log.warning("!" * 72)

    if DATA_DIR_IS_CUSTOM:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Migration assistée vers NEBULA_DATA_DIR (copie sans écrasement, cf.
    # dashcore/data_migration.py) : automatique au 1er lancement sur un
    # dossier vide, forcée par --migrate-data.
    from dashcore.data_migration import startup_migration
    try:
        startup_migration(force=args.migrate_data)
    except OSError as e:
        log.warning("Migration des données impossible : %s", e)

    server_cls = _NebulaHTTPServer
    if ipv6:
        server_cls = type("NebulaHTTPServer6", (_NebulaHTTPServer,),
                          {"address_family": socket.AF_INET6})
    server = server_cls((host, port), Handler)
    server.nebula_host = host
    url_host = {"0.0.0.0": "127.0.0.1", "::": "[::1]"}.get(host, _host_header_name(host))
    url = f"http://{url_host}:{port}/"
    log.info("Dashboard Claude Workspace — %s", url)
    log.info("  registry : %s", MCP_REGISTRY)
    log.info("  données : %s%s", DATA_DIR, " (NEBULA_DATA_DIR)" if DATA_DIR_IS_CUSTOM else "")
    log.info("  .env.local : %s  (%s)", ENV_FILE, "présent" if ENV_FILE.exists() else "absent")
    log.info("  logs : %s", LOGS_DIR / "dashboard.log")
    _start_improve_loop()
    log.info("Ctrl+C pour arrêter.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Arrêt demandé (Ctrl+C).")
        sched = _improve_scheduler()
        if sched is not None:
            try:
                sched.stop()
            except Exception:  # noqa: BLE001
                log.exception("Arrêt du planificateur de la boucle")
        server.shutdown()


if __name__ == "__main__":
    main()
