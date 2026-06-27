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
from raser.supports.paths import project_root_context
from raser.supports.paths import work_root


VERSION = 4.1

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
for python_root in (REPO_ROOT / "src", REPO_ROOT):
    python_root_text = str(python_root)
    if python_root_text not in sys.path:
        sys.path.insert(0, python_root_text)


PROJECT_ARGUMENTS = {
    "cce": "det_name",
    "field": "target",
    "metrics": "det_name",
    "signal": "det_name",
    "tct": "det_name",
    "timeres": "det_name",
}

WORK_ROOT_COMMANDS = {"bmos", "lumi", "telescope"}
APP_COMPONENT_ROOTS = {
    "cce": ("cce", "signal"),
    "timeres": ("timeres", "signal"),
}


@contextmanager
def _component_context(command, group):
    if group != "app":
        yield
        return

    previous = os.environ.get("RASER_COMPONENT_PATH")
    app_names = APP_COMPONENT_ROOTS.get(command, (command,))
    app_root = os.pathsep.join(str(app_component_root(app)) for app in app_names)
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


@contextmanager
def _project_context(command, kwargs):
    argument = PROJECT_ARGUMENTS.get(command)
    if argument is not None:
        with project_root_context(infer_project_root(kwargs.get(argument))):
            yield
        return
    if command in WORK_ROOT_COMMANDS:
        with project_root_context(work_root()):
            yield
        return
    yield


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


def _add_verbose(parser):
    parser.add_argument("-v", "--verbose", help="VERBOSE level", action="count", default=0)


def _add_detector_source(parser, default_source):
    parser.add_argument("det_name", help="name of the detector")
    parser.add_argument(
        "source",
        nargs="?",
        default=default_source,
        help="signal source or beam configuration",
    )
    parser.add_argument("--config", help="run configuration")
    parser.add_argument("--field", help="field asset name")
    parser.add_argument("--run", help="run id")
    parser.add_argument("--collect", help="collect finished batch jobs", action="store_true")
    parser.add_argument("--events-per-job", type=int, help="events per batch job")
    parser.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=str, help="irradiation flux")
    parser.add_argument("-g4_vis", help="visualization of Geant4 experiment", action="store_true")
    parser.add_argument("--g4-vis-driver", help="Geant4 visualization driver")
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
    parser.add_argument("-mem", type=int, help="memory limit of the job in 8GB", default=1)


def _add_field(parser):
    parser.add_argument("target", help="sensor or field target")
    _add_verbose(parser)
    parser.add_argument("-cv", help="CV simulation", action="store_true")
    parser.add_argument("-wf", help="WeightField Simulation", action="store_true")
    parser.add_argument("-irr", "--irradiation_flux", help="irradiationm flux", type=float)
    parser.add_argument("-bias", help="bias voltage", type=float)
    parser.add_argument("-v_current", help="Current voltage for step-by-step simulation", type=float)
    parser.add_argument("-noise", help="Detector Noise simulation", action="store_true")
    parser.add_argument("-umf", help="use umf solver", action="store_true")
    parser.add_argument("-ext", "--extract", help="extract field from TCAD file", action="store_true")
    parser.add_argument("-flip", help="flip the direction of the electric field", action="store_true")
    parser.add_argument("-wf_sub", help="calculate weight field from two devsim file", nargs=2)


def _add_field_artifacts(subparsers):
    parser = subparsers.add_parser("field", help="field artifacts")
    actions = parser.add_subparsers(dest="field_action", required=True)

    solve = actions.add_parser("solve", help="solve electric or weighting field")
    solve.add_argument("target", help="sensor or field target")
    _add_verbose(solve)
    solve.add_argument("-cv", help="CV simulation", action="store_true")
    solve.add_argument("-wf", help="WeightField Simulation", action="store_true")
    solve.add_argument("-irr", "--irradiation_flux", help="irradiationm flux", type=float)
    solve.add_argument("-bias", help="bias voltage", type=float)
    solve.add_argument("-v_current", help="Current voltage for step-by-step simulation", type=float)
    solve.add_argument("-noise", help="Detector Noise simulation", action="store_true")
    solve.add_argument("-umf", help="use umf solver", action="store_true")
    solve.set_defaults(extract=False, flip=False, wf_sub=None)
    _entry(solve, ".apps.field", "solve", command="field", group="app", prefix=("field", "solve"))

    import_field = actions.add_parser("import", help="import a TCAD field file")
    import_field.add_argument("target", help="TCAD .tdr field file")
    import_field.add_argument("-flip", help="flip the direction of the electric field", action="store_true")
    import_field.set_defaults(
        verbose=0,
        umf=False,
        extract=True,
        wf_sub=None,
        cv=False,
        wf=False,
        irradiation_flux=None,
        bias=None,
        v_current=None,
        noise=False,
    )
    _entry(
        import_field,
        ".apps.field",
        "import_field",
        command="field",
        group="app",
        prefix=("field", "import"),
    )

    weight = actions.add_parser("weight", help="derive weighting potential from two field files")
    weight.add_argument("voltage", help="bias voltage used for the source potential")
    weight.add_argument("electrode", help="readout electrode name")
    weight.add_argument("target", help="sensor or field target")
    weight.set_defaults(
        verbose=0,
        umf=False,
        extract=False,
        flip=False,
        cv=False,
        wf=False,
        irradiation_flux=None,
        bias=None,
        v_current=None,
        noise=False,
    )
    _entry(
        weight,
        ".apps.field",
        "weight",
        command="field",
        group="app",
        prefix=("field", "weight"),
        args=("voltage", "electrode", "target"),
    )


def _add_metrics(parser):
    parser.add_argument("det_name", help="name of the detector")
    parser.add_argument("-tct", type=str, help="specify TCT signal class")
    parser.add_argument("-daq", type=str, help="specify DAQ system")
    parser.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=str, help="irradiation flux")
    parser.add_argument("-g4", "--g4experiment", type=str, help="model of Geant4 experiment")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser.add_argument("-source", help="signal batch source in the form cce/Am241 or timeres/Sr90")


def _entry(parser, module, function="main", *, command, group, args=None, prefix=None):
    parser.set_defaults(
        _entry_module=module,
        _entry_function=function,
        _entry_args=args,
        _entry_command_prefix=prefix or (command,),
        _command=command,
        _group=group,
    )


def _call_entry(kwargs):
    module = importlib.import_module(kwargs["_entry_module"], package="raser")
    function = getattr(module, kwargs["_entry_function"])
    entry_args = kwargs.get("_entry_args")
    if entry_args is None:
        return function(kwargs)
    return function(*(kwargs[name] for name in entry_args))


def _add_bmos(subparsers):
    parser = subparsers.add_parser("bmos", help="Beam Monitor Online System")
    parser.add_argument("sensor", help="sensor or BMOS detector config")
    actions = parser.add_subparsers(dest="bmos_action", required=True)

    get_signal = actions.add_parser("GetSignal", help="generate BMOS signal")
    _entry(get_signal, ".apps.bmos.get_signal", "get_signal", command="bmos", group="app", args=("sensor",))

    histogram_signal = actions.add_parser("histogram_signal", help="generate BMOS histogram signal")
    _entry(histogram_signal, ".apps.bmos.histogram_signal", "get_signal", command="bmos", group="app", args=())

    one_histogram = actions.add_parser("one_histogram", help="draw one BMOS histogram")
    _entry(one_histogram, ".apps.bmos.histogram", "main", command="bmos", group="app", args=("_histogram_one",))
    one_histogram.set_defaults(_histogram_one="one")

    all_histogram = actions.add_parser("all_histogram", help="draw all BMOS histograms")
    _entry(all_histogram, ".apps.bmos.histogram", "main", command="bmos", group="app", args=("_histogram_all",))
    all_histogram.set_defaults(_histogram_all="all")


def _add_lumi(subparsers):
    parser = subparsers.add_parser("lumi", help="CEPC Fast Luminosity Monitor")
    tasks = parser.add_subparsers(dest="lumi_task", required=True)
    entries = {
        "pe_dis": (".apps.lumi.data_file", "main", ()),
        "spd_dis": (".apps.lumi.spd_dis", "main", ()),
        "spd_dis_plot": (".apps.lumi.spd_plot", "main", ()),
        "np_precision_plot": (".apps.lumi.np_precision_plot", "main", ()),
        "lumi_fit": (".apps.lumi.lumi_TSC_precision_fit", "main", ()),
        "Amp_dis": (".apps.lumi.amplitude_dis", "main", ()),
        "bunch_number": (".apps.lumi.bunch_number", "main", ()),
        "p1_sample": (".apps.lumi.p1_sample", "main", ()),
        "DAQ_sim": (".apps.lumi.DAQ_system_sim", "main", ()),
    }
    for task, (module, function, args) in entries.items():
        task_parser = tasks.add_parser(task)
        _entry(task_parser, module, function, command="lumi", group="app", args=args)

    current = tasks.add_parser("current")
    current.set_defaults(_lumi_output="test")
    _entry(current, ".apps.lumi.get_current_p1", "main", command="lumi", group="app", args=("_lumi_output_path",))

    pixel_current = tasks.add_parser("Pixel_current")
    pixel_current.set_defaults(_lumi_output="N0_3_4", _lumi_fig="340")
    _entry(
        pixel_current,
        ".apps.lumi.pixel_current_plot",
        "main",
        command="lumi",
        group="app",
        args=("_lumi_output_path", "_lumi_fig"),
    )


def _add_tct(subparsers):
    parser = subparsers.add_parser("tct", help="TCT simulation")
    modes = parser.add_subparsers(dest="tct_mode", required=True)

    signal = modes.add_parser("signal", help="TCT signal")
    signal.add_argument("det_name", help="name of the detector")
    signal.add_argument("laser", help="name of the laser")
    signal.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    signal.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    signal.add_argument("-s", "--scan", type=int, help="instance number for scan mode")
    signal.add_argument("--job", type=int, help="flag of run in job")
    _entry(signal, ".apps.tct", "run_signal", command="tct", group="app")

    position_signal = modes.add_parser("position_signal", help="TCT position signal")
    position_signal.add_argument("det_name", help="name of the detector")
    position_signal.add_argument("laser", help="name of the laser")
    position_signal.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    position_signal.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    position_signal.add_argument("-s", "--scan", type=int, help="instance number for scan mode")
    position_signal.add_argument("--job", type=int, help="flag of run in job")
    _entry(position_signal, ".apps.tct", "run_position_signal", command="tct", group="app")

    position_scan_draw = modes.add_parser("position_scan_draw", help="draw TCT position scan")
    position_scan_draw.add_argument("det_name", help="name of the detector")
    position_scan_draw.add_argument("laser", help="name of the laser")
    _entry(position_scan_draw, ".apps.tct.tct_signal_position_scan_draw", "main", command="tct", group="app")


def _add_telescope(subparsers):
    parser = subparsers.add_parser("telescope", help="telescope")
    setups = parser.add_subparsers(dest="telescope_setup", required=True)

    taichu_v1 = setups.add_parser("taichu_v1")
    _entry(taichu_v1, ".apps.telescope.telescope_signal", "main", command="telescope", group="app", args=())

    taichu_v2 = setups.add_parser("taichu_v2")
    taichu_v2.add_argument("variant", nargs="?", default="taichu_v2")
    _entry(taichu_v2, ".apps.telescope.telescope_signal", "taichu_v2", command="telescope", group="app", args=("variant",))

    acts_v1 = setups.add_parser("acts_v1")
    _entry(acts_v1, ".apps.telescope.telescope_acts", "main", command="telescope", group="app", args=())

    g4 = setups.add_parser("g4")
    _entry(g4, ".apps.telescope.telescope_g4", "main", command="telescope", group="app", args=())


def _add_public_parsers(subparsers):
    _add_bmos(subparsers)

    parser_cce = subparsers.add_parser("cce", help="charge-collection experiment")
    _add_detector_source(parser_cce, None)
    _entry(parser_cce, ".apps.cce", "run", command="cce", group="app")

    _add_field_artifacts(subparsers)

    _add_lumi(subparsers)

    parser_project = subparsers.add_parser("project", help="manage work projects")
    project_subparsers = parser_project.add_subparsers(dest="project_action", required=True)
    parser_project_create = project_subparsers.add_parser("create", help="create a work project")
    parser_project_create.add_argument("project_name", help="project directory name")
    parser_project_create.add_argument(
        "--template",
        choices=["bmos", "cce", "lumi", "signal", "tct", "telescope", "timeres"],
        help="copy app component assets into the project",
    )
    _entry(parser_project_create, ".cli.project", "main", command="project", group="cli")

    parser_signal = subparsers.add_parser("signal", help="single signal simulation")
    _add_detector_source(parser_signal, "decay/Sr90")
    _entry(parser_signal, ".apps.signal", "run_signal", command="signal", group="app")

    parser_timeres = subparsers.add_parser("timeres", help="time-resolution experiment")
    _add_detector_source(parser_timeres, None)
    _entry(parser_timeres, ".apps.timeres", "run", command="timeres", group="app")

    _add_tct(subparsers)
    _add_telescope(subparsers)


def _add_dev_parsers(subparsers):
    analog = subparsers.add_parser("analog", help="Analog electronics readout")
    analog_actions = analog.add_subparsers(dest="analog_action", required=True)

    trans = analog_actions.add_parser("trans")
    trans.add_argument("name", help="electronics file name")
    _entry(trans, ".core.analog", "trans", command="analog", group="dev", args=("name",))

    readout = analog_actions.add_parser("readout")
    readout.add_argument("name", help="electronics file name")
    _entry(readout, ".core.analog", "readout", command="analog", group="dev", args=("name",))

    batch_signal = analog_actions.add_parser("batch_signal")
    batch_signal.add_argument("name", help="electronics file name")
    batch_signal.add_argument("-source", help="source current file for recreate_batch_signals")
    batch_signal.add_argument("-job_file", help="job file for recreate_batch_signals")
    batch_signal.add_argument("-tct", help="reprocess TCT signal for recreate_batch_signals")
    _entry(batch_signal, ".core.analog", "batch_signal", command="analog", group="dev")

    control = subparsers.add_parser("control", help="Control logic design")
    control_actions = control.add_subparsers(dest="control_action", required=True)
    regincr_sim = control_actions.add_parser("regincr_sim")
    _entry(regincr_sim, ".core.control.regincr_sim", "main", command="control", group="dev", args=())

    current = subparsers.add_parser("current", help="calculate drift current")
    current_actions = current.add_subparsers(dest="current_action", required=True)
    model = current_actions.add_parser("model")
    _entry(model, ".core.current.model", "main", command="current", group="dev", args=())

    digital = subparsers.add_parser("digital", help="Digital electronics design")
    digital_actions = digital.add_subparsers(dest="digital_action", required=True)
    regincr = digital_actions.add_parser("regincr")
    _entry(regincr, ".core.digital.regincr", "main", command="digital", group="dev", args=())
    regincr2stage = digital_actions.add_parser("regincr2stage")
    _entry(regincr2stage, ".core.digital.regincr2stage", "main", command="digital", group="dev", args=())

    field = subparsers.add_parser("field", help="calculate field/weight field and iv/cv")
    _add_field(field)
    _entry(field, ".apps.field", "main", command="field", group="dev")

    interaction = subparsers.add_parser("interaction", help="particle-matter interaction module")
    interaction_actions = interaction.add_subparsers(dest="interaction_action", required=True)
    energy_deposit = interaction_actions.add_parser("energy_deposit")
    _entry(energy_deposit, ".core.interaction.g4_sic_energy_deposition", "main", command="interaction", group="dev", args=())

    metrics = subparsers.add_parser("metrics", help="waveform and signal-derived metrics")
    _add_metrics(metrics)
    _entry(metrics, ".core.metrics", "main", command="metrics", group="dev")


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
    _add_public_parsers(subparsers)

    parser_dev = subparsers.add_parser("dev", help="developer entry points for core modules")
    dev_subparsers = parser_dev.add_subparsers(help="core module help", dest="dev_command", required=True)
    _add_dev_parsers(dev_subparsers)

    return parser


def _prepare_entry_args(kwargs):
    if kwargs.get("_lumi_output"):
        from raser.supports.output import output

        kwargs["_lumi_output_path"] = output(
            str(PACKAGE_ROOT / "apps" / "lumi" / "__init__.py"),
            kwargs["_lumi_output"],
        )


def main(argv=None):
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.subparser_name is None:
        parser.print_help()
        return 1

    kwargs = vars(args)
    kwargs["_argv"] = argv
    command = kwargs["_command"]
    group = kwargs["_group"]
    _prepare_entry_args(kwargs)

    try:
        if kwargs["global_batch"] != 0 and not kwargs.get("signal_batch", False):
            batch_level = kwargs["global_batch"]
            from raser.supports import batchjob

            batch_args = [
                item
                for item in (sys.argv[1:] if argv is None else argv)
                if item not in ("-b", "--batch", "-t", "--test")
            ]
            shell_command = " ".join(batch_args)
            with _project_context(command, kwargs):
                batchjob.main(command, shell_command, batch_level, kwargs["test"])
        else:
            with _project_context(command, kwargs):
                with _component_context(command, group):
                    _call_entry(kwargs)
    finally:
        _release_g4ppyy_globals()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
