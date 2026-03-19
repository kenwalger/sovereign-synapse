# 🏛️ Sovereign Synapse
### Subtitle: Building a Local-First Cognitive Estate

Sovereign Synapse is a local-first engine designed to aggregate fragmented intellectual history—LLM chats, scanned notebooks, and technical logs—into a unified, searchable "Synapse" vault.

## 🛡️ The Sovereign Principles
1. **Zero Cloud Leakage:** All data processing, embedding, and HTR occurs on local silicon.
2. **Human-First Storage:** The Source of Truth is a vault of human-readable Markdown files.
3. **Turn-Based Atomic Logic:** Conversations are broken into individual "Turns" (Human + AI) to preserve context without bloat.

## 🛠️ Tech Stack
- **Language:** Python 3.11+
- **Inference:** Ollama (Local LLM)
- **Embeddings:** Ollama `mxbai-embed-large`
- **Vector Store:** ChromaDB (Local)
- **Testing:** pytest
- **Interface:** Model Context Protocol (MCP)

## 📁 Project Layout
- **`vault/synapses/`** — Turn-based Markdown files (the source of truth)
- **`vault/chroma/`** — ChromaDB persistence for semantic search

## 🚀 Getting Started
1. Drop your LLM exports into `raw_data/[provider]/` (or any path).
2. Run `pip install -r requirements.txt`.
3. **Ingest:** `python main.py raw_data/openai/conversations.json`
4. **Index (Phase 1.3):** With [Ollama](https://ollama.com) running and `mxbai-embed-large` pulled (`ollama pull mxbai-embed-large`), index synapses into the vector store:

   ```python
   from core.vector_store import VectorStore
   from pathlib import Path

   store = VectorStore()
   for path in Path("vault/synapses").glob("*.md"):
       store.add_synapse(str(path))
   ```

---
*The Scribe is no longer just a project. It is a partner.*