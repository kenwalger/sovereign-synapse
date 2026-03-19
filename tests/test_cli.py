"""Tests for main.py CLI subcommands."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.vector_store import CHUNK_SIZE
from main import cmd_index, cmd_query


def _run_cli(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run main.py with given args, return completed process.

    Args:
        args: CLI arguments (e.g., ["ingest", "path"]).
        cwd: Working directory; defaults to project root.

    Returns:
        Completed process with stdout, stderr, returncode.
    """
    return subprocess.run(
        [sys.executable, "main.py"] + args,
        cwd=cwd or Path.cwd(),
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_ingest_requires_path() -> None:
    """Verify 'ingest' subcommand requires a path argument."""
    result = _run_cli(["ingest"])
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


def test_ingest_with_valid_file_uses_tmp_path(tmp_path: Path) -> None:
    """Verify ingest writes only to the specified --output directory."""
    convo_json = tmp_path / "convos.json"
    convo_json.write_text(
        """[
  {
    "id": "conv-1",
    "title": "Test",
    "mapping": {
      "n1": {
        "message": {
          "author": {"role": "user"},
          "content": {"parts": ["Hello?"]},
          "create_time": 1719000000
        },
        "children": ["n2"]
      },
      "n2": {
        "message": {
          "author": {"role": "assistant"},
          "content": {"parts": ["Hi!"]}
        }
      }
    }
  }
]
""",
        encoding="utf-8",
    )

    output_dir = tmp_path / "synapses"
    output_dir.mkdir()

    result = _run_cli(
        ["ingest", str(convo_json), "--output", str(output_dir)],
    )

    assert result.returncode == 0
    assert "Ingestion complete" in result.stdout or "complete" in result.stdout.lower()

    md_files = list(output_dir.glob("*.md"))
    assert len(md_files) >= 1


def test_index_missing_synapses_dir_exits_zero(tmp_path: Path) -> None:
    """Verify index handles missing vault/synapses gracefully (exit 0, no crash)."""
    missing_dir = tmp_path / "nonexistent" / "synapses"

    result = _run_cli(
        [
            "index",
            "--synapses-dir", str(missing_dir),
            "--chroma-dir", str(tmp_path / "chroma"),
        ],
    )

    assert result.returncode == 0
    assert "not found" in result.stdout or "Run 'ingest'" in result.stdout


def test_index_subcommand_zero_state(tmp_path: Path) -> None:
    """Verify index runs in zero-state: no dependence on project filesystem.

    Creates vault/synapses in tmp_path; runs index from there. Must not crash.
    """
    vault_synapses = tmp_path / "vault" / "synapses"
    vault_synapses.mkdir(parents=True)

    result = _run_cli(
        [
            "index",
            "--synapses-dir", str(vault_synapses),
            "--chroma-dir", str(tmp_path / "vault" / "chroma"),
        ],
    )

    assert result.returncode == 0
    assert "index" in result.stdout.lower() or "Index" in result.stdout


def test_index_embedding_failure_increments_failed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify index correctly increments failed counter when embedding returns empty.

    Mocks ollama.embed to return no embeddings; cmd_index should print a WARNING
    for the file and report failed=1 in the summary.
    """
    synapse_dir = tmp_path / "synapses"
    synapse_dir.mkdir()
    synapse_file = synapse_dir / "test.md"
    synapse_file.write_text(
        """---
uuid: urn:uuid:f1e2d3c4-b5a6-7890-1234-567890abcdef
source: gpt_export
model: gpt-4o
---
### User
Test

### Assistant
Test response.
""",
        encoding="utf-8",
    )

    chroma_dir = str(tmp_path / "chroma")
    args = argparse.Namespace(synapses_dir=str(synapse_dir), chroma_dir=chroma_dir)

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = SimpleNamespace(embeddings=[])
        cmd_index(args)

    captured = capsys.readouterr()
    assert "Embedding failed" in captured.out
    assert "failed 1" in captured.out


def test_query_cli_prints_results_to_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify query subcommand prints output to stdout correctly.

    Uses a multi-chunk document; asserts Timestamp, Snippet, File path resolution.
    """
    synapse_dir = tmp_path / "synapses"
    synapse_dir.mkdir()
    long_body = "x" * (CHUNK_SIZE * 2 + 100)
    synapse_file = synapse_dir / "long-wearable.md"
    synapse_file.write_text(
        f"""---
uuid: urn:uuid:q1e2r3t4-y5u6-7890-abcd-ef1234567890
source: gpt_export
model: gpt-4o
original_timestamp: 2025-06-06T11:27:59.564000
---
### User
What wearable provides raw sensor data?

### Assistant
The Movesense Sensor by Suunto offers raw accelerometer and gyroscope data.
{long_body}
""",
        encoding="utf-8",
    )

    chroma_dir = str(tmp_path / "chroma")
    fake_embedding = [0.1] * 1024
    mock_response = SimpleNamespace(embeddings=[fake_embedding])

    with patch("core.vector_store.ollama.embed") as mock_embed:
        mock_embed.return_value = mock_response

        cmd_index(argparse.Namespace(synapses_dir=str(synapse_dir), chroma_dir=chroma_dir))
        capsys.readouterr()

        cmd_query(
            argparse.Namespace(
                query_string="wearable sensor data",
                n_results=3,
                synapses_dir=str(synapse_dir),
                chroma_dir=chroma_dir,
            ),
        )

    captured = capsys.readouterr()
    assert "Timestamp" in captured.out
    assert "Snippet" in captured.out
    assert "File" in captured.out
    assert "long-wearable.md" in captured.out
    assert "(Path not found)" not in captured.out
    # Snippet quality: multiple lines of content, skips headers/metadata
    assert "Movesense" in captured.out or "raw sensor" in captured.out
    snippet_section = captured.out.split("Snippet:")[1].split("File:")[0] if "Snippet:" in captured.out else ""
    assert "\n" in snippet_section or "Movesense" in snippet_section, "Snippet should show multi-line content, not just ### User"
    assert "uuid:" not in snippet_section and "### User" not in snippet_section, "Snippet should skip metadata and headers"
