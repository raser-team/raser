"""Resistance of a layer of 4H-SiC implanted with aluminium.

The model and its numbers are those of Spera et al., arXiv:2001.08021
(layers of 300 nm with 1e20 cm^-3 of aluminium implanted at 500 C, annealed
at 1675 to 1825 C, measured at room temperature).
"""

import math

import numpy as np

from raser.core.model.incomplete_ionization import free_holes
from raser.core.model.material import Material

ELEMENTARY_CHARGE_C = 1.602176634e-19
BOLTZMANN_EV_K = 8.617333262e-5

# Spera et al., the layers they measured
IMPLANTED_CM3 = 1e20
THICKNESS_CM = 300e-7
MEASURED_K = 300.0
# tables 1 and 2: temperature of the anneal [C], acceptors [cm^-3],
# compensating donors [cm^-3], Hall mobility of the holes [cm^2 / V s],
# resistance of a square [Ohm]
ANNEALED = (
    (1675.0, 3.87e19, 3.66e18, 26.7, 12000.0),
    (1775.0, 4.84e19, 3.49e18, 22.1, 9750.0),
    (1825.0, 5.64e19, 3.48e18, 20.8, 7470.0),
)
ZERO_CELSIUS_K = 273.15


def _fits():
    """What follows from the measured layers: the slope and the intercept of
    ln(acceptors / implanted) against 1 / (k T of the anneal), the donors per
    implanted atom, and the measured mobility over that of the drift."""
    anneal_c, acceptors, donors, mobility, _ = np.array(ANNEALED).T
    slope, intercept = np.polyfit(
        1 / (BOLTZMANN_EV_K * (anneal_c + ZERO_CELSIUS_K)),
        np.log(acceptors / IMPLANTED_CM3),
        1,
    )
    of_drift = Material("SiC").cal_mobility(MEASURED_K, IMPLANTED_CM3, 1, 0)
    return (
        slope,
        intercept,
        np.mean(donors) / IMPLANTED_CM3,
        np.mean(mobility) / of_drift,
    )


ACTIVATION_SLOPE_EV, ACTIVATION_INTERCEPT, DONORS_PER_IMPLANTED, MOBILITY_LEFT = _fits()


def activated(anneal_c):
    """Part of the implanted aluminium that sits as an acceptor after an
    anneal at anneal_c [C]: the Arrhenius line through the measured layers,
    not above 1. The layers were annealed at 1675 to 1825 C; outside that
    range, e.g. at the 1500 C of sicar3, the line is extrapolated."""
    kt_ev = BOLTZMANN_EV_K * (anneal_c + ZERO_CELSIUS_K)
    return min(1.0, math.exp(ACTIVATION_INTERCEPT + ACTIVATION_SLOPE_EV / kt_ev))


def holes(acceptors_cm3, donors_cm3, temperature_k):
    """Free holes [cm^-3] of a layer with aluminium acceptors that are partly
    ionized and compensating donors: the level and the neutrality of
    core/model, Spera et al., eqs. 5, 6 and 13."""
    return free_holes("SiC", "Al", acceptors_cm3, donors_cm3, temperature_k)


def sheet_resistance(dose_cm2, thickness_cm, anneal_c, temperature_k):
    """Resistance of a square [Ohm] of the implanted layer, away from any
    field.

    dose_cm2 : implanted aluminium per area [cm^-2].
    thickness_cm : thickness of the layer, over which the dose is taken as
        uniform [cm].
    anneal_c : temperature of the anneal after the implantation [C].
    temperature_k : temperature of the layer [K].

    The compensating donors are taken in proportion to the implanted
    aluminium, and the mobility of the holes is that of the drift at the
    implanted concentration, lowered as in the measured layers.
    """
    implanted_cm3 = dose_cm2 / thickness_cm
    holes_cm3 = holes(
        implanted_cm3 * activated(anneal_c),
        implanted_cm3 * DONORS_PER_IMPLANTED,
        temperature_k,
    )
    mobility_cm2_vs = MOBILITY_LEFT * Material("SiC").cal_mobility(
        temperature_k, implanted_cm3, 1, 0
    )
    return 1 / (ELEMENTARY_CHARGE_C * holes_cm3 * thickness_cm * mobility_cm2_vs)
