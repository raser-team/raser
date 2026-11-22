# Carrier Transport and Induced Current Stage (`stages/current`)

`src/raser/stages/current.py` is the 3rd stage, `current`, of the eight-stage simulation chain. It consumes the electron-hole pair depositions from the [Energy Deposition Stage (`stages/deposit`)](deposit.md) node and the field nodes solved under `<device_project>/field/<node_id>/` by the [Field Solving Stage (`stages/field`)](field.md). Using the device file, this stage constructs the device model and interpolated field, calls [Carrier Drift and Induced Current (`core/current`)](../core/current.md) to drift electron-hole pairs in the electric field and weighting field, writes the time-domain induced currents on each readout electrode into its own node `nodes/current/<node_id>/`, and draws drift-path and current plots for the first `plots` events of each job. The induced currents are passed downstream to the [Electronics Readout Stage (`stages/readout`)](readout.md); net induced charge `charge` and initial pair count `pairs` are passed to the [Statistical Analysis Stage (`stages/analysis`)](analysis.md) to compute charge collection efficiency.

## Behavior

### Running Up to the Induced Current Stage with Automatic Upstream Completion

`raser current` (short alias `raser cur`) runs up through `current` on the experiment in the current folder or at the given path, computing missing `field` and `deposit` nodes first:

```bash
raser current [path]
raser cur [path]
```

The `current` stage of `tct` additionally convolves the standard drift result with the laser temporal pulse (see [Transient Current Technique Test (`bench/tct`)](../bench/tct.md)); this page documents the standard simulation chain's `current` stage.

For example, scanning $100\ \text{V}$ and $200\ \text{V}$ bias on the `HPK-Si-PiN` example, with $2$ jobs per scan point and $200$ recorded events per job, stopping at the induced current stage:

```bash
raser current examples/HPK-Si-PiN/signal --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

The program first checks that field nodes for both biases exist in `examples/HPK-Si-PiN/field/` and solves any missing ones before jobs start, storing them in `examples/HPK-Si-PiN/field/`; it then computes `deposit` and `current` nodes for the two scan points `voltage_100` and `voltage_200`, with `points/voltage_100/current/<job>` and `points/voltage_200/current/<job>` pointing to each job's `current` node. Changing the bias voltage constitutes a separate measurement, so the two bias points are measured independently with $2$ jobs per point, giving $4$ nodes each for `deposit` and `current` ($2$ per point). Running the full `raser signal` afterward leaves these node fingerprints unchanged, reusing them directly and computing only `readout` and subsequent stages.

### Locating the Field Node and Constructing the Interpolated Field

Required fields are solved before jobs start and stored in the device project's `field/`. If the field is not ready when a job starts, the job raises:

```text
FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>`
```

This usually occurs after bypassing the main command's automatic field solve or modifying a field node midway. Follow the message by running `raser field` to solve the field for the required bias voltage and irradiation fluence, then rerun this command.

Next, this stage resolves the run's irradiation fluence (using `field.irradiation_flux` when it is not `null`, otherwise `irradiation_flux` from the device file, or $0\ \text{cm}^{-2}$ if the device file has no irradiation block) and bias voltage (in $\text{V}$), and calls `solved_field` to locate the solved device field whose irradiation fluence, solve mode, and device parameters all match and which has both potential and weighting field solved at that bias, constructing `DevsimField` from [Field Solving and Loading (`core/field`)](../core/field.md) to provide interpolated electric field, conductive-region flags, trapping rates, weighting potential, and the 1D planar gain interface for drift calculation. If no matching field is found, it raises an error specifying the missing item:

```text
FileNotFoundError: no <mode> field of <det_name> at the irradiation flux <flux> in <root> (flux and mode of those solved: <have>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode> --set field.irradiation_flux=<flux>`
ValueError: the field in <folder> was solved for another device (<differing>); solve it again with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
FileNotFoundError: the field in <folder> is not solved at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
FileNotFoundError: the field in <folder> has no weighting field at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>` with the weighting field switched on in the field settings
```

The four messages indicate, respectively: no field at that irradiation fluence and mode; the field was solved for device parameters prior to a change; missing electric potential at the target bias; missing weighting field at the target bias. Run the `raser field` command shown at the end of the error message and then rerun; when the weighting field is missing, enable weighting-field solving in the `field` section (modify field settings with `--set field.<key>=<value>`).

### Zero-Deposit Events and Multi-Position Filtering by Detector

When upstream `deposit` records $0$ valid events in a job, `current` skips that job accordingly.

Multi-position experiments (such as the 24 pads in `cflm`) compute induced currents per position. When a position has no deposit step with `detector` equal to that position in the current job, that position directly records $0$ events while other positions in the same job run normally.

If a deposit file is not marked as having ended early yet contains no recorded events (for example, after manual editing), or has no deposit steps left after filtering by `detector`, the calculation entry point raises:

```text
ValueError: <deposits_path> holds no event: there is no current to write
ValueError: <deposits_path> holds no deposit in the detector <detector>: there is no current to write
```

This indicates that the input deposit file is empty or corrupted. Delete that `deposit` node and rerun.

### Event-by-Event Drift, Writing Induced Currents, and Single-Event Plotting

When deposit events exist, this stage constructs `Detector` from [Device Model (`core/device`)](../core/device.md) using the device file, removes any existing current file of the same name, and filters deposit steps per event within the device boundaries and the projection of the electrode array (in multi-position runs, keeping only steps whose `detector` equals that position and writing rows only for events with deposits at that position). It advances carrier drift, thermal diffusion, irradiation trapping decay, and optional avalanche multiplication in `DevsimField`, accumulates time-domain induced currents and net induced charge on each readout electrode via the Shockley-Ramo theorem, and appends them event by event to the current file. For the first `plots` events, the program clears and recreates the event's plotting subfolder and draws the drift-path plot, waveform plots for electrodes with nonzero current, and (for strip or pixel devices) the electrode collected-charge plot. Plots are stored inside this stage's own output.

After all events are written, the job log summarizes cluster and carrier counts by stop reason; if any cluster stopped in a zero-field region (`"no_field"`), a warning is logged:

```text
<clusters> clusters (<carriers> carriers) stopped where the field has no value, the first in event <event> at x, y, z = <x>, <y>, <z> um: what they would have induced further on is missing
```

This indicates that drift trajectories reached coordinates outside the field mesh, so subsequent induced current is missing. Verify that the device dimensions match the field mesh extent.

Taking job `0`'s `current.h5` at the $200\ \text{V}$ point in the example above: `current` reads `deposit.h5` ($200$ events) from the `deposit` node together with the $200\ \text{V}$ electric field and `top` electrode weighting field from the field node, writes `current.h5`, and draws `drift_path_<event>` and `current_<event>` under `plots/` inside the node for each of the first $100$ recorded events (each as `.png`, `.pdf`, `.root`; `HPK-Si-PiN` is a single-electrode `pad` device; `charge_per_electrode_<event>` is drawn only for strip or pixel devices). The file attributes (`attrs`) are `dt = 5e-12` (default time-bin width for 1D devices, in $\text{s}$) and `electrodes = ['top']` (list of readout electrode names), and the datasets (`datasets`) are:

| Dataset name | Example shape | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | None | Geant4 event ID of each recorded event |
| `t0` | `(200,)` | `float64` | $\text{s}$ | Left edge time of the first time bin |
| `count` | `(200,)` | `int64` | bins | Number of time bins for each event |
| `pairs` | `(200,)` | `float64` | pairs | Total input electron-hole pairs before multiplication |
| `sensitive_pairs` | `(200,)` | `float64` | pairs | Pairs generated inside the device in the non-conductive region above the electrode array that actually participate in drift |
| `carriers_without_field` | `(200,)` | `float64` | carriers | Total untrapped carriers that stopped upon encountering a zero-field region (`"no_field"`) |
| `charge` | `(200, 1)` | `float64` | $\text{C}$ | Signed net induced charge per electrode |
| `stored` | `(200,)` | `int64` | electrodes | Number of electrodes with nonzero current stored in each event |
| `index` | `(196,)` | `int64` | None | Indices of stored electrodes in `electrodes` ($196$ of the $200$ events produced nonzero current) |
| `current` | `(245196,)` | `float64` | $\text{A}$ | 1D average induced current concatenated across time bins for all stored electrodes |

`index` has length `196`, meaning $196$ of the $200$ recorded events wrote induced current into `current`, while the remaining $4$ were zero across all time bins. Downstream readers slice `index` and `current` using `stored` and `count`, reconstructing unstored electrodes as zero.

![HPK-Si-PiN single-event carrier drift path](../images/current-drift-path-HPK-Si-PiN.png)

Single-event carrier drift path plot for `HPK-Si-PiN`: top shows 3D trajectories inside the device bulk; bottom shows deposit points, electron trajectories, and hole trajectories in the $x$-$z$ plane (coordinates in $\mu\text{m}$).

![HPK-Si-PiN single-event induced current](../images/current-event-HPK-Si-PiN.png)

Single-event induced current on the `top` electrode of `HPK-Si-PiN`, showing the electron component, hole component, and total induced current versus time (horizontal axis in $\text{s}$, vertical axis in $\text{A}$).

### Reuse and Recomputation

`current` is a measurement stage; its fingerprint includes the setting values used by this stage, the part of the device file it uses, the upstream `deposit` and field node IDs, and the seed (derived from the job seed; see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md#seeds)). Matching fingerprints are reused regardless of which point or run produced them; changing bias voltage, fluence, or `current.plots` computes a new node while keeping the old node, and reverting the setting points the view back to the old node. When the code version differs from the one recorded in the node, only a notice is printed and the result is still reused. Each node is locked individually; a partially written node carries the `.part` suffix and is renamed to its final name only after writing finishes. See [Slices and Reruns](../lifecycle/slices.md) for node and reuse rules.

## Rules

### Built-in Constants

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `STAGES["current"]` | `("cur", "the induced currents, after the deposits and the field", ...)` | None | `src/raser/stages/stage_commands.py`: short alias and help string for `raser current` |

### Parsing and Launching Stage Commands (`stage_commands.run`)

1. **Mount arguments (`register`)**: Register `current` (alias `cur`), mount shared run parameters and this stage's command options (settings for upstream stages live in their respective sections; see [Field Solving Stage (`stages/field`)](field.md) and [Energy Deposition Stage (`stages/deposit`)](deposit.md)), and bind the execution entry point to `partial(run, "current")`.
2. **Resolve experiment**: Read `config.json` in the experiment folder to identify its experiment class.
3. **Validate stage**: If the experiment class does not include the `current` stage, exit with:

   ```text
   <folder>: the experiment <workflow> has no current slice; its slices: <names>
   ```

4. **Launch**: Set the cutoff stage to `current`, enter the project context of the experiment, change into the experiment folder to run, and restore the original directory afterward. When the experiment folder contains `config.json`, the target argument on the command line is rewritten to an absolute path so that cluster jobs rerunning the original command from the experiment folder can locate it.

### Field Lookup and Interpolated Field Construction (`current.solved` and `solved_field`)

1. **Irradiation fluence**: Take `my_d.irradiation_flux` (in $\text{cm}^{-2}$); when `field.irradiation_flux` is not `null`, use `float(irradiation_flux)` instead.
2. **Locate and validate field (`solved_field(my_d, my_d.voltage, flux, mode)`, with `mode` taken from `field.mode`)**:
   - Filter the device's solved fields to those with irradiation fluence equal to `flux` and solve mode equal to `mode`; if none exist, raise `FileNotFoundError` for missing fluence and mode.
   - Compare the device parameters read at solve time against the current `my_d` using `changed`, preferring a field with no differences; if all differ, take the first and raise `ValueError: the field in <folder> was solved for another device ...`.
   - If `float(my_d.voltage)` (in $\text{V}$) is not in the biases with solved potential, raise `FileNotFoundError` for missing potential; if it is not in the biases with solved weighting field, raise `FileNotFoundError` for missing weighting field. Once all checks pass, return that field folder.
3. **Construct interpolated field**: Return `devfield.DevsimField(my_d.device, my_d.voltage, my_d.read_out_contact, irradiation_flux=flux, bounds=my_d.bound, field_directory=folder, interpolation_bins=my_d.device_dict.get("field_interpolation_bins"))`.

### Induced Current Calculation (`current.currents`)

1. **Multi-position pre-check**: When a position is given, read the job's deposits; if no deposit step has `detector` containing that position, return `{"events": 0}` immediately.
2. **Construct device**: `my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])`.
3. **Write induced currents (`write_induced_currents`)**:
   - Read the deposits; if there are no events, raise `ValueError(f"{deposits_path} holds no event: there is no current to write")`.
   - When `detector=position` is given, use `deposits_in(record, detector)` to retain only deposit steps whose `record.detector` equals that position and drop events with no remaining steps; if empty after filtering, raise `ValueError(f"{deposits_path} holds no deposit in the detector {detector}: there is no current to write")`.
   - Remove the current file if it already exists, then construct `CalCurrent(my_d, my_f, record.pairs, positions, keep_drift_paths=(count < plots))` event by event and append with `append_currents`; when `plots > 0`, first remove the figures an earlier run left in `plot_path` whose names start with `current_`, `drift_path_`, or `charge_per_electrode_`; when `count < plots`, draw trajectory plots, waveform plots, and (when `my_d.is_strip` or `my_d.is_pixel` is true) the charge-per-electrode plot.
   - After all events finish, call `log_ends(ends, without_field)` to summarize stop reasons.

## Software Implementation

### Source File Responsibilities

- `src/raser/stages/current.py`: `solved(my_d, kwargs)` resolves the run irradiation fluence and calls `solved_field` to construct `DevsimField`; `currents(kwargs, position=None)` performs the multi-position pre-check, constructs `Detector`, assembles output and plot paths, and calls `write_induced_currents`.
- `src/raser/stages/chain.py`: Defines the lazy-import entry point `_currents` for the `current` module and `_field` for verifying field readiness at job startup.
- `src/raser/stages/stage_commands.py`: Registers stage commands; resolves the target experiment, verifies it includes the target stage, sets the cutoff stage, and switches into the experiment folder to run.
- `src/raser/stages/files.py`: Provides the output file paths for this stage in the current job.

### Core Data Structures

`currents(kwargs, position=None)` and `solved(my_d, kwargs)` read the following from the run dictionary `kwargs`:

| `kwargs` key | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `"det_name"` | `str` | None | Current device name |
| `"_files"` | `dict` | None | Component file contents; `kwargs["_files"]["device"]` is the device JSON dictionary already updated with the run's bias voltage (in $\text{V}$) |
| `"irradiation_flux"` | `float \| None` | $\text{cm}^{-2}$ | Run irradiation fluence ($1\ \text{MeV}$ neutron-equivalent fluence); when `None`, `solved` falls back to `my_d.irradiation_flux` |
| `"plots"` | `int` | events | Maximum number of events per job for which single-event drift-path and current plots are drawn |

## Interface

### Options and Configuration Keys

Only the options and keys listed below are configurable in this stage; the cutoff stage, thermal diffusion switch `diffusion=True` passed to `CalCurrent`, and plot filenames are hardcoded. `--set` and `--scan` use `"section.key"` addresses, such as `--set field.voltage=100`. Shared run parameters (`-s`, `--seed`, `--same-seeds`, `--set`, `--scan`, `-b`, `-t`, `-mem`, `--dry-run`) are documented in [Command-Line Interface (`raser`)](../cli.md) and [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md); settings for upstream stages live in their respective sections, see [Field Solving Stage (`stages/field`)](field.md) and [Energy Deposition Stage (`stages/deposit`)](deposit.md); device geometry, electrodes, temperature, material, doping, irradiation model, and avalanche multiplication keys are documented in [Carrier Drift and Induced Current (`core/current`)](../core/current.md). For configuration keys, "Value in example" shows the value written in `examples/HPK-Si-PiN/signal/config.json`, with different values from other examples in parentheses; if `config.json` is missing a key that is needed, an error is raised naming the missing `section.key`.

| Section.Key or CLI option | Value in example | Unit | Meaning |
| --- | --- | --- | --- |
| `[path]` | Current folder | None | Experiment folder |
| `current.plots` | `100` (`0` in the `timeres`, `bmos`, and `cflm` examples) | events | Maximum number of events per job for which `current` draws its own plots: drift paths, electrode currents, and (for strip/pixel devices) collected-charge plots ($\le 0$ disables plotting); drift paths are drawn from the deposit list provided by `deposit`. In multi-position experiments, each position counts from its own events with deposits; changing it triggers recomputation of `current` and downstream stages |
| `field.voltage` | `200.0` (uses bias voltage from the device file when `null`) | $\text{V}$ | Device bias voltage, belonging to the `field` section; determines which bias field is used, and changing it triggers recomputation of `field`, `current`, and downstream stages |
| `field.irradiation_flux` | `null` (uses irradiation fluence from the device file, or `0` if the device file has no irradiation block) | $\text{cm}^{-2}$ | Device irradiation fluence ($1\ \text{MeV}$ neutron-equivalent fluence), belonging to the `field` section; determines which fluence field is used, and changing it triggers recomputation of `field`, `current`, and downstream stages |
| Device file key `field_interpolation_bins` | Omitted (`DevsimField` uses `{"x": 30, "y": 30, "z": 30}`) | bins | Number of bins along each axis of the 3D unstructured inverse-distance-weighted field interpolation grid when constructing `DevsimField` |

### Files Read and Written

- **Read: `deposit.h5` in the `deposit` node**. `current` reads each recorded event's Geant4 ID `event`, deposit-step logical volume name `detector`, local coordinates `x`/`y`/`z` ($\mu\text{m}$), global time `t` ($\text{s}$), and number of electron-hole pairs `pairs` (pairs); see [Energy Deposition Stage (`stages/deposit`)](deposit.md) for the format.
- **Read: field node in `<device_project>/field/<node_id>/`**. Written by `raser field`. `DevsimField` reads `Potential_<V>V.pkl`, `Conductive_<V>V.pkl`, `NetDoping_0V.pkl` (`NetDoping_<V>V.pkl` for TCAD imports), `TrappingRate_n_<V>V.pkl`, `TrappingRate_p_<V>V.pkl`, and `weightingfield/<electrode>/Potential_<V>V.pkl`; see [Field Solving and Loading (`core/field`)](../core/field.md) for data structures and units.
- **Write: `nodes/current/<node_id>/current.h5`** (in multi-position experiments, one file `current.<position>.h5` per position inside the same node). Written when upstream `deposit` has recorded events and (in multi-position experiments) the position has deposit steps in this job; any old file is removed before recomputing and events are appended one by one. Passed to `readout` for output waveforms, while `charge` ($\text{C}$) and `pairs` (pairs) are also passed to `analysis` for charge collection efficiency; see [Carrier Drift and Induced Current (`core/current`)](../core/current.md) for HDF5 attributes (`electrodes`, `dt` [$\text{s}$]) and the shapes, types, and units of all datasets.
- **Write: single-event plots in `nodes/current/<node_id>/plots/`**. Written for the first `plots` events when `plots > 0` (removing the figures of the same kind an earlier run left in this folder beforehand), each as `.png`, `.pdf`, `.root`: 3D and $x$-$z$ plane drift-path plot `drift_path_<event>` (coordinates in $\mu\text{m}$), current-component waveform plot `current_<event>` (with several readout electrodes, one `current_<event>_electrode_<k>` for each electrode with nonzero current, `<k>` starting from `1`; horizontal axis `Time [ns]`, vertical axis `Current [μA]`), and charge-per-electrode plot `charge_per_electrode_<event>` for `strip` or `pixel` devices (values are the net charge of each electrode, in $\text{fC}$); see [Carrier Drift and Induced Current (`core/current`)](../core/current.md) for contents and axis units.
- **Write: `nodes/current/<node_id>/node.json`**. Records this node's inputs along with the code version, runtime environment, and run status.
- **Write: `points.json` and `points/<point>/current/<job>`**. The parameter table records the `current` node ID used by each point; the view symlink points to `../../../nodes/current/<node_id>`.
