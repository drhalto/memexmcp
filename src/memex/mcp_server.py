"""FastMCP stdio server exposing MemexMCP to any MCP-aware client."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from memex.embedder import EmbedProvider, get_embedder
from memex.search import search as do_search
from memex.store import open_db

mcp = FastMCP("memex")

_embedder: EmbedProvider | None = None


def _emb() -> EmbedProvider:
    global _embedder
    if _embedder is None:
        _embedder = get_embedder()
    return _embedder


def _file_filters(
    repo_id: int | None,
    collection: str | None,
    language: str | None,
    path_glob: str | None,
) -> tuple[list[str], list[Any], bool]:
    clauses: list[str] = []
    params: list[Any] = []
    needs_repos = False
    if repo_id is not None:
        clauses.append("f.repo_id = ?")
        params.append(repo_id)
    if collection is not None:
        clauses.append("r.collection = ?")
        params.append(collection)
        needs_repos = True
    if language is not None:
        clauses.append("f.language = ?")
        params.append(language)
    if path_glob is not None:
        clauses.append("f.rel_path GLOB ?")
        params.append(path_glob)
    return clauses, params, needs_repos


def _resolve_repo_file(
    conn: sqlite3.Connection, repo: str, path: str
) -> tuple[Path | None, str | None]:
    row = conn.execute("SELECT path FROM repos WHERE name = ?", (repo,)).fetchone()
    if not row:
        return None, f"no repo named '{repo}'"
    root = Path(row["path"])
    if root.is_file() and path not in {"", ".", root.name}:
        return None, f"not a file: {path}"
    abs_path = root / path if root.is_dir() else root
    try:
        abs_path.resolve().relative_to(root.resolve() if root.is_dir() else root.parent.resolve())
    except ValueError:
        return None, "path escapes repo root"
    if not abs_path.is_file():
        return None, f"not a file: {path}"
    return abs_path, None


def _literal_fts_query(pattern: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", pattern)
    return " AND ".join(f'"{t}"*' for t in tokens) if tokens else ""


def _indexed_file_rows(conn: sqlite3.Connection, repo: str, path: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT c.start_line, c.end_line, c.content
        FROM chunks c
        JOIN files f ON f.id = c.file_id
        JOIN repos r ON r.id = f.repo_id
        WHERE r.name = ? AND f.rel_path = ?
        ORDER BY c.start_line, c.end_line, c.id
        """,
        (repo, path),
    ).fetchall()


def _format_indexed_rows(rows: list[sqlite3.Row], path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return "\n\n".join(f"[page {r['start_line']}]\n{r['content']}" for r in rows)
    return "\n\n".join(r["content"] for r in rows)


def _indexed_file_slice(
    conn: sqlite3.Connection,
    repo: str,
    path: str,
    *,
    start: int,
    end: int,
) -> dict[str, Any] | None:
    rows = _indexed_file_rows(conn, repo, path)
    if not rows:
        return None
    total = max(r["end_line"] for r in rows)
    s = max(1, start)
    e = min(total, end)
    content_rows = [r for r in rows if r["end_line"] >= s and r["start_line"] <= e]
    return {
        "repo": repo,
        "path": path,
        "start_line": s,
        "end_line": e,
        "total_lines": total,
        "content": _format_indexed_rows(content_rows, path),
    }


@mcp.tool()
def ref_collections() -> list[dict[str, Any]]:
    """List collections with repo/file/chunk counts."""
    conn = open_db()
    rows = conn.execute("""
        SELECT r.collection,
               COUNT(DISTINCT r.id) AS n_repos,
               COUNT(DISTINCT f.id) AS n_files,
               COUNT(c.id) AS n_chunks,
               MAX(r.last_sync) AS last_sync
        FROM repos r
        LEFT JOIN files f ON f.repo_id = r.id
        LEFT JOIN chunks c ON c.file_id = f.id
        GROUP BY r.collection
        ORDER BY r.collection
    """).fetchall()
    return [
        {
            "collection": r["collection"],
            "repos": r["n_repos"],
            "files": r["n_files"],
            "chunks": r["n_chunks"],
            "last_sync": r["last_sync"],
        }
        for r in rows
    ]


@mcp.tool()
def ref_list(collection: str | None = None) -> list[dict[str, Any]]:
    """List indexed sources (optionally filtered by collection)."""
    conn = open_db()
    if collection:
        sql = (
            "SELECT r.name, r.path, r.collection, r.last_sync, "
            " (SELECT COUNT(*) FROM files WHERE repo_id = r.id) AS n_files, "
            " (SELECT COUNT(*) FROM chunks c JOIN files f ON c.file_id = f.id "
            "  WHERE f.repo_id = r.id) AS n_chunks "
            "FROM repos r WHERE r.collection = ? ORDER BY r.name"
        )
        rows = conn.execute(sql, (collection,)).fetchall()
    else:
        sql = (
            "SELECT r.name, r.path, r.collection, r.last_sync, "
            " (SELECT COUNT(*) FROM files WHERE repo_id = r.id) AS n_files, "
            " (SELECT COUNT(*) FROM chunks c JOIN files f ON c.file_id = f.id "
            "  WHERE f.repo_id = r.id) AS n_chunks "
            "FROM repos r ORDER BY r.collection, r.name"
        )
        rows = conn.execute(sql).fetchall()
    return [
        {
            "name": r["name"],
            "collection": r["collection"],
            "path": r["path"],
            "files": r["n_files"],
            "chunks": r["n_chunks"],
            "last_sync": r["last_sync"],
        }
        for r in rows
    ]


@mcp.tool()
def ref_ask(
    query: str,
    collection: str | None = None,
    repo: str | None = None,
    k: int = 8,
    language: str | None = None,
    path_glob: str | None = None,
) -> list[dict[str, Any]]:
    """Hybrid semantic + keyword search across indexed sources.

    Filters: `collection` scopes to one group (e.g. "research-papers"); `repo`
    narrows to a single source; `language` matches file extension ("py", "md",
    "pdf"); `path_glob` is a SQLite GLOB against the relative path.
    """
    conn = open_db()
    hits = do_search(
        conn, query, collection=collection, repo=repo, k=k, embedder=_emb(),
        language=language, path_glob=path_glob,
    )
    return [
        {
            "collection": h.collection,
            "repo": h.repo,
            "path": h.rel_path,
            "start_line": h.start_line,
            "end_line": h.end_line,
            "content": h.content,
            "score": h.score,
            "vec_rank": h.vec_rank,
            "fts_rank": h.fts_rank,
        }
        for h in hits
    ]


@mcp.tool()
def ref_search(
    pattern: str,
    collection: str | None = None,
    repo: str | None = None,
    regex: bool = False,
    limit: int = 50,
    language: str | None = None,
    path_glob: str | None = None,
) -> list[dict[str, Any]]:
    """Literal (token-level) or regex match across indexed content."""
    conn = open_db()
    repo_id: int | None = None
    if repo:
        row = conn.execute("SELECT id FROM repos WHERE name = ?", (repo,)).fetchone()
        if not row:
            return []
        repo_id = row["id"]

    clauses, fparams, needs_repos = _file_filters(repo_id, collection, language, path_glob)

    if regex:
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return [{"error": f"invalid regex: {e}"}]
        joins = "JOIN files f ON f.id = c.file_id JOIN repos r ON r.id = f.repo_id"
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT r.name AS repo, r.collection, f.rel_path, c.start_line, c.end_line, c.content "
            f"FROM chunks c {joins}{where} LIMIT ?"
        )
        rows = conn.execute(sql, [*fparams, limit * 20]).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            if rx.search(row["content"]):
                out.append({
                    "collection": row["collection"],
                    "repo": row["repo"],
                    "path": row["rel_path"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "content": row["content"],
                })
                if len(out) >= limit:
                    break
        return out

    fts_q = _literal_fts_query(pattern)
    if not fts_q:
        return []
    joins = "JOIN chunks c ON c.id = fts.rowid JOIN files f ON f.id = c.file_id JOIN repos r ON r.id = f.repo_id"
    where_parts = ["chunks_fts MATCH ?", *clauses]
    where = " AND ".join(where_parts)
    sql = f"""
        SELECT r.name AS repo, r.collection, f.rel_path, c.start_line, c.end_line, c.content
        FROM chunks_fts fts
        {joins}
        WHERE {where}
        ORDER BY fts.rank
        LIMIT ?
    """
    del needs_repos  # repos is always joined above for the collection column in output
    try:
        rows = conn.execute(sql, [fts_q, *fparams, limit]).fetchall()
    except sqlite3.OperationalError as e:
        return [{"error": f"fts query failed: {e}"}]
    return [
        {
            "collection": r["collection"],
            "repo": r["repo"],
            "path": r["rel_path"],
            "start_line": r["start_line"],
            "end_line": r["end_line"],
            "content": r["content"],
        }
        for r in rows
    ]


@mcp.tool()
def ref_file(
    repo: str,
    path: str,
    start: int | None = None,
    end: int | None = None,
) -> dict[str, Any]:
    """Read a file from an indexed source. Pass start/end (1-based) for a line range."""
    conn = open_db()
    abs_path, err = _resolve_repo_file(conn, repo, path)
    if err or abs_path is None:
        return {"error": err}
    try:
        text = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        indexed = _indexed_file_slice(conn, repo, path, start=start or 1, end=end or (1 << 30))
        if indexed is not None:
            return indexed
        return {"error": "file is not utf-8"}
    except OSError as e:
        return {"error": str(e)}

    lines = text.split("\n")
    total = len(lines)
    s = max(1, start) if start else 1
    e = min(total, end) if end else total
    slice_ = "\n".join(lines[s - 1 : e])
    return {
        "repo": repo,
        "path": path,
        "start_line": s,
        "end_line": e,
        "total_lines": total,
        "content": slice_,
    }


@mcp.tool()
def ref_expand(
    repo: str,
    path: str,
    around_line: int,
    span: int = 60,
) -> dict[str, Any]:
    """Read a line window centered on `around_line` (1-based) in an indexed file."""
    conn = open_db()
    abs_path, err = _resolve_repo_file(conn, repo, path)
    if err or abs_path is None:
        return {"error": err}
    try:
        text = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        half = max(1, span) // 2
        indexed = _indexed_file_slice(
            conn,
            repo,
            path,
            start=max(1, around_line - half),
            end=around_line + half,
        )
        if indexed is None:
            return {"error": "file is not utf-8"}
        indexed["around_line"] = around_line
        return indexed
    except OSError as e:
        return {"error": str(e)}

    lines = text.split("\n")
    total = len(lines)
    half = max(1, span) // 2
    s = max(1, around_line - half)
    e = min(total, around_line + half)
    slice_ = "\n".join(lines[s - 1 : e])
    return {
        "repo": repo,
        "path": path,
        "around_line": around_line,
        "start_line": s,
        "end_line": e,
        "total_lines": total,
        "content": slice_,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
