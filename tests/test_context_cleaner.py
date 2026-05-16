"""Tests for core.context_cleaner."""

from __future__ import annotations

from core.context_cleaner import ContextCleaner


def test_is_preamble_detects_boilerplate():
    assert ContextCleaner.is_preamble("Certainly! Here is the answer.")
    assert not ContextCleaner.is_preamble("Use `pip install` to add the package.")


def test_is_postamble_detects_closing():
    assert ContextCleaner.is_postamble("The value is 42. I hope this helps.")
    assert not ContextCleaner.is_postamble("The value is 42.")


def test_is_clean_when_no_tax():
    text = "Install dependencies with pip, then run pytest."
    assert ContextCleaner.is_clean(text)
    assert not ContextCleaner.is_clean("Certainly! I hope this helps.")


def test_distill_signal_preserves_code_block():
    raw = (
        "Certainly! Here is the code.\n\n"
        "```python\nprint(1)\n```\n\n"
        "I hope this helps."
    )
    out = ContextCleaner.distill_signal(raw)
    assert "```python" in out
    assert "print(1)" in out
    assert "Certainly" not in out
    assert "I hope this helps" not in out


def test_distill_signal_keeps_structural_lines():
    raw = (
        "Great question!\n"
        "- Step one: configure Ollama\n"
        "- Step two: run index\n"
        "Let me know if you have any other questions."
    )
    out = ContextCleaner.distill_signal(raw)
    assert "configure Ollama" in out
    assert "Great question" not in out
    assert "Let me know" not in out


def test_distill_signal_empty_input():
    assert ContextCleaner.distill_signal("") == ""
    assert ContextCleaner.distill_signal("   ") == ""


def test_is_clean_empty_text():
    assert ContextCleaner.is_clean("")
    assert ContextCleaner.is_clean("   ")
