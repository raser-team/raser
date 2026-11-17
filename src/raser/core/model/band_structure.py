"""Band gap, effective densities of states and intrinsic density of each material.

Formulas of the temperature T [K]: N_c, N_v and n_i in cm^-3, E_g in J
(from eV times 1.6e-19, the value RASER has used for the charge here).
These are the values the field solver has taken; the sources of the Si and
diamond coefficients are not recorded in the code they come from and have
not been found. The band gaps do not depend on the temperature.
"""

from .formula import Formula

_K_J_PER_K = 1.3806503e-23
_INTRINSIC = "pow(N_c*N_v, 0.5)*exp(-E_g/(2*k*T))"


def _material(n_c, n_v, e_g):
    quantities = {"N_c": n_c, "N_v": n_v, "E_g": e_g}
    formulas = {name: Formula(text, ["T"]) for name, text in quantities.items()}
    formulas["n_i"] = Formula(_INTRINSIC, ["T"], **quantities, k=_K_J_PER_K)
    return formulas


BAND_STRUCTURE = {
    "Si": _material("2.82e19*pow(T/300, 1.5)", "1.83e19*pow(T/300, 1.5)", "1.12*1.6e-19"),
    # 4H-SiC: N = 2 M_c (2 pi m k T / h^2)^(3/2) with M_c = 3 valleys of
    # 0.37 m0 and holes of 1.0 m0 (TCAD Parameters for 4H-SiC: A Review,
    # arXiv:2410.06798, section 6) gives 3.25e15 T^1.5 and 4.8e15 T^1.5,
    # 1.69e19 and 2.49e19 at 300 K.
    "SiC": _material("3.25e15*pow(T, 1.5)", "4.8e15*pow(T, 1.5)", "3.26*1.6*1e-19"),
    "Diamond": _material("1.8e19*pow(T/300, 1.5)", "1.5e19*pow(T/300, 1.5)", "5.47*1.6e-19"),
}
