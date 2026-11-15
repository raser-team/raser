import numpy as np
import pytest

from raser.core.metrics.collection import collection_efficiency

E = 1.602176634e-19


def test_efficiency_is_the_charge_of_all_electrodes_per_pair_without_sign() -> None:
    # event 0: 1000 pairs, the electrons shared by two strips, a tenth lost;
    # event 1: 4000 pairs, holes with gain 10 on the first strip
    charge = np.array([[-600 * E, -300 * E], [40000 * E, 0.0]])
    pairs = np.array([1000.0, 4000.0])

    efficiency = collection_efficiency(charge, pairs)

    assert efficiency == pytest.approx(np.array([0.9, 10.0]))


def test_event_without_pairs_is_an_error() -> None:
    with pytest.raises(ValueError, match=r"events \[1\] have no pairs"):
        collection_efficiency(np.zeros((2, 1)), np.array([5.0, 0.0]))
