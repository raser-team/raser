"""The files a finished job left behind."""

import json
from pathlib import Path

from raser.core.deposit.deposits import read_deposits


def slice_file(folder, index, name):
    """Path of the file of the slice `name` ("deposit", "current",
    "readout") of a job of the seed folder `folder`.

    The file is in the seed folder of the same name in the point that holds
    the slice; run.json of the seed folder names that point for each slice.
    """
    folder = Path(folder)
    record = json.loads((folder / "run.json").read_text())
    experiment = folder.parent.parent if record["point"] else folder.parent
    return experiment / record["held_in"][name] / folder.name / "batch" / f"{name}_{index}.h5"


def job_file(folder, index, name):
    """Path of the file `name` ("current", "readout") of a job, or None for
    a job that recorded no event: it has a deposits file without events and
    nothing after it."""
    path = slice_file(folder, index, name)
    if path.exists():
        return path
    recorded = len(read_deposits(str(slice_file(folder, index, "deposit"))).events)
    if recorded:
        raise FileNotFoundError(
            f"{path}: job {index} recorded {recorded} events but left no {name} file"
        )
    return None
