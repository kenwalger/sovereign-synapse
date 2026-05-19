"""Tests for core.context_cleaner."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from core.context_cleaner import (
    DEFAULT_KEYS_DIR,
    PRIVATE_KEY_FILE,
    PUBLIC_KEY_FILE,
    ContextCleaner,
    _default_keys_dir,
    ensure_signing_keypair,
    resolve_keys_dir,
)


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


def test_default_keys_dir_is_absolute_and_repo_scoped():
    keys_dir = _default_keys_dir()
    assert keys_dir.is_absolute()
    assert keys_dir == resolve_keys_dir(None)
    assert keys_dir.name == "keys"
    assert os.path.basename(os.path.dirname(keys_dir)) == "vault"
    assert os.path.normpath(str(keys_dir)) == os.path.normpath(DEFAULT_KEYS_DIR)


def test_resolve_keys_dir_normalizes_relative_override(tmp_path, monkeypatch):
    rel = "custom/keys"
    monkeypatch.chdir(tmp_path)
    resolved = resolve_keys_dir(rel)
    assert resolved.is_absolute()
    assert resolved == (tmp_path / "custom" / "keys").resolve()


def test_ensure_signing_keypair_raises_on_orphan_private_only(tmp_path):
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(parents=True)
    (keys_dir / PRIVATE_KEY_FILE).write_bytes(b"-----BEGIN PRIVATE KEY-----\n")
    with pytest.raises(RuntimeError, match="incomplete"):
        ensure_signing_keypair(keys_dir)


def test_ensure_signing_keypair_raises_on_orphan_public_only(tmp_path):
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(parents=True)
    (keys_dir / PUBLIC_KEY_FILE).write_text("aa" * 32, encoding="utf-8")
    with pytest.raises(RuntimeError, match="orphan"):
        ensure_signing_keypair(keys_dir)


def test_ensure_signing_keypair_creates_files(tmp_path):
    keys_dir = tmp_path / "keys"
    ensure_signing_keypair(keys_dir)
    assert (keys_dir / PRIVATE_KEY_FILE).is_file()
    assert (keys_dir / PUBLIC_KEY_FILE).is_file()
    pub_before = (keys_dir / PUBLIC_KEY_FILE).read_text(encoding="utf-8")
    ensure_signing_keypair(keys_dir)
    assert (keys_dir / PUBLIC_KEY_FILE).read_text(encoding="utf-8") == pub_before


def test_distill_and_sign_returns_forensic_fields(tmp_path):
    keys_dir = tmp_path / "keys"
    ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    signed = ContextCleaner.distill_and_sign(
        "What is Paris?",
        (
            "Certainly! Here are the facts:\n"
            "- The capital of France is Paris.\n"
            "I hope this helps."
        ),
        ts,
        "openai",
        keys_dir=keys_dir,
    )
    assert signed["uuid"] == signed["receipt_id"]
    assert str(signed["receipt_id"]).startswith("urn:synapse:receipt:")
    assert len(str(signed["signature_hex"])) == 128
    assert signed["prose_tax_redacted"] is True
    assert "Paris" in str(signed["structural_signal"])


def test_distill_and_sign_verifies_signature(tmp_path):
    keys_dir = tmp_path / "keys"
    ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    user = "Explain BLE sensors."
    assistant = "Use a Movesense IMU for raw accelerometer data."
    signed = ContextCleaner.distill_and_sign(
        user,
        assistant,
        ts,
        "openai",
        keys_dir=keys_dir,
    )
    assert ContextCleaner.verify_signature(
        str(signed["signature_hex"]),
        receipt_id=str(signed["receipt_id"]),
        structural_signal=str(signed["structural_signal"]),
        user_text=user,
        timestamp=ts,
        keys_dir=keys_dir,
    )


def test_distill_and_sign_deterministic_receipt_id(tmp_path):
    keys_dir = tmp_path / "keys"
    ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    a = ContextCleaner.distill_and_sign("hi", "hello", ts, "openai", keys_dir=keys_dir)
    b = ContextCleaner.distill_and_sign("hi", "hello", ts, "openai", keys_dir=keys_dir)
    assert a["receipt_id"] == b["receipt_id"]
    assert a["signature_hex"] == b["signature_hex"]
