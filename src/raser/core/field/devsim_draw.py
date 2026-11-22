#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
Description:  This module is for drawing IV, CV, noise, electron, hole, electric field plots.
@Date       : 2023
@Author     : Tao Yang, Xingchen Li, Zaiyi Li
@version    : 2.0
"""

import csv
from array import array
import os

import numpy as np
import ROOT
from raser.supports import figures
ROOT.gROOT.SetBatch(True)
import matplotlib.pyplot
import matplotlib.tri

from raser.supports.output import output

OUTLIER_DECADES = 6  # a point this far below the median of its curve is not drawn


def draw_iv(V, I, path):
    """Write the IV points as `simIV<min>to<max>.root` and draw `iv` into `<path>/plots`.

    V [V] and I [A] are lists of the same length; the figure shows |V| and |I|.
    """
    file = ROOT.TFile(os.path.join(path, "simIV{}to{}.root".format(min(V),max(V))), "RECREATE")
    tree = ROOT.TTree("SicarTestIV", "SicarTest with impactgen")
    x = array('d', [0])
    y = array('d', [0])

    tree.Branch("voltage", x, "x/D")
    tree.Branch("Current", y, "y/D")

    for point in zip(V,I):
        x[0], y[0] = point
        tree.Fill()

    file.Write()
    file.Close()

    figure, axis = figures.new()
    # a point far below the rest of its curve, as the one at 0 V beside
    # currents of pA, hides the curve on the log axis: it is left out of the
    # figure (the file keeps it). A curve that is small as a whole is drawn
    # as it is
    bias, current = np.abs(V), np.abs(I)
    kept = current > np.median(current) / 10**OUTLIER_DECADES
    axis.plot(bias[kept], current[kept], color=figures.TOTAL, marker="o", markersize=3)
    axis.set_yscale("log")
    axis.set_xlabel(figures.label("Reverse bias", "V"))
    axis.set_ylabel(figures.label("Leakage current", "A"))
    figures.save(figure, os.path.join(path, "plots"), "iv")


def draw_noise(V, noise, path):
    """Write the noise points as `simnoise<min>to<max>.root` and draw `noise` into `<path>/plots`.

    V [V] and noise [A] are lists of the same length.
    """
    file = ROOT.TFile(os.path.join(path, "simnoise{}to{}.root".format(min(V),max(V))), "RECREATE")
    tree = ROOT.TTree("SicarTestnoise", "SicarTest with impactgen")
    x = array('d', [0])
    y = array('d', [0])

    tree.Branch("voltage", x, "x/D")
    tree.Branch("Current", y, "y/D")

    for point in zip(V,noise):
        x[0], y[0] = point
        tree.Fill()

    file.Write()
    file.Close()

    figure, axis = figures.new()
    axis.plot(np.abs(V), np.abs(noise), color=figures.TOTAL, marker="o", markersize=3)
    axis.set_yscale("log")
    axis.set_xlabel(figures.label("Reverse bias", "V"))
    axis.set_ylabel(figures.label("Noise current", "A"))
    figures.save(figure, os.path.join(path, "plots"), "noise")


def draw_cv(V, C, path):
    """Write the CV points as `simCV<min>to<max>.root` and draw `cv` into `<path>/plots`.

    V [V] and C [pF] are lists of the same length; the figure shows C and
    1/C^2 against |V|.
    """
    file = ROOT.TFile(os.path.join(path, "simCV{}to{}.root".format(min(V),max(V))), "RECREATE")
    tree = ROOT.TTree("SicarTestCV", "SicarTest with impactgen")
    x = array('d', [0])
    y = array('d', [0])

    tree.Branch("voltage", x, "x/D")
    tree.Branch("CAP", y, "y/D")

    for point in zip(V,C):
        x[0], y[0] = point
        tree.Fill()

    file.Write()
    file.Close()

    bias = np.abs(V)
    capacitance = np.asarray(C, dtype=float)
    figure, (left, right) = figures.new(1, 2)
    left.plot(bias, capacitance, color=figures.TOTAL, marker="o", markersize=3)
    left.set_xlabel(figures.label("Reverse bias", "V"))
    left.set_ylabel(figures.label("Capacitance", "pF"))
    right.plot(bias, 1 / capacitance**2, color=figures.TOTAL, marker="o", markersize=3)
    right.set_xlabel(figures.label("Reverse bias", "V"))
    right.set_ylabel(r"$1/C^2$ [pF$^{-2}$]")
    figures.save(figure, os.path.join(path, "plots"), "cv")

def draw_electrons(device, positions, electrons, bias_voltages,path):
    fig1=matplotlib.pyplot.figure()
    ax1 = fig1.add_subplot(111)
    for x,n,V in zip(positions, electrons, bias_voltages):
        matplotlib.pyplot.plot(x,n,label="%s"%(str(V)))
    matplotlib.pyplot.xlabel('Depth [cm]')
    matplotlib.pyplot.ylabel('Electron Density [cm^{-3}]')
    matplotlib.pyplot.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    matplotlib.pyplot.yscale('log')
    ax1.legend(loc='upper right')
    if device == "SICAR-1.1.8":
        ax1.set_xlim(0,5e-4)
    fig1.show()
     
    fig1.savefig(os.path.join(path, "{}_electrons.png".format(device)))
    fig1.clear()

def draw_holes(device, positions, holes, bias_voltages,path):
    fig1=matplotlib.pyplot.figure()
    ax1 = fig1.add_subplot(111)
    for x,p,V in zip(positions, holes, bias_voltages):
        matplotlib.pyplot.plot(x,p,label="%s"%(str(V)))
    matplotlib.pyplot.xlabel('Depth [cm]')
    matplotlib.pyplot.ylabel('Hole Density [cm^{-3}]')
    matplotlib.pyplot.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    matplotlib.pyplot.yscale('log')

    ax1.legend(loc='upper right')
    if device == "SICAR-1.1.8":
        ax1.set_xlim(0,5e-4)
    fig1.show()
     
    fig1.savefig(os.path.join(path, "{}_holes.png".format(device)))
    fig1.clear()

def draw_field(device, positions,intensities, bias_voltages,path):
    fig1=matplotlib.pyplot.figure()
    ax1 = fig1.add_subplot(111)
    for x,E,V in zip(positions,intensities, bias_voltages):
        matplotlib.pyplot.plot(x,E,label="%s"%(str(V)))
    matplotlib.pyplot.xlabel('Depth [cm]')
    matplotlib.pyplot.ylabel('E (V/cm)')
    matplotlib.pyplot.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    ax1.legend(loc='upper right')
    if device == "SICAR-1.1.8":
        ax1.set_xlim(0,5e-4)
    fig1.show()
     
    fig1.savefig(os.path.join(path, "{}_electricfield.png".format(device)))
    fig1.clear()

def save_field(device, positions, intensities, bias_voltages,path):
    for x,E,V in zip(positions,intensities, bias_voltages):
        header_iv = ["Depth [cm]","E (V/cm)"]
         
        f=open(os.path.join(path, str(V)+'V_x_E.csv'),'w')
        writer_E = csv.writer(f)
        writer_E.writerow(header_iv)
        for per_x,per_E in zip(x,E):
            writer_E.writerow([float(per_x),float(per_E)])

def doping_boundaries(depth, doping):
    """Depths [um] of the boundaries inside the device, ascending.

    depth is the ascending depth [um]; doping is the net doping at the same
    points, in any unit. A boundary lies midway between two neighbouring points
    whose |doping| differs by more than a factor of ten (one of them may be 0).
    Boundaries closer than 0.5 um to each other are merged into their mean.
    """
    magnitude = np.abs(np.asarray(doping, dtype=float))
    depth = np.asarray(depth, dtype=float)
    low = np.minimum(magnitude[:-1], magnitude[1:])
    high = np.maximum(magnitude[:-1], magnitude[1:])
    middles = 0.5 * (depth[:-1] + depth[1:])[(high > 10 * low) & (high > 0)]
    merged = []
    group = []
    for position in middles:
        if group and position - group[-1] >= 0.5:
            merged.append(float(np.mean(group)))
            group = []
        group.append(float(position))
    if group:
        merged.append(float(np.mean(group)))
    return merged


def draw_profile(x, curves, ylabel, path, name, *suffixes, log=False, boundaries=()):
    """Draw curves against the depth into `<path>/plots` as `<name>_<suffixes>`.

    x is the depth [um]; curves is a list of (y, color, legend text or None),
    y in the unit of ylabel; log makes the vertical axis logarithmic;
    boundaries are the depths [um] of the boundaries inside the device, each
    drawn as a thin dashed vertical line.
    """
    figure, axis = figures.new()
    for depth in boundaries:
        axis.axvline(depth, color="0.5", linestyle="--", linewidth=0.8)
    for y, color, text in curves:
        axis.plot(x, y, color=color, label=text)
    if log:
        axis.set_yscale("log")
    axis.set_xlabel(figures.label("Depth", "um"))
    axis.set_ylabel(ylabel)
    if any(text is not None for _, _, text in curves):
        axis.legend()
    figures.save(figure, os.path.join(path, "plots"), name, *suffixes)


PROFILE_POINTS = 400  # points of a profile line
SLICE_POINTS = 200  # points of a 3D slice along each of its two directions
PAIRS_PER_CHUNK = 2_000_000  # point-element pairs judged at once
INSIDE_TOLERANCE = 1e-9  # barycentric coordinates down to this below 0 are inside


def _um(x_cm):
    """Positions [cm] of the field solver in um."""
    return np.asarray(x_cm) * 1e-2 / figures.UNIT["um"]


def _simplices(points, elements):
    """Origin vertex, edge matrix (rows: the other vertices minus the origin)
    and its determinant of each simplex; points (N, d), elements (M, d + 1)."""
    points = np.asarray(points, dtype=float)
    elements = np.asarray(elements, dtype=int)
    if points.ndim != 2 or elements.ndim != 2 or elements.shape[1] != points.shape[1] + 1:
        raise ValueError(
            f"points {points.shape} and elements {elements.shape} do not make simplices: "
            "elements must be (M, d + 1) for points (N, d)")
    vertices = points[elements]  # (M, d + 1, d)
    origin = vertices[:, 0, :]
    edges = vertices[:, 1:, :] - origin[:, None, :]
    return origin, edges, np.linalg.det(edges)


def field_strength_at_nodes(points, elements, potential):
    """|grad potential| at the nodes of a mesh of triangles (d = 2) or tetrahedra (d = 3).

    points (N, d) [cm], elements (M, d + 1) node indices, potential (N,) [V].
    On each element the potential is linear between its nodes, which gives a
    constant gradient; a node takes the mean of the moduli of its elements,
    weighted by their area (volume). Returns (N,) [V/cm]; a node of no
    element, or of degenerate elements only, is nan.
    """
    potential = np.asarray(potential, dtype=float)
    elements = np.asarray(elements, dtype=int)
    origin, edges, determinant = _simplices(points, elements)
    if potential.shape != (len(np.asarray(points)),):
        raise ValueError(f"potential {potential.shape} does not match {len(np.asarray(points))} points")
    proper = determinant != 0
    dimension = edges.shape[1]
    factorial = float(np.prod(np.arange(1, dimension + 1)))
    measure = np.abs(determinant[proper]) / factorial
    drop = potential[elements[proper][:, 1:]] - potential[elements[proper][:, :1]]
    gradient = np.linalg.solve(edges[proper], drop[:, :, None])[:, :, 0]
    modulus = np.linalg.norm(gradient, axis=1)
    nodes = elements[proper].ravel()
    count = len(potential)
    weight = np.bincount(nodes, weights=np.repeat(measure, dimension + 1), minlength=count)
    total = np.bincount(nodes, weights=np.repeat(measure * modulus, dimension + 1), minlength=count)
    strength = np.full(count, np.nan)
    covered = weight > 0
    strength[covered] = total[covered] / weight[covered]
    return strength


def interpolate_on_elements(points, elements, values, queries):
    """Linear interpolation of node values on simplices at query points.

    points (N, d), elements (M, d + 1), values (N,), queries (K, d), in the
    same unit of length. A query inside an element, its boundary included
    (barycentric coordinates down to -1e-9), takes the barycentric
    interpolation of that element; one inside none is nan. Returns (K,).
    """
    values = np.asarray(values, dtype=float)
    queries = np.asarray(queries, dtype=float)
    elements = np.asarray(elements, dtype=int)
    origin, edges, determinant = _simplices(points, elements)
    if queries.ndim != 2 or queries.shape[1] != origin.shape[1]:
        raise ValueError(f"queries {queries.shape} do not match points of dimension {origin.shape[1]}")
    result = np.full(len(queries), np.nan)
    proper = determinant != 0
    elements, origin, edges = elements[proper], origin[proper], edges[proper]
    if len(elements) == 0 or len(queries) == 0:
        return result

    # only the elements whose box meets the box of the queries are judged
    vertices = np.asarray(points, dtype=float)[elements]
    low, high = vertices.min(axis=1), vertices.max(axis=1)
    meets = np.all((high >= queries.min(axis=0)) & (low <= queries.max(axis=0)), axis=1)
    elements, origin, edges = elements[meets], origin[meets], edges[meets]
    if len(elements) == 0:
        return result

    # lambda_1..d = (q - origin) inverse(edges); lambda_0 = 1 - their sum
    inverse = np.linalg.inv(edges)
    node_values = values[elements]
    step = max(1, PAIRS_PER_CHUNK // len(elements))
    for start in range(0, len(queries), step):
        chunk = queries[start:start + step]
        offset = chunk[:, None, :] - origin[None, :, :]  # (k, m, d)
        coordinates = np.einsum("kmj,mji->kmi", offset, inverse)
        first = 1.0 - coordinates.sum(axis=2)
        inside = np.all(coordinates >= -INSIDE_TOLERANCE, axis=2) & (first >= -INSIDE_TOLERANCE)
        found = inside.any(axis=1)
        which = inside.argmax(axis=1)[found]
        rows = np.flatnonzero(found)
        interpolated = (
            first[rows, which] * node_values[which, 0]
            + np.einsum("ki,ki->k", coordinates[rows, which], node_values[which, 1:])
        )
        result[start + rows] = interpolated
    return result


def profile_positions(axes, points, electrode=None):
    """The profile lines drawn of a 2D or 3D field.

    axes is the tuple of mesh_axes, points (N, d) the nodes in that order.
    Returns a list of (name, start, end, along): the line runs from start to
    end (arrays of d coordinates) along the axis `along`. "Middle" is
    (min + max) / 2 of the coordinate over the points.

    - with a depth ("z" in axes): "depth" along z, at the middle of the
      lateral coordinates, or at their mean over the electrode nodes (n, d)
      when given; "lateral" along x, at the middle of the others;
    - a cross section ("x", "y"): "x" along x at the middle of y, "y" along
      y at the middle of x.
    """
    points = np.asarray(points, dtype=float)
    axes = tuple(axes)
    if points.ndim != 2 or points.shape[1] != len(axes):
        raise ValueError(f"points {points.shape} do not match the axes {axes}")
    low, high = points.min(axis=0), points.max(axis=0)
    middle = (low + high) / 2

    def line(along, at):
        start, end = np.array(at, dtype=float), np.array(at, dtype=float)
        start[axes.index(along)], end[axes.index(along)] = low[axes.index(along)], high[axes.index(along)]
        return start, end

    if "z" not in axes:
        if axes != ("x", "y"):
            raise ValueError(f"axes {axes} have neither a depth nor the cross section (x, y)")
        return [(name, *line(name, middle), name) for name in ("x", "y")]

    depth_at = middle.copy()
    if electrode is not None:
        electrode = np.asarray(electrode, dtype=float)
        if electrode.ndim != 2 or electrode.shape[1] != len(axes) or len(electrode) == 0:
            raise ValueError(f"electrode {electrode.shape} does not match the axes {axes}")
        depth_at = electrode.mean(axis=0)
    return [("depth", *line("z", depth_at), "z"), ("lateral", *line("x", middle), "x")]


NEARLY_CONSTANT = 1e-6  # a spread this small against the values is numerical


def value_limits(values):
    """Limits of the axis and colour scale of a field that is constant up to
    numerical noise, which left alone fills the ticks with digits: 5 % either
    side of its mean. None when the field varies, for the usual limits."""
    values = np.asarray(values, dtype=float)
    low, high = np.nanmin(values), np.nanmax(values)
    middle = (low + high) / 2
    if high - low > NEARLY_CONSTANT * max(abs(low), abs(high)):
        return None
    if middle == 0:
        return -1.0, 1.0
    return middle - 0.05 * abs(middle), middle + 0.05 * abs(middle)


def _axis_label(along):
    return figures.label("Depth" if along == "z" else along, "um")


def _along_line(points, elements, values, axes, start, end, along):
    """The coordinate along the line [um] and the values on it."""
    parameter = np.linspace(0.0, 1.0, PROFILE_POINTS)
    line = start[None, :] + parameter[:, None] * (end - start)[None, :]
    return _um(line[:, axes.index(along)]), interpolate_on_elements(points, elements, values, line)


def draw_field_map(points, elements, values, axes, label, path, name, *suffixes, electrode=None):
    """Draw a field of a 2D or 3D device into `<path>/plots`: the slice, the
    profile along the depth and the profile across it.

    points (N, d) [cm] and elements (M, d + 1) are the mesh, values (N,) the
    field at its nodes in the unit of `label` (an axis title such as
    "Electric field [kV/cm]"), axes the mesh_axes of the points. The slice is
    the whole mesh in 2D and, in 3D, the x-depth plane through the middle of y.
    electrode (n, d) places the depth profile under that electrode.
    """
    points = np.asarray(points, dtype=float)
    values = np.asarray(values, dtype=float)
    axes = tuple(axes)
    vertical = "z" if "z" in axes else "y"
    horizontal = axes.index("x")
    figure, (surface, first, second) = figures.new(1, 3)
    limits = value_limits(values) or (None, None)

    if len(axes) == 2:
        triangulation = matplotlib.tri.Triangulation(
            _um(points[:, horizontal]), _um(points[:, axes.index(vertical)]), np.asarray(elements, dtype=int))
        shown = surface.tripcolor(
            triangulation, values, shading="gouraud", cmap="viridis",
            vmin=limits[0], vmax=limits[1])
    else:
        low, high = points.min(axis=0), points.max(axis=0)
        across = np.linspace(low[horizontal], high[horizontal], SLICE_POINTS)
        depth = np.linspace(low[axes.index("z")], high[axes.index("z")], SLICE_POINTS)
        grid_across, grid_depth = np.meshgrid(across, depth)
        queries = np.empty((grid_across.size, 3))
        queries[:, horizontal] = grid_across.ravel()
        queries[:, axes.index("z")] = grid_depth.ravel()
        queries[:, axes.index("y")] = (low[axes.index("y")] + high[axes.index("y")]) / 2
        slice_values = interpolate_on_elements(points, elements, values, queries).reshape(grid_across.shape)
        shown = surface.pcolormesh(
            _um(grid_across), _um(grid_depth), np.ma.masked_invalid(slice_values), shading="auto", cmap="viridis",
            vmin=limits[0], vmax=limits[1])
    colorbar = figure.colorbar(shown, ax=surface)
    colorbar.set_label(label)
    surface.set_xlabel(_axis_label("x"))
    surface.set_ylabel(_axis_label(vertical))

    for axis, (_, start, end, along) in zip(
        (first, second), profile_positions(axes, points, electrode)
    ):
        position, line_values = _along_line(points, elements, values, axes, start, end, along)
        axis.plot(position, line_values, color=figures.TOTAL)
        if limits[0] is not None:
            axis.set_ylim(*limits)
        axis.set_xlabel(_axis_label(along))
        axis.set_ylabel(label)
    figures.save(figure, os.path.join(path, "plots"), name, *suffixes)


def draw_depth_profiles(points, elements, curves, axes, ylabel, path, name, *suffixes, log=False):
    """Draw curves of node values along the first profile line of the mesh
    (the depth; along x in a cross section) into `<path>/plots`.

    points (N, d) [cm], elements (M, d + 1), axes the mesh_axes of the
    points; curves is a list of (values (N,), color, legend text or None),
    values in the unit of ylabel; log makes the vertical axis logarithmic.
    """
    points = np.asarray(points, dtype=float)
    axes = tuple(axes)
    _, start, end, along = profile_positions(axes, points)[0]
    figure, axis = figures.new()
    for values, color, text in curves:
        position, line_values = _along_line(points, elements, values, axes, start, end, along)
        axis.plot(position, line_values, color=color, label=text)
    if log:
        axis.set_yscale("log")
    axis.set_xlabel(_axis_label(along))
    axis.set_ylabel(ylabel)
    if any(text is not None for _, _, text in curves):
        axis.legend()
    figures.save(figure, os.path.join(path, "plots"), name, *suffixes)
