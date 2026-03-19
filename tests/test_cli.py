"""Tests for main.py CLI subcommands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run main.py with given args, return completed process."""
    return subprocess.run(
        [sys.executable, "main.py"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_ingest_requires_path() -> None:
    """Verify 'ingest' subcommand requires a path argument."""
    result = _run_cli(["ingest"], Path.cwd())
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


def test_ingest_with_valid_file(tmp_path: Path) -> None:
    """Verify ingest subcommand parses JSON and writes Markdown."""
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
        ["ingest", str(convo_json)],
        Path.cwd(),
    )

    assert result.returncode == 0
    assert "Ingestion complete" in result.stdout or "complete" in result.stdout.lower()

    synapses_dir = Path("vault/synapses")
    md_files = list(synapses_dir.glob("*.md")) if synapses_dir.exists() else []
    assert len(md_files) >= 1


def test_index_subcommand_runs(tmp_path: Path) -> None:
    """Verify index subcommand runs without error (may warn if no synapses)."""
    result = _run_cli(["index"], Path.cwd())
    assert result.returncode == 0
    assert "index" in result.stdout.lower() or "Index" in result.stdout
