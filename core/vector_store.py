"""
Vector storage layer for local semantic search over synapse documents.

Uses ChromaDB for persistence and Ollama (mxbai-embed-large) for embeddings.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import chromadb
import ollama
import yaml

# Default embedding model for local inference
EMBEDDING_MODEL = "mxbai-embed-large"

_logger = logging.getLogger(__name__)


def _parse_synapse_markdown(file_path: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and body from a synapse Markdown file.

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

    content = path.read_text(encoding="utf-8")

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n*(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError(f"No valid YAML frontmatter in {file_path}")

    frontmatter_str, body = match.group(1), match.group(2)
    metadata = yaml.safe_load(frontmatter_str)
    if metadata is None:
        metadata = {}

    return metadata, body.strip()


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
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, text: str) -> list[float]:
        """Generate embedding vector for the given text via Ollama.

        Args:
            text: Input text to embed.

        Returns:
            A list of floats representing the embedding vector, or empty list
            if the response contains no embeddings.
        """
        response = ollama.embed(model=self._embedding_model, input=text)
        embeddings = response.embeddings if response.embeddings else []
        if not embeddings:
            return []
        return list(embeddings[0])

    def add_synapse(self, file_path: str) -> str:
        """Read a synapse Markdown file, extract metadata, and add to the store.

        Parses the file for YAML frontmatter and body, generates an embedding
        via Ollama (mxbai-embed-large), and upserts the document into ChromaDB.

        Args:
            file_path: Path to the synapse Markdown file.

        Returns:
            The ChromaDB document ID (derived from uuid), or empty string if
            embeddings were empty and the document was not upserted.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If frontmatter is malformed or uuid is missing.
        """
        metadata, body = _parse_synapse_markdown(file_path)

        doc_id = _extract_uuid(metadata)
        if not doc_id:
            raise ValueError(f"No uuid in frontmatter for {file_path}")

        embedding = self._embed(body)
        if not embedding:
            _logger.warning(
                "Empty embeddings for %s; skipping upsert",
                file_path,
            )
            return ""

        # ChromaDB metadata values must be str, int, float, or bool
        safe_metadata: dict[str, str | int | float | bool] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                safe_metadata[key] = value
            else:
                safe_metadata[key] = str(value)

        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[body],
            metadatas=[safe_metadata],
        )

        return doc_id
