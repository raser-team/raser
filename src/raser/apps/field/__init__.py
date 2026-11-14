"""Field application."""

import json
from pathlib import Path

from raser.core.field import command


def _capacitance(kwargs):
    """The capacitance at one bias the field was saved at, the bias of the
    field itself when none is given, into the folder of that field as
    <bias>V.cv.json."""
    # devsim and ROOT stay out of the command line until a solve needs them.
    from raser.core.device.build_device import Detector
    from raser.core.field import saved_point

    plan = command.build_plan({**kwargs, "wf": False})
    at = plan.configuration.values["bias_voltage"] if kwargs["cv"] is True else kwargs["cv"]
    voltage = float(at)
    value, frequency = saved_point.capacitance(
        Detector(kwargs["target"]),
        plan.directory,
        voltage,
        plan.configuration.values["solver"],
    )
    point = {"voltage_V": voltage, "capacitance_pF": value, "frequency_Hz": frequency}
    (Path(plan.directory) / f"{voltage}V.cv.json").write_text(json.dumps(point, indent=2))
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
    if kwargs.get("input") is not None or kwargs.get("dry_run"):
        return command.main(kwargs)
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
            command.main({**kwargs, "cv": not named, "wf": part == "wf"})
    return None


def register(subparsers):
    parser = subparsers.add_parser(
        "field", help="calculate electric fields, weighting fields, and IV/CV"
    )
    parser.add_argument("target", help="Device project")
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
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(_run=solve, _project="target")
