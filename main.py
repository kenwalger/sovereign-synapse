"""CLI entry point for Sovereign Synapse ingest and index pipeline.

Subcommands:
  ingest PATH [-o OUTPUT]  Parse export JSON into Markdown turns.
  index [--synapses-dir DIR] [--chroma-dir DIR]  Index Markdown into vector store.
  query QUERY_STRING [--n-results N]  Semantic search over indexed synapses.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import frontmatter

from adapters import OpenAIAdapter
from core.vector_store import VectorStore

SNIPPET_MAX_LEN = 200


def _clean_snippet(doc: str, max_len: int = SNIPPET_MAX_LEN) -> str:
    """Strip boilerplate (---, created_at, updated_at); if code block, show first content line."""
    lines = doc.split("\n")
    out: list[str] = []
    after_code_fence = False
    for line in lines:
        s = line.strip()
        if s == "---" or s.startswith("created_at:") or s.startswith("updated_at:"):
            continue
        if s.startswith("```"):
            after_code_fence = True
            continue
        if s:
            out.append(line)
            if after_code_fence or not s.startswith("```"):
                break
    result = "\n".join(out) if out else doc
    return result[:max_len] + ("..." if len(result) > max_len else "")


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
            print(f"⚠️ Embedding failed for {path.name} (uuid={doc_id}); skipped.")
        else:
            raise ValueError(f"Unknown add_synapse status: {status!r}")

    print(
        f"✅ Index complete. Indexed {indexed} new synapses, skipped {skipped} existing, failed {failed}."
    )


_logger = logging.getLogger(__name__)


def _build_uuid_to_path_map(synapse_dir: Path) -> dict[str, str]:
    """Build uuid (short form) -> file path mapping. O(n) scan once."""
    mapping: dict[str, str] = {}
    if not synapse_dir.exists():
        return mapping
    for path in synapse_dir.glob("*.md"):
        try:
            post = frontmatter.load(path)
            uuid_val = post.metadata.get("uuid")
            if uuid_val is None:
                continue
            short = str(uuid_val).replace("urn:uuid:", "")
            mapping[short] = str(path)
        except Exception as e:
            _logger.debug("Failed to parse %s: %s", path, e)
    return mapping


def cmd_query(args: argparse.Namespace) -> None:
    """Run semantic search and print results to stdout.

    Args:
        args: Parsed arguments with query_string, n_results, synapses_dir, chroma_dir.
    """
    query_string = args.query_string
    n_results = args.n_results
    synapse_dir = Path(args.synapses_dir)
    chroma_dir = args.chroma_dir

    try:
        store = VectorStore(persist_directory=chroma_dir)
    except Exception as e:
        print(f"❌ Failed to initialize vector store: {e}")
        raise SystemExit(1)

    results = store.query(query_string, n_results=n_results)
    if not results:
        print("No matching synapses found.")
        return

    uuid_to_path = _build_uuid_to_path_map(synapse_dir)

    print(f"🔍 Top {len(results)} matches for: {query_string}\n")
    for i, hit in enumerate(results, 1):
        meta = hit.get("metadata") or {}
        timestamp = meta.get("original_timestamp", "—")
        doc = hit.get("document") or ""
        snippet = _clean_snippet(doc)
        doc_id = hit["id"]
        base_uuid = doc_id.split("#")[0]
        file_path = uuid_to_path.get(base_uuid)
        path_str = file_path or f"{base_uuid} (Path not found)"

        print(f"--- Result {i} ---")
        print(f"Timestamp: {timestamp}")
        print(f"Snippet: {snippet}")
        print(f"File: {path_str}")
        print()


def main() -> None:
    """Main entry point with argparse subcommands."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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

    query_parser = subparsers.add_parser("query", help="Semantic search over indexed synapses")
    query_parser.add_argument(
        "query_string",
        metavar="QUERY",
        help="Search query text",
    )
    query_parser.add_argument(
        "--n-results",
        type=int,
        default=5,
        help="Maximum number of results (default: 5)",
    )
    query_parser.add_argument(
        "--synapses-dir",
        default="vault/synapses",
        help="Directory containing synapse Markdown files (default: vault/synapses)",
    )
    query_parser.add_argument(
        "--chroma-dir",
        default="vault/chroma",
        help="ChromaDB persistence directory (default: vault/chroma)",
    )
    query_parser.set_defaults(func=cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
