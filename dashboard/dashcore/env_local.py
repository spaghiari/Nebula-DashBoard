"""Gestion du fichier .env.local : lecture, upsert, suppression, substitution.

Format simple : `KEY=VALUE` une par ligne, lignes `#` ignorées.
La fonction `substitute_env` remplace les `${VAR}` dans strings/lists/dicts.

Mode chiffré (DPAPI Windows) : si `.env.local.enc` existe, le contenu est
chiffré via DPAPI CurrentUser. Toutes les opérations de lecture/écriture
passent alors par le fichier chiffré ; `.env.local` en clair est ignoré
(sauf pour la migration).
"""
from __future__ import annotations

import os
import time

from dashcore.config import (
    ENV_ENC_FILE, ENV_FILE, ENV_KEY_RE, ENV_VAR_PATTERN, _MUTATION_LOCK, log,
)
from dashcore.env_crypto import (
    CryptoError, read_encrypted_file, write_encrypted_file,
)


def is_encrypted_mode() -> bool:
    """True si le fichier chiffré existe (mode chiffré actif)."""
    return ENV_ENC_FILE.exists()


def env_health() -> dict:
    """Diagnostic non-destructif : essaie de déchiffrer si chiffré, remonte l'erreur.

    Retourne {encrypted: bool, readable: bool, error: str|None}.
    """
    if not ENV_ENC_FILE.exists():
        return {"encrypted": False, "readable": ENV_FILE.exists() or True, "error": None}
    try:
        read_encrypted_file(ENV_ENC_FILE)
        return {"encrypted": True, "readable": True, "error": None}
    except CryptoError as e:
        return {"encrypted": True, "readable": False, "error": str(e)}
    except Exception as e:
        return {"encrypted": True, "readable": False, "error": f"erreur inattendue : {e}"}


def _parse_env_text(text: str) -> dict:
    env = {}
    for line in text.splitlines():
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


def _serialize_env(env: dict) -> str:
    """Sérialise un dict en lignes KEY=VALUE triées (mode chiffré)."""
    return "\n".join(f"{k}={env[k]}" for k in sorted(env.keys())) + "\n"


def load_env_local() -> dict:
    """Charge les variables d'env, depuis le fichier chiffré si présent, sinon clair.

    En cas d'échec DPAPI (compte/machine ≠), retourne un dict vide et log l'erreur :
    surtout NE PAS retomber silencieusement sur le clair, ce qui pourrait laisser
    croire qu'il n'y a aucune variable alors que le blob est juste illisible ici.
    """
    if ENV_ENC_FILE.exists():
        try:
            plaintext = read_encrypted_file(ENV_ENC_FILE)
            return _parse_env_text(plaintext.decode("utf-8"))
        except CryptoError as e:
            log.error("env: déchiffrement .env.local.enc impossible : %s", e)
            return {}
        except Exception as e:
            log.error("env: erreur lecture .env.local.enc : %s", e)
            return {}
    if not ENV_FILE.exists():
        return {}
    try:
        return _parse_env_text(ENV_FILE.read_text(encoding="utf-8"))
    except OSError as e:
        log.error("env: lecture .env.local impossible : %s", e)
        return {}


def _write_encrypted(env: dict) -> None:
    """Écrit le dict env dans le fichier chiffré (atomique + ACL stricte)."""
    write_encrypted_file(ENV_ENC_FILE, _serialize_env(env).encode("utf-8"))


def _write_plain_upsert(key: str, value: str) -> None:
    """Upsert dans .env.local en préservant commentaires et ordre. Mode clair."""
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


def set_env_var(key: str, value: str) -> tuple[int, dict]:
    """Upsert une clé dans le store (chiffré ou clair selon le mode actif)."""
    if not key or not ENV_KEY_RE.match(key):
        return 400, {"error": "clé invalide (lettres, chiffres, underscore ; ne commence pas par un chiffre)"}
    if "\n" in value or "\r" in value:
        return 400, {"error": "la valeur contient un saut de ligne"}

    with _MUTATION_LOCK:
        if is_encrypted_mode():
            try:
                env = load_env_local()
                env[key] = value
                _write_encrypted(env)
            except CryptoError as e:
                log.error("env: écriture chiffrée impossible : %s", e)
                return 500, {"error": f"chiffrement DPAPI échoué : {e}"}
        else:
            _write_plain_upsert(key, value)

    log.info("env: set %s", key)
    return 200, {"ok": True, "key": key}


def delete_env_var(key: str) -> tuple[int, dict]:
    """Retire une clé du store."""
    if not key or not ENV_KEY_RE.match(key):
        return 400, {"error": "clé invalide"}

    with _MUTATION_LOCK:
        if is_encrypted_mode():
            env = load_env_local()
            if key not in env:
                return 404, {"error": f"clé absente : {key}"}
            try:
                del env[key]
                _write_encrypted(env)
            except CryptoError as e:
                log.error("env: écriture chiffrée impossible : %s", e)
                return 500, {"error": f"chiffrement DPAPI échoué : {e}"}
        else:
            if not ENV_FILE.exists():
                return 404, {"error": ".env.local absent"}
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


def export_plain_text() -> tuple[int, str | dict]:
    """Retourne le contenu courant du store env sérialisé en clair (KEY=VALUE).

    Lecture pure, AUCUNE mutation : ni le .enc ni le .env.local ne sont touchés.
    Sert le filet de sécurité « télécharge une sauvegarde en clair avant de
    chiffrer » : si la clé DPAPI est perdue (changement de poste/compte),
    l'utilisateur a une copie hors-ligne de ses secrets.

    Retourne (200, texte) en cas de succès, (status, {error}) sinon.
    Le contenu EST en clair par construction (c'est l'objet de l'export) ;
    l'appelant est responsable de l'étiquetage et du transport (pièce jointe).
    """
    if is_encrypted_mode():
        try:
            plaintext = read_encrypted_file(ENV_ENC_FILE)
        except CryptoError as e:
            return 500, {"error": f"déchiffrement échoué : {e}"}
        try:
            env = _parse_env_text(plaintext.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            return 500, {"error": f"contenu déchiffré illisible : {e}"}
    else:
        if not ENV_FILE.exists():
            return 404, {"error": ".env.local absent : rien à exporter"}
        try:
            env = _parse_env_text(ENV_FILE.read_text(encoding="utf-8"))
        except OSError as e:
            return 500, {"error": f"lecture .env.local impossible : {e}"}

    header = (
        "# .env.local -- SAUVEGARDE EN CLAIR (secrets non chiffrés)\n"
        f"# Exporté le {time.strftime('%Y-%m-%d %H:%M:%S')} par Nebula.\n"
        "# ATTENTION : ce fichier contient tes secrets en clair. Stocke-le en\n"
        "# lieu sûr (gestionnaire de mots de passe, coffre chiffré) et supprime\n"
        "# toute copie qui traîne. Pour le restaurer : place-le à la racine de\n"
        "# Nebula sous le nom .env.local puis réactive le chiffrement.\n"
    )
    return 200, header + _serialize_env(env)


def enable_encryption() -> tuple[int, dict]:
    """Migre .env.local (clair) vers .env.local.enc (chiffré DPAPI).

    Le fichier clair est renommé .env.local.bak.<timestamp> (PAS supprimé, pour
    que l'utilisateur puisse vérifier avant de l'effacer manuellement). Le .bak
    reçoit la même ACL stricte que le .enc.
    """
    from dashcore.env_crypto import dpapi_self_test, restrict_acl_user_only

    with _MUTATION_LOCK:
        if is_encrypted_mode():
            return 409, {"error": "chiffrement déjà actif"}
        try:
            dpapi_self_test()
        except CryptoError as e:
            return 500, {"error": f"DPAPI indisponible : {e}"}

        env = {}
        if ENV_FILE.exists():
            try:
                env = _parse_env_text(ENV_FILE.read_text(encoding="utf-8"))
            except OSError as e:
                return 500, {"error": f"lecture .env.local impossible : {e}"}

        try:
            _write_encrypted(env)
        except CryptoError as e:
            return 500, {"error": f"écriture chiffrée échouée : {e}"}

        bak_path = None
        if ENV_FILE.exists():
            ts = time.strftime("%Y%m%d-%H%M%S")
            bak_path = ENV_FILE.with_suffix(ENV_FILE.suffix + f".bak.{ts}")
            try:
                os.replace(ENV_FILE, bak_path)
                try:
                    restrict_acl_user_only(bak_path)
                except Exception as e:
                    log.warning("ACL sur backup %s impossible : %s", bak_path, e)
            except OSError as e:
                log.warning("renommage .env.local en backup échoué : %s", e)
                bak_path = None

    log.info("env: chiffrement activé (%d clés)", len(env))
    return 200, {"ok": True, "encrypted": True, "keys": len(env), "backup": str(bak_path) if bak_path else None}


def disable_encryption() -> tuple[int, dict]:
    """Déchiffre .env.local.enc vers .env.local en clair, supprime le .enc.

    Utile pour exporter / migrer hors-poste. Le fichier clair reste sur disque,
    à l'utilisateur de le sécuriser après.
    """
    with _MUTATION_LOCK:
        if not is_encrypted_mode():
            return 409, {"error": "chiffrement non actif"}
        try:
            plaintext = read_encrypted_file(ENV_ENC_FILE)
        except CryptoError as e:
            return 500, {"error": f"déchiffrement échoué : {e}"}

        env = _parse_env_text(plaintext.decode("utf-8"))

        if ENV_FILE.exists():
            ts = time.strftime("%Y%m%d-%H%M%S")
            try:
                os.replace(ENV_FILE, ENV_FILE.with_suffix(ENV_FILE.suffix + f".bak.{ts}"))
            except OSError as e:
                log.warning("backup .env.local existant échoué : %s", e)

        body = "\n".join(f"{k}={v}" for k, v in sorted(env.items())) + "\n"
        ENV_FILE.write_text(body, encoding="utf-8")

        try:
            os.unlink(ENV_ENC_FILE)
        except OSError as e:
            log.warning("suppression .env.local.enc échouée : %s", e)

    log.info("env: chiffrement désactivé (%d clés)", len(env))
    return 200, {"ok": True, "encrypted": False, "keys": len(env)}


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
