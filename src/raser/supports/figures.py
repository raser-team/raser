"""Shared style, units, colours and file names for every figure RASER draws."""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import matplotlib
import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
import ROOT

WIDTH_INCHES = 6.0
HEIGHT_INCHES = 4.0
DPI = 200
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 800

STYLE = {
    "savefig.dpi": DPI,
    "savefig.bbox": "tight",
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "legend.frameon": False,
    "axes.formatter.useoffset": False,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.top": True,
    "ytick.right": True,
}

UNIT: dict[str, float] = {
    "ns": 1e-9,
    "ps": 1e-12,
    "uA": 1e-6,
    "A": 1.0,
    "V": 1.0,
    "mV": 1e-3,
    "um": 1e-6,
    "mm": 1e-3,
    "kV/cm": 1e5,
    "cm-3": 1e6,
    "s-1": 1.0,
    "pF": 1e-12,
    "fC": 1e-15,
    "keV": 1.602176634e-16,
}

_DISPLAY = {"cm-3": "cm⁻³", "s-1": "s⁻¹"}
_ROOT_DISPLAY = {"cm-3": "cm^{-3}", "s-1": "s^{-1}"}

ELECTRON = "#1f6fb4"
HOLE = "#d1352b"
GAIN_ELECTRON = "#5bb6e8"
GAIN_HOLE = "#f08a3c"
TOTAL = "black"
DEPOSIT = "#808080"
HISTOGRAM = "#6c8ebf"

OKABE_ITO = [
    "#000000",
    "#e69f00",
    "#56b4e9",
    "#009e73",
    "#f0e442",
    "#0072b2",
    "#d55e00",
    "#cc79a7",
]

_WORD = re.compile(r"[a-z0-9]+(_[a-z0-9]+)*")
_UNIT_WORD = re.compile(r"[A-Za-z]+")
_canvas_count = itertools.count()


def new(rows: int = 1, columns: int = 1):
    """Return a styled matplotlib figure and its axes, 6 x 4 inches per panel."""
    matplotlib.rcParams.update(STYLE)
    return plt.subplots(
        rows,
        columns,
        figsize=(WIDTH_INCHES * columns, HEIGHT_INCHES * rows),
    )


def canvas(columns: int = 1, rows: int = 1) -> ROOT.TCanvas:
    """Set gStyle and return a ROOT canvas of 1200 x 800 pixels per pad."""
    style = ROOT.gStyle
    style.SetOptStat(0)
    style.SetOptTitle(0)
    style.SetTextFont(43)
    style.SetLegendFont(43)
    style.SetLegendBorderSize(0)
    style.SetLegendTextSize(20)
    style.SetLabelFont(43, "XYZ")
    style.SetTitleFont(43, "XYZ")
    style.SetTitleSize(24, "XYZ")
    style.SetLabelSize(20, "XYZ")
    style.SetPadTickX(1)
    style.SetPadTickY(1)
    style.SetPalette(ROOT.kViridis)
    result = ROOT.TCanvas(
        f"raser_canvas_{next(_canvas_count)}",
        "",
        CANVAS_WIDTH * columns,
        CANVAS_HEIGHT * rows,
    )
    result.SetCanvasSize(CANVAS_WIDTH * columns, CANVAS_HEIGHT * rows)
    if columns > 1 or rows > 1:
        result.Divide(columns, rows)
    return result


def _number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return repr(value)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _suffix(value) -> str:
    if _is_number(value):
        return _number(value)
    if isinstance(value, str) and _WORD.fullmatch(value):
        return value
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and _is_number(value[0])
        and isinstance(value[1], str)
        and _UNIT_WORD.fullmatch(value[1])
    ):
        return f"{_number(value[0])}{value[1]}"
    raise ValueError(f"figure name must be lowercase words joined by _: {value}")


def file_name(name: str, *suffixes) -> str:
    """Join a figure name and its suffixes into a file name without extension."""
    if not isinstance(name, str) or not _WORD.fullmatch(name):
        raise ValueError(f"figure name must be lowercase words joined by _: {name}")
    return "_".join([name, *(_suffix(suffix) for suffix in suffixes)])


def label(quantity: str, unit: str | None = None, root: bool = False) -> str:
    """Return the axis title `quantity [unit]`, or the quantity alone."""
    if unit is None:
        return quantity
    if unit not in UNIT:
        raise ValueError(f"unknown unit: {unit}")
    special = _ROOT_DISPLAY if root else _DISPLAY
    if unit in special:
        shown = special[unit]
    elif unit.startswith("u"):
        shown = ("#mu" if root else "μ") + unit[1:]
    else:
        shown = unit
    return f"{quantity} [{shown}]"


def series(count: int, ordered: bool) -> list[str]:
    """Return colours for `count` curves of the same kind."""
    if ordered:
        colormap = matplotlib.colormaps["viridis"]
        return [
            matplotlib.colors.to_hex(colormap(position))
            for position in np.linspace(0.0, 0.9, count)
        ]
    return [OKABE_ITO[index % len(OKABE_ITO)] for index in range(count)]


def root_color(color: str) -> int:
    """Return the ROOT colour index of a matplotlib colour."""
    return ROOT.TColor.GetColor(matplotlib.colors.to_hex(color))


def save(figure, folder: str | Path, name: str, *suffixes) -> Path:
    """Write `<file_name>.png` and `.pdf` into `folder`, close the figure, return the png."""
    stem = file_name(name, *suffixes)
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    png = destination / f"{stem}.png"
    figure.savefig(png, dpi=DPI, bbox_inches="tight")
    figure.savefig(destination / f"{stem}.pdf", bbox_inches="tight")
    plt.close(figure)
    return png


def save_canvas(canvas: ROOT.TCanvas, folder: str | Path, name: str, *suffixes) -> Path:
    """Write `<file_name>.png`, `.pdf` and `.root` into `folder`, return the png."""
    stem = file_name(name, *suffixes)
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    png = destination / f"{stem}.png"
    canvas.SaveAs(str(png))
    canvas.SaveAs(str(destination / f"{stem}.pdf"))
    canvas.SaveAs(str(destination / f"{stem}.root"))
    return png
