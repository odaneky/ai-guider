#!/usr/bin/env python3
"""Cursor hook entry: sessionStart / preToolUse for AI Guider."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from ~/.cursor/hooks without install on PYTHONPATH
_REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if _REPO_SRC.is_dir() and str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

from guider.hooks_runtime import run_hook_stdin  # noqa: E402


if __name__ == "__main__":
    run_hook_stdin()
