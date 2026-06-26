"""Time-resolution experiment application."""

from pathlib import Path

from raser.apps import signal
from raser.core import metrics


def main(kwargs):
    label = kwargs.get("label", "signal")
    kwargs["experiment"] = "time_resolution"
    kwargs["signal_output_label"] = "timeres"
    kwargs["signal_source"] = Path(str(kwargs.get("source", "radioactive/Sr90"))).stem

    if label == "signal":
        signal.main(kwargs)
    elif label == "metrics":
        metrics.main(kwargs)
    else:
        raise NameError(label)
