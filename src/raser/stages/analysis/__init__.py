"""Analysis of the files the jobs of an experiment left."""

import json
from pathlib import Path

from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute
from raser.lifecycle.workflow import finished_in
from raser.supports.paths import project_root_context

from .point import write_point
from .across_points import write_points


def collect(options):
    """The job of one point of `raser ana`: the results of every point of the
    analysed experiment as the digitizer of this point sees them, each in the
    folder of its name inside the folder of this point, and of several of
    them side by side in the folder of this point itself."""
    root, folder = Path(options["experiment"]), Path(options["_run_path"])
    digitizer = options["_files"]["adc"]
    points = finished_in(root)
    failed = []
    done, results = [], []
    for name, point_options, jobs in points:
        if not jobs:
            failed.append(f"  {root / name}: no finished job")
            continue
        error = write_point(jobs, digitizer, folder / name)
        # too few selected events for a width is a result of the point
        if error is not None:
            print(f"{folder / name}: no time resolution: {error}")
        print(f"{folder / name / 'result.json'}")
        done.append((name, point_options))
        results.append(json.loads((folder / name / "result.json").read_text()))
    if len(done) > 1:
        write_points(done, results, folder)
    if failed:
        raise SystemExit("\n".join([f"{len(failed)} of {len(points)} points are not complete:", *failed]))


WORKFLOW = Workflow(
    name="analysis",
    job=collect,
    keys=("adc", "threshold", "amplitude_threshold"),
    defaults={"adc": "scope", "threshold": None, "amplitude_threshold": None},
    components={"adc": "adc"},
    in_file={"threshold": "adc.threshold", "amplitude_threshold": "adc.amplitude_threshold"},
    device=False,
    seeds=False,
    # the analysis is an experiment inside the experiment it analyses
    folder=lambda kwargs: Path(kwargs["experiment"]) / "analysis",
    command=lambda kwargs: [kwargs["experiment"]],
)


def run(kwargs):
    """`raser ana <experiment folder>`, and each of its jobs."""
    root = Path(kwargs["experiment"]).resolve()
    words = json.loads((root / "config.json").read_text())["workflow"].split()
    # the experiment is work/<device>/<words>; its files and the digitizer are
    # found as its own command finds them
    project = root.parents[len(words) - 1]
    with project_root_context(project, kwargs["_components_of"][words[0]]):
        return execute(WORKFLOW, {**kwargs, "experiment": str(root)})


def register(subparsers):
    parser = subparsers.add_parser("analysis", aliases=["ana"], help="stage: the results of the points of an experiment")
    parser.add_argument("experiment", help="experiment folder, work/<device>/<command>")
    parser.add_argument("-adc", help="digitizer")
    parser.add_argument("-threshold", type=float, help="of the times of arrival [mV], in place of the digitizer's")
    parser.add_argument("-amplitude_threshold", type=float, help="of the selected events [mV], in place of the digitizer's")
    WORKFLOW.attach(parser)
    parser.set_defaults(_run=run)
