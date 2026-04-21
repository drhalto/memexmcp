"""SQLite + sqlite-vec store. Dim-aware lazy schema + collections."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import sqlite_vec

from memex.config import load as load_config
from memex.paths import db_path

SCHEMA_VERSION = 1
ACTIVE_VEC_TABLE = "chunks_vec"
REBUILD_VEC_TABLE = "chunks_vec_rebuild"

_CORE_MIGRATIONS: dict[int, list[str]] = {
    1: [
        """
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            path TEXT NOT NULL,
            collection TEXT NOT NULL DEFAULT 'default',
            added_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_sync TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_repos_collection ON repos(collection)",
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
            rel_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            language TEXT,
            loc INTEGER,
            UNIQUE(repo_id, rel_path)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo_id)",
        "CREATE INDEX IF NOT EXISTS idx_files_language ON files(language)",
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            content TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id)",
        # Identifier-friendly FTS: unicode61 with underscore as a token char.
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content,
            content='chunks',
            content_rowid='id',
            tokenize='unicode61 tokenchars ''_'''
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END
        """,
        # Track the dim currently stored in chunks_vec so a dim switch can be detected.
        """
        CREATE TABLE IF NOT EXISTS vec_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            dim INTEGER NOT NULL
        )
        """,
    ],
}


def open_db(path: Path | str | None = None, *, dim: int | None = None) -> sqlite3.Connection:
    """Open/create the DB. chunks_vec is created lazily at the configured dim.

    If `dim` is not passed, it's read from config.json. On dim mismatch against
    an existing chunks_vec, we raise — the caller (GUI) drives the rebuild flow.
    """
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(p)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.row_factory = sqlite3.Row

    _migrate_core(conn)

    target_dim = dim if dim is not None else load_config().dim
    _ensure_vec_table(conn, target_dim)
    return conn


def _migrate_core(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in range(current + 1, SCHEMA_VERSION + 1):
        for stmt in _CORE_MIGRATIONS[version]:
            conn.execute(stmt)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()


def _ensure_vec_table(conn: sqlite3.Connection, dim: int) -> None:
    row = conn.execute("SELECT dim FROM vec_meta WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {ACTIVE_VEC_TABLE} USING vec0(embedding FLOAT[{dim}])"
        )
        # Delete chunks_vec rows when their backing chunk is deleted.
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_av AFTER DELETE ON chunks BEGIN
                DELETE FROM chunks_vec WHERE rowid = old.id;
            END
        """)
        conn.execute("INSERT INTO vec_meta (id, dim) VALUES (1, ?)", (dim,))
        conn.commit()
        return
    if row["dim"] != dim:
        raise DimMismatch(stored=row["dim"], requested=dim)


class DimMismatch(RuntimeError):
    """Raised when the requested embed dim doesn't match the stored vec table.

    The caller is expected to show a rebuild confirmation, then call
    `rebuild_vec_table(conn, new_dim)` to drop + recreate + re-embed.
    """

    def __init__(self, *, stored: int, requested: int) -> None:
        super().__init__(f"vec dim mismatch: stored={stored} requested={requested}")
        self.stored = stored
        self.requested = requested


def rebuild_vec_table(conn: sqlite3.Connection, new_dim: int) -> None:
    """Drop chunks_vec and recreate it at the new dim. Caller must re-embed after."""
    conn.execute(f"DROP TABLE IF EXISTS {ACTIVE_VEC_TABLE}")
    conn.execute(
        f"CREATE VIRTUAL TABLE {ACTIVE_VEC_TABLE} USING vec0(embedding FLOAT[{new_dim}])"
    )
    conn.execute("UPDATE vec_meta SET dim = ? WHERE id = 1", (new_dim,))
    conn.commit()


def prepare_rebuild_vec_table(conn: sqlite3.Connection, new_dim: int) -> None:
    """Create a scratch vec table for a safe dim switch rebuild."""
    conn.execute(f"DROP TABLE IF EXISTS {REBUILD_VEC_TABLE}")
    conn.execute(
        f"CREATE VIRTUAL TABLE {REBUILD_VEC_TABLE} USING vec0(embedding FLOAT[{new_dim}])"
    )
    conn.commit()


def finalize_rebuild_vec_table(conn: sqlite3.Connection, new_dim: int) -> None:
    """Swap in the scratch vec table after it has been fully populated."""
    try:
        conn.execute("BEGIN")
        conn.execute(f"DROP TABLE IF EXISTS {ACTIVE_VEC_TABLE}")
        conn.execute(
            f"CREATE VIRTUAL TABLE {ACTIVE_VEC_TABLE} USING vec0(embedding FLOAT[{new_dim}])"
        )
        conn.execute(
            f"INSERT INTO {ACTIVE_VEC_TABLE}(rowid, embedding) "
            f"SELECT rowid, embedding FROM {REBUILD_VEC_TABLE}"
        )
        conn.execute(f"DROP TABLE {REBUILD_VEC_TABLE}")
        conn.execute("UPDATE vec_meta SET dim = ? WHERE id = 1", (new_dim,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def discard_rebuild_vec_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"DROP TABLE IF EXISTS {REBUILD_VEC_TABLE}")
    conn.commit()


def serialize_vec(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def current_dim(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT dim FROM vec_meta WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("vec_meta not initialized")
    return row["dim"]
