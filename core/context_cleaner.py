import re

class ContextCleaner:
    """
    Heuristic-based scanner to identify and flag AI conversational noise.
    """
    
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
        # Escaped the ? to match the literal character
        r".*Is there anything else I can assist you with\?$", 
        r".*Let me know if you have any other questions\.?$"
    ]

    @classmethod
    def is_preamble(cls, text: str) -> bool:
        """Checks if the start of the text is AI boilerplate."""
        if not text:
            return False
        sample = text[:200].strip()
        return any(re.match(p, sample, re.IGNORECASE | re.DOTALL) for p in cls.PREAMBLE_PATTERNS)

    @classmethod
    def is_postamble(cls, text: str) -> bool:
        """Checks if the end of the text is AI boilerplate."""
        if not text:
            return False
        # Scan the last 200 characters using re.search for end-anchored patterns
        sample = text[-200:].strip()
        return any(re.search(p, sample, re.IGNORECASE | re.DOTALL) for p in cls.POSTAMBLE_PATTERNS)