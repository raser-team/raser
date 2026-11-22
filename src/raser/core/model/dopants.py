"""The dopants of each material: donor or acceptor, ionization energy, degeneracy.

A dopant may sit on lattice sites of different energy (the hexagonal and
the cubic site of 4H-SiC, half of each); `levels` gives each ionization
energy [eV, from the band edge] at low doping with the fraction of the
dopants on it. Where a source gives it, an energy falls with the
concentration N [cm^-3] of the dopant as dE = E - fall_ev_cm N^(1/3)
(Pearson and Bardeen).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dopant:
    kind: str  # "donor" or "acceptor"
    levels: tuple[tuple[float, float], ...]  # (ionization energy [eV], fraction)
    degeneracy: float
    fall_ev_cm: float = 0.0


# Degeneracy factors 2 for donors, 4 for acceptors: Sze and Ng, Physics of
# Semiconductor Devices, 3rd ed. (2007), section 1.4.3, p. 22.
def _donor(*levels):
    return Dopant("donor", levels, 2.0)


def _acceptor(*levels):
    return Dopant("acceptor", levels, 4.0)


DOPANTS = {
    # Sze and Ng (2007), Fig. 10(a), p. 23 (measured ionization energies in Si).
    "Si": {
        "P": _donor((0.046, 1.0)),
        "As": _donor((0.054, 1.0)),
        "Sb": _donor((0.043, 1.0)),
        "B": _acceptor((0.044, 1.0)),
    },
    # 4H-SiC, hexagonal and cubic sites: TCAD Parameters for 4H-SiC: A
    # Review, arXiv:2410.06798, section 10.2 and table "Changing ionization
    # energy of donors with doping" (N: Schoener et al. 1994; P: the fit of
    # that review). Al: E = 216 meV - 3e-8 eV cm N^(1/3), Spera et al.,
    # Mater. Sci. Semicond. Process. 93 (2019) 274 (arXiv:2001.08021), eq. 13
    # and Fig. 7, a fit to their and earlier Hall measurements of implanted
    # layers, within the 225 +- 25 meV the review finds (section 10.2.1).
    # B: the shallow level, 311 meV, the fit of that review to all
    # measurements (285-332 meV, section 10.2.2); the deep D-center of boron
    # (495-630 meV) is a trap, not a dopant level.
    "SiC": {
        "N": _donor((0.0533, 0.5), (0.0996, 0.5)),
        "P": _donor((0.057, 0.5), (0.113, 0.5)),
        "Al": Dopant("acceptor", ((0.216, 1.0),), 4.0, fall_ev_cm=3e-8),
        "B": _acceptor((0.311, 1.0)),
    },
    # Diamond. B: 368.5 +- 1.5 meV from the Hall effect of five natural
    # diamonds, Collins and Williams, J. Phys. C 4 (1971) 1789, p. 1795; N, the
    # substitutional deep donor: Farrer, Solid State Commun. 7 (1969) 685;
    # P: 0.60 +- 0.02 eV, the optical ionization energy from its excited
    # states, as Hall measurements give it: Gheeraert et al., Solid State
    # Commun. 113 (2000) 577.
    "Diamond": {
        "B": _acceptor((0.3685, 1.0)),
        "N": _donor((1.7, 1.0)),
        "P": _donor((0.60, 1.0)),
    },
}
