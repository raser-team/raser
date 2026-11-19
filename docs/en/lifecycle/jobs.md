# Jobs, Logs, Locks, Resuming, and Cluster Submission

`src/raser/lifecycle/jobs.py`, `src/raser/lifecycle/scheduler.py`, and `src/raser/lifecycle/workflow.py` manage splitting and running local and cluster jobs, job logs, three file locks, resuming interrupted runs, and submitting jobs with automatic resume on `hep_sub` or HTCondor clusters.

## Inputs

### Run Records and Submission Markers

- `<seed_or_point_folder>/run.json`: Each job reads `"options"`, `"files"`, `"seed"`, `"point"`, `"same_seeds"`, and `"held_in"` on startup; automatic resume after cluster job completion reads `"command"`, `"cwd"`, and `"waiting"`.
- `<seed_or_point_folder>/batch/<name>_<index>.submitted`: Records a slice (`job` for sliceless workflows) that has been submitted to the cluster and has not yet finished; its content is JSON containing `"job"` (cluster job ID) and `"time"` (submission timestamp `YYYY-MM-DD HH:MM:SS`).

### Environment Variables

Cluster planning, submission, and resuming read the following environment variables:

| Environment Variable | Default | Unit | Description |
| --- | --- | --- | --- |
| `RASER_SCHEDULER` | `"hep_sub"` | None | Cluster scheduler type; `"hep_sub"` or `"condor"` |
| `RASER_CONDOR_JOB_FLAVOUR` | `"workday"` | None | `+JobFlavour` written to `.sub` when `RASER_SCHEDULER=condor`; one of `"espresso"`, `"microcentury"`, `"longlunch"`, `"workday"`, `"tomorrow"`, `"testmatch"`, `"nextweek"` |
| `RASER_ENV_ROUTE` | Unset | None | Environment route name activated in a source tree on cluster nodes (runs `. env/setup_cvmfs.sh <route>` when set, or `. env/setup.sh` when unset) |
| `RASER_SUBMIT_QUEUE` | Unset | None | Path to the submission command queue file inside a container; when set, submission commands are appended to this file for the host to submit |
| `RASER_CLUSTER_JOB` | Unset | None | Exported as `"1"` in cluster job scripts to mark that the current process is running on a cluster worker node |
| `RASER_RESUBMIT_DEPTH` | `"0"` | count | Current recursion depth of automatic command relaunches upon cluster job completion |

## Outputs

### Local and Cluster Job Execution Modes

Depending on the command-line options and number of scan points, pending jobs are launched in one of the following ways:

- **Local single point, single job (`-s` omitted, `-b` not passed, only 1 scan point)**: Runs job `0` directly in the current process, writing output to both the terminal and `batch/job_0.log`.
- **Local multiple points, single job (`-s` omitted, `-b` not passed, multiple scan points)**: Spawns a separate subprocess for job `0` of each scan point, writing output to each point's `batch/job_0.log`; if one point fails, the remaining points continue first and errors are summarized afterward.
- **Local multi-job process pool (`-s <N>` passed, `-b` not passed)**: Runs pending job indices in parallel via `ProcessPoolExecutor`, with a maximum concurrency of `min(pending jobs, CPU core count)`, writing each job's output to `batch/job_<index>.log`.
- **Cluster batch submission (`-b` / `--batch` passed)**: Generates cluster scripts for each pending job and submits them via `hep_sub` or `condor_submit`.

### Job Logs `batch/job_<index>.log` and Exception Extraction

- Each locally executed job writes its log to `<seed_or_point_folder>/batch/job_<index>.log`.
- After a sliced workflow finishes all requested slices for the current run, it prints the normal completion marker `raser: the job ran its slices: <comma-separated list of slice names>` to stdout. When a local job exits with a non-zero exit code, the main command scans backward from the end of the log to extract the last Python exception line (skipping trailing Geant4/ROOT C++ output).

### What Happens in the Example

In the [Getting Started](../getting-started.md) example, running `raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1` launches two local parallel jobs (`0` and `1`) for each scan point, producing per-slice `.done` markers and job logs under `work/HPK-Si-PiN/signal/seed_1/batch/` (and `voltage_100/seed_1/batch/`):

1. **What `<slice>_<job>.done` looks like**:
   - `deposit_0.done`, `current_0.done`, `readout_0.done`, `reconstruction_0.done`, and the whole-job completion marker `job_0.done` are all empty files (the slices return nothing or no extra information).
   - `field_0.done` (and `field_1.done`) writes the shared field directory path as JSON (an absolute path is recorded during an actual run):

     ```json
     {"field": "work/HPK-Si-PiN/field"}
     ```

2. **What `job_<job>.log` looks like**:
   `work/HPK-Si-PiN/signal/seed_1/batch/job_0.log` records Geant4 initialization, carrier counts and plot file paths for each event, and prints the list of completed slices at the end (lengthy repetitive Geant4 and ROOT output is omitted below):

   ```text
   ...
   2026-11-18 21:47:43,887 - INFO - DevsimField initialization complete, resolution: {'z': 0.05, 'x': 10000.0, 'y': 10000.0} um
   2026-11-18 21:47:43,889 - INFO - current calculation start...
   2026-11-18 21:47:43,889 - INFO - carriers inside the detector: 27 electrons, 27 holes
   Info in <TCanvas::Print>: pdf file work/HPK-Si-PiN/signal/seed_1/plots/job_0/event_4/planar_drift_path.pdf has been created
   ...
   2026-11-18 21:48:15,582 - INFO - clusters stopped: collected 5726 (1.92481e+06 carriers), left_device 5226 (1.8019e+06 carriers)
   ...
   raser: the job ran its slices: deposit,field,current,readout,reconstruction
   ```

### Three File Locks (`fcntl.flock`)

RASER coordinates concurrent processes through non-blocking exclusive locks:

| Lock File Path | Held During | Purpose |
| --- | --- | --- |
| `<experiment_folder_parent>/.<experiment_folder_name>.config.lock` | Acquired after the initial lock-free read of `config.json` identifies the experiment directory (then re-reads `config.json`), and released after acquiring all point-folder locks and finishing writing `config.json` (`--dry-run` does not acquire locks) | Serializes concurrent commands reading, merging, and writing the same experiment's `config.json` |
| `<seed_or_point_folder_parent>/.<seed_or_point_folder_name>.lock` | Acquired before writing `config.json`, and released after jobs for all scan points have been launched or have finished running locally | Protects the seed or scan-point folder (placed alongside the folder so the lock remains valid even when a rerun renames the old folder) |
| `<seed_or_point_folder>/batch/job_<index>.lock` | Acquired at the entry of a single job process and released when the job exits | Prevents the same job index from running concurrently; checked before rerunning stale slices to ensure no job is currently running |

When the underlying filesystem does not support `flock`, a warning is printed to the terminal and execution continues.

### Cluster Job Scripts and Submission Files

`scheduler.plan_job` plans the job script `<command_name>.job` (truncated with a digest appended when longer than 200 bytes) and submission specification under `work/<device>/<command>/jobs/` and returns a `ClusterJobPlan`; `scheduler.main` writes the actual `.job` and `.sub` files outside preview mode. The script clears display environment variables, exports `RASER_CLUSTER_JOB=1`, filters X11 container bind mounts, activates the local or `/cvmfs` environment, and runs the job command; each job requests `8000 * batch_level` MB of memory.

- **`hep_sub` backend (default)**: Runs `hep_sub -o <job_dir> -e <job_dir> <job_file> -mem <memory_mb> -g <group_name>`.
- **`condor` backend (`RASER_SCHEDULER=condor`)**: Generates `<job_dir>/<command_name>.sub` and runs `condor_submit`.
- **Host submission queue (when `RASER_SUBMIT_QUEUE` is non-empty)**: Appends the submission command to that queue file so the host submits it centrally; commands waiting on upstream work must be run again manually once their dependencies finish.

### Resuming Runs and Automatic Cluster Resume

1. **Resuming locally and on login nodes**:
   - When rerunning with the same fixed seed `--seed <N>` or increasing the `-s` job count, as long as the old run and its slices are not stale and remain reusable, jobs and slices that already have `.done` markers are skipped directly and only newly added or unfinished parts are run.
   - In cluster mode, a successful submission creates a `.submitted` marker (removed on completion). When `-b` is run again on the login node, the scheduler is queried automatically: jobs still in the queue are skipped, jobs no longer in the queue are treated as failed and automatically resubmitted, and jobs are left as-is if the scheduler cannot be queried.
2. **Automatic resume on cluster worker nodes**:
   - After a cluster job adds at least one new slice completion marker (for sliced workflows) or finishes normally (for sliceless workflows), it automatically relaunches `"waiting"` entries recorded in `run.json` (such as commands waiting for a shared field solve); sliced workflows also relaunch this experiment's `"command"` (with `--seed-folder`) that is waiting on cross-point upstream slices. Each relaunch attempts up to 4 times (waiting 30 s only before a retry) with a bounded recursion depth; if the depth limit is reached or all 4 attempts fail to start, a message is printed so you can rerun the original command manually once the prerequisite jobs finish.

## Options

| Option | Default | Unit | Description |
| --- | --- | --- | --- |
| `-s`, `--jobs` | `None` (treated as `1`) | jobs | Number of jobs to run per scan point, with job indices `0 .. N-1` (registered by seeded workflows and the four stage commands) |
| `-b`, `--batch` | `False` (global count `0`) | None | Submit jobs to the cluster; global `-b`, `-bb`, etc. placed before the subcommand also sets `mem` to `max(mem, count of b)` |
| `-mem` | `1` | `8000 MB` | Memory tier requested per cluster job; requests `8000 * mem` MB |
| `-t`, `--test` | `False` | None | Global option placed before the subcommand; sets `dry_run` to true only when combined with top-level `-b` |
| `--dry-run` | `False` | None | Print the pending jobs and slices for each scan point and return immediately (`raser field <experiment_dir>` prints whether each point's shared slice is ready) |

## Common Errors

- `Running: <what> is run by another process now; run the command again when it is done`: The experiment configuration lock `.config.lock`, run folder lock `.<folder>.lock`, or single-job lock `batch/job_<index>.lock` is currently held by another process.
- `RuntimeError: Local jobs failed for indices <list>\n  job <index>: <last_line> (<log>)`: One or more jobs in the local process pool exited with a non-zero exit code; the error lists the failed indices, the last exception line extracted from each log, and the log path.
- `RuntimeError: the job failed: <last_line> (<log>)`: A scan point's subprocess exited with a non-zero exit code in local multi-point single-job mode.
- `RuntimeError: Cluster accepted indices <accepted>; failed indices <failed>` (`Cluster queued indices <accepted>; failed indices <failed>` when `RASER_SUBMIT_QUEUE` is set): Some job indices failed during batch cluster submission.
- `ValueError: Unknown scheduler: <scheduler>`: Environment variable `RASER_SCHEDULER` was set to a value other than `"hep_sub"` or `"condor"`.
- `ValueError: Unknown HTCondor job flavour: <flavour>`: When `RASER_SCHEDULER=condor`, environment variable `RASER_CONDOR_JOB_FLAVOUR` is not among the 7 allowed flavours.
- `ValueError: Indexed job count must be positive` / `ValueError: Indexed job memory level must be positive`: `plan_indexed_jobs` received job count `count <= 0` or memory tier `mem <= 0`.
- `ValueError: Batch memory level must be positive` / `ValueError: Batch worker command must contain tokens`: `scheduler.plan_job` received `batch_level <= 0` or an empty command token list.

## Related Pages

- [Getting Started](../getting-started.md)
- [Architecture Overview](../architecture.md)
- [CLI Overview](../cli.md)
- [Experiments and Scan Points](experiments.md)
- [Slices and Status Inspection](slices.md)
- [Paths and Runtime Supports](../supports/README.md)
