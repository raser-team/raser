"""`raser <command> -s <n>`: an experiment, its points, a seed folder in each, n jobs."""

from __future__ import annotations

import argparse
import errno
import fcntl
import itertools
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from pathlib import Path
from typing import Callable, Mapping

import raser
from raser.components import load_component
from raser.core.device.build_device import device_json
from raser.lifecycle import jobs
from raser.lifecycle import nodes
from raser.lifecycle import scheduler
from raser.lifecycle import slices
from raser.supports.paths import REPO_ROOT
from raser.supports.paths import project_path


WORKFLOWS: dict = {}  # the workflows that have a command, by name


class Running(SystemExit):
    """Another process runs this already: a folder of a command, or a job.
    The command stops with the message alone."""


def _lock(path, what) -> object | None:
    """Hold the lock on `path` until the handle it returns is closed or the
    process ends; Running when another process holds it. A file system that
    cannot lock, as some network ones, gets a warning, and the run goes on."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise Running(f"{what} is run by another process now; run the command again when it is done") from None
    except OSError as error:
        handle.close()
        if error.errno not in (errno.ENOLCK, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL):
            raise
        print(f"warning: {path} cannot be locked here ({error.strerror}): nothing keeps another command off it")
        return None
    return handle


def _running_jobs(folder) -> list[int]:
    """The jobs of a seed or point folder whose lock another process holds."""
    running = []
    for path in sorted(Path(folder).glob("batch/job_*.lock")):
        with open(path, "a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                running.append(int(path.stem.split("_")[1]))
            except OSError:
                pass  # a file system that cannot lock tells nothing
    return sorted(running)


def _folder_lock(folder) -> Path:
    """The lock of a seed or point folder, beside it, so that it holds when the folder is put aside."""
    folder = Path(folder)
    return folder.parent / f".{folder.name}.lock"


@dataclass(frozen=True)
class Workflow:
    """What an application hands in."""

    name: str  # command words, "signal" or "telescope taichu_v1"; folder work/<device>/<words>
    job: Callable | None = None  # runs one job; receives the options as a dict
    # Instead of `job`: the Slices of slices.py that a job runs one after
    # another. A slice is run again when what it or a slice it reads
    # (Slice.needs) reads changed; the slices it does not read stay as they are.
    slices: tuple = ()
    keys: tuple = ()  # the options an experiment may set
    defaults: Mapping = field(default_factory=dict)  # their values when nobody set them
    components: Mapping = field(default_factory=dict)  # kind of json file -> the option naming it
    # kind of file -> the function that reads the file its option names into
    # a dict, for a file that is not json, such as the SPICE files of a chain
    readers: Mapping = field(default_factory=dict)
    in_file: Mapping = field(default_factory=dict)  # option -> where its value sits in a file
    device: bool = True  # the command names a device
    # False: nothing is drawn; a point holds one run, in its own folder, and its
    # job is started by every command: the job itself sees what is left to do.
    seeds: bool = True
    # (the run.json of an old run, the record of this one) -> what makes the old
    # run out of date, or None. Not given: any difference between the two does,
    # and so do uncommitted changes of the code.
    outdated: Callable | None = None
    # the options of a command -> the settings of its command line that change
    # what its jobs write and that no option of the experiment holds, such as
    # the linear solver of a field; recorded in run.json, other ones make the
    # run out of date whatever `outdated` judges. Given no options, the
    # default settings.
    settings: Callable | None = None
    command: Callable | None = None  # extra words of the job command
    # the options of a command -> its experiment folder, for an experiment that
    # is not at work/<device>/<words>, such as one inside another experiment
    folder: Callable | None = None
    # Groups of keys of which one is given: a key of a group given in a layer
    # (the command line, then the config's "set", then the defaults) leaves
    # out the others of its group from the layers below; two of a group in
    # one layer are an error.
    exclusive: tuple = ()
    # More than one device: name -> (its device, None for the one the command
    # names; the positions it takes). Each device file is files[name]["device"],
    # its options at the addresses <name>.device.... One device is the one the
    # command names, in files["device"].
    devices: Mapping = field(default_factory=dict)
    # The sections of config.json, for an experiment whose settings are
    # written whole in sections: its keys are then addresses <section>.<key>,
    # config.json holds every one of them, a key it lacks or does not know is
    # an error, and each slice reads those of its stage under their bare names.
    sections: tuple = ()
    # Those of the sections whose settings say what is measured: a list of
    # values for one of them is a scan, a run of the experiment for each
    # value. A setting of the other sections says how what was measured is
    # analysed: a list is its value, and it is not scanned.
    scanned: tuple = ()
    # <section>.<slot> -> the kind of file the slot names: a key inside that
    # file is given as <section>.<slot>.<keys down to it>.
    slots: Mapping = field(default_factory=dict)
    # The last stage of the chain, the analysis: (the experiment folder) ->
    # the results of its points whose jobs are all done. It works on the jobs
    # of a point together, so it is no slice of a job: the command runs it
    # when its jobs are done, and so does the last job on the cluster.
    analysis: Callable | None = None

    def __post_init__(self):
        _one_of_each_group(self.exclusive, self.defaults, f"the defaults of {self.name}")

    @property
    def words(self):
        return self.name.split()

    def attach(self, parser):
        run_arguments(parser, self.seeds)
        if self.slices:
            parser.add_argument("--job-slices", help=argparse.SUPPRESS)
        parser.add_argument("--job-dir", help=argparse.SUPPRESS)
        parser.add_argument("--job-index", type=int, help=argparse.SUPPRESS)
        parser.set_defaults(_run=lambda kwargs: execute(self, kwargs))
        WORKFLOWS[self.name] = self


def run_arguments(parser, seeds=True):
    """The options of how a command runs: its jobs and their seeds, the
    cluster, a dry run, scans. A command that runs a workflow of its own
    gets them from `Workflow.attach`."""
    if seeds:
        parser.add_argument("-s", "--jobs", type=int)
        parser.add_argument("--seed", type=int)
        parser.add_argument("--same-seeds", action="store_true")
        # A job on the cluster that starts the command again goes on in the seed
        # folder of the command, whatever names it, not in a new one.
        parser.add_argument("--seed-folder", help=argparse.SUPPRESS)
    parser.add_argument("-b", "--batch", action="store_true")
    parser.add_argument("-mem", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scan", action="append", default=[])
    parser.add_argument("--set", action="append", default=[], help="address=value, as --scan with one value")


def execute(workflow, kwargs, register=True):
    """Run the points of an experiment that a command asks for.

    register=False runs only the points the command itself gives, not the
    scans of the config, and leaves config.json as it is; a config made now
    holds only what names the experiment. The command line has no such
    switch: a shared slice that a point of another experiment needs, such
    as its field, is made so, and the experiment of the shared slice does
    not take that point for one of its own."""
    if kwargs.get("job_dir"):
        return _run_job(workflow, kwargs)  # one of the jobs started below

    # The experiment: a folder with a config.json, here or at the default place.
    # Its options are the defaults, then the config's "set", then the command line.
    identity = {"workflow": workflow.name}
    if workflow.device:
        identity["device"] = kwargs["det_name"]
    root = Path(workflow.folder(kwargs)) if workflow.folder else Path.cwd()
    config = _read(root / "config.json")
    if not workflow.folder and any(config.get(key) != value for key, value in identity.items()):
        root = Path(project_path(*workflow.words))
    # One command at a time reads and writes the config of an experiment: it
    # is read again under the lock, and the lock is let go once the command
    # holds the folders it writes and has written the config.
    lock = None if kwargs["dry_run"] else _lock(root.parent / f".{root.name}.config.lock", f"the config of {root}")
    held = [lock]

    def release() -> None:
        if held[0] is not None:
            held[0].close()
            held[0] = None

    try:
        return _execute(workflow, kwargs, register, root, read_config(workflow, root), identity, release)
    finally:
        release()


def _execute(workflow, kwargs, register, root, config, identity, release):
    """execute, from the config of the experiment in `root` on; `release`
    lets go of the lock of the config."""
    given = {key: kwargs[key] for key in workflow.keys if kwargs.get(key) is not None}
    # --set: one value at an address, written as --scan writes it.
    address = {name: key for key, name in config.get("names", {}).items()}
    fixed_here = {}
    for item in kwargs.get("set") or []:
        key, _, value = item.partition("=")
        fixed_here[address.get(key, key)] = _parse(value)
    scanned_here = {address.get(item.partition("=")[0], item.partition("=")[0]) for item in kwargs["scan"]}
    for key, value in fixed_here.items():
        if workflow.sections and key.split(".")[0] not in workflow.scanned:
            continue  # a setting of the analysis names no folder: any value
        if workflow.sections and isinstance(value, list):
            raise ValueError(f"{key}: a list of values is a scan; give it to --scan as {key}=" + ",".join(map(str, value)))
        _check_folder_names(key, [value])
    if workflow.sections:
        # what the command line gives is a setting or a key under a slot; anything else is told now
        for key in sorted(scanned_here | set(fixed_here)):
            if key not in workflow.keys:
                in_file(workflow, key)
    if workflow.sections:
        for key in sorted(scanned_here):
            if key.split(".")[0] not in workflow.scanned:
                raise ValueError(
                    f"{key} is not scanned: a setting of {key.split('.')[0]} says how the events that were measured "
                    f"are analysed, not what is measured. Set another value with --set and run again: the events are "
                    f"used as they are. Scanned are the settings of {', '.join(workflow.scanned)}"
                )
    if both := sorted(scanned_here & set(fixed_here)):
        raise ValueError(f"{', '.join(both)}: given to --set and to --scan at once; give it to one of them")
    given = {**given, **fixed_here}
    scan, points, asked = _points(workflow, kwargs, config if register else {**config, "scan": {}}, given)

    # The seed folder of this command in every point, and the jobs left in it.
    # Without seeds the point folder itself holds the run, and its one job.
    if not workflow.seeds:
        label, seed = "", None
    elif kwargs.get("seed_folder"):
        label, seed = kwargs["seed_folder"], _seed_of(root, kwargs["seed_folder"])
    elif kwargs["seed"] is None:
        label, seed = time.strftime("%Y_%m%d_%H%M%S"), secrets.randbits(31)
    else:
        label, seed = f"seed_{kwargs['seed']}", kwargs["seed"]
    # A seed folder that was run with another record is run again from the start,
    # and so is any when the code has uncommitted changes; the old one is kept.
    commit = _commit()
    same_seeds = kwargs.get("same_seeds") or config.get("same_seeds", False)
    todo = []
    # The slices this command runs: all, or one and those it reads.
    runs = set(range(len(workflow.slices)))
    if kwargs.get("until"):
        # A stage whose slices are one per position, current.<position>: all of them.
        named = [piece.name for piece in workflow.slices]
        until = [k for k, name in enumerate(named) if kwargs["until"] in (name, name.split(".")[0])]
        if kwargs["until"] == "analysis" and workflow.analysis:
            until = list(range(len(named)))  # the last stage: every slice before it
        if not until:
            raise ValueError(f"no slice {kwargs['until']} in {named}")
        runs = set(until).union(*(slices.upstream(workflow.slices, k) for k in until))
    # A slice is held by the run of the point that differs from this one only
    # in what the slice reads: the points that hold slices of others come first.
    # A point that holds none of its slices, as one whose two roots are held by
    # two others, comes after them.
    def depth(name) -> int:
        holders = set(points[name][3]) - {name}
        return 1 + max(map(depth, holders)) if holders else 0

    order = sorted(points, key=lambda name: (depth(name), points[name][3].index(name) if name in points[name][3] else 0))
    for name in order:
        options, files, given_here, held_in = points[name]
        folder = root / name / label
        # The slices to run in this folder: those that an asked point has here.
        wanted = [
            piece
            for k, piece in enumerate(workflow.slices)
            if k in runs and any(points[other][3][k] == name for other in asked)
        ]
        # The scanned options of the point that make it a measurement of its
        # own: those a slice that measures reads, all of them without slices.
        measured = {
            key: options[key]
            for key in scan
            if not workflow.slices
            or any(workflow.slices[j].new_events for j in slices.owners(workflow.slices, key))
        }
        record = {"seed": seed, "point": name, "same_seeds": same_seeds, "measured": measured}
        if not workflow.seeds:
            record = {"point": name}
        # Whether the chain goes on to its last stage when the jobs are done.
        analysed = bool(workflow.analysis) and kwargs.get("until") in (None, "analysis")
        if workflow.analysis:
            record["analysis"] = analysed
        if workflow.slices:
            # Its view: the scanned options with their values, every one of
            # them; DEFAULT for an experiment that scans nothing. A point that
            # only holds slices of the points asked has none.
            titles = config.get("names", {})
            view = (
                "_".join(
                    f"{_label(key, titles, workflow)}_{_text(options.get(key, given_here.get(key)))}" for key in scan
                )
                or DEFAULT
            )
            record["view"] = view if name in asked else None
        record.update(commit=commit, options=options, files=files)
        if workflow.settings:
            record["settings"] = workflow.settings(kwargs)
        for k, piece in enumerate(workflow.slices):
            record.setdefault("slices", {})[piece.name] = _read_by(workflow, kwargs, given_here, k)
            record.setdefault("held_in", {})[piece.name] = held_in[k]
        _stamp(workflow, record, options, files)
        record = json.loads(json.dumps(record))
        old = _read(folder / "run.json")
        why = _outdated(workflow, old, record) if old else None
        if workflow.slices and old and old.get("commit") != commit:
            print(f"note: {folder} was run by {old.get('commit')}, the code is {commit} now; what it wrote is used")
        # With slices: when some slice of the folder, a shared one aside, reads
        # what it read in the old run and nothing else of the record changed,
        # the old run is not out of date; the slices in `again`, those that read
        # something else, are run again in it.
        everything = set(range(len(workflow.slices)))
        again = slices.to_run_again(workflow.slices, old, record) if old else everything
        own = {k for k, piece in enumerate(workflow.slices) if not piece.shared}
        rest = {key: value for key, value in record.items() if key not in SLICED}
        if workflow.slices and not own <= again and _outdated(workflow, {key: old.get(key) for key in rest}, rest) is None:
            why = None
        stale = why is not None
        left = [
            i
            for i in range(kwargs.get("jobs") or 1)
            if stale or not workflow.seeds or not _done(folder, i).exists()
        ]
        if workflow.slices:
            to_run = slices.left(
                workflow.slices, folder, range(kwargs.get("jobs") or 1), everything if stale else again
            )
            left = sorted(set().union(*(to_run[piece.name] for piece in wanted)))
        aside = "kept aside" if workflow.seeds else "replaced"
        print(f"{folder}: jobs {left}" + (f", the old run is {aside}: {why}" if stale else ""))
        width = max([12, *(len(piece.name) + 1 for piece in wanted)])  # a long name keeps a space after it
        for piece in wanted:
            print(f"  {piece.name:<{width}}" + (f"jobs {to_run[piece.name]}" if to_run[piece.name] else "reused"))
        again = again if old and not stale else set()  # nothing to run again in place
        # What the jobs wrote into run.json themselves stays while the run is not out of date.
        if not stale:
            record = {**{key: old[key] for key in old if key not in record}, **record}
        # The slices that those run here read and that do not run here, each
        # with the seed folder that holds it.
        here = {workflow.slices.index(piece) for piece in wanted}
        read = set().union(*(slices.upstream(workflow.slices, k) for k in here)) - here
        before = [(workflow.slices[k].name, root / held_in[k] / label) for k in sorted(read)]
        names = ",".join(piece.name for piece in wanted)
        # The shared slices this point reads: those a slice it runs is or reads.
        shared = [
            piece
            for k, piece in enumerate(workflow.slices)
            if piece.shared
            and any(
                to_run[later.name]
                for later in wanted
                if (j := workflow.slices.index(later)) == k or k in slices.upstream(workflow.slices, j)
            )
        ]
        run_again = [piece for k, piece in enumerate(workflow.slices) if k in again]
        todo.append((folder, left, stale, record, run_again, before, names, (shared, options, files)))
    if kwargs["dry_run"]:
        return None
    if commit.endswith("+dirty"):
        print("warning: the code has uncommitted changes; run.json records this")

    # No other command writes these folders while this one does; one that
    # holds one of them stops this command before the config is written.
    held = []
    try:
        for folder, *_ in todo:
            held.append(_lock(_folder_lock(folder), folder))
    except BaseException:
        _close(held)
        raise
    try:
        _write_config(workflow, kwargs, register, root, config, identity, given, scan, same_seeds, address, fixed_here)
    except BaseException:
        _close(held)
        raise
    release()
    try:
        # On the cluster, a shared slice made for this command starts it again
        # in its seed folder when it is done.
        waiting = {
            "command": _without_seed_folder(kwargs.get("_argv") or []),
            "cwd": os.getcwd(),
            "seed_folder": label or None,
        }
        _make_shared(
            workflow, {**kwargs, "_waiting": waiting} if kwargs["batch"] else kwargs, [need for *_, need in todo], root
        )
        for folder, left, stale, record, run_again, before, names, (shared, options, files) in todo:
            _stamp(workflow, record, options, files)  # of what was made just now
        # The table is of the points of the experiment: a command that runs
        # points of its own beside them (register=False) leaves it as it is.
        if workflow.slices and register:
            _write_points(workflow, kwargs, root, scan, asked, todo)
        failed = _run_points(workflow, kwargs, todo, label)
    finally:
        _close(held)
    if failed:
        raise SystemExit("\n".join([f"{len(failed)} of {len(todo)} points failed:", *failed]))
    if workflow.analysis and kwargs.get("until") in (None, "analysis"):
        workflow.analysis(root)
    return None


def complete_points(root) -> list[str]:
    """The points of points.json whose jobs are all done: every node the
    table lists for them is there, or the job was ended before it."""
    root = Path(root)
    done = []
    for name, row in _read(root / "points.json").items():
        count = max(map(len, row["nodes"].values()))
        whole = True
        for index in range(count):
            states = [
                nodes.read(place)["state"] if ((place := nodes.node_dir(root, stage_of(piece), listed[index])) / "node.json").is_file() else None
                for piece, listed in row["nodes"].items()
            ]
            whole = whole and (None not in states or "ended" in states)
        if whole:
            done.append(name)
    return done


def _write_points(workflow, kwargs, root, scan, asked, todo) -> None:
    """points.json of the experiment: per point asked, the values of the
    scanned options and the node of each slice of each job; and the views of
    the nodes that are there already. An experiment that scans has no point
    DEFAULT: none of its points is the one it would run without the scan."""
    records = {record["point"]: record for _, _, _, record, *_ in todo}
    default = Path(root) / "points" / DEFAULT
    if default.is_symlink():
        default.unlink()
    elif scan and default.is_dir():
        shutil.rmtree(default)  # the view of the experiment before it scanned: links only
    rows: dict = {}
    for name in asked:
        record = records[name]
        table: dict = {}
        for index in range(kwargs.get("jobs") or 1):
            for piece, (_, node) in job_nodes(workflow, record, index).items():
                table.setdefault(piece, []).append(node)
                place = nodes.node_dir(root, stage_of(piece), node)
                if (place / "node.json").is_file():
                    nodes.link_view(root, record["view"], piece, place, job=index)
        measures = {
            piece: measured_thing(workflow, inputs) for piece, (inputs, _) in job_nodes(workflow, record, 0).items()
        }
        rows[record["view"]] = {
            "values": {key: record["options"].get(key) for key in scan},
            "nodes": table,
            "measures": measures,
        }
    root.mkdir(parents=True, exist_ok=True)
    nodes.write_points(root, rows)
    # The views of points the experiment no longer has go: they hold links only.
    for old in default.parent.iterdir() if default.parent.is_dir() else ():
        if old.name not in rows:
            old.unlink() if old.is_symlink() else shutil.rmtree(old)


def _close(handles) -> None:
    for handle in handles:
        if handle is not None:
            handle.close()


def _write_config(workflow, kwargs, register, root, config, identity, given, scan, same_seeds, address, fixed_here):
    """config.json: made with what this command gives when there is none;
    else what --scan and --set give joins it."""
    if not config:
        root.mkdir(parents=True, exist_ok=True)
        new = {**identity, "set": given if register else {}, "scan": scan if register else {}}
        if workflow.seeds:
            new["same_seeds"] = same_seeds
        if workflow.sections:
            # written whole: what the experiment takes where nothing is given
            new["set"] = {**workflow.defaults, **new["set"]}
        _write(root / "config.json", written_config(workflow, new))
    elif register and (kwargs["scan"] or fixed_here):
        # A scan or a --set given to an experiment that exists joins its config,
        # under its address as _points reads it, in place of what the config
        # had there; later commands repeat it.
        # A key given leaves out what the config had for it and for the
        # other keys of its group, scanned or set.
        written = dict(config.get("scan", {}))
        kept = dict(config.get("set", {}))

        def leave_out(key) -> None:
            nonlocal written, kept
            group = next((group for group in workflow.exclusive if key in group), (key,))
            written = {old: v for old, v in written.items() if address.get(old, old) not in group}
            kept = {old: v for old, v in kept.items() if address.get(old, old) not in group}

        for item in kwargs["scan"]:
            key, _, values = item.partition("=")
            key = address.get(key, key)
            leave_out(key)
            written[key] = [_parse(value) for value in values.split(",")]
        for key in fixed_here:
            leave_out(key)
        # Another component in a slot is another file: the keys that were set
        # inside the one before it go, but for those this command gives.
        now = {*fixed_here, *written} - set(config.get("scan", {}))
        for slot in workflow.slots:
            if slot in fixed_here or any(address.get(item.partition("=")[0], item.partition("=")[0]) == slot for item in kwargs["scan"]):
                kept = {key: v for key, v in kept.items() if not key.startswith(slot + ".") or key in fixed_here}
                written = {key: v for key, v in written.items() if not key.startswith(slot + ".") or key in now}
        _write(root / "config.json", written_config(workflow, {**config, "scan": written, "set": {**kept, **fixed_here}}))


def _run_points(workflow, kwargs, todo, label) -> list:
    """Start the jobs of every point of `todo`, in folders this command
    holds; what failed, a line each."""
    failed: list = []
    for folder, left, stale, record, run_again, before, names, (shared, options, files) in todo:
        if (stale or run_again) and (running := _running_jobs(folder)):
            # A job that runs read the old settings: the folder stays as it is.
            said = (
                f"{folder}: jobs {running} run there now; the new settings did not take effect "
                "there; run the command again when they are done"
            )
            print(said)
            failed.append(f"  {said}")
            continue
        slices.forget(run_again, folder)
        if workflow.slices and not stale and (folder / "batch").is_dir():
            # A job killed after the mark of its last slice and before its own.
            held_by = _slice_folders(workflow, record, folder)
            for i in range(kwargs.get("jobs") or 1):
                if all(slices.mark(held_by[piece.name], i, piece.name).exists() for piece in workflow.slices):
                    _done(folder, i).touch()
        unready = [
            piece.name
            for piece in shared
            if piece.shared.ready(flat(workflow, options, stage_of(piece.name)), files) is None
        ]
        waiting = [
            i
            for i in left
            if unready or any(not slices.mark(place, i, piece).exists() for piece, place in before)
        ]
        if waiting:
            left = [i for i in left if i not in waiting]
            needed = ", ".join(
                [f"{name}, shared with other experiments" for name in unready]
                + [f"{piece} in {place}" for piece, place in before]
            )
            print(f"{folder}: jobs {waiting} wait for {needed}; run the command again when it is done")
            failed.append(f"  {folder}: jobs {waiting} wait for {needed}")
        if stale and workflow.seeds:
            folder.rename(folder.with_name(f"{label}_{time.strftime('%Y_%m%d_%H%M%S')}"))
        elif stale:  # a point without seeds has no folder of its own to set aside
            slices.forget(workflow.slices, folder)
            for i in left:
                _done(folder, i).unlink(missing_ok=True)
        if kwargs.get("_waiting") is not None and left:
            # The commands that wait for this job, kept over a new run of it.
            listed = _read(folder / "run.json").get("waiting", [])
            record["waiting"] = listed + [kwargs["_waiting"]] * (kwargs["_waiting"] not in listed)
        if left or (waiting and kwargs["batch"]):  # a run whose jobs all wait goes on from its record
            (folder / "batch").mkdir(parents=True, exist_ok=True)
            # The most jobs the seed folder was asked for, for raser status;
            # it does not make a run out of date: -s 5 after -s 3 adds two.
            record["jobs"] = max(record.get("jobs", 0), kwargs.get("jobs") or 1)
            if kwargs["batch"] and os.environ.get("RASER_SUBMIT_QUEUE"):
                # Jobs the host submits are not recorded: a job that started the
                # command again would submit them all once more.
                record.pop("command", None)
            elif kwargs["batch"]:
                # What a job on the cluster starts again when it is done.
                record["command"] = _without_seed_folder(kwargs.get("_argv") or [])
                record["cwd"] = os.getcwd()
                left = _not_submitted(folder, left, names.split(",") if workflow.slices else ["job"])
            _write(folder / "run.json", record)
            if not left:
                continue
            try:
                _start(workflow, {**kwargs, "job_slices": names}, folder, left, alone=len(todo) == 1)
            except Exception as error:
                if len(todo) == 1:
                    raise
                # The points do not depend on each other: the rest still run.
                traceback.print_exc()
                failed.append(f"  {folder}: {error!r}")
    return failed


def _stamp(workflow, record, options, files) -> None:
    """Write into what each slice of `record` reads the stamps of the shared
    slices it reads, itself or through others: a shared slice made again
    runs it again."""
    for k, piece in enumerate(workflow.slices):
        shared = [j for j in sorted(slices.upstream(workflow.slices, k) | {k}) if workflow.slices[j].shared]
        if shared:
            record["slices"][piece.name]["shared"] = {
                workflow.slices[j].name: workflow.slices[j].shared.stamp(
                    flat(workflow, options, stage_of(workflow.slices[j].name)), files
                )
                for j in shared
            }


def _make_shared(workflow, kwargs, needs, root) -> None:
    """Make what the points share and is not ready, once for all the points
    that read the same of it. `needs` holds, per point, (its shared slices,
    its options, its files). A shared slice that another command is making
    is left to it: the points wait."""
    started = set()
    for shared, options, files in needs:
        for piece in shared:
            same = json.dumps([piece.name, {key: options.get(key) for key in piece.keys}, files.get("device")])
            options = flat(workflow, options, stage_of(piece.name))
            if same not in started and piece.shared.ready(options, files) is None:
                started.add(same)
                try:
                    piece.shared.start(kwargs, options, files)
                except Running as running:  # another command makes it: the point waits
                    print(f"{piece.name}: {running}")
                    continue
                if not kwargs["batch"] and not kwargs["dry_run"] and piece.shared.ready(options, files) is None:
                    raise RuntimeError(
                        f"{piece.name} was made in this process and is still not ready for a point of "
                        f"{root}: waiting would not help"
                    )


def make_shared(workflow, kwargs, root) -> None:
    """What every point of the experiment in `root` shares and is not ready,
    made as a command of the experiment makes it before its jobs start, as
    raser field <experiment> does; no job of the experiment runs. Its
    --scan and --set choose the points, for this command only."""
    config = read_config(workflow, root)
    address = {name: key for key, name in config.get("names", {}).items()}
    given = {}
    for item in kwargs.get("set") or []:
        key, _, value = item.partition("=")
        given[address.get(key, key)] = _parse(value)
    _, points, asked = _points(workflow, kwargs, config, given)
    shared = [piece for piece in workflow.slices if piece.shared]
    needs = [(shared, *points[name][:2]) for name in asked]
    if kwargs["dry_run"]:
        for _, options, files in needs:
            for piece in shared:
                seen = flat(workflow, options, stage_of(piece.name))
                state = "ready" if piece.shared.ready(seen, files) is not None else "to be made"
                print(f"{root}: {piece.name} {state} for {options}")
        return
    _make_shared(workflow, kwargs, needs, root)


def finished(workflow, kwargs, root) -> list[tuple[str, dict, list[tuple[Path, int]]]]:
    """The points of the experiment in `root`, each with its folder name, its
    options and the finished (seed folder, job index) pairs.

    A point's jobs come from all its seed folders that ran with the options and
    files the experiment has now, whatever their seed and commit. Folders kept
    aside by a rerun are left out: their name is not seed_<their seed>."""
    _, points, asked = _points(workflow, kwargs, read_config(workflow, root), {})
    result = []
    for name in asked:
        options, files = points[name][:2]
        now = json.loads(json.dumps({"options": options, "files": files}))
        done = []
        for path in sorted((root / name).glob("*/run.json" if workflow.seeds else "run.json")):
            old, label = _read(path), path.parent.name
            # A seed folder kept aside by a rerun is named seed_<n>_<time>.
            kept = workflow.seeds and label.startswith("seed_") and label != f"seed_{old['seed']}"
            any_code = {**old, "commit": ""}  # a finished run counts whatever its commit
            if not kept and _outdated(workflow, any_code, {**any_code, **now}) is None:
                marks = sorted((path.parent / "batch").glob("job_*.done"))
                done += [(path.parent, int(mark.stem.split("_")[1])) for mark in marks]
        result.append((name, options, done))
    return result


def finished_in(root) -> list[tuple[str, dict, list[tuple[Path, int]]]]:
    """`finished` for the experiment in the folder `root`, whichever command
    ran it: its config.json names the workflow and the device."""
    config = _read(Path(root) / "config.json")
    if "workflow" not in config:
        raise ValueError(f"{root}: not an experiment folder, no config.json that names a workflow")
    if config["workflow"] not in WORKFLOWS:
        raise ValueError(f"{root}: no command runs its workflow {config['workflow']!r}")
    kwargs = {"det_name": config.get("device"), "scan": []}
    return finished(WORKFLOWS[config["workflow"]], kwargs, Path(root))


def measured_thing(workflow, inputs) -> str:
    """The fingerprint of what a node measured, from its inputs: the same
    for nodes that differ only in how much was measured or drawn
    (Slice.counts), in their seed and in the nodes they read. The stamps of
    the shared slices they read, as a field, are part of it."""
    counts = {key for piece in workflow.slices for key in piece.counts}
    names = {piece.name for piece in workflow.slices if not piece.shared}
    return nodes.fingerprint(
        {
            "slice": inputs["slice"],
            "settings": {key: value for key, value in inputs["settings"].items() if key not in counts},
            "components": inputs["components"],
            "shared": {key: value for key, value in inputs["upstream"].items() if key not in names},
            "command_line": inputs.get("command_line"),
        }
    )


def jobs_of_points(root) -> list[tuple[str, dict, list[tuple[Path, dict]], list[tuple[int, dict]]]]:
    """The points of the experiment in `root` as its last command left them
    in points.json, each with its name, the values of its scanned options,
    the finished jobs that measured it and, for the screen, the finished
    jobs that measured something no point of the experiment measures now:
    (how many, the settings they have otherwise). A job is (the experiment
    folder, slice -> its node).

    The jobs of a point are all those in the nodes of the experiment that
    measured what the point measures (points.json: "measures"), whichever
    run, seed or number of events they are of: running a point again with
    another seed adds to it. A job is finished when every slice of it has
    its node, or one of them ended it, as a job that recorded no event. The
    events of the root of a job, its deposits, are counted once: of two
    chains that read the same deposits, as one drawn and one not, the first
    by the names of its nodes is taken."""
    root = Path(root)
    table = _read(root / "points.json")
    if not table:
        raise ValueError(f"{root}: no points.json; run the experiment first")
    config = _read(root / "config.json")
    workflow = WORKFLOWS[config["workflow"]]
    own = [piece for piece in workflow.slices if not piece.shared]
    names = [piece.name for piece in own]
    counts = {key for piece in workflow.slices for key in piece.counts}
    written: dict = {name: {} for name in names}  # slice -> node -> its node.json
    for name in names:
        for path in sorted((root / "nodes" / stage_of(name)).glob("*/node.json")):
            record = nodes.read(path.parent)
            if record["inputs"].get("slice") == name:
                written[name][record["node"]] = record

    def finished(chain) -> bool:
        ended = any(written[name][node]["state"] == "ended" for name, node in chain.items())
        return len(chain) == len(names) or ended

    def roots(chain) -> tuple:
        return tuple(chain[piece.name] for piece in own if not _needs(own, piece) and piece.name in chain)

    def settings(chain) -> dict:
        """What a job was set to, of what says what is measured: its last
        slice holds the settings of those it reads."""
        last = [name for name in names if name in chain][-1]
        given = written[last][chain[last]]["inputs"]["settings"]
        return {key: value for key, value in given.items() if key not in counts}

    everything = [chain for chain in _chains(own, written) if roots(chain) and finished(chain)]

    def measures(chain, row) -> bool:
        return all(
            measured_thing(workflow, written[name][node]["inputs"]) == row["measures"][name]
            for name, node in chain.items()
        )

    # A job of another point of the experiment is counted there: it is not
    # set apart here. Set apart are the jobs that no point of now measures.
    of_no_point = [chain for chain in everything if not any(measures(chain, row) for row in table.values())]
    result = []
    for point, row in table.items():
        mine: dict = {}  # the deposits of a job -> the job: two chains on the same deposits are one
        for chain in everything:
            if measures(chain, row):
                mine.setdefault(roots(chain), chain)
        elsewhere = of_no_point
        here = settings(next(iter(mine.values()))) if mine else {}
        apart: dict = {}  # what they are set to otherwise -> their deposits
        for chain in elsewhere:
            theirs = settings(chain)
            differ = {name: theirs.get(name) for name in sorted(set(theirs) | set(here)) if theirs.get(name) != here.get(name)}
            apart.setdefault(json.dumps(differ if mine else {}, sort_keys=True, default=str), set()).add(roots(chain))
        jobs = [(root, chain) for _, chain in sorted(mine.items())]
        result.append((point, row["values"], jobs, [(len(found), json.loads(text)) for text, found in apart.items()]))
    return result


def _needs(own, piece) -> list[str]:
    """The slices of `own` that `piece` reads itself."""
    names = [other.name for other in own]
    k = names.index(piece.name)
    needs = piece.needs if piece.needs is not None else names[max(k - 1, 0) : k]
    return [name for name in needs if name in names]


def _chains(own, same) -> list[dict]:
    """The jobs in the nodes `same` (slice -> node -> node.json): each a
    slice -> node, from a node of a slice that no other slice reads up to
    the nodes it reads. A slice whose node is not there is left out."""
    read = {name for piece in own for name in _needs(own, piece)}
    last = [piece for piece in own if piece.name not in read]
    chains = []

    def follow(piece, node, chain) -> None:
        chain[piece.name] = node
        for name in _needs(own, piece):
            above = same[piece.name][node]["inputs"]["upstream"].get(name)
            if above in same[name]:
                follow(next(other for other in own if other.name == name), above, chain)

    seen = set()
    for piece in last:
        for node in same[piece.name]:
            chain: dict = {}
            follow(piece, node, chain)
            chains.append(chain)
            seen.update(chain.items())
    # A job that an early slice ended has no node of a last slice.
    for piece in reversed(own):
        for node in same[piece.name]:
            if (piece.name, node) not in seen:
                chain = {}
                follow(piece, node, chain)
                chains.append(chain)
                seen.update(chain.items())
    return chains


def batches(jobs) -> str:
    """The jobs of a point by the run that wrote them, for the screen: its
    seed, or the time of a run that was given none."""
    count: dict = {}
    for root, chain in jobs:
        name, node = sorted(chain.items())[0]
        job = nodes.read(nodes.node_dir(root, stage_of(name), node))["job"]
        run = str(job.get("run") or f"seed_{job['master_seed']}")
        label = f"seed {run[5:]}" if run.startswith("seed_") else f"the run of {run}, without --seed"
        count[label] = count.get(label, 0) + 1
    return ", ".join(f"{label}: {number} job{'s' * (number != 1)}" for label, number in sorted(count.items()))


def set_apart(others) -> list[str]:
    """A line for each group of finished jobs a point does not count: how
    many, and what they were set to otherwise."""
    lines = []
    for number, differ in others:
        what = ", ".join(f"{key}={value}" for key, value in differ.items()) or "other files or another field"
        lines.append(f"{number} job{'s' * (number != 1)} measured something else and {'are' if number != 1 else 'is'} not counted: {what}")
    return lines


def _outdated(workflow, old, record) -> str | None:
    """What makes the run that wrote `old` out of date for `record`, or None."""
    # A run recorded without its settings was made with the default ones:
    # those of a command line that gives none.
    default = workflow.settings({}) if workflow.settings else None
    if old.get("settings", default) != record.get("settings"):
        return "other settings of the command line"
    if workflow.outdated:
        return workflow.outdated(old, record)
    # The nodes of a run in slices are named by what they read, not by the
    # code that wrote them: another version of the code uses them, with a note.
    if record["commit"].endswith("+dirty") and not workflow.slices:
        return "the code has uncommitted changes"
    # Nor does the name of the view of a point change what its jobs wrote.
    # Nor does whether the chain goes on to the analysis: the jobs are the same.
    changed = [
        key
        for key in record
        if old.get(key) != record[key] and not (workflow.slices and key in ("commit", "view", "analysis"))
    ]
    return "other " + ", ".join(changed) if changed else None


def _points(workflow, kwargs, config, given) -> tuple[dict, dict]:
    """The scanned options and the points of an experiment.

    One point for every combination of the scanned values. A point's folder is
    named by every scanned option and its value, as its view is."""
    # Another component in a slot is another file: what config.json set or
    # scanned inside the one before it is not read by this command.
    replaced = tuple(
        slot + "."
        for slot in workflow.slots
        if slot in given or any(item.partition("=")[0] == slot for item in kwargs["scan"])
    )
    if replaced:
        config = {
            **config,
            **{part: {key: v for key, v in config.get(part, {}).items() if not key.startswith(replaced)} for part in ("set", "scan")},
        }
    fixed = {**workflow.defaults, **config.get("set", {}), **given}
    if workflow.sections:
        # every setting is there, None where nothing sets it, as config.json holds them:
        # the first command and the ones after it read the same
        fixed = {**dict.fromkeys(workflow.keys), **fixed}
    # Of a group of keys of which one is given, the highest layer that gives
    # one decides; the others of the group from the layers below are left out.
    layers = (("the command line", given), ('the "set" of config.json', config.get("set", {})), ("the defaults", workflow.defaults))
    for group in workflow.exclusive:
        top = next((layer for where, layer in layers if _one_of_each_group([group], layer, where)), None)
        for key in group:
            if top is not None and top.get(key) is None:
                fixed.pop(key, None)
    same_seeds = kwargs.get("same_seeds") or config.get("same_seeds", False)
    # "names" in the config gives an address a short name: the scan may be
    # written with it, and the folders are named by it.
    names = config.get("names", {})
    address = {name: key for key, name in names.items()}
    scan = {address.get(key, key): values for key, values in config.get("scan", {}).items()}
    for item in kwargs["scan"]:
        key, _, values = item.partition("=")
        scan[address.get(key, key)] = [_parse(value) for value in values.split(",")]
    scan = {key: values for key, values in scan.items() if key not in given}
    # A key of a group that is scanned is the one of its group: the others'
    # values below the command line are left out. The command line decides
    # over a scan of the config.
    on_command_line = {address.get(item.partition("=")[0], item.partition("=")[0]) for item in kwargs["scan"]}
    for group in workflow.exclusive:
        scanned = [key for key in group if key in scan]
        if any(key in given for key in group):
            for key in scanned:
                if key in on_command_line:
                    raise ValueError(f"{key} is scanned and another key of its group is given; give one of them")
                del scan[key]
        elif len(scanned) > 1:
            raise ValueError(f"{scanned[0]} and {scanned[1]} are scanned at once; scan one of them")
        elif scanned:
            for key in group:
                if key != scanned[0]:
                    fixed.pop(key, None)
    for key, values in scan.items():
        _check_folder_names(key, values)
    label = {key: _label(key, names, workflow) for key in scan}
    for key, other in itertools.combinations(scan, 2):
        if label[key] == label[other]:
            raise ValueError(
                f"{key} and {other} would both be {label[key]!r} in the names of folders: "
                'give one of them a name under "names" in config.json'
            )
    # A scanned address that no file of the run holds is told before any point is made.
    _point(
        workflow, kwargs, {**dict.fromkeys(key for key in scan if "." in key and key not in workflow.keys), **fixed}
    )
    # folder inside the experiment -> (options, files, the options given, per
    # slice the folder of the point whose run holds it)
    points: dict = {}

    def point(values) -> str:
        """The folder of the point where the scanned options have `values`.
        Each of its slices is held by the point that leaves out the scanned
        options the slice and the ones before it do not read, as far as those
        options do not make a measurement of its own (Slice.new_events)."""
        given_here = {**fixed, **values}
        options, files = _point(workflow, kwargs, given_here)
        name = "_".join(f"{label[key]}_{_text(options[key])}" for key in values)
        if name in points and any(points[name][0].get(key) != options.get(key) for key in scan):
            other = {key: points[name][0].get(key) for key in scan}
            raise ValueError(
                f"{other} and {({key: options.get(key) for key in scan})} would both be the folder {name!r}; "
                "scan values that do not hold the names of other scanned options"
            )
        if name not in points:
            points[name] = (options, files, given_here, held_in := [])
            for k in range(len(workflow.slices)):
                read = {
                    key: v
                    for key, v in values.items()
                    if slices.reads(workflow.slices, key, k)
                    or (not same_seeds and any(workflow.slices[j].new_events for j in slices.owners(workflow.slices, key)))
                }
                held_in.append(name if len(read) == len(values) else point(read))
        return name

    asked = [point(dict(zip(scan, combination))) for combination in itertools.product(*scan.values())]
    return scan, points, list(dict.fromkeys(asked))


def _point(workflow, kwargs, options) -> tuple[dict, dict]:
    """The options and json files of one run, from the options that were set."""
    options = dict(options)

    # The json files the run uses: the device, and the files its options name.
    files = {}
    if workflow.device and len(workflow.devices) > 1:
        for name, (device, _) in workflow.devices.items():
            files[name] = {"device": device_json(kwargs["det_name"] if device is None else device)}
    elif workflow.device:
        files["device"] = device_json(kwargs["det_name"])
    for kind, key in workflow.components.items():
        if options.get(key) is None:
            raise ValueError(f"config.json has no {key}: it names the {kind} of the experiment")
        read = workflow.readers.get(kind)
        files[kind] = read(options[key]) if read else load_component(kind, options[key])[1]

    # An option that is a value inside a file, such as the bias in the device:
    # given, it is written into the file; not given, it takes the file's value.
    # An option may also be named by its address, "afe.stages.first.R1.ohm":
    # the kind of file, then the keys down to a value the file has.
    addresses = {key: in_file(workflow, key) for key in options if "." in key and key not in workflow.keys}
    for key, address in {**addresses, **workflow.in_file}.items():
        *steps, last = address.split(".")
        place, walked = files, "the files of this run"
        for step in steps:
            if not isinstance(place, dict) or step not in place:
                raise ValueError(f"{address}: no {step!r} in {walked}")
            place, walked = place[step], step if place is files else f"{walked}.{step}"
        if key in addresses and (not isinstance(place, dict) or last not in place):
            raise ValueError(f"{address}: no {last!r} in {walked}")
        if options.get(key) is None:
            options[key] = place[last]
        else:
            place[last] = options[key]
    return options, files


SLICED = ("options", "files", "slices")  # the part of a record that the slices judge


def _read_by(workflow, kwargs, given, k) -> dict:
    """The options and files that the k-th slice reads, itself or through the
    slices it reads, when the options `given` were set. The options of the
    other slices are not given here: the files they name are left out, and a
    value they would write into a file stays as the file has it."""
    mine = {key for key in [*given, *workflow.keys] if slices.reads(workflow.slices, key, k)}
    named = {kind: key for kind, key in workflow.components.items() if key in mine}
    options, files = _point(
        replace(workflow, components=named),
        kwargs,
        {key: value for key, value in given.items() if key in mine},
    )
    return {"options": {key: options[key] for key in options if key in mine}, "files": files}


def _start(workflow, kwargs, folder, left, alone) -> None:
    """Start the jobs `left` of a seed folder; `alone` when the command has no other point."""
    single = kwargs.get("jobs") is None and not kwargs["batch"]
    if single and alone:
        with _logged(Path(folder) / "batch" / "job_0.log"):
            _run_job(workflow, {**kwargs, "job_dir": str(folder)})  # in this process
        return
    tail = workflow.words[1:]
    if workflow.device:
        tail.append(kwargs["det_name"])
    if workflow.command:
        tail += workflow.command(kwargs)
    if kwargs.get("job_slices"):
        tail += ["--job-slices", kwargs["job_slices"]]
    if single:  # one point among several: a process of its own, as on the cluster
        _own_process(workflow, kwargs, [*kwargs["_entry_command_prefix"], *tail, "--job-dir", str(folder)])
        return
    names = kwargs["job_slices"].split(",") if kwargs.get("job_slices") else ["job"]
    if kwargs["batch"] and os.environ.get("RASER_SUBMIT_QUEUE"):
        print(
            "the jobs go to the queue the host submits: a job that waits for others is not "
            "started again by itself; run the command again when those are done"
        )
    jobs.run_indexed_jobs(
        kwargs["_entry_command_prefix"],
        [*tail, "--job-dir", str(folder)],
        len(left),
        use_cluster=kwargs["batch"],
        mem=kwargs["mem"],
        destination=workflow.words[0],
        indices=left,
        log_folder=None if kwargs["batch"] else Path(folder) / "batch",
        submitted=(lambda index, job: _note_submitted(folder, index, names, job)) if kwargs["batch"] else None,
    )


class _Both:
    """A stream that writes to the terminal's stream and to a log."""

    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, text):
        self.log.write(text)
        return self.stream.write(text)

    def flush(self):
        self.log.flush()
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


@contextmanager
def _logged(log):
    """What Python prints while a job runs in this process goes to the
    terminal and to `log`, as for a job in a process of its own; a failure
    leaves its traceback in the log. What Geant4 and ROOT print from C++
    goes to the terminal only."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as file:
        out, err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Both(out, file), _Both(err, file)
        try:
            yield
        except BaseException:
            file.write(traceback.format_exc())
            raise
        finally:
            sys.stdout, sys.stderr = out, err


def _own_process(workflow, kwargs, words) -> None:
    """Run the command `words`, the single job of one point, in another
    process; what it prints goes to the terminal and to batch/job_0.log."""
    log = Path(words[-1]) / "batch" / "job_0.log"
    try:
        jobs._run_local_job(tuple(words), log)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"the job failed: {jobs.last_line(log)} ({log})") from error


def _run_job(workflow, kwargs):
    """One job: its options, files and seed come from the run.json of its seed folder.

    The job's seed is a hash of the run's seed, the job index and the scanned
    options of the point that measure, so points that measure something else
    draw different random numbers, whatever their names; with same_seeds the
    options are left out and the jobs with one index draw the same numbers in
    every point."""
    folder, index = Path(kwargs["job_dir"]), kwargs.get("job_index") or 0
    # The same job run twice at once, as when it is submitted twice: the second stops.
    held = _lock(folder / "batch" / f"job_{index}.lock", f"job {index} of {folder}")
    try:
        _run_one_job(workflow, kwargs, folder, index)
    finally:
        if held is not None:
            held.close()


def _run_one_job(workflow, kwargs, folder, index):
    record = _read(folder / "run.json")
    for line in waited_for_by(record):
        print(line)
    options = {**kwargs, **record["options"]}
    options["_run_path"] = str(folder)
    options["_run_batch_path"] = str(folder / "batch")
    options["_files"] = record["files"]

    def seed(piece=None) -> None:
        """Seed the generators for this job, or for one slice of it. A slice
        is run by the point that holds it, so the points that read what it
        wrote all have the numbers it drew there."""
        from raser.core.seeding import seed_generators  # loads ROOT

        job = nodes.job_seed(record["seed"], index, record["measured"], record["same_seeds"])
        options["seed"] = job if piece is None else nodes.stage_seed(job, piece)
        seed_generators(options["seed"])

    if not workflow.slices:
        if workflow.seeds:
            seed()
        workflow.job(flat(workflow, options, None))
        _done(folder, index).touch()
        _submitted(folder, index, "job").unlink(missing_ok=True)
        _start_again(workflow, record, folder, progress=True)
        return
    folders = _slice_folders(workflow, record, folder)
    root = experiment_of(folder, record, workflow.seeds)
    planned = job_nodes(workflow, record, index)
    # Where each slice of the job writes and the later ones read: its node,
    # <node>.part while the slice writes it.
    options["_node_paths"] = {
        name: str(nodes.node_dir(root, stage_of(name), node)) for name, (_, node) in planned.items()
    }
    wanted = (kwargs.get("job_slices") or ",".join(folders)).split(",")
    view = record["view"]

    def call(piece, options):
        """Run a slice into its node, or take the node that is there: what a
        slice wrote for these inputs is not written twice, whichever point,
        run or version of the code wrote it."""
        if piece.name not in planned:
            return piece.run(flat(workflow, options, stage_of(piece.name)))  # shared: held outside the experiment
        inputs, node = planned[piece.name]
        stage = stage_of(piece.name)
        place = nodes.node_dir(root, stage, node)
        held = None
        try:
            written = nodes.found(place, inputs)
            if written is None:
                held = nodes.lock(place)
                written = nodes.found(place, inputs)  # written while this job waited for the lock
            if written is None:
                noted = {
                    "job": {"index": index, "master_seed": record.get("seed"), "run": folder.name},
                    "code": record["commit"],
                }
                part = nodes.start(place, stage, inputs, noted)
                options["_node_paths"][piece.name] = str(part)
                try:
                    left, state = piece.run(flat(workflow, options, stage_of(piece.name))) or {}, "done"
                except slices.Ended:
                    left, state = {}, "ended"
                finally:
                    options["_node_paths"][piece.name] = str(place)
                nodes.finish(part, state, left)
                written = nodes.read(place)
            elif note := nodes.code_differs(written, record["commit"]):
                print(note)
        finally:
            if held is not None:
                held.close()
        return {**written["notes"], "node": node, **({"ended": True} if written["state"] == "ended" else {})}

    def before(piece) -> None:
        if workflow.seeds:
            seed(piece.name)

    read = _what_a_job_reads(record)

    def publish(piece) -> bool:
        """Whether `piece` ran by the run.json there is now. If another
        command changed it meanwhile, the node the slice wrote stays, named
        by what it read, and the slice has no mark in this run."""
        return _what_a_job_reads(_read(folder / "run.json")) == read

    marked = {name for name in wanted if slices.mark(folders[name], index, name).exists()}
    try:
        whole = slices.run(workflow.slices, folders, index, options, wanted, before, publish, call)
    finally:
        # The view of this point holds the nodes of the slices another point ran too.
        for name, (_, node) in planned.items():
            place = nodes.node_dir(root, stage_of(name), node)
            if view is not None and (place / "node.json").is_file():
                nodes.link_view(root, view, name, place, job=index)
    if whole:
        _done(folder, index).touch()
    now = {name for name in wanted if slices.mark(folders[name], index, name).exists()}
    for name in now:
        _submitted(folder, index, name).unlink(missing_ok=True)
    print(f"{JOB_ENDED}: {','.join(wanted)}")
    _start_again(workflow, record, folder, progress=bool(now - marked))
    if workflow.analysis and record.get("analysis") and os.environ.get("RASER_CLUSTER_JOB"):
        # On the cluster no command waits for the jobs: the one that ends
        # last finds the points whole. Another job that analyses now does it.
        try:
            workflow.analysis(root)
        except nodes.Running as running:
            print(running)


DEFAULT = "default"  # the view of the point of an experiment that scans nothing


def stage_of(name) -> str:
    """The stage of a slice: current of current.<position>."""
    return name.split(".")[0]


def experiment_of(folder, record, seeds=True) -> Path:
    """The experiment folder of the seed or point folder `folder` of a run."""
    root = Path(folder).parent if seeds else Path(folder)
    return root.parent if record["point"] else root


def job_nodes(workflow, record, index) -> dict:
    """slice -> (its inputs, its node) for job `index` of the run of `record`,
    for the slices the experiment holds itself. The inputs of a slice: the
    options and files it reads, the stamps of the shared slices it reads, the
    nodes of the slices it reads, and its seed."""
    job = None
    if workflow.seeds:
        job = nodes.job_seed(record["seed"], index, record["measured"], record["same_seeds"])
    names = [piece.name for piece in workflow.slices]
    found: dict = {}
    for k, piece in enumerate(workflow.slices):
        if piece.shared:
            continue
        reads = record["slices"][piece.name]
        needs = piece.needs if piece.needs is not None else names[max(k - 1, 0) : k]
        upstream = {name: found[name][1] for name in needs if name in found}
        inputs = {
            "slice": piece.name,
            "settings": reads["options"],
            "components": reads["files"],
            "upstream": {**reads.get("shared", {}), **upstream},
        }
        if "settings" in record:
            inputs["command_line"] = record["settings"]
        if job is None:
            inputs["job"] = index
        else:
            inputs["seed"] = nodes.stage_seed(job, piece.name)
        found[piece.name] = (inputs, nodes.node_of(inputs))
    return found


def _what_a_job_reads(record) -> str:
    """The part of a run.json that a job runs by, without what the command
    keeps there for itself: what the jobs asked for, and how to start it again."""
    return json.dumps({key: value for key, value in record.items() if key not in ("jobs", "command", "cwd")}, sort_keys=True)


# The line a job of slices prints when it ran them all; a log without it is
# of a job that failed, or that runs.
JOB_ENDED = "raser: the job ran its slices"


def _slice_folders(workflow, record, folder) -> dict[str, Path]:
    """The seed folder of each slice: the one of this run in the point that holds it."""
    root = folder.parent if workflow.seeds else folder
    root = root.parent if record["point"] else root
    label = folder.name if workflow.seeds else ""
    return {name: root / point / label for name, point in record["held_in"].items()}


def _submitted(folder, index, name) -> Path:
    """The record that the slice `name` of a job was submitted to the cluster."""
    return Path(folder) / "batch" / f"{name}_{index}.submitted"


def _note_submitted(folder, index, names, job) -> None:
    """Record that a job was submitted for its slices `names`: what the
    scheduler named it and when. A job queued for the host has no name yet:
    nothing is recorded, and nothing starts the command again for it."""
    if job is None:
        return
    text = json.dumps({"job": job, "time": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n"
    for name in names:
        # Written beside it, then linked in whole: a record is never there half
        # written, and one already there stays.
        path = _submitted(folder, index, name)
        part = path.with_name(f"{path.name}.{os.getpid()}.part")
        part.write_text(text)
        try:
            os.link(part, path)
        except FileExistsError:
            pass
        finally:
            part.unlink()


def _not_submitted(folder, left, names) -> list[int]:
    """The jobs of `left` to submit: not those already submitted for a slice
    they would run. On the login node the scheduler is asked about each: one
    it no more holds failed, its record goes and it is submitted again; one
    it cannot be asked about stays as it is. A job on the cluster that
    starts the command again submits only the jobs never submitted."""
    on_cluster = bool(os.environ.get("RASER_CLUSTER_JOB"))
    asked: dict = {}
    kept = []
    for index in left:
        records = [path for name in names if (path := _submitted(folder, index, name)).is_file()]
        if not records:
            kept.append(index)
            continue
        if on_cluster:
            continue
        job = json.loads(records[0].read_text())["job"]
        if job not in asked:
            asked[job] = scheduler.job_alive(job)
        if asked[job] is False:
            print(f"{folder}: job {index} ({job}) is no more on the cluster: it failed and is submitted again")
            for path in records:
                path.unlink(missing_ok=True)
            kept.append(index)
        elif asked[job] is None:
            print(f"{folder}: job {index} ({job}): the scheduler cannot be asked; left as it is")
    if len(kept) < len(left):
        print(f"{folder}: jobs {sorted(set(left) - set(kept))} are submitted already")
    return kept


def _start_again(workflow, record, folder, progress) -> None:
    """On the cluster, after a job that wrote a mark it had not: the command
    of the run again, in the same seed folder, so that the jobs that wait
    for this one are submitted. As many starts deep as the chain has slices,
    no more."""
    if not os.environ.get("RASER_CLUSTER_JOB") or not progress:
        return
    depth = int(os.environ.get("RASER_RESUBMIT_DEPTH", "0"))
    # The commands that wait for this job, as for a field others share; what
    # they start counts its own depth from here.
    for entry in _read(folder / "run.json").get("waiting", []):
        words = [*entry["command"], *(["--seed-folder", entry["seed_folder"]] if entry["seed_folder"] else [])]
        if depth >= _WAITING_DEPTH:
            print(f"not starting raser {' '.join(words)}: {depth} starts deep")
        elif _run_again(words, entry["cwd"], depth):
            done = _read(folder / "run.json")
            done["waiting"] = [other for other in done.get("waiting", []) if other != entry]
            _write(folder / "run.json", done)
    # Its own command, for the jobs of the run that wait for this one; a job
    # of a workflow without slices leaves none waiting.
    if not workflow.slices or not record.get("command"):
        return
    if depth >= len(workflow.slices):
        print(f"not starting the command again: {depth} starts deep, as many as the slices of the chain")
        return
    _run_again([*record["command"], *(["--seed-folder", folder.name] if workflow.seeds else [])], record["cwd"], depth)


def waited_for_by(record) -> list[str]:
    """A line for each command that waits for the jobs of `record`."""
    return [
        f"  waited for by: (in {entry['cwd']}) raser "
        + " ".join([*entry["command"], *(["--seed-folder", entry["seed_folder"]] if entry["seed_folder"] else [])])
        for entry in record.get("waiting", [])
    ]


def _run_again(words, cwd, depth) -> bool:
    """Start `raser <words>` in `cwd` one start deeper; whether it started."""
    print("starting the command again: raser " + " ".join(words))
    environment = {**os.environ, "RASER_RESUBMIT_DEPTH": str(depth + 1)}
    # Another job that ended at the same time may hold the folders: try again a few times.
    for attempt in range(_STARTS):
        if attempt:
            time.sleep(_PAUSE)
        started = subprocess.run([sys.executable, "-m", "raser.cli.raser", *words], cwd=cwd, env=environment, check=False)
        if getattr(started, "returncode", 0) == 0:
            return True
    print(f"the command did not start again in {_STARTS} tries: give it again when the jobs it waits for are done")
    return False


_STARTS, _PAUSE = 4, 30  # tries to start a command again on the cluster, and seconds between
_WAITING_DEPTH = 8  # the most starts deep a job starts the commands that wait for it


def _without_seed_folder(argv) -> list[str]:
    """The words of a command without --seed-folder and its folder."""
    words, skip = [], False
    for word in argv:
        if skip:
            skip = False
        elif word == "--seed-folder":
            skip = True
        elif not word.startswith("--seed-folder="):
            words.append(word)
    return words


def _seed_of(root, label) -> int:
    """The seed of the seed folder `label` of the experiment in `root`: in
    the experiment or in one of its points, not in an experiment inside it."""
    points = [Path(root)] + sorted(
        place for place in Path(root).iterdir() if place.is_dir() and not (place / "config.json").exists()
    )
    for path in (place / label / "run.json" for place in points):
        if path.is_file():
            return int(json.loads(path.read_text())["seed"])
    raise ValueError(f"{root}: no seed folder {label} to go on in")


def _done(folder, index) -> Path:
    return slices.mark(folder, index)


def _label(key, names, workflow=None) -> str:
    """A scanned option in the name of a folder: the name the config gives it,
    else the key of a setting without its section, else the last two steps of
    an address into a file, else the option itself."""
    if workflow is not None and workflow.sections and key in workflow.keys:
        return names.get(key) or key.split(".", 1)[1]
    return names.get(key) or ".".join(key.split(".")[-2:])


def in_file(workflow, key) -> str:
    """Where the key `key`, no setting of the experiment, sits in the files
    of a run: <kind of file>.<keys down to it>. In an experiment written in
    sections the key is <section>.<slot>.<keys>, of a slot of Workflow.slots."""
    for slot, kind in workflow.slots.items():
        if key.startswith(slot + "."):
            return kind + key[len(slot) :]
    if workflow.sections:
        raise ValueError(
            f"{key}: no such setting. The settings are {', '.join(workflow.keys)}; "
            f"a key inside a component is <section>.<slot>.<key>, with the slots {', '.join(workflow.slots) or 'none'}"
        )
    return key


def flat(workflow, options, stage) -> dict:
    """The options as a slice of `stage` reads them: the settings of the
    sections under their bare names, those of its own section over the
    others, so that deposit.plots and current.plots are each "plots" to
    their stage. Without sections, the options as they are."""
    if not workflow.sections:
        return options
    seen = dict(options)
    ordered = sorted((key for key in workflow.keys if key in options), key=lambda key: key.split(".")[0] == stage)
    for key in ordered:
        seen[key.split(".", 1)[1]] = options[key]
    return seen


def _leaves(held, path=()):
    """(keys down to it, value) of every value in the nested objects `held`."""
    for key, value in held.items():
        if isinstance(value, dict):
            yield from _leaves(value, (*path, key))
        else:
            yield ".".join((*path, key)), value


def read_config(workflow, root) -> dict:
    """config.json of the experiment in `root`, {} when there is none. For
    an experiment written in sections, its settings as "set": address ->
    value, and as "scan": address -> values those of the sections that are
    scanned (Workflow.scanned) whose value is a list. A setting that is not
    there is null; nothing but its settings is in a section. A slot may hold an object: its
    "name" is the component, its other keys are keys inside the file."""
    raw = _read(Path(root) / "config.json")
    if not raw or not workflow.sections:
        return raw
    path = Path(root) / "config.json"
    known = {"workflow", "device", "names", "same_seeds", *workflow.sections}
    if unknown := sorted(set(raw) - known):
        raise ValueError(
            f"{path}: no {', '.join(unknown)} in a config.json; it holds workflow, device, the sections "
            f"{', '.join(workflow.sections)}, names and same_seeds"
        )
    settings: dict = {}
    scan: dict = {}

    def take(address, value, section) -> None:
        (scan if isinstance(value, list) and section in workflow.scanned else settings)[address] = value

    for section in workflow.sections:
        held = raw.get(section, {})
        if not isinstance(held, dict):
            raise ValueError(f"{path}: {section} is a section, an object of its settings")
        for key, value in held.items():
            address = f"{section}.{key}"
            if address in workflow.slots and isinstance(value, dict):
                inside = dict(value)
                if address in workflow.keys:
                    if "name" not in inside:
                        raise ValueError(f"{path}: {address} is an object without the name of its component")
                    take(address, inside.pop("name"), section)
                for below, leaf in _leaves(inside):
                    take(f"{address}.{below}", leaf, section)
            elif address in workflow.keys:
                take(address, value, section)
            else:
                mine = [name.split(".", 1)[1] for name in workflow.keys if name.startswith(section + ".")]
                raise ValueError(f"{path}: no {address}; the settings of {section} are {', '.join(mine) or 'none'}")
    # A setting that is not written is null: the stage that needs a value of it tells.
    settings = {**{key: None for key in workflow.keys if key not in scan}, **settings}
    return {**{key: raw[key] for key in raw if key not in workflow.sections}, "set": settings, "scan": scan}


def written_config(workflow, config) -> dict:
    """`config` as config.json holds it: for an experiment written in
    sections, each section with every setting of it, null where none is
    set and the list of its values where it is scanned; a key inside the
    file of a slot is in the object of the slot, beside its name."""
    if not workflow.sections:
        return config
    values = {**config.get("set", {}), **config.get("scan", {})}
    out = {key: config[key] for key in ("workflow", "device") if key in config}
    for section in workflow.sections:
        out[section] = {key.split(".", 1)[1]: values.get(key) for key in workflow.keys if key.startswith(section + ".")}
    for address, value in values.items():
        if address in workflow.keys:
            continue
        slot = next(slot for slot in workflow.slots if address.startswith(slot + "."))
        section, name = slot.split(".", 1)
        held = out[section].get(name)
        if not isinstance(held, dict):
            if isinstance(held, list):
                raise ValueError(f"{address}: {slot} is scanned; a key inside it belongs to one component")
            held = out[section][name] = {"name": held} if slot in workflow.keys else {}
        *steps, last = address[len(slot) + 1 :].split(".")
        for step in steps:
            held = held.setdefault(step, {})
        held[last] = value
    out["names"] = config.get("names", {})
    out["same_seeds"] = config.get("same_seeds", False)
    return out


def _one_of_each_group(groups, layer, where) -> bool:
    """Whether `layer` gives a key of the one group in `groups`; two keys of
    a group in it are an error that names them and `where` they are."""
    gives = False
    for group in groups:
        present = [key for key in group if layer.get(key) is not None]
        if len(present) > 1:
            raise ValueError(f"{present[0]} and {present[1]} are given at once in {where}; give one of them")
        gives = gives or bool(present)
    return gives


# The text a value names a folder with may hold only these.
_FOLDER_TEXT = re.compile(r"[A-Za-z0-9._+-]+")


def _check_folder_names(key, values) -> None:
    """Refuse values of `key` that cannot name a folder, as an expression,
    and two values that would name the same folder, as beam/muon and
    other/muon. What is scanned or set is a number or a short name; an
    expression, as a doping profile, becomes a parameter with a name in its
    file, and that number is scanned."""
    seen: dict[str, object] = {}
    for value in values:
        text = _text(value)
        if not _FOLDER_TEXT.fullmatch(text):
            raise ValueError(
                f"{key} = {value!r}: the folder of this value would be named {text!r}, which "
                "holds more than letters, digits and ._+-; scan or set a number or a short name, "
                "and give an expression such as a doping profile a parameter with a name in its file"
            )
        if text in seen and seen[text] != value:
            raise ValueError(f"{key}: {seen[text]!r} and {value!r} would both be the folder {text!r}")
        seen[text] = value


def _text(value) -> str:
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return "%g" % value if number else str(value).rstrip("/").split("/")[-1]


def _parse(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _read(path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def _write(path, content) -> None:
    path.write_text(json.dumps(content, indent=2) + "\n")


def _commit() -> str:
    """The commit of the code, +dirty when files differ from it. Where there
    is no commit to read, in a package that is installed or in a source tree
    that is not a git repository, the version of the package."""
    version = f"raser {raser.__version__}"
    if REPO_ROOT is None:
        return version

    def git(*words):
        command = ["git", "-C", str(REPO_ROOT), *words]
        result = subprocess.run(command, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    commit, changes = git("rev-parse", "HEAD"), git("status", "--short")
    if commit is None:
        return version
    return commit + ("" if changes == "" else "+dirty")
