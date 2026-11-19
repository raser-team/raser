# Slices, Staleness Checks, Completion Markers, and Status Inspection

`src/raser/lifecycle/slices.py`, `src/raser/lifecycle/status.py`, `src/raser/lifecycle/workflow.py`, and `src/raser/stages/chain.py` split each job by stage into slices (`Slice`), and manage inter-slice `needs` dependencies, slice input snapshots and staleness checks, `.done` completion markers, slice reruns, and `raser status` progress queries.

## Inputs

### Slice Definitions (`Slice` and `Shared`) and Simulation Chain Expansion

`Slice` (`src/raser/lifecycle/slices.py`) defines one execution segment of a single job:

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | Required | Slice name, corresponding to the prefix of its slice data file and `.done` marker file |
| `run` | `Callable` | Required | Execution function `run(options) -> dict \| None`; its return value is written to the slice's `.done` file |
| `keys` | `tuple` | `()` | Tuple of experiment option names that directly affect this slice's output |
| `kinds` | `tuple` | `()` | Tuple of component file kinds that directly affect this slice's output |
| `new_events` | `bool` | `True` | Whether scanning options of this slice generates independent events; when `True` (without `--same-seeds`), each scan point runs its upstream slices independently; when `False`, scan points share the same upstream slices |
| `shared` | `Shared \| None` | `None` | Cross-experiment shared resource interface (containing the three callbacks `ready`, `start`, and `stamp`) |
| `needs` | `tuple \| None` | `None` | Tuple of upstream slice names whose outputs this slice directly reads; `None` means the preceding slice in the list, and `()` means no upstream slice dependencies |

`src/raser/stages/chain.py` constructs the slice sequence for the standard simulation chain:

- Single device, single position:

| Slice Name | `needs` | `keys` | `kinds` | `new_events` | `shared` |
| --- | --- | --- | --- | --- | --- |
| `deposit` | `()` | `source`, `g4setup`, `events_per_job`, `generated_per_job`, `generated_limit`, `edep_min`, `edep_max`, `fano` | `source`, `g4setup` | `True` | `None` |
| `field` | `()` | `voltage`, `irradiation` | `()` | `True` | [`field.SHARED`](../stages/field.md) |
| `current` | `("deposit", "field")` | `plots` | `()` | `True` | `None` |
| `readout` | `("current", "field")` | `amplifier`, `sheet_resistance` | `()` | `False` | `None` |
| `reconstruction` | `("readout",)` | `threshold`, `amplitude_threshold`, `fractions`, `edge` | `()` | `False` | `None` |

- Multiple devices or multiple positions: the first slice is `deposit`; each device gets its own field slice (named `field.<device>` when there is more than 1 device, each with its own shared field interface); each position generates `current.<position>`, `readout.<position>`, and `reconstruction.<position>` in order.

### Dependency Propagation and Parameter Ownership

Each slice traces backward along `needs` to all of its upstream slices: any option or component file read by the slice itself or by any of its upstream slices is recorded in that slice's input snapshot under `run.json["slices"]`. Keys not explicitly assigned to a specific slice (such as `device.*`) belong to all root slices (`deposit` and `field`).

### Run Records and On-Disk Marker Files

Staleness checks, slice reruns, and `raser status` read the following files and keys:

- `<experiment_folder>/config.json`: Reads experiment settings and scan lists.
- `<seed_or_point_folder>/run.json`: Reads `"slices"` (each slice's parameter snapshot and shared slice digest), `"held_in"` (the scan-point directory where each slice is actually stored), `"commit"`, `"settings"`, `"seed"`, `"point"`, `"same_seeds"`, `"jobs"`, and `"waiting"`.
- `<slice_holder_folder>/batch/<slice_name>_<index>.done`: Completion marker and optional JSON return value for a single job on the corresponding slice.
- `<seed_or_point_folder>/batch/job_<index>.done`: Completion marker indicating that all slices of a single job have finished.
- `<seed_or_point_folder>/batch/job_<index>.lock`, `batch/job_<index>.log`, `batch/<slice_name>_<index>.submitted`: Read by `raser status` to determine real-time job status (see [Jobs and Cluster Submission](jobs.md)).

## Outputs

### Stage Slice Data Files `batch/<slice_name>_<index>.h5`

Each slice reads and writes its slice data files under `batch/` in the folder holding that slice (specified by `held_in`):

| File Path | Written by Slice |
| --- | --- |
| `batch/deposit_<job>.h5` | [`deposit`](../stages/deposit.md) |
| `batch/current_<job>.h5` or `batch/current.<position>_<job>.h5` | [`current`](../stages/current.md) / `current.<position>` |
| `batch/readout_<job>.h5` or `batch/readout.<position>_<job>.h5` | [`readout`](../stages/readout.md) / `readout.<position>` |
| `batch/reconstruction_<job>.h5` or `batch/reconstruction.<position>_<job>.h5` | [`reconstruction`](../stages/reconstruction.md) / `reconstruction.<position>` |

### Completion Markers `batch/<name>_<index>.done` and Outputs Set Aside as `.stale`

- **Slice completion marker `batch/<slice_name>_<index>.done`**: Written under `batch/` in the folder holding the slice. An executed slice writes `.done.part` first and atomically replaces it: an empty file when there is no return value, or JSON when a value is returned (for example, the `field` slice records the shared field directory path, a multi-position run with no depositions at a position records `{"events": 0}`, and early termination on zero depositions records `{"ended": true}`); downstream slices skipped because an upstream slice `ended` create an empty `.done` marker directly via `touch()`.
- **Whole-job completion marker `batch/job_<index>.done`**: Once all slices of the job have finished, an empty `batch/job_<index>.done` is created under the current seed or scan-point folder.
- **Outputs set aside as `.stale`**: If `run.json` is modified by another concurrent command while a slice is running, the newly generated slice output is renamed to `<original_filename>.stale` and the user is prompted to rerun the command.

### Staleness Checks and Slice Reruns

On each command invocation, the program compares the newly computed input snapshots and shared slice digests for all slices against the existing `run.json`:

- Only slices whose input snapshot or shared slice digest changed—along with their downstream slices—have their `.done` markers cleared and are rerun in place. A slice displays `reused` only when its inputs are unchanged and all requested job indices already have `.done` markers; otherwise it displays the pending job indices.
- If CLI `settings` changed, or all non-shared slices need to rerun, or (under the default check when no custom `outdated` callback is provided) the code `commit` changed, contains uncommitted changes `+dirty`, or any other recorded field changed, the entire run is marked stale (for example, the `field` workflow checks only CLI `settings`, options, device `"field"` configuration, and the device values actually read by the solver): seeded runs rename the old seed directory to `<label>_<YYYY_mmdd_HHMMSS>` and keep it aside, while unseeded runs replace it in place.

### What Happens in the Example

In the [Getting Started](../getting-started.md) example, first run with `--dry-run`:

```bash
raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1 --dry-run
```

The terminal prints the pending slices and job indices for each scan point:

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
work/HPK-Si-PiN/signal/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
```

This output shows:

- The experiment expands into two scan points: `100 V` corresponds to `voltage_100/seed_1`, and the default bias `200 V` corresponds to `seed_1` under the experiment root.
- Each scan point runs two jobs (`0` and `1`), and each job passes sequentially through five slices: `deposit`, `field`, `current`, `readout`, and `reconstruction`. Before launching jobs, `field` checks whether the shared field in `work/HPK-Si-PiN/field/` is ready; when it is not ready, `raser field` is invoked automatically to solve the `100 V` and `200 V` fields, and the shared field digest (`"23679e6b10596a26"` in `seed_1/run.json` of the example) is written into `"shared"` for `field` and its downstream slices `current`, `readout`, and `reconstruction`.
- Because `voltage` belongs to the `field` slice (and `--same-seeds` is not enabled), the two bias points each store their own outputs for all 5 slices independently (all 5 slices map to the empty string `""` in `held_in`).

After all jobs finish, run `raser status work/HPK-Si-PiN/signal` to inspect progress:

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
work/HPK-Si-PiN/signal/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
```

Both jobs for both scan points have completed every slice (`2/2 done`).

### `raser status <experiment>` Status Definitions

`raser status` inspects `.done`, `.lock`, `.submitted`, `.log`, and shared-slice readiness for each job of every slice (or sliceless workflow), classifying each job into one of the following 7 statuses (while also noting cases such as missing `run.json`, runs that are `out of date` compared to the current `config.json`, or runs `waited for by` other commands):

| Status | Condition |
| --- | --- |
| `done` | `batch/<slice>_<i>.done` exists under the folder holding that slice (`batch/job_<i>.done` for sliceless workflows) |
| `running` | Not done, and another process currently holds `batch/job_<i>.lock` in that folder |
| `submitted` | Not done and not running locally, `batch/<slice>_<i>.submitted` exists, and the cluster scheduler confirms the job is still in the cluster |
| `uncertain` | `batch/<slice>_<i>.submitted` exists, and the cluster scheduler cannot be queried (command error or timeout exceeding 120 s) |
| `failed` | `batch/<slice>_<i>.submitted` exists but the scheduler confirms the job is no longer in the cluster (the `.submitted` file is automatically deleted); or `batch/job_<i>.log` exists and, for a sliced workflow, the log is missing the normal completion line `"raser: the job ran its slices"` |
| `waiting` | An upstream slice has unfinished jobs; for scan points requested by the current `config.json`, also `waiting` when a required shared slice is not ready yet (extra on-disk points discovered outside `config.json` check only upstream slices and marker files) |
| `not started` | All upstream slices are done (or there are no upstream slices), and the job has not been started, has not been submitted, and has no failure log |

## Options

| Command / Argument | Default | Unit | Description |
| --- | --- | --- | --- |
| `raser status <experiment>` | Required | None | Inspect job progress across scan points and slices under the experiment folder `<experiment>` (such as `work/<device>/<command>`) |
| `raser deposit <target>` (alias `dep`) | Required | None | Run `<target>` (an experiment folder, or `work/<device>/signal` for a device name) up through the `deposit` slice |
| `raser current <target>` (alias `cur`) | Required | None | Run the simulation chain of `<target>` up through the `current` (or all `current.<position>`) slice(s) |
| `raser readout <target>` (alias `rdo`) | Required | None | Run the simulation chain of `<target>` up through the `readout` (or all `readout.<position>`) slice(s) |
| `raser reconstruction <target>` (alias `reco`) | Required | None | Run the simulation chain of `<target>` up through the `reconstruction` (or all `reconstruction.<position>`) slice(s) |

The stage commands `raser deposit|current|readout|reconstruction` also accept all options of that stage and its upstream stages (see [CLI Overview](../cli.md)) as well as the shared run options in [Experiments and Scan Points](experiments.md).

## Common Errors

- `SystemExit: <target>: neither an experiment folder (a folder with a config.json) nor a device; give one of them, e.g. work/<device>/cce or HPK-Si-PiN`: The `<target>` passed to a stage command is neither an experiment folder containing `config.json` nor a matching device file (only `FileNotFoundError` is caught; if the target exists but is not a readable device file, the original exception propagates).
- `SystemExit: <folder>: the experiment <workflow> has no <stage> slice; its slices: <names>`: The target experiment's workflow slice list does not contain the requested `<stage>`.
- `ValueError: no slice <until> in <named>`: The requested cutoff slice name `until` matches neither the full name of any slice in the current workflow nor the stage-name prefix before the first `.` of any slice.
- ``FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>` ``: No ready electric field matching the device, bias voltage, and irradiation fluence was found when executing the `field` slice.
- `RuntimeError: <piece.name> was made in this process and is still not ready for a point of <root>: waiting would not help`: After the local process finished building a shared slice, the shared slice is still not ready.
- `RuntimeError: <piece.name> of job <index> needs <earlier.name>, which is not done in <folder>`: During slice startup checks, an upstream slice is missing its `.done` marker in its holding folder.
- `RuntimeError: run.json changed while <piece.name> of job <index> ran: its output is set aside as .stale and not marked done; run the command again`: `run.json` was modified by a concurrent command while the slice was running, so the newly generated output file has been renamed to `.stale`.
- `SystemExit: <k> of <n> points failed:\n  <folder>: jobs <waiting> wait for <needed>`: A shared slice or cross-scan-point upstream slice needed by jobs of a scan point has not finished yet.
- `SystemExit: <k> of <n> points failed:\n  <folder>: jobs <running> run there now; the new settings did not take effect there; run the command again when they are done`: When a run folder needs to rerun stale slices, running jobs inside that folder still hold `batch/job_<i>.lock`.

## Related Pages

- [Getting Started](../getting-started.md)
- [Architecture Overview](../architecture.md)
- [CLI Overview](../cli.md)
- [Experiments and Scan Points](experiments.md)
- [Jobs and Cluster Submission](jobs.md)
- [Field Stage](../stages/field.md)
- [Deposit Stage](../stages/deposit.md)
- [Current Stage](../stages/current.md)
- [Readout Stage](../stages/readout.md)
- [Reconstruction Stage](../stages/reconstruction.md)
- [Analysis Stage](../stages/analysis.md)
