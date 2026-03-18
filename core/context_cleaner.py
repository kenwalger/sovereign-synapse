import re

class ContextCleaner:
    """
    Heuristic-based scanner to identify and flag AI conversational noise.
    Designed to improve signal-to-noise ratio in the Cognitive Estate.
    """
    
    # Common patterns used by LLMs as conversational "filler"
    PATTERNS = [
        r"^Certainly!.*",
        r"^I'd be happy to help.*",
        r"^Excellent question.*",
        r"^As an AI language model.*",
        r"^I understand you're looking for.*",
        r"^Here is the information you requested.*",
        r"^I hope this helps.*",
        r"^Let me know if you have any other questions.*",
        r"^Is there anything else I can assist you with?.*"
    ]

    @classmethod
    def is_preamble(cls, text: str) -> bool:
        """
        Scans the start of a text block for known AI boilerplate patterns.
        
        Args:
            text: The assistant's response string.
            
        Returns:
            bool: True if the text starts with recognized "noise."
        """
        if not text:
            return False
            
        # We only scan the first 200 characters to save processing time
        # and avoid false positives in the middle of a technical explanation.
        sample = text[:200].strip()
        
        for pattern in cls.PATTERNS:
            if re.match(pattern, sample, re.IGNORECASE | re.DOTALL):
                return True
        return False