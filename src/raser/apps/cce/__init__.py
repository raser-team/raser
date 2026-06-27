"""Charge-collection experiment application."""

from raser.apps import signal
from raser.apps.cce import summary
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
    kwargs["experiment"] = "charge_collection"
    kwargs["workflow"] = "cce"
    kwargs["signal_output_label"] = "cce"
    kwargs["signal_source"] = runs.source_name(kwargs["source"])


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
        destination="cce",
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
    summary.collect(kwargs)


main = run
