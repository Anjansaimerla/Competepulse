#!/usr/bin/env python3
"""Competepulse entry point: runs the full weekly intelligence pipeline."""

import sys

from competepulse.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
