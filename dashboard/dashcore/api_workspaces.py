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
    PATH_UNSAFE, STATIC_TYPES, ENV_KEY_RE, ALLOWED_TRANSPORTS, _MUTATION_LOCK, log,
)


from dashcore.helpers import (
    _remove_dir_or_link, apply_template, list_workspaces,
    project_dir_for_path, read_json, resolve_ws_dir, safe_id, safe_path,
    sanitize_bat, validate_ws_path, write_json, write_launch_bat,
)


def list_templates() -> list[dict]:
    # Import local pour eviter le cycle d'import api_overlays -> helpers ->
    # api_workspaces. Les overlays sont des dossiers de `templates/`
    # marques par `.nebula-overlay.json` -- on les filtre ici pour qu'ils
    # n'apparaissent pas dans la liste des templates (ils ont leur propre
    # route `/api/overlays`).
    from dashcore.api_overlays import is_overlay_dir
    if not TEMPLATES_DIR.exists():
        return []
    out = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if not d.is_dir():
            continue
        if is_overlay_dir(d):
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


_TEMPLATE_STARTERS: dict[str, dict[str, str]] = {
    "empty": {},
    "standard": {
        "CLAUDE.md": (
            "# {{label}}\n\n"
            "{{description}}\n\n"
            "## Contexte\n\n"
            "- ID : `{{name}}`\n"
            "- Créé le : {{date}}\n"
            "- Outils / contexte : {{tools}}\n\n"
            "## Conventions\n\n"
            "- Réponds en français.\n"
            "- Privilégie des solutions locales / self-hosted.\n"
            "- Toujours fournir une version testable immédiatement.\n"
        ),
        "README.md": (
            "# {{emoji}} {{label}}\n\n"
            "{{description}}\n\n"
            "## Démarrage\n\n"
            "```bash\n"
            "claude\n"
            "```\n"
        ),
        ".gitignore": (
            "# Secrets & env\n"
            ".env\n.env.local\n\n"
            "# OS\n"
            ".DS_Store\nThumbs.db\n\n"
            "# Editors\n"
            ".vscode/\n.idea/\n*.swp\n"
        ),
    },
    "python": {
        "CLAUDE.md": (
            "# {{label}}\n\n{{description}}\n\n"
            "## Stack\n\n- Python 3.10+\n- Outils : {{tools}}\n\n"
            "## Conventions\n\n- Type hints partout\n- `requirements.txt` à jour\n"
        ),
        "requirements.txt": "# Ajoute tes dépendances ici, une par ligne\n",
        ".gitignore": (
            "# Python\n__pycache__/\n*.py[cod]\n*$py.class\n*.so\n.Python\n"
            "build/\ndist/\n*.egg-info/\n.venv/\nvenv/\nenv/\n\n"
            "# Secrets\n.env\n.env.local\n\n"
            "# Editors\n.vscode/\n.idea/\n"
        ),
        "README.md": "# {{emoji}} {{label}}\n\n{{description}}\n\n## Setup\n\n```bash\npython -m venv .venv\n.venv\\Scripts\\activate\npip install -r requirements.txt\n```\n",
    },
    "node": {
        "CLAUDE.md": (
            "# {{label}}\n\n{{description}}\n\n"
            "## Stack\n\n- Node.js\n- Outils : {{tools}}\n"
        ),
        "package.json": (
            "{\n"
            "  \"name\": \"{{name}}\",\n"
            "  \"version\": \"0.1.0\",\n"
            "  \"description\": \"{{description}}\",\n"
            "  \"scripts\": {\n"
            "    \"start\": \"node index.js\"\n"
            "  }\n"
            "}\n"
        ),
        ".gitignore": (
            "# Node\nnode_modules/\nnpm-debug.log*\nyarn-debug.log*\nyarn-error.log*\n"
            ".pnpm-debug.log*\ndist/\nbuild/\n\n"
            "# Secrets\n.env\n.env.local\n\n"
            "# Editors\n.vscode/\n.idea/\n"
        ),
        "README.md": "# {{emoji}} {{label}}\n\n{{description}}\n\n## Setup\n\n```bash\nnpm install\nnpm start\n```\n",
    },
    "docker": {
        "CLAUDE.md": (
            "# {{label}}\n\n{{description}}\n\n"
            "## Stack\n\n- Docker / docker-compose\n- Outils : {{tools}}\n"
        ),
        "Dockerfile": (
            "FROM alpine:latest\n\n"
            "WORKDIR /app\n\n"
            "# COPY . .\n"
            "# RUN ...\n\n"
            "CMD [\"sh\"]\n"
        ),
        "docker-compose.yml": (
            "version: '3.8'\n\n"
            "services:\n"
            "  {{name}}:\n"
            "    build: .\n"
            "    container_name: {{name}}\n"
            "    restart: unless-stopped\n"
            "    # ports:\n"
            "    #   - \"8080:8080\"\n"
            "    # environment:\n"
            "    #   - KEY=VALUE\n"
        ),
        ".dockerignore": "node_modules/\n.git/\n.env\n.env.local\n*.log\n",
        ".gitignore": ".env\n.env.local\n*.log\n",
        "README.md": "# {{emoji}} {{label}}\n\n{{description}}\n\n## Setup\n\n```bash\ndocker compose up -d\n```\n",
    },
}


def create_template(payload: dict) -> tuple[int, dict]:
    tpl_id = (payload.get("id") or "").strip()
    label = (payload.get("label") or tpl_id).strip()
    description = (payload.get("description") or "").strip()
    emoji = (payload.get("emoji") or "📦").strip()
    starter = (payload.get("starter") or "empty").strip()

    if not safe_id(tpl_id):
        return 400, {"error": "id invalide (a-z, 0-9, _, -, max 40)"}
    if starter not in _TEMPLATE_STARTERS:
        return 400, {"error": f"starter inconnu : {starter}"}

    dst = TEMPLATES_DIR / tpl_id
    if dst.exists():
        return 409, {"error": f"Template déjà existant : {tpl_id}"}

    dst.mkdir(parents=True)
    write_json(dst / ".template.json", {"label": label, "description": description, "emoji": emoji})
    for rel_path, content in _TEMPLATE_STARTERS[starter].items():
        f = dst / rel_path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    return 201, {"ok": True, "id": tpl_id, "starter": starter}


_KNOWN_PLACEHOLDERS = frozenset({"name", "label", "description", "tools", "emoji", "date"})
_PLACEHOLDER_RE = re.compile(r"\{\{(name|label|description|tools|emoji|date)\}\}")
# Candidat placeholder : 1 ou 2 accolades, espaces tolérés, autour d'un mot.
# Capture les formes mal écrites (accolade simple, espaces, nom inconnu) pour
# les distinguer des placeholders valides exacts. Le (?<!\$) évite de
# flagger les interpolations env shell ${HOME} (qui ne sont pas des
# placeholders de template Nebula).
_PLACEHOLDER_CANDIDATE_RE = re.compile(r"(?<!\$)\{\{?\s*(\w+)\s*\}?\}")
# Placeholder "runtime" : `{{snake_case}}` syntaxiquement clean mais inconnu
# de Nebula. Convention : c'est un slot que Claude remplira au moment de
# rediger son rapport (ex. `{{cible}}`, `{{nb_critique}}` dans un template
# audit). On les groupe en `info` au lieu d'inonder le linter de warn.
_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def analyze_template_quality(tpl_id: str) -> tuple[int, dict]:
    """Scan d'un template et retourne suggestions/problèmes (badges qualité)."""
    if not safe_id(tpl_id):
        return 400, {"error": "id invalide"}
    base = TEMPLATES_DIR / tpl_id
    if not base.exists():
        return 404, {"error": "introuvable"}

    suggestions: list[dict] = []
    placeholders_used: set[str] = set()
    # Mal-formes : 1 ligne `warn` par occurrence (texte litteral ne sera pas
    # substitue). Cle = texte brut fautif, valeur = chemin du fichier.
    malformed_placeholders: dict[str, str] = {}
    # Runtime placeholders : `{{snake_case}}` clean mais inconnu de Nebula.
    # On groupe par fichier pour eviter de cracher 80 lignes sur un seul
    # template audit. Cle = chemin de fichier, valeur = liste ordonnee
    # (deduplicee) des placeholders runtime trouves dans ce fichier.
    runtime_placeholders_per_file: dict[str, list[str]] = {}
    has_claude_md = False
    has_gitignore = False
    has_readme = False
    forbidden = []
    big_files = []

    for entry in base.rglob("*"):
        if entry.is_dir():
            if entry.name in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}:
                forbidden.append(str(entry.relative_to(base)).replace("\\", "/"))
            continue
        if not entry.is_file() or entry.name == ".template.json":
            continue
        rel = entry.relative_to(base).as_posix()
        if rel.lower() == "claude.md":
            has_claude_md = True
        elif rel == ".gitignore":
            has_gitignore = True
        elif rel.lower() == "readme.md":
            has_readme = True
        try:
            size = entry.stat().st_size
            if size > 512 * 1024:
                big_files.append({"path": rel, "size": size})
                continue
            text = entry.read_text(encoding="utf-8", errors="ignore")
            for m in _PLACEHOLDER_RE.finditer(text):
                placeholders_used.add(m.group(1))
            # Classification des candidats :
            #   - exact `{{<known>}}` (sans espace) -> placeholder valide, ok.
            #   - exact `{{<snake_case_inconnu>}}` -> placeholder "runtime"
            #     (Claude le remplira au moment de generer son rapport),
            #     niveau info groupe par fichier.
            #   - tout le reste ({label}, {{ name }}, {{X-Y}}...) -> mal forme,
            #     niveau warn 1 ligne par occurrence (resterait litteral).
            seen_runtime_in_file: set[str] = set()
            for m in _PLACEHOLDER_CANDIDATE_RE.finditer(text):
                raw = m.group(0)
                word = m.group(1)
                is_exact_double = (raw == "{{" + word + "}}")
                if is_exact_double and word in _KNOWN_PLACEHOLDERS:
                    continue  # placeholder valide Nebula
                if is_exact_double and _SNAKE_CASE_RE.match(word):
                    # `{{snake_case}}` bien forme mais inconnu = placeholder
                    # runtime. Groupe par fichier, dedup par word.
                    if word not in seen_runtime_in_file:
                        seen_runtime_in_file.add(word)
                        runtime_placeholders_per_file.setdefault(rel, []).append(word)
                    continue
                # Sinon : vraiment mal forme (accolade simple, espaces,
                # caracteres invalides). Warn 1 ligne par occurrence.
                if raw not in malformed_placeholders:
                    malformed_placeholders[raw] = rel
        except OSError:
            continue

    if not has_claude_md:
        suggestions.append({"level": "warn", "msg": "Pas de CLAUDE.md — Claude n'aura pas de contexte projet à la session."})
    if not has_gitignore:
        suggestions.append({"level": "warn", "msg": "Pas de .gitignore — risque de committer des secrets ou des artefacts."})
    if not has_readme:
        suggestions.append({"level": "info", "msg": "Pas de README.md — bonne pratique pour documenter le projet."})
    for f in forbidden:
        suggestions.append({"level": "error", "msg": f"Dossier interdit dans un template : {f} (sera copié dans chaque workspace)."})
    for bf in big_files:
        suggestions.append({"level": "warn", "msg": f"Fichier > 512 Kio non éditable : {bf['path']}."})
    for raw, rel in sorted(malformed_placeholders.items()):
        suggestions.append({
            "level": "warn",
            "msg": f"Placeholder mal formé : « {raw} » dans {rel} — "
                   f"ne sera pas substitué et restera littéral dans le workspace créé. "
                   f"Placeholders valides : {', '.join('{{' + p + '}}' for p in sorted(_KNOWN_PLACEHOLDERS))}.",
        })
    # Runtime placeholders : 1 ligne `info` par fichier (premiers 10 + queue
    # ". . . et N autres"). Format compact pour ne pas saturer la modale
    # Qualite d'un template audit qui en compte 90.
    for rel in sorted(runtime_placeholders_per_file):
        words = runtime_placeholders_per_file[rel]
        shown = ", ".join("{{" + w + "}}" for w in words[:10])
        tail = f" — et {len(words) - 10} autres" if len(words) > 10 else ""
        n = len(words)
        suggestions.append({
            "level": "info",
            "msg": f"{n} placeholder{'s' if n > 1 else ''} runtime détecté{'s' if n > 1 else ''} "
                   f"dans {rel} (rempli{'s' if n > 1 else ''} par Claude au moment d'utiliser "
                   f"le template) : {shown}{tail}.",
        })

    declared = {"name", "label", "description", "tools", "emoji", "date"}
    unused_critical = {"name", "label"} - placeholders_used
    if unused_critical:
        suggestions.append({"level": "info", "msg": f"Placeholders critiques jamais utilisés : {', '.join(sorted(unused_critical))} — le template ne s'adapte pas au workspace créé."})

    score = "ok"
    if any(s["level"] == "error" for s in suggestions):
        score = "error"
    elif any(s["level"] == "warn" for s in suggestions):
        score = "warn"

    return 200, {
        "score": score,
        "suggestions": suggestions,
        "placeholders_used": sorted(placeholders_used),
        "stats": {
            "has_claude_md": has_claude_md,
            "has_gitignore": has_gitignore,
            "has_readme": has_readme,
        },
    }


def preview_template_file(tpl_id: str, rel_path: str) -> tuple[int, dict]:
    """Retourne le contenu du fichier après substitution des placeholders avec
    des valeurs de test (pour l'aperçu GUI)."""
    target, err = _resolve_template_file(tpl_id, rel_path)
    if err:
        return 400, err
    if not target.exists() or not target.is_file():
        return 404, {"error": "fichier introuvable"}
    test_vars = {
        "name": "mon-projet",
        "label": "Mon Projet",
        "description": "Description de test",
        "tools": "VS Code, Claude Code",
        "emoji": "🚀",
        "date": dt.date.today().isoformat(),
    }
    try:
        size = target.stat().st_size
        if size > 512 * 1024:
            return 200, {"path": rel_path, "preview": "", "binary": True, "error": "fichier > 512 Kio"}
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return 200, {"path": rel_path, "preview": "", "binary": True}
        rendered = _PLACEHOLDER_RE.sub(lambda m: test_vars.get(m.group(1), m.group(0)), content)
        return 200, {"path": rel_path, "preview": rendered, "test_vars": test_vars}
    except OSError as e:
        return 500, {"error": str(e)}


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
    # Garde-fou : un fichier .json de template doit être un JSON valide.
    # Sinon un settings.json cassé se propagerait à CHAQUE workspace créé
    # depuis ce template (le copy ne re-valide pas). Aligné sur
    # save_workspace_settings qui valide déjà le JSON.
    if rel_path.lower().endswith(".json"):
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return 400, {"error": f"JSON invalide ({rel_path}) : {e}. "
                                  "Corrige la syntaxe avant d'enregistrer - "
                                  "ce fichier serait copié cassé dans chaque workspace."}
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


_SETTINGS_ALLOWED_ROOT_KEYS = frozenset({
    "permissions", "hooks", "model", "env", "effortLevel",
    "enabledPlugins", "mcpServers", "alwaysAllowedTools",
    "outputStyle", "includeCoAuthoredBy",
})
_SETTINGS_MAX_BYTES = 256 * 1024  # 256 Kio — un settings.json sain ne dépasse jamais ça


def save_workspace_settings(ws_id: str, content: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    if len(content) > _SETTINGS_MAX_BYTES:
        return 413, {"error": f"settings.json trop gros (> {_SETTINGS_MAX_BYTES} octets)"}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return 400, {"error": f"JSON invalide : {e}"}
    if not isinstance(parsed, dict):
        return 400, {"error": "doit être un objet JSON"}
    unknown = set(parsed.keys()) - _SETTINGS_ALLOWED_ROOT_KEYS
    if unknown:
        return 400, {"error": f"clés racine non reconnues : {', '.join(sorted(unknown))}"}

    # Lint structurel des hooks embarqués (3a bloquant) : même garde-fou que
    # le patch partiel, pour ne pas laisser passer un settings.json complet
    # contenant un chemin de hook relatif.
    hook_warnings: list[dict] = []
    if isinstance(parsed.get("hooks"), dict):
        errors, hook_warnings = _lint_hooks_structure(parsed["hooks"], project_dir=resolve_ws_dir(ws_id))
        if errors:
            return 400, {"error": errors[0]["msg"], "hook_errors": errors, "hook_warnings": hook_warnings}

    path = _workspace_settings_path(ws_id)
    with _MUTATION_LOCK:
        if path.exists():
            bak = path.with_suffix(".json.bak")
            try:
                bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError as e:
                return 500, {"error": f"backup impossible : {e}"}
        path.parent.mkdir(parents=True, exist_ok=True)
        if parsed:
            write_json(path, parsed)
        elif path.exists():
            path.unlink()
    return 200, {"ok": True, "hook_warnings": hook_warnings}


def patch_workspace_settings(ws_id: str, key: str, value) -> tuple[int, dict]:
    """Met à jour une clé précise (permissions, hooks, model, env, effortLevel)."""
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    allowed = {"permissions", "hooks", "model", "env", "effortLevel", "enabledPlugins"}
    if key not in allowed:
        return 400, {"error": f"clé non gérée : {key}"}

    # Lint structurel des hooks (3a bloquant / 3b-3c warn). project_dir =
    # racine du workspace pour résoudre ${CLAUDE_PROJECT_DIR} (check d'existence).
    hook_warnings: list[dict] = []
    if key == "hooks" and isinstance(value, dict):
        errors, hook_warnings = _lint_hooks_structure(value, project_dir=resolve_ws_dir(ws_id))
        if errors:
            return 400, {"error": errors[0]["msg"], "hook_errors": errors, "hook_warnings": hook_warnings}

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
    return 200, {"ok": True, "hook_warnings": hook_warnings}


def get_global_hooks() -> dict:
    settings = read_json(CLAUDE_SETTINGS, {}) or {}
    return settings.get("hooks") or {}


def _hooks_settings_paths(ws_id: str | None) -> tuple[Path, Path]:
    """Retourne (settings.json, settings.json.bak) pour le scope demandé.

    ws_id None/"" => settings global (~/.claude/settings.json). Sinon le
    settings.json du workspace. Le `.bak` est écrit par `set_global_hooks`
    (global) et `save_workspace_settings` / `patch_workspace_settings` (ws).
    """
    if ws_id:
        path = _workspace_settings_path(ws_id)
    else:
        path = CLAUDE_SETTINGS
    return path, path.with_suffix(".json.bak")


def get_hooks_backup(ws_id: str | None = None) -> tuple[int, dict]:
    """Indique si un settings.json.bak existe et expose sa section `hooks`.

    Lecture seule. Sert à conditionner l'affichage du bouton « Restaurer la
    version précédente » dans la modale Hooks et à proposer un aperçu de ce
    qui serait restauré.
    """
    if ws_id and not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    path, bak = _hooks_settings_paths(ws_id)
    if not bak.exists():
        return 200, {"exists": False}
    try:
        raw = bak.read_text(encoding="utf-8")
        parsed = json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError) as e:
        # Un .bak illisible/corrompu : on le signale mais sans 500 (l'UI
        # affichera juste « sauvegarde présente mais illisible »).
        return 200, {"exists": True, "readable": False, "error": str(e)}
    hooks = parsed.get("hooks") if isinstance(parsed, dict) else None
    try:
        mtime = dt.datetime.fromtimestamp(bak.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        mtime = None
    return 200, {
        "exists": True,
        "readable": True,
        "hooks": hooks or {},
        "mtime": mtime,
    }


def restore_hooks_backup(ws_id: str | None = None) -> tuple[int, dict]:
    """Restaure settings.json depuis son .bak, en gardant la réversibilité.

    Swap atomique en mémoire : on lit l'état courant ET le .bak, puis on écrit
    l'état courant DANS le .bak (nouveau backup) avant d'écrire le contenu du
    .bak dans settings.json. Re-cliquer « Restaurer » re-swap donc -- l'action
    reste réversible et ne perd jamais la version courante.

    Périmètre : on restaure le settings.json complet (le .bak est un snapshot
    intégral du fichier, pas seulement de la section hooks).
    """
    if ws_id and not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    path, bak = _hooks_settings_paths(ws_id)
    if not bak.exists():
        return 404, {"error": "aucune sauvegarde (.bak) à restaurer"}
    try:
        bak_content = bak.read_text(encoding="utf-8")
    except OSError as e:
        return 500, {"error": f"lecture de la sauvegarde impossible : {e}"}
    # Valide que le .bak est un JSON exploitable avant tout écrasement.
    try:
        bak_parsed = json.loads(bak_content) if bak_content.strip() else {}
    except json.JSONDecodeError as e:
        return 400, {"error": f"sauvegarde corrompue (JSON invalide) : {e}"}
    if not isinstance(bak_parsed, dict):
        return 400, {"error": "sauvegarde invalide (objet JSON attendu)"}

    with _MUTATION_LOCK:
        # État courant en mémoire (peut ne pas exister si jamais sauvé).
        cur_content = path.read_text(encoding="utf-8") if path.exists() else ""
        try:
            # 1. L'état courant devient le nouveau backup (réversibilité).
            bak.write_text(cur_content, encoding="utf-8")
            # 2. On restaure l'ancien backup dans settings.json.
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, bak_parsed)
        except OSError as e:
            return 500, {"error": f"restauration impossible : {e}"}
    log.info("Hooks: settings.json restauré depuis .bak (scope=%s)", ws_id or "global")
    return 200, {"ok": True, "hooks": bak_parsed.get("hooks") or {}}


# Événements de hook reconnus par Claude Code (pour le lint 3c).
_KNOWN_HOOK_EVENTS = frozenset({
    "PreToolUse", "PostToolUse", "Notification", "UserPromptSubmit",
    "Stop", "SubagentStop", "PreCompact", "SessionStart", "SessionEnd",
})

# Token ressemblant à un chemin de script .sh dans une commande de hook.
# On capture les chemins shell-quotés ou nus se terminant par .sh.
_HOOK_SH_TOKEN_RE = re.compile(r"""["']?([^\s"']*\.sh)["']?""")


def _sh_path_is_safe(path: str) -> bool:
    """Vrai si le chemin d'un script .sh de hook est robuste au cwd.

    Sûr : variable d'env (${CLAUDE_PROJECT_DIR}/...), chemin absolu POSIX
    (/...), chemin absolu Windows (C:\\... ou C:/...), home (~/...).
    Dangereux : chemin relatif (.claude/hooks/x.sh, ./x.sh, hooks/x.sh) -
    casse dès que le shell s'exécute hors de la racine projet.
    """
    p = path.strip()
    if not p:
        return True
    if p.startswith("${") or p.startswith("$"):
        return True
    if p.startswith("~"):
        return True
    if p.startswith("/") or p.startswith("\\"):
        return True
    # Chemin absolu Windows : lettre de lecteur suivie de :\ ou :/
    if re.match(r"^[A-Za-z]:[\\/]", p):
        return True
    return False


def _lint_hooks_structure(hooks: dict, project_dir: Path | None = None) -> tuple[list[dict], list[dict]]:
    """Analyse structurelle d'un objet `hooks` Claude Code.

    Retourne (errors, warnings) :
      - errors (BLOQUANT) : chemin .sh relatif dans une command (3a).
      - warnings (non bloquant) : fichier hook absent sur disque (3b),
        clé d'événement inconnue (3c).

    `project_dir` sert à résoudre ${CLAUDE_PROJECT_DIR} pour vérifier
    l'existence des fichiers (3b). Si None, le check d'existence est sauté.
    """
    errors: list[dict] = []
    warnings: list[dict] = []
    if not isinstance(hooks, dict):
        return errors, warnings

    for event, entries in hooks.items():
        if event not in _KNOWN_HOOK_EVENTS:
            warnings.append({
                "event": event,
                "msg": f"Événement de hook inconnu : « {event} ». "
                       f"Claude Code ne déclenchera jamais ce hook. "
                       f"Événements valides : {', '.join(sorted(_KNOWN_HOOK_EVENTS))}.",
            })
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for sub in (entry.get("hooks") or []):
                if not isinstance(sub, dict):
                    continue
                command = sub.get("command") or ""
                if not isinstance(command, str):
                    continue
                for m in _HOOK_SH_TOKEN_RE.finditer(command):
                    sh_path = m.group(1)
                    if not _sh_path_is_safe(sh_path):
                        errors.append({
                            "event": event,
                            "command": command,
                            "bad_path": sh_path,
                            "msg": f"Chemin de hook relatif dans « {event} » : "
                                   f"« {sh_path} ». Un chemin relatif casse dès que le "
                                   f"shell s'exécute hors de la racine projet (toutes les "
                                   f"sessions Claude Code planteraient). Corrige en "
                                   f"${{CLAUDE_PROJECT_DIR}}/.claude/hooks/"
                                   f"{Path(sh_path).name}.",
                        })
                    elif project_dir is not None and "${CLAUDE_PROJECT_DIR}" in sh_path:
                        # 3b : résout la variable et vérifie l'existence du fichier.
                        rel = sh_path.split("${CLAUDE_PROJECT_DIR}", 1)[1].lstrip("/\\")
                        resolved = project_dir / rel
                        if not resolved.exists():
                            warnings.append({
                                "event": event,
                                "msg": f"Fichier hook introuvable : « {sh_path} » "
                                       f"(résolu : {resolved}). Le hook échouera au "
                                       f"déclenchement.",
                            })
    return errors, warnings


def get_hooks_errors(tail_lines: int = 200) -> tuple[int, dict]:
    """Lit les dernières lignes du log d'erreurs des hooks Claude Code.

    Couvre les hooks qui écrivent vers `dashboard/data/hook_errors.log`.
    Les hooks .sh classiques n'écrivent pas dans un log dédié — leur
    stderr va dans le transcript Claude Code et n'est pas accessible
    depuis Nebula. Pour étendre la couverture : ajouter
    `>> dashboard/data/hook_errors.log` dans le hook concerné.
    """
    log_path = ROOT / "dashboard" / "data" / "hook_errors.log"
    if not log_path.exists():
        return 200, {
            "exists": False,
            "lines": [],
            "path": str(log_path),
            "note": "Aucun log d'erreur hook (le fichier n'a jamais été créé). "
                    "Les hooks .sh n'écrivent pas dans un log dédié par défaut "
                    "(leur stderr va dans le transcript Claude Code).",
        }
    try:
        # Lit la fin du fichier (cap raisonnable contre fichier énorme)
        size = log_path.stat().st_size
        max_read = 256 * 1024  # 256 KB max
        with log_path.open("rb") as f:
            if size > max_read:
                f.seek(size - max_read)
                f.readline()  # skip ligne tronquée
            data = f.read()
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        lines = lines[-tail_lines:]
        return 200, {
            "exists": True,
            "lines": lines,
            "path": str(log_path),
            "size": size,
            "tail_lines": len(lines),
        }
    except OSError as e:
        return 500, {"error": f"lecture échouée : {e}"}


def set_global_hooks(hooks: dict) -> tuple[int, dict]:
    # Lint structurel : refuse un chemin .sh relatif (casserait toutes les
    # sessions). project_dir=None côté global (pas de racine déterministe
    # pour résoudre ${CLAUDE_PROJECT_DIR}), donc pas de check d'existence.
    errors, warnings = _lint_hooks_structure(hooks or {}, project_dir=None)
    if errors:
        return 400, {"error": errors[0]["msg"], "hook_errors": errors, "hook_warnings": warnings}
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
    return 200, {"ok": True, "hook_warnings": warnings}


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


def read_session_tail(ws_id: str, filename: str, offset: int = 0) -> tuple[int, dict]:
    """Lit les nouvelles entrées du fichier session depuis l'octet `offset`.

    Permet le polling live d'une session active. Retourne :
        {messages: [...nouveaux msg], new_offset: <int>, mtime: <int>, size: <int>}

    Ne renvoie que les messages user/assistant (cohérent avec
    read_session_messages). Les lignes incomplètes (pas de \\n final)
    sont ignorées et l'offset s'arrête au dernier \\n vu → la prochaine
    lecture les capturera quand elles seront flushed.
    """
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

    try:
        st = path.stat()
    except OSError as e:
        return 500, {"error": f"stat échoué : {e}"}

    # Si l'offset > size, le fichier a été tronqué/recréé : on relit depuis 0
    if offset < 0 or offset > st.st_size:
        offset = 0

    messages: list[dict] = []
    new_offset = offset
    try:
        with path.open("rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError as e:
        return 500, {"error": f"lecture échouée : {e}"}

    # Décodage et split par lignes complètes (terminées par \n)
    text = data.decode("utf-8", errors="replace")
    if not text.endswith("\n"):
        # Dernière ligne potentiellement incomplète : on ne l'inclut pas
        last_nl = text.rfind("\n")
        if last_nl < 0:
            return 200, {"messages": [], "new_offset": offset, "mtime": int(st.st_mtime), "size": st.st_size}
        text = text[:last_nl + 1]
        new_offset = offset + len(text.encode("utf-8"))
    else:
        new_offset = st.st_size

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try: entry = json.loads(line)
        except json.JSONDecodeError: continue
        t = entry.get("type")
        if t not in ("user", "assistant"):
            continue
        msg = entry.get("message") or {}
        content = msg.get("content")
        formatted = ""
        if isinstance(content, str):
            formatted = content
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
            formatted = "\n".join(parts)
        messages.append({
            "role": t,
            "text": formatted[:5000],
            "timestamp": entry.get("timestamp"),
        })

    return 200, {
        "messages": messages,
        "new_offset": new_offset,
        "mtime": int(st.st_mtime),
        "size": st.st_size,
    }


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
    # Le `cd path` implicite de `cmd /k` échoue en silence si le dossier
    # n'existe pas → toast « Reprise » mensonger. On préfère une erreur claire.
    if not Path(path).is_dir():
        return 404, {"ok": False, "error": (
            f"Dossier introuvable : {path} — corrige le chemin "
            f"(Modifier le workspace) ou recrée le dossier"
        )}
    try:
        # cmd /k directement (pas cmd /c start) pour que Popen.pid reste valide
        # tant que la fenêtre cmd est ouverte. Permet d'enregistrer le PID
        # dans active_sessions pour offrir un bouton Stop côté Nebula.
        proc = subprocess.Popen(
            ["cmd", "/k", "claude -c"],
            cwd=path,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            shell=False,
        )
        try:
            from dashcore.active_sessions import register as _register
            _register(ws_id, proc.pid, label=w.get("label") or ws_id)
        except (ImportError, OSError) as e:
            log.warning("active_sessions register failed for %s : %s", ws_id, e)
        return 200, {"ok": True, "pid": proc.pid, "message": f"Reprise session : {ws_id}"}
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
                # relative_to(ws_dir.parent) et non WORKSPACES_DIR : les
                # workspaces adoptés vivent hors de WORKSPACES_DIR, auquel cas
                # relative_to(WORKSPACES_DIR) lèverait ValueError (export cassé,
                # cf. review #9). ws_dir.parent donne toujours une arborescence
                # préfixée par le nom du dossier workspace.
                arc = str(entry.relative_to(ws_dir.parent))
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
    # Overlays optionnels appliques apres le template de base. Liste d'ids
    # validee individuellement -- un overlay inconnu ne casse pas la creation
    # mais est trace dans la reponse pour information.
    overlays_in = payload.get("overlays") or []
    if not isinstance(overlays_in, list):
        return 400, {"error": "overlays doit etre une liste d'ids"}

    if not safe_id(ws_id):
        return 400, {"error": "id invalide (a-z, 0-9, -, _)"}
    if not safe_id(template):
        return 400, {"error": "template invalide"}

    # Refuse explicitement qu'un overlay soit choisi comme template de base.
    # Sinon la dualite template/overlay serait subtilement violee.
    from dashcore.api_overlays import is_overlay_dir, apply_overlay
    tpl_dir = TEMPLATES_DIR / template
    if not tpl_dir.exists():
        return 400, {"error": f"Template introuvable : {template}"}
    if is_overlay_dir(tpl_dir):
        return 400, {"error": f"« {template} » est un overlay, pas un template de base "
                              f"(à passer via le champ `overlays`, pas `template`)"}

    ws_dir = WORKSPACES_DIR / ws_id
    if ws_dir.exists():
        return 409, {"error": f"Workspace déjà existant : {ws_id}"}

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

    # Application des overlays dans l'ordre soumis. Chaque overlay est
    # idempotent (ne reecrit jamais un fichier deja present), donc l'ordre
    # n'affecte que les conflits inter-overlays (premier servi). On collecte
    # un resume par overlay pour le retour API.
    overlays_applied: list[dict] = []
    for ov_id in overlays_in:
        if not isinstance(ov_id, str) or not safe_id(ov_id):
            overlays_applied.append({"id": ov_id, "ok": False, "error": "id invalide"})
            continue
        status, result = apply_overlay(ws_id, ov_id, vars)
        if status == 200:
            overlays_applied.append({
                "id": ov_id, "ok": True,
                "copied": result.get("copied", []),
                "skipped": result.get("skipped", []),
            })
        else:
            overlays_applied.append({"id": ov_id, "ok": False, "error": result.get("error")})

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
    return 201, {
        "ok": True, "id": ws_id, "template": template,
        "files": created, "overlays": overlays_applied,
    }


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


def _backup_workspace_zip(ws_dir: Path, ws_id: str) -> Path:
    """Zippe le dossier workspace dans backups/ avant une purge irréversible.

    Retourne le chemin du zip. Lève OSError si l'écriture échoue -- l'appelant
    doit alors annuler la purge (aucune suppression sans copie récupérable,
    cf. review #5). Backup complet (secrets inclus) : c'est une sauvegarde
    locale gitignored destinée à une restauration fidèle.
    """
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = BACKUPS_DIR / f"deleted-ws-{ws_id}-{stamp}.zip"
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in ws_dir.rglob("*"):
            if entry.is_file():
                zf.write(entry, arcname=str(entry.relative_to(ws_dir.parent)))
    return dst


def delete_workspace(ws_id: str, purge: bool = False) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    # Résoudre le dossier AVANT de retirer l'entrée du registre : pour un
    # workspace adopté/importé, resolve_ws_dir s'appuie sur l'entrée registre
    # (le dossier peut vivre hors de WORKSPACES_DIR). Le résoudre après
    # suppression retomberait sur WORKSPACES_DIR/<id> -> purge sur la mauvaise
    # cible, voire suppression d'un dossier homonyme sans rapport (cf. #4).
    ws_dir = _resolve_ws_dir(ws_id)
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
        if ws_dir.exists():
            # Backup zip avant suppression irréversible (cf. #5) : aucune purge
            # sans copie récupérable. Si le backup échoue, on annule la purge.
            try:
                backup = _backup_workspace_zip(ws_dir, ws_id)
                notes.append(f"backup : {backup.name}")
            except OSError as e:
                log.error("purge %s : backup échoué, suppression annulée : %s", ws_id, e)
                return 500, {"ok": False,
                             "error": f"Backup avant purge échoué, suppression annulée : {e}"}
            _remove_dir_or_link(ws_dir)
            notes.append(f"dossier supprimé : {ws_dir}")
        else:
            notes.append("dossier déjà absent du disque")
    else:
        notes.append("dossier conservé")

    if not registered and not purge:
        return 404, {"error": "Workspace absent du registre"}
    return 200, {"ok": True, "note": " · ".join(notes)}


# Masque affiché à la place d'une valeur de secret (env/header résolu).
_SECRET_MASK = "••••••"


def _mask_secret_values(d) -> dict:
    """Remplace les valeurs d'un dict env/headers par un masque (garde les clés)."""
    if not isinstance(d, dict):
        return {}
    return {str(k): _SECRET_MASK for k in d}


def _mask_mcp_json_text(text: str | None) -> str | None:
    """Masque env/headers/url d'un `.mcp.json` avant de le renvoyer au
    navigateur. Le fichier sur disque porte les secrets résolus (${VAR}
    substitués) nécessaires à Claude Code -- ils ne doivent jamais transiter
    par l'API (cf. review #3, cohérent avec le masquage F3.2 de api_mcps)."""
    if not text:
        return text
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return "[.mcp.json présent mais illisible en JSON — masqué par sécurité]"
    from dashcore.api_mcps import _mask_url
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if isinstance(servers, dict):
        for entry in servers.values():
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("env"), dict):
                entry["env"] = _mask_secret_values(entry["env"])
            if isinstance(entry.get("headers"), dict):
                entry["headers"] = _mask_secret_values(entry["headers"])
            if isinstance(entry.get("url"), str) and entry["url"]:
                entry["url"] = _mask_url(entry["url"])
    return json.dumps(data, ensure_ascii=False, indent=2)


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
        # .mcp.json masqué : le fichier disque porte les secrets résolus (#3).
        ".mcp.json":              _mask_mcp_json_text(read_text(ws_dir / ".mcp.json")),
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
    is_json = target.name.endswith(".json")
    if is_json:
        # Validation JSON avant tout, hors verrou
        try:
            parsed = json.loads(content) if content.strip() else None
        except json.JSONDecodeError as e:
            return 400, {"error": f"JSON invalide : {e}"}
    with _MUTATION_LOCK:
        if target.exists():
            target.with_suffix(target.suffix + ".bak").write_bytes(target.read_bytes())
        if is_json and parsed is not None:
            # Écriture atomique pour les JSON critiques
            write_json(target, parsed)
        else:
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(target)
    log.info("workspace file written: %s / %s", ws_id, filename)
    return 200, {"ok": True, "path": str(target)}


# ────────────────────────────────────────────────────────────────────────────
# Adoption d'un workspace existant -- inspection puis adoption sans toucher
# au contenu du dossier. Distinct de `register_existing_workspace` (utilise
# par le wizard d'onboarding qui auto-suffixe les ids et accepte les chemins
# inexistants pour rejouer un soft-delete). Ici on est plus strict :
#  - garde-fous de securite (refus sous ~/.claude/ ou egal a ROOT) ;
#  - pas d'auto-suffix sur l'id ;
#  - import optionnel des MCPs declares dans le .mcp.json du dossier.
# ────────────────────────────────────────────────────────────────────────────


def _is_path_under_claude_home(path: Path) -> bool:
    """True si `path` est sous ~/.claude/ (resolu) -- refus d'adoption.

    On compare en `resolve()` pour eviter qu'un dossier symlink-e detourne le
    garde-fou. CLAUDE_HOME lui-meme est aussi interdit.
    """
    try:
        rp = path.resolve()
        rh = CLAUDE_HOME.resolve()
    except OSError:
        return False
    try:
        rp.relative_to(rh)
        return True
    except ValueError:
        return rp == rh


def _is_path_root(path: Path) -> bool:
    """True si `path` est ROOT (installation Nebula elle-meme) -- refus."""
    try:
        return path.resolve() == ROOT.resolve()
    except OSError:
        return False


def _parse_mcp_json_entries(mcp_json_path: Path) -> list[dict]:
    """Extrait les entrees MCP d'un .mcp.json (format Claude Code standard).

    Format attendu : {"mcpServers": {"<name>": {transport?, command|url, ...}}}
    Tolere une absence totale ou une structure cassee : renvoie [] sans lever.
    """
    try:
        data = read_json(mcp_json_path, {}) or {}
    except (OSError, json.JSONDecodeError):
        return []
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return []
    # Masquage des valeurs sensibles avant renvoi au navigateur : inspect peut
    # cibler un .mcp.json arbitraire porteur de secrets résolus (cf. #3).
    from dashcore.api_mcps import _mask_url
    out: list[dict] = []
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        transport = (cfg.get("transport") or cfg.get("type")
                     or ("http" if cfg.get("url") else "stdio"))
        url = cfg.get("url") or ""
        out.append({
            "name": str(name),
            "transport": str(transport),
            "command": cfg.get("command") or "",
            "url": _mask_url(url) if url else "",
            "args": cfg.get("args") or [],
            "env": _mask_secret_values(cfg.get("env")),
            "headers": _mask_secret_values(cfg.get("headers")),
        })
    return out


def _count_subdirs_with_marker(dir_path: Path, marker_name: str) -> int:
    """Compte les sous-dossiers de `dir_path` qui contiennent `marker_name`.

    Utilise pour les skills : `.claude/skills/<nom>/SKILL.md`. Renvoie 0 si le
    dossier parent n'existe pas (lecture silencieuse, ne leve jamais).
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    n = 0
    try:
        for sub in dir_path.iterdir():
            if sub.is_dir() and (sub / marker_name).exists():
                n += 1
    except OSError:
        return 0
    return n


def _count_files_with_ext(dir_path: Path, ext: str) -> int:
    """Compte les fichiers `*.ext` directement dans `dir_path` (non-recursif).

    Utilise pour agents et commands : `.claude/agents/*.md`,
    `.claude/commands/*.md`. Renvoie 0 si le dossier n'existe pas.
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    try:
        return sum(1 for f in dir_path.glob(f"*{ext}") if f.is_file())
    except OSError:
        return 0


def inspect_workspace_path(payload: dict) -> tuple[int, dict]:
    """Inspecte un dossier candidat a l'adoption (read-only).

    Detecte signaux Claude (CLAUDE.md, .mcp.json, skills/agents/commands,
    hooks dans settings.json) et applique les garde-fous (chemin sous
    ~/.claude/, egal a ROOT, doublon dans workspaces.json). Aucun effet
    de bord sur le filesystem.
    """
    raw_path = (payload.get("path") or "").strip()
    ok, err = validate_ws_path(raw_path)
    if not ok:
        return 400, {"error": err}

    p = Path(raw_path)
    warnings: list[str] = []

    # Garde-fous critiques (bloquants) : on n'inspecte meme pas.
    if _is_path_under_claude_home(p):
        return 403, {"error": "Chemin interdit : sous ~/.claude/ (config Claude Code)"}
    if _is_path_root(p):
        return 403, {"error": "Chemin interdit : ROOT de Nebula (installation elle-meme)"}

    exists = p.exists()
    is_dir = exists and p.is_dir()

    if not exists:
        return 200, {
            "path": str(p),
            "exists": False, "is_dir": False,
            "has_claude_md": False, "has_mcp_json": False, "has_claude_dir": False,
            "skills_count": 0, "agents_count": 0, "commands_count": 0,
            "hooks_settings": None, "mcps": [], "claude_md_size": 0,
            "warnings": ["le dossier n'existe pas sur disque"],
            "already_adopted": False,
        }
    if not is_dir:
        return 400, {"error": "Le chemin existe mais n'est pas un dossier"}

    # Doublon dans le registre (chemin deja adopte).
    path_norm = str(Path(raw_path)).rstrip("\\/").lower()
    already_adopted = False
    try:
        data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
        for w in data.get("workspaces", []):
            if (w.get("path") or "").rstrip("\\/").lower() == path_norm:
                already_adopted = True
                warnings.append(f"déjà adopté sous l'id « {w.get('id')} »")
                break
    except (OSError, json.JSONDecodeError):
        pass

    # Detection des signaux Claude.
    claude_md = p / "CLAUDE.md"
    mcp_json = p / ".mcp.json"
    claude_dir = p / ".claude"
    settings_json = claude_dir / "settings.json"

    has_claude_md = claude_md.is_file()
    has_mcp_json = mcp_json.is_file()
    has_claude_dir = claude_dir.is_dir()

    claude_md_size = 0
    if has_claude_md:
        try:
            claude_md_size = claude_md.stat().st_size
        except OSError:
            claude_md_size = 0

    skills_count = _count_subdirs_with_marker(claude_dir / "skills", "SKILL.md")
    agents_count = _count_files_with_ext(claude_dir / "agents", ".md")
    commands_count = _count_files_with_ext(claude_dir / "commands", ".md")

    # Section hooks du settings.json (uniquement, pas le reste -- on respecte
    # le perimetre minimal demande).
    hooks_settings = None
    if settings_json.is_file():
        try:
            raw = settings_json.read_text(encoding="utf-8")
            parsed = json.loads(raw) if raw.strip() else {}
            if isinstance(parsed, dict) and isinstance(parsed.get("hooks"), dict):
                hooks_settings = parsed["hooks"]
        except (OSError, json.JSONDecodeError):
            hooks_settings = None

    mcps = _parse_mcp_json_entries(mcp_json) if has_mcp_json else []

    has_any_signal = (
        has_claude_md or has_mcp_json or has_claude_dir
        or skills_count or agents_count or commands_count
    )
    if not has_any_signal:
        warnings.append("aucun signal Claude détecté dans ce dossier")

    return 200, {
        "path": str(p),
        "exists": True,
        "is_dir": True,
        "has_claude_md": has_claude_md,
        "has_mcp_json": has_mcp_json,
        "has_claude_dir": has_claude_dir,
        "skills_count": skills_count,
        "agents_count": agents_count,
        "commands_count": commands_count,
        "hooks_settings": hooks_settings,
        "mcps": mcps,
        "claude_md_size": claude_md_size,
        "warnings": warnings,
        "already_adopted": already_adopted,
    }


def adopt_workspace(payload: dict) -> tuple[int, dict]:
    """Adopte un dossier existant comme workspace Nebula.

    Distinct de `register_existing_workspace` : pas d'auto-suffix sur l'id
    (erreur 409 explicite si conflit), garde-fous de securite renforces,
    import optionnel des MCPs declares dans le .mcp.json (strategie merge
    non destructif : un MCP existant dans le registre n'est jamais ecrase).
    Ne touche AUCUN fichier du dossier adopte (pas de creation, pas de copie).
    """
    raw_path = (payload.get("path") or "").strip()
    ws_id = (payload.get("id") or "").strip()
    label = sanitize_bat((payload.get("label") or ws_id).strip()) or ws_id
    emoji = (payload.get("emoji") or "📁").strip()
    description = (payload.get("description") or "").strip()
    import_mcps = bool(payload.get("import_mcps"))

    if not safe_id(ws_id):
        return 400, {"error": "id invalide (a-z, 0-9, _, -, max 40)"}

    ok, err = validate_ws_path(raw_path)
    if not ok:
        return 400, {"error": err}

    p = Path(raw_path)

    # Re-verification des garde-fous (l'inspection peut avoir ete sautee).
    if _is_path_under_claude_home(p):
        return 403, {"error": "Chemin interdit : sous ~/.claude/ (config Claude Code)"}
    if _is_path_root(p):
        return 403, {"error": "Chemin interdit : ROOT de Nebula (installation elle-meme)"}
    if not p.exists():
        return 404, {"error": f"Dossier introuvable : {raw_path}"}
    if not p.is_dir():
        return 400, {"error": "Le chemin existe mais n'est pas un dossier"}

    path_norm = str(Path(raw_path)).rstrip("\\/")

    # Detection des signaux pour la reponse (avant ecriture du registre, pour
    # ne pas re-lire le disque deux fois).
    claude_dir = p / ".claude"
    skills_n = _count_subdirs_with_marker(claude_dir / "skills", "SKILL.md")
    agents_n = _count_files_with_ext(claude_dir / "agents", ".md")
    commands_n = _count_files_with_ext(claude_dir / "commands", ".md")
    settings_json = claude_dir / "settings.json"
    hooks_present = False
    if settings_json.is_file():
        try:
            parsed = json.loads(settings_json.read_text(encoding="utf-8") or "{}")
            hooks_present = isinstance(parsed, dict) and bool(parsed.get("hooks"))
        except (OSError, json.JSONDecodeError):
            hooks_present = False
    mcp_entries = _parse_mcp_json_entries(p / ".mcp.json")

    warnings: list[str] = []

    # Verrou + ecriture du registre. Garde-fous doublons sous lock pour eviter
    # une course entre 2 adoptions simultanees.
    with _MUTATION_LOCK:
        data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
        ws_list = data.setdefault("workspaces", [])

        if any(w.get("id") == ws_id for w in ws_list):
            return 409, {"error": f"Id déjà pris : « {ws_id} »"}
        if any((w.get("path") or "").rstrip("\\/").lower() == path_norm.lower()
               for w in ws_list):
            return 409, {"error": f"Chemin déjà adopté : {path_norm}"}

        ws_list.append({
            "id": ws_id,
            "label": label,
            "emoji": emoji,
            "description": description,
            "path": path_norm,
            "template": "adopted",
        })
        write_json(WORKSPACES_JSON, data)

    # Bat de lancement, best-effort (un echec ici n'invalide pas l'adoption).
    try:
        write_launch_bat(ws_id, label, path_norm)
    except Exception as e:
        log.warning("write_launch_bat failed for adopted %s : %s", ws_id, e)
        warnings.append("script de lancement non genere (.bat)")

    # Import optionnel des MCPs : strategie merge non destructif.
    mcps_added: list[str] = []
    mcps_skipped: list[dict] = []
    if import_mcps and mcp_entries:
        # Lecture du registre actuel (hors lock : add_or_update_mcp prend son
        # propre verrou, et on accepte que la liste evolue entre les iterations
        # -- la verification finale dans add_or_update_mcp est la source de
        # verite. On filtre ici juste pour eviter d'appeler add_or_update pour
        # rien sur les ids deja connus, et tracer le skip cote UI).
        from dashcore.api_mcps import add_or_update_mcp
        try:
            registry = read_json(MCP_REGISTRY, {"version": "1.0", "mcps": []})
            existing_ids = {m.get("id") for m in registry.get("mcps", [])}
        except (OSError, json.JSONDecodeError):
            existing_ids = set()

        for entry in mcp_entries:
            name = entry["name"]
            if not safe_id(name):
                mcps_skipped.append({"id": name, "reason": "id invalide"})
                continue
            if name in existing_ids:
                mcps_skipped.append({"id": name, "reason": "déjà présent dans le registre"})
                continue
            mcp_payload = {
                "id": name,
                "name": name,
                "transport": entry["transport"] if entry["transport"] in ALLOWED_TRANSPORTS else "stdio",
                "command": entry["command"],
                "args": entry["args"],
                "env": entry["env"],
                "url": entry["url"],
                "headers": entry["headers"],
                "status": "disponible",
            }
            status, result = add_or_update_mcp(mcp_payload)
            if status < 400:
                mcps_added.append(name)
                existing_ids.add(name)
            else:
                mcps_skipped.append({"id": name, "reason": result.get("error", "echec")})

    log.info(
        "workspace adopted: %s -> %s (skills=%d agents=%d commands=%d hooks=%s mcps_in_file=%d)",
        ws_id, path_norm, skills_n, agents_n, commands_n, hooks_present, len(mcp_entries),
    )
    return 201, {
        "ok": True,
        "id": ws_id,
        "path": path_norm,
        "detected": {
            "skills": skills_n,
            "agents": agents_n,
            "commands": commands_n,
            "hooks": hooks_present,
            "mcps_in_file": len(mcp_entries),
        },
        "imported": {
            "mcps_added": mcps_added,
            "mcps_skipped": mcps_skipped,
        },
        "warnings": warnings,
    }


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
