from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raser.apps import field
from raser.cli.raser import build_parser
from raser.core.field import saved_point


def _parsed(*words: str) -> dict[str, Any]:
    argv = ["field", "HPK-Si-PiN", *words]
    return {**vars(build_parser().parse_args(argv)), "_argv": argv}


@pytest.fixture
def solves(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What a field command solves, and where it empties devsim, in order."""
    done: list[str] = []

    def ramp_or_weighting(kwargs: dict[str, Any]) -> None:
        done.append("wf" if kwargs["wf"] else "iv+cv" if kwargs["cv"] else "iv")

    monkeypatch.setattr(field.command, "main", ramp_or_weighting)
    monkeypatch.setattr(
        field, "_capacitance", lambda kwargs: done.append(f"cv at {kwargs['cv']}")
    )
    monkeypatch.setattr(field, "_empty_devsim", lambda: done.append("emptied"))
    return done


@pytest.mark.parametrize(
    ("options", "solved"),
    [
        ((), ["iv+cv", "emptied", "wf"]),
        (("-iv",), ["iv"]),
        (("-cv",), ["cv at True"]),
        (("-cv", "0"), ["cv at 0.0"]),
        (("-wf",), ["wf"]),
        (("-w", "-c", "100"), ["cv at 100.0", "emptied", "wf"]),
        (("-wf", "-cv", "-iv"), ["iv", "emptied", "cv at True", "emptied", "wf"]),
    ],
)
def test_the_parts_named_are_solved_in_order_with_devsim_emptied_between_them(
    solves: list[str], options: tuple[str, ...], solved: list[str]
) -> None:
    field.solve(_parsed(*options))

    assert solves == solved


def test_a_capacitance_is_refused_at_a_bias_the_field_was_not_saved_at(
    tmp_path: Path,
) -> None:
    (tmp_path / "100.0V.devsim").touch()

    with pytest.raises(FileNotFoundError, match=r"150.*100\.0V\.devsim"):
        saved_point.capacitance(None, tmp_path, 150, {})
