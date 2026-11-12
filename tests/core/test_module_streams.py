"""Draws of one module stay the same when other generators are consumed."""

from __future__ import annotations

import random
from collections.abc import Callable
from types import SimpleNamespace

import pytest
import ROOT

from raser.core import seeding
from raser.core.interaction.energy_loss import sample_fano_pairs
from raser.core.interaction.energy_loss import sample_landau_energy_loss
from raser.core.interaction.toy_mip import ToyMIPInteraction


def _energy_loss() -> object:
    return (
        sample_landau_energy_loss(1.0, 0.1),
        sample_fano_pairs(1000.0, 0.1),
    )


def _toy_mip_tracks() -> object:
    sensor = SimpleNamespace(l_x=100.0, l_y=100.0, l_z=50.0, material="Si")
    interaction = ToyMIPInteraction(
        sensor,
        {
            "total_events": 3,
            "packets": 5,
            "pairs_per_um": 75.0,
            "position_range_um": {"x": [0.0, 100.0], "y": [0.0, 100.0]},
            "direction_sigma_mrad": 5.0,
        },
    )
    return interaction.p_steps


@pytest.mark.parametrize("draw", [_energy_loss, _toy_mip_tracks])
def test_module_draws_follow_the_seed_and_ignore_other_generators(
    draw: Callable[[], object],
) -> None:
    seeding.seed_generators(11)
    expected = draw()

    seeding.seed_generators(12)
    other = draw()

    seeding.seed_generators(11)
    for _ in range(50):
        random.random()
        ROOT.gRandom.Rndm()
        seeding.stream("amplifier").Rndm()

    assert draw() == expected
    assert other != expected
