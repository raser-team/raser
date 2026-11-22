"""Run edge and pattern triggering on a digitizer file."""

from dataclasses import dataclass

import h5py
import numpy as np

from raser.core.digitizer.digital_waveforms import read_digitized
from raser.core.digitizer.quantize import to_volts

from .coincidence import CoincidenceSettings, coincidence_time
from .conditions import TriggerConditions
from .crossing import first_crossing, state_intervals
from .draw import amplitude, draw_trigger_amplitude


@dataclass(frozen=True)
class Triggered:
    events_seen: int
    event: np.ndarray
    trigger_time: np.ndarray


def _pattern_time(event, digitized, conditions):
    by_place = {
        digitized.electrodes.index(name): row
        for row, name in enumerate(event.electrodes)
    }
    if any(condition.place not in by_place for condition in conditions):
        return None
    intersections = None
    first_times = []
    for condition in conditions:
        row = by_place[condition.place]
        volts = to_volts(
            event.code[row], digitized.bits, digitized.lsb_V, digitized.offset_V
        )
        first_time = float(event.t0[row])
        first_times.append(first_time)
        intervals = state_intervals(
            volts,
            condition.level_V,
            condition.state,
            first_time,
            digitized.sampling_period,
        )
        if intersections is None:
            intersections = intervals
        else:
            combined = []
            for left_start, left_stop in intersections:
                for right_start, right_stop in intervals:
                    start = max(left_start, right_start)
                    stop = min(left_stop, right_stop)
                    if stop > start:
                        combined.append((start, stop))
            intersections = combined
    if not intersections:
        return None
    t_first = max(first_times)
    intersections.sort()
    for start, _ in intersections:
        if start > t_first:
            return start
    return None


def _trigger_time(event, digitized, conditions):
    by_place = {
        digitized.electrodes.index(name): row
        for row, name in enumerate(event.electrodes)
    }
    if conditions.mode == "edge":
        condition = conditions.conditions[0]
        if condition.place not in by_place:
            return None
        row = by_place[condition.place]
        volts = to_volts(
            event.code[row], digitized.bits, digitized.lsb_V, digitized.offset_V
        )
        return first_crossing(
            volts,
            condition.level_V,
            condition.slope,
            float(event.t0[row]),
            digitized.sampling_period,
        )
    return _pattern_time(event, digitized, conditions)


def _write_trigger_file(path, events_seen, events, trigger_times):
    """Write ``trigger.h5``: attribute events_seen, datasets event and trigger_time (s)."""
    with h5py.File(str(path), "w") as output:
        output.attrs["events_seen"] = int(events_seen)
        output.create_dataset(
            "event", data=np.asarray(events, dtype=np.int64), dtype="int64"
        )
        output.create_dataset(
            "trigger_time",
            data=np.asarray(trigger_times, dtype=np.float64),
            dtype="float64",
        )


def _slot_hit_time(digitized, event, level_V, slope):
    """Earliest crossing time (s) over the stored electrodes of one event, or None."""
    times = []
    for row in range(event.code.shape[0]):
        volts = to_volts(
            event.code[row], digitized.bits, digitized.lsb_V, digitized.offset_V
        )
        crossing = first_crossing(
            volts, level_V, slope, float(event.t0[row]), digitized.sampling_period
        )
        if crossing is not None:
            times.append(crossing)
    return min(times) if times else None


def write_coincidence(
    digitizer_paths,
    trigger_paths,
    settings: CoincidenceSettings,
    plot_path,
):
    """Write one identical ``trigger.h5`` per slot for a coincidence trigger.

    ``digitizer_paths`` and ``trigger_paths`` map every slot of ``settings`` to
    a path; a slot whose digitizer path is ``None`` has no file and is hit in
    no event. Events are matched by event number over the union of the events
    of the slot files; a slot without the event, or without a stored electrode
    in it, is not hit.
    """
    slots = list(settings.slots)
    if set(digitizer_paths) != set(slots) or set(trigger_paths) != set(slots):
        raise ValueError(
            f"digitizer_paths and trigger_paths must have exactly the slots {slots}"
        )
    waveforms = {
        slot: read_digitized(digitizer_paths[slot])
        for slot in slots
        if digitizer_paths[slot] is not None
    }
    events = {}
    for slot, digitized in waveforms.items():
        numbers = [event.event for event in digitized.events]
        if len(set(numbers)) != len(numbers):
            raise ValueError(f"{digitizer_paths[slot]} has an event number twice")
        events[slot] = {event.event: event for event in digitized.events}
    numbers = sorted(set().union(*(set(by_number) for by_number in events.values())))
    recorded = []
    for number in numbers:
        hit_times = {}
        for slot in events:
            event = events[slot].get(number)
            if event is None:
                continue
            time = _slot_hit_time(
                waveforms[slot], event, settings.level_V[slot], settings.slope
            )
            if time is not None:
                hit_times[slot] = time
        trigger_time = coincidence_time(
            settings.require, hit_times, settings.coincidence_window_s
        )
        if trigger_time is not None:
            recorded.append((number, trigger_time))
    for slot in slots:
        _write_trigger_file(
            trigger_paths[slot],
            len(numbers),
            [item[0] for item in recorded],
            [item[1] for item in recorded],
        )
    recorded_numbers = {item[0] for item in recorded}
    panels = []
    for slot in slots:
        kept, dropped = [], []
        for event in waveforms[slot].events if slot in waveforms else []:
            if event.code.shape[0] == 0:
                continue
            digitized = waveforms[slot]
            values = [
                amplitude(
                    to_volts(
                        event.code[row],
                        digitized.bits,
                        digitized.lsb_V,
                        digitized.offset_V,
                    ),
                    settings.slope,
                )
                for row in range(event.code.shape[0])
            ]
            value = min(values) if settings.slope == "falling" else max(values)
            (kept if event.event in recorded_numbers else dropped).append(value)
        panels.append((slot, kept, dropped, settings.level_V[slot]))
    if any(kept or dropped for _, kept, dropped, _ in panels):
        draw_trigger_amplitude(plot_path, panels)


def write_triggered(
    digitizer_path, trigger_path, conditions: TriggerConditions, plot_path
):
    """Write event numbers and trigger times to ``trigger.h5``."""
    digitized = read_digitized(digitizer_path)
    for condition in conditions:
        if condition.place >= len(digitized.electrodes):
            raise ValueError(
                f"trigger channel {condition.channel} is outside the "
                f"{len(digitized.electrodes)} electrodes of {digitizer_path}"
            )
    recorded = []
    for event in digitized.events:
        trigger_time = _trigger_time(event, digitized, conditions)
        if trigger_time is not None:
            recorded.append((event, trigger_time))
    _write_trigger_file(
        trigger_path,
        len(digitized.events),
        [item[0].event for item in recorded],
        [item[1] for item in recorded],
    )
    recorded_numbers = {item[0].event for item in recorded}
    panels = []
    for condition in conditions:
        direction = condition.slope or condition.state
        kept, dropped = [], []
        for event in digitized.events:
            names = list(event.electrodes)
            name = digitized.electrodes[condition.place]
            if name not in names:
                continue
            volts = to_volts(
                event.code[names.index(name)],
                digitized.bits,
                digitized.lsb_V,
                digitized.offset_V,
            )
            value = amplitude(volts, direction)
            (kept if event.event in recorded_numbers else dropped).append(value)
        panels.append((condition.channel, kept, dropped, condition.level_V))
    if any(kept or dropped for _, kept, dropped, _ in panels):
        draw_trigger_amplitude(plot_path, panels)


def read_triggered(path):
    """Read a trigger result file."""
    with h5py.File(str(path), "r") as file:
        if set(file) != {"event", "trigger_time"}:
            raise ValueError(f"{path} must contain event and trigger_time datasets")
        if "events_seen" not in file.attrs:
            raise ValueError(f"{path} is missing attribute 'events_seen'")
        event = file["event"][()]
        trigger_time = file["trigger_time"][()]
        if event.dtype != np.dtype("int64") or trigger_time.dtype != np.dtype(
            "float64"
        ):
            raise ValueError(f"{path} has trigger datasets of the wrong type")
        if event.shape != trigger_time.shape:
            raise ValueError(f"{path} has event and trigger_time lengths that differ")
        events_seen = int(file.attrs["events_seen"])
    return Triggered(events_seen, event, trigger_time)
