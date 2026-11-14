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
def solves(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """What a field command solves in its own process, and the commands it starts."""
    done: list[Any] = []

    def ramp_or_weighting(kwargs: dict[str, Any]) -> None:
        done.append("wf" if kwargs["wf"] else "iv+cv" if kwargs["cv"] else "iv")

    monkeypatch.setattr(field.command, "main", ramp_or_weighting)
    monkeypatch.setattr(
        field, "_capacitance", lambda kwargs: done.append(f"cv at {kwargs['cv']}")
    )
    monkeypatch.setattr(
        field.subprocess, "run", lambda command, check: done.append(command[3:])
    )
    return done


@pytest.mark.parametrize(
    ("options", "solved"),
    [
        ((), ["iv+cv", ["field", "HPK-Si-PiN", "-wf"]]),
        (("-iv",), ["iv"]),
        (("-cv", "100"), ["cv at 100.0"]),
        (("-wf",), ["wf"]),
        (("-iv", "-cv"), ["iv", ["field", "HPK-Si-PiN", "-cv"]]),
        (("-cv", "100", "-wf"), ["cv at 100.0", ["field", "HPK-Si-PiN", "-wf"]]),
        (("-w", "-c", "100"), ["cv at 100.0", ["field", "HPK-Si-PiN", "-wf"]]),
        (
            ("-wf", "-iv", "-cv", "0", "-bias", "-300", "-irr", "1e15"),
            [
                "iv",
                [
                    "field",
                    "HPK-Si-PiN",
                    "-cv=0.0",
                    "-bias=-300.0",
                    "-irr=1000000000000000.0",
                ],
                [
                    "field",
                    "HPK-Si-PiN",
                    "-wf",
                    "-bias=-300.0",
                    "-irr=1000000000000000.0",
                ],
            ],
        ),
    ],
)
def test_the_first_part_is_solved_here_and_each_further_one_by_a_command_naming_it_alone(
    solves: list[Any], options: tuple[str, ...], solved: list[Any]
) -> None:
    field.solve(_parsed(*options))

    assert solves == solved
    for started in solved[1:]:
        solves.clear()
        field.solve(_parsed(*started[2:]))
        assert len(solves) == 1 and isinstance(solves[0], str)


def test_a_capacitance_is_refused_at_a_bias_the_field_was_not_saved_at(
    tmp_path: Path,
) -> None:
    (tmp_path / "100.0V.devsim").touch()

    with pytest.raises(FileNotFoundError, match=r"150.*100\.0V\.devsim"):
        saved_point.capacitance(None, tmp_path, 150, {})
