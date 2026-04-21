# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-20

First public release.

### Added
- Local indexing of code, Markdown, plain text, PDF, DOCX, and HTML.
- Hybrid search: vector (sqlite-vec) + keyword (FTS5), fused with Reciprocal Rank Fusion.
- **Collections** — group sources and scope searches per collection.
- **Tier system** — Small (`nomic-embed-text`, 768-dim, ~270 MB), Medium (`mxbai-embed-large`, 1024-dim, ~670 MB), Large (`qwen3-embedding:8b`, 1024-dim, ~6 GB), and optional Gemini (`gemini-embedding-2-preview`, 1536-dim, cloud).
- **First-launch wizard** in the GUI: tier picker, optional Gemini key, Ollama install, model pull, MCP config snippet.
- **Dim-aware schema** — `chunks_vec` is created lazily at the configured dim. Switching tiers across dims rebuilds the vec table and re-embeds existing chunks (no re-reading files).
- MCP tools: `ref_collections`, `ref_list`, `ref_ask`, `ref_search`, `ref_file`, `ref_expand`.
- PySide6 GUI with collections sidebar, drop-zone, embed progress, and Settings tab.
- CLI: `memex-cli add / sync / list / remove / query / tier / gemini-key / info`.
- Frozen Windows binaries via PyInstaller: `Memex.exe`, `MemexMCP-Server.exe`, `memex-cli.exe`.
- Portable zip distribution (~323 MB) with the three exes plus a short README.
- Inno Setup installer script (`build/MemexMCP.iss`) — minimal file-copy wrapper, since the in-app wizard handles the real setup.
- Apache 2.0 license.

### Notes
- Gemini API keys are stored in **Windows Credential Manager** under service `memex`, user `gemini-api-key` — never written to disk.
- Frozen exes are unsigned. SmartScreen will warn on first run unless the downloaded zip is **Unblocked** (right-click → Properties → Unblock) before extraction.

[Unreleased]: https://github.com/drhalto/memexmcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/drhalto/memexmcp/releases/tag/v0.1.0
