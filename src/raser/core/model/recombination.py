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
# recorded in the code they come from and have not been found. The trap is
# taken at the intrinsic level: n1 = p1 = n_i (at midgap n1/p1 would be
# N_c/N_v).
SRH_LIFETIME = {
    "Si": {"tau_n": 7e-3, "tau_p": 7e-3},
    "SiC": {"tau_n": 2.5e-6, "tau_p": 0.5e-6},
    "Diamond": {"tau_n": 5.6e-7, "tau_p": 2.4e-7},
}

# The field enhancement of trap-assisted tunnelling, Gamma = 2 sqrt(3 pi)
# F / F_gamma exp((F / F_gamma)^2) (Hurkx, de Graaff, Kloosterman and
# Knuvers, IEEE Trans. Electron Devices 39 (1992) 331), held at its value at
# the field F_sat [V/cm] above it, by default TAT_SATURATION_FIELD (a device
# file may set another). F_gamma = 3.9e4 V/cm, F_sat = 1e5 V/cm and pi as
# 3.14159 are the values the field solver has taken for 4H-SiC; their
# source has not been found (Hurkx's F_gamma = sqrt(24 m (kT)^3)/(q hbar) is
# of the order of 4e5 V/cm here).
TAT_SATURATION_FIELD = 1e5
TAT_FIELD_ENHANCEMENT = Formula(
    "ifelse(E < F_sat, 2*(3*pi)^0.5*E/F_gamma*exp((E/F_gamma)^2), 2*(3*pi)^0.5*F_sat/F_gamma*exp((F_sat/F_gamma)^2))",
    ["E", "F_sat"],
    F_gamma=3.9e4,
    pi=3.14159,
)
