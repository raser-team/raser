import math

import pytest

from raser.core.current.carrier import VectorizedCarrierSystem


pytestmark = pytest.mark.root


class MissingThenValidWeightingField:
    def get_w_p_cached(self, x, y, z, electrode_idx):
        if x == 0.0:
            return None
        return 0.5


def test_weighting_potential_batch_marks_missing_point_as_nan():
    system = VectorizedCarrierSystem.__new__(VectorizedCarrierSystem)

    potentials = system._get_weighting_potentials_batch(
        MissingThenValidWeightingField(),
        [0.0, 1.0],
        [0.0, 0.0],
        [0.0, 1.0],
        0,
    )

    assert math.isnan(potentials[0])
    assert potentials[1] == 0.5
