"""Persistent runtime config (provider / model / embed dim).

Stored at $MEMEX_HOME/config.json. Env vars win over file values so
power users and the frozen MCP server can override without editing JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal

from memex.paths import config_path

Provider = Literal["ollama", "gemini"]
Tier = Literal["small", "medium", "large", "gemini"]


@dataclass(frozen=True, slots=True)
class Tierdef:
    tier: Tier
    provider: Provider
    model: str
    dim: int
    label: str
    disk_mb: int  # approx, for UI disk-space warnings


# The four canonical presets. Installer + GUI pick from this list only.
TIERS: dict[Tier, Tierdef] = {
    "small":  Tierdef("small",  "ollama", "nomic-embed-text",     768,  "Small  (nomic-embed-text)",  270),
    "medium": Tierdef("medium", "ollama", "mxbai-embed-large",    1024, "Medium (mxbai-embed-large)", 670),
    "large":  Tierdef("large",  "ollama", "qwen3-embedding:8b",   1024, "Large  (qwen3-embedding:8b)", 6000),
    "gemini": Tierdef("gemini", "gemini", "gemini-embedding-2-preview", 1536, "Gemini (cloud, requires API key)", 0),
}

DEFAULT_TIER: Tier = "small"


@dataclass(slots=True)
class Config:
    tier: Tier = DEFAULT_TIER
    provider: Provider = "ollama"
    model: str = "nomic-embed-text"
    dim: int = 768
    ollama_host: str = "http://localhost:11434"
    extras: dict = field(default_factory=dict)

    @classmethod
    def from_tier(cls, tier: Tier, *, ollama_host: str = "http://localhost:11434") -> Config:
        t = TIERS[tier]
        return cls(tier=tier, provider=t.provider, model=t.model, dim=t.dim, ollama_host=ollama_host)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def load() -> Config:
    p = config_path()
    if not p.exists():
        return Config.from_tier(DEFAULT_TIER)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Config.from_tier(DEFAULT_TIER)
    return Config(
        tier=raw.get("tier", DEFAULT_TIER),
        provider=raw.get("provider", "ollama"),
        model=raw.get("model", "nomic-embed-text"),
        dim=int(raw.get("dim", 768)),
        ollama_host=raw.get("ollama_host", "http://localhost:11434"),
        extras=raw.get("extras", {}),
    )


def save(cfg: Config) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cfg.to_json(), encoding="utf-8")
