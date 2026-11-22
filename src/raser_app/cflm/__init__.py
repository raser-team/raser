"""CEPC fast luminosity monitor: what the lost electrons of a bunch leave in
the pads beside the beam pipe.

An event is one bunch. Its deposits in all 24 pads are in one file; every
pad then has its own currents and waveforms, as the signal app has for its
one device. The electronics is that of signal: the pads are read as in the
time resolution study of the same SiC PIN (Yang et al., Front. Phys. 10
(2022) 718071), on the UCSC board with a broadband amplifier.
"""

from raser.lifecycle.experiment import Experiment
from raser.lifecycle.experiment import Slot
from raser.lifecycle.workflow import Workflow
from raser.stages import chain

# side I at -x, side II at +x of the beam pipe; rows i along y, columns j along the beam
PADS = tuple(f"{side}_{i}_{j}" for side in ("I", "II") for i in range(-3, 3) for j in range(2))


def _deposits(kwargs):
    from . import deposits

    deposits.deposits(kwargs)


class Cflm(Experiment):
    name = "cflm"
    help = "CEPC Fast Luminosity Monitor"
    stages = ("field", "deposit", "current", "readout", "digitizer", "trigger", "reconstruction")
    # One device, the device of the command, in 24 positions: the pads.
    devices = {"Device": Slot(positions=PADS)}

    @classmethod
    def build(cls) -> Workflow:
        devices = cls.table()
        return Workflow(
            name=cls.name,
            keys=tuple(key for key in chain.KEYS if not key.startswith("deposit.")),
            defaults={
                **{key: value for key, value in chain.DEFAULTS.items() if not key.startswith("deposit.")},
                "current.plots": 0,
                "digitizer.plots": 0,
            },
            sections=chain.SECTIONS,
            scanned=chain.SCANNED,
            slots={key: kind for key, kind in chain.SLOTS.items() if not key.startswith("deposit.")},
            components={kind: key for kind, key in chain.COMPONENTS.items() if not key.startswith("deposit.")},
            nullable=chain.NULLABLE,
            in_file=chain.IN_FILE,
            # Its own deposits until the Geant4 world scripts place the pads.
            slices=chain.expand(devices, deposit=_deposits),
            devices=devices,
        )


WORKFLOW = Cflm.workflow()
