"""Make ``thzprotocol`` importable as a top-level package (its future PyPI form)."""

from pathlib import Path
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "custom_components" / "lwz_thz")
)
