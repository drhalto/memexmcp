"""Walk a source, chunk & embed modified files, upsert into the store."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from memex.chunker import ALLOWED_SUFFIXES, MAX_FILE_BYTES, chunk_file
from memex.embedder import EmbedBadInput, EmbedProvider, get_embedder
from memex.store import (
    REBUILD_VEC_TABLE,
    discard_rebuild_vec_table,
    finalize_rebuild_vec_table,
    prepare_rebuild_vec_table,
    serialize_vec,
)

_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "dist", "build", "out", "target",
    "__pycache__", ".venv", "venv", "env",
    ".next", ".nuxt", ".svelte-kit", ".turbo", ".cache",
    "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".memex", ".codexref", ".idea", ".vscode",
    "vendor",
})

_SKIP_FILE_NAMES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "uv.lock", "poetry.lock", "Pipfile.lock",
    "Cargo.lock", "go.sum", "composer.lock",
})


# done: files processed so far (includes unchanged/skipped), total: files scanned,
# current: rel path of the most recent file. Callers use this to drive a bar.
ProgressCb = Callable[[int, int, str], None]


@dataclass(frozen=True, slots=True, kw_only=True)
class SyncStats:
    files_scanned: int = 0
    files_indexed: int = 0
    files_partial: int = 0
    files_unchanged: int = 0
    files_skipped: int = 0
    files_purged: int = 0
    chunks_written: int = 0


def _language_of(path: Path) -> str | None:
    suffix = path.suffix.lower()
    return suffix[1:] if suffix in ALLOWED_SUFFIXES else None


def _iter_source_files(root: Path):
    if root.is_file():
        if root.suffix.lower() in ALLOWED_SUFFIXES and root.name not in _SKIP_FILE_NAMES:
            yield root
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.name in _SKIP_FILE_NAMES:
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        yield path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_repo_name(path: Path) -> str:
    return path.resolve().name or path.drive.rstrip(":\\") or "root"


def _same_path(left: str | Path, right: str | Path) -> bool:
    return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(str(Path(right).resolve()))


def suggest_repo_name(conn: sqlite3.Connection, path: Path) -> str:
    base = _default_repo_name(path)
    candidate = base
    suffix = 2
    while True:
        row = conn.execute("SELECT path FROM repos WHERE name = ?", (candidate,)).fetchone()
        if row is None or _same_path(row["path"], path):
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def add_repo(
    conn: sqlite3.Connection,
    name: str,
    path: Path,
    *,
    collection: str = "default",
) -> int:
    abs_path = str(path.resolve())
    row = conn.execute("SELECT id, path FROM repos WHERE name = ?", (name,)).fetchone()
    if row and not _same_path(row["path"], abs_path):
        raise ValueError(f"repo name '{name}' is already used by {row['path']}")
    cur = conn.execute(
        "INSERT INTO repos (name, path, collection) VALUES (?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET path = excluded.path, collection = excluded.collection "
        "RETURNING id",
        (name, abs_path, collection),
    )
    row = cur.fetchone()
    conn.commit()
    return row[0]


def remove_repo(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("SELECT id FROM repos WHERE name = ?", (name,))
    row = cur.fetchone()
    if not row:
        return False
    # vec0 rows aren't FK'd — wipe explicitly.
    conn.execute(
        "DELETE FROM chunks_vec WHERE rowid IN ("
        " SELECT c.id FROM chunks c JOIN files f ON c.file_id = f.id WHERE f.repo_id = ?)",
        (row["id"],),
    )
    conn.execute("DELETE FROM repos WHERE id = ?", (row["id"],))
    conn.commit()
    return True


def sync_repo(
    conn: sqlite3.Connection,
    repo_id: int,
    *,
    embedder: EmbedProvider | None = None,
    progress_cb: ProgressCb | None = None,
) -> SyncStats:
    repo_row = conn.execute("SELECT path FROM repos WHERE id = ?", (repo_id,)).fetchone()
    if not repo_row:
        raise ValueError(f"repo_id {repo_id} not found")
    root = Path(repo_row["path"])
    if not root.exists():
        raise FileNotFoundError(f"source path missing: {root}")

    close_embedder = False
    if embedder is None:
        embedder = get_embedder()
        close_embedder = True

    # Two-pass so progress_cb has a real total to report against.
    all_files = list(_iter_source_files(root))
    total = len(all_files)

    scanned = indexed = partial = unchanged = skipped = purged = chunks_written = 0
    seen_rel_paths: set[str] = set()

    try:
        for i, path in enumerate(all_files, start=1):
            scanned += 1
            if root.is_file():
                rel = path.name
            else:
                rel = str(path.relative_to(root)).replace("\\", "/")
            seen_rel_paths.add(rel)

            if progress_cb:
                progress_cb(i, total, rel)

            try:
                data = path.read_bytes()
            except OSError:
                skipped += 1
                continue
            if len(data) > MAX_FILE_BYTES:
                skipped += 1
                continue

            sha = _sha256(data)
            existing = conn.execute(
                "SELECT id, sha256 FROM files WHERE repo_id = ? AND rel_path = ?",
                (repo_id, rel),
            ).fetchone()
            if existing and existing["sha256"] == sha:
                unchanged += 1
                continue

            chunks = chunk_file(path)
            if not chunks:
                skipped += 1
                continue

            vectors = embedder.embed([c.content for c in chunks], task="document")
            pairs = [(c, v) for c, v in zip(chunks, vectors, strict=True) if v is not None]
            if not pairs:
                skipped += 1
                continue

            # Partial: store what we got, but mark sha empty so next sync retries.
            is_partial = len(pairs) < len(chunks)
            stored_sha = "" if is_partial else sha

            content_str = data.decode("utf-8", errors="replace")
            loc = content_str.count("\n") + 1 if path.suffix.lower() not in {".pdf", ".docx"} else None

            if existing:
                conn.execute("DELETE FROM chunks WHERE file_id = ?", (existing["id"],))
                conn.execute(
                    "UPDATE files SET sha256 = ?, language = ?, loc = ? WHERE id = ?",
                    (stored_sha, _language_of(path), loc, existing["id"]),
                )
                file_id = existing["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO files (repo_id, rel_path, sha256, language, loc) VALUES (?, ?, ?, ?, ?)",
                    (repo_id, rel, stored_sha, _language_of(path), loc),
                )
                file_id = cur.lastrowid

            for chunk, vec in pairs:
                cur = conn.execute(
                    "INSERT INTO chunks (file_id, start_line, end_line, content) VALUES (?, ?, ?, ?)",
                    (file_id, chunk.start_line, chunk.end_line, chunk.content),
                )
                conn.execute(
                    "INSERT INTO chunks_vec (rowid, embedding) VALUES (?, ?)",
                    (cur.lastrowid, serialize_vec(vec)),
                )
                chunks_written += 1

            if is_partial:
                partial += 1
            else:
                indexed += 1
            conn.commit()

        # Purge files that vanished from disk.
        existing_rels = {
            r["rel_path"] for r in conn.execute(
                "SELECT rel_path FROM files WHERE repo_id = ?", (repo_id,)
            ).fetchall()
        }
        for rel in existing_rels - seen_rel_paths:
            conn.execute("DELETE FROM files WHERE repo_id = ? AND rel_path = ?", (repo_id, rel))
            purged += 1

        conn.execute(
            "UPDATE repos SET last_sync = ? WHERE id = ?",
            (datetime.now(UTC).isoformat(timespec="seconds"), repo_id),
        )
        conn.commit()
    finally:
        if close_embedder:
            embedder.close()

    return SyncStats(
        files_scanned=scanned,
        files_indexed=indexed,
        files_partial=partial,
        files_unchanged=unchanged,
        files_skipped=skipped,
        files_purged=purged,
        chunks_written=chunks_written,
    )


def reembed_all(
    conn: sqlite3.Connection,
    *,
    embedder: EmbedProvider | None = None,
    progress_cb: ProgressCb | None = None,
) -> int:
    """Re-embed every chunk already in the DB. Used after a dim switch.

    Assumes `chunks_vec` was already recreated at the new dim via
    `store.rebuild_vec_table`; this fills it back in from `chunks.content`.
    Returns total chunks re-embedded.
    """
    close_embedder = False
    if embedder is None:
        embedder = get_embedder()
        close_embedder = True

    try:
        rows = conn.execute("SELECT id, content FROM chunks ORDER BY id").fetchall()
        total = len(rows)
        done = 0
        BATCH = 64
        for start in range(0, total, BATCH):
            batch = rows[start : start + BATCH]
            vectors = embedder.embed([r["content"] for r in batch], task="document")
            for row, vec in zip(batch, vectors, strict=True):
                if vec is None:
                    continue
                conn.execute(
                    "INSERT INTO chunks_vec (rowid, embedding) VALUES (?, ?)",
                    (row["id"], serialize_vec(vec)),
                )
            done += len(batch)
            conn.commit()
            if progress_cb:
                progress_cb(done, total, f"re-embedding chunk {done}/{total}")
        return done
    finally:
        if close_embedder:
            embedder.close()


def rebuild_embeddings(
    conn: sqlite3.Connection,
    new_dim: int,
    *,
    embedder: EmbedProvider | None = None,
    progress_cb: ProgressCb | None = None,
) -> int:
    """Rebuild vectors at a new dim without discarding the old table first."""
    close_embedder = False
    if embedder is None:
        embedder = get_embedder()
        close_embedder = True

    rows = conn.execute("SELECT id, content FROM chunks ORDER BY id").fetchall()
    total = len(rows)
    done = 0
    batch_size = 64

    prepare_rebuild_vec_table(conn, new_dim)
    try:
        for start in range(0, total, batch_size):
            batch = rows[start : start + batch_size]
            vectors = embedder.embed([r["content"] for r in batch], task="document")
            for row, vec in zip(batch, vectors, strict=True):
                if vec is None:
                    raise EmbedBadInput(f"provider rejected stored chunk id={row['id']}")
                conn.execute(
                    f"INSERT INTO {REBUILD_VEC_TABLE} (rowid, embedding) VALUES (?, ?)",
                    (row["id"], serialize_vec(vec)),
                )
            done += len(batch)
            conn.commit()
            if progress_cb:
                progress_cb(done, total, f"re-embedding chunk {done}/{total}")
        finalize_rebuild_vec_table(conn, new_dim)
        return total
    except Exception:
        discard_rebuild_vec_table(conn)
        raise
    finally:
        if close_embedder:
            embedder.close()
