# Command-Line Interface (`raser`)

`raser` (defined in `src/raser/cli/raser.py`) is the unified command-line entry point for RASER. `cli` only dispatches: it parses top-level global options, recognizes experiment directories or short command aliases, sets up project and component search path contexts, and hands arguments to the target module. Each subcommand registers its own arguments; see each command's documentation page for exact option meanings and defaults.

## Commands

| Command (short alias) | What it does | Registered module | Page |
| --- | --- | --- | --- |
| `field` (`fld`) | Solves device electric potential, electric field, weighting field, and IV/CV; with `-ext`, imports a single-bias TCAD field solution and solves weighting potential; or solves the shared fields needed by an experiment's scan points | `raser.stages.field` | [stages/field.md](stages/field.md) |
| `deposit` (`dep`) | Runs an experiment up through `deposit`; when given only a device name, uses the default `signal` experiment (folder `work/<device>/signal`) | `raser.stages.stage_commands` | [stages/deposit.md](stages/deposit.md) |
| `current` (`cur`) | Runs an experiment up through `current`, filling in missing upstream stages automatically; when given only a device name, uses the default `signal` experiment (folder `work/<device>/signal`) | `raser.stages.stage_commands` | [stages/current.md](stages/current.md) |
| `readout` (`rdo`) | Runs an experiment up through `readout`, filling in missing upstream stages automatically; when given only a device name, uses the default `signal` experiment (folder `work/<device>/signal`) | `raser.stages.stage_commands` | [stages/readout.md](stages/readout.md) |
| `reconstruction` (`reco`) | Runs an experiment up through `reconstruction`, filling in missing upstream stages automatically; when given only a device name, uses the default `signal` experiment (folder `work/<device>/signal`) | `raser.stages.stage_commands` | [stages/reconstruction.md](stages/reconstruction.md) |
| `analysis` (`ana`) | Summarizes charge collection efficiency and time resolution across finished jobs of requested scan points (if any scan point has no finished jobs, processes the remaining points and then exits with an error) | `raser.stages.analysis` | [stages/analysis.md](stages/analysis.md) |
| `status` | Checks job run status across scan points and stages of an experiment | `raser.lifecycle.status` | [lifecycle/slices.md](lifecycle/slices.md) |
| `signal` | Runs the single-device signal simulation workflow | `raser.bench.signal` | [bench/signal.md](bench/signal.md) |
| `cce` | Runs the charge collection efficiency experiment workflow | `raser.bench.cce` | [bench/cce.md](bench/cce.md) |
| `timeres` | Runs the time resolution experiment workflow | `raser.bench.timeres` | [bench/timeres.md](bench/timeres.md) |
| `tct` | Runs the transient current technique (TCT) laser pulse simulation workflow | `raser.bench.tct` | [bench/tct.md](bench/tct.md) |
| `telescope` | Runs the beam telescope (`taichu_v1`, `taichu_v2`) spatial resolution simulation workflow | `raser.bench.telescope` | [bench/telescope.md](bench/telescope.md) |
| `bmos` | Runs the Beam Monitoring Online System (BMOS) simulation workflow | `raser.apps.bmos` | [apps/bmos.md](apps/bmos.md) |
| `cflm` | Runs the CEPC Fast Luminosity Monitor (CFLM) 24-pad simulation workflow | `raser.apps.cflm` | [apps/cflm.md](apps/cflm.md) |

## Dispatch Mechanism and Global Options

### 1. Top-Level Global Options (Placed Before the Subcommand)

- `-h`, `--help`: Prints top-level help and exits; pass after a subcommand to see options registered by that subcommand (`raser <command> --help`).
- `--version`: Prints the current version (for example `raser 5.0`) and exits.
- `-b`, `--batch`: Submits job-supporting subcommands (workflows and stage commands) to the cluster; can be stacked as `-bb`, `-bbb`, etc., where the repeat count sets the requested memory tier (`8000` MB per tier).
- `-t`, `--test`: When combined with top-level `-b`, enables `--dry-run` on job-supporting subcommands.

### 2. Automatic Command Completion Inside an Experiment Directory

When the current working directory contains an experiment configuration file `config.json`, the first word of `"workflow"` in that config is registered, and the command-line arguments contain none of `-h`, `--help`, `--version`, or any token matching a registered command name or short alias, `raser` reads `"workflow"` (and `"device"` if present) from `config.json` in the current directory and inserts them automatically after the global options. Thus running `raser -s 2` inside an experiment folder (such as `work/HPK-Si-PiN/signal`) is equivalent to running `raser signal HPK-Si-PiN -s 2`.

### 3. Shared Run Options

All workflows and stage commands except `status` have shared run options registered by `lifecycle`:

- **Jobs and random seeds**: `-s` / `--jobs` sets the number of parallel jobs per scan point; `--seed` sets the run seed integer; `--same-seeds` makes jobs with the same index across scan points use the same random seed in corresponding slices and share slices whose inputs and dependencies did not change. These three options are registered only by seeded workflows (`Workflow.seeds=True`) and the four stage commands (`dep|cur|rdo|reco`).
- **Parameter setting and scanning**: `--set key=value` fixes a single parameter or a dotted path inside a component file; `--scan key=v1,v2,...` scans a parameter or a key path inside a file (normal experiment runs write to `config.json`; `--dry-run` previews and `raser field <experiment_dir>` only select points for the current invocation without writing `config.json`).
- **Cluster submission and preview**: `-b` / `--batch` and `-mem` (`8000 * mem` MB) submit cluster jobs; `--dry-run` prints pending scan points, jobs, and slice status (`raser field <experiment_dir>` prints whether each point's shared slice is ready) without starting computation.

Details of these shared options, configuration merge priority, and scan folder naming are in [lifecycle/experiments.md](lifecycle/experiments.md); cluster submission and job lock mechanisms are in [lifecycle/jobs.md](lifecycle/jobs.md).

### 4. Runtime Path Environment Variables

- `RASER_WORK_PATH`: Working root directory (defaults to `<repo_root>/work` in a source tree, or `<cwd>/work` in an installed package).
- `RASER_PROJECT_PATH`: When non-empty, explicitly specifies the current project root in `infer_project_root()`, overriding `<RASER_WORK_PATH>/<device>` inferred from a device name (standalone `deposit`, `current`, `readout`, and `reconstruction` commands given only a device name directly use `<RASER_WORK_PATH>/<device>/signal` and its project context).
- `RASER_COMPONENT_PATH`: Additional component search paths (joined by the OS path separator), searched before the built-in component directory `src/raser/components/` (see [supports/README.md](supports/README.md)).

## Common Errors

- `raser: <what>. <how>` (exit code `1`): Printed when `MissingDependency` is caught during command execution, or when an import raises `ModuleNotFoundError` with `error.name` equal to `"ROOT"` or `"cppyy"` (for example, missing `g4ppyy`, `ngspice`, or `ROOT`).
- `<target>: neither an experiment folder (a folder with a config.json) nor a device; give one of them, e.g. work/<device>/cce or HPK-Si-PiN` (exit code `1`): The argument passed to `raser dep|cur|rdo|reco` is neither an experiment folder containing `config.json` nor a matching device file.
- `<folder>: the experiment <workflow> has no <stage> slice; its slices: <names>` (exit code `1`): The target experiment's workflow does not include the requested stage.

## Related Pages

- [README.md](README.md)
- [getting-started.md](getting-started.md)
- [architecture.md](architecture.md)
- [lifecycle/experiments.md](lifecycle/experiments.md)
- [lifecycle/slices.md](lifecycle/slices.md)
- [lifecycle/jobs.md](lifecycle/jobs.md)
- [stages/README.md](stages/README.md)
- [supports/README.md](supports/README.md)
