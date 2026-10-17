"""Constantes et chemins partagés + lecture des variables d'environnement.

Aucune logique métier ici : seulement des valeurs, résolues une fois à
l'import. Variables d'environnement reconnues (toutes optionnelles, défaut =
comportement historique) :

- `ATELIER_ROOT`     : racine de l'installation (défaut : parent de `dashboard/`).
- `NEBULA_DATA_DIR`  : dossier des données utilisateur/runtime (défaut :
                       `<ROOT>/dashboard/data`).
- `NEBULA_HOST`      : hôte d'écoute (défaut : 127.0.0.1, loopback).
- `NEBULA_PORT`      : port d'écoute (défaut : 4777 ; `--port` prime).
- `NEBULA_ALLOWED_HOSTS` : noms supplémentaires acceptés dans l'en-tête Host
                       (liste séparée par des virgules, sans port).
"""
from __future__ import annotations

import ipaddress
import logging
import os
import re
import sys
import threading
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

# Messages de configuration à afficher au démarrage (valeur d'env invalide...).
CONFIG_WARNINGS: list[str] = []


def _env_port(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if 1 <= value <= 65535:
        return value
    CONFIG_WARNINGS.append(
        f"{name}={raw!r} invalide (entier 1-65535 attendu) : port {default} utilisé")
    return default


def is_loopback_host(host: str) -> bool:
    """True si `host` (nom ou IP, crochets IPv6 tolérés) désigne la boucle locale."""
    h = (host or "").strip().strip("[]").lower()
    if h == "localhost":
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


# --- Réseau -----------------------------------------------------------------
DEFAULT_HOST = "127.0.0.1"
HOST = (os.environ.get("NEBULA_HOST") or "").strip() or DEFAULT_HOST
DEFAULT_PORT = _env_port("NEBULA_PORT", 4777)
# Noms acceptés en plus de 127.0.0.1 / localhost / HOST dans l'en-tête Host
# (anti DNS-rebinding, cf. server.Handler._allowed_hosts).
EXTRA_ALLOWED_HOSTS = tuple(
    h.strip().lower()
    for h in (os.environ.get("NEBULA_ALLOWED_HOSTS") or "").split(",")
    if h.strip()
)
for _h in EXTRA_ALLOWED_HOSTS:
    # « nom:port » ne correspondra jamais (le port d'écoute est ajouté) :
    # on le signale au lieu d'ignorer l'entrée en silence. Les IPv6 brutes
    # (plusieurs « : ») restent acceptées.
    if _h.count(":") == 1 and not _h.startswith("["):
        CONFIG_WARNINGS.append(
            f"NEBULA_ALLOWED_HOSTS : « {_h} » contient un port, indique le nom seul")

# ROOT = racine de l'installation Nebula (parent du dossier `dashboard/`).
# Auto-détecté à partir de l'emplacement de ce fichier : <ROOT>/dashboard/dashcore/config.py
# Override possible via la variable d'env ATELIER_ROOT (tests, installation déportée).
ROOT = Path(os.environ.get("ATELIER_ROOT") or Path(__file__).resolve().parents[2])
USER_HOME = Path.home()
CLAUDE_HOME = USER_HOME / ".claude"
CLAUDE_JSON = USER_HOME / ".claude.json"
CLAUDE_SETTINGS = CLAUDE_HOME / "settings.json"
CLAUDE_PROJECTS = CLAUDE_HOME / "projects"
BACKUPS_DIR = ROOT / "backups"
JOURNAL_FILE = ROOT / "memory" / "journal.md"
TEMPLATES_DIR = ROOT / "templates"

TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts",
    ".sh", ".bat", ".ps1", ".html", ".css", ".cfg", ".ini", ".toml",
    ".gitignore", ".env",
}
DASHBOARD_DIR = ROOT / "dashboard"
WORKSPACES_DIR = ROOT / "workspaces"
SCRIPTS_DIR = ROOT / "scripts"
SNIPPETS_DIR = ROOT / "memory" / "snippets"
MCP_REGISTRY = ROOT / "mcp" / "registry.json"
ENV_FILE = ROOT / ".env.local"
ENV_ENC_FILE = ROOT / ".env.local.enc"
LOGS_DIR = ROOT / "logs"

# --- Données utilisateur / runtime (déplaçables via NEBULA_DATA_DIR) ---------
_data_env = (os.environ.get("NEBULA_DATA_DIR") or "").strip()
DATA_DIR = Path(os.path.expanduser(_data_env)).resolve() if _data_env else DASHBOARD_DIR / "data"
DATA_DIR_IS_CUSTOM = bool(_data_env)
WORKSPACES_JSON = DATA_DIR / "workspaces.json"
UI_STATE_FILE = DATA_DIR / "ui_state.json"
MCP_SYNC_STATE_FILE = DATA_DIR / "mcp_sync_state.json"
ACTIVE_SESSIONS_FILE = DATA_DIR / "active_sessions.json"
MCP_RECIPES_LOCAL_FILE = DATA_DIR / "mcp_recipes.local.json"
SKILLS_LIBRARY_DIR = DATA_DIR / "skills-library"
# Catalogue de recettes LIVRÉ avec le code (versionné) : reste dans le dépôt.
MCP_RECIPES_FILE = DASHBOARD_DIR / "data" / "mcp_recipes.json"
# Écrit par des hooks externes à un chemin fixe (`dashboard/data/...`) : non
# déplacé par NEBULA_DATA_DIR, sinon Nebula ne lirait plus ce qu'ils écrivent.
HOOK_ERRORS_LOG = DASHBOARD_DIR / "data" / "hook_errors.log"

SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")
SAFE_PLUGIN_SPEC = re.compile(r"^[a-zA-Z0-9@/_.-]{1,120}$")
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
BAT_UNSAFE = re.compile(r'[&|<>^"%\r\n]')
PATH_UNSAFE = re.compile(r'["\r\n]')
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".ico":  "image/x-icon",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
    ".woff2": "font/woff2",
    ".woff":  "font/woff",
}

ALLOWED_TRANSPORTS = ("stdio", "http", "sse")
ALLOWED_STATUS = ("connecté", "disponible", "à configurer", "désactivé")

# --- Dépôt amont (auto-update) ------------------------------------------------
# Dépôt public du projet (liens « Voir le projet », README, problèmes, commits
# de l'écran des mises à jour) : toujours GitHub, quel que soit le remote local.
PUBLIC_REPO_URL = "https://github.com/spaghiari/Nebula-DashBoard"
# Bascule de l'ancien GitLab vers GitHub : un clone dont `origin` pointe encore
# vers l'ancien dépôt est réorienté vers le nouveau avant tout fetch/pull
# (cf. system_update._migrate_origin_remote). Variantes https/ssh, avec ou
# sans `.git`, reconnues ; tout autre `origin` (fork, miroir) est laissé tel quel.
LEGACY_ORIGIN_URL = "https://git.exemple.lan/erti/claude-dashboard.git"
ORIGIN_URL = PUBLIC_REPO_URL + ".git"

# Message renvoyé par les actions qui ouvrent une console Windows (cmd).
WINDOWS_ONLY_MSG = ("Fonction disponible uniquement sous Windows (ouverture d'une "
                    "console cmd) : lance `claude` depuis un terminal dans le dossier du workspace.")

# --- Adoption groupée (inspection d'un dossier parent) -----------------------
# Fichiers / dossiers dont la présence fait d'un sous-dossier un projet
# candidat. Suffixes : fichiers de solution .NET (nom libre).
PROJECT_SIGNAL_NAMES = (
    "CLAUDE.md", ".claude", ".mcp.json", ".git", "package.json", "pyproject.toml",
    "requirements.txt", "setup.py", "Cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "build.gradle.kts", "composer.json", "Gemfile",
    "CMakeLists.txt", "Makefile", "deno.json",
)
PROJECT_SIGNAL_SUFFIXES = (".sln", ".csproj")
# Signaux propres à Claude Code (badge dédié dans la liste).
PROJECT_CLAUDE_SIGNALS = ("CLAUDE.md", ".claude", ".mcp.json")
# Jamais candidats (en plus des dossiers cachés, préfixe `.`).
PARENT_SCAN_IGNORED = frozenset({
    "node_modules", "__pycache__", "venv", "site-packages",
    "$recycle.bin", "system volume information",
})
PARENT_SCAN_MAX_CANDIDATES = 200
# Garde-fou de coût : nombre maximal de dossiers listés pendant une inspection.
PARENT_SCAN_MAX_VISITED = 2000

# --- Sélecteur de dossier natif (dashcore/folder_picker.py) ------------------
FOLDER_PICKER_TIMEOUT = 300  # secondes : au-delà, le dialogue est abandonné

# --- Module claude-team (dashcore/api_team.py) --------------------------------
# Capacités abstraites du manifeste `.claude/team.json` -> outils Claude Code
# du frontmatter généré. Ordre stable (celui des capacités de l'agent, puis
# celui de ces tuples), dédupliqué à la génération.
CAPABILITY_TOOLS = {
    "filesystem": ("Read", "Glob", "Grep"),
    "code_exec":  ("Bash",),
    "repo":       ("Bash",),
    "web_search": ("WebSearch", "WebFetch"),
    "knowledge":  ("Read", "Grep"),
    "eval_runner": ("Bash", "Read"),
}
# Outils d'écriture ajoutés quand l'agent n'est pas `read_only`.
CAPABILITY_WRITE_TOOLS = {
    "filesystem": ("Edit", "Write"),
}
# Alias de modèle acceptés dans le frontmatter Claude Code (`model:`).
TEAM_MODEL_ALIASES = ("sonnet", "opus", "haiku")
# Marqueur en tête de corps d'un agent généré : seul un fichier qui le porte
# peut être réécrit par l'option `regenerate` (jamais un agent édité à la main).
TEAM_GENERATED_MARKER = "<!-- generated by nebula claude-team -->"
# Statuts reconnus dans les registres du module self-improving (compteurs de
# l'onglet « Amélioration »).
REGISTER_STATUSES = ("IDEAS", "VALIDATED", "IN PROGRESS", "DONE", "TODO",
                     "BACKLOG", "ABANDONED", "REJECTED")

_MUTATION_LOCK = threading.RLock()
log = logging.getLogger("dashboard")
