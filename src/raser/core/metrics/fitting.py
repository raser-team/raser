"""ROOT histogram fits used by waveform metrics."""

from __future__ import annotations

import ROOT


def is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def fit_data_normal(histogram, x_min, x_max):
    fit = ROOT.TF1("fit_func_1", "gaus", x_min, x_max)
    histogram.Fit(fit, "ROQ+", "", x_min, x_max)
    return (
        fit,
        fit.GetParameter(1),
        fit.GetParError(1),
        fit.GetParameter(2),
        fit.GetParError(2),
    )


def fit_data_landau(histogram, x_min, x_max):
    fit = ROOT.TF1("fit_func_1", "landau", x_min, x_max)
    histogram.Fit(fit, "ROQ+", "", x_min, x_max)
    return (
        fit,
        fit.GetParameter(1),
        fit.GetParError(1),
        fit.GetParameter(2),
        fit.GetParError(2),
    )
