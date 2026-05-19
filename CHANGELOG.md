# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.35.1] - 2026-05-16 (Tests — embed_text mocks & CLI subprocess)

### Fixed (tests)
- **`tests/test_vector_store.py`**, **`tests/test_cli.py`**: Mocks for `core.vector_store.embed_text` now return **`list[float]`** (or **`[]`** for failure paths), matching `embed_text()` instead of legacy `SimpleNamespace(embeddings=[...])` objects that were truthy even when empty.
- **Call assertions**: `mock_embed.call_args.args[0]` / `args[1]` align with `(model, text)` positional signature.
- **`tests/test_cli.py::_run_cli`**: Subprocess helpers set **`PYTHONUTF8`**, **`PYTHONIOENCODING=utf-8`**, **`encoding="utf-8"` / `errors="replace"`**, and a **120s** timeout so Windows subprocess capture works with emoji in `main.py` output and cold Chroma imports.

## [0.35.0] - 2026-05-15 (Fiscal Architecture — Prose Tax, Forensic Receipts, Typed Retrieval)

### Added
- **`core/context_cleaner.ContextCleaner.distill_signal`**: Heuristic stripping of conversational boilerplate (“Prose Tax”) while preserving code blocks and structural lines; optional Ollama pass via `SYNAPSE_DISTILL_USE_OLLAMA` and `SYNAPSE_DISTILL_LLM`.
- **`ContextCleaner.is_clean`** (static): Returns `True` when no preamble or postamble prose tax is detected.
- **`schemas/synapse_manifest.json`**: JSON Schema for Sovereign Asset frontmatter and MCP Structural Contract shape (`receipt_id`, `forensic_receipt`, `structural_signal`).
- **MCP `search_synapses`**: Returns **Structural Contracts** (`metadata` with `prose_tax_redacted` and `forensic_receipt`, plus `distilled_signal` and `receipt_id`) instead of raw snippets; response includes `contract_schema` pointer.

### Changed
- **`adapters/openai_adapter`**: Deterministic `receipt_id` via SHA-256 of user text, timestamp, and source; **`uuid` in frontmatter is now the `receipt_id`** (primary Forensic Trace anchor). Frontmatter also includes `forensic_receipt`, `forensic_integrity`, `prose_tax_redacted`, and `structural_signal`.
- **`core/vector_store._extract_uuid`**: Normalizes `urn:synapse:receipt:` IDs for Chroma document keys.
- **`mcp_server/server.py`**: `_structural_contract` exposes `metadata` / `provenance` with `prose_tax_redacted` and `forensic_receipt`; `get_recent_context` still uses snippet format for working memory.

### Note
- Re-index the vault after upgrading frontmatter so Chroma metadata carries `receipt_id`, `forensic_receipt`, and `structural_signal`.

## [0.34.1] - 2026-04-22 (Unbroken Voice + MCP P2: errors, n_results log, read-only policy)

### Fixed
- **`unbroken_voice.py` — P2 error handling**: `build_sovereign_persona_payload` wraps the Ollama call and JSON parsing in try/except; raises **`LegacyExtractionError`** for :class:`ollama.ResponseError`, :exc:`json.JSONDecodeError` / :exc:`ValueError`, and common transport cases. The CLI prints **`❌ Legacy Extraction Error`** and exits `1` without a traceback on that path.
- **`mcp_server/server.py` — P2 dead code**: Removed redundant `snippet_excerpt[:800]` in `query_legacy_persona` receipts; snippets are already limited by `_format_hit` to 600 characters.
- **`mcp_server/server.py` — P2 transparency**: `_semantic_search_results` logs at **debug** when `n_results` is **capped to 50** (requested value included in the message).
- **Read-only guard**: :class:`_ReadOnlyCollection` now raises :exc:`PermissionError` (not ``RuntimeError``) on add/update/delete/upsert/modify. New **`get_vault_policy`** MCP tool returns JSON with `chroma_mutation_forbidden`, `set_via`, and `on_mutation: {error_code, python_exception}` for host-side checks before any write path.

## [0.34.0] - 2026-04-22 (Unbroken Voice — Legacy Persona, MCP, read-only vault)

### Added
- **`unbroken_voice.py`**: Build **Sovereign_Persona.json** in the vault (default `vault/Sovereign_Persona.json`). Selects the top 50 (configurable) **thematically reflective** synapses by semantic search against a fixed *reflective* probe, with optional **context_score** down-rank for boilerplate; calls a local Ollama model to produce **Reasoning Fingerprint** fields (metaphors, core values, technical standards, characteristic phrases) and a long **legacy_system_prompt** for the “Synapse Navigator.” No cloud.
- **`mcp_server/server.py` — `query_legacy_persona`**: MCP tool that loads the persona file, semantically retrieves **Forensic Receipts** (synapse_id, chunk_id, snippets), and answers the user’s question *as* the author via local Ollama, requiring grounded citations. Env: `SYNAPSE_PERSONA_PATH`, `SYNAPSE_LEGACY_PERSONA_LLM` (default: same family as `SYNAPSE_REFLECT_LLM` / `llama3`).
- **Read-only / Legacy Mode**: `SYNAPSE_MCP_READ_ONLY=1` and/or `SYNAPSE_LEGACY_MODE=1` wraps the Chroma collection in **`_ReadOnlyCollection`** — `add` / `update` / `delete` / `upsert` / `modify` raise `RuntimeError` so hosted interrogation cannot mutate the index. **Shared** `_semantic_search_results` powers `search_synapses` and the legacy tool.
- **`tests/test_unbroken_voice.py`**, **tests/test_mcp_server.py**: tests for JSON parse, read-only guard, and `query_legacy_persona` (mocked Ollama/embed).

## [0.33.9] - 2026-04-22 (Temporal Mirror — Ollama errors, class API, docstrings)

### Fixed
- **`temporal_mirror.py` P1 — CLI error handling**: ``main()`` now catches ``ollama.ResponseError`` and ``httpx`` connection/timeout types when available, plus a narrow fallback (``_is_ollama_transport_error``) for e.g. ``httpcore`` ``ConnectError`` if the daemon is down. Exits with code 1 and prints: `❌ Ollama error: Ensure the Ollama service is running locally.` (no stack trace to stdout). Invalid date ranges still exit 2.

### Added
- **`temporal_mirror.py`**: Public :class:`TemporalMirror` with ``build_report``; ``run_temporal_mirror`` delegates to it. Forensic section copy clarifies that both range blocks are always present; an empty range notes “no Forensic UUIDs for this range” so the other range’s citations stay intact.

### Added (tests)
- **`tests/test_temporal_mirror.py`**: ``test_format_report_both_forensic_sections_when_one_range_empty`` asserts two Forensic sections and UUID bullets when one era is empty.

## [0.33.8] - 2026-04-22 (Temporal Mirror — cross-era comparison)

### Added
- **`temporal_mirror.py`**: Compare two calendar windows in the Chroma vault on a free-text topic. Uses :class:`core.vector_store.VectorStore` semantic search with over-fetch, then filters chunks by `original_timestamp` (or `original_year` as mid-year) into `--range1` and `--range2` (``YYYY`` or ``YYYY-YYYY``). Deduplicates by synapse id, takes top *N* per range, builds **Forensic Receipts** (synapse UUID + chunk id + snippet), and sends the bundle to a **local Ollama** LLM (default `llama3` or `TEMPORAL_MIRROR_LLM`) with the *Temporal Mirror* system prompt: evolutionary changes, direct contradictions, and lost knowledge. Emits a single **Temporal Mirror Report** in Markdown, with optional `-o` file output. No cloud services.
- **`tests/test_temporal_mirror.py`**: Unit tests for range parsing, timestamp parsing, and range membership.

## [0.33.7] - 2026-04-22 (Analog Bridge — JSON/LaTeX, atomic commit, recursive scan)

### Fixed
- **`analog_bridge.py` P1 — `_json_load_loose`**: Replaced naive brace-depth scanning with a **string-aware** scan (`_outer_json_object_slice`) that tracks JSON double-quoted strings and backslash escapes, so `{` and `}` inside string values (e.g. LaTeX `\\frac{a}{b}`) no longer truncate the object before `json.loads`.

### Changed
- **`analog_bridge.py` P2 — Atomicity**: The durable synapse ``.md`` is written only after a successful vector index. Flow: HITL (if any) → write a **temp** file under the synapse dir → `VectorStore.add_synapse(temp)` → `os.replace` to the final filename. On `FAILED` or any exception, the temp is removed and the final path is not left behind in a half-committed state.
- **`analog_bridge.py` P2 — Scan**: Image discovery now uses `Path.rglob("*")` (recursive) instead of a single directory level, so subfolders are included; `source_image` frontmatter uses a path **relative to the input root** when possible.

### Added
- **`tests/test_analog_bridge.py`**: Unit tests for string-aware JSON extraction, fenced JSON, and frontmatter validity with LaTeX in the body.

## [0.33.6] - 2026-04-22 (Analog Bridge — notebook HTR)

### Added
- **`analog_bridge.py`**: Ingests a directory of `.png`/`.jpg` engineering notebook scans. Calls a local **Ollama** vision model (`llava` by default, e.g. `llama3.2-vision`) with an **Engineering Notebook HTR** system prompt that preserves dates, diagram descriptions, math (LaTeX), **Keywords**, and **Temporal Markers** (JSON in the model reply, then converted to Sovereign Markdown with `source: physical_notebook` and `original_year`). Indexes each file with :class:`core.vector_store.VectorStore` (Chroma + `mxbai-embed-large` embeddings) so metadata includes `source` and `original_year` for the vault. **`--hitl`**: human-in-the-loop — prints each transcription and waits for Enter to write and index, or `s` to skip (for verifying equations before indexing).
- **README.md**: "Analog Bridge" section — prerequisites, example CLI, and pointer to the vision model.

### Note
- Pull a vision model once, e.g. `ollama pull llava` (or your chosen `llava` / `llama3.2-vision`).

## [0.33.5] - 2026-03-18 (Test suite — drop pytest-asyncio)

### Fixed
- **tests/test_mcp_server.py**: Converted all 23 `async def` tests to plain `def`. The MCP tool functions are synchronous (return `str`, not `Coroutine`); `async def` was speculative and required `pytest-asyncio`, which was never installed in the project venv.
- **pytest.ini**: Removed `asyncio_mode = auto` (no longer needed; was causing `PytestConfigWarning: Unknown config option` on every run).
- **requirements-dev.txt**: Removed `pytest-asyncio>=1.3.0` (no longer a dependency).

### Verified
- `pytest` reports **52 passed, 22 warnings** with zero framework warnings; remaining warnings are all upstream third-party library deprecations (ChromaDB, python-frontmatter).

---

## [0.33.4] - 2026-03-18 (MCP Server — test suite)

### Added
- **tests/test_mcp_server.py**: 23-test pytest-asyncio suite covering all three MCP tools with fully mocked ChromaDB and Ollama.
  - `get_recent_context` (7 tests): newest-first sort, `n` bounds (0, 999), chunk deduplication, empty vault, ChromaDB unavailable.
  - `search_synapses` (7 tests): chunk dedup (best-score wins), `n_results` bounds, empty query, empty vault, embedding failure.
  - `reflect_on_memories` (9 tests): structured output, `truncated=False` for small input, `truncated=True` for chars overflow, snippet-count overflow, both limits, empty/whitespace inputs, Ollama failure, `focus` parameter forwarding.
- **requirements-dev.txt**: `pytest-asyncio>=1.3.0` added.

## [0.33.3] - 2026-03-18 (MCP Server — truncated flag P1 fix)

### Fixed
- **mcp_server/server.py** P1: `reflect_on_memories` — `truncated` flag now correctly fires when EITHER the snippet count exceeded `REFLECT_MAX_SNIPPETS` OR the concatenated text was clipped by `REFLECT_MAX_CHARS`. Previously it only checked the snippet count.
- **mcp_server/server.py**: Added `truncation_reason` field to the response (`"snippet_count"`, `"chars"`, `"snippet_count_and_chars"`, or `null`) so callers know exactly which limit was hit.
- **mcp_server/server.py** PEP 8: Third-party imports sorted alphabetically (`chromadb`, `ollama`, then `from` imports).

## [0.33.2] - 2026-03-18 (MCP Server — Blog Polish)

### Changed
- **mcp/ → mcp_server/**: Renamed directory to avoid namespace collision with the `mcp` Python package. Updated README run commands and `mcp.json` config snippet.
- **mcp_server/server.py**: `reflect_on_memories` now caps input to the first 10 snippets (`REFLECT_MAX_SNIPPETS`) and 15,000 characters (`REFLECT_MAX_CHARS`); response includes `truncated` flag.
- **mcp_server/server.py**: `logging.basicConfig` moved into `_main()` so it does not hijack the root logger when the module is imported.
- **mcp_server/server.py**: Renamed `"id"` key in `_format_hit` return dict to `"synapse_id"` to avoid shadowing the Python built-in `id`.
- **mcp_server/server.py**: Renamed local variables `ids` → `hit_ids` (search_synapses) and `ids` → `chunk_ids` (get_recent_context) to avoid shadowing built-ins.

## [0.33.1] - 2026-03-18 (MCP Server — PR Feedback)

### Fixed
- **mcp/server.py** P1: `get_recent_context` now fetches the entire collection (`limit=count`) before sorting by `original_timestamp`, ensuring the most recent entries across the whole vault are found — not just a partial window.
- **mcp/server.py** P2: `import re` moved from inside `reflect_on_memories` body to module-level imports.
- **mcp/server.py** P2: `search_synapses` now clamps `n_results` to `[1, 50]`, matching the guard pattern in `get_recent_context`.
- **requirements.txt** P2: `mcp>=1.0.0` → `mcp==1.2.1` (pinned to match project dependency strategy).

## [0.33.0] - 2026-03-18 (MCP Server — Agent Interface)

### Added
- **mcp/server.py**: New MCP server exposing the Synapse vault over stdio transport via the `mcp` Python SDK.
  - `search_synapses(query, n_results=5)` — semantic search with over-fetch + dedup; returns JSON array of snippets + metadata.
  - `get_recent_context(n=10)` — working memory; fetches last N unique synapses sorted by `original_timestamp` descending.
  - `reflect_on_memories(snippets, focus="")` — internal LLM reflection via Ollama; surfaces 3 strategic themes across retrieved memories.
  - Configurable via environment variables: `SYNAPSE_CHROMA_PATH`, `SYNAPSE_COLLECTION`, `SYNAPSE_EMBED_MODEL`, `SYNAPSE_REFLECT_LLM`.
  - Graceful error handling for missing collection, ChromaDB lock, and Ollama failures.
- **requirements.txt**: Add `mcp>=1.0.0`.
- **README.md**: Document MCP server tools, environment variables, run command, and Cursor `mcp.json` config block.

## [0.32.0] - 2026-03-18 (5/5 Logic Gaps Closed)

### Fixed
- **main.py**: Search over-fetching — request n_results * 4 (min 10) from vector store; deduplicate by file path, then slice to n_results for unique file count.
- **core/vector_store.py**: UUID type consistency — uuid_val = str(metadata.get("uuid")); store uuid as string in safe_metadata for ChromaDB where-clause match (fixes stale entries).
- **core/vector_store.py**: _embed logging — one event, one log; remove redundant debug when is_query=True, keep warning only.
- **adapters/openai_adapter.py**: Strict stats — stats[status] += 1 (KeyError on unregistered status).

### Added
- **tests/test_cli.py**: test_query_deduplicates_chunks_respects_n_results — mock multi-chunk from same file; assert --n-results unique files.

## [0.31.0] - 2026-03-18 (5/5 Finish Line)

### Fixed
- **adapters/base.py**: write_turn return type -> str; docstring reflects "written"|"skipped"|"protected".
- **core/vector_store.py**: Promote _embed_with_retry to private instance method; remove unreachable uuid_val is None block.

### Verified
- cmd_ingest correctly uses adapter return strings for Written, Skipped, Protected counters.
- All 28 tests pass; _embed_with_retry move does not break ollama.embed mocks.

## [0.30.0] - 2026-03-18 (5/5 Data Visibility & Logic)

### Fixed
- **adapters/openai_adapter.py**: Noisy manual-edit protection — when skipping overwrite due to content differs, keep _logger.warning and print "⚠️ Skipped [filename]: exists with manual edits." to stdout; write_turn returns "written"|"skipped"|"protected".
- **core/vector_store.py**: Clean add_synapse — remove dead `if len != len: pass`; simplify skip invariant to `if count_matches and all_hashes_match: return SKIPPED`; _embed_with_retry takes file_path as explicit `fp` argument for isolated testability.

### Changed
- **main.py**: cmd_ingest tracks and prints "Protected (Manual Edits)" count in summary (written, skipped, protected).
- **adapters/base.py**: parse() returns dict[str, int] | None with written/skipped/protected counts.

## [0.29.0] - 2026-03-18 (5/5 100% Confidence)

### Fixed
- **main.py**: Informative snippets — _clean_snippet drops --- logic (chunks have body only); returns first 3 non-empty lines, skips headers (#) and metadata (uuid:, created_at:, updated_at:); shows actual content like "Manufactured in 1889..." instead of ### User.
- **core/vector_store.py**: Logic consistency — uuid_val uses explicit `if uuid_val is None` fallback instead of `or`, avoiding falsy-check bug.

### Changed
- **main.py**: Deduplicate by file path — show 5 unique files per query (keep best match per file); format timestamp as YYYY-MM-DD HH:MM.

### Verified
- Empty body (whitespace only) returns SKIPPED immediately.

### Changed
- **tests/test_cli.py**: test_query_cli_prints_results_to_stdout — assert snippet has multiple lines of content and skips metadata/headers.

## [0.28.0] - 2026-03-18 (5/5 Final Logic Gates)

### Fixed
- **core/vector_store.py**: Strict re-indexing guard — delete must succeed before add; if delete raises (other than "no items found"), log error and return FAILED; do not proceed to upsert.
- **main.py**: Precision snippet filtering — use s.startswith("uuid:"), s.startswith("created_at:"), s.startswith("updated_at:") instead of substring match; lines like "I need to generate a new uuid" now display in search results.

### Added
- **tests/test_vector_store.py**: test_delete_failure_aborts_upsert — mock delete to raise; assert FAILED and synapse not added.

### Verified
- Empty body (frontmatter only, no content) returns SKIPPED (nothing for embedding model to learn).
- All 28 tests pass.

## [0.27.0] - 2026-03-18 (5/5 Professional Build)

### Fixed
- **main.py**: Robust snippet cleaning — _clean_snippet skips YAML frontmatter (---), lines containing created_at/updated_at/uuid; skips triple-backtick code fences and finds first human-readable text line.
- **core/vector_store.py**: Strict skip invariant — add_synapse returns SKIPPED only when (1) existing chunk count equals new chunk count and (2) every chunk's metadata content_hash matches current file; otherwise full re-index.
- **core/vector_store.py**: Encapsulate side effects — move os.environ["CHROMA_TELEMETRY_NOOP"] into VectorStore.__init__; replace broad except Exception in delete step with ChromaDB-specific handling; log _logger.error when delete fails for reasons other than "not found".
- **main.py**: Organization — move _logger definition to top of file, just below imports.

### Added
- **tests/test_vector_store.py**: test_partial_index_triggers_reindex — index multi-chunk file, remove one chunk, re-add; assert SUCCESS and full re-index restores correct chunk count.

### Verified
- All 27 tests pass.

## [0.26.0] - 2026-03-18 (5/5 Final)

### Fixed
- **core/vector_store.py**: Atomic skip logic — only return SKIPPED if hash matches AND existing chunk count matches generated chunks; otherwise delete-and-re-index.
- **core/vector_store.py**: Log level — _logger.critical → _logger.error in _embed_with_retry; add _logger.debug when text truncated.
- **main.py**: Clean snippets — _clean_snippet strips ---, created_at, updated_at; if code block, show first content line.

### Added
- **tests/test_vector_store.py**: test_reindex_on_hash_mismatch — index, change content, re-index; assert SUCCESS and new content in store.

### Verified
- chromadb==0.5.3 pinned.

## [0.25.0] - 2026-03-18 (5/5 Perfect Score)

### Fixed
- **adapters/openai_adapter.py**: Robust part extraction — if "text" exists and is not None and not "", use it; else fall back to "content". Prevents empty string in text from skipping valid content.
- **core/vector_store.py**: Hash-check exception — log warning instead of silent pass: "Could not verify existing hash for {doc_id}, proceeding with re-index: {e}".
- **requirements.txt**: Pin chromadb==0.5.3 for reproducibility.

### Verified
- All 25 tests pass.
- Query returns human-readable file paths (uuid_to_path resolution).

## [0.24.0] - 2026-03-18 (5/5 Hard Mute)

### Fixed
- **core/vector_store.py**: Hard mute — logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL) at __init__ start (permanent suppression).
- **core/vector_store.py**: Content hash flow — compute SHA-256 of body first; check ChromaDB before embed; if metadata.content_hash matches, return SKIPPED; else delete-and-add with content_hash in metadata.
- **core/vector_store.py**: Empty synapse guard — if body empty or whitespace, return SKIPPED (no vector space for stubs).

### Verified
- cmd_index correctly reports skipped count from add_synapse return value.

## [0.23.0] - 2026-03-18 (5/5 UX & Telemetry)

### Fixed
- **core/vector_store.py**: Nuclear telemetry — os.environ["CHROMA_TELEMETRY_NOOP"] = "True" before chromadb import; suppress chromadb.telemetry logger during PersistentClient init.
- **core/vector_store.py**: Delete debug message — "No existing chunks found for {uuid} to delete." instead of exception repr.
- **main.py**: cmd_query empty result — print "No matching synapses found." instead of "No results found."

### Verified
- SKIPPED via content_hash (query before embed/delete); empty body → SKIPPED.

## [0.22.0] - 2026-03-18 (5/5 Contract & Telemetry)

### Fixed
- **core/vector_store.py**: Restore SKIPPED — content_hash check before delete-add; if existing doc has matching content_hash, return SKIPPED (restores CLI skipped counter).
- **core/vector_store.py**: Empty body — return SKIPPED instead of FAILED.
- **core/vector_store.py**: Delete exception — _logger.debug("Optional delete failed (normal if new): %s", e) instead of silent pass.
- **core/vector_store.py**: Telemetry — Settings(anonymized_telemetry=False, allow_reset=True).
- **adapters/openai_adapter.py**: UUID semantic fix — NAMESPACE_URL instead of NAMESPACE_DNS for turn-ID.

### Changed
- **core/vector_store.py**: Store content_hash in metadata for skip detection.
- **requirements.txt**: chromadb>=0.5.0 to match Settings usage.
- **tests**: test_add_synapse_returns_skipped_when_content_unchanged (asserts no re-embed on unchanged file).

## [0.21.0] - 2026-03-18 (5/5 Data Integrity)

### Fixed
- **core/vector_store.py**: Atomic re-indexing — delete-before-add; remove last-chunk dedup; always embed first, delete existing by uuid, then upsert. Re-index returns SUCCESS.
- **core/vector_store.py**: _chunk_text loop invariant — step = max(1, CHUNK_SIZE - CHUNK_OVERLAP) prevents infinite loop on malformed config.
- **core/vector_store.py**: Prune unreachable truncation log in _embed (else branch for is_query=False).
- **main.py**: _build_uuid_to_path_map — replace silent except with _logger.debug for diagnostic trail.

### Verified
- ChromaDB settings=Settings(anonymized_telemetry=False) passed to PersistentClient.
- requirements.txt: no unused packages.

### Changed
- **tests/test_vector_store.py**: test_add_synapse_returns_skipped_when_doc_already_exists → test_add_synapse_reindex_returns_success (asserts delete-before-add).

## [0.20.0] - 2026-03-18 (5/5 Merge Ready)

### Fixed
- **main.py**: UUID resolution — strip #chunk-N suffix from doc_id before comparing to frontmatter UUID.
- **main.py**: Path-not-found output — print "File: [UUID] (Path not found)" when resolution fails.

### Changed
- **main.py**: Performance — pre-build uuid→path dict once (_build_uuid_to_path_map); O(n+k) instead of O(n×k).
- **adapters/openai_adapter.py**: _safe_join_parts — simplify to `if isinstance(val, str): ... elif val is not None: ...`.

### Verified
- ChromaDB Settings(anonymized_telemetry=False) imported and passed to PersistentClient.

### Added
- **tests/test_cli.py**: test_query_cli_prints_results_to_stdout — now uses multi-chunk doc, asserts file path resolves.

## [0.19.0] - 2026-03-18 (Local Brain)

### Added
- **main.py**: `query` subcommand — semantic search over indexed synapses; positional QUERY, optional --n-results (default 5). Prints Timestamp, Snippet, File Path to stdout.
- **main.py**: _resolve_uuid_to_path() — resolves doc_id to synapse file path for human-readable output.
- **tests/test_cli.py**: test_query_cli_prints_results_to_stdout.

### Fixed
- **core/vector_store.py**: Targeted exception handling — catch only ollama.ResponseError in query(); let other exceptions propagate (logic bugs).
- **core/vector_store.py**: Query truncation warning — WARNING log when query string is truncated in _embed(). _embed() now accepts `is_query` parameter.
- **adapters/openai_adapter.py**: Idempotent logic — remove redundant `+ "\n"` before .strip() in write_turn overwrite check.

### Changed
- **main.py**: Docstring updated to include query subcommand.

## [0.18.0] - 2026-03-18

### Fixed
- **core/vector_store.py**: Search resilience — wrap query embedding in try/except; on ollama.ResponseError, log error and return [] as documented.

### Changed
- **core/vector_store.py**: Chunk 400-retry log level WARNING → INFO (expected for large files).

### Verified
- ChromaDB anonymized_telemetry=False active.

### Added
- **tests/test_vector_store.py**: test_query_returns_empty_on_embedding_failure.

## [0.17.0] - 2026-03-18 (5/5 Golden Build)

### Fixed
- **core/vector_store.py**: Atomic upserts — batch all chunks in a single upsert call; no partial writes.
- **core/vector_store.py**: Robust dedup — always check final expected chunk ID (doc_id for single, uuid#chunk-{N-1} for multi).

### Changed
- **core/vector_store.py**: Truncation docstring — HARD_TRUNCATE_CHARS (500) instead of hardcoded 1000.

### Verified
- Telemetry silenced, all-or-nothing embedding, pydantic/jinja2 pruned.

## [0.16.0] - 2026-03-18

### Changed
- **core/vector_store.py**: ChromaDB Settings(anonymized_telemetry=False) — silence telemetry noise.
- **core/vector_store.py**: Safe chunker — 800 chars, 150 overlap (dense technical logs); HARD_TRUNCATE 500.

## [0.15.0] - 2026-03-18

### Fixed
- **core/vector_store.py**: All-or-nothing embedding — generate all chunk embeddings before any upsert; if any chunk fails, add zero chunks (prevents partial/stranded data).
- **core/vector_store.py**: Refined deduplication — check last chunk ID (uuid#chunk-{N-1}) instead of chunk-0; if last chunk missing, re-index whole file.

### Removed
- **requirements.txt**: pydantic, jinja2 (not imported in core/ or adapters/).

### Added
- **tests/test_vector_store.py**: test_add_synapse_partial_chunk_failure_adds_zero_chunks.

## [0.14.0] - 2026-03-18

### Changed
- **core/vector_store.py**: Aggressive chunking — 1500 chars, 200-char overlap (~400 tokens, safety for 512 limit).
- **core/vector_store.py**: Chunk IDs: doc_id#chunk-0, doc_id#chunk-1 (was _part1, _part2).
- **core/vector_store.py**: Hard truncation — on 400, retry with 1000-char truncation; if still fails, log CRITICAL, return FAILED.
- **core/vector_store.py**: INFO log when splitting: "Splitting [filename] into [N] chunks due to length."

## [0.13.0] - 2026-03-18

### Added
- **core/vector_store.py**: Truncation/chunking — _embed truncates to 2000 words; add_synapse chunks long bodies into doc_id_part1, doc_id_part2, etc.
- **core/vector_store.py**: _chunk_text() helper; MAX_WORDS_PER_CHUNK = 2000.
- **core/vector_store.py**: try/except for ollama.ResponseError 400 — log WARNING, return FAILED; prevents loop crash on context-length errors.
- **tests/test_vector_store.py**: test_add_synapse_chunks_long_document.

### Verified
- **main.py**: logging.basicConfig(level=logging.INFO) — truncation/chunk logs visible.

## [0.12.0] - 2026-03-18 (Golden Build)

### Fixed
- **adapters/openai_adapter.py**: Zero-data-loss ingress — when val (text/content) is not a string (e.g. list), json.dumps(val) in code block instead of dropping.
- **adapters/openai_adapter.py**: Removed unreachable convo_id hash fallback; trust title variable.
- **core/vector_store.py**: Consistent query access — use results["distances"] instead of results.get("distances").

### Added
- **tests/test_vector_store.py**: test_parse_list_content_part_appears_as_json_block — verifies list content appears as JSON block, not dropped.

## [0.11.0] - 2026-03-18

### Fixed
- **adapters/openai_adapter.py**: Native YAML booleans — preamble and postamble now Python bool (True/False) so frontmatter serializes as native YAML (true/false without quotes).
- **adapters/openai_adapter.py**: _safe_join_parts — skip empty or whitespace-only parts; avoid wrapping them in JSON code blocks (reduces index noise).

### Added
- **tests/test_vector_store.py**: Assert preamble and postamble are read back as bool in test_write_turn_original_timestamp_is_utc_iso.

## [0.10.0] - 2026-03-18

### Fixed
- **adapters/openai_adapter.py**: Robust title fallback — use existing `title` variable (with "Untitled Conversation" default) for original_convo_id instead of re-calling convo.get("title"); never skip to hash when title is available.
- **core/vector_store.py**: Zero-result safety — `if n_results <= 0: return []` at start of query() to prevent ChromaDB ValueError.
- **adapters/openai_adapter.py**: Explicit part extraction in _safe_join_parts — `val = text if text is not None else content` to avoid falsy-but-valid string (e.g. "") falling through incorrectly.

### Added
- **main.py**: Module docstring listing ingest and index subcommands.

### Verified
- Trailing newlines on all files; ingest/index subcommands functional and documented.

## [0.9.0] - 2026-03-18 (Phase 1.3 Final)

### Added
- **main.py**: logging.basicConfig(level=logging.INFO) at top of main() — adapter WARNING messages (e.g. skip overwrite, malformed turn) now visible in CLI.

### Changed
- **adapters/openai_adapter.py**: _safe_join_parts — for dict parts, extract part.get('text') or part.get('content'); complex tool-result wrapped in ```json``` block instead of str(dict).
- **core/vector_store.py**: add_synapse return type tuple[AddResultStatus, str]; docstring updated (doc_id always str on return).

### Verified
- **README.md**: ingest/index commands match argparse (path positional, -o/--output, --synapses-dir, --chroma-dir defaults).

## [0.8.0] - 2026-03-18 (Golden Build)

### Fixed
- **main.py**: Status-checking logic moved outside try/except — unknown status now raises ValueError and fails loudly instead of being caught as "failed embedding".
- **adapters/openai_adapter.py**: Comment on .strip() — clarify that file is left untouched (skip overwrite) if the only difference is trailing whitespace.

### Changed
- **tests/test_vector_store.py**: mtime test uses os.utime() to set mtime 1 hour in past instead of time.sleep(); reliable across filesystems.
- **tests/test_vector_store.py**: Import grouping — stdlib, then third-party, then local.

## [0.7.0] - 2026-03-18 (Golden Build)

### Changed
- **adapters/openai_adapter.py**: Idempotent I/O — when file exists with identical content, return immediately without write; preserves mtime and avoids unnecessary disk I/O.
- **adapters/openai_adapter.py**: PEP 8 imports — grouped typing and datetime at top, separated from stdlib by newline.
- **main.py**: Exhaustive status handling in cmd_index — explicit SUCCESS/SKIPPED/FAILED branches; unknown status raises ValueError.
- **core/vector_store.py**: add_synapse docstring — add Raises for ollama.ResponseError.

### Added
- **tests/test_vector_store.py**: `test_write_turn_identical_content_preserves_mtime` — verifies mtime unchanged after re-ingest of identical content.

## [0.6.0] - 2026-03-18

### Changed
- **core/vector_store.py**: `add_synapse` returns `(status, doc_id)` — status is "SUCCESS", "SKIPPED", or "FAILED" for clearer semantics (no overloaded is_new).
- **main.py**: Index loop tracks indexed, skipped, failed; prints WARNING with filename when embedding fails; summary includes "failed Z".

### Added
- **adapters/openai_adapter.py**: Comment on `.strip()` behavior — protects meaningful content but ignores whitespace-only edits.
- **tests/test_vector_store.py**: `test_add_synapse_returns_skipped_when_doc_already_exists`, `test_add_synapse_returns_failed_when_embedding_empty`.
- **tests/test_cli.py**: `test_index_embedding_failure_increments_failed` — mocks empty embedding, verifies failed counter and WARNING output.

## [0.5.0] - 2026-03-18

### Added
- **adapters/openai_adapter.py**: Protect manual edits — before overwriting, check if file exists with different content; if so, log WARNING and skip to avoid losing human annotations during re-ingest.
- **main.py**: Index command summary — "Indexed X new synapses, skipped Y existing" at completion.
- **core/vector_store.py**: `add_synapse` returns `(doc_id, is_new)` to distinguish new vs. existing documents.
- **tests/test_vector_store.py**: `test_write_turn_existing_file_different_content_not_overwritten` — verifies no overwrite when content differs and WARNING is logged.

### Changed
- **adapters/openai_adapter.py**: Filename hash length increased from 6 to 10 characters for stronger collision resistance.
- **adapters/openai_adapter.py**: Deterministic convo fallback — `json.dumps(mapping, sort_keys=True)` instead of `str(mapping)` for stable IDs when `convo.id` is missing.

## [0.4.0] - 2026-03-18

### Fixed
- **adapters/openai_adapter.py**: Zero-collision filenames — add 6-char hash of `original_convo_id`; format `{timestamp}-{slug}-{convo_hash}-{content_hash}.md`.
- **tests/test_vector_store.py**: All datetimes use UTC (`tzinfo=timezone.utc`); no naive datetimes.
- **tests/test_vector_store.py**: Type-safe frontmatter assertions — `str(post.get("original_timestamp", ""))` to avoid TypeError if PyYAML returns datetime.
- **CHANGELOG.md, README.md**: Trailing newlines.

### Verified
- **main.py**: VectorStore init error remains user-friendly (prints message, no traceback).

## [0.3.9] - 2026-03-18

### Fixed
- **adapters/openai_adapter.py**: Narrow exception scope — only data extraction (parsing JSON nodes) wrapped in try/except; `write_turn()` moved outside so disk/IO errors propagate to the user instead of being logged as "malformed turn."
- **adapters/openai_adapter.py**: Enforce timezone determinism — `datetime.fromtimestamp(create_time, tz=timezone.utc)` for cross-platform UUID/filename consistency.
- **adapters/openai_adapter.py**: LSP — `write_turn` signature matches `BaseAdapter` including `**kwargs: Any`.
- **main.py**: Wrap `VectorStore()` in try/except; ChromaDB init failures (e.g., locked DB) print a clean error and exit gracefully.

### Added
- **tests/test_vector_store.py**: `test_write_turn_original_timestamp_is_utc_iso` — verifies `original_timestamp` in frontmatter is ISO with `+00:00` UTC suffix.

## [0.3.8] - 2026-03-18

### Fixed
- **adapters/openai_adapter.py**: Hardened string joining — `"".join([str(p) for p in parts])` to handle non-string elements (e.g. tool-use dicts) in content.parts.
- **adapters/openai_adapter.py**: Per-turn try/except — malformed turns log a warning and are skipped instead of aborting ingestion.
- **main.py**: Use `synapse_dir` variable in "not found" warning instead of hardcoded "vault/synapses".

### Changed
- **adapters/openai_adapter.py**: OpenAIAdapter now explicitly inherits from BaseAdapter.
- **adapters/base.py**: `@abstractmethod` decorators with full signature for `parse` and `write_turn`; use `...` instead of `pass`.

### Added
- **tests/test_vector_store.py**: `test_parse_handles_poisoned_export_with_non_string_parts` — export with `{"tool_use": "..."}` in parts; verifies no crash.

## [0.3.7] - 2026-03-18

### Fixed
- **Security & isolation**: Add `vault/chroma/` to `.gitignore`; `vault/synapses/` was already present.
- **main.py index**: When `vault/synapses` is missing, log warning and exit 0 (no crash).
- **main.py**: Add `--output` to ingest, `--synapses-dir` and `--chroma-dir` to index for test isolation.

### Changed
- **tests/test_cli.py**: `test_ingest_with_valid_file` → `test_ingest_with_valid_file_uses_tmp_path` — uses `--output` with tmp_path; no writes to project vault.
- **tests/test_cli.py**: `test_index_subcommand_runs` → `test_index_subcommand_zero_state` — creates dummy vault/synapses in tmp_path; zero dependence on project filesystem.
- **tests/test_cli.py**: Add `test_index_missing_synapses_dir_exits_zero` — verifies graceful handling.

### Repository cleanup (manual)
If vault/chroma was previously committed, run:
`git rm -r --cached vault/chroma/` to remove from index without deleting local files.

## [0.3.6] - 2026-03-18

### Added
- **main.py**: Argparse subcommands `ingest` and `index` — aligns with README usage.
- **main.py ingest PATH**: Parse export JSON into vault/synapses Markdown turns.
- **main.py index**: Sweep vault/synapses and index into VectorStore (vault/chroma).
- **tests/test_cli.py**: CLI tests for ingest (requires path, valid file) and index subcommands.
- **tests/test_vector_store.py**: `test_write_turn_title_with_special_chars_produces_valid_yaml` — verifies titles with `#` and `{` produce parseable YAML.

### Fixed
- **adapters/openai_adapter.py**: YAML frontmatter — use `frontmatter.dumps()` for metadata serialization; special chars in `original_convo_id` (e.g. `#`, `{`, `:`) no longer break parsing.
- **core/vector_store.py**: Optimize `query()` — check `count() == 0` before calling `ollama.embed` to avoid wasted compute on empty store.
- **tests**: Empty-collection query test now asserts `mock_embed.assert_not_called()` to verify no embed call.

## [0.3.5] - 2026-03-18

### Fixed
- **core/vector_store.py**: Empty collection guard — `query()` returns `[]` when `count() == 0` to avoid ChromaDB `ValueError` for `limit=0`.
- **adapters/openai_adapter.py**: ID guard — explicit `if convo.get('id') is None`; fallback to title, then hash of mapping content when both are missing.
- **README.md**: Example uses dict access `result['document']` and `result['metadata']` instead of attribute notation.
- **README.md**: Git clone command uses plain URL (no Markdown link syntax in code block).

### Changed
- **requirements.txt**: Moved pytest to `requirements-dev.txt`; all packages now have explicit versions.
- **requirements-dev.txt**: New file including pytest for development.

### Added
- **tests/test_vector_store.py**: `test_vector_store_query_empty_collection_returns_empty_list` — verifies empty store returns `[]` without crashing.

## [0.3.4] - 2026-03-18

### Fixed
- **P1 data integrity**: Robust frontmatter parsing in `core/vector_store.py` — replaced regex with `python-frontmatter` so body content containing Markdown horizontal rules (`---`) no longer mis-splits.
- **adapters/openai_adapter.py**: ID guard — when `convo.get('id')` is None, use `convo.get('title', 'unknown_convo')` as fallback.
- **adapters/openai_adapter.py**: Filename uniqueness — add 6-char SHA256 hash of `user_text` to filename so different prompts in the same minute do not overwrite each other.

### Added
- **core/vector_store.py**: `query(text: str, n_results: int = 5)` — embeds query via Ollama and returns top matching synapses from ChromaDB.
- **tests/test_vector_store.py**: `test_add_synapse_handles_horizontal_rule_in_body` — verifies parser handles `---` in body.
- **tests/test_vector_store.py**: `test_parse_handles_none_convo_id` — verifies fallback when conversation has no id.
- **tests/test_vector_store.py**: `test_write_turn_same_minute_different_text_produces_distinct_files` — verifies content hash prevents overwrites.
- **tests/test_vector_store.py**: `test_vector_store_query_returns_top_matches` — verifies query method.

### Changed
- **requirements.txt**: Added `python-frontmatter==1.1.0`.

## [0.3.3] - 2026-03-18

### Fixed
- **P1 data integrity**: UUID collision in `adapters/openai_adapter.py` — seed now includes timestamp: `{convo_id}-{timestamp.isoformat()}-{user_text}` so repeated messages in the same thread get unique, deterministic IDs.
- **core/vector_store.py**: UUID guard changed from `if not uuid_val` to `if uuid_val is None` to avoid falsy integer bugs (e.g., `uuid: 0`).

### Removed
- **beautifulsoup4**: Not used for Markdown parsing; removed from requirements.

### Changed
- **requirements.txt**: Pin all dependencies; removed beautifulsoup4; added pydantic==2.11.0, jinja2==3.1.5, pytest==8.3.4, pyyaml==6.0.2.

### Added
- **tests/test_vector_store.py**: `test_write_turn_generates_unique_uuids_for_same_message_different_timestamps` — verifies adapter produces distinct UUIDs for identical user messages with different timestamps.

## [0.3.2] - 2026-03-18

### Fixed
- **core/vector_store.py**: Type guard in `_extract_uuid` for non-string uuid (e.g., YAML-parsed int); prevents AttributeError on `.startswith()`.
- **core/vector_store.py**: Empty embedding guard already in place; skips upsert when Ollama returns empty list or None.
- **adapters/openai_adapter.py**: Remove unnecessary f-string from static `"source: gpt_export"` line.
- **Project hygiene**: Trailing newlines on requirements.txt, README.md, and all `.py` files.
- **requirements.txt**: Version pinning for reproducibility — chromadb==0.5.3, ollama==0.2.1, beautifulsoup4==4.12.3, python-slugify==8.0.4.

### Added
- **tests/test_vector_store.py**: `test_add_synapse_malformed_frontmatter_uuid_type_guard` — verifies type guard handles non-string uuid without crash.

## [0.3.1] - 2026-03-18

### Fixed
- **core/vector_store.py**: Use SDK attribute access (`response.embeddings`) instead of dict `.get()` for Ollama EmbedResponse.
- **core/vector_store.py**: Validate embeddings before upsert; log warning and return empty string when empty.
- **core/vector_store.py**: Ensure file ends with single trailing newline.
- **adapters/openai_adapter.py**: Change `uuid.NAMESPACE_URL` to `uuid.NAMESPACE_DNS` for domain-like seed identifiers.
- **tests/test_vector_store.py**: Use `tmp_path` fixture for temp files (no leaks); mock returns EmbedResponse-like object with `.embeddings` attribute; Google-style docstrings.

## [0.3.0] - 2026-03-18

### Added
- **Phase 1.3: The Local Brain** — Professional-grade vector storage layer.
- `core/vector_store.py`: `VectorStore` class using ChromaDB for local persistence.
- `VectorStore.add_synapse(file_path)`: Reads Markdown, extracts YAML metadata, and generates embeddings via Ollama (mxbai-embed-large).
- `tests/test_vector_store.py`: Test suite with mocked Ollama client to verify `add_synapse` parsing and embedding invocation.
- Dependencies: `chromadb`, `ollama`, `pytest`, `pyyaml`.

### Changed
- **Style pass**: All methods in `adapters/openai_adapter.py` and `core/context_cleaner.py` now have type hints and Google-style docstrings.

## [0.2.0] - 2026-03-18

### Added
- `postamble: true/false` field in write_turn YAML frontmatter for closing-phrase detection.
- `core/context_cleaner.py`: Introduced heuristic-based regex scanning to identify AI conversational noise.
- Integrated `ContextCleaner` into `OpenAIAdapter` to dynamically flag preambles in YAML frontmatter.

### Fixed
- Improved signal-to-noise ratio in generated Markdown synapses by identifying non-technical conversational "fluff."
- Corrected unescaped literal question mark in ContextCleaner regex.
- Reclassified postamble patterns; transitioned from `re.match` to `re.search` for closing phrase detection.
- Removed stale comments in OpenAIAdapter.
- **adapters/openai_adapter.py**: Guard child_node retrieval to avoid crash when mapping lacks a child (dangling child check).
- **adapters/openai_adapter.py**: Handle missing `create_time` by defaulting to current timestamp instead of raising.
- **adapters/openai_adapter.py**: Removed stale comments.
- **core/context_cleaner.py**: Properly split PREAMBLE_PATTERNS (start of string) and POSTAMBLE_PATTERNS (end of string).
- **core/context_cleaner.py**: Escaped literal `\?` in "Is there anything else..." pattern.
- **core/context_cleaner.py**: Use `re.match` for preambles and `re.search` anchored with `$` for postambles.

## [0.1.0] - 2026-03-18
### Added
- Initial project structure and documentation.
- `SYNAPSE_SPEC.md` for architectural guidance.
- `.cursorrules` for sovereign development constraints.
- `OpenAIAdapter` boilerplate for Phase 1 Ingestion.
