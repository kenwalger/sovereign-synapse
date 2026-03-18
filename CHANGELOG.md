# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.1.1] - 2026-03-18
### Added
- `core/context_cleaner.py`: Introduced heuristic-based regex scanning to identify AI conversational noise.
- Integrated `ContextCleaner` into `OpenAIAdapter` to dynamically flag preambles in YAML frontmatter.

### Fixed
- Improved signal-to-noise ratio in generated Markdown synapses by identifying non-technical conversational "fluff."

## [0.1.0] - 2026-03-18
### Added
- Initial project structure and documentation.
- `SYNAPSE_SPEC.md` for architectural guidance.
- `.cursorrules` for sovereign development constraints.
- `OpenAIAdapter` boilerplate for Phase 1 Ingestion.