# Contributing to Sovereign Synapse

Thank you for your interest in helping build a local-first cognitive estate. As a "Sovereign" project, we adhere to strict architectural principles to ensure data privacy and long-term durability.

## 🛡️ The Sovereign Standard
Before submitting a Pull Request, verify that your changes meet these criteria:
1. **No Cloud Leakage:** No new dependencies on cloud-based APIs (OpenAI, Anthropic, Pinecone, etc.).
2. **Local-First:** All processing, embeddings, and storage must remain on the user's local hardware.
3. **Atomic Context:** Code must respect the "Turn-Based" Markdown structure defined in `SYNAPSE_SPEC.md`.

## 🛠️ Development Setup
1. Clone the repo: `git clone <repo-url>`
2. Create a venv: `python -m venv venv`
3. Activate: `source venv/bin/activate` (Mac/Linux) or `.\venv\Scripts\activate` (Windows)
4. Install: `pip install -r requirements.txt`

## 📝 Pull Request Process
- **Describe the Change:** Explain how this improves the "Synapse" or the "Scribe."
- **Dry Run:** Include a log or screenshot of the script running against a `raw_data` sample.
- **Documentation:** Update docstrings using the Google Python Style Guide.