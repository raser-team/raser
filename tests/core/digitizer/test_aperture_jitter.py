import numpy as np
import pytest

from raser.core.digitizer.sampling import sample
from raser.core.digitizer.settings import DigitizerSettings

SLOPE_V_PER_S = 1e6
DT = 50e-12
BINS = 4000


def _settings(jitter_ps):
    return DigitizerSettings.from_component(
        "test",
        {
            "channels": 2,
            "bits": 10,
            "max_sampling_rate_GSps": 20,
            "response": "none",
            "aperture_jitter_ps": jitter_ps,
            "sampling_rate_GSps": 10,
            "full_scale_V": 1.0,
            "offset_V": 0.0,
        },
    )


def _ramp_residuals(jitter_ps, places, rng_of_electrode):
    config = _settings(jitter_ps)
    centres = (np.arange(BINS) + 0.5) * DT
    voltage = np.tile(SLOPE_V_PER_S * centres, (len(places), 1))
    phases, samples = sample(
        voltage,
        DT,
        places,
        config,
        lambda device: np.random.default_rng([7, 0, 0, device]),
        rng_of_electrode,
    )
    ideal = SLOPE_V_PER_S * (
        phases[:, None] + np.arange(samples.shape[1]) * config.period_s
    )
    return samples - ideal


def test_aperture_jitter_adds_slope_times_jitter_of_rms_to_a_ramp():
    jitter_ps = 20.0
    residual = _ramp_residuals(
        jitter_ps, [0], lambda place: np.random.default_rng([7, 0, 1, place])
    )
    expected = SLOPE_V_PER_S * jitter_ps * 1e-12
    assert np.sqrt(np.mean(residual**2)) == pytest.approx(expected, rel=0.05)
    assert abs(residual.mean()) < 0.1 * expected


def test_zero_aperture_jitter_leaves_a_ramp_exact_and_draws_nothing():
    def forbidden(place):
        raise AssertionError("no jitter must be drawn at zero aperture jitter")

    residual = _ramp_residuals(0.0, [0, 1], forbidden)
    assert np.abs(residual).max() < 1e-12 * SLOPE_V_PER_S * BINS * DT


def test_every_electrode_draws_its_own_jitter():
    residual = _ramp_residuals(
        20.0, [0, 1], lambda place: np.random.default_rng([7, 0, 1, place])
    )
    assert abs(np.corrcoef(residual[0], residual[1])[0, 1]) < 0.1


def test_aperture_jitter_is_required_and_not_negative():
    values = {
        "channels": 2,
        "bits": 10,
        "max_sampling_rate_GSps": 20,
        "response": "none",
        "sampling_rate_GSps": 10,
        "full_scale_V": 1.0,
        "offset_V": 0.0,
    }
    with pytest.raises(ValueError, match="aperture_jitter_ps"):
        DigitizerSettings.from_component("x", values)
    with pytest.raises(ValueError, match="aperture_jitter_ps"):
        DigitizerSettings.from_component("x", {**values, "aperture_jitter_ps": -0.1})
    config = DigitizerSettings.from_component(
        "x", {**values, "aperture_jitter_ps": 0.15}
    )
    assert config.aperture_jitter_s == pytest.approx(0.15e-12, rel=1e-12)
