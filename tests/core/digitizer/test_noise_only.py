import numpy as np
import pytest
from scipy.integrate import trapezoid

from raser.core.digitizer.noise_only import (
    noise_codes,
    noise_only_channels,
    sampled_density,
)
from raser.core.digitizer.quantize import to_volts
from raser.core.digitizer.settings import DigitizerSettings


def test_white_noise_power_after_brickwall_filter():
    frequencies = np.linspace(0.0, 20e9, 1001)
    density = np.full_like(frequencies, 2e-6)
    sampled, result = sampled_density(frequencies, density, "brickwall", 2e9, 8e9)
    expected = density[0] ** 2 * 2e9
    assert trapezoid(result**2, sampled) == pytest.approx(expected, rel=2e-3)


def test_none_response_keeps_high_frequency_line_in_sampling_band():
    frequencies = np.array([1.9e9, 2.0e9, 2.1e9])
    density = np.array([0.0, 1.0, 0.0])
    sampled, result = sampled_density(frequencies, density, "none", None, 8e9)
    assert sampled[np.argmax(result)] == 2e9


def test_noise_codes_have_spectrum_power():
    settings = DigitizerSettings.from_component(
        "test",
        {
            "channels": 1,
            "bits": 14,
            "max_sampling_rate_GSps": 20,
            "response": "brickwall",
            "aperture_jitter_ps": 0,
            "bandwidth_GHz": 1,
            "sampling_rate_GSps": 4,
            "full_scale_V": 10,
            "offset_V": 0,
        },
    )
    frequencies = np.linspace(0.0, 8e9, 1001)
    density = np.full_like(frequencies, 1e-5)
    sampled = sampled_density(
        frequencies,
        density,
        settings.response,
        settings.bandwidth_hz,
        1 / settings.period_s,
    )
    values = []
    for seed in range(12):
        codes, _ = noise_codes(
            sampled, 3000, settings.period_s, settings, np.random.default_rng(seed)
        )
        values.extend(to_volts(codes, settings.bits, settings.lsb_V, settings.offset_V))
    assert np.var(values) == pytest.approx(
        trapezoid(sampled[1] ** 2, sampled[0]), rel=0.05
    )


def test_noise_only_channel_selection():
    assert noise_only_channels([0.2, 3.0, 0.1], [1], 1.0) == [0, 2]
    assert noise_only_channels([0.2, 0.3], [], 0.25) == [0]
    assert noise_only_channels([0.0, 0.0, 5.0], [0], 1.0) == [1]


def _integral_of_squared_interpolant(frequencies, density):
    """Exact integral of the square of the piecewise-linear interpolant of a spectrum."""
    widths = np.diff(frequencies)
    left, right = density[:-1], density[1:]
    return float(np.sum(widths * (left**2 + left * right + right**2) / 3))


# Deliberate change that breaks the folding tests: the alias sum of equation (6)
# reduced to the term m = 0 only (nothing above the sampling Nyquist is folded).
# the brickwall edge falls inside one cell of the sampled grid, which the
# trapezoid rule of the check resolves to about one percent
@pytest.mark.parametrize(
    "bandwidth, kept, tolerance", [(None, 1.0, 1e-3), (6.0e9, 0.5, 2e-2)]
)
def test_a_band_between_half_and_full_sampling_rate_folds_and_conserves_power(
    bandwidth, kept, tolerance
):
    sampling_rate = 8e9
    low, width, level = 5.5e9, 1.0e9, 1e-6
    frequencies = np.linspace(0.0, 7e9, 1401)
    inside = (frequencies >= low) & (frequencies <= low + width)
    density = np.where(
        inside, level * np.sin(np.pi * (frequencies - low) / width) ** 2, 0.0
    )
    response = "none" if bandwidth is None else "brickwall"
    sampled, result = sampled_density(
        frequencies, density, response, bandwidth, sampling_rate
    )
    # integral of S^2 |H|^2 df over the input band; the band is symmetric about
    # 6 GHz, so a brickwall at 6 GHz keeps exactly half of it
    expected = level**2 * width * 3 / 8 * kept
    assert _integral_of_squared_interpolant(frequencies, density) == pytest.approx(
        level**2 * width * 3 / 8, rel=1e-4
    )
    assert trapezoid(result**2, sampled) == pytest.approx(expected, rel=tolerance)
    # the power of the input at f appears at fs - f, inside [1.5, 2.5] GHz
    folded = (sampled >= sampling_rate - low - width) & (sampled <= sampling_rate - low)
    assert trapezoid(result[folded] ** 2, sampled[folded]) == pytest.approx(
        trapezoid(result**2, sampled), rel=1e-9
    )
    if bandwidth is None:
        assert sampled[np.argmax(result)] == pytest.approx(
            sampling_rate - (low + width / 2), abs=2e6
        )
