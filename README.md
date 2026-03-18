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
- **Vector Store:** ChromaDB (Local)
- **Interface:** Model Context Protocol (MCP)

## 🚀 Getting Started
1. Drop your LLM exports into `/raw_data/[provider]/`.
2. Run `pip install -r requirements.txt`.
3. Execute `python main.py raw_data/openai/conversations.json`.

---
*The Scribe is no longer just a project. It is a partner.*