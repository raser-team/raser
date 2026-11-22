# Event Reconstruction Stage (`stages/reconstruction`)

`src/raser/stages/reconstruction.py` is the 7th stage, `reconstruction`, of the eight-stage simulation chain, dispatched by `raser reconstruction` (short alias `raser reco`) or by benchmark and application experiment commands. Positioned after the [Trigger Stage (`stages/trigger`)](trigger.md), it reads the output of `trigger`: the recorded events and their digital waveforms produced by the [Digitization Stage (`stages/digitizer`)](digitizer.md). This stage converts thresholds from $\text{mV}$ to $\text{V}$, determines each electrode's pulse edge direction, calls [Event Reconstruction (`core/reconstruction`)](../core/reconstruction.md) to subtract the baseline, estimate noise, and extract pulse amplitude, timing quantities, main-lobe area, and cross-electrode clusters, and writes each event as a row of an event table into its own node `nodes/reconstruction/<node_id>/`. The event table is passed downstream to the [Statistical Analysis Stage (`stages/analysis`)](analysis.md) for time-resolution statistics.

## Behavior

### Running Up to the Reconstruction Stage

`raser reconstruction` (or `raser reco`) runs up through `reconstruction` on the experiment in the current folder or at the given path, computing any missing upstream nodes first:

```bash
raser reconstruction [path] [<source>] [options...]
raser reco [path] [<source>] [options...]
```

Multi-position experiments (such as the `24` positions in `cflm`) reconstruct each position separately using the same set of reconstruction settings.

For example, scanning two bias voltages on the `HPK-Si-PiN` example:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 -evt 200 --seed 1
```

Both `voltage_100` and `voltage_200` are reconstructed with the default parameters `threshold = 10.0` $\text{mV}$, `amplitude_threshold = 10.0` $\text{mV}$, and 9 constant fractions `[0.1, ..., 0.9]`, inheriting `pulse_edge = ['falling']` from `readout`. In the node pointed to by `points/voltage_200/reconstruction`, job `0`'s event table has attributes `threshold = 0.01` (in $\text{V}$), `amplitude_threshold = 0.01` (in $\text{V}$), `edge = ['falling']`, `electrodes = ['top']`, and `fractions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]`, with 14 datasets as follows (`196` of the `200` events have a stored waveform for the `top` electrode; the remaining `4` fill numeric waveform columns with `NaN` and set `above` to `False`):

| Dataset name | Example shape | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | None | Geant4 event ID of each recorded event |
| `selected` | `(200,)` | `bool` | None | Whether the event finds a seed: at least one electrode has amplitude at least `amplitude_threshold` |
| `cluster_size` | `(200,)` | `int64` | electrodes | Number of electrodes in the cluster |
| `cluster_center` | `(200,)` | `float64` | electrode index (0-based) | Amplitude-weighted center position of the cluster (`NaN` when there is no cluster) |
| `traced` | `(200, 1)` | `bool` | None | Whether this event has a stored waveform for this electrode (`True` for `196` events) |
| `above` | `(200, 1)` | `bool` | None | Whether the waveform peak reaches `threshold` |
| `baseline` | `(200, 1)` | `float64` | $\text{V}$ | Baseline mean over the first `200` waveform samples |
| `noise` | `(200, 1)` | `float64` | $\text{V}$ | Baseline population standard deviation over the first `200` waveform samples |
| `amplitude` | `(200, 1)` | `float64` | $\text{V}$ | Maximum pulse amplitude above baseline |
| `ToA` | `(200, 1)` | `float64` | $\text{s}$ | Time of arrival over threshold |
| `ToT` | `(200, 1)` | `float64` | $\text{s}$ | Time over threshold |
| `CoG` | `(200, 1)` | `float64` | $\text{s}$ | Time center of gravity over the above-threshold interval |
| `area` | `(200, 1)` | `float64` | $\text{V}\cdot\text{s}$ | Integrated area of the positive main pulse lobe |
| `CFD` | `(200, 1, 9)` | `float64` | $\text{s}$ | Timing results corresponding to each constant fraction in `fractions` |

### Changing Reconstruction Settings with Full Upstream Node Reuse

Reconstruction settings are read only by `reconstruction`. When only this section is changed, the fingerprints of `deposit`, `current`, `readout`, `digitizer`, and `trigger` remain unchanged, all upstream nodes are reused, and only new `reconstruction` nodes are computed:

```bash
raser reco work/HPK-Si-PiN/signal --set reconstruction.threshold=15 --set reconstruction.amplitude_threshold=20
```

`--set` writes the new thresholds `15` $\text{mV}$ and `20` $\text{mV}$ into the `reconstruction` section of `config.json`, and subsequent `raser analysis` runs gather statistics under the new thresholds. Nodes are append-only: changing the thresholds back to `10` points the view back to the original node. When the code version differs from the one recorded in the node, only a notice is printed and the result is still reused. Each node is locked individually, and a partially written node carries the `.part` suffix. Add `--dry-run` before an actual run to print only the scan points, stages, and job states to be executed. See [Slices and Reruns](../lifecycle/slices.md) for node and reuse rules.

### Upstream Zero-Event Jobs and Empty Multi-Position Inputs

When upstream `deposit` records `0` valid events in a job, `reconstruction` skips that job accordingly. In a multi-position experiment, when a position has no energy deposition—and therefore no waveform—in a job, that position directly records `0` events while other positions in the same job run normally.

### Inheriting Pulse Edge Direction and Reversed-Edge Notice

When `edge` is unset (default `None`), each electrode inherits the `pulse_edge` provided by `readout` (for example, negative pulses use `"falling"`, so reconstruction multiplies the baseline-subtracted net waveform by `-1.0` to flip it positive before extracting features). When `"rising"` or `"falling"` is specified via `--edge` or `reconstruction.edge`, that direction is applied uniformly to all electrodes; if any electrode has the opposite `pulse_edge`, computation continues normally and a notice line is printed to the terminal for that electrode:

```text
<readout_path>: edge <edge> given for <electrode>, whose pulse is <pulse_edge>: its pulses are not seen as the readout makes them
```

This indicates that the chosen direction is opposite to the pulse polarity actually produced by the readout chain. Unless performing an intentional reversed-polarity check, remove `--edge` (or delete `edge` from the configuration), or change it to match `pulse_edge`.

## Rules

### Built-in Constants

The constants below are hardcoded in module source code:

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `MILLIVOLT` | `1.0e-3` | $\text{V/mV}$ (commented as `V` in code) | `src/raser/stages/reconstruction.py`: multiplier converting `threshold` and `amplitude_threshold` from $\text{mV}$ to $\text{V}$ |
| `BASELINE_POINTS` | `200` | samples | `src/raser/core/reconstruction/event.py`: number of samples at the start of each waveform used to compute baseline mean and noise standard deviation |
| `EDGE_SIGN` | `{"rising": 1.0, "falling": -1.0}` | None | `src/raser/core/reconstruction/event_table.py`: polarity multiplier flipping the net waveform into a positive pulse according to the chosen edge |

### Parsing and Launching Stage Commands (`stage_commands.run`)

1. **Mount arguments (`register`)**: Register `reconstruction` (alias `reco`), sequentially mount the options of all upstream stages, this stage, and shared run parameters, and bind the execution entry point to `partial(run, "reconstruction")`.
2. **Resolve experiment**: Read `config.json` in the experiment folder to identify its experiment class.
3. **Validate stage**: If the experiment class does not include the `reconstruction` stage, exit with:

   ```text
   <folder>: the experiment <workflow> has no reconstruction slice; its slices: <names>
   ```

   Use a stage command supported by that experiment, or switch to an experiment that includes reconstruction.
4. **Launch**: Set the cutoff stage to `reconstruction`, enter the project context of the experiment, change into the experiment folder to run, and restore the original directory afterward. When the experiment folder contains `config.json`, the target argument on the command line is rewritten to an absolute path so that cluster jobs rerunning the original command from the experiment folder can locate it.

### Single-Job Reconstruction (`reconstruction.run` and `reconstruct`)

1. **Multi-position pre-check**: When a position is given and that position has no input waveform in the current job, return `{"events": 0}` immediately.
2. **Invoke reconstruction**: `reconstruct(input_waveforms, output_event_table, float(threshold), float(amplitude_threshold), tuple(float(part) for part in fractions), edge)`.
3. **Read and validate waveforms (`read_waveforms`)**:
   - `_check_layout` verifies that all datasets `("event", "t0", "count", "stored", "index", "voltage")` are present and `voltage` is 1D; otherwise it raises:

     ```text
     ValueError: <path> is a readout file of an older layout (no <missing>): run the readout again
     ```

   - If the file attributes lack `pulse_edge`, it raises:

     ```text
     ValueError: <path> has no pulse_edge: the readout of this version did not write it; run the readout again
     ```

     Both indicate that the input was written by an older version; rerunning `readout` resolves them. After validation passes, voltage waveforms `voltage` (in $\text{V}$) of all stored electrodes per event are restored and returned as `Waveforms(electrodes, dt, events, pulse_edge)`.
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
   - If the input contains no events, raise `ValueError: the readout holds no event`; inspect the job's `current` and `readout` outputs and recompute upstream stages if needed.
   - Call `net_pulse(samples)` on every stored electrode waveform of every event. If the number of samples is `<= 200` (`BASELINE_POINTS`), raise `ValueError: <count> samples, not more than the 200 of the baseline`; check whether the simulation time window or sampling step `dt` is too short. When the sample count exceeds `200`, subtract the mean of the first `200` samples as `baseline` ($\text{V}$), compute the population standard deviation of the first `200` samples as `noise` ($\text{V}$), multiply by `EDGE_SIGN[edge]` to flip positive, and compute single-electrode features and cross-electrode clusters via `electrode_row` and `cluster`, assembling an `EventTable`.
6. **Write output (`write_event_table(path, table)`)**: Write the `EventTable` to the event table file in one pass.

## Software Implementation

### Source File Responsibilities

- `src/raser/stages/reconstruction.py`: Defines `MILLIVOLT`, single-job reconstruction function `reconstruct`, and stage entry point `run`; handles unit conversion, printing reversed-edge notices, and invoking core reconstruction functions.
- `src/raser/stages/chain.py`: Defines default parameters `RECONSTRUCTION_DEFAULTS`, argument registration function `reconstruction_arguments` (`-threshold`, `-amplitude_threshold`, `--edge`), and lazy-import entry point `_reconstruction` for the `reconstruction` module.
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

Only the options and keys listed below are configurable in this stage; the baseline sample count `200`, millivolt-to-volt conversion factor `1.0e-3` $\text{V/mV}$, and edge polarity multipliers are hardcoded. Settings are stored in the `reconstruction` section of `config.json`, and `--set` and `--scan` use `"section.key"` addresses, such as `--set reconstruction.threshold=15`.

| Option or key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `[path]` | Current folder | None | Experiment folder |
| `-threshold` (`reconstruction.threshold`) | `10.0` | $\text{mV}$ | Pulse over-threshold value (multiplied by `1e-3` inside the stage to convert to $\text{V}$); used to determine per-electrode `above`, compute `ToA`, `ToT`, `CoG`, and `area`, and include immediately adjacent electrodes around a seed in a cluster |
| `-amplitude_threshold` (`reconstruction.amplitude_threshold`) | `10.0` | $\text{mV}$ | Amplitude threshold for finding cluster seeds (multiplied by `1e-3` inside the stage to convert to $\text{V}$); electrodes with amplitude at or above it become seeds, and events with a seed are marked `selected = True` |
| `--edge` (`reconstruction.edge`) | `None` | None | Pulse edge direction on which thresholds act: `"rising"` (positive pulse), `"falling"` (negative pulse), or `None` (each electrode inherits `pulse_edge` written by `readout`) |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | None | Constant fraction discrimination (`CFD`) amplitude ratios, each strictly in $(0, 1)$; written in the `reconstruction` section of `config.json` |

Because the list value of `fractions` contains square brackets and commas, passing it on the command line via `--set` or `--scan` raises an error:

```text
ValueError: fractions = <value>: the folder of this value would be named <name>, which holds more than letters, digits and ._+-; scan or set a number or a short name, and give an expression such as a doping profile a parameter with a name in its file
```

Edit `fractions` directly in the `reconstruction` section of `config.json` instead.

`raser reconstruction` also mounts options of upstream stages for creating new experiments or filling in missing upstream stages: `deposit` options (`source`, `--g4setup`, `-evt`, `-gen`, `--generated-limit`, `--edep-min`, `--edep-max`, `deposit.plots`, `current.plots`, `-g4_vis`, `--g4-vis-driver`) are documented in [Energy Deposition Stage (`stages/deposit`)](deposit.md), `-vol`/`--voltage` and `-irr`/`--irradiation` in [Field Solving Stage (`stages/field`)](field.md) and [Carrier Transport and Induced Current Stage (`stages/current`)](current.md), and `-amp`/`--amplifier` and `--sheet-resistance` in [Electronics Readout Stage (`stages/readout`)](readout.md). Shared run parameters (`-s`, `--seed`, `--same-seeds`, `--set`, `--scan`, `-b`, `-t`, `--dry-run`) are documented in [Command-Line Interface (`raser`)](../cli.md) and [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md).

### Files Read and Written

- **Read: output of `trigger`**. Digital waveforms of recorded events, carrying file attributes `electrodes` (`string[]`, dimensionless), `dt` (`float64`, in $\text{s}$), and `pulse_edge` (`string[]`, `"rising"` or `"falling"`), and datasets `event` (`(events,)`, `int64`), `t0` (`(events,)`, `float64`, in $\text{s}$), `count` (`(events,)`, `int64`, in bins), `stored` (`(events,)`, `int64`, in electrodes), `index` (`(sum(stored),)`, `int64`), and `voltage` (`(sum(stored * count),)`, `float64`, in $\text{V}$). See [Electronics Readout (`core/readout`)](../core/readout.md) for the waveform format.
- **Write: event table in `nodes/reconstruction/<node_id>/`**. Written when upstream stages have recorded events and (in multi-position experiments) the position has input waveforms. The HDF5 file contains 5 attributes (`electrodes` [`string[]`, dimensionless], `threshold` [`float64`, in $\text{V}$], `amplitude_threshold` [`float64`, in $\text{V}$], `fractions` [`float64[]`, shape `(fractions,)`, dimensionless], `edge` [`string[]`, `"rising"` or `"falling"`]), 4 1D datasets of shape `(events,)` (`event` [`int64`], `selected` [`bool`], `cluster_size` [`int64`, in electrodes], `cluster_center` [`float64`, in 0-based electrode index]), 9 2D datasets of shape `(events, electrodes)` (`traced` [`bool`], `baseline` [`float64`, in $\text{V}$], `noise` [`float64`, in $\text{V}$], `amplitude` [`float64`, in $\text{V}$], `above` [`bool`], `ToA` [`float64`, in $\text{s}$], `ToT` [`float64`, in $\text{s}$], `CoG` [`float64`, in $\text{s}$], `area` [`float64`, in $\text{V}\cdot\text{s}$]), and 1 3D dataset `CFD` of shape `(events, electrodes, fractions)` (`float64`, in $\text{s}$). See [Event Reconstruction (`core/reconstruction`)](../core/reconstruction.md) for definitions of all attributes and datasets.
- **Write: `nodes/reconstruction/<node_id>/node.json`**. Records this node's inputs along with the code version, runtime environment, and run status.
- **Write: `points.json` and `points/<point>/reconstruction`**. The parameter table records the `reconstruction` node ID used by each point; the view symlink points to that node.
