# Trigger Stage (`stages/trigger`)

`trigger` is the 6th stage of the simulation chain, positioned after the [Digitization Stage (`stages/digitizer`)](digitizer.md) and before the [Event Reconstruction Stage (`stages/reconstruction`)](reconstruction.md), with the command `raser trigger` (short alias `raser trig`). It reads the digital waveforms in the `digitizer` node, the `trigger` section of `config.json`, and the trigger conditions in [Trigger Components (`components/trigger`)](../components/trigger.md), deciding which events are recorded just as a real trigger device (such as an oscilloscope trigger) does. Recorded events are written into this stage's node `nodes/trigger/<node_id>/`, pointed to by the view `points/<point>/trigger`, and handed off to `reconstruction`. Everything in a real instrument belonging to triggering belongs here.

## Behavior

### Running Up to Trigger

`raser trigger` runs up to `trigger` on the experiment in the current folder or at the given path, automatically computing any missing upstream stages:

```bash
raser trigger [path]
raser trig [path]
```

Omitting the path uses the current folder; providing a path accepts either a relative or an absolute path. Upstream `field`, `deposit`, `current`, `readout`, and `digitizer` nodes with matching fingerprints are reused regardless of which point or run produced them; missing ones are computed first in chain order. `trigger` nodes are likewise reused by fingerprint. When the code version differs from the one recorded in the node, only a notice is printed and the result is still reused. See [Slices and Reruns](../lifecycle/slices.md) for nodes, the parameter table, and reuse.

### Amplitude-Threshold Triggering

The `HPK-Si-PiN` example triggers on an amplitude threshold: events whose waveform crosses the threshold are recorded, and those that do not are discarded.

## Rules

### Execution Flow

1. Read the digital waveforms from the `digitizer` node, together with the `trigger` section and the trigger conditions from the trigger component.
2. Evaluate each event against the trigger condition to decide which events are recorded.
3. Write the recorded events and this stage's plots into the `trigger` node.

The fingerprint of this stage's node is composed of the setting values used from the `trigger` section, the part of the trigger component used, and the node ID of the upstream `digitizer` node.

## Interface

### Settings

Settings for this stage live in the `trigger` section of `config.json`. Use `--set trigger.<key>=<value>` to modify a setting and `--scan trigger.<key>=<value1>,<value2>` to scan it. Trigger conditions are stored under `components/trigger/`; when a single instrument handles both sampling and triggering (such as an oscilloscope), its settings are stored once under [`components/digitizer/`](../components/digitizer.md) and read by both `digitizer` and `trigger`. Common run parameters are documented in [Command-Line Interface (`raser`)](../cli.md), and configuration sections and scanning in [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md).

### Files Read and Written

- **`digitizer` node**: Digital waveforms written by the [Digitization Stage (`stages/digitizer`)](digitizer.md), read-only for this stage.
- **`nodes/trigger/<node_id>/`**: Recorded events and plots written by this stage, together with a `node.json` recording this stage's inputs, code version, runtime environment, and run status. A partially written node carries the `.part` suffix and is renamed to its final name only after writing finishes.
- **`points/<point>/trigger`**: Symlink pointing to this stage's node; the node ID used by each scan point is recorded in `points.json` in the experiment folder.
