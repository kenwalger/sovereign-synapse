"""Ollama embedding helper with API compatibility across package versions."""

from __future__ import annotations

from typing import Any

import ollama


def embed_text(model: str, text: str) -> list[float]:
    """Return an embedding vector for *text* using the local Ollama daemon.

    Supports:
    - ``ollama>=0.2.1``: ``ollama.embed(model=..., input=...)``
    - Older releases: ``ollama.embeddings(model=..., prompt=...)``

    Raises:
        AttributeError: If neither API exists on the installed package.
        ollama.ResponseError: On HTTP errors from Ollama.
    """
    if hasattr(ollama, "embed"):
        response = ollama.embed(model=model, input=text)
        embeddings = getattr(response, "embeddings", None) or []
        if not embeddings:
            return []
        return list(embeddings[0])

    if hasattr(ollama, "embeddings"):
        result: Any = ollama.embeddings(model=model, prompt=text)
        if isinstance(result, dict):
            single = result.get("embedding")
            if single is not None:
                return list(single)
            plural = result.get("embeddings")
            if plural and len(plural) > 0:
                return list(plural[0])
        return []

    raise AttributeError(
        "The installed 'ollama' package has no embed API. "
        "Install the project pin: pip install 'ollama>=0.2.1'",
    )
