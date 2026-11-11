"""Telescope application package."""


def register(subparsers):
    parser = subparsers.add_parser("telescope", help="telescope")
    setups = parser.add_subparsers(dest="telescope_setup", required=True)
    setups.add_parser("taichu_v1")
    taichu_v2 = setups.add_parser("taichu_v2")
    taichu_v2.add_argument("variant", nargs="?", default="taichu_v2")
    setups.add_parser("acts_v1")
    setups.add_parser("g4")
    parser.set_defaults(_run=run, _components=("telescope",))


def run(kwargs):
    setup = kwargs["telescope_setup"]
    if setup == "taichu_v1":
        from .telescope_signal import main

        return main()
    if setup == "taichu_v2":
        from .telescope_signal import taichu_v2

        return taichu_v2(kwargs["variant"])
    if setup == "acts_v1":
        from .telescope_acts import main

        return main()
    from .telescope_g4 import main

    return main()
