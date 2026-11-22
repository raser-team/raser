"""The files a finished job left behind."""

from raser.core.deposit.deposits import read_deposits
from raser.lifecycle.nodes import node_dir


def slice_file(experiment, nodes, name):
    """Path of the file of the slice `name` ("deposit", "current",
    "readout") of a job: in the node of the slice.

    experiment, nodes : a job as lifecycle hands it out, the experiment
        folder and the node of each of its slices.
    """
    # a slice after one that ended the job has no node: its file is not there
    return node_dir(experiment, name.split(".")[0], nodes.get(name, "none")) / f"{name}.h5"


def job_file(experiment, nodes, name):
    """Path of the file `name` ("current", "readout") of a job, or None for
    a job that recorded no event: it has a deposits file without events and
    nothing after it."""
    path = slice_file(experiment, nodes, name)
    if path.exists():
        return path
    recorded = len(read_deposits(str(slice_file(experiment, nodes, "deposit"))).events)
    if recorded:
        raise FileNotFoundError(
            f"{path}: the job recorded {recorded} events but left no {name} file"
        )
    return None
