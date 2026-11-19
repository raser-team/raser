# Experiments, Scan Points, and Seeds

`src/raser/lifecycle/workflow.py` and `src/raser/core/seeding.py` manage experiment folders, `config.json` experiment configurations, `--set` and `--scan` parameter scan-point expansion, seed folders and `run.json` run records, and random seed derivation for jobs and slices.

## Inputs

### Experiment Configuration File `<experiment_folder>/config.json`

The program locates the experiment root directory and reads `config.json` according to the following rules: if a workflow has a fixed output directory (for example, [`analysis`](../stages/analysis.md) points to `<experiment>/analysis`), that directory is used directly; otherwise, it first checks whether `config.json` in the current working directory matches the current command, and if not, falls back to `<project_root>/<workflow...>` (when `RASER_PROJECT_PATH` is unset and only a plain device name is passed, this defaults to `<work_root>/<device>/<workflow...>`; inside an experiment directory that already contains `config.json`, you can run `raser <options>` directly).

`config.json` contains the following keys:

| Key | Type | Unit | Description |
| --- | --- | --- | --- |
| `"workflow"` | `str` | None | Workflow command name, such as `"signal"`, `"cce"`, or `"telescope taichu_v1"` |
| `"device"` | `str` | None | Device name (present only for workflows that take a device) |
| `"set"` | `dict[str, Any]` | Parameter-dependent | Mapping of fixed experiment parameters or in-file dotted addresses to values |
| `"scan"` | `dict[str, list]` | Parameter-dependent | Mapping of scanned parameters or in-file dotted addresses to lists of scan values |
| `"names"` | `dict[str, str]` | None | Optional; mapping of parameters or in-file dotted addresses to short names used by `--set`, `--scan`, and scan-point folder naming |
| `"same_seeds"` | `bool` | None | Switch for sharing seeds across scan points; the effective value is the CLI `--same-seeds` flag or this key; this key is written only when creating a new `config.json` (present only for seeded workflows) |

### Device and Component Files

Each scan point reads the device file(s) used by the experiment (stored in `files["device"]`, or separately by device name for multi-device workflows) as well as component files such as source and `g4setup` (stored in `files[kind]`).

### Parameter Merging, Mutually Exclusive Groups, and In-File Dotted Addresses

Parameters for each scan point are merged across three layers from lowest to highest priority: workflow defaults, `"set"` in `config.json`, and command-line arguments (including command-specific options and `--set`). A key given a fixed value on the command line is not scanned during that run.

- **Mutually exclusive option groups**: For example, `("events_per_job", "generated_per_job")`. Parameters in the same group are determined by the highest-priority layer that specifies any member of the group; other keys from the same group in lower layers are removed.
- **In-file dotted addresses**: Keys containing `.` are treated as dotted paths inside `files` (such as `device.bias.voltage`); the single-device chain maps the top-level option `voltage` to `device.bias.voltage`. When the option is not `None`, it overwrites the corresponding leaf node in `files`; when it is `None`, the original value is read from `files`.

### Existing Run Record `<seed_or_point_folder>/run.json`

Before running, if `run.json` already exists under the target seed or scan-point folder, its run record is read for staleness checks, slice reuse, and resuming.

## Outputs

### Experiment Configuration File `<experiment_folder>/config.json`

When creating a new experiment, `config.json` is created with `"workflow"`, `"device"` (for workflows with a device), `"set"`, `"scan"`, and `"same_seeds"` (for seeded workflows). When `--set` or `--scan` is passed to an existing experiment, the new entries are merged into `config.json` and old entries for the same key or the same mutually exclusive group are cleared; ordinary command options apply only to the current run.

### Scan-Point Folders and Seed Folders

- **Scan-point folder `<experiment_folder>/<point>`**:
  - Takes the Cartesian product of all scanned keys' values and compares each key against the baseline non-scanned run (the baseline point uses the fixed value merged from the three layers; for a scanned dotted address without a fixed value, the baseline takes the original value from the component file, while the actual scan point uses the current combination's scan value).
  - When all scanned key values equal the baseline point's values, the point directory name is empty and `<experiment_folder>` is used directly; when differences exist, differing items are joined as `<label>_<text>` to form the subfolder name (`<label>` prefers the short name in `"names"` of `config.json`, falling back to the last two segments of a dotted address or the key name itself; numeric values are formatted with `"%g" % value`).
- **Seed folder `<experiment_folder>/[<point>/]<seed_folder>`**:
  - Seeded workflows: when `--seed <N>` is passed, the folder is named `seed_<N>`; when `--seed` is omitted, it is named with a timestamp `YYYY_mmdd_HHMMSS` and a random 31-bit integer is drawn as the seed. When a fixed-seed folder is rerun because it is stale, the old folder is renamed to `<label>_<YYYY_mmdd_HHMMSS>` and kept aside.
  - Unseeded workflows (such as `field`, `tct`, `analysis`): the run lands directly in the scan-point folder `<experiment_folder>/[<point>]`.

### Run Record File `<seed_or_point_folder>/run.json`

`run.json` records the full context of a single run; when a job executes, it reads parameters, file snapshots, and slice information from `run.json` in its folder:

| Key | Type | Unit | Description |
| --- | --- | --- | --- |
| `"seed"` | `int` | None | Run seed (written for seeded workflows) |
| `"point"` | `str` | None | Relative scan-point folder name; `""` for a non-scanned run (or when values equal defaults) |
| `"same_seeds"` | `bool` | None | Whether cross-scan-point same-seed mode is enabled (written for seeded workflows) |
| `"commit"` | `str` | None | Git HEAD commit hash in a source tree (with `"+dirty"` appended if there are uncommitted changes); `"raser <__version__>"` in package-install mode |
| `"options"` | `dict[str, Any]` | Parameter-dependent | Complete option table after merging the three configuration layers and syncing with in-file dotted addresses |
| `"files"` | `dict[str, Any]` | File-dependent | Device JSON and component data after applying `options` overrides (JSON component content or the return value of a specialized loader; for example, `g4setup` stores `G4SETUP`, `"file"`, and `"sha256"` from the script) |
| `"settings"` | `dict[str, Any]` | None | Additional CLI settings (such as `umf` and `imported` for `field`) |
| `"slices"` | `dict[str, dict]` | None | `"options"`, `"files"`, and shared slice digest `"shared"` read by each slice (see [Slices and Status Inspection](slices.md)) |
| `"held_in"` | `dict[str, str]` | None | Mapping from each slice name to the scan-point folder name holding that slice's outputs (see [Slices and Status Inspection](slices.md)) |
| `"jobs"` | `int` | jobs | Maximum number of jobs requested in the current run record (retains the historical maximum when resuming a non-stale run; resets when a stale rerun creates a new record) |
| `"command"` | `list[str]` | None | Command-line token list recorded in cluster mode |
| `"cwd"` | `str` | None | Working directory path where the command was launched, recorded in cluster mode |
| `"waiting"` | `list[dict]` | None | List of commands waiting for the current shared job to finish in cluster mode |

### What Happens in the Example

Take the run `raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1` from [Getting Started](../getting-started.md) as an example:

1. **Exact contents of the experiment configuration file `work/HPK-Si-PiN/signal/config.json`**:

   ```json
   {
     "workflow": "signal",
     "device": "HPK-Si-PiN",
     "set": {
       "events_per_job": 200
     },
     "scan": {
       "voltage": [
         100,
         200
       ]
     },
     "same_seeds": false
   }
   ```

   In the command, `-evt 200` is a fixed experiment parameter written to `"set"`, `--scan voltage=100,200` is written to `"scan"`, and `--seed 1` determines the seed folder name rather than being written into `config.json`.

2. **Scan-point folder naming**:

   The default bias voltage in the `HPK-Si-PiN` device file is `200 V`, so the `200 V` point is identical to the default run: its point folder name is `""` and its results land directly under the experiment root at `work/HPK-Si-PiN/signal/seed_1/`. Because `100 V` differs from the default bias, it lands in `work/HPK-Si-PiN/signal/voltage_100/seed_1/`. The subsequent `raser analysis work/HPK-Si-PiN/signal` follows the exact same rule: `200 V` results go under the `analysis/` root, and `100 V` results go under `analysis/voltage_100/`.

3. **Top-level keys of `work/HPK-Si-PiN/signal/seed_1/run.json`**:

   The top-level keys written by this run are:

   ```text
   ['seed', 'point', 'same_seeds', 'commit', 'options', 'files', 'slices', 'held_in', 'jobs']
   ```

   Among them, `"seed": 1`, `"point": ""`, `"same_seeds": false`, `"jobs": 2`; `"options"` records the full parameter set including `"voltage": 200`, `"events_per_job": 200`, `"source": "decay/Sr90"`, `"g4setup": "device_alone"`, and `"amplifier": "SantaCruz+Gali52+Termination50"`; in `"held_in"`, `deposit`, `field`, `current`, `readout`, and `reconstruction` all map to `""`.

### Random Seed Derivation and Finished-Job Collection

- **Job and slice random seed derivation**: Before each job or slice starts, the program joins `[seed, point, job_index, slice_name]` (omitting `point` when `--same-seeds` is enabled) into a path string, hashes it with SHA-256, maps the digest to an integer in $[1, 2^{31}-1]$, and seeds both Python `random` and `ROOT.gRandom`. Named random streams `seeding.stream(name)` derive independent seeds on top of this, so scan points with `--same-seeds` enabled use identical random seeds for the same job and slice; when an upstream slice also reads the same scanned value, the points share that upstream slice's output.
- **Finished-job collection**: `finished` and `finished_in` traverse non-stale `run.json` files under each scan point (skipping by name any rerun-archived directories starting with `seed_` whose name does not match the recorded seed, such as `seed_<n>_<timestamp>`; separately saved timestamped directories are still filtered by whether their options and files are stale) and collect all jobs that have `batch/job_<index>.done` for `raser analysis` to aggregate.

## Options

The following shared run options are registered on experiment and stage commands:

| Option | Default | Unit | Description |
| --- | --- | --- | --- |
| `-s`, `--jobs` | `None` (treated as `1`) | jobs | Number of jobs to run per scan point (registered by seeded workflows and the four stage commands; unseeded target workflows run in the point directory) |
| `--seed` | `None` (random 31-bit integer) | None | Specify the integer run seed `<N>`, naming the seed folder `seed_<N>` (registered by seeded workflows and the four stage commands; unseeded target workflows run in the point directory with no separate seed folder) |
| `--same-seeds` | `False` | None | Use the same derived seed across scan points for the same job index and slice name, sharing upstream slice outputs when the scanned values read by the upstream slice are identical; the effective value is this option or `"same_seeds"` in `config.json` (registered by seeded workflows and the four stage commands) |
| `--set` | `[]` | None | Set a single parameter or in-file dotted address `address=value`; values are parsed as JSON and kept as raw strings if parsing fails; repeatable; normal experiment runs write to `"set"` in `config.json` (`--dry-run` and `raser field <experiment_dir>` only select points for this invocation without modifying the experiment config) |
| `--scan` | `[]` | None | Scan a parameter or in-file dotted address `address=v1,v2,...`; split on `,` first, then each value is parsed as JSON and kept as a raw string if parsing fails; repeatable; normal experiment runs write to `"scan"` in `config.json` (`--dry-run` and `raser field <experiment_dir>` only select points for this invocation without modifying the experiment config) |
| `-b`, `--batch` | `False` | None | Submit jobs to the cluster (see [Jobs and Cluster Submission](jobs.md)) |
| `-mem` | `1` | `8000 MB` | Memory tier requested per cluster job (see [Jobs and Cluster Submission](jobs.md)) |
| `--dry-run` | `False` | None | Print the pending jobs and slices for each scan point and return immediately (`raser field <experiment_dir>` prints whether each point's shared slice is ready) |

## Common Errors

- `ValueError: <keys>: given to --set and to --scan at once; give it to one of them`: The same parameter or address (including a short name mapped through `"names"`) was passed to both `--set` and `--scan` in one command.
- `ValueError: <key1> and <key2> are given at once in <where>; give one of them`: Two non-`None` keys from the same mutually exclusive group are both specified in the currently checked configuration layer (`_points` checks CLI, `"set"` in `config.json`, and defaults from highest to lowest and stops at the first effective layer; workflow construction also checks defaults with `<where> = "the defaults of <workflow_name>"`).
- `ValueError: <key> is scanned and another key of its group is given; give one of them`: One key of a mutually exclusive group is scanned via `--scan` on the command line while another key of the same group is given a fixed value on the command line.
- `ValueError: <key1> and <key2> are scanned at once; scan one of them`: Two keys from the same mutually exclusive group appear together in the scan list.
- `ValueError: <address>: no '<step>' in <walked>`: A dotted address specified via `--set`, `--scan`, or `Workflow.in_file` is missing an intermediate level in `files`, or an explicit dotted key is missing its leaf key (for a regular `Workflow.in_file` mapping such as `voltage → device.bias.voltage`, if only the leaf key is missing, reading raises `KeyError` and writing creates that key).
- `ValueError: <key> = <value>: the folder of this value would be named '<text>', which holds more than letters, digits and ._+-; scan or set a number or a short name, and give an expression such as a doping profile a parameter with a name in its file`: The formatted name of a scanned or set value contains characters other than letters, digits, and `._+-`.
- `ValueError: <key>: <v1> and <v2> would both be the folder '<text>'`: Two different values of the same scanned key format to the same folder-name fragment.
- `ValueError: <key1> and <key2> would both be '<label>' in the names of folders: give one of them a name under "names" in config.json`: Two scanned keys produce the same `<label>`, so one of them must be given a short name under `"names"` in `config.json`.
- `ValueError: <other> and <current> would both be the folder '<name>'; scan values that do not hold the names of other scanned options`: Two different scan-parameter combinations join into the same scan-point folder name.
- `ValueError: <root>: no seed folder <label> to go on in`: When resuming, `<label>/run.json` was not found in the experiment directory or any of its scan-point subdirectories.
- `ValueError: <root>: not an experiment folder, no config.json that names a workflow`: When calling `finished_in(root)`, the target folder lacks a `config.json` containing a `"workflow"` key.
- `ValueError: <root>: no command runs its workflow '<workflow>'`: The `"workflow"` in `config.json` is not registered.

## Related Pages

- [Getting Started](../getting-started.md)
- [Architecture Overview](../architecture.md)
- [CLI Overview](../cli.md)
- [Slices and Status Inspection](slices.md)
- [Jobs and Cluster Submission](jobs.md)
- [Device Definition](../core/device.md)
- [Analysis Stage](../stages/analysis.md)
- [Paths and Runtime Supports](../supports/README.md)
