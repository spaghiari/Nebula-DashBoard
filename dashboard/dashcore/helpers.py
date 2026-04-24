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


def set_env_var(key: str, value: str) -> tuple[int, dict]:
    """Upsert une clé dans .env.local en préservant les commentaires existants."""
    if not key or not ENV_KEY_RE.match(key):
        return 400, {"error": "clé invalide (lettres, chiffres, underscore ; ne commence pas par un chiffre)"}
    if "\n" in value or "\r" in value:
        return 400, {"error": "la valeur contient un saut de ligne"}

    with _MUTATION_LOCK:
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
        new_lines = []
        found = False
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k == key:
                    new_lines.append(f"{key}={value}")
                    found = True
                    continue
            new_lines.append(line)
        if not found:
            if new_lines and new_lines[-1].strip():
                new_lines.append("")
            new_lines.append(f"{key}={value}")
        ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    log.info("env: set %s", key)
    return 200, {"ok": True, "key": key}


def delete_env_var(key: str) -> tuple[int, dict]:
    """Retire une clé de .env.local (préserve le reste)."""
    if not key or not ENV_KEY_RE.match(key):
        return 400, {"error": "clé invalide"}
    if not ENV_FILE.exists():
        return 404, {"error": ".env.local absent"}

    with _MUTATION_LOCK:
        kept = []
        removed = False
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k == key:
                    removed = True
                    continue
            kept.append(line)
        if not removed:
            return 404, {"error": f"clé absente : {key}"}
        ENV_FILE.write_text("\n".join(kept) + "\n", encoding="utf-8")

    log.info("env: delete %s", key)
    return 200, {"ok": True, "key": key}


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


def list_workspaces() -> list[dict]:
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    return data.get("workspaces", [])


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


def project_dir_for_path(path: Path) -> Path | None:
    """Trouve le dossier ~/.claude/projects/<encodé> qui correspond à `path`.

    Claude encode le chemin en remplaçant `:` et `\\` par `-`. On encode
    directement le path cible plutôt que d'essayer de décoder les noms
    de dossier (décodage ambigu dès qu'un segment contient un `-`)."""
    if not CLAUDE_PROJECTS.exists():
        return None
    target = str(path.resolve())
    encoded = target.replace(":", "-").replace("\\", "-").replace("/", "-")
    candidate = CLAUDE_PROJECTS / encoded
    if candidate.is_dir():
        return candidate
    enc_lower = encoded.lower()
    for d in CLAUDE_PROJECTS.iterdir():
        if d.is_dir() and d.name.lower() == enc_lower:
            return d
    return None


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


def sanity_check() -> dict:
    """Compare registre ↔ .mcp.json effectivement écrits dans chaque workspace."""
    # Import tardif pour éviter le cycle dashcore.helpers ↔ dashcore.api_mcps
    from dashcore.api_mcps import mcp_applies_to, build_mcp_server_entry

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


