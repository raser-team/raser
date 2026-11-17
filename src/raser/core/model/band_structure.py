"""Band gap, effective densities of states and intrinsic density of each material.

Formulas of the temperature T [K]: N_c, N_v and n_i in cm^-3, E_g in J
(from eV times 1.6e-19, the value RASER has used for the charge here).
These are the values the field solver has taken; their sources are not
recorded in the code they come from.
"""

from .formula import Formula

_K_J_PER_K = 1.3806503e-23
_INTRINSIC = "pow(N_c*N_v, 0.5)*exp(-E_g/(2*k*T))"


def _material(n_c, n_v, e_g, n_i=None):
    quantities = {"N_c": n_c, "N_v": n_v, "E_g": e_g}
    formulas = {name: Formula(text, ["T"]) for name, text in quantities.items()}
    formulas["n_i"] = Formula(n_i or _INTRINSIC, ["T"], **quantities, k=_K_J_PER_K)
    return formulas


BAND_STRUCTURE = {
    "Si": _material("2.82e19*pow(T/300, 1.5)", "1.83e19*pow(T/300, 1.5)", "1.12*1.6e-19"),
    # 4H-SiC: N_c, N_v and n_i are taken as they are, without the
    # temperature.
    "SiC": _material("3.25e15", "4.8e15", "3.26*1.6*1e-19", n_i="3.89e-9"),
    "Diamond": _material("1.8e19*pow(T/300, 1.5)", "1.5e19*pow(T/300, 1.5)", "5.47*1.6e-19"),
}
