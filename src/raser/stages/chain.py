"""The deposits, currents and waveforms slices put together for an experiment.

Building the command line imports this file: it loads nothing heavy. The
slices import their stage when they run.
"""

from raser.lifecycle.slices import Slice
from raser.stages import field

KEYS = (
    "source",
    "g4setup",
    "events_per_job",
    "edep_min",
    "edep_max",
    "fano",
    "plots",
    "voltage",
    "irradiation",
    "amplifier",
)
COMPONENTS = {"source": "source", "g4setup": "g4setup"}  # kind of file -> option
IN_FILE = {"voltage": "device.bias.voltage"}  # option -> where it sits in a file


# The defaults of the options of each stage; an experiment declares only
# those it sets otherwise.
DEPOSIT_DEFAULTS = {"source": "decay/Sr90", "g4setup": "device_alone", "events_per_job": 1, "fano": True}


def deposit_arguments(parser):
    parser.add_argument(
        "source",
        nargs="?",
        help="signal source or beam configuration",
    )
    parser.add_argument("--g4setup", help="what surrounds the device in Geant4")
    parser.add_argument("-evt", "--events-per-job", type=int, help="events per job")
    parser.add_argument(
        "--edep-min", type=float, help="least energy deposited in the device [MeV]"
    )
    parser.add_argument(
        "--edep-max", type=float, help="most energy deposited in the device [MeV]"
    )
    parser.add_argument(
        "-g4_vis", help="visualization of Geant4 experiment", action="store_true"
    )
    parser.add_argument(
        "--g4-vis-driver",
        default="OGL",
        help="Geant4 visualization driver of -g4_vis (default: OGL)",
    )


CURRENT_DEFAULTS = {"plots": 100}


def current_arguments(parser):
    parser.add_argument("--plots", type=int, help="draw the first N recorded events of each job")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=float, help="irradiation flux")


READOUT_DEFAULTS = {"amplifier": "SantaCruz+Gali52+Termination50"}


def readout_arguments(parser):
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")


DEFAULTS = {**DEPOSIT_DEFAULTS, **CURRENT_DEFAULTS, **READOUT_DEFAULTS}


def add_arguments(parser):
    parser.add_argument("det_name", help="Device project")
    deposit_arguments(parser)
    current_arguments(parser)
    readout_arguments(parser)


def job_command(kwargs):
    if kwargs.get("g4_vis"):
        return ["-g4_vis", "--g4-vis-driver", kwargs["g4_vis_driver"]]
    return []


def _deposits(kwargs):
    from . import deposit

    deposit.deposits(kwargs)


def _field(kwargs):
    """The field the currents take: found, not solved. A command of the
    chain solves it before the jobs start."""
    folder = field.SHARED.ready(kwargs, kwargs["_files"])
    if folder is None:
        raise FileNotFoundError(
            f"no field of {kwargs['det_name']} ready for this run: solve it with `raser field {kwargs['det_name']}`"
        )
    return {"field": str(folder)}


def _currents(kwargs):
    from . import current

    current.currents(kwargs)


def _waveforms(kwargs):
    from . import readout

    readout.waveforms(kwargs)


# A slice is named by the file it writes; its keys and kinds of file are what
# it reads and no slice before it does.
SLICES = (
    Slice(
        "deposit",
        _deposits,
        keys=("source", "g4setup", "events_per_job", "edep_min", "edep_max", "fano"),
        kinds=("source", "g4setup"),
        needs=(),
    ),
    # The field is shared by the experiments of a device, in work/<device>/field;
    # it and the deposits do not read each other.
    Slice("field", _field, keys=("voltage", "irradiation"), shared=field.SHARED, needs=()),
    Slice("current", _currents, keys=("plots",), needs=("deposit", "field")),
    # The electronics works on what was measured: its points read the same currents.
    Slice("readout", _waveforms, keys=("amplifier",), new_events=False, needs=("current",)),
)
