"""Tests for core.vector_store.VectorStore."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.vector_store import VectorStore


@pytest.fixture
def temp_persist_dir(tmp_path: Path) -> str:
    """Provide a temporary directory for ChromaDB persistence.

    Args:
        tmp_path: Pytest built-in fixture providing a temporary directory.

    Returns:
        Path to a chroma subdirectory, cleaned up after test.
    """
    return str(tmp_path / "chroma")


@pytest.fixture
def sample_synapse_content() -> str:
    """Sample synapse Markdown with valid frontmatter.

    Returns:
        A complete synapse document string for testing.
    """
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
    tmp_path: Path,
    temp_persist_dir: str,
    sample_synapse_content: str,
) -> None:
    """Verify add_synapse parses the file and invokes the embedding function.

    Uses tmp_path for temporary synapse files (auto-cleaned). Mocks
    ollama.embed to return an EmbedResponse-like object with .embeddings.

    Args:
        tmp_path: Pytest temporary directory fixture.
        temp_persist_dir: Temporary ChromaDB persistence path.
        sample_synapse_content: Valid synapse Markdown content.
    """
    synapse_path = tmp_path / "synapse.md"
    synapse_path.write_text(sample_synapse_content, encoding="utf-8")

    fake_embedding = [0.1] * 1024  # mxbai-embed-large uses 1024-dim vectors
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response

        store = VectorStore(persist_directory=temp_persist_dir)
        doc_id = store.add_synapse(str(synapse_path))

    assert doc_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    mock_embed.assert_called_once()
    call_args = mock_embed.call_args
    assert call_args.kwargs["model"] == "mxbai-embed-large"
    input_text = call_args.kwargs["input"]
    assert "What wearable provides raw sensor data?" in input_text
    assert "Movesense Sensor" in input_text
