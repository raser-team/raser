"""Telescope application package."""

from raser.lifecycle.workflow import Workflow


def register(subparsers):
    parser = subparsers.add_parser("telescope", help="telescope")
    setups = parser.add_subparsers(dest="telescope_setup", required=True)
    for setup in ("taichu_v1", "taichu_v2", "acts_v1", "g4"):
        setup_parser = setups.add_parser(setup)
        command = None
        if setup == "taichu_v2":
            setup_parser.add_argument("variant", nargs="?", default="taichu_v2")
            command = _variant
        Workflow(
            name=f"telescope {setup}", job=run, device=False, command=command
        ).attach(setup_parser)
    parser.set_defaults(_run=run, _components=("telescope",))


def _variant(kwargs):
    return [kwargs["variant"]]


def run(kwargs):
    setup = kwargs["telescope_setup"]
    if setup == "taichu_v1":
        from .telescope_signal import main

        return main(kwargs["seed"])
    if setup == "taichu_v2":
        from .telescope_signal import taichu_v2

        return taichu_v2(kwargs["variant"])
    if setup == "acts_v1":
        from .telescope_acts import main

        return main()
    from .telescope_g4 import main

    return main()
