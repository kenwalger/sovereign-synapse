"""Forensic receipt alignment tests for OpenAIAdapter."""

from __future__ import annotations

from datetime import datetime, timezone

from adapters.openai_adapter import OpenAIAdapter


def test_generate_forensic_receipt_matches_write_turn_signature(tmp_path):
    """generate_forensic_receipt must use the same distill_and_sign inputs as write_turn."""
    adapter = OpenAIAdapter(output_path=str(tmp_path))
    ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    user = "How do I index synapses?"
    assistant = (
        "Certainly! Run python main.py index after ingest.\n"
        "- Ensure Ollama is running.\n"
        "I hope this helps."
    )

    receipt = adapter.generate_forensic_receipt(user, assistant, ts, "openai")
    adapter.write_turn(
        user_text=user,
        assistant_text=assistant,
        timestamp=ts,
        model="gpt-4o",
        original_convo_id="convo-1",
    )

    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text(encoding="utf-8")
    assert f"receipt_id: {receipt['receipt_id']}" in content
    assert f"signature_hex: {receipt['signature_hex']}" in content
