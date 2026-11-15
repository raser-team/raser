"""A job in slices: a slice is run again alone when what it reads changed."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Slice:
    """One stretch of a job, between two of the files it leaves behind."""

    name: str
    run: Callable  # runs the slice of one job; receives the options as a dict
    keys: tuple = ()  # the options that change what it writes
    kinds: tuple = ()  # the kinds of json file that change what it writes
    # A scanned option of it makes each point a measurement of its own, with
    # its own events: the point runs the slices before this one itself. False
    # for a slice that only works on what was measured, such as electronics:
    # its points all read the same earlier slices. A run with same_seeds
    # shares the earlier slices in either case.
    new_events: bool = True


def mark(folder, index, name="job") -> Path:
    """The file that says the slice `name` of a job, or the whole job, is done."""
    return Path(folder) / "batch" / f"{name}_{index}.done"


def owner(slices, key) -> int:
    """The first slice that reads the option or the kind of file `key`.
    One that no slice names counts for the first: changing it runs everything again."""
    for k, piece in enumerate(slices):
        if key in piece.keys or key in piece.kinds or key.split(".")[0] in piece.kinds:
            return k
    return 0


def first_changed(slices, old, record) -> int:
    """The first slice that read something else in the run `old` than in
    `record`; the number of slices when none did."""
    for k, piece in enumerate(slices):
        if old.get("slices", {}).get(piece.name) != record["slices"][piece.name]:
            return k
    return len(slices)


def left(slices, folder, jobs, again) -> dict:
    """Per slice, the jobs it still has to run: every job from the slice
    `again` on, before it the jobs without its mark."""
    return {
        piece.name: [i for i in jobs if k >= again or not mark(folder, i, piece.name).exists()]
        for k, piece in enumerate(slices)
    }


def forget(slices, folder) -> None:
    """Remove the marks of these slices, and those of the whole jobs."""
    for name in [piece.name for piece in slices] + ["job"] * bool(slices):
        for path in (Path(folder) / "batch").glob(f"{name}_*.done"):
            path.unlink()


def run(slices, folders, index, options, wanted, before) -> bool:
    """Run the `wanted` slices of one job that have no mark, in order; True
    when every slice of the job is done.

    `folders` gives each slice the seed folder that holds its mark, which is
    another point's when the slice does not read what makes this point
    differ. A slice starts only when the ones before it are done there.
    `before` is called with a slice before it runs."""
    for k, piece in enumerate(slices):
        if piece.name not in wanted or mark(folders[piece.name], index, piece.name).exists():
            continue
        for earlier in slices[:k]:
            if not mark(folders[earlier.name], index, earlier.name).exists():
                raise RuntimeError(
                    f"{piece.name} of job {index} needs {earlier.name}, "
                    f"which is not done in {folders[earlier.name]}"
                )
        before(piece)
        piece.run(options)
        mark(folders[piece.name], index, piece.name).touch()
    return all(mark(folders[piece.name], index, piece.name).exists() for piece in slices)
