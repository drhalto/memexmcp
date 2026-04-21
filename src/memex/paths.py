"""Runtime path resolution for installed, portable, and dev launches."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    """Directory containing the running app artifacts."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def home() -> Path:
    """Directory used for Memex data and, in frozen builds, sibling binaries."""
    env = os.environ.get("MEMEX_HOME")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return app_root()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "MemexMCP"
    return Path.home() / "memexmcp"


def config_path() -> Path:
    return home() / "config.json"


def db_path() -> Path:
    env = os.environ.get("MEMEX_DB")
    if env:
        return Path(env)
    return home() / "index.db"


def collections_dir() -> Path:
    return home() / "collections"


def ensure_dirs() -> None:
    home().mkdir(parents=True, exist_ok=True)
    collections_dir().mkdir(parents=True, exist_ok=True)
