# Memex

> Local semantic + keyword search over your codebases and documents — served to Claude (or any MCP client) over MCP.

Drop folders or files in, click **Embed**, then ask Claude. Everything runs on your PC; nothing leaves the machine unless you opt in to Gemini cloud embeddings.

- **Provider**: Ollama (local, default) or Gemini (cloud, optional). Pick a tier — *Small* (270 MB), *Medium* (670 MB), or *Large* (~6 GB) — and the wizard handles the rest.
- **File types**: code (Python / TS / Go / Rust / …), Markdown, plain text, PDF, DOCX, HTML.
- **Search**: vector (sqlite-vec) **+** keyword (FTS5), fused with Reciprocal Rank Fusion.
- **Surface**: a desktop GUI for indexing, an MCP stdio server for Claude Desktop, a CLI for power users.
- **Platform**: Windows. Linux / macOS aren't currently shipped, but the Python package itself is portable — see *Build from source* below.

---

## Quick start

Pick the path that fits you.

| You are… | Use this |
|---|---|
| Just want to use it on Windows | [Run from a Release zip](#run-from-a-release-zip) |
| Have Python and want to hack | [Build from source](#build-from-source) |
| Want to peek at the code | [Project layout](#project-layout) |

---

## Run from a Release zip

Grab the latest `MemexMCP-Portable.zip` from the [Releases page](https://github.com/drhalto/memexmcp/releases) (or build it yourself — see below).

1. Right-click the downloaded zip → **Properties** → tick **Unblock** → **OK**.
   *Skipping this is the #1 reason SmartScreen flags the exe on first run.*
2. Extract the zip anywhere.
3. Double-click **`Memex.exe`**.

A first-launch wizard walks you through tier choice, optional Gemini key, Ollama install (~1 GB if you don't have it), model download, and prints the MCP client config snippet to paste into Claude Desktop.

After that, drag folders or files into a collection and click **Embed**. Use Settings to switch tiers, update keys, or copy the MCP config later.

Default install location: `%LOCALAPPDATA%\MemexMCP\`.

---

## Build from source

### Prereqs
- **Python 3.12+**
- [`uv`](https://docs.astral.sh/uv/) (recommended) or stock `pip` + `venv`
- **Windows** for the frozen-exe pipeline. Other OSes can run the Python package directly.
- *Optional:* [Inno Setup 6](https://jrsoftware.org/isdl.php) if you want a Setup.exe installer.

### 1. Clone
```bash
git clone https://github.com/drhalto/memexmcp.git
cd memexmcp
```

### 2. Set up a venv and install
With `uv`:
```bash
uv venv --python 3.12
uv pip install -e ".[gui,dev]"
```

Without `uv`:
```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate    # Linux / macOS
pip install -e ".[gui,dev]"
```

The `gui` extra pulls PySide6 (~80 MB). Skip it if you only want the MCP server + CLI.

### 3. Run something

**The GUI** (Windows, with the `gui` extra installed):
```bash
python -m memex.gui
```
First launch shows the setup wizard. After that, drag in files, click Embed.

**The MCP stdio server** (what Claude Desktop spawns):
```bash
python -m memex.mcp_server
```

**The CLI:**
```bash
memex-cli --help
memex-cli add C:\path\to\some\repo --collection work
memex-cli sync --all
memex-cli query "vector search"
memex-cli tier medium    # switch embedding tier
```

### 4. Wire it into Claude Desktop

Add to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "memex": {
      "command": "python",
      "args": ["-m", "memex.mcp_server"],
      "env": {
        "MEMEX_HOME": "C:\\path\\to\\where\\you\\want\\data",
        "MEMEX_EMBED_PROVIDER": "ollama",
        "MEMEX_EMBED_MODEL": "nomic-embed-text",
        "MEMEX_EMBED_DIM": "768"
      }
    }
  }
}
```
Then restart Claude. The wizard generates a similar snippet pointing at the frozen `MemexMCP-Server.exe` — adapt to whichever you prefer.

### 5. Build the frozen exes (Windows)

```powershell
.\build\build.ps1
```
Produces:
- `dist\Memex.exe` — the GUI (~258 MB; PySide6 dominates)
- `dist\MemexMCP-Server.exe` — the MCP server (~37 MB)
- `dist\memex-cli.exe` — the CLI (~32 MB)

### 6. Package the portable zip

```powershell
.\build\package.ps1
```
Produces `dist\MemexMCP-Portable.zip` (~323 MB) — the three exes plus a short README. Upload this to a GitHub Release.

### WDAC / AppLocker note

If your machine has Windows Defender Application Control or AppLocker blocking new `pyinstaller.exe` installs, edit `build\build-reuse-venv.ps1` to point at an already-approved venv's PyInstaller and run it instead of `build.ps1`.

---

## Project layout

```
memexmcp/
├── assets/
│   ├── icon.png              # source logo (drop a new file here to rebrand)
│   └── icon.ico              # multi-res Windows icon (regenerate after editing icon.png)
├── build/
│   ├── Memex.spec            # PyInstaller spec — GUI
│   ├── MemexMCP-Server.spec  # PyInstaller spec — MCP server
│   ├── memex-cli.spec        # PyInstaller spec — CLI
│   ├── MemexMCP.iss          # Inno Setup script (optional installer)
│   ├── build.ps1             # main build pipeline
│   ├── build-reuse-venv.ps1  # WDAC workaround
│   ├── package.ps1           # zip assembler
│   └── README.txt            # ships inside the zip
├── pyproject.toml
├── src/memex/
│   ├── chunker.py            # file-type dispatch (code / md / pdf / docx / html)
│   ├── cli.py                # add / sync / list / remove / query / tier / gemini-key
│   ├── config.py             # tier defs, config.json load/save
│   ├── embedder.py           # Ollama + Gemini providers
│   ├── gui.py                # PySide6 main window
│   ├── gui_worker.py         # QThread embed worker
│   ├── indexer.py            # walk + chunk + embed + persist
│   ├── mcp_config.py         # builds the MCP client config snippet
│   ├── mcp_server.py         # FastMCP stdio server (what Claude calls)
│   ├── paths.py              # MEMEX_HOME / config / db / collections paths
│   ├── search.py             # vec + FTS + RRF fusion
│   ├── setup_wizard.py       # first-launch QWizard
│   └── store.py              # SQLite + sqlite-vec, dim-aware lazy schema
└── tests/                    # pytest suite (paths / indexer / mcp_server)
```

### Architecture in 5 lines

1. `indexer.sync_repo` walks a source path, asks `chunker.chunk_file` for chunks per file.
2. Chunks go through `embedder.embed()` → vectors.
3. `store` persists chunks + vectors into SQLite (`chunks` + FTS5 `chunks_fts` + sqlite-vec `chunks_vec`).
4. `search.search` queries both vec and FTS, fuses with Reciprocal Rank Fusion (RRF), returns top hits.
5. `mcp_server` exposes `ref_collections`, `ref_list`, `ref_ask`, `ref_search`, `ref_file`, `ref_expand` as MCP tools.

### Switching embedding model dim

`store.chunks_vec` is created at the dim active when the DB was first opened. Switching to a model with a different dim requires `rebuild_vec_table(conn, new_dim)` + `reembed_all(conn)`. The GUI handles this in Settings; the CLI exposes it via `memex-cli tier <name>` (with a confirmation prompt unless `--yes`).

---

## Where data lives

```
%LOCALAPPDATA%\MemexMCP\
├── config.json          # tier / model / dim / Ollama host
├── index.db             # SQLite + sqlite-vec store
├── mcp-config.json      # the MCP client snippet, dropped here for reference
└── collections/         # subfolder per collection (created on demand)
```

Override the location with `MEMEX_HOME`. Override the DB path specifically with `MEMEX_DB`.

Your Gemini key (if set) lives in **Windows Credential Manager** under service `memex`, user `gemini-api-key`. It is not written to disk.

### Uninstall
1. Delete `%LOCALAPPDATA%\MemexMCP\`.
2. Settings → Apps → uninstall **Ollama** if you don't need it anymore.
3. *(Optional)* Open Credential Manager → Generic Credentials → remove the `memex` entry.

---

## Tests

```bash
pytest
```

Tests under `tests/` cover paths, indexer behavior on a temp DB, and MCP tool surface. The frozen exes aren't exercised by tests — those rely on a successful build pipeline.

---

## Contributing

Issues and PRs welcome. Before submitting a PR:
- `ruff check` — lint
- `pytest` — tests pass
- Don't commit anything under `dist/` or `build/_work/` (the `.gitignore` should keep them out automatically; if `git status` shows binaries staged, something's off).

---

## License

[Apache License 2.0](LICENSE).
