"""Heuristic-based scanner for AI conversational noise detection and signal distillation."""

from __future__ import annotations

import os
import re

# Lines that are almost always prose tax (polite filler), not structural signal.
_PROSE_TAX_LINE_PATTERNS = [
    r"^Certainly[!,.]?\s*",
    r"^I'd be happy to help.*",
    r"^Excellent question[!,.]?\s*",
    r"^As an AI language model.*",
    r"^I understand you're looking for.*",
    r"^Here is the information you requested.*",
    r"^Great question[!,.]?\s*",
    r"^Of course[!,.]?\s*",
    r".*I hope this helps\.?$",
    r".*Is there anything else I can assist you with\?$",
    r".*Let me know if you have any other questions\.?$",
    r"^Feel free to ask.*",
    r"^Please let me know if.*",
]

# Heuristic: line looks like structural signal (code, lists, facts, math).
_STRUCTURAL_LINE = re.compile(
    r"(^#{1,6}\s|^\s*[-*+]\s|^\s*\d+[.)]\s|^\s*```|```$|"
    r"^\s*(def |class |import |from |const |let |var |function )|"
    r"[{}\[\]();=]|`\S+`|https?://|\d+\.\d+)",
    re.IGNORECASE,
)


class ContextCleaner:
    """Heuristic-based scanner to identify and flag AI conversational noise."""

    # Patterns that appear at the START of a response
    PREAMBLE_PATTERNS = [
        r"^Certainly!.*",
        r"^I'd be happy to help.*",
        r"^Excellent question.*",
        r"^As an AI language model.*",
        r"^I understand you're looking for.*",
        r"^Here is the information you requested.*",
    ]

    # Patterns that appear at the END of a response
    POSTAMBLE_PATTERNS = [
        r".*I hope this helps\.?$",
        r".*Is there anything else I can assist you with\?$",  # \? escaped for literal ?
        r".*Let me know if you have any other questions\.?$",
    ]

    @classmethod
    def is_preamble(cls, text: str) -> bool:
        """Check if the start of the text matches AI preamble boilerplate."""
        if not text:
            return False
        sample = text[:200].strip()
        return any(re.match(p, sample, re.IGNORECASE) for p in cls.PREAMBLE_PATTERNS)

    @classmethod
    def is_postamble(cls, text: str) -> bool:
        """Check if the end of the text matches AI postamble boilerplate."""
        if not text:
            return False
        sample = text[-200:].strip()
        return any(re.search(p, sample, re.IGNORECASE) for p in cls.POSTAMBLE_PATTERNS)

    @staticmethod
    def is_clean(text: str) -> bool:
        """Return True if the text has no detectable preamble or postamble."""
        if not text or not text.strip():
            return True
        return not ContextCleaner.is_preamble(text) and not ContextCleaner.is_postamble(
            text,
        )

    @classmethod
    def _line_is_prose_tax(cls, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        return any(re.match(p, stripped, re.IGNORECASE) for p in _PROSE_TAX_LINE_PATTERNS)

    @classmethod
    def _line_is_structural(cls, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if cls._line_is_prose_tax(stripped):
            return False
        if _STRUCTURAL_LINE.search(stripped):
            return True
        # Dense technical prose: multiple tokens with punctuation or digits
        words = stripped.split()
        if len(words) >= 4 and any(c.isdigit() for c in stripped):
            return True
        return len(stripped) > 80 and not stripped.endswith("?")

    @classmethod
    def _distill_heuristic(cls, text: str) -> str:
        """Strip prose tax; preserve fenced code blocks and structural lines."""
        if not text or not text.strip():
            return ""

        parts: list[str] = []
        fence_re = re.compile(r"^```")
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if fence_re.match(line.strip()):
                block = [line]
                i += 1
                while i < len(lines):
                    block.append(lines[i])
                    if fence_re.match(lines[i].strip()) and len(block) > 1:
                        i += 1
                        break
                    i += 1
                parts.append("\n".join(block))
                continue

            if cls._line_is_prose_tax(line):
                i += 1
                continue
            if cls._line_is_structural(line) or line.strip():
                if cls._line_is_structural(line) or (
                    line.strip() and not cls.is_preamble(line) and not cls.is_postamble(line)
                ):
                    parts.append(line)
            i += 1

        distilled = "\n".join(parts).strip()
        if not distilled:
            # Fallback: return non-boilerplate lines only
            kept = [ln for ln in lines if ln.strip() and not cls._line_is_prose_tax(ln)]
            distilled = "\n".join(kept).strip()
        return distilled

    @classmethod
    def _distill_via_ollama(cls, text: str) -> str:
        """Optional local LLM pass to remove prose tax; falls back to heuristic."""
        model = os.environ.get("SYNAPSE_DISTILL_LLM", "").strip()
        if not model:
            return cls._distill_heuristic(text)
        try:
            import ollama

            response = ollama.chat(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract only structural signal: facts, logic, code, lists, and "
                            "technical steps. Remove polite boilerplate and filler. "
                            "Preserve code blocks verbatim. Output plain text only."
                        ),
                    },
                    {"role": "user", "content": text[:12_000]},
                ],
            )
            out = (response.message.content or "").strip()
            return out if out else cls._distill_heuristic(text)
        except Exception:
            return cls._distill_heuristic(text)

    @classmethod
    def distill_signal(cls, text: str, *, use_ollama: bool | None = None) -> str:
        """Strip 'Prose Tax' and return 'Structural Signal' (code, logic, facts).

        Args:
            text: Raw assistant or document text.
            use_ollama: When True, try SYNAPSE_DISTILL_LLM; when None, honor env
                SYNAPSE_DISTILL_USE_OLLAMA=1.

        Returns:
            Distilled structural content.
        """
        if not text or not text.strip():
            return ""
        if use_ollama is None:
            use_ollama = os.environ.get("SYNAPSE_DISTILL_USE_OLLAMA", "").lower() in (
                "1",
                "true",
                "yes",
            )
        if use_ollama:
            return cls._distill_via_ollama(text)
        return cls._distill_heuristic(text)
