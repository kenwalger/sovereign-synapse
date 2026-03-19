"""Tests for core.vector_store.VectorStore and related adapter behavior."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from adapters.openai_adapter import OpenAIAdapter
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


def test_add_synapse_malformed_frontmatter_uuid_type_guard(
    tmp_path: Path,
    temp_persist_dir: str,
) -> None:
    """Verify _extract_uuid type guard handles non-string uuid without AttributeError.

    When YAML parses uuid as int or float (e.g., uuid: 12345), the type guard
    coerces to str before calling .startswith(), preventing AttributeError.

    Args:
        tmp_path: Pytest temporary directory fixture.
        temp_persist_dir: Temporary ChromaDB persistence path.
    """
    malformed_content = """---
uuid: 12345
source: gpt_export
model: gpt-4o
---
### User
Test

### Assistant
Test response.
"""
    synapse_path = tmp_path / "malformed_synapse.md"
    synapse_path.write_text(malformed_content, encoding="utf-8")

    fake_embedding = [0.1] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response

        store = VectorStore(persist_directory=temp_persist_dir)
        doc_id = store.add_synapse(str(synapse_path))

    assert doc_id == "12345"


def test_write_turn_generates_unique_uuids_for_same_message_different_timestamps(
    tmp_path: Path,
) -> None:
    """Verify identical user messages with different timestamps get unique UUIDs.

    Two write_turn calls with the same user_text but different timestamps must
    produce synapse files with different uuid values in frontmatter.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    user_text = "What is the capital of France?"
    assistant_text = "The capital of France is Paris."
    convo_id = "test-convo-123"
    model = "gpt-4o"

    timestamp1 = datetime(2025, 6, 1, 10, 0, 0)
    timestamp2 = datetime(2025, 6, 1, 10, 5, 0)

    adapter.write_turn(
        user_text=user_text,
        assistant_text=assistant_text,
        timestamp=timestamp1,
        model=model,
        original_convo_id=convo_id,
    )
    adapter.write_turn(
        user_text=user_text,
        assistant_text=assistant_text,
        timestamp=timestamp2,
        model=model,
        original_convo_id=convo_id,
    )

    md_files = sorted(tmp_path.glob("*.md"))
    assert len(md_files) == 2

    uuid_pattern = re.compile(r"uuid: urn:uuid:([a-f0-9-]{36})")
    uuids = []
    for path in md_files:
        content = path.read_text(encoding="utf-8")
        match = uuid_pattern.search(content)
        assert match, f"No uuid found in {path}"
        uuids.append(match.group(1))

    assert uuids[0] != uuids[1], "Identical messages with different timestamps must have distinct UUIDs"
