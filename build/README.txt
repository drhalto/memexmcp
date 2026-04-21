Memex - portable install
========================

IMPORTANT - before extracting the zip:

  1. Right-click the downloaded zip -> Properties
  2. Check "Unblock" near the bottom -> OK
  3. THEN extract the zip.

Unblocking strips the "downloaded from internet" flag from every file
inside, in one click. Skip this and Windows SmartScreen will block
the exe on first run.

How to run:
-----------

  Just double-click Memex.exe.

On first launch a setup wizard walks you through:
  * Picking an embedding tier (Small / Medium / Large)
  * Optionally saving a Gemini API key
  * Installing Ollama (downloads ~1 GB if you don't already have it)
  * Downloading the chosen embedding model
  * Showing the MCP client config to paste into Claude Desktop / etc.

After that, use the app normally - drag folders or files into a
collection and click Embed. The Settings tab lets you switch tiers
or update your Gemini key later.

Files in this zip:
------------------

  Memex.exe              The app. This is what you double-click.
  MemexMCP-Server.exe    Runs silently when Claude Desktop calls it.
  memex-cli.exe          Optional CLI for power users.

Uninstall:
----------

  Delete the extracted folder. Your indexed data lives beside the exes in
  that same folder, so removing it removes everything.
  Ollama has its own uninstaller in Settings -> Apps.
