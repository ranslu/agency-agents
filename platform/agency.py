#!/usr/bin/env python3
"""Entry point: python3 platform/agency.py <command>. See platform/README.md."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agency_platform.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
