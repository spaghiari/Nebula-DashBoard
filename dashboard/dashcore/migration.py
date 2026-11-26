"""Migration d'environnement : inventaire, estimation et export chiffré.

Une archive `.nebmig` (cf. `migration_crypto.py` pour le chiffrement) contient,
dans un flux tar compressé puis chiffré :

    manifest.json                    description (sans secret) : source, unités, totaux
    meta/workspaces.json             entrées du registre des workspaces exportés
    meta/mcp_registry.json           registre MCP
    meta/env.json                    variables d'environnement (SECRETS, d'où le chiffrement)
    meta/claude_json.json            extrait (liste blanche) de ~/.claude.json
    meta/plugins.json                plugins installés (information seule)
    nebula/... claude/... ws/<id>/...  fichiers, du plus petit au plus gros

Chaque UNITÉ du manifeste (un workspace, un skill, un dossier de sessions, un
fichier de configuration...) est la granularité des décisions à l'import. Les
dossiers régénérables (`node_modules`, `.venv`...), les liens symboliques et
les jonctions ne sont jamais exportés. Tout se fait en flux : rien n'est
chargé en entier en mémoire.

Le module `migration_import.py` fait le chemin inverse (aperçu puis import).
"""
from __future__ import annotations

import datetime as dt
import gzip
import io
import json
import os
import shutil
import socket
import sys
import tarfile
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from dashcore.config import (
    CLAUDE_HOME, CLAUDE_JSON, DATA_DIR, IS_WINDOWS, JOURNAL_FILE,
    MCP_REGISTRY, MIGRATION_CLAUDE_DIRS, MIGRATION_CLAUDE_FILES,
    MIGRATION_CLAUDE_JSON_PROJECT_KEYS, MIGRATION_DATA_FILES,
    MIGRATION_EXCLUDED_DIRS, MIGRATION_EXCLUDED_SUFFIXES, MIGRATION_EXT,
    MIGRATION_FORMAT_VERSION, MIGRATION_MIN_PASSPHRASE, ROOT, SKILLS_LIBRARY_DIR,
    TEMPLATES_DIR, USER_HOME, WORKSPACES_DIR, WORKSPACES_JSON, log,
)
from dashcore.helpers import read_json, read_json_strict, safe_id
from dashcore.env_local import is_encrypted_mode, load_env_local_strict
from dashcore.migration_crypto import (
    EncryptingWriter, MigrationCancelled, MigrationError, MigrationFormatError,
    OpenedArchive, open_archive,
)
from dashcore.migration_gzip import ParallelGzipWriter
from dashcore.migration_paths import valid_component

# progress(phase, done, total, label) ; cancel() -> bool
ProgressFn = Callable[[str, int, int, str], None]
CancelFn = Callable[[], bool]

MANIFEST_NAME = "manifest.json"
FORMAT_NAME = "nebula-migration"
MAX_META_BYTES = 64 << 20
_COPY_BLOCK = 1 << 20

# Groupes d'unités affichés par l'interface (ordre d'affichage).
GROUP_LABELS = {
    "workspaces": "Workspaces",
    "sessions": "Historique des sessions Claude Code",
    "claude_global": "Configuration Claude globale",
    "nebula_config": "Configuration Nebula",
    "mcp_servers": "Serveurs MCP locaux (code)",
}
_ENV_LIKE_DIRS = ("node_modules", ".venv", "venv")


# ---------------------------------------------------------------------------
# Parcours d'arborescence
# ---------------------------------------------------------------------------

class Walker:
    """Collecte ce qui est écarté pendant un parcours (liens, noms, exclus)."""

    def __init__(self):
        self.links = 0
        self.bad_names = 0
        self.unreadable = 0
        self.samples: dict[str, list[str]] = {"links": [], "bad_names": []}
        self.excluded: list[dict] = []

    def _sample(self, kind: str, rel: str) -> None:
        if len(self.samples[kind]) < 10:
            self.samples[kind].append(rel)

    def warnings(self) -> list[str]:
        out = []
        if self.links:
            out.append(f"{self.links} lien(s) symbolique(s) ou jonction(s) non exporté(s) "
                       f"(ex. {', '.join(self.samples['links'][:3])}).")
        if self.bad_names:
            out.append(f"{self.bad_names} fichier(s) au nom incompatible avec l'archive ignoré(s) "
                       f"(ex. {', '.join(self.samples['bad_names'][:3])}).")
        if self.unreadable:
            out.append(f"{self.unreadable} dossier(s) illisible(s) ignoré(s).")
        return out


def _is_link(entry: os.DirEntry) -> bool:
    """Lien symbolique ou jonction (jamais suivis : pas d'export, pas de boucle)."""
    try:
        if entry.is_symlink():
            return True
        is_junction = getattr(entry, "is_junction", None)
        if is_junction is not None:
            return bool(is_junction())
        if IS_WINDOWS and entry.is_dir(follow_symlinks=False):
            st = entry.stat(follow_symlinks=False)
            return bool(getattr(st, "st_file_attributes", 0) & 0x400)
    except OSError:
        return False
    return False


def _walk_dir(root: str, arc: str, walker: Walker) -> Iterator[tuple[str, str, bool, int]]:
    """Génère (chemin, nom d'archive, est_dossier, taille), parents avant enfants."""
    yield (root, arc, True, 0)
    stack = [(root, arc)]
    while stack:
        d, a = stack.pop()
        try:
            with os.scandir(d) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            walker.unreadable += 1
            continue
        subdirs = []
        for e in entries:
            name = e.name
            rel = f"{a}/{name}"
            if _is_link(e):
                walker.links += 1
                walker._sample("links", rel)
                continue
            try:
                is_dir = e.is_dir(follow_symlinks=False)
                is_file = (not is_dir) and e.is_file(follow_symlinks=False)
            except OSError:
                walker.unreadable += 1
                continue
            if is_dir:
                if name in MIGRATION_EXCLUDED_DIRS:
                    walker.excluded.append({"path": rel, "name": name})
                    continue
                if not valid_component(name):
                    walker.bad_names += 1
                    walker._sample("bad_names", rel)
                    continue
                yield (e.path, rel, True, 0)
                subdirs.append((e.path, rel))
            elif is_file:
                if name.endswith(MIGRATION_EXCLUDED_SUFFIXES):
                    continue
                if not valid_component(name):
                    walker.bad_names += 1
                    walker._sample("bad_names", rel)
                    continue
                try:
                    size = e.stat(follow_symlinks=False).st_size
                except OSError:
                    walker.unreadable += 1
                    continue
                yield (e.path, rel, False, size)
        stack.extend(reversed(subdirs))


# ---------------------------------------------------------------------------
# Unités
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    key: str            # clé stable = préfixe d'archive (« ws/<id> », « claude/skills/<n> »)
    kind: str           # workspace | item | merge
    group: str
    label: str
    src: Path
    is_dir: bool
    files: int = 0
    dirs: int = 0
    bytes: int = 0
    extra: dict = field(default_factory=dict)

    def manifest_entry(self) -> dict:
        return {"key": self.key, "kind": self.kind, "group": self.group, "label": self.label,
                "is_dir": self.is_dir, "files": self.files, "bytes": self.bytes}


def walk_unit(unit: Unit, walker: Walker) -> Iterator[tuple[str, str, bool, int]]:
    if not unit.is_dir:
        try:
            yield (str(unit.src), unit.key, False, unit.src.stat().st_size)
        except OSError:
            walker.unreadable += 1
        return
    yield from _walk_dir(str(unit.src), unit.key, walker)


def count_unit(unit: Unit, walker: Walker, cancel: CancelFn | None = None) -> None:
    files = dirs = size = 0
    for _p, _a, is_dir, sz in walk_unit(unit, walker):
        if cancel and cancel():
            raise MigrationCancelled()
        if is_dir:
            dirs += 1
        else:
            files += 1
            size += sz
    unit.files, unit.dirs, unit.bytes = files, dirs, size


def _is_plain(p: Path) -> bool:
    """Fichier ou dossier ordinaire (ni lien, ni jonction)."""
    try:
        if p.is_symlink():
            return False
        is_junction = getattr(p, "is_junction", None)
        if is_junction is not None and is_junction():
            return False
        return True
    except OSError:
        return False


def _children(d: Path, dirs_only: bool = False) -> list[Path]:
    try:
        kids = sorted(d.iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    out = []
    for p in kids:
        if not valid_component(p.name) or not _is_plain(p):
            continue
        if dirs_only and not p.is_dir():
            continue
        out.append(p)
    return out


def source_info() -> dict:
    try:
        host = socket.gethostname()
    except OSError:
        host = ""
    return {
        "os": sys.platform, "sep": os.sep, "host": host,
        "root": str(ROOT), "user_home": str(USER_HOME),
        "claude_home": str(CLAUDE_HOME), "data_dir": str(DATA_DIR),
        "workspaces_dir": str(WORKSPACES_DIR),
    }


def list_source_workspaces() -> list[dict]:
    """Workspaces du registre avec leur dossier réel (point d'accès unique :
    `_ws_dir_from_entry`, qui gère les workspaces adoptés hors WORKSPACES_DIR)."""
    from dashcore.workspace_io import _ws_dir_from_entry
    data = read_json_strict(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    out = []
    for w in data.get("workspaces", []):
        ws_id = w.get("id") if isinstance(w, dict) else None
        if not isinstance(ws_id, str) or not safe_id(ws_id):
            continue
        path = _ws_dir_from_entry(w)
        try:
            exists = path.is_dir()
            inside = path.resolve().parent == WORKSPACES_DIR.resolve()
        except OSError:
            exists, inside = False, False
        out.append({"id": ws_id, "label": str(w.get("label") or ws_id),
                    "emoji": str(w.get("emoji") or ""), "path": str(path),
                    "exists": exists, "in_workspaces_dir": inside, "entry": w})
    return out


def collect_units(selected_ws: set[str] | None) -> tuple[list[Unit], list[dict], list[str]]:
    """Unités à exporter (petites d'abord), workspaces du registre, avertissements.

    `selected_ws` : ids exportés (None = tous ceux dont le dossier existe)."""
    warnings: list[str] = []
    units: list[Unit] = []

    def add(key, kind, group, label, src: Path, is_dir: bool, **extra):
        units.append(Unit(key, kind, group, label, src, is_dir, extra=extra))

    # Données Nebula
    for name in MIGRATION_DATA_FILES:
        p = DATA_DIR / name
        if p.is_file() and _is_plain(p):
            add(f"nebula/data/{name}", "item", "nebula_config", f"data/{name}", p, False)
    for p in _children(SKILLS_LIBRARY_DIR, dirs_only=True):
        add(f"nebula/skills-library/{p.name}", "item", "nebula_config",
            f"Bibliothèque de skills : {p.name}", p, True)
    for p in _children(JOURNAL_FILE.parent):
        add(f"nebula/memory/{p.name}", "item", "nebula_config", f"memory/{p.name}", p, p.is_dir())
    for p in _children(TEMPLATES_DIR):
        add(f"nebula/templates/{p.name}", "item", "nebula_config", f"Template : {p.name}",
            p, p.is_dir())
    mcp_dir = MCP_REGISTRY.parent
    for p in _children(mcp_dir / "configs"):
        add(f"nebula/mcp-configs/{p.name}", "item", "nebula_config",
            f"Config MCP : {p.name}", p, p.is_dir())
    # ~/.claude : fichiers, puis dossiers listés élément par élément
    for name in MIGRATION_CLAUDE_FILES:
        p = CLAUDE_HOME / name
        if p.is_file() and _is_plain(p):
            add(f"claude/{name}", "item", "claude_global", f"~/.claude/{name}", p, False)
    for sub in MIGRATION_CLAUDE_DIRS:
        for p in _children(CLAUDE_HOME / sub):
            add(f"claude/{sub}/{p.name}", "item", "claude_global",
                f"{sub} global : {p.name}", p, p.is_dir())
    # Code des serveurs MCP locaux (hors configs : exportées ci-dessus)
    for p in _children(mcp_dir, dirs_only=True):
        if p.name == "configs":
            continue
        add(f"nebula/mcp-servers/{p.name}", "item", "mcp_servers",
            f"Serveur MCP : {p.name}", p, True)

    # Workspaces
    ws_info = list_source_workspaces()
    for w in ws_info:
        w["selected"] = bool(w["exists"]) and (selected_ws is None or w["id"] in selected_ws)
        if selected_ws is not None and w["id"] in selected_ws and not w["exists"]:
            warnings.append(f"Workspace « {w['id']} » : dossier introuvable ({w['path']}), non exporté.")
        if w["selected"]:
            add(f"ws/{w['id']}", "workspace", "workspaces", w["label"], Path(w["path"]), True,
                ws_id=w["id"])

    # Sessions (fusionnées fichier par fichier à l'import, jamais écrasées)
    for sub in ("projects", "file-history"):
        base = CLAUDE_HOME / sub
        for p in _children(base, dirs_only=True):
            add(f"claude/{sub}/{p.name}", "merge", "sessions",
                f"{'Sessions' if sub == 'projects' else 'Restauration'} : {p.name}", p, True)
    return units, ws_info, warnings


# ---------------------------------------------------------------------------
# Métadonnées (petits JSON placés en tête d'archive)
# ---------------------------------------------------------------------------

def claude_json_extract() -> dict:
    """Extrait de ~/.claude.json : MCPs racine + entrées de projet en liste
    blanche (jamais compte, jeton, historique de prompts)."""
    data = read_json(CLAUDE_JSON, {})
    if not isinstance(data, dict):
        return {"mcpServers": {}, "projects": {}}
    projects: dict[str, dict] = {}
    for key, proj in (data.get("projects") or {}).items():
        if not isinstance(key, str) or not isinstance(proj, dict):
            continue
        keep = {k: proj[k] for k in MIGRATION_CLAUDE_JSON_PROJECT_KEYS
                if k in proj and proj[k] not in (None, {}, [], "")}
        if keep:
            projects[key] = keep
    root_mcp = data.get("mcpServers")
    return {"mcpServers": root_mcp if isinstance(root_mcp, dict) else {}, "projects": projects}


def installed_plugin_names() -> list[str]:
    data = read_json(CLAUDE_HOME / "plugins" / "installed_plugins.json", {})
    plugins = data.get("plugins") if isinstance(data, dict) else None
    return sorted(str(k) for k in plugins) if isinstance(plugins, dict) else []


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------

def _count_all(units: list[Unit], walker: Walker, progress: ProgressFn | None,
               cancel: CancelFn | None, phase: str = "inventory") -> None:
    total = len(units)
    for i, u in enumerate(units):
        if cancel and cancel():
            raise MigrationCancelled()
        if progress:
            progress(phase, i, total, u.label)
        count_unit(u, walker, cancel)
    if progress:
        progress(phase, total, total, "")


def estimate(selected_ws: set[str] | None, progress: ProgressFn | None = None,
             cancel: CancelFn | None = None) -> dict:
    """Taille de ce qui serait exporté (lecture seule)."""
    units, ws_info, warnings = collect_units(selected_ws)
    walker = Walker()
    _count_all(units, walker, progress, cancel)
    groups: dict[str, dict] = {g: {"id": g, "label": lab, "files": 0, "bytes": 0, "units": 0}
                               for g, lab in GROUP_LABELS.items()}
    for u in units:
        g = groups[u.group]
        g["files"] += u.files
        g["bytes"] += u.bytes
        g["units"] += 1
    ws_sizes = {u.extra["ws_id"]: u for u in units if u.kind == "workspace"}
    workspaces = []
    for w in ws_info:
        u = ws_sizes.get(w["id"])
        workspaces.append({
            "id": w["id"], "label": w["label"], "emoji": w["emoji"], "path": w["path"],
            "exists": w["exists"], "selected": w["selected"],
            "files": u.files if u else 0, "bytes": u.bytes if u else 0,
        })
    try:
        env_keys = len(load_env_local_strict())
        env_error = None
    except Exception as e:  # noqa: BLE001 - EnvStoreUnreadable : message sans secret
        env_keys, env_error = 0, str(e)
    return {
        "groups": [groups[g] for g in GROUP_LABELS],
        "workspaces": workspaces,
        "total_bytes": sum(u.bytes for u in units),
        "total_files": sum(u.files for u in units),
        "env_keys": env_keys,
        "env_error": env_error,
        "env_encrypted_source": is_encrypted_mode(),
        "recreate": _recreate_list(walker),
        "warnings": warnings + walker.warnings(),
    }


def _recreate_list(walker: Walker) -> list[str]:
    """Environnements à recréer sur la machine cible (venv, node_modules écartés)
    dans les serveurs MCP locaux et les workspaces."""
    out = []
    for e in walker.excluded:
        if e["name"] in _ENV_LIKE_DIRS:
            out.append(e["path"])
    return out[:200]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class _FixedReader:
    """Lit exactement `size` octets d'un fichier qui peut changer pendant
    l'export (transcript de session en cours d'écriture) : tronque s'il a grossi,
    complète par des zéros s'il a rétréci (comptabilisé)."""

    def __init__(self, f, size: int, stats: dict, cancel: CancelFn | None):
        self._f = f
        self._left = size
        self._stats = stats
        self._cancel = cancel

    def read(self, n: int = -1) -> bytes:
        if self._cancel and self._cancel():
            raise MigrationCancelled()
        if self._left <= 0:
            return b""
        n = self._left if n < 0 else min(n, self._left)
        try:
            data = self._f.read(n)
        except OSError:
            data = b""
        if len(data) < n:
            self._stats["padded"] += 1
            data = data + b"\0" * (n - len(data))
        self._left -= len(data)
        return data


def _tarinfo(name: str, size: int, mtime: float, is_dir: bool = False,
             executable: bool = False) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(name)
    ti.size = 0 if is_dir else size
    ti.mtime = int(mtime)
    ti.type = tarfile.DIRTYPE if is_dir else tarfile.REGTYPE
    ti.mode = 0o755 if (is_dir or executable) else 0o644
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = ""
    return ti


def _add_bytes(tf: tarfile.TarFile, name: str, data: bytes) -> None:
    ti = _tarinfo(name, len(data), time.time())
    tf.addfile(ti, io.BytesIO(data))


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


def _build_manifest(units: list[Unit], ws_info: list[dict], walker: Walker,
                    warnings: list[str], env_keys: list[str], plugins: list[str],
                    claude_json: dict) -> dict:
    selected = [w for w in ws_info if w["selected"]]
    return {
        "format": FORMAT_NAME,
        "format_version": MIGRATION_FORMAT_VERSION,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "nebula_version": _nebula_version(),
        "source": source_info(),
        "workspaces": [{
            "id": w["id"], "label": w["label"], "emoji": w["emoji"],
            "source_path": w["path"], "in_workspaces_dir": w["in_workspaces_dir"],
            "entry": w["entry"],
        } for w in selected],
        "units": [u.manifest_entry() for u in units],
        "env_keys": sorted(env_keys),
        "mcp_ids": [],            # rempli par l'appelant
        "claude_json": {"projects": sorted(claude_json["projects"]),
                        "root_mcp": sorted(claude_json["mcpServers"])},
        "plugins_installed": plugins,
        "recreate": _recreate_list(walker),
        "excluded_dirs": sorted(MIGRATION_EXCLUDED_DIRS),
        "totals": {"files": sum(u.files for u in units), "bytes": sum(u.bytes for u in units)},
        "warnings": warnings + walker.warnings(),
    }


def _nebula_version() -> str:
    from dashcore import __version__
    return __version__


def _unique_dest(dest_dir: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = dest_dir / f"nebula-migration-{stamp}{MIGRATION_EXT}"
    n = 2
    cand = base
    while cand.exists() or cand.with_name(cand.name + ".part").exists():
        cand = dest_dir / f"nebula-migration-{stamp}-{n}{MIGRATION_EXT}"
        n += 1
    return cand


def _restrict_file(path: Path) -> None:
    """Archive lisible par l'utilisateur seul (best-effort)."""
    try:
        if IS_WINDOWS:
            from dashcore.env_crypto import restrict_acl_user_only
            restrict_acl_user_only(path)
        else:
            os.chmod(path, 0o600)
    except Exception as e:  # noqa: BLE001 - jamais bloquant
        log.warning("migration: permissions de l'archive non restreintes : %s", type(e).__name__)


def validate_passphrase(passphrase) -> str | None:
    if not isinstance(passphrase, str) or len(passphrase) < MIGRATION_MIN_PASSPHRASE:
        return (f"La phrase de passe doit faire au moins {MIGRATION_MIN_PASSPHRASE} caractères.")
    return None


def run_export(passphrase: str, dest_dir: str, selected_ws: set[str] | None,
               progress: ProgressFn | None = None, cancel: CancelFn | None = None,
               kdf_iterations: int | None = None) -> dict:
    """Écrit l'archive chiffrée et la vérifie. Retourne le bilan (sans secret).

    Lève `MigrationError` (message affichable) ; le fichier partiel est supprimé
    en cas d'échec ou d'annulation."""
    err = validate_passphrase(passphrase)
    if err:
        raise MigrationError(err)
    dest = Path(os.path.expanduser(str(dest_dir or "").strip())) if dest_dir else None
    if dest is None or not dest.is_absolute():
        raise MigrationError("Dossier de destination : chemin absolu requis.")
    try:
        dest.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(dest).free
    except OSError as e:
        raise MigrationError(f"Dossier de destination inutilisable : {e.strerror or e}") from e
    if free < 100 << 20:
        raise MigrationError("Moins de 100 Mio libres dans le dossier de destination.")

    def prog(phase, done, total, label=""):
        if progress:
            progress(phase, done, total, label)

    started = time.time()
    # Lectures strictes AVANT toute écriture : un registre ou un coffre illisible
    # ferait exporter une archive silencieusement incomplète.
    units, ws_info, warnings = collect_units(selected_ws)
    env = load_env_local_strict()           # EnvStoreUnreadable -> 409 côté serveur
    ws_registry = read_json_strict(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    mcp_registry = read_json_strict(MCP_REGISTRY, {"version": "1.0", "mcps": []})
    claude_json = claude_json_extract()
    plugins = installed_plugin_names()

    walker = Walker()
    _count_all(units, walker, progress, cancel)
    manifest = _build_manifest(units, ws_info, walker, warnings, list(env), plugins, claude_json)
    manifest["mcp_ids"] = sorted(
        str(m.get("id")) for m in (mcp_registry.get("mcps") or []) if isinstance(m, dict) and m.get("id"))
    selected_ids = {w["id"] for w in ws_info if w["selected"]}
    ws_meta = {"version": ws_registry.get("version", "1.0"),
               "workspaces": [w for w in ws_registry.get("workspaces", [])
                              if isinstance(w, dict) and w.get("id") in selected_ids]}

    final = _unique_dest(dest)
    part = final.with_name(final.name + ".part")
    stats = {"padded": 0, "skipped": 0, "files": 0, "bytes": 0}
    total_bytes = max(manifest["totals"]["bytes"], 1)
    skip_paths = {os.path.normcase(os.path.abspath(part)), os.path.normcase(os.path.abspath(final))}
    raw = open(part, "wb")
    enc = None
    gz = None
    tf = None
    try:
        enc = EncryptingWriter(raw, passphrase, kdf_iterations or _default_iterations())
        # Membres gzip indépendants compressés en parallèle (migration_gzip.py) :
        # même format relu par `gzip.GzipFile`, mais tous les cœurs travaillent.
        gz = ParallelGzipWriter(enc)
        tf =tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT)
        _add_bytes(tf, MANIFEST_NAME, _json_bytes(manifest))
        _add_bytes(tf, "meta/workspaces.json", _json_bytes(ws_meta))
        _add_bytes(tf, "meta/mcp_registry.json", _json_bytes(mcp_registry))
        _add_bytes(tf, "meta/env.json", _json_bytes(
            {"env": env, "encrypted_source": is_encrypted_mode()}))
        _add_bytes(tf, "meta/claude_json.json", _json_bytes(claude_json))
        _add_bytes(tf, "meta/plugins.json", _json_bytes({"plugins": plugins}))
        env = None  # n'est plus utile en mémoire
        for u in units:
            prog("write", stats["bytes"], total_bytes, u.label)
            walker2 = Walker()
            for path, arc, is_dir, size in walk_unit(u, walker2):
                if cancel and cancel():
                    raise MigrationCancelled()
                if is_dir:
                    try:
                        mtime = os.stat(path).st_mtime
                    except OSError:
                        stats["skipped"] += 1
                        continue
                    tf.addfile(_tarinfo(arc, 0, mtime, True))
                    continue
                if os.path.normcase(os.path.abspath(path)) in skip_paths:
                    continue          # destination dans un dossier exporté : jamais l'archive elle-même
                _add_file(tf, path, arc, stats, cancel)
                if stats["files"] % 50 == 0:
                    prog("write", stats["bytes"], total_bytes, u.label)
        tf.close()
        gz.close()
        enc.close()           # écrit l'étiquette et ferme `raw`
    except BaseException:
        for closer in (tf, gz):
            try:
                if closer is not None:
                    closer.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            raw.close()
        except OSError:
            pass
        try:
            part.unlink()
        except OSError:
            pass
        raise
    os.replace(part, final)
    _restrict_file(final)

    # Vérification : étiquette + relecture du manifeste (preuve de relecture).
    prog("verify", 0, 1, "")
    try:
        with open_archive(final, passphrase,
                          lambda d, t: prog("verify", d, t, ""), cancel) as arc_open:
            stream = ArchiveStream(arc_open)
            m2, _meta = read_head(stream)
            stream.close()
        if m2.get("totals") != manifest["totals"]:
            raise MigrationError("Vérification de l'archive : manifeste différent.")
    except MigrationError:
        try:
            final.unlink()
        except OSError:
            pass
        raise
    size = final.stat().st_size
    log.info("migration: export termine -> %s (%d octets)", final, size)
    warns = manifest["warnings"]
    if stats["padded"]:
        warns = warns + [f"{stats['padded']} fichier(s) modifié(s) pendant l'export (session en cours ?) : "
                         "complété(s) par des zéros ; relance l'export Claude Code fermé."]
    if stats["skipped"]:
        warns = warns + [f"{stats['skipped']} fichier(s) illisible(s) ignoré(s)."]
    return {
        "path": str(final), "size": size, "verified": True,
        "files": stats["files"], "bytes": stats["bytes"],
        "workspaces": len(manifest["workspaces"]),
        "env_keys": len(manifest["env_keys"]),
        "recreate": manifest["recreate"], "warnings": warns,
        "plugins_installed": plugins,
        "seconds": round(time.time() - started, 1),
    }


def _default_iterations() -> int:
    from dashcore.config import MIGRATION_KDF_ITERATIONS
    return MIGRATION_KDF_ITERATIONS


def _add_file(tf: tarfile.TarFile, path: str, arc: str, stats: dict,
              cancel: CancelFn | None) -> None:
    try:
        f = open(path, "rb")
    except OSError:
        stats["skipped"] += 1
        return
    with f:
        try:
            st = os.fstat(f.fileno())
        except OSError:
            stats["skipped"] += 1
            return
        tf.addfile(_tarinfo(arc, st.st_size, st.st_mtime, executable=bool(st.st_mode & 0o111)),
                   _FixedReader(f, st.st_size, stats, cancel))
        stats["files"] += 1
        stats["bytes"] += st.st_size


# ---------------------------------------------------------------------------
# Lecture d'une archive (partagée par l'export, pour sa vérification, et l'import)
# ---------------------------------------------------------------------------

class ArchiveStream:
    """Parcours séquentiel (tar en flux) d'une archive ouverte et vérifiée."""

    def __init__(self, opened: OpenedArchive):
        self.opened = opened
        self._gz = gzip.GzipFile(fileobj=opened.reader, mode="rb")
        self._tf = tarfile.open(fileobj=self._gz, mode="r|")
        self._it = iter(self._tf)
        self._pending = None

    def next_member(self) -> tarfile.TarInfo | None:
        if self._pending is not None:
            m, self._pending = self._pending, None
            return m
        try:
            return next(self._it, None)
        except (tarfile.TarError, EOFError, OSError, zlib.error) as e:
            if isinstance(e, MigrationError):
                raise
            raise MigrationFormatError("Contenu de l'archive illisible.") from e

    def push_back(self, m: tarfile.TarInfo) -> None:
        self._pending = m

    def file_object(self, m: tarfile.TarInfo):
        f = self._tf.extractfile(m)
        if f is None:
            raise MigrationFormatError("Entrée d'archive illisible.")
        return f

    def read_bytes(self, m: tarfile.TarInfo, cap: int = MAX_META_BYTES) -> bytes:
        if m.size > cap:
            raise MigrationFormatError("Entrée de description anormalement grosse.")
        try:
            return self.file_object(m).read(cap + 1)
        except (tarfile.TarError, EOFError, zlib.error) as e:
            raise MigrationFormatError("Contenu de l'archive illisible.") from e

    def close(self) -> None:
        try:
            self._tf.close()
        except Exception:  # noqa: BLE001
            pass


def read_head(stream: ArchiveStream) -> tuple[dict, dict]:
    """Manifeste + fichiers `meta/*` (parsés). S'arrête au premier membre de
    données, qu'il remet en attente pour la suite."""
    m = stream.next_member()
    if m is None or m.name != MANIFEST_NAME or not m.isreg():
        raise MigrationFormatError("Archive invalide : manifeste absent.")
    try:
        manifest = json.loads(stream.read_bytes(m).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise MigrationFormatError("Manifeste illisible.") from e
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT_NAME:
        raise MigrationFormatError("Ce fichier n'est pas une archive de migration Nebula.")
    version = manifest.get("format_version")
    if not isinstance(version, int) or version < 1:
        raise MigrationFormatError("Version du format invalide.")
    if version > MIGRATION_FORMAT_VERSION:
        raise MigrationFormatError(
            f"Archive de format {version}, plus récente que cette version de Nebula : "
            "mets Nebula à jour avant d'importer.")
    meta: dict = {}
    while True:
        m = stream.next_member()
        if m is None:
            break
        if m.name.startswith("meta/") and m.name.endswith(".json") and m.isreg():
            try:
                meta[m.name[5:-5]] = json.loads(stream.read_bytes(m).decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                raise MigrationFormatError(f"Description « {m.name} » illisible.") from e
        else:
            stream.push_back(m)
            break
    return manifest, meta
