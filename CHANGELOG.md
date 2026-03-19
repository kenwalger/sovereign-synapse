# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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