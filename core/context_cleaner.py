"""Heuristic-based scanner for AI conversational noise detection."""

from __future__ import annotations

import re


class ContextCleaner:
    """Heuristic-based scanner to identify and flag AI conversational noise."""

    # Patterns that appear at the START of a response
    PREAMBLE_PATTERNS = [
        r"^Certainly!.*",
        r"^I'd be happy to help.*",
        r"^Excellent question.*",
        r"^As an AI language model.*",
        r"^I understand you're looking for.*",
        r"^Here is the information you requested.*"
    ]

    # Patterns that appear at the END of a response
    POSTAMBLE_PATTERNS = [
        r".*I hope this helps\.?$",
        r".*Is there anything else I can assist you with\?$",  # \? escaped for literal ?
        r".*Let me know if you have any other questions\.?$"
    ]

    @classmethod
    def is_preamble(cls, text: str) -> bool:
        """Check if the start of the text matches AI preamble boilerplate.

        Args:
            text: The response text to scan.

        Returns:
            True if the start matches a preamble pattern.
        """
        if not text:
            return False
        sample = text[:200].strip()
        return any(re.match(p, sample, re.IGNORECASE) for p in cls.PREAMBLE_PATTERNS)

    @classmethod
    def is_postamble(cls, text: str) -> bool:
        """Check if the end of the text matches AI postamble boilerplate.

        Args:
            text: The response text to scan.

        Returns:
            True if the end matches a postamble pattern.
        """
        if not text:
            return False
        # Scan the last 200 characters using re.search for end-anchored patterns
        sample = text[-200:].strip()
        return any(re.search(p, sample, re.IGNORECASE) for p in cls.POSTAMBLE_PATTERNS)
