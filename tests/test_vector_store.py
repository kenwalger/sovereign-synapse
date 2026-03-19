"""Tests for core.vector_store.VectorStore."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from core.vector_store import VectorStore


def _make_synapse_file(content: str) -> str:
    """Write a synapse Markdown file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".md", prefix="synapse_")
    try:
        Path(path).write_text(content, encoding="utf-8")
        return path
    finally:
        os.close(fd)


@pytest.fixture
def temp_persist_dir(tmp_path):
    """Provide a temporary directory for ChromaDB persistence."""
    return str(tmp_path / "chroma")


@pytest.fixture
def sample_synapse_content() -> str:
    """Sample synapse Markdown with valid frontmatter."""
    return """---
uuid: urn:uuid:a1b2c3d4-e5f6-7890-abcd-ef1234567890
source: gpt_export
model: gpt-4o
original_timestamp: 2025-06-06T11:27:59.564000
preamble: false
postamble: true
---
### User
What wearable provides raw sensor data?

### Assistant
The Movesense Sensor by Suunto offers raw accelerometer and gyroscope data.
"""


def test_add_synapse_parses_file_and_calls_embedding(
    temp_persist_dir: str,
    sample_synapse_content: str,
) -> None:
    """add_synapse correctly parses the file and invokes the embedding function."""
    synapse_path = _make_synapse_file(sample_synapse_content)

    fake_embedding = [0.1] * 1024  # mxbai-embed-large uses 1024-dim vectors

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = {"embeddings": [fake_embedding]}

        store = VectorStore(persist_directory=temp_persist_dir)
        doc_id = store.add_synapse(synapse_path)

    assert doc_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    mock_embed.assert_called_once()
    call_args = mock_embed.call_args
    assert call_args.kwargs["model"] == "mxbai-embed-large"
    input_text = call_args.kwargs["input"]
    assert "What wearable provides raw sensor data?" in input_text
    assert "Movesense Sensor" in input_text
