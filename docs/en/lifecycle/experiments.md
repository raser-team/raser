# Experiments, Scan Points, and Seeds

`src/raser/lifecycle/workflow.py` and `src/raser/core/seeding.py` receive the benchmark commands, application commands, and `raser new` command dispatched by [Command-Line Interface (`raser`)](../cli.md) together with the eight stage commands from [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md), and read the definitions of each experiment class. This module copies example projects from `examples/` to create new projects, locates project and experiment folders, reads and writes the configuration file `config.json` sectioned by the eight stages, applies `"section.key"` addresses from `--set` and `--scan` to expand parameter scan points, computes input fingerprints for each stage node, maintains the parameter table `points.json`, the node directories `nodes/<stage>/<node_id>/` (including `node.json`), and the symlink views `points/<point>/<stage>/<job>`, and initializes random number generators and named random streams for measurement stages and jobs. Planned nodes and jobs are handed to [Slices and Reruns](slices.md) for fingerprint reuse and code-version checking, and to [Jobs, Logs, Locks, Resuming, and Cluster Submission](jobs.md) to lock nodes and launch local or cluster jobs; once stages finish, [Statistical Analysis Stage (`stages/analysis`)](../stages/analysis.md) aggregates results across scan points and outputs cross-point trend plots under `<experiment>/analysis/`.

## Behavior

### Experiment Classes, Projects, and Directory Layout

Each benchmark or application is a Python class inheriting from the `raser` experiment base class, specifying which stages it consists of, which devices it uses, and what role each device plays (such as device under test or reference device); the class does not store setting values—values come solely from `config.json`, no default values are kept in code, and if a required key is missing an error is raised identifying the missing `"section.key"`. The device passed on the command line replaces the device under test (for example, `telescope` uses `TAICHU3` as reference layers by default with two devices under test in the middle, and the device passed on the command line replaces both of them). Official benchmark classes live in the `raser_bench` package (`signal`, `timeres`, `tct`, `telescope`), with output placed under the device's project at `work/<device>/<bench>/`; official application classes live in the `raser_app` package (`bmos`, `cflm`, `hbf`, `pimg`), with output placed under `work/<app>/`, where the device itself can serve as a scan axis (multiple device axes are supported) to compare results across different devices. User-defined benchmarks or applications are likewise written as Python classes inheriting from the experiment base class, placed in a user package and registered under `[project.entry-points."raser.experiments"]` in `pyproject.toml` or placed in `*.py` files at the project root for automatic discovery, and registered by name (see [Architecture Overview](../architecture.md#experiments-are-python-classes)). Stage names (`field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, `analysis`) and their short commands (`fld`, `dep`, `cur`, `rdo`, `digi`, `trig`, `reco`, `ana`), along with `status`, `new`, `model`, and `device`, are reserved words and are not used as experiment folder names.

A device folder or an application folder under `work/` constitutes a project; each example in `examples/` is also a project with a complete `config.json` (such as `examples/HPK-Si-PiN/` and `examples/bmos/`). Examples can be run in place inside `examples/`, storing results in their own project. When an experiment command is given a name (for example `raser signal HPK-Si-PiN` or `raser bmos`), it looks first for `work/<name>/`, then `examples/<name>/`, and finally `./<name>/` under the current directory; if none of the three exists, it exits with an error. Running `raser new --from <example> <path>` copies all of `examples/<example>` into a new project with a complete configuration, independent of the example thereafter:

```bash
raser new --from HPK-Si-PiN work/my-PiN
raser signal my-PiN
```

When referencing a device, if the project folder has its own device file, that file takes precedence; when only a device name is given, it is looked up in the `raser/components/device/` component library (see [Device Definition (`components/device`)](../components/device.md)). The component library is used only to locate device files; the project itself must exist in one of the three locations above, so having the device in the library still exits with an error—use `raser new --from` to create a new project.

The results of an experiment are stored in two layers: content-addressed nodes underneath, and symlink views organized by scan point on top. The directory layout of a device project and an experiment folder is as follows:

| Path | Contents |
| --- | --- |
| `<device_project>/field/<node_id>/` | Field nodes for this device (containing electric field, weighting field, IV/CV, device parameter circuit diagram, and `node.json`), shared by all experiments on this device |
| `<experiment>/config.json` | Sectioned configuration file listing all settings used by this run, sectioned into the eight stages `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, and `analysis` |
| `<experiment>/points.json` | Parameter table computed from `config.json` on each run, one row per scan point, recording each scan axis value and the node ID used for each stage; printed by `raser status` |
| `<experiment>/nodes/<stage>/<node_id>/` | Stage node folder holding the files written by this stage for that set of inputs, stage plots, and a `node.json`; `deposit` through `reconstruction` have one node per job, and `analysis` has one node per scan point |
| `<experiment>/points/<point>/<stage>/<job>` | Scan-point view: `deposit` through `reconstruction` have one folder per stage, with one symlink per job pointing to `../../../nodes/<stage>/<node_id>`; `points/<point>/field` points to the shared field node and `points/<point>/analysis` points to `../../nodes/analysis/<node_id>`, each as a single symlink |
| `<experiment>/analysis/` | Cross-point statistics and trend plots generated by the `analysis` stage |

When running `raser <options>` directly in the root of an experiment folder that already contains a valid `config.json`, the CLI entry point automatically reads the experiment command words and device name from `config.json` and inserts them after leading global options (`-b`, `-t`, etc.). If `raser -s 2` is run directly outside the root of an experiment folder containing a valid `config.json` (for example, inside a subfolder or in a directory without `config.json`), the CLI parses the arguments verbatim and reports an error:

```text
raser: error: argument command: invalid choice: '2' (choose from ...)
```

This happens because `raser` auto-completes the command words and device name only when `config.json` exists in the current working directory, the experiment command recorded in it is registered, and the command line contains no other command name, short alias, or `-h`/`--help`/`--version`. Either `cd` back to the root of the experiment folder and rerun, or write out `raser <command> <device> ...` in full.

### Sectioned Configuration and `--set` / `--scan` Parameter Scans

`config.json` in each experiment folder is sectioned by the eight stages in the chain (one section each for `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, and `analysis`) and specifies all settings used by the run; every setting used by a run comes from the configuration file. Component files are stored under `raser/components/` in folders grouped by the stage that reads them (`device/` holds devices; `deposit/`, `readout/`, `digitizer/`, and `trigger/` hold the components for their respective stages).

From the command line, `--set <section.key>=<value>` modifies a single setting in `config.json`, and `--scan <section.key>=<value1>,<value2>,...` expands comma-separated values by Cartesian product into a set of scan points; both options may be passed multiple times:

```bash
raser signal my-PiN --set field.voltage=100
raser signal my-PiN --scan field.voltage=100,200
```

On each run, the program computes `points.json` from `config.json` and updates the symlink views under `points/<point>/`. Point names are named from scan-axis values (such as `voltage_100`, `voltage_200`) as human-readable entry points; after modifying settings or adding a scan axis, a point name may remain unchanged while the node its symlink points to updates accordingly, keeping parameters and results strictly matched by fingerprint.

Passing the same key to both `--set` and `--scan` in the same command raises an error before expanding scan points:

```text
ValueError: field.voltage: given to --set and to --scan at once; give it to one of them
```

This occurs because the command requested both a fixed value and a multi-value scan for the same parameter; use `--set` for a fixed value or `--scan` to scan multiple values, keeping only one of the two.

### Node Fingerprints, Cross-Point Reuse, Version Notices, and Node Locks

One result computed by a stage for a given set of inputs is a node. A node's inputs consist of four items:

1. the setting values used by this stage;
2. the part of the component files used by this stage;
3. the node IDs of its upstream nodes;
4. the random seeds of the measurement stages (`deposit`, `current`), as well as the own seeds of `readout` (NGspice noise) and `digitizer` (clock phase, aperture jitter), all derived from the job seed according to the "Seeds" section below. When `--seed` is omitted, the master seed is taken from the launch timestamp, so each run is a new measurement; to reuse nodes of measurement stages, pass the same `--seed`.

The fingerprint is computed from these four inputs, and the fingerprint is the node ID. `node.json` inside `nodes/<stage>/<node_id>/` records these inputs verbatim, and additionally records the code version, runtime environment, and run status.

Whenever fingerprints match, a node is reused directly regardless of which scan point or run computed it. When a scan affects only downstream settings, upstream nodes are shared automatically across scan points; passing `--seed <integer>` fixes the random seed for reproducible results, and passing `--same-seeds` makes jobs with the same index across scan points share random seeds so upstream results unaffected by the scan are reused. For example, when scanning both `field.voltage=100,200` and two values of a resistor in `readout` on `signal`: `deposit` and `current` produce `2` nodes (changing bias is a new measurement, so each bias is measured separately; only `readout` reads the resistor, so both resistor values share these two nodes), while `readout` and downstream stages produce `4` nodes (two bias values times two resistor values).

Nodes are append-only: changing the number of events per job from `20` to `40` changes the fingerprints of all stages and writes new nodes while the old nodes remain under `nodes/`; changing the event count back to `20` points the `points/<point>/<stage>/<job>` views back to the original old nodes, reusing all of them directly. When the code version differs from the code version recorded in a node's `node.json`, the program prints only a notice and reuses the existing result as usual.

During concurrent runs, each node is locked individually; a node being written carries a `.part` suffix and is renamed to its final name only when writing finishes, so every node with a final name is a complete result. If the underlying network filesystem does not support `flock`, a warning is printed to the terminal and execution continues:

```text
warning: <lock_file_path> cannot be locked here (Operation not supported): nothing keeps another command off it
```

When this warning appears, avoid launching concurrent write commands against the same experiment manually.

### Seeds

A run has one master seed, given by `--seed <integer>` or taken from the launch timestamp if omitted. Each job's seed is derived from three items:

1. the master seed;
2. the job index (`0` through the job count given to `-s` minus `1`);
3. the values of the measurement-related scan axes at this scan point: scan axes in the `field`, `deposit`, and `current` sections. Changing the bias voltage, source, or drift settings constitutes a new measurement, so the values of these axes enter the job seed; scan axes in `readout` and downstream sections only change post-measurement processing and do not enter the job seed.

The point name does not enter the derivation: changing how the point name is written, or adding a scan axis unrelated to measurement, leaves the job seed unchanged. The job seed is obtained from the string `"<master_seed>/<job>/<section.key>=<value>;<section.key>=<value>;…"` (with measurement-related scan axes sorted alphabetically by `"section.key"` and values formatted as JSON) using the same SHA-256 mapping as Eq. (1); the seeds of each stage and random stream inside the job are then derived by name from the job seed via Eq. (1), with `readout`'s NGspice noise seed being one of them.

- **Adding jobs**: Changing `-s 3` to `-s 5` under the same `--seed` leaves the seeds of jobs `0`, `1`, and `2` unchanged, so their nodes are reused as usual and only jobs `3` and `4` are newly computed; because the jobs aggregated by `analysis` have changed, each point's `analysis` is computed into a new node, and the cross-point statistics under `<experiment>/analysis/` are rewritten accordingly.
- **Scanning bias voltage**: Under `--scan field.voltage=100,200`, the two points get different job seeds, so `deposit` and `current` are measured separately for each bias.
- **Scanning a readout resistor**: When scanning only keys in the `readout` section, all points get the same job seed, so `deposit` and `current` nodes are shared across points.
- **`--same-seeds`**: The job seed is derived only from the master seed and job index without scan-axis values, so jobs with the same index across scan points share seeds; when a scan axis is not read by a given measurement stage, that stage's nodes are shared across points.

### Multi-Point Scheduling and Cluster Resubmission Checks

In multi-point experiments, the program first prepares shared nodes needed by the points (such as `work/<device>/field/<node_id>/`) and then schedules pending jobs for each scan point in turn. Scan points are independent of one another: if one point enters a waiting state because a prerequisite is not ready, or fails because job execution raises an exception, the program continues running the remaining scan points and lists all failed points together before exiting:

```text
1 of 2 points failed:
  ...
```

When rerunning a command with `-b` on a login node, the program queries the cluster scheduler (`hep_q` or `condor_q`, timeout `120` $\text{s}$) for the liveness of submitted jobs: if a job is still on the cluster, it prints `are submitted already` and skips it; if a job is no longer on the cluster and has not finished, it prints `is no more on the cluster: it failed and is submitted again` and automatically resubmits it; if the scheduler errors or times out so it cannot be queried, it prints `the scheduler cannot be asked; left as it is` and leaves it unchanged.

## Rules

### Built-in Constants

The table below lists the built-in constants and fixed runtime parameters in `src/raser/cli/raser.py`, `src/raser/lifecycle/workflow.py`, and `src/raser/core/seeding.py`. They are module-level constants hardcoded in the source:

| Constant | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `GLOBAL_OPTIONS` | `{"-t", "--test", "--batch"}` (plus regex match `r"-b+"`) | None | Leading global options kept at the front by `_experiment_arguments` in `cli/raser.py` when auto-completing command words and device name inside an experiment folder |
| `SHORT` | `{"fld": "field", "dep": "deposit", "cur": "current", "rdo": "readout", "digi": "digitizer", "trig": "trigger", "reco": "reconstruction", "ana": "analysis"}` | None | Command-line short-alias map for the eight stage subcommands in `cli/raser.py` (full names are always used when writing files and folders) |
| `_STARTS` | `4` | attempts | Maximum number of attempts by `_run_again` in `workflow.py` to relaunch a waiting command or this experiment's command when a cluster job finishes |
| `_PAUSE` | `30` | $\text{s}$ | Sleep interval between consecutive relaunch attempts in `_run_again` in `workflow.py` |
| `_WAITING_DEPTH` | `8` | levels | Maximum recursion depth for `_start_again` in `workflow.py` to automatically relaunch external waiting commands on the cluster |
| Derived seed modulus | $2^{31}-1$ (`2147483647`) | None | Modulus in `seeding.py` for mapping the first `8` $\text{B}$ big-endian unsigned integer of SHA-256 to a positive integer seed (range $[1, 2^{31}-1]$ after adding `1`) |

### Command-Line Completion and Entry-Point Dispatch

`main(argv)` in `src/raser/cli/raser.py` parses and dispatches commands in the following order:

1. **Auto-completion inside an experiment folder (`_experiment_arguments(argv)`)**: Checks `config = Path.cwd() / "config.json"` in the current working directory. If any of the following conditions holds, returns `argv` unchanged:
   - `not config.is_file()`;
   - `{"-h", "--help", "--version"}.intersection(argv)` is non-empty;
   - any argument in `argv` belongs to the registered command table `APPLICATIONS` or the short-alias table `SHORT`.
   Otherwise reads `config.json` to extract experiment command words `words` and device name `device` (empty list `[]` for deviceless applications); if `words` is empty or its first word is unregistered, returns `argv` unchanged. Otherwise scans rightward from index `lead = 0`, skipping all leading global options satisfying `argv[lead] in GLOBAL_OPTIONS` or `re.fullmatch(r"-b+", argv[lead])`, and returns `[*argv[:lead], *words, *device, *argv[lead:]]`.
2. **Merging top-level global options**: Calls `build_parser().parse_args(argv)` to obtain the dictionary `kwargs`, and expands the subcommand name via `command = SHORT.get(kwargs["_command"], kwargs["_command"])` (if `None`, prints help and returns exit code `1`). If the top-level `-b`/`--batch` cumulative count `kwargs["global_batch"] != 0`, executes:
   - `kwargs["dry_run"] = kwargs["dry_run"] or kwargs["test"]`;
   - `kwargs["batch"] = True`;
   - `kwargs["mem"] = max(kwargs["mem"], kwargs["global_batch"])`;
   - `kwargs["global_batch"] = 0`.
3. **Setting project root context and running the command**: Sets `kwargs["_argv"] = argv` and `kwargs["_entry_command_prefix"] = (command,)`. The project is determined in the lookup order of the "Experiment Classes, Projects, and Directory Layout" section: benchmark commands look up the device name and application commands look up the application name in `work/<name>/`, `examples/<name>/`, and `./<name>/` in turn; stage commands and `raser status` use the project containing the given path (or the current directory if omitted) (see [Common Infrastructure (`supports`)](../supports/README.md) for path resolution). Enters `project_root_context(project, kwargs.get("_components", ()))` and calls `kwargs["_run"](kwargs)`; if `MissingDependency` or a `ModuleNotFoundError` belonging to `ROOT_MODULES` is caught, prints a hint to stderr and returns exit code `1`; before exiting, calls `process.close()` in `finally`.

### Configuration Parsing, Node Planning, and Locked Scheduling

After an experiment command or stage command starts, it expands scan points, computes node fingerprints, and schedules jobs in the following steps:

1. **Locating the project and reading/writing sectioned `config.json`**: A benchmark experiment's folder is `<device_project>/<bench>/`, and an application experiment's folder is `<app_project>/` itself, with the project located in the lookup order of the previous section (such as `work/HPK-Si-PiN/signal/`, `examples/HPK-Si-PiN/signal/`, or `work/bmos/`). Reads `config.json` at the experiment root (containing the eight sections `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, and `analysis`). For each `--set` and `--scan` entry passed on the command line, splits on the first `"="` into a `"section.key"` address and value string (`--scan` values are split on `","`), and passes each value to `_parse` (returns the parsed value if `json.loads` succeeds, or keeps the original string on `JSONDecodeError`); if the same address appears in both `--set` and `--scan`, raises `ValueError`. Outside `--dry-run` mode, writes the updated settings back to `config.json`.
2. **Expanding scan points and computing stage node IDs**: Generates a scan point for each combination in the Cartesian product of scan-axis values, computes each stage's node ID from the setting values used by that stage, the used portions of component files (the project's own device file or the stage's components under `raser/components/`), upstream node IDs, and seeds (the seeds of measurement stages `deposit` and `current`, and the own seeds of `readout` and `digitizer`, all derived from the job seed), writes `points.json`, and updates the `points/<point>/<stage>/<job>` symlinks.
3. **Comparing node fingerprints and code version `_commit()`**: Obtains the current code version identifier `_commit()` (`f"raser {raser.__version__}"` when `REPO_ROOT is None`; otherwise runs `git rev-parse HEAD` and `git status --short` under `REPO_ROOT`, returning the commit hash when the worktree is clean and appending `"+dirty"` when uncommitted changes exist; a source tree that is not a git repository, such as one unpacked from an archive, has no commit to read and also gives `f"raser {raser.__version__}"`). If the target node `nodes/<stage>/<node_id>/` (or `<device_project>/field/<node_id>/`) already exists, reuses that node directly; if the code version recorded in its `node.json` differs from the current `_commit()`, prints a notice and reuses it as usual. If `--dry-run` is true, prints the scan points, stages, and job plan and returns immediately.
4. **Node locking, `.part` writes, and launching local or cluster jobs**: For each node to be computed, calls `_lock` to open the lock file in append mode and execute `fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)` (on `BlockingIOError`, closes the handle and raises `Running`; on `OSError` whose `errno` is in `(errno.ENOLCK, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL)`, prints a warning and returns `None`). During computation the node carries a `.part` suffix, and after writing data files and `node.json` it is atomically renamed to its final node directory. Local and cluster jobs are launched by the following rules (see [Jobs, Logs, Locks, Resuming, and Cluster Submission](jobs.md)):
   - single scan point, `-s` omitted, no `-b`: executes `_run_job` directly in the current process with Python stdout and stderr mirrored to the log via `_logged`;
   - multiple scan points, `-s` omitted, no `-b`: calls `_own_process` to spawn an independent subprocess `jobs._run_local_job` for each scan point;
   - `-s` or `-b` passed: calls `jobs.run_indexed_jobs` to run in parallel via a local process pool or package and submit to the cluster scheduler (when `RASER_SUBMIT_QUEUE` is enabled, prints `the jobs go to the queue the host submits: a job that waits for others is not started again by itself; run the command again when those are done`).

### Random Seed Initialization, Named Random Streams, and Automatic Cluster Resume

Random number generators for measurement stages and jobs are seeded centrally in `src/raser/core/seeding.py`, and automatic resume after cluster job completion is executed by `_start_again` and `_run_again` in `src/raser/lifecycle/workflow.py`:

1. **Resetting global random number generators (`seeding.seed_generators(seed)`)**: Sets the module variable `_job_seed` to `int(seed)`, synchronously executes `random.seed(_job_seed)` and `ROOT.gRandom.SetSeed(_job_seed)`, and calls `_streams.clear()` to clear cached named random streams.
2. **Deriving independent named random streams (`seeding.stream(name)`)**: When a physics module calls `seeding.stream(name)` to obtain a `ROOT.TRandom3` instance named `name` (such as `"drift"`, `"diffusion"`, `"source"`, `"ionization/<event>"`), returns the cached instance if `name in _streams`; if `name not in _streams`:
   - when `_job_seed is None` (before `seed_generators` is called), sets the stream seed $\text{seed}_{\text{stream}} = 0$ (randomly initialized by ROOT);
   - when `_job_seed is not None` (where `_job_seed` is the job seed derived in the "Seeds" section above), computes the SHA-256 digest of the UTF-8 bytes of `f"{_job_seed}/{name}"`, takes the first `8` $\text{B}$ as a big-endian unsigned integer, and maps it into $[1, 2^{31}-1]$:

     $$\text{seed}_{\text{stream}}(name) = 1 + \left(\operatorname{int\_from\_bytes}\!\left(\operatorname{SHA256}\!\left(\text{"\{\_job\_seed\}/\{name\}"}\right)[0:8],\, \text{"big"}\right) \bmod (2^{31} - 1)\right) \tag{1}$$

     where $\text{seed}_{\text{stream}}(name)$ is the positive integer seed passed to `ROOT.TRandom3` (dimensionless, range $[1, 2^{31}-1]$), `_job_seed` is the current integer seed (dimensionless), and `name` is the stream name string. Constructs `_streams[name] = ROOT.TRandom3(seed)`, stores it in the cache, and returns it.
3. **Automatically relaunching commands after cluster job completion (`_start_again`, `_run_again`)**: When environment variable `RASER_CLUSTER_JOB` is non-empty and the current job has completed new computation progress, reads the current recursion depth `depth = int(os.environ.get("RASER_RESUBMIT_DEPTH", "0"))`:
   - first iterates over the list of external commands waiting on the current shared result: if `depth >= _WAITING_DEPTH` (`8` levels), prints `not starting raser <command>: <depth> starts deep`; otherwise calls `_run_again` to relaunch that external command and removes it from the waiting list on success;
   - then checks this experiment's resume command (recorded when `RASER_SUBMIT_QUEUE` is not enabled): if `depth` has reached the number of slices in the chain, prints `not starting the command again: <depth> starts deep, ...` and returns; otherwise calls `_run_again` to relaunch this experiment's command so downstream jobs waiting on upstream completion are submitted;
   - `_run_again(words, cwd, depth)` prints `starting the command again: raser <command>`, sets `RASER_RESUBMIT_DEPTH` to `str(depth + 1)` in the subprocess environment, and tries up to `_STARTS = 4` times under `cwd` (with `time.sleep(_PAUSE)`, i.e., `30` $\text{s}$, between consecutive attempts); returns `True` as soon as any attempt exits with code `0`, or prints `the command did not start again in 4 tries: give it again when the jobs it waits for are done` and returns `False` if all `4` fail.

## Software Implementation

### Source File Responsibilities

- `src/raser/lifecycle/experiment.py`: the experiment base class `Experiment` and the device slot `Slot`.
- `src/raser/lifecycle/workflow.py`: Provides the concurrent-occupancy exit exception `Running`; implements `raser new --from` example project copying, shared run option registration `run_arguments`, sectioned `config.json` reading/writing and `--set`/`--scan` `"section.key"` address merging, node fingerprint calculation, maintenance of the `points.json` parameter table and `points/<point>/<stage>/<job>` symlink views, shared field node preparation, multi-point local and cluster job scheduling, and automatic cluster resume `_start_again`/`_run_again`.
- `src/raser/core/seeding.py`: Maintains the module-level current seed `_job_seed` and named random stream dictionary `_streams`; provides `seed_generators(seed)` to seed Python `random` and `ROOT.gRandom` together and clear the stream cache, and `stream(name)` to derive via SHA-256 and cache independent `ROOT.TRandom3` instances by stream name.
- `src/raser/cli/raser.py`: Defines the `raser` CLI entry point `main` and argument parser `build_parser`, maintains the subcommand map `APPLICATIONS` and the eight-stage short-alias map `SHORT`; provides `_experiment_arguments` to auto-complete command words and device name in the root of an experiment folder containing `config.json`, and merges top-level `-b`/`-t` global options into subcommand arguments.

### Core Data Structures

| Data structure and fields | Type and default | Unit | Meaning |
| --- | --- | --- | --- |
| Experiment base class and experiment subclasses | Python classes | None | Base class inherited by `raser_bench`, `raser_app`, and user-defined experiments, declaring the stages included in the experiment, the device list, and each device's role (such as device under test or reference device); discovered via the `raser.experiments` package entry point or project folders and registered by name (see [Architecture Overview](../architecture.md#experiments-are-python-classes)) |
| Class attributes of `Experiment` | `name` (the command word), `stages`, `devices` (slot name → `Slot`, in the order of the experiment), `components`, `application` (default `False`) | None | An experiment of one device has the single slot `Device`; a slot name uses letters, digits, `_` and `-` only; with `application` `True` the output goes to `work/<name>/`, otherwise to `work/<device>/<name>/` |
| `Slot(role, device, positions)` | `role` is `"tested"` (default) or `"reference"`; `device` defaults to `None`; `positions` defaults to `()` | None | A tested slot takes the device given on the command line and names no `device`; a reference slot must name its `device`; at least one slot is tested; `positions` are the places the device takes, one place named as the slot when omitted |
| `Running` | Subclass of `SystemExit` | None | Concurrent-occupancy exit exception raised when the target lock file is already held by another process |
| `seeding._job_seed` | `int \| None`, default `None` | None | Current integer random seed written by `seed_generators` (range $[1, 2^{31}-1]$) |
| `seeding._streams` | `dict[str, ROOT.TRandom3]`, default `{}` | None | Dictionary caching independent `ROOT.TRandom3` instances by stream name `name` within the current job or stage |

## Interface

### Command-Line Options and Configuration Sections

The table below lists the shared run options and configuration sections users can set on the command line and in `config.json`; other runtime control parameters (such as the derived seed modulus, automatic cluster resume retry count `_STARTS`, retry interval `_PAUSE`, and external waiting recursion depth limit `_WAITING_DEPTH`) are hardcoded in the code.

| Option or config section | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `--version` (top-level position) | None | None | Prints the current `raser` version number and exits |
| `-h`, `--help` | None | None | Prints help for the top-level command or a subcommand and exits |
| `-b`, `--batch` (top-level position) | `0` | tiers (`8000 MB`/tier) | Can be stacked to accumulate count (e.g., `-b`, `-bb`, `-bbb`); when non-zero, enables cluster submission and updates the memory tier to `max(-mem, count of b)` |
| `-t`, `--test` (top-level position) | `False` | None | Takes effect only when combined with top-level `-b`: sets `dry_run` to `True` to only check and preview submission details |
| `raser new --from <example> <path>` | None (required) | None | Copies all of `examples/<example>` into a new project at `<path>` with a complete `config.json`, independent of the example thereafter |
| `-s`, `--jobs <integer>` | `None` (treated as `1`) | jobs | Sets the number of parallel jobs per scan point, with job indices `0` through `<integer>-1` |
| `--seed <integer>` | `None` (launch timestamp) | None | Sets an integer random seed to make the measurement stages (`deposit`, `current`) and `readout` noise reproducible |
| `--same-seeds` | `False` | None | Makes jobs with the same index across scan points share random seeds so upstream results unaffected by the scan are reused |
| `--set <section.key>=<value>` | `[]` | Parameter-dependent | Modifies a setting in `config.json` using `"section.key"` as the address (e.g., `--set field.voltage=100`); repeatable; values are parsed with `json.loads` (kept as raw strings on failure) |
| `--scan <section.key>=<value1>,<value2>,...` | `[]` | Parameter-dependent | Scans one or more settings using `"section.key"` as the address (e.g., `--scan field.voltage=100,200`); values are split on commas and parsed with `json.loads`; repeatable and expanded by Cartesian product |
| `--dry-run` | `False` | None | Prints only the scan points, stages, and job statuses to be run and returns immediately |
| `-b`, `--batch` (subcommand position) | `False` | None | Submits pending jobs to the cluster queue |
| `-mem <tier>` | `1` | `8000 MB` | Memory tier requested per job in cluster mode (actually requests `8000 * <tier>` $\text{MB}$); must be a positive integer; passing a non-positive integer raises `ValueError: Indexed job memory level must be positive` on submission |
| `config.json`: eight stage sections `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, `analysis` | Depends on experiment class and example project | Depends on each section's keys | Lists all settings used by the run, sectioned across the eight stages; every setting used by the run comes from its corresponding stage section (see the pages under [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md) for the keys in each stage section) |

### Files and Directories Read and Written

- **`<experiment_folder>/config.json`**: Sectioned experiment configuration file recording complete settings across the eight stage sections `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, and `analysis`; `--set` and `--scan` read and write keys in the corresponding stage sections via `"section.key"` addresses.
- **`<experiment_folder>/points.json`**: Parameter table JSON file computed from `config.json` on each run, one row per scan point, recording each scan axis value and the node ID used by each stage; read and printed by `raser status`.
- **`<experiment_folder>/nodes/<stage>/<node_id>/` and `<device_project>/field/<node_id>/`**: Node directories named by input fingerprint (carrying a `.part` suffix while being written, renamed to their final names upon completion, each locked individually), storing the data files written by the stage (such as HDF5 files and stage plots; see [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md) and the pages under `docs/en/core/` for exact formats) together with a `node.json`. `node.json` records verbatim the four inputs determining the node fingerprint (setting values used by this stage, used portions of component files, upstream node IDs, the seeds of the measurement stages `deposit` and `current`, and the own seeds of `readout` and `digitizer`), and additionally records the code version, runtime environment, and run status.
- **`<experiment_folder>/points/<point>/<stage>/<job>`**: Scan-point view symlinks where `<point>` is named from scan-axis values (such as `voltage_100`); `deposit` through `reconstruction` have one symlink per job pointing to `../../../nodes/<stage>/<node_id>`, while `points/<point>/field` points to `<device_project>/field/<node_id>` and `points/<point>/analysis` points to `../../nodes/analysis/<node_id>`.
- **`<experiment_folder>/analysis/`**: Directory holding cross-point statistics and trend plots written by the `analysis` stage.

### Format of `config.json`

`config.json` comes with the project: `raser new --from <example> <path>` copies the `config.json` of every experiment of the example along, and a run in place on an example uses the one the example carries. The keys of each section and their meaning are in the settings table of [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md#settings) and on the page of each stage.

`config.json` is a JSON object. Its top-level keys fall into three groups:

| Key | Type | Meaning |
| --- | --- | --- |
| `workflow` | string | Command word of the experiment, such as `"signal"` |
| `device` | string | Device name; absent for an application that takes no device |
| `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, `analysis` | object | One section per stage, holding all settings of that stage; an empty object for a stage the experiment does not have |
| `names` | object | Short names for long addresses: "section.key" or "section.slot.key" → short name, for example `{"readout.amplifier": "amp"}`; point names use the short name (`amp_SantaCruz`), `--set` and `--scan` accept both spellings |
| `same_seeds` | boolean | Whether jobs of the same number share their seed across scan points |

The `signal` example of `HPK-Si-PiN`:

```json
{
  "workflow": "signal",
  "device": "HPK-Si-PiN",
  "field": {"voltage": 200.0, "irradiation_flux": null},
  "deposit": {
    "source": "decay/Sr90", "g4setup": "device_alone",
    "events_per_job": 200, "generated_per_job": null, "generated_limit": 10000000,
    "edep_min": null, "edep_max": null, "fano": true, "plots": 100
  },
  "current": {"plots": 100},
  "readout": {"amplifier": "SantaCruz+Gali52+Termination50", "sheet_resistance": null},
  "digitizer": {},
  "trigger": {},
  "reconstruction": {
    "threshold": 10.0, "amplitude_threshold": 10.0,
    "fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], "edge": null
  },
  "analysis": {},
  "names": {},
  "same_seeds": false
}
```

Rules for reading and writing:

1. **One way to give a setting**: `--set <section.key>=<value>` writes the value into its section, `--scan <section.key>=<value1>,<value2>` writes the list of values into the same place. Both stay in `config.json`, and later commands without options use them. The settings of the chain have no command-line options of their own; switches that hold for one run only (`-g4_vis`, `--g4-vis-driver`) do not enter `config.json`.
2. **Two kinds of settings**: the settings of the four sections `field`, `deposit`, `current`, `readout` say what is measured and are physics parameters; the settings of the four sections `digitizer`, `trigger`, `reconstruction`, `analysis` say how the measured events are analysed and are analysis parameters. One more value of a physics parameter is one more set of experiments: written as a list in its section it is a scan, one point per value, for example `"field": {"voltage": [100, 200]}`, with points named by the values (`voltage_100`, `voltage_200`). An analysis parameter is not scanned: its list is the value of the parameter itself, such as `reconstruction.fractions`; giving it to `--scan` is an error. To use another analysis parameter, change it with `--set` and run again with the same `--seed`; the events already measured are reused and only the analysis stages are redone. Without `--seed` every run is a new measurement. Giving a physics parameter a list with `--set` is an error as well, with a hint to use `--scan`.
3. **Ending a scan and restoring a setting**: giving `--set` for an address that is scanned replaces the list in the section by this one value, and the scan ends. An experiment that scans nothing has one point, named `default`; with a scan there is no point `default`. After a scan ends or its values change, the views under `points/` of points that no longer belong to the experiment are removed; the nodes stay. A value given with `--set` stays in its section, and there is no "undo"; to restore it, give `--set` once more with the earlier value, or edit `config.json` directly.
4. **Keys inside a component**: a key of a section that selects a component is a slot, such as `deposit.source` and `deposit.g4setup`; the device is `field.device`. A slot that is missing or `null` is an error before any job starts, for example `ValueError: config.json has no deposit.source: it names the source of the experiment`; the exception is a slot whose stage page says it may be `null`: then no component file is read, as `trigger.device` set to `null` means the trigger of the oscilloscope in `digitizer.device` (see [Trigger Stage (`stages/trigger`)](../stages/trigger.md)). A key inside the component file is written "section.slot.key", for example `--set deposit.source.par_radius=1000` changes `par_radius` in the source file (the radius of the source disk, $\mu\text{m}$). In `config.json` it is written into the object of the slot, beside the name of the component: `"source": {"name": "decay/Sr90", "par_radius": 1000}`; when scanned it is written as a list, and the point name takes the last two parts of the address (`source.par_radius_1000`). Giving the slot another component (`--set deposit.source=decay/Am241`) removes the keys written in the object. An address that is neither a setting nor under a slot is an error that lists all settings and slots. A key of a component that is itself a list cannot be overridden this way: to change it, copy the component file into the project and edit it there.
5. **Each stage reads its own section**: a running stage receives the settings of its own section, so `deposit.plots` and `current.plots` are two settings.
6. **Missing and unknown keys**: a key not written in its section is `null`; when a stage needs its value and it is `null`, an error names the missing "section.key", for example `ValueError: examples/HPK-Si-PiN/signal/config.json has no deposit.generated_limit`; a missing key that is not used raises no error. A key in a section that the stage does not know is an error, for example `config.json: no current.plot; the settings of current are plots`; so is a top-level key other than those in the table above. The program writes every key when it writes `config.json`.
7. **`null` is a value**: keys whose table entry says "`null` takes …" (such as `field.voltage`, which takes the bias in the device file) take that value when written `null`.
