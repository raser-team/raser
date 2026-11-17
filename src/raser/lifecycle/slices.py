"""A job in slices: a slice is run again alone when what it reads changed."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Shared:
    """What a slice reads that no experiment holds: several share it, such
    as the field of a device in work/<device>/field. Whether it is done is
    asked of it, not of the marks of the experiment."""

    # (options, files) of a point -> the folder that holds it, or None when
    # it has to be made first
    ready: Callable
    # (kwargs of the command, options, files) of a point: make it, in this
    # process or as jobs on the cluster when the command has -b
    start: Callable
    # (options, files) of a point -> what tells one making of it from another,
    # as a digest of what it was made from; None when it is not ready. The
    # slices that read it run again when it changes.
    stamp: Callable = lambda options, files: None


@dataclass(frozen=True)
class Slice:
    """One stretch of a job, between two of the files it leaves behind."""

    name: str
    # Runs the slice of one job; receives the options as a dict. It may return
    # a dict of what it used that the run could not know before, such as the
    # field it found: `notes` reads it back. It is kept, not judged.
    run: Callable
    keys: tuple = ()  # the options that change what it writes
    kinds: tuple = ()  # the kinds of json file that change what it writes
    # A scanned option of it makes each point a measurement of its own, with
    # its own events: the point runs the slices before this one itself. False
    # for a slice that only works on what was measured, such as electronics:
    # its points all read the same earlier slices. A run with same_seeds
    # shares the earlier slices in either case.
    new_events: bool = True
    # Given: the slice reads something shared with other experiments; the
    # command makes it first where it is not ready, and its jobs wait for it.
    shared: Shared | None = None
    # The slices whose files it reads, by name; None: the one before it.
    needs: tuple | None = None


class Ended(Exception):
    """Raised by a slice that leaves nothing for the slices after it, such as
    a job that recorded no event: the job is done, the later slices are not run."""


def mark(folder, index, name="job") -> Path:
    """The file that says the slice `name` of a job, or the whole job, is done."""
    return Path(folder) / "batch" / f"{name}_{index}.done"


def notes(folder, index, name) -> dict:
    """What the slice `name` of a job left with its mark: what its function
    returned, and "ended" when it ended the job."""
    return json.loads(mark(folder, index, name).read_text() or "{}")


def upstream(slices, k) -> set[int]:
    """The slices the k-th reads the files of, directly or through others."""
    index = {piece.name: j for j, piece in enumerate(slices)}
    needs = slices[k].needs
    direct = {k - 1} if needs is None and k > 0 else {index[name] for name in needs or ()}
    return direct.union(*(upstream(slices, j) for j in direct))


def owners(slices, key) -> set[int]:
    """The slices that read the option or the kind of file `key`. One that no
    slice names counts for those that read no other slice: changing it runs
    everything again."""
    named = {
        k
        for k, piece in enumerate(slices)
        if key in piece.keys or key in piece.kinds or key.split(".")[0] in piece.kinds
    }
    return named or {k for k in range(len(slices)) if not upstream(slices, k)}


def reads(slices, key, k) -> bool:
    """Whether the k-th slice reads `key`, itself or through a slice it reads."""
    return bool(owners(slices, key) & (upstream(slices, k) | {k}))


def to_run_again(slices, old, record) -> set[int]:
    """The slices that read something else in the run `old` than in `record`.
    What a slice reads holds what the slices it reads read, so a slice that
    reads the files of one of them is among them too."""
    return {
        k
        for k, piece in enumerate(slices)
        if old.get("slices", {}).get(piece.name) != record["slices"][piece.name]
    }


def left(slices, folder, jobs, again) -> dict:
    """Per slice, the jobs it still has to run: every job of the slices in
    `again`, of the others the jobs without its mark."""
    return {
        piece.name: [i for i in jobs if k in again or not mark(folder, i, piece.name).exists()]
        for k, piece in enumerate(slices)
    }


def forget(slices, folder) -> None:
    """Remove the marks of these slices, and those of the whole jobs."""
    for name in [piece.name for piece in slices] + ["job"] * bool(slices):
        for path in (Path(folder) / "batch").glob(f"{name}_*.done"):
            path.unlink()


def run(slices, folders, index, options, wanted, before, publish=lambda piece: True) -> bool:
    """Run the `wanted` slices of one job that have no mark, in order; True
    when every slice of the job is done.

    `folders` gives each slice the seed folder that holds its mark, which is
    another point's when the slice does not read what makes this point
    differ. A slice starts only when the ones it reads (Slice.needs) are done
    there, and is not run when one of them raised `Ended`, which the mark of
    that one says.
    `before` is called with a slice before it runs; `publish` after, and
    False from it stops the job without the mark of the slice."""
    for k, piece in enumerate(slices):
        if piece.name not in wanted or mark(folders[piece.name], index, piece.name).exists():
            continue
        earlier_ones = [slices[j] for j in sorted(upstream(slices, k))]
        for earlier in earlier_ones:
            if not mark(folders[earlier.name], index, earlier.name).exists():
                raise RuntimeError(
                    f"{piece.name} of job {index} needs {earlier.name}, "
                    f"which is not done in {folders[earlier.name]}"
                )
        done = mark(folders[piece.name], index, piece.name)
        if any(notes(folders[earlier.name], index, earlier.name).get("ended") for earlier in earlier_ones):
            done.touch()  # an earlier slice ended the job
            continue
        before(piece)
        try:
            left = piece.run(options) or {}
        except Ended:
            left = {"ended": True}
        if not publish(piece):
            raise RuntimeError(
                f"run.json changed while {piece.name} of job {index} ran: its output is set aside "
                "as .stale and not marked done; run the command again"
            )
        # Written whole or not at all: a mark cut short would read as no notes.
        part = done.with_name(done.name + ".part")
        part.write_text(json.dumps(left) if left else "")
        os.replace(part, done)
    return all(mark(folders[piece.name], index, piece.name).exists() for piece in slices)
