"""Analog Bridge — ingest scans of physical engineering notebooks into the Synapse vault.

Transcribe notebook page images with a local Ollama vision model, emit Sovereign Markdown
(frontmatter + body) compatible with :class:`core.vector_store.VectorStore`, and index
into the ChromaDB collection.

Sovereign context: This is the "physical layer" of the knowledge estate—handwritten
lab notes, sketches, and formulas become first-class, searchable synapses.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Project import path (this repo is not an installed package)
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import ollama
import yaml
from slugify import slugify

from core.vector_store import VectorStore

_logger = logging.getLogger(__name__)

# --- Vision: Engineering Notebook HTR (handwritten text recognition) ------------

ENGINEERING_NOTEBOOK_HTR_SYSTEM = """You are a specialist in Engineering Notebook HTR
(handwritten text recognition) for R&D and lab work.

Your job is to read the attached scan of a single notebook page and extract structure
for long-term archival and search.

Non-negotiable rules:
- Preserve all dates and date-like phrases you see (margin dates, "June 2005", etc.).
- Describe diagrams and sketches in words (placement, components, labels you can read).
- Preserve mathematical content: use LaTeX in $...$ for inline and $$...$$ for
  display when possible; if a symbol is uncertain, mark it with [?].
- Extract a concise "Keywords" list: technical terms, part numbers, test names, units.
- Extract "Temporal Markers" separately: any calendar or phase references
  (e.g. "June 2005", "Week 3", "FY06") even if the exact day is not visible.
- Be faithful: do not invent experiment outcomes or values not visible in the page.
- Output format: the user message will request a single JSON object. Respond with
  that JSON only—no surrounding prose, no markdown code fences."""

# User message instructing strict JSON (filled in with optional default year)
USER_JSON_INSTRUCTION = """Transcribe this engineering notebook page.

Output exactly one JSON object (UTF-8, no markdown) with these keys:
- "keywords": array of strings
- "temporal_markers": array of strings (e.g. "June 2005", "Q2 2004")
- "diagrams": array of short strings, each describing one figure/sketch
- "formulas_latex": array of strings (each a LaTeX or plain equation line)
- "transcription": string, the full page in Markdown, preserving order and line breaks
- "inferred_year": integer or null (best year guess from the page, else null)
- "inferred_date_iso": string or null (ISO-8601 if a full date is clear, else null)

Context for missing dates: if a year cannot be read, the operator default year
may be {default_year_hint!r} — you may set inferred_year to that only when the page
gives no year at all."""


@dataclass
class ParsedHtr:
    """Structured result of vision HTR, before Sovereign Markdown emission."""

    keywords: list[str] = field(default_factory=list)
    temporal_markers: list[str] = field(default_factory=list)
    diagrams: list[str] = field(default_factory=list)
    formulas_latex: list[str] = field(default_factory=list)
    transcription: str = ""
    inferred_year: int | None = None
    inferred_date_iso: str | None = None
    raw_model_output: str = ""


def _read_image_bytes(path: Path) -> bytes:
    """Load raw bytes from an image file for hashing and (optional) encoding.

    Args:
        path: Path to a .png or .jpeg scan.

    Returns:
        File contents as bytes.

    Raises:
        OSError: If the file cannot be read.
    """
    return path.read_bytes()


def stable_synapse_uuid(image_bytes: bytes) -> str:
    """Return a stable ``urn:uuid:...`` for a given page image in the analog pipeline.

    The same image bytes always yield the same UUID, so re-running ingestion without
    changing the source file maps to a single synapse identity.

    Args:
        image_bytes: Raw image bytes (SHA-256 is used in the name).

    Returns:
        UUID string in ``urn:uuid:`` form for Sovereign frontmatter.
    """
    h = hashlib.sha256(image_bytes).hexdigest()
    u = uuid.uuid5(uuid.NAMESPACE_URL, f"sovereign-synapse/analog-v1/{h}")
    return f"urn:uuid:{u}"


def _json_load_loose(text: str) -> dict[str, Any]:
    """Parse the first JSON object in ``text``, allowing accidental fences/whitespace.

    Args:
        text: Model output, possibly containing code fences or preamble.

    Returns:
        Decoded object as a dict.

    Raises:
        ValueError: If no valid JSON object can be read.
    """
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    start = s.find("{")
    if start < 0:
        raise ValueError("No JSON object in model output")
    depth = 0
    for i, ch in enumerate(s[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = s[start : i + 1]
                return json.loads(blob)
    raise ValueError("Unbalanced JSON object in model output")


def parse_htr_json(raw: str) -> ParsedHtr:
    """Convert raw vision model output into :class:`ParsedHtr`.

    If JSON parsing fails, the full string is placed in ``transcription`` and other
    fields are left empty so the pipeline can still index the page.

    Args:
        raw: The assistant message from ``ollama.chat`` for the notebook page.

    Returns:
        A populated :class:`ParsedHtr` (possibly with only ``transcription`` set).
    """
    p = ParsedHtr(raw_model_output=raw)
    try:
        data = _json_load_loose(raw)
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning("Could not parse HTR JSON, storing raw text in body: %s", e)
        p.transcription = raw
        return p

    p.keywords = [str(x) for x in (data.get("keywords") or []) if str(x).strip()]
    p.temporal_markers = [str(x) for x in (data.get("temporal_markers") or []) if str(x).strip()]
    p.diagrams = [str(x) for x in (data.get("diagrams") or []) if str(x).strip()]
    p.formulas_latex = [str(x) for x in (data.get("formulas_latex") or []) if str(x).strip()]
    p.transcription = (data.get("transcription") or "").strip() or (
        "_(No structured transcription; see raw output in synapse if enabled.)_"
    )
    iy = data.get("inferred_year")
    if isinstance(iy, (int, float)) and 1000 <= int(iy) <= 9999:
        p.inferred_year = int(iy)
    elif isinstance(iy, str) and iy.strip().isdigit() and 1000 <= int(iy.strip()) <= 9999:
        p.inferred_year = int(iy.strip())
    else:
        p.inferred_year = None
    idiso = data.get("inferred_date_iso")
    p.inferred_date_iso = str(idiso).strip() if idiso else None
    return p


def _resolve_original_timestamp(
    p: ParsedHtr,
    default_year: int,
) -> str:
    """Build ``original_timestamp`` ISO-8601 for the synapse.

    Args:
        p: Parsed HTR with optional date fields.
        default_year: Fallback year if the model and markers give nothing usable.

    Returns:
        A timezone-aware ISO-8601 string in UTC.
    """
    if p.inferred_date_iso:
        s = p.inferred_date_iso.strip()
        s2 = s.replace("Z", "+00:00")
        try:
            if "T" in s2:
                dt = datetime.fromisoformat(s2)
            else:
                d0 = datetime.strptime(s2[:10], "%Y-%m-%d")
                dt = datetime(
                    d0.year, d0.month, d0.day, 12, 0, 0, tzinfo=timezone.utc
                )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass
    year = p.inferred_year or default_year
    return datetime(year, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()


def _original_year_str(p: ParsedHtr, default_year: int) -> str:
    """Return a four-digit ``original_year`` string for ChromaDB metadata.

    Args:
        p: Parsed HTR.
        default_year: Fallback if none inferred.

    Returns:
        A string "YYYY" suitable for frontmatter and filters.
    """
    y = p.inferred_year or default_year
    return f"{y:04d}"


def to_sovereign_markdown(
    p: ParsedHtr,
    *,
    image_stem: str,
    source_image_name: str,
    vision_model: str,
    default_year: int,
    image_bytes: bytes,
) -> str:
    """Build a Sovereign Synapse Markdown document (Phase 1.1) from parsed HTR.

    Matches the project's frontmatter + Markdown body style used for indexing.

    Args:
        p: Parsed HTR from the vision model.
        image_stem: File stem of the source scan (for logging-friendly titles).
        source_image_name: Original file name of the image.
        vision_model: Ollama vision model name (recorded in frontmatter for provenance).
        default_year: Default calendar year for timestamps when the page is undated.
        image_bytes: Raw bytes; used to compute a stable ``uuid`` in the vault.

    Returns:
        A full string ready to write as ``.md`` and pass to
        :meth:`core.vector_store.VectorStore.add_synapse`.
    """
    body_parts: list[str] = [
        f"## {image_stem}\n",
        f"*Analyzed from scan `{source_image_name}` via Ollama `{vision_model}`.*\n",
    ]
    if p.diagrams:
        body_parts.append("### Diagrams (HTR descriptions)\n")
        for d in p.diagrams:
            body_parts.append(f"- {d}\n")
        body_parts.append("\n")
    if p.formulas_latex:
        body_parts.append("### Notable formulas\n\n")
        for fline in p.formulas_latex:
            fl = fline.strip()
            if not fl:
                continue
            if (fl.startswith("$") and fl.endswith("$")) or fl.startswith("$$"):
                body_parts.append(f"- {fl}\n")
            else:
                body_parts.append(f"- ${fl}$\n")
        body_parts.append("\n")
    if p.transcription:
        body_parts.append("### Transcription\n\n")
        body_parts.append(p.transcription.rstrip() + "\n\n")
    if p.temporal_markers or p.keywords:
        body_parts.append("### Extracted index hints\n\n")
        if p.temporal_markers:
            body_parts.append("**Temporal markers:** " + "; ".join(p.temporal_markers) + "\n\n")
        if p.keywords:
            body_parts.append("**Keywords:** " + ", ".join(p.keywords) + "\n\n")

    body = "".join(body_parts).strip() + "\n"

    u = stable_synapse_uuid(image_bytes)
    ts = _resolve_original_timestamp(p, default_year)
    oy = _original_year_str(p, default_year)
    tags = p.keywords[:24]

    front: dict[str, Any] = {
        "uuid": u,
        "source": "physical_notebook",
        "model": "human",
        "htr_vision_model": vision_model,
        "tags": tags,
        "original_timestamp": ts,
        "original_year": oy,
        "htr_temporal_markers": ", ".join(p.temporal_markers) if p.temporal_markers else "",
        "source_image": source_image_name,
        "preamble": False,
        "context_score": 0.0,
    }
    if not front["htr_temporal_markers"]:
        del front["htr_temporal_markers"]

    fm = yaml.safe_dump(front, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{fm}---\n{body}"


def _out_filename(
    p: ParsedHtr,
    image_path: Path,
    image_hash_short: str,
    default_year: int,
) -> str:
    """Build ``YYYY-MM-DD-HHMM-[SLUG].md`` filename for the synapse (SYNAPSE_SPEC).

    Args:
        p: Parsed HTR (for inferred date).
        image_path: Source image path.
        image_hash_short: First 8 hex chars of image SHA-256.
        default_year: Fallback year.

    Returns:
        A safe filename ending in ``.md``.
    """
    y = p.inferred_year or default_year
    if p.inferred_date_iso and len(p.inferred_date_iso) >= 10:
        try:
            d = datetime.fromisoformat(
                p.inferred_date_iso.replace("Z", "+00:00")[:19]
            )
            y, m, d_ = d.year, d.month, d.day
        except ValueError:
            m, d_ = 1, 1
    else:
        m, d_ = 1, 1
    hh, mm = 12, 0
    slug = slugify(image_path.stem, max_length=60) or "page"
    # Ensure uniqueness: short hash in slug when two files collide on time
    return f"{y:04d}-{m:02d}-{d_:02d}-{hh:02d}{mm:02d}-analog-{image_hash_short}-{slug}.md"


def transcribe_image(
    image_path: Path,
    vision_model: str,
    default_year: int,
) -> str:
    """Run the Ollama vision model on a single page image and return raw assistant text.

    Args:
        image_path: Path to a ``.png`` or ``.jpeg`` scan.
        vision_model: Name of a local Ollama multimodal model (e.g. ``llava``).
        default_year: Hints the model for ``inferred_year`` when the page is undated.

    Returns:
        The raw ``message.content`` from ``ollama.chat`` (expected to be one JSON object).

    Raises:
        ollama.ResponseError: If Ollama returns an error.
        FileNotFoundError: If the image is missing.
    """
    if not image_path.is_file():
        raise FileNotFoundError(str(image_path))
    hint = default_year
    user = USER_JSON_INSTRUCTION.format(default_year_hint=hint)
    _logger.info("HTR: %s with %s", image_path.name, vision_model)
    response = ollama.chat(
        model=vision_model,
        messages=[
            {"role": "system", "content": ENGINEERING_NOTEBOOK_HTR_SYSTEM},
            {
                "role": "user",
                "content": user,
                "images": [str(image_path.resolve())],
            },
        ],
    )
    return (response.message.content or "").strip()


def _hitl_pause(markdown: str) -> bool:
    """Block until the operator accepts the markdown (or aborts).

    For verification of complex equations and transcription quality before vault write.

    Args:
        markdown: The full document that would be written and indexed.

    Returns:
        True to proceed with write+index, False to skip this file.
    """
    max_print = 120_000
    shown = markdown if len(markdown) <= max_print else (markdown[:max_print] + "\n\n[…truncated for display…]\n")
    print("\n" + "=" * 72)
    print("HUMAN-IN-THE-LOOP: Review transcription (formulas, sketch descriptions)\n")
    print(shown)
    print("=" * 72)
    while True:
        a = input("Press Enter to write+index, or 's' to skip: ").strip().lower()
        if a == "s":
            return False
        if a == "" or a in ("y", "ok", "yes"):
            return True
        print("  (Enter=accept, s=skip)")


def run_analog_ingest(
    input_dir: Path,
    synapses_dir: Path,
    chroma_dir: str,
    vision_model: str,
    default_year: int,
    human_in_the_loop: bool,
    image_extensions: frozenset[str],
) -> None:
    """Transcribe all images under ``input_dir`` and index into the vector store.

    Emits one Markdown file per image into ``synapses_dir`` and calls
    :class:`core.vector_store.VectorStore` to embed into the Chroma vault.

    Args:
        input_dir: Directory containing ``.png``/``.jpg`` scans.
        synapses_dir: ``vault/synapses`` (or custom) for ``.md`` output.
        chroma_dir: ChromaDB persistence path.
        vision_model: Ollama vision model name.
        default_year: Used when a page has no legible year.
        human_in_the_loop: If True, pause for operator review before write+index.
        image_extensions: Filenames must end with one of these (lowercased, with dot).
    """
    paths = sorted(
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in image_extensions
    )
    if not paths:
        _logger.warning("No %s files under %s", "/".join(sorted(image_extensions)), input_dir)
        return

    synapses_dir.mkdir(parents=True, exist_ok=True)
    store = VectorStore(persist_directory=chroma_dir)
    ok = 0
    index_unchanged = 0
    skip = 0
    err = 0
    for img in paths:
        try:
            raw = transcribe_image(img, vision_model, default_year)
        except ollama.ResponseError as e:
            _logger.error("Ollama HTR failed for %s: %s", img.name, e)
            err += 1
            continue
        except OSError as e:
            _logger.error("Read failed for %s: %s", img, e)
            err += 1
            continue

        parsed = parse_htr_json(raw)
        image_bytes = _read_image_bytes(img)
        h8 = hashlib.sha256(image_bytes).hexdigest()[:8]
        doc = to_sovereign_markdown(
            parsed,
            image_stem=img.stem,
            source_image_name=img.name,
            vision_model=vision_model,
            default_year=default_year,
            image_bytes=image_bytes,
        )
        out_name = _out_filename(parsed, img, h8, default_year)
        out_path = synapses_dir / out_name

        if human_in_the_loop and not _hitl_pause(doc):
            _logger.info("Operator skipped: %s", img.name)
            skip += 1
            continue

        out_path.write_text(doc, encoding="utf-8")
        _logger.info("Wrote %s", out_path)

        try:
            status, _ = store.add_synapse(str(out_path))
        except Exception as e:
            _logger.error("Index failed for %s: %s", out_path, e)
            err += 1
            continue
        if status == "SUCCESS":
            ok += 1
        elif status == "SKIPPED":
            index_unchanged += 1
            _logger.info("Chroma: unchanged hash, skipped: %s", out_name)
        else:
            _logger.warning("Chroma: status=%s for %s", status, out_name)
            err += 1

    print(
        f"✅ Analog Bridge complete. Newly indexed: {ok}, "
        f"index unchanged: {index_unchanged}, operator-skipped: {skip}, failed: {err}."
    )


def _parse_args() -> argparse.Namespace:
    """Parse command-line flags for the analog bridge entry point."""
    p = argparse.ArgumentParser(
        description=(
            "Transcribe engineering notebook scans with a local Ollama vision model, "
            "write Sovereign Markdown, and index into the ChromaDB vault."
        ),
    )
    p.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing .png / .jpg scans",
    )
    p.add_argument(
        "--synapses-dir",
        type=Path,
        default=Path("vault/synapses"),
        help="Output directory for .md files (default: vault/synapses)",
    )
    p.add_argument(
        "--chroma-dir",
        default="vault/chroma",
        help="ChromaDB persistence path (default: vault/chroma)",
    )
    p.add_argument(
        "--vision-model",
        default="llava",
        help="Ollama vision model, e.g. llava, llama3.2-vision, bakllava (default: llava)",
    )
    p.add_argument(
        "--default-year",
        type=int,
        default=2005,
        help="When the page has no legible year, use this in timestamps (default: 2005)",
    )
    p.add_argument(
        "--hitl",
        action="store_true",
        help="Pause after each page so the operator can verify transcriptions and equations",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print warnings and errors to the log",
    )
    return p.parse_args()


def main() -> None:
    """CLI entry: configure logging, parse args, and run the analog pipeline."""
    args = _parse_args()
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    d = args.input_dir
    if not d.is_dir():
        print(f"❌ Not a directory: {d}", file=sys.stderr)
        raise SystemExit(1)

    exts = frozenset({".png", ".jpg", ".jpeg"})
    run_analog_ingest(
        d,
        synapses_dir=Path(args.synapses_dir),
        chroma_dir=str(args.chroma_dir),
        vision_model=args.vision_model,
        default_year=args.default_year,
        human_in_the_loop=bool(args.hitl),
        image_extensions=exts,
    )


if __name__ == "__main__":
    main()
