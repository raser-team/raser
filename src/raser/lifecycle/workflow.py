"""`raser <command> -s <n>`: an experiment, its points, a seed folder in each, n jobs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import secrets
import subprocess
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Callable, Mapping

from raser.components import load_component
from raser.core.device import load_definition
from raser.lifecycle import jobs
from raser.supports.paths import REPO_ROOT
from raser.supports.paths import project_path


@dataclass(frozen=True)
class Workflow:
    """What an application hands in."""

    name: str  # command words, "cce" or "tct signal"; folder work/<device>/<words>
    job: Callable  # runs one job; receives the options as a dict
    keys: tuple = ()  # the options an experiment may set
    defaults: Mapping = field(default_factory=dict)  # their values when nobody set them
    components: Mapping = field(default_factory=dict)  # kind of json file -> the option naming it
    in_file: Mapping = field(default_factory=dict)  # option -> where its value sits in a file
    device: bool = True  # the command names a device
    command: Callable | None = None  # extra words of the job command
    extract: Callable | None = None  # (point folder, [(seed folder, job)]) -> a summary row

    @property
    def words(self):
        return self.name.split()

    def attach(self, parser):
        parser.add_argument("-s", "--jobs", type=int)
        parser.add_argument("-b", "--batch", action="store_true")
        parser.add_argument("-mem", type=int, default=1)
        parser.add_argument("--seed", type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--scan", action="append", default=[])
        parser.add_argument("--job-dir", help=argparse.SUPPRESS)
        parser.add_argument("--job-index", type=int, help=argparse.SUPPRESS)
        parser.set_defaults(_run=lambda kwargs: execute(self, kwargs))


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
    fixed = {**workflow.defaults, **config.get("set", {}), **given}

    # The points: one for every combination of the scanned values. A point's
    # folder is named by the scanned options that differ from the unscanned run.
    scan = dict(config.get("scan", {}))
    for item in kwargs["scan"]:
        key, _, values = item.partition("=")
        scan[key] = [_parse(value) for value in values.split(",")]
    scan = {key: values for key, values in scan.items() if key not in given}
    base, _ = _point(workflow, kwargs, fixed)
    points = {}  # folder inside the experiment -> (options, files)
    for combination in itertools.product(*scan.values()):
        options, files = _point(workflow, kwargs, {**fixed, **dict(zip(scan, combination))})
        changed = [key for key in scan if options[key] != base[key]]
        name = "_".join(f"{key}_{_text(options[key])}" for key in changed)
        points[name] = (options, files)

    # The seed folder of this command in every point, and the jobs left in it.
    if kwargs["seed"] is None:
        label, seed = time.strftime("%Y_%m%d_%H%M%S"), secrets.randbits(31)
    else:
        label, seed = f"seed_{kwargs['seed']}", kwargs["seed"]
    # A seed folder that was run with another record is run again from the start,
    # and so is any when the code has uncommitted changes; the old one is kept.
    commit = _commit()
    todo = []
    for name, (options, files) in points.items():
        folder = root / name / label
        record = {"seed": seed, "commit": commit, "options": options, "files": files}
        record = json.loads(json.dumps(record))
        old = _read(folder / "run.json")
        stale = bool(old) and (old != record or commit.endswith("+dirty"))
        left = [
            i
            for i in range(kwargs["jobs"] or 1)
            if stale or not _done(folder, i).exists()
        ]
        print(f"{folder}: jobs {left}" + (", the old run is kept aside" if stale else ""))
        todo.append((folder, left, stale, record))
    if kwargs["dry_run"]:
        return None
    if commit.endswith("+dirty"):
        print("warning: the code has uncommitted changes; run.json records this")

    if not config:
        root.mkdir(parents=True, exist_ok=True)
        _write(root / "config.json", {**identity, "set": given, "scan": scan})
    for folder, left, stale, record in todo:
        if stale:
            folder.rename(folder.with_name(f"{label}_{time.strftime('%Y_%m%d_%H%M%S')}"))
        if left:
            (folder / "batch").mkdir(parents=True, exist_ok=True)
            _write(folder / "run.json", record)
            _start(workflow, kwargs, folder, left)

    # The summary: one row per point, from the finished jobs of every seed folder
    # of the point that ran with the same commit, options and files.
    rows = []
    for (name, (options, _)), (_, _, _, record) in zip(points.items(), todo):
        done = [
            (folder, int(path.stem.split("_")[1]))
            for folder in _seed_folders(root / name, record)
            for path in sorted((folder / "batch").glob("job_*.done"))
        ]
        if workflow.extract is not None and done:
            scanned = {key: options[key] for key in scan}
            row = workflow.extract(root / name, done)
            rows.append({"point": name or ".", **scanned, "jobs": len(done), **row})
    if rows:
        with (root / "summary.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, list(dict.fromkeys(k for row in rows for k in row)))
            writer.writeheader()
            writer.writerows(rows)
    return None


def _point(workflow, kwargs, options) -> tuple[dict, dict]:
    """The options and json files of one run, from the options that were set."""
    options = dict(options)

    # The json files the run uses: the device, and the files its options name.
    files = {}
    if workflow.device:
        files["device"] = dict(load_definition(kwargs["det_name"]).raw)
    for kind, key in workflow.components.items():
        files[kind] = load_component(kind, options[key])[1]

    # An option that is a value inside a file, such as the bias in the device:
    # given, it is written into the file; not given, it takes the file's value.
    for key, address in workflow.in_file.items():
        kind, *steps, last = address.split(".")
        place = files[kind]
        for step in steps:
            place = place[step]
        if options.get(key) is None:
            options[key] = place[last]
        else:
            place[last] = options[key]
    return options, files


def _start(workflow, kwargs, folder, left) -> None:
    """Start the jobs `left` of a seed folder."""
    if kwargs["jobs"] is None and not kwargs["batch"]:
        _run_job(workflow, {**kwargs, "job_dir": str(folder)})  # in this process
        return
    tail = workflow.words[1:]
    if workflow.device:
        tail.append(kwargs["det_name"])
    if workflow.command:
        tail += workflow.command(kwargs)
    jobs.run_indexed_jobs(
        kwargs["_entry_command_prefix"],
        [*tail, "--job-dir", str(folder)],
        len(left),
        use_cluster=kwargs["batch"],
        mem=kwargs["mem"],
        destination=workflow.words[0],
        indices=left,
    )


def _seed_folders(point, record) -> list[Path]:
    """The seed folders of a point that ran with this record apart from the seed.
    A folder kept aside by a rerun is left out: its name is not seed_<its seed>."""
    same = {key: value for key, value in record.items() if key != "seed"}
    folders = []
    for path in sorted(point.glob("*/run.json")):
        old, name = _read(path), path.parent.name
        kept = name.startswith("seed_") and name != f"seed_{old['seed']}"
        if not kept and {key: value for key, value in old.items() if key != "seed"} == same:
            folders.append(path.parent)
    return folders


def _run_job(workflow, kwargs):
    """One job: its options, files and seed come from the run.json of its seed folder."""
    from raser.core.seeding import seed_generators  # loads ROOT

    folder, index = Path(kwargs["job_dir"]), kwargs.get("job_index") or 0
    record = _read(folder / "run.json")
    digest = hashlib.sha256(f"{record['seed']}/{index}".encode()).digest()
    options = {**kwargs, **record["options"]}
    options["seed"] = 1 + int.from_bytes(digest[:8], "big") % (2**31 - 1)
    options["_run_path"] = str(folder)
    options["_run_batch_path"] = str(folder / "batch")
    options["_files"] = record["files"]
    seed_generators(options["seed"])
    workflow.job(options)
    _done(folder, index).touch()


def _done(folder, index) -> Path:
    return folder / "batch" / f"job_{index}.done"


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
