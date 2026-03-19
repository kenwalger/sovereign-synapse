"""
Vector storage layer for local semantic search over synapse documents.

Uses ChromaDB for persistence and Ollama (mxbai-embed-large) for embeddings.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import chromadb
from chromadb.config import Settings
import frontmatter
import ollama

# Default embedding model for local inference
EMBEDDING_MODEL = "mxbai-embed-large"

# Safe mode for dense technical logs; 800 chars won't exceed token limit
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
HARD_TRUNCATE_CHARS = 500  # last resort when chunk still causes 400

_logger = logging.getLogger(__name__)


def _chunk_text(text: str) -> list[str]:
    """Split text into chunks of CHUNK_SIZE chars with CHUNK_OVERLAP.

    Args:
        text: Input text to chunk.

    Returns:
        List of chunk strings.
    """
    if not text.strip():
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    while start < len(text):
        chunk = text[start : start + CHUNK_SIZE]
        if chunk.strip():
            chunks.append(chunk)
        start += step
    return chunks


def _parse_synapse_markdown(file_path: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and body from a synapse Markdown file.

    Uses python-frontmatter for robust parsing; correctly handles body content
    containing Markdown horizontal rules (---) without mis-splitting.

    Args:
        file_path: Path to the Markdown file.

    Returns:
        A tuple of (metadata dict, body text).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If frontmatter is malformed.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Synapse file not found: {file_path}")

    try:
        post = frontmatter.load(path)
    except Exception as e:
        raise ValueError(f"Failed to parse frontmatter in {file_path}: {e}") from e

    metadata = dict(post.metadata) if post.metadata else {}
    body = post.content.strip() if post.content else ""

    return metadata, body


AddResultStatus = Literal["SUCCESS", "SKIPPED", "FAILED"]


def _extract_uuid(metadata: dict[str, Any]) -> str:
    """Derive a stable string ID from metadata for ChromaDB.

    Handles non-string uuid values (e.g., parsed as int from YAML) by
    coercing to string before calling str methods.
    """
    uuid_val = metadata.get("uuid")
    if uuid_val is None:
        return ""
    if not isinstance(uuid_val, str):
        return str(uuid_val)
    # Normalize URN form to a short ID
    if uuid_val.startswith("urn:uuid:"):
        return uuid_val.replace("urn:uuid:", "")
    return uuid_val


class VectorStore:
    """
    ChromaDB-backed vector store for synapse documents with Ollama embeddings.
    """

    def __init__(
        self,
        persist_directory: str = "vault/chroma",
        collection_name: str = "synapses",
        embedding_model: str = EMBEDDING_MODEL,
    ) -> None:
        """Initialize the vector store.

        Args:
            persist_directory: Directory for ChromaDB persistence.
            collection_name: Name of the ChromaDB collection.
            embedding_model: Ollama model used for embeddings.
        """
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._embedding_model = embedding_model
        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, text: str, *, is_query: bool = False) -> list[float]:
        """Generate embedding vector for the given text via Ollama.

        Args:
            text: Input text to embed.
            is_query: If True, log WARNING when truncating (query strings).

        Returns:
            A list of floats representing the embedding vector, or empty list
            if the response contains no embeddings.
        """
        if len(text) > CHUNK_SIZE:
            text = text[:CHUNK_SIZE]
            if is_query:
                _logger.warning("Query string truncated to %d chars for embedding", CHUNK_SIZE)
        response = ollama.embed(model=self._embedding_model, input=text)
        embeddings = response.embeddings if response.embeddings else []
        if not embeddings:
            return []
        return list(embeddings[0])

    def add_synapse(self, file_path: str) -> tuple[AddResultStatus, str]:
        """Read a synapse Markdown file, extract metadata, and add to the store.

        Parses the file for YAML frontmatter and body, generates an embedding
        via Ollama (mxbai-embed-large), and upserts the document into ChromaDB.

        Args:
            file_path: Path to the synapse Markdown file.

        Returns:
            A tuple (status, doc_id). status is "SUCCESS" (added), "SKIPPED"
            (duplicate), or "FAILED" (embedding error). doc_id is always a string;
            exceptions are raised for true failures (parse error, missing uuid).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If frontmatter is malformed or uuid is missing.
            ollama.ResponseError: If Ollama is unreachable or returns an error.
        """
        metadata, body = _parse_synapse_markdown(file_path)

        doc_id = _extract_uuid(metadata)
        if not doc_id:
            raise ValueError(f"No uuid in frontmatter for {file_path}")

        chunks = _chunk_text(body)
        if not chunks:
            _logger.warning("Empty body for %s; skipping", file_path)
            return ("FAILED", doc_id)

        if len(chunks) > 1:
            filename = Path(file_path).name
            _logger.info(
                "Splitting %s into %d chunks due to length.",
                filename,
                len(chunks),
            )

        # ChromaDB metadata values must be str, int, float, or bool
        safe_metadata: dict[str, str | int | float | bool] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                safe_metadata[key] = value
            else:
                safe_metadata[key] = str(value)

        def _embed_with_retry(chunk: str, chunk_idx: int) -> list[float] | None:
            """Embed chunk; on 400, retry with hard truncation to HARD_TRUNCATE_CHARS."""
            try:
                return self._embed(chunk)
            except ollama.ResponseError as e:
                if e.status_code != 400:
                    raise
                if len(chunk) <= HARD_TRUNCATE_CHARS:
                    raise
                fallback = chunk[:HARD_TRUNCATE_CHARS]
                _logger.info(
                    "Chunk %d for %s caused 400; retrying with %d-char truncation",
                    chunk_idx + 1,
                    file_path,
                    HARD_TRUNCATE_CHARS,
                )
                try:
                    return self._embed(fallback)
                except ollama.ResponseError as e2:
                    if e2.status_code == 400:
                        _logger.critical(
                            "Chunk %d for %s still fails after truncation: %s",
                            chunk_idx + 1,
                            file_path,
                            e2,
                        )
                        return None
                    raise

        # All-or-nothing: embed all chunks before any upsert
        embeddings_list: list[list[float]] = []
        try:
            for i, chunk in enumerate(chunks):
                emb = _embed_with_retry(chunk, i)
                if not emb:
                    return ("FAILED", doc_id)
                embeddings_list.append(emb)
        except ollama.ResponseError as e:
            if e.status_code == 400:
                _logger.warning(
                    "Ollama 400 (context length?) for %s: %s; skipping",
                    file_path,
                    e,
                )
            else:
                raise
            return ("FAILED", doc_id)

        # All embeddings succeeded; delete-before-add for atomic re-indexing
        uuid_val = metadata.get("uuid") or f"urn:uuid:{doc_id}"
        try:
            self._collection.delete(where={"uuid": {"$eq": uuid_val}})
        except Exception:
            pass  # No existing entries or metadata format differs; proceed with add

        # Atomic upsert (single call per file)
        if len(chunks) == 1:
            self._collection.upsert(
                ids=[doc_id],
                embeddings=[embeddings_list[0]],
                documents=[chunks[0]],
                metadatas=[safe_metadata],
            )
        else:
            ids_batch = [f"{doc_id}#chunk-{i}" for i in range(len(chunks))]
            metadatas_batch = [{**safe_metadata, "part": i} for i in range(len(chunks))]
            self._collection.upsert(
                ids=ids_batch,
                embeddings=embeddings_list,
                documents=chunks,
                metadatas=metadatas_batch,
            )

        return ("SUCCESS", doc_id)

    def query(self, text: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Return the top matching synapses for the given query text.

        Embeds the query via Ollama and retrieves the nearest neighbors from
        ChromaDB by cosine similarity.

        Args:
            text: Query string to search for.
            n_results: Maximum number of results to return.

        Returns:
            List of dicts with keys: id, document, metadata, distance.
            Empty list if the query embedding fails or the collection is empty.
        """
        if n_results <= 0:
            return []
        if self._collection.count() == 0:
            return []

        try:
            embedding = self._embed(text, is_query=True)
        except ollama.ResponseError as e:
            _logger.error("Query embedding failed: %s", e)
            return []
        if not embedding:
            return []

        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        documents = results["documents"][0] if results["documents"] else [""] * len(ids)
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
        distances = results["distances"][0] if results["distances"] else [None] * len(ids)

        return [
            {
                "id": doc_id,
                "document": doc or "",
                "metadata": meta or {},
                "distance": dist,
            }
            for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances)
        ]
