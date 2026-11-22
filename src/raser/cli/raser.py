#!/usr/bin/env python3
"""RASER command-line entry point."""

import argparse
import importlib
import importlib.metadata
import json
import re
import sys
import tomllib
from pathlib import Path
from contextlib import contextmanager

import raser
from raser.supports import process
from raser.supports.dependency import ROOT_MISSING
from raser.supports.dependency import ROOT_MODULES
from raser.supports.dependency import MissingDependency
from raser.supports.paths import infer_project_root
from raser.supports.paths import REPO_ROOT
from raser.supports.paths import project_root_context
from raser.supports.paths import work_root

LIBRARY = {  # command of the library -> the module that registers it
    "analysis": "raser.stages.stage_commands",
    "field": "raser.stages.field",
    "deposit": "raser.stages.stage_commands",
    "current": "raser.stages.stage_commands",
    "readout": "raser.stages.stage_commands",
    "reconstruction": "raser.stages.stage_commands",
    "status": "raser.lifecycle.status",
}
GROUP = "raser.experiments"  # the entry points of the experiments: command -> module


def experiments(tree=REPO_ROOT) -> dict[str, str]:
    """command -> the module that registers it, for each experiment in the
    entry points of GROUP. Run from a source tree, which is not installed,
    the experiments of raser itself are those its pyproject.toml lists."""
    given = [
        (point.name, point.value, point.dist.name if point.dist else "?")
        for point in importlib.metadata.entry_points(group=GROUP)
        if tree is None or point.dist is None or point.dist.name != "raser"
    ]
    if tree is not None:
        project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))
        listed = project["project"]["entry-points"][GROUP]
        given = [(name, value, "raser") for name, value in listed.items()] + given
    found: dict[str, str] = {}
    by: dict[str, str] = {}
    for name, value, dist in given:
        if name in LIBRARY or name in SHORT:
            raise SystemExit(
                f"raser: {dist} registers an experiment {name}: {name} is a command of raser"
            )
        if name in found:
            raise SystemExit(
                f"raser: the experiment {name} is registered by {by[name]} and by {dist}"
            )
        found[name], by[name] = value, dist
    return found


# The short commands of the stages; files and folders hold the full names.
SHORT = {
    "fld": "field",
    "dep": "deposit",
    "cur": "current",
    "rdo": "readout",
    "reco": "reconstruction",
    "ana": "analysis",
}
APPLICATIONS = {**LIBRARY, **experiments()}  # command -> the module that registers it


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
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {raser.__version__}"
    )
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
    for module in dict.fromkeys(APPLICATIONS.values()):  # a module may register several
        importlib.import_module(module).register(subparsers)
    # The component roots each command registers: `raser ana` finds the files
    # of an experiment as the command that ran it does.
    parser.set_defaults(
        _components_of={
            name: tuple(command.get_default("_components") or ())
            for name, command in subparsers.choices.items()
        }
    )

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
        or any(argument in APPLICATIONS or argument in SHORT for argument in argv)
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
    command = SHORT.get(kwargs["_command"], kwargs["_command"])
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
    except MissingDependency as missing:
        print(f"raser: {missing}", file=sys.stderr)
        return 1
    except ModuleNotFoundError as error:
        if error.name not in ROOT_MODULES:
            raise
        print(f"raser: {ROOT_MISSING}", file=sys.stderr)
        return 1
    finally:
        process.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
