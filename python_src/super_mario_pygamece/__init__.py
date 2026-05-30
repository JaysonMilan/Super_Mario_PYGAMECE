"""Standalone Pygame CE port for Super Mario SDL3 assets."""

from __future__ import annotations

import os
import warnings

__all__ = ["__version__"]

__version__ = "0.1.0"

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)
