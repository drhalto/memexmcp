"""Helpers for generating MCP client configuration."""

from __future__ import annotations

import json
import sys
from typing import Any

from memex.config import Config
from memex.paths import app_root, home


def server_command() -> tuple[str, list[str] | None]:
    """Return the command a client should use to start the MCP server."""
    if getattr(sys, "frozen", False):
        return str(app_root() / "MemexMCP-Server.exe"), None
    return sys.executable, ["-m", "memex.mcp_server"]


def server_config(cfg: Config) -> dict[str, Any]:
    command, args = server_command()
    out: dict[str, Any] = {
        "command": command,
        "env": {
            "MEMEX_HOME": str(home()),
            "MEMEX_EMBED_PROVIDER": cfg.provider,
            "MEMEX_EMBED_MODEL": cfg.model,
            "MEMEX_EMBED_DIM": str(cfg.dim),
        },
    }
    if args:
        out["args"] = args
    return out


def server_snippet(cfg: Config) -> str:
    return json.dumps({"mcpServers": {"memex": server_config(cfg)}}, indent=2)
