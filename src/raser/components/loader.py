"""Load JSON definitions from the active component search path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raser.supports.paths import component_file_path
from raser.supports.paths import component_path


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"Component definition must be a JSON object: {path}")
    return value


def load_component(kind: str, selector: str | Path) -> tuple[Path, dict[str, Any]]:
    candidate = Path(selector)
    explicit = (
        hasattr(selector, "__fspath__")
        or candidate.is_absolute()
        or (candidate.parts and candidate.parts[0] in {".", ".."})
        or bool(candidate.suffix)
    )
    path = (
        component_file_path(kind, selector)
        if explicit
        else component_path(kind, str(selector) + ".json")
    )
    return path, _read_json(path)


def load_source(selector: str | Path) -> tuple[Path, dict[str, Any]]:
    return load_component("source", selector)


def load_laser(selector: str | Path) -> tuple[Path, dict[str, Any]]:
    return load_component("laser", selector)
