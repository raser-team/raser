"""Charge-collection experiment application."""

from raser.apps import signal
from raser.core import metrics
from raser.supports import runs

DEFAULT_SOURCE = "decay/Am241"
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


def run(kwargs):
    _prepare(kwargs)
    signal.run_signal(kwargs)


def analyze(kwargs):
    _prepare(kwargs)
    metrics.main(kwargs)


main = run
