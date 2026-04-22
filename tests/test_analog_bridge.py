"""Tests for analog_bridge JSON extraction and sovereign markdown emission."""

from __future__ import annotations

import json

import frontmatter
import pytest

from analog_bridge import (
    _json_load_loose,
    _outer_json_object_slice,
    parse_htr_json,
    to_sovereign_markdown,
    ParsedHtr,
)


def test_outer_json_object_slice_ignores_braces_inside_strings() -> None:
    """LaTeX-style ``{ }`` in JSON string values must not close the outer object."""
    inner = {
        "keywords": ["k"],
        "transcription": r"Test $\frac{1}{2}$ and { nested } { braces }",
        "diagrams": [],
        "formulas_latex": ["E_{\\mathrm{k}}=mc^2"],
        "temporal_markers": ["June 2005"],
        "inferred_year": 2005,
        "inferred_date_iso": None,
    }
    text = "prefix noise " + json.dumps(inner, ensure_ascii=False)
    start = text.find("{")
    blob = _outer_json_object_slice(text, start)
    assert blob is not None
    out = json.loads(blob)
    assert "frac" in out["transcription"]
    assert "nested" in out["transcription"]


def test_json_load_loose_strips_fences() -> None:
    """Fenced JSON still parses, including LaTeX in transcription."""
    inner = {
        "keywords": [],
        "transcription": "a{b}c{d}",
        "diagrams": [],
        "formulas_latex": [],
        "temporal_markers": [],
        "inferred_year": None,
        "inferred_date_iso": None,
    }
    raw = "```json\n" + json.dumps(inner) + "\n```"
    data = _json_load_loose(raw)
    assert data["transcription"] == "a{b}c{d}"


def test_to_sovereign_markdown_valid_frontmatter_with_latex_in_body() -> None:
    """Body may contain LaTeX; frontmatter should load via python-frontmatter."""
    p = ParsedHtr(
        keywords=["spring"],
        temporal_markers=["Q1 2000"],
        transcription="Line1\n\n$$\\int_{0}^{1} f(t)\\,dt$$\n",
        diagrams=["A sketch of a {spring-mass} system with labels."],
        formulas_latex=[r"F = kx"],
    )
    md = to_sovereign_markdown(
        p,
        image_stem="p01",
        source_image_name="batch/p01.png",
        vision_model="llava",
        default_year=2005,
        image_bytes=b"fake-bytes",
    )
    post = frontmatter.loads(md)
    assert post.metadata.get("source") == "physical_notebook"
    assert post.metadata.get("original_year") == "2005"
    assert "spring-mass" in (post.content or "")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
