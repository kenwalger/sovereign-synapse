"""Root conftest.py — makes the project root importable for all pytest invocations.

Without this, running `pytest` from inside the venv fails with
ModuleNotFoundError for local top-level packages (adapters, core, mcp_server)
because they are not installed; they only exist as directories relative to the
project root.  Adding the root to sys.path here is the standard fix for
src-less project layouts.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is first on sys.path regardless of where pytest is
# invoked from or whether a venv is active.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
