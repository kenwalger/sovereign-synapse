"""Tests for unbroken_voice JSON parsing and (mocked) persona payload."""

from __future__ import annotations

from unbroken_voice import _parse_persona_json, _effective_distance, select_reflective_synapses
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
