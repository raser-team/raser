import h5py
import numpy as np
import pytest

from raser.core.digitizer.digital_waveforms import (
    DigitizerFileSettings,
    EventDigitized,
    append_digitized,
    read_digitized,
)
from raser.core.digitizer.quantize import quantize, to_volts
from raser.core.digitizer.sampling import sample
from raser.core.digitizer.settings import DigitizerSettings


def settings(response="brickwall"):
    values = {
        "channels": 2,
        "bits": 10,
        "max_sampling_rate_GSps": 20,
        "response": response,
        "aperture_jitter_ps": 0,
        "sampling_rate_GSps": 10,
        "full_scale_V": 1.0,
        "offset_V": 0.0,
    }
    if response == "brickwall":
        values["bandwidth_GHz"] = 1
    return DigitizerSettings.from_component("test", values)


def test_settings_require_response_dependent_bandwidth_and_ignore_trigger():
    values = {
        "channels": 2,
        "bits": 10,
        "max_sampling_rate_GSps": 20,
        "response": "brickwall",
        "aperture_jitter_ps": 0,
        "bandwidth_GHz": 1,
        "sampling_rate_GSps": 10,
        "full_scale_V": 1,
        "offset_V": 0,
        "trigger": {"mode": "edge"},
    }
    with pytest.raises(ValueError, match="offset_V"):
        DigitizerSettings.from_component(
            "x", {key: value for key, value in values.items() if key != "offset_V"}
        )
    with pytest.raises(ValueError, match="unknown"):
        DigitizerSettings.from_component("x", {**values, "extra": 1})
    with pytest.raises(ValueError, match="response"):
        DigitizerSettings.from_component("x", {**values, "response": "gaussian"})
    with pytest.raises(ValueError, match="bandwidth_GHz"):
        DigitizerSettings.from_component(
            "x", {key: value for key, value in values.items() if key != "bandwidth_GHz"}
        )
    none_values = {
        key: value for key, value in values.items() if key != "bandwidth_GHz"
    }
    none_values["response"] = "none"
    with pytest.raises(ValueError, match="bandwidth_GHz"):
        DigitizerSettings.from_component("x", {**none_values, "bandwidth_GHz": 1})
    assert DigitizerSettings.from_component("x", none_values).bandwidth_hz is None


def test_sampling_has_one_phase_per_device_and_repeats_for_the_same_generators():
    config = settings("none")
    voltage = np.vstack([np.arange(100.0), np.arange(100.0) + 10])
    first_phase, first_samples = sample(
        voltage, 1e-11, [0, 1], config, lambda _: np.random.default_rng(3), None
    )
    second_phase, second_samples = sample(
        voltage, 1e-11, [0, 1], config, lambda _: np.random.default_rng(3), None
    )
    np.testing.assert_array_equal(first_phase, second_phase)
    np.testing.assert_array_equal(first_samples, second_samples)
    assert first_phase[0] == first_phase[1]


def test_digitizer_file_round_trip_stores_per_electrode_t0_and_noise_flags(tmp_path):
    config = settings("none")
    codes, clipped = quantize(np.array([[0.1, -0.1], [0.2, -0.2]]), config)
    path = tmp_path / "digitizer.h5"
    append_digitized(
        path,
        ["a", "b"],
        DigitizerFileSettings.from_settings(config, "test"),
        EventDigitized(
            7,
            codes,
            clipped,
            np.array([1.0e-9, 2.0e-9]),
            ["a", "b"],
            np.array([False, True]),
        ),
        ["rising", "falling"],
    )
    result = read_digitized(path)
    event = result.events[0]
    np.testing.assert_array_equal(event.t0, [1.0e-9, 2.0e-9])
    np.testing.assert_array_equal(event.noise_only, [False, True])
    with h5py.File(path, "r") as file:
        assert "phase" not in file
        assert "trigger_time" not in file
        assert "t0" in file


def test_quantized_codes_round_trip_to_midpoints():
    config = settings("none")
    volts = np.array([[-0.49, -0.01, 0.01, 0.49]])
    codes, clipped = quantize(volts, config)
    assert clipped.tolist() == [0]
    decoded = to_volts(codes, config.bits, config.lsb_V, config.offset_V)
    assert np.abs(volts - decoded).max() <= config.lsb_V / 2
