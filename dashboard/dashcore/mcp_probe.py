"""Dernier verdict de « Diagnostiquer » par MCP (pastille « vérifié »).

Le statut calculé d'un MCP (`compute_mcp_status`) ne dit que « config
complète » : rien ne prouve que le serveur démarre. Le diagnostic, lui,
lance réellement le process (stdio) ou sonde l'URL (http/sse), mais son
résultat n'était pas retenu. Ce module le mémorise.

Règles :
- Écrit UNIQUEMENT à la fin d'un diagnostic déclenché par l'utilisateur
  (`diagnose_mcp`) : jamais de sonde automatique (elle lancerait N process).
- Fichier runtime dans le dossier de données (`NEBULA_DATA_DIR` respecté,
  lu à l'appel), non versionné, écriture atomique (`write_json`).
- Un verdict n'a de valeur que pour la config testée : on retient une
  signature des champs techniques (transport, commande, args, env, cwd,
  url, headers). Un MCP modifié depuis le test invalide son verdict.
- Un verdict vieillit : au-delà de `PROBE_FRESH_DAYS` il n'est plus affiché
  comme un état, seulement comme une information (« dernier test il y a... »).

Limite assumée : la signature porte sur le registre, pas sur les valeurs de
`.env.local` (on ne recopie aucune empreinte de secret du coffre dans un
fichier en clair). Un token changé dans `.env.local` n'invalide donc pas le
verdict ; la fenêtre de fraîcheur borne ce cas.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from dashcore import config as _config
from dashcore.config import log
from dashcore.helpers import CorruptJsonError, read_json, read_json_strict, write_json

PROBE_STATE_NAME = "mcp_probe_state.json"
# Fenêtre de fraîcheur : 7 jours. Un MCP casse surtout par un token expiré,
# un service arrêté ou un package mis à jour ; au-delà d'une semaine sans
# nouveau test, « vérifié » deviendrait une affirmation non étayée. En deçà
# (24 h), la pastille ne serait presque jamais verte pour un usage normal
# (on ne diagnostique pas un MCP qui marche tous les jours).
PROBE_FRESH_DAYS = 7
PROBE_FRESH_S = PROBE_FRESH_DAYS * 86400
# Tolérance d'horloge : un horodatage dans le futur au-delà de ce délai est
# traité comme expiré (horloge système corrigée, fichier copié d'un autre poste).
_CLOCK_SKEW_S = 300
VERDICTS = ("ok", "warn", "err")
SIG_FIELDS = ("transport", "command", "args", "env", "cwd", "url", "headers")
_LOCK = threading.Lock()


def probe_state_path() -> Path:
    return _config.DATA_DIR / PROBE_STATE_NAME


def _norm(value):
    """Forme canonique d'un champ : vide -> None, chaînes nettoyées."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (list, tuple)):
        out = [_norm(v) for v in value]
        return out or None
    if isinstance(value, dict):
        out = {str(k): _norm(v) for k, v in value.items()}
        return out or None
    return value


def mcp_signature(mcp: dict) -> str:
    """Empreinte des champs techniques d'un MCP (16 hex, sha256 tronqué)."""
    payload = {k: _norm(mcp.get(k)) for k in SIG_FIELDS}
    if not payload["transport"]:
        payload["transport"] = "stdio"
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _clean_entries(data) -> dict:
    entries = data.get("mcps") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        return {}
    out = {}
    for mid, e in entries.items():
        if (isinstance(e, dict) and e.get("verdict") in VERDICTS
                and isinstance(e.get("at"), (int, float)) and isinstance(e.get("sig"), str)):
            out[str(mid)] = {"verdict": e["verdict"], "at": int(e["at"]), "sig": e["sig"]}
    return out


def read_probe_entries() -> dict:
    """Entrées valides {id: {verdict, at, sig}} ; fichier absent ou illisible -> {}."""
    return _clean_entries(read_json(probe_state_path(), {}))


def record_probe(mcp: dict, verdict: str, known_ids=None, now: float | None = None) -> dict:
    """Mémorise le verdict d'un diagnostic terminé. Renvoie l'entrée écrite.

    `known_ids` (ids du registre) : élague les entrées des MCPs supprimés ou
    renommés. Un fichier corrompu est repris de zéro (`write_json` en garde
    une copie `.corrupt-<ts>`) : ce n'est qu'une aide à la lecture.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict inconnu : {verdict!r}")
    mid = str(mcp.get("id") or "")
    if not mid:
        raise ValueError("MCP sans id")
    entry = {"verdict": verdict, "at": int(now if now is not None else time.time()),
             "sig": mcp_signature(mcp)}
    path = probe_state_path()
    with _LOCK:
        try:
            raw = read_json_strict(path, {})
        except CorruptJsonError:
            log.warning("État des diagnostics MCP illisible, repris de zéro : %s", path)
            raw = {}
        entries = _clean_entries(raw)
        if known_ids is not None:
            keep = set(known_ids) | {mid}
            entries = {k: v for k, v in entries.items() if k in keep}
        entries[mid] = entry
        write_json(path, {"version": 1, "mcps": entries})
    return entry


def probe_summary(mcp: dict, entry: dict | None, now: float | None = None) -> dict | None:
    """Vue d'un verdict mémorisé pour l'API (None si aucun).

    `state` : "ok" | "warn" | "err" (verdict valable), "changed" (MCP modifié
    depuis le test), "expired" (plus vieux que la fenêtre de fraîcheur).
    """
    if not entry:
        return None
    now = time.time() if now is None else now
    age = now - entry["at"]
    if entry["sig"] != mcp_signature(mcp):
        state = "changed"
    elif age > PROBE_FRESH_S or age < -_CLOCK_SKEW_S:
        state = "expired"
    else:
        state = entry["verdict"]
    return {"verdict": entry["verdict"], "at": entry["at"], "state": state,
            "fresh_days": PROBE_FRESH_DAYS}
