"""Current pickle representation for calculated Field quantities."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FieldData:
    points: Sequence[Any]
    values: Sequence[Any]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "values", tuple(self.values))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if len(self.points) != len(self.values):
            raise ValueError("Field points and values must have equal length")
        for name in ("voltage", "dimension"):
            if name not in self.metadata:
                raise ValueError(f"Field metadata is missing {name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "points": list(self.points),
            "values": list(self.values),
            "metadata": dict(self.metadata),
        }


def write_field_data(path: str | Path, data: FieldData) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as stream:
        pickle.dump(data.as_dict(), stream)
    return destination


def read_field_data(path: str | Path) -> FieldData:
    source = Path(path)
    with source.open("rb") as stream:
        value = pickle.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"Field file must contain a mapping: {source}")
    return FieldData(value["points"], value["values"], value["metadata"])
