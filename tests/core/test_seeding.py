"""One job seed fixes the draws of every generator."""

from __future__ import annotations

import random

import ROOT

from raser.core import seeding


def _draws() -> tuple[float, float, float]:
    return (
        random.random(),
        ROOT.gRandom.Rndm(),
        seeding.stream("amplifier").Rndm(),
    )


def test_one_seed_fixes_python_root_and_stream_draws() -> None:
    seeding.seed_generators(11)
    first = _draws()
    seeding.seed_generators(12)
    other = _draws()
    seeding.seed_generators(11)

    assert _draws() == first
    assert all(a != b for a, b in zip(first, other))


def test_a_stream_is_untouched_by_draws_from_the_other_generators() -> None:
    seeding.seed_generators(11)
    expected = seeding.stream("amplifier").Rndm()

    seeding.seed_generators(11)
    for _ in range(100):
        ROOT.gRandom.Rndm()
        seeding.stream("interaction").Rndm()

    assert seeding.stream("amplifier").Rndm() == expected
