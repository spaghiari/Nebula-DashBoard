"""Constantes et chemins partagés. Aucune logique ici."""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 4777

ROOT = Path(r"C:\claude-workspace")
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
WORKSPACES_JSON = DASHBOARD_DIR / "data" / "workspaces.json"
MCP_REGISTRY = ROOT / "mcp" / "registry.json"
ENV_FILE = ROOT / ".env.local"
LOGS_DIR = ROOT / "logs"

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
}

ALLOWED_TRANSPORTS = ("stdio", "http", "sse")
ALLOWED_STATUS = ("connecté", "disponible", "à configurer", "désactivé")

_MUTATION_LOCK = threading.Lock()
log = logging.getLogger("dashboard")
