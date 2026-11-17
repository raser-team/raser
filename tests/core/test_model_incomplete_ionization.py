import math

import pytest

from raser.core.model.incomplete_ionization import ionized_fraction

K_EV = 8.617333262e-5


def test_a_donor_is_half_ionized_where_g_n_equals_n1() -> None:
    # Si:P, 0.046 eV, g = 2, at 300 K with N_c = 2.82e19 /cm3.
    n1 = 2.82e19 * math.exp(-0.046 / (K_EV * 300.0))
    fraction = ionized_fraction("Si", "P")

    assert fraction.value(carriers=n1 / 2, N_band=2.82e19, T=300.0) == pytest.approx(0.5)
    assert fraction.value(carriers=1e10, N_band=2.82e19, T=300.0) == pytest.approx(1.0, abs=1e-8)


def test_an_acceptor_is_half_ionized_where_g_p_equals_p1() -> None:
    # Si:B, 0.044 eV, g = 4, at 300 K with N_v = 1.83e19 /cm3.
    p1 = 1.83e19 * math.exp(-0.044 / (K_EV * 300.0))

    assert ionized_fraction("Si", "B").value(carriers=p1 / 4, N_band=1.83e19, T=300.0) == pytest.approx(0.5)


def test_the_two_sites_of_nitrogen_in_4h_sic_ionize_apart() -> None:
    # Half on the hexagonal site (53.3 meV), half on the cubic one (99.6 meV),
    # at 254 K: where the hexagonal site is half ionized the cubic one is far less.
    n1_hex = 1.7e19 * math.exp(-0.0533 / (K_EV * 254.0))
    n1_cubic = 1.7e19 * math.exp(-0.0996 / (K_EV * 254.0))
    electrons = n1_hex / 2
    expected = 0.5 * 0.5 + 0.5 / (1 + 2 * electrons / n1_cubic)

    fraction = ionized_fraction("SiC", "N").value(carriers=electrons, N_band=1.7e19, T=254.0)

    assert fraction == pytest.approx(expected)
    assert fraction < 0.4


def test_a_frozen_out_dopant_is_not_ionized_unless_there_are_no_carriers() -> None:
    # Diamond N, 1.7 eV deep, at 20 K: n1 underflows to zero.
    fraction = ionized_fraction("Diamond", "N")

    assert fraction.value(carriers=1.0, N_band=1e18, T=20.0) == 0.0
    assert fraction.value(carriers=0.0, N_band=1e18, T=20.0) == 1.0
