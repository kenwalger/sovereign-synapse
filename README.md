# 🏛️ Sovereign Synapse
### Subtitle: Building a Local-First Cognitive Estate

Sovereign Synapse is an infrastructure-first engine designed to aggregate fragmented intellectual history—starting with LLM chats—into a unified, searchable "Synapse" vault. 

> **Note:** This project currently uses OpenAI as its reference implementation. It is designed as a modular blueprint; we welcome community contributions for additional adapters (Claude, Gemini, etc.) that follow our Sovereign principles.

## Core Philosophy: Fiscal Architecture
1. **Infrastructure Integrity:** All data remains on local silicon, moving from "Privacy as a Choice" to "Privacy as a Financial Strategy."
2. **Prose Tax Elimination:** We strip conversational boilerplate at ingestion to reduce the "Reasoning Tax" on downstream inference. `ContextCleaner.is_clean()` flags turns with preamble/postamble; ingested synapses record `prose_tax_redacted` in frontmatter.
3. **Forensic Traceability:** Every turn is distilled and **Ed25519-signed** at ingest via `ContextCleaner.distill_and_sign()`. A deterministic **`receipt_id`** (`urn:synapse:receipt:…` from SHA-256) is the primary **`uuid`**; `signature_hex` proves local provenance. Signing keys are created once under `vault/keys/` (gitignored). MCP `search_synapses` returns Structural Contracts with the **full** canonical `distilled_signal` (use `distilled_signal_excerpt` only for short previews), plus `signature_hex` and `prose_tax_redacted` (see `schemas/synapse_manifest.json`).

## The Sovereign Principles
1. **Zero Cloud Leakage:** All data processing, embedding, and retrieval occurs on local silicon.
2. **Human-First Storage:** The Source of Truth is a vault of human-readable Markdown files—no proprietary databases as the primary record.
3. **Turn-Based Atomic Logic:** Conversations are broken into individual "Turns" (Human + AI) to preserve context and enable granular semantic search.

## Tech Stack
- **Language:** Python 3.11+
- **Inference Engine:** [Ollama](https://ollama.com) (Local LLM)
- **Embedding Model:** `mxbai-embed-large` (via Ollama)
- **Vector Memory:** [ChromaDB](https://www.trychroma.com) (Local Persistence)
- **Processing:** `python-frontmatter` (Safe YAML/Markdown separation)
- **Agent Interface:** [Model Context Protocol](https://modelcontextprotocol.io) (MCP) via `mcp` Python SDK

## 📁 Project Layout
- **`adapters/`** — Translation layers (Reference: `openai_adapter.py`)
- **`analog_bridge.py`** — Ingest scans of **handwritten** engineering notebooks (Ollama vision HTR → Sovereign Markdown → Chroma index)
- **`temporal_mirror.py`** — Compare two **time ranges** in the vault on a topic (Chroma + local Ollama; Markdown report with synapse “forensic” citations)
- **`unbroken_voice.py`** — Build **Sovereign_Persona.json** (Reasoning Fingerprint + legacy system prompt) from the most reflective synapses, using Ollama only
- **`core/`** — The engine: `context_cleaner.py` (prose-tax detection + `distill_signal`) and `vector_store.py`
- **`schemas/`** — `synapse_manifest.json` (typed Sovereign Asset / Structural Contract schema for agents)
- **`vault/keys/`** — Local Ed25519 signing material (`sovereign_signing.key` / `.pub`; absolute path under repo root, generated on first ingest; never commit)
- **`mcp_server/`** — MCP server exposing the vault to Cursor, Claude Desktop, and other MCP hosts
- **`vault/synapses/`** — Turn-based Markdown files (The Source of Truth)
- **`vault/chroma/`** — Local vector persistence for semantic search

## Getting Started

### 1. Requirements
Ensure you have **Ollama** installed and the embedding model pulled:
```bash
ollama pull mxbai-embed-large
```

For **notebook scans** (Analog Bridge), also pull a **vision** model, for example:
```bash
ollama pull llava
# or: ollama pull llama3.2-vision
```

### 2. Installation

```bash
git clone https://github.com/yourusername/sovereign-synapse.git
cd sovereign-synapse
pip install -r requirements.txt
```

### 3. Usage: Ingest & Index

Drop your OpenAI `conversations.json` into `raw_data/openai/` and run the pipeline.

```bash
# Evacuate from the cloud to local Markdown
python main.py ingest raw_data/openai/conversations.json

# "Brainwash" the Markdown into a searchable vector index
python main.py index
```

### 3b. Analog Bridge (handwritten engineering notebooks)

Point the script at a **root folder** of **`.png` or `.jpg` / `.jpeg`** scans (images in **subfolders** are included). The pipeline: vision model → JSON with optional LaTeX in the transcription → **Sovereign Markdown**; the file under `vault/synapses/` is only finalized **after** a successful `VectorStore` index (write temp → embed → replace). Frontmatter includes `source: physical_notebook` and `original_year` for the vector store.

```bash
# Transcribe + index (default vision model: llava)
python analog_bridge.py path/to/scan_folder

# Pause after each page to verify transcriptions and equations, then index
python analog_bridge.py path/to/scan_folder --hitl

# Use another local vision model and a default year when the page is undated
python analog_bridge.py path/to/scan_folder --vision-model llama3.2-vision --default-year 2010
```

The vision model is prompted for Engineering Notebook HTR: dates, diagram descriptions, LaTeX-style math, **Keywords**, and **Temporal Markers** (e.g. `June 2005`), structured as JSON and then stored in human-readable synapse Markdown.

### 3c. Temporal Mirror (compare two eras)

Given a **topic** and two **date ranges** (inclusive, as `YYYY` or `YYYY-YYYY`), the script over-queries the Chroma index, keeps synapses whose `original_timestamp` (or `original_year`) falls in each range, and sends the top snippets to a **local** Ollama chat model to surface evolution, contradictions, and *lost* detail. The **Temporal Mirror Report** includes a forensic block per range listing `urn:uuid:…` synapse ids and short snippets, then the model synthesis. No data leaves the machine.

```bash
# Compare e.g. early work vs recent notes (5 synapses per range; write report file)
python temporal_mirror.py "sensor calibration" --range1 "2005-2010" --range2 "2024-2026" -o reports/mirror.md

# Another LLM, more candidates per range, more vector over-fetch
python temporal_mirror.py "gait analysis" --range1 "2015" --range2 "2024-2025" -n 8 --fetch 300 --llm mistral -o mirror.md
```

Pull the default chat model if needed: `ollama pull llama3`. Set `TEMPORAL_MIRROR_LLM` to default a different model.

If the mirror fails with `❌ Ollama error: Ensure the Ollama service is running locally.`, start the Ollama app/daemon and confirm `ollama list` works, then re-run the command.

For scripting, use `TemporalMirror(chroma_dir=..., llm_model=...).build_report(...)`; the CLI wraps the same class.

### 3d. Unbroken Voice (Legacy Persona & Synapse Navigator)

After the vault is **indexed**, generate **Sovereign_Persona.json** — a durable **Reasoning Fingerprint** (metaphors, values, technical standards, characteristic phrases) and a **legacy system prompt** derived from the ~50 most *reflective* synapses (semantic match to a fixed “self-authorship” probe; optional `context_score` in frontmatter reduces boilerplate weight). This is the **Unbroken Voice**: a stable persona for future local interrogation.

```bash
# Build vault/Sovereign_Persona.json (default: top 50 synapses, local Ollama only)
python unbroken_voice.py

# Custom output path and model
python unbroken_voice.py -o vault/Sovereign_Persona.json --llm mistral -n 50
```

The MCP tool **`query_legacy_persona`** loads that JSON, pulls **Forensic Receipts** from Chroma for the user’s question, and answers *as* you in your voice, citing `synapse_id` lines. For **read-only** deployment (e.g. shared “Legacy” interrogation), start the server with `SYNAPSE_MCP_READ_ONLY=1` or `SYNAPSE_LEGACY_MODE=1` so the Chroma collection cannot be mutated through the client API.

### 4. Search your History

```python
from core.vector_store import VectorStore

store = VectorStore()
results = store.query("What were those sensors for tracking gait?", n_results=3)

for result in results:
    print(f"Match found in: {result['metadata']['original_timestamp']}")
    print(result['document'][:200] + "...")
```

---

## 🤖 MCP Server (Agent Interface)

`mcp_server/server.py` exposes the Synapse vault to any MCP-compatible host via **stdio transport**.

### Tools

| Tool | Description |
|---|---|
| `search_synapses` | Semantic search — returns top N unique-file matches with snippet + metadata |
| `get_recent_context` | Working memory — last N synapses sorted by timestamp |
| `reflect_on_memories` | Reflection — sends snippets (capped: 10 / 15 000 chars) to a local Ollama LLM to surface 3 strategic themes |
| `query_legacy_persona` | **Unbroken Voice** — answer *as* the author using `Sovereign_Persona.json` and Forensic Receipts (local Ollama); requires a prior `unbroken_voice.py` run |
| `get_vault_policy` | Read-only / Legacy policy JSON (`chroma_mutation_forbidden`, `VAULT_READ_ONLY` / `PermissionError` on mutations) |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SYNAPSE_CHROMA_PATH` | `vault/chroma` | Path to your ChromaDB persistence directory |
| `SYNAPSE_COLLECTION` | `synapses` | ChromaDB collection name |
| `SYNAPSE_EMBED_MODEL` | `mxbai-embed-large` | Ollama embedding model |
| `SYNAPSE_REFLECT_LLM` | `llama3` | Ollama chat model for `reflect_on_memories` |
| `SYNAPSE_PERSONA_PATH` | `vault/Sovereign_Persona.json` (under project root) | File produced by `unbroken_voice.py` for `query_legacy_persona` |
| `SYNAPSE_LEGACY_PERSONA_LLM` | falls back to `SYNAPSE_REFLECT_LLM` / `llama3` | Ollama model for the legacy persona reply |
| `SYNAPSE_MCP_READ_ONLY` / `SYNAPSE_LEGACY_MODE` | unset | If `1` / `true` / `yes`, Chroma `add`/`delete`/… are disabled (read-only vault for hosted interrogation) |

### Running the server

```bash
# Standard Python
python mcp_server/server.py

# Or with uv (no venv needed)
uv run mcp_server/server.py
```

### Cursor Integration

Add this block to your Cursor MCP config (`~/.cursor/mcp.json` or workspace `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "sovereign-synapse": {
      "command": "python",
      "args": ["/absolute/path/to/sovereign-synapse/mcp_server/server.py"],
      "env": {
        "SYNAPSE_CHROMA_PATH": "/absolute/path/to/sovereign-synapse/vault/chroma"
      }
    }
  }
}
```

> **Tip:** Pull the reflection LLM once: `ollama pull llama3`

### Running tests

From the repo root, with dependencies installed (`pip install -r requirements.txt` and `pip install -r requirements-dev.txt`), run **`pytest`** locally. On Windows, if third-party pytest plugins break collection (e.g. Celery / incompatible stacks), use **`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`** when invoking pytest.

---

_The Scribe is no longer just a project. It is a partner._
