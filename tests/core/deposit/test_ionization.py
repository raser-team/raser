import numpy as np
import pytest

from raser.core import seeding
from raser.core.deposit import ionization
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.ionization import ionized_pairs


def _deposits(energies: list[float]) -> EventDeposits:
    count = len(energies)
    return EventDeposits(
        event=0,
        detector=["Device"] * count,
        x=[1.0 + k for k in range(count)],
        y=[3.0 + k for k in range(count)],
        z=[5.0 + k for k in range(count)],
        t=[7.0e-12 + k * 1.0e-12 for k in range(count)],
        e=energies,
    )


@pytest.mark.parametrize(
    ("material", "energy_mev", "mean", "variance"),
    [
        ("Si", 0.036, 10000.0, 1150.0),
        ("SiC", 0.084, 10000.0, 1280.0),
        ("Diamond", 0.131, 10000.0, 3820.0),
    ],
)
def test_ionized_pairs_have_the_mean_and_the_fano_variance(
    material: str, energy_mev: float, mean: float, variance: float
) -> None:
    seeding.seed_generators(3)

    pairs, _ = ionized_pairs(_deposits([energy_mev] * 20000), material)

    # 20000 draws: the mean is known to 0.3 pairs, the variance to 1 %.
    assert np.mean(pairs) == pytest.approx(mean, abs=1.5)
    assert np.var(pairs) == pytest.approx(variance, rel=0.05)


def test_ionized_pairs_keep_position_and_time_of_each_deposit() -> None:
    _, positions = ionized_pairs(_deposits([0.036, 0.084]), "Si")

    assert positions == [[1.0, 3.0, 5.0, 7.0e-12], [2.0, 4.0, 6.0, 8.0e-12]]


def test_without_fano_the_pairs_are_energy_over_pair_energy() -> None:
    seeding.seed_generators(3)

    pairs, _ = ionized_pairs(_deposits([0.131, 5.54]), "Diamond", fano=False)

    assert pairs == pytest.approx([10000.0, 5.54e6 / 13.1])


def test_without_fano_a_material_needs_no_fano_factor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ionization.PAIR_ENERGY_EV, "Unmeasured", 10.0)

    pairs, _ = ionized_pairs(_deposits([0.01]), "Unmeasured", fano=False)

    assert pairs == pytest.approx([1000.0])
    with pytest.raises(ValueError, match="no Fano factor"):
        ionized_pairs(_deposits([0.01]), "Unmeasured")


def test_a_deposit_takes_the_material_of_the_detector_it_lies_in() -> None:
    event = _deposits([0.036, 0.084, 0.036, 0.084])
    event.detector = ["ref", "dut", "dut", "ref"]

    pairs, _ = ionized_pairs(event, {"ref": "Si", "dut": "SiC"}, fano=False)

    # Si: 3.6 eV a pair, SiC: 8.4 eV a pair, whatever the order of the deposits
    assert pairs == pytest.approx([10000.0, 10000.0, 0.036e6 / 8.4, 0.084e6 / 3.6])
    # with Fano, each deposit draws around the mean of its own material
    event = _deposits([0.036] * 4000 + [0.084] * 4000)
    event.detector = ["ref"] * 4000 + ["dut"] * 4000
    seeding.seed_generators(3)
    drawn, _ = ionized_pairs(event, {"ref": "Si", "dut": "SiC"})
    assert np.var(drawn[:4000]) == pytest.approx(1150.0, rel=0.1)
    assert np.var(drawn[4000:]) == pytest.approx(1280.0, rel=0.1)
