"""Module extrait de server.py — ne pas éditer le script _split.py."""
from __future__ import annotations

import datetime as dt
import json
import logging
import logging.handlers
import os
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

from dashcore.config import (
    ROOT, CLAUDE_HOME, CLAUDE_JSON, CLAUDE_SETTINGS, BACKUPS_DIR, TEMPLATES_DIR, WORKSPACES_DIR,
    WORKSPACES_JSON, MCP_REGISTRY, ENV_FILE, LOGS_DIR,
    TEXT_EXTENSIONS, SAFE_ID, BAT_UNSAFE,
    PATH_UNSAFE, _MUTATION_LOCK, log,
    MCP_RECIPES_LOCAL_FILE, IS_WINDOWS,
)




def setup_logging(level: int = logging.INFO) -> None:
    """Initialise le logger avec console + fichier rotatif (5 MB × 5)."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log.setLevel(level)
    log.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    log.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "dashboard.log",
        maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s")
    )
    log.addHandler(file_handler)


class CorruptJsonError(ValueError):
    """Fichier JSON présent mais illisible (syntaxe / encodage).

    Levée par `read_json_strict` : un chemin lecture-modification-écriture
    ne doit JAMAIS repartir d'un défaut vide (sinon l'écriture suivante
    écrase la donnée réelle). `server._dispatch` la convertit en 409 avec
    un message explicite (aucune écriture effectuée).
    """

    def __init__(self, path: Path, detail: str):
        self.path = Path(path)
        self.detail = detail
        bak = self.path.with_suffix(self.path.suffix + ".bak")
        super().__init__(
            f"Fichier JSON illisible : {self.path} ({detail}). Aucune écriture "
            f"effectuée. Corrige le fichier ou restaure la sauvegarde {bak.name}."
        )


def read_json(path: Path, default):
    """Lecture tolérante : `default` si absent OU illisible (log warning).

    À réserver aux lectures seules. Pour lire-modifier-écrire, utiliser
    `read_json_strict` (cf. pitfalls : un défaut vide réécrit = perte de données).
    """
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning("JSON illisible, défaut utilisé : %s (%s)", path, e)
        return default


def read_json_strict(path: Path, default):
    """Comme `read_json` mais lève `CorruptJsonError` si le fichier existe
    et est illisible. `default` n'est renvoyé QUE si le fichier est absent."""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CorruptJsonError(path, str(e)) from e


def _json_file_is_valid(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8-sig"))
        return True
    except (OSError, ValueError):
        return False


def write_json(path: Path, data) -> None:
    """Écriture atomique (tmp + os.replace) avec rotation `.bak` sûre.

    - Le `.bak` n'est tourné QUE si le fichier courant est un JSON valide :
      un fichier corrompu n'écrase jamais la dernière sauvegarde saine.
    - Un fichier courant corrompu est préservé en `<nom>.corrupt-<ts>`
      avant d'être remplacé (rien n'est perdu, même via un appelant non
      strict).
    """
    with _MUTATION_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if _json_file_is_valid(path):
                backup = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup)
            else:
                ts = time.strftime("%Y%m%d-%H%M%S")
                keep = path.with_name(f"{path.name}.corrupt-{ts}")
                shutil.copy2(path, keep)
                log.warning("JSON corrompu préservé avant réécriture : %s", keep)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)


def resolve_cli(name: str) -> str:
    """Retourne le chemin absolu d'un binaire CLI ou son nom brut en fallback."""
    return shutil.which(name) or name


def git_cli() -> str:
    """Chemin de git, même hors du PATH.

    Git for Windows installé avec l'option « Git Bash seulement » n'est pas
    dans le PATH : un dashboard lancé par double-clic sur
    `start-dashboard.bat` ne le trouvait pas (« v2.4.0 ? », mises à jour
    impossibles) alors qu'il marche depuis Git Bash. On essaie alors les
    emplacements d'installation habituels avant de renvoyer « git ».
    """
    found = shutil.which("git")
    if found:
        return found
    if os.name == "nt":
        bases = [os.environ.get(k) for k in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            bases.append(os.path.join(local, "Programs"))
        for base in bases:
            if not base:
                continue
            cand = os.path.join(base, "Git", "cmd", "git.exe")
            if os.path.isfile(cand):
                return cand
    return "git"


def safe_path(path: str) -> bool:
    """Refuse les chemins avec caractères problématiques pour un shell Windows."""
    return bool(path) and not PATH_UNSAFE.search(path)


def safe_id(s: str) -> bool:
    return bool(SAFE_ID.match(s or ""))


def sanitize_bat(s: str) -> str:
    """Retire les chars qui cassent un .bat en contexte echo."""
    return BAT_UNSAFE.sub("", s or "").strip()


# Variables .env.local — implémentation déplacée dans dashcore/env_local.py
# Re-exports pour compat ascendante
from dashcore.env_local import (  # noqa: E402,F401
    load_env_local, set_env_var, delete_env_var, substitute_env,
    is_encrypted_mode, enable_encryption, disable_encryption, env_health,
    export_plain_text, strip_invisible,
)


def port_free(host: str, port: int) -> bool:
    # Hôte IPv6 (contient « : ») : socket AF_INET6, sinon le bind échoue toujours.
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_port(host: str, start: int) -> int:
    for p in range(start, start + 20):
        if port_free(host, p):
            return p
    raise RuntimeError(f"Aucun port libre entre {start} et {start+19}")


# launch_script / list_workspaces / cleanup_orphan_bats
# déplacés dans dashcore/workspace_io.py (re-exports en bas de fichier)


def parse_skill_frontmatter(skill_md: Path) -> dict:
    """Lit les clés name/description/model de la frontmatter YAML d'un SKILL.md."""
    meta = {}
    try:
        with skill_md.open("r", encoding="utf-8", errors="replace") as f:
            text = f.read(3000)
    except OSError:
        return meta
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    block = text[3:end]
    for line in block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def is_text_file(path: Path) -> bool:
    if path.name in (".gitignore", ".gitkeep", ".env", ".env.local"):
        return True
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return path.stat().st_size < 512 * 1024
    return False


def render_placeholders(text: str, vars: dict) -> str:
    out = text
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def apply_template(src_dir: Path, dst_dir: Path, vars: dict) -> list[str]:
    """Copie récursivement `src_dir` dans `dst_dir`, substitue les placeholders.
    Retourne la liste des fichiers créés (relative à dst_dir)."""
    created = []
    for entry in src_dir.rglob("*"):
        rel = entry.relative_to(src_dir)
        if rel.name == ".template.json":
            continue
        target = dst_dir / rel
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if is_text_file(entry):
            content = entry.read_text(encoding="utf-8")
            content = render_placeholders(content, vars)
            target.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(entry, target)
        created.append(str(rel))
    return created


# project_dir_for_path / resolve_ws_dir / validate_ws_path / write_launch_bat
# / workspace_stats / all_stats / sanity_check
# déplacés dans dashcore/workspace_io.py (re-exports en bas de fichier)


def _force_remove(func, path, *exc) -> None:
    """Handler rmtree : sur Windows, un fichier en lecture seule (typique des
    objets `.git/objects/...`) fait échouer os.unlink avec WinError 5. On
    retire le flag lecture seule et on réessaie l'opération qui a échoué."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _remove_dir_or_link(p: Path) -> None:
    """shutil.rmtree refuse un symlink/junction pointant sur un dossier.
    On tente unlink (symlink, junction, fichier) puis rmtree (vrai dossier).

    rmtree est appelé avec un handler qui neutralise le flag lecture seule
    (Windows : les objets d'un dépôt git imbriqué sont read-only et font
    échouer la suppression avec WinError 5)."""
    try:
        p.unlink()
        return
    except (IsADirectoryError, PermissionError, OSError):
        pass
    # onexc (Python 3.12+) remplace onerror (déprécié en 3.12). _force_remove
    # accepte *exc -> compatible avec les deux signatures.
    if sys.version_info >= (3, 12):
        shutil.rmtree(p, onexc=_force_remove)
    else:
        shutil.rmtree(p, onerror=_force_remove)


OPEN_TARGETS = {
    "claude-json": CLAUDE_JSON,
    "claude-settings": CLAUDE_SETTINGS,
    "root-claude-md": ROOT / "CLAUDE.md",
    "registry": MCP_REGISTRY,
    "env-local": ENV_FILE,
    "workspaces-json": WORKSPACES_JSON,
    "global-memory": ROOT / "memory",
    "mcp-recipes-local": MCP_RECIPES_LOCAL_FILE,
}


def open_target(key: str) -> tuple[int, dict]:
    if key.startswith("workspace-claude-md:"):
        ws_id = key.split(":", 1)[1]
        if not safe_id(ws_id):
            return 400, {"ok": False, "error": "id invalide"}
        p = resolve_ws_dir(ws_id) / "CLAUDE.md"
    elif key.startswith("workspace-dir:"):
        ws_id = key.split(":", 1)[1]
        if not safe_id(ws_id):
            return 400, {"ok": False, "error": "id invalide"}
        p = resolve_ws_dir(ws_id)
    elif key.startswith("workspace-removed:"):
        # Archives des modules retirés (.claude/.nebula-removed/), cf.
        # api_overlays.remove_overlay.
        ws_id = key.split(":", 1)[1]
        if not safe_id(ws_id):
            return 400, {"ok": False, "error": "id invalide"}
        p = resolve_ws_dir(ws_id) / ".claude" / ".nebula-removed"
    elif key.startswith("template:"):
        tpl_id = key.split(":", 1)[1]
        if not safe_id(tpl_id):
            return 400, {"ok": False, "error": "id invalide"}
        p = TEMPLATES_DIR / tpl_id
    elif key.startswith("skill-global:"):
        name = key.split(":", 1)[1]
        if not safe_id(name):
            return 400, {"ok": False, "error": "nom invalide"}
        p = CLAUDE_HOME / "skills" / name
    elif key.startswith("skill-ws:"):
        parts = key.split(":")
        if len(parts) != 3 or not safe_id(parts[1]) or not safe_id(parts[2]):
            return 400, {"ok": False, "error": "format : skill-ws:<ws_id>:<name>"}
        p = WORKSPACES_DIR / parts[1] / ".claude" / "skills" / parts[2]
    else:
        p = OPEN_TARGETS.get(key)
        if p is None:
            return 400, {"ok": False, "error": "cible inconnue"}

    if not p.exists():
        # Fichier absent : propose notepad pour les cas où on veut le créer
        if key == "env-local" and IS_WINDOWS:
            try:
                subprocess.Popen(["notepad", str(p)])
                return 200, {"ok": True, "message": f"Notepad ouvert (fichier sera créé au save) : {p}"}
            except OSError as e:
                return 500, {"ok": False, "error": f"Erreur : {e}"}
        return 404, {"ok": False, "error": f"Introuvable : {p}"}
    try:
        if IS_WINDOWS:
            try:
                os.startfile(str(p))  # noqa
            except OSError:
                # Pas d'association pour .env ou .local → fallback notepad
                subprocess.Popen(["notepad", str(p)])
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            if not shutil.which(opener):
                # Poste sans environnement graphique (serveur, conteneur) :
                # erreur claire plutôt qu'un 500 « No such file ».
                return 501, {"ok": False, "error": (
                    f"Ouverture impossible : « {opener} » introuvable sur ce système. "
                    f"Chemin : {p}")}
            subprocess.Popen([opener, str(p)])
        return 200, {"ok": True, "message": f"Ouvert : {p}"}
    except OSError as e:
        return 500, {"ok": False, "error": f"Erreur : {e}"}


def backup_claude_config() -> tuple[int, dict]:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    copied = []
    for name, src in [("claude.json", CLAUDE_JSON), ("settings.json", CLAUDE_SETTINGS)]:
        if src.exists():
            dst = BACKUPS_DIR / f"{stamp}-{name}"
            shutil.copy2(src, dst)
            copied.append(dst.name)
    if not copied:
        return 400, {"ok": False, "error": "Aucun fichier à sauvegarder"}
    return 200, {"ok": True, "message": "Sauvegardés : " + ", ".join(copied)}


def restore_backup(name: str) -> tuple[int, dict]:
    """Restaure un fichier de sauvegarde vers sa destination Claude.

    Réversibilité (lot D-3) : un backup auto de l'état courant est créé AVANT
    tout écrasement (via `backup_claude_config`) -- la restauration est donc
    annulable en restaurant le snapshot fraîchement créé.

    Périmètre identique à `backup_claude_config` : on ne restaure que les
    deux fichiers couverts par la sauvegarde (claude.json + settings.json).
    Le `name` doit correspondre à une entrée existante de `list_backups()`
    et se terminer par l'un des suffixes connus.
    """
    name = (name or "").strip()
    # Garde-fou anti-traversal : pas de séparateur de chemin, doit exister
    # dans le dossier de backups (et donc dedans, pas ailleurs).
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return 400, {"ok": False, "error": "nom de sauvegarde invalide"}

    src = BACKUPS_DIR / name
    try:
        # resolve() pour neutraliser tout ".." résiduel et confiner à BACKUPS_DIR.
        if BACKUPS_DIR.resolve() not in src.resolve().parents:
            return 400, {"ok": False, "error": "nom de sauvegarde invalide"}
    except OSError:
        return 400, {"ok": False, "error": "nom de sauvegarde invalide"}
    if not src.is_file():
        return 404, {"ok": False, "error": "sauvegarde introuvable"}

    # Mappe le suffixe du fichier de backup vers sa destination réelle.
    suffix_to_dst = {"-claude.json": CLAUDE_JSON, "-settings.json": CLAUDE_SETTINGS}
    dst = next((d for sfx, d in suffix_to_dst.items() if name.endswith(sfx)), None)
    if dst is None:
        return 400, {"ok": False, "error": "type de sauvegarde non restaurable"}

    # 1. Backup auto de l'état courant AVANT d'écraser (réversibilité).
    status, info = backup_claude_config()
    auto_backup = info.get("message") if status == 200 else None

    # 2. Restauration.
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as e:
        return 500, {"ok": False, "error": f"restauration impossible : {e}"}

    msg = f"Restauré : {dst.name}"
    return 200, {
        "ok": True,
        "message": msg,
        "restored": dst.name,
        "auto_backup": auto_backup,
    }


def list_backups() -> list[dict]:
    if not BACKUPS_DIR.exists():
        return []
    out = []
    for p in sorted(BACKUPS_DIR.iterdir(), reverse=True):
        if p.is_file():
            out.append({
                "name": p.name,
                "size": p.stat().st_size,
                "mtime": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
            })
    return out


# ─────────────────────────────────────────────────────────────────────────
# Re-exports : modules extraits, gardés ici pour compat ascendante.
# (Importer depuis le module dédié quand on écrit du nouveau code.)
# ─────────────────────────────────────────────────────────────────────────

from dashcore.journal import (  # noqa: E402,F401
    read_journal, append_journal, clear_journal, JOURNAL_ENTRY,
)
from dashcore.workspace_io import (  # noqa: E402,F401
    list_workspaces, cleanup_orphan_bats, project_dir_for_path,
    resolve_ws_dir, validate_ws_path, write_launch_bat,
    workspace_stats, all_stats, sanity_check, launch_script,
)


