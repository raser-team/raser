# Trigger Stage (`stages/trigger`)

`trigger` is the 6th stage of the simulation chain, positioned after the [Digitization Stage (`stages/digitizer`)](digitizer.md) and before the [Event Reconstruction Stage (`stages/reconstruction`)](reconstruction.md), with the command `raser trigger` (short alias `raser trig`). It reads `digitizer.h5` from the `digitizer` node, the `trigger` section of `config.json`, and the trigger conditions in [Trigger Components (`components/trigger`)](../components/trigger.md), deciding which events are recorded just as a real trigger device (such as an oscilloscope trigger) does. Event IDs of recorded events are written into `trigger.h5` of this stage's node (under `nodes/trigger/<node_id>/`), pointed to by the view `points/<point>/trigger/<job>`, and handed off to `reconstruction` (which uses it to read the digital waveforms of those events from `digitizer.h5`). Everything in a real instrument belonging to triggering belongs here.

## Behavior

### Running Up to Trigger

`raser trigger` runs up to `trigger` on the experiment in the current folder or at the given path, automatically computing any missing upstream stages:

```bash
raser trigger [path]
raser trig [path]
```

Omitting the path uses the current folder; providing a path accepts either a relative or an absolute path. Upstream `field`, `deposit`, `current`, `readout`, and `digitizer` nodes with matching fingerprints are reused regardless of which point or run produced them; missing ones are computed first in chain order. `trigger` nodes are likewise reused by fingerprint. When the code version differs from the one recorded in the node, only a notice is printed and the result is still reused. See [Slices and Reruns](../lifecycle/slices.md) for nodes, the parameter table, and reuse.

### Amplitude-Threshold Triggering

Following the group's bench measurement settings, the `HPK-Si-PiN` example uses edge triggering on `CH1` of `MXR608A`: falling edge, level $-2\ \text{mV}$. Events whose digital waveform on `CH1` crosses downward past the level are recorded in `trigger.h5`, and those that do not are discarded. To change the level:

```bash
raser trig --set digitizer.device.trigger.level_V=-0.005
```

Because this modifies the trigger condition, only a new `trigger` node is produced, while `digitizer` and earlier nodes are reused as normal.

### Coincidence Between Multiple Devices

The two- and three-device setups of `timeres` use the standalone trigger device `coincidence`: each slot is assigned a threshold, and whether the whole event is recorded is decided from the logic expression and coincidence window, with every position recording the same set of events. See [Trigger Components](../components/trigger.md#coincidence-conditions) for the syntax.

## Rules

### Execution Flow

1. Read `digitizer.h5` from the `digitizer` node (converting quantized codes back to voltage in $\text{V}$ using `lsb_V` and `offset_V`), together with the `trigger` section and the trigger conditions from the trigger component.
2. Evaluate each event against the trigger condition to decide which events are recorded: when `trigger.device` is `null`, use each position's oscilloscope edge or pattern trigger; otherwise use the coincidence condition of the standalone trigger device. See [Trigger (`core/trigger`)](../core/trigger.md) for the equations.
3. Write the `event` (`int64`) dataset of recorded event IDs and `trigger_time` ($\text{s}$) into `nodes/trigger/<node_id>/trigger.h5` (one file `trigger.<position>.h5` per position in the same node in multi-position experiments), and write this stage's plot `trigger_amplitude`.

The fingerprint of this stage's node is composed of the setting values used from the `trigger` section, the part of the trigger component used, and the node ID of the upstream `digitizer` node.

## Software Implementation

- `src/raser/stages/trigger.py`: Module for this stage. `triggered(kwargs, position=None)` uses the oscilloscope's own trigger, one slice per position in multi-position experiments: it reads the `digitizer.h5` of the position and takes the trigger conditions from `trigger` in the content of the `digitizer.device` component, raising an error when the component has no `trigger`; when upstream left no digital waveform file at the position, the slice writes no file and records 0 events. `coincident(kwargs, positions)` uses a standalone trigger device: one slice reads the `digitizer.<position>.h5` of every position and writes the `trigger.<position>.h5` of every position, with settings from the content of the `trigger.device` component, raising an error when there is no such component; a position that left no digital waveform file is a slot that hits in no event. Both functions return the number of recorded events.
- `src/raser/core/trigger/`: Level crossing, edge, pattern, coincidence between slots, and writing; see [Trigger (`core/trigger`)](../core/trigger.md).

## Interface

### Settings

The `trigger` section of `config.json` has only one key, the slot `device`: `null` means using the trigger condition of the oscilloscope in `digitizer.device`; otherwise it is the component name of a standalone trigger device or an object with `name`. An error is raised if this key is missing. Settings of this stage itself live in the `trigger` section of `config.json`; use `--set trigger.<key>=<value>` to modify a setting. The `trigger` section holds analysis parameters and is not scanned: `--scan` on it raises an error; to use another value, change it with `--set` and run again, which reuses the events already measured and redoes only `trigger` and the stages after it. Components for standalone trigger devices are stored under `components/trigger/` and selected via the slot `trigger.device`, with their internal quantities addressed as "section.slot.key" (`--set trigger.device.<key>=<value>`); `name` cannot be modified with `--set`—to switch devices, write `--set trigger.device=<component_name>`, which replaces the entire slot with that component file and drops any previously overridden keys. When a single instrument handles both sampling and triggering (such as the `MXR608A` oscilloscope), its settings are stored once under [`components/digitizer/`](../components/digitizer.md) and read by both `digitizer` and `trigger`, with its trigger conditions in the slot `digitizer.device` addressed as `digitizer.device.trigger.<key>` (for example, `digitizer.device.trigger.level_V`); see [Trigger Components (`components/trigger`)](../components/trigger.md). Common run parameters are documented in [Command-Line Interface (`raser`)](../cli.md), and configuration sections and scanning in [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md).

### Files Read and Written

- **Read: `digitizer.h5` in the `digitizer` node** (`digitizer.<position>.h5` in multi-position experiments): Digital waveforms (quantized codes `code` together with `sampling_period`, `lsb_V`, `offset_V`, `bits`, etc.), written by the [Digitization Stage (`stages/digitizer`)](digitizer.md), read-only for this stage.
- **Write: `nodes/trigger/<node_id>/trigger.h5`** (`trigger.<position>.h5` in the same node in multi-position experiments): List of recorded events containing the dimensionless `int64` dataset `event` of shape `(recorded,)`, storing the event IDs that pass the trigger condition, the `float64` dataset `trigger_time` ($\text{s}$) of the same shape, storing the trigger times, and the attribute `events_seen`, giving the total number of events in `digitizer.h5`; downstream [Event Reconstruction Stage (`stages/reconstruction`)](reconstruction.md) uses it to read the digital waveforms of those events from `digitizer.h5`.
- **Write: this stage's plots and `nodes/trigger/<node_id>/node.json`**: The node also contains this stage's plots and `node.json`, recording this stage's inputs, code version, runtime environment, and run status. A partially written node carries the `.part` suffix and is renamed to its final name only after writing finishes.
- **Write: `points.json` and `points/<point>/trigger/<job>`**: The parameter table records the `trigger` node ID used by each point; the view symlink points to `../../../nodes/trigger/<node_id>`.
