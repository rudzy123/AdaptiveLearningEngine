#!/usr/bin/env python3
"""Wrapper: ingest PDFs into chunks (see project root ingest_pdfs.py)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    runpy.run_path(str(ROOT / "ingest_pdfs.py"), run_name="__main__")
