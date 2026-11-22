"""Run bandwidth filtering, sampling, and quantisation for a readout file."""

import numpy as np

from raser.core.readout.waveforms import read_waveforms

from .bandwidth import filter_waveform
from .digital_waveforms import (
    DigitizerFileSettings,
    EventDigitized,
    append_digitized,
    create_digitized,
)
from .draw import draw_codes, draw_samples
from .noise_only import noise_codes, sampled_density
from .quantize import quantize, to_volts
from .sampling import device_of, sample, sample_count
from .settings import DigitizerSettings


def write_digitized(
    readout_path,
    digitizer_path,
    settings: DigitizerSettings,
    device_name,
    seed,
    plots,
    plot_path,
    noise_only,
):
    """Write all readout events to a new sparse digitizer file.

    ``seed`` is an integer. ``noise_only(event)`` returns, for one readout
    event, a list of ``(place, frequencies_hz, density)`` of the noise-only
    electrodes; it returns an empty list when there are none. ``plots`` is the
    number of ``samples`` figures; ``plots > 0`` also draws ``codes``.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    readout = read_waveforms(readout_path)
    attributes = DigitizerFileSettings.from_settings(settings, device_name)
    create_digitized(digitizer_path, readout.electrodes, attributes, readout.pulse_edge)
    made_plots = 0
    all_codes = []
    sampled_cache = {}
    for event in readout.events:
        places = [readout.electrodes.index(name) for name in event.electrodes]

        def rng_device(device, e=event.event):
            return np.random.default_rng([seed, e, 0, device])

        def rng_electrode(place, e=event.event):
            return np.random.default_rng([seed, e, 1, place])

        count = sample_count(event.voltage.shape[1], readout.dt, settings.period_s)
        if count < 2:
            raise ValueError(
                f"event {event.event} has {count} sampling points; its waveform of "
                f"{event.voltage.shape[1] * readout.dt} s with sampling period "
                f"{settings.period_s} s needs at least 2"
            )
        phase, sampled = sample(
            event.voltage, readout.dt, places, settings, rng_device, rng_electrode
        )
        codes, clipped = quantize(sampled, settings)
        stored_places = list(places)
        stored_codes = [codes[row] for row in range(codes.shape[0])]
        stored_clipped = [int(value) for value in clipped]
        stored_t0 = [event.t0 + float(value) for value in phase]
        stored_noise = [False] * len(stored_places)
        requested = list(noise_only(event))
        seen_noise = set()
        phase_by_device = {
            device_of(place, settings.channels): phase[row]
            for row, place in enumerate(places)
        }
        for place, frequencies_hz, density in requested:
            place = int(place)
            if place < 0 or place >= len(readout.electrodes):
                raise ValueError(
                    f"noise-only electrode place {place} is outside the electrodes"
                )
            if place in seen_noise:
                raise ValueError(
                    f"noise-only electrode place {place} occurs more than once"
                )
            seen_noise.add(place)
            if place in stored_places:
                raise ValueError(
                    f"electrode place {place} of event {event.event} is both in the readout file and noise-only"
                )
            device = device_of(place, settings.channels)
            if device not in phase_by_device:
                phase_by_device[device] = float(
                    rng_device(device).uniform(0.0, settings.period_s)
                )
            frequencies = np.asarray(frequencies_hz, dtype=np.float64)
            spectrum_density = np.asarray(density, dtype=np.float64)
            key = (
                frequencies.shape,
                frequencies.tobytes(),
                spectrum_density.shape,
                spectrum_density.tobytes(),
            )
            if key not in sampled_cache:
                sampled_cache[key] = sampled_density(
                    frequencies,
                    spectrum_density,
                    settings.response,
                    settings.bandwidth_hz,
                    1.0 / settings.period_s,
                )
            generator = np.random.default_rng([seed, event.event, 2, place])
            noise_code, noise_clipped = noise_codes(
                sampled_cache[key], count, settings.period_s, settings, generator
            )
            stored_places.append(place)
            stored_codes.append(noise_code)
            stored_clipped.append(noise_clipped)
            stored_t0.append(event.t0 + phase_by_device[device])
            stored_noise.append(True)
        if requested:
            order = np.argsort(stored_places)
            stored_places = [stored_places[index] for index in order]
            stored_codes = [stored_codes[index] for index in order]
            stored_clipped = [stored_clipped[index] for index in order]
            stored_t0 = [stored_t0[index] for index in order]
            stored_noise = [stored_noise[index] for index in order]
        if stored_places:
            codes = np.asarray(stored_codes, dtype=np.int16).reshape(
                len(stored_places), count
            )
            clipped = np.asarray(stored_clipped, dtype=np.int64)
            starts = np.asarray(stored_t0, dtype=np.float64)
            noise_flags = np.asarray(stored_noise, dtype=bool)
            names = [readout.electrodes[place] for place in stored_places]
        else:
            codes = np.empty((0, count), dtype=np.int16)
            clipped = np.empty(0, dtype=np.int64)
            starts = np.empty(0, dtype=np.float64)
            noise_flags = np.empty(0, dtype=bool)
            names = []
        append_digitized(
            digitizer_path,
            readout.electrodes,
            attributes,
            EventDigitized(event.event, codes, clipped, starts, names, noise_flags),
            readout.pulse_edge,
        )
        all_codes.append(codes)
        if made_plots < plots and places:
            filtered = filter_waveform(
                event.voltage,
                readout.dt,
                settings.response,
                settings.bandwidth_hz,
            )
            rows = [row for row in range(len(names)) if not noise_flags[row]]
            bin_times = event.t0 + (np.arange(filtered.shape[1]) + 0.5) * readout.dt
            draw_samples(
                plot_path,
                event.event,
                bin_times,
                filtered[[places.index(stored_places[row]) for row in rows]],
                starts[rows, None]
                + np.arange(codes.shape[1])[None, :] * settings.period_s,
                to_volts(codes[rows], settings.bits, settings.lsb_V, settings.offset_V),
                [names[row] for row in rows],
            )
            made_plots += 1
    if plots > 0:
        draw_codes(
            plot_path,
            np.concatenate([c.ravel() for c in all_codes] or [np.empty(0)]),
            settings.bits,
        )
