"""Unbroken Voice — extract a Legacy Persona from the vault and write *Sovereign_Persona.json*.

Sovereign Synapse end-state: a local, private **Reasoning Fingerprint** (metaphors, values,
technical standards, phrases) distilled from the most thematically *reflective* synapses,
plus a *legacy system prompt* for the Synapse Navigator. All model calls use Ollama on
this machine only; no cloud APIs.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Project import path
# ---------------------------------------------------------------------------
import sys
from pathlib import Path
from textwrap import dedent

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import ollama
from core.vector_store import VectorStore

_logger = logging.getLogger(__name__)

# Phase 2-style “thematic reflectiveness”: rank synapses by semantic proximity to a
# fixed probe. When frontmatter `context_score` is present, treat it as boilerplate
# weight (0–1) and down-rank high values.
REFLECTIVE_PROBE = (
    "Reflective reasoning, values, trade-offs, why I care, engineering judgment, "
    "personal technical philosophy, what I would change next time, lessons learned, "
    "honest limitations, and standards I hold my work to."
)
DEFAULT_PERSONA_LLM = os.environ.get("UNBROKEN_VOICE_LLM", "llama3")
DEFAULT_N_SYNAPSES = 50
DEFAULT_CHROMA_FETCH = 400
DEFAULT_OUTPUT = Path("vault/Sovereign_Persona.json")

class LegacyExtractionError(Exception):
    """Raised when the Ollama fingerprint pass or JSON parsing fails (user-facing: Legacy Extraction Error)."""


PERSONA_USER_PROMPT = dedent("""You are a careful analyst building a *Reasoning Fingerprint* from
archived personal knowledge (human–AI turns, lab notes, etc.).

The JSON below lists excerpts from the top semantically *reflective* synapses, each with
`synapse_id` and `excerpt_text`.

Output **exactly one** JSON object (no markdown code fences) with these keys:
- "metaphors": array of strings (recurring images or analogies, max 20)
- "core_values": array of strings (ethical or priority statements, max 20)
- "technical_standards": array of strings (bar for rigor, tools, or methods, max 20)
- "characteristic_phrases": array of strings (distinctive wording, max 25)
- "legacy_system_prompt": string, 800–2000 words, in **second person** — instructions for
  an AI that will answer *as* the author, in their voice, and that must ground claims in
  cited vault evidence (Forensic Receipts) when making judgments; describe tone, what to
  avoid, and how to say "I don't have evidence" honestly.

If excerpts are thin, be conservative: generalize only where clearly supported.""")


def _parse_persona_json(raw: str) -> dict[str, Any]:
    """Strip accidental fences and parse the first JSON object from the model string."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    i = s.find("{")
    if i < 0:
        raise ValueError("No JSON in model output")
    depth = 0
    in_str = False
    esc = False
    for j, ch in enumerate(s[i:], start=i):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[i : j + 1])
    raise ValueError("Unbalanced JSON")


def _coerce_context_score(meta: dict[str, Any]) -> float | None:
    """Return ``context_score`` in [0,1] if present, else None."""
    v = meta.get("context_score")
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if 0.0 <= f <= 1.0:
        return f
    return None


def _effective_distance(distance: float | None, context_score: float | None) -> float:
    """Rank key: lower is *more* chosen for the reflective set (like vector distance)."""
    d = float(distance if distance is not None else 1.0)
    if context_score is None:
        return d
    return d * (0.4 + 0.6 * (0.2 + 0.8 * context_score))


def select_reflective_synapses(
    store: VectorStore,
    *,
    n: int = DEFAULT_N_SYNAPSES,
    over_fetch: int = DEFAULT_CHROMA_FETCH,
) -> list[dict[str, Any]]:
    """Select up to *n* unique synapses with highest thematic reflectiveness (Phase 2-style).

    Ranking uses semantic search against :data:`REFLECTIVE_PROBE` (what “reflects”
    self-authorship), with optional :attr:`context_score` from frontmatter to reduce
    boilerplate-weighted material.

    Args:
        store: The vault :class:`core.vector_store.VectorStore`.
        n: How many top unique synapse files to return (default 50).
        over_fetch: Initial Chroma ``n_results`` before deduplication and ranking.

    Returns:
        List of dicts with ``synapse_id``, ``excerpt`` (first chunk), ``metadata``,
        and ``effective_distance`` for each chosen synapse.
    """
    raw = store.query(REFLECTIVE_PROBE, n_results=max(over_fetch, n * 4))
    if not raw:
        return []
    by_bid: dict[str, dict[str, Any]] = {}
    for h in raw:
        did = h["id"]
        base = did.split("#", 1)[0]
        meta = h.get("metadata") or {}
        ctx = _coerce_context_score(meta)
        d_eff = _effective_distance(h.get("distance"), ctx)
        prev = by_bid.get(base)
        if prev is None or d_eff < prev["effective_distance"]:
            by_bid[base] = {
                "id": did,
                "doc": h.get("document") or "",
                "metadata": meta,
                "best_distance": h.get("distance"),
                "context_score": ctx,
                "effective_distance": d_eff,
            }
    items = list(by_bid.values())
    items.sort(key=lambda x: x["effective_distance"])
    out: list[dict[str, Any]] = []
    for it in items[:n]:
        meta = it["metadata"]
        uid = str(meta.get("uuid", it["id"].split("#")[0]))
        u = uid.replace("urn:uuid:", "") if "urn" in uid else it["id"].split("#")[0]
        out.append(
            {
                "synapse_id": u,
                "excerpt": (it["doc"] or "")[:6000].strip(),
                "metadata": meta,
                "effective_distance": it["effective_distance"],
            }
        )
    return out


def build_sovereign_persona_payload(
    excerpts: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    """Call a local Ollama model to produce the Reasoning Fingerprint and legacy prompt.

    Args:
        excerpts: Output of :func:`select_reflective_synapses`.
        model: Ollama chat model name (e.g. ``llama3``).

    Returns:
        A dict including ``reasoning_fingerprint`` and ``legacy_system_prompt`` keys
        ready to merge into the written JSON.

    Raises:
        ValueError: If the model output is not valid JSON.
    """
    bundle = {
        "reflective_synapse_stubs": [
            {
                "synapse_id": e["synapse_id"],
                "excerpt_text": e["excerpt"][:3000],
            }
            for e in excerpts
        ],
    }
    user = PERSONA_USER_PROMPT + "\n\n" + json.dumps(bundle, ensure_ascii=False, indent=2)
    _logger.info("Persona extraction with Ollama model %s", model)
    try:
        r = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": user}],
        )
        raw = (r.message.content or "").strip()
        return _parse_persona_json(raw)
    except ollama.ResponseError as e:
        _logger.debug("Ollama ResponseError during persona extraction", exc_info=True)
        raise LegacyExtractionError(
            f"Ollama API error (model may be missing: ollama pull {model}): {e}"
        ) from e
    except (json.JSONDecodeError, ValueError) as e:
        _logger.debug("JSON parse failed for persona model output", exc_info=True)
        raise LegacyExtractionError(f"Model output is not valid JSON: {e}") from e
    except Exception as e:
        _logger.debug("Unexpected error during legacy extraction", exc_info=True)
        n = type(e).__name__
        m = str(e).lower()
        if n == "ConnectError" or "connect" in m or "refused" in m or "http" in n.lower():
            raise LegacyExtractionError(
                f"Ollama unreachable or transport error: {e}"
            ) from e
        raise LegacyExtractionError(f"Unexpected extraction error: {e}") from e


def build_sovereign_persona_file(
    *,
    chroma_dir: str = "vault/chroma",
    output: Path = DEFAULT_OUTPUT,
    llm_model: str = DEFAULT_PERSONA_LLM,
    n: int = DEFAULT_N_SYNAPSES,
    over_fetch: int = DEFAULT_CHROMA_FETCH,
) -> dict[str, Any]:
    """Build the full document written to *Sovereign_Persona.json*.

    Args:
        chroma_dir: ChromaDB persistence path.
        output: Destination file path.
        llm_model: Ollama model for fingerprinting.
        n: Number of reflective synapses to use.
        over_fetch: Chroma pre-fetch for semantic ranking.

    Returns:
        The in-memory document dict (also written to ``output`` as UTF-8).
    """
    store = VectorStore(persist_directory=chroma_dir)
    excerpts = select_reflective_synapses(store, n=n, over_fetch=over_fetch)
    if not excerpts:
        _logger.warning("No synapses in the vault; writing minimal persona stub.")
        doc = {
            "version": 1,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "id": f"urn:uuid:{uuid.uuid4()}",
            "model_used": llm_model,
            "selection": {
                "method": "semantic_reflection_probe",
                "n": n,
                "probe": REFLECTIVE_PROBE,
                "note": "Vault was empty; run index then re-run unbroken_voice.",
            },
            "source_synapse_ids": [],
            "reasoning_fingerprint": {
                "metaphors": [],
                "core_values": [],
                "technical_standards": [],
                "characteristic_phrases": [],
            },
            "legacy_system_prompt": (
                "The vault is empty. Ingest and index content before a Legacy Persona "
                "can be defined."
            ),
        }
    else:
        body = build_sovereign_persona_payload(excerpts, llm_model)
        doc = {
            "version": 1,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "id": f"urn:uuid:{uuid.uuid4()}",
            "model_used": llm_model,
            "selection": {
                "method": "semantic_reflection_probe_top_n",
                "n": n,
                "over_fetch": over_fetch,
                "probe": REFLECTIVE_PROBE,
            },
            "source_synapse_ids": [e["synapse_id"] for e in excerpts],
            "reasoning_fingerprint": {
                "metaphors": body.get("metaphors", []),
                "core_values": body.get("core_values", []),
                "technical_standards": body.get("technical_standards", []),
                "characteristic_phrases": body.get("characteristic_phrases", []),
            },
            "legacy_system_prompt": (body.get("legacy_system_prompt") or "").strip(),
        }

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _logger.info("Wrote %s", out)
    return doc


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Unbroken Voice: build Sovereign_Persona.json (Legacy Persona) from the top "
            "thematically reflective synapses, using a local Ollama model only."
        ),
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON (default: vault/Sovereign_Persona.json)",
    )
    p.add_argument(
        "--chroma-dir",
        default="vault/chroma",
        help="ChromaDB path (default: vault/chroma)",
    )
    p.add_argument(
        "--llm",
        default=DEFAULT_PERSONA_LLM,
        help="Ollama model for extraction (default: UNBROKEN_VOICE_LLM or llama3)",
    )
    p.add_argument(
        "-n",
        type=int,
        default=DEFAULT_N_SYNAPSES,
        help="Top N reflective synapses (default: 50)",
    )
    p.add_argument(
        "--over-fetch",
        type=int,
        default=DEFAULT_CHROMA_FETCH,
        help="Chroma query size before dedup (default: 400)",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Log warnings only",
    )
    return p.parse_args()


def main() -> None:
    """CLI: extract persona and write *Sovereign_Persona.json*."""
    args = _parse_args()
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        build_sovereign_persona_file(
            chroma_dir=args.chroma_dir,
            output=args.output,
            llm_model=args.llm,
            n=args.n,
            over_fetch=args.over_fetch,
        )
    except LegacyExtractionError as e:
        print("❌ Legacy Extraction Error", str(e), file=sys.stderr)
        raise SystemExit(1) from e
    print(f"✅ Wrote {args.output}")


if __name__ == "__main__":
    main()
