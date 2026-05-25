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




def setup_logging(level: int = logging.INFO) -> None:
    """Initialise le logger avec console + fichier rotatif (5 MB × 5)."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log.setLevel(level)
    log.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    log.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "dashboard.log",
        maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s")
    )
    log.addHandler(file_handler)


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


# Variables .env.local — implémentation déplacée dans dashcore/env_local.py
# Re-exports pour compat ascendante
from dashcore.env_local import (  # noqa: E402,F401
    load_env_local, set_env_var, delete_env_var, substitute_env,
    is_encrypted_mode, enable_encryption, disable_encryption, env_health,
    export_plain_text, strip_invisible,
)


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


# launch_script / list_workspaces / cleanup_orphan_bats
# déplacés dans dashcore/workspace_io.py (re-exports en bas de fichier)


def parse_skill_frontmatter(skill_md: Path) -> dict:
    """Lit les clés name/description/model de la frontmatter YAML d'un SKILL.md."""
    meta = {}
    try:
        with skill_md.open("r", encoding="utf-8", errors="replace") as f:
            text = f.read(3000)
    except OSError:
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


def global_search(q: str) -> dict:
    q = (q or "").strip().lower()
    if not q:
        return {"results": []}
    results = []

    from dashcore.workspace_io import list_workspaces  # import tardif (cycle)
    for w in list_workspaces():
        hay = f"{w.get('id','')} {w.get('label','')} {w.get('description','')}".lower()
        if q in hay:
            results.append({"kind": "workspace", "id": w["id"], "label": w.get("label"), "route": f"#/workspace/{w['id']}"})
    for m in read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", []):
        hay = f"{m.get('id','')} {m.get('name','')} {m.get('description','')} {m.get('notes','')}".lower()
        if q in hay:
            results.append({"kind": "mcp", "id": m["id"], "label": m.get("name"), "route": "#/mcps"})
    # Import tardif pour éviter les cycles dashcore.helpers ↔ dashcore.api_{plugins,workspaces}
    from dashcore.api_plugins import list_skills_global
    from dashcore.api_workspaces import list_templates
    for s in list_skills_global():
        if q in (s["name"] + " " + s["description"]).lower():
            results.append({"kind": "skill", "id": s["id"], "label": s["name"], "route": "#/tools"})
    for t in list_templates():
        if q in (t["id"] + " " + t["label"] + " " + t["description"]).lower():
            results.append({"kind": "template", "id": t["id"], "label": t["label"], "route": "#/templates"})
    return {"results": results[:40]}


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


# project_dir_for_path / resolve_ws_dir / validate_ws_path / write_launch_bat
# / workspace_stats / all_stats / sanity_check
# déplacés dans dashcore/workspace_io.py (re-exports en bas de fichier)


def _remove_dir_or_link(p: Path) -> None:
    """shutil.rmtree refuse un symlink/junction pointant sur un dossier.
    On tente unlink (symlink, junction, fichier) puis rmtree (vrai dossier)."""
    try:
        p.unlink()
        return
    except (IsADirectoryError, PermissionError, OSError):
        pass
    shutil.rmtree(p)


OPEN_TARGETS = {
    "claude-json": CLAUDE_JSON,
    "claude-settings": CLAUDE_SETTINGS,
    "root-claude-md": ROOT / "CLAUDE.md",
    "registry": MCP_REGISTRY,
    "env-local": ENV_FILE,
    "workspaces-json": WORKSPACES_JSON,
    "global-memory": ROOT / "memory",
    "mcp-recipes-local": ROOT / "dashboard" / "data" / "mcp_recipes.local.json",
}


def open_target(key: str) -> tuple[int, dict]:
    if key.startswith("workspace-claude-md:"):
        ws_id = key.split(":", 1)[1]
        if not safe_id(ws_id):
            return 400, {"ok": False, "error": "id invalide"}
        p = resolve_ws_dir(ws_id) / "CLAUDE.md"
    elif key.startswith("workspace-dir:"):
        ws_id = key.split(":", 1)[1]
        if not safe_id(ws_id):
            return 400, {"ok": False, "error": "id invalide"}
        p = resolve_ws_dir(ws_id)
    elif key.startswith("template:"):
        tpl_id = key.split(":", 1)[1]
        if not safe_id(tpl_id):
            return 400, {"ok": False, "error": "id invalide"}
        p = TEMPLATES_DIR / tpl_id
    elif key.startswith("skill-global:"):
        name = key.split(":", 1)[1]
        if not safe_id(name):
            return 400, {"ok": False, "error": "nom invalide"}
        p = CLAUDE_HOME / "skills" / name
    elif key.startswith("skill-ws:"):
        parts = key.split(":")
        if len(parts) != 3 or not safe_id(parts[1]) or not safe_id(parts[2]):
            return 400, {"ok": False, "error": "format : skill-ws:<ws_id>:<name>"}
        p = WORKSPACES_DIR / parts[1] / ".claude" / "skills" / parts[2]
    else:
        p = OPEN_TARGETS.get(key)
        if p is None:
            return 400, {"ok": False, "error": "cible inconnue"}

    if not p.exists():
        # Fichier absent : propose notepad pour les cas où on veut le créer
        if key == "env-local":
            try:
                subprocess.Popen(["notepad", str(p)])
                return 200, {"ok": True, "message": f"Notepad ouvert (fichier sera créé au save) : {p}"}
            except OSError as e:
                return 500, {"ok": False, "error": f"Erreur : {e}"}
        return 404, {"ok": False, "error": f"Introuvable : {p}"}
    try:
        if sys.platform == "win32":
            try:
                os.startfile(str(p))  # noqa
            except OSError:
                # Pas d'association pour .env ou .local → fallback notepad
                subprocess.Popen(["notepad", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return 200, {"ok": True, "message": f"Ouvert : {p}"}
    except OSError as e:
        return 500, {"ok": False, "error": f"Erreur : {e}"}


def backup_claude_config() -> tuple[int, dict]:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    copied = []
    for name, src in [("claude.json", CLAUDE_JSON), ("settings.json", CLAUDE_SETTINGS)]:
        if src.exists():
            dst = BACKUPS_DIR / f"{stamp}-{name}"
            shutil.copy2(src, dst)
            copied.append(dst.name)
    if not copied:
        return 400, {"ok": False, "error": "Aucun fichier à sauvegarder"}
    return 200, {"ok": True, "message": "Sauvegardés : " + ", ".join(copied)}


def restore_backup(name: str) -> tuple[int, dict]:
    """Restaure un fichier de sauvegarde vers sa destination Claude.

    Réversibilité (lot D-3) : un backup auto de l'état courant est créé AVANT
    tout écrasement (via `backup_claude_config`) -- la restauration est donc
    annulable en restaurant le snapshot fraîchement créé.

    Périmètre identique à `backup_claude_config` : on ne restaure que les
    deux fichiers couverts par la sauvegarde (claude.json + settings.json).
    Le `name` doit correspondre à une entrée existante de `list_backups()`
    et se terminer par l'un des suffixes connus.
    """
    name = (name or "").strip()
    # Garde-fou anti-traversal : pas de séparateur de chemin, doit exister
    # dans le dossier de backups (et donc dedans, pas ailleurs).
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return 400, {"ok": False, "error": "nom de sauvegarde invalide"}

    src = BACKUPS_DIR / name
    try:
        # resolve() pour neutraliser tout ".." résiduel et confiner à BACKUPS_DIR.
        if BACKUPS_DIR.resolve() not in src.resolve().parents:
            return 400, {"ok": False, "error": "nom de sauvegarde invalide"}
    except OSError:
        return 400, {"ok": False, "error": "nom de sauvegarde invalide"}
    if not src.is_file():
        return 404, {"ok": False, "error": "sauvegarde introuvable"}

    # Mappe le suffixe du fichier de backup vers sa destination réelle.
    suffix_to_dst = {"-claude.json": CLAUDE_JSON, "-settings.json": CLAUDE_SETTINGS}
    dst = next((d for sfx, d in suffix_to_dst.items() if name.endswith(sfx)), None)
    if dst is None:
        return 400, {"ok": False, "error": "type de sauvegarde non restaurable"}

    # 1. Backup auto de l'état courant AVANT d'écraser (réversibilité).
    status, info = backup_claude_config()
    auto_backup = info.get("message") if status == 200 else None

    # 2. Restauration.
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as e:
        return 500, {"ok": False, "error": f"restauration impossible : {e}"}

    msg = f"Restauré : {dst.name}"
    return 200, {
        "ok": True,
        "message": msg,
        "restored": dst.name,
        "auto_backup": auto_backup,
    }


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


# ─────────────────────────────────────────────────────────────────────────
# Re-exports : modules extraits, gardés ici pour compat ascendante.
# (Importer depuis le module dédié quand on écrit du nouveau code.)
# ─────────────────────────────────────────────────────────────────────────

from dashcore.journal import (  # noqa: E402,F401
    read_journal, append_journal, clear_journal, JOURNAL_ENTRY,
)
from dashcore.workspace_io import (  # noqa: E402,F401
    list_workspaces, cleanup_orphan_bats, project_dir_for_path,
    resolve_ws_dir, validate_ws_path, write_launch_bat,
    workspace_stats, all_stats, sanity_check, launch_script,
)


