"""The fast mode of telescope bins its immediate collections as the diffusion model does."""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.geant4


def test_a_deposit_0_6_step_after_the_first_lies_in_the_first_bin() -> None:
    from raser.bench.telescope.telescope_signal import collect_under  # loads Geant4

    pixels = SimpleNamespace(p_x=25.0, p_y=25.0, x_ele_num=2, y_ele_num=2, l_z=10.0)
    t0, current, _ = collect_under(pixels, [1.0, 1.0], [[5.0, 5.0, 5.0, 0.0], [5.0, 5.0, 5.0, 30e-12]], 50e-12)

    assert t0 == 0.0
    assert current.shape == (4, 1)
    assert current[0, 0] * 50e-12 == pytest.approx(-2.0 * 1.602176634e-19)
