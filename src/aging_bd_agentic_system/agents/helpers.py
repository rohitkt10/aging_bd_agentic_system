"""
Helper utilities for agent nodes.
"""

from __future__ import annotations

from typing import Any


def unique_non_empty(items: list[Any]) -> list[Any]:
    """Return unique non-empty items from a list."""
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
