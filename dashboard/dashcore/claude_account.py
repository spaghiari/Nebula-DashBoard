"""Lecture sûre de l'abonnement Claude de l'utilisateur.

Sert à avertir sur la consommation (opus, effort élevé sur un abonnement
Pro). Ordre de priorité : réglage manuel `claude_plan` de l'UI, puis
`~/.claude.json` (`oauthAccount`), puis `claude auth status` (CLI), puis
`~/.claude/.credentials.json`, sinon `unknown`. Une clé API (`authMethod:
api_key` côté CLI) est un mode de facturation : elle prime (`plan: api`),
sauf réglage manuel.

Constat réel : après un changement d'abonnement (Pro -> Max 5x), la CLI et
`.credentials.json` restent sur l'ancienne valeur (`subscriptionType`
enregistré à la connexion), alors que `oauthAccount.organizationType` /
`organizationRateLimitTier` de `~/.claude.json` sont à jour. D'où cet ordre.
`conflict` / `sources_seen` signalent les désaccords entre sources.

SÉCURITÉ : `.credentials.json` contient des jetons OAuth. Seules les clés de
`_CREDENTIALS_ALLOWED` en sont lues ; le reste n'est jamais copié, renvoyé
ni journalisé.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time

from dashcore import config
from dashcore.helpers import read_json, resolve_cli

CACHE_TTL = 300.0  # 5 minutes
CLI_TIMEOUT = 10
_CREDENTIALS_ALLOWED = ("subscriptionType", "rateLimitTier")

# Horloge injectable pour les tests.
_clock = time.monotonic
_cache: dict = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _norm_plan(value) -> str | None:
    """Normalise un type d'abonnement brut vers pro|max|team|api (ou None)."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None
    if "max" in v:
        return "max"
    if "team" in v or "enterprise" in v:
        return "team"
    if "pro" in v:
        return "pro"
    if "api" in v:
        return "api"
    return None


def _norm_tier(value) -> str | None:
    """`default_claude_max_5x` -> `max_5x` ; None si rien d'exploitable."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    for prefix in ("default_claude_", "claude_", "default_"):
        if v.startswith(prefix):
            v = v[len(prefix):]
            break
    return v or None


def _manual_plan() -> str | None:
    try:
        from dashcore.api_ui_state import _read
        value = _read().get("claude_plan", "auto")
    except Exception:
        return None
    return value if value in ("pro", "max", "api") else None


def _from_cli() -> dict | None:
    """Résultat normalisé de `claude auth status`, ou None (absent, échec).

    `plan` peut être None (connecté mais type non reconnu) : la CLI sert alors
    seulement pour `auth_method`.
    """
    cli = resolve_cli("claude")
    try:
        proc = subprocess.run(
            [cli, "auth", "status"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=CLI_TIMEOUT,
            shell=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "")
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("loggedIn"):
        return None
    method = data.get("authMethod") if isinstance(data.get("authMethod"), str) else None
    plan = _norm_plan(data.get("subscriptionType"))
    if method and "api_key" in method.lower():
        plan = "api"
    return {"plan": plan, "tier": _norm_tier(data.get("rateLimitTier")), "auth_method": method}


def _from_claude_json() -> dict | None:
    data = read_json(config.CLAUDE_JSON, {})
    acc = data.get("oauthAccount") if isinstance(data, dict) else None
    if not isinstance(acc, dict):
        return None
    plan = _norm_plan(acc.get("organizationType"))
    if plan is None:
        return None
    return {"plan": plan, "tier": _norm_tier(acc.get("organizationRateLimitTier")),
            "auth_method": "oauth"}


def _from_credentials() -> dict | None:
    data = read_json(config.CLAUDE_HOME / ".credentials.json", {})
    oauth = data.get("claudeAiOauth") if isinstance(data, dict) else None
    if not isinstance(oauth, dict):
        return None
    safe = {k: oauth.get(k) for k in _CREDENTIALS_ALLOWED}  # liste blanche stricte
    plan = _norm_plan(safe["subscriptionType"])
    if plan is None:
        return None
    return {"plan": plan, "tier": _norm_tier(safe["rateLimitTier"]), "auth_method": "oauth"}


def _detect(run_cli: bool) -> dict:
    api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    cli_available = bool(run_cli) and bool(_cli_exists())
    cli = _from_cli() if run_cli else None
    candidates = {"cli": cli if cli and cli["plan"] else None,
                  "claude_json": _from_claude_json(),
                  "credentials": _from_credentials()}
    # Plans seulement : jamais d'autre donnée des sources.
    sources_seen = {k: v["plan"] for k, v in candidates.items() if v}
    # `~/.claude.json` fait foi (la CLI et les identifiants gardent souvent
    # l'ancien plan après un changement d'abonnement) : pas de conflit signalé
    # quand il est lisible, seulement quand les sources restantes divergent.
    conflict = (not candidates["claude_json"]) and len(set(sources_seen.values())) > 1
    cli_method = cli["auth_method"] if cli else None
    found, source = None, "none"
    if cli and cli["plan"] == "api":  # mode de facturation : prioritaire
        found, source = cli, "cli"
    else:
        for name in ("claude_json", "cli", "credentials"):
            if candidates[name]:
                found, source = candidates[name], name
                break
    if not found and api_key_present:
        found = {"plan": "api", "tier": None, "auth_method": "api_key"}
    if (found and (found.get("auth_method") or "").lower().find("api_key") >= 0) or             (cli_method and "api_key" in cli_method.lower()):
        api_key_present = True
    auth_method = cli_method or (found["auth_method"] if found else None)
    if not found:
        return {"plan": "unknown", "tier": None, "source": "none", "auth_method": auth_method,
                "api_key_present": api_key_present, "cli_available": cli_available,
                "conflict": False, "sources_seen": sources_seen}
    return {"plan": found["plan"], "tier": found["tier"], "source": source,
            "auth_method": auth_method, "api_key_present": api_key_present,
            "cli_available": cli_available, "conflict": conflict,
            "sources_seen": sources_seen}


def _cli_exists() -> bool:
    import shutil
    return shutil.which("claude") is not None


def subscription_info(run_cli: bool = True) -> dict:
    """Abonnement détecté : plan, tier, source, auth_method, api_key_present,
    cli_available, conflict (sources en désaccord), sources_seen ({source: plan}).

    Le réglage manuel est relu à chaque appel (non mis en cache) ; la
    détection est mise en cache 5 minutes.
    """
    key = bool(run_cli)
    now = _clock()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            info = dict(hit[1])
        else:
            info = None
    if info is None:
        info = _detect(key)
        with _cache_lock:
            _cache[key] = (now, dict(info))
    manual = _manual_plan()
    if manual:
        info = {**info, "plan": manual, "tier": info["tier"] if info["plan"] == manual else None,
                "source": "manual", "conflict": False}
    return info


_EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")


def _effort_rank(value) -> int:
    v = value.strip().lower() if isinstance(value, str) else ""
    return _EFFORT_ORDER.index(v) if v in _EFFORT_ORDER else _EFFORT_ORDER.index("medium")


def consumption_warnings(plan: str, agents: list[dict], auto: bool = False,
                         conflict: bool = False) -> list[dict]:
    """Avertissements de consommation `[{level, code, message, agents}]`.

    Fonction pure, pilotée par `config.CONSUMPTION_RULES`. `agents` =
    `[{id, model, effort}]` ; un effort absent vaut le défaut de session
    (`medium`). `agents` de la sortie : ids concernés par la règle.
    """
    out = []
    for rule in config.CONSUMPTION_RULES:
        when = rule["when"]
        if "plan" in when and when["plan"] != plan:
            continue
        if when.get("auto") and not auto:
            continue
        if when.get("conflict") and not conflict:
            continue
        concerned: list = []
        if "model" in when or "effort_min" in when:
            for a in agents or []:
                model = str(a.get("model") or "").lower()
                if "model" in when and when["model"] not in model:
                    continue
                if "effort_min" in when and \
                        _effort_rank(a.get("effort")) < _effort_rank(when["effort_min"]):
                    continue
                concerned.append(a.get("id"))
            if not concerned:
                continue
        out.append({"level": rule["level"], "code": rule["code"],
                    "message": rule["message"], "agents": concerned})
    return out
