"""Strip dataset contracts, separate labels and event identity checks."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

CONTRACT = (
    "response_id",
    "waveform_kind",
    "channels",
    "positions_um",
    "entrance_reference_um",
    "entrance_z_um",
)


def _hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _waveform_hash(times, signals):
    digest = hashlib.sha256()
    for t, v in zip(times, signals):
        digest.update(str(t.shape).encode())
        digest.update(np.asarray(t, dtype="<f8").tobytes())
        digest.update(np.asarray(v, dtype="<f8").tobytes())
    return digest.hexdigest()


def _json(path):
    return json.loads(Path(path).read_text())


def _write(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(values, indent=2, allow_nan=False) + "\n")


def load_dataset(path):
    """NPZ access and waveform hashes use exactly the declared readout channels."""
    path = Path(path).resolve()
    m = _json(path)
    channels = m.get("channels", [])
    positions = np.asarray(m.get("positions_um", []), dtype=float)
    if (
        m.get("schema") != "raser-joint-strip-dataset-v1"
        or m.get("kind") != "strip"
        or len(channels) not in (1, 2, 3)
        or len(set(channels)) != len(channels)
        or any(not isinstance(c, str) or not c for c in channels)
        or positions.shape != (len(channels), 2)
        or not np.isfinite(positions).all()
        or np.any(np.diff(positions[:, 0]) <= 0)
        or np.ptp(positions[:, 1]) > 1e-9
    ):
        raise ValueError(
            "Joint dataset requires one, two or three explicit ordered strip channels"
        )
    if (
        m.get("waveform_kind") not in {"frontend_mV", "current_A"}
        or not isinstance(m.get("response_id"), str)
        or len(m["response_id"]) != 64
        or any(c not in "0123456789abcdef" for c in m["response_id"])
        or not all(
            math.isfinite(m.get(k, float("nan")))
            for k in ["entrance_reference_um", "entrance_z_um"]
        )
    ):
        raise ValueError(
            "Explicit waveform, response SHA256 and entrance coordinates required"
        )
    records = m.get("events", [])
    ids = [e.get("event_id") for e in records]
    if (
        not records
        or any(not isinstance(i, str) or not i for i in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("Unique nonempty waveform event IDs required")
    events = []
    for record in records:
        if (
            not {"event_id", "waveforms"}
            <= set(record)
            <= {"event_id", "waveforms", "particle_id"}
        ):
            raise ValueError(
                "Waveform records contain event_id, waveforms and optional particle_id; labels are separate"
            )
        particle_id = record.get("particle_id", record["event_id"])
        if not isinstance(particle_id, str) or not particle_id:
            raise ValueError("A nonempty particle identity is required")
        source = (path.parent / record["waveforms"]).resolve()
        times, signals = [], []
        with np.load(source, allow_pickle=False) as data:
            for channel in channels:
                prefix = (
                    "frontend_time_s_"
                    if m["waveform_kind"] == "frontend_mV"
                    else "time_s_"
                )
                times.append(np.asarray(data[prefix + channel], dtype=float))
                signals.append(
                    np.asarray(data[m["waveform_kind"] + "_" + channel], dtype=float)
                )
        events.append(
            {
                "event_id": record["event_id"],
                "particle_id": particle_id,
                "times_s": times,
                "signals": signals,
                "waveform_hash": _waveform_hash(times, signals),
            }
        )
    m["manifest_sha256"] = _hash(path)
    return m, events


def labels(path, event_ids):
    records = _json(path)["events"]
    if set(records) != set(event_ids):
        raise ValueError("Joint labels must cover every waveform event exactly")
    result = {}
    for event_id in event_ids:
        r = records[event_id]
        q, u = (
            np.asarray(r.get("slopes", []), dtype=float),
            np.asarray(r.get("entrance_um", []), dtype=float),
        )
        if (
            q.shape != (1,)
            or u.shape != (1,)
            or not np.isfinite(q).all()
            or not np.isfinite(u).all()
        ):
            raise ValueError(
                "Labels require finite signed slope and entrance_um, each length one"
            )
        result[event_id] = [float(q[0]), float(u[0])]
    return result


def compatible(first, second):
    if any(first[k] != second[k] for k in CONTRACT):
        raise ValueError("Joint detector/readout/entrance contract differs")


def independent(populations):
    ids: set[str] = set()
    hashes: set[str] = set()
    particles: set[str] = set()
    for events in populations:
        new_ids = [e["event_id"] for e in events]
        new_hashes = [e["waveform_hash"] for e in events]
        new_particles = {e.get("particle_id", e["event_id"]) for e in events}
        if (
            len(set(new_ids)) != len(new_ids)
            or len(set(new_hashes)) != len(new_hashes)
            or ids.intersection(new_ids)
            or hashes.intersection(new_hashes)
            or particles.intersection(new_particles)
        ):
            raise ValueError(
                "Training/calibration/evaluation leakage: repeated event or observed waveform"
            )
        ids.update(new_ids)
        hashes.update(new_hashes)
        particles.update(new_particles)
