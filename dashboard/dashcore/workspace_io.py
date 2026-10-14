"""I/O et chemins liés aux workspaces : résolution de path, stats, lancement.

Centralise la traduction id workspace → chemin disque (`resolve_ws_dir`),
la génération du `.bat` de lancement, le calcul des stats de session,
et la cohérence registre vs fichiers `.mcp.json` (`sanity_check`).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

from dashcore.config import (
    BAT_UNSAFE, CLAUDE_PROJECTS, MCP_REGISTRY, SCRIPTS_DIR,
    WORKSPACES_DIR, WORKSPACES_JSON, log, IS_WINDOWS, WINDOWS_ONLY_MSG,
)
from dashcore.env_local import load_env_local
from dashcore.helpers import read_json


def list_workspaces() -> list[dict]:
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    return data.get("workspaces", [])


def list_workspaces_with_status() -> dict:
    """Comme le registre brut, mais chaque workspace est annoté de `path_exists`.

    `path_exists` = le dossier du workspace existe-t-il sur disque (1 `is_dir`
    par workspace, peu coûteux). Surface la donnée pour le badge « chemin KO »
    de la home card (lot E item 1b) sans appel réseau supplémentaire côté front.
    Le chemin réel passe par `resolve_ws_dir` (point d'accès unique disque).
    """
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    out = dict(data)
    annotated = []
    for w in data.get("workspaces", []):
        w2 = dict(w)
        ws_id = w.get("id")
        try:
            # Même résolution que resolve_ws_dir, sans relire le registre
            # pour chaque workspace (il vient d'être lu une fois ci-dessus).
            w2["path_exists"] = bool(ws_id) and _ws_dir_from_entry(w).is_dir()
        except OSError:
            w2["path_exists"] = False
        annotated.append(w2)
    out["workspaces"] = annotated
    return out


def ws_mcp_info(ws_dir: Path) -> dict:
    """Serveurs MCP présents dans `<ws_dir>/.mcp.json` : {active, has_file}.

    Implémentation unique partagée par `GET /api/workspaces/<id>/mcps`
    (`api_mcps.workspace_mcp_status`) et l'endpoint agrégé `/api/overview`.
    """
    mcp_file = ws_dir / ".mcp.json"
    data = read_json(mcp_file, None)
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    active = list(servers.keys()) if isinstance(servers, dict) else []
    return {"active": active, "has_file": mcp_file.exists()}


def workspaces_overview() -> dict:
    """Données de démarrage du front en UNE requête (`GET /api/overview`).

    = `list_workspaces_with_status()` + `ws_mcps` ({ws_id: {active,
    has_file}}), qui demandait auparavant un `GET /api/workspaces/<id>/mcps`
    par workspace dans `loadAll` (js/router.js). Le registre des workspaces
    est lu une seule fois. Les routes unitaires restent disponibles.
    """
    out = list_workspaces_with_status()
    ws_mcps: dict[str, dict] = {}
    for w in out.get("workspaces", []):
        ws_id = w.get("id")
        if not ws_id or ws_id in ws_mcps:
            continue
        try:
            ws_mcps[ws_id] = ws_mcp_info(_ws_dir_from_entry(w))
        except OSError:
            ws_mcps[ws_id] = {"active": [], "has_file": False}
    out["ws_mcps"] = ws_mcps
    out["overlays_active"] = overlays_active_map(out.get("workspaces", []))
    return out


def overlays_active_map(workspaces: list[dict]) -> dict[str, list[str]]:
    """{ws_id: [overlay_id actif, ...]} pour les workspaces DÉJÀ lus.

    Alimente l'indicateur « Auto-amélioration » de l'accueil et de l'en-tête
    workspace sans une requête par workspace côté front. Coût : la liste des
    overlays est calculée une fois, puis un `exists()` (signature_file) par
    couple workspace x overlay. Les workspaces sans overlay actif sont omis.
    """
    # Import différé : api_overlays importe helpers (ordre d'import imposé,
    # cf. performance.md), on évite tout cycle au chargement du module.
    from dashcore.api_overlays import list_overlays, overlay_is_active
    try:
        overlays = list_overlays()
    except OSError:
        return {}
    if not overlays:
        return {}
    out: dict[str, list[str]] = {}
    for w in workspaces:
        ws_id = w.get("id")
        if not ws_id or ws_id in out or w.get("path_exists") is False:
            continue
        try:
            ws_dir = _ws_dir_from_entry(w)
            active = [ov["id"] for ov in overlays if overlay_is_active(ws_dir, ov)]
        except OSError:
            continue
        if active:
            out[ws_id] = active
    return out


def cleanup_orphan_bats() -> dict:
    """Retire les .bat qui ne correspondent à aucun workspace du registre."""
    ws_ids = {w["id"] for w in list_workspaces()}
    removed = []
    for bat in SCRIPTS_DIR.glob("launch-*.bat"):
        wid = bat.stem[len("launch-"):]
        if wid not in ws_ids:
            bat.unlink()
            removed.append(bat.name)
    return {"removed": removed}


def project_dir_for_path(path: Path) -> Path | None:
    """Trouve le dossier ~/.claude/projects/<encodé> qui correspond à `path`.

    Claude encode le chemin en remplaçant tout caractère non alphanumérique
    par `-` (`C:\\foo\\bar.baz` -> `C--foo-bar-baz`). On encode
    directement le path cible plutôt que d'essayer de décoder les noms
    de dossier (décodage ambigu dès qu'un segment contient un `-`).
    """
    if not CLAUDE_PROJECTS.exists():
        return None
    target = str(path.resolve())
    # Même règle que Claude Code : TOUT caractère non alphanumérique ASCII
    # devient `-` (`.`, `_`, accents, parenthèses... inclus, pas seulement
    # `:` `\` `/` espace). Implémentation unique du projet.
    encoded = re.sub(r"[^A-Za-z0-9]", "-", target)
    candidate = CLAUDE_PROJECTS / encoded
    if candidate.is_dir():
        return candidate
    enc_lower = encoded.lower()
    for d in CLAUDE_PROJECTS.iterdir():
        if d.is_dir() and d.name.lower() == enc_lower:
            return d
    return None


def resolve_ws_dir(ws_id: str) -> Path:
    """Retourne le chemin disque réel d'un workspace.

    Cherche d'abord le path dans workspaces.json (workspaces importés peuvent
    pointer hors de WORKSPACES_DIR). Fallback : WORKSPACES_DIR/ws_id.
    Point d'accès UNIQUE — toute fonction qui touche au disque d'un workspace
    DOIT passer par ici, sinon les workspaces importés sont cassés.
    """
    data = read_json(WORKSPACES_JSON, {"workspaces": []})
    w = next((x for x in data.get("workspaces", []) if x.get("id") == ws_id), None)
    if w:
        return _ws_dir_from_entry(w)
    return WORKSPACES_DIR / ws_id


def _ws_dir_from_entry(w: dict) -> Path:
    """Chemin disque d'une entrée de registre DÉJÀ lue (même règle que
    resolve_ws_dir). Pour les boucles sur tous les workspaces : évite de
    relire workspaces.json une fois par workspace."""
    if w.get("path"):
        return Path(w["path"])
    return WORKSPACES_DIR / str(w.get("id") or "")


def validate_ws_path(path: str) -> tuple[bool, str]:
    """Valide un chemin saisi par l'utilisateur (import / update workspace).

    Refuse : vide, relatif, UNC, caractères incompatibles avec un .bat.
    """
    p = (path or "").strip()
    if not p:
        return False, "chemin vide"
    if p.startswith("\\\\"):
        return False, "chemins UNC non supportés"
    pp = Path(p)
    if not pp.is_absolute():
        return False, "chemin absolu requis"
    if BAT_UNSAFE.search(p):
        return False, "caractères interdits dans le chemin (& | < > ^ \" %)"
    return True, ""


def write_launch_bat(ws_id: str, label: str, path: str) -> Path:
    """Écrit le script de lancement Claude Code pour un workspace."""
    bat_path = SCRIPTS_DIR / f"launch-{ws_id}.bat"
    safe_label = (label or ws_id).replace("\n", " ").replace("\r", " ")
    bat_path.write_text(
        f"@echo off\n"
        f"echo.\n"
        f"echo  +======================================+\n"
        f"echo  ^|   Claude Code -- {safe_label}\n"
        f"echo  +======================================+\n"
        f"echo.\n"
        f'cd /d "{path}"\n'
        # Auto-bootstrap : si le CLAUDE.md de l'overlay claude-self-improving
        # est encore "Non initialise", on demarre Claude avec le prompt de
        # bootstrap (session INTERACTIVE : le prompt positionnel est traite en
        # 1er message puis le REPL reste ouvert). Une fois le projet
        # bootstrappe, Claude remplace "Non initialise" -> les lancements
        # suivants sont normaux. Marqueur ASCII (sans accent) pour un findstr
        # fiable sur un CLAUDE.md encode en UTF-8.
        f'findstr /C:"Non initialis" "CLAUDE.md" >nul 2>&1\n'
        f"if errorlevel 1 (\n"
        f"    claude\n"
        f") else (\n"
        f"    echo  Projet non initialise -- lancement du bootstrap...\n"
        f'    claude "Bootstrap ce projet"\n'
        f")\n",
        encoding="utf-8",
    )
    return bat_path


def launch_script(bat_name: str, *, ws_id: str | None = None, ws_label: str | None = None,
                  ws_path: str | None = None) -> tuple[int, dict]:
    """Lance un .bat dans une nouvelle console.

    Si ws_id est fourni, enregistre le PID du cmd dans active_sessions
    pour permettre un Stop ultérieur depuis Nebula. cmd /k garde la
    fenêtre ouverte, ce qui maintient Popen.pid valide tant que la
    session tourne.

    Si ws_path est fourni, on vérifie son existence AVANT de spawner le
    .bat : le `cd /d "path"` du script échoue en silence dans une console
    neuve, ce qui produisait un toast « Lancé » mensonger sur un dossier
    inexistant. On préfère une erreur explicite.
    """
    if not IS_WINDOWS:
        # `cmd /k` + CREATE_NEW_CONSOLE : Windows uniquement (501 explicite
        # plutôt qu'un FileNotFoundError opaque ou un faux « Lancé »).
        return 501, {"ok": False, "error": WINDOWS_ONLY_MSG}
    bat = SCRIPTS_DIR / bat_name
    if not bat.exists():
        return 404, {"ok": False, "error": f"Script introuvable : {bat}"}
    if ws_path is not None and not Path(ws_path).is_dir():
        return 404, {"ok": False, "error": (
            f"Dossier introuvable : {ws_path} — corrige le chemin "
            f"(Modifier le workspace) ou recrée le dossier"
        )}
    try:
        proc = subprocess.Popen(
            ["cmd", "/k", "call", str(bat)],
            cwd=str(SCRIPTS_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            shell=False,
        )
        if ws_id:
            try:
                from dashcore.active_sessions import register as _register
                _register(ws_id, proc.pid, label=ws_label or ws_id)
            except (ImportError, OSError):
                pass  # best-effort, le launch reste OK même si le register rate
        return 200, {"ok": True, "pid": proc.pid, "message": f"Lancé : {bat.name}"}
    except OSError as e:
        return 500, {"ok": False, "error": f"Erreur : {e}"}


# Cache des compteurs par fichier de session `.jsonl`.
# Clé : chemin absolu ; valeur : ((st_mtime_ns, st_size), compteurs).
# Invalidation naturelle : si mtime ou taille change (session en cours qui
# s'allonge, fichier réécrit), la clé ne correspond plus et le fichier est
# relu. Un fichier en cours d'écriture pendant la lecture est relu au tour
# suivant (sa taille aura bougé). Purge des fichiers disparus dans all_stats.
_STATS_CACHE: dict[str, tuple[tuple[int, int], tuple]] = {}
_STATS_CACHE_LOCK = threading.Lock()


def _scan_session_file(jsonl: Path) -> tuple:
    """Une passe sur un .jsonl : (messages, input, output, cache_creation,
    cache_read, first_user_message|None).

    Partagé par les stats (`workspace_stats`) et la liste des sessions d'un
    workspace (`api_workspaces.list_sessions_for_workspace`), mêmes règles de
    comptage que les deux boucles d'origine. Lève OSError si illisible.
    """
    messages = inp = out = cc = cr = 0
    first_msg = None
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
                content = (entry.get("message") or {}).get("content")
                if isinstance(content, str):
                    first_msg = content[:200]
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            first_msg = c.get("text", "")[:200]
                            break
            if entry.get("type") in ("user", "assistant"):
                messages += 1
            msg = entry.get("message") or {}
            usage = msg.get("usage") or entry.get("usage") or {}
            if not usage:
                continue
            inp += int(usage.get("input_tokens") or 0)
            out += int(usage.get("output_tokens") or 0)
            cc += int(usage.get("cache_creation_input_tokens") or 0)
            cr += int(usage.get("cache_read_input_tokens") or 0)
    return messages, inp, out, cc, cr, first_msg


def session_file_counts(jsonl: Path, st) -> tuple:
    """Résultat de `_scan_session_file` via le cache (clé mtime_ns + taille).

    `st` = résultat de `jsonl.stat()` déjà fait par l'appelant.
    """
    key = str(jsonl)
    sig = (st.st_mtime_ns, st.st_size)
    with _STATS_CACHE_LOCK:
        hit = _STATS_CACHE.get(key)
    if hit and hit[0] == sig:
        return hit[1]
    # Lecture hors verrou : deux requêtes concurrentes peuvent relire le même
    # fichier (résultat identique), mais aucune n'attend l'autre.
    counts = _scan_session_file(jsonl)
    with _STATS_CACHE_LOCK:
        _STATS_CACHE[key] = (sig, counts)
    return counts


def _prune_stats_cache(seen: set[str]) -> None:
    """Retire du cache les fichiers non vus lors d'un balayage complet."""
    with _STATS_CACHE_LOCK:
        for key in [k for k in _STATS_CACHE if k not in seen]:
            del _STATS_CACHE[key]


def workspace_stats(ws: dict, _seen: set[str] | None = None) -> dict:
    pdir = project_dir_for_path(Path(ws["path"]))
    if not pdir:
        return {
            "sessions": 0, "messages": 0, "last": None,
            "input_tokens": 0, "output_tokens": 0,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
        }
    sessions = 0
    messages = 0
    last_mtime = 0.0
    inp = out = cc = cr = 0

    for jsonl in pdir.glob("*.jsonl"):
        sessions += 1
        try:
            st = jsonl.stat()
            mtime = st.st_mtime
            if mtime > last_mtime:
                last_mtime = mtime
            if _seen is not None:
                _seen.add(str(jsonl))
            m, i, o, c1, c2, _first = session_file_counts(jsonl, st)
            messages += m
            inp += i
            out += o
            cc += c1
            cr += c2
        except OSError as e:
            log.warning("workspace_stats: skip %s (%s)", jsonl, e)
            continue

    last_iso = dt.datetime.fromtimestamp(last_mtime).isoformat(timespec="seconds") if last_mtime else None
    return {
        "sessions": sessions,
        "messages": messages,
        "last": last_iso,
        "input_tokens": inp,
        "output_tokens": out,
        "cache_creation_tokens": cc,
        "cache_read_tokens": cr,
    }


def all_stats() -> dict:
    out = {}
    seen: set[str] = set()
    for w in list_workspaces():
        out[w["id"]] = workspace_stats(w, seen)
    # Balayage complet : on peut purger les entrées de fichiers disparus.
    _prune_stats_cache(seen)
    return out


def sanity_check() -> dict:
    """Compare registre ↔ .mcp.json effectivement écrits dans chaque workspace."""
    # Import tardif pour éviter le cycle workspace_io ↔ api_mcps
    from dashcore.api_mcps import build_mcp_server_entry, mcp_applies_to

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

        missing_sync = expected_ids - actual_ids
        stale = actual_ids - expected_ids
        if missing_sync or stale:
            findings.append({
                "workspace": ws_id,
                "missing_sync": sorted(missing_sync),
                "stale": sorted(stale),
            })

    missing_env = {}
    for m in registry:
        _, miss = build_mcp_server_entry(m, env_local)
        if miss:
            missing_env[m["id"]] = miss

    return {"findings": findings, "missing_env": missing_env}
