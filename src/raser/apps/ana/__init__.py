"""Analysis of the files the jobs of an experiment left."""

import json
from pathlib import Path

from raser.components import load_component
from raser.lifecycle.workflow import finished_in
from raser.supports.paths import project_root_context

from .point import write_point


def collect(kwargs):
    """`raser ana <experiment folder>`: the results of every point of the
    experiment, in <point>/ana/<digitizer>/ of each."""
    root = Path(kwargs["experiment"]).resolve()
    config = json.loads((root / "config.json").read_text())
    words = config["workflow"].split()
    # the experiment is work/<device>/<words>; its files are found as its own command finds them
    project = root.parents[len(words) - 1]
    failed = []
    with project_root_context(project, (words[0], "signal")):
        _, digitizer = load_component("adc", kwargs["adc"])
        points = finished_in(root)
    for name, _, jobs in points:
        folder = root / name / "ana" / Path(kwargs["adc"]).stem
        if not jobs:
            failed.append(f"  {root / name}: no finished job")
            continue
        error = write_point(jobs, digitizer, folder)
        if error is not None:
            failed.append(f"  {folder}: no time resolution: {error}")
        print(f"{folder / 'result.json'}")
    if failed:
        raise SystemExit("\n".join([f"{len(failed)} of {len(points)} points are not complete:", *failed]))


def register(subparsers):
    parser = subparsers.add_parser("ana", help="results of the points of an experiment")
    parser.add_argument("experiment", help="experiment folder, work/<device>/<command>")
    parser.add_argument("-adc", default="scope", help="digitizer")
    parser.set_defaults(_run=collect)
