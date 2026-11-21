#!/usr/bin/env python3
"""RASER command-line entry point."""

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from contextlib import contextmanager

from raser.lifecycle import process
from raser.supports.paths import infer_project_root
from raser.supports.paths import project_root_context
from raser.supports.paths import work_root


VERSION = "5.0"

APPLICATIONS = (
    "ana",
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


GLOBAL_OPTIONS = {"-t", "--test", "--batch"}  # and -b, -bb, ...


def _experiment_arguments(argv):
    """Inside an experiment folder `raser <options>` runs the experiment: the
    command words and the device come from its config.json and go after the
    global options."""
    config = Path.cwd() / "config.json"
    if (
        not config.is_file()
        or {"-h", "--help", "--version"}.intersection(argv)
        or any(argument in APPLICATIONS for argument in argv)
    ):
        return argv
    experiment = json.loads(config.read_text(encoding="utf-8"))
    words = str(experiment.get("workflow", "")).split()
    if not words or words[0] not in APPLICATIONS:
        return argv
    device = [experiment["device"]] if "device" in experiment else []
    lead = 0
    while lead < len(argv) and (
        argv[lead] in GLOBAL_OPTIONS or re.fullmatch(r"-b+", argv[lead])
    ):
        lead += 1
    return [*argv[:lead], *words, *device, *argv[lead:]]


def main(argv=None):
    argv = _experiment_arguments(list(sys.argv[1:] if argv is None else argv))

    parser = build_parser()
    kwargs = vars(parser.parse_args(argv))
    command = kwargs["_command"]
    if command is None:
        parser.print_help()
        return 1

    if kwargs["global_batch"] != 0:
        # Every command splits into jobs and submits each job itself: -b, -bb,
        # ... before it is its own -b, with the memory level the b's count, and
        # -t is its --dry-run.
        kwargs["dry_run"] = kwargs["dry_run"] or kwargs["test"]
        kwargs["batch"] = True
        kwargs["mem"] = max(kwargs["mem"], kwargs["global_batch"])
        kwargs["global_batch"] = 0

    kwargs["_argv"] = argv
    kwargs["_entry_command_prefix"] = (command,)

    try:
        with _context(kwargs):
            kwargs["_run"](kwargs)
    finally:
        process.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
