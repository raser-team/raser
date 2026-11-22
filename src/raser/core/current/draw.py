"""Plots of induced currents and collected charges."""

from array import array
import logging

import numpy as np
import ROOT

from raser.supports import figures

ROOT.gROOT.SetBatch(True)

logger = logging.getLogger(__name__)

ELECTRON_CHARGE = 1.6e-19  # C


def _histogram(name, values, t0, dt):
    histogram = ROOT.TH1F(name, "", len(values), t0, t0 + len(values) * dt)
    for index, value in enumerate(values, start=1):
        histogram.SetBinContent(index, float(value))
    return histogram


def draw_currents(path, event, t0, dt, current, hole_current, electron_current,
                  gain_hole_current=None, gain_electron_current=None):
    """Draw the currents of every electrode that has any, as `current_<event>`
    (`current_<event>_electrode_<number>` with several electrodes, counted
    from 1).

    The currents are arrays (electrodes, bins) in A on the time axis that
    starts at `t0` with bins of `dt` [s]; the two of the gain are drawn
    where given. An electrode without current, as most strips of a row are
    for one particle, is not drawn.
    """
    parts = [current, hole_current, electron_current, gain_hole_current, gain_electron_current]
    t0 = t0 / figures.UNIT["ns"]
    dt = dt / figures.UNIT["ns"]
    for electrode in range(len(current)):
        if not any(part[electrode].any() for part in parts if part is not None):
            continue
        canvas = figures.canvas()
        canvas.SetLeftMargin(0.12)
        canvas.SetBottomMargin(0.13)

        def scaled(part):
            return part[electrode] / figures.UNIT["uA"]

        sum_cu = _histogram("charge"+str(electrode+1), scaled(current), t0, dt)
        positive_cu = _histogram("charge+"+str(electrode+1), scaled(hole_current), t0, dt)
        negative_cu = _histogram("charge-"+str(electrode+1), scaled(electron_current), t0, dt)

        sum_cu.GetXaxis().SetTitle(figures.label("Time", "ns", root=True))
        sum_cu.GetYaxis().SetTitle(figures.label("Current", "uA", root=True))
        # the axis holds every curve, the ones of the parts included: on a
        # neighbouring electrode they can be larger than the total
        values = [scaled(part) for part in parts if part is not None]
        low = min(float(min(part)) for part in values)
        high = max(float(max(part)) for part in values)
        margin = 0.05 * (high - low)
        if margin > 0:
            sum_cu.SetMinimum(low - margin)
            sum_cu.SetMaximum(high + margin)
        time = t0 + (np.arange(len(current[electrode])) + 0.5) * dt
        start, stop = figures.signal_window(time, np.array(values))
        sum_cu.GetXaxis().SetRangeUser(start, stop)
        # the total first and wide, the parts over it: where a part is the
        # whole current, as the holes after the electrons are collected,
        # both stay in sight
        sum_cu.SetLineColor(figures.root_color(figures.TOTAL))
        sum_cu.SetLineWidth(3)
        sum_cu.Draw("HIST")
        positive_cu.SetLineColor(figures.root_color(figures.HOLE))
        negative_cu.SetLineColor(figures.root_color(figures.ELECTRON))
        positive_cu.SetLineWidth(2)
        negative_cu.SetLineWidth(2)
        positive_cu.Draw("SAME HIST")
        negative_cu.Draw("SAME HIST")

        if gain_hole_current is not None:
            gain_positive_cu = _histogram(
                "gain_charge+"+str(electrode+1), scaled(gain_hole_current), t0, dt)
            gain_negative_cu = _histogram(
                "gain_charge-"+str(electrode+1), scaled(gain_electron_current), t0, dt)
            gain_positive_cu.SetLineColor(figures.root_color(figures.GAIN_HOLE))
            gain_negative_cu.SetLineColor(figures.root_color(figures.GAIN_ELECTRON))
            gain_positive_cu.SetLineWidth(2)
            gain_negative_cu.SetLineWidth(2)
            gain_positive_cu.Draw("SAME HIST")
            gain_negative_cu.Draw("SAME HIST")

        legend = ROOT.TLegend(0.68, 0.2, 0.88, 0.45)
        legend.SetFillStyle(0)
        legend.AddEntry(negative_cu, "electrons", "l")
        legend.AddEntry(positive_cu, "holes", "l")
        if gain_hole_current is not None:
            legend.AddEntry(gain_negative_cu, "gain electrons", "l")
            legend.AddEntry(gain_positive_cu, "gain holes", "l")
        legend.AddEntry(sum_cu, "total", "l")
        legend.Draw("same")
        canvas.Update()

        if len(current) == 1:
            figures.save_canvas(canvas, path, "current", event)
        else:
            figures.save_canvas(canvas, path, "current", event, "electrode", electrode + 1)
        del canvas


def electrode_edges(length, number, pitch):
    """Edges [um] of `number` electrodes of `pitch`, centred in `length`."""
    first = (length - number * pitch) / 2
    return [first + k * pitch for k in range(number + 1)]


def electrode_centers(length, number, pitch):
    """Centres [um] of `number` electrodes of `pitch`, centred in `length`."""
    first = (length - number * pitch) / 2
    return [first + (k + 0.5) * pitch for k in range(number)]


def pixel_cells(charge, x_ele_num, y_ele_num):
    """(ix, jy, value) of every pixel; electrode number i = ix * y_ele_num + jy."""
    return [(i // y_ele_num, i % y_ele_num, charge[i]) for i in range(x_ele_num * y_ele_num)]


def charge_collection_strip(path, event, charge, l_x, x_ele_num, p_x):
    """Draw the net charge [C] of every strip, in fC, against the x [um] of its centre."""
    electrons = [value / ELECTRON_CHARGE for value in charge]
    logger.info(
        "Collected charge of the strips that have any (number from 1: e): %s",
        {number: value for number, value in enumerate(electrons, start=1) if value},
    )
    femtocoulombs = array('d', [value / figures.UNIT["fC"] for value in charge])
    x = array('d', electrode_centers(l_x, x_ele_num, p_x))
    canvas = figures.canvas()
    canvas.SetLeftMargin(0.12)
    canvas.SetBottomMargin(0.13)
    graph = ROOT.TGraph(len(femtocoulombs), x, femtocoulombs)
    graph.SetMarkerStyle(20)
    graph.SetMarkerColor(figures.root_color(figures.TOTAL))
    graph.Draw("AP")
    graph.GetXaxis().SetTitle(figures.label("x", "um", root=True))
    graph.GetYaxis().SetTitle(figures.label("Charge", "fC", root=True))
    figures.save_canvas(canvas, path, "charge_per_electrode", event)


def pixel_histogram(charge, l_x, l_y, x_ele_num, y_ele_num, p_x, p_y):
    """The charge [C] of every pixel in fC, on the pixels' x, y [um] edges."""
    histogram = ROOT.TH2D(
        "cce", "",
        x_ele_num, array('d', electrode_edges(l_x, x_ele_num, p_x)),
        y_ele_num, array('d', electrode_edges(l_y, y_ele_num, p_y)),
    )
    for ix, jy, value in pixel_cells(charge, x_ele_num, y_ele_num):
        histogram.SetBinContent(ix + 1, jy + 1, float(value) / figures.UNIT["fC"])
    return histogram


def charge_collection_pixel(path, event, charge, l_x, l_y, x_ele_num, y_ele_num, p_x, p_y):
    """Draw the net charge [C] of every pixel, in fC, as a map over x, y [um]."""
    electrons = [value / ELECTRON_CHARGE for value in charge]
    logger.info(
        "Collected charge of the pixels that have any (number from 1: e): %s",
        {number: value for number, value in enumerate(electrons, start=1) if value},
    )
    canvas = figures.canvas()
    canvas.SetLeftMargin(0.12)
    canvas.SetRightMargin(0.15)
    canvas.SetBottomMargin(0.13)
    histogram = pixel_histogram(charge, l_x, l_y, x_ele_num, y_ele_num, p_x, p_y)
    histogram.Draw("COLZ")
    histogram.GetXaxis().SetTitle(figures.label("x", "um", root=True))
    histogram.GetYaxis().SetTitle(figures.label("y", "um", root=True))
    histogram.GetZaxis().SetTitle(figures.label("Charge", "fC", root=True))
    figures.save_canvas(canvas, path, "charge_per_electrode", event)
