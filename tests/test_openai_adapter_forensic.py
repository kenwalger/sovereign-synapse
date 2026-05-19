"""Forensic receipt alignment tests for OpenAIAdapter."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from adapters.openai_adapter import OpenAIAdapter
from core.context_cleaner import DEFAULT_KEYS_DIR, PRIVATE_KEY_FILE, PUBLIC_KEY_FILE


@pytest.fixture
def isolated_keys_dir(tmp_path, monkeypatch):
    """Route signing to a unique temp directory; never touch production vault/keys/."""
    keys_dir = tmp_path / "signing_keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SYNAPSE_KEYS_DIR", str(keys_dir))
    return keys_dir


def test_generate_forensic_receipt_matches_write_turn_signature(
    tmp_path,
    isolated_keys_dir,
):
    """generate_forensic_receipt must use the same distill_and_sign inputs as write_turn."""
    prod_priv = Path(DEFAULT_KEYS_DIR) / PRIVATE_KEY_FILE
    prod_pub = Path(DEFAULT_KEYS_DIR) / PUBLIC_KEY_FILE
    prod_priv_mtime = prod_priv.stat().st_mtime if prod_priv.is_file() else None
    prod_pub_mtime = prod_pub.stat().st_mtime if prod_pub.is_file() else None

    adapter = OpenAIAdapter(output_path=str(tmp_path / "synapses"))
    ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    user = "How do I index synapses?"
    assistant = (
        "Certainly! Run python main.py index after ingest.\n"
        "- Ensure Ollama is running.\n"
        "I hope this helps."
    )

    receipt = adapter.generate_forensic_receipt(user, ts, "openai", assistant_text=assistant)
    adapter.write_turn(
        user_text=user,
        assistant_text=assistant,
        timestamp=ts,
        model="gpt-4o",
        original_convo_id="convo-1",
    )

    assert (isolated_keys_dir / PRIVATE_KEY_FILE).is_file()
    assert (isolated_keys_dir / PUBLIC_KEY_FILE).is_file()
    if prod_priv_mtime is not None:
        assert prod_priv.stat().st_mtime == prod_priv_mtime
    else:
        assert not prod_priv.is_file()
    if prod_pub_mtime is not None:
        assert prod_pub.stat().st_mtime == prod_pub_mtime
    else:
        assert not prod_pub.is_file()

    md_files = list((tmp_path / "synapses").glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text(encoding="utf-8")
    assert f"receipt_id: {receipt['receipt_id']}" in content
    assert f"signature_hex: {receipt['signature_hex']}" in content


def test_generate_forensic_receipt_legacy_three_arg_signature(tmp_path, isolated_keys_dir):
    """Legacy generate_forensic_receipt(user, timestamp, source) must remain valid."""
    adapter = OpenAIAdapter(output_path=str(tmp_path / "synapses"))
    ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    receipt = adapter.generate_forensic_receipt("Index my vault.", ts, "openai")

    assert receipt["receipt_id"].startswith("urn:synapse:receipt:")
    assert len(str(receipt["signature_hex"])) == 128
    assert receipt["structural_signal"] == ""
