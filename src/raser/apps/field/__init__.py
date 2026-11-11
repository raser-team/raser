"""Field application."""

from raser.core.field import command


def register(subparsers):
    parser = subparsers.add_parser(
        "field", help="calculate electric fields, weighting fields, and IV/CV"
    )
    parser.add_argument("target", help="Device project")
    parser.add_argument(
        "-v", "--verbose", help="VERBOSE level", action="count", default=0
    )
    parser.add_argument("-cv", help="CV simulation", action="store_true")
    parser.add_argument("-wf", help="weighting-field simulation", action="store_true")
    parser.add_argument(
        "-irr", "--irradiation_flux", help="irradiationm flux", type=float
    )
    parser.add_argument("-bias", help="bias voltage", type=float)
    parser.add_argument(
        "-v_current", help="Current voltage for step-by-step simulation", type=float
    )
    parser.add_argument("-noise", help="Detector Noise simulation", action="store_true")
    parser.add_argument("-umf", help="use umf solver", action="store_true")
    parser.add_argument(
        "-ext",
        "--extract",
        dest="input",
        metavar="TCAD_FILE",
        help="import a TCAD field file",
    )
    parser.add_argument(
        "-flip", help="flip the direction of the electric field", action="store_true"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(_run=command.main, _project="target")
