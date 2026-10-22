"""Project-owned output paths and narrow filesystem operations."""

from __future__ import annotations

from pathlib import Path

from raser.supports.paths import module_work_path
from raser.supports.paths import project_root


def _relative_parts(parts) -> tuple[str, ...]:
    values = tuple(str(part) for part in parts)
    for value in values:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Output label must remain inside the project: {value}")
    return values


def owned_path(owner: str, *parts: str) -> Path:
    labels = _relative_parts((owner, *parts))
    if not owner:
        raise ValueError("Output owner must be named")
    return project_root().joinpath(*labels)


def output(current_file_path, *label):
    """Legacy module-owned output directory."""
    path = module_work_path(current_file_path, *_relative_parts(label))
    create_path(path)
    return str(path.resolve())


def create_path(path):
    destination = Path(path)
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def delete_file(path):
    target = Path(path).resolve()
    try:
        target.relative_to(project_root().resolve())
    except ValueError as exc:
        raise ValueError(
            f"File removal must remain inside the project: {target}"
        ) from exc
    if target.exists():
        target.unlink()
