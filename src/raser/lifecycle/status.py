"""raser status <experiment folder>: how far the jobs of every point are, from
the marks, logs and locks the runs left. It reads; it writes nothing."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path

from raser.lifecycle import scheduler
from raser.lifecycle import slices
from raser.lifecycle.workflow import JOB_ENDED
from raser.lifecycle.workflow import WORKFLOWS
from raser.lifecycle.workflow import _outdated
from raser.lifecycle.workflow import _points
from raser.supports.paths import project_root_context

STATES = ("done", "running", "submitted", "uncertain", "failed", "waiting", "not started")


def _held(lock: Path) -> bool:
    """Whether another process holds the lock file `lock`."""
    if not lock.is_file():
        return False
    with open(lock, "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        except OSError:
            return False  # a file system that cannot lock tells nothing
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


def job_state(done: bool, running: bool, logged: bool, upstream_done: bool) -> str:
    """The state of one slice of one job: done with its mark; running while
    its job holds its lock; failed when the job left a log and no mark and
    runs no more; waiting while a slice it reads is not done; else not started."""
    if done:
        return "done"
    if running:
        return "running"
    if logged:
        return "failed"
    if not upstream_done:
        return "waiting"
    return "not started"


def _on_cluster(folder: Path, index: int, name: str, asked: dict) -> str | None:
    """A job submitted for slice `name` that has not run it: "submitted" while
    the cluster holds it; when it no more does, "failed", and its record goes;
    "uncertain" when the scheduler cannot be asked. None: never submitted."""
    record = folder / "batch" / f"{name}_{index}.submitted"
    if not record.is_file():
        return None
    job = json.loads(record.read_text())["job"]
    if job not in asked:
        asked[job] = scheduler.job_alive(job)
    if asked[job] is None:
        return "uncertain"
    if asked[job]:
        return "submitted"
    record.unlink(missing_ok=True)
    return "failed"


def folder_states(workflow, folder: Path, record: dict, ready=None) -> dict[str, dict[str, list[int]]]:
    """Per slice (or "job" for a workflow without slices), the job indices in each state.

    `ready(piece)` says whether a shared slice is ready for this point."""
    root = folder.parent.parent if workflow.seeds and record.get("point") else folder.parent
    if not workflow.seeds:
        root = folder.parent if record.get("point") else folder
    label = folder.name if workflow.seeds else ""
    count = record.get("jobs") or 1
    pieces = workflow.slices or (None,)
    states: dict[str, dict[str, list[int]]] = {}
    asked: dict = {}
    for i in range(count):
        running = _held(folder / "batch" / f"job_{i}.lock")
        log = folder / "batch" / f"job_{i}.log"
        # A job that ran all it was asked, as only the deposits, did not fail.
        logged = log.is_file() and (not workflow.slices or JOB_ENDED not in log.read_text(errors="replace"))
        done_of: dict[int, bool] = {}
        for k, piece in enumerate(pieces):
            name = piece.name if piece else "job"
            if piece:
                holder = root / record["held_in"][piece.name] / label
                done = slices.mark(holder, i, piece.name).exists()
            else:
                done = slices.mark(folder, i).exists()
            done_of[k] = done
            upstream = piece is None or all(done_of[j] for j in slices.upstream(workflow.slices, k))
            state = job_state(done, running, logged and not done, upstream)
            if not done and not running:
                state = _on_cluster(folder, i, name, asked) or state
            if piece is not None and piece.shared and ready is not None and not ready(piece):
                state = "waiting" if not done else state
            states.setdefault(name, {s: [] for s in STATES})[state].append(i)
    return states


def _folder_lines(workflow, folder: Path, record: dict, why: str | None, ready, note: str = "") -> list[str]:
    """The lines of one seed or point folder: its slices and their jobs."""
    held_in = record.get("held_in", {})
    if workflow.slices and set(held_in) != {piece.name for piece in workflow.slices}:
        # A run of an older raser, whose slices had other names.
        return [f"{folder}: out of date (recorded with the slices {sorted(held_in)})" + note]
    lines = [f"{folder}:" + (f" out of date ({why})" if why else "") + note]
    for piece_name, by_state in folder_states(workflow, folder, record, ready).items():
        count = sum(len(jobs) for jobs in by_state.values())
        done = len(by_state["done"])
        shown = f"{done}/{count} done" if not why else f"{done}/{count} done, out of date"
        rest = ", ".join(f"{state} {jobs}" for state, jobs in by_state.items() if state != "done" and jobs)
        lines.append(f"  {piece_name:<12}{shown}" + (f"; {rest}" if rest else ""))
    return lines


def _runs(workflow, root: Path, name: str) -> list[Path]:
    """The run.json of the seed folders (or the point folder) of the point `name`."""
    runs = sorted((root / name).glob("*/run.json" if workflow.seeds else "run.json"))
    # Not a seed folder: an experiment inside this one, such as its analysis.
    return [path for path in runs if not workflow.seeds or "seed" in json.loads(path.read_text())]


def _lines(workflow, root: Path, kwargs) -> list[str]:
    config = json.loads((root / "config.json").read_text())
    _, points, asked = _points(workflow, kwargs, config, {})
    lines = []
    for name in asked:
        options, files = points[name][:2]
        now = json.loads(json.dumps({"options": options, "files": files}))
        runs = _runs(workflow, root, name)
        if not runs:
            lines.append(f"{root / name}: not started")
        for path in runs:
            record, folder = json.loads(path.read_text()), path.parent
            if workflow.seeds and folder.name.startswith("seed_") and folder.name != f"seed_{record['seed']}":
                continue  # kept aside by a rerun
            any_code = {**record, "commit": ""}
            why = _outdated(workflow, any_code, {**any_code, **now})
            ready = (lambda piece, options=options, files=files: piece.shared.ready(options, files) is not None)
            lines += _folder_lines(workflow, folder, record, why, ready)
    # Points on disk that the config does not ask for: made for another
    # experiment, as a field one of its points needs.
    pattern = "*/*/run.json" if workflow.seeds else "*/run.json"
    for path in sorted(root.glob(pattern)):
        record = json.loads(path.read_text())
        point_folder = path.parent.parent if workflow.seeds else path.parent
        if record.get("point") in asked or point_folder != root / str(record.get("point")):
            continue
        lines += _folder_lines(workflow, path.parent, record, None, None, " asked for by another experiment, not in this config")
    return lines


def run(kwargs):
    root = Path(kwargs["experiment"]).resolve()
    config = json.loads((root / "config.json").read_text())
    words = config["workflow"].split()
    workflow = WORKFLOWS[config["workflow"]]
    project = root.parents[len(words) - 1]
    with project_root_context(project, kwargs["_components_of"].get(words[0], ())):
        for line in _lines(workflow, root, {"det_name": config.get("device"), "scan": []}):
            print(line)
    return 0


def register(subparsers):
    parser = subparsers.add_parser("status", help="how far the jobs of an experiment are")
    parser.add_argument("experiment", help="experiment folder, work/<device>/<command>")
    parser.set_defaults(_run=run)
