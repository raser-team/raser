#!/usr/bin/env python3
"""RASER command-line entry point."""

import argparse
import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from raser.supports.paths import app_component_root
from raser.supports.paths import infer_project_root
from raser.supports.paths import work_root
from raser.supports.paths import project_root_context


VERSION = 4.1

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
for python_root in (REPO_ROOT / "src", REPO_ROOT):
    python_root_text = str(python_root)
    if python_root_text not in sys.path:
        sys.path.insert(0, python_root_text)

PROJECT_ARGUMENTS = {
    "cce": "det_name",
    "field": "label",
    "metrics": "det_name",
    "tct": "det_name",
    "timeres": "det_name",
}

APP_WORKSPACE_PROJECTS = {"bmos", "lumi", "telescope"}


def _discover_submodules():
    modules = {}
    for package_name in ("core", "apps", "cli"):
        package_dir = PACKAGE_ROOT / package_name
        if not package_dir.is_dir():
            continue
        for path in package_dir.iterdir():
            if path.name.startswith("_"):
                continue
            if path.is_dir() and (path / "__init__.py").exists():
                modules[path.name] = f".{package_name}.{path.name}"
            elif path.suffix == ".py" and path.stem not in {"__init__", "raser"}:
                modules[path.stem] = f".{package_name}.{path.stem}"
    return modules


def _submodule_path(name):
    modules = _discover_submodules()
    try:
        return modules[name]
    except KeyError as exc:
        raise KeyError(f"Unknown RASER submodule: {name}") from exc


def _import_submodule(name):
    return importlib.import_module(_submodule_path(name), package="raser")


@contextmanager
def _submodule_components(name):
    module_path = _submodule_path(name)
    if not module_path.startswith(".apps."):
        yield
        return

    previous = os.environ.get("RASER_COMPONENT_PATH")
    app_roots = [app_component_root(name)]
    if name in {"cce", "timeres"}:
        app_roots.append(app_component_root("signal"))
    app_root = os.pathsep.join(str(path) for path in app_roots)
    os.environ["RASER_COMPONENT_PATH"] = (
        app_root if not previous else app_root + os.pathsep + previous
    )
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("RASER_COMPONENT_PATH", None)
        else:
            os.environ["RASER_COMPONENT_PATH"] = previous


def _release_g4ppyy_globals():
    g4ppyy = sys.modules.get("g4ppyy")
    if g4ppyy is None:
        return
    managers = getattr(g4ppyy, "_managers", None)
    if managers is None:
        return
    # Geant4 visualization keeps pointers into the run manager; release it first.
    for name in ("VisExecutive", "RunManager"):
        obj = getattr(managers, name, None)
        if hasattr(obj, "__destruct__"):
            obj.__destruct__()
            setattr(managers, name, None)


@contextmanager
def _submodule_project(name, kwargs):
    argument = PROJECT_ARGUMENTS.get(name)
    if argument is not None:
        with project_root_context(infer_project_root(kwargs.get(argument))):
            yield
        return
    if name in APP_WORKSPACE_PROJECTS:
        with project_root_context(work_root()):
            yield
        return
    else:
        yield
        return


def _add_detector_source_options(parser, default_source):
    parser.add_argument("det_name", help="name of the detector")
    parser.add_argument(
        "source",
        nargs="?",
        default=default_source,
        help="signal source or beam configuration",
    )
    parser.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=str, help="irradiation flux")
    parser.add_argument(
        "-g4_vis", help="visualization of Geant4 experiment", action="store_true"
    )
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser.add_argument("-s", "--scan", type=int, help="instance number for scan mode")
    parser.add_argument(
        "-b",
        "--batch",
        action="store_true",
        help="submit signal scan jobs to cluster (used with -s)",
        dest="signal_batch",
    )
    parser.add_argument("--job", type=int, help="flag of run in job")
    parser.add_argument(
        "-mem", type=int, help="memory limit of the job in 8GB", default=1
    )


def build_parser():
    parser = argparse.ArgumentParser(prog="raser")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "-b",
        "--batch",
        help="submit BATCH job to cluster",
        action="count",
        default=0,
        dest="global_batch",
    )
    parser.add_argument("-t", "--test", help="TEST", action="store_true")

    subparsers = parser.add_subparsers(help="sub-command help", dest="subparser_name")

    parser_afe = subparsers.add_parser("afe", help="Analog Front End readout")
    parser_afe.add_argument("label", help="LABEL to identify electronics operations")
    parser_afe.add_argument("name", help="LABEL to identify electronics files")
    parser_afe.add_argument(
        "-source", help="source current file for recreate_batch_signals"
    )
    parser_afe.add_argument("-job_file", help="job file for recreate_batch_signals")
    parser_afe.add_argument(
        "-tct", help="reprocess TCT signal for recreate_batch_signals"
    )

    parser_bmos = subparsers.add_parser("bmos", help="Beam Monitor Online System")
    parser_bmos.add_argument("sensor", help="sensor or BMOS detector config")
    parser_bmos.add_argument("label", help="LABEL to identify BMOS simulations")
    parser_bmos.add_argument("bmos_extra_args", nargs="*")
    parser_bmos.add_argument(
        "-v", "--verbose", help="VERBOSE level", action="count", default=0
    )

    parser_current = subparsers.add_parser("current", help="calculate drift current")
    parser_current.add_argument("label", help="LABEL to identify root files")

    parser_cce = subparsers.add_parser("cce", help="charge-collection experiment")
    _add_detector_source_options(parser_cce, "radioactive/Am241")

    parser_dfe = subparsers.add_parser("dfe", help="Digital Front End design")
    parser_dfe.add_argument("label", help="LABEL to identify Digital Front End design")

    parser_field = subparsers.add_parser(
        "field", help="calculate field/weight field and iv/cv"
    )
    parser_field.add_argument("label", help="LABEL to identify operation")
    parser_field.add_argument(
        "-v", "--verbose", help="VERBOSE level", action="count", default=0
    )
    parser_field.add_argument("-cv", help="CV simulation", action="store_true")
    parser_field.add_argument("-wf", help="WeightField Simulation", action="store_true")
    parser_field.add_argument(
        "-irr", "--irradiation_flux", help="irradiationm flux", type=float
    )
    parser_field.add_argument("-bias", help="bias voltage", type=float)
    parser_field.add_argument(
        "-v_current", help="Current voltage for step-by-step simulation", type=float
    )
    parser_field.add_argument(
        "-noise", help="Detector Noise simulation", action="store_true"
    )
    parser_field.add_argument("-umf", help="use umf solver", action="store_true")
    parser_field.add_argument(
        "-ext", "--extract", help="extract field from TCAD file", action="store_true"
    )
    parser_field.add_argument(
        "-flip", help="flip the direction of the electric field", action="store_true"
    )
    parser_field.add_argument(
        "-wf_sub", help="calculate weight field from two devsim file", nargs=2
    )

    parser_interaction = subparsers.add_parser(
        "interaction", help="particle-matter interation module"
    )
    parser_interaction.add_argument(
        "label", help="LABEL to identify particle-matter interation"
    )
    parser_interaction.add_argument(
        "-v", "--verbose", help="VERBOSE level", action="count", default=0
    )

    parser_lumi = subparsers.add_parser("lumi", help="CEPC Fast Luminosity Monitor")
    parser_lumi.add_argument("label", help="LABEL to identify CFLM simulations")
    parser_lumi.add_argument(
        "-v", "--verbose", help="VERBOSE level", action="count", default=0
    )

    parser_mcu = subparsers.add_parser("mcu", help="Micro Control Unit design")
    parser_mcu.add_argument("label", help="LABEL to identify Micro Control Unit design")

    parser_project = subparsers.add_parser("project", help="manage work projects")
    project_subparsers = parser_project.add_subparsers(
        dest="project_action", required=True
    )
    parser_project_create = project_subparsers.add_parser(
        "create", help="create a work project"
    )
    parser_project_create.add_argument("project_name", help="project directory name")
    parser_project_create.add_argument(
        "--template",
        choices=["bmos", "cce", "lumi", "signal", "tct", "telescope", "timeres"],
        help="copy app component assets into the project",
    )

    parser_metrics = subparsers.add_parser(
        "metrics", help="waveform and signal-derived metrics"
    )
    parser_metrics.add_argument("det_name", help="name of the detector")
    parser_metrics.add_argument("-tct", type=str, help="specify TCT signal class")
    parser_metrics.add_argument("-daq", type=str, help="specify DAQ system")
    parser_metrics.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    parser_metrics.add_argument(
        "-irr", "--irradiation", type=str, help="irradiation flux"
    )
    parser_metrics.add_argument(
        "-g4", "--g4experiment", type=str, help="model of Geant4 experiment"
    )
    parser_metrics.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser_metrics.add_argument(
        "-source",
        help="signal batch source in the form cce/Am241 or timeres/Sr90",
    )

    parser_timeres = subparsers.add_parser("timeres", help="time-resolution experiment")
    parser_timeres.add_argument(
        "--mode",
        choices=["signal", "metrics"],
        default="signal",
        help="experiment step to run",
    )
    _add_detector_source_options(parser_timeres, "radioactive/Sr90")

    parser_tct = subparsers.add_parser("tct", help="TCT simulation")
    parser_tct.add_argument("label", help="LABEL to identify TCT options")
    parser_tct.add_argument("det_name", help="name of the detector")
    parser_tct.add_argument("laser", help="name of the laser")
    parser_tct.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    parser_tct.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser_tct.add_argument(
        "-s", "--scan", type=int, help="instance number for scan mode"
    )
    parser_tct.add_argument("--job", type=int, help="flag of run in job")

    parser_telescope = subparsers.add_parser("telescope", help="telescope")
    parser_telescope.add_argument("label", help="LABEL to identify telescope files")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.subparser_name is None:
        parser.print_help()
        return 1

    kwargs = vars(args)
    submodule_name = kwargs["subparser_name"]
    if submodule_name == "timeres":
        kwargs["label"] = kwargs["mode"]

    try:
        if kwargs["global_batch"] != 0 and not kwargs.get("signal_batch", False):
            batch_level = kwargs["global_batch"]
            from raser.supports import batchjob

            destination = submodule_name
            command = " ".join(sys.argv[1:] if argv is None else argv)
            command = command.replace("--batch ", "")
            command = command.replace("-b ", "")
            batchjob.main(destination, command, batch_level, kwargs["test"])
        else:
            with _submodule_project(submodule_name, kwargs):
                with _submodule_components(submodule_name):
                    submodule = _import_submodule(submodule_name)
                    submodule.main(kwargs)
    finally:
        _release_g4ppyy_globals()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
