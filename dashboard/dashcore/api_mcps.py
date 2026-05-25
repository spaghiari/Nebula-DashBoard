"""Module extrait de server.py — ne pas éditer le script _split.py."""
from __future__ import annotations

import glob
import hashlib
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
import webbrowser
import zipfile
from pathlib import Path

from dashcore.config import (
    ROOT, USER_HOME, CLAUDE_HOME, CLAUDE_JSON, CLAUDE_SETTINGS, CLAUDE_PROJECTS,
    BACKUPS_DIR, JOURNAL_FILE, TEMPLATES_DIR, DASHBOARD_DIR, WORKSPACES_DIR,
    SCRIPTS_DIR, SNIPPETS_DIR, WORKSPACES_JSON, MCP_REGISTRY, ENV_FILE, LOGS_DIR,
    TEXT_EXTENSIONS, SAFE_ID, SAFE_PLUGIN_SPEC, ENV_VAR_PATTERN, BAT_UNSAFE,
    PATH_UNSAFE, STATIC_TYPES, ENV_KEY_RE, _MUTATION_LOCK, log,
    ALLOWED_TRANSPORTS, ALLOWED_STATUS,
)


from dashcore.helpers import (
    load_env_local, read_json, resolve_cli, resolve_ws_dir, safe_id,
    strip_invisible, substitute_env, write_json,
)
from dashcore.workspace_io import list_workspaces


def mcp_live_check(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    w = next((x for x in list_workspaces() if x["id"] == ws_id), None)
    if not w:
        return 404, {"error": "workspace absent"}
    try:
        r = subprocess.run(
            [resolve_cli("claude"), "mcp", "list"],
            cwd=w["path"], capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        output = (r.stdout or "") + (r.stderr or "")
        # Parsing basique : lignes avec "name: ..."
        seen = set()
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # formats possibles : "name (transport)", "- name", "name: ..."
            m = re.match(r"^[-*]?\s*([a-zA-Z0-9_-]+)\s*[:(]", line)
            if m:
                seen.add(m.group(1))
            elif re.match(r"^[a-zA-Z0-9_-]+$", line):
                seen.add(line)

        mcp_file = Path(w["path"]) / ".mcp.json"
        expected = set()
        if mcp_file.exists():
            data = read_json(mcp_file, {})
            expected = set((data.get("mcpServers") or {}).keys())

        return 200, {
            "cli_output": output,
            "seen_by_claude": sorted(seen),
            "expected_from_mcp_json": sorted(expected),
            "only_in_claude": sorted(seen - expected),
            "only_in_file": sorted(expected - seen),
        }
    except FileNotFoundError:
        return 200, {"error": "Claude Code CLI introuvable dans le PATH"}
    except subprocess.TimeoutExpired:
        return 200, {"error": "claude mcp list a timeout (10s)"}
    except Exception as e:
        return 500, {"error": str(e)}


# ── Diagnostic actionnable d'un MCP (Lot C audit UX 2026-05-25) ──────────────
# Le principe : passer de « connecté / pas connecté » à « POURQUOI + COMMENT
# réparer ». Chaque check renvoie {label, status, detail, fix} avec un mapping
# symptôme -> cause précis (le coeur de la valeur : Forbidden=token, env
# manquant=.env.local, commande absente=PATH...).

# Détecte un caractère alphanumérique collé juste après le `}` d'un ${VAR}
# (le « Q » wikijs). Miroir back de detectStuckCharAfterVar (js/lint.js).
_STUCK_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}([A-Za-z0-9])")
_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _mcp_interpolable_strings(mcp: dict) -> list[str]:
    """Champs d'un MCP susceptibles de contenir des ${VAR} (miroir du front)."""
    out: list[str] = []
    for v in (mcp.get("command"), mcp.get("url"), mcp.get("cwd")):
        if v:
            out.append(str(v))
    for a in (mcp.get("args") or []):
        if a:
            out.append(str(a))
    for v in (mcp.get("env") or {}).values():
        if v:
            out.append(str(v))
    for v in (mcp.get("headers") or {}).values():
        if v:
            out.append(str(v))
    return out


def _stdio_executable(mcp: dict) -> str:
    """1er token de la commande stdio (npx / uvx / node / python...)."""
    cmd = (mcp.get("command") or "").strip()
    if not cmd:
        return ""
    parts = shlex.split(cmd, posix=False)
    return parts[0] if parts else cmd


def diagnose_mcp(mcp_id: str) -> tuple[int, dict]:
    """Diagnostic actionnable d'un MCP : agrège des checks structurés.

    Retourne {verdict: "ok"|"warn"|"err", checks: [{label, status, detail, fix}]}.
    PÉRIMÈTRE = diagnostic (lecture + verdict). N'effectue aucune mutation.
    Aucun secret en clair n'est renvoyé : on ne manipule que les NOMS de vars
    et on ne renvoie jamais une valeur de header/env résolue.
    """
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
    registry = read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", [])
    mcp = next((m for m in registry if m.get("id") == mcp_id), None)
    if mcp is None:
        return 404, {"error": "MCP absent du registre"}

    transport = mcp.get("transport", "stdio")
    env_local = load_env_local()
    checks: list[dict] = []

    # ── 1a. Résolution des ${VAR} ────────────────────────────────────────────
    referenced: list[str] = []
    seen_vars: set[str] = set()
    for s in _mcp_interpolable_strings(mcp):
        for v in _VAR_RE.findall(s):
            if v not in seen_vars:
                seen_vars.add(v)
                referenced.append(v)
    missing_vars = [
        v for v in referenced
        if v not in env_local and v not in os.environ
    ]
    if not referenced:
        checks.append({
            "label": "Résolution des variables ${VAR}",
            "status": "ok",
            "detail": "Aucune variable ${VAR} référencée dans la config.",
            "fix": "",
        })
    elif missing_vars:
        checks.append({
            "label": "Résolution des variables ${VAR}",
            "status": "err",
            "detail": f"{len(missing_vars)} variable(s) référencée(s) mais absente(s) de .env.local : "
                      + ", ".join(missing_vars) + ". Le MCP plantera : les ${VAR} ne seront pas substituées.",
            "fix": "Définis " + ", ".join(missing_vars) + " dans .env.local (Outils -> Variables d'environnement).",
        })
    else:
        checks.append({
            "label": "Résolution des variables ${VAR}",
            "status": "ok",
            "detail": f"{len(referenced)} variable(s) référencée(s), toutes définies : "
                      + ", ".join(referenced) + ".",
            "fix": "",
        })

    # ── 1b. Lint statique : caractère parasite après ${VAR} (le « Q » wikijs) ──
    stuck: list[dict] = []
    for s in _mcp_interpolable_strings(mcp):
        for m in _STUCK_VAR_RE.finditer(s):
            stuck.append({"var": m.group(1), "char": m.group(2)})
    if stuck:
        details = ", ".join(f"« {h['char']} » accolé à ${{{h['var']}}}" for h in stuck)
        checks.append({
            "label": "Lint statique de la config",
            "status": "warn",
            "detail": f"Caractère parasite accolé à une variable : {details}. "
                      "Probable typo (ex. la valeur copiée a un char en trop).",
            "fix": "Retire le caractère accolé juste après le } de la variable.",
        })
    else:
        checks.append({
            "label": "Lint statique de la config",
            "status": "ok",
            "detail": "Aucun caractère parasite accolé à une variable.",
            "fix": "",
        })

    # ── 1c. Commande disponible (stdio) ──────────────────────────────────────
    if transport == "stdio":
        exe = _stdio_executable(mcp)
        if not exe:
            checks.append({
                "label": "Commande exécutable",
                "status": "err",
                "detail": "Aucune commande définie pour un transport stdio.",
                "fix": "Renseigne le champ Command (ex. npx, uvx, node, python).",
            })
        elif shutil.which(exe):
            checks.append({
                "label": "Commande exécutable",
                "status": "ok",
                "detail": f"« {exe} » est résoluble dans le PATH ({shutil.which(exe)}).",
                "fix": "",
            })
        else:
            checks.append({
                "label": "Commande exécutable",
                "status": "err",
                "detail": f"« {exe} » est introuvable dans le PATH. Le MCP ne démarrera pas "
                          "(Claude affichera « commande introuvable »).",
                "fix": f"Installe « {exe} » ou vérifie qu'il est dans le PATH "
                       "(ex. Node.js pour npx, uv pour uvx).",
            })

    # ── 1d. Sonde HTTP (http/sse) ────────────────────────────────────────────
    if transport in ("http", "sse"):
        url_raw = (mcp.get("url") or "").strip()
        url, miss_url = substitute_env(url_raw, env_local)
        headers_dict, _ = substitute_env(mcp.get("headers") or {}, env_local)
        if not url_raw:
            checks.append({
                "label": "Sonde HTTP",
                "status": "err",
                "detail": "Aucune URL définie pour un transport http/sse.",
                "fix": "Renseigne le champ URL.",
            })
        elif miss_url:
            # URL non résolue : 1a a déjà signalé les vars manquantes ; on évite
            # une requête vers une URL qui contient encore des ${VAR}.
            checks.append({
                "label": "Sonde HTTP",
                "status": "warn",
                "detail": "URL non sondée : elle contient des ${VAR} non résolues "
                          + "(" + ", ".join(miss_url) + ").",
                "fix": "Définis les variables manquantes puis relance le diagnostic.",
            })
        elif not (url.lower().startswith("http://") or url.lower().startswith("https://")):
            checks.append({
                "label": "Sonde HTTP",
                "status": "err",
                "detail": "L'URL ne commence pas par http:// ou https://.",
                "fix": "Corrige l'URL pour qu'elle soit un endpoint HTTP(S) valide.",
            })
        else:
            checks.append(_probe_http(url, headers_dict))

    # ── 1e. Sync registre <-> workspaces ─────────────────────────────────────
    desync = _diagnose_sync(mcp)
    if desync is not None:
        checks.append(desync)

    # ── Verdict global (le pire des statuts l'emporte) ───────────────────────
    statuses = {c["status"] for c in checks}
    if "err" in statuses:
        verdict = "err"
    elif "warn" in statuses:
        verdict = "warn"
    else:
        verdict = "ok"

    return 200, {"id": mcp_id, "verdict": verdict, "checks": checks}


def _probe_http(url: str, headers: dict) -> dict:
    """Sonde HTTP légère (stdlib only). Mappe le code -> cause actionnable.

    Profondeur volontairement minimale : on ne lit pas le body (peut contenir
    des données sensibles ou être volumineux), on ne renvoie JAMAIS la valeur
    des headers (qui contiennent les secrets résolus). Timeout court (5s).
    HEAD d'abord (moins coûteux), fallback GET si la méthode est refusée (405).
    """
    import urllib.error
    import urllib.request

    label = "Sonde HTTP"

    def _request(method: str):
        req = urllib.request.Request(url, method=method)
        for k, v in (headers or {}).items():
            # On envoie les headers résolus (auth comprise) mais on ne les
            # renvoie jamais dans la réponse : pas de fuite de secret.
            req.add_header(k, v)
        return urllib.request.urlopen(req, timeout=5)

    try:
        try:
            resp = _request("HEAD")
        except urllib.error.HTTPError as e:
            if e.code == 405:  # HEAD non supporté -> on retente en GET
                resp = _request("GET")
            else:
                raise
        code = getattr(resp, "status", None) or resp.getcode()
        resp.close()
        return {
            "label": label,
            "status": "ok",
            "detail": f"Le serveur répond (HTTP {code}). Endpoint joignable et auth acceptée.",
            "fix": "",
        }
    except urllib.error.HTTPError as e:
        code = e.code
        if code in (401, 403):
            return {
                "label": label,
                "status": "err",
                "detail": f"HTTP {code} (Forbidden/Unauthorized) : le serveur refuse l'accès. "
                          "Cause la plus fréquente : un token/header d'auth invalide "
                          "(ex. JWT tronqué ou avec un caractère en trop -> fallback invité).",
                "fix": "Vérifie la valeur du token/header d'auth dans .env.local "
                       "(compare les derniers caractères, attention à un char collé).",
            }
        if code in (405, 400, 406):
            # Endpoint MCP qui n'accepte ni HEAD ni GET (attend POST/JSON-RPC).
            # Le serveur EST joignable et l'auth est passée (sinon 401/403) :
            # c'est un signal positif pour notre objectif (joignabilité + auth).
            return {
                "label": label,
                "status": "ok",
                "detail": f"Le serveur répond (HTTP {code}) : endpoint joignable et auth acceptée "
                          "(le code reflète juste que la méthode de sonde n'est pas celle attendue, "
                          "un endpoint MCP attend POST/JSON-RPC).",
                "fix": "",
            }
        if code == 404:
            return {
                "label": label,
                "status": "warn",
                "detail": "HTTP 404 : l'endpoint répond mais le chemin est introuvable. "
                          "L'URL pointe peut-être sur la mauvaise route.",
                "fix": "Vérifie le chemin de l'URL (souvent /mcp ou /sse selon le serveur).",
            }
        return {
            "label": label,
            "status": "warn",
            "detail": f"HTTP {code} : le serveur répond mais avec une erreur.",
            "fix": "Consulte la doc du serveur MCP pour ce code de statut.",
        }
    except urllib.error.URLError as e:
        # Connexion refusée, DNS, timeout enrobé... reason peut être un
        # socket.timeout ou une OSError. L'URL n'est pas un secret ; on ne
        # logue/renvoie jamais les headers.
        reason = getattr(e, "reason", e)
        return {
            "label": label,
            "status": "err",
            "detail": f"Serveur injoignable : {url} ({reason}).",
            "fix": "Vérifie que le serveur tourne et que l'URL/le port sont corrects "
                   "(et que la machine est joignable depuis ce poste).",
        }
    except socket.timeout:
        return {
            "label": label,
            "status": "err",
            "detail": f"Délai dépassé (5s) en contactant {url}.",
            "fix": "Le serveur est lent ou injoignable : vérifie l'URL, le port et le réseau.",
        }
    except Exception as e:  # noqa: BLE001 — robustesse de la sonde
        return {
            "label": label,
            "status": "warn",
            "detail": f"Sonde HTTP impossible : {type(e).__name__}.",
            "fix": "Vérifie l'URL et les headers de la config.",
        }


def _diagnose_sync(mcp: dict) -> dict | None:
    """Compare le registre aux .mcp.json des workspaces ciblés (réutilise la
    logique de sanity_check). Signale les workspaces désync (warn).

    Retourne None si le MCP est désactivé (rien à synchroniser). PÉRIMÈTRE :
    le fix est TEXTUEL (« lance Sync ») — aucun bouton d'action ici (Lot D).
    """
    if mcp.get("status") == "désactivé":
        return None
    targeted = _workspaces_affected_by_mcp(mcp)
    if not targeted:
        return {
            "label": "Synchronisation workspaces",
            "status": "warn",
            "detail": "Ce MCP ne cible aucun workspace : il est enregistré mais distribué nulle part.",
            "fix": "Coche au moins un workspace dans « Workspaces ciblés » (modale Modifier).",
        }
    mcp_id = mcp["id"]
    not_synced = []
    for w in list_workspaces():
        if w["id"] not in targeted:
            continue
        mcp_file = Path(w["path"]) / ".mcp.json"
        actual = set()
        if mcp_file.exists():
            data = read_json(mcp_file, {})
            actual = set((data.get("mcpServers") or {}).keys())
        if mcp_id not in actual:
            not_synced.append(w["id"])
    if not_synced:
        return {
            "label": "Synchronisation workspaces",
            "status": "warn",
            "detail": f"Absent du .mcp.json de {len(not_synced)} workspace(s) ciblé(s) : "
                      + ", ".join(not_synced) + ". La config registre n'est pas propagée.",
            "fix": "Lance « Sync » (Home ou page workspace) pour régénérer les .mcp.json.",
        }
    return {
        "label": "Synchronisation workspaces",
        "status": "ok",
        "detail": f"Propagé dans les {len(targeted)} workspace(s) ciblé(s).",
        "fix": "",
    }


# _si : alias du sanitizer partage (defini dans env_local, importe via
# helpers). Retire les caracteres invisibles/bidi des args/command/cwd au
# save registre. cf. audit-ux-2026-05-25.
_si = strip_invisible


def _si_list(lst: list) -> list:
    return [_si(x) if isinstance(x, str) else x for x in lst]


def clean_mcp_payload(payload: dict) -> tuple[dict, str | None]:
    mcp_id = (payload.get("id") or "").strip()
    if not safe_id(mcp_id):
        return {}, "id invalide"

    clean = {
        "id": mcp_id,
        "name": (payload.get("name") or mcp_id).strip(),
        "description": (payload.get("description") or "").strip(),
        "transport": (payload.get("transport") or "stdio").strip(),
        "command": _si((payload.get("command") or "").strip()),
        "args": _si_list(payload.get("args") or []),
        "env": payload.get("env") or {},
        "cwd": _si((payload.get("cwd") or "").strip()),
        "url": (payload.get("url") or "").strip(),
        "headers": payload.get("headers") or {},
        "workspaces": payload.get("workspaces") or [],
        "status": (payload.get("status") or "à configurer").strip(),
        "notes": (payload.get("notes") or "").strip(),
        "author": (payload.get("author") or "").strip(),
        "source_url": (payload.get("source_url") or "").strip(),
    }
    if clean["transport"] not in ALLOWED_TRANSPORTS:
        return {}, f"transport invalide ({'/'.join(ALLOWED_TRANSPORTS)})"
    if clean["status"] not in ALLOWED_STATUS:
        return {}, f"status invalide"
    if not isinstance(clean["args"], list):
        return {}, "args doit être une liste"
    if not isinstance(clean["env"], dict):
        return {}, "env doit être un objet"
    if not isinstance(clean["headers"], dict):
        return {}, "headers doit être un objet"
    if not isinstance(clean["workspaces"], list):
        return {}, "workspaces doit être une liste"

    clean = {k: v for k, v in clean.items() if v not in ("", [], {}, None)}
    clean["id"] = mcp_id
    return clean, None


def _workspaces_affected_by_mcp(mcp: dict) -> set:
    """Ids de workspaces visés par un MCP (gère '*' et 'all')."""
    ws = mcp.get("workspaces") or []
    all_ids = {w["id"] for w in list_workspaces()}
    if "*" in ws or "all" in ws:
        return all_ids
    return {x for x in ws if x in all_ids}


def _auto_sync(workspace_ids: set) -> dict:
    """Régénère les .mcp.json pour chaque workspace donné."""
    results = {}
    for ws_id in workspace_ids:
        try:
            _, r = sync_workspace_mcps(ws_id)
            results[ws_id] = r
        except Exception as e:
            results[ws_id] = {"error": str(e)}
    return results


def compute_mcp_status(mcp: dict) -> str:
    """Calcule le statut d'un MCP à partir de son état réel.

    - "désactivé" : choix explicite manuel — respecté tel quel
    - "à configurer" : pas de command (stdio) ou pas d'url (http/sse)
    - "disponible" : config complète

    Le statut "connecté" n'est plus retourné ici (demanderait un test live).
    Le bouton "Diag" sur la MCP card permet une vérif live à la demande.
    """
    if mcp.get("status") == "désactivé":
        return "désactivé"
    transport = mcp.get("transport", "stdio")
    if transport == "stdio" and not (mcp.get("command") or "").strip():
        return "à configurer"
    if transport in ("http", "sse") and not (mcp.get("url") or "").strip():
        return "à configurer"
    return "disponible"


def list_mcps_with_computed_status() -> dict:
    """Lit le registre et override status par la valeur calculée."""
    data = read_json(MCP_REGISTRY, {"version": "1.0", "mcps": []})
    for m in data.get("mcps", []):
        m["status"] = compute_mcp_status(m)
    return data


def add_or_update_mcp(payload: dict) -> tuple[int, dict]:
    clean, err = clean_mcp_payload(payload)
    if err:
        return 400, {"error": err}
    with _MUTATION_LOCK:
        data = read_json(MCP_REGISTRY, {"version": "1.0", "mcps": []})
        mcps = data.setdefault("mcps", [])
        idx = next((i for i, m in enumerate(mcps) if m.get("id") == clean["id"]), None)

        # Union des workspaces impactés (avant + après) pour ne rien oublier
        before_scopes = _workspaces_affected_by_mcp(mcps[idx]) if idx is not None else set()
        after_scopes = _workspaces_affected_by_mcp(clean)
        affected = before_scopes | after_scopes

        if idx is None:
            mcps.append(clean)
            action = "created"
        else:
            mcps[idx] = clean
            action = "overwritten"
        write_json(MCP_REGISTRY, data)
        # Sync sous le verrou : garantit que les .mcp.json reflètent
        # exactement le registre qu'on vient d'écrire (pas d'interleaving).
        synced = _auto_sync(affected)
    # `action` permet à l'import bulk de distinguer création vs écrasement
    # silencieux d'un id déjà présent (récap front, audit UX Lot G item 2).
    return 200, {"ok": True, "id": clean["id"], "action": action, "synced": sorted(synced.keys())}


def delete_mcp(mcp_id: str) -> tuple[int, dict]:
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
    with _MUTATION_LOCK:
        data = read_json(MCP_REGISTRY, {"version": "1.0", "mcps": []})
        existing = next((m for m in data.get("mcps", []) if m.get("id") == mcp_id), None)
        if existing is None:
            return 404, {"error": "MCP absent"}

        affected = _workspaces_affected_by_mcp(existing)
        data["mcps"] = [m for m in data.get("mcps", []) if m.get("id") != mcp_id]
        write_json(MCP_REGISTRY, data)
        synced = _auto_sync(affected)
    return 200, {"ok": True, "synced": sorted(synced.keys())}


def mcp_applies_to(mcp: dict, ws_id: str) -> bool:
    ws = mcp.get("workspaces") or []
    return "*" in ws or "all" in ws or ws_id in ws


def build_mcp_server_entry(mcp: dict, env_local: dict) -> tuple[dict, list[str]]:
    """Formate une entrée `mcpServers[x]` conforme à Claude Code + liste env manquants."""
    transport = mcp.get("transport", "stdio")
    entry = {}
    missing_total = []

    if transport in ("http", "sse"):
        url, miss = substitute_env(mcp.get("url", ""), env_local)
        entry["type"] = transport
        entry["url"] = url
        missing_total.extend(miss)
        # Headers HTTP/SSE (Authorization, X-API-Key, etc.) avec interpolation ${VAR}
        headers_dict, miss_h = substitute_env(mcp.get("headers", {}), env_local)
        if headers_dict:
            entry["headers"] = headers_dict
        missing_total.extend(miss_h)
    else:
        cmd, miss = substitute_env(mcp.get("command", ""), env_local)
        args, miss2 = substitute_env(mcp.get("args", []), env_local)
        if cmd and not args:
            parts = shlex.split(cmd, posix=False)
            if parts:
                cmd = parts[0]
                args = parts[1:]
        entry["command"] = cmd
        if args:
            entry["args"] = args
        # cwd : working directory du process MCP (avec interpolation ${VAR})
        cwd_val, miss_cwd = substitute_env(mcp.get("cwd", ""), env_local)
        if cwd_val:
            entry["cwd"] = cwd_val
        missing_total.extend(miss + miss2 + miss_cwd)

    env_dict, miss3 = substitute_env(mcp.get("env", {}), env_local)
    if env_dict:
        entry["env"] = env_dict
    missing_total.extend(miss3)
    return entry, sorted(set(missing_total))


# ── Détection d'édition manuelle du .mcp.json (audit UX Lot G item 3) ────────
# Le registre Nebula EST la source de vérité ; sync_workspace_mcps régénère le
# .mcp.json de chaque workspace. Si l'utilisateur a édité le .mcp.json à la main
# (piège documenté : il FAUT éditer le registre, pas le fichier), son edit est
# écrasé au sync. On détecte la divergence pour l'AVERTIR -- sans bloquer : le
# sync reste la bonne action, le registre fait foi.
#
# Mécanisme : on stocke le hash du DERNIER .mcp.json généré par Nebula dans un
# état centralisé (data/mcp_sync_state.json, mappé par ws_id). Au sync suivant,
# si le fichier sur disque ne correspond pas à ce hash -> il a été édité hors
# Nebula. État centralisé (pas de sidecar dans le workspace) : ne pollue pas
# l'arbre du workspace, ne part pas dans git, un seul fichier à gérer.
MCP_SYNC_STATE_FILE = DASHBOARD_DIR / "data" / "mcp_sync_state.json"


def _mcp_file_hash(path: Path) -> str | None:
    """sha256 hex du contenu brut du fichier, ou None s'il n'existe pas/illisible."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _read_mcp_sync_state() -> dict:
    state = read_json(MCP_SYNC_STATE_FILE, {})
    return state if isinstance(state, dict) else {}


def _set_mcp_sync_hash(ws_id: str, file_hash: str | None) -> None:
    """Persiste (ou retire si None) le hash du dernier .mcp.json généré pour ws_id."""
    state = _read_mcp_sync_state()
    if file_hash is None:
        state.pop(ws_id, None)
    else:
        state[ws_id] = file_hash
    write_json(MCP_SYNC_STATE_FILE, state)


def sync_workspace_mcps(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = resolve_ws_dir(ws_id)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}

    env_local = load_env_local()
    registry = read_json(MCP_REGISTRY, {"mcps": []})
    mcp_servers = {}
    missing = {}
    applied = []

    for m in registry.get("mcps", []):
        if not mcp_applies_to(m, ws_id):
            continue
        if m.get("status") == "désactivé":
            continue
        entry, miss = build_mcp_server_entry(m, env_local)
        mcp_servers[m["id"]] = entry
        applied.append(m["id"])
        if miss:
            missing[m["id"]] = miss

    out_path = ws_dir / ".mcp.json"

    # Détection AVANT écrasement : le fichier sur disque diverge-t-il du dernier
    # rendu Nebula connu ? On ne signale que si on a une empreinte de référence
    # (sinon = première sync ou état perdu : pas d'alerte, on (re)synchronise).
    prev_hash = _read_mcp_sync_state().get(ws_id)
    cur_hash = _mcp_file_hash(out_path)
    hand_edited = bool(prev_hash and cur_hash and cur_hash != prev_hash)

    if mcp_servers:
        write_json(out_path, {"mcpServers": mcp_servers})
        # Stocke le hash du fichier RÉELLEMENT écrit (relu sur disque) pour que
        # la prochaine comparaison soit exacte, indépendamment du rendu json.
        _set_mcp_sync_hash(ws_id, _mcp_file_hash(out_path))
    elif out_path.exists():
        out_path.unlink()
        _set_mcp_sync_hash(ws_id, None)
    else:
        # Rien à générer et rien sur disque : nettoie un éventuel hash résiduel.
        _set_mcp_sync_hash(ws_id, None)

    result = {"ok": True, "applied": applied, "missing_env": missing, "path": str(out_path)}
    if hand_edited:
        result["hand_edited"] = True
    return 200, result


def sync_all_workspaces() -> tuple[int, dict]:
    results = {}
    for w in list_workspaces():
        _, r = sync_workspace_mcps(w["id"])
        results[w["id"]] = r
    return 200, {"ok": True, "results": results}


def workspace_mcp_status(ws_id: str) -> tuple[int, dict]:
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = resolve_ws_dir(ws_id)
    mcp_file = ws_dir / ".mcp.json"
    data = read_json(mcp_file, None)
    active = list((data or {}).get("mcpServers", {}).keys())
    return 200, {"active": active, "has_file": mcp_file.exists()}


# ── Setup / Import wizard ─────────────────────────────────────────────────────

def _read_cwd_from_sessions(proj_dir: Path) -> str | None:
    """Lit le `cwd` d'un message dans les fichiers .jsonl du projet.

    Source de vérité : Claude Code stocke le chemin original (`cwd`) dans
    chaque message utilisateur. Plus fiable que tout décodage du nom de dossier,
    et fonctionne même si le dossier source a été supprimé/renommé/déplacé.
    """
    for jl in proj_dir.glob("*.jsonl"):
        try:
            with jl.open("r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i > 50:  # cwd se trouve quasi-toujours dans les 5 premières lignes
                        break
                    line = line.strip()
                    if not line or '"cwd"' not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cwd = obj.get("cwd")
                    if isinstance(cwd, str) and cwd:
                        return cwd
        except OSError:
            continue
    return None


def _decode_project_path(name: str) -> tuple[str, bool]:
    """Décode best-effort un nom de dossier ~/.claude/projects/ en chemin Windows.

    Fallback uniquement : utilisé quand aucune session ne contient de `cwd`.
    Le décodage est ambigu (`:`, `\\`, espaces tous encodés en `-`) — on tente
    un DFS avec vérification d'existence pour résoudre l'ambiguïté.
    Retourne (chemin, existe_sur_disque).
    """
    m = re.match(r'^([A-Za-z])--(.*)$', name)
    if not m:
        return "", False
    drive = m.group(1).upper() + ":\\"
    parts = [p for p in m.group(2).split('-') if p]
    if not parts:
        base = drive.rstrip("\\")
        return base, Path(base).exists()

    def dfs(idx: int, segs: list[str]) -> list[str] | None:
        if idx == len(parts):
            return segs if Path(drive + "\\".join(segs)).exists() else None
        seg = parts[idx]
        # Option A : nouveau segment de chemin
        r = dfs(idx + 1, segs + [seg])
        if r is not None:
            return r
        if segs:
            # Option B : tiret littéral (ex: reverse-engineering)
            r = dfs(idx + 1, segs[:-1] + [segs[-1] + "-" + seg])
            if r is not None:
                return r
            # Option C : espace littéral (Claude encode aussi les espaces en -)
            r = dfs(idx + 1, segs[:-1] + [segs[-1] + " " + seg])
            if r is not None:
                return r
        return None

    found = dfs(1, [parts[0]])
    if found:
        return drive + "\\".join(found), True
    # Fallback naïf (chemin probablement incorrect mais utile comme point de départ)
    return drive + "\\".join(parts), False


CLAUDE_GLOBAL_SOURCES = (
    USER_HOME / ".claude.json",
    CLAUDE_SETTINGS,
    CLAUDE_HOME / "settings.local.json",
)


def find_global_mcp_conflicts() -> dict:
    """Détecte les MCPs présents à la fois dans la config Claude globale et dans le registre Nebula.

    Pour chaque MCP du registre, on regarde s'il existe une entrée homonyme dans
    `~/.claude.json`, `~/.claude/settings.json` ou `~/.claude/settings.local.json`.
    Les doublons créent une config zombie : Nebula sync vers le `.mcp.json` du
    workspace, mais l'entrée globale reste et peut diverger silencieusement.
    """
    registry = read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", [])
    registry_ids = {m["id"]: m for m in registry}

    conflicts = []
    for src in CLAUDE_GLOBAL_SOURCES:
        if not src.exists():
            continue
        try:
            data = read_json(src, {})
        except Exception:
            continue
        servers = (data.get("mcpServers") or {})
        if not isinstance(servers, dict):
            continue
        for name, cfg in servers.items():
            if name in registry_ids:
                conflicts.append({
                    "id": name,
                    "source": str(src),
                    "source_label": src.name,
                    "registry_status": registry_ids[name].get("status", "à configurer"),
                    "registry_workspaces": registry_ids[name].get("workspaces", []),
                    "global_command": cfg.get("command", ""),
                    "global_url": cfg.get("url", ""),
                    "global_transport": cfg.get("type") or cfg.get("transport") or ("http" if cfg.get("url") else "stdio"),
                })

    # MCPs uniquement dans la config globale (jamais importés dans Nebula)
    orphans = []
    for src in CLAUDE_GLOBAL_SOURCES:
        if not src.exists():
            continue
        try:
            data = read_json(src, {})
        except Exception:
            continue
        servers = (data.get("mcpServers") or {})
        if not isinstance(servers, dict):
            continue
        for name, cfg in servers.items():
            if name not in registry_ids:
                orphans.append({
                    "id": name,
                    "source": str(src),
                    "source_label": src.name,
                    "transport": cfg.get("type") or cfg.get("transport") or ("http" if cfg.get("url") else "stdio"),
                    "command": cfg.get("command", ""),
                    "url": cfg.get("url", ""),
                })

    return {
        "conflicts": conflicts,
        "orphans": orphans,
        "sources": [str(s) for s in CLAUDE_GLOBAL_SOURCES if s.exists()],
    }


def remove_mcp_from_claude_global(mcp_id: str, source: str) -> tuple[int, dict]:
    """Retire un MCP d'un fichier de config Claude globale (avec backup automatique)."""
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
    # Vérifie que le source est bien un des fichiers autorisés (anti-traversal)
    src_path = Path(source).resolve()
    allowed = [s.resolve() for s in CLAUDE_GLOBAL_SOURCES]
    if src_path not in allowed:
        return 400, {"error": "source non autorisée"}
    if not src_path.exists():
        return 404, {"error": "fichier introuvable"}

    with _MUTATION_LOCK:
        try:
            data = read_json(src_path, {}) or {}
        except Exception as e:
            return 500, {"error": f"lecture impossible : {e}"}
        servers = data.get("mcpServers") or {}
        if mcp_id not in servers:
            return 404, {"error": f"MCP '{mcp_id}' absent de {src_path.name}"}
        # Backup
        bak = src_path.with_suffix(src_path.suffix + ".bak")
        bak.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")
        # Retrait
        del servers[mcp_id]
        if servers:
            data["mcpServers"] = servers
        else:
            data.pop("mcpServers", None)
        write_json(src_path, data)
        log.info("global mcp cleanup: removed %s from %s", mcp_id, src_path.name)
        return 200, {"ok": True, "backup": str(bak)}


def migrate_global_mcp_to_registry(mcp_id: str, source: str, workspaces: list | None = None) -> tuple[int, dict]:
    """Importe un MCP de la config globale dans le registre Nebula puis le retire de la source.

    Pour les "orphelins" — MCPs présents dans ~/.claude/settings.json mais pas
    dans le registre. Évite la double action import + cleanup manuel.
    """
    if not safe_id(mcp_id):
        return 400, {"error": "id invalide"}
    src_path = Path(source).resolve()
    allowed = [s.resolve() for s in CLAUDE_GLOBAL_SOURCES]
    if src_path not in allowed:
        return 400, {"error": "source non autorisée"}
    if not src_path.exists():
        return 404, {"error": "fichier introuvable"}

    data = read_json(src_path, {}) or {}
    servers = data.get("mcpServers") or {}
    if mcp_id not in servers:
        return 404, {"error": f"MCP '{mcp_id}' absent de {src_path.name}"}
    cfg = servers[mcp_id]

    payload = {
        "id": mcp_id,
        "name": cfg.get("name", mcp_id),
        "transport": cfg.get("transport") or cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
        "command": cfg.get("command", ""),
        "args": cfg.get("args", []),
        "env": cfg.get("env", {}),
        "cwd": cfg.get("cwd", ""),
        "url": cfg.get("url", ""),
        "headers": cfg.get("headers", {}),
        "workspaces": workspaces or [],
        "status": "disponible",
    }
    s, r = add_or_update_mcp(payload)
    if s >= 400:
        return s, r
    # Retire de la source seulement après import OK
    s2, r2 = remove_mcp_from_claude_global(mcp_id, source)
    if s2 >= 400:
        return s2, {"warning": "MCP importé mais nettoyage source échoué", **r2}
    return 200, {"ok": True, "imported": mcp_id, "removed_from": str(src_path.name)}


def scan_claude_config() -> tuple[int, dict]:
    """Scanne ~/.claude/ pour détecter MCPs et projets existants.

    Utilisé par le wizard d'import initial : permet à un nouvel utilisateur
    de pré-remplir le dashboard depuis sa config Claude Code existante.
    """
    result: dict = {"mcps": [], "projects": []}

    # ── MCPs ─────────────────────────────────────────────────────────────────
    existing_ids = {m["id"] for m in read_json(MCP_REGISTRY, {"mcps": []}).get("mcps", [])}
    seen: set[str] = set()

    def _collect_servers(servers: dict) -> None:
        for name, cfg in servers.items():
            if name in seen:
                return
            seen.add(name)
            result["mcps"].append({
                "id": name,
                "name": name,
                "transport": cfg.get("transport") or cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "env": cfg.get("env", {}),
                "cwd": cfg.get("cwd", ""),
                "url": cfg.get("url", ""),
                "headers": cfg.get("headers", {}),
                "already_registered": name in existing_ids,
            })

    # Sources globales : settings.json, settings.local.json, .claude.json (niveau racine)
    for sf in CLAUDE_GLOBAL_SOURCES:
        if not sf.exists():
            continue
        servers = (read_json(sf, {}).get("mcpServers") or {})
        if isinstance(servers, dict):
            _collect_servers(servers)

    # .claude.json : MCPs déclarés par projet (projects.<path>.mcpServers)
    if CLAUDE_JSON.exists():
        try:
            projects_data = (read_json(CLAUDE_JSON, {}).get("projects") or {})
            if isinstance(projects_data, dict):
                for proj_cfg in projects_data.values():
                    servers = (proj_cfg.get("mcpServers") or {}) if isinstance(proj_cfg, dict) else {}
                    if isinstance(servers, dict):
                        _collect_servers(servers)
        except Exception:
            pass

    # ── Projets ───────────────────────────────────────────────────────────────
    if not CLAUDE_PROJECTS.exists():
        return 200, result

    existing_paths = {
        w.get("path", "").lower()
        for w in read_json(WORKSPACES_JSON, {"workspaces": []}).get("workspaces", [])
    }

    for proj_dir in sorted(CLAUDE_PROJECTS.iterdir()):
        if not proj_dir.is_dir():
            continue
        sessions = list(proj_dir.glob("*.jsonl"))
        if not sessions:
            continue
        # Source de vérité prioritaire : le cwd stocké dans les sessions
        path = _read_cwd_from_sessions(proj_dir)
        source = "session"
        if not path:
            # Fallback : DFS sur le nom de dossier (ambigu mais souvent correct)
            path, _ = _decode_project_path(proj_dir.name)
            source = "decoded"
        path_exists = bool(path) and Path(path).exists()
        last_mod = max(s.stat().st_mtime for s in sessions)
        result["projects"].append({
            "encoded": proj_dir.name,
            "path": path or "",
            "path_exists": path_exists,
            "path_source": source,
            "sessions": len(sessions),
            "already_registered": (path or "").lower() in existing_paths,
            "last_modified": last_mod,
        })

    result["projects"].sort(key=lambda x: x["last_modified"], reverse=True)
    return 200, result


# ── Recettes MCP ────────────────────────────────────────────────────────────
MCP_RECIPES_FILE = DASHBOARD_DIR / "data" / "mcp_recipes.json"
MCP_RECIPES_LOCAL_FILE = DASHBOARD_DIR / "data" / "mcp_recipes.local.json"

_LOCAL_RECIPES_TEMPLATE = {
    "version": 1,
    "_help": "Recettes MCP locales — gitignored. Ajoute ici tes recettes perso ou propriétaires (ne partent pas dans le repo public).",
    "recipes": [
        {
            "id": "opnsense",
            "name": "OPNsense",
            "emoji": "🛡️",
            "description": "Lecture/écriture de la config d'un firewall OPNsense via son API REST.",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@richard-stovall/opnsense-mcp-server"],
            "env": {
                "OPNSENSE_URL": "${URL}",
                "OPNSENSE_API_KEY": "${API_KEY}",
                "OPNSENSE_API_SECRET": "${API_SECRET}",
                "OPNSENSE_VERIFY_SSL": "${VERIFY_SSL}"
            },
            "params": [
                {"key": "URL", "label": "URL OPNsense", "placeholder": "https://192.168.1.1", "required": True},
                {"key": "API_KEY", "label": "API Key", "placeholder": "...", "required": True, "secret": True},
                {"key": "API_SECRET", "label": "API Secret", "placeholder": "...", "required": True, "secret": True},
                {"key": "VERIFY_SSL", "label": "Verify SSL", "placeholder": "true", "required": False}
            ]
        }
    ]
}


def ensure_local_recipes_file() -> Path:
    """Crée mcp_recipes.local.json avec un template si absent. Retourne le chemin."""
    if not MCP_RECIPES_LOCAL_FILE.exists():
        MCP_RECIPES_LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_json(MCP_RECIPES_LOCAL_FILE, _LOCAL_RECIPES_TEMPLATE)
    return MCP_RECIPES_LOCAL_FILE


def add_or_update_local_recipe(payload: dict) -> tuple[int, dict]:
    """Upsert d'une recette locale (mcp_recipes.local.json).

    Validation minimale : id valide + au moins command (stdio) ou url (http/sse).
    Les params sont validés (chaque param doit avoir au moins key + label).
    """
    rid = (payload.get("id") or "").strip()
    if not safe_id(rid):
        return 400, {"error": "ID invalide (alphanumérique + - _ uniquement)"}
    transport = payload.get("transport", "stdio")
    if transport not in ALLOWED_TRANSPORTS:
        return 400, {"error": f"Transport invalide. Autorisés : {ALLOWED_TRANSPORTS}"}
    if transport == "stdio" and not (payload.get("command") or "").strip():
        return 400, {"error": "command requis pour stdio"}
    if transport in ("http", "sse") and not (payload.get("url") or "").strip():
        return 400, {"error": f"url requis pour {transport}"}

    # Valide les params
    params = payload.get("params") or []
    if not isinstance(params, list):
        return 400, {"error": "params doit être une liste"}
    for p in params:
        if not isinstance(p, dict) or not p.get("key") or not p.get("label"):
            return 400, {"error": "chaque param doit avoir key + label"}

    ensure_local_recipes_file()
    with _MUTATION_LOCK:
        data = read_json(MCP_RECIPES_LOCAL_FILE, {"version": 1, "recipes": []})
        recipes = data.get("recipes", [])
        # Construit la recette nettoyée (drop le `source` si fourni par le front)
        clean = {k: v for k, v in payload.items() if k != "source"}

        replaced = False
        for i, r in enumerate(recipes):
            if r.get("id") == rid:
                recipes[i] = clean
                replaced = True
                break
        if not replaced:
            recipes.append(clean)
        data["recipes"] = recipes
        write_json(MCP_RECIPES_LOCAL_FILE, data)
        return 200, {"ok": True, "id": rid, "action": "updated" if replaced else "created"}


def delete_local_recipe(rid: str) -> tuple[int, dict]:
    if not safe_id(rid):
        return 400, {"error": "id invalide"}
    if not MCP_RECIPES_LOCAL_FILE.exists():
        return 404, {"error": "Aucune recette locale"}
    with _MUTATION_LOCK:
        data = read_json(MCP_RECIPES_LOCAL_FILE, {"version": 1, "recipes": []})
        recipes = data.get("recipes", [])
        new_recipes = [r for r in recipes if r.get("id") != rid]
        if len(new_recipes) == len(recipes):
            return 404, {"error": f"Recette '{rid}' introuvable"}
        data["recipes"] = new_recipes
        write_json(MCP_RECIPES_LOCAL_FILE, data)
        return 200, {"ok": True, "deleted": rid}


def list_mcp_recipes() -> tuple[int, dict]:
    """Sert le catalogue de recettes MCP : public (versionné) + local (gitignored).

    Chaque recette est marquée `source: "public" | "local"` pour que l'UI
    puisse les afficher en sections séparées.
    Substitution des `${KEY}` faite côté client avant le POST /api/mcps.
    """
    public = read_json(MCP_RECIPES_FILE, {"version": 1, "recipes": []})
    local = read_json(MCP_RECIPES_LOCAL_FILE, {"version": 1, "recipes": []})

    public_recipes = [{**r, "source": "public"} for r in public.get("recipes", []) if isinstance(r, dict)]
    local_recipes = [{**r, "source": "local"} for r in local.get("recipes", []) if isinstance(r, dict)]

    return 200, {
        "version": 1,
        "recipes": public_recipes + local_recipes,
        "local_file_exists": MCP_RECIPES_LOCAL_FILE.exists(),
        "local_file_path": str(MCP_RECIPES_LOCAL_FILE),
    }
