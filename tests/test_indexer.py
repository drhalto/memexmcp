from __future__ import annotations

import sqlite3

import pytest

from memex.indexer import add_repo, rebuild_embeddings, suggest_repo_name
from memex.store import current_dim, open_db


class FailingEmbedder:
    dim = 4

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str], *, task: str = "document") -> list[list[float]]:
        del task
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("embed failed")
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def close(self) -> None:
        return None


def _seed_chunks(conn: sqlite3.Connection, repo_path: str, *, count: int) -> None:
    repo_id = conn.execute(
        "INSERT INTO repos (name, path, collection) VALUES (?, ?, ?)",
        ("repo", repo_path, "default"),
    ).lastrowid
    file_id = conn.execute(
        "INSERT INTO files (repo_id, rel_path, sha256, language, loc) VALUES (?, ?, ?, ?, ?)",
        (repo_id, "doc.txt", "sha", "txt", count),
    ).lastrowid
    for i in range(count):
        chunk_id = conn.execute(
            "INSERT INTO chunks (file_id, start_line, end_line, content) VALUES (?, ?, ?, ?)",
            (file_id, i + 1, i + 1, f"chunk {i + 1}"),
        ).lastrowid
        conn.execute(
            "INSERT INTO chunks_vec (rowid, embedding) VALUES (?, ?)",
            (chunk_id, sqlite3.Binary(bytes(12))),
        )
    conn.commit()


def test_suggest_repo_name_avoids_silent_collision(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMEX_HOME", str(tmp_path / "memex-home"))
    conn = open_db()

    first = tmp_path / "alpha" / "src"
    second = tmp_path / "beta" / "src"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    add_repo(conn, "src", first)

    assert suggest_repo_name(conn, second) == "src-2"
    with pytest.raises(ValueError, match="repo name 'src'"):
        add_repo(conn, "src", second)


def test_rebuild_embeddings_keeps_old_vectors_on_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMEX_HOME", str(tmp_path / "memex-home"))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    conn = open_db(dim=3)
    _seed_chunks(conn, str(repo_root), count=65)

    with pytest.raises(RuntimeError, match="embed failed"):
        rebuild_embeddings(conn, 4, embedder=FailingEmbedder())

    assert current_dim(conn) == 3
    assert conn.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[0] == 65
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'chunks_vec_rebuild'"
    ).fetchone()[0] == 0
