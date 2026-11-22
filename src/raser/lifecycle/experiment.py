"""The base class of the experiments.

A test or an application is a class that inherits Experiment and says what
it is made of: its command word, the stages it runs and its devices, each a
slot with a role. The values of its settings are not in the class.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from raser.lifecycle.workflow import Workflow

TESTED = "tested"  # the device of the command takes this slot
REFERENCE = "reference"  # a device of the experiment itself
ROLES = (TESTED, REFERENCE)
ONE = "Device"  # the slot of an experiment of one device
SLOT = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Slot:
    """One device of an experiment. A tested slot takes the device the
    command names; a reference slot takes `device`. `positions` are the
    places the device takes, one place named as the slot when none is given."""

    role: str = TESTED
    device: str | None = None
    positions: tuple = ()


class Experiment:
    """What a test or an application is made of. A subclass gives `name`,
    the command word, `stages`, `devices` and `workflow`."""

    name: str = ""
    help: str = ""
    stages: tuple = ()
    # slot -> Slot, in the order of the experiment
    devices: Mapping = {ONE: Slot()}
    components: tuple = ()  # the roots of the components of its own
    # A test writes into the project of its device, work/<device>/<name>/;
    # an application into work/<name>/.
    application: bool = False

    @classmethod
    def check(cls) -> None:
        """Refuse a declaration that names no command or whose slots are not
        slots: a name of letters, digits, _ and -, a role of ROLES, a device
        for each reference and none for a tested slot, one tested slot at least."""
        if not cls.name:
            raise ValueError(
                f"{cls.__name__}: an experiment has a name, its command word"
            )
        if len(cls.devices) == 1 and ONE not in cls.devices:
            raise ValueError(
                f"{cls.name}: the slot of an experiment of one device is {ONE}"
            )
        for slot, held in cls.devices.items():
            if not SLOT.fullmatch(slot):
                raise ValueError(
                    f"{cls.name}: the slot {slot!r} is not a name of letters, digits, _ and -"
                )
            if held.role not in ROLES:
                raise ValueError(
                    f"{cls.name}: the slot {slot} is {held.role}; a slot is {' or '.join(ROLES)}"
                )
            if (held.role == REFERENCE) == (held.device is None):
                raise ValueError(
                    f"{cls.name}: the slot {slot} is {held.role}: a reference names its device, "
                    "a tested slot takes the device of the command"
                )
        if cls.devices and not cls.tested():
            raise ValueError(
                f"{cls.name}: no slot is tested; the device of the command takes the tested slots"
            )

    @classmethod
    def tested(cls) -> tuple:
        """The slots the device of the command takes."""
        return tuple(slot for slot, held in cls.devices.items() if held.role == TESTED)

    @classmethod
    def table(cls) -> dict:
        """The devices as Workflow.devices holds them, slot -> (device,
        positions): None for the device of the command. Empty for one device."""
        if len(cls.devices) < 2 and not any(
            held.positions for held in cls.devices.values()
        ):
            return {}
        return {
            slot: (held.device, list(held.positions or (slot,)))
            for slot, held in cls.devices.items()
        }

    @classmethod
    def build(cls) -> Workflow:
        raise NotImplementedError(f"{cls.__name__} builds no workflow")

    @classmethod
    def workflow(cls) -> Workflow:
        """The workflow of the experiment, built once."""
        if "_workflow" not in cls.__dict__:
            cls.check()
            cls._workflow = cls.build()
        return cls.__dict__["_workflow"]

    @classmethod
    def arguments(cls, parser) -> None:
        """The arguments of the command: the device that takes the tested slots."""
        if cls.devices:
            parser.add_argument("det_name", help="Device project")

    @classmethod
    def register(cls, subparsers) -> None:
        parser = subparsers.add_parser(cls.name, help=cls.help or cls.name)
        cls.arguments(parser)
        cls.workflow().attach(parser)
        if cls.devices and not cls.application:
            parser.set_defaults(_project="det_name")
        parser.set_defaults(_components=tuple(cls.components))
