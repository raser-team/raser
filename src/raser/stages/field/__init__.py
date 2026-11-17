"""Field application: the fields of a device, in work/<device>/field.

The folder holds the field at every bias that was saved; an irradiation flux
that is scanned gets a folder of its own inside it. run.json there records
what the solve read from the device: the field is solved again from the start
when any of that has changed.
"""

import argparse
import copy
import json
import os
from pathlib import Path

from raser.core.device.build_device import Detector
from raser.core.field.reading import changed
from raser.core.field.solved import DEFAULT_MODE
from raser.core.field.solved import HAS_DEVSIM
from raser.core.field.solved import solved_field
from raser.lifecycle.slices import Shared
from raser.lifecycle.workflow import WORKFLOWS
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute
from raser.lifecycle.workflow import make_shared
from raser.supports.paths import project_root_context


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


def _bias(kwargs):
    """The bias the command asks for: its option, else the bias of the device."""
    if kwargs["bias"] is not None:
        return float(kwargs["bias"])
    return Detector(kwargs["det_name"], kwargs["_files"]["device"]).voltage


def _solved(kwargs, asset, at):
    """Whether run.json of the folder lists `asset` at `at` among what is solved."""
    record = Path(kwargs["_run_path"]) / "run.json"
    listed = json.loads(record.read_text()).get("solved", {}) if record.is_file() else {}
    return at in listed.get(asset, [])


def _ramp_or_weighting(kwargs, cv, wf):
    """One solve into the folder of the run: the bias ramp, or the weighting field."""
    from raser.core.field import solver_section

    solver_section.main(
        {
            **kwargs,
            "target": kwargs["det_name"],
            "bias": _bias(kwargs),
            "cv": cv,
            "wf": wf,
            "solver": _solver(kwargs),
            "_field_directory": kwargs["_run_path"],
        }
    )


def _capacitance(kwargs):
    """The capacitance at one bias the field was saved at, the bias of the
    field itself when none is given, into the folder of that field as
    <bias>V.cv.json: the specific capacitance of the mesh, and beside it the
    area factor of the device that makes it the capacitance of the device."""
    # devsim stays out of the command line until a solve needs it.
    from raser.core.field import saved_point

    from raser.core.field.save_milestone import save_solved

    my_d = Detector(kwargs["det_name"], kwargs["_files"]["device"])
    voltage = _bias(kwargs) if kwargs["cv"] is True else float(kwargs["cv"])
    folder = Path(kwargs["_run_path"])
    value, frequency = saved_point.capacitance(my_d, folder, voltage, _solver(kwargs))
    point = {
        "voltage_V": voltage,
        "specific_capacitance_pF": value,
        "per": {1: "cm^2", 2: "cm", 3: "device"}[my_d.dimension],
        "area_factor": float(my_d.device_dict.get("area_factor", 1.0)),
        "frequency_Hz": frequency,
    }
    (folder / f"{voltage}V.cv.json").write_text(json.dumps(point, indent=2))
    save_solved(str(folder), "capacitance", voltage)
    print(point)


def _import(kwargs):
    """The TCAD solution in the file of -ext, into the folder of the run as
    the field at the bias of that file."""
    from raser.core.field import tcad

    my_d = Detector(kwargs["det_name"], kwargs["_files"]["device"])
    bias = tcad.import_field(
        kwargs["input"], my_d, kwargs["_run_path"], kwargs["bias"], kwargs["flip"]
    )
    print(f"{kwargs['_run_path']}: the field of {kwargs['input']} at {bias} V")


def _empty_devsim():
    """devsim holds one device: emptied for the next part, with the linear
    solver it chose when it was loaded, which emptying forgets. With MKL that
    is the parameter direct_solver alone; with UMFPACK also solver_callback."""
    import devsim

    kept = {
        name: devsim.get_parameter(name=name)
        for name in ("direct_solver", "solver_callback")
        if name in devsim.get_parameter_list()
    }
    devsim.reset_devsim()
    for name, value in kept.items():
        devsim.set_parameter(name=name, value=value)


def solve(kwargs):
    """The parts that are named, in this order: -iv the field up to its bias
    with its IV, -cv the capacitance at one bias the field was saved at, -wf
    the weighting field of the read-out electrodes. With none named, the field
    with its IV and its CV along the ramp, then the weighting field. A part
    that run.json lists as solved is left as it is. With -ext nothing is
    solved: the field is taken from a TCAD file.

    --mode says how the field is found: "full" solves the electric field
    and the weighting field on the mesh of the device; "semi_fast" takes the
    electric field of a planar device and solves the weighting field of the
    fully depleted device; "fast" takes both from closed forms."""
    if kwargs["mode"] == "fast" and not HAS_DEVSIM:
        print(f"devsim is not installed: the field of {kwargs['det_name']} is found in the fast mode, not the full one")
    if kwargs["mode"] != "full":
        raise NotImplementedError(
            f"the {kwargs['mode']} mode of a field is not there yet: only `--mode full` is"
        )
    if kwargs["input"] is not None:
        return _import(kwargs)
    # Temporary: the HEMT solver is outside this command for now and is only
    # passed through here; this goes when it is taken into the field solve.
    physics = kwargs["_files"]["device"].get("hemt_physics", {})
    if physics.get("transport_model") == "drift_diffusion_v1":
        dropped = [
            option
            for option, asked in (
                ("-cv", kwargs["cv"] is not None),
                ("-wf", kwargs["wf"]),
                ("-noise", kwargs["noise"]),
            )
            if asked
        ]
        print(
            f"{kwargs['det_name']} is solved by its own transport solver: only its"
            " DC sweep is run, without CV, weighting field or noise"
            + (f"; {' '.join(dropped)} dropped" if dropped else "")
        )
        return _ramp_or_weighting({**kwargs, "noise": False}, cv=False, wf=False)
    if kwargs["umf"]:
        # Loading it makes UMFPACK the linear solver of devsim in this process,
        # where devsim would have taken MKL; without MKL devsim loads it itself.
        import devsim.umfpack.umfshim  # noqa: F401
    named = [
        part
        for part, asked in (
            ("iv", kwargs["iv"]),
            ("cv", kwargs["cv"] is not None),
            ("wf", kwargs["wf"]),
        )
        if asked
    ]
    cv_at = _bias(kwargs) if kwargs["cv"] is True else kwargs["cv"]
    have = {
        "iv": _solved(kwargs, "potential", _bias(kwargs)),
        "cv": _solved(kwargs, "capacitance", cv_at),
        "wf": _solved(kwargs, "weighting", _bias(kwargs)),
    }
    left = [part for part in named or ["iv", "wf"] if not have[part]]
    for done, part in enumerate(left):
        if done:
            _empty_devsim()
        if part == "cv":
            _capacitance(kwargs)
        else:
            _ramp_or_weighting(kwargs, cv=not named, wf=part == "wf")
    if not left:
        print(f"{kwargs['_run_path']}: already solved")
    return None


def outdated(old, record):
    """What makes the field of an earlier solve out of date, or None: another
    flux, other settings in the device file, or a change in what the solve
    read from the device."""
    if old["options"] != record["options"]:
        return "another irradiation flux or another mode"
    device, before = record["files"]["device"], old["files"]["device"]
    if device.get("field") != before.get("field"):
        return 'other settings under "field" in the device file'
    if "read" not in old:
        return None  # nothing was solved yet
    differing = changed(old["read"], Detector(device["det_name"], device))
    return "the device has another " + ", ".join(differing) if differing else None


def job_command(kwargs):
    """The options of a field command that its run does not record."""
    words = [f"-{part}" for part in ("iv", "wf", "noise", "umf", "flip") if kwargs[part]]
    if kwargs["input"] is not None:
        words.append(f"-ext={os.path.abspath(kwargs['input'])}")
    if kwargs["cv"] is not None:
        words.append("-cv" if kwargs["cv"] is True else f"-cv={kwargs['cv']}")
    if kwargs["bias"] is not None:
        words.append(f"-bias={kwargs['bias']}")
    return words


WORKFLOW = Workflow(
    name="field",
    job=solve,
    command=job_command,
    keys=("irradiation_flux", "mode"),
    defaults={"irradiation_flux": None, "mode": DEFAULT_MODE},
    seeds=False,
    outdated=outdated,
)


def run(kwargs):
    """raser field <device>: its field; raser field <experiment folder>: the
    fields the points of that experiment need, as its own command would
    solve them before its jobs start."""
    folder = Path(kwargs["det_name"]).expanduser()
    if not (folder / "config.json").is_file():
        return execute(WORKFLOW, kwargs)
    config = json.loads((folder / "config.json").read_text())
    words = config["workflow"].split()
    if words == WORKFLOW.words:
        raise SystemExit(f"{folder}: this is the field itself; give its device, raser field {config['device']}")
    experiment = WORKFLOWS[config["workflow"]]
    folder = folder.resolve()
    with project_root_context(folder.parents[len(words) - 1], kwargs["_components_of"][words[0]]):
        make_shared(experiment, {**kwargs, "det_name": config.get("device"), "scan": []}, folder)
    return None


def _flux_of_run(my_d, options):
    """The flux of the field a run of the chain takes: its option, else that of the device."""
    if options.get("irradiation") is not None:
        return float(options["irradiation"])
    return float(my_d.irradiation_flux)


def ready(options, files):
    """The folder of the field a point of the chain takes, or None when
    `raser field` has to solve it: there is none at its flux and mode, it
    was solved for another device or under other "field" settings, or not
    at the bias of the point."""
    device = files["device"]
    my_d = Detector(device["det_name"], device)
    try:
        folder = solved_field(my_d, my_d.voltage, _flux_of_run(my_d, options))
    except (FileNotFoundError, ValueError):
        return None
    old = json.loads((folder / "run.json").read_text())
    if outdated(old, {"options": old["options"], "files": {"device": device}}) is not None:
        return None
    return folder


def start(kwargs, options, files):
    """`raser field <device> -bias <bias of the point>` for a field that is
    not ready, at the flux of the point in a folder of its own when that is
    not the device's; as jobs on the cluster when the command has -b."""
    device = files["device"]
    my_d = Detector(device["det_name"], device)
    words = ["field", device["det_name"], "-bias", str(my_d.voltage)]
    flux = _flux_of_run(my_d, options)
    if flux != float(my_d.irradiation_flux):
        words += ["--scan", f"irradiation_flux={flux:g}"]
    # What the point changed in the device file, the field is solved for too,
    # in a folder of its own; the bias is -bias.
    for address in sorted(key for key in options if key.startswith("device.") and key != "device.bias.voltage"):
        value = json.dumps(options[address])
        if "," in value:
            raise ValueError(
                f"{address} = {value}: a value with a comma cannot be handed to `raser field --scan`; "
                f"solve the field of this device yourself, with the device file changed"
            )
        words += ["--scan", f"{address}={value}"]
    parser = argparse.ArgumentParser(prog="raser")
    register(parser.add_subparsers(dest="_command"))
    field_kwargs = vars(parser.parse_args(words))
    # jobs=1: each field is solved in a process of its own, as devsim holds
    # one device a process, and the command of the experiment never loads it.
    field_kwargs.update(
        batch=kwargs["batch"], mem=kwargs["mem"], jobs=1, _argv=words, _entry_command_prefix=("field",)
    )
    print("the field is not ready: " + " ".join(["raser", *words]))
    # The point is this experiment's, not one of the field's own scans.
    execute(WORKFLOW, field_kwargs, register=False)


SHARED = Shared(ready=ready, start=start)


def register(subparsers):
    parser = subparsers.add_parser(
        "field", aliases=["fld"], help="stage: the fields of a device, its weighting fields and IV/CV"
    )
    parser.add_argument("det_name", help="a device, or an experiment folder whose points' fields to solve")
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
    parser.add_argument(
        "--mode",
        choices=("full", "semi_fast", "fast"),
        help="how the field is found: solved in full, the planar field with a solved weighting field, or closed forms; "
        "full by default, fast where devsim is not installed",
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
