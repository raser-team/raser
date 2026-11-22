"""Straight tracks through the layers of a telescope, and the widths of the residuals.

Lengths are in um, angles in degrees. A slot is a device placed in the
telescope; its clusters come from its event table (`SlotHits`) and its place
from the experiment (`Placement`).

`TrackEvents.columns`, one row per event of any slot, in ascending event
number; `slots` is the order of the columns of the 2D arrays:
    event        (events,), int64
    selected     (events,), bool: every slot has one cluster
    x, y         (events, slots): cluster in global coordinates [um]; NaN
                 for a slot without one cluster
    kx, ky       (events,): slope of the track fitted to the reference layers
    bx, by       (events,): intercept [um] of that track at Z = 0
    chi2         (events,): of the reference layers, pixel pitch as spread
    residual_x, residual_y
                 (events, slots): track minus cluster [um]
The track quantities and residuals are NaN for an event that is not selected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from raser.supports import figures

from .resolution import TooFewValues
from .resolution import core_width

# cos and sin of the rotations about z that keep the pixels on the axes
ROTATIONS = {0: (1.0, 0.0), 90: (0.0, 1.0), 180: (-1.0, 0.0), 270: (0.0, -1.0)}
ROLES = ("reference", "dut")
BINS = 64


@dataclass
class SlotHits:
    """The columns of the event table of a slot, four arrays of equal length."""

    event: np.ndarray
    clusters: np.ndarray
    cluster_x: np.ndarray  # [um]
    cluster_y: np.ndarray  # [um]


@dataclass
class Placement:
    position: list[float]  # [x, y, z] [um]
    rotation_z: float  # degrees
    l_x: float  # [um]
    l_y: float
    l_z: float
    p_x: float  # pixel pitch [um]
    p_y: float


@dataclass
class TrackEvents:
    slots: list[str]
    roles: list[str]
    z: np.ndarray  # (slots,) [um]
    columns: dict[str, np.ndarray]


def track_events(
    hits: dict[str, SlotHits],
    placements: dict[str, Placement],
    roles: dict[str, str],
) -> TrackEvents:
    """Tracks of the events of a job: clusters to global coordinates, a line
    through the reference layers, residuals on every slot."""
    if not set(hits) == set(placements) == set(roles):
        raise ValueError("the slots of hits, placements and roles differ")
    slots = list(placements)
    for slot in slots:
        if roles[slot] not in ROLES:
            raise ValueError(f"role {roles[slot]!r} of slot {slot}: one of {ROLES}")
    z = np.array(
        [placements[slot].position[2] + placements[slot].l_z / 2 for slot in slots]
    )
    reference = np.array([roles[slot] == "reference" for slot in slots])
    if reference.sum() < 2 or np.ptp(z[reference]) == 0:
        raise ValueError("a track needs reference layers at two or more z")
    for slot in slots:
        if placements[slot].rotation_z not in ROTATIONS:
            raise ValueError(
                f"rotation_z {placements[slot].rotation_z} of slot {slot}: one of 0, 90, 180, 270"
            )

    events = np.unique(np.concatenate([hits[slot].event for slot in slots])).astype(
        "int64"
    )
    n_events, n_slots = len(events), len(slots)
    clusters = np.zeros((n_events, n_slots), dtype="int64")
    x = np.full((n_events, n_slots), np.nan)
    y = np.full((n_events, n_slots), np.nan)
    for s, slot in enumerate(slots):
        hit, place = hits[slot], placements[slot]
        row = np.searchsorted(events, hit.event)
        clusters[row, s] = hit.clusters
        cos, sin = ROTATIONS[int(place.rotation_z)]
        local_x = np.asarray(hit.cluster_x, dtype="float64") - place.l_x / 2
        local_y = np.asarray(hit.cluster_y, dtype="float64") - place.l_y / 2
        x[row, s] = place.position[0] + cos * local_x - sin * local_y
        y[row, s] = place.position[1] + sin * local_x + cos * local_y
    # a slot without one cluster has no position, whatever its columns hold
    x[clusters != 1] = np.nan
    y[clusters != 1] = np.nan
    selected = np.all(clusters == 1, axis=1)

    nothing = np.full(n_events, np.nan)
    columns = {
        "event": events,
        "selected": selected,
        "x": x,
        "y": y,
        "kx": nothing.copy(),
        "bx": nothing.copy(),
        "ky": nothing.copy(),
        "by": nothing.copy(),
        "chi2": nothing.copy(),
        "residual_x": np.full((n_events, n_slots), np.nan),
        "residual_y": np.full((n_events, n_slots), np.nan),
    }
    z_reference = z[reference]
    z_centred = z_reference - z_reference.mean()
    # the pitch along global x and y: swapped by a quarter turn
    pitch = np.array(
        [
            (placements[slot].p_x, placements[slot].p_y)
            if placements[slot].rotation_z in (0, 180)
            else (placements[slot].p_y, placements[slot].p_x)
            for slot in slots
        ]
    )[reference]
    chi2 = np.zeros(selected.sum())
    for axis, position in (("x", x), ("y", y)):
        chosen = position[selected]
        on_reference = chosen[:, reference]
        slope = (
            (on_reference - on_reference.mean(axis=1, keepdims=True)) * z_centred
        ).sum(axis=1) / np.dot(z_centred, z_centred)
        intercept = on_reference.mean(axis=1) - slope * z_reference.mean()
        residual = slope[:, None] * z + intercept[:, None] - chosen
        columns[f"k{axis}"][selected] = slope
        columns[f"b{axis}"][selected] = intercept
        columns[f"residual_{axis}"][selected] = residual
        q = pitch[:, 0 if axis == "x" else 1]
        chi2 += (residual[:, reference] ** 2 / (q**2 / 12)).sum(axis=1)
    columns["chi2"][selected] = chi2
    return TrackEvents(slots, [roles[slot] for slot in slots], z, columns)


def residual_widths(tracks: list[TrackEvents]) -> dict:
    """Core width of the residuals of each "dut" slot, {slot: {"x": ..., "y": ...}}.

    tracks : the jobs of a point, with the same slots and roles. Each result
        is what `core_width` returns [um] over the selected events of all
        jobs, or {"events": count, "error": text} when there are too few.
    """
    if not tracks:
        raise ValueError("no tracks")
    if any(
        track.slots != tracks[0].slots or track.roles != tracks[0].roles
        for track in tracks
    ):
        raise ValueError("the slots or roles of the tracks differ")
    widths: dict = {}
    for s, slot in enumerate(tracks[0].slots):
        if tracks[0].roles[s] != "dut":
            continue
        widths[slot] = {}
        for axis in ("x", "y"):
            values = np.concatenate(
                [
                    track.columns[f"residual_{axis}"][track.columns["selected"], s]
                    for track in tracks
                ]
            )
            try:
                widths[slot][axis] = core_width(values)
            except TooFewValues as error:
                widths[slot][axis] = {"events": len(values), "error": str(error)}
    return widths


def draw_track(tracks: TrackEvents, event: int, path) -> Path:
    """Draw the clusters and the fitted line of one selected event, X-Z
    (left) and Y-Z (right), as `track_<event>` in the folder `path`; returns the png."""
    rows = np.nonzero(tracks.columns["event"] == event)[0]
    if len(rows) == 0 or not tracks.columns["selected"][rows[0]]:
        raise ValueError(f"event {event} is not a selected event of the tracks")
    row = rows[0]
    reference = np.array([role == "reference" for role in tracks.roles])
    z_mm = tracks.z * 1e-6 / figures.UNIT["mm"]
    line = np.array([tracks.z.min(), tracks.z.max()])
    figure, axes = figures.new(1, 2)
    for ax, axis in zip(axes, ("x", "y")):
        position = tracks.columns[axis][row]
        ax.scatter(
            z_mm[reference],
            position[reference],
            color=figures.HISTOGRAM,
            label="Reference",
            zorder=3,
        )
        if not reference.all():
            ax.scatter(
                z_mm[~reference],
                position[~reference],
                facecolors="none",
                edgecolors=figures.HOLE,
                label="DUT",
                zorder=3,
            )
        slope, intercept = (
            tracks.columns[f"k{axis}"][row],
            tracks.columns[f"b{axis}"][row],
        )
        ax.plot(
            line * 1e-6 / figures.UNIT["mm"],
            slope * line + intercept,
            color="black",
            label="Fit to reference layers",
        )
        ax.set_xlabel(figures.label("z", "mm"))
        ax.set_ylabel(figures.label(axis, "um"))
        ax.legend()
    return figures.save(figure, path, "track", event)


def truncated_curve(grid: np.ndarray, fit: dict, bin_width: float) -> np.ndarray:
    """Counts per bin of the Gaussian of `fit` cut to its window, scaled to
    the events inside the window."""
    low, high = fit["window"]
    mean, sigma = fit["mean"], fit["sigma"]
    inside = 0.5 * (
        math.erf((high - mean) / (sigma * math.sqrt(2)))
        - math.erf((low - mean) / (sigma * math.sqrt(2)))
    )
    density = np.exp(-0.5 * ((grid - mean) / sigma) ** 2) / (
        sigma * math.sqrt(2 * math.pi) * inside
    )
    return np.where(
        (grid >= low) & (grid <= high),
        fit["window_events"] * bin_width * density,
        np.nan,
    )


def draw_residual(tracks: list[TrackEvents], slot: str, widths: dict, path) -> Path:
    """Draw the residuals of a slot over all jobs, x (left) and y (right), as
    `residual_<slot>` in the folder `path`; returns the png.

    widths : the entry of `slot` in the result of `residual_widths`
    """
    s = tracks[0].slots.index(slot)
    figure, axes = figures.new(1, 2)
    for ax, axis in zip(axes, ("x", "y")):
        values = np.concatenate(
            [t.columns[f"residual_{axis}"][t.columns["selected"], s] for t in tracks]
        )
        if len(values) == 0:
            raise ValueError(f"no selected event for the residual {axis} of {slot}")
        fit = widths[axis]
        if "error" in fit:
            low, high = float(values.min()), float(values.max())
        else:
            low, high = fit["mean"] - 8 * fit["sigma"], fit["mean"] + 8 * fit["sigma"]
        ax.hist(values, bins=BINS, range=(low, high), color=figures.HISTOGRAM)
        if "error" not in fit:
            ax.axvspan(*fit["window"], color="lightgrey", alpha=0.5, zorder=0)
            grid = np.linspace(low, high, 400)
            ax.plot(
                grid,
                truncated_curve(grid, fit, (high - low) / BINS),
                color="black",
                label=f"σ = {fit['sigma']:.2f} μm",
            )
            ax.legend()
        ax.set_xlabel(figures.label(f"Residual {axis}", "um"))
        ax.set_ylabel("Events")
    return figures.save(figure, path, "residual", slot)
