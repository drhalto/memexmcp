# Memex

Local semantic + keyword search over your codebases and documents — served to Claude (or any MCP client) over MCP.

Drop folders or files in, click **Embed**, then ask Claude. Everything runs on your PC; nothing leaves the machine unless you opt into Gemini cloud embeddings.

---

## For end users — installing and running

### 1. Get the zip

The shippable artifact is `dist/MemexMCP-Portable.zip` (~323 MB). Either grab it from a build, or have someone send it to you.

### 2. Unblock the zip *before* extracting

> **This is the one critical step.** If you skip it, every exe inside the zip will be flagged by SmartScreen on first run.

1. Right-click the downloaded zip → **Properties**
2. Tick **Unblock** near the bottom → **OK**
3. *Now* extract it (anywhere — Desktop, Downloads, your own folder).

Unblocking the zip strips the "downloaded from internet" mark from every file inside, in one click.

### 3. Run

Double-click **`Memex.exe`**.

That's it. On first launch, an in-app setup wizard walks you through:

| Step | What happens |
|---|---|
| Welcome | Brief intro |
| Tier | Pick **Small** (270 MB), **Medium** (670 MB), or **Large** (~6 GB) |
| Gemini key | Optional. Pasted key is saved to Windows Credential Manager — never to disk |
| Ollama | If not already installed, downloads (~1 GB) and silent-installs Ollama |
| Model pull | Downloads the embedding model with a real progress bar |
| Done | Shows the MCP config snippet to paste into your MCP client |

After that, you're in the main app.

### 4. Daily use

The app has two tabs:

- **Sources** — drag folders or files onto the drop zone. They show up as rows. Click **Embed** to index them. Progress bar tracks files done / total.
- **Settings** — switch tier, set/clear Gemini key, change Ollama host, copy MCP config.

The left sidebar holds **collections** (think "datasets" or "topics"). Click **+ New collection** to make one. Each collection has its own sources and is its own search scope.

### 5. Hooking it up to Claude

After the wizard finishes, copy the MCP config snippet shown on the last page. Memex also saves a copy as `mcp-config.json` next to the running app.

For **Claude Desktop**, paste it into `%APPDATA%\Claude\claude_desktop_config.json` and restart Claude. The snippet looks like:

```json
{
  "mcpServers": {
    "memex": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\MemexMCP\\MemexMCP-Server.exe",
      "env": {
        "MEMEX_HOME": "C:\\Users\\<you>\\AppData\\Local\\MemexMCP",
        "MEMEX_EMBED_PROVIDER": "ollama",
        "MEMEX_EMBED_MODEL": "nomic-embed-text",
        "MEMEX_EMBED_DIM": "768"
      }
    }
  }
}
```

Claude will then have these tools available:

| Tool | Purpose |
|---|---|
| `ref_collections` | List collections with file/chunk counts |
| `ref_list` | List sources (optionally filtered by collection) |
| `ref_ask` | Hybrid semantic + keyword search |
| `ref_search` | Literal token / regex match |
| `ref_file` | Read a file from an indexed source |
| `ref_expand` | Read a line window around a hit |

Ask Claude things like *"search the research-papers collection for stuff about RAG evaluation"* — Claude will pick the right tool.

### 6. Switching tiers later

In **Settings → Embedding tier**, pick a different one and click **Apply tier**.
- If the new tier has the **same dim** as the old one (e.g. Medium ↔ Large, both 1024), the swap is instant — only newly-indexed chunks use the new model.
- If the **dim changes** (e.g. Small 768 → Medium 1024), the app prompts to re-embed everything. It re-uses the existing chunked text — no re-reading files — so it's typically a few minutes per thousand chunks.

### 7. Where everything lives

Installed build location: `%LOCALAPPDATA%\MemexMCP\`

Portable zip location: wherever you extracted it

```
%LOCALAPPDATA%\MemexMCP\
├── Memex.exe
├── MemexMCP-Server.exe
├── memex-cli.exe
├── config.json          # tier / model / dim / Ollama host
├── index.db             # SQLite + sqlite-vec store
├── mcp-config.json      # the MCP snippet
└── collections/         # subfolder per collection (created as you make them)
```

Your Gemini key (if set) lives in **Windows Credential Manager** under service `memex` user `gemini-api-key`.

### 8. Uninstall

1. Delete the installed app folder or extracted portable folder (removes the app + your data).
2. Settings → Apps → uninstall **Ollama** if you don't want it anymore.
3. (Optional) Open Credential Manager → Generic Credentials → remove the `memex` entry.

---

## For developers — building from source

### Prereqs

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (preferred) or stock `pip` + `venv`
- Inno Setup 6 *(only if you want to produce a `Setup.exe` installer)*

### Build

```powershell
# from C:\Users\Dustin\memexmcp
.\build\build.ps1
```

This will:
1. Create `.venv`, install runtime + build deps (PySide6, pyinstaller, etc.)
2. Run PyInstaller three times → `dist\Memex.exe`, `dist\MemexMCP-Server.exe`, `dist\memex-cli.exe`
3. Skip the Inno Setup step unless `iscc` is on PATH

### Package the portable zip

```powershell
.\build\package.ps1
```

Produces `dist\MemexMCP-Portable.zip` (~320 MB) — exes + README.

### WDAC / AppLocker note

If your machine has Windows Defender Application Control (or AppLocker) blocking newly-installed `pyinstaller.exe`, use the workaround script — it points at an already-approved PyInstaller in a different venv:

```powershell
.\build\build-reuse-venv.ps1
```

(You'd have to edit the path inside the script to point at *your* known-good venv.)

### Project layout

```
memexmcp/
├── assets/
│   ├── icon.png         # source logo
│   └── icon.ico         # multi-res Windows icon (generated)
├── build/
│   ├── Memex.spec               # PyInstaller spec — GUI
│   ├── MemexMCP-Server.spec     # PyInstaller spec — MCP server
│   ├── memex-cli.spec           # PyInstaller spec — CLI
│   ├── MemexMCP.iss             # Inno Setup script
│   ├── build.ps1                # main build pipeline
│   ├── build-reuse-venv.ps1     # WDAC workaround
│   ├── package.ps1              # zip assembler
│   └── README.txt               # ships in the zip
├── pyproject.toml
└── src/memex/
    ├── __init__.py
    ├── chunker.py        # file-type dispatch (code / md / pdf / docx / html)
    ├── cli.py            # add / sync / list / remove / query / tier / gemini-key
    ├── config.py         # tier defs, config.json load/save
    ├── embedder.py       # Ollama + Gemini providers
    ├── gui.py            # PySide6 main window
    ├── gui_worker.py     # QThread embed worker
    ├── indexer.py        # walk + chunk + embed + persist
    ├── mcp_server.py     # FastMCP stdio server (Claude talks to this)
    ├── paths.py          # MEMEX_HOME / config / db / collections paths
    ├── search.py         # vec + FTS + RRF fusion
    ├── setup_wizard.py   # first-launch QWizard
    └── store.py          # SQLite + sqlite-vec, dim-aware lazy schema
```

### Architecture in 5 lines

1. `indexer.sync_repo` walks a source, asks `chunker.chunk_file` for chunks per file.
2. Chunks go to `embedder.embed()` → vectors.
3. `store` persists chunks + vectors into SQLite (`chunks` + FTS5 `chunks_fts` + sqlite-vec `chunks_vec`).
4. `search.search` queries both vec and FTS, fuses with Reciprocal Rank Fusion (RRF), returns top hits.
5. `mcp_server` exposes `ref_ask`, `ref_search`, etc. as MCP tools.

### Switching embedding model dim

`store.chunks_vec` is created at the dim active when the DB was first opened. Switching to a model with a different dim requires `rebuild_vec_table(conn, new_dim)` + `reembed_all(conn)` — the app handles this in Settings; the CLI exposes it as `memex-cli tier <name>`.

---

## License

(Add one before you ship publicly.)
