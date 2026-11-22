"""Cleanup that runtime owners register for the end of a RASER process."""

from __future__ import annotations

from typing import Callable

_callbacks: list[Callable[[], None]] = []


def at_process_end(callback: Callable[[], None]) -> None:
    if callback not in _callbacks:
        _callbacks.append(callback)


def close() -> None:
    """Run the registered callbacks once, latest registration first."""
    while _callbacks:
        _callbacks.pop()()
