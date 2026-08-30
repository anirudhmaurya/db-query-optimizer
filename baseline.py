#!/usr/bin/env python3
"""Root entry point script for running the zero-shot baseline."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path if not already present
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.baseline import main

if __name__ == "__main__":
    main()
