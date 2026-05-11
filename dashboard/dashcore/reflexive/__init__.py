"""Sous-package Reflexive — observation, scoring, propositions.

Conçu pour être chargé paresseusement : importer ce package n'ouvre pas la DB.
La connexion est établie au premier appel via `reflexive.db.connect()`.

Stdlib uniquement (sqlite3).
"""
from __future__ import annotations

from dashcore.reflexive.db import connect, ensure_initialized, DB_PATH

__all__ = ["connect", "ensure_initialized", "DB_PATH"]
