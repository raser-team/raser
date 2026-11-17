"""Impact ionization coefficients in 1/cm, of the field E in V/cm and the temperature T in K."""

from .formula import Formula

# van Overstraeten and de Man, Solid-State Electronics 13 (1970) 583: a
# Chynoweth law with a low- and a high-field set of a [1/cm] and b [V/cm],
# the two met at E0, and the temperature dependence of the optical phonon
# energy hbarOmega [eV] (k_T0 = k T0 [eV]). Below 1.75e5 V/cm the coefficient
# is taken to be zero.
_VAN_OVERSTRAETEN = (
    "ifelse(E > 1.75e5, "
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
        # The paper gives b = 1.231e6 V/cm for electrons; 1.232e6 is the
        # value RASER has used, kept: 0.34% lower alpha at 3e5 V/cm.
        b_low=1.232e6,
        b_high=1.232e6,
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
