"""The files a finished job left in its seed folder."""

from pathlib import Path

from raser.core.interaction.deposits import read_deposits


def job_file(folder, index, name):
    """Path of the file `name` ("currents", "waveforms") of a job, or None for
    a job that recorded no event: it has a deposits file without events and
    nothing after it."""
    batch = Path(folder) / "batch"
    path = batch / f"{name}_{index}.h5"
    if path.exists():
        return path
    recorded = len(read_deposits(str(batch / f"deposits_{index}.h5")).events)
    if recorded:
        raise FileNotFoundError(
            f"{path}: job {index} recorded {recorded} events but left no {name} file"
        )
    return None
