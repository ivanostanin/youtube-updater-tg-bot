#!/usr/bin/env python3
"""CLI entry point to remove Allure artifacts using the project utilities."""

from __future__ import annotations

import sys
from pathlib import Path

from src.utils.allure_cleanup import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
