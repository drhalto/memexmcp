"""Hybrid search: vec0 + FTS5, fused with Reciprocal Rank Fusion."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from memex.embedder import EmbedProvider, get_embedder
from memex.store import serialize_vec

RRF_K = 60
CANDIDATE_MULT = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchHit:
    repo: str
    collection: str
    rel_path: str
    start_line: int
    end_line: int
    content: str
    score: float
    vec_rank: int | None
    fts_rank: int | None


def _fts_query(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", text)
    return " OR ".join(tokens) if tokens else ""


def _repo_id(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM repos WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None


def _file_filters(
    repo_id: int | None,
    collection: str | None,
    language: str | None,
    path_glob: str | None,
) -> tuple[list[str], list[object], bool]:
    """Build WHERE clauses. Third return flag is True if any clause joins `repos`."""
    clauses: list[str] = []
    params: list[object] = []
    needs_repos_join = False
    if repo_id is not None:
        clauses.append("f.repo_id = ?")
        params.append(repo_id)
    if collection is not None:
        clauses.append("r.collection = ?")
        params.append(collection)
        needs_repos_join = True
    if language is not None:
        clauses.append("f.language = ?")
        params.append(language)
    if path_glob is not None:
        clauses.append("f.rel_path GLOB ?")
        params.append(path_glob)
    return clauses, params, needs_repos_join


def _vec_candidates(
    conn: sqlite3.Connection,
    query_vec: bytes,
    limit: int,
    *,
    repo_id: int | None = None,
    collection: str | None = None,
    language: str | None = None,
    path_glob: str | None = None,
) -> list[int]:
    clauses, fparams, needs_repos_join = _file_filters(repo_id, collection, language, path_glob)
    if not clauses:
        rows = conn.execute(
            "SELECT rowid FROM chunks_vec WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (query_vec, limit),
        ).fetchall()
        return [r["rowid"] for r in rows]
    over = max(limit * 5, 50)
    where = " AND ".join(clauses)
    joins = "JOIN chunks c ON c.id = v.rowid JOIN files f ON f.id = c.file_id"
    if needs_repos_join:
        joins += " JOIN repos r ON r.id = f.repo_id"
    sql = f"""
        SELECT v.rowid, v.distance
        FROM chunks_vec v
        {joins}
        WHERE v.embedding MATCH ? AND k = ? AND {where}
        ORDER BY v.distance
        LIMIT ?
    """
    rows = conn.execute(sql, (query_vec, over, *fparams, limit)).fetchall()
    return [r["rowid"] for r in rows]


def _fts_candidates(
    conn: sqlite3.Connection,
    fts_q: str,
    limit: int,
    *,
    repo_id: int | None = None,
    collection: str | None = None,
    language: str | None = None,
    path_glob: str | None = None,
) -> list[int]:
    if not fts_q:
        return []
    clauses, fparams, needs_repos_join = _file_filters(repo_id, collection, language, path_glob)
    if not clauses:
        sql = "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?"
        params: tuple = (fts_q, limit)
    else:
        joins = "JOIN chunks c ON c.id = fts.rowid JOIN files f ON f.id = c.file_id"
        if needs_repos_join:
            joins += " JOIN repos r ON r.id = f.repo_id"
        where = " AND ".join(clauses)
        sql = f"""
            SELECT fts.rowid
            FROM chunks_fts fts
            {joins}
            WHERE chunks_fts MATCH ? AND {where}
            ORDER BY fts.rank
            LIMIT ?
        """
        params = (fts_q, *fparams, limit)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    return [r["rowid"] for r in rows]


def _fuse(vec_ids: list[int], fts_ids: list[int]) -> dict[int, tuple[float, int | None, int | None]]:
    scores: dict[int, float] = {}
    vec_ranks: dict[int, int] = {}
    fts_ranks: dict[int, int] = {}
    for rank, rid in enumerate(vec_ids):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (RRF_K + rank + 1)
        vec_ranks[rid] = rank + 1
    for rank, rid in enumerate(fts_ids):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (RRF_K + rank + 1)
        fts_ranks[rid] = rank + 1
    return {rid: (s, vec_ranks.get(rid), fts_ranks.get(rid)) for rid, s in scores.items()}


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    repo: str | None = None,
    collection: str | None = None,
    k: int = 10,
    embedder: EmbedProvider | None = None,
    language: str | None = None,
    path_glob: str | None = None,
) -> list[SearchHit]:
    repo_id = _repo_id(conn, repo) if repo else None
    if repo and repo_id is None:
        raise ValueError(f"no repo named '{repo}'")

    close_embedder = False
    if embedder is None:
        embedder = get_embedder()
        close_embedder = True
    try:
        vecs = embedder.embed([query], task="query")
    finally:
        if close_embedder:
            embedder.close()
    query_vec = serialize_vec(vecs[0])

    n_candidates = k * CANDIDATE_MULT
    vec_ids = _vec_candidates(
        conn, query_vec, n_candidates,
        repo_id=repo_id, collection=collection, language=language, path_glob=path_glob,
    )
    fts_ids = _fts_candidates(
        conn, _fts_query(query), n_candidates,
        repo_id=repo_id, collection=collection, language=language, path_glob=path_glob,
    )

    fused = _fuse(vec_ids, fts_ids)
    if not fused:
        return []

    top_ids = sorted(fused.items(), key=lambda kv: -kv[1][0])[:k]
    id_list = [rid for rid, _ in top_ids]
    placeholders = ",".join("?" * len(id_list))
    rows = conn.execute(
        f"""
        SELECT c.id, r.name AS repo, r.collection, f.rel_path,
               c.start_line, c.end_line, c.content
        FROM chunks c
        JOIN files f ON f.id = c.file_id
        JOIN repos r ON r.id = f.repo_id
        WHERE c.id IN ({placeholders})
        """,
        id_list,
    ).fetchall()
    by_id = {r["id"]: r for r in rows}

    hits: list[SearchHit] = []
    for rid, (score, v_rank, f_rank) in top_ids:
        r = by_id.get(rid)
        if not r:
            continue
        hits.append(SearchHit(
            repo=r["repo"],
            collection=r["collection"],
            rel_path=r["rel_path"],
            start_line=r["start_line"],
            end_line=r["end_line"],
            content=r["content"],
            score=score,
            vec_rank=v_rank,
            fts_rank=f_rank,
        ))
    return hits
