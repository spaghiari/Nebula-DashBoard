"""Schéma SQLite Reflexive + migrations versionnées.

Versionning via `PRAGMA user_version`. Toute évolution future ajoute une étape
dans `_MIGRATIONS` ; `migrate()` applique les étapes manquantes dans une
transaction.
"""
from __future__ import annotations

import sqlite3

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS interactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id    TEXT NOT NULL,
    session_id      TEXT,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    task_summary    TEXT,
    tools_used      TEXT,
    files_touched   TEXT,
    outcome         TEXT CHECK(outcome IN ('success','partial','failure','unknown')),
    self_confidence REAL,
    user_signal     TEXT
);

CREATE TABLE IF NOT EXISTS evals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id  INTEGER NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
    evaluated_at    TEXT NOT NULL,
    correctness     INTEGER,
    efficiency      INTEGER,
    alignment       INTEGER,
    learning        INTEGER,
    total           INTEGER GENERATED ALWAYS AS (correctness+efficiency+alignment+learning) STORED,
    flags           TEXT,
    justification   TEXT
);

CREATE TABLE IF NOT EXISTS proposals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id      TEXT,
    created_at        TEXT NOT NULL,
    path              TEXT NOT NULL,
    title             TEXT,
    target            TEXT,
    status            TEXT CHECK(status IN ('pending','applied','rejected','reverted')),
    applied_at        TEXT,
    rejection_reason  TEXT,
    evidence_count    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skill_versions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name           TEXT NOT NULL,
    workspace_id         TEXT,
    version              INTEGER NOT NULL,
    applied_proposal_id  INTEGER REFERENCES proposals(id),
    applied_at           TEXT NOT NULL,
    UNIQUE(skill_name, workspace_id, version)
);

CREATE TABLE IF NOT EXISTS measurement_plans (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id          INTEGER NOT NULL REFERENCES proposals(id),
    criteria             TEXT NOT NULL,
    threshold_dimension  TEXT NOT NULL,
    threshold_value      REAL NOT NULL,
    sample_size          INTEGER NOT NULL,
    status               TEXT CHECK(status IN ('active','met','failed')),
    created_at           TEXT NOT NULL,
    resolved_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_interactions_workspace ON interactions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_interactions_started   ON interactions(started_at);
CREATE INDEX IF NOT EXISTS idx_evals_total            ON evals(total);
CREATE INDEX IF NOT EXISTS idx_proposals_status      ON proposals(status);
"""


def _apply_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_V1)


# Liste ordonnée des migrations : index = version cible. Ajouter au bout.
_MIGRATIONS = [_apply_v1]

CURRENT_VERSION = len(_MIGRATIONS)


def migrate(conn: sqlite3.Connection) -> int:
    """Applique toutes les migrations manquantes. Retourne la nouvelle version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= CURRENT_VERSION:
        return current
    for i in range(current, CURRENT_VERSION):
        with conn:
            _MIGRATIONS[i](conn)
            conn.execute(f"PRAGMA user_version = {i + 1}")
    return CURRENT_VERSION
