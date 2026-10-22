from __future__ import annotations

import numpy as np
import pytest

from raser.core.frontend import ELEMENTARY_CHARGE_C
from raser.core.frontend import equivalent_noise_charge
from raser.core.frontend import load_noise_spectrum
from raser.core.frontend import output_noise_rms_from_enc
from raser.core.frontend import spieler_noise_spectrum
from raser.core.frontend import synthesize_noise_from_spectrum
from raser.core.frontend import white_noise_spectrum_for_rms


def test_load_noise_spectrum_averages_duplicate_frequencies(tmp_path) -> None:
    spectrum = tmp_path / "noise.raw"
    spectrum.write_text("* header\n10 2\n1 1\n10 4\n", encoding="utf-8")

    frequencies, density = load_noise_spectrum(spectrum)

    assert frequencies == pytest.approx([1.0, 10.0])
    assert density == pytest.approx([1.0, 3.0])


def test_load_noise_spectrum_reports_malformed_rows(tmp_path) -> None:
    spectrum = tmp_path / "noise.raw"
    spectrum.write_text("1 2\nbad row\n", encoding="utf-8")

    with pytest.raises(ValueError, match="row 2"):
        load_noise_spectrum(spectrum)


def test_spectrum_noise_is_seeded_and_normalized() -> None:
    frequencies = np.array([0.0, 5.0e8], dtype=np.float64)
    density = np.array([1.0e-6, 1.0e-6], dtype=np.float64)

    first = synthesize_noise_from_spectrum(
        frequencies,
        density,
        n_samples=1024,
        time_step_s=1.0e-9,
        seed=7,
        target_rms=0.25,
    )
    second = synthesize_noise_from_spectrum(
        frequencies,
        density,
        n_samples=1024,
        time_step_s=1.0e-9,
        seed=7,
        target_rms=0.25,
    )

    assert first == pytest.approx(second)
    assert float(np.mean(first)) == pytest.approx(0.0, abs=1.0e-12)
    assert float(np.std(first)) == pytest.approx(0.25)


def test_enc_uses_device_capacitance_and_output_charge_gain() -> None:
    enc = equivalent_noise_charge(
        10.0,
        constant_electrons=100.0,
        slope_electrons_per_pF=20.0,
    )
    rms, converted_enc = output_noise_rms_from_enc(
        10.0,
        constant_electrons=100.0,
        slope_electrons_per_pF=20.0,
        output_gain_mV_per_fC=10.0,
    )

    expected = (100.0**2 + 200.0**2) ** 0.5
    assert enc == pytest.approx(expected)
    assert converted_enc == pytest.approx(expected)
    assert rms == pytest.approx(expected * ELEMENTARY_CHARGE_C * 1.0e15 * 10.0)


def test_white_spectrum_integrates_to_requested_rms() -> None:
    frequencies, density = white_noise_spectrum_for_rms(2.0, 10.0, 110.0)

    assert frequencies == pytest.approx([10.0, 110.0])
    assert density == pytest.approx([0.2, 0.2])


def test_spieler_spectrum_uses_capacitance_and_afe_pole() -> None:
    arguments = {
        "voltage_noise_V_per_sqrtHz": 1.0e-9,
        "current_noise_A_per_sqrtHz": 1.0e-15,
        "flicker_voltage_noise_V2_Hz": 0.0,
        "transimpedance_ohm": 1000.0,
        "min_frequency_hz": 1.0e6,
        "max_frequency_hz": 1.0e7,
        "points_per_decade": 1,
        "pole_frequency_hz": 1.0e6,
    }
    frequencies, low_cap_density = spieler_noise_spectrum(1.0, **arguments)
    _, high_cap_density = spieler_noise_spectrum(10.0, **arguments)

    assert frequencies == pytest.approx([1.0e6, 1.0e7])
    assert high_cap_density[-1] > low_cap_density[-1]
    assert low_cap_density[-1] < low_cap_density[0] * 10.0
