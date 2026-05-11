"""Helpers partagés par les 3 hooks Reflexive.

Règle d'or : un hook NE DOIT JAMAIS faire échouer la session Claude Code.
Toute exception est silencieusement loggée puis ravalée.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path

# Le hook est appelé depuis un workspace, on doit donc retrouver Nebula par
# le chemin du script lui-même.
ROOT = Path(__file__).resolve().parents[4]
DB_PATH = ROOT / "dashboard" / "data" / "reflexive.db"
ERR_LOG = ROOT / "dashboard" / "data" / "reflexive_hook_errors.log"
WORKSPACES_JSON = ROOT / "dashboard" / "data" / "workspaces.json"

HOOK_TIMEOUT_S = 5


def log_error(where: str, exc: BaseException) -> None:
    try:
        ERR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ERR_LOG.open("a", encoding="utf-8") as f:
            ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            f.write(f"[{ts}] {where}: {exc!r}\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass  # On ne fait littéralement rien si même le log échoue.


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_payload() -> dict:
    """Claude Code envoie le payload du hook en JSON sur stdin."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception as exc:
        log_error("read_payload", exc)
        return {}


def workspace_id_for_cwd() -> str | None:
    """Retrouve l'id du workspace dont le `path` correspond au cwd courant."""
    try:
        cwd = Path(os.getcwd()).resolve()
        data = json.loads(WORKSPACES_JSON.read_text(encoding="utf-8"))
        for w in data.get("workspaces", []):
            wp = Path(w.get("path", "")).resolve()
            try:
                cwd.relative_to(wp)
                return w.get("id")
            except ValueError:
                continue
    except Exception as exc:
        log_error("workspace_id_for_cwd", exc)
    return None


@contextmanager
def db_conn():
    """Connexion SQLite avec timeout strict. Yield None si échec."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=HOOK_TIMEOUT_S)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as exc:
        log_error("db_conn", exc)
        yield None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
