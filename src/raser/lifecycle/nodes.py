"""Nodes: what a stage wrote for one set of inputs, known by those inputs.

A node is a folder <root>/nodes/<stage>/<node>/ (a field: <project>/field/<node>/)
with what the stage wrote and a node.json. Its name is the first DIGITS hex
digits of the fingerprint, the sha256 of the canonical json of its inputs: the
settings the stage reads, the part of the component files it uses, the nodes
it reads and its seed. The commit of the code, the environment and the state
are in node.json and not in the name.

A node is written as <node>.part/ and takes its name when it is whole. The
points of an experiment are views: <root>/points/<point>/<stage>/<job> is a
link to the node of that job, points.json the table of them.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import math
import os
import shutil
from pathlib import Path

DIGITS = 12  # hex digits of the fingerprint that name a node
MEASURING = ("field", "deposit", "current")  # a scan of these measures anew
STATES = ("running", "done", "ended")


class Running(SystemExit):
    """Another process writes this node now."""


def canonical(value) -> object:
    """`value` with one spelling for one value: a float that is a whole number
    is that int (the text of a config or of --set gives 1 or 1.0 for the same
    number), any other float is kept to the last bit. A bool is not a number.
    Numbers that are not finite, keys that are not text and values that are
    not json are refused."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                f"{value!r}: a node cannot read a number that is not finite"
            )
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError(
                f"keys {sorted(map(repr, value))}: a node reads keys that are text"
            )
        return {key: canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    raise TypeError(f"{value!r}: a node reads json values, not {type(value).__name__}")


def text(inputs) -> str:
    """The canonical json of the inputs of a node: keys sorted, no spaces."""
    return json.dumps(
        canonical(inputs),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def fingerprint(inputs) -> str:
    return hashlib.sha256(text(inputs).encode()).hexdigest()


def node_of(inputs) -> str:
    return fingerprint(inputs)[:DIGITS]


def file_digest(path) -> str:
    """The sha256 of a file a component names by its path, such as a mesh, a
    macro or a .cir: its content is an input, its path is not."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _seed(words: str) -> int:
    digest = hashlib.sha256(words.encode()).digest()
    return 1 + int.from_bytes(digest[:8], "big") % (2**31 - 1)


def measured(axes) -> dict:
    """Of the scanned settings of a point, "section.key" -> value, those of
    the sections that measure: a point at another bias, source or drift
    setting is measured anew, one that differs in a later section is not."""
    return {
        address: value
        for address, value in axes.items()
        if address.split(".")[0] in MEASURING
    }


def job_seed(seed, index, axes, same_seeds=False) -> int:
    """The seed of job `index` of a point of the run seeded `seed`, where the
    scanned settings that measure are `axes`. The name of the point is not in
    it, nor is a setting that does not measure. With `same_seeds` no setting
    is: the jobs of one index share their seed over the points."""
    axes = {} if same_seeds else axes
    words = ";".join(f"{address}={text(axes[address])}" for address in sorted(axes))
    return _seed(f"{int(seed)}/{int(index)}/{words}")


def stage_seed(seed, stage) -> int:
    """The seed of `stage` in the job seeded `seed`, as core.seeding names a stream."""
    return _seed(f"{int(seed)}/{stage}")


def node_dir(root, stage, node) -> Path:
    return Path(root) / "nodes" / stage / node


def lock(folder) -> object | None:
    """Hold the lock of the node `folder` until the handle is closed or the
    process ends; Running when another process holds it. A file system that
    cannot lock gets a warning, and the run goes on."""
    folder = Path(folder)
    path = folder.with_name(f".{folder.name}.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise Running(
            f"{folder} is written by another process now; run the command again when it is done"
        ) from None
    except OSError as error:
        handle.close()
        if error.errno not in (
            errno.ENOLCK,
            errno.ENOTSUP,
            errno.EOPNOTSUPP,
            errno.EINVAL,
        ):
            raise
        print(
            f"warning: {path} cannot be locked here ({error.strerror}): nothing keeps another command off it"
        )
        return None
    return handle


def _write_json(path, content) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(
        json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(part, path)


def read(folder) -> dict:
    return json.loads((Path(folder) / "node.json").read_text(encoding="utf-8"))


def found(folder, inputs) -> dict | None:
    """The node.json of the whole node `folder`, None when there is none.
    One that read other inputs under the same name is refused: the name is
    DIGITS digits of the fingerprint, the whole of it is compared."""
    folder = Path(folder)
    if not (folder / "node.json").is_file():
        return None
    record = read(folder)
    if record["fingerprint"] != fingerprint(inputs):
        raise RuntimeError(
            f"{folder} read other inputs than this node: two fingerprints share the name {folder.name}"
        )
    return record


def start(folder, stage, inputs, noted) -> Path:
    """<folder>.part/, empty but for its node.json in the state "running":
    where the stage writes. What an earlier, interrupted writing left there
    is removed. `noted` (job, code, environment) is kept and not read into
    the name. The caller holds the lock of the node."""
    folder = Path(folder)
    part = folder.with_name(folder.name + ".part")
    if part.exists():
        shutil.rmtree(part)
    part.mkdir(parents=True)
    record = {
        "stage": stage,
        "node": folder.name,
        "fingerprint": fingerprint(inputs),
        "inputs": canonical(inputs),
        **noted,
        "state": "running",
        "notes": {},
    }
    _write_json(part / "node.json", record)
    return part


def finish(part, state="done", notes=None) -> Path:
    """Give the node written in `part` its name, in the state "done", or
    "ended" for a stage that left nothing for the stages after it. The keys
    the stage itself wrote into node.json stay."""
    if state not in ("done", "ended"):
        raise ValueError(f"a node is finished done or ended, not {state}")
    part = Path(part)
    record = read(part)
    record["state"] = state
    record["notes"] = notes or {}
    _write_json(part / "node.json", record)
    folder = part.with_name(part.name.removesuffix(".part"))
    os.replace(part, folder)
    return folder


def code_differs(record, code) -> str | None:
    """The note for a node written by another version of the code; it is used all the same."""
    if record.get("code") == code:
        return None
    return f"note: {record['stage']} node {record['node']} was written by {record.get('code')}, the code is {code} now"


def _link(link, target) -> None:
    link = Path(link)
    target = Path(target)
    if not target.is_dir():
        raise FileNotFoundError(f"{target}: no node to link {link} to")
    if os.path.lexists(link) and not link.is_symlink():
        raise FileExistsError(f"{link} is not a link: a point view holds only links")
    link.parent.mkdir(parents=True, exist_ok=True)
    part = link.with_name(link.name + ".part")
    part.unlink(missing_ok=True)
    part.symlink_to(os.path.relpath(target, link.parent))
    os.replace(part, link)


def link_view(root, point, stage, target, job=None) -> Path:
    """<root>/points/<point>/<stage>/<job> -> the node of that job; without a
    job, for a field or an analysis, <root>/points/<point>/<stage> -> the
    node. A link that was there follows the new node."""
    if not point:
        raise ValueError("a point view needs a name")
    link = Path(root) / "points" / point / stage
    link = link if job is None else link / str(int(job))
    _link(link, target)
    return link


def write_points(root, rows) -> Path:
    """<root>/points.json, the table of the points: per point the value of
    each scanned setting and the nodes of each stage, a list over the jobs
    for the stages run job by job."""
    path = Path(root) / "points.json"
    _write_json(path, canonical(rows))
    return path
