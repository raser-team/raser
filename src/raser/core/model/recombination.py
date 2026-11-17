"""Shockley-Read-Hall recombination, in cm^-3 s^-1.

U = (n p - n_i^2) / (tau_p (n + n1) + tau_n (p + p1)), of the electron and
hole densities n, p [cm^-3], the intrinsic density n_i, n1 and p1 of the
trap level [cm^-3] and the lifetimes tau_n, tau_p [s] (Sze and Ng, Physics
of Semiconductor Devices, 3rd ed. (2007), section 1.5.4).
"""

from .formula import Formula

SRH = Formula(
    "(n*p - n_i^2)/(tau_p*(n + n1) + tau_n*(p + p1))",
    ["n", "p", "n_i", "n1", "p1", "tau_n", "tau_p"],
)

# The lifetimes [s] the field solver has taken; their sources are not
# recorded in the code they come from. The trap is taken at midgap:
# n1 = p1 = n_i.
SRH_LIFETIME = {
    "Si": {"tau_n": 7e-3, "tau_p": 7e-3},
    "SiC": {"tau_n": 2.5e-6, "tau_p": 0.5e-6},
    "Diamond": {"tau_n": 5.6e-7, "tau_p": 2.4e-7},
}
