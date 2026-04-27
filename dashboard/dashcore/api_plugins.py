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


from dashcore.helpers import (
    _remove_dir_or_link, parse_skill_frontmatter, read_json,
    resolve_cli, resolve_ws_dir, safe_id, write_json,
)
from dashcore.api_workspaces import list_workspaces, _workspace_settings_path


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


def _scan_plugin_dir(plugin_dir: Path, marketplace: str | None = None) -> dict:
    """Lit les méta d'un dossier de plugin (priorité .claude-plugin/plugin.json)."""
    candidates = [
        plugin_dir / ".claude-plugin" / "plugin.json",
        plugin_dir / "plugin.json",
        plugin_dir / "manifest.json",
        plugin_dir / "package.json",
    ]
    meta = {}
    for p in candidates:
        if p.exists():
            meta = read_json(p, {}) or {}
            break
    try:
        size_kb = sum(f.stat().st_size for f in plugin_dir.rglob("*") if f.is_file()) // 1024
    except OSError:
        size_kb = 0
    author = meta.get("author")
    if isinstance(author, dict):
        author = author.get("name", "")
    return {
        "dir_name": plugin_dir.name,
        "marketplace": marketplace,
        "path": str(plugin_dir),
        "name": meta.get("name") or plugin_dir.name,
        "version": meta.get("version") or "",
        "description": meta.get("description") or "",
        "author": author or "",
        "size_kb": size_kb,
    }


def _discover_all_installed(plugins_dir: Path) -> list[dict]:
    """Discovery complète : marketplaces + plugins standalone à la racine.

    Structure typique :
    - ~/.claude/plugins/marketplaces/<mkt>/plugins/<plugin>/
    - ~/.claude/plugins/marketplaces/<mkt>/external_plugins/<plugin>/
    - ~/.claude/plugins/<plugin>/  (plugins installés sans marketplace)
    """
    out = []
    if not plugins_dir.exists():
        return out

    # Marketplaces
    mkt_root = plugins_dir / "marketplaces"
    if mkt_root.exists():
        for mkt in sorted(mkt_root.iterdir()):
            if not mkt.is_dir():
                continue
            for sub in ("plugins", "external_plugins"):
                kind_dir = mkt / sub
                if not kind_dir.exists():
                    continue
                for p in sorted(kind_dir.iterdir()):
                    if p.is_dir():
                        info = _scan_plugin_dir(p, marketplace=mkt.name)
                        info["kind"] = sub
                        out.append(info)

    # Plugins standalone (au cas où — non utilisé en pratique par Claude Code)
    for entry in sorted(plugins_dir.iterdir()):
        if not entry.is_dir() or entry.name == "marketplaces":
            continue
        # Détecte si c'est un plugin (présence d'un manifeste reconnaissable)
        if any((entry / c).exists() for c in (".claude-plugin/plugin.json", "plugin.json")):
            info = _scan_plugin_dir(entry, marketplace=None)
            info["kind"] = "standalone"
            out.append(info)

    return out


def _match_enabled_key(key: str, on_disk: list[dict]) -> dict | None:
    """Associe une clé `enabledPlugins` (ex: 'code-review@claude-plugins-official') à un plugin trouvé."""
    if "@" in key:
        plug_id, mkt = key.split("@", 1)
    else:
        plug_id, mkt = key, None
    for d in on_disk:
        if d["dir_name"] != plug_id and d["name"] != plug_id:
            continue
        if mkt is None or d.get("marketplace") == mkt or d.get("marketplace") is None:
            return d
    # Fallback : match juste sur l'id, n'importe quel marketplace
    for d in on_disk:
        if d["dir_name"] == plug_id or d["name"] == plug_id:
            return d
    return None


def list_installed_plugins() -> dict:
    """Source de vérité : ~/.claude/plugins/installed_plugins.json + settings.json.

    Le fichier installed_plugins.json (maintenu par Claude Code) liste précisément
    les plugins installés avec leur installPath, version et scope. On lit ce
    fichier puis on enrichit avec les méta lues dans le manifeste.
    """
    plugins_dir = CLAUDE_HOME / "plugins"
    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    enabled = settings.get("enabledPlugins") or {}

    installed_file = plugins_dir / "installed_plugins.json"
    installed_data = read_json(installed_file, {}) or {}
    installed_map = installed_data.get("plugins") or {}

    marketplaces = _discover_marketplaces(plugins_dir)

    # Construit la liste des plugins installés
    cross = []
    seen_keys = set()
    for key, entries in installed_map.items():
        seen_keys.add(key)
        # Prend la première entrée (scope=user de préférence, sinon la première)
        entry = next((e for e in entries if e.get("scope") == "user"), None) or (entries[0] if entries else {})
        install_path = Path(entry.get("installPath", "")) if entry.get("installPath") else None
        on_disk = bool(install_path and install_path.exists())

        # Lit le manifeste pour description et autres
        meta = {}
        size_kb = 0
        if on_disk:
            for cand in (".claude-plugin/plugin.json", "plugin.json", "manifest.json"):
                p = install_path / cand
                if p.exists():
                    meta = read_json(p, {}) or {}
                    break
            try:
                size_kb = sum(f.stat().st_size for f in install_path.rglob("*") if f.is_file()) // 1024
            except OSError:
                size_kb = 0

        # Marketplace extrait de la clé
        mkt = key.split("@", 1)[1] if "@" in key else None
        version = entry.get("version") or meta.get("version") or ""
        if version == "unknown":
            version = ""

        cross.append({
            "id": key,
            "enabled": bool(enabled.get(key, True)),  # Présent dans installed_plugins.json = activé par défaut
            "on_disk": on_disk,
            "path": str(install_path) if install_path else None,
            "marketplace": mkt,
            "version": version,
            "description": meta.get("description") or "",
            "scope": entry.get("scope") or "",
            "size_kb": size_kb,
            "installed_at": entry.get("installedAt"),
        })

    # Plugins listés dans settings.json mais absents de installed_plugins.json (rare)
    for key, val in enabled.items():
        if key in seen_keys:
            continue
        cross.append({
            "id": key,
            "enabled": bool(val),
            "on_disk": False,
            "path": None,
            "marketplace": key.split("@", 1)[1] if "@" in key else None,
            "version": "",
            "description": "",
            "scope": "",
            "size_kb": 0,
            "installed_at": None,
        })

    # Dossiers orphelins dans cache/ qui ne sont plus référencés
    orphans = []
    cache_dir = plugins_dir / "cache"
    if cache_dir.exists():
        referenced_paths = {Path(c["path"]).resolve() for c in cross if c.get("path")}
        for mkt_dir in cache_dir.iterdir():
            if not mkt_dir.is_dir():
                continue
            for plugin_dir in mkt_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue
                # Le sous-dossier version
                for version_dir in plugin_dir.iterdir():
                    if not version_dir.is_dir():
                        continue
                    if version_dir.resolve() not in referenced_paths:
                        orphans.append({
                            "dir_name": f"{mkt_dir.name}/{plugin_dir.name}/{version_dir.name}",
                            "rel_path": str(version_dir.relative_to(plugins_dir)),
                            "path": str(version_dir),
                        })

    return {
        "plugins_dir": str(plugins_dir),
        "dir_exists": plugins_dir.exists(),
        "enabled": enabled,
        "cross": cross,
        "orphans_on_disk": orphans,
        "marketplaces": marketplaces,
    }


def uninstall_plugin(plugin_id: str, remove_files: bool = False) -> tuple[int, dict]:
    if not plugin_id or "\\" in plugin_id or ".." in plugin_id:
        return 400, {"error": "plugin_id invalide"}

    with _MUTATION_LOCK:
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
            encoding="utf-8", errors="replace",
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


_SKILL_PATH_RE = re.compile(r"^[a-zA-Z0-9_./-]{1,200}$")


def _resolve_skill_file(scope: str, name: str, rel_path: str) -> tuple[Path | None, dict | None]:
    """Valide scope/name/rel_path et renvoie le Path absolu sécurisé."""
    parent = _skill_dir(scope)
    if parent is None or not safe_id(name):
        return None, {"error": "scope ou nom invalide"}
    skill_dir = (parent / name).resolve()
    if not skill_dir.exists():
        return None, {"error": "skill introuvable"}
    if not rel_path or not _SKILL_PATH_RE.match(rel_path):
        return None, {"error": "chemin invalide (a-z, 0-9, _, -, /, ., max 200)"}
    if ".." in rel_path.split("/"):
        return None, {"error": "traversal interdit"}
    target = (skill_dir / rel_path).resolve()
    try:
        target.relative_to(skill_dir)
    except ValueError:
        return None, {"error": "chemin hors du skill"}
    return target, None


def get_skill_detail(scope: str, name: str) -> tuple[int, dict]:
    """Retourne le détail d'un skill : meta + arborescence des fichiers."""
    parent = _skill_dir(scope)
    if parent is None or not safe_id(name):
        return 400, {"error": "scope ou nom invalide"}
    skill_dir = parent / name
    if not skill_dir.exists():
        return 404, {"error": "skill introuvable"}
    meta = parse_skill_frontmatter(skill_dir / "SKILL.md") if (skill_dir / "SKILL.md").exists() else {}
    files = []
    for entry in sorted(skill_dir.rglob("*")):
        if not entry.is_file():
            continue
        # Ignore les .bak
        if entry.suffix == ".bak":
            continue
        rel = entry.relative_to(skill_dir).as_posix()
        try:
            size = entry.stat().st_size
        except OSError:
            size = 0
        files.append({"path": rel, "size": size})
    return 200, {
        "scope": scope,
        "name": name,
        "meta": meta,
        "files": files,
        "path": str(skill_dir),
    }


def get_skill_file(scope: str, name: str, rel_path: str) -> tuple[int, dict]:
    target, err = _resolve_skill_file(scope, name, rel_path)
    if err:
        return 400, err
    if not target.exists() or not target.is_file():
        return 404, {"error": "fichier introuvable"}
    try:
        size = target.stat().st_size
        if size > 512 * 1024:
            return 200, {"path": rel_path, "size": size, "content": "", "binary": True, "error": "fichier > 512 Kio"}
        data = target.read_bytes()
        try:
            return 200, {"path": rel_path, "size": size, "content": data.decode("utf-8"), "binary": False}
        except UnicodeDecodeError:
            return 200, {"path": rel_path, "size": size, "content": "", "binary": True}
    except OSError as e:
        return 500, {"error": str(e)}


def write_skill_file(scope: str, name: str, rel_path: str, content: str) -> tuple[int, dict]:
    target, err = _resolve_skill_file(scope, name, rel_path)
    if err:
        return 400, err
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.with_suffix(target.suffix + ".bak").write_bytes(target.read_bytes())
        target.write_text(content, encoding="utf-8")
        log.info("skill file written: %s/%s/%s", scope, name, rel_path)
        return 200, {"ok": True, "path": rel_path, "size": target.stat().st_size}
    except OSError as e:
        return 500, {"error": str(e)}


def delete_skill_file(scope: str, name: str, rel_path: str) -> tuple[int, dict]:
    target, err = _resolve_skill_file(scope, name, rel_path)
    if err:
        return 400, err
    # Refuse de supprimer SKILL.md (fichier obligatoire)
    if rel_path == "SKILL.md":
        return 400, {"error": "SKILL.md ne peut pas être supprimé (renommez le skill ou supprimez-le entièrement)"}
    if not target.exists() or not target.is_file():
        return 404, {"error": "fichier introuvable"}
    try:
        target.unlink()
        # Nettoie dossiers parents vides
        parent = target.parent
        skill_dir = (_skill_dir(scope) / name).resolve()
        while parent != skill_dir and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        return 200, {"ok": True}
    except OSError as e:
        return 500, {"error": str(e)}


def list_skill_workspace_usage(skill_name: str) -> list[str]:
    """Liste les workspaces où ce skill est copié localement."""
    if not safe_id(skill_name):
        return []
    out = []
    # Import tardif pour éviter le cycle
    from dashcore.api_workspaces import list_workspaces
    for w in list_workspaces():
        skill_path = resolve_ws_dir(w["id"]) / ".claude" / "skills" / skill_name
        if skill_path.exists():
            out.append(w["id"])
    return out


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


_GITHUB_URL_RE = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)?"
    r"([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Accepte 'user/repo', 'https://github.com/user/repo', 'https://github.com/user/repo.git'."""
    s = (url or "").strip()
    if not s:
        return None
    m = _GITHUB_URL_RE.match(s)
    if not m:
        return None
    return m.group(1), m.group(2)


def _clone_github_shallow(owner: str, repo: str, branch: str | None) -> tuple[Path, str] | None:
    """Clone shallow dans un temp dir. Retourne (path, commit_sha) ou None."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="atelier-skill-import-"))
    url = f"https://github.com/{owner}/{repo}.git"
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [url, str(tmp)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        return tmp, sha
    except (subprocess.TimeoutExpired, FileNotFoundError):
        shutil.rmtree(tmp, ignore_errors=True)
        return None


def _find_skills_in_repo(repo_dir: Path) -> list[dict]:
    """Cherche tous les dossiers contenant un SKILL.md (max 3 niveaux). Retourne meta."""
    out = []
    seen = set()
    # Priorité au sous-dossier 'skills/' s'il existe (convention)
    candidates = []
    skills_root = repo_dir / "skills"
    if skills_root.is_dir():
        candidates.append(skills_root)
    candidates.append(repo_dir)

    for root in candidates:
        for skill_md in root.rglob("SKILL.md"):
            sub = skill_md.parent
            # Ignore si dans .git ou node_modules
            if any(p in {".git", "node_modules", ".github"} for p in sub.parts):
                continue
            try:
                rel = sub.relative_to(repo_dir)
            except ValueError:
                continue
            key = str(rel)
            if key in seen:
                continue
            seen.add(key)
            meta = parse_skill_frontmatter(skill_md)
            out.append({
                "id": sub.name,
                "rel_path": key.replace("\\", "/"),
                "name": meta.get("name") or sub.name,
                "description": meta.get("description") or "",
            })
    return out


def preview_github_skills(payload: dict) -> tuple[int, dict]:
    parsed = _parse_github_url(payload.get("url", ""))
    if not parsed:
        return 400, {"error": "URL GitHub invalide (attendu: user/repo ou https://github.com/user/repo)"}
    owner, repo = parsed
    branch = (payload.get("branch") or "").strip() or None
    if branch and not re.match(r"^[A-Za-z0-9._/-]{1,80}$", branch):
        return 400, {"error": "branche invalide"}
    cloned = _clone_github_shallow(owner, repo, branch)
    if cloned is None:
        return 502, {"error": "git clone a échoué (repo introuvable, privé, ou git absent)"}
    tmp, sha = cloned
    try:
        skills = _find_skills_in_repo(tmp)
        if not skills:
            return 404, {"error": "Aucun SKILL.md détecté dans ce repo"}
        return 200, {
            "owner": owner, "repo": repo, "branch": branch or "default",
            "commit": sha, "skills": skills,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def import_github_skills(payload: dict) -> tuple[int, dict]:
    parsed = _parse_github_url(payload.get("url", ""))
    if not parsed:
        return 400, {"error": "URL GitHub invalide"}
    owner, repo = parsed
    branch = (payload.get("branch") or "").strip() or None
    scope = (payload.get("scope") or "").strip()
    selected = payload.get("skills") or []  # liste de rel_path
    overwrite = bool(payload.get("overwrite"))

    if not isinstance(selected, list) or not selected:
        return 400, {"error": "Aucun skill sélectionné"}

    parent = _skill_dir(scope)
    if parent is None:
        return 400, {"error": "scope invalide (global ou workspace:<id>)"}

    cloned = _clone_github_shallow(owner, repo, branch)
    if cloned is None:
        return 502, {"error": "git clone a échoué"}
    tmp, sha = cloned
    try:
        parent.mkdir(parents=True, exist_ok=True)
        imported = []
        skipped = []
        errors = []
        now_iso = dt.datetime.now().isoformat(timespec="seconds")

        for rel in selected:
            rel = str(rel).replace("\\", "/").strip("/")
            if ".." in rel.split("/"):
                errors.append({"rel": rel, "error": "chemin invalide"})
                continue
            src = tmp / rel
            if not (src / "SKILL.md").exists():
                errors.append({"rel": rel, "error": "SKILL.md introuvable côté source"})
                continue
            dst = parent / src.name
            if dst.exists():
                if not overwrite:
                    skipped.append({"name": src.name, "reason": "existe déjà"})
                    continue
                _remove_dir_or_link(dst)
            try:
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "node_modules"))
                # Métadonnées de provenance pour futur "vérifier MAJ"
                origin = {
                    "repo": f"{owner}/{repo}",
                    "branch": branch or "default",
                    "commit": sha,
                    "source_path": rel,
                    "imported_at": now_iso,
                }
                (dst / ".atelier-origin.json").write_text(
                    json.dumps(origin, indent=2), encoding="utf-8"
                )
                imported.append({"name": src.name, "path": str(dst)})
            except OSError as e:
                errors.append({"rel": rel, "error": str(e)})

        return 200, {
            "ok": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "commit": sha,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    with _MUTATION_LOCK:
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


