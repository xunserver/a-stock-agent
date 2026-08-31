"""Internal SQLite construction and migration support.

This module centralises connection defaults so every namespace starts with the
same safety and contention settings.  It is deliberately private: domain
stores remain responsible for their own schema and migrations.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path

Migration = Callable[[sqlite3.Connection], None]


def connect(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with the shared domain-store defaults."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    namespace: str,
    migrations: Sequence[Migration],
) -> None:
    """Apply ordered, idempotent migrations for one schema namespace.

    The namespace table lets independent stores share a file in the future
    without conflating their version histories.  A version is marked only
    after its migration has committed successfully.
    """
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                namespace TEXT PRIMARY KEY,
                version INTEGER NOT NULL
            )
            """
        )
        row = connection.execute(
            "SELECT version FROM _schema_migrations WHERE namespace = ?",
            (namespace,),
        ).fetchone()
        current = int(row["version"]) if row else 0

    for version, migration in enumerate(migrations, start=1):
        if version <= current:
            continue
        with connection:
            migration(connection)
            connection.execute(
                """
                INSERT INTO _schema_migrations (namespace, version)
                VALUES (?, ?)
                ON CONFLICT(namespace) DO UPDATE SET version = excluded.version
                """,
                (namespace, version),
            )
