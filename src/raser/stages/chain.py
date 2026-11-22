"""The slices of the chain, from the deposits to the reconstruction, put together for an experiment.

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
from raser.supports.paths import project_root_context
from raser.supports.paths import work_root

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
    "deposit.require",
    "deposit.coincidence_window_ns",
    "deposit.fano",
    "deposit.plots",
    "current.plots",
    "readout.amplifier",
    "readout.sheet_resistance",
    "readout.pre_window_ns",
    "readout.max_post_window_ns",
    "readout.cable",
    "digitizer.device",
    "digitizer.plots",
    "trigger.device",
    "reconstruction.threshold",
    "reconstruction.amplitude_threshold",
    "reconstruction.fractions",
    "reconstruction.edge",
)
# kind of file -> the setting naming it; a setting that is null names no file
COMPONENTS = {
    "source": "deposit.source",
    "g4setup": "deposit.g4setup",
    "digitizer": "digitizer.device",
    "trigger": "trigger.device",
}
NULLABLE = ("trigger.device",)  # null: the trigger of digitizer.device, no file of a trigger device
READERS = {"g4setup": read_g4setup}  # kind of file -> what reads the file its setting names
# <section>.<slot> -> the kind of file: a key inside it is <section>.<slot>.<key>
SLOTS = {
    "field.device": "device",
    "deposit.source": "source",
    "deposit.g4setup": "g4setup",
    "digitizer.device": "digitizer",
    "trigger.device": "trigger",
}
IN_FILE = {"field.voltage": "device.bias.voltage"}  # setting -> where it sits in a file


# What an experiment of the chain takes where its command gives nothing, until
# the examples hold these values; an experiment declares only those it sets
# otherwise. The edge of the pulses the thresholds are set on is as on a
# scope; None: the one the readout wrote its pulses with.
DEFAULTS = {
    "deposit.source": "decay/Sr90",
    "deposit.g4setup": "device_alone",
    "deposit.events_per_job": 1,
    "deposit.require": "any",
    "deposit.coincidence_window_ns": None,
    "deposit.fano": True,
    "deposit.plots": 100,
    "current.plots": 100,
    "readout.amplifier": "SantaCruz+Gali52+Termination50",
    "readout.sheet_resistance": None,
    "readout.pre_window_ns": 15.0,
    "readout.max_post_window_ns": 1000.0,
    "readout.cable": None,
    "digitizer.device": "MXR608A",
    "digitizer.plots": 100,
    "trigger.device": None,
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


def _deposits(kwargs, slots=None):
    from . import deposit

    deposit.deposits(kwargs, slots)


def _of(kwargs, device):
    """The options and files of a job as one device of it sees them: its
    own options without the prefix <device>., its file as files["device"]."""
    if device is None:
        return kwargs
    prefix = device + "."
    seen = {**kwargs, **{key[len(prefix):]: value for key, value in kwargs.items() if key.startswith(prefix)}}
    device_file = kwargs["_files"][device]["device"]
    return {
        **seen,
        "_files": {**kwargs["_files"], "device": device_file},
        "det_name": device_file["det_name"],
        # Where the field of this device is solved and found, see files.field_project.
        "_field_project": str(work_root() / device_file["det_name"]),
    }


def _home(files):
    """The project of a device, work/<device>, where its field is solved and
    found, whichever device the command of the experiment is given."""
    return project_root_context(work_root() / files["device"]["det_name"])


def _field(kwargs, device=None):
    """The field the currents take: found, not solved. A command of the
    chain solves it before the jobs start."""
    kwargs = _of(kwargs, device)
    shared = field.SHARED if device is None else _shared_field(device)
    folder = shared.ready(kwargs, kwargs["_files"])
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


def _digitized(kwargs, device=None, position=None):
    from . import digitizer

    return digitizer.digitized(_of(kwargs, device), position)


def _triggered(kwargs, device=None, position=None):
    """The trigger of the digitizer of each position. A trigger device of
    its own judges an event over all the positions at once, in one node that
    holds a file for each: the chain does not run that yet."""
    from . import trigger

    if kwargs["device"] is not None:
        raise ValueError(
            f"trigger.device {kwargs['device']}: a trigger device of its own is not run by the chain yet; "
            "set trigger.device to null for the trigger of digitizer.device"
        )
    return trigger.triggered(_of(kwargs, device), position)


def _reconstruction(kwargs, device=None, position=None):
    from . import reconstruction

    return reconstruction.run(_of(kwargs, device), position)


def _shared_field(device):
    """The field of one of several devices, shared as field.SHARED is."""

    def seen(options, files):
        of = _of({**options, "_files": files}, device)
        return of, of["_files"]

    def ready(options, files):
        with _home(seen(options, files)[1]):
            return field.ready(*seen(options, files))

    def start(kwargs, options, files):
        with _home(seen(options, files)[1]):
            field.start(kwargs, *seen(options, files))

    def stamp(options, files):
        with _home(seen(options, files)[1]):
            return field.stamp(*seen(options, files))

    return Shared(ready=ready, start=start, stamp=stamp)


DEPOSIT_KEYS = tuple(key for key in KEYS if key.startswith("deposit."))
EDEP_BOUNDS = ("edep_min", "edep_max")  # the keys a slot may set for itself: deposit.<slot>.<bound>
# A job records a number of events or generates one: one of the two is given.
EXCLUSIVE = (("deposit.events_per_job", "deposit.generated_per_job"),)


def _slot_bounds(devices) -> tuple:
    """The energy bounds each slot of several may set for itself."""
    return tuple(f"deposit.{device}.{bound}" for device in devices for bound in EDEP_BOUNDS)


def expand(devices=None, deposit=None) -> tuple:
    """The slices of the chain for the devices of an experiment, the table of
    Workflow.devices: name -> (device, positions). None is one device in one
    place, the chain as it always was: deposit, field, current, readout,
    reconstruction.

    One deposit slice; a field for each device, field.<device> when there are
    more than one; a current and a readout for each position, current.<position>
    and readout.<position> when there are more than one, and a
    digitizer.<position>, a trigger.<position> and a reconstruction.<position>
    of each readout. The digitizer reads the readout, the trigger the
    digitizer, and the reconstruction the events the trigger recorded of the
    digitizer. `deposit` lets an experiment put its
    own energy deposition in place of the stage's, until the Geant4 world
    scripts place its devices (a stopgap for cflm)."""
    devices = devices or {None: (None, [None])}
    several = len(devices) > 1
    if deposit is None:
        # With several devices the slots of the setup are the names of the table.
        deposit = partial(_deposits, slots=tuple(devices)) if several else _deposits
    places = sum(len(positions) for _, positions in devices.values()) > 1
    pieces = [
        Slice(
            "deposit",
            deposit,
            keys=DEPOSIT_KEYS + (_slot_bounds(devices) if several else ()),
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
                    keys=(
                        "readout.amplifier",
                        "readout.sheet_resistance",
                        "readout.pre_window_ns",
                        "readout.max_post_window_ns",
                        "readout.cable",
                    ),
                    new_events=False,
                    needs=(current, name),
                )
            )
            of = {"device": device if several else None, "position": at}
            # What the digitizer draws, its clock phase and its jitter, is of
            # its own seed: the seed of the slice, which holds its position.
            digitizer = f"digitizer.{at}" if at else "digitizer"
            pieces.append(
                Slice(
                    digitizer,
                    partial(_digitized, **of) if at or several else _digitized,
                    keys=("digitizer.device", "digitizer.plots"),
                    counts=("digitizer.plots",),
                    kinds=("digitizer.device",),
                    new_events=False,
                    needs=(readout,),
                )
            )
            # The level of the trigger is a key of digitizer.device that the
            # digitizer does not use: both slices read the file.
            trigger = f"trigger.{at}" if at else "trigger"
            pieces.append(
                Slice(
                    trigger,
                    partial(_triggered, **of) if at or several else _triggered,
                    keys=("trigger.device", "digitizer.device"),
                    kinds=("trigger.device",),
                    new_events=False,
                    needs=(digitizer,),
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
                    needs=(trigger, digitizer),
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
        *_slot_bounds(devices),
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
    slot, and a current, a readout, a digitizer, a trigger and a
    reconstruction for each position."""

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
            nullable=NULLABLE,
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
