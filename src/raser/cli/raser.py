#!/usr/bin/env python3
"""RASER command-line entry point."""

import argparse
import importlib
import sys
from contextlib import contextmanager

from raser.lifecycle import scheduler
from raser.lifecycle import process
from raser.supports.paths import infer_project_root
from raser.supports.paths import project_root_context
from raser.supports.paths import work_root


VERSION = "5.0"

APPLICATIONS = (
    "bmos",
    "cce",
    "field",
    "lumi",
    "signal",
    "tct",
    "telescope",
    "timeres",
)


@contextmanager
def _context(kwargs):
    argument = kwargs.get("_project")
    if argument is None:
        project = work_root()
    else:
        project = infer_project_root(kwargs[argument])
    with project_root_context(project, kwargs.get("_components", ())):
        yield


def build_parser():
    parser = argparse.ArgumentParser(prog="raser")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "-b",
        "--batch",
        help="submit BATCH job to cluster",
        action="count",
        default=0,
        dest="global_batch",
    )
    parser.add_argument(
        "-t", "--test", help="test batch submission", action="store_true"
    )

    subparsers = parser.add_subparsers(
        help="sub-command help", dest="_command", metavar="command"
    )
    for name in APPLICATIONS:
        importlib.import_module(f"raser.apps.{name}").register(subparsers)

    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = build_parser()
    kwargs = vars(parser.parse_args(argv))
    command = kwargs["_command"]
    if command is None:
        parser.print_help()
        return 1

    if kwargs["global_batch"] != 0 and "batch" in kwargs:
        # A command that splits into jobs submits every job itself: -b, -bb, ...
        # before it is its own -b, with the memory level the b's count, and -t
        # is its --dry-run.
        kwargs["dry_run"] = kwargs["dry_run"] or kwargs["test"]
        kwargs["batch"] = True
        kwargs["mem"] = max(kwargs["mem"], kwargs["global_batch"])
        kwargs["global_batch"] = 0

    kwargs["_argv"] = argv
    kwargs["_entry_command_prefix"] = (command,)

    try:
        with _context(kwargs):
            if kwargs["global_batch"] != 0:
                # Global options such as -bb precede the sub-command; the worker
                # must not see them, or it would submit itself again.
                scheduler.main(
                    command,
                    argv[argv.index(command) :],
                    kwargs["global_batch"],
                    is_test=kwargs["test"],
                )
            else:
                kwargs["_run"](kwargs)
    finally:
        process.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
