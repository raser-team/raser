"""The ionized part of a dopant, in Boltzmann statistics.

N+/N = sum over the levels i of f_i / (1 + g carriers / n1_i), with
n1_i = N_band exp(-dE_i / kT): the electrons and N_c for a donor, the holes
and N_v for an acceptor. Sze and Ng, Physics of Semiconductor Devices,
3rd ed. (2007), section 1.4.3, p. 22, with E_F through the carrier density;
TCAD Parameters for 4H-SiC: A Review, arXiv:2410.06798, section 10.1.
"""

from .dopants import DOPANTS
from .formula import Formula
from .impact_ionization import BOLTZMANN_EV_PER_K


def ionized_fraction(material, element):
    """The fraction of `element` in `material` that is ionized, a formula of
    `carriers` [cm^-3], `N_band` [cm^-3] and the temperature `T` [K]."""
    dopant = DOPANTS[material][element]
    terms = []
    parameters = {"g": dopant.degeneracy, "k": BOLTZMANN_EV_PER_K}
    for i, (energy, fraction) in enumerate(dopant.levels):
        # f n1/(n1 + g carriers): n1 may underflow to zero at freeze-out;
        # without carriers every dopant is ionized
        n1 = f"N_band*exp(-E{i}/(k*T))"
        terms.append(f"ifelse(carriers > 0, f{i}*{n1}/({n1} + g*carriers), f{i})")
        parameters[f"f{i}"] = fraction
        parameters[f"E{i}"] = energy
    return Formula(" + ".join(terms), ["carriers", "N_band", "T"], **parameters)
