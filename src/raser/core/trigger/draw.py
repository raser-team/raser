"""Figure of the amplitudes of recorded and discarded events."""

import numpy as np

from raser.supports import figures

_MINIMUM = {"falling", "low"}
_MAXIMUM = {"rising", "high"}


def amplitude(volts, direction):
    """Return the extreme of ``volts`` (V, shape ``(samples,)``) towards the trigger direction.

    ``direction`` is ``"falling"`` or ``"low"`` for the minimum, ``"rising"`` or
    ``"high"`` for the maximum.
    """
    if direction in _MINIMUM:
        return float(np.min(volts))
    if direction in _MAXIMUM:
        return float(np.max(volts))
    raise ValueError(
        f"direction must be 'falling', 'low', 'rising' or 'high', got {direction!r}"
    )


def draw_trigger_amplitude(folder, panels):
    """Draw ``trigger_amplitude``, one panel per trigger channel or slot.

    ``panels`` is a list of ``(title, recorded_V, discarded_V, level_V)``: the
    amplitudes (V, shape ``(events,)``) of the recorded and discarded events
    and the trigger level (V).
    """
    figure, axes = figures.new(1, len(panels))
    axes = np.atleast_1d(axes)
    for axis, (title, recorded_V, discarded_V, level_V) in zip(axes, panels):
        recorded = np.asarray(recorded_V, dtype=np.float64) / figures.UNIT["mV"]
        discarded = np.asarray(discarded_V, dtype=np.float64) / figures.UNIT["mV"]
        level = level_V / figures.UNIT["mV"]
        values = np.concatenate([recorded, discarded, [level]])
        edges = np.histogram_bin_edges(values, bins=20)
        recorded_counts, _, _ = axis.hist(
            recorded, bins=edges, color=figures.HISTOGRAM, label="recorded"
        )
        discarded_counts, _, _ = axis.hist(
            discarded,
            bins=edges,
            histtype="step",
            color="black",
            label="discarded",
        )
        axis.axvline(level, color="black", linestyle="--")
        axis.set_xlabel(figures.label("Amplitude", "mV"))
        figures.events(axis, counts=np.concatenate([recorded_counts, discarded_counts]))
        axis.set_title(title)
        axis.legend()
    return figures.save(figure, folder, "trigger_amplitude")
