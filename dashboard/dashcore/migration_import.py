"""Migration d'environnement : aperçu (lecture seule) puis import.

Déroulé d'un import sûr :

1. `preview_archive` : première passe d'authentification (étiquette HMAC vérifiée
   avant tout déchiffrement), lecture du seul manifeste + `meta/*`, puis
   `build_plan` : ce qui serait créé / ignoré / remplacé, les conflits, les
   chemins remappés. AUCUNE écriture. Le plan reçoit un `digest` ; l'appelant
   (api_migration) en fait un `plan_id` à durée limitée.
2. `run_import` : réauthentifie l'archive (phrase de passe redemandée, jamais
   conservée), relit les `meta/*`, RECONSTRUIT le plan et refuse s'il diffère du
   plan prévisualisé (`PlanStale`), extrait les seules unités retenues dans un
   dossier de préparation (rien n'est touché ailleurs), vérifie l'étiquette en fin
   de flux, PUIS applique : tout ce qui est remplacé est d'abord rangé dans
   `backups/migration-<horodatage>/`, les fichiers JSON de configuration sont
   fusionnés (jamais réécrits à l'aveugle), les sessions sont fusionnées fichier
   par fichier sans jamais écraser.
"""
from __future__ import annotations

import datetime as dt
import filecmp
import hashlib
import json
import os
import re
import shutil
import tarfile
import time
import zlib
from pathlib import Path
from typing import Callable

from dashcore.config import (
    BACKUPS_DIR, CLAUDE_HOME, CLAUDE_JSON, CLAUDE_PROJECTS, DASHBOARD_DIR, DATA_DIR, ROOT, ENV_ENC_FILE,
    ENV_FILE, ENV_KEY_RE, IS_WINDOWS, JOURNAL_FILE, MCP_REGISTRY, MIGRATION_BACKUP_PREFIX,
    MIGRATION_CLAUDE_DIRS, MIGRATION_CLAUDE_FILES, MIGRATION_CLAUDE_MERGE_DIRS,
    MIGRATION_DATA_FILES, MIGRATION_EXT, MIGRATION_MAX_MEMBERS, SCRIPTS_DIR, SKILLS_LIBRARY_DIR,
    TEMPLATES_DIR, WORKSPACES_DIR, WORKSPACES_JSON, _MUTATION_LOCK, log,
)
from dashcore.env_local import load_env_local_strict, set_env_var
from dashcore.helpers import (
    _remove_dir_or_link, read_json_strict, safe_id, sanitize_bat, validate_ws_path, write_json,
    write_launch_bat,
)
from dashcore.migration import (
    GROUP_LABELS, ArchiveStream, read_head, source_info,
)
from dashcore.migration_crypto import (
    MigrationCancelled, MigrationError, MigrationFormatError, open_archive,
    read_header_and_tag,
)
from dashcore.migration_paths import PathRemapper, Rule, is_windows_style, split_member_name

ProgressFn = Callable[[str, int, int, str], None]
CancelFn = Callable[[], bool]

_UNIT_KINDS = {"workspace", "item", "merge"}
_NEBULA_DIRS = ("skills-library", "memory", "templates", "mcp-configs", "mcp-servers")
_WS_ACTIONS = {"import", "skip", "replace", "rename"}
_STAGING_NAME = ".migration-staging"
_BLOCK = 1 << 20


class PlanStale(MigrationError):
    """Le plan recalculé diffère du plan prévisualisé (état de la cible changé)."""
    code = "plan_stale"

    def __init__(self, plan: dict):
        super().__init__("L'état de cette machine a changé depuis l'aperçu : "
                         "relis le nouvel aperçu avant d'importer.")
        self.plan = plan


# ---------------------------------------------------------------------------
# Archive : informations sans phrase de passe
# ---------------------------------------------------------------------------

def archive_info(path: str) -> dict:
    """Taille, date, version du format et empreinte de l'archive, SANS phrase de
    passe (l'en-tête et l'étiquette ne révèlent rien du contenu)."""
    p = Path(os.path.expanduser(str(path or "").strip()))
    if not p.is_absolute():
        raise MigrationError("Chemin de l'archive : chemin absolu requis.")
    if not p.is_file():
        raise MigrationError("Archive introuvable.")
    try:
        header, tag, size = read_header_and_tag(p)
        mtime_ns = p.stat().st_mtime_ns
    except OSError as e:
        raise MigrationError(f"Archive illisible : {e.strerror or e}") from e
    return {"path": str(p), "name": p.name, "size": size, "mtime_ns": mtime_ns,
            "mtime": dt.datetime.fromtimestamp(mtime_ns / 1e9).isoformat(timespec="seconds"),
            "format_version": header.version, "kdf_iterations": header.iterations,
            "tag": tag.hex()}


def find_archives(folder: str) -> list[dict]:
    """Archives `.nebmig` d'un dossier (non récursif), plus récentes d'abord."""
    d = Path(os.path.expanduser(str(folder or "").strip()))
    if not d.is_absolute():
        raise MigrationError("Dossier : chemin absolu requis.")
    if not d.is_dir():
        return []                 # dossier de sauvegarde pas encore créé : aucune archive
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError as e:
        raise MigrationError(f"Dossier illisible : {e.strerror or e}") from e
    for name in names:
        if not name.endswith(MIGRATION_EXT):
            continue
        try:
            info = archive_info(str(d / name))
        except MigrationError:
            continue
        info.pop("tag", None)
        out.append(info)
    out.sort(key=lambda i: i["mtime_ns"], reverse=True)
    return out[:100]


# ---------------------------------------------------------------------------
# Validation du manifeste (entrée non fiable, même authentifiée)
# ---------------------------------------------------------------------------

def _str(v, cap: int = 1024) -> str:
    if not isinstance(v, str) or "\0" in v or len(v) > cap:
        raise MigrationFormatError("Manifeste invalide (champ texte).")
    return v


def _int(v) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise MigrationFormatError("Manifeste invalide (nombre).")
    return v


def known_unit_key(key: str) -> bool:
    """Clé d'unité reconnue (liste fermée : rien d'autre n'est jamais écrit)."""
    parts = split_member_name(key)
    if not parts:
        return False
    if parts[0] == "ws":
        return len(parts) == 2 and safe_id(parts[1])
    if parts[0] == "claude":
        if len(parts) == 2:
            return parts[1] in MIGRATION_CLAUDE_FILES
        if len(parts) == 3:
            return parts[1] in MIGRATION_CLAUDE_DIRS or parts[1] in MIGRATION_CLAUDE_MERGE_DIRS
        return False
    if parts[0] == "nebula" and len(parts) == 3:
        if parts[1] == "data":
            return parts[2] in MIGRATION_DATA_FILES
        if parts[1] == "mcp-servers":
            return parts[2] != "configs" and not parts[2].lower().startswith("registry.json")
        return parts[1] in _NEBULA_DIRS
    return False


def validate_manifest(m: dict) -> dict:
    """Manifeste normalisé ou `MigrationFormatError`."""
    if not isinstance(m, dict):
        raise MigrationFormatError("Manifeste invalide.")
    src = m.get("source")
    if not isinstance(src, dict):
        raise MigrationFormatError("Manifeste invalide (source).")
    source = {k: _str(src.get(k, ""), 1024) for k in
              ("os", "sep", "host", "root", "user_home", "claude_home", "data_dir", "workspaces_dir")}
    workspaces = []
    seen_ids: set[str] = set()
    for w in m.get("workspaces") or []:
        if not isinstance(w, dict):
            raise MigrationFormatError("Manifeste invalide (workspace).")
        ws_id = _str(w.get("id"), 40)
        if not safe_id(ws_id) or ws_id in seen_ids:
            raise MigrationFormatError("Manifeste invalide (id de workspace).")
        seen_ids.add(ws_id)
        entry = w.get("entry")
        workspaces.append({
            "id": ws_id, "label": _str(w.get("label", ws_id), 200),
            "emoji": _str(w.get("emoji", ""), 16),
            "source_path": _str(w.get("source_path"), 1024),
            "in_workspaces_dir": bool(w.get("in_workspaces_dir")),
            "entry": entry if isinstance(entry, dict) else {},
        })
    units = []
    seen_keys: set[str] = set()
    for u in m.get("units") or []:
        if not isinstance(u, dict):
            raise MigrationFormatError("Manifeste invalide (unité).")
        key = _str(u.get("key"), 400)
        if key in seen_keys or not known_unit_key(key):
            raise MigrationFormatError("Manifeste invalide (unité inconnue).")
        seen_keys.add(key)
        kind, group = _str(u.get("kind"), 20), _str(u.get("group"), 30)
        if kind not in _UNIT_KINDS or group not in GROUP_LABELS:
            raise MigrationFormatError("Manifeste invalide (type d'unité).")
        units.append({"key": key, "kind": kind, "group": group,
                      "label": _str(u.get("label", key), 300), "is_dir": bool(u.get("is_dir")),
                      "files": _int(u.get("files", 0)), "bytes": _int(u.get("bytes", 0))})
    for w in workspaces:
        if f"ws/{w['id']}" not in seen_keys:
            raise MigrationFormatError("Manifeste invalide (workspace sans unité).")
    totals = m.get("totals") or {}
    env_keys = [k for k in (m.get("env_keys") or []) if isinstance(k, str) and ENV_KEY_RE.match(k)]
    return {
        "format_version": _int(m.get("format_version", 1)),
        "created": _str(m.get("created", ""), 40),
        "nebula_version": _str(m.get("nebula_version", ""), 40),
        "source": source, "workspaces": workspaces, "units": units,
        "env_keys": env_keys[:5000],
        "mcp_ids": [x for x in (m.get("mcp_ids") or []) if isinstance(x, str)][:1000],
        "claude_json": m.get("claude_json") if isinstance(m.get("claude_json"), dict) else {},
        "plugins_installed": [x for x in (m.get("plugins_installed") or [])
                              if isinstance(x, str)][:500],
        "recreate": [x for x in (m.get("recreate") or []) if isinstance(x, str)][:200],
        "totals": {"files": _int(totals.get("files", 0)), "bytes": _int(totals.get("bytes", 0))},
        "warnings": [x for x in (m.get("warnings") or []) if isinstance(x, str)][:50],
    }


# ---------------------------------------------------------------------------
# Options de l'utilisateur
# ---------------------------------------------------------------------------

def normalize_options(opts) -> dict:
    o = opts if isinstance(opts, dict) else {}
    rules = []
    for r in (o.get("rules") or [])[:50]:
        if not isinstance(r, dict):
            continue
        a, b = r.get("from"), r.get("to")
        if (isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip()
                and len(a) <= 1024 and len(b) <= 1024 and "\0" not in a + b):
            rules.append({"from": a.strip(), "to": b.strip()})
    workspaces: dict[str, dict] = {}
    for ws_id, d in (o.get("workspaces") or {}).items():
        if not isinstance(d, dict) or not isinstance(ws_id, str):
            continue
        action = d.get("action")
        tp, nid = d.get("target_path"), d.get("new_id")
        workspaces[ws_id] = {
            "action": action if action in _WS_ACTIONS else None,
            "target_path": tp.strip() if isinstance(tp, str) and tp.strip() and "\0" not in tp else None,
            "new_id": nid.strip() if isinstance(nid, str) and nid.strip() else None,
        }

    def pick(name: str, allowed: set[str]) -> dict[str, str]:
        out = {}
        for k, v in (o.get(name) or {}).items():
            if isinstance(k, str) and v in allowed:
                out[k] = v
        return out

    return {
        "rules": rules, "workspaces": workspaces,
        "mcp": pick("mcp", {"skip", "replace"}),
        "env": pick("env", {"keep", "replace"}),
        "items": pick("items", {"skip", "replace"}),
        "claude_json": "replace" if o.get("claude_json") == "replace" else "keep",
    }


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------

def unit_destination(key: str) -> Path | None:
    """Destination d'une unité « item » sur cette machine (None si hors liste)."""
    parts = key.split("/")
    if parts[0] == "claude":
        if len(parts) == 2 and parts[1] in MIGRATION_CLAUDE_FILES:
            return CLAUDE_HOME / parts[1]
        if len(parts) == 3 and parts[1] in MIGRATION_CLAUDE_DIRS:
            return CLAUDE_HOME / parts[1] / parts[2]
    elif parts[0] == "nebula" and len(parts) == 3:
        base = {
            "data": DATA_DIR, "skills-library": SKILLS_LIBRARY_DIR,
            "memory": JOURNAL_FILE.parent, "templates": TEMPLATES_DIR,
            "mcp-configs": MCP_REGISTRY.parent / "configs", "mcp-servers": MCP_REGISTRY.parent,
        }.get(parts[1])
        if base is not None:
            return base / parts[2]
    return None


def merge_destination(key: str, remap: PathRemapper) -> tuple[Path, str] | None:
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "claude":
        return None
    if parts[1] == "projects":
        name = remap.remap_project_dir_name(parts[2])
        return CLAUDE_PROJECTS / name, name
    if parts[1] == "file-history":
        return CLAUDE_HOME / "file-history" / parts[2], parts[2]
    return None


def _pkey(p) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def _anchor_ok(p: str) -> bool:
    """Chemin absolu du style de CE système, dont le lecteur / la racine existe."""
    pp = Path(p)
    if not pp.is_absolute():
        return False
    if is_windows_style(p) != IS_WINDOWS:
        return False
    try:
        return Path(pp.anchor).exists()
    except OSError:
        return False


def _protected_target(p: Path) -> bool:
    """Cible interdite pour un workspace : un dossier protégé, l'un de ses
    ancêtres, ou l'intérieur du code / des données / des sauvegardes de Nebula
    (seul l'intérieur de `workspaces/` est libre)."""
    try:
        t = os.path.normcase(str(p.resolve()))
        sep = os.sep

        def inside(child: str, parent: str) -> bool:
            return child == parent or child.startswith(parent.rstrip(sep) + sep)

        whole = [ROOT, WORKSPACES_DIR, CLAUDE_HOME, DATA_DIR, BACKUPS_DIR, DASHBOARD_DIR,
                 MCP_REGISTRY.parent, TEMPLATES_DIR, SCRIPTS_DIR, Path.home()]
        for q in whole:
            qn = os.path.normcase(str(q.resolve()))
            if inside(qn, t):                 # la cible est le dossier protégé ou un de ses ancêtres
                return True
        for q in (CLAUDE_HOME, DATA_DIR, BACKUPS_DIR, DASHBOARD_DIR, MCP_REGISTRY.parent,
                  TEMPLATES_DIR, SCRIPTS_DIR):
            if inside(t, os.path.normcase(str(q.resolve()))):
                return True                    # la cible est à l'intérieur
    except OSError:
        return True
    return False


def _non_empty(p: Path) -> bool:
    try:
        if not os.path.lexists(p):
            return False
        if p.is_dir() and not p.is_symlink():
            return any(p.iterdir())
        return True
    except OSError:
        return True


def auto_rules(src: dict, tgt: dict) -> list[Rule]:
    rules = []
    for key in ("root", "claude_home", "data_dir", "user_home"):
        if src.get(key) and tgt.get(key) and src[key] != tgt[key]:
            rules.append(Rule(src[key], tgt[key], "auto"))
    return rules


def _unique_id(base: str, taken: set[str]) -> str:
    base = base[:36]
    cand, n = base, 2
    while cand in taken or not safe_id(cand):
        cand = f"{base}-{n}"[:40]
        n += 1
    return cand


# ---------------------------------------------------------------------------
# Plan (lecture seule)
# ---------------------------------------------------------------------------

def _mcp_equal(a: dict, b: dict) -> bool:
    strip = lambda d: {k: v for k, v in d.items() if k != "workspaces"}  # noqa: E731
    return strip(a) == strip(b)


def _norm_key(k: str) -> str:
    """Clé de comparaison de chemins : insensible à la casse et aux séparateurs
    seulement pour un style Windows (un FS POSIX distingue `/srv/App` de `/srv/app`)."""
    n = k.replace("\\", "/").rstrip("/")
    return n.lower() if is_windows_style(k) else n


def build_plan(manifest: dict, meta: dict, options: dict, archive: dict) -> dict:
    """Plan complet (JSON) de ce que ferait l'import avec ces options. Lit l'état
    de cette machine, n'écrit rien. Chaque élément porte son `action` effective."""
    opts = normalize_options(options)
    src, tgt = manifest["source"], source_info()
    user_rules = [Rule(r["from"], r["to"], "user") for r in opts["rules"]]
    base_rules = user_rules + auto_rules(src, tgt)
    base = PathRemapper(base_rules)
    warnings: list[str] = []
    notes: list[str] = []

    reg = read_json_strict(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    reg_ws = [w for w in reg.get("workspaces", []) if isinstance(w, dict)]
    from dashcore.workspace_io import _ws_dir_from_entry
    reg_ids = {w.get("id") for w in reg_ws}
    reg_paths = {}
    for w in reg_ws:
        try:
            reg_paths[_pkey(_ws_dir_from_entry(w))] = w.get("id")
        except (OSError, ValueError):
            pass
    units_by_key = {u["key"]: u for u in manifest["units"]}

    # -- Workspaces ----------------------------------------------------------
    from dashcore.api_workspaces import _is_path_root, _is_path_under_claude_home
    ws_plan: list[dict] = []
    taken_ids = set(reg_ids) | {w["id"] for w in manifest["workspaces"]}
    plan_target_keys: dict[str, str] = {}
    for w in manifest["workspaces"]:
        d = opts["workspaces"].get(w["id"], {})
        req = d.get("action")
        unit = units_by_key[f"ws/{w['id']}"]
        suggested = _unique_id(w["id"] + "-import", taken_ids)
        eff_id = (d.get("new_id") or suggested) if req == "rename" else w["id"]
        if d.get("target_path"):
            target, origin = d["target_path"], "user"
        elif w["in_workspaces_dir"]:
            target, origin = str(WORKSPACES_DIR / eff_id), "workspaces"
        else:
            mapped = base.remap_text(w["source_path"])
            if mapped != w["source_path"]:
                target, origin = mapped, "rule"
            elif _anchor_ok(w["source_path"]):
                target, origin = w["source_path"], "same"
            else:
                target, origin = str(WORKSPACES_DIR / eff_id), "fallback"
        id_conflict = eff_id in reg_ids
        path_owner = reg_paths.get(_pkey(target))
        tpath = Path(target)
        fs_conflict = _non_empty(tpath)
        conflicts = []
        if id_conflict:
            conflicts.append("id")
        if fs_conflict or (path_owner and path_owner != eff_id):
            conflicts.append("path")
        action = req or ("import" if not conflicts else "skip")
        blocked = None
        if action != "skip":
            ok, why = validate_ws_path(target)
            if not ok:
                blocked = f"chemin cible invalide : {why}"
            elif not _anchor_ok(target):
                blocked = "chemin cible inutilisable sur ce système (lecteur absent ou style de chemin différent)"
            elif _is_path_under_claude_home(tpath):
                blocked = "chemin cible interdit : sous ~/.claude/"
            elif _is_path_root(tpath) or _protected_target(tpath):
                blocked = "chemin cible interdit : installation de Nebula, configuration Claude ou dossier personnel"
            elif path_owner and path_owner != eff_id:
                blocked = f"chemin déjà utilisé par le workspace « {path_owner} »"
            elif _pkey(target) in plan_target_keys:
                blocked = f"chemin déjà visé par le workspace « {plan_target_keys[_pkey(target)]} »"
            elif action == "import" and conflicts:
                blocked = "conflit non résolu : choisis Remplacer, Renommer ou Ignorer"
            elif action == "rename":
                if not safe_id(eff_id):
                    blocked = "nouvel id invalide (lettres, chiffres, - et _, 40 max)"
                elif id_conflict:
                    blocked = "ce nouvel id existe déjà"
                elif fs_conflict:
                    blocked = "chemin occupé : choisis un autre chemin cible"
            elif action == "replace" and not conflicts:
                action = "import"
            if blocked is None:
                plan_target_keys[_pkey(target)] = eff_id
                if eff_id != w["id"]:
                    taken_ids.add(eff_id)
        ws_plan.append({
            "id": w["id"], "eff_id": eff_id, "label": w["label"], "emoji": w["emoji"],
            "source_path": w["source_path"], "target_path": target, "path_origin": origin,
            "status": "new" if not conflicts else "conflict", "conflicts": conflicts,
            "action": action, "blocked": blocked, "suggested_id": suggested,
            "target_exists": os.path.lexists(tpath),
            "parent_exists": tpath.parent.exists(),
            "files": unit["files"], "bytes": unit["bytes"],
        })
    ws_rules = [Rule(w["source_path"], w["target_path"], "workspace")
                for w in ws_plan if w["action"] != "skip" and not w["blocked"]
                and _norm_key(w["source_path"]) != _norm_key(w["target_path"])]
    full = PathRemapper(ws_rules + base_rules)

    # -- Registre MCP --------------------------------------------------------
    mcp_src = (meta.get("mcp_registry") or {}).get("mcps") or []
    mcp_tgt_reg = read_json_strict(MCP_REGISTRY, {"version": "1.0", "mcps": []})
    mcp_tgt = {m.get("id"): m for m in mcp_tgt_reg.get("mcps", []) if isinstance(m, dict)}
    mcp_plan = []
    for m in mcp_src:
        if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not safe_id(m["id"]):
            continue
        remapped, _n = full.remap_json(m)
        existing = mcp_tgt.get(m["id"])
        if existing is None:
            status, action = "new", "import"
        elif _mcp_equal(existing, remapped):
            status, action = "same", "none"
        else:
            status = "conflict"
            action = opts["mcp"].get(m["id"], "skip")
        mcp_plan.append({"id": m["id"], "name": str(m.get("name") or m["id"]),
                         "status": status, "action": action})

    # -- Variables d'environnement ------------------------------------------
    env_src = (meta.get("env") or {}).get("env") or {}
    env_plan: dict = {"items": [], "error": None}
    try:
        env_tgt = load_env_local_strict()
    except Exception as e:  # noqa: BLE001 - EnvStoreUnreadable, message sans secret
        env_tgt = None
        env_plan["error"] = str(e)
    if env_tgt is not None:
        for k in sorted(env_src):
            if not isinstance(k, str) or not ENV_KEY_RE.match(k) or not isinstance(env_src[k], str):
                continue
            val = full.remap_text(env_src[k])
            if k not in env_tgt:
                status, action = "new", "import"
            elif env_tgt[k] == val:
                status, action = "same", "none"
            else:
                status = "conflict"
                action = "replace" if opts["env"].get(k) == "replace" else "keep"
            env_plan["items"].append({"key": k, "status": status, "action": action})

    # -- ~/.claude.json ------------------------------------------------------
    cj_src = meta.get("claude_json") or {}
    cj_plan = {"policy": opts["claude_json"], "projects": 0, "projects_new": 0,
               "projects_merge": 0, "missing_paths": 0, "mcp_conflicts": 0, "error": None}
    try:
        cj_tgt = read_json_strict(CLAUDE_JSON, {})
    except Exception as e:  # noqa: BLE001 - CorruptJsonError
        cj_tgt, cj_plan["error"] = None, str(e)
    if isinstance(cj_tgt, dict):
        tgt_keys = {_norm_key(k) for k in (cj_tgt.get("projects") or {})}
        for key, proj in (cj_src.get("projects") or {}).items():
            if not isinstance(key, str) or not isinstance(proj, dict):
                continue
            cj_plan["projects"] += 1
            nk = full.remap_text(key)
            if _norm_key(nk) in tgt_keys:
                cj_plan["projects_merge"] += 1
                existing = next((v for k, v in cj_tgt["projects"].items()
                                 if _norm_key(k) == _norm_key(nk)), {})
                new_mcp = full.remap_json(proj.get("mcpServers") or {})[0]
                for name, conf in new_mcp.items():
                    cur = (existing.get("mcpServers") or {}).get(name)
                    if cur is not None and cur != conf:
                        cj_plan["mcp_conflicts"] += 1
            else:
                cj_plan["projects_new"] += 1
            try:
                if not Path(nk).exists():
                    cj_plan["missing_paths"] += 1
            except OSError:
                cj_plan["missing_paths"] += 1

    # -- Éléments (fichiers de config, skills, templates, serveurs MCP...) ---
    item_plan = []
    for u in manifest["units"]:
        if u["kind"] != "item":
            continue
        dest = unit_destination(u["key"])
        if dest is None:
            raise MigrationFormatError("Manifeste invalide (destination d'élément).")
        exists = os.path.lexists(dest)
        req = opts["items"].get(u["key"])
        if not exists:
            action = "import"
        else:
            action = "replace" if req == "replace" else "skip"
        item_plan.append({"key": u["key"], "group": u["group"], "label": u["label"],
                          "kind": "dir" if u["is_dir"] else "file", "status": "exists" if exists else "new",
                          "action": action, "dest": str(dest), "files": u["files"], "bytes": u["bytes"]})

    # -- Sessions ------------------------------------------------------------
    sessions = []
    for u in manifest["units"]:
        if u["kind"] != "merge":
            continue
        md = merge_destination(u["key"], full)
        if md is None:
            raise MigrationFormatError("Manifeste invalide (destination de sessions).")
        dest, tname = md
        sessions.append({"key": u["key"], "name": u["key"].split("/")[-1], "target_name": tname,
                         "renamed": tname != u["key"].split("/")[-1],
                         "kind": u["key"].split("/")[1],
                         "status": "merge" if dest.exists() else "new",
                         "files": u["files"], "bytes": u["bytes"]})

    # -- Espace disque et notes ---------------------------------------------
    extract_bytes = (sum(w["bytes"] for w in ws_plan if w["action"] != "skip" and not w["blocked"])
                     + sum(i["bytes"] for i in item_plan if i["action"] != "skip")
                     + sum(s["bytes"] for s in sessions))
    probe = BACKUPS_DIR
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        free = 0
    disk = {"needed": extract_bytes, "free": free,
            "ok": free >= int(extract_bytes * 1.05) + (256 << 20)}
    if not disk["ok"]:
        warnings.append("Espace disque insuffisant pour préparer l'import "
                        f"({extract_bytes} octets nécessaires, {free} libres).")
    if src["os"] != tgt["os"]:
        notes.append(f"Archive créée sous « {src['os']} », importée sous « {tgt['os']} » : les chemins "
                     "absolus sont convertis, mais vérifie les commandes et scripts propres à un système.")
    if manifest["recreate"]:
        notes.append(f"{len(manifest['recreate'])} environnement(s) (.venv, node_modules) non exportés : "
                     "à recréer sur cette machine (voir la liste).")
    if manifest["plugins_installed"]:
        notes.append(f"{len(manifest['plugins_installed'])} plugin(s) Claude Code étaient installés : "
                     "ils sont à réinstaller (page Plugins), seule leur liste est conservée.")
    if (meta.get("env") or {}).get("encrypted_source") and not ENV_ENC_FILE.exists():
        notes.append("Les secrets venaient d'un coffre chiffré (DPAPI) ; ils seront écrits en clair dans "
                     "`.env.local` : réactive le chiffrement dans Outils après l'import.")
    if cj_plan["missing_paths"]:
        notes.append(f"{cj_plan['missing_paths']} projet(s) de ~/.claude.json pointent vers des dossiers "
                     "absents sur cette machine.")
    try:
        from dashcore import active_sessions
        # (la purge des PID morts que fait list_active est déjà faite toutes les 5 s par l'UI)
        if active_sessions.list_active(prune_dead=True):
            warnings.append("Une session Claude lancée par Nebula est ouverte : ferme Claude Code "
                            "avant d'importer (il réécrit ~/.claude.json).")
    except Exception:  # noqa: BLE001 - information seule
        pass

    blocked = any(w["blocked"] for w in ws_plan if w["action"] != "skip")
    if env_plan["error"]:
        warnings.append("Coffre d'environnement illisible sur cette machine : les variables ne seront "
                        "pas importées (corrige le coffre puis relance l'aperçu).")
    counts = {
        "workspaces_import": sum(1 for w in ws_plan if w["action"] != "skip" and not w["blocked"]),
        "workspaces_skip": sum(1 for w in ws_plan if w["action"] == "skip"),
        "workspaces_blocked": sum(1 for w in ws_plan if w["blocked"]),
        "conflicts": (sum(1 for w in ws_plan if w["conflicts"]) + sum(1 for m in mcp_plan if m["status"] == "conflict")
                      + sum(1 for e in env_plan["items"] if e["status"] == "conflict")
                      + sum(1 for i in item_plan if i["status"] == "exists")),
    }
    plan = {
        "archive": {k: archive.get(k) for k in ("path", "name", "size", "mtime", "format_version")}
                   | {"created": manifest["created"], "nebula_version": manifest["nebula_version"],
                      "source_os": src["os"], "source_host": src["host"],
                      "totals": manifest["totals"]},
        "target": tgt,
        "rules": {"auto": [{"from": r.source, "to": r.target} for r in auto_rules(src, tgt)],
                  "user": opts["rules"]},
        "workspaces": ws_plan, "mcp": mcp_plan, "env": env_plan, "claude_json": cj_plan,
        "items": item_plan, "sessions": sessions, "disk": disk,
        "recreate": manifest["recreate"], "plugins_installed": manifest["plugins_installed"],
        "warnings": warnings + manifest["warnings"], "notes": notes, "counts": counts,
        "blocked": blocked, "ok": (not blocked) and disk["ok"],
    }
    digest_src = {
        "tag": archive.get("tag"),
        "ws": [(w["id"], w["eff_id"], w["action"], w["target_path"], bool(w["blocked"])) for w in ws_plan],
        "mcp": [(m["id"], m["action"]) for m in mcp_plan],
        "env": [(e["key"], e["action"]) for e in env_plan["items"]],
        "cj": [cj_plan["policy"], cj_plan["projects_new"], cj_plan["projects_merge"]],
        "items": [(i["key"], i["action"]) for i in item_plan],
        "sessions": [(s["key"], s["target_name"], s["status"]) for s in sessions],
        "rules": [(r.source, r.target) for r in full.rules],
    }
    plan["digest"] = hashlib.sha256(
        json.dumps(digest_src, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return plan


# ---------------------------------------------------------------------------
# Aperçu
# ---------------------------------------------------------------------------

def preview_archive(path: str, passphrase: str, options: dict,
                    progress: ProgressFn | None = None, cancel: CancelFn | None = None) -> tuple[dict, dict]:
    """Aperçu (aucune écriture). Retourne (plan, empreinte de l'archive)."""
    info = archive_info(path)
    p = Path(info["path"])
    with open_archive(p, passphrase,
                      (lambda d, t: progress("verify", d, t, "")) if progress else None, cancel) as oa:
        if oa.tag.hex() != info["tag"]:
            raise MigrationError("L'archive a changé pendant la lecture.")
        stream = ArchiveStream(oa)
        manifest, meta = read_head(stream)
        stream.close()
    manifest = validate_manifest(manifest)
    if progress:
        progress("plan", 0, 1, "")
    plan = build_plan(manifest, meta, options, info)
    fingerprint = {"path": info["path"], "size": info["size"], "mtime_ns": info["mtime_ns"],
                   "tag": info["tag"]}
    return plan, fingerprint


# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------

class _Backup:
    """Dossier `backups/migration-<horodatage>/`, créé à la première sauvegarde."""

    def __init__(self):
        self.stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = BACKUPS_DIR / f"{MIGRATION_BACKUP_PREFIX}{self.stamp}"
        self.used = False

    def _target(self, rel: str) -> Path:
        self.used = True
        t = self.dir.joinpath(*rel.split("/"))
        t.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(t):
            t = t.with_name(t.name + f".{int(time.time())}")
        return t

    def stash(self, path: Path, rel: str) -> None:
        """Range `path` (déplacé, jamais supprimé) dans la sauvegarde."""
        _move_tree(path, self._target(rel))

    def copy_file(self, path: Path, rel: str) -> None:
        if path.is_file():
            shutil.copy2(path, self._target(rel))


def _move_tree(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(src, dst)
        return
    except OSError:
        pass
    if src.is_dir() and not src.is_symlink():
        shutil.copytree(src, dst, symlinks=True)
        _remove_dir_or_link(src)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)
        src.unlink()


def _remap_json_file(path: Path, remap: PathRemapper) -> bool:
    """Réécrit un fichier JSON dont des valeurs contiennent un chemin remappé."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    new, n = remap.remap_json(data)
    if not n:
        return False
    path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def _extract_targets(plan: dict) -> set[str]:
    keys = {f"ws/{w['id']}" for w in plan["workspaces"] if w["action"] != "skip" and not w["blocked"]}
    keys |= {i["key"] for i in plan["items"] if i["action"] != "skip"}
    keys |= {s["key"] for s in plan["sessions"]}
    return keys


def _unit_of_member(parts: list[str], known) -> str | None:
    for n in (3, 2):
        if len(parts) >= n and "/".join(parts[:n]) in known:
            return "/".join(parts[:n])
    return None


def _extract(stream: ArchiveStream, units: dict[str, dict], wanted: set[str], staging: Path,
             declared: int, progress: ProgressFn | None, cancel: CancelFn | None) -> dict:
    stats = {"files": 0, "bytes": 0, "errors": []}
    cap = declared + declared // 50 + (64 << 20)
    members = 0
    staging_resolved = staging.resolve()
    known = set(units)
    while True:
        if cancel and cancel():
            raise MigrationCancelled()
        m = stream.next_member()
        if m is None:
            break
        members += 1
        if members > MIGRATION_MAX_MEMBERS:
            raise MigrationFormatError("Archive anormale : trop d'entrées.")
        if not (m.isreg() or m.isdir()):
            raise MigrationFormatError("Entrée refusée (lien ou fichier spécial) : archive non conforme.")
        parts = split_member_name(m.name)
        if not parts:
            raise MigrationFormatError("Entrée refusée (chemin dangereux) : archive non conforme.")
        unit = _unit_of_member(parts, known)
        if unit is None:
            raise MigrationFormatError("Entrée refusée (hors des unités déclarées).")
        if unit not in wanted:
            continue
        dest = staging.joinpath(*parts)
        try:
            dest.resolve().relative_to(staging_resolved)
        except (ValueError, OSError):
            raise MigrationFormatError("Entrée refusée (sortie du dossier de préparation).") from None
        if m.isdir():
            try:
                dest.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                if len(stats["errors"]) < 100:
                    stats["errors"].append({"path": m.name, "error": e.strerror or "erreur"})
            continue
        stats["bytes"] += m.size
        if stats["bytes"] > cap:
            raise MigrationFormatError("Archive anormale : volume supérieur à celui déclaré.")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as out:
                src_f = stream.file_object(m)
                while True:
                    block = src_f.read(_BLOCK)
                    if not block:
                        break
                    out.write(block)
            if not IS_WINDOWS and m.mode & 0o111:
                try:
                    os.chmod(dest, 0o755)
                except OSError:
                    pass
            try:
                os.utime(dest, (m.mtime, m.mtime))
            except (OSError, OverflowError, ValueError):
                pass            # date non rétablie : sans conséquence
            stats["files"] += 1
        except OSError as e:
            if len(stats["errors"]) < 100:
                stats["errors"].append({"path": m.name, "error": e.strerror or "erreur"})
        except (tarfile.TarError, EOFError, zlib.error) as e:
            raise MigrationFormatError("Contenu de l'archive illisible.") from e
        if progress and stats["files"] % 25 == 0:
            progress("extract", stats["bytes"], max(declared, 1), m.name.split("/", 2)[-1][:80])
    return stats


def run_import(stored: dict, passphrase: str, progress: ProgressFn | None = None,
               cancel: CancelFn | None = None) -> dict:
    """Importe l'archive selon le plan prévisualisé (`stored`, cf. api_migration).

    Lève `PlanStale` si l'état a changé, `MigrationError` sinon. Retourne le
    bilan (sans secret)."""
    p = Path(stored["archive"]["path"])
    info = archive_info(str(p))
    for k in ("size", "mtime_ns", "tag"):
        if info[k] != stored["archive"][k]:
            raise MigrationError("L'archive a changé depuis l'aperçu : relance l'aperçu.")
    started = time.time()
    with open_archive(p, passphrase,
                      (lambda d, t: progress("verify", d, t, "")) if progress else None, cancel) as oa:
        if oa.tag.hex() != info["tag"]:
            raise MigrationError("L'archive a changé pendant la lecture.")
        stream = ArchiveStream(oa)
        manifest, meta = read_head(stream)
        manifest = validate_manifest(manifest)
        plan = build_plan(manifest, meta, stored["options"], info)
        if plan["digest"] != stored["digest"]:
            raise PlanStale(plan)
        if plan["blocked"]:
            raise MigrationError("Le plan contient des éléments bloqués : corrige-les dans l'aperçu.")
        if not plan["disk"]["ok"]:
            raise MigrationError("Espace disque insuffisant pour préparer l'import.")
        units = {u["key"]: u for u in manifest["units"]}
        wanted = _extract_targets(plan)
        declared = sum(units[k]["bytes"] for k in wanted)
        staging = BACKUPS_DIR / _STAGING_NAME / f"{int(time.time())}-{os.getpid()}"
        staging.mkdir(parents=True, exist_ok=True)
        try:
            ex = _extract(stream, units, wanted, staging, declared, progress, cancel)
            stream.close()
            oa.finish()           # étiquette finale : rien n'est appliqué avant
            if progress:
                progress("apply", 0, 1, "")
            result = _apply(plan, manifest, meta, staging, progress)
        finally:
            try:
                _remove_dir_or_link(staging)
                parent = staging.parent
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
                if BACKUPS_DIR.is_dir() and not any(BACKUPS_DIR.iterdir()):
                    BACKUPS_DIR.rmdir()       # créé pour la préparation : rien à y garder
            except OSError:
                log.warning("migration: dossier de préparation non supprimé : %s", staging)
    result["extract_errors"] = ex["errors"]
    result["seconds"] = round(time.time() - started, 1)
    log.info("migration: import termine (%d workspace(s), sauvegarde %s)",
             result["workspaces"]["imported"], result.get("backup_dir"))
    return result


def _apply(plan: dict, manifest: dict, meta: dict, staging: Path,
           progress: ProgressFn | None) -> dict:
    """Applique le plan à partir du dossier de préparation (étiquette déjà vérifiée)."""
    src, tgt = manifest["source"], source_info()
    user_rules = [Rule(r["from"], r["to"], "user") for r in plan["rules"]["user"]]
    base_rules = user_rules + auto_rules(src, tgt)
    ws_rules = [Rule(w["source_path"], w["target_path"], "workspace")
                for w in plan["workspaces"] if w["action"] != "skip"
                and _norm_key(w["source_path"]) != _norm_key(w["target_path"])]
    full = PathRemapper(ws_rules + base_rules)
    backup = _Backup()
    errors: list[dict] = []
    res = {"workspaces": {"imported": 0, "replaced": 0, "skipped": 0, "errors": 0},
           "mcp": {"added": 0, "replaced": 0, "kept": 0},
           "env": {"added": 0, "replaced": 0, "kept": 0, "errors": 0},
           "claude_json": {"projects_added": 0, "projects_merged": 0, "mcp_added": 0, "mcp_replaced": 0},
           "items": {"imported": 0, "replaced": 0, "skipped": 0},
           "sessions": {"files_added": 0, "identical": 0, "kept_local": 0, "sidecars": 0},
           "json_remapped": 0}

    def check():
        """Plus d'annulation une fois l'application commencée : un état à moitié
        appliqué sans bilan serait pire qu'un import mené à son terme."""

    # 1. Workspaces : fichiers d'abord, registre ensuite (un échec laisse le registre intact).
    new_entries: list[dict] = []
    by_old = {w["id"]: w for w in manifest["workspaces"]}
    for w in plan["workspaces"]:
        check()
        if w["action"] == "skip" or w["blocked"]:
            res["workspaces"]["skipped"] += 1
            continue
        staged = staging / "ws" / w["id"]
        target = Path(w["target_path"])
        try:
            if not staged.is_dir():
                raise OSError("dossier extrait introuvable")
            for rel in (".mcp.json", ".claude/settings.json", ".claude/settings.local.json"):
                f = staged.joinpath(*rel.split("/"))
                if f.is_file() and _remap_json_file(f, full):
                    res["json_remapped"] += 1
            if os.path.lexists(target):
                if _non_empty(target):
                    if w["action"] != "replace":
                        raise OSError("chemin cible occupé")
                    backup.stash(target, f"workspaces/{w['eff_id']}")
                    res["workspaces"]["replaced"] += 1
                else:
                    _remove_dir_or_link(target)     # dossier vide
            _move_tree(staged, target)
        except OSError as e:
            res["workspaces"]["errors"] += 1
            errors.append({"area": "workspace", "id": w["id"], "error": e.strerror or str(e)})
            continue
        res["workspaces"]["imported"] += 1
        entry = {k: v for k, v in by_old[w["id"]]["entry"].items()
                 if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,40}", str(k))
                 and (v is None or isinstance(v, (str, int, float, bool)))}
        entry["label"] = sanitize_bat(str(entry.get("label") or w["eff_id"])) or w["eff_id"]
        entry["id"] = w["eff_id"]
        if "path" in entry or _pkey(target) != _pkey(WORKSPACES_DIR / w["eff_id"]):
            entry["path"] = str(target)
        new_entries.append(entry)
        try:
            SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            write_launch_bat(w["eff_id"], entry["label"], str(target))
        except OSError:
            log.warning("migration: script de lancement non genere pour %s", w["eff_id"])
    if new_entries:
        with _MUTATION_LOCK:
            data = read_json_strict(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
            backup.copy_file(WORKSPACES_JSON, "workspaces.json")
            lst = data.setdefault("workspaces", [])
            for entry in new_entries:
                idx = next((i for i, x in enumerate(lst)
                            if isinstance(x, dict) and x.get("id") == entry["id"]), None)
                if idx is None:
                    lst.append(entry)
                else:
                    lst[idx] = entry
            write_json(WORKSPACES_JSON, data)
    rename_map = {w["id"]: w["eff_id"] for w in plan["workspaces"]
                  if w["eff_id"] != w["id"] and w["action"] == "rename"}

    # 2. Registre MCP
    try:
        check()
        mcp_src = {m["id"]: m for m in (meta.get("mcp_registry") or {}).get("mcps", [])
                   if isinstance(m, dict) and isinstance(m.get("id"), str)}
        todo = [m for m in plan["mcp"] if m["action"] in ("import", "replace")]
        res["mcp"]["kept"] = sum(1 for m in plan["mcp"] if m["action"] in ("skip", "none"))
        if todo:
            with _MUTATION_LOCK:
                data = read_json_strict(MCP_REGISTRY, {"version": "1.0", "mcps": []})
                backup.copy_file(MCP_REGISTRY, "mcp-registry.json")
                lst = data.setdefault("mcps", [])
                for m in todo:
                    entry, _n = full.remap_json(mcp_src[m["id"]])
                    if isinstance(entry.get("workspaces"), list):
                        entry["workspaces"] = [rename_map.get(x, x) for x in entry["workspaces"]]
                    idx = next((i for i, x in enumerate(lst)
                                if isinstance(x, dict) and x.get("id") == m["id"]), None)
                    if idx is None:
                        lst.append(entry)
                        res["mcp"]["added"] += 1
                    else:
                        old_ws = lst[idx].get("workspaces") if isinstance(lst[idx].get("workspaces"), list) else []
                        new_ws = entry.get("workspaces") if isinstance(entry.get("workspaces"), list) else []
                        entry["workspaces"] = old_ws + [x for x in new_ws if x not in old_ws]
                        lst[idx] = entry
                        res["mcp"]["replaced"] += 1
                write_json(MCP_REGISTRY, data)
    except Exception as e:  # noqa: BLE001 - une phase en échec ne masque pas le bilan
        errors.append({"area": "mcp", "id": "phase", "error": type(e).__name__})
        log.error("migration: phase mcp en echec (%s)", type(e).__name__)

    # 3. Variables d'environnement (via set_env_var : respecte le mode clair / chiffré)
    try:
        check()
        env_src = (meta.get("env") or {}).get("env") or {}
        todo_env = [e for e in plan["env"]["items"] if e["action"] in ("import", "replace")]
        res["env"]["kept"] = sum(1 for e in plan["env"]["items"] if e["action"] in ("keep", "none"))
        if todo_env:
            backup.copy_file(ENV_ENC_FILE, "env-local.enc")
            backup.copy_file(ENV_FILE, "env-local")
            for e in todo_env:
                status, _payload = set_env_var(e["key"], full.remap_text(env_src[e["key"]]))
                if status == 200:
                    res["env"]["added" if e["action"] == "import" else "replaced"] += 1
                else:
                    res["env"]["errors"] += 1
                    errors.append({"area": "env", "id": e["key"], "error": "écriture refusée"})
    except Exception as e:  # noqa: BLE001 - une phase en échec ne masque pas le bilan
        errors.append({"area": "env", "id": "phase", "error": type(e).__name__})
        log.error("migration: phase env en echec (%s)", type(e).__name__)

    # 4. ~/.claude.json (fusion ciblée, jamais d'écrasement du fichier)
    try:
        check()
        _apply_claude_json(plan, meta, full, backup, res, errors)
    except Exception as e:  # noqa: BLE001 - une phase en échec ne masque pas le bilan
        errors.append({"area": "claude_json", "id": "phase", "error": type(e).__name__})
        log.error("migration: phase claude_json en echec (%s)", type(e).__name__)

    # 5. Éléments
    try:
        for i in plan["items"]:
            check()
            if i["action"] == "skip":
                res["items"]["skipped"] += 1
                continue
            staged = staging.joinpath(*i["key"].split("/"))
            dest = Path(i["dest"])
            try:
                if not os.path.lexists(staged):
                    raise OSError("élément extrait introuvable")
                if staged.is_file() and (i["key"].endswith(("settings.json", "settings.local.json"))
                                         or i["key"].startswith("nebula/mcp-configs/") and i["key"].endswith(".json")):
                    if _remap_json_file(staged, full):
                        res["json_remapped"] += 1
                if os.path.lexists(dest):
                    backup.stash(dest, i["key"])
                    res["items"]["replaced"] += 1
                else:
                    res["items"]["imported"] += 1
                _move_tree(staged, dest)
            except OSError as e:
                errors.append({"area": "item", "id": i["key"], "error": e.strerror or str(e)})
    except Exception as e:  # noqa: BLE001 - une phase en échec ne masque pas le bilan
        errors.append({"area": "items", "id": "phase", "error": type(e).__name__})
        log.error("migration: phase items en echec (%s)", type(e).__name__)

    # 6. Sessions : fusion fichier par fichier, jamais d'écrasement
    try:
        for s in plan["sessions"]:
            check()
            staged = staging.joinpath(*s["key"].split("/"))
            if not staged.is_dir():
                continue
            md = merge_destination(s["key"], full)
            try:
                _merge_dir(staged, md[0], res["sessions"])
            except OSError as e:
                errors.append({"area": "sessions", "id": s["name"], "error": e.strerror or str(e)})
    except Exception as e:  # noqa: BLE001 - une phase en échec ne masque pas le bilan
        errors.append({"area": "sessions", "id": "phase", "error": type(e).__name__})
        log.error("migration: phase sessions en echec (%s)", type(e).__name__)

    res["backup_dir"] = str(backup.dir) if backup.used else None
    res["errors"] = errors[:100]
    res["next_steps"] = _next_steps(plan)
    return res


def _next_steps(plan: dict) -> list[str]:
    steps = []
    if plan["recreate"]:
        steps.append("Recréer les environnements non exportés (.venv, node_modules) des serveurs MCP "
                     "et des workspaces listés.")
    if plan["plugins_installed"]:
        steps.append("Réinstaller les plugins Claude Code (page Plugins).")
    steps.append("Vérifier les variables d'environnement dont la valeur est un chemin (Outils), "
                 "puis lancer « Synchroniser tout » pour régénérer les .mcp.json.")
    steps.append("Relancer Claude Code : ~/.claude.json et les skills sont relus au démarrage.")
    return steps


def _apply_claude_json(plan: dict, meta: dict, remap: PathRemapper, backup: _Backup,
                       res: dict, errors: list) -> None:
    cj_src = meta.get("claude_json") or {}
    src_projects = cj_src.get("projects") or {}
    src_root_mcp = cj_src.get("mcpServers") or {}
    if not src_projects and not src_root_mcp:
        return
    policy = plan["claude_json"]["policy"]
    if plan["claude_json"]["error"]:
        errors.append({"area": "claude_json", "id": "~/.claude.json", "error": "fichier illisible, non modifié"})
        return
    list_keys = ("allowedTools", "enabledMcpjsonServers", "disabledMcpjsonServers",
                 "disabledMcpServers", "mcpContextUris", "ignorePatterns")

    def merge_mcp(dst: dict, new: dict) -> None:
        for name, conf in new.items():
            if name not in dst:
                dst[name] = conf
                res["claude_json"]["mcp_added"] += 1
            elif dst[name] != conf and policy == "replace":
                dst[name] = conf
                res["claude_json"]["mcp_replaced"] += 1

    with _MUTATION_LOCK:
        data = read_json_strict(CLAUDE_JSON, {})
        if not isinstance(data, dict):
            errors.append({"area": "claude_json", "id": "~/.claude.json", "error": "contenu inattendu"})
            return
        snapshot = json.dumps(data, sort_keys=True)
        projects = data.setdefault("projects", {})
        if not isinstance(projects, dict):
            errors.append({"area": "claude_json", "id": "~/.claude.json", "error": "contenu inattendu"})
            return
        by_norm = {_norm_key(k): k for k in projects}
        for key, proj in src_projects.items():
            if not isinstance(key, str) or not isinstance(proj, dict):
                continue
            new_key = remap.remap_text(key)
            exist = by_norm.get(_norm_key(new_key))
            if exist is None:
                projects[new_key] = {}
                by_norm[_norm_key(new_key)] = new_key
                dst = projects[new_key]
                res["claude_json"]["projects_added"] += 1
            else:
                dst = projects[exist]
                if not isinstance(dst, dict):
                    continue
                res["claude_json"]["projects_merged"] += 1
            for k, v in remap.remap_json(proj)[0].items():
                if k == "mcpServers" and isinstance(v, dict):
                    merge_mcp(dst.setdefault("mcpServers", {}), v)
                elif k in list_keys and isinstance(v, list):
                    cur = dst.setdefault(k, [])
                    if isinstance(cur, list):
                        cur.extend(x for x in v if x not in cur)
                elif k not in dst or (policy == "replace" and dst.get(k) != v and v is not False):
                    dst[k] = v
        if isinstance(src_root_mcp, dict) and src_root_mcp:
            root = data.setdefault("mcpServers", {})
            if isinstance(root, dict):
                merge_mcp(root, remap.remap_json(src_root_mcp)[0])
        if json.dumps(data, sort_keys=True) == snapshot:
            return                  # rien de nouveau : fichier ni sauvegarde touchés
        backup.copy_file(CLAUDE_JSON, "claude.json")
        write_json(CLAUDE_JSON, data)


def _merge_dir(staged: Path, dest: Path, stats: dict) -> None:
    """Fusionne `staged` dans `dest` sans écraser : fichier absent -> ajouté,
    identique -> ignoré, différent -> le local est gardé (version importée
    rangée à côté sous `.migration-<ts>` hors transcripts `.jsonl`)."""
    if not os.path.lexists(dest):
        _move_tree(staged, dest)
        n = sum(1 for _ in dest.rglob("*") if _.is_file())
        stats["files_added"] += n
        return
    stamp = int(time.time())
    for root, _dirs, files in os.walk(staged):
        rel_root = Path(root).relative_to(staged)
        for name in files:
            s = Path(root) / name
            d = dest / rel_root / name
            if not os.path.lexists(d):
                d.parent.mkdir(parents=True, exist_ok=True)
                _move_tree(s, d)
                stats["files_added"] += 1
            elif filecmp.cmp(s, d, shallow=False):
                stats["identical"] += 1
            else:
                stats["kept_local"] += 1
                if not name.endswith(".jsonl"):
                    side = d.with_name(f"{d.name}.migration-{stamp}")
                    if not os.path.lexists(side):
                        _move_tree(s, side)
                        stats["sidecars"] += 1
