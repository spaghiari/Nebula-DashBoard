"""Explorateur de fichiers d'un workspace.

Endpoints exposés (câblés dans server.py) :
    GET  /api/workspaces/<id>/tree?path=<rel>&depth=<1-5>
    GET  /api/workspaces/<id>/file?path=<rel>
    POST /api/workspaces/<id>/file        body={path, content}
    GET  /api/workspaces/<id>/search?q=<term>&max=<int>

Sécurité :
    _safe_resolve refuse `..`, chemins absolus, drive letters, et tout
    chemin dont le resolve() sort du workspace (couvre symlinks).

Stdlib uniquement.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from dashcore.config import _MUTATION_LOCK
from dashcore.helpers import safe_id
from dashcore.workspace_io import resolve_ws_dir

log = logging.getLogger("dashboard")

# Dossiers visibles dans l'arbre mais marqués `excluded` → non explorables
_EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox", ".idea", ".vscode-test",
}

# Extensions clairement binaires → on ne lit jamais le contenu
_BINARY_EXT = {
    ".exe", ".dll", ".so", ".dylib", ".pyd", ".pyc",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp", ".svg",
    ".pdf", ".zip", ".7z", ".gz", ".tar", ".rar", ".bz2", ".xz",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".wav", ".ogg", ".flac", ".webm", ".mov", ".avi",
    ".db", ".sqlite", ".sqlite3", ".bin", ".dat", ".pack",
    ".class", ".jar", ".war",
}

_MAX_READ_BYTES = 5 * 1024 * 1024          # 5 MB cap pour lecture/édition
_MAX_SEARCH_FILE_BYTES = 2 * 1024 * 1024   # 2 MB cap par fichier scanné
_MAX_SEARCH_FILES = 500                    # nombre max de fichiers scannés
_MAX_SEARCH_HITS = 200                     # nombre max de résultats renvoyés


# ---------------------------------------------------------------------------
# Sécurité path
# ---------------------------------------------------------------------------

def _safe_resolve(ws_root: Path, rel: str) -> Path | None:
    """Résout `rel` sous `ws_root`. Retourne None si inacceptable.

    Refuse : path absolu, drive letter, segments `..`, et tout résultat
    dont le resolve() sort de ws_root (couvre symlinks crafted).
    Le path vide ou "." renvoie ws_root lui-même.
    """
    rel = (rel or "").strip().replace("\\", "/")
    if not rel or rel == ".":
        return ws_root.resolve()
    # Refuse drive letter (C:, D:...) et chemins absolus POSIX
    if rel.startswith("/") or (len(rel) >= 2 and rel[1] == ":"):
        return None
    # Refuse tout segment `..` (même au milieu)
    parts = [p for p in rel.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        return None
    try:
        target = (ws_root / Path(*parts)).resolve()
        root_resolved = ws_root.resolve()
        # Python 3.9+ : is_relative_to
        target.relative_to(root_resolved)
    except (ValueError, OSError):
        return None
    return target


# ---------------------------------------------------------------------------
# Détection binaire
# ---------------------------------------------------------------------------

def _is_binary(path: Path, sample_size: int = 8192) -> bool:
    """True si le fichier semble binaire (extension OU NULL byte dans l'en-tête)."""
    if path.suffix.lower() in _BINARY_EXT:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(sample_size)
        return b"\x00" in chunk
    except OSError:
        return True


def _read_text(path: Path, max_bytes: int = _MAX_READ_BYTES) -> tuple[str, str]:
    """Lit un fichier texte. Retourne (content, encoding_used)."""
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    # BOM UTF-8
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", "replace"), "utf-8-sig"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace"), "cp1252"


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------

def _entry_dict(entry: Path, *, with_children_count: bool = False) -> dict[str, Any]:
    is_dir = entry.is_dir()
    excluded = is_dir and entry.name in _EXCLUDED_DIRS
    out: dict[str, Any] = {
        "name": entry.name,
        "type": "dir" if is_dir else "file",
        "excluded": excluded,
    }
    try:
        st = entry.stat()
        out["mtime"] = int(st.st_mtime)
        out["size"] = st.st_size if not is_dir else None
    except OSError:
        out["mtime"] = None
        out["size"] = None
    if not is_dir:
        out["binary"] = _is_binary(entry) if (out.get("size") or 0) < 64 * 1024 else (
            entry.suffix.lower() in _BINARY_EXT
        )
    elif with_children_count and not excluded:
        try:
            out["children_count"] = sum(1 for _ in entry.iterdir())
        except OSError:
            out["children_count"] = None
    return out


def _list_entries(target: Path, *, with_children_count: bool = True) -> list[dict[str, Any]]:
    """Liste triée d'un dossier : dirs alpha, puis fichiers alpha."""
    try:
        children = list(target.iterdir())
    except OSError as e:
        raise FileNotFoundError(str(e)) from e
    children.sort(key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))
    return [_entry_dict(c, with_children_count=with_children_count) for c in children]


def list_tree(ws_id: str, rel_path: str = "", depth: int = 1) -> tuple[int, dict]:
    """Liste l'arbre du workspace à partir de rel_path. Lazy par défaut (depth=1)."""
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_root = resolve_ws_dir(ws_id)
    if not ws_root.exists():
        return 404, {"error": "workspace absent sur disque"}
    target = _safe_resolve(ws_root, rel_path)
    if target is None:
        return 400, {"error": "chemin invalide"}
    if not target.exists() or not target.is_dir():
        return 404, {"error": "dossier introuvable"}
    try:
        depth = max(1, min(int(depth), 5))
    except (TypeError, ValueError):
        depth = 1

    def walk(node: Path, remaining: int) -> list[dict[str, Any]]:
        out = _list_entries(node, with_children_count=True)
        if remaining > 1:
            for entry, src in zip(out, sorted(node.iterdir(), key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))):
                if entry["type"] == "dir" and not entry["excluded"]:
                    try:
                        entry["children"] = walk(src, remaining - 1)
                    except FileNotFoundError:
                        entry["children"] = []
        return out

    try:
        entries = walk(target, depth)
    except FileNotFoundError as e:
        return 500, {"error": f"lecture impossible : {e}"}
    rel_norm = str(target.relative_to(ws_root.resolve())).replace("\\", "/")
    if rel_norm == ".":
        rel_norm = ""
    return 200, {"path": rel_norm, "entries": entries}


# ---------------------------------------------------------------------------
# Read / Write
# ---------------------------------------------------------------------------

def read_file(ws_id: str, rel_path: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_root = resolve_ws_dir(ws_id)
    if not ws_root.exists():
        return 404, {"error": "workspace absent sur disque"}
    target = _safe_resolve(ws_root, rel_path)
    if target is None:
        return 400, {"error": "chemin invalide"}
    if not target.exists():
        return 404, {"error": "fichier introuvable"}
    if not target.is_file():
        return 400, {"error": "pas un fichier"}
    try:
        st = target.stat()
    except OSError as e:
        return 500, {"error": f"stat échoué : {e}"}
    base = {
        "path": rel_path.replace("\\", "/"),
        "size": st.st_size,
        "mtime": int(st.st_mtime),
    }
    if st.st_size > _MAX_READ_BYTES:
        return 200, {**base, "binary": True, "reason": "trop volumineux", "content": None}
    if _is_binary(target):
        return 200, {**base, "binary": True, "reason": "binaire", "content": None}
    try:
        content, encoding = _read_text(target)
    except OSError as e:
        return 500, {"error": f"lecture échouée : {e}"}
    return 200, {**base, "binary": False, "encoding": encoding, "content": content}


def write_file(ws_id: str, rel_path: str, content: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_root = resolve_ws_dir(ws_id)
    if not ws_root.exists():
        return 404, {"error": "workspace absent sur disque"}
    target = _safe_resolve(ws_root, rel_path)
    if target is None:
        return 400, {"error": "chemin invalide"}
    if target == ws_root.resolve():
        return 400, {"error": "ne peut pas écrire à la racine du workspace"}
    if target.exists() and target.is_dir():
        return 400, {"error": "cible est un dossier"}
    # Refus écriture si binaire détecté sur l'existant (protection contre corruption)
    if target.exists() and _is_binary(target):
        return 403, {"error": "fichier binaire non éditable"}
    # Validation JSON si extension .json
    if target.suffix.lower() == ".json" and content.strip():
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return 400, {"error": f"JSON invalide : {e}"}
    with _MUTATION_LOCK:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            try:
                target.with_suffix(target.suffix + ".bak").write_bytes(target.read_bytes())
            except OSError:
                pass  # backup best-effort
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8", newline="")
        tmp.replace(target)
    log.info("workspace file written: %s / %s (%d bytes)", ws_id, rel_path, len(content))
    try:
        st = target.stat()
        return 200, {"ok": True, "path": rel_path.replace("\\", "/"), "size": st.st_size, "mtime": int(st.st_mtime)}
    except OSError:
        return 200, {"ok": True, "path": rel_path.replace("\\", "/")}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_file(ws_id: str, rel_path: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    if not (rel_path or "").strip():
        return 400, {"error": "chemin requis"}
    ws_root = resolve_ws_dir(ws_id)
    if not ws_root.exists():
        return 404, {"error": "workspace absent sur disque"}
    target = _safe_resolve(ws_root, rel_path)
    if target is None:
        return 400, {"error": "chemin invalide"}
    if target == ws_root.resolve():
        return 400, {"error": "ne peut pas supprimer la racine"}
    if not target.exists():
        return 404, {"error": "fichier introuvable"}
    if target.is_dir():
        # Refuse de supprimer un dossier non-vide ; vide → rmdir OK
        try:
            next(target.iterdir())
            return 400, {"error": "dossier non vide (suppression de dossier non supportée)"}
        except StopIteration:
            pass
        with _MUTATION_LOCK:
            target.rmdir()
        log.info("workspace dir deleted: %s / %s", ws_id, rel_path)
        return 200, {"ok": True, "path": rel_path.replace("\\", "/"), "type": "dir"}
    # Fichier : suppression directe (pas de .bak — c'est une action explicite)
    with _MUTATION_LOCK:
        target.unlink()
    log.info("workspace file deleted: %s / %s", ws_id, rel_path)
    return 200, {"ok": True, "path": rel_path.replace("\\", "/"), "type": "file"}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_workspace(ws_id: str, query: str, max_hits: int = _MAX_SEARCH_HITS) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    q = (query or "").strip()
    if len(q) < 2:
        return 400, {"error": "requête trop courte (min 2 caractères)"}
    ws_root = resolve_ws_dir(ws_id)
    if not ws_root.exists():
        return 404, {"error": "workspace absent sur disque"}
    try:
        max_hits = max(1, min(int(max_hits), _MAX_SEARCH_HITS))
    except (TypeError, ValueError):
        max_hits = _MAX_SEARCH_HITS

    q_lower = q.lower()
    hits: list[dict[str, Any]] = []
    files_scanned = 0
    truncated = False

    def walk(d: Path) -> bool:
        """True pour continuer, False pour stopper (cap atteint)."""
        nonlocal files_scanned, truncated
        try:
            children = sorted(d.iterdir(), key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))
        except OSError:
            return True
        for entry in children:
            if len(hits) >= max_hits or files_scanned >= _MAX_SEARCH_FILES:
                truncated = True
                return False
            if entry.is_dir():
                if entry.name in _EXCLUDED_DIRS:
                    continue
                if not walk(entry):
                    return False
                continue
            if entry.suffix.lower() in _BINARY_EXT:
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            if size > _MAX_SEARCH_FILE_BYTES:
                continue
            files_scanned += 1
            try:
                with entry.open("r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, start=1):
                        if q_lower in line.lower():
                            rel = str(entry.relative_to(ws_root)).replace("\\", "/")
                            snippet = line.rstrip("\n")
                            if len(snippet) > 240:
                                idx = snippet.lower().find(q_lower)
                                start = max(0, idx - 60)
                                snippet = ("…" if start > 0 else "") + snippet[start:start + 240] + "…"
                            hits.append({"path": rel, "line": lineno, "snippet": snippet})
                            if len(hits) >= max_hits:
                                truncated = True
                                return False
            except OSError:
                continue
        return True

    walk(ws_root)
    return 200, {
        "query": q,
        "hits": hits,
        "files_scanned": files_scanned,
        "truncated": truncated,
    }
