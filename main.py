"""CLI entry point for Sovereign Synapse ingest and index pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from adapters import OpenAIAdapter
from core.vector_store import VectorStore


def cmd_ingest(args: argparse.Namespace) -> None:
    """Parse export JSON and write turn-based Markdown to vault/synapses."""
    input_file = args.path
    print(f"🏛️ Initializing Sovereign Ingest for: {input_file}")

    adapter = OpenAIAdapter(output_path="vault/synapses")
    try:
        adapter.parse(input_file)
        print("✅ Ingestion complete. Check vault/synapses for your new history.")
    except Exception as e:
        print(f"❌ Critical Error during ingestion: {e}")
        raise SystemExit(1)


def cmd_index(args: argparse.Namespace) -> None:
    """Index all synapses in vault/synapses into the vector store."""
    synapse_dir = Path("vault/synapses")
    if not synapse_dir.exists():
        print("⚠️ vault/synapses not found. Run 'ingest' first.")
        raise SystemExit(1)

    print("🧠 Indexing synapses into vector store...")
    store = VectorStore()

    count = 0
    for path in sorted(synapse_dir.glob("*.md")):
        try:
            doc_id = store.add_synapse(str(path))
            if doc_id:
                count += 1
        except Exception as e:
            print(f"⚠️ Skipped {path.name}: {e}")

    print(f"✅ Index complete. {count} synapses indexed in vault/chroma.")


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
    ingest_parser.set_defaults(func=cmd_ingest)

    index_parser = subparsers.add_parser("index", help="Index vault/synapses into vector store")
    index_parser.set_defaults(func=cmd_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
