"""
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
"""

from raser.supports import jobs
from raser.supports import runs

from .workflow import load_defaults


def register(subparsers):
    parser = subparsers.add_parser("tct", help="TCT simulation")
    modes = parser.add_subparsers(dest="tct_mode", required=True)
    parser.set_defaults(_project="det_name")

    signal = modes.add_parser("signal", help="TCT signal")
    signal.add_argument("det_name", help="name of the detector")
    signal.add_argument("laser", help="name of the laser")
    signal.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    signal.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    signal.add_argument("-s", "--jobs", type=int, help="number of jobs")
    signal.add_argument("-b", "--batch", action="store_true", dest="signal_batch")
    signal.add_argument("-mem", type=int, default=1)
    signal.add_argument("--job-index", type=int, help="index of this job")
    signal.add_argument("--run", help="run id")
    signal.add_argument("--seed", type=int, default=0)
    signal.add_argument("--dry-run", action="store_true")
    signal.set_defaults(_run=run_signal)

    position_signal = modes.add_parser("position_signal", help="TCT position signal")
    position_signal.add_argument("det_name", help="name of the detector")
    position_signal.add_argument("laser", help="name of the laser")
    position_signal.add_argument("-vol", "--voltage", type=str, help="bias voltage")
    position_signal.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    position_signal.add_argument("-s", "--jobs", type=int, help="number of jobs")
    position_signal.add_argument(
        "-b",
        "--batch",
        action="store_true",
        dest="signal_batch",
    )
    position_signal.add_argument("-mem", type=int, default=1)
    position_signal.add_argument("--job-index", type=int, help="index of this job")
    position_signal.add_argument("--run", help="run id")
    position_signal.add_argument("--seed", type=int, default=0)
    position_signal.add_argument("--dry-run", action="store_true")
    position_signal.set_defaults(_run=run_position_signal)

    position_scan_draw = modes.add_parser(
        "position_scan_draw", help="draw TCT position scan"
    )
    position_scan_draw.add_argument("det_name", help="name of the detector")
    position_scan_draw.add_argument("laser", help="name of the laser")
    position_scan_draw.set_defaults(_run=run_position_scan_draw)


def _apply_defaults(kwargs):
    config = load_defaults()
    kwargs["amplifier"] = kwargs.get("amplifier") or config.get("amplifier")
    if kwargs["amplifier"] is None:
        raise ValueError("TCT app config is missing required setting: amplifier")


def _run_scan(kwargs):
    prefix = list(kwargs["_entry_command_prefix"])
    tail = jobs.command_tail(
        kwargs["_argv"],
        prefix,
        {"-s", "--jobs", "--job-index", "--run"},
    )
    tail.extend(["--run", runs.ensure_run_id(kwargs)])
    return jobs.run_indexed_jobs(
        prefix,
        tail,
        kwargs["jobs"],
        use_cluster=kwargs["signal_batch"],
        mem=kwargs["mem"],
        destination="tct",
    )


def run_signal(kwargs):
    from .workflow import build_plan

    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        plan.show()
        return plan
    from raser.apps._planning import activate_plan

    activate_plan(plan, kwargs)
    _apply_defaults(kwargs)
    if kwargs["job_index"] is not None:
        from . import tct_signal_scan

        tct_signal_scan.job_main(kwargs)
    elif kwargs["jobs"] is not None:
        _run_scan(kwargs)
    else:
        from . import tct_signal

        tct_signal.main(kwargs)


def run_position_signal(kwargs):
    from .workflow import build_plan

    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        plan.show()
        return plan
    from raser.apps._planning import activate_plan

    activate_plan(plan, kwargs)
    _apply_defaults(kwargs)
    from . import tct_signal_position_scan

    if kwargs["job_index"] is not None:
        tct_signal_position_scan.job_main(kwargs)
    elif kwargs["jobs"] is not None:
        _run_scan(kwargs)
    else:
        kwargs["job_index"] = 0
        tct_signal_position_scan.job_main(kwargs)


def run_position_scan_draw(kwargs):
    from . import tct_signal_position_scan_draw

    tct_signal_position_scan_draw.main(kwargs)
