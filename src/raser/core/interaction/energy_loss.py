"""Energy-loss fluctuation helpers shared by toy and Geant4 sources."""

from __future__ import annotations

import math

import ROOT

ROOT.gROOT.SetBatch(True)


def sample_fano_pairs(mean_pairs, fano_factor, rng=None):
    """Sample electron-hole pairs with variance equal to F times N."""
    mean_pairs = float(mean_pairs)
    fano_factor = float(fano_factor or 0.0)
    if mean_pairs < 0:
        raise ValueError("mean_pairs must be non-negative")
    if fano_factor < 0:
        raise ValueError("fano_factor must be non-negative")
    if fano_factor == 0.0 or mean_pairs == 0.0:
        return mean_pairs
    if rng is None:
        rng = ROOT.gRandom
    sigma = math.sqrt(fano_factor * mean_pairs)
    return max(0.0, float(rng.Gaus(mean_pairs, sigma)))


def sample_landau_energy_loss(mean_energy_mev, landau_width_mev, rng=None):
    """Sample deposited energy with ROOT's Landau distribution."""
    mean_energy_mev = float(mean_energy_mev)
    landau_width_mev = float(landau_width_mev or 0.0)
    if mean_energy_mev < 0:
        raise ValueError("mean_energy_mev must be non-negative")
    if landau_width_mev < 0:
        raise ValueError("landau_width_mev must be non-negative")
    if landau_width_mev == 0.0 or mean_energy_mev == 0.0:
        return mean_energy_mev
    if rng is None:
        rng = ROOT.gRandom
    return max(0.0, float(rng.Landau(mean_energy_mev, landau_width_mev)))
