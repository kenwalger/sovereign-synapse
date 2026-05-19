"""Heuristic prose-tax distillation and Ed25519 signing for Sovereign Synapses."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

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

_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_CORE_DIR, os.pardir))
DEFAULT_KEYS_DIR = os.path.abspath(os.path.join(_REPO_ROOT, "vault", "keys"))
PRIVATE_KEY_FILE = "sovereign_signing.key"
PUBLIC_KEY_FILE = "sovereign_signing.pub"
FORENSIC_INTEGRITY_VERSION = "1.0"
_logger = logging.getLogger(__name__)


def _default_keys_dir() -> Path:
    """Absolute vault/keys path (repo root), independent of process CWD."""
    override = os.environ.get("SYNAPSE_KEYS_DIR", "").strip()
    if override:
        return Path(os.path.abspath(override))
    return Path(DEFAULT_KEYS_DIR)


def resolve_keys_dir(keys_dir: Path | str | None = None) -> Path:
    """Resolve signing key directory to an absolute path."""
    if keys_dir is None:
        return _default_keys_dir()
    return Path(os.path.abspath(str(keys_dir)))


def _permission_error_read(path: Path, purpose: str) -> RuntimeError:
    return RuntimeError(
        f"Cannot read Sovereign Synapse signing material at {path} ({purpose}): "
        "permission denied. Ensure this process can read files under vault/keys/ "
        f"({PRIVATE_KEY_FILE} and {PUBLIC_KEY_FILE}), or set SYNAPSE_KEYS_DIR to a "
        "directory with correct ACLs for ingest and MCP."
    )


def _read_key_bytes(path: Path, purpose: str) -> bytes:
    """Read a key file; translate ``PermissionError`` into a clear ``RuntimeError``."""
    try:
        return path.read_bytes()
    except PermissionError as exc:
        raise _permission_error_read(path, purpose) from exc


def _read_key_text(path: Path, purpose: str) -> str:
    """Read a key file as UTF-8 text; translate ``PermissionError`` into ``RuntimeError``."""
    try:
        return path.read_text(encoding="utf-8")
    except PermissionError as exc:
        raise _permission_error_read(path, purpose) from exc


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write *data* to *path* atomically via a temp file in the same directory.

    Temp files are always created under ``path.parent`` (e.g. ``vault/keys/``), never
    in the system temp folder, so ``os.replace`` stays on one filesystem (avoids EXDEV).
    """
    path = Path(path)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(directory),
    )
    tmp = Path(tmp_path)
    if tmp.parent.resolve() != directory.resolve():
        os.close(fd)
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Atomic key write failed: temporary file {tmp} is not in {directory}. "
            "Refusing a cross-device replace that would raise EXDEV."
        )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def ensure_signing_keypair(keys_dir: Path | str | None = None) -> Path:
    """Create an Ed25519 key pair under *keys_dir* when none exists.

    Never overwrites a lone key file if its pair is missing (anti-orphan guard).
    Initial creation uses atomic writes so partial files cannot be left behind.

    Returns:
        Path to the directory containing ``sovereign_signing.key`` and
        ``sovereign_signing.pub``.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    directory = resolve_keys_dir(keys_dir)
    directory.mkdir(parents=True, exist_ok=True)
    priv_path = directory / PRIVATE_KEY_FILE
    pub_path = directory / PUBLIC_KEY_FILE

    priv_exists = priv_path.is_file()
    pub_exists = pub_path.is_file()

    if priv_exists and pub_exists:
        return directory

    if priv_exists != pub_exists:
        present = PRIVATE_KEY_FILE if priv_exists else PUBLIC_KEY_FILE
        missing = PUBLIC_KEY_FILE if priv_exists else PRIVATE_KEY_FILE
        raise RuntimeError(
            f"Sovereign Synapse signing key pair is incomplete under {directory}: "
            f"found {present} but missing {missing}. "
            "Restore the missing file from backup, or remove both files to generate "
            "a new pair. Refusing to overwrite a single key file — that would orphan "
            "existing signatures."
        )

    private_key = Ed25519PrivateKey.generate()
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    _atomic_write_bytes(priv_path, priv_bytes)
    _atomic_write_text(pub_path, pub_bytes.hex())
    try:
        os.chmod(priv_path, 0o600)
    except OSError:
        pass
    return directory


def _load_private_key(keys_dir: Path) -> Any:
    from cryptography.hazmat.primitives import serialization

    priv_path = keys_dir / PRIVATE_KEY_FILE
    if not priv_path.is_file():
        ensure_signing_keypair(keys_dir)
    data = _read_key_bytes(priv_path, "Ed25519 private signing key")
    return serialization.load_pem_private_key(data, password=None)


def _load_public_key_bytes(keys_dir: Path) -> bytes:
    pub_path = keys_dir / PUBLIC_KEY_FILE
    if not pub_path.is_file():
        ensure_signing_keypair(keys_dir)
    return bytes.fromhex(_read_key_text(pub_path, "Ed25519 public signing key").strip())


def _deterministic_receipt_id(user_text: str, timestamp: datetime, source: str) -> str:
    seed = f"{user_text}|{timestamp.isoformat()}|{source}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"urn:synapse:receipt:{digest}"


def _signing_payload(
    receipt_id: str,
    structural_signal: str,
    user_text: str,
    timestamp: datetime,
) -> bytes:
    canonical = (
        f"{receipt_id}\n"
        f"{timestamp.isoformat()}\n"
        f"{structural_signal}\n"
        f"{user_text}"
    )
    return canonical.encode("utf-8")


class ContextCleaner:
    """Heuristic-based scanner to identify and flag AI conversational noise."""

    PREAMBLE_PATTERNS = [
        r"^Certainly!.*",
        r"^I'd be happy to help.*",
        r"^Excellent question.*",
        r"^As an AI language model.*",
        r"^I understand you're looking for.*",
        r"^Here is the information you requested.*",
    ]

    POSTAMBLE_PATTERNS = [
        r".*I hope this helps\.?$",
        r".*Is there anything else I can assist you with\?$",
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
        """Strip 'Prose Tax' and return 'Structural Signal' (code, logic, facts)."""
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

    @classmethod
    def verify_signature(
        cls,
        signature_hex: str,
        *,
        receipt_id: str,
        structural_signal: str,
        user_text: str,
        timestamp: datetime,
        keys_dir: Path | None = None,
    ) -> bool:
        """Return True when *signature_hex* validates the canonical signing payload."""
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        directory = resolve_keys_dir(keys_dir)
        try:
            public_key = Ed25519PublicKey.from_public_bytes(_load_public_key_bytes(directory))
            payload = _signing_payload(receipt_id, structural_signal, user_text, timestamp)
            public_key.verify(bytes.fromhex(signature_hex), payload)
            return True
        except (InvalidSignature, ValueError, OSError):
            return False
        except (PermissionError, FileNotFoundError, RuntimeError) as exc:
            _logger.warning(
                "Cannot verify Sovereign Synapse signature: public signing key "
                "unavailable or inaccessible (%s). Ensure vault/keys/ is readable "
                "by this process or set SYNAPSE_KEYS_DIR with correct permissions.",
                exc,
            )
            return False

    @classmethod
    def distill_and_sign(
        cls,
        user_text: str,
        assistant_text: str,
        timestamp: datetime,
        source: str = "openai",
        *,
        keys_dir: Path | None = None,
        use_ollama: bool | None = None,
    ) -> dict[str, str | bool]:
        """Distill assistant prose tax, anchor a forensic receipt, and Ed25519-sign the turn.

        Generates a local Ed25519 key pair under ``vault/keys/`` (or ``SYNAPSE_KEYS_DIR``)
        when no signing material exists yet.

        Returns:
            Frontmatter-ready fields: ``uuid``, ``receipt_id``, ``structural_signal``,
            ``prose_tax_redacted``, ``signature_hex``, ``forensic_receipt``,
            ``forensic_integrity``, ``preamble``, ``postamble``.
        """
        directory = resolve_keys_dir(keys_dir)
        ensure_signing_keypair(directory)

        structural_signal = cls.distill_signal(assistant_text, use_ollama=use_ollama)
        prose_tax_redacted = not cls.is_clean(assistant_text) or (
            structural_signal.strip() != assistant_text.strip()
        )
        receipt_id = _deterministic_receipt_id(user_text, timestamp, source)

        private_key = _load_private_key(directory)
        payload = _signing_payload(receipt_id, structural_signal, user_text, timestamp)
        signature_hex = private_key.sign(payload).hex()

        return {
            "uuid": receipt_id,
            "receipt_id": receipt_id,
            "structural_signal": structural_signal,
            "prose_tax_redacted": prose_tax_redacted,
            "signature_hex": signature_hex,
            "forensic_receipt": FORENSIC_INTEGRITY_VERSION,
            "forensic_integrity": FORENSIC_INTEGRITY_VERSION,
            "preamble": cls.is_preamble(assistant_text),
            "postamble": cls.is_postamble(assistant_text),
        }
