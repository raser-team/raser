"""The deposits, currents, waveforms and reconstruction slices put together for an experiment.

Building the command line imports this file: it loads nothing heavy. The
slices import their stage when they run.
"""

from functools import partial

from raser.components.loader import read_g4setup
from raser.lifecycle.slices import Shared
from raser.lifecycle.slices import Slice
from raser.stages import field

KEYS = (
    "source",
    "g4setup",
    "events_per_job",
    "generated_per_job",
    "generated_limit",
    "edep_min",
    "edep_max",
    "fano",
    "plots",
    "voltage",
    "irradiation",
    "amplifier",
    "sheet_resistance",
    "threshold",
    "amplitude_threshold",
    "fractions",
    "edge",
)
COMPONENTS = {"source": "source", "g4setup": "g4setup"}  # kind of file -> option
READERS = {"g4setup": read_g4setup}  # kind of file -> what reads the file its option names
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
    parser.add_argument("-evt", "--events-per-job", type=int, help="events a job records")
    parser.add_argument("-gen", "--generated-per-job", type=int, help="events a job generates, in place of -evt")
    parser.add_argument(
        "--generated-limit", type=int, help="the most events a job generates to record its -evt"
    )
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


READOUT_DEFAULTS = {"amplifier": "SantaCruz+Gali52+Termination50", "sheet_resistance": None}


def readout_arguments(parser):
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser.add_argument(
        "--sheet-resistance", type=float, help="of the resistive layer of the device, in place of its file's [Ohm]"
    )


# The edge of the pulses the thresholds are set on, as on a scope; None:
# the one the readout wrote its pulses with.
RECONSTRUCTION_DEFAULTS = {
    "threshold": 10.0,
    "amplitude_threshold": 10.0,
    "fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    "edge": None,
}


def reconstruction_arguments(parser):
    parser.add_argument("-threshold", type=float, help="of the times and the area of the pulses [mV]")
    parser.add_argument("-amplitude_threshold", type=float, help="of the selected events [mV]")
    parser.add_argument("--edge", choices=("rising", "falling"), help="the edge of the pulses the thresholds are set on; by default that of the readout")


DEFAULTS = {**DEPOSIT_DEFAULTS, **CURRENT_DEFAULTS, **READOUT_DEFAULTS, **RECONSTRUCTION_DEFAULTS}


def add_arguments(parser):
    parser.add_argument("det_name", help="Device project")
    deposit_arguments(parser)
    current_arguments(parser)
    readout_arguments(parser)
    reconstruction_arguments(parser)


def job_command(kwargs):
    if kwargs.get("g4_vis"):
        return ["-g4_vis", "--g4-vis-driver", kwargs["g4_vis_driver"]]
    return []


def _deposits(kwargs):
    from . import deposit

    deposit.deposits(kwargs)


def _of(kwargs, device):
    """The options and files of a job as one device of it sees them: its
    own options without the prefix <device>., its file as files["device"]."""
    if device is None:
        return kwargs
    prefix = device + "."
    seen = {**kwargs, **{key[len(prefix):]: value for key, value in kwargs.items() if key.startswith(prefix)}}
    device_file = kwargs["_files"][device]["device"]
    return {**seen, "_files": {**kwargs["_files"], "device": device_file}, "det_name": device_file["det_name"]}


def _field(kwargs, device=None):
    """The field the currents take: found, not solved. A command of the
    chain solves it before the jobs start."""
    kwargs = _of(kwargs, device)
    folder = field.SHARED.ready(kwargs, kwargs["_files"])
    if folder is None:
        raise FileNotFoundError(
            f"no field of {kwargs['det_name']} ready for this run: solve it with `raser field {kwargs['det_name']}`"
        )
    return {"field": str(folder)}


def _currents(kwargs, device=None, position=None):
    from . import current

    return current.currents(_of(kwargs, device), position)


def _waveforms(kwargs, device=None, position=None):
    from . import readout

    return readout.waveforms(_of(kwargs, device), position)


def _reconstruction(kwargs, device=None, position=None):
    from . import reconstruction

    return reconstruction.run(_of(kwargs, device), position)


def _shared_field(device):
    """The field of one of several devices, shared as field.SHARED is."""

    def seen(options, files):
        of = _of({**options, "_files": files}, device)
        return of, of["_files"]

    return Shared(
        ready=lambda options, files: field.ready(*seen(options, files)),
        start=lambda kwargs, options, files: field.start(kwargs, *seen(options, files)),
        stamp=lambda options, files: field.stamp(*seen(options, files)),
    )


DEPOSIT_KEYS = (
    "source", "g4setup", "events_per_job", "generated_per_job", "generated_limit", "edep_min", "edep_max", "fano"
)
# A job records a number of events or generates one: one of the two is given.
EXCLUSIVE = (("events_per_job", "generated_per_job"),)


def expand(devices=None, deposit=_deposits) -> tuple:
    """The slices of the chain for the devices of an experiment, the table of
    Workflow.devices: name -> (device, positions). None is one device in one
    place, the chain as it always was: deposit, field, current, readout,
    reconstruction.

    One deposit slice; a field for each device, field.<device> when there are
    more than one; a current and a readout for each position, current.<position>
    and readout.<position> when there are more than one, and a reconstruction
    of each readout, reconstruction.<position>, each reading the
    deposits and the field of its device. `deposit` lets an experiment put its
    own energy deposition in place of the stage's, until the Geant4 world
    scripts place its devices (a stopgap for cflm)."""
    devices = devices or {None: (None, [None])}
    several = len(devices) > 1
    places = sum(len(positions) for _, positions in devices.values()) > 1
    pieces = [
        Slice(
            "deposit",
            deposit,
            keys=DEPOSIT_KEYS,
            kinds=("source", "g4setup"),
            needs=(),
        )
    ]
    for device, (_, positions) in devices.items():
        prefix = f"{device}." if several else ""
        name = f"field.{device}" if several else "field"
        # The field is shared by the experiments of a device, in work/<device>/field;
        # it and the deposits do not read each other.
        pieces.append(
            Slice(
                name,
                partial(_field, device=device) if several else _field,
                keys=(f"{prefix}voltage", f"{prefix}irradiation"),
                shared=_shared_field(device) if several else field.SHARED,
                needs=(),
            )
        )
        for position in positions:
            at = position if places else None
            current = f"current.{at}" if at else "current"
            pieces.append(
                Slice(
                    current,
                    partial(_currents, device=device if several else None, position=at) if at or several else _currents,
                    keys=("plots",),
                    needs=("deposit", name),
                )
            )
            # The electronics works on what was measured: its points read the same
            # currents. It takes the circuit of the device from its field too.
            readout = f"readout.{at}" if at else "readout"
            pieces.append(
                Slice(
                    readout,
                    partial(_waveforms, device=device if several else None, position=at) if at or several else _waveforms,
                    keys=("amplifier", "sheet_resistance"),
                    new_events=False,
                    needs=(current, name),
                )
            )
            pieces.append(
                Slice(
                    f"reconstruction.{at}" if at else "reconstruction",
                    partial(_reconstruction, device=device if several else None, position=at)
                    if at or several
                    else _reconstruction,
                    keys=("threshold", "amplitude_threshold", "fractions", "edge"),
                    new_events=False,
                    needs=(readout,),
                )
            )
    return tuple(pieces)


def keys_of(devices) -> tuple:
    """The options of the chain for the devices: those of each device under its name."""
    if len(devices) < 2:
        return KEYS
    own = ("voltage", "irradiation")
    return (*(key for key in KEYS if key not in own), *(f"{device}.{key}" for device in devices for key in own))


def in_file_of(devices) -> dict:
    """Where the options of the devices sit in their files."""
    if len(devices) < 2:
        return IN_FILE
    return {f"{device}.voltage": f"{device}.device.bias.voltage" for device in devices}


# A slice is named by the file it writes; its keys and kinds of file are what
# it reads and no slice before it does.
SLICES = expand()
