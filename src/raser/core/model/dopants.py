"""The dopants of each material: donor or acceptor, ionization energy, degeneracy.

A dopant may sit on lattice sites of different energy (the hexagonal and
the cubic site of 4H-SiC, half of each); `levels` gives each ionization
energy [eV, from the band edge] with the fraction of the dopants on it.
The energies are those at low doping.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dopant:
    kind: str  # "donor" or "acceptor"
    levels: tuple[tuple[float, float], ...]  # (ionization energy [eV], fraction)
    degeneracy: float


# Degeneracy factors 2 for donors, 4 for acceptors: Sze and Ng, Physics of
# Semiconductor Devices, 3rd ed. (2007), chapter 1.
def _donor(*levels):
    return Dopant("donor", levels, 2.0)


def _acceptor(*levels):
    return Dopant("acceptor", levels, 4.0)


DOPANTS = {
    # Sze and Ng (2007), chapter 1 (measured ionization energies in Si).
    "Si": {
        "P": _donor((0.045, 1.0)),
        "As": _donor((0.054, 1.0)),
        "Sb": _donor((0.039, 1.0)),
        "B": _acceptor((0.045, 1.0)),
    },
    # 4H-SiC, hexagonal and cubic sites: TCAD Parameters for 4H-SiC: A
    # Review, arXiv:2410.06798, section 10.2 and table "Changing ionization
    # energy of donors with doping" (N: Schoener et al. 1994; P: the fit of
    # that review). Al: 225 meV at low doping, the value the measurements
    # agree on (section 10.2.1).
    "SiC": {
        "N": _donor((0.0533, 0.5), (0.0996, 0.5)),
        "P": _donor((0.057, 0.5), (0.113, 0.5)),
        "Al": _acceptor((0.225, 1.0)),
    },
    # Diamond. B: Collins and Williams, J. Phys. C 4 (1971) 1789; N, the
    # substitutional deep donor: Farrer, Solid State Commun. 7 (1969) 685.
    "Diamond": {
        "B": _acceptor((0.37, 1.0)),
        "N": _donor((1.7, 1.0)),
    },
}
