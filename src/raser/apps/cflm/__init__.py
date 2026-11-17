"""CEPC fast luminosity monitor: what the lost electrons of a bunch leave in
the pads beside the beam pipe.

An event is one bunch. Its deposits in all 24 pads are in one file; every
pad then has its own currents and waveforms, as the signal app has for its
one device. The electronics is that of signal: the pads are read as in the
time resolution study of the same SiC PIN (Yang et al., Front. Phys. 10
(2022) 718071), on the UCSC board with a broadband amplifier.
"""

from raser.lifecycle.workflow import Workflow
from raser.stages import chain

# side I at -x, side II at +x of the beam pipe; rows i along y, columns j along the beam
PADS = tuple(f"{side}_{i}_{j}" for side in ("I", "II") for i in range(-3, 3) for j in range(2))


def _deposits(kwargs):
    from . import deposits

    deposits.deposits(kwargs)


# One device, the device of the command, in 24 positions: the pads.
DEVICES = {"pad": (None, list(PADS))}
# Its own deposits until the Geant4 world scripts place the pads.
SLICES = chain.expand(DEVICES, deposit=_deposits)

WORKFLOW = Workflow(
    name="cflm",
    keys=("voltage", "irradiation", "plots", "amplifier", "sheet_resistance", "threshold", "amplitude_threshold", "fractions", "edge"),
    defaults={**chain.READOUT_DEFAULTS, **chain.RECONSTRUCTION_DEFAULTS, "plots": 0},
    in_file=chain.IN_FILE,
    slices=SLICES,
    devices=DEVICES,
)


def register(subparsers):
    parser = subparsers.add_parser("cflm", help="CEPC Fast Luminosity Monitor")
    parser.add_argument("det_name", help="Device project")
    parser.add_argument("--plots", type=int, help="draw the first N recorded bunches of each pad")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=float, help="irradiation flux")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser.add_argument("--sheet-resistance", type=float, help="of the resistive layer of the pads [Ohm]")
    chain.reconstruction_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name")
