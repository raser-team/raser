import math

import pytest

from raser.core.model.impact_ionization import VAN_OVERSTRAETEN


def test_van_overstraeten_holes_take_the_low_field_set_below_e0() -> None:
    # At 3e5 V/cm < E0 = 4e5 V/cm, holes take a = 1.582e6 /cm, b = 2.036e6 V/cm;
    # gamma = tanh(0.063/(2*0.0257)) / tanh(0.063/(2*0.0257*300/293)) at 300 K.
    gamma = math.tanh(0.063 / 0.0514) / math.tanh(0.063 / (0.0514 * 300 / 293))
    expected = gamma * 1.582e6 * math.exp(-gamma * 2.036e6 / 3e5)

    assert VAN_OVERSTRAETEN["hole"].value(E=3e5, T=300.0) == pytest.approx(expected, rel=1e-12)
    assert VAN_OVERSTRAETEN["hole"].value(E=1.7e5, T=300.0) == 0.0
    # the fit holds from 1.75e5 V/cm on, that end included
    assert VAN_OVERSTRAETEN["electron"].value(E=1.75e5, T=300.0) > 500.0


def test_van_overstraeten_ionization_grows_as_the_lattice_cools() -> None:
    # Fewer optical phonons at 254 K: a carrier gains more energy between collisions.
    warm = VAN_OVERSTRAETEN["electron"].value(E=3e5, T=300.0)
    cold = VAN_OVERSTRAETEN["electron"].value(E=3e5, T=254.0)

    assert cold > 1.2 * warm
