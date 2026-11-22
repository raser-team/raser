"""Random streams of write_digitized: each draw is keyed by the electrode, not its row."""

import numpy as np
import pytest

from raser.core.digitizer.digital_waveforms import read_digitized
from raser.core.digitizer.job import write_digitized
from raser.core.digitizer.settings import DigitizerSettings
from raser.core.readout.waveforms import EventWaveforms, append_waveforms

ELECTRODES = ["e0", "e1", "e2", "e3"]
DT = 50e-12
BINS = 80
NOISE_FREQUENCIES = np.linspace(0.0, 8e9, 50)
NOISE_DENSITY = np.full_like(NOISE_FREQUENCIES, 1e-8)


def _settings():
    # two channels per device: e0 and e1 on device 0, e2 and e3 on device 1
    return DigitizerSettings.from_component(
        "test",
        {
            "channels": 2,
            "bits": 8,
            "max_sampling_rate_GSps": 16,
            "response": "none",
            "aperture_jitter_ps": 20,
            "sampling_rate_GSps": 16,
            "full_scale_V": 0.04,
            "offset_V": 0.0,
        },
    )


def _digitize(tmp_path, stored, noise_places):
    """Digitize one event that stores ``stored`` and samples ``noise_places`` as noise only."""
    rng = np.random.default_rng(5)
    waveform = {name: rng.normal(0.0, 0.003, BINS) for name in ELECTRODES}
    tag = "_".join(stored) + "-" + "".join(map(str, noise_places))
    readout = tmp_path / f"readout_{tag}.h5"
    append_waveforms(
        readout,
        ELECTRODES,
        DT,
        10 * DT,
        EventWaveforms(3, 0.0, np.array([waveform[n] for n in stored]), stored),
        pulse_edge=["falling"] * len(ELECTRODES),
    )
    output = tmp_path / f"digitizer_{tag}.h5"
    write_digitized(
        readout,
        output,
        _settings(),
        "test",
        11,
        0,
        tmp_path / "plots",
        lambda event: [(p, NOISE_FREQUENCIES, NOISE_DENSITY) for p in noise_places],
    )
    event = read_digitized(output).events[0]
    return {
        name: (code, t0)
        for name, code, t0 in zip(event.electrodes, event.code, event.t0, strict=True)
    }


# Deliberate changes that break these tests: in sample(), the jitter generator
# keyed by the row number instead of the electrode; in write_digitized, the
# noise generator keyed by the row number; device_of always returning 0.
def test_jittered_codes_of_an_electrode_do_not_depend_on_earlier_electrodes(tmp_path):
    with_earlier = _digitize(tmp_path, ["e1", "e2", "e3"], [])
    alone = _digitize(tmp_path, ["e3"], [])
    np.testing.assert_array_equal(with_earlier["e3"][0], alone["e3"][0])
    assert with_earlier["e3"][1] == alone["e3"][1]


def test_noise_only_codes_of_an_electrode_do_not_depend_on_earlier_electrodes(
    tmp_path,
):
    with_earlier = _digitize(tmp_path, ["e0", "e1", "e2"], [3])
    alone = _digitize(tmp_path, ["e2"], [3])
    np.testing.assert_array_equal(with_earlier["e3"][0], alone["e3"][0])
    assert with_earlier["e3"][1] == alone["e3"][1]
    # the noise really is drawn: it differs from the codes of another electrode
    assert not np.array_equal(with_earlier["e3"][0], with_earlier["e2"][0])


@pytest.mark.parametrize("noise_places", [[], [3]])
def test_clock_phases_differ_between_devices_and_agree_within_one(
    tmp_path, noise_places
):
    stored = ["e0", "e1", "e2", "e3"]
    stored = [name for name in stored if ELECTRODES.index(name) not in noise_places]
    result = _digitize(tmp_path, stored, noise_places)
    assert result["e0"][1] == result["e1"][1]
    assert result["e2"][1] == result["e3"][1]
    assert result["e0"][1] != result["e2"][1]


def test_the_clock_phase_is_drawn_anew_for_every_event_and_seed(tmp_path):
    # the same waveform in three events: the clock is free running, so the
    # phase of the device differs from event to event, and with the seed
    readout = tmp_path / "readout.h5"
    waveform = np.zeros((1, BINS))
    for number in (0, 1, 2):
        append_waveforms(
            readout,
            ELECTRODES,
            DT,
            10 * DT,
            EventWaveforms(number, 0.0, waveform, ["e0"]),
            pulse_edge=["falling"] * len(ELECTRODES),
        )
    phases = {}
    for seed in (11, 12):
        output = tmp_path / f"digitizer_{seed}.h5"
        write_digitized(
            readout,
            output,
            _settings(),
            "test",
            seed,
            0,
            tmp_path / "plots",
            lambda event: [],
        )
        phases[seed] = [float(event.t0[0]) for event in read_digitized(output).events]
    period = _settings().period_s
    assert len(set(phases[11])) == 3
    assert all(0.0 <= phase < period for phase in phases[11])
    assert phases[11] != phases[12]
