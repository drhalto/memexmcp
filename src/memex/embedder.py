"""Embedding providers — Gemini (when key is set) and Ollama (default).

Gemini key resolved from Windows Credential Manager via keyring, or env var.
Provider + model + dim come from config.py; env vars can override.
"""

from __future__ import annotations

import math
import os
import sys
import time
from typing import Literal, Protocol

import httpx

from memex.config import Config, load as load_config

type EmbedTask = Literal["document", "query"]

REQUEST_TIMEOUT = 120.0
OLLAMA_BATCH_SIZE = 16
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_BATCH_SIZE = 64

_GEMINI_TASK_MAP: dict[EmbedTask, str] = {
    "document": "RETRIEVAL_DOCUMENT",
    "query": "CODE_RETRIEVAL_QUERY",
}
# v2 models reject taskType — bake the task into the prompt instead.
_EMBED_V2_MODELS: frozenset[str] = frozenset({"gemini-embedding-2-preview"})

KEYRING_SERVICE = "memex"
KEYRING_USER = "gemini-api-key"


def _format_v2(text: str, task: EmbedTask) -> str:
    if task == "query":
        return f"task: code retrieval | query: {text}"
    return f"title: none | text: {text}"


class EmbedError(RuntimeError):
    """Transient/systemic embed failure — callers should surface."""


class EmbedBadInput(EmbedError):
    """Provider rejected specific input (4xx). Not retryable. Drop the chunk."""


class EmbedProvider(Protocol):
    dim: int

    def embed(
        self, texts: list[str], *, task: EmbedTask = "document"
    ) -> list[list[float] | None]: ...
    def close(self) -> None: ...


def gemini_key() -> str | None:
    try:
        import keyring
        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY") or None


def set_gemini_key(key: str) -> None:
    import keyring
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key)


def clear_gemini_key() -> None:
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass


class OllamaEmbedder:
    def __init__(
        self,
        *,
        host: str,
        model: str,
        dim: int,
        client: httpx.Client | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.dim = dim
        self._client = client or httpx.Client(timeout=REQUEST_TIMEOUT)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaEmbedder:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def embed(
        self, texts: list[str], *, task: EmbedTask = "document"
    ) -> list[list[float] | None]:
        del task  # Ollama /api/embed doesn't expose task prompts.
        if not texts:
            return []
        out: list[list[float] | None] = []
        for i in range(0, len(texts), OLLAMA_BATCH_SIZE):
            out.extend(self._embed_batch(texts[i : i + OLLAMA_BATCH_SIZE]))
        return out

    def _embed_batch(self, batch: list[str]) -> list[list[float] | None]:
        try:
            return list(self._post(batch))
        except (httpx.HTTPError, EmbedError):
            out: list[list[float] | None] = []
            for t in batch:
                try:
                    out.append(self._post([t])[0])
                except EmbedBadInput as e:
                    print(f"  [embed] dropping chunk: {e}", file=sys.stderr, flush=True)
                    out.append(None)
            return out

    def _post(self, batch: list[str], *, retries: int = 2) -> list[list[float]]:
        url = f"{self.host}/api/embed"
        payload = {"model": self.model, "input": batch}
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                r = self._client.post(url, json=payload)
                if 400 <= r.status_code < 500 and r.status_code not in (408, 429):
                    raise EmbedBadInput(f"ollama HTTP {r.status_code}: {r.text[:300]}")
                r.raise_for_status()
                data = r.json()
                raw = data.get("embeddings")
                if not raw or len(raw) != len(batch):
                    raise EmbedError(f"bad response: embeddings count mismatch ({data!r})")
                return [_truncate_normalize(v, self.dim) for v in raw]
            except EmbedBadInput:
                raise
            except httpx.HTTPError as e:
                last_err = e
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
        raise EmbedError(f"ollama embed failed after {retries + 1} attempts: {last_err}")


class GeminiEmbedder:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str,
        dim: int,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key or gemini_key()
        if not key:
            raise EmbedError(
                "no Gemini API key configured — set via Settings, or the "
                "GEMINI_API_KEY env var"
            )
        self._key = key
        self.model = model
        self.dim = dim
        self._client = client or httpx.Client(timeout=REQUEST_TIMEOUT)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GeminiEmbedder:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def embed(
        self, texts: list[str], *, task: EmbedTask = "document"
    ) -> list[list[float] | None]:
        if not texts:
            return []
        out: list[list[float] | None] = []
        for i in range(0, len(texts), GEMINI_BATCH_SIZE):
            batch = texts[i : i + GEMINI_BATCH_SIZE]
            try:
                out.extend(self._post(batch, task=task))
            except EmbedBadInput as e:
                print(f"  [embed] batch 4xx, falling back to singles: {e}", file=sys.stderr, flush=True)
                for t in batch:
                    try:
                        out.append(self._post([t], task=task)[0])
                    except EmbedBadInput as ie:
                        print(
                            f"  [embed] dropping chunk ({len(t)} chars): {ie}",
                            file=sys.stderr, flush=True,
                        )
                        out.append(None)
        return out

    def _post(self, batch: list[str], *, task: EmbedTask, retries: int = 7) -> list[list[float]]:
        url = f"{GEMINI_URL}/models/{self.model}:batchEmbedContents"
        is_v2 = self.model in _EMBED_V2_MODELS
        if is_v2:
            texts = [_format_v2(t, task) for t in batch]
            requests = [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": self.dim,
                }
                for t in texts
            ]
        else:
            task_type = _GEMINI_TASK_MAP[task]
            requests = [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": self.dim,
                }
                for t in batch
            ]
        payload = {"requests": requests}
        headers = {"x-goog-api-key": self._key}
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                r = self._client.post(url, json=payload, headers=headers)
                if r.status_code == 408 or r.status_code == 429 or r.status_code >= 500:
                    last_err = EmbedError(f"gemini {r.status_code}: {r.text[:300]}")
                    if attempt < retries:
                        time.sleep(min(75.0, 2.0 ** attempt))
                        continue
                    raise last_err
                if 400 <= r.status_code < 500:
                    raise EmbedBadInput(f"gemini HTTP {r.status_code}: {r.text[:400]}")
                r.raise_for_status()
                data = r.json()
                raw = data.get("embeddings") or []
                if len(raw) != len(batch):
                    raise EmbedError(f"gemini embeddings count mismatch: {len(raw)} vs {len(batch)}")
                return [_truncate_normalize(e["values"], self.dim) for e in raw]
            except (EmbedBadInput, EmbedError):
                raise
            except httpx.HTTPError as e:
                last_err = e
                if attempt < retries:
                    time.sleep(min(30.0, 1.5 ** attempt))
        raise EmbedError(f"gemini embed failed after {retries + 1} attempts: {last_err}")


def get_embedder(cfg: Config | None = None) -> EmbedProvider:
    """Resolve provider from config + env. Env MEMEX_EMBED_PROVIDER overrides."""
    cfg = cfg or load_config()
    explicit = os.environ.get("MEMEX_EMBED_PROVIDER", "").strip().lower()
    provider = explicit or cfg.provider

    model = os.environ.get("MEMEX_EMBED_MODEL") or cfg.model
    dim = int(os.environ.get("MEMEX_EMBED_DIM") or cfg.dim)

    if provider == "gemini":
        return GeminiEmbedder(model=model, dim=dim)
    if provider == "ollama":
        host = os.environ.get("OLLAMA_HOST") or cfg.ollama_host
        return OllamaEmbedder(host=host, model=model, dim=dim)
    raise EmbedError(f"unknown provider: {provider!r}")


def probe_dim(cfg: Config | None = None) -> int:
    """Embed a dummy string to discover the native dim of the current model.

    Used by the GUI/installer when the user wants 'auto' rather than a preset.
    Matryoshka truncation still applies at embed-time; this reports native.
    """
    cfg = cfg or load_config()
    # Build a throwaway embedder that won't truncate: ask for a very large dim
    # and let the provider return its native length.
    probe_cfg = Config(
        tier=cfg.tier, provider=cfg.provider, model=cfg.model,
        dim=4096, ollama_host=cfg.ollama_host,
    )
    emb = get_embedder(probe_cfg)
    try:
        vecs = emb.embed(["probe"], task="document")
        if not vecs or vecs[0] is None:
            raise EmbedError("probe returned no vector")
        return len(vecs[0])
    finally:
        emb.close()


def _truncate_normalize(vec: list[float], dim: int) -> list[float]:
    if len(vec) < dim:
        raise EmbedError(f"model returned {len(vec)}-dim vector, need >= {dim}")
    v = vec[:dim]
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0.0:
        raise EmbedError("all-zero vector from embed provider")
    return [x / norm for x in v]
