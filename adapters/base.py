"""Abstract base class for LLM export adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BaseAdapter(ABC):
    """Abstract base class for all LLM data adapters."""

    @abstractmethod
    def parse(self, file_path: str) -> None:
        """Parse provider-specific export and write turn-based Markdown.

        Args:
            file_path: Path to the export file (JSON, CSV, etc.).
        """
        ...

    @abstractmethod
    def write_turn(
        self,
        user_text: str,
        assistant_text: str,
        timestamp: datetime,
        model: str,
        original_convo_id: str,
        **kwargs: Any,
    ) -> None:
        """Write a single user/assistant turn to a synapse Markdown file.

        Args:
            user_text: The user's message content.
            assistant_text: The assistant's response content.
            timestamp: When the turn occurred.
            model: Model identifier.
            original_convo_id: Source conversation identifier.
            **kwargs: Provider-specific additional fields.
        """
        ...
