"""Charge-collection experiment application."""

from raser.apps import signal


def main(kwargs):
    kwargs["label"] = "signal"
    kwargs["experiment"] = "charge_collection"
    signal.main(kwargs)
