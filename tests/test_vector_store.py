"""Tests for core.vector_store.VectorStore and related adapter behavior."""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frontmatter
import pytest

from adapters.openai_adapter import OpenAIAdapter
from core.vector_store import CHUNK_SIZE, VectorStore


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
        status, doc_id = store.add_synapse(str(synapse_path))

    assert status == "SUCCESS"
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
    malformed_synapse_path = tmp_path / "malformed_synapse.md"
    malformed_synapse_path.write_text(malformed_content, encoding="utf-8")

    fake_embedding = [0.1] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response

        store = VectorStore(persist_directory=temp_persist_dir)
        status, doc_id = store.add_synapse(str(malformed_synapse_path))

    assert status == "SUCCESS"
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

    timestamp1 = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    timestamp2 = datetime(2025, 6, 1, 10, 5, 0, tzinfo=timezone.utc)

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


def test_add_synapse_handles_horizontal_rule_in_body(
    tmp_path: Path,
    temp_persist_dir: str,
) -> None:
    """Verify parser handles body content with Markdown horizontal rules (---).

    python-frontmatter correctly splits YAML from body so --- in the content
    does not confuse the parser.

    Args:
        tmp_path: Pytest temporary directory fixture.
        temp_persist_dir: Temporary ChromaDB persistence path.
    """
    content_with_hr = """---
uuid: urn:uuid:b2c3d4e5-f6a7-8901-bcde-f23456789012
source: gpt_export
model: gpt-4o
---
### User
Show me a divider.

### Assistant
Here is a horizontal rule:

---

And more text after it.
"""
    synapse_path = tmp_path / "with_hr.md"
    synapse_path.write_text(content_with_hr, encoding="utf-8")

    fake_embedding = [0.2] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response

        store = VectorStore(persist_directory=temp_persist_dir)
        status, doc_id = store.add_synapse(str(synapse_path))

    assert status == "SUCCESS"
    assert doc_id == "b2c3d4e5-f6a7-8901-bcde-f23456789012"
    # Verify the body passed to embed includes content after the ---
    call_input = mock_embed.call_args.kwargs["input"]
    assert "And more text after it" in call_input
    assert "---" in call_input


def test_parse_handles_poisoned_export_with_non_string_parts(tmp_path: Path) -> None:
    """Verify ingest does not crash when content.parts contains non-string elements.

    Real exports can include tool-use dicts; plain join(parts) would raise
    TypeError. The adapter uses str() coercion and handles malformed turns.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    poisoned_json = tmp_path / "poisoned.json"
    poisoned_json.write_text(
        """[
  {
    "id": "conv-poison",
    "title": "Poisoned",
    "mapping": {
      "n1": {
        "message": {
          "author": {"role": "user"},
          "content": {"parts": ["Hello", {"tool_use": {"id": "x", "name": "foo"}}]},
          "create_time": 1719000000
        },
        "children": ["n2"]
      },
      "n2": {
        "message": {
          "author": {"role": "assistant"},
          "content": {"parts": ["Hi!", {"type": "tool_result", "content": "ok"}]}
        }
      }
    }
  }
]
""",
        encoding="utf-8",
    )

    adapter = OpenAIAdapter(output_path=str(tmp_path))
    adapter.parse(str(poisoned_json))

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) >= 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "Hello" in content
    assert "Hi!" in content


def test_parse_list_content_part_appears_as_json_block(tmp_path: Path) -> None:
    """Verify parts with list content (e.g. content: [\"a\", \"b\"]) are not dropped.

    When content field is a list, _safe_join_parts must json.dumps it into a
    code block instead of silently dropping it (zero-data-loss).
    """
    list_content_json = tmp_path / "list_content.json"
    list_content_json.write_text(
        """[
  {
    "id": "conv-list",
    "title": "List Content",
    "mapping": {
      "n1": {
        "message": {
          "author": {"role": "user"},
          "content": {"parts": ["Question: ", {"content": ["item1", "item2", "item3"]}]},
          "create_time": 1719000000
        },
        "children": ["n2"]
      },
      "n2": {
        "message": {
          "author": {"role": "assistant"},
          "content": {"parts": ["Answer.", {"content": [{"nested": "data"}]}]}
        }
      }
    }
  }
]
""",
        encoding="utf-8",
    )

    adapter = OpenAIAdapter(output_path=str(tmp_path))
    adapter.parse(str(list_content_json))

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) >= 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "Question:" in content
    assert "Answer." in content
    assert "```json" in content
    assert "item1" in content
    assert "item2" in content
    assert "nested" in content


def test_write_turn_original_timestamp_is_utc_iso(tmp_path: Path) -> None:
    """Verify original_timestamp in frontmatter is ISO format with +00:00 UTC suffix."""
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    timestamp = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    adapter.write_turn(
        user_text="Test?",
        assistant_text="Answer.",
        timestamp=timestamp,
        model="gpt-4o",
        original_convo_id="test-convo",
    )

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    post = frontmatter.load(md_files[0])
    ts = str(post.get("original_timestamp", ""))
    assert ts
    assert "+00:00" in ts or ts.endswith("Z")
    assert isinstance(post.get("preamble"), bool)
    assert isinstance(post.get("postamble"), bool)


def test_parse_handles_none_convo_id(tmp_path: Path) -> None:
    """Verify parse() uses fallback when convo has id=None.

    Uses convo.get('title', 'unknown_convo') when convo.get('id') is None.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    convo_json = tmp_path / "convos.json"
    convo_json.write_text(
        """
[
  {
    "id": null,
    "title": "Fallback Conversation",
    "mapping": {
      "node1": {
        "message": {
          "author": {"role": "user"},
          "content": {"parts": ["What is 2+2?"]},
          "create_time": 1719000000
        },
        "children": ["node2"]
      },
      "node2": {
        "message": {
          "author": {"role": "assistant"},
          "content": {"parts": ["Four."]}
        }
      }
    }
  }
]
""",
        encoding="utf-8",
    )

    adapter.parse(str(convo_json))

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text(encoding="utf-8")
    # Should use title as fallback: "Fallback Conversation"
    assert "original_convo_id: Fallback Conversation" in content


def test_write_turn_same_minute_different_text_produces_distinct_files(tmp_path: Path) -> None:
    """Verify two turns in the same minute with different text do not overwrite.

    The content hash ensures distinct filenames.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    timestamp = datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)  # Same minute
    convo_id = "test-convo"

    adapter.write_turn(
        user_text="First question?",
        assistant_text="First answer.",
        timestamp=timestamp,
        model="gpt-4o",
        original_convo_id=convo_id,
    )
    adapter.write_turn(
        user_text="Second question?",
        assistant_text="Second answer.",
        timestamp=timestamp,
        model="gpt-4o",
        original_convo_id=convo_id,
    )

    md_files = sorted(tmp_path.glob("*.md"))
    assert len(md_files) == 2

    contents = [f.read_text(encoding="utf-8") for f in md_files]
    assert "First question?" in contents[0] and "Second question?" not in contents[0]
    assert "Second question?" in contents[1] and "First question?" not in contents[1]


def test_write_turn_title_with_special_chars_produces_valid_yaml(tmp_path: Path) -> None:
    """Verify conversation titles with # and { produce valid YAML frontmatter.

    original_convo_id (from title fallback) must be properly quoted/escaped
    when written to prevent YAML parse errors.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    adapter.write_turn(
        user_text="Test?",
        assistant_text="Answer.",
        timestamp=datetime(2025, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
        model="gpt-4o",
        original_convo_id='Bug #123 {urgent}: fix needed',
    )

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text(encoding="utf-8")

    post = frontmatter.loads(content)
    assert str(post.get("original_convo_id", "")) == "Bug #123 {urgent}: fix needed"


def test_write_turn_existing_file_different_content_not_overwritten(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify write_turn skips overwrite when file exists with different content.

    Protects manual human annotations during re-ingest: if the target file
    exists and has different content, log WARNING and do not overwrite.

    Args:
        tmp_path: Pytest temporary directory fixture.
        caplog: Pytest log capture fixture.
    """
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    user_text = "What is the answer?"
    assistant_text = "The answer is 42."
    timestamp = datetime(2025, 7, 1, 14, 30, 0, tzinfo=timezone.utc)
    convo_id = "test-convo-manual"

    adapter.write_turn(
        user_text=user_text,
        assistant_text=assistant_text,
        timestamp=timestamp,
        model="gpt-4o",
        original_convo_id=convo_id,
    )

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    path = md_files[0]
    original_content = path.read_text(encoding="utf-8")
    path.write_text(original_content + "\n\n<!-- MANUAL ANNOTATION -->\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        adapter.write_turn(
            user_text=user_text,
            assistant_text=assistant_text,
            timestamp=timestamp,
            model="gpt-4o",
            original_convo_id=convo_id,
        )

    final_content = path.read_text(encoding="utf-8")
    assert "MANUAL ANNOTATION" in final_content
    assert any("Skipping overwrite" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "WARNING" for rec in caplog.records)


def test_write_turn_identical_content_preserves_mtime(tmp_path: Path) -> None:
    """Verify re-ingest of identical content does not change file mtime.

    Idempotent I/O: when existing file content matches new content, skip write
    to avoid unnecessary disk I/O and preserve the modification timestamp.
    Uses os.utime() to set mtime in the past for reliable assertion.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    user_text = "Same content?"
    assistant_text = "Same response."
    timestamp = datetime(2025, 7, 15, 9, 0, 0, tzinfo=timezone.utc)
    convo_id = "test-convo-idempotent"

    adapter.write_turn(
        user_text=user_text,
        assistant_text=assistant_text,
        timestamp=timestamp,
        model="gpt-4o",
        original_convo_id=convo_id,
    )

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    path = md_files[0]
    mtime_past = time.time() - 3600  # 1 hour ago
    os.utime(path, (mtime_past, mtime_past))
    mtime_before = path.stat().st_mtime

    adapter.write_turn(
        user_text=user_text,
        assistant_text=assistant_text,
        timestamp=timestamp,
        model="gpt-4o",
        original_convo_id=convo_id,
    )

    mtime_after = path.stat().st_mtime
    assert mtime_before == mtime_after


def test_add_synapse_returns_skipped_when_doc_already_exists(
    tmp_path: Path,
    temp_persist_dir: str,
    sample_synapse_content: str,
) -> None:
    """Verify add_synapse returns SKIPPED when document already in collection."""
    synapse_path = tmp_path / "synapse.md"
    synapse_path.write_text(sample_synapse_content, encoding="utf-8")

    fake_embedding = [0.1] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response
        store = VectorStore(persist_directory=temp_persist_dir)
        status1, doc_id1 = store.add_synapse(str(synapse_path))
        status2, doc_id2 = store.add_synapse(str(synapse_path))

    assert status1 == "SUCCESS"
    assert status2 == "SKIPPED"
    assert doc_id1 == doc_id2 == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_add_synapse_returns_failed_when_embedding_empty(
    tmp_path: Path,
    temp_persist_dir: str,
    sample_synapse_content: str,
) -> None:
    """Verify add_synapse returns FAILED when Ollama returns no embeddings."""
    synapse_path = tmp_path / "synapse.md"
    synapse_path.write_text(sample_synapse_content, encoding="utf-8")

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = SimpleNamespace(embeddings=[])
        store = VectorStore(persist_directory=temp_persist_dir)
        status, doc_id = store.add_synapse(str(synapse_path))

    assert status == "FAILED"
    assert doc_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_add_synapse_chunks_long_document(
    tmp_path: Path,
    temp_persist_dir: str,
) -> None:
    """Verify add_synapse chunks long documents into doc_id#chunk-0, doc_id#chunk-1."""
    long_body = "x" * (CHUNK_SIZE * 2 + 100)  # > 2 chunks
    content = f"""---
uuid: urn:uuid:c1d2e3f4-a5b6-7890-cdef-123456789abc
source: gpt_export
model: gpt-4o
---
### User
Long question.

### Assistant
{long_body}
"""
    synapse_path = tmp_path / "long.md"
    synapse_path.write_text(content, encoding="utf-8")

    fake_embedding = [0.1] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response
        store = VectorStore(persist_directory=temp_persist_dir)
        status, doc_id = store.add_synapse(str(synapse_path))

    assert status == "SUCCESS"
    assert doc_id == "c1d2e3f4-a5b6-7890-cdef-123456789abc"
    assert mock_embed.call_count >= 2  # 2+ chunks
    ids = store._collection.get()["ids"]
    assert "c1d2e3f4-a5b6-7890-cdef-123456789abc#chunk-0" in ids
    assert "c1d2e3f4-a5b6-7890-cdef-123456789abc#chunk-1" in ids


def test_add_synapse_partial_chunk_failure_adds_zero_chunks(
    tmp_path: Path,
    temp_persist_dir: str,
) -> None:
    """Verify multi-chunk doc with embedding failure on second chunk adds zero chunks.

    All-or-nothing: if any chunk fails to embed, no chunks are upserted.
    """
    long_body = "x" * (CHUNK_SIZE * 2 + 100)
    content = f"""---
uuid: urn:uuid:d1e2f3a4-b5c6-7890-defa-123456789012
source: gpt_export
model: gpt-4o
---
### User
Long question.

### Assistant
{long_body}
"""
    synapse_path = tmp_path / "partial_fail.md"
    synapse_path.write_text(content, encoding="utf-8")

    call_count = 0

    def mock_embed_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return SimpleNamespace(embeddings=[])  # fail second chunk
        return SimpleNamespace(embeddings=[[0.1] * 1024])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.side_effect = mock_embed_side_effect
        store = VectorStore(persist_directory=temp_persist_dir)
        status, doc_id = store.add_synapse(str(synapse_path))

    assert status == "FAILED"
    assert doc_id == "d1e2f3a4-b5c6-7890-defa-123456789012"
    ids = store._collection.get()["ids"]
    assert "d1e2f3a4-b5c6-7890-defa-123456789012#chunk-0" not in ids
    assert "d1e2f3a4-b5c6-7890-defa-123456789012#chunk-1" not in ids
    assert len(ids) == 0


def test_vector_store_query_empty_collection_returns_empty_list(
    temp_persist_dir: str,
) -> None:
    """Verify query on empty VectorStore returns [] without crashing.

    ChromaDB raises ValueError for n_results=0 when querying; the empty
    collection guard prevents this.

    Args:
        temp_persist_dir: Temporary ChromaDB persistence path.
    """
    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = SimpleNamespace(embeddings=[[0.1] * 1024])

        store = VectorStore(persist_directory=temp_persist_dir)
        results = store.query("any query", n_results=5)

    assert results == []
    mock_embed.assert_not_called()


def test_vector_store_query_returns_top_matches(
    tmp_path: Path,
    temp_persist_dir: str,
    sample_synapse_content: str,
) -> None:
    """Verify VectorStore.query embeds query and returns top matching synapses.

    Args:
        tmp_path: Pytest temporary directory fixture.
        temp_persist_dir: Temporary ChromaDB persistence path.
        sample_synapse_content: Valid synapse Markdown content.
    """
    synapse_path = tmp_path / "synapse.md"
    synapse_path.write_text(sample_synapse_content, encoding="utf-8")

    fake_embedding = [0.1] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response

        store = VectorStore(persist_directory=temp_persist_dir)
        status, _ = store.add_synapse(str(synapse_path))
        assert status == "SUCCESS"
        results = store.query("wearable sensor data", n_results=5)

    assert len(results) == 1
    assert results[0]["id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert "Movesense" in results[0]["document"]


def test_query_returns_empty_on_embedding_failure(
    tmp_path: Path,
    temp_persist_dir: str,
    sample_synapse_content: str,
) -> None:
    """Verify query() returns [] when embedding fails instead of crashing.

    When Ollama raises ResponseError during search (e.g. 500), query must
    log the error and return [] as documented.
    """
    import ollama

    synapse_path = tmp_path / "synapse.md"
    synapse_path.write_text(sample_synapse_content, encoding="utf-8")

    fake_embedding = [0.1] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    call_count = [0]

    def embed_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_response  # add_synapse
        raise ollama.ResponseError("Connection refused", 500)  # query

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.side_effect = embed_side_effect

        store = VectorStore(persist_directory=temp_persist_dir)
        status, _ = store.add_synapse(str(synapse_path))
        assert status == "SUCCESS"

        results = store.query("wearable sensor", n_results=5)

    assert results == []
