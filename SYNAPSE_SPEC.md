# 🏛️ Sovereign Synapse: Technical Specification (MVP)

## 1. The Markdown Standard (The Source of Truth)
- **Format:** CommonMark with YAML Frontmatter.
- **File Naming:** `YYYY-MM-DD-HHMM-[SLUG].md` (Human-readable + chronological).
- **Frontmatter Schema:**
  - `uuid`: unique identifier (urn:uuid:...)
  - `source`: [claude_export, gpt_export, engineering_notebook_2005]
  - `model`: [claude-3-opus, gpt-4o, human]
  - `tags`: []
  - `original_timestamp`: ISO-8601
  - `context_score`: [0-1] (Flagging potential boilerplate/preamble)

## 2. Phase 1: The Ingestor (CLI)
- **Primary Goal:** Parse raw JSON/CSV into Turn-Based Markdown.
- **Atomic Principle:** Each "Turn" (Human Question + AI Answer) is a single file. 
- **Boilerplate Strategy:** DO NOT DELETE. Use a `preamble: true` flag in YAML for suspected AI fluff. This allows the Query Layer (Phase 2) to filter it without losing data.

## 3. Tech Stack (Phase 1)
- **Language:** Python 3.11+
- **Parsing:** `pydantic` (for schema validation of raw exports).
- **Templates:** `jinja2` (for consistent Markdown generation).