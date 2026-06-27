"""Time-resolution experiment application."""

from pathlib import Path

from raser.apps import signal
from raser.core import metrics
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


def run(kwargs):
    _prepare(kwargs)
    signal.run_signal(kwargs)


def analyze(kwargs):
    _prepare(kwargs)
    metrics.main(kwargs)


run_signal = run
run_metrics = analyze
