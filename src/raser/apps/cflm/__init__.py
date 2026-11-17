"""CEPC fast luminosity monitor: what the lost electrons of a bunch leave in
the pads beside the beam pipe.

An event is one bunch. Its deposits in all 24 pads are in one file; every
pad then has its own currents and waveforms, as the signal app has for its
one device. The electronics is that of signal: the pads are read as in the
time resolution study of the same SiC PIN (Yang et al., Front. Phys. 10
(2022) 718071), on the UCSC board with a broadband amplifier.
"""

from functools import partial

from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow
from raser.stages import chain

# side I at -x, side II at +x of the beam pipe; rows i along y, columns j along the beam
PADS = tuple(f"{side}_{i}_{j}" for side in ("I", "II") for i in range(-3, 3) for j in range(2))


def _deposits(kwargs):
    from . import deposits

    deposits.deposits(kwargs)


def _currents(pad, kwargs):
    from . import signals

    return signals.currents(kwargs, pad)


def _waveforms(pad, kwargs):
    from . import signals

    return signals.waveforms(kwargs, pad)


SLICES = (
    Slice("deposits", _deposits),
    *(
        Slice(f"currents.{pad}", partial(_currents, pad), keys=("voltage", "irradiation", "plots"))
        for pad in PADS
    ),
    # The electronics works on what was measured: its points read the same currents.
    *(
        Slice(f"waveforms.{pad}", partial(_waveforms, pad), keys=("amplifier",), new_events=False)
        for pad in PADS
    ),
)

WORKFLOW = Workflow(
    name="cflm",
    keys=("voltage", "irradiation", "plots", "amplifier"),
    defaults={"amplifier": "SantaCruz+Gali52+Termination50", "plots": 0},
    in_file=chain.IN_FILE,
    slices=SLICES,
)


def register(subparsers):
    parser = subparsers.add_parser("cflm", help="CEPC Fast Luminosity Monitor")
    parser.add_argument("det_name", help="Device project")
    parser.add_argument("--plots", type=int, help="draw the first N recorded bunches of each pad")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=float, help="irradiation flux")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name")
