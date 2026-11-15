"""BMOS application package."""

from raser.lifecycle.workflow import Workflow


def register(subparsers):
    parser = subparsers.add_parser("bmos", help="Beam Monitor Online System")
    actions = parser.add_subparsers(dest="bmos_action", required=True)
    get_signal = actions.add_parser("GetSignal", help="generate BMOS signal")
    get_signal.add_argument("det_name", help="sensor or BMOS detector config")
    get_signal.set_defaults(_project="det_name")
    Workflow(name="bmos GetSignal", job=run).attach(get_signal)
    histogram_signal = actions.add_parser(
        "histogram_signal", help="generate BMOS histogram signal"
    )
    histogram_signal.add_argument("det_name", help="sensor or BMOS detector config")
    histogram_signal.set_defaults(_project="det_name")
    Workflow(name="bmos histogram_signal", job=run).attach(histogram_signal)
    for action, text in (
        ("one_histogram", "draw one BMOS histogram"),
        ("all_histogram", "draw all BMOS histograms"),
    ):
        histogram = actions.add_parser(action, help=text)
        histogram.add_argument("det_name", help="sensor or BMOS detector config")
        histogram.set_defaults(_project="det_name")
    parser.set_defaults(_run=run)


def run(kwargs):
    action = kwargs["bmos_action"]
    if action == "GetSignal":
        from .get_signal import get_signal

        return get_signal(kwargs["det_name"])
    if action == "histogram_signal":
        from .histogram_signal import get_signal

        return get_signal(kwargs["det_name"])
    from .histogram import main

    return main({"one_histogram": "one", "all_histogram": "all"}[action])
