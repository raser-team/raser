from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.lifecycle import status
from raser.lifecycle import workflow
from raser.lifecycle.slices import Shared
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute
from raser.stages import chain

DEVICES = {"A": ("devA", ["a1", "a2"]), "B": ("devB", ["b1", "b2"])}


@pytest.fixture
def two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Two devices, A and B, in two positions each; the slices only note that they ran."""
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "devA"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(workflow, "_commit", lambda: "abc")
    monkeypatch.setattr(workflow, "device_json", lambda name: {"det_name": name, "bias": {"voltage": 100.0}})
    monkeypatch.setitem(sys.modules, "raser.core.seeding", SimpleNamespace(seed_generators=lambda seed: None))
    monkeypatch.setattr(
        workflow, "_own_process", lambda flow, kwargs, words: workflow._run_job(flow, {**kwargs, "job_dir": words[-1]})
    )
    ran: list[str] = []
    ready = Shared(ready=lambda options, files: Path("field"), start=lambda kwargs, options, files: None)
    pieces = tuple(
        replace(piece, run=lambda options, name=piece.name: ran.append(name), shared=ready if piece.shared else None)
        for piece in chain.expand(DEVICES)
    )
    toy = Workflow(
        name="toy", keys=chain.keys_of(DEVICES), in_file=chain.in_file_of(DEVICES), slices=pieces, devices=DEVICES
    )
    return {"workflow": toy, "ran": ran, "root": tmp_path / "devA" / "toy"}


def _kwargs(**given: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"det_name": "devA", "jobs": None, "batch": False, "mem": 1, "seed": 1}
    kwargs.update(dry_run=False, scan=[], same_seeds=False, _entry_command_prefix=("toy",))
    return {**kwargs, **given}


def test_the_slices_of_two_devices_in_two_positions_each() -> None:
    names = [piece.name for piece in chain.expand(DEVICES)]
    assert names == [
        "deposit",
        "field.A", "current.a1", "readout.a1", "current.a2", "readout.a2",
        "field.B", "current.b1", "readout.b1", "current.b2", "readout.b2",
    ]
    needs = {piece.name: piece.needs for piece in chain.expand(DEVICES)}
    assert needs["current.b2"] == ("deposit", "field.B") and needs["readout.b2"] == ("current.b2",)


def test_another_bias_of_one_device_runs_its_field_and_positions_alone_again(two: dict[str, Any]) -> None:
    execute(two["workflow"], _kwargs())
    two["ran"].clear()

    execute(two["workflow"], _kwargs(**{"A.voltage": 200.0}))

    assert two["ran"] == ["field.A", "current.a1", "readout.a1", "current.a2", "readout.a2"]
    record = json.loads((two["root"] / "seed_1" / "run.json").read_text())
    assert record["files"]["A"]["device"]["bias"]["voltage"] == 200.0
    assert record["files"]["B"]["device"]["bias"]["voltage"] == 100.0


def test_a_scanned_bias_of_one_device_still_gives_every_point_its_own_deposits(two: dict[str, Any]) -> None:
    execute(two["workflow"], _kwargs(scan=["A.voltage=200,300"]))

    for point in ("A.voltage_200", "A.voltage_300"):
        held_in = json.loads((two["root"] / point / "seed_1" / "run.json").read_text())["held_in"]
        assert held_in["deposit"] == point


def test_raser_status_lists_the_slices_of_every_position(two: dict[str, Any]) -> None:
    execute(two["workflow"], _kwargs())
    folder = two["root"] / "seed_1"

    states = status.folder_states(two["workflow"], folder, json.loads((folder / "run.json").read_text()))

    assert set(states) == {piece.name for piece in two["workflow"].slices}
    assert all(by_state["done"] == [0] for by_state in states.values())
