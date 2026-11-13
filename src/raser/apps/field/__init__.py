"""Field application."""

import subprocess
import sys

from raser.core.field import command


def solve(kwargs):
    """The field of a device up to its bias with its IV, its CV, and the
    weighting field of its read-out electrodes, all into one folder; with
    -iv, -cv or -wf only the parts that are named. The CV is taken along the
    bias ramp, so -cv ramps as -iv does."""
    if kwargs.get("input") is not None or kwargs.get("dry_run"):
        return command.main(kwargs)
    parts = [part for part in ("iv", "cv", "wf") if kwargs[part]] or ["iv", "cv", "wf"]
    if parts == ["wf"]:
        return command.main({**kwargs, "cv": False, "wf": True})
    command.main({**kwargs, "cv": "cv" in parts, "wf": False})
    if "wf" in parts:
        # devsim holds one device in a process: the weighting field gets its own.
        words = [word for word in kwargs["_argv"] if word not in ("-iv", "-cv", "-wf")]
        subprocess.run([sys.executable, "-m", "raser.cli.raser", *words, "-wf"], check=True)
    return None


def register(subparsers):
    parser = subparsers.add_parser(
        "field", help="calculate electric fields, weighting fields, and IV/CV"
    )
    parser.add_argument("target", help="Device project")
    parser.add_argument(
        "-v", "--verbose", help="VERBOSE level", action="count", default=0
    )
    parser.add_argument("-iv", help="only the field and its IV", action="store_true")
    parser.add_argument("-cv", help="only the field, its IV and its CV", action="store_true")
    parser.add_argument("-wf", help="only the weighting field", action="store_true")
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
