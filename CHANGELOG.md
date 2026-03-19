# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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
