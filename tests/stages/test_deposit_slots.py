from __future__ import annotations

from typing import Any

import pytest

from raser.stages import chain
from raser.stages import deposit as stage


class _Detector:
    def __init__(self, name: str, device: dict[str, Any]) -> None:
        self.name, self.device = name, device


def test_slots_are_built_from_the_device_table_in_its_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stage.bdv, "Detector", _Detector)
    files = {
        "dut": {"device": {"det_name": "PiN"}},
        "ref": {"device": {"det_name": "LGAD"}},
    }
    built = stage.detectors({"_files": files}, ("ref", "dut"))
    assert list(built) == ["ref", "dut"]
    assert [d.name for d in built.values()] == ["LGAD", "PiN"]


def test_a_single_device_keeps_its_one_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stage.bdv, "Detector", _Detector)
    built = stage.detectors({"det_name": "PiN", "_files": {"device": {"det_name": "PiN"}}})
    assert list(built) == ["Device"]


def test_the_deposit_slice_of_several_devices_carries_their_names_in_table_order() -> None:
    table = {"ref": ("LGAD", ["ref"]), "dut": (None, ["dut"])}
    run = chain.expand(table)[0].run
    assert run.keywords["slots"] == ("ref", "dut")


def test_the_field_of_a_device_of_several_is_found_in_its_own_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    import os

    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path))
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "PiN"))
    seen: list[str] = []

    def ready(options: dict[str, Any], files: dict[str, Any]) -> str:
        seen.append(os.environ["RASER_PROJECT_PATH"])
        return "folder"

    monkeypatch.setattr(chain.field, "ready", ready)
    kwargs = {"det_name": "PiN", "_files": {"ref": {"device": {"det_name": "LGAD"}}}}
    assert chain._field(kwargs, device="ref") == {"field": "folder"}
    assert seen == [str(tmp_path / "LGAD")]
