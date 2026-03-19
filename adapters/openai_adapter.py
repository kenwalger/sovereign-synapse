"""OpenAI conversations.json adapter for Sovereign Synapse ingestion."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime

import frontmatter
from slugify import slugify

from adapters.base import BaseAdapter
from core.context_cleaner import ContextCleaner

_logger = logging.getLogger(__name__)


def _safe_join_parts(parts: list[object]) -> str:
    """Join message parts, coercing non-strings (e.g. tool-use dicts) to str."""
    return "".join([str(p) for p in parts])


class OpenAIAdapter(BaseAdapter):
    """Parses OpenAI conversations.json into Sovereign Synapse Markdown turns."""

    def __init__(self, output_path: str = "vault/synapses") -> None:
        """Initialize the adapter.

        Args:
            output_path: Directory where synapse Markdown files are written.
        """
        self.output_path = output_path

    def _generate_slug(self, text: str, length: int = 40) -> str:
        """Create a human-readable slug from the first few words of a prompt.

        Args:
            text: Source text to slugify.
            length: Maximum number of characters to use from the start of text.

        Returns:
            A URL-safe slug string.
        """
        return slugify(text[:length])

    def _content_hash(self, text: str, length: int = 6) -> str:
        """Generate a short hash of the text for filename uniqueness.

        Args:
            text: Source text to hash.
            length: Number of hex characters to return.

        Returns:
            A short hex hash string.
        """
        return hashlib.sha256(text.encode()).hexdigest()[:length]

    def parse(self, file_path: str) -> None:
        """Parse an OpenAI conversations.json export into synapse Markdown files.

        Args:
            file_path: Path to the conversations.json file.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for convo in data:
            title = convo.get("title") or "Untitled Conversation"
            mapping = convo.get("mapping", {})

            for node_id, node in mapping.items():
                message = node.get("message")
                if not message:
                    continue

                if message.get("author", {}).get("role") != "user":
                    continue

                try:
                    user_text = _safe_join_parts(
                        message.get("content", {}).get("parts", []),
                    )

                    for child_id in node.get("children", []):
                        child_node = mapping.get(child_id)
                        if not child_node:
                            continue
                        child_msg = child_node.get("message")

                        if child_msg and child_msg.get("author", {}).get("role") == "assistant":
                            assistant_text = _safe_join_parts(
                                child_msg.get("content", {}).get("parts", []),
                            )
                            create_time = message.get("create_time")
                            if create_time is None:
                                create_time = datetime.now().timestamp()
                            timestamp = datetime.fromtimestamp(create_time)

                            convo_id = convo.get("id")
                            if convo_id is None:
                                convo_id = convo.get("title")
                            if convo_id is None or convo_id == "":
                                convo_id = f"hash_{hashlib.sha256(str(mapping)[:500].encode()).hexdigest()[:12]}"
                            original_convo_id = str(convo_id)
                            self.write_turn(
                                user_text=user_text,
                                assistant_text=assistant_text,
                                timestamp=timestamp,
                                model=child_msg.get("metadata", {}).get("model_slug", "gpt-unknown"),
                                original_convo_id=original_convo_id,
                            )
                except Exception as e:
                    _logger.warning(
                        "Skipping malformed turn at node %s: %s",
                        node_id,
                        e,
                    )

    def write_turn(
        self,
        user_text: str,
        assistant_text: str,
        timestamp: datetime,
        model: str,
        original_convo_id: str,
    ) -> None:
        """Write a single user/assistant turn to a synapse Markdown file.

        Args:
            user_text: The user's message content.
            assistant_text: The assistant's response content.
            timestamp: When the turn occurred.
            model: Model identifier (e.g., gpt-4o).
            original_convo_id: Source conversation ID.
        """
        slug = self._generate_slug(user_text)
        content_hash = self._content_hash(user_text)
        filename = f"{timestamp.strftime('%Y-%m-%d-%H%M')}-{slug}-{content_hash}.md"

        has_preamble = ContextCleaner.is_preamble(assistant_text)
        has_postamble = ContextCleaner.is_postamble(assistant_text)

        # Create a unique but repeatable ID based on conversation, timestamp, and question
        seed = f"{original_convo_id}-{timestamp.isoformat()}-{user_text}"
        unique_id = uuid.uuid5(uuid.NAMESPACE_DNS, seed)

        os.makedirs(self.output_path, exist_ok=True)

        metadata = {
            "uuid": f"urn:uuid:{unique_id}",
            "source": "gpt_export",
            "model": model,
            "original_timestamp": timestamp.isoformat(),
            "original_convo_id": original_convo_id,
            "preamble": "true" if has_preamble else "false",
            "postamble": "true" if has_postamble else "false",
        }
        body = f"### User\n{user_text}\n\n### Assistant\n{assistant_text}"
        post = frontmatter.Post(content=body, **metadata)
        content = frontmatter.dumps(post)
        
        with open(os.path.join(self.output_path, filename), "w", encoding="utf-8") as f:
            f.write(content + "\n")
