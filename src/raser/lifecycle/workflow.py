"""`raser <command> -s <n>`: an experiment, its points, a seed folder in each, n jobs."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import secrets
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from pathlib import Path
from typing import Callable, Mapping

from raser.components import load_component
from raser.core.device.build_device import device_json
from raser.lifecycle import jobs
from raser.lifecycle import slices
from raser.supports.paths import REPO_ROOT
from raser.supports.paths import project_path


WORKFLOWS: dict = {}  # the workflows that have a command, by name


@dataclass(frozen=True)
class Workflow:
    """What an application hands in."""

    name: str  # command words, "cce" or "tct signal"; folder work/<device>/<words>
    job: Callable | None = None  # runs one job; receives the options as a dict
    # Instead of `job`: the Slices of slices.py that a job runs one after
    # another. A slice is run again when what it or a slice before it reads
    # changed; the slices before it stay as they are.
    slices: tuple = ()
    keys: tuple = ()  # the options an experiment may set
    defaults: Mapping = field(default_factory=dict)  # their values when nobody set them
    components: Mapping = field(default_factory=dict)  # kind of json file -> the option naming it
    in_file: Mapping = field(default_factory=dict)  # option -> where its value sits in a file
    device: bool = True  # the command names a device
    # False: nothing is drawn; a point holds one run, in its own folder, and its
    # job is started by every command: the job itself sees what is left to do.
    seeds: bool = True
    # (the run.json of an old run, the record of this one) -> what makes the old
    # run out of date, or None. Not given: any difference between the two does,
    # and so do uncommitted changes of the code.
    outdated: Callable | None = None
    command: Callable | None = None  # extra words of the job command
    extract: Callable | None = None  # (point folder, [(seed folder, job)]) -> a summary row
    # TODO(ana): nothing calls extract yet. A separate `raser ana` command is to
    # collect the results of an experiment folder: it takes the points and jobs
    # from `finished` and hands them to the analysis. Until it exists, cce and
    # timeres have no command that writes their summary.

    @property
    def words(self):
        return self.name.split()

    def attach(self, parser):
        if self.seeds:
            parser.add_argument("-s", "--jobs", type=int)
            parser.add_argument("--seed", type=int)
            parser.add_argument("--same-seeds", action="store_true")
        parser.add_argument("-b", "--batch", action="store_true")
        parser.add_argument("-mem", type=int, default=1)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--scan", action="append", default=[])
        if self.slices:
            names = [piece.name for piece in self.slices]
            parser.add_argument("--until", choices=names, help="stop after this slice")
        parser.add_argument("--job-dir", help=argparse.SUPPRESS)
        parser.add_argument("--job-index", type=int, help=argparse.SUPPRESS)
        parser.set_defaults(_run=lambda kwargs: execute(self, kwargs))
        WORKFLOWS[self.name] = self


def execute(workflow, kwargs):
    if kwargs.get("job_dir"):
        return _run_job(workflow, kwargs)  # one of the jobs started below

    # The experiment: a folder with a config.json, here or at the default place.
    # Its options are the defaults, then the config's "set", then the command line.
    identity = {"workflow": workflow.name}
    if workflow.device:
        identity["device"] = kwargs["det_name"]
    root = Path.cwd()
    config = _read(root / "config.json")
    if any(config.get(key) != value for key, value in identity.items()):
        root = Path(project_path(*workflow.words))
        config = _read(root / "config.json")
    given = {key: kwargs[key] for key in workflow.keys if kwargs.get(key) is not None}
    scan, points = _points(workflow, kwargs, config, given)

    # The seed folder of this command in every point, and the jobs left in it.
    # Without seeds the point folder itself holds the run, and its one job.
    if not workflow.seeds:
        label, seed = "", None
    elif kwargs["seed"] is None:
        label, seed = time.strftime("%Y_%m%d_%H%M%S"), secrets.randbits(31)
    else:
        label, seed = f"seed_{kwargs['seed']}", kwargs["seed"]
    # A seed folder that was run with another record is run again from the start,
    # and so is any when the code has uncommitted changes; the old one is kept.
    commit = _commit()
    same_seeds = kwargs.get("same_seeds") or config.get("same_seeds", False)
    todo = []
    wanted = workflow.slices  # the slices this command runs
    if kwargs.get("until"):
        wanted = wanted[: 1 + [piece.name for piece in wanted].index(kwargs["until"])]
    for name, (options, files, given_here) in points.items():
        folder = root / name / label
        record = {"seed": seed, "point": name, "same_seeds": same_seeds}
        if not workflow.seeds:
            record = {"point": name}
        record.update(commit=commit, options=options, files=files)
        for k, piece in enumerate(workflow.slices):
            record.setdefault("slices", {})[piece.name] = _read_by(workflow, kwargs, given_here, k)
        record = json.loads(json.dumps(record))
        old = _read(folder / "run.json")
        why = _outdated(workflow, old, record) if old else None
        # With slices: when the first slice reads what it read in the old run and
        # nothing else of the record changed, the old run is not out of date;
        # the slices from `again` on are run again in it.
        again = slices.first_changed(workflow.slices, old, record) if old else 0
        rest = {key: value for key, value in record.items() if key not in SLICED}
        if again > 0 and _outdated(workflow, {key: old.get(key) for key in rest}, rest) is None:
            why = None
        stale = why is not None
        left = [
            i
            for i in range(kwargs.get("jobs") or 1)
            if stale or not workflow.seeds or not _done(folder, i).exists()
        ]
        if workflow.slices:
            to_run = slices.left(wanted, folder, range(kwargs.get("jobs") or 1), 0 if stale else again)
            left = sorted(set().union(*to_run.values()))
        aside = "kept aside" if workflow.seeds else "replaced"
        print(f"{folder}: jobs {left}" + (f", the old run is {aside}: {why}" if stale else ""))
        for piece in wanted:
            print(f"  {piece.name:<12}" + (f"jobs {to_run[piece.name]}" if to_run[piece.name] else "reused"))
        again = again if old and not stale else len(workflow.slices)  # nothing to run again in place
        # What the jobs wrote into run.json themselves stays while the run is not out of date.
        if not stale:
            record = {**{key: old[key] for key in old if key not in record}, **record}
        todo.append((folder, left, stale, record, workflow.slices[again:]))
    if kwargs["dry_run"]:
        return None
    if commit.endswith("+dirty"):
        print("warning: the code has uncommitted changes; run.json records this")

    if not config:
        root.mkdir(parents=True, exist_ok=True)
        new = {**identity, "set": given, "scan": scan}
        if workflow.seeds:
            new["same_seeds"] = same_seeds
        _write(root / "config.json", new)
    failed = []
    for folder, left, stale, record, run_again in todo:
        slices.forget(run_again, folder)
        if stale and workflow.seeds:
            folder.rename(folder.with_name(f"{label}_{time.strftime('%Y_%m%d_%H%M%S')}"))
        elif stale:  # a point without seeds has no folder of its own to set aside
            for i in left:
                _done(folder, i).unlink(missing_ok=True)
        if left:
            (folder / "batch").mkdir(parents=True, exist_ok=True)
            _write(folder / "run.json", record)
            try:
                _start(workflow, kwargs, folder, left, alone=len(todo) == 1)
            except Exception as error:
                if len(todo) == 1:
                    raise
                # The points do not depend on each other: the rest still run.
                traceback.print_exc()
                failed.append(f"  {folder}: {error!r}")
    if failed:
        raise SystemExit("\n".join([f"{len(failed)} of {len(todo)} points failed:", *failed]))
    return None


def finished(workflow, kwargs, root) -> list[tuple[str, dict, list[tuple[Path, int]]]]:
    """The points of the experiment in `root`, each with its folder name, its
    options and the finished (seed folder, job index) pairs.

    A point's jobs come from all its seed folders that ran with the options and
    files the experiment has now, whatever their seed and commit. Folders kept
    aside by a rerun are left out: their name is not seed_<their seed>."""
    _, points = _points(workflow, kwargs, _read(root / "config.json"), {})
    result = []
    for name, (options, files, _) in points.items():
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


def _outdated(workflow, old, record) -> str | None:
    """What makes the run that wrote `old` out of date for `record`, or None."""
    if workflow.outdated:
        return workflow.outdated(old, record)
    if record["commit"].endswith("+dirty"):
        return "the code has uncommitted changes"
    changed = [key for key in record if old.get(key) != record[key]]
    return "other " + ", ".join(changed) if changed else None


def _points(workflow, kwargs, config, given) -> tuple[dict, dict]:
    """The scanned options and the points of an experiment.

    One point for every combination of the scanned values. A point's folder is
    named by the scanned options that differ from the unscanned run."""
    fixed = {**workflow.defaults, **config.get("set", {}), **given}
    # "names" in the config gives an address a short name: the scan may be
    # written with it, and the folders are named by it.
    names = config.get("names", {})
    address = {name: key for key, name in names.items()}
    scan = {address.get(key, key): values for key, values in config.get("scan", {}).items()}
    for item in kwargs["scan"]:
        key, _, values = item.partition("=")
        scan[address.get(key, key)] = [_parse(value) for value in values.split(",")]
    scan = {key: values for key, values in scan.items() if key not in given}
    label = {key: _label(key, names) for key in scan}
    for key, other in itertools.combinations(scan, 2):
        if label[key] == label[other]:
            raise ValueError(
                f"{key} and {other} would both be {label[key]!r} in the names of folders: "
                'give one of them a name under "names" in config.json'
            )
    # A scanned address is not given in the unscanned run: there it takes the file's value.
    base, _ = _point(workflow, kwargs, {**dict.fromkeys(key for key in scan if "." in key), **fixed})
    points = {}  # folder inside the experiment -> (options, files, the options given)
    for combination in itertools.product(*scan.values()):
        given_here = {**fixed, **dict(zip(scan, combination))}
        options, files = _point(workflow, kwargs, given_here)
        changed = [key for key in scan if options[key] != base[key]]
        name = "_".join(f"{label[key]}_{_text(options[key])}" for key in changed)
        points[name] = (options, files, given_here)
    return scan, points


def _point(workflow, kwargs, options) -> tuple[dict, dict]:
    """The options and json files of one run, from the options that were set."""
    options = dict(options)

    # The json files the run uses: the device, and the files its options name.
    files = {}
    if workflow.device:
        files["device"] = device_json(kwargs["det_name"])
    for kind, key in workflow.components.items():
        files[kind] = load_component(kind, options[key])[1]

    # An option that is a value inside a file, such as the bias in the device:
    # given, it is written into the file; not given, it takes the file's value.
    # An option may also be named by its address, "afe.stages.first.R1.ohm":
    # the kind of file, then the keys down to a value the file has.
    addresses = {key: key for key in options if "." in key}
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
    """The options and files that the slices up to the k-th read, when the
    options `given` were set. The options of the later slices are not given
    here: the files they name are left out, and a value they would write into
    a file stays as the file has it."""
    mine = {key for key in [*given, *workflow.keys] if slices.owner(workflow.slices, key) <= k}
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
        _run_job(workflow, {**kwargs, "job_dir": str(folder)})  # in this process
        return
    tail = workflow.words[1:]
    if workflow.device:
        tail.append(kwargs["det_name"])
    if workflow.command:
        tail += workflow.command(kwargs)
    if kwargs.get("until"):
        tail += ["--until", kwargs["until"]]
    if single:  # one point among several: a process of its own, as on the cluster
        _own_process(workflow, kwargs, [*kwargs["_entry_command_prefix"], *tail, "--job-dir", str(folder)])
        return
    jobs.run_indexed_jobs(
        kwargs["_entry_command_prefix"],
        [*tail, "--job-dir", str(folder)],
        len(left),
        use_cluster=kwargs["batch"],
        mem=kwargs["mem"],
        destination=workflow.words[0],
        indices=left,
    )


def _own_process(workflow, kwargs, words) -> None:
    """Run the command `words`, the single job of one point, in another process."""
    subprocess.run([sys.executable, "-m", "raser.cli.raser", *words], check=True)


def _run_job(workflow, kwargs):
    """One job: its options, files and seed come from the run.json of its seed folder.

    The job's seed is a hash of the run's seed, the point and the job index, so
    points draw different random numbers; with same_seeds the point is left out
    and the jobs with one index draw the same numbers in every point."""
    folder, index = Path(kwargs["job_dir"]), kwargs.get("job_index") or 0
    record = _read(folder / "run.json")
    options = {**kwargs, **record["options"]}
    options["_run_path"] = str(folder)
    options["_run_batch_path"] = str(folder / "batch")
    options["_files"] = record["files"]
    if workflow.seeds:
        from raser.core.seeding import seed_generators  # loads ROOT

        source = f"{record['seed']}/{index}"
        if not record["same_seeds"]:
            source = f"{record['seed']}/{record['point']}/{index}"
        digest = hashlib.sha256(source.encode()).digest()
        options["seed"] = 1 + int.from_bytes(digest[:8], "big") % (2**31 - 1)
        seed_generators(options["seed"])
    if workflow.slices:
        if not slices.run(workflow.slices, folder, index, options, kwargs.get("until")):
            return  # stopped after --until: the job is not finished
    else:
        workflow.job(options)
    _done(folder, index).touch()


def _done(folder, index) -> Path:
    return slices.mark(folder, index)


def _label(key, names) -> str:
    """A scanned option in the name of a folder: the name the config gives it,
    else the last two steps of an address, else the option itself."""
    return names.get(key) or ".".join(key.split(".")[-2:])


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
    """The commit of the code; +dirty when files differ from it or it is unknown."""

    def git(*words):
        command = ["git", "-C", str(REPO_ROOT), *words]
        result = subprocess.run(command, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    commit, changes = git("rev-parse", "HEAD"), git("status", "--short")
    return (commit or "unknown") + ("" if commit and changes == "" else "+dirty")
