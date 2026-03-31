"""Sovereign Synapse MCP Server.

Exposes the local ChromaDB Synapse vault to any MCP-compatible host (Cursor,
Claude Desktop, etc.) over stdio.

Tools
-----
search_synapses          Semantic search over indexed turns.
get_recent_context       Last N synapses sorted by original_timestamp (working memory).
reflect_on_memories      Identify strategic themes via Ollama (mxbai-embed-large + llm).

Run (stdio transport for Cursor):
    python mcp/server.py
or via uv:
    uv run mcp/server.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Resolve project root so imports work whether server.py is run from repo root
# or from mcp/ directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import chromadb
from chromadb.config import Settings
from mcp.server.fastmcp import FastMCP
import ollama

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHROMA_PATH = os.environ.get(
    "SYNAPSE_CHROMA_PATH",
    str(_PROJECT_ROOT / "vault" / "chroma"),
)
COLLECTION_NAME = os.environ.get("SYNAPSE_COLLECTION", "synapses")
EMBEDDING_MODEL = os.environ.get("SYNAPSE_EMBED_MODEL", "mxbai-embed-large")
REFLECT_LLM = os.environ.get("SYNAPSE_REFLECT_LLM", "llama3")
CHUNK_SIZE = 800  # match core/vector_store.py

os.environ["CHROMA_TELEMETRY_NOOP"] = "True"
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
_logger = logging.getLogger("synapse.mcp")

# ---------------------------------------------------------------------------
# ChromaDB connection  (lazy singleton, handles lock / missing collection)
# ---------------------------------------------------------------------------

_chroma_client: chromadb.PersistentClient | None = None
_collection: Any | None = None


def _get_collection() -> Any:
    """Return the ChromaDB collection, creating a lazy client if needed."""
    global _chroma_client, _collection
    if _collection is not None:
        return _collection

    try:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        _collection = _chroma_client.get_collection(name=COLLECTION_NAME)
        _logger.info(
            "Connected to ChromaDB at %s — collection '%s' (%d items)",
            CHROMA_PATH,
            COLLECTION_NAME,
            _collection.count(),
        )
    except Exception as e:
        _logger.error("Failed to connect to ChromaDB: %s", e)
        raise

    return _collection


def _embed(text: str) -> list[float]:
    """Embed text using the configured Ollama model."""
    text = text[:CHUNK_SIZE]
    response = ollama.embed(model=EMBEDDING_MODEL, input=text)
    embeddings = getattr(response, "embeddings", None) or []
    if not embeddings:
        raise RuntimeError(f"Ollama returned no embeddings for model '{EMBEDDING_MODEL}'")
    return list(embeddings[0])


def _format_hit(
    doc_id: str,
    document: str,
    metadata: dict[str, Any],
    distance: float | None,
) -> dict[str, Any]:
    """Convert a raw ChromaDB hit to a clean dict for MCP response."""
    base_uuid = doc_id.split("#")[0]
    return {
        "id": base_uuid,
        "chunk_id": doc_id,
        "snippet": document[:600].strip() if document else "",
        "timestamp": str(metadata.get("original_timestamp", "")),
        "model": str(metadata.get("model", "")),
        "source": str(metadata.get("source", "")),
        "distance": round(distance, 4) if distance is not None else None,
    }


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="sovereign-synapse",
    instructions=(
        "You are connected to the Sovereign Synapse vault — a local-first archive of "
        "human–AI conversation turns. Use the provided tools to retrieve semantically "
        "relevant memories, recent context, and reflective synthesis."
    ),
)


@mcp.tool()
def search_synapses(query: str, n_results: int = 5) -> str:
    """Search the Synapse vault for semantically relevant memories.

    Args:
        query:     Natural language search query.
        n_results: Number of unique-file results to return (default 5).

    Returns:
        JSON array of matching snippets with metadata and similarity distance.
    """
    if not query.strip():
        return json.dumps({"error": "query must not be empty"})

    try:
        collection = _get_collection()
    except Exception as e:
        return json.dumps({"error": f"ChromaDB unavailable: {e}"})

    if collection.count() == 0:
        return json.dumps({"results": [], "message": "Vault is empty — run index first."})

    try:
        embedding = _embed(query)
    except Exception as e:
        return json.dumps({"error": f"Embedding failed: {e}"})

    fetch_n = max(n_results * 4, 10)
    try:
        raw = collection.query(
            query_embeddings=[embedding],
            n_results=min(fetch_n, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        return json.dumps({"error": f"ChromaDB query error: {e}"})

    ids = raw.get("ids", [[]])[0]
    docs = raw.get("documents", [[]])[0]
    metas = raw.get("metadatas", [[]])[0]
    dists = raw.get("distances", [[]])[0]

    # Deduplicate by base UUID (same file, different chunk → keep best)
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
        base = doc_id.split("#")[0]
        if base in seen:
            continue
        seen.add(base)
        results.append(_format_hit(doc_id, doc, meta, dist))
        if len(results) >= n_results:
            break

    return json.dumps({"results": results, "query": query, "returned": len(results)}, indent=2)


@mcp.tool()
def get_recent_context(n: int = 10) -> str:
    """Retrieve the most recently indexed synapses as working memory.

    Sorts by original_timestamp (descending) across all indexed chunks,
    deduplicates to unique source files, and returns the top N.

    Args:
        n: Number of recent unique synapses to return (default 10).

    Returns:
        JSON array of recent synapses with snippet and timestamp.
    """
    if n < 1:
        n = 1
    if n > 50:
        n = 50

    try:
        collection = _get_collection()
    except Exception as e:
        return json.dumps({"error": f"ChromaDB unavailable: {e}"})

    count = collection.count()
    if count == 0:
        return json.dumps({"results": [], "message": "Vault is empty — run index first."})

    try:
        # Fetch more than N to allow dedup; cap at collection size
        raw = collection.get(
            limit=min(n * 4, count),
            include=["documents", "metadatas"],
        )
    except Exception as e:
        return json.dumps({"error": f"ChromaDB fetch error: {e}"})

    ids = raw.get("ids") or []
    docs = raw.get("documents") or []
    metas = raw.get("metadatas") or []

    items = list(zip(ids, docs, metas))

    # Sort by original_timestamp descending (string ISO sort works for our format)
    items.sort(
        key=lambda t: str(t[2].get("original_timestamp", "") if t[2] else ""),
        reverse=True,
    )

    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for doc_id, doc, meta in items:
        base = doc_id.split("#")[0]
        if base in seen:
            continue
        seen.add(base)
        results.append(_format_hit(doc_id, doc or "", meta or {}, None))
        if len(results) >= n:
            break

    return json.dumps({"results": results, "returned": len(results)}, indent=2)


@mcp.tool()
def reflect_on_memories(snippets: list[str], focus: str = "") -> str:
    """Identify strategic themes and connections across retrieved memory snippets.

    Sends the snippets to a local Ollama LLM and asks it to surface 3 themes,
    patterns, or strategic insights — functioning as an internal reflection step.

    Args:
        snippets: List of text snippets retrieved from the vault.
        focus:    Optional guiding question or topic for the reflection.

    Returns:
        JSON with the model's reflection text and the 3 identified themes.
    """
    if not snippets:
        return json.dumps({"error": "snippets list must not be empty"})

    combined = "\n\n---\n\n".join(s.strip() for s in snippets if s.strip())
    if not combined:
        return json.dumps({"error": "all snippets were empty"})

    focus_line = f"\n\nFocus question: {focus}" if focus.strip() else ""
    prompt = (
        "You are a senior knowledge architect reviewing a set of memory excerpts "
        "from a personal knowledge vault. Each excerpt is a snippet of a past "
        "human–AI conversation.\n\n"
        "Your task:\n"
        "1. Identify exactly 3 strategic themes or meaningful connections present "
        "across these memories.\n"
        "2. For each theme, give it a concise title and a 2-3 sentence explanation.\n"
        "3. End with a single-sentence synthesis that captures the overarching insight.\n"
        f"{focus_line}\n\n"
        "=== MEMORY EXCERPTS ===\n\n"
        f"{combined}\n\n"
        "=== END EXCERPTS ===\n\n"
        "Respond in plain text. Be precise and strategic."
    )

    try:
        response = ollama.chat(
            model=REFLECT_LLM,
            messages=[{"role": "user", "content": prompt}],
        )
        reflection_text: str = response.message.content or ""
    except Exception as e:
        return json.dumps(
            {
                "error": f"Ollama LLM call failed: {e}",
                "hint": f"Ensure '{REFLECT_LLM}' is available: ollama pull {REFLECT_LLM}",
            }
        )

    # Best-effort: extract 3 theme titles from the response (lines with leading digits)
    import re
    theme_lines = re.findall(r"(?:^|\n)\s*(?:\d+[.)]\s*)(.+)", reflection_text)
    themes = [t.strip() for t in theme_lines[:3]] if theme_lines else []

    return json.dumps(
        {
            "reflection": reflection_text,
            "themes": themes,
            "snippet_count": len(snippets),
            "llm": REFLECT_LLM,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _logger.info("Starting Sovereign Synapse MCP server (stdio transport)")
    _logger.info("  ChromaDB path : %s", CHROMA_PATH)
    _logger.info("  Collection    : %s", COLLECTION_NAME)
    _logger.info("  Embed model   : %s", EMBEDDING_MODEL)
    _logger.info("  Reflect LLM   : %s", REFLECT_LLM)
    mcp.run(transport="stdio")
