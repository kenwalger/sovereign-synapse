# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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