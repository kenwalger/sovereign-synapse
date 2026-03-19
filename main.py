"""CLI entry point for Sovereign Synapse ingest and index pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from adapters import OpenAIAdapter
from core.vector_store import VectorStore


def cmd_ingest(args: argparse.Namespace) -> None:
    """Parse export JSON and write turn-based Markdown.

    Args:
        args: Parsed arguments with path and output.
    """
    input_file = args.path
    output_path = args.output
    print(f"🏛️ Initializing Sovereign Ingest for: {input_file}")

    adapter = OpenAIAdapter(output_path=output_path)
    try:
        adapter.parse(input_file)
        print(f"✅ Ingestion complete. Check {output_path} for your new history.")
    except Exception as e:
        print(f"❌ Critical Error during ingestion: {e}")
        raise SystemExit(1)


def cmd_index(args: argparse.Namespace) -> None:
    """Index synapses into the vector store.

    Exits with code 0 (no crash) when synapse dir is missing; logs a warning.

    Args:
        args: Parsed arguments with synapses_dir and chroma_dir.
    """
    synapse_dir = Path(args.synapses_dir)
    chroma_dir = args.chroma_dir

    if not synapse_dir.exists():
        print(f"⚠️ {synapse_dir} not found. Run 'ingest' first.")
        return

    print("🧠 Indexing synapses into vector store...")
    try:
        store = VectorStore(persist_directory=chroma_dir)
    except Exception as e:
        print(f"❌ Failed to initialize vector store: {e}")
        raise SystemExit(1)

    indexed = 0
    skipped = 0
    failed = 0
    for path in sorted(synapse_dir.glob("*.md")):
        try:
            status, doc_id = store.add_synapse(str(path))
        except Exception as e:
            failed += 1
            print(f"⚠️ Skipped {path.name}: {e}")
            continue

        if status == "SUCCESS":
            indexed += 1
        elif status == "SKIPPED":
            skipped += 1
        elif status == "FAILED":
            failed += 1
            print(f"⚠️ Embedding failed for {path.name} (uuid={doc_id or '?'}); skipped.")
        else:
            raise ValueError(f"Unknown add_synapse status: {status!r}")

    print(
        f"✅ Index complete. Indexed {indexed} new synapses, skipped {skipped} existing, failed {failed}."
    )


def main() -> None:
    """Main entry point with argparse subcommands."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Sovereign Synapse: Ingest LLM exports and index for semantic search.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Parse export JSON into Markdown turns")
    ingest_parser.add_argument(
        "path",
        metavar="PATH",
        help="Path to conversations.json (or other export)",
    )
    ingest_parser.add_argument(
        "-o",
        "--output",
        default="vault/synapses",
        help="Output directory for Markdown files (default: vault/synapses)",
    )
    ingest_parser.set_defaults(func=cmd_ingest)

    index_parser = subparsers.add_parser("index", help="Index vault/synapses into vector store")
    index_parser.add_argument(
        "--synapses-dir",
        default="vault/synapses",
        help="Directory containing synapse Markdown files (default: vault/synapses)",
    )
    index_parser.add_argument(
        "--chroma-dir",
        default="vault/chroma",
        help="ChromaDB persistence directory (default: vault/chroma)",
    )
    index_parser.set_defaults(func=cmd_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
