"""Temporal Mirror — compare two time periods in the Synapse vault (local, Ollama only).

Retrieves topically relevant synapses in two date windows via the vector store, then
asks a local LLM to reason about evolution, contradictions, and lost knowledge, with
forensic citations to ``uuid``/synapse IDs. All inference stays on hardware (Ollama);
no cloud API calls.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Project import path (this repo is not an installed package)
# ---------------------------------------------------------------------------
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import logging
import re
import os
from dataclasses import dataclass, field
from typing import Any

import ollama

from core.vector_store import VectorStore

_logger = logging.getLogger(__name__)

# Default: align with mcp_server reflect
DEFAULT_LLM = os.environ.get("TEMPORAL_MIRROR_LLM", "llama3")
DEFAULT_N_PER_ERA = 5
# Over-fetch semantic hits before date filtering; must be high enough to fill two ranges
DEFAULT_FETCH = 200


# --- Temporal Mirror system prompt (local Ollama) --------------------------------
TEMPORAL_MIRROR_SYSTEM = dedent("""You are the Temporal Mirror.

You compare two eras of thought from a single person's or team's knowledge vault. You
only use the provided excerpts; do not invent material that is not supported by the
excerpts. When you state a claim, tie it to the relevant synapse receipt ID(s) using
the exact UUID format given (e.g. a1b2c3d4-...).

Identify clearly:
- Evolutionary Changes: Where did the understanding, method, or hypothesis improve or mature?
- Direct Contradictions: Where does an earlier conclusion or assumption conflict with a later one? Quote or paraphrase precisely.
- Lost Knowledge: What concrete details, numbers, methods, or caveats appear in the older notes but are absent, diluted, or contradicted in the newer set?

If one era has little or no data, state that and reason only from what exists.

End with a short "Forensic summary" table listing which synapse IDs you relied on for each main point (Era 1 vs Era 2). Use Markdown.""")


@dataclass
class EraContext:
    """Labeled search hits for one date window, ready for prompting and the report."""

    label: str
    range_spec: str
    items: list[dict[str, Any]] = field(default_factory=list)  # synapse_id, chunk_id, distance, doc, metadata


@dataclass
class ParsedRange:
    """Inclusive [start, end] UTC for filtering synapse times."""

    start: datetime
    end: datetime


def parse_inclusive_date_range(spec: str) -> ParsedRange:
    """Parse ``"YYYY"`` or ``"YYYY-YYYY"`` into inclusive UTC start/end.

    Args:
        spec: User string such as ``"2005-2010"`` or ``"2024"``.

    Returns:
        Half-open [start, end) style via inclusive end-of-year for two-year form.

    Raises:
        ValueError: If the format is invalid.
    """
    s = spec.strip()
    m = re.match(r"^(\d{4})\s*-\s*(\d{4})$", s)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y1 > y2:
            y1, y2 = y2, y1
        start = datetime(y1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(y2, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return ParsedRange(start=start, end=end)
    m1 = re.match(r"^(\d{4})$", s)
    if m1:
        y = int(m1.group(1))
        start = datetime(y, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return ParsedRange(start=start, end=end)
    raise ValueError(
        f"Invalid range {spec!r}. Use a single year (YYYY) or a span (YYYY-YYYY).",
    )


def _metadata_datetime(meta: dict[str, Any]) -> datetime | None:
    """Best-effort instant from Chroma/synapse metadata for temporal filtering.

    Args:
        meta: Chunk metadata (includes ``original_timestamp`` or ``original_year``).

    Returns:
        UTC :class:`datetime` for comparison, or ``None`` if unknown.
    """
    raw = meta.get("original_timestamp")
    if raw is not None and str(raw).strip() and str(raw) not in ("—", "-", ""):
        if isinstance(raw, datetime):
            dt = raw
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        dtp = _parse_timestamp_string(str(raw).strip())
        if dtp is not None:
            if dtp.tzinfo is None:
                dtp = dtp.replace(tzinfo=timezone.utc)
            return dtp.astimezone(timezone.utc)
    yraw = meta.get("original_year")
    if yraw is not None:
        m = re.match(r"^(\d{4})$", str(yraw).strip())
        if m:
            y = int(m.group(1))
            return datetime(y, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return None


def _parse_timestamp_string(s: str) -> datetime | None:
    """Parse common ISO-8601 and space-separated timestamps from frontmatter (stdlib only)."""
    if not s or s in ("—", "-"):
        return None
    t0 = s.replace("Z", "+00:00")
    if " " in t0 and "T" not in t0 and len(t0) > 10:
        t0 = t0.replace(" ", "T", 1)
    cands: list[str] = [t0, t0[:10] if len(t0) >= 10 else ""]
    if len(t0) >= 19:
        cands.append(t0[:19])
    for c in cands:
        if len(c) < 4:
            continue
        try:
            return datetime.fromisoformat(c)
        except ValueError:
            continue
    return None


def _in_range(when: datetime | None, r: ParsedRange) -> bool:
    """True if ``when`` falls in ``r`` (inclusive end)."""
    if when is None:
        return False
    return r.start <= when <= r.end


def _base_uuid_from_hit(doc_id: str) -> str:
    """Chroma id may be ``uuid`` or ``uuid#chunk-N``."""
    return doc_id.split("#", 1)[0]


def retrieve_for_era(
    store: VectorStore,
    query_text: str,
    date_range: ParsedRange,
    *,
    top_n: int,
    over_fetch: int,
) -> list[dict[str, Any]]:
    """Run semantic search and return up to ``top_n`` unique synapses in the given window.

    Results are ordered by Chroma distance (smaller = more similar), best first.

    Args:
        store: Vector store bound to the vault.
        query_text: Topic (embedded with the project embedding model).
        date_range: Inclusive range filter.
        top_n: Maximum unique files to return for this era.
        over_fetch: How many vector hits to pull before date filtering.
    """
    n_fetch = min(max(over_fetch, top_n * 6), 5000)
    raw = store.query(query_text, n_results=n_fetch)
    if not raw:
        return []
    by_uuid: dict[str, dict[str, Any]] = {}
    for h in raw:
        meta = h.get("metadata") or {}
        when = _metadata_datetime(meta)
        if not _in_range(when, date_range):
            continue
        bid = _base_uuid_from_hit(h["id"])
        dist = h.get("distance")
        if bid not in by_uuid:
            by_uuid[bid] = h
        else:
            d_old = by_uuid[bid].get("distance")
            if dist is not None and (d_old is None or dist < d_old):
                by_uuid[bid] = h
    out = list(by_uuid.values())
    out.sort(
        key=lambda h: (h.get("distance") is None, h.get("distance") or float("inf")),
    )
    return out[:top_n]


def _hit_to_receipt(
    h: dict[str, Any],
    era_name: str,
) -> dict[str, Any]:
    """Normalize a Chroma row for the report and LLM context."""
    meta = h.get("metadata") or {}
    bid = _base_uuid_from_hit(h["id"])
    return {
        "synapse_id": bid,
        "chunk_id": h["id"],
        "era": era_name,
        "distance": h.get("distance"),
        "snippet": (h.get("document") or "")[:2000].strip(),
        "original_timestamp": str(meta.get("original_timestamp", "")),
        "source": str(meta.get("source", "")),
        "model": str(meta.get("model", "")),
    }


def _build_user_prompt(
    topic: str,
    era1: EraContext,
    era2: EraContext,
) -> str:
    """Assemble the user message with receipts and raw snippets for the mirror LLM.

    Args:
        topic: Search / comparison subject.
        era1: First window context.
        era2: Second window context.
    """
    def block(e: EraContext) -> str:
        lines: list[str] = [
            f"### {e.label} ({e.range_spec})",
            f"Count: {len(e.items)}",
            "",
        ]
        for it in e.items:
            lines.append(
                f"- **Synapse ID (cite this):** `{it['synapse_id']}` | chunk: `{it['chunk_id']}` | "
                f"ts: {it.get('original_timestamp', '—')}",
            )
            lines.append(f"  - Snippet:\n```\n{it.get('snippet', '')}\n```\n")
        if not e.items:
            lines.append("_(No synapses in this range matched the query after date filtering.)_\n")
        return "\n".join(lines)

    return dedent(f"""\
    Topic: {topic}

    Compare the following two eras. Use the synapse IDs in square brackets in your
    answer when you attribute a claim, e.g. [synapse:xxxxxxxx-xxxx-...]

    {block(era1)}

    {block(era2)}
    """)


def run_temporal_mirror(
    topic: str,
    range1: str,
    range2: str,
    *,
    n_per_era: int = DEFAULT_N_PER_ERA,
    over_fetch: int = DEFAULT_FETCH,
    chroma_dir: str = "vault/chroma",
    llm_model: str = DEFAULT_LLM,
    out_path: Path | None = None,
) -> str:
    """Query the vault, call Ollama, and return the full Markdown report.

    Args:
        topic: Thematic search string.
        range1: First year or YYYY-YYYY.
        range2: Second year or YYYY-YYYY.
        n_per_era: Top unique synapse hits per range after filtering.
        over_fetch: Chroma result cap before time filtering.
        chroma_dir: Chroma persistence directory.
        llm_model: Local Ollama chat model name.
        out_path: If set, write the same Markdown to this file.

    Returns:
        The report body as a Markdown string.

    Raises:
        ValueError: If date ranges are invalid.
        ollama.ResponseError: If Ollama is unreachable.
    """
    p1 = parse_inclusive_date_range(range1)
    p2 = parse_inclusive_date_range(range2)
    store = VectorStore(persist_directory=chroma_dir)
    h1 = retrieve_for_era(store, topic, p1, top_n=n_per_era, over_fetch=over_fetch)
    h2 = retrieve_for_era(store, topic, p2, top_n=n_per_era, over_fetch=over_fetch)

    ctx1 = EraContext(
        label="Range 1 (first --range1 window)",
        range_spec=range1,
        items=[_hit_to_receipt(h, "1") for h in h1],
    )
    ctx2 = EraContext(
        label="Range 2 (second --range2 window)",
        range_spec=range2,
        items=[_hit_to_receipt(h, "2") for h in h2],
    )

    user = _build_user_prompt(topic, ctx1, ctx2)

    _logger.info("Calling Temporal Mirror with model %s", llm_model)
    res = ollama.chat(
        model=llm_model,
        messages=[
            {"role": "system", "content": TEMPORAL_MIRROR_SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    body = (res.message.content or "").strip()

    report = _format_report_markdown(
        topic=topic,
        range1=range1,
        range2=range2,
        llm_model=llm_model,
        ctx1=ctx1,
        ctx2=ctx2,
        analysis=body,
    )
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        _logger.info("Wrote %s", out_path)
    return report


def _format_report_markdown(
    topic: str,
    range1: str,
    range2: str,
    llm_model: str,
    ctx1: EraContext,
    ctx2: EraContext,
    analysis: str,
) -> str:
    """Assemble the official Temporal Mirror Report in Markdown with forensic blocks."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = dedent(
        f"""# Temporal Mirror Report

- **Topic:** {topic}
- **Range 1:** {range1}
- **Range 2:** {range2}
- **Generated (UTC):** {now}
- **Mirror LLM (local, Ollama):** `{llm_model}`

## Forensic Receipts: Era 1 (`{ctx1.range_spec}`)

{ _forensic_list(ctx1) }

## Forensic Receipts: Era 2 (`{ctx2.range_spec}`)

{ _forensic_list(ctx2) }

## Mirror Synthesis (Temporal Mirror)

{ analysis }

---
*Sovereign Synapse — all retrieval and generation ran locally. Synapse IDs above match Chroma/vault uuids (short form).*
""",
    )
    return head.strip() + "\n"


def _forensic_list(e: EraContext) -> str:
    """Build markdown bullet list of receipt ids and truncated snippets."""
    if not e.items:
        return "_No matching synapses in this window. Index more content in this time range, or relax the topic._\n"
    lines: list[str] = []
    for it in e.items:
        bid = it["synapse_id"]
        lines.append(
            f"- `urn:uuid:{bid}` (chunk `{it['chunk_id']}`) — {it.get('original_timestamp', '—')}\n"
            f"  - *Snippet:* {it.get('snippet', '')[:400]}{'…' if len(it.get('snippet', '')) > 400 else ''}",
        )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Temporal Mirror: compare two time periods in the local Synapse vault (Ollama, private).",
    )
    p.add_argument("topic", help='Search / comparison subject (e.g. "sensor calibration")')
    p.add_argument("--range1", required=True, help='First window: YYYY or YYYY-YYYY (e.g. "2005-2010")')
    p.add_argument("--range2", required=True, help='Second window: YYYY or YYYY-YYYY (e.g. "2024-2026")')
    p.add_argument(
        "-n",
        "--per-era",
        type=int,
        default=DEFAULT_N_PER_ERA,
        help=f"Top N unique synapses per range after time filter (default: {DEFAULT_N_PER_ERA})",
    )
    p.add_argument(
        "--fetch",
        type=int,
        default=DEFAULT_FETCH,
        help=f"Chroma over-fetch size before time filter (default: {DEFAULT_FETCH})",
    )
    p.add_argument(
        "--chroma-dir",
        default="vault/chroma",
        help="ChromaDB path (default: vault/chroma)",
    )
    p.add_argument(
        "--llm",
        default=DEFAULT_LLM,
        help=f"Ollama model for the mirror (default: {DEFAULT_LLM}, or env TEMPORAL_MIRROR_LLM)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write Markdown report to this path (default: print to stdout only)",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Log warnings only",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        report = run_temporal_mirror(
            args.topic,
            args.range1,
            args.range2,
            n_per_era=args.per_era,
            over_fetch=args.fetch,
            chroma_dir=args.chroma_dir,
            llm_model=args.llm,
            out_path=args.output,
        )
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        raise SystemExit(2) from e
    except ollama.ResponseError as e:
        print(f"❌ Ollama error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    if not args.output:
        print(report)


if __name__ == "__main__":
    main()
