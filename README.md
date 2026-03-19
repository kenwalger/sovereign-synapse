# 🏛️ Sovereign Synapse
### Subtitle: Building a Local-First Cognitive Estate

Sovereign Synapse is a local-first engine designed to aggregate fragmented intellectual history—starting with LLM chats—into a unified, searchable "Synapse" vault. 

> **Note:** This project currently uses OpenAI as its reference implementation. It is designed as a modular blueprint; we welcome community contributions for additional adapters (Claude, Gemini, etc.) that follow our Sovereign principles.

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

## 📁 Project Layout
- **`adapters/`** — Translation layers (Reference: `openai_adapter.py`)
- **`core/`** — The engine: `context_cleaner.py` and `vector_store.py`
- **`vault/synapses/`** — Turn-based Markdown files (The Source of Truth)
- **`vault/chroma/`** — Local vector persistence for semantic search

## Getting Started

### 1. Requirements
Ensure you have **Ollama** installed and the embedding model pulled:
```bash
ollama pull mxbai-embed-large
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

_The Scribe is no longer just a project. It is a partner._
