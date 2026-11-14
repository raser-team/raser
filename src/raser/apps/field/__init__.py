"""Field application: the fields of a device, in work/<device>/field.

The folder holds the field at every bias that was saved; an irradiation flux
that is scanned gets a folder of its own inside it. run.json there records
what the solve read from the device: the field is solved again from the start
when any of that has changed.
"""

import copy
import json
from pathlib import Path

from raser.core.device.build_device import Detector
from raser.core.field import command
from raser.core.field.reading import changed
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute


def _solver(kwargs):
    """The settings of the solver: its own, with those the device file gives
    in "field": {"solver": ...} laid over them."""
    from raser.core.field.solver_section import SOLVER

    def over(base, given):
        merged = dict(base)
        for key, value in given.items():
            both = isinstance(value, dict) and isinstance(merged.get(key), dict)
            merged[key] = over(merged[key], value) if both else value
        return merged

    return over(copy.deepcopy(SOLVER), kwargs["_files"]["device"].get("field", {}).get("solver", {}))


def _ramp_or_weighting(kwargs, cv, wf):
    """One solve into the folder of the run: the bias ramp, or the weighting field."""
    from raser.core.field import solver_section

    solver_section.main(
        {
            **kwargs,
            "target": kwargs["det_name"],
            "cv": cv,
            "wf": wf,
            "solver": _solver(kwargs),
            "_field_directory": kwargs["_run_path"],
        }
    )


def _capacitance(kwargs):
    """The capacitance at one bias the field was saved at, the bias of the
    field itself when none is given, into the folder of that field as
    <bias>V.cv.json."""
    # devsim stays out of the command line until a solve needs it.
    from raser.core.field import saved_point

    my_d = Detector(kwargs["det_name"], kwargs["_files"]["device"])
    bias = my_d.voltage if kwargs["bias"] is None else kwargs["bias"]
    voltage = float(bias if kwargs["cv"] is True else kwargs["cv"])
    folder = Path(kwargs["_run_path"])
    value, frequency = saved_point.capacitance(my_d, folder, voltage, _solver(kwargs))
    point = {"voltage_V": voltage, "capacitance_pF": value, "frequency_Hz": frequency}
    (folder / f"{voltage}V.cv.json").write_text(json.dumps(point, indent=2))
    print(point)


def _empty_devsim():
    """devsim holds one device: emptied for the next part, with the linear
    solver it chose when it was loaded, which emptying forgets."""
    import devsim

    kept = {
        name: devsim.get_parameter(name=name)
        for name in ("direct_solver", "solver_callback")
    }
    devsim.reset_devsim()
    for name, value in kept.items():
        devsim.set_parameter(name=name, value=value)


def solve(kwargs):
    """The parts that are named, in this order: -iv the field up to its bias
    with its IV, -cv the capacitance at one bias the field was saved at, -wf
    the weighting field of the read-out electrodes. With none named, the field
    with its IV and its CV along the ramp, then the weighting field."""
    named = [
        part
        for part, asked in (
            ("iv", kwargs["iv"]),
            ("cv", kwargs["cv"] is not None),
            ("wf", kwargs["wf"]),
        )
        if asked
    ]
    for done, part in enumerate(named or ["iv", "wf"]):
        if done:
            _empty_devsim()
        if part == "cv":
            _capacitance(kwargs)
        else:
            _ramp_or_weighting(kwargs, cv=not named, wf=part == "wf")
    return None


def outdated(old, record):
    """What makes the field of an earlier solve out of date, or None: another
    flux, other settings in the device file, or a change in what the solve
    read from the device."""
    if old["options"] != record["options"]:
        return "another irradiation flux"
    device, before = record["files"]["device"], old["files"]["device"]
    if device.get("field") != before.get("field"):
        return 'other settings under "field" in the device file'
    if "read" not in old:
        return None  # nothing was solved yet
    differing = changed(old["read"], Detector(device["det_name"], device))
    return "the device has another " + ", ".join(differing) if differing else None


WORKFLOW = Workflow(
    name="field",
    job=solve,
    keys=("irradiation_flux",),
    defaults={"irradiation_flux": None},
    seeds=False,
    outdated=outdated,
)


def run(kwargs):
    if kwargs["input"] is not None:  # importing a TCAD field: not on the lifecycle yet
        return command.main({**kwargs, "target": kwargs["det_name"], "dry_run": False})
    return execute(WORKFLOW, kwargs)


def register(subparsers):
    parser = subparsers.add_parser(
        "field", help="calculate electric fields, weighting fields, and IV/CV"
    )
    parser.add_argument("det_name", help="name of the detector")
    parser.add_argument(
        "-v", "--verbose", help="VERBOSE level", action="count", default=0
    )
    parser.add_argument("-iv", help="the field and its IV", action="store_true")
    parser.add_argument(
        "-cv",
        metavar="V",
        type=float,
        nargs="?",
        const=True,
        help="the capacitance at one saved bias, the bias of the field by default",
    )
    parser.add_argument("-wf", help="the weighting field", action="store_true")
    parser.add_argument(
        "-irr", "--irradiation_flux", help="irradiationm flux", type=float
    )
    parser.add_argument("-bias", help="bias voltage", type=float)
    parser.add_argument(
        "-v_current", help="Current voltage for step-by-step simulation", type=float
    )
    parser.add_argument("-noise", help="Detector Noise simulation", action="store_true")
    parser.add_argument("-umf", help="use umf solver", action="store_true")
    parser.add_argument(
        "-ext",
        "--extract",
        dest="input",
        metavar="TCAD_FILE",
        help="import a TCAD field file",
    )
    parser.add_argument(
        "-flip", help="flip the direction of the electric field", action="store_true"
    )
    WORKFLOW.attach(parser)
    parser.set_defaults(_run=lambda kwargs: run(kwargs), _project="det_name")
