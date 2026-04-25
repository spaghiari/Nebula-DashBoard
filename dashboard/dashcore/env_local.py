"""Gestion du fichier .env.local : lecture, upsert, suppression, substitution.

Format simple : `KEY=VALUE` une par ligne, lignes `#` ignorées.
La fonction `substitute_env` remplace les `${VAR}` dans strings/lists/dicts.
"""
from __future__ import annotations

import os

from dashcore.config import ENV_FILE, ENV_KEY_RE, ENV_VAR_PATTERN, _MUTATION_LOCK, log


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
    """Remplace récursivement ${VAR} dans strings / lists / dicts.

    Retourne (valeur_substituée, liste_des_variables_manquantes).
    Cherche d'abord dans `env` (.env.local), puis dans os.environ en fallback.
    """
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
