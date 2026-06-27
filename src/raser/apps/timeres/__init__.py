"""Time-resolution experiment application."""

from pathlib import Path

from raser.apps import signal
from raser.apps.timeres import summary
from raser.supports import jobs
from raser.supports import runs

DEFAULT_SOURCE = "decay/Sr90"
DEFAULT_FIELD = "default"
DEFAULT_EVENTS_PER_JOB = 10000


def _prepare(kwargs):
    runs.apply_run_config(kwargs)
    if kwargs.get("source") is None:
        kwargs["source"] = DEFAULT_SOURCE
    if kwargs.get("field") is None:
        kwargs["field"] = DEFAULT_FIELD
    if kwargs.get("events_per_job") is None:
        kwargs["events_per_job"] = DEFAULT_EVENTS_PER_JOB
    kwargs["experiment"] = "time_resolution"
    kwargs["workflow"] = "timeres"
    kwargs["signal_output_label"] = "timeres"
    kwargs["signal_source"] = Path(str(kwargs["source"])).stem


def _run_root(kwargs):
    run_id = kwargs.get("run")
    source = kwargs.get("source")
    voltage = kwargs.get("voltage")
    field = kwargs.get("field")
    if run_id == "latest":
        return runs.latest_run_path("timeres", source=source, voltage=voltage, field=field)
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
    if kwargs.get("collect"):
        collect(kwargs)
        return
    if _run_jobs(kwargs):
        collect(kwargs)


def collect(kwargs):
    _prepare(kwargs)
    if kwargs.get("run") is None:
        kwargs["run"] = "latest"
    run_root = _run_root(kwargs)
    summary.collect(run_root)


run_signal = run
