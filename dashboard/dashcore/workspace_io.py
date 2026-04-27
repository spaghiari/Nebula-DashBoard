"""I/O et chemins liés aux workspaces : résolution de path, stats, lancement.

Centralise la traduction id workspace → chemin disque (`resolve_ws_dir`),
la génération du `.bat` de lancement, le calcul des stats de session,
et la cohérence registre vs fichiers `.mcp.json` (`sanity_check`).
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from dashcore.config import (
    BAT_UNSAFE, CLAUDE_PROJECTS, DASHBOARD_DIR, MCP_REGISTRY, SCRIPTS_DIR,
    WORKSPACES_DIR, WORKSPACES_JSON, log,
)
from dashcore.env_local import load_env_local
from dashcore.helpers import read_json


_PRICING_FILE = DASHBOARD_DIR / "data" / "pricing.json"
_PRICING_CACHE: dict | None = None
_PRICING_MTIME: float = 0.0


def _load_pricing() -> dict:
    """Charge la table de prix avec cache (invalidé si mtime change)."""
    global _PRICING_CACHE, _PRICING_MTIME
    try:
        m = _PRICING_FILE.stat().st_mtime
    except OSError:
        return _DEFAULT_PRICING
    if _PRICING_CACHE is None or m != _PRICING_MTIME:
        try:
            _PRICING_CACHE = json.loads(_PRICING_FILE.read_text(encoding="utf-8"))
            _PRICING_MTIME = m
        except (OSError, json.JSONDecodeError) as e:
            log.warning("pricing.json illisible : %s — utilisation des tarifs par défaut", e)
            return _DEFAULT_PRICING
    return _PRICING_CACHE


_DEFAULT_PRICING = {
    "models": [
        {"match": "claude-opus-4",   "label": "Opus 4.x",   "input": 15.0, "output": 75.0, "cache_create": 18.75, "cache_read": 1.50},
        {"match": "claude-sonnet-4", "label": "Sonnet 4.x", "input":  3.0, "output": 15.0, "cache_create":  3.75, "cache_read": 0.30},
        {"match": "claude-haiku-4",  "label": "Haiku 4.x",  "input":  1.0, "output":  5.0, "cache_create":  1.25, "cache_read": 0.10},
    ],
    "fallback": {"label": "Inconnu (tarif Sonnet)", "input": 3.0, "output": 15.0, "cache_create": 3.75, "cache_read": 0.30},
}


def _resolve_model(model_id: str | None, pricing: dict) -> dict:
    """Trouve l'entrée tarif via match (préfixe le plus long gagne)."""
    if model_id:
        candidates = sorted(pricing.get("models", []), key=lambda m: -len(m.get("match", "")))
        for entry in candidates:
            if model_id.startswith(entry.get("match", "")):
                return entry
    return pricing.get("fallback") or _DEFAULT_PRICING["fallback"]


def _entry_cost(usage: dict, model_id: str | None, pricing: dict) -> tuple[float, str]:
    """Coût d'une entry assistant (toutes dimensions). Retourne (cost_usd, model_label)."""
    rate = _resolve_model(model_id, pricing)
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    cc = int(usage.get("cache_creation_input_tokens") or 0)
    cr = int(usage.get("cache_read_input_tokens") or 0)
    cost = (
        inp / 1_000_000 * float(rate.get("input", 0))
        + out / 1_000_000 * float(rate.get("output", 0))
        + cc / 1_000_000 * float(rate.get("cache_create", 0))
        + cr / 1_000_000 * float(rate.get("cache_read", 0))
    )
    return cost, rate.get("label") or model_id or "Inconnu"


def list_workspaces() -> list[dict]:
    data = read_json(WORKSPACES_JSON, {"version": "1.0", "workspaces": []})
    return data.get("workspaces", [])


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

    Claude encode le chemin en remplaçant `:` et `\\` par `-`. On encode
    directement le path cible plutôt que d'essayer de décoder les noms
    de dossier (décodage ambigu dès qu'un segment contient un `-`).
    """
    if not CLAUDE_PROJECTS.exists():
        return None
    target = str(path.resolve())
    encoded = target.replace(":", "-").replace("\\", "-").replace("/", "-").replace(" ", "-")
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
    if w and w.get("path"):
        return Path(w["path"])
    return WORKSPACES_DIR / ws_id


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
        f"claude\n",
        encoding="utf-8",
    )
    return bat_path


def launch_script(bat_name: str) -> tuple[int, dict]:
    bat = SCRIPTS_DIR / bat_name
    if not bat.exists():
        return 404, {"ok": False, "error": f"Script introuvable : {bat}"}
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(bat)],
            cwd=str(SCRIPTS_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            shell=False,
        )
        return 200, {"ok": True, "message": f"Lancé : {bat.name}"}
    except OSError as e:
        return 500, {"ok": False, "error": f"Erreur : {e}"}


def workspace_stats(ws: dict) -> dict:
    pdir = project_dir_for_path(Path(ws["path"]))
    if not pdir:
        return {
            "sessions": 0, "messages": 0, "last": None,
            "input_tokens": 0, "output_tokens": 0,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "cost_usd": 0.0, "cost_by_model": {}, "cache_savings_usd": 0.0,
        }
    pricing = _load_pricing()
    sessions = 0
    messages = 0
    last_mtime = 0.0
    inp = out = cc = cr = 0
    cost_total = 0.0
    cache_savings = 0.0
    cost_by_model: dict[str, dict] = {}

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
                    msg = entry.get("message") or {}
                    usage = msg.get("usage") or entry.get("usage") or {}
                    if not usage:
                        continue
                    e_inp = int(usage.get("input_tokens") or 0)
                    e_out = int(usage.get("output_tokens") or 0)
                    e_cc = int(usage.get("cache_creation_input_tokens") or 0)
                    e_cr = int(usage.get("cache_read_input_tokens") or 0)
                    inp += e_inp; out += e_out; cc += e_cc; cr += e_cr

                    model_id = msg.get("model") or entry.get("model")
                    rate = _resolve_model(model_id, pricing)
                    label = rate.get("label") or model_id or "Inconnu"
                    cost = (
                        e_inp / 1_000_000 * float(rate.get("input", 0))
                        + e_out / 1_000_000 * float(rate.get("output", 0))
                        + e_cc / 1_000_000 * float(rate.get("cache_create", 0))
                        + e_cr / 1_000_000 * float(rate.get("cache_read", 0))
                    )
                    cost_total += cost
                    bucket = cost_by_model.setdefault(label, {
                        "label": label, "cost_usd": 0.0,
                        "input_tokens": 0, "output_tokens": 0,
                        "cache_creation_tokens": 0, "cache_read_tokens": 0,
                    })
                    bucket["cost_usd"] += cost
                    bucket["input_tokens"] += e_inp
                    bucket["output_tokens"] += e_out
                    bucket["cache_creation_tokens"] += e_cc
                    bucket["cache_read_tokens"] += e_cr
                    # Économie cache = (ce que les cache_read_tokens auraient coûté en input plein) - (ce qu'ils ont coûté en cache_read)
                    if e_cr:
                        cache_savings += e_cr / 1_000_000 * (float(rate.get("input", 0)) - float(rate.get("cache_read", 0)))
        except OSError as e:
            log.warning("workspace_stats: skip %s (%s)", jsonl, e)
            continue

    # Round + sort by_model
    by_model = []
    for v in cost_by_model.values():
        v["cost_usd"] = round(v["cost_usd"], 4)
        by_model.append(v)
    by_model.sort(key=lambda x: -x["cost_usd"])

    last_iso = dt.datetime.fromtimestamp(last_mtime).isoformat(timespec="seconds") if last_mtime else None
    return {
        "sessions": sessions,
        "messages": messages,
        "last": last_iso,
        "input_tokens": inp,
        "output_tokens": out,
        "cache_creation_tokens": cc,
        "cache_read_tokens": cr,
        "cost_usd": round(cost_total, 4),
        "cost_by_model": by_model,
        "cache_savings_usd": round(cache_savings, 4),
    }


def all_stats() -> dict:
    out = {}
    for w in list_workspaces():
        out[w["id"]] = workspace_stats(w)
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
