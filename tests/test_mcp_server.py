"""Tests for mcp_server/server.py tool functions.

All MCP tool functions are synchronous (they return str, not Coroutine), so
these tests are plain synchronous pytest functions.  No async framework is
required.

The live ChromaDB and Ollama services are fully mocked — no production
database or network calls are made.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import mcp_server.server as srv
from mcp_server.server import (
    REFLECT_MAX_CHARS,
    REFLECT_MAX_SNIPPETS,
    get_recent_context,
    reflect_on_memories,
    search_synapses,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Five controlled synapses with explicit timestamps (NOT in sorted order so
# the sort-under-test actually has something to do).
_SYNAPSE_IDS = [
    "aaaa0001-0000-0000-0000-000000000001",
    "bbbb0002-0000-0000-0000-000000000002",
    "cccc0003-0000-0000-0000-000000000003",
    "dddd0004-0000-0000-0000-000000000004",
    "eeee0005-0000-0000-0000-000000000005",
]
_SYNAPSE_TIMESTAMPS = [
    "2025-03-01T10:00:00+00:00",  # 3rd newest
    "2025-06-15T08:30:00+00:00",  # newest
    "2024-12-01T00:00:00+00:00",  # oldest
    "2025-05-20T17:45:00+00:00",  # 2nd newest
    "2025-01-10T12:00:00+00:00",  # 4th newest
]
_SYNAPSE_DOCS = [
    "Bicep tendon healing protocol and return-to-training schedule.",
    "Movesense wearable raw accelerometer setup via BLE.",
    "Early research on gait analysis with gyroscope data.",
    "Garmin Connect IQ SDK for custom workout metrics.",
    "Comparative study of mxbai-embed-large vs nomic-embed-text.",
]
_SYNAPSE_METAS = [
    {"original_timestamp": ts, "model": "gpt-4o", "source": "gpt_export"}
    for ts in _SYNAPSE_TIMESTAMPS
]


def _make_collection_mock(count: int = 5) -> MagicMock:
    """Return a MagicMock ChromaDB collection pre-wired with the 5 test synapses."""
    col = MagicMock()
    col.count.return_value = count

    # collection.get() — used by get_recent_context
    col.get.return_value = {
        "ids": list(_SYNAPSE_IDS),
        "documents": list(_SYNAPSE_DOCS),
        "metadatas": list(_SYNAPSE_METAS),
    }

    # collection.query() — used by search_synapses
    # Returns two chunks from the same source file to test deduplication.
    col.query.return_value = {
        "ids": [
            [
                f"{_SYNAPSE_IDS[1]}",           # best match
                f"{_SYNAPSE_IDS[1]}#chunk-1",   # duplicate of same file
                f"{_SYNAPSE_IDS[3]}",           # 2nd unique file
                f"{_SYNAPSE_IDS[0]}",           # 3rd unique file
                f"{_SYNAPSE_IDS[4]}",           # 4th unique file
            ]
        ],
        "documents": [[
            _SYNAPSE_DOCS[1],
            _SYNAPSE_DOCS[1] + " (continued)",
            _SYNAPSE_DOCS[3],
            _SYNAPSE_DOCS[0],
            _SYNAPSE_DOCS[4],
        ]],
        "metadatas": [[
            _SYNAPSE_METAS[1],
            _SYNAPSE_METAS[1],
            _SYNAPSE_METAS[3],
            _SYNAPSE_METAS[0],
            _SYNAPSE_METAS[4],
        ]],
        "distances": [[0.05, 0.07, 0.12, 0.18, 0.22]],
    }

    return col


@pytest.fixture(autouse=True)
def reset_collection_singleton():
    """Reset the module-level lazy singleton before every test.

    Ensures each test gets a clean _collection so mocks do not bleed.
    """
    srv._collection = None
    srv._chroma_client = None
    yield
    srv._collection = None
    srv._chroma_client = None


# ---------------------------------------------------------------------------
# get_recent_context
# ---------------------------------------------------------------------------


def test_get_recent_context_sorted_newest_first():
    """Verify results are ordered by original_timestamp descending."""
    col = _make_collection_mock()
    with patch("mcp_server.server._get_collection", return_value=col):
        raw = get_recent_context(n=5)

    data = json.loads(raw)
    assert "results" in data
    results = data["results"]
    assert len(results) == 5

    timestamps = [r["timestamp"] for r in results]
    assert timestamps == sorted(timestamps, reverse=True), (
        "Results must be in newest-first order"
    )
    # Explicitly: the newest synapse must appear first
    assert results[0]["timestamp"] == "2025-06-15T08:30:00+00:00"


def test_get_recent_context_respects_n_parameter():
    """Requesting n=2 must return exactly 2 unique results."""
    col = _make_collection_mock()
    with patch("mcp_server.server._get_collection", return_value=col):
        raw = get_recent_context(n=2)

    data = json.loads(raw)
    assert data["returned"] == 2
    assert len(data["results"]) == 2


def test_get_recent_context_clamps_n_below_minimum():
    """n < 1 must be clamped to 1 — tool must not crash or return 0 results."""
    col = _make_collection_mock()
    with patch("mcp_server.server._get_collection", return_value=col):
        raw = get_recent_context(n=0)

    data = json.loads(raw)
    assert data["returned"] == 1


def test_get_recent_context_clamps_n_above_maximum():
    """n > 50 must be clamped to 50; collection has 5 so 5 results returned."""
    col = _make_collection_mock()
    with patch("mcp_server.server._get_collection", return_value=col):
        raw = get_recent_context(n=999)

    data = json.loads(raw)
    # Collection only has 5 entries, so we get 5 back (≤ clamped max of 50)
    assert data["returned"] == 5


def test_get_recent_context_deduplicates_chunks():
    """Two chunk IDs from the same synapse must yield only one result entry."""
    col = _make_collection_mock()
    # Add a duplicate chunk for the first synapse
    base_id = _SYNAPSE_IDS[0]
    col.get.return_value = {
        "ids": [base_id, f"{base_id}#chunk-1"] + list(_SYNAPSE_IDS[1:]),
        "documents": [_SYNAPSE_DOCS[0], _SYNAPSE_DOCS[0] + " extra"]
                     + list(_SYNAPSE_DOCS[1:]),
        "metadatas": [_SYNAPSE_METAS[0], _SYNAPSE_METAS[0]]
                     + list(_SYNAPSE_METAS[1:]),
    }
    col.count.return_value = 6  # 5 unique + 1 extra chunk

    with patch("mcp_server.server._get_collection", return_value=col):
        raw = get_recent_context(n=10)

    data = json.loads(raw)
    synapse_ids = [r["synapse_id"] for r in data["results"]]
    assert len(synapse_ids) == len(set(synapse_ids)), (
        "Duplicate chunk IDs from the same file must be deduplicated"
    )
    assert data["returned"] == 5


def test_get_recent_context_empty_vault():
    """Empty vault must return a graceful message and an empty results list."""
    col = MagicMock()
    col.count.return_value = 0
    with patch("mcp_server.server._get_collection", return_value=col):
        raw = get_recent_context()

    data = json.loads(raw)
    assert data["results"] == []
    assert "message" in data


def test_get_recent_context_chromadb_unavailable():
    """ChromaDB connection failure must return a JSON error, not raise."""
    with patch(
        "mcp_server.server._get_collection",
        side_effect=Exception("database locked"),
    ):
        raw = get_recent_context()

    data = json.loads(raw)
    assert "error" in data
    assert "database locked" in data["error"]


# ---------------------------------------------------------------------------
# search_synapses
# ---------------------------------------------------------------------------


def test_search_synapses_deduplicates_chunks():
    """Two chunks from the same file must appear as one result entry."""
    col = _make_collection_mock()
    fake_embed = [0.1] * 1024

    with (
        patch("mcp_server.server._get_collection", return_value=col),
        patch("mcp_server.server._embed", return_value=fake_embed),
    ):
        raw = search_synapses(query="wearable sensor", n_results=5)

    data = json.loads(raw)
    results = data["results"]
    synapse_ids = [r["synapse_id"] for r in results]
    assert len(synapse_ids) == len(set(synapse_ids)), (
        "search_synapses must deduplicate chunks from the same source file"
    )
    # The mock has 5 hits but one is a duplicate, so max 4 unique results
    assert data["returned"] <= 4


def test_search_synapses_best_chunk_wins():
    """The first (closest) chunk from a duplicated file must be kept."""
    col = _make_collection_mock()
    fake_embed = [0.1] * 1024

    with (
        patch("mcp_server.server._get_collection", return_value=col),
        patch("mcp_server.server._embed", return_value=fake_embed),
    ):
        raw = search_synapses(query="wearable sensor", n_results=5)

    data = json.loads(raw)
    # The best match is _SYNAPSE_IDS[1] (distance 0.05); its duplicate
    # is _SYNAPSE_IDS[1]#chunk-1 (distance 0.07) — only the 0.05 hit survives.
    first_result = data["results"][0]
    assert first_result["synapse_id"] == _SYNAPSE_IDS[1]
    assert first_result["distance"] == 0.05


def test_search_synapses_n_results_upper_bound():
    """n_results > 50 must be silently clamped; no error raised."""
    col = _make_collection_mock()
    fake_embed = [0.1] * 1024

    with (
        patch("mcp_server.server._get_collection", return_value=col),
        patch("mcp_server.server._embed", return_value=fake_embed),
    ):
        raw = search_synapses(query="test", n_results=999)

    data = json.loads(raw)
    # Collection only has 5 entries (4 unique after dedup); must not crash
    assert "error" not in data
    assert data["returned"] <= 4


def test_search_synapses_n_results_lower_bound():
    """n_results < 1 must be clamped to 1."""
    col = _make_collection_mock()
    fake_embed = [0.1] * 1024

    with (
        patch("mcp_server.server._get_collection", return_value=col),
        patch("mcp_server.server._embed", return_value=fake_embed),
    ):
        raw = search_synapses(query="test", n_results=0)

    data = json.loads(raw)
    assert "error" not in data
    assert data["returned"] == 1


def test_search_synapses_empty_query_returns_error():
    """Blank query must return a JSON error without touching ChromaDB."""
    with patch("mcp_server.server._get_collection") as mock_col:
        raw = search_synapses(query="   ", n_results=5)

    data = json.loads(raw)
    assert "error" in data
    mock_col.assert_not_called()


def test_search_synapses_empty_vault():
    """Empty collection must return graceful message, no embedding call."""
    col = MagicMock()
    col.count.return_value = 0
    with (
        patch("mcp_server.server._get_collection", return_value=col),
        patch("mcp_server.server._embed") as mock_embed,
    ):
        raw = search_synapses(query="sensor data")

    data = json.loads(raw)
    assert data["results"] == []
    mock_embed.assert_not_called()


def test_search_synapses_embedding_failure():
    """Embedding failure must return a JSON error, not raise."""
    col = _make_collection_mock()
    with (
        patch("mcp_server.server._get_collection", return_value=col),
        patch("mcp_server.server._embed", side_effect=RuntimeError("model not found")),
    ):
        raw = search_synapses(query="test")

    data = json.loads(raw)
    assert "error" in data
    assert "Embedding failed" in data["error"]


# ---------------------------------------------------------------------------
# reflect_on_memories
# ---------------------------------------------------------------------------

_STATIC_REFLECTION = (
    "1. Theme: Wearable Sensor Integration\n"
    "   Across these memories you consistently explored low-level sensor APIs.\n\n"
    "2. Theme: Local-First AI Architecture\n"
    "   A recurring drive to keep all inference on-device.\n\n"
    "3. Theme: Rehabilitation & Performance Monitoring\n"
    "   Bridging injury recovery with quantified training data.\n\n"
    "Synthesis: Your intellectual history converges on sovereign, sensor-driven AI."
)


def _mock_ollama_chat(*args, **kwargs) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=_STATIC_REFLECTION))


def test_reflect_on_memories_returns_structured_output():
    """Verify the response contains reflection, themes, snippet_count, truncated."""
    snippets = [
        "Movesense gyroscope raw data format",
        "Bicep tendon rehab return-to-training",
        "mxbai-embed-large 1024-dim vectors",
    ]
    with patch("mcp_server.server.ollama.chat", side_effect=_mock_ollama_chat):
        raw = reflect_on_memories(snippets=snippets)

    data = json.loads(raw)
    assert data["reflection"] == _STATIC_REFLECTION
    assert isinstance(data["themes"], list)
    assert len(data["themes"]) == 3
    assert data["snippet_count"] == 3
    assert data["truncated"] is False
    assert data["truncation_reason"] is None
    assert data["llm"] == srv.REFLECT_LLM


def test_reflect_on_memories_not_truncated_small_input():
    """Small input (< both limits) must report truncated=False, reason=null."""
    snippets = ["Short snippet A", "Short snippet B"]
    with patch("mcp_server.server.ollama.chat", side_effect=_mock_ollama_chat):
        raw = reflect_on_memories(snippets=snippets)

    data = json.loads(raw)
    assert data["truncated"] is False
    assert data["truncation_reason"] is None


def test_reflect_on_memories_truncated_by_chars():
    """Input exceeding REFLECT_MAX_CHARS must set truncated=True, reason='chars'."""
    big_snippet = "x" * (REFLECT_MAX_CHARS + 1_000)
    with patch("mcp_server.server.ollama.chat", side_effect=_mock_ollama_chat):
        raw = reflect_on_memories(snippets=[big_snippet])

    data = json.loads(raw)
    assert data["truncated"] is True
    assert data["truncation_reason"] == "chars"


def test_reflect_on_memories_truncated_by_snippet_count():
    """More than REFLECT_MAX_SNIPPETS inputs must set truncated=True, reason='snippet_count'."""
    snippets = [f"Memory number {i}" for i in range(REFLECT_MAX_SNIPPETS + 5)]
    with patch("mcp_server.server.ollama.chat", side_effect=_mock_ollama_chat):
        raw = reflect_on_memories(snippets=snippets)

    data = json.loads(raw)
    assert data["truncated"] is True
    assert data["truncation_reason"] == "snippet_count"
    assert data["snippet_count"] == REFLECT_MAX_SNIPPETS


def test_reflect_on_memories_truncated_by_both_limits():
    """Exceeding both limits must set reason='snippet_count_and_chars'."""
    big_snippet = "y" * (REFLECT_MAX_CHARS // REFLECT_MAX_SNIPPETS + 1_000)
    snippets = [big_snippet] * (REFLECT_MAX_SNIPPETS + 3)
    with patch("mcp_server.server.ollama.chat", side_effect=_mock_ollama_chat):
        raw = reflect_on_memories(snippets=snippets)

    data = json.loads(raw)
    assert data["truncated"] is True
    assert data["truncation_reason"] == "snippet_count_and_chars"


def test_reflect_on_memories_empty_snippets_returns_error():
    """Empty snippets list must return a JSON error without calling Ollama."""
    with patch("mcp_server.server.ollama.chat") as mock_chat:
        raw = reflect_on_memories(snippets=[])

    data = json.loads(raw)
    assert "error" in data
    mock_chat.assert_not_called()


def test_reflect_on_memories_all_whitespace_snippets_returns_error():
    """All-whitespace snippets must return error without calling Ollama."""
    with patch("mcp_server.server.ollama.chat") as mock_chat:
        raw = reflect_on_memories(snippets=["   ", "\t", "\n"])

    data = json.loads(raw)
    assert "error" in data
    mock_chat.assert_not_called()


def test_reflect_on_memories_ollama_failure_returns_structured_error():
    """Ollama failure must return JSON with 'error' and 'hint' keys, not raise."""
    with patch(
        "mcp_server.server.ollama.chat",
        side_effect=Exception("connection refused"),
    ):
        raw = reflect_on_memories(snippets=["some memory"])

    data = json.loads(raw)
    assert "error" in data
    assert "hint" in data
    assert "ollama pull" in data["hint"]


def test_reflect_on_memories_focus_parameter_included_in_call():
    """A non-empty focus string must reach the Ollama prompt."""
    captured_prompt: list[str] = []

    def capture_chat(model, messages, **kwargs):
        captured_prompt.append(messages[0]["content"])
        return SimpleNamespace(message=SimpleNamespace(content="ok"))

    focus_text = "How do these relate to my wrist injury recovery?"
    with patch("mcp_server.server.ollama.chat", side_effect=capture_chat):
        reflect_on_memories(snippets=["Memory A"], focus=focus_text)

    assert captured_prompt, "ollama.chat must have been called"
    assert focus_text in captured_prompt[0], (
        "Focus text must appear in the prompt sent to Ollama"
    )
