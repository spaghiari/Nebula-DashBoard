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
    _remove_dir_or_link, apply_template, list_workspaces,
    project_dir_for_path, read_json, resolve_ws_dir, safe_id, safe_path,
    sanitize_bat, validate_ws_path, write_json, write_launch_bat,
)


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
    _remove_dir_or_link(d)
    return 200, {"ok": True}


# Caractères interdits dans un chemin de fichier de template (sécurité)
_TPL_PATH_RE = re.compile(r"^[a-zA-Z0-9_./-]{1,200}$")


def _resolve_template_file(tpl_id: str, rel_path: str) -> tuple[Path, dict | None]:
    """Valide tpl_id + rel_path et renvoie le Path absolu sécurisé.

    Retourne (path, error_dict). En cas d'erreur, path est None.
    Garantit que le chemin résolu reste dans TEMPLATES_DIR/tpl_id.
    """
    if not safe_id(tpl_id):
        return None, {"error": "id invalide"}
    if not rel_path or not _TPL_PATH_RE.match(rel_path):
        return None, {"error": "chemin invalide (a-z, 0-9, _, -, /, ., max 200)"}
    if ".." in rel_path.split("/"):
        return None, {"error": "traversal interdit"}
    base = (TEMPLATES_DIR / tpl_id).resolve()
    if not base.exists():
        return None, {"error": "template introuvable"}
    target = (base / rel_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None, {"error": "chemin hors du template"}
    return target, None


def get_template_detail(tpl_id: str) -> tuple[int, dict]:
    """Retourne le détail complet d'un template : meta + arborescence des fichiers."""
    if not safe_id(tpl_id):
        return 400, {"error": "id invalide"}
    base = TEMPLATES_DIR / tpl_id
    if not base.exists():
        return 404, {"error": "Template introuvable"}
    meta = read_json(base / ".template.json", {}) or {}
    files = []
    for entry in sorted(base.rglob("*")):
        if not entry.is_file():
            continue
        if entry.name == ".template.json":
            continue
        rel = entry.relative_to(base).as_posix()
        try:
            size = entry.stat().st_size
        except OSError:
            size = 0
        files.append({"path": rel, "size": size})
    return 200, {
        "id": tpl_id,
        "label": meta.get("label") or tpl_id,
        "description": meta.get("description") or "",
        "emoji": meta.get("emoji") or "📦",
        "files": files,
        "path": str(base),
    }


def get_template_file(tpl_id: str, rel_path: str) -> tuple[int, dict]:
    target, err = _resolve_template_file(tpl_id, rel_path)
    if err:
        return 400, err
    if not target.exists() or not target.is_file():
        return 404, {"error": "fichier introuvable"}
    try:
        size = target.stat().st_size
        if size > 512 * 1024:
            return 200, {"path": rel_path, "size": size, "content": "", "binary": True, "truncated": False, "error": "fichier > 512 Kio non éditable"}
        data = target.read_bytes()
        try:
            content = data.decode("utf-8")
            binary = False
        except UnicodeDecodeError:
            content = ""
            binary = True
        return 200, {"path": rel_path, "size": size, "content": content, "binary": binary}
    except OSError as e:
        return 500, {"error": str(e)}


def write_template_file(tpl_id: str, rel_path: str, content: str) -> tuple[int, dict]:
    target, err = _resolve_template_file(tpl_id, rel_path)
    if err:
        return 400, err
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Backup si existant
        if target.exists():
            target.with_suffix(target.suffix + ".bak").write_bytes(target.read_bytes())
        target.write_text(content, encoding="utf-8")
        log.info("template file written: %s / %s", tpl_id, rel_path)
        return 200, {"ok": True, "path": rel_path, "size": target.stat().st_size}
    except OSError as e:
        return 500, {"error": str(e)}


def delete_template_file(tpl_id: str, rel_path: str) -> tuple[int, dict]:
    target, err = _resolve_template_file(tpl_id, rel_path)
    if err:
        return 400, err
    if not target.exists() or not target.is_file():
        return 404, {"error": "fichier introuvable"}
    try:
        target.unlink()
        # Nettoie les dossiers parents vides
        parent = target.parent
        base = (TEMPLATES_DIR / tpl_id).resolve()
        while parent != base and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        return 200, {"ok": True}
    except OSError as e:
        return 500, {"error": str(e)}


def update_template_meta(tpl_id: str, payload: dict) -> tuple[int, dict]:
    """Met à jour label/description/emoji dans .template.json."""
    if not safe_id(tpl_id):
        return 400, {"error": "id invalide"}
    base = TEMPLATES_DIR / tpl_id
    if not base.exists():
        return 404, {"error": "template introuvable"}
    with _MUTATION_LOCK:
        meta = read_json(base / ".template.json", {}) or {}
        if "label" in payload: meta["label"] = (payload.get("label") or tpl_id).strip()
        if "description" in payload: meta["description"] = (payload.get("description") or "").strip()
        if "emoji" in payload: meta["emoji"] = (payload.get("emoji") or "📦").strip()
        write_json(base / ".template.json", meta)
    return 200, {"ok": True, "meta": meta}


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
    with _MUTATION_LOCK:
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


def get_global_hooks() -> dict:
    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    return settings.get("hooks") or {}


def set_global_hooks(hooks: dict) -> tuple[int, dict]:
    with _MUTATION_LOCK:
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
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
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
        except OSError as e:
            log.warning("session illisible %s : %s", jsonl, e)
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
    write_launch_bat(new_id, label, str(dst))

    # registre
    with _MUTATION_LOCK:
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


def launch_resume(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"ok": False, "error": "id invalide"}
    w = next((x for x in list_workspaces() if x["id"] == ws_id), None)
    if not w:
        return 404, {"ok": False, "error": "workspace absent"}
    path = w.get("path", "")
    if not safe_path(path):
        return 400, {"ok": False, "error": "chemin de workspace invalide"}
    try:
        # /D définit le répertoire de démarrage du nouveau cmd (évite le double-quotage
        # mal géré par list2cmdline quand on enchaîne `cd /d "path" && ...`).
        # /k garde la fenêtre ouverte après exécution (utile si claude -c termine ou échoue).
        subprocess.Popen(
            ["cmd", "/c", "start", "", "/D", path, "cmd", "/k", "claude -c"],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
        return 200, {"ok": True, "message": f"Reprise session : {ws_id}"}
    except OSError as e:
        return 500, {"ok": False, "error": f"Erreur : {e}"}


_resolve_ws_dir = resolve_ws_dir  # alias rétro-compat (centralisé dans helpers.py)


def export_workspace(ws_id: str) -> tuple[int, bytes | dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = _resolve_ws_dir(ws_id)
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


def _workspace_settings_path(ws_id: str) -> Path:
    return _resolve_ws_dir(ws_id) / ".claude" / "settings.json"


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
    write_launch_bat(ws_id, label, str(ws_dir))

    with _MUTATION_LOCK:
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
    with _MUTATION_LOCK:
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
        if "path" in payload:
            new_path = (payload.get("path") or "").strip()
            if new_path:
                ok, err = validate_ws_path(new_path)
                if not ok:
                    return 400, {"error": f"chemin invalide : {err}"}
                entry["path"] = str(Path(new_path)).rstrip("\\/")
        ws_list[idx] = entry
        write_json(WORKSPACES_JSON, data)
    write_launch_bat(ws_id, entry["label"], entry["path"])
    return 200, {"ok": True, "workspace": entry}


def delete_workspace(ws_id: str, purge: bool = False) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    with _MUTATION_LOCK:
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
        ws_dir = _resolve_ws_dir(ws_id)
        if ws_dir.exists():
            _remove_dir_or_link(ws_dir)
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
    ws_dir = _resolve_ws_dir(ws_id)
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


# Fichiers éditables depuis la vue config (chemin relatif → chemin absolu autorisé)
_EDITABLE_FILES: dict[str, list[str]] = {
    "CLAUDE.md":              ["CLAUDE.md"],
    "notes.md":               ["notes.md"],
    ".claude/settings.json":  [".claude", "settings.json"],
}

def write_workspace_file(ws_id: str, filename: str, content: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    if filename not in _EDITABLE_FILES:
        return 403, {"error": f"Fichier non éditable : {filename}. Autorisés : {', '.join(_EDITABLE_FILES)}"}
    ws_dir = _resolve_ws_dir(ws_id)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}
    target = ws_dir.joinpath(*_EDITABLE_FILES[filename])
    target.parent.mkdir(parents=True, exist_ok=True)
    with _MUTATION_LOCK:
        if target.exists():
            target.with_suffix(target.suffix + ".bak").write_bytes(target.read_bytes())
        target.write_text(content, encoding="utf-8")
    log.info("workspace file written: %s / %s", ws_id, filename)
    return 200, {"ok": True, "path": str(target)}


def register_existing_workspace(payload: dict) -> tuple[int, dict]:
    """Enregistre un dossier existant comme workspace sans créer de fichiers.

    Contrairement à create_workspace, ne touche pas au contenu du dossier.
    Auto-suffixe l'ID en cas de collision et renvoie l'ID effectif au front.
    """
    requested_id = re.sub(r'[^a-zA-Z0-9_-]', '-', (payload.get("id") or "").strip())[:40].strip('-')
    path = (payload.get("path") or "").strip()
    label = sanitize_bat((payload.get("label") or requested_id).strip()) or requested_id

    if not safe_id(requested_id):
        return 400, {"error": f"id invalide après nettoyage : '{requested_id}'"}

    ok, err = validate_ws_path(path)
    if not ok:
        return 400, {"error": err}

    path_norm = str(Path(path)).rstrip("\\/")
    path_exists = Path(path_norm).exists()

    with _MUTATION_LOCK:
        data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
        data.setdefault("workspaces", [])

        if any(w.get("path", "").lower() == path_norm.lower() for w in data["workspaces"]):
            return 409, {"error": f"Chemin déjà enregistré : {path_norm}"}

        # Auto-suffix si l'ID est déjà pris
        ws_id = requested_id
        suffix = 2
        while any(w["id"] == ws_id for w in data["workspaces"]):
            ws_id = f"{requested_id}-{suffix}"
            suffix += 1
            if suffix > 99:
                return 409, {"error": f"Trop de conflits d'ID pour : {requested_id}"}

        data["workspaces"].append({
            "id": ws_id,
            "label": label,
            "emoji": (payload.get("emoji") or "📁").strip(),
            "description": (payload.get("description") or "").strip(),
            "path": path_norm,
            "template": "imported",
        })
        write_json(WORKSPACES_JSON, data)

    try:
        write_launch_bat(ws_id, label, path_norm)
    except Exception as e:
        log.warning("write_launch_bat failed for %s: %s", ws_id, e)

    log.info("workspace imported: %s → %s (path_exists=%s)", ws_id, path_norm, path_exists)
    return 201, {
        "ok": True,
        "id": ws_id,
        "renamed": ws_id != requested_id,
        "requested_id": requested_id,
        "path_exists": path_exists,
    }
