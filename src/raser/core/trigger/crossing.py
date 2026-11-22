"""Linear threshold crossings and low/high waveform intervals."""

import numpy as np


def crossing_time(previous, current, level, previous_time, current_time):
    """Return equation (1) for two samples on opposite sides of a level."""
    denominator = float(current) - float(previous)
    if denominator == 0:
        raise ValueError("crossing samples must have different voltages")
    return float(
        previous_time
        + (float(level) - float(previous))
        / denominator
        * (float(current_time) - float(previous_time))
    )


def first_crossing(volts, level, slope, t_first, period):
    """Return the first crossing in the requested direction."""
    values = np.asarray(volts, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("volts must be one-dimensional")
    if slope not in {"falling", "rising"}:
        raise ValueError("slope must be 'falling' or 'rising'")
    if not np.isfinite(values).all():
        raise ValueError("volts must be finite")
    level = float(level)
    t_first = float(t_first)
    period = float(period)
    if (
        not np.isfinite(level)
        or not np.isfinite(t_first)
        or not np.isfinite(period)
        or period <= 0
    ):
        raise ValueError("level and t_first must be finite and period must be positive")
    if values.size < 2:
        return None
    for index in range(1, values.size):
        previous, current = values[index - 1], values[index]
        if slope == "falling":
            crossed = previous > level >= current
        else:
            crossed = previous < level <= current
        if crossed:
            return crossing_time(
                previous,
                current,
                level,
                t_first + (index - 1) * period,
                t_first + index * period,
            )
    return None


def state_intervals(volts, level, state, t_first, period):
    """Return finite intervals in which a sampled channel has ``state``."""
    values = np.asarray(volts, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("volts must be one-dimensional")
    if state not in {"low", "high"}:
        raise ValueError("state must be 'low' or 'high'")
    if values.size < 2:
        return []
    level = float(level)
    t_first = float(t_first)
    period = float(period)
    if (
        not np.isfinite(values).all()
        or not np.isfinite(level)
        or not np.isfinite(t_first)
        or not np.isfinite(period)
        or period <= 0
    ):
        raise ValueError(
            "volts, level, and t_first must be finite and period must be positive"
        )
    boundaries = [t_first]
    for index in range(1, values.size):
        previous, current = values[index - 1], values[index]
        if (previous < level and current >= level) or (
            previous > level and current <= level
        ):
            boundaries.append(
                crossing_time(
                    previous,
                    current,
                    level,
                    t_first + (index - 1) * period,
                    t_first + index * period,
                )
            )
    boundaries.append(t_first + (values.size - 1) * period)
    intervals = []
    for start, stop in zip(boundaries, boundaries[1:]):
        if stop <= start:
            continue
        midpoint = (start + stop) / 2
        sample_index = min(
            int(np.floor((midpoint - t_first) / period)), values.size - 2
        )
        fraction = (midpoint - (t_first + sample_index * period)) / period
        midpoint_value = values[sample_index] + fraction * (
            values[sample_index + 1] - values[sample_index]
        )
        is_state = midpoint_value < level if state == "low" else midpoint_value > level
        if is_state:
            intervals.append((float(start), float(stop)))
    return intervals
