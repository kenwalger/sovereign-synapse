"""Tests for core.ollama_embed API compatibility."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core import ollama_embed


def test_embed_text_uses_modern_embed_api():
    fake_ollama = SimpleNamespace(
        embed=lambda model, input: SimpleNamespace(embeddings=[[0.1, 0.2, 0.3]]),
    )
    with patch.object(ollama_embed, "ollama", fake_ollama):
        vec = ollama_embed.embed_text("mxbai-embed-large", "hello")
    assert vec == [0.1, 0.2, 0.3]


def test_embed_text_falls_back_to_legacy_embeddings():
    fake_ollama = SimpleNamespace(
        embeddings=lambda model, prompt: {"embedding": [1.0, 2.0]},
    )
    with patch.object(ollama_embed, "ollama", fake_ollama):
        vec = ollama_embed.embed_text("mxbai-embed-large", "hello")
    assert vec == [1.0, 2.0]


def test_embed_text_raises_when_no_api():
    with patch.object(ollama_embed, "ollama", SimpleNamespace()):
        with pytest.raises(AttributeError, match="ollama>=0.2.1"):
            ollama_embed.embed_text("m", "x")
