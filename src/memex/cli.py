"""MemexMCP CLI: add / sync / list / remove / tier / query / reindex."""

from __future__ import annotations

from pathlib import Path

import typer

from memex import config as cfg_mod
from memex.config import TIERS, Tier
from memex.embedder import get_embedder, set_gemini_key
from memex.indexer import (
    SyncStats,
    add_repo,
    rebuild_embeddings,
    remove_repo,
    suggest_repo_name,
    sync_repo,
)
from memex.search import search as do_search
from memex.store import open_db

app = typer.Typer(no_args_is_help=True, add_completion=False, help="MemexMCP CLI.")


def _print_stats(name: str, stats: SyncStats) -> None:
    typer.echo(
        f"[{name}] scanned={stats.files_scanned} indexed={stats.files_indexed} "
        f"partial={stats.files_partial} unchanged={stats.files_unchanged} "
        f"skipped={stats.files_skipped} purged={stats.files_purged} "
        f"chunks={stats.chunks_written}"
    )


@app.command()
def add(
    path: Path = typer.Argument(..., exists=True, resolve_path=True),
    name: str | None = typer.Option(None, "--name", "-n"),
    collection: str = typer.Option("default", "--collection", "-c"),
) -> None:
    """Register a source path and run an initial sync."""
    conn = open_db()
    repo_name = name or suggest_repo_name(conn, path)
    try:
        repo_id = add_repo(conn, repo_name, path, collection=collection)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2) from e
    typer.echo(f"registered '{repo_name}' in collection '{collection}' -> {path}")
    stats = sync_repo(conn, repo_id)
    _print_stats(repo_name, stats)


@app.command("list")
def list_cmd(collection: str | None = typer.Option(None, "--collection", "-c")) -> None:
    """List registered sources."""
    conn = open_db()
    if collection:
        rows = conn.execute(
            "SELECT r.name, r.path, r.collection, r.last_sync, "
            " (SELECT COUNT(*) FROM files WHERE repo_id = r.id) AS n_files, "
            " (SELECT COUNT(*) FROM chunks c JOIN files f ON c.file_id = f.id WHERE f.repo_id = r.id) AS n_chunks "
            "FROM repos r WHERE r.collection = ? ORDER BY r.name",
            (collection,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT r.name, r.path, r.collection, r.last_sync, "
            " (SELECT COUNT(*) FROM files WHERE repo_id = r.id) AS n_files, "
            " (SELECT COUNT(*) FROM chunks c JOIN files f ON c.file_id = f.id WHERE f.repo_id = r.id) AS n_chunks "
            "FROM repos r ORDER BY r.collection, r.name"
        ).fetchall()
    if not rows:
        typer.echo("(no sources registered — use `memex add <path>`)")
        return
    for r in rows:
        typer.echo(
            f"[{r['collection']:15}] {r['name']:20}  files={r['n_files']:>5} chunks={r['n_chunks']:>6}  "
            f"synced={r['last_sync'] or 'never'}  {r['path']}"
        )


@app.command()
def sync(
    name: str | None = typer.Argument(None),
    all_: bool = typer.Option(False, "--all"),
    collection: str | None = typer.Option(None, "--collection", "-c"),
) -> None:
    """Re-index sources (incremental — unchanged files are skipped)."""
    conn = open_db()
    if all_:
        if collection:
            repos = conn.execute(
                "SELECT id, name FROM repos WHERE collection = ? ORDER BY name", (collection,)
            ).fetchall()
        else:
            repos = conn.execute("SELECT id, name FROM repos ORDER BY name").fetchall()
    elif name:
        repos = conn.execute("SELECT id, name FROM repos WHERE name = ?", (name,)).fetchall()
        if not repos:
            typer.echo(f"no source named '{name}'", err=True)
            raise typer.Exit(code=1)
    else:
        typer.echo("give a name, pass --all, or scope with --collection + --all", err=True)
        raise typer.Exit(code=2)

    for r in repos:
        stats = sync_repo(conn, r["id"])
        _print_stats(r["name"], stats)


@app.command()
def remove(name: str = typer.Argument(...)) -> None:
    """Remove a source and all its indexed content."""
    conn = open_db()
    if remove_repo(conn, name):
        typer.echo(f"removed '{name}'")
    else:
        typer.echo(f"no source named '{name}'", err=True)
        raise typer.Exit(code=1)


@app.command()
def query(
    text: str = typer.Argument(...),
    collection: str | None = typer.Option(None, "--collection", "-c"),
    repo: str | None = typer.Option(None, "--repo", "-r"),
    k: int = typer.Option(8, "--k", "-k"),
    snippet: int = typer.Option(180, "--snippet"),
) -> None:
    """Hybrid (vec + FTS) search."""
    conn = open_db()
    hits = do_search(conn, text, collection=collection, repo=repo, k=k)
    if not hits:
        typer.echo("(no hits)")
        return
    for i, h in enumerate(hits, start=1):
        marks = []
        if h.vec_rank is not None:
            marks.append(f"vec#{h.vec_rank}")
        if h.fts_rank is not None:
            marks.append(f"fts#{h.fts_rank}")
        badge = ",".join(marks) or "—"
        first_line = h.content.strip().splitlines()[0] if h.content.strip() else ""
        typer.echo(
            f"{i:>2}. [{h.score:.4f} {badge:15}] "
            f"{h.collection}/{h.repo}/{h.rel_path}:{h.start_line}-{h.end_line}"
        )
        typer.echo(f"    {first_line[:snippet]}")


@app.command()
def tier(
    name: Tier = typer.Argument(..., help="small | medium | large | gemini"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation for re-embed."),
) -> None:
    """Switch embedding tier. Rebuilds vec table + re-embeds if dim changes."""
    current = cfg_mod.load()
    if name not in TIERS:
        typer.echo(f"unknown tier '{name}'. choices: {', '.join(TIERS)}", err=True)
        raise typer.Exit(code=2)
    t = TIERS[name]
    new_cfg = cfg_mod.Config.from_tier(name, ollama_host=current.ollama_host)

    dim_change = current.dim != new_cfg.dim
    if dim_change and not yes:
        conn = open_db()
        n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        typer.confirm(
            f"Switching to {t.label} changes dim {current.dim} -> {new_cfg.dim}. "
            f"Re-embed {n} chunks?",
            abort=True,
        )
    if dim_change:
        conn = open_db(dim=current.dim)
        embedder = get_embedder(new_cfg)
        typer.echo("re-embedding all chunks…")
        total = rebuild_embeddings(conn, new_cfg.dim, embedder=embedder)
        typer.echo(f"re-embedded {total} chunks at dim {new_cfg.dim}")
    cfg_mod.save(new_cfg)
    typer.echo(f"tier set to {t.label}")


@app.command()
def gemini_key(key: str = typer.Argument(..., help="Your Gemini API key.")) -> None:
    """Save a Gemini API key to Windows Credential Manager."""
    set_gemini_key(key)
    typer.echo("saved.")


@app.command()
def info() -> None:
    """Show current config + tier."""
    c = cfg_mod.load()
    typer.echo(f"tier:     {c.tier}")
    typer.echo(f"provider: {c.provider}")
    typer.echo(f"model:    {c.model}")
    typer.echo(f"dim:      {c.dim}")
    typer.echo(f"ollama:   {c.ollama_host}")


if __name__ == "__main__":
    app()
