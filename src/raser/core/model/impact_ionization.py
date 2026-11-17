"""Impact ionization coefficients in 1/cm, of the field E in V/cm and the temperature T in K."""

import functools
import math

from .formula import Formula

# van Overstraeten and de Man, Solid-State Electronics 13 (1970) 583: a
# Chynoweth law with a low- and a high-field set of a [1/cm] and b [V/cm],
# the two met at E0. The temperature dependence through the optical phonon
# energy hbarOmega [eV] (k_T0 = k T0 [eV]) has no source found yet. Below 1.75e5 V/cm, the lower
# end of the measured fit, the coefficient is taken to be zero.
_VAN_OVERSTRAETEN = (
    "ifelse(E >= 1.75e5, "
    "ifelse(E > E0, gamma*a_high*exp(-(gamma*b_high)/E), gamma*a_low*exp(-(gamma*b_low)/E)), "
    "0)"
)
_VAN_OVERSTRAETEN_TEMPERATURE = {
    "gamma": "tanh(hbarOmega/(2*k_T0))/tanh(hbarOmega/(2*k_T0*T/T0))",
    "E0": 4.0e5,
    "hbarOmega": 0.063,
    "k_T0": 0.0257,
    "T0": 293.0,
}

VAN_OVERSTRAETEN = {
    "electron": Formula(
        _VAN_OVERSTRAETEN,
        ["E", "T"],
        **_VAN_OVERSTRAETEN_TEMPERATURE,
        a_low=7.03e5,
        a_high=7.03e5,
        b_low=1.231e6,
        b_high=1.231e6,
    ),
    "hole": Formula(
        _VAN_OVERSTRAETEN,
        ["E", "T"],
        **_VAN_OVERSTRAETEN_TEMPERATURE,
        a_low=1.582e6,
        a_high=6.71e5,
        b_low=2.036e6,
        b_high=1.693e6,
    ),
}


# Hatakeyama et al., Appl. Phys. Lett. 85 (2004) 1380: the coefficients of
# 4H-SiC along <0001> and <11-20>; Hatakeyama, Nishio, Ota and Shinohe,
# SISPAD 2005, "Physical modeling and scaling properties of 4H-SiC power
# devices", appendix: the law for a field `angle` off <0001> between them.
# The temperature dependence through the optical phonon energy hbarOmega
# [eV] (k_T0 = k T0 [eV]) has no source found yet. For a
# field at a fixed angle B and a are numbers; b depends on the field
# through its second term. Below 1e4 V/cm the coefficient is taken to be
# zero.
_HATAKEYAMA = "ifelse(E > 1e4, gamma*a*exp(-gamma*b/E), 0)"
_HATAKEYAMA_TEMPERATURE = {
    "gamma": "tanh(hbarOmega/(2*k_T0))/tanh(hbarOmega/(2*k_T0*T/T0))",
    "hbarOmega": 0.19,
    "k_T0": 0.0257,
    "T0": 300.0,
}
_HATAKEYAMA_COEFFICIENTS = {
    "electron": {"a_0001": 1.76e8, "a_1120": 2.10e7, "b_0001": 3.30e7, "b_1120": 1.70e7},
    "hole": {"a_0001": 3.41e8, "a_1120": 2.96e7, "b_0001": 2.50e7, "b_1120": 1.60e7},
}


@functools.cache
def hatakeyama(carrier, angle_deg):
    """The Hatakeyama coefficient of `carrier` for a field `angle_deg` off <0001>."""
    c = _HATAKEYAMA_COEFFICIENTS[carrier]
    along_0001 = math.cos(math.radians(angle_deg))
    along_1120 = math.sin(math.radians(angle_deg))
    # B, a and A of the paper, the field divided out of them
    big_b = 1 / math.pow(math.pow(along_1120 / c["b_1120"], 2) + math.pow(along_0001 / c["b_0001"], 2), 0.5)
    a = math.pow(c["a_1120"], math.pow(big_b * along_1120 / c["b_1120"], 2)) * math.pow(
        c["a_0001"], math.pow(big_b * along_0001 / c["b_0001"], 2)
    )
    big_a = math.log(c["a_0001"] / c["a_1120"])
    b = "B*pow(1 - pow(A, 2)*pow(B*along_1120*along_0001*E/(b_1120*b_0001), 2), 0.5)"
    return Formula(
        _HATAKEYAMA,
        ["E", "T"],
        **_HATAKEYAMA_TEMPERATURE,
        a=a,
        b=b,
        B=big_b,
        A=big_a,
        along_1120=along_1120,
        along_0001=along_0001,
        b_1120=c["b_1120"],
        b_0001=c["b_0001"],
    )
