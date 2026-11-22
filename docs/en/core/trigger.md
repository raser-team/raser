# Trigger (`core/trigger`)

`src/raser/core/trigger/` is the underlying module of the [trigger stage (`stages/trigger`)](../stages/trigger.md). It takes the digital waveforms written by [digitizer (`core/digitizer`)](digitizer.md), decides event by event whether to record each event according to the trigger conditions, and gives the trigger time of recorded events. Trigger conditions are written either in the component of an oscilloscope that also handles triggering ([digitizer components](../components/digitizer.md#trigger-conditions)), or in the component of a standalone trigger device ([trigger components](../components/trigger.md#coincidence-conditions)).

## Physics

### Level Crossing

A channel's codes are converted back to voltage $\hat V_k$ via Eq. (5) of [digitizer](digitizer.md#quantization), with sample $k$ at time $t_k$ (that electrode's `t0` $+ k\cdot$`sampling_period`). Interpolating linearly between adjacent samples, the time at which the voltage equals level $L$ is:

$$t_{\text{x}} = t_{k-1} + \frac{L - \hat V_{k-1}}{\hat V_k - \hat V_{k-1}}\,(t_k - t_{k-1}) \tag{1}$$

By these times, a channel's record is partitioned into intervals below $L$ and above $L$.

### Edge Trigger

Triggers the first time the source channel crosses the level in the specified direction: $\hat V_{k-1} > L \ge \hat V_k$ for a falling edge, and $\hat V_{k-1} < L \le \hat V_k$ for a rising edge ($k \ge 1$). The trigger time is the crossing time given by Eq. (1). When the first sample of the record is already on the opposite side of the level, the waveform must first return to this side before a subsequent crossing counts.

### Pattern Trigger

In a pattern, each channel has its own level and state (below or above the level). The intervals during which all channels are simultaneously in their respective states form the intersection of the corresponding intervals of each channel; the start of the first interval in the intersection is the trigger time:

$$t_{\text{trig}} = \min\Bigl\{\, t \;:\; t \in \bigcap_{s} I_s \Bigr\},\qquad t > t_{\text{first}} \tag{2}$$

where:

- $I_s$: intervals during which channel $s$ is in its specified state (partitioned by the crossing times of Eq. (1));
- $t_{\text{first}}$: the latest of the first-sample times across the channels.

If the pattern already holds at the start of the record, it must first cease to hold and then hold again to trigger. Channels may belong to different instruments, with times evaluated from each channel's own `t0`.

### Coincidence Between Slots

A standalone trigger device computes the hit time $t_s$ for each slot: the earliest among the times at which each electrode in that slot first crosses the level in the specified direction (using the edge-trigger rule); if no electrode crosses, that slot does not hit. With a coincidence window $W$, the trigger time is

$$t_{\text{trig}} = \min\Bigl\{\, t \in \{t_s\} \;:\; E\bigl(\{\, s : t - W \le t_s \le t \,\}\bigr)\ \text{is true} \Bigr\} \tag{3}$$

where $E(\cdot)$ is the value of the logic expression when the given slots are treated as hits and the rest as misses; when no time window is applied, $W = \infty$. Events for which Eq. (3) has no solution are not recorded. See [trigger components](../components/trigger.md#coincidence-conditions) for how the logic expression is written.

## Algorithm

1. **Read**: Digital waveform files and trigger conditions.
2. **Event-by-event evaluation**: For an oscilloscope's trigger condition: if any channel used has no digital waveform in that event, the event is not recorded; otherwise convert the codes of those channels back to voltage and find the trigger time by edge or pattern, and if none is found, do not record the event. For a standalone trigger device: find the hit time of each slot from its digital waveforms and evaluate Eq. (3) for the trigger time; slots with no digital waveform in that event do not hit.
3. **Output**: Pass the event IDs and trigger times of recorded events to the trigger stage to write into `trigger.h5`.

## Software Implementation

### Module and Function Responsibilities

- `__init__.py`: package docstring.
- `conditions.py`: `TriggerConditions`, constructed from the `trigger` of an oscilloscope component; raises an error on missing keys, extra keys, or invalid values.
- `coincidence.py`: parsing and evaluation of logic expressions, and Eq. (3).
- `crossing.py`: Eq. (1) and partitioning by level.
- `job.py`: `write_triggered`, a single job from digital waveform files to `trigger.h5`: edge, Eq. (2), Eq. (3), and writing.
- `draw.py`: plots for this stage.

## Interface

### Settings

The `trigger` of an oscilloscope component, with keys given in [digitizer components](../components/digitizer.md#trigger-conditions); keys for a standalone trigger device are given in [trigger components](../components/trigger.md#key-meanings).

### Input

`digitizer.h5` of the `digitizer` node (`digitizer.<position>.h5` for each position in multi-position experiments, where each position is a slot); see the "Output" section of [digitizer](digitizer.md) for the format.

### Output: `trigger.h5`

One `trigger.<position>.h5` per position in multi-position experiments.

| Category | Name | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| Attribute | `events_seen` | integer | count | Total number of events in `digitizer.h5` |
| Dataset | `event` | `(recorded,)`, `int64` | none | Event IDs of recorded events |
| Dataset | `trigger_time` | `(recorded,)`, `float64` | $\text{s}$ | Trigger times of recorded events |

Downstream stages read the digital waveforms of recorded events from `digitizer.h5` by `event`.

### Plot Output

For the first few recorded events, overlays the voltages converted back from codes for the channels used by triggering, dashed lines at their respective levels, and a vertical line at the trigger time, with $\text{ns}$ on the horizontal axis and $\text{mV}$ on the vertical axis, writing pdf and root for each plot.
