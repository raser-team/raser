"""Amplifier noise is one sequence over events, fixed by the job seed."""

from __future__ import annotations

import pytest
import ROOT

from raser.core import seeding
from raser.core.frontend.legacy_readout import Amplifier


def _pulse() -> ROOT.TH1F:
    pulse = ROOT.TH1F("", "", 200, 0, 2e-9)
    for index in range(21, 61):
        pulse.SetBinContent(index, -0.05e-6 * (60 - index))
    pulse.SetDirectory(ROOT.nullptr)
    return pulse


def _waveforms(amplifier: str, events: int) -> list[list[float]]:
    waveforms = []
    for _ in range(events):
        output = Amplifier([_pulse()], amplifier, CDet=30).amplified_currents[0]
        waveforms.append(
            [output.GetBinContent(index) for index in range(1, output.GetNbinsX() + 1)]
        )
    return waveforms


@pytest.mark.parametrize("amplifier", ["Broad_Band_UCSC", "Charge_Sensitive_UCSC"])
def test_amplifier_noise_is_a_sequence_over_events_fixed_by_the_seed(
    amplifier: str,
) -> None:
    seeding.seed_generators(11)
    first = _waveforms(amplifier, 3)
    seeding.seed_generators(12)
    other = _waveforms(amplifier, 3)
    seeding.seed_generators(11)

    assert _waveforms(amplifier, 3) == first
    assert first[0] != first[1] != first[2] != first[0]
    assert other[0] != first[0]
