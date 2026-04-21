# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-04-20

### Changed
- **Major GUI refresh.** New global stylesheet (modern Windows-friendly light theme, navy accent from the app icon), consistent margins and spacing across all pages, better type hierarchy.
- **Drop zone** — larger (140 px tall), hover feedback on drag-over, clearer primary + secondary text.
- **Source table** — alternating row colors, right-aligned thousands-formatted counts, tooltip on long paths, hidden gridlines, comfortable row height. Empty-state placeholder when no sources are in the collection yet.
- **Buttons** get a primary / danger / secondary hierarchy. "Embed all" is the obvious CTA; "Remove selected" reads as destructive.
- **Progress bar** is taller, shows percentage and current file name inline, hides itself after a successful run.
- **Status bar** at the bottom of the main window now carries transient feedback instead of a cramped label above the progress bar. Inline message feedback replaces most `QMessageBox` popups.
- **Settings tier picker** replaces cramped one-line radios with card-style rows: title, size/dim meta, one-line description, and a "RECOMMENDED" badge on Small.
- **Setup wizard** gets the same visual language: hero header with the app icon on Welcome, tier cards on the Tier page, bigger install button on the Ollama page, percentage + MB display while downloading, more breathing room throughout.
- Sidebar has a proper title, padded list, and preserves selection across collection list refreshes.

### Added
- `memex.style` module with the shared QSS stylesheet and `apply_style()` helper.
- `TierCard` widget reused across Settings and the wizard.

### Fixed
- Collection list selection no longer jumps to the top on refresh.
- Collection header no longer shows a placeholder em-dash on first paint.

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

[Unreleased]: https://github.com/drhalto/memexmcp/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/drhalto/memexmcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/drhalto/memexmcp/releases/tag/v0.1.0
