"""Time-resolution experiment application."""

from pathlib import Path

from raser.apps import signal
from raser.apps._planning import activate_plan
from raser.supports import jobs
from raser.supports import runs

from .workflow import build_plan
from .workflow import load_defaults

DEFAULT_EVENTS_PER_JOB = 10000


def _prepare(kwargs):
    runs.apply_run_config(kwargs)
    if kwargs.get("source") is None:
        kwargs["source"] = load_defaults()["source"]
    if kwargs.get("events_per_job") is None:
        kwargs["events_per_job"] = DEFAULT_EVENTS_PER_JOB
    kwargs["workflow"] = "timeres"
    kwargs["signal_output_label"] = "timeres"
    kwargs["signal_source"] = Path(str(kwargs["source"])).stem


def _run_root(kwargs):
    run_id = kwargs.get("run")
    if run_id == "latest":
        return runs.latest_run_path("timeres", specification=build_plan(kwargs).as_dict())
    path = Path(str(run_id))
    if path.is_absolute() or len(path.parts) > 1:
        return path
    return runs.run_path("timeres", str(run_id))


def _job_tail(kwargs):
    tail = jobs.command_tail(
        kwargs["_argv"],
        kwargs["_entry_command_prefix"],
        {"-s", "--scan", "--job", "--run", "--events-per-job"},
    )
    tail.extend(["--run", runs.ensure_run_id(kwargs)])
    tail.extend(["--events-per-job", str(kwargs["events_per_job"])])
    return tail


def _run_jobs(kwargs):
    if kwargs.get("job") is not None:
        from .g4_interaction import TimeresActionInitialization

        kwargs["_g4_action_initialization"] = TimeresActionInitialization
        signal.run_signal(kwargs)
        return False

    count = 1
    if kwargs.get("signal_batch"):
        count = kwargs["scan"] or 1
    elif kwargs.get("scan") is not None:
        kwargs["events_per_job"] = kwargs["scan"]

    jobs.run_indexed_jobs(
        kwargs["_entry_command_prefix"],
        _job_tail(kwargs),
        count,
        use_cluster=kwargs["signal_batch"],
        mem=kwargs["mem"],
        destination="timeres",
    )
    return not kwargs["signal_batch"]


def run(kwargs):
    _prepare(kwargs)
    if kwargs.get("collect") and not kwargs.get("dry_run"):
        collect(kwargs)
        return
    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        plan.show()
        return plan
    activate_plan(plan, kwargs)
    if _run_jobs(kwargs):
        collect(kwargs)


def collect(kwargs):
    from raser.apps.timeres import summary

    _prepare(kwargs)
    if kwargs.get("run") is None:
        kwargs["run"] = "latest"
    run_root = _run_root(kwargs)
    summary.collect(run_root)


run_signal = run
