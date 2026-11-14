from raser.core.field.conductive import conductive

MU_N, MU_P = 1400.0, 450.0  # cm^2/(V s), silicon


def _is_conductive(electrons, holes, net_doping):
    return bool(conductive([electrons], [holes], [net_doping], MU_N, MU_P)[0])


def test_a_heavily_doped_substrate_is_conductive() -> None:
    # p-type 1e18 cm^-3 with all its holes: 0.014 Ohm cm
    assert _is_conductive(electrons=1e2, holes=1e18, net_doping=-1e18)


def test_a_depleted_bulk_is_dielectric() -> None:
    assert not _is_conductive(electrons=28.0, holes=77.0, net_doping=-5e12)


def test_a_high_resistivity_bulk_that_is_not_depleted_is_conductive() -> None:
    # p-type 5e12 cm^-3 with all its holes: 2.8 kOhm cm, far above 10 Ohm cm
    assert _is_conductive(electrons=1.7e7, holes=5e12, net_doping=-5e12)


def test_without_net_doping_only_the_resistivity_decides() -> None:
    assert not _is_conductive(
        electrons=1e10, holes=1e10, net_doping=0.0
    )  # intrinsic silicon
    assert not _is_conductive(
        electrons=1e-20, holes=1e-20, net_doping=0.0
    )  # an insulator
    assert _is_conductive(electrons=1e18, holes=1e2, net_doping=0.0)
