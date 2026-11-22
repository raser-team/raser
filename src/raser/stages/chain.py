"""The deposits, currents, waveforms and reconstruction slices put together for an experiment.

Building the command line imports this file: it loads nothing heavy. The
slices import their stage when they run.
"""

from collections.abc import Mapping
from functools import partial

from raser.components.loader import read_g4setup
from raser.lifecycle.experiment import Experiment
from raser.lifecycle.slices import Shared
from raser.lifecycle.slices import Slice
from raser.lifecycle.workflow import Workflow
from raser.stages import field

SECTIONS = ("field", "deposit", "current", "readout", "digitizer", "trigger", "reconstruction", "analysis")
# What is measured is set up to the readout; from the digitizer on the events are analysed.
SCANNED = ("field", "deposit", "current", "readout")
KEYS = (
    "field.voltage",
    "field.irradiation_flux",
    "deposit.source",
    "deposit.g4setup",
    "deposit.events_per_job",
    "deposit.generated_per_job",
    "deposit.generated_limit",
    "deposit.edep_min",
    "deposit.edep_max",
    "deposit.fano",
    "deposit.plots",
    "current.plots",
    "readout.amplifier",
    "readout.sheet_resistance",
    "reconstruction.threshold",
    "reconstruction.amplitude_threshold",
    "reconstruction.fractions",
    "reconstruction.edge",
)
COMPONENTS = {"source": "deposit.source", "g4setup": "deposit.g4setup"}  # kind of file -> the setting naming it
READERS = {"g4setup": read_g4setup}  # kind of file -> what reads the file its setting names
# <section>.<slot> -> the kind of file: a key inside it is <section>.<slot>.<key>
SLOTS = {"field.device": "device", "deposit.source": "source", "deposit.g4setup": "g4setup"}
IN_FILE = {"field.voltage": "device.bias.voltage"}  # setting -> where it sits in a file


# What an experiment of the chain takes where its command gives nothing, until
# the examples hold these values; an experiment declares only those it sets
# otherwise. The edge of the pulses the thresholds are set on is as on a
# scope; None: the one the readout wrote its pulses with.
DEFAULTS = {
    "deposit.source": "decay/Sr90",
    "deposit.g4setup": "device_alone",
    "deposit.events_per_job": 1,
    "deposit.fano": True,
    "deposit.plots": 100,
    "current.plots": 100,
    "readout.amplifier": "SantaCruz+Gali52+Termination50",
    "readout.sheet_resistance": None,
    "reconstruction.threshold": 10.0,
    "reconstruction.amplitude_threshold": 10.0,
    "reconstruction.fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    "reconstruction.edge": None,
}


def run_arguments(parser):
    """What holds for one run only and is no setting of config.json."""
    parser.add_argument(
        "-g4_vis", help="open a window to turn the Geant4 geometry and tracks in", action="store_true"
    )
    parser.add_argument(
        "--g4-vis-driver",
        default="TSG_QT_GLES",
        help="Geant4 visualization driver of -g4_vis (default: TSG_QT_GLES, a window)",
    )


def add_arguments(parser):
    parser.add_argument("det_name", help="Device project")
    run_arguments(parser)


def job_command(kwargs):
    if kwargs.get("g4_vis"):
        return ["-g4_vis", "--g4-vis-driver", kwargs["g4_vis_driver"]]
    return []


def analyse(root):
    """The last stage, for the experiments whose chain ends in an analysis."""
    from . import analysis

    return analysis.collect(root)


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


DEPOSIT_KEYS = tuple(key for key in KEYS if key.startswith("deposit."))
# A job records a number of events or generates one: one of the two is given.
EXCLUSIVE = (("deposit.events_per_job", "deposit.generated_per_job"),)


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
            counts=("deposit.events_per_job", "deposit.generated_per_job", "deposit.plots"),
            kinds=("deposit.source", "deposit.g4setup"),
            needs=(),
        )
    ]
    for device, (_, positions) in devices.items():
        prefix = f"field.{device}." if several else "field."
        name = f"field.{device}" if several else "field"
        # The field is shared by the experiments of a device, in work/<device>/field;
        # it and the deposits do not read each other.
        pieces.append(
            Slice(
                name,
                partial(_field, device=device) if several else _field,
                keys=(f"{prefix}voltage", f"{prefix}irradiation_flux"),
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
                    keys=("current.plots",),
                    counts=("current.plots",),
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
                    keys=("readout.amplifier", "readout.sheet_resistance"),
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
                    keys=tuple(key for key in KEYS if key.startswith("reconstruction.")),
                    new_events=False,
                    needs=(readout,),
                )
            )
    return tuple(pieces)


def keys_of(devices) -> tuple:
    """The options of the chain for the devices: those of each device under its name."""
    if len(devices) < 2:
        return KEYS
    own = ("field.voltage", "field.irradiation_flux")
    return (
        *(key for key in KEYS if key not in own),
        *(f"field.{device}.{key.split('.', 1)[1]}" for device in devices for key in own),
    )


def in_file_of(devices) -> dict:
    """Where the options of the devices sit in their files."""
    if len(devices) < 2:
        return IN_FILE
    return {f"field.{device}.voltage": f"{device}.device.bias.voltage" for device in devices}


# A slice is named by the file it writes; its keys and kinds of file are what
# it reads and no slice before it does.
SLICES = expand()


class Chain(Experiment):
    """An experiment that runs the chain for its devices: a field for each
    slot, and a current, a readout and a reconstruction for each position."""

    stages = SECTIONS
    # What the experiment takes where the chain takes another value, until
    # the values come from the config.json of the examples.
    defaults: Mapping = {}

    @classmethod
    def build(cls) -> Workflow:
        devices = cls.table()
        return Workflow(
            name=cls.name,
            keys=keys_of(devices),
            defaults={**DEFAULTS, **cls.defaults},
            sections=SECTIONS,
            scanned=SCANNED,
            slots=SLOTS,
            components=COMPONENTS,
            readers=READERS,
            in_file=in_file_of(devices),
            slices=expand(devices) if devices else SLICES,
            exclusive=EXCLUSIVE,
            command=job_command,
            analysis=analyse,
            devices=devices,
        )

    @classmethod
    def arguments(cls, parser) -> None:
        add_arguments(parser)
