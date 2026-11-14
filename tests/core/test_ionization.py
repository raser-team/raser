import numpy as np
import pytest

from raser.core import seeding
from raser.core.interaction.deposits import EventDeposits
from raser.core.interaction.ionization import ionized_pairs


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
    [("Si", 0.036, 10000.0, 1150.0), ("SiC", 0.084, 10000.0, 1280.0)],
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
