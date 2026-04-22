"""Tests for unbroken_voice JSON parsing and (mocked) persona payload."""

from __future__ import annotations

from unittest.mock import patch

import ollama
import pytest

from unbroken_voice import (
    LegacyExtractionError,
    _parse_persona_json,
    _effective_distance,
    build_sovereign_persona_payload,
    select_reflective_synapses,
)
from core.vector_store import VectorStore


def test_parse_persona_json_object() -> None:
    s = 'prefix {"metaphors":["x"],"core_values":["y"],"technical_standards":[],"characteristic_phrases":[],"legacy_system_prompt":"Z"}'
    o = _parse_persona_json(s)
    assert o["metaphors"] == ["x"]


def test_effective_distance_uses_context_score() -> None:
    d0 = _effective_distance(0.1, 0.0)
    d1 = _effective_distance(0.1, 1.0)
    assert d1 > d0


def test_select_reflective_monkeypatched_query(tmp_path, monkeypatch) -> None:
    def fake_query(self, text: str, n_results: int) -> list[dict]:
        return [
            {
                "id": "a-b-c-d-000000000001#chunk-0",
                "document": "I always validate on real hardware first.",
                "metadata": {
                    "uuid": "urn:uuid:a-b-c-d-000000000001",
                    "context_score": 0.1,
                },
                "distance": 0.2,
            }
        ]

    monkeypatch.setattr(VectorStore, "query", fake_query)
    store = VectorStore(persist_directory=str(tmp_path / "c"))
    out = select_reflective_synapses(store, n=5, over_fetch=10)
    assert len(out) == 1
    assert "validate" in out[0]["excerpt"]


def test_build_sovereign_persona_payload_ollama_error() -> None:
    """Ollama failures become LegacyExtractionError (not bare tracebacks in CLI)."""
    excerpt = {
        "synapse_id": "a",
        "excerpt": "x",
        "metadata": {},
        "effective_distance": 0.1,
    }
    with patch(
        "unbroken_voice.ollama.chat",
        side_effect=ollama.ResponseError("nope", status_code=500),
    ):
        with pytest.raises(LegacyExtractionError) as ex:
            build_sovereign_persona_payload([excerpt], "llama3")
    assert "Ollama" in str(ex.value) or "nope" in str(ex.value)
