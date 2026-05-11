"""Connexion SQLite Reflexive — WAL, foreign_keys, busy_timeout.

Init paresseuse : la DB n'est créée qu'au premier appel à `connect()` ou
`ensure_initialized()`. Une connexion fraîche est ouverte par appel
(cohérent avec le ThreadingHTTPServer de Nebula). Le mode WAL permet
plusieurs lecteurs concurrents + un écrivain sans verrouiller la base.

Usage typique :
    with connect() as conn:
        rows = conn.execute("SELECT * FROM interactions").fetchall()
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from dashcore.config import DASHBOARD_DIR, log
from dashcore.reflexive.schema import migrate

DB_PATH: Path = DASHBOARD_DIR / "data" / "reflexive.db"

_init_lock = threading.Lock()
_initialized = False


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")


def ensure_initialized() -> None:
    """Crée le fichier + applique les migrations si nécessaire. Idempotent."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)
        try:
            _configure(conn)
            version = migrate(conn)
            log.info("Reflexive DB prête (%s) — schéma v%d", DB_PATH, version)
        finally:
            conn.close()
        _initialized = True


@contextmanager
def connect():
    """Context manager : ouvre une connexion fraîche, ferme à la sortie."""
    ensure_initialized()
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        _configure(conn)
        yield conn
    finally:
        conn.close()
