"""The ionized part of a dopant, in Boltzmann statistics.

N+/N = sum over the levels i of f_i / (1 + g carriers / n1_i), with
n1_i = N_band exp(-dE_i / kT): the electrons and N_c for a donor, the holes
and N_v for an acceptor. Sze and Ng, Physics of Semiconductor Devices,
3rd ed. (2007), section 1.4.3, p. 22, with E_F through the carrier density;
TCAD Parameters for 4H-SiC: A Review, arXiv:2410.06798, section 10.1.
The levels fall with the concentration of the dopant as the table gives it.
"""

import math

from .band_structure import BAND_STRUCTURE
from .dopants import DOPANTS
from .formula import Formula
from .impact_ionization import BOLTZMANN_EV_PER_K


def _levels(dopant, concentration_cm3):
    """(ionization energy [eV], fraction) of each level at this concentration."""
    fall_ev = dopant.fall_ev_cm * concentration_cm3 ** (1 / 3)
    return [(energy - fall_ev, fraction) for energy, fraction in dopant.levels]


def ionized_fraction(material, element, concentration_cm3=0.0):
    """The fraction of `element` in `material`, at `concentration_cm3`, that
    is ionized: a formula of `carriers` [cm^-3], `N_band` [cm^-3] and the
    temperature `T` [K]."""
    dopant = DOPANTS[material][element]
    terms = []
    parameters = {"g": dopant.degeneracy, "k": BOLTZMANN_EV_PER_K}
    for i, (energy, fraction) in enumerate(_levels(dopant, concentration_cm3)):
        # f n1/(n1 + g carriers): n1 may underflow to zero at freeze-out;
        # without carriers every dopant is ionized
        n1 = f"N_band*exp(-E{i}/(k*T))"
        terms.append(f"ifelse(carriers > 0, f{i}*{n1}/({n1} + g*carriers), f{i})")
        parameters[f"f{i}"] = fraction
        parameters[f"E{i}"] = energy
    return Formula(" + ".join(terms), ["carriers", "N_band", "T"], **parameters)


def free_holes(material, element, acceptors_cm3, donors_cm3, temperature_k):
    """Free holes [cm^-3] of a layer of `material` with `acceptors_cm3` of the
    acceptor `element`, partly ionized, and `donors_cm3` of compensating
    donors, fully ionized; electrons and n_i neglected. The neutrality
    p (p + N_D) = (N_A - N_D) p1/g, p1 = N_v exp(-dE/kT), solved for p:
    Spera et al., Mater. Sci. Semicond. Process. 93 (2019) 274, eqs. 5, 6.
    """
    dopant = DOPANTS[material][element]
    if dopant.kind != "acceptor" or len(dopant.levels) != 1:
        raise ValueError(f"{element} in {material} is not an acceptor of one level")
    ((level_ev, _),) = _levels(dopant, acceptors_cm3)
    freed_cm3 = (
        BAND_STRUCTURE[material]["N_v"].value(T=temperature_k)
        / dopant.degeneracy
        * math.exp(-level_ev / (BOLTZMANN_EV_PER_K * temperature_k))
    )
    taken_cm3 = donors_cm3 + freed_cm3
    return (
        math.sqrt(taken_cm3**2 + 4 * freed_cm3 * (acceptors_cm3 - donors_cm3))
        - taken_cm3
    ) / 2
