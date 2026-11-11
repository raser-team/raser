"""BMOS application package."""


def register(subparsers):
    parser = subparsers.add_parser("bmos", help="Beam Monitor Online System")
    parser.add_argument("sensor", help="sensor or BMOS detector config")
    actions = parser.add_subparsers(dest="bmos_action", required=True)
    actions.add_parser("GetSignal", help="generate BMOS signal")
    actions.add_parser("histogram_signal", help="generate BMOS histogram signal")
    actions.add_parser("one_histogram", help="draw one BMOS histogram")
    actions.add_parser("all_histogram", help="draw all BMOS histograms")
    parser.set_defaults(_run=run)


def run(kwargs):
    action = kwargs["bmos_action"]
    if action == "GetSignal":
        from .get_signal import get_signal

        return get_signal(kwargs["sensor"])
    if action == "histogram_signal":
        from .histogram_signal import get_signal

        return get_signal()
    from .histogram import main

    return main({"one_histogram": "one", "all_histogram": "all"}[action])
