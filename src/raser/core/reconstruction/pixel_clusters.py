"""Clusters of a pixel device: fired pixels joined over the 2D array.

A pixel is (i_x, i_y) with i_x < n_x along x and i_y < n_y along y; its
electrode index is k = i_x * n_y + i_y and its centre in the coordinates of
the device is ((i_x + 0.5) * p_x, (i_y + 0.5) * p_y) [um].

Arrays of a job, one row per event:
    fired   (events, n_x, n_y), bool: the pixel is above threshold
    weight  (events, n_x, n_y), float: what the seed of a cluster is looked
            for in; the amplitude [V] of a pixel, or the pairs of a deposit

Columns `pixel_cluster_columns` gives, each of length events:
    clusters         number of clusters of the event
    cluster_x, cluster_y
                     position of the cluster in the device [um]; NaN unless
                     the event has one cluster
    cluster_pixels   pixels of the cluster; 0 unless the event has one cluster
    cluster_seed     electrode index of the pixel of the cluster with the
                     largest weight; -1 unless the event has one cluster
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage

from raser.supports import figures

from .event_table import EventTable

CLUSTER_COLUMNS = (
    "clusters",
    "cluster_x",
    "cluster_y",
    "cluster_pixels",
    "cluster_seed",
)
# the eight neighbours of a pixel, the diagonal ones included
EIGHT_NEIGHBOURS = np.ones((3, 3), dtype=int)


def pixel_clusters(
    fired_event: np.ndarray,
    weight_event: np.ndarray,
    seed_threshold: float,
    p_x: float,
    p_y: float,
) -> list[tuple[float, float, int, int]]:
    """Clusters (x_c, y_c, n_c, seed_k) of one event, ascending in seed_k.

    fired_event, weight_event : (n_x, n_y); a connected set of fired pixels is
        a cluster when one of its pixels has weight >= seed_threshold. The
        position [um] is the mean of the centres of its n_c pixels, the seed
        its pixel of the largest weight, the lower k among equal ones.
    """
    if fired_event.shape != weight_event.shape:
        raise ValueError(
            f"fired has shape {fired_event.shape}, weight {weight_event.shape}"
        )
    n_y = fired_event.shape[1]
    labels, count = ndimage.label(fired_event, structure=EIGHT_NEIGHBOURS)
    found = []
    for label in range(1, count + 1):
        i_x, i_y = np.nonzero(labels == label)  # ascending in k
        weights = weight_event[i_x, i_y]
        if not np.any(weights >= seed_threshold):
            continue
        # a NaN weight is no seed
        seed = int(np.argmax(np.where(np.isnan(weights), -np.inf, weights)))
        x_c = float(np.mean((i_x + 0.5) * p_x))
        y_c = float(np.mean((i_y + 0.5) * p_y))
        found.append((x_c, y_c, len(i_x), int(i_x[seed] * n_y + i_y[seed])))
    return sorted(found, key=lambda cluster: cluster[3])


def pixel_cluster_columns(
    fired: np.ndarray,
    weight: np.ndarray,
    seed_threshold: float,
    p_x: float,
    p_y: float,
) -> dict[str, np.ndarray]:
    """The columns of CLUSTER_COLUMNS of the events of a job.

    fired, weight : (events, n_x, n_y)
    """
    if fired.ndim != 3 or fired.shape != weight.shape:
        raise ValueError(
            f"fired has shape {fired.shape}, weight {weight.shape}, expected (events, n_x, n_y) for both"
        )
    events = len(fired)
    columns = {
        "clusters": np.zeros(events, dtype="int64"),
        "cluster_x": np.full(events, np.nan),
        "cluster_y": np.full(events, np.nan),
        "cluster_pixels": np.zeros(events, dtype="int64"),
        "cluster_seed": np.full(events, -1, dtype="int64"),
    }
    for row in range(events):
        found = pixel_clusters(fired[row], weight[row], seed_threshold, p_x, p_y)
        columns["clusters"][row] = len(found)
        if len(found) == 1:
            x_c, y_c, n_c, seed = found[0]
            columns["cluster_x"][row] = x_c
            columns["cluster_y"][row] = y_c
            columns["cluster_pixels"][row] = n_c
            columns["cluster_seed"][row] = seed
    return columns


def fired_from_table(
    table: EventTable, n_x: int, n_y: int
) -> tuple[np.ndarray, np.ndarray, float]:
    """(fired, weight, seed_threshold) of the pixels of an event table: the
    columns above and amplitude [V] by electrode index k = i_x * n_y + i_y,
    and its amplitude_threshold."""
    if len(table.electrodes) != n_x * n_y:
        raise ValueError(
            f"the table has {len(table.electrodes)} electrodes, a {n_x} x {n_y} array has {n_x * n_y}"
        )
    events = len(table)
    fired = table.columns["above"].reshape(events, n_x, n_y)
    weight = table.columns["amplitude"].reshape(events, n_x, n_y)
    return fired, weight, table.amplitude_threshold


def fired_from_deposits(
    deposits, slot: str, device
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """(events, fired, weight, seed_threshold) of the deposits of a detector.

    A step of `slot` with pairs > 0 inside the device fires the pixel it lies
    in, and its pairs add to the weight of that pixel. events are the Geant4
    event numbers of all recorded events, seed_threshold is 0.
    """
    n_x, n_y = device.x_ele_num, device.y_ele_num
    events = np.array([record.event for record in deposits.events], dtype="int64")
    fired = np.zeros((len(events), n_x, n_y), dtype=bool)
    weight = np.zeros((len(events), n_x, n_y))
    for row, record in enumerate(deposits.events):
        if record.pairs is None:
            raise ValueError(
                f"event {record.event} has no pairs: the ionization is not drawn"
            )
        names = np.array(record.detector)
        x, y, z = (
            np.array(values, dtype="float64")
            for values in (record.x, record.y, record.z)
        )
        pairs = np.array(record.pairs, dtype="float64")
        inside = (
            (names == slot)
            & (pairs > 0)
            & (x >= 0)
            & (x <= device.l_x)
            & (y >= 0)
            & (y <= device.l_y)
            & (z >= 0)
            & (z <= device.l_z)
        )
        i_x = np.floor(x[inside] / device.p_x).astype(int)
        i_y = np.floor(y[inside] / device.p_y).astype(int)
        # a step on the far edge of the device lies beyond the last pixel
        on_array = (i_x < n_x) & (i_y < n_y)
        np.add.at(weight[row], (i_x[on_array], i_y[on_array]), pairs[inside][on_array])
        fired[row] = weight[row] > 0
    return events, fired, weight, 0.0


def table_from_deposits(deposits, slot: str, device) -> EventTable:
    """Event table with the event, selected and CLUSTER_COLUMNS columns from
    the deposits of a detector."""
    events, fired, weight, seed_threshold = fired_from_deposits(deposits, slot, device)
    columns = pixel_cluster_columns(
        fired, weight, seed_threshold, device.p_x, device.p_y
    )
    return EventTable(
        electrodes=[],
        threshold=0.0,
        amplitude_threshold=0.0,
        fractions=(),
        edges=[],
        columns={"event": events, "selected": columns["clusters"] > 0, **columns},
    )


def draw_hitmap(table: EventTable, device, path, slot: str | None = None) -> Path:
    """Draw the positions of the events with one cluster, a bin per pixel,
    as `hitmap` or `hitmap_<slot>` in the folder `path`; returns the png."""
    one = table.columns["clusters"] == 1
    figure, axes = figures.new()
    image = axes.hist2d(
        table.columns["cluster_x"][one],
        table.columns["cluster_y"][one],
        bins=[device.x_ele_num, device.y_ele_num],
        range=[[0, device.l_x], [0, device.l_y]],
        cmap="viridis",
    )[3]
    figure.colorbar(image, ax=axes, label="Clusters")
    axes.set_xlabel(figures.label("x", "um"))
    axes.set_ylabel(figures.label("y", "um"))
    if slot is None:
        return figures.save(figure, path, "hitmap")
    return figures.save(figure, path, "hitmap", slot)
