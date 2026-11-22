# Event Reconstruction Stage (`stages/reconstruction`)

`src/raser/stages/reconstruction.py` is the 7th stage, `reconstruction`, of the eight-stage simulation chain, dispatched by `raser reconstruction` (short alias `raser reco`) or by benchmark and application experiment commands. Positioned after the [Trigger Stage (`stages/trigger`)](trigger.md), it reads the recorded event IDs from the `trigger` node and the digital waveforms of those events from the [Digitization Stage (`stages/digitizer`)](digitizer.md) node. This stage converts quantized codes back to voltage ($\text{V}$) using `lsb_V` and `offset_V`, converts thresholds from $\text{mV}$ to $\text{V}$, determines each electrode's pulse edge direction, calls [Event Reconstruction (`core/reconstruction`)](../core/reconstruction.md) to subtract the baseline, estimate noise, and extract pulse amplitude, timing quantities, main-lobe area, and cross-electrode clusters, and writes each recorded event as a row of an event table into `reconstruction.h5` inside its own node `nodes/reconstruction/<node_id>/`. The event table is passed downstream to the [Statistical Analysis Stage (`stages/analysis`)](analysis.md) for time-resolution statistics.

## Behavior

### Running Up to the Reconstruction Stage

`raser reconstruction` (or `raser reco`) runs up through `reconstruction` on the experiment in the current folder or at the given path, computing any missing upstream nodes first:

```bash
raser reconstruction [path]
raser reco [path]
```

Multi-position experiments (such as the `24` positions in `cflm`) reconstruct each position separately using the same set of reconstruction settings.

For example, scanning two bias voltages on the `HPK-Si-PiN` example:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

When `HPK-Si-PiN` is not present under `work/`, the command runs in place under `examples/HPK-Si-PiN/`, and the experiment folder is `examples/HPK-Si-PiN/signal`. Before `reconstruction`, `digitizer` samples and quantizes each job's waveforms using the sampling rate, bandwidth, and range of `MXR608A` and writes `digitizer.h5`; `trigger` writes the event IDs that cross the amplitude threshold into `trigger.h5`. Both `voltage_100` and `voltage_200` are reconstructed with the default parameters `threshold = 10.0` $\text{mV}$, `amplitude_threshold = 10.0` $\text{mV}$, and 9 constant fractions `[0.1, ..., 0.9]`, inheriting `pulse_edge = ['falling']` from `readout`. In the node pointed to by `points/voltage_200/reconstruction/0`, `reconstruction.h5` has attributes `threshold = 0.01` (in $\text{V}$), `amplitude_threshold = 0.01` (in $\text{V}$), `edge = ['falling']`, `electrodes = ['top']`, and `fractions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]`, with 14 datasets as follows (each row is an event recorded by `trigger`, and `recorded` is the length of `event` in that job's `trigger.h5`):

| Dataset name | Example shape | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `event` | `(recorded,)` | `int64` | None | Geant4 event ID of each event recorded by `trigger` |
| `selected` | `(recorded,)` | `bool` | None | Whether the event finds a cluster seed: at least one electrode has amplitude at least `amplitude_threshold` |
| `cluster_size` | `(recorded,)` | `int64` | electrodes | Number of electrodes in the cluster |
| `cluster_center` | `(recorded,)` | `float64` | electrode index (0-based) | Amplitude-weighted center position of the cluster (`NaN` when there is no cluster) |
| `traced` | `(recorded, 1)` | `bool` | None | Whether this event has a stored waveform for this electrode |
| `above` | `(recorded, 1)` | `bool` | None | Whether the waveform peak reaches `threshold` |
| `baseline` | `(recorded, 1)` | `float64` | $\text{V}$ | Baseline mean over the first `200` waveform samples |
| `noise` | `(recorded, 1)` | `float64` | $\text{V}$ | Baseline population standard deviation over the first `200` waveform samples |
| `amplitude` | `(recorded, 1)` | `float64` | $\text{V}$ | Maximum pulse amplitude above baseline |
| `ToA` | `(recorded, 1)` | `float64` | $\text{s}$ | Time of arrival over threshold |
| `ToT` | `(recorded, 1)` | `float64` | $\text{s}$ | Time over threshold |
| `CoG` | `(recorded, 1)` | `float64` | $\text{s}$ | Time center of gravity over the above-threshold interval |
| `area` | `(recorded, 1)` | `float64` | $\text{V}\cdot\text{s}$ | Integrated area of the positive main pulse lobe |
| `CFD` | `(recorded, 1, 9)` | `float64` | $\text{s}$ | Timing results corresponding to each constant fraction in `fractions` |

### Changing Reconstruction Settings with Full Upstream Node Reuse

Reconstruction settings are read only by `reconstruction`. When only this section is changed, the fingerprints of `deposit`, `current`, `readout`, `digitizer`, and `trigger` remain unchanged, all upstream nodes are reused, and only new `reconstruction` nodes are computed:

```bash
raser reco examples/HPK-Si-PiN/signal --set reconstruction.threshold=15 --set reconstruction.amplitude_threshold=20
```

`--set` writes the new thresholds `15` $\text{mV}$ and `20` $\text{mV}$ into the `reconstruction` section of `config.json`, and subsequent `raser analysis` runs gather statistics under the new thresholds. Nodes are append-only: changing the thresholds back to `10` points the view back to the original node. When the code version differs from the one recorded in the node, only a notice is printed and the result is still reused. Each node is locked individually, and a partially written node carries the `.part` suffix. Add `--dry-run` before an actual run to print only the scan points, stages, and job states to be executed. See [Slices and Reruns](../lifecycle/slices.md) for node and reuse rules.

### Upstream Zero-Event Jobs and Empty Multi-Position Inputs

When upstream `deposit` records `0` valid events in a job, `reconstruction` skips that job accordingly. In a multi-position experiment, when a position has no energy deposition—and therefore no waveform—in a job, that position directly records `0` events while other positions in the same job run normally.

### Inheriting Pulse Edge Direction and Reversed-Edge Notice

When `reconstruction.edge` is set to `null`, each electrode inherits the `pulse_edge` provided by `readout` (for example, negative pulses use `"falling"`, so reconstruction multiplies the baseline-subtracted net waveform by `-1.0` to flip it positive before extracting features). When `"rising"` or `"falling"` is specified via `reconstruction.edge`, that direction is applied uniformly to all electrodes; if any electrode has the opposite `pulse_edge`, computation continues normally and a notice line is printed to the terminal for that electrode:

```text
<readout_path>: edge <edge> given for <electrode>, whose pulse is <pulse_edge>: its pulses are not seen as the readout makes them
```

This indicates that the chosen direction is opposite to the pulse polarity actually produced by the readout chain. Unless performing an intentional reversed-polarity check, delete `reconstruction.edge`, or change it to match `pulse_edge`.

## Rules

### Built-in Constants

The constants below are hardcoded in module source code:

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `MILLIVOLT` | `1.0e-3` | $\text{V/mV}$ (commented as `V` in code) | `src/raser/stages/reconstruction.py`: multiplier converting `threshold` and `amplitude_threshold` from $\text{mV}$ to $\text{V}$ |
| `BASELINE_POINTS` | `200` | samples | `src/raser/core/reconstruction/event.py`: number of samples at the start of each waveform used to compute baseline mean and noise standard deviation |
| `EDGE_SIGN` | `{"rising": 1.0, "falling": -1.0}` | None | `src/raser/core/reconstruction/event_table.py`: polarity multiplier flipping the net waveform into a positive pulse according to the chosen edge |

### Parsing and Launching Stage Commands (`stage_commands.run`)

1. **Mount arguments (`register`)**: Register `reconstruction` (alias `reco`), mount shared run parameters and this stage's command options (settings for upstream stages live in their own sections; see [Electronics Readout Stage (`stages/readout`)](readout.md), [Digitization Stage (`stages/digitizer`)](digitizer.md), and [Trigger Stage (`stages/trigger`)](trigger.md)), and bind the execution entry point to `partial(run, "reconstruction")`.
2. **Resolve experiment**: Read `config.json` in the experiment folder to identify its experiment class.
3. **Validate stage**: If the experiment class does not include the `reconstruction` stage, exit with:

   ```text
   <folder>: the experiment <workflow> has no reconstruction slice; its slices: <names>
   ```

   Use a stage command supported by that experiment, or switch to an experiment that includes reconstruction.
4. **Launch**: Set the cutoff stage to `reconstruction`, enter the project context of the experiment, change into the experiment folder to run, and restore the original directory afterward. When the experiment folder contains `config.json`, the target argument on the command line is rewritten to an absolute path so that cluster jobs rerunning the original command from the experiment folder can locate it.

### Single-Job Reconstruction (`reconstruction.run` and `reconstruct`)

1. **Multi-position pre-check**: When a position is given and that position has no input waveform in the current job, return `{"events": 0}` immediately.
2. **Invoke reconstruction**: `reconstruct(digital_waveforms, recorded_events, output_event_table, float(threshold), float(amplitude_threshold), tuple(float(part) for part in fractions), edge)`.
3. **Read digital waveforms of recorded events**: Read the `event` dataset from `trigger.h5`, fetch the codes of those events from `digitizer.h5`, and convert them back to voltage (in $\text{V}$) via $V = (\texttt{code} - 2^{N-1} + 0.5)\cdot\texttt{lsb\_V} + \texttt{offset\_V}$ (where $N$ is the `bits` attribute); the timestamp of the $k$-th sample (0-based) of each electrode is that electrode's `t0` $+ k\cdot$`sampling_period` (in $\text{s}$). Pulse edge directions are taken from the `pulse_edge` attribute of `digitizer.h5`. See [Digitization Stage (`stages/digitizer`)](digitizer.md) for the digital waveform format.
4. **Select pulse edge direction (`chosen_edges(edge, waveforms.pulse_edge, waveforms.electrodes)`)**:
   - When `edge is None`, return `list(waveforms.pulse_edge)` and an empty notice list.
   - When `edge` is not in `EDGE_SIGN`, raise:

     ```text
     ValueError: edge <value>: the thresholds are set on a rising (positive pulses) or a falling (negative pulses) edge
     ```

     Change it to `"rising"` or `"falling"`, or delete the key so it inherits `pulse_edge`.
   - When `edge` is `"rising"` or `"falling"`, apply it to all electrodes; generate one notice for each electrode whose `pulse_edge` differs from `edge`, and `reconstruct` prints each as `f"{readout_path}: {note}"`.
5. **Convert thresholds and extract features (`event_table`)**:
   - Pass `threshold * MILLIVOLT` and `amplitude_threshold * MILLIVOLT` (in $\text{V}$).
   - If any element of `fractions` lies outside the open interval $(0, 1)$, raise `ValueError: fractions <invalid_list>: a constant fraction lies between 0 and 1`.
   - If the input contains no events, raise `ValueError: the readout holds no event`; inspect the job's `trigger` and upstream outputs and recompute upstream stages if needed.
   - Call `net_pulse(samples)` on every stored electrode waveform of every event. If the number of samples is `<= 200` (`BASELINE_POINTS`), raise `ValueError: <count> samples, not more than the 200 of the baseline`; check whether the simulation time window or sampling interval `sampling_period` is too short. When the sample count exceeds `200`, subtract the mean of the first `200` samples as `baseline` ($\text{V}$), compute the population standard deviation of the first `200` samples as `noise` ($\text{V}$), multiply by `EDGE_SIGN[edge]` to flip positive, and compute single-electrode features and cross-electrode clusters via `electrode_row` and `cluster`, assembling an `EventTable`.
6. **Write output (`write_event_table(path, table)`)**: Write the `EventTable` to `reconstruction.h5` in one pass.

## Software Implementation

### Source File Responsibilities

- `src/raser/stages/reconstruction.py`: Defines `MILLIVOLT`, single-job reconstruction function `reconstruct`, and stage entry point `run`; handles unit conversion, printing reversed-edge notices, and invoking core reconstruction functions.
- `src/raser/stages/chain.py`: Defines the lazy-import entry point `_reconstruction` for the `reconstruction` module.
- `src/raser/stages/stage_commands.py`: Registers stage commands; resolves the target experiment, verifies it includes the target stage, sets the cutoff stage, and switches into the experiment folder to run.
- `src/raser/stages/files.py`: Provides the input and output file paths for each stage in the current job.

### Core Data Structures

`EventTable` (`src/raser/core/reconstruction/event_table.py`):

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `electrodes` | `list[str]` | None | Readout electrode names, matching the order of axis 2 in 2D and 3D arrays |
| `threshold` | `float` | $\text{V}$ | Over-threshold value converted to $\text{V}$ |
| `amplitude_threshold` | `float` | $\text{V}$ | Amplitude threshold for finding cluster seeds, converted to $\text{V}$ |
| `fractions` | `tuple[float, ...]` | None | Constant fraction discrimination ratios, each in $(0, 1)$ |
| `edges` | `list[str]` | None | Actual pulse edge direction used for each electrode (`"rising"` or `"falling"`) |
| `columns` | `dict[str, np.ndarray]` | $\text{V}$ for `baseline`, `noise`, `amplitude`; $\text{s}$ for `ToA`, `ToT`, `CoG`, `CFD`; $\text{V}\cdot\text{s}$ for `area`; electrodes for `cluster_size`; electrode index for `cluster_center`; dimensionless for the rest | Mapping from the 14 output dataset names to NumPy arrays |

## Interface

### Options and Configuration Keys

Only the keys listed below are configurable in this stage; the baseline sample count `200`, millivolt-to-volt conversion factor `1.0e-3` $\text{V/mV}$, and edge polarity multipliers are hardcoded. Settings are stored in the `reconstruction` section of `config.json`, and `--set` and `--scan` use `"section.key"` addresses, such as `--set reconstruction.threshold=15`. The "Value in example" column shows what `examples/HPK-Si-PiN/signal/config.json` sets; if `config.json` is missing a required key, an error is raised naming the missing `"section.key"`.

| Section.key | Value in example | Unit | Meaning |
| --- | --- | --- | --- |
| `[path]` | Current folder | None | Experiment folder |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | Pulse over-threshold value (multiplied by `1e-3` inside the stage to convert to $\text{V}$); used to determine per-electrode `above`, compute `ToA`, `ToT`, `CoG`, and `area`, and include immediately adjacent electrodes around a seed in a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | Amplitude threshold for cluster seed channels (multiplied by `1e-3` inside the stage to convert to $\text{V}$); electrodes with amplitude at or above it become seeds, events recorded by `trigger` that find a seed are marked `selected`, and `analysis` timing statistics use `selected` events |
| `reconstruction.edge` | `null` (each electrode inherits `pulse_edge` written by `readout`) | None | Pulse edge direction on which thresholds act: `"rising"` (positive pulse), `"falling"` (negative pulse), or `null` (each electrode inherits `pulse_edge` written by `readout`) |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | None | Constant fraction discrimination (`CFD`) amplitude ratios, each strictly in $(0, 1)$; written in the `reconstruction` section of `config.json` |

Because the list value of `fractions` contains square brackets and commas, passing it on the command line via `--set` or `--scan` raises an error:

```text
ValueError: reconstruction.fractions = <value>: the folder of this value would be named <name>, which holds more than letters, digits and ._+-; scan or set a number or a short name, and give an expression such as a doping profile a parameter with a name in its file
```

Edit `fractions` directly in the `reconstruction` section of `config.json` instead.

Settings for upstream stages live in their own sections; see [Energy Deposition Stage (`stages/deposit`)](deposit.md), [Carrier Transport and Induced Current Stage (`stages/current`)](current.md), [Electronics Readout Stage (`stages/readout`)](readout.md), [Digitization Stage (`stages/digitizer`)](digitizer.md), and [Trigger Stage (`stages/trigger`)](trigger.md). Shared run parameters (`-s`, `--seed`, `--same-seeds`, `--set`, `--scan`, `-b`, `-t`, `-mem`, `--dry-run`) are documented in [Command-Line Interface (`raser`)](../cli.md) and [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md).

### Files Read and Written

- **Read: `trigger.h5` in the `trigger` node and `digitizer.h5` in the `digitizer` node** (`trigger.<position>.h5` and `digitizer.<position>.h5` in the same node for multi-position experiments). The `event` dataset (`(recorded,)`, `int64`) in `trigger.h5` gives the recorded event IDs; `digitizer.h5` provides the quantized codes `code` (`int16`) for those events along with attributes `electrodes`, `sampling_period` ($\text{s}$), `lsb_V` ($\text{V}$), `offset_V` ($\text{V}$), `bits`, and `pulse_edge`. See [Digitization Stage (`stages/digitizer`)](digitizer.md) for the format.
- **Write: `nodes/reconstruction/<node_id>/reconstruction.h5`** (one file `reconstruction.<position>.h5` per position in the same node in multi-position experiments). Written when upstream stages have recorded events and (in multi-position experiments) the position has input waveforms. The HDF5 file contains 5 attributes (`electrodes` [`string[]`, dimensionless], `threshold` [`float64`, in $\text{V}$], `amplitude_threshold` [`float64`, in $\text{V}$], `fractions` [`float64[]`, shape `(fractions,)`, dimensionless], `edge` [`string[]`, `"rising"` or `"falling"`]), 4 1D datasets of shape `(recorded,)` (`event` [`int64`], `selected` [`bool`], `cluster_size` [`int64`, in electrodes], `cluster_center` [`float64`, in 0-based electrode index]), 9 2D datasets of shape `(recorded, electrodes)` (`traced` [`bool`], `baseline` [`float64`, in $\text{V}$], `noise` [`float64`, in $\text{V}$], `amplitude` [`float64`, in $\text{V}$], `above` [`bool`], `ToA` [`float64`, in $\text{s}$], `ToT` [`float64`, in $\text{s}$], `CoG` [`float64`, in $\text{s}$], `area` [`float64`, in $\text{V}\cdot\text{s}$]), and 1 3D dataset `CFD` of shape `(recorded, electrodes, fractions)` (`float64`, in $\text{s}$). See [Event Reconstruction (`core/reconstruction`)](../core/reconstruction.md) for definitions of all attributes and datasets.
- **Write: `nodes/reconstruction/<node_id>/node.json`**. Records this node's inputs along with the code version, runtime environment, and run status.
- **Write: `points.json` and `points/<point>/reconstruction/<job>`**. The parameter table records the `reconstruction` node ID used by each point; the view symlink points to that node.
