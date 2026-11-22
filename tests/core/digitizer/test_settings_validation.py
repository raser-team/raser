"""Rejected values of DigitizerSettings."""

import pytest

from raser.core.digitizer.settings import DigitizerSettings

VALUES = {
    "channels": 4,
    "bits": 12,
    "max_sampling_rate_GSps": 20,
    "response": "brickwall",
    "aperture_jitter_ps": 1.0,
    "bandwidth_GHz": 2.0,
    "sampling_rate_GSps": 10,
    "full_scale_V": 1.0,
    "offset_V": 0.0,
}
NUMERIC_KEYS = [
    "max_sampling_rate_GSps",
    "aperture_jitter_ps",
    "bandwidth_GHz",
    "sampling_rate_GSps",
    "full_scale_V",
    "offset_V",
]


def test_the_reference_values_are_accepted():
    settings = DigitizerSettings.from_component("x", VALUES)
    assert settings.period_s == pytest.approx(1e-10, rel=1e-12)


def test_a_sampling_rate_above_the_maximum_is_refused():
    with pytest.raises(ValueError, match="sampling_rate_GSps"):
        DigitizerSettings.from_component("x", {**VALUES, "sampling_rate_GSps": 25})
    # equal to the maximum is allowed
    DigitizerSettings.from_component("x", {**VALUES, "sampling_rate_GSps": 20})


@pytest.mark.parametrize("bits", [0, 16, -1, 2.5, "12", True])
def test_bits_must_be_an_integer_from_one_through_fifteen(bits):
    with pytest.raises(ValueError, match="bits"):
        DigitizerSettings.from_component("x", {**VALUES, "bits": bits})


@pytest.mark.parametrize("bits", [1, 15])
def test_the_extreme_bit_counts_are_accepted(bits):
    assert DigitizerSettings.from_component("x", {**VALUES, "bits": bits}).bits == bits


@pytest.mark.parametrize("channels", [2.5, 0, -2, "4", True])
def test_channels_must_be_a_positive_integer(channels):
    with pytest.raises(ValueError, match="channels"):
        DigitizerSettings.from_component("x", {**VALUES, "channels": channels})


# Deliberate change: number() accepting a bool (the exclusion of bool removed).
@pytest.mark.parametrize("key", NUMERIC_KEYS)
@pytest.mark.parametrize("wrong", ["5", True, False, None, float("nan")])
def test_numeric_keys_reject_strings_bools_and_non_finite_values(key, wrong):
    with pytest.raises(ValueError, match=key):
        DigitizerSettings.from_component("x", {**VALUES, key: wrong})
