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
)


from dashcore.helpers import *
from dashcore.api_workspaces import list_workspaces, _workspace_settings_path


def _remove_dir_or_link(p: Path) -> None:
    if os.path.islink(p) or p.is_symlink():
        p.unlink()
    elif p.is_dir():
        try:
            shutil.rmtree(p)
        except OSError:
            # Junction point détecté tardivement (Windows)
            p.unlink()
    elif p.exists():
        p.unlink()


def list_plugins() -> dict:
    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    enabled = settings.get("enabledPlugins") or {}
    return {"enabled": enabled, "count": len(enabled)}


def _discover_plugins_recursive(base: Path, max_depth: int = 3) -> list[dict]:
    """Cherche des dossiers de plugin (repérés via plugin.json/manifest/package.json) jusqu'à max_depth."""
    out = []
    if not base.exists():
        return out

    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        for entry in d.iterdir():
            if not entry.is_dir():
                continue
            manifest = None
            for candidate in ("plugin.json", "manifest.json", "package.json"):
                p = entry / candidate
                if p.exists():
                    manifest = p
                    break
            if manifest:
                meta = read_json(manifest, {}) or {}
                out.append({
                    "dir_name": entry.name,
                    "rel_path": str(entry.relative_to(base)),
                    "path": str(entry),
                    "name": meta.get("name") or entry.name,
                    "version": meta.get("version") or "",
                    "description": meta.get("description") or "",
                    "size_kb": sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) // 1024,
                })
            else:
                walk(entry, depth + 1)

    walk(base, 1)
    return out


def _discover_marketplaces(base: Path) -> list[dict]:
    """Cherche les marketplaces enregistrées dans ~/.claude/plugins/marketplaces/"""
    mkt_dir = base / "marketplaces"
    out = []
    if not mkt_dir.exists():
        return out
    for entry in sorted(mkt_dir.iterdir()):
        if entry.is_dir():
            info = {"id": entry.name, "path": str(entry)}
            for candidate in ("marketplace.json", "index.json", "info.json"):
                p = entry / candidate
                if p.exists():
                    info["manifest"] = read_json(p, {})
                    break
            out.append(info)
    return out


def _read_plugin_meta(plugin_dir: Path) -> dict:
    """Lit le manifeste d'un plugin dans un marketplace."""
    # Essaie .claude-plugin/plugin.json puis racine
    candidates = [
        plugin_dir / ".claude-plugin" / "plugin.json",
        plugin_dir / "plugin.json",
        plugin_dir / "manifest.json",
    ]
    meta = {}
    for p in candidates:
        if p.exists():
            meta = read_json(p, {}) or {}
            break

    # Compte les composants (skills/agents/commands/hooks)
    components = {}
    for kind in ("skills", "agents", "commands"):
        sub = plugin_dir / kind
        if sub.exists() and sub.is_dir():
            components[kind] = sum(1 for _ in sub.iterdir() if _.is_dir() or _.suffix == ".md")

    # Readme présent ?
    has_readme = (plugin_dir / "README.md").exists()

    return {
        "id": plugin_dir.name,
        "name": meta.get("name") or plugin_dir.name,
        "description": meta.get("description") or "",
        "author": (meta.get("author") or {}).get("name") if isinstance(meta.get("author"), dict) else (meta.get("author") or ""),
        "version": meta.get("version") or "",
        "components": components,
        "has_readme": has_readme,
        "path": str(plugin_dir),
    }


def list_marketplace_plugins(marketplace_id: str = "claude-plugins-official") -> dict:
    """Liste tous les plugins d'un marketplace (first-party + external)."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", marketplace_id):
        return {"error": "marketplace_id invalide"}

    mkt_dir = CLAUDE_HOME / "plugins" / "marketplaces" / marketplace_id
    if not mkt_dir.exists():
        return {"error": f"marketplace introuvable : {marketplace_id}", "plugins": [], "external": []}

    first_party = []
    plugins_dir = mkt_dir / "plugins"
    if plugins_dir.exists():
        for p in sorted(plugins_dir.iterdir()):
            if p.is_dir():
                first_party.append(_read_plugin_meta(p))

    external = []
    ext_dir = mkt_dir / "external_plugins"
    if ext_dir.exists():
        for p in sorted(ext_dir.iterdir()):
            if p.is_dir():
                external.append(_read_plugin_meta(p))

    return {
        "marketplace": marketplace_id,
        "first_party": first_party,
        "external": external,
        "total": len(first_party) + len(external),
    }


def read_plugin_readme(marketplace_id: str, kind: str, plugin_id: str) -> tuple[int, dict]:
    """Lit le README d'un plugin dans le marketplace. kind in {plugins, external_plugins}."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", marketplace_id) or not re.match(r"^[a-zA-Z0-9_-]+$", plugin_id):
        return 400, {"error": "id invalide"}
    if kind not in ("plugins", "external_plugins"):
        return 400, {"error": "kind invalide"}

    plugin_dir = CLAUDE_HOME / "plugins" / "marketplaces" / marketplace_id / kind / plugin_id
    if not plugin_dir.exists():
        return 404, {"error": "plugin introuvable"}

    readme = plugin_dir / "README.md"
    if not readme.exists():
        return 404, {"error": "pas de README"}

    content = readme.read_text(encoding="utf-8", errors="replace")
    if len(content) > 100_000:
        content = content[:100_000] + "\n\n[tronqué]"
    return 200, {"content": content, "path": str(readme)}


def list_installed_plugins() -> dict:
    """Inspecte ~/.claude/plugins/ + cross-check avec enabledPlugins."""
    plugins_dir = CLAUDE_HOME / "plugins"
    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    enabled = settings.get("enabledPlugins") or {}

    on_disk = _discover_plugins_recursive(plugins_dir, max_depth=3)
    marketplaces = _discover_marketplaces(plugins_dir)

    cross = []
    for key, val in enabled.items():
        short = key.split("@")[0]
        found = next(
            (d for d in on_disk
             if key in d["dir_name"] or d["dir_name"] == short or d["name"] == short),
            None,
        )
        cross.append({
            "id": key,
            "enabled": bool(val),
            "on_disk": bool(found),
            "path": found["path"] if found else None,
            "version": found["version"] if found else "",
            "size_kb": found["size_kb"] if found else 0,
        })

    orphans_on_disk = []
    for d in on_disk:
        referenced = any(
            d["dir_name"] == key.split("@")[0] or d["name"] == key.split("@")[0] or d["dir_name"] in key
            for key in enabled.keys()
        )
        if not referenced:
            orphans_on_disk.append({"dir_name": d["dir_name"], "rel_path": d["rel_path"], "path": d["path"]})

    return {
        "plugins_dir": str(plugins_dir),
        "dir_exists": plugins_dir.exists(),
        "on_disk": on_disk,
        "enabled": enabled,
        "cross": cross,
        "orphans_on_disk": orphans_on_disk,
        "marketplaces": marketplaces,
    }


def uninstall_plugin(plugin_id: str, remove_files: bool = False) -> tuple[int, dict]:
    if not plugin_id or "\\" in plugin_id or ".." in plugin_id:
        return 400, {"error": "plugin_id invalide"}

    # Backup settings.json
    if CLAUDE_SETTINGS.exists():
        bak = CLAUDE_SETTINGS.with_suffix(".json.bak")
        bak.write_text(CLAUDE_SETTINGS.read_text(encoding="utf-8"), encoding="utf-8")

    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    enabled = settings.get("enabledPlugins") or {}
    removed_from_config = plugin_id in enabled
    enabled.pop(plugin_id, None)
    if enabled:
        settings["enabledPlugins"] = enabled
    else:
        settings.pop("enabledPlugins", None)
    CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    write_json(CLAUDE_SETTINGS, settings)

    removed_dir = None
    if remove_files:
        plugins_dir = CLAUDE_HOME / "plugins"
        short = plugin_id.split("@")[0]
        for entry in (plugins_dir / plugin_id, plugins_dir / short):
            if entry.exists():
                _remove_dir_or_link(entry)
                removed_dir = str(entry)
                break
        if not removed_dir:
            for d in plugins_dir.iterdir() if plugins_dir.exists() else []:
                if d.is_dir() and (plugin_id in d.name or short in d.name):
                    _remove_dir_or_link(d)
                    removed_dir = str(d)
                    break

    return 200, {
        "ok": True,
        "removed_from_config": removed_from_config,
        "removed_dir": removed_dir,
    }


def claude_plugin_cli(args: list[str], timeout: int = 120) -> tuple[int, dict]:
    """Appelle `claude plugin ...` en CLI direct. Retourne (status_http, {ok, output})."""
    try:
        r = subprocess.run(
            [resolve_cli("claude"), "plugin"] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        return 200, {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout or "",
            "stderr": r.stderr or "",
        }
    except FileNotFoundError:
        return 500, {"ok": False, "error": "claude CLI introuvable dans le PATH"}
    except subprocess.TimeoutExpired:
        return 500, {"ok": False, "error": f"timeout ({timeout}s)"}
    except Exception as e:
        return 500, {"ok": False, "error": str(e)}


def install_plugin_cli(plugin_spec: str) -> tuple[int, dict]:
    """`claude plugin install <name>@<marketplace>`"""
    if not plugin_spec or not SAFE_PLUGIN_SPEC.match(plugin_spec):
        return 400, {"error": "spec invalide"}
    return claude_plugin_cli(["install", plugin_spec])


def enable_plugin_cli(plugin_id: str) -> tuple[int, dict]:
    if not plugin_id or not SAFE_PLUGIN_SPEC.match(plugin_id):
        return 400, {"error": "id invalide"}
    return claude_plugin_cli(["enable", plugin_id])


def disable_plugin_cli(plugin_id: str) -> tuple[int, dict]:
    if not plugin_id or not SAFE_PLUGIN_SPEC.match(plugin_id):
        return 400, {"error": "id invalide"}
    return claude_plugin_cli(["disable", plugin_id])


def uninstall_plugin_cli(plugin_id: str) -> tuple[int, dict]:
    if not plugin_id or not SAFE_PLUGIN_SPEC.match(plugin_id):
        return 400, {"error": "id invalide"}
    return claude_plugin_cli(["uninstall", plugin_id])


def list_skills_in_dir(d: Path) -> list[dict]:
    if not d.exists():
        return []
    out = []
    for sub in sorted(d.iterdir()):
        if not sub.is_dir():
            continue
        skill_md = sub / "SKILL.md"
        if not skill_md.exists():
            continue
        meta = parse_skill_frontmatter(skill_md)
        out.append({
            "id": sub.name,
            "name": meta.get("name") or sub.name,
            "description": meta.get("description") or "",
            "path": str(sub),
        })
    return out


def list_skills_global() -> list[dict]:
    return list_skills_in_dir(CLAUDE_HOME / "skills")


def list_skills_for_workspace(ws_id: str) -> dict:
    if not safe_id(ws_id):
        return {"global": list_skills_global(), "local": []}
    ws_dir = resolve_ws_dir(ws_id)
    local = list_skills_in_dir(ws_dir / ".claude" / "skills")
    return {"global": list_skills_global(), "local": local}


def _skill_dir(scope: str) -> Path | None:
    """Retourne le dossier parent des skills selon le scope."""
    if scope == "global":
        return CLAUDE_HOME / "skills"
    if scope.startswith("workspace:"):
        ws_id = scope.split(":", 1)[1]
        if not safe_id(ws_id):
            return None
        return resolve_ws_dir(ws_id) / ".claude" / "skills"
    return None


def create_skill(payload: dict) -> tuple[int, dict]:
    scope = (payload.get("scope") or "").strip()
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    body = payload.get("body") or ""

    parent = _skill_dir(scope)
    if parent is None:
        return 400, {"error": "scope invalide (global ou workspace:<id>)"}
    if not safe_id(name):
        return 400, {"error": "nom invalide (a-z, 0-9, -, _)"}
    if not description:
        return 400, {"error": "description requise"}

    skill_dir = parent / name
    if skill_dir.exists():
        return 409, {"error": f"Skill déjà existant : {name}"}

    parent.mkdir(parents=True, exist_ok=True)
    skill_dir.mkdir()

    # Frontmatter : échappe les guillemets + newlines pour description
    desc_escaped = description.replace('"', '\\"').replace("\n", " ")
    content = f"""---
name: {name}
description: "{desc_escaped}"
---

# {name}

{body.strip() or '(instructions du skill)'}
"""
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return 201, {"ok": True, "path": str(skill_dir)}


def delete_skill(scope: str, name: str) -> tuple[int, dict]:
    parent = _skill_dir(scope)
    if parent is None or not safe_id(name):
        return 400, {"error": "scope ou nom invalide"}
    d = parent / name
    if not d.exists() and not d.is_symlink():
        return 404, {"error": "skill introuvable"}
    _remove_dir_or_link(d)
    return 200, {"ok": True}


def get_skill_content(scope: str, name: str) -> tuple[int, dict]:
    parent = _skill_dir(scope)
    if parent is None or not safe_id(name):
        return 400, {"error": "scope ou nom invalide"}
    skill_md = parent / name / "SKILL.md"
    if not skill_md.exists():
        return 404, {"error": "SKILL.md introuvable"}
    content = skill_md.read_text(encoding="utf-8")
    return 200, {"content": content, "path": str(skill_md)}


def save_skill_content(scope: str, name: str, content: str) -> tuple[int, dict]:
    parent = _skill_dir(scope)
    if parent is None or not safe_id(name):
        return 400, {"error": "scope ou nom invalide"}
    skill_md = parent / name / "SKILL.md"
    if not skill_md.exists():
        return 404, {"error": "SKILL.md introuvable"}
    # Backup auto avant écriture
    bak = skill_md.with_suffix(".md.bak")
    bak.write_text(skill_md.read_text(encoding="utf-8"), encoding="utf-8")
    skill_md.write_text(content, encoding="utf-8")
    return 200, {"ok": True, "backup": str(bak)}


def copy_skill_to_workspace(payload: dict) -> tuple[int, dict]:
    name = (payload.get("name") or "").strip()
    ws_id = (payload.get("workspace") or "").strip()
    if not safe_id(name) or not safe_id(ws_id):
        return 400, {"error": "nom ou workspace invalide"}
    src = CLAUDE_HOME / "skills" / name
    if not src.exists():
        return 404, {"error": "skill global introuvable"}
    dst_parent = resolve_ws_dir(ws_id) / ".claude" / "skills"
    dst = dst_parent / name
    if dst.exists():
        return 409, {"error": "skill déjà présent dans le workspace"}
    dst_parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    return 201, {"ok": True, "path": str(dst)}


def _file_scope_path(kind: str, scope: str, name: str) -> Path | None:
    """kind in {agents, commands}. Retourne le .md du fichier."""
    if not safe_id(name):
        return None
    if scope == "global":
        return CLAUDE_HOME / kind / f"{name}.md"
    if scope.startswith("workspace:"):
        ws_id = scope.split(":", 1)[1]
        if not safe_id(ws_id):
            return None
        return resolve_ws_dir(ws_id) / ".claude" / kind / f"{name}.md"
    return None


def _list_files_in_dir(d: Path) -> list[dict]:
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*.md")):
        meta = parse_skill_frontmatter(f)
        out.append({
            "id": f.stem,
            "name": meta.get("name") or f.stem,
            "description": meta.get("description") or "",
            "path": str(f),
        })
    return out


def list_agents(ws_id: str | None = None) -> dict:
    g = _list_files_in_dir(CLAUDE_HOME / "agents")
    local = _list_files_in_dir(resolve_ws_dir(ws_id) / ".claude" / "agents") if ws_id and safe_id(ws_id) else []
    return {"global": g, "local": local}


def list_commands(ws_id: str | None = None) -> dict:
    g = _list_files_in_dir(CLAUDE_HOME / "commands")
    local = _list_files_in_dir(resolve_ws_dir(ws_id) / ".claude" / "commands") if ws_id and safe_id(ws_id) else []
    return {"global": g, "local": local}


def create_fileitem(kind: str, payload: dict) -> tuple[int, dict]:
    """kind in {agents, commands}"""
    scope = (payload.get("scope") or "").strip()
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    body = payload.get("body") or ""
    path = _file_scope_path(kind, scope, name)
    if path is None:
        return 400, {"error": "scope ou nom invalide"}
    if not description:
        return 400, {"error": "description requise"}
    if path.exists():
        return 409, {"error": f"{kind[:-1]} existe déjà"}
    path.parent.mkdir(parents=True, exist_ok=True)
    desc_escaped = description.replace('"', '\\"').replace("\n", " ")
    content = f"""---
name: {name}
description: "{desc_escaped}"
---

{body.strip() or '(contenu)'}
"""
    path.write_text(content, encoding="utf-8")
    return 201, {"ok": True, "path": str(path)}


def delete_fileitem(kind: str, scope: str, name: str) -> tuple[int, dict]:
    path = _file_scope_path(kind, scope, name)
    if path is None:
        return 400, {"error": "scope ou nom invalide"}
    if not path.exists():
        return 404, {"error": "introuvable"}
    # backup
    bak = path.with_suffix(".md.bak")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.unlink()
    return 200, {"ok": True, "backup": str(bak)}


def get_fileitem_content(kind: str, scope: str, name: str) -> tuple[int, dict]:
    path = _file_scope_path(kind, scope, name)
    if path is None or not path.exists():
        return 404, {"error": "introuvable"}
    return 200, {"content": path.read_text(encoding="utf-8"), "path": str(path)}


def save_fileitem_content(kind: str, scope: str, name: str, content: str) -> tuple[int, dict]:
    path = _file_scope_path(kind, scope, name)
    if path is None or not path.exists():
        return 404, {"error": "introuvable"}
    bak = path.with_suffix(".md.bak")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(content, encoding="utf-8")
    return 200, {"ok": True, "backup": str(bak)}


def get_workspace_plugins(ws_id: str) -> dict:
    """Retourne les plugins globaux avec leur statut effectif pour ce workspace."""
    if not safe_id(ws_id):
        return {}
    global_plugins = list_plugins().get("enabled", {})
    # Override éventuel dans <ws>/.claude/settings.json
    ws_settings = read_json(_workspace_settings_path(ws_id), {}) or {}
    overrides = (ws_settings.get("enabledPlugins") or {})
    out = {}
    for pid, global_enabled in global_plugins.items():
        if pid in overrides:
            out[pid] = {"global": bool(global_enabled), "effective": bool(overrides[pid]), "overridden": True}
        else:
            out[pid] = {"global": bool(global_enabled), "effective": bool(global_enabled), "overridden": False}
    return out


def set_workspace_plugin(ws_id: str, plugin_id: str, enabled) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "workspace invalide"}
    if not plugin_id or "/" in plugin_id or "\\" in plugin_id:
        return 400, {"error": "plugin_id invalide"}

    path = _workspace_settings_path(ws_id)
    settings = read_json(path, {}) or {}
    plugins = settings.setdefault("enabledPlugins", {})
    if enabled is None:
        # reset : retire l'override, revient au global
        plugins.pop(plugin_id, None)
    else:
        plugins[plugin_id] = bool(enabled)
    if not plugins:
        settings.pop("enabledPlugins", None)
    if settings:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, settings)
    elif path.exists():
        path.unlink()
    return 200, {"ok": True}


