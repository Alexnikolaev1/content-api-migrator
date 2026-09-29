"""Repo-root launcher: no PYTHONPATH, no install required."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from content_api_migrator.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
