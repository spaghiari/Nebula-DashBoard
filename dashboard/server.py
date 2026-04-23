"""
Dashboard Claude Workspace — serveur local.

- Bind 127.0.0.1 uniquement (aucune exposition réseau).
- Sert dashboard/index.html et expose /api/* pour piloter le workspace.
- Aucune dépendance externe (stdlib only).

Lancement :
    python server.py              # port 4777 par défaut
    python server.py --port 4800  # port custom
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import io
import json
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
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HOST = "127.0.0.1"
DEFAULT_PORT = 4777

ROOT = Path(r"C:\claude-workspace")
USER_HOME = Path.home()
CLAUDE_HOME = USER_HOME / ".claude"
CLAUDE_JSON = USER_HOME / ".claude.json"
CLAUDE_SETTINGS = CLAUDE_HOME / "settings.json"
CLAUDE_PROJECTS = CLAUDE_HOME / "projects"
BACKUPS_DIR = ROOT / "backups"
JOURNAL_FILE = ROOT / "memory" / "journal.md"
TEMPLATES_DIR = ROOT / "templates"

TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts",
    ".sh", ".bat", ".ps1", ".html", ".css", ".cfg", ".ini", ".toml",
    ".gitignore", ".env",
}
DASHBOARD_DIR = ROOT / "dashboard"
WORKSPACES_DIR = ROOT / "workspaces"
SCRIPTS_DIR = ROOT / "scripts"
SNIPPETS_DIR = ROOT / "memory" / "snippets"
WORKSPACES_JSON = DASHBOARD_DIR / "data" / "workspaces.json"
MCP_REGISTRY = ROOT / "mcp" / "registry.json"
ENV_FILE = ROOT / ".env.local"

SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")
SAFE_PLUGIN_SPEC = re.compile(r"^[a-zA-Z0-9@/_.-]{1,120}$")
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
BAT_UNSAFE = re.compile(r'[&|<>^"%\r\n]')
PATH_UNSAFE = re.compile(r'["\r\n]')

# Sérialise les mutations JSON concurrentes (ThreadingHTTPServer).
_MUTATION_LOCK = threading.Lock()

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".ico":  "image/x-icon",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
}


# ------------------------ helpers ------------------------

def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    with _MUTATION_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def resolve_cli(name: str) -> str:
    """Retourne le chemin absolu d'un binaire CLI ou son nom brut en fallback."""
    return shutil.which(name) or name


def safe_path(path: str) -> bool:
    """Refuse les chemins avec caractères problématiques pour un shell Windows."""
    return bool(path) and not PATH_UNSAFE.search(path)


def safe_id(s: str) -> bool:
    return bool(SAFE_ID.match(s or ""))


def sanitize_bat(s: str) -> str:
    """Retire les chars qui cassent un .bat en contexte echo."""
    return BAT_UNSAFE.sub("", s or "").strip()


def load_env_local() -> dict:
    """Parse un .env.local simple (KEY=VALUE, lignes # ignorées)."""
    env = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            env[k] = v
    return env


def substitute_env(value, env: dict):
    """Remplace récursivement ${VAR} dans strings / lists / dicts."""
    if isinstance(value, str):
        missing = []
        def repl(m):
            key = m.group(1)
            if key in env:
                return env[key]
            if key in os.environ:
                return os.environ[key]
            missing.append(key)
            return m.group(0)
        out = ENV_VAR_PATTERN.sub(repl, value)
        return out, missing
    if isinstance(value, list):
        all_missing = []
        out = []
        for v in value:
            nv, miss = substitute_env(v, env)
            out.append(nv)
            all_missing.extend(miss)
        return out, all_missing
    if isinstance(value, dict):
        all_missing = []
        out = {}
        for k, v in value.items():
            nv, miss = substitute_env(v, env)
            out[k] = nv
            all_missing.extend(miss)
        return out, all_missing
    return value, []


# ------------------------ port handling ------------------------

def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_port(host: str, start: int) -> int:
    for p in range(start, start + 20):
        if port_free(host, p):
            return p
    raise RuntimeError(f"Aucun port libre entre {start} et {start+19}")


# ------------------------ launch ------------------------

def launch_script(bat_name: str) -> tuple[bool, str]:
    bat = SCRIPTS_DIR / bat_name
    if not bat.exists():
        return False, f"Script introuvable : {bat}"
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(bat)],
            cwd=str(SCRIPTS_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            shell=False,
        )
        return True, f"Lancé : {bat.name}"
    except Exception as e:
        return False, f"Erreur : {e}"


# ------------------------ workspace ops ------------------------

def list_workspaces() -> list[dict]:
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    return data.get("workspaces", [])


def list_templates() -> list[dict]:
    if not TEMPLATES_DIR.exists():
        return []
    out = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / ".template.json"
        meta = read_json(meta_path, {}) or {}
        files = []
        for entry in d.rglob("*"):
            if entry.is_file() and entry.name != ".template.json":
                files.append(str(entry.relative_to(d)))
        out.append({
            "id": d.name,
            "label": meta.get("label") or d.name,
            "description": meta.get("description") or "",
            "emoji": meta.get("emoji") or "📦",
            "files": files,
            "file_count": len(files),
            "path": str(d),
        })
    return out


def duplicate_template(payload: dict) -> tuple[int, dict]:
    src_id = (payload.get("source") or "").strip()
    new_id = (payload.get("id") or "").strip()
    label = (payload.get("label") or new_id).strip()
    description = (payload.get("description") or "").strip()
    emoji = (payload.get("emoji") or "📦").strip()

    if not safe_id(src_id) or not safe_id(new_id):
        return 400, {"error": "id invalide"}

    src = TEMPLATES_DIR / src_id
    dst = TEMPLATES_DIR / new_id
    if not src.exists():
        return 404, {"error": f"Template source introuvable : {src_id}"}
    if dst.exists():
        return 409, {"error": f"Template déjà existant : {new_id}"}

    shutil.copytree(src, dst)
    meta_path = dst / ".template.json"
    meta = {"label": label, "description": description, "emoji": emoji}
    write_json(meta_path, meta)
    return 201, {"ok": True, "id": new_id}


def delete_template(tpl_id: str) -> tuple[int, dict]:
    if not safe_id(tpl_id):
        return 400, {"error": "id invalide"}
    d = TEMPLATES_DIR / tpl_id
    if not d.exists():
        return 404, {"error": "Template introuvable"}
    shutil.rmtree(d)
    return 200, {"ok": True}


# ------------------------ plugins & skills ------------------------

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
                shutil.rmtree(entry)
                removed_dir = str(entry)
                break
        if not removed_dir:
            for d in plugins_dir.iterdir() if plugins_dir.exists() else []:
                if d.is_dir() and (plugin_id in d.name or short in d.name):
                    shutil.rmtree(d)
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


def cleanup_orphan_bats() -> dict:
    """Retire les .bat qui ne correspondent à aucun workspace du registre."""
    ws_ids = {w["id"] for w in list_workspaces()}
    removed = []
    for bat in SCRIPTS_DIR.glob("launch-*.bat"):
        # extract id from "launch-<id>.bat"
        wid = bat.stem[len("launch-"):]
        if wid not in ws_ids:
            bat.unlink()
            removed.append(bat.name)
    return {"removed": removed}


def parse_skill_frontmatter(skill_md: Path) -> dict:
    """Lit les clés name/description/model de la frontmatter YAML d'un SKILL.md."""
    meta = {}
    try:
        with skill_md.open("r", encoding="utf-8", errors="replace") as f:
            text = f.read(3000)
    except Exception:
        return meta
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    block = text[3:end]
    for line in block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


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
    ws_dir = WORKSPACES_DIR / ws_id
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
        return WORKSPACES_DIR / ws_id / ".claude" / "skills"
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
    if not d.exists():
        return 404, {"error": "skill introuvable"}
    shutil.rmtree(d)
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
    dst_parent = WORKSPACES_DIR / ws_id / ".claude" / "skills"
    dst = dst_parent / name
    if dst.exists():
        return 409, {"error": "skill déjà présent dans le workspace"}
    dst_parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    return 201, {"ok": True, "path": str(dst)}


# ------------------------ agents & commands (structure commune) ------------------------

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
        return WORKSPACES_DIR / ws_id / ".claude" / kind / f"{name}.md"
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
    local = _list_files_in_dir(WORKSPACES_DIR / ws_id / ".claude" / "agents") if ws_id and safe_id(ws_id) else []
    return {"global": g, "local": local}


def list_commands(ws_id: str | None = None) -> dict:
    g = _list_files_in_dir(CLAUDE_HOME / "commands")
    local = _list_files_in_dir(WORKSPACES_DIR / ws_id / ".claude" / "commands") if ws_id and safe_id(ws_id) else []
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


# ------------------------ settings par workspace ------------------------

def get_workspace_settings(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    path = _workspace_settings_path(ws_id)
    content = "{}"
    if path.exists():
        content = path.read_text(encoding="utf-8")
    return 200, {"path": str(path), "exists": path.exists(), "content": content}


def save_workspace_settings(ws_id: str, content: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return 400, {"error": f"JSON invalide : {e}"}
    if not isinstance(parsed, dict):
        return 400, {"error": "doit être un objet JSON"}

    path = _workspace_settings_path(ws_id)
    if path.exists():
        bak = path.with_suffix(".json.bak")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if parsed:
        write_json(path, parsed)
    elif path.exists():
        path.unlink()
    return 200, {"ok": True}


def patch_workspace_settings(ws_id: str, key: str, value) -> tuple[int, dict]:
    """Met à jour une clé précise (permissions, hooks, model, env, effortLevel)."""
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    allowed = {"permissions", "hooks", "model", "env", "effortLevel", "enabledPlugins"}
    if key not in allowed:
        return 400, {"error": f"clé non gérée : {key}"}

    path = _workspace_settings_path(ws_id)
    settings = read_json(path, {}) or {}
    if value is None or (isinstance(value, (dict, list)) and not value):
        settings.pop(key, None)
    else:
        settings[key] = value

    if path.exists():
        bak = path.with_suffix(".json.bak")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    if settings:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, settings)
    elif path.exists():
        path.unlink()
    return 200, {"ok": True}


# ------------------------ hooks globaux (~/.claude/settings.json) ------------------------

def get_global_hooks() -> dict:
    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    return settings.get("hooks") or {}


def set_global_hooks(hooks: dict) -> tuple[int, dict]:
    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    if CLAUDE_SETTINGS.exists():
        bak = CLAUDE_SETTINGS.with_suffix(".json.bak")
        bak.write_text(CLAUDE_SETTINGS.read_text(encoding="utf-8"), encoding="utf-8")
    if hooks:
        settings["hooks"] = hooks
    else:
        settings.pop("hooks", None)
    CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    write_json(CLAUDE_SETTINGS, settings)
    return 200, {"ok": True}


# ------------------------ sessions browser ------------------------

def list_sessions_for_workspace(ws_id: str) -> list[dict]:
    w = next((x for x in list_workspaces() if x["id"] == ws_id), None)
    if not w:
        return []
    pdir = project_dir_for_path(Path(w["path"]))
    if not pdir:
        return []
    out = []
    for jsonl in sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            mtime = jsonl.stat().st_mtime
            first_msg = None
            n = 0
            inp = out_tokens = 0
            with jsonl.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try: entry = json.loads(line)
                    except: continue
                    if entry.get("type") == "user" and first_msg is None:
                        msg = entry.get("message") or {}
                        content = msg.get("content")
                        if isinstance(content, str):
                            first_msg = content[:200]
                        elif isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    first_msg = c.get("text", "")[:200]; break
                    if entry.get("type") in ("user", "assistant"):
                        n += 1
                    usage = (entry.get("message") or {}).get("usage") or entry.get("usage") or {}
                    inp += int(usage.get("input_tokens") or 0)
                    out_tokens += int(usage.get("output_tokens") or 0)
            out.append({
                "file": jsonl.name,
                "path": str(jsonl),
                "mtime": dt.datetime.fromtimestamp(mtime).isoformat(timespec="seconds"),
                "messages": n,
                "first_message": first_msg or "(vide)",
                "input_tokens": inp,
                "output_tokens": out_tokens,
            })
        except Exception:
            continue
    return out


def read_session_messages(ws_id: str, filename: str, limit: int = 200) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    if "/" in filename or "\\" in filename or not filename.endswith(".jsonl"):
        return 400, {"error": "filename invalide"}
    w = next((x for x in list_workspaces() if x["id"] == ws_id), None)
    if not w:
        return 404, {"error": "workspace absent"}
    pdir = project_dir_for_path(Path(w["path"]))
    if not pdir:
        return 404, {"error": "pas de projets Claude pour ce workspace"}
    path = pdir / filename
    if not path.exists():
        return 404, {"error": "fichier absent"}

    messages = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try: entry = json.loads(line)
            except: continue
            t = entry.get("type")
            if t not in ("user", "assistant"):
                continue
            msg = entry.get("message") or {}
            content = msg.get("content")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict):
                        if c.get("type") == "text":
                            parts.append(c.get("text", ""))
                        elif c.get("type") == "tool_use":
                            parts.append(f"[tool_use: {c.get('name')}]")
                        elif c.get("type") == "tool_result":
                            tr = c.get("content", "")
                            if isinstance(tr, list):
                                tr = " ".join(x.get("text","") if isinstance(x, dict) else str(x) for x in tr)
                            parts.append(f"[tool_result: {str(tr)[:500]}]")
                text = "\n".join(parts)
            messages.append({
                "role": t,
                "text": text[:5000],
                "timestamp": entry.get("timestamp"),
            })
            if len(messages) >= limit:
                break
    return 200, {"messages": messages, "file": filename}


# ------------------------ duplicate workspace ------------------------

def duplicate_workspace(payload: dict) -> tuple[int, dict]:
    source = (payload.get("source") or "").strip()
    new_id = (payload.get("id") or "").strip()
    label = sanitize_bat(payload.get("label") or "") or new_id
    emoji = (payload.get("emoji") or "📁").strip()
    description = (payload.get("description") or "").strip()

    if not safe_id(source) or not safe_id(new_id):
        return 400, {"error": "id invalide"}
    src = WORKSPACES_DIR / source
    dst = WORKSPACES_DIR / new_id
    if not src.exists():
        return 404, {"error": "source introuvable"}
    if dst.exists():
        return 409, {"error": "destination déjà existante"}

    shutil.copytree(src, dst)

    # .bat de lancement
    bat_path = SCRIPTS_DIR / f"launch-{new_id}.bat"
    bat_content = f"""@echo off
echo.
echo  +======================================+
echo  ^|   Claude Code -- {label}
echo  +======================================+
echo.
cd /d {dst}
claude
"""
    bat_path.write_text(bat_content, encoding="utf-8")

    # registre
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    src_entry = next((w for w in data.get("workspaces", []) if w.get("id") == source), None)
    data.setdefault("workspaces", []).append({
        "id": new_id,
        "label": label,
        "emoji": emoji,
        "description": description,
        "path": str(dst),
        "template": (src_entry or {}).get("template", "clone"),
    })
    write_json(WORKSPACES_JSON, data)
    return 201, {"ok": True, "id": new_id}


# ------------------------ resume last session ------------------------

def launch_resume(ws_id: str) -> tuple[bool, str]:
    if not safe_id(ws_id):
        return False, "id invalide"
    w = next((x for x in list_workspaces() if x["id"] == ws_id), None)
    if not w:
        return False, "workspace absent"
    path = w.get("path", "")
    if not safe_path(path):
        return False, "chemin de workspace invalide"
    try:
        # /k garde la fenêtre ouverte après exécution (utile si claude -c termine ou échoue)
        subprocess.Popen(
            ["cmd", "/c", "start", "", "cmd", "/k", f'cd /d "{path}" && claude -c'],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
        return True, f"Reprise session : {ws_id}"
    except Exception as e:
        return False, f"Erreur : {e}"


# ------------------------ MCP live check (claude mcp list) ------------------------

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


# ------------------------ search global ------------------------

def global_search(q: str) -> dict:
    q = (q or "").strip().lower()
    if not q:
        return {"results": []}
    results = []

    for w in list_workspaces():
        hay = f"{w.get('id','')} {w.get('label','')} {w.get('description','')}".lower()
        if q in hay:
            results.append({"kind": "workspace", "id": w["id"], "label": w.get("label"), "route": f"#/workspace/{w['id']}"})
    for m in read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", []):
        hay = f"{m.get('id','')} {m.get('name','')} {m.get('description','')} {m.get('notes','')}".lower()
        if q in hay:
            results.append({"kind": "mcp", "id": m["id"], "label": m.get("name"), "route": "#/mcps"})
    for s in list_skills_global():
        if q in (s["name"] + " " + s["description"]).lower():
            results.append({"kind": "skill", "id": s["id"], "label": s["name"], "route": "#/tools"})
    for t in list_templates():
        if q in (t["id"] + " " + t["label"] + " " + t["description"]).lower():
            results.append({"kind": "template", "id": t["id"], "label": t["label"], "route": "#/templates"})
    return {"results": results[:40]}


# ------------------------ export / import workspace ------------------------

def export_workspace(ws_id: str) -> tuple[int, bytes | dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = WORKSPACES_DIR / ws_id
    if not ws_dir.exists():
        return 404, {"error": "workspace absent"}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in ws_dir.rglob("*"):
            if entry.is_file():
                # Skip secrets locaux
                if entry.name in (".env", ".env.local"):
                    continue
                arc = str(entry.relative_to(WORKSPACES_DIR))
                zf.write(entry, arcname=arc)
    return 200, buf.getvalue()


# ------------------------ plugins par workspace ------------------------

def _workspace_settings_path(ws_id: str) -> Path:
    return WORKSPACES_DIR / ws_id / ".claude" / "settings.json"


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


def is_text_file(path: Path) -> bool:
    if path.name in (".gitignore", ".gitkeep", ".env", ".env.local"):
        return True
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return path.stat().st_size < 512 * 1024
    return False


def render_placeholders(text: str, vars: dict) -> str:
    out = text
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def apply_template(src_dir: Path, dst_dir: Path, vars: dict) -> list[str]:
    """Copie récursivement `src_dir` dans `dst_dir`, substitue les placeholders.
    Retourne la liste des fichiers créés (relative à dst_dir)."""
    created = []
    for entry in src_dir.rglob("*"):
        rel = entry.relative_to(src_dir)
        if rel.name == ".template.json":
            continue
        target = dst_dir / rel
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if is_text_file(entry):
            content = entry.read_text(encoding="utf-8")
            content = render_placeholders(content, vars)
            target.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(entry, target)
        created.append(str(rel))
    return created


def create_workspace(payload: dict) -> tuple[int, dict]:
    ws_id = (payload.get("id") or "").strip()
    label = sanitize_bat(payload.get("label") or "") or ws_id
    emoji = (payload.get("emoji") or "📁").strip()
    desc  = (payload.get("description") or "").strip()
    tools = (payload.get("tools") or "").strip()
    template = (payload.get("template") or "blank").strip()

    if not safe_id(ws_id):
        return 400, {"error": "id invalide (a-z, 0-9, -, _)"}
    if not safe_id(template):
        return 400, {"error": "template invalide"}

    ws_dir = WORKSPACES_DIR / ws_id
    if ws_dir.exists():
        return 409, {"error": f"Workspace déjà existant : {ws_id}"}

    tpl_dir = TEMPLATES_DIR / template
    if not tpl_dir.exists():
        return 400, {"error": f"Template introuvable : {template}"}

    ws_dir.mkdir(parents=True, exist_ok=True)

    vars = {
        "name": ws_id,
        "label": label,
        "description": desc or "(à compléter)",
        "tools": tools or "(à compléter)",
        "date": dt.date.today().isoformat(),
        "emoji": emoji,
    }
    created = apply_template(tpl_dir, ws_dir, vars)

    bat_path = SCRIPTS_DIR / f"launch-{ws_id}.bat"
    bat_content = f"""@echo off
echo.
echo  +======================================+
echo  ^|   Claude Code -- {label}
echo  +======================================+
echo.
cd /d {ws_dir}
claude
"""
    bat_path.write_text(bat_content, encoding="utf-8")

    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    data.setdefault("workspaces", []).append({
        "id": ws_id,
        "label": label,
        "emoji": emoji,
        "description": desc,
        "path": str(ws_dir),
        "template": template,
    })
    write_json(WORKSPACES_JSON, data)
    return 201, {"ok": True, "id": ws_id, "template": template, "files": created}


def update_workspace(ws_id: str, payload: dict) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    ws_list = data.get("workspaces", [])
    idx = next((i for i, w in enumerate(ws_list) if w.get("id") == ws_id), None)
    if idx is None:
        return 404, {"error": "workspace absent du registre"}

    entry = ws_list[idx]
    if "label" in payload:
        entry["label"] = sanitize_bat(payload.get("label") or "") or ws_id
    if "description" in payload:
        entry["description"] = (payload.get("description") or "").strip()
    if "emoji" in payload:
        entry["emoji"] = (payload.get("emoji") or "📁").strip()
    ws_list[idx] = entry
    write_json(WORKSPACES_JSON, data)

    # Regénère le .bat avec le nouveau label
    bat_path = SCRIPTS_DIR / f"launch-{ws_id}.bat"
    bat_content = f"""@echo off
echo.
echo  +======================================+
echo  ^|   Claude Code -- {entry['label']}
echo  +======================================+
echo.
cd /d {entry['path']}
claude
"""
    bat_path.write_text(bat_content, encoding="utf-8")

    return 200, {"ok": True, "workspace": entry}


def delete_workspace(ws_id: str, purge: bool = False) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    before = len(data.get("workspaces", []))
    data["workspaces"] = [w for w in data.get("workspaces", []) if w.get("id") != ws_id]
    registered = len(data["workspaces"]) != before
    if registered:
        write_json(WORKSPACES_JSON, data)

    bat = SCRIPTS_DIR / f"launch-{ws_id}.bat"
    if bat.exists():
        bat.unlink()

    notes = []
    if not registered:
        notes.append("absent du registre")

    if purge:
        ws_dir = WORKSPACES_DIR / ws_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir)
            notes.append(f"dossier supprimé : {ws_dir}")
        else:
            notes.append("dossier déjà absent du disque")
    else:
        notes.append("dossier conservé")

    if not registered and not purge:
        return 404, {"error": "Workspace absent du registre"}
    return 200, {"ok": True, "note": " · ".join(notes)}


def read_workspace_config(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = WORKSPACES_DIR / ws_id
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}

    def read_text(p: Path, max_bytes: int = 200_000) -> str | None:
        if not p.exists():
            return None
        try:
            data = p.read_bytes()
            if len(data) > max_bytes:
                return data[:max_bytes].decode("utf-8", "replace") + f"\n\n[tronqué — fichier {len(data)} octets]"
            return data.decode("utf-8", "replace")
        except Exception as e:
            return f"[erreur de lecture : {e}]"

    files = {
        "CLAUDE.md":              read_text(ws_dir / "CLAUDE.md"),
        ".mcp.json":              read_text(ws_dir / ".mcp.json"),
        ".claude/settings.json":  read_text(ws_dir / ".claude" / "settings.json"),
        "notes.md":               read_text(ws_dir / "notes.md"),
    }
    # Liste des fichiers à la racine (jusqu'à 50)
    listing = []
    for entry in sorted(ws_dir.iterdir()) if ws_dir.exists() else []:
        listing.append({
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "size": entry.stat().st_size if entry.is_file() else None,
        })
    return 200, {
        "path": str(ws_dir),
        "files": files,
        "listing": listing[:50],
    }


# ------------------------ mcp ops ------------------------

ALLOWED_MCP_FIELDS = {
    "id", "name", "description", "transport", "command", "args", "env",
    "url", "workspaces", "status", "notes", "author", "source_url",
}

ALLOWED_STATUS = {"connecté", "disponible", "à configurer", "à tester", "désactivé"}
ALLOWED_TRANSPORTS = {"stdio", "http", "sse"}


def clean_mcp_payload(payload: dict) -> tuple[dict, str | None]:
    mcp_id = (payload.get("id") or "").strip()
    if not safe_id(mcp_id):
        return {}, "id invalide"

    clean = {
        "id": mcp_id,
        "name": (payload.get("name") or mcp_id).strip(),
        "description": (payload.get("description") or "").strip(),
        "transport": (payload.get("transport") or "stdio").strip(),
        "command": (payload.get("command") or "").strip(),
        "args": payload.get("args") or [],
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


# ------------------------ test / ping ------------------------

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


# ------------------------ stats (jsonl des sessions) ------------------------

def project_dir_for_path(path: Path) -> Path | None:
    """Trouve le dossier ~/.claude/projects/<encodé> qui correspond à `path`."""
    if not CLAUDE_PROJECTS.exists():
        return None
    target = str(path.resolve()).lower()
    best = None
    best_score = 0
    for d in CLAUDE_PROJECTS.iterdir():
        if not d.is_dir():
            continue
        decoded = d.name.replace("-", "\\").lstrip("\\").lower()
        decoded = re.sub(r"^([a-z])\\", r"\1:\\", decoded)
        if decoded == target or decoded.rstrip("\\") == target.rstrip("\\"):
            return d
        if target.startswith(decoded) and len(decoded) > best_score:
            best = d
            best_score = len(decoded)
    return best


def workspace_stats(ws: dict) -> dict:
    pdir = project_dir_for_path(Path(ws["path"]))
    if not pdir:
        return {"sessions": 0, "messages": 0, "last": None, "input_tokens": 0, "output_tokens": 0}
    sessions = 0
    messages = 0
    last_mtime = 0.0
    inp = out = 0
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
                    usage = (entry.get("message") or {}).get("usage") or entry.get("usage") or {}
                    inp += int(usage.get("input_tokens") or 0)
                    out += int(usage.get("output_tokens") or 0)
        except Exception:
            continue
    last_iso = dt.datetime.fromtimestamp(last_mtime).isoformat(timespec="seconds") if last_mtime else None
    # Pricing approx Opus 4.7 : $15 / M input, $75 / M output
    cost_usd = (inp / 1_000_000) * 15 + (out / 1_000_000) * 75
    return {
        "sessions": sessions,
        "messages": messages,
        "last": last_iso,
        "input_tokens": inp,
        "output_tokens": out,
        "cost_usd": round(cost_usd, 4),
    }


def all_stats() -> dict:
    out = {}
    for w in list_workspaces():
        out[w["id"]] = workspace_stats(w)
    return out


# ------------------------ sanity check MCPs ------------------------

def sanity_check() -> dict:
    """Compare registre ↔ .mcp.json effectivement écrits dans chaque workspace."""
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

        missing_sync  = expected_ids - actual_ids  # dans le registre mais pas écrit
        stale = actual_ids - expected_ids          # écrit mais plus dans le registre
        if missing_sync or stale:
            findings.append({
                "workspace": ws_id,
                "missing_sync": sorted(missing_sync),
                "stale": sorted(stale),
            })

    # variables manquantes
    missing_env = {}
    for m in registry:
        _, miss = build_mcp_server_entry(m, env_local)
        if miss:
            missing_env[m["id"]] = miss

    return {"findings": findings, "missing_env": missing_env}


# ------------------------ ouverture de fichiers ------------------------

OPEN_TARGETS = {
    "claude-json":       CLAUDE_JSON,
    "claude-settings":   CLAUDE_SETTINGS,
    "root-claude-md":    ROOT / "CLAUDE.md",
    "registry":          MCP_REGISTRY,
    "env-local":         ENV_FILE,
    "workspaces-json":   WORKSPACES_JSON,
    "global-memory":     ROOT / "memory",
}


def open_target(key: str) -> tuple[bool, str]:
    if key.startswith("workspace-claude-md:"):
        ws_id = key.split(":", 1)[1]
        if not safe_id(ws_id):
            return False, "id invalide"
        p = WORKSPACES_DIR / ws_id / "CLAUDE.md"
    elif key.startswith("workspace-dir:"):
        ws_id = key.split(":", 1)[1]
        if not safe_id(ws_id):
            return False, "id invalide"
        p = WORKSPACES_DIR / ws_id
    elif key.startswith("template:"):
        tpl_id = key.split(":", 1)[1]
        if not safe_id(tpl_id):
            return False, "id invalide"
        p = TEMPLATES_DIR / tpl_id
    elif key.startswith("skill-global:"):
        name = key.split(":", 1)[1]
        if not safe_id(name):
            return False, "nom invalide"
        p = CLAUDE_HOME / "skills" / name
    elif key.startswith("skill-ws:"):
        parts = key.split(":")
        if len(parts) != 3 or not safe_id(parts[1]) or not safe_id(parts[2]):
            return False, "format : skill-ws:<ws_id>:<name>"
        p = WORKSPACES_DIR / parts[1] / ".claude" / "skills" / parts[2]
    else:
        p = OPEN_TARGETS.get(key)
        if p is None:
            return False, "cible inconnue"

    if not p.exists():
        # Fichier absent : propose notepad pour les cas où on veut le créer
        if key == "env-local":
            try:
                subprocess.Popen(["notepad", str(p)])
                return True, f"Notepad ouvert (fichier sera créé au save) : {p}"
            except Exception as e:
                return False, f"Erreur : {e}"
        return False, f"Introuvable : {p}"
    try:
        if sys.platform == "win32":
            try:
                os.startfile(str(p))  # noqa
            except OSError:
                # Pas d'association pour .env ou .local → fallback notepad
                subprocess.Popen(["notepad", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return True, f"Ouvert : {p}"
    except Exception as e:
        return False, f"Erreur : {e}"


# ------------------------ backups de config Claude ------------------------

def backup_claude_config() -> tuple[bool, str]:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    copied = []
    for name, src in [("claude.json", CLAUDE_JSON), ("settings.json", CLAUDE_SETTINGS)]:
        if src.exists():
            dst = BACKUPS_DIR / f"{stamp}-{name}"
            shutil.copy2(src, dst)
            copied.append(dst.name)
    if not copied:
        return False, "Aucun fichier à sauvegarder"
    return True, "Sauvegardés : " + ", ".join(copied)


def list_backups() -> list[dict]:
    if not BACKUPS_DIR.exists():
        return []
    out = []
    for p in sorted(BACKUPS_DIR.iterdir(), reverse=True):
        if p.is_file():
            out.append({
                "name": p.name,
                "size": p.stat().st_size,
                "mtime": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
            })
    return out


# ------------------------ journal persistant ------------------------

JOURNAL_ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s*$", re.MULTILINE)


def read_journal() -> list[dict]:
    if not JOURNAL_FILE.exists():
        return []
    text = JOURNAL_FILE.read_text(encoding="utf-8")
    entries = []
    parts = JOURNAL_ENTRY.split(text)
    # parts = [preamble, ts1, body1, ts2, body2, ...]
    for i in range(1, len(parts), 2):
        ts = parts[i].strip()
        body = parts[i+1].strip() if i+1 < len(parts) else ""
        entries.append({"ts": ts, "text": body})
    return entries


def append_journal(text: str) -> None:
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    header_needed = not JOURNAL_FILE.exists() or not JOURNAL_FILE.read_text(encoding="utf-8").startswith("# Journal")
    with JOURNAL_FILE.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write("# Journal\n\n")
        f.write(f"## {ts}\n{text.strip()}\n\n")


def clear_journal() -> None:
    if JOURNAL_FILE.exists():
        JOURNAL_FILE.unlink()


# ------------------------ handler ------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.address_string()}] {fmt % args}\n")

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self._send_json(404, {"error": "not found"})
            return
        try:
            path.resolve().relative_to(DASHBOARD_DIR.resolve())
        except ValueError:
            self._send_json(403, {"error": "forbidden"})
            return
        ct = STATIC_TYPES.get(path.suffix.lower(), "application/octet-stream")
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        p = urlparse(self.path).path

        if p in ("/", "/index.html"):
            self._send_file(DASHBOARD_DIR / "index.html"); return

        if p == "/api/workspaces":
            self._send_json(200, read_json(WORKSPACES_JSON, {"version":"1.0","workspaces":[]})); return
        if p == "/api/mcps":
            self._send_json(200, read_json(MCP_REGISTRY, {"version":"1.0","mcps":[]})); return
        if p == "/api/env":
            env = load_env_local()
            self._send_json(200, {"keys": sorted(env.keys()), "file": str(ENV_FILE), "exists": ENV_FILE.exists()}); return
        if p == "/api/snippets":
            out = {}
            if SNIPPETS_DIR.exists():
                for f in SNIPPETS_DIR.glob("*.md"):
                    out[f.stem] = f.read_text(encoding="utf-8")
            self._send_json(200, out); return
        if p.startswith("/api/workspaces/") and p.endswith("/mcps"):
            ws_id = p.split("/")[3]
            status, payload = workspace_mcp_status(ws_id)
            self._send_json(status, payload); return

        if p.startswith("/api/workspaces/") and p.endswith("/config"):
            ws_id = p.split("/")[3]
            status, payload = read_workspace_config(ws_id)
            self._send_json(status, payload); return

        if p == "/api/stats":
            self._send_json(200, all_stats()); return

        if p == "/api/sanity-check":
            self._send_json(200, sanity_check()); return

        if p == "/api/backups":
            self._send_json(200, {"dir": str(BACKUPS_DIR), "items": list_backups()}); return

        if p == "/api/journal":
            self._send_json(200, {"entries": read_journal()[-100:]}); return

        if p == "/api/templates":
            self._send_json(200, {"templates": list_templates()}); return

        if p == "/api/plugins":
            self._send_json(200, list_plugins()); return

        if p == "/api/plugins/installed":
            self._send_json(200, list_installed_plugins()); return

        # /api/plugins/marketplace/<id>  → catalogue d'une marketplace
        m = re.match(r"^/api/plugins/marketplace/([a-zA-Z0-9_-]+)$", p)
        if m:
            self._send_json(200, list_marketplace_plugins(m.group(1))); return

        # /api/plugins/marketplace/<id>/<kind>/<plugin>/readme
        m = re.match(r"^/api/plugins/marketplace/([a-zA-Z0-9_-]+)/(plugins|external_plugins)/([a-zA-Z0-9_-]+)/readme$", p)
        if m:
            s, r = read_plugin_readme(m.group(1), m.group(2), m.group(3))
            self._send_json(s, r); return

        if p == "/api/skills":
            self._send_json(200, {"global": list_skills_global()}); return

        if p.startswith("/api/workspaces/") and p.endswith("/skills"):
            ws_id = p.split("/")[3]
            if not safe_id(ws_id):
                self._send_json(400, {"error":"id invalide"}); return
            self._send_json(200, list_skills_for_workspace(ws_id)); return

        if p.startswith("/api/workspaces/") and p.endswith("/plugins"):
            ws_id = p.split("/")[3]
            if not safe_id(ws_id):
                self._send_json(400, {"error":"id invalide"}); return
            self._send_json(200, {"plugins": get_workspace_plugins(ws_id)}); return

        # /api/skills/<scope>/<name>/content  → contenu brut du SKILL.md
        m = re.match(r"^/api/skills/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = get_skill_content(m.group(1), m.group(2))
            self._send_json(s, r); return

        # agents & commands
        m = re.match(r"^/api/(agents|commands)(?:/workspace/([a-zA-Z0-9_-]+))?$", p)
        if m:
            kind = m.group(1)
            ws = m.group(2)
            data = list_agents(ws) if kind == "agents" else list_commands(ws)
            self._send_json(200, data); return

        m = re.match(r"^/api/(agents|commands)/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = get_fileitem_content(m.group(1), m.group(2), m.group(3))
            self._send_json(s, r); return

        # settings par workspace
        if p.startswith("/api/workspaces/") and p.endswith("/settings"):
            ws_id = p.split("/")[3]
            s, r = get_workspace_settings(ws_id)
            self._send_json(s, r); return

        # sessions
        if p.startswith("/api/workspaces/") and p.endswith("/sessions"):
            ws_id = p.split("/")[3]
            self._send_json(200, {"sessions": list_sessions_for_workspace(ws_id)}); return

        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/sessions/([^/]+)$", p)
        if m:
            s, r = read_session_messages(m.group(1), m.group(2))
            self._send_json(s, r); return

        # hooks globaux
        if p == "/api/hooks/global":
            self._send_json(200, {"hooks": get_global_hooks()}); return

        # search
        if p.startswith("/api/search"):
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q", [""])[0])
            self._send_json(200, global_search(q)); return

        # export workspace (returns zip binary)
        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/export$", p)
        if m:
            status, data = export_workspace(m.group(1))
            if status != 200:
                self._send_json(status, data); return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{m.group(1)}.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # MCP live check
        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/mcp-check$", p)
        if m:
            s, r = mcp_live_check(m.group(1))
            self._send_json(s, r); return

        safe = p.lstrip("/").replace("..", "")
        self._send_file(DASHBOARD_DIR / safe)

    def do_POST(self):
        p = urlparse(self.path).path
        body = self._read_json_body()
        if body is None:
            self._send_json(400, {"error":"JSON invalide"}); return

        if p.startswith("/api/launch/"):
            ws_id = p[len("/api/launch/"):]
            if not safe_id(ws_id):
                self._send_json(400, {"error":"id invalide"}); return
            ok, msg = launch_script(f"launch-{ws_id}.bat")
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg}); return

        if p == "/api/workspaces":
            s, r = create_workspace(body); self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/update"):
            ws_id = p.split("/")[3]
            s, r = update_workspace(ws_id, body or {})
            self._send_json(s, r); return

        if p == "/api/mcps":
            s, r = add_or_update_mcp(body); self._send_json(s, r); return

        if p == "/api/mcps/import":
            results = []
            servers = body.get("mcpServers") or body.get("servers") or {}
            if not isinstance(servers, dict):
                self._send_json(400, {"error":"Attendu: objet mcpServers"}); return
            for name, cfg in servers.items():
                if not safe_id(name):
                    results.append({"id": name, "ok": False, "error": "id invalide"}); continue
                mcp = {
                    "id": name,
                    "name": name,
                    "transport": cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
                    "command": cfg.get("command", ""),
                    "args": cfg.get("args", []),
                    "env": cfg.get("env", {}),
                    "url": cfg.get("url", ""),
                    "workspaces": body.get("workspaces", []),
                    "status": "disponible",
                }
                s, r = add_or_update_mcp(mcp)
                results.append({"id": name, "ok": s < 400, **r})
            self._send_json(200, {"ok": True, "results": results}); return

        if p.startswith("/api/mcps/") and p.endswith("/test"):
            mcp_id = p.split("/")[3]
            s, r = test_mcp(mcp_id); self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/sync-mcps"):
            ws_id = p.split("/")[3]
            s, r = sync_workspace_mcps(ws_id); self._send_json(s, r); return

        if p == "/api/sync-all":
            s, r = sync_all_workspaces(); self._send_json(s, r); return

        if p == "/api/open":
            key = (body or {}).get("target", "")
            ok, msg = open_target(key)
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg}); return

        if p == "/api/backup":
            ok, msg = backup_claude_config()
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg}); return

        if p == "/api/journal":
            text = (body or {}).get("text", "").strip()
            if not text:
                self._send_json(400, {"error": "texte vide"}); return
            append_journal(text)
            self._send_json(200, {"ok": True}); return

        if p == "/api/templates/duplicate":
            s, r = duplicate_template(body or {})
            self._send_json(s, r); return

        if p == "/api/skills":
            s, r = create_skill(body or {})
            self._send_json(s, r); return

        if p == "/api/skills/copy":
            s, r = copy_skill_to_workspace(body or {})
            self._send_json(s, r); return

        m = re.match(r"^/api/skills/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = save_skill_content(m.group(1), m.group(2), (body or {}).get("content", ""))
            self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/plugins"):
            ws_id = p.split("/")[3]
            s, r = set_workspace_plugin(
                ws_id,
                (body or {}).get("plugin_id", ""),
                (body or {}).get("enabled"),
            )
            self._send_json(s, r); return

        # Resume session
        if p.startswith("/api/launch-resume/"):
            ws_id = p[len("/api/launch-resume/"):]
            ok, msg = launch_resume(ws_id)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg}); return

        # Duplicate workspace
        if p == "/api/workspaces/duplicate":
            s, r = duplicate_workspace(body or {})
            self._send_json(s, r); return

        # Save skill content
        m = re.match(r"^/api/skills/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = save_skill_content(m.group(1), m.group(2), (body or {}).get("content", ""))
            self._send_json(s, r); return

        # Create agent/command
        if p == "/api/agents":
            s, r = create_fileitem("agents", body or {})
            self._send_json(s, r); return
        if p == "/api/commands":
            s, r = create_fileitem("commands", body or {})
            self._send_json(s, r); return

        # Save agent/command content
        m = re.match(r"^/api/(agents|commands)/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = save_fileitem_content(m.group(1), m.group(2), m.group(3), (body or {}).get("content", ""))
            self._send_json(s, r); return

        # Save workspace settings (full JSON)
        if p.startswith("/api/workspaces/") and p.endswith("/settings"):
            ws_id = p.split("/")[3]
            s, r = save_workspace_settings(ws_id, (body or {}).get("content", "{}"))
            self._send_json(s, r); return

        # Patch une clé spécifique (permissions, hooks, model, …)
        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/settings/([a-zA-Z]+)$", p)
        if m:
            s, r = patch_workspace_settings(m.group(1), m.group(2), (body or {}).get("value"))
            self._send_json(s, r); return

        # Set hooks globaux
        if p == "/api/hooks/global":
            hooks = (body or {}).get("hooks") or {}
            s, r = set_global_hooks(hooks)
            self._send_json(s, r); return

        # Plugins (soft uninstall qui modifie seulement settings.json)
        if p == "/api/plugins/uninstall-soft":
            pid = (body or {}).get("plugin_id", "")
            rm = bool((body or {}).get("remove_files"))
            s, r = uninstall_plugin(pid, remove_files=rm)
            self._send_json(s, r); return

        # Plugins via CLI Claude
        if p == "/api/plugins/install":
            spec = (body or {}).get("spec", "")
            s, r = install_plugin_cli(spec)
            self._send_json(s, r); return

        if p == "/api/plugins/enable":
            pid = (body or {}).get("plugin_id", "")
            s, r = enable_plugin_cli(pid)
            self._send_json(s, r); return

        if p == "/api/plugins/disable":
            pid = (body or {}).get("plugin_id", "")
            s, r = disable_plugin_cli(pid)
            self._send_json(s, r); return

        if p == "/api/plugins/uninstall":
            pid = (body or {}).get("plugin_id", "")
            s, r = uninstall_plugin_cli(pid)
            self._send_json(s, r); return

        # Maintenance
        if p == "/api/cleanup/orphan-bats":
            self._send_json(200, cleanup_orphan_bats()); return

        self._send_json(404, {"error":"route inconnue"})

    def do_DELETE(self):
        u = urlparse(self.path)
        p = u.path
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        if p.startswith("/api/workspaces/"):
            ws_id = p[len("/api/workspaces/"):]
            purge = qs.get("purge", "").lower() in ("1", "true", "yes")
            s, r = delete_workspace(ws_id, purge=purge); self._send_json(s, r); return
        if p.startswith("/api/mcps/"):
            mcp_id = p[len("/api/mcps/"):]
            s, r = delete_mcp(mcp_id); self._send_json(s, r); return
        if p == "/api/journal":
            clear_journal()
            self._send_json(200, {"ok": True}); return
        if p.startswith("/api/templates/"):
            tpl_id = p[len("/api/templates/"):]
            s, r = delete_template(tpl_id); self._send_json(s, r); return
        if p.startswith("/api/skills/"):
            rest = p[len("/api/skills/"):]
            m = re.match(r"^(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)$", rest)
            if not m:
                self._send_json(400, {"error": "format : /api/skills/<scope>/<name>"}); return
            s, r = delete_skill(m.group(1), m.group(2))
            self._send_json(s, r); return
        m = re.match(r"^/api/(agents|commands)/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)$", p)
        if m:
            s, r = delete_fileitem(m.group(1), m.group(2), m.group(3))
            self._send_json(s, r); return
        self._send_json(404, {"error":"route inconnue"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    port = args.port
    if not port_free(HOST, port):
        new = find_port(HOST, port + 1)
        print(f"⚠ Port {port} occupé → fallback sur {new}")
        port = new

    server = ThreadingHTTPServer((HOST, port), Handler)
    url = f"http://{HOST}:{port}/"
    print(f"Dashboard Claude Workspace — {url}")
    print(f"  registry : {MCP_REGISTRY}")
    print(f"  .env.local : {ENV_FILE}  ({'présent' if ENV_FILE.exists() else 'absent'})")
    print("Ctrl+C pour arrêter.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
        server.shutdown()


if __name__ == "__main__":
    main()
