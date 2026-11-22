from __future__ import annotations

import argparse
from typing import Any

import pytest

from raser.lifecycle import workflow as workflow_module
from raser.lifecycle.experiment import REFERENCE
from raser.lifecycle.experiment import Experiment
from raser.lifecycle.experiment import Slot
from raser.stages import chain


def _chain(name: str, slots: dict[str, Slot]) -> type[chain.Chain]:
    return type(name.title(), (chain.Chain,), {"name": name, "devices": slots})


def test_the_device_of_the_command_takes_the_tested_slots_and_a_reference_keeps_its_own() -> (
    None
):
    two = _chain("two", {"ref": Slot(REFERENCE, "HPK-Si-LGAD"), "dut": Slot()})
    three = _chain(
        "three",
        {"ref": Slot(REFERENCE, "HPK-Si-LGAD"), "dut": Slot(), "dut2": Slot()},
    )

    assert two.tested() == ("dut",) and three.tested() == ("dut", "dut2")
    assert two.table() == {"ref": ("HPK-Si-LGAD", ["ref"]), "dut": (None, ["dut"])}
    assert three.workflow().devices["dut2"] == (None, ["dut2"])


def test_each_slot_has_a_field_and_a_chain_of_its_own_in_the_order_of_the_class() -> (
    None
):
    planes = {f"ref{i}": Slot(REFERENCE, "TAICHU3") for i in range(3)}
    eight = _chain(
        "eight",
        {
            **planes,
            "dut0": Slot(),
            "dut1": Slot(),
            **{f"ref{i}": Slot(REFERENCE, "TAICHU3") for i in range(3, 6)},
        },
    )

    built = eight.workflow()
    names = [piece.name for piece in built.slices]

    assert names[0] == "deposit"
    assert [name for name in names if name.startswith("field.")] == [
        "field.ref0", "field.ref1", "field.ref2", "field.dut0", "field.dut1",
        "field.ref3", "field.ref4", "field.ref5",
    ]  # fmt: skip
    assert {"current.dut1", "readout.dut1", "reconstruction.dut1"} <= set(names)
    assert "field.dut0.voltage" in built.keys and "field.voltage" not in built.keys
    one = next(piece for piece in built.slices if piece.name == "current.dut1")
    assert one.needs == ("deposit", "field.dut1")


def test_an_experiment_of_one_device_is_the_chain_as_it_was() -> None:
    one = _chain("one", {"Device": Slot()})

    assert one.table() == {} and one.workflow().slices == chain.SLICES
    assert one.workflow() is one.workflow()  # built once


@pytest.mark.parametrize(
    ("slots", "message"),
    [
        ({"dut": Slot()}, "the slot of an experiment of one device is Device"),
        ({"a b": Slot(), "dut": Slot()}, "'a b' is not a name"),
        ({"ref": Slot("spare", "X"), "dut": Slot()}, "ref is spare; a slot is tested or reference"),
        ({"ref": Slot(REFERENCE), "dut": Slot()}, "a reference names its device"),
        ({"ref": Slot(REFERENCE, "X"), "dut": Slot(device="Y")}, "a tested slot takes the device of the command"),
        ({"a": Slot(REFERENCE, "X"), "b": Slot(REFERENCE, "X")}, "no slot is tested"),
    ],
)  # fmt: skip
def test_a_declaration_whose_slots_are_not_slots_is_refused(
    slots: dict[str, Slot], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _chain("bad", slots).workflow()


def test_the_command_of_an_experiment_class_is_its_name_and_writes_where_its_kind_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflow_module, "WORKFLOWS", {})

    class Test(Experiment):
        name = "mine"
        components = ("my_lab/mine",)

        @classmethod
        def build(cls) -> Any:
            return workflow_module.Workflow(name=cls.name, job=lambda kwargs: None)

    class Application(Test):
        name = "plant"
        application = True

    commands = argparse.ArgumentParser().add_subparsers()
    Test.register(commands)
    Application.register(commands)

    test = commands.choices["mine"]
    assert test.get_default("_project") == "det_name"  # work/<device>/mine/
    assert test.get_default("_components") == ("my_lab/mine",)
    assert commands.choices["plant"].get_default("_project") is None  # work/plant/
    assert set(workflow_module.WORKFLOWS) == {"mine", "plant"}
