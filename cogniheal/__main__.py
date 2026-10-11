"""CogniHeal-Engine package main entrypoint module.

Allows running CogniHeal directly via `python -m cogniheal`.
"""

from __future__ import annotations

import sys
from cogniheal.cli import main

if __name__ == "__main__":
    main()
