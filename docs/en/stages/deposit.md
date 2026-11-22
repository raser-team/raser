# Energy Deposition Stage (`stages/deposit`)

`src/raser/stages/deposit.py` is dispatched by `raser deposit` (short alias `raser dep`) of [Simulation Chain and Stage Entry Points (`stages`)](README.md) or by benchmark and application experiment commands, standing at the front of the eight-stage simulation chain alongside the shared [Field Solving Stage (`stages/field`)](field.md). This stage reads the `deposit` section of `config.json`, the device definition `files["device"]` from [Detector Components (`components/device`)](../components/device.md), and the Geant4 setup script `files["g4setup"]` and the particle source or beam configuration `files["source"]` named by the setup's `source` block from [Energy Deposition Components (`components/deposit`)](../components/deposit.md). It invokes [Device Model (`core/device`)](../core/device.md) to construct a `Detector` instance, then calls [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md) to simulate particle energy deposit steps inside the detector and convert deposited energy into electron-hole pairs, writing `deposit.h5` and `node.json` under the node directory `nodes/deposit/<node_id>/` (and optionally drawing the Geant4 geometry and track plot `g4_geometry.png` inside the node or opening an interactive window to inspect the setup), with the view symlink `points/<point>/deposit/<job>` pointing to that node. The written deposit-step coordinates, times, energies, and electron-hole pair counts are passed downstream to the [Carrier Transport and Induced Current Stage (`stages/current`)](current.md) for carrier drift, while each event's earliest deposit time (`truth`) is passed to the [Statistical Analysis Stage (`stages/analysis`)](analysis.md) for time-resolution computation.

## Behavior

### Running the Deposit Stage Standalone and Node Reuse

`raser deposit` (or `raser dep`) runs up through the `deposit` stage on the experiment in the current folder or at the given path. The command syntax is:

```bash
raser deposit [path] [<source>]
raser dep [path] [<source>]
```

`<source>` is shorthand for `--set deposit.g4setup.source=<source>`. Omitting the path operates on the current experiment folder; passing a relative or absolute path targets an experiment folder containing `config.json`. In standard mode, the `deposit` stage computes a fingerprint as `<node_id>` from the setting values used by this stage, the parts of the component files it uses, and the random seed (derived from the job seed; see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md#seeds)), then runs particle transport and ionization conversion using that seed; each node is locked individually, carries the `.part` suffix while partially written, and is renamed upon completion to the final node directory `nodes/deposit/<node_id>/` containing `deposit.h5` and `node.json` (which records the inputs, code version, runtime environment, and run status). When `deposit.plots` is greater than `0` and a Geant4 source (`"beam"` or `"decay_source"`) is used, the same Geant4 run uses the offscreen driver `TSG_OFFSCREEN` to render the device, surrounding setup, and tracks of the first `deposit.plots` recorded events into `g4_geometry.png` under that node's output directory. The program also updates the parameter table `points.json` at the experiment root and points the view symlink `points/<point>/deposit/<job>` to `../../../nodes/deposit/<node_id>`. In subsequent full-chain or downstream stage runs across any scan point or invocation, any `deposit` node with an identical input fingerprint is reused; reverting settings points the view back to the old node; if the code version differs from the one recorded in `node.json`, only a notice is printed and existing results are still reused. See [Slices and Reruns](../lifecycle/slices.md) for node and reuse rules.

For example, running `2` energy-deposition jobs for the `signal` experiment on device `HPK-Si-PiN`, recording `200` valid events per job:

```bash
raser deposit examples/HPK-Si-PiN/signal -s 2 --set deposit.events_per_job=200 --seed 1
```

This command targets the experiment folder `examples/HPK-Si-PiN/signal`, runs only through the `deposit` stage, writes `deposit.h5`, `node.json`, and `g4_geometry.png` under `examples/HPK-Si-PiN/signal/nodes/deposit/<node_id>/`, updates `examples/HPK-Si-PiN/signal/points.json`, and creates the `points/<point>/deposit/<job>` symlink.

When running a full-chain bias scan command:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

When `HPK-Si-PiN` is not present under `work/`, the command runs in place under `examples/HPK-Si-PiN/`. The `deposit` stage uses the example's `decay/Sr90` radioactive source, `device_alone` setup, and `fano = true` to collect valid events for both the `100 V` (view `points/voltage_100/deposit`) and `200 V` (view `points/voltage_200/deposit`) scan points and write them into their respective `deposit` nodes. Taking `deposit.h5` written by a single job collecting `200` valid events as an example, the file attributes (`attrs`) are `generated_events` (number of decays launched from the `Sr90` collimator emission distribution, in events), `recorded_events = 200` (valid recorded events with nonzero deposition in the device, in events), `emission_probability` (probability $\varepsilon$ per decay of exiting the `Sr90` collimator exit plane given by its emission distribution, or `1.0` for sources without an emission distribution, dimensionless), and `require = "any"` (slot logical expression; per-slot energy-window attributes `edep_min.<slot>`, `edep_max.<slot>` and timing-window attribute `coincidence_window_ns` are written only when the corresponding values are set), and the dataset (`datasets`) structure and example shapes are:

| Dataset name | Example shape | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | None | Geant4 event ID of each recorded event |
| `count` | `(200,)` | `int64` | steps | Number of deposit steps contained in each recorded event |
| `detector` | `(5476,)` | `object` (variable-length string) | None | Logical volume name of the detector containing the deposit step |
| `x`, `y`, `z` | `(5476,)` | `float64` | `μm` | Local coordinates of the deposit-step midpoint (step start coordinates under `cflm`) |
| `x_start`, `y_start`, `z_start` | `(5476,)` | `float64` | `μm` | Local coordinates of the deposit-step start (optional columns) |
| `t` | `(5476,)` | `float64` | `s` | Global time of the deposit step |
| `e` | `(5476,)` | `float64` | `MeV` | Deposited energy |
| `pairs` | `(5476,)` | `float64` | pairs | Converted number of electron-hole pairs |

Here `5476` is the sum of `count` across the `200` recorded events; `x`, `y`, `z`, etc. are stored flattened across deposit steps, and the `current` stage slices them back into per-event deposit-step lists using `count` and passes `pairs` to the carrier drift calculation.

### Running by Recorded or Generated Events and Early Exit on Zero Events

A single job chooses exclusively between `deposit.events_per_job` and `deposit.generated_per_job`. With `deposit.events_per_job`, the particle source keeps generating events until the number of recorded events satisfying the recording condition (total deposited energy inside each slot's active layer is nonzero and falls within its energy window, and passes `deposit.require` and `deposit.coincidence_window_ns`) reaches the target count (generating at most `deposit.generated_limit` source events). With `deposit.generated_per_job`, the particle source generates the fixed number of source events and stops; the actual number of valid recorded events may be lower than that count, or even `0`.

When a single job records `0` valid events (for instance, generating a small number of events with `deposit.generated_per_job` where none hit the device or fall within the energy window), the `deposit` stage still writes `deposit.h5` recording `generated_events` inside the node, and then raises `Ended` to terminate the job early. The lifecycle catches this exception, records the early-exit state, and skips all downstream stages for that job.

### Geant4 Setup and Track Visualization (`-g4_vis`)

Enabling `-g4_vis` on the command line puts the job into Geant4 visualization mode. The program uses the value of `deposit.events_per_job` or `deposit.generated_per_job` as the number of generated events, opens an interactive window or exports the setup and tracks as a PNG image according to `--g4-vis-driver`, and immediately exits via `SystemExit` once the window closes or the image is exported.

To inspect the Geant4 setup and tracks on a headless terminal, use the short alias `raser dep` with the offscreen driver:

```bash
raser dep examples/HPK-Si-PiN/signal --set deposit.events_per_job=5 -g4_vis --g4-vis-driver TSG_OFFSCREEN
```

This generates `5` events, exports the geometry and tracks to `g4_geometry.png` in the current run directory, and exits; on a local machine with a graphical display, omit `--g4-vis-driver TSG_OFFSCREEN` to open an interactively rotatable Qt window using the default `TSG_QT_GLES`.

## Rules

### Built-in Constants and Chain Configuration Constants

The table below lists all built-in constants and module-level configuration constants related to the `deposit` stage in `src/raser/stages/deposit.py`, `src/raser/stages/chain.py`, and `src/raser/stages/stage_commands.py`:

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `DEPOSIT_KEYS` | `("g4setup", "events_per_job", "generated_per_job", "generated_limit", "edep_min", "edep_max", "require", "coincidence_window_ns", "fano", "plots")` | None | `stages/chain.py`; tuple of setting keys belonging to the `deposit` stage for computing node fingerprints (plus per-slot overrides `<slot>.edep_min` and `<slot>.edep_max`) |
| `COMPONENTS` | `{"g4setup": "deposit"}` | None | `stages/chain.py`; mapping from setting keys loaded by `deposit` in the standard simulation chain to their component directory (`components/deposit/`) |
| `READERS` | `{"g4setup": read_g4setup}` | None | `stages/chain.py`; mapping of custom readers for non-JSON component kinds |
| `STAGES["deposit"]` | `("dep", "the energy deposited by the source", (chain.deposit_arguments,))` | None | `stages/stage_commands.py`; short alias, help text, and tuple of CLI option-mounting functions for the `raser deposit` subcommand |

### Stage Command Target Resolution and Dispatch (`stage_commands.py`)

When running `raser deposit [path]` (or `raser dep [path]`), `stage_commands.run("deposit", kwargs)` proceeds through the following steps:

1. **Resolve target path (`_experiment(target)`)**:
   - Uses the current folder when no path is given; when `<target>` is supplied, sets `folder = Path(target).expanduser()` and `config = folder / "config.json"`.
   - If `config.is_file()` is true, reads the JSON as `record` and returns `(folder.resolve(), record["workflow"].split(), record.get("device"))`.
2. **Validate that the target experiment class includes the `deposit` stage**:
   - Looks up the experiment class corresponding to the target experiment (each benchmark or application is a Python class inheriting from the `raser` experiment base class that declares which stages it comprises) and collects its list of stage names `names`.
   - Checks whether `"deposit"` is in `{name.split(".")[0] for name in names}`. If not (i.e., the target experiment class does not include a `deposit` stage), raises `SystemExit`:
     ```text
     <folder>: the experiment <workflow> has no deposit slice; its slices: <names>
     ```
     Cause: that experiment does not include a `deposit` stage; use one of the stage names listed at the end of the message or run the original experiment command instead.
3. **Construct run options and expand cluster target path**:
   - Computes the project root `project = folder.parents[len(words) - 1]`.
   - Constructs `options = {**kwargs, "det_name": device, "until": "deposit", "_entry_command_prefix": (words[0],)}`.
   - If `(folder / "config.json").is_file()` is true, takes `argv = kwargs.get("_argv") or []`, replaces any token equal to `kwargs["target"]` with `str(folder)`, and stores it in `options["_argv"]`.
4. **Enter project context and experiment directory to run**:
   - Saves the current directory `here = os.getcwd()` and enters `project_root_context(project, kwargs["_components_of"][words[0]])`.
   - If `folder.is_dir()` is true, executes `os.chdir(folder)`; invokes `execute(workflow, options)` to launch the lifecycle, and restores the original working directory via `os.chdir(here)` in a `finally` block.

### Assembling the `deposit` Stage in the Simulation Chain and Helper Callbacks (`chain.py`)

1. **Integration into the eight-stage chain and execution entry point (`_deposits`)**:
   - The eight-stage simulation chain consists in order of `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, and `analysis`. `deposit` has no upstream stages, reads `DEPOSIT_KEYS` settings along with the `"g4setup"` component definition (`files["source"]` is read from the setup's `source` block, see the next step), and as a measurement stage includes its random seed in the node fingerprint.
   - The default execution callback `_deposits(kwargs)` executes `from . import deposit` at runtime and calls `deposit.deposits(kwargs)` (experiments with custom deposition such as `cflm` pass their own `deposit` function while keeping the stage name `"deposit"`).
2. **Loading the `g4setup` script snapshot (`read_g4setup(selector)`)**:
   - When preparing the `files["g4setup"]` component snapshot to record in node inputs, the main command invokes `READERS["g4setup"]` (i.e., `read_g4setup`).
   - If `selector` is an explicit path ending in `.json`, or if traversing `component_roots()` for `deposit/<selector>.py` encounters a `deposit/<selector>.json` file in the first matching root, raises `ValueError`:
     ```text
     ValueError: <stale>: a g4setup is a script now; write it as <name>.py with its keys in G4SETUP
     ```
     Cause: Geant4 setups have been migrated to Python scripts; rewrite it as a `.py` file exporting a `G4SETUP` dictionary and remove the `.json` file from the same directory.
   - Once validated, reads the `.py` file's byte stream, computes its SHA-256 hash, executes it in an isolated module namespace, and returns `{**module.G4SETUP, "file": str(selector), "sha256": module.SHA256}`.
3. **Reading the setup's source (`files["source"]`)**:
   - Takes `files["g4setup"]["source"]`: `name` points to the source component `deposit/<name>.json` (component lookup follows the same rules as other components); keys other than `name` and `angle` override same-named keys of the source component; `angle` stays in the setup and is used by `simulate_deposits`. The result is `files["source"]`, passed as the `source` argument of `simulate_deposits`.
   - `--set deposit.g4setup.source=<source component name>` replaces only `name`, and the setup's `angle` is kept; `--set deposit.g4setup.source.<key>=<value>` writes one overriding key.
4. **Forwarding per-job visualization arguments (`job_command(kwargs)`)**:
   - If `kwargs.get("g4_vis")` is true, returns `["-g4_vis", "--g4-vis-driver", kwargs["g4_vis_driver"]]` to append to single-job commands; otherwise returns `[]`.

### Single-Job `deposit` Stage Execution Flow (`deposit.py`)

Upon entering the `deposit` stage of a single job, the lifecycle has already written the measurement stage's random seed (in $[1, 2^{31}-1]$; when `--same-seeds` is enabled, jobs with the same index across scan points share the same random seed) into `kwargs["seed"]` (see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md) for sectioned configuration, scan expansion, and random seeding rules). Each node is locked individually, carries the `.part` suffix while partially written, and is renamed to `nodes/deposit/<node_id>/` only upon completion. `deposits(kwargs)` executes in the following strict order:

1. **Construct the device model and read event-count options**:
   - Reads `files = kwargs["_files"]` and constructs the device object with `my_d = bdv.Detector(kwargs["det_name"], files["device"])`.
   - Reads `events = kwargs.get("events_per_job")` and `generated = kwargs.get("generated_per_job")`.
2. **Validate mutual exclusion of recorded vs. generated event counts**:
   - If `(events is None) == (generated is None)` is true (both are `None` or both are non-`None`), immediately raises `ValueError`:
     ```text
     ValueError: events_per_job (<events>) and generated_per_job (<generated>): a job records a number of events or generates one, so exactly one of them is set
     ```
     Cause: a job may specify either a target recorded event count or a generated event count, not both or neither (for example, after manually editing the `deposit` section of `config.json`); set exactly one of them in the configuration or command.
   - Reads `limit = kwargs.get("generated_limit")`.
3. **Dispatch `-g4_vis` visualization mode**:
   - If `kwargs.get("g4_vis")` is true:
     - Takes `driver = kwargs["g4_vis_driver"]` and initializes `picture = None`.
     - If `driver.upper() in ("TSG", "TSG_FILE", "TSG_OFFSCREEN")`, sets `picture = os.path.join(kwargs["_run_path"], "g4_geometry")`.
     - Calls `view_geometry(my_d, files["source"], files.get("g4setup"), int(events if generated is None else generated), kwargs["seed"], driver, picture)`.
     - Immediately executes `raise SystemExit` once `view_geometry` returns, terminating the job process.
4. **Prepare track-plot path and event count for standard runs (`_picture(kwargs)`)**:
   - When `kwargs.get("g4_vis")` is false, calls `_picture(kwargs)`, which computes `drawn = int(kwargs.get("plots") or 0)`.
   - If `not drawn` (i.e., `drawn == 0`), returns `(None, 0)`.
   - If `drawn != 0`, prepares the image output path `g4_geometry` inside this stage's node output directory `nodes/deposit/<node_id>/` and returns that path together with `drawn`.
5. **Call `write_simulated_deposits` to simulate and persist**:
   - Calls `output(kwargs, "deposit")` to obtain the `deposit.h5` output path inside `nodes/deposit/<node_id>/`.
   - Constructs `windows` per slot (each slot defaults to `(deposit.edep_min, deposit.edep_max)`, with either bound overridden when `deposit.<slot>.edep_min` or `deposit.<slot>.edep_max` is given), and reads `require = kwargs["require"]` and `coincidence_window_ns = kwargs.get("coincidence_window_ns")`.
   - Calls `recorded = write_simulated_deposits(output(kwargs, "deposit"), devices, files["source"], files.get("g4setup"), None if events is None else int(events), kwargs["seed"], windows, require, coincidence_window_ns, kwargs["fano"], None if generated is None else int(generated), GENERATED_LIMIT if limit is None else int(limit), *_picture(kwargs), observers=..., primaries=...)` (`devices` is `{"Device": my_d}` for a single device; passed together with `observers` or `primaries` when defined on the experiment class).
   - According to `files["source"]["kind"]`, `write_simulated_deposits` runs Geant4 transport (`"beam"`, `"decay_source"`) or straight-line minimum-ionizing-particle calculation (`"toy_mip"`), filters valid events by `windows`, `require`, and `coincidence_window_ns`, converts energy to electron-hole pairs via `ionized_pairs`, writes results into `deposit.h5`, and returns the recorded event count `recorded`.
6. **Check recorded event count and finalize node persistence**:
   - If `not recorded` (i.e., `recorded == 0`), executes `raise Ended`. The lifecycle catches `Ended`, records the early-exit status, and skips all subsequent stages for this job.
   - If `recorded > 0`, `deposits(kwargs)` returns `None`; the lifecycle renames the finished `.part` node to the final node directory `nodes/deposit/<node_id>/` (containing `node.json`), and updates `points.json` and the view symlink `points/<point>/deposit/<job>`.

## Software Implementation

### Source File Responsibilities

- `src/raser/stages/deposit.py`: Implements the `deposit` stage job function `deposits(kwargs)` and standard-run track-plot path helper `_picture(kwargs)`, performing `Detector` construction, event-count mutual-exclusion validation, `-g4_vis` visualization dispatch, `write_simulated_deposits` invocation, and raising `Ended` on zero events.
- `src/raser/stages/chain.py`: Defines `DEPOSIT_KEYS`, `COMPONENTS`, `READERS`, visualization CLI switch registration function `deposit_arguments(parser)`, visualization argument forwarder `job_command(kwargs)`, and lazy-import callback `_deposits(kwargs)`, assembling `"deposit"` into the simulation chain.
- `src/raser/stages/stage_commands.py`: Registers `raser deposit` (short alias `dep`) in `STAGES["deposit"]`, resolves experiment folders via `_experiment(target)`, verifies in `run("deposit", kwargs)` that the target experiment includes the `deposit` stage, and invokes lifecycle `execute` with `until="deposit"`.
- `src/raser/stages/files.py`: Implements `_job(kwargs)` and `output(kwargs, name)`, returning the output path of `deposit.h5` inside the `deposit` stage node.

### Core Data Structures

| Data structure | Field name | Type or fixed value | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `files["g4setup"]` (return value of `read_g4setup`) | Keys of `G4SETUP` | `dict` | `μm`, degrees, `g/cm^3` | Dictionary entries exported by `G4SETUP` in the setup script (including `maxstep`, `along_beam`, `materials`, `objects`, etc.) |
| `files["g4setup"]` (return value of `read_g4setup`) | `"file"` | `str` | None | Supplied `deposit.g4setup` component name or `.py` file path |
| `files["g4setup"]` (return value of `read_g4setup`) | `"sha256"` | `str` | None | 64-character hexadecimal SHA-256 digest of the setup script byte stream |
| `kwargs` (input dict to `deposits`) | `"det_name"` | `str` | None | Detector name passed to `Detector(det_name, files["device"])` |
| `kwargs` (input dict to `deposits`) | `"_files"` | `dict` | None | Component snapshot dictionary containing `"device"`, `"source"`, and optional `"g4setup"` |
| `kwargs` (input dict to `deposits`) | `"seed"` | `int` | None | Random seed derived by the lifecycle for this stage ($[1, 2^{31}-1]$) |
| `kwargs` (input dict to `deposits`) | `"job_index"` | `int \| None` | None | Current job index (0-based; `_job` defaults to `0` if omitted or `None`) |
| `kwargs` (input dict to `deposits`) | `"_run_path"` | `str` | None | Current run directory path (where `g4_geometry.png` is written in `-g4_vis` offscreen mode) |
| `kwargs` (input dict to `deposits`) | Keys of `DEPOSIT_KEYS`, plus `<slot>.edep_min` and `<slot>.edep_max` | `str \| int \| float \| bool \| None` | events, `MeV`, `ns` | Effective settings for this stage after merging the `deposit` section of `config.json` with command-line arguments (see Interface table below) |
| `kwargs` (input dict to `deposits`) | `"g4_vis"`, `"g4_vis_driver"` | `bool`, `str` | None | Per-run visualization switch and Geant4 visualization driver name |

## Interface

### Command-Line Options and Configuration Keys

Only the parameters, CLI options, and `config.json` `deposit`-section keys listed below are user-configurable in this stage (shared run parameters `-s`, `--seed`, `--same-seeds`, `-b`, `-t`, `-mem`, `--dry-run`, `--scan`, `--set` are documented in [Command-Line Interface (`raser`)](../cli.md) and [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md)). `--set` and `--scan` use `"section.key"` addresses (such as `--set deposit.events_per_job=200` and `--scan deposit.g4setup.source=decay/Sr90,bunch`). Parameters outside this table (such as stage name `"deposit"`, offscreen driver `TSG_OFFSCREEN` for standard runs, node paths, and image filename `g4_geometry.png`) are hardcoded. Except for `-g4_vis` and `--g4-vis-driver`, which apply only to the current invocation, all settings come from the `deposit` section of `config.json` and enter the `deposit` node fingerprint and `node.json`. Changing any of them, including `deposit.plots`, causes `deposit` and all downstream stages to compute new nodes. For configuration keys in the table, "Value in example" shows the value written in `examples/HPK-Si-PiN/signal/config.json`, with different values from other examples in parentheses; all of these keys (including `deposit.require`, `deposit.coincidence_window_ns`, `deposit.edep_min`, and `deposit.edep_max`) must be written in `config.json`, and if a key is missing, an error is raised naming the missing `section.key` (per-slot overrides `deposit.<slot>.edep_min` and `deposit.<slot>.edep_max` inherit the un-slotted values when omitted). For CLI option rows, the column shows the value used when the option is omitted.

| Section.Key or CLI option | Value in example | Unit | Meaning |
| --- | --- | --- | --- |
| `[path]` (positional argument for `raser deposit` / `dep` only) | Current folder | None | Path to an experiment folder containing `config.json` (defaults to the current folder when omitted) |
| `deposit.g4setup` | `"device_alone"` (`"time_resolution"` in the `timeres` example) | None | Geant4 setup script name (looked up as `<name>.py` under component directory `deposit/`; see [Energy Deposition Components (`components/deposit`)](../components/deposit.md)) or `.py` file path; defines the source, slots, and surrounding objects arranged along the beam (`along_beam`), maximum step length `maxstep` (`μm`), and the setup's `source` block (source component name `name` and incidence angle `angle`) |
| `deposit.g4setup.source` | `"decay/Sr90"` (`name` of the setup's `source` block; `"bunch"` in the `bmos` example) | None | Replaces the whole source: particle source or beam component name (looked up as `<name>.json` under component directory `deposit/`; see [Energy Deposition Components (`components/deposit`)](../components/deposit.md)) or JSON file path; supports `"beam"`, `"decay_source"`, and `"toy_mip"`; the setup's `angle` is kept |
| `deposit.g4setup.source.<key>` | None (not overridden when absent) | per key | Overrides one key of the source component, for example `deposit.g4setup.source.activity`; any key other than `name` and `angle` can be written |
| `deposit.events_per_job` | `200` (`10000` in the `timeres` example, `1000` in the `telescope` example) | events | Number of valid deposit events to record per job (integer not less than `1`); the particle source keeps generating events until this count is recorded inside the device (bounded by `deposit.generated_limit`); mutually exclusive with `deposit.generated_per_job` |
| `deposit.generated_per_job` | `null` (unused) | events | Total number of events generated by the particle source per job (integer not less than `1`), used instead of `deposit.events_per_job`; the source stops after generating this fixed count, and the actual recorded count inside the device may be lower or `0` |
| `deposit.generated_limit` | `10000000` | events | Maximum number of source events a job is allowed to generate to reach `deposit.events_per_job` recorded events (integer not less than `1`) |
| `deposit.edep_min` | `null` (no lower bound) | `MeV` | Lower bound on total deposited energy applied to all slots when no slot prefix is given (`null` disables checking); total deposited energy inside a slot's active layer must be greater than `0` and at least this value to count as a hit |
| `deposit.edep_max` | `null` (no upper bound) | `MeV` | Upper bound on total deposited energy applied to all slots when no slot prefix is given (`null` disables checking); total deposited energy inside a slot's active layer must be at most this value to count as a hit |
| `deposit.<slot>.edep_min` | Omitted (inherits `deposit.edep_min`) | `MeV` | Per-slot lower bound on total deposited energy for the named slot, overriding the un-slotted `deposit.edep_min`; `null` disables lower-bound checking for that slot |
| `deposit.<slot>.edep_max` | Omitted (inherits `deposit.edep_max`) | `MeV` | Per-slot upper bound on total deposited energy for the named slot, overriding the un-slotted `deposit.edep_max`; `null` disables upper-bound checking for that slot |
| `deposit.require` | `"any"` | None | Slot logical expression for recording events, using slot names as operands and `AND`, `OR`, and parentheses as operators (`AND` binds tighter than `OR`), with `"any"` and `"all"` as shorthand for `OR` and `AND` over all slots; setting `"ref AND dut"` in `timeres` saves downstream computation at the cost of losing events for comparing other trigger conditions, see [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md#recording-conditions-for-multiple-devices) |
| `deposit.coincidence_window_ns` | `null` (no timing cut) | `ns` | Timing window width (positive number, or `null` for no timing cut); an event is recorded only if `deposit.require` evaluates to true when counting only slots whose hit times fall within some interval $[t_0, t_0 + W]$ of this width |
| `deposit.fano` | `true` | None | Controls whether Fano fluctuation sampling is enabled for ionized electron-hole pairs: `true` or `false` (`false` uses the mean number of ionized pairs directly) |
| `deposit.plots` | `100` (`0` in the `timeres`, `bmos`, and `cflm` examples) | events | Per-job plots drawn by `deposit` itself: when greater than `0`, Geant4 sources render the geometry and tracks of the first `N` recorded events offscreen (`g4_geometry.png`) during standard runs; `0` disables plotting. `current` plots are controlled by `current.plots`; see [Carrier Transport and Induced Current Stage (`stages/current`)](current.md) |
| `-g4_vis` | `False` | None | Per-run CLI boolean switch; when enabled, performs only Geant4 geometry and track visualization using the event count from `deposit.events_per_job` or `deposit.generated_per_job` as generated events, then exits the job |
| `--g4-vis-driver` | `"TSG_QT_GLES"` | None | Per-run Geant4 visualization driver used with `-g4_vis`; drivers `"TSG"`, `"TSG_FILE"`, or `"TSG_OFFSCREEN"` (case-insensitive) export a PNG image and exit, while windowed drivers such as `"TSG_QT_GLES"` and `"OGL"` open an interactively rotatable window and exit when closed |

When an experiment is a Python class in a project, it can define `observers` and `primaries` on the class, which the `deposit` stage passes to `simulate_deposits` (see [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md#entry-points-for-experiment-scripts)); how to write an experiment class is described in [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md). When an experiment class provides `observers` or `primaries`, the content digest of the Python file defining them is included in the `deposit` node fingerprint, so editing those functions produces a new node.

Terminal errors raised when options are misconfigured or fail at runtime:

- **Unsupported `"kind"` in the source component named by `deposit.g4setup.source`**:
  ```text
  ValueError: no simulation of deposits for a source of kind '<kind>'; known: ['toy_mip', 'beam', 'decay_source']
  ```
  Cause: `"kind"` in the source JSON is not among the three supported types; check the component file and change `"kind"` to a valid value.
- **`deposit.g4setup` points to or matches a legacy `.json` file**:
  ```text
  ValueError: <stale>: a g4setup is a script now; write it as <name>.py with its keys in G4SETUP
  ```
  Cause: setup definitions have moved to Python scripts; rewrite it as a `.py` file exporting a `G4SETUP` dictionary and remove any leftover `.json` file from the same directory.
- **Conflict or out-of-range value for `deposit.events_per_job` and `deposit.generated_per_job`**:
  - Both unset or both set at runtime (for example, after manual configuration edits):
    ```text
    ValueError: events_per_job (<events>) and generated_per_job (<generated>): a job records a number of events or generates one, so exactly one of them is set
    ```
    Set exactly one of the two in the configuration or command.
  - Value less than `1`:
    ```text
    ValueError: the recorded events asked for are <number>: at least 1
    ValueError: the generated events asked for are <number>: at least 1
    ```
    Change `deposit.events_per_job` or `deposit.generated_per_job` to a positive integer at least `1`.
- **`deposit.generated_limit` reached before collecting `deposit.events_per_job`, or out-of-range value**:
  - Generation cap hit before reaching the target recorded count:
    ```text
    RuntimeError: <recorded> of the <events> events asked for were recorded when the limit of <generated> generated events was reached: <ratio> of the generated events are recorded. Ask for fewer events, or raise generated_limit
    ```
    Cause: the recording efficiency is too low (e.g., small source solid angle, thin device, narrow energy window, or strict recording condition); reduce `deposit.events_per_job`, widen `deposit.edep_min`/`deposit.edep_max` (or per-slot energy windows), relax `deposit.require` / `deposit.coincidence_window_ns`, or increase `deposit.generated_limit`.
  - Value less than `1`:
    ```text
    ValueError: the generated_limit asked for are <number>: at least 1
    ```
    Change `deposit.generated_limit` to a positive integer at least `1`.
- **`config.json` missing a required setting key or invalid recording-condition settings**:
  - If `config.json` is missing a key needed in the `deposit` section (such as `deposit.require`, `deposit.coincidence_window_ns`, `deposit.edep_min`, `deposit.edep_max`, etc.), `ValueError` is raised naming the missing `section.key` (e.g. `<config_path> has no deposit.require`).
  - If a slot's energy-window lower bound exceeds its upper bound, if `deposit.require` has a syntax error, names a non-slot operand, or leaves a slot unused, or if `deposit.coincidence_window_ns` is non-positive, `ValueError` is raised; see [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md#branches-of-simulate_deposits) for the error message formats.
- **`--g4-vis-driver` unsupported in the current environment or missing graphical session**:
  ```text
  RuntimeError: Geant4 refused the command '<text>' (status <status>)
  ```
  Cause: the driver was not compiled into the current environment, or the default windowed driver `TSG_QT_GLES` was used on a headless cluster node; switch to `--g4-vis-driver TSG_OFFSCREEN` for offscreen rendering.

### Files Read and Written

Except for offscreen `-g4_vis` images written in the current run directory, all outputs of the `deposit` stage live inside the node folder `nodes/deposit/<node_id>/` under the experiment directory, pointed to by the view symlink `points/<point>/deposit/<job>`. Each node is locked individually, carries the `.part` suffix while partially written, and is renamed to its final name upon completion.

- **`deposit` section of `config.json` and component definitions `files["device"]`, `files["source"]`, `files["g4setup"]` (inputs; used parts recorded in `nodes/deposit/<node_id>/node.json`)**: The lifecycle reads the setting values in the `deposit` section of `config.json`, the device JSON, the setup snapshot returned by `read_g4setup`, and the source component named by the setup's `source` block together with its overriding keys, and hashes the parts used by this stage together with the measurement stage's random seed to obtain the fingerprint (`<node_id>`); the `deposit` stage reads the device, source, and setup snapshots from `kwargs["_files"]`. `files["g4setup"]` records both the script's exported `G4SETUP` and the file's `"sha256"` digest, so editing the script alters the node fingerprint and produces a new node.
- **`work/<source_name>/emission/<node_id>/emission.h5` and `node.json` (input; emission distribution asset for collimated sources)**: When a source contains `nuclides` and `collimator`, each experiment's `deposit` stage reads emitted particles block by block from this asset and launches them from the collimator exit plane $z = 0$ (the node ID depends on all keys of the source component, the `world` material, the seed, and the block index; `node.json` of block `0` contains `emission_check`; see [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md#generation-of-emission-distributions)).
- **`nodes/deposit/<node_id>/deposit.h5` (output; written by `deposit`)**: Written in standard mode by `write_simulated_deposits` (including when `0` events are recorded), containing only events passing the recording condition (a recorded event keeps the deposit steps of all slots), and read via the view symlink `points/<point>/deposit/<job>` by downstream [Carrier Transport and Induced Current Stage (`stages/current`)](current.md) and [Statistical Analysis Stage (`stages/analysis`)](analysis.md). HDF5 format: attributes include `generated_events` (`int`, events), `recorded_events` (`int`, events), `emission_probability` (`float`, dimensionless), `dropped_primaries` (`int`, particles), `vetoed_events` (`int`, events), `require` (`str`, dimensionless), `edep_min.<slot>` and `edep_max.<slot>` (`float`, `MeV`) when a per-slot energy window is set, and `coincidence_window_ns` (`float`, `ns`) when a timing window is set; datasets include `(recorded_events,)` arrays `event` (`int64`, dimensionless) and `count` (`int64`, steps), plus `(sum(count),)` arrays `detector` (variable-length `str`, dimensionless; `"Device"` for a single device or the slot name for multiple devices), `x`/`y`/`z` (`float64`, `μm`, local step midpoint in standard Geant4 or local step start in `cflm`), `t` (`float64`, `s`), `e` (`float64`, `MeV`), and `pairs` (`float64`, pairs), together with optional `(sum(count),)` datasets `x_start`/`y_start`/`z_start` (`float64`, `μm`) and `t_fwhm` (`float64`, `s`) when all recorded events carry step starts or generation time widths. See [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md) for the underlying `write_deposits` / `read_deposits` specification.
- **`nodes/deposit/<node_id>/node.json`, `points.json`, and `points/<point>/deposit/<job>` (node record, parameter table, and view symlink; written by the lifecycle framework)**: `node.json` records verbatim the inputs that produced the node (the setting values used by this stage, the parts of component files used, upstream node IDs, and the random seed from which the fingerprint is computed), along with the code version, runtime environment, and run status. `points.json` at the experiment root records one row per scan point with its scan-axis values and the node IDs used by `deposit` and all other stages; `points/<point>/deposit/<job>` is a symlink pointing to `../../../nodes/deposit/<node_id>`.
- **`nodes/deposit/<node_id>/plots/g4_geometry.png` (output image; written by `deposit`)**: Written offscreen via `TSG_OFFSCREEN` by the `deposit` stage during standard Geant4 runs (when `-g4_vis` is off, `deposit.plots > 0`, and `source["kind"]` is `"beam"` or `"decay_source"`), stored in this stage's own node output and displaying the device, surrounding setup, and tracks of the first `deposit.plots` recorded events.
- **`g4_geometry.png` in the current run directory (visualization output image; written by `deposit`)**: Written at the root of `kwargs["_run_path"]` when `-g4_vis` is enabled and `--g4-vis-driver` is `"TSG"`, `"TSG_FILE"`, or `"TSG_OFFSCREEN"` (case-insensitive), containing an offscreen PNG view of the Geant4 setup geometry and tracks of the specified number of generated events.
