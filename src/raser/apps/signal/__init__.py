"""
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
"""

from raser.supports import jobs
from raser.supports import runs


def add_arguments(parser, default_source):
    parser.add_argument("det_name", help="Device project")
    parser.add_argument(
        "source",
        nargs="?",
        default=default_source,
        help="signal source or beam configuration",
    )
    parser.add_argument("--config", help="run configuration")
    parser.add_argument("--run", help="run id")
    parser.add_argument("-evt", "--events-per-job", type=int, help="events per job")
    parser.add_argument("-vol", "--voltage", type=float, help="bias voltage")
    parser.add_argument("-irr", "--irradiation", type=float, help="irradiation flux")
    parser.add_argument(
        "-g4_vis", help="visualization of Geant4 experiment", action="store_true"
    )
    parser.add_argument("--g4-vis-driver", help="Geant4 visualization driver")
    parser.add_argument("-amp", "--amplifier", type=str, help="amplifier")
    parser.add_argument("-s", "--jobs", type=int, help="number of jobs")
    parser.add_argument(
        "-b",
        "--batch",
        action="store_true",
        help="submit the jobs to the cluster",
        dest="signal_batch",
    )
    parser.add_argument("--job-index", type=int, help="index of this job")
    parser.add_argument(
        "-mem", type=int, help="memory limit of the job in 8GB", default=1
    )
    parser.add_argument("--seed", type=int, default=0, help="run random seed")
    parser.add_argument("--adc", help="ADC component")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve and display the workflow plan",
    )


def register(subparsers):
    parser = subparsers.add_parser("signal", help="single signal simulation")
    add_arguments(parser, "decay/Sr90")
    parser.set_defaults(_run=run_signal, _project="det_name", _components=("signal",))


def _command_tail(kwargs):
    command_prefix = list(kwargs["_entry_command_prefix"])
    return jobs.command_tail(
        kwargs["_argv"],
        command_prefix,
        {"-s", "--jobs", "--job-index", "--run"},
    )


def _run_scan(kwargs):
    scan_number = kwargs["jobs"]
    mem = kwargs["mem"]
    use_cluster = kwargs["signal_batch"]
    command_prefix = list(kwargs["_entry_command_prefix"])
    command_tail_list = _command_tail(kwargs)
    run_id = runs.ensure_run_id(kwargs)
    command_tail_list.extend(["--run", run_id])
    jobs.run_indexed_jobs(
        command_prefix,
        command_tail_list,
        scan_number,
        use_cluster=use_cluster,
        mem=mem,
        destination=command_prefix[0],
    )


def _run_signal_samples(kwargs):
    sample_count = kwargs["jobs"]
    kwargs["events_per_job"] = sample_count
    kwargs["job_index"] = 0
    kwargs["jobs"] = None
    kwargs["_signal_plot_samples"] = sample_count
    from . import gen_signal_scan

    gen_signal_scan.main(kwargs)


def run_signal(kwargs):
    runs.apply_run_config(kwargs)
    from .workflow import build_plan

    plan = kwargs.get("_workflow_plan") or build_plan(
        kwargs,
        workflow=kwargs.get("workflow") or "signal",
    )
    if kwargs.get("dry_run"):
        plan.show()
        return plan
    from raser.apps._planning import activate_plan

    if kwargs.get("_run_path") is None:
        activate_plan(plan, kwargs)
    if kwargs["jobs"] is not None:
        if kwargs.get("_command") == "signal" and not kwargs["signal_batch"]:
            _run_signal_samples(kwargs)
        else:
            _run_scan(kwargs)
    elif kwargs["job_index"] is not None:
        from . import gen_signal_scan

        gen_signal_scan.main(kwargs)
    else:
        from . import gen_signal_main

        gen_signal_main.main(kwargs)
