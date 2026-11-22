"""The analysis, the last stage of the chain: the results of the points of an
experiment, from what its jobs left in their nodes."""

import json
from pathlib import Path

from raser.lifecycle import nodes
from raser.lifecycle import workflow
from raser.lifecycle.workflow import batches
from raser.lifecycle.workflow import complete_points
from raser.lifecycle.workflow import jobs_of_points
from raser.lifecycle.workflow import set_apart

from .point import write_point
from .across_points import write_points


def collect(root):
    """The last stage of the chain: the result of every point of the
    experiment in `root` whose jobs are all done, from the reconstruction
    tables of its jobs, in the analysis node of the point,
    nodes/analysis/<node>/, which the view of the point links to; and of
    several points side by side in <root>/analysis.

    The node of a point is named by the jobs it takes together: other jobs
    are another node, and a result is not written over by that of other
    settings. One that is there is used as it is."""
    root = Path(root)
    whole = complete_points(root)
    done, results = [], []
    for name, values, jobs, others in jobs_of_points(root):
        if name not in whole:
            print(f"{root}: {name}: no analysis yet, its jobs are not all done")
            continue
        for line in set_apart(others):
            print(f"{root}: {name}: {line}")
        inputs = {"slice": "analysis", "jobs": sorted(sorted(chain.items()) for _, chain in jobs)}
        place = nodes.node_dir(root, "analysis", nodes.node_of(inputs))
        written = nodes.found(place, inputs)
        if written is None:
            held = nodes.lock(place)
            try:
                part = nodes.start(place, "analysis", inputs, {"code": workflow._commit()})
                # too few events for a width or an efficiency is a result of the point;
                # a fit that fails with enough events raises
                try:
                    error = write_point(jobs, part)
                except NotImplementedError as limit:
                    # what the analysis does not do yet is told, and the point has no result
                    print(f"{root}: {name}: no analysis: {limit}")
                    continue
                nodes.finish(part, notes={"error": error})
            finally:
                if held is not None:
                    held.close()
        else:
            error = written["notes"].get("error")
        nodes.link_view(root, name, "analysis", place)
        result = json.loads((place / "result.json").read_text())
        print(f"{root}: {name}: {result['collection']['events']} events of {batches(jobs)}")
        if error is not None:
            print(f"{place}: {error}")
        print(f"{place / 'result.json'}")
        done.append((name, values))
        results.append(result)
    if len(done) > 1:
        write_points(done, results, root / "analysis")
