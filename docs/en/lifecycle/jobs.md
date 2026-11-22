# Jobs, Logs, Locks, Resuming, and Cluster Submission

`src/raser/lifecycle/jobs.py`, `src/raser/lifecycle/scheduler.py`, and the job-scheduling portion of `src/raser/lifecycle/workflow.py` receive experiment commands dispatched by [Command-Line Interface (`raser`)](../cli.md) and stage commands from [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md). After [Experiments, Scan Points, and Seeds](experiments.md) expands scan points and [Slices and Reruns](slices.md) determines which nodes must be newly computed, these three modules take over execution: they first solve any missing device fields, then split and launch indexed jobs as local processes or via the `hep_sub`/HTCondor cluster scheduler, write job logs and submission records, and resume after interruptions, failures, or completion of prerequisite jobs. Each individual job runs stages in dependency order; finished nodes are read by downstream stages, inspected by `raser status`, and reused by subsequent runs.

## Behavior

### Local Execution and Job Splitting

When `-b` is not passed, the main command executes pending jobs locally in one of three ways depending on the number of scan points and whether `-s` (`--jobs`) is given:

- **Single scan point with `-s` omitted**: Runs job `0` directly in the current process. If the job fails, the original exception propagates directly.
- **Multiple scan points with `-s` omitted**: Launches a separate subprocess for each scan point in turn to run job `0`. If one scan point fails, the main command prints its traceback, continues running the remaining scan points, and exits with a summary error after all finish:

  ```text
  1 of 2 points failed:
    <scan_point>: RuntimeError('the job failed: <exception_line> (<job_log>)')
  ```

  This means the subprocess for that job exited with a non-zero exit code. Open the job log in parentheses for the full traceback, fix the issue, and rerun the original command verbatim (with the same `--seed`); already completed nodes are reused by fingerprint.

- **`-s <count>` passed**: Whether there is one scan point or many, each scan point runs its pending jobs (job indices `0` through `<count> - 1`) in parallel using a local process pool (`ProcessPoolExecutor`). The maximum concurrency is $\min(\text{pending jobs},\, \text{CPU cores or } 4)$. If a job in the pool exits with a non-zero exit code, the remaining jobs run to completion, and the main command exits with an error summarizing the failed jobs' exception lines and log paths:

  ```text
  RuntimeError: Local jobs failed for indices [1]
    job 1: <exception_line> (<job_log>)
  ```

  This means the subprocess for that job in the pool returned a non-zero exit code. Open the job log in parentheses to diagnose, fix the issue, and rerun the original command verbatim so only unfinished nodes are computed.

Before launching jobs for scan points, if the device's field does not exist yet, the main command solves it locally first; fields with identical inputs are solved only once. If a field that was just solved locally is still judged unavailable, the main command aborts immediately:

```text
RuntimeError: <stage> was made in this process and is still not ready for a point of <experiment_folder>: waiting would not help
```

This means the newly solved field is missing results needed by the current scan point or failed validation. Inspect that field node's `node.json` and job log before rerunning.

Passing `--dry-run` prints only the scan points, stages, and job statuses to be run and returns immediately. For `raser field <experiment_folder>`, it prints whether each scan point's device field is `ready` or `to be made`.

As an example of a two-bias scan, the following command runs jobs `0` and `1` in parallel at each of the two bias points:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --seed 1
```

### Job Logs and Failure Summaries

Every locally executed job writes a job log.

- Independent subprocess mode and process-pool mode (multiple scan points or `-s` passed) merge the subprocess's stdout and stderr and write them to both the terminal and the job log.
- Current-process mode (single scan point with `-s` omitted) writes Python's stdout, stderr, and exception tracebacks to both the terminal and the job log; output printed directly from the C++ layer by Geant4 and ROOT appears only on the terminal.
- After a job finishes all stages requested in the current run, it prints the normal completion line `raser: the job ran its slices: <comma-separated stage names>` at the end of the log.
- When a local job fails, the main command scans backward from the end of the job log for the last Python exception line (an exception name ending in `Error`, `Exception`, `Exit`, or `Interrupt`), skipping C++ trailing lines flushed by Geant4 and ROOT on process exit, and includes it in the terminal error summary; if no line matches, it takes the last non-empty line.

### Node Locks

Each node is locked individually. A node being written carries a `.part` suffix and is renamed to its final name only when writing finishes, so every node with a final name is a complete result.

The lock is a non-blocking exclusive file lock (`fcntl.flock`). If the lock is already held by another process, the command prints only the line below and exits immediately:

```text
<target> is run by another process now; run the command again when it is done
```

This means another `raser` process is currently writing the same result. Wait for it to finish and rerun; you can check progress with `raser status`.

When the underlying filesystem does not support `flock` (the system call returns `ENOLCK`, `ENOTSUP`, `EOPNOTSUPP`, or `EINVAL`), the program prints a single warning line and continues running:

```text
warning: <lock_file> cannot be locked here (No locks available): nothing keeps another command off it
```

This means the network filesystem hosting the experiment directory does not support file locks, leaving concurrent writes unprotected. In that case, avoid issuing concurrent write commands to the same experiment manually; use read-only `raser status` or `--dry-run` to check progress.

### Cluster Submission and Host Submission Queue

When `-b` (`--batch`) is passed, the main command writes an executable script `<command_name>.job` (mode `0o755`) for each pending job and submits it via the cluster scheduler specified by `RASER_SCHEDULER`; if `-s` is omitted, job `0` is submitted. When written before the subcommand as a global option, `-b` can be stacked as `-b`, `-bb`, `-bbb`, etc., setting the memory tier to $\max(\text{-mem},\, \text{count of global } \texttt{b})$ and requesting $8000 \times \text{tier}\ \text{MB}$ of memory from the scheduler. Top-level `-t` (`--test`) takes effect only when given together with top-level `-b`, checking and previewing submission information without submitting.

Job scripts and submission files are stored in `<experiment>/jobs/`; see [Common Infrastructure (`supports`)](../supports/README.md) for path resolution. At the start of the script, login-node X11 environment variables are unset, `RASER_CLUSTER_JOB=1` is exported, and X11 bind entries are filtered out of container bind variables. When running from a source tree, the script first `cd`s to the repository root and sources `env/setup_cvmfs.sh <route>` (or `env/setup.sh` when `RASER_ENV_ROUTE` is unset); when running as an installed Python package, the script `cd`s to the working directory at submission time and inherits the scheduler environment.

As an example submitting two jobs requesting two memory tiers (`16000 MB`):

```bash
raser -bb signal HPK-Si-PiN -s 2 --seed 1
```

Under the default scheduler `hep_sub`, each job executes `hep_sub -o <jobs_dir> -e <jobs_dir> <job_file> -mem 16000 -g <current_dir_group>`. Under `RASER_SCHEDULER=condor`, an additional `<command_name>.sub` is generated and `condor_submit <sub_file>` is executed, with `.sub` contents like:

```text
executable = /.../examples/HPK-Si-PiN/signal/jobs/<command_name>.job
output = /.../examples/HPK-Si-PiN/signal/jobs/<command_name>.out
error = /.../examples/HPK-Si-PiN/signal/jobs/<command_name>.err
log = /.../examples/HPK-Si-PiN/signal/jobs/<command_name>.log
request_memory = 16000
getenv = True
+JobFlavour = "workday"
queue
```

When configuration validation fails or batch submission partially fails, the program reports errors at the corresponding trigger point:

- **`-mem` is `0` or negative**: Raises `ValueError: Indexed job memory level must be positive` (or `ValueError: Batch memory level must be positive` when calling `scheduler.plan_job` directly). Change `-mem` to a positive integer.
- **`RASER_SCHEDULER` is neither `"hep_sub"` nor `"condor"`**: Raises `ValueError: Unknown scheduler: <value>` before writing scripts or submitting. Change it back to `"hep_sub"` or `"condor"` and rerun.
- **`RASER_CONDOR_JOB_FLAVOUR` is not among the `7` allowed values**: In `condor` mode, raises `ValueError: Unknown HTCondor job flavour: <value>`. Set it to one of `"espresso"`, `"microcentury"`, `"longlunch"`, `"workday"`, `"tomorrow"`, `"testmatch"`, or `"nextweek"`.
- **Partial failure during batch submission**: The main command still attempts to submit the remaining jobs in the batch, and once all have been tried raises:

  ```text
  RuntimeError: Cluster accepted indices [0, 2]; failed indices [1]
  ```

  When `RASER_SUBMIT_QUEUE` is enabled, `accepted` in the message becomes `queued`:

  ```text
  RuntimeError: Cluster queued indices [0, 2]; failed indices [1]
  ```

  This means `hep_sub`/`condor_submit` returned non-zero or writing to the queue file failed for some jobs, while the other jobs succeeded. Inspect the chained original exception immediately following (such as temporary scheduler rejection, job quota exceeded, group permissions, or an unwritable queue path), resolve it, and rerun the original `-b` command. In direct submission mode, already accepted jobs have submission records and are skipped automatically.

When running inside a SIF container without scheduler client tools, the host wrapper sets `RASER_SUBMIT_QUEUE` to a temporary queue file. While this variable is non-empty, the program appends each submission command to the queue file so the host submits them line by line after the container command exits. Because cluster job IDs are unavailable when writing to the queue, the program skips recording the original command and prints before submitting:

```text
the jobs go to the queue the host submits: a job that waits for others is not started again by itself; run the command again when those are done
```

Skipping the original command record prevents the whole batch from being resubmitted repeatedly once jobs finish. After confirming via cluster tools or `raser status` that prerequisite device fields or upstream nodes have all completed, rerun the original command on the host. Because this mode skips writing submission records, rerunning the same `-b` command before queued jobs finish will enqueue duplicates.

### Submission Records and Automatic Cluster Resume

After submitting directly to the scheduler and matching `submitted to cluster (\d+)` in the scheduler's stdout, the main command atomically writes a submission record for that job containing the cluster job ID and submission timestamp:

```json
{"job": "123456", "time": "2026-11-22 04:30:00"}
```

Once the job finishes the corresponding stage on the cluster, it deletes this submission record automatically.

Cluster job scripts export `RASER_CLUSTER_JOB=1`. When a cluster job newly finishes at least one requested stage during its run, it automatically relaunches commands waiting on it in order before exiting:

1. **External waiting commands**: For example, when an experiment in `-b` mode triggers a missing device field solve (see [Field Solving Stage (`stages/field`)](../stages/field.md)), that experiment's command and working directory are recorded as waiting on the field job. When the field job finishes, it restarts that command in its original working directory and removes it from the waiting list once it exits with code `0`. The recursion depth limit is `8` levels.
2. **This experiment's own command**: During direct `-b` submission, the main command records the original command and working directory. This is used to automatically submit downstream scan points once shared upstream nodes finish. The command restarts in the recorded working directory. The recursion depth limit equals the number of stages in the chain.

Before each automatic relaunch, the job prints `starting the command again: raser <command>` and increments `RASER_RESUBMIT_DEPTH` by `1` in the subprocess environment. To handle another job finishing concurrently and still holding a lock, each relaunch tries up to `4` times, waiting `30 s` between consecutive attempts. Because the relaunch runs on a cluster node where `RASER_CLUSTER_JOB=1` remains set, jobs that already have submission records are skipped directly and only previously unsubmitted jobs are submitted.

When automatic resume fails or reaches the nesting depth limit, one of the following three lines appears at the end of the job's `.out` log:

```text
the command did not start again in 4 tries: give it again when the jobs it waits for are done
not starting the command again: <depth> starts deep, as many as the slices of the chain
not starting raser ...: 8 starts deep
```

The first line indicates that all `4` attempts (each `30 s` apart) returned non-zero, commonly because another job held the lock or the worker node lacked the runtime environment or scheduler client. The last two lines indicate that automatic relaunch reached its nesting depth limit (the number of stages in the chain for this experiment's command, or `8` levels for external waiting commands), so the program stopped intentionally to prevent cyclic submission. Check the output below each `starting the command again: raser ...` in `.out`/`.err` under `<experiment>/jobs/`; once prerequisite jobs complete, rerun the original command manually on a login node to continue.

### Resuming After Interruption

After an interruption or failure, rerun the same command verbatim (with the same `--seed`) to resume: completed nodes are reused by fingerprint, half-written nodes carry `.part`, and only nodes with final names count as results. When the code version differs from the one recorded in a node, only a notice is printed and the result is reused as usual.

On rerun, jobs already submitted to the cluster that have not yet finished are handled according to the scheduler's response. When rerunning `-b` on a login node, `hep_sub` queries via `hep_q -u <current_user>` and `condor` queries via `condor_q <cluster_job_id> -af ClusterId`, with a `120 s` timeout per query:

| Job situation | Local rerun | Login-node `-b` rerun | Cluster-node automatic resume |
| --- | --- | --- | --- |
| All requested stages are done | Skip | Skip | Skip |
| Not done, no submission record | Compute missing nodes | Submit | Submit |
| Not done, submission record exists, scheduler confirms still on cluster | Run directly | Skip, print `are submitted already` | Skip |
| Not done, submission record exists, scheduler confirms no longer on cluster | Run directly | Delete submission record and resubmit | Skip |
| Not done, submission record exists, scheduler error or `120 s` timeout | Run directly | Leave as is | Skip |
| Required device field or upstream node not done yet | Skip and print wait reason | Skip and print wait reason | Skip and print wait reason |

Terminal notices for each situation are shown below. `<location>` at the start of each line is the scan point of the job.

- **Still on the cluster**:

  ```text
  <location>: jobs [0, 1] are submitted already
  ```

  Those jobs are already queued or running on the cluster; the command skips them to avoid duplicate submissions—simply wait for them to finish.

- **Gone from the cluster**:

  ```text
  <location>: job 0 (123456) is no more on the cluster: it failed and is submitted again
  ```

  The scheduler confirmed that the job is no longer on the cluster while it remains unfinished. The program deleted the stale submission record and resubmitted it; the resubmitted job still reuses completed upstream nodes. Check the previous job's `.out`/`.err` under `<experiment>/jobs/` to diagnose the failure (for example, raise `-mem` if it was killed for exceeding memory).

- **Scheduler cannot be queried**:

  ```text
  <location>: job 0 (123456): the scheduler cannot be asked; left as it is
  ```

  Calling `hep_q` or `condor_q` failed, the command was not found, or it timed out after `120 s`; the program keeps the submission record and leaves the job unchanged. Switch to a login node with the scheduler client, check `RASER_SCHEDULER`, and rerun once the scheduler recovers; if you have confirmed manually that the job ended, remove its submission record and rerun.

- **Waiting on a device field or upstream node**:

  ```text
  <location>: jobs <job_index_list> wait for <dependency_description>; run the command again when it is done
  ```

  A required device field has not finished solving yet, or an upstream node being computed by another scan point has not finished writing yet. The command adds this scan point to the failed list and skips those jobs. With direct cluster submission, the prerequisite job normally relaunches automatically upon completion; when using the host submission queue, hitting the recursion limit, or encountering a lock held by another local process, wait for the prerequisite job to finish and rerun the original command.

## Rules

### Built-in Constants

The table below lists the built-in constants in `jobs.py`, `scheduler.py`, and the job-scheduling portion of `workflow.py`. They are hardcoded in the source:

| Constant | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| Default process-pool fallback concurrency | `4` | processes | `os.cpu_count() or 4` in `run_indexed_jobs` of `jobs.py`; maximum concurrent processes when CPU core count is unavailable |
| `_RAISED` | `^[A-Za-z_][\w.]*(Error\|Exception\|Exit\|Interrupt)\b` | None | `jobs.py`; regex scanned backward from the end of a log to match a Python exception line |
| Memory per tier | `8000` | $\text{MB/tier}$ | `memory_mb = 8000 * batch_level` in `plan_job` of `scheduler.py`; megabytes per memory tier |
| `_NAME_BYTES` | `200` | $\text{B}$ | `scheduler.py`; maximum UTF-8 byte length of cluster job script basename `command_name`; longer names truncate the prefix to `183` $\text{B}$ and append `_` plus a `16`-character hex SHA-256 digest |
| Script file permissions | `0o755` | None | `gen_job` in `scheduler.py`; permissions set on the written `<command_name>.job` |
| `allowed_flavours` | `{"espresso", "microcentury", "longlunch", "workday", "tomorrow", "testmatch", "nextweek"}` | None | `plan_job` in `scheduler.py`; allowed `+JobFlavour` values for the `condor` backend |
| Cluster job ID regex | `submitted to cluster (\d+)` | None | `submit_job` in `scheduler.py`; extracts the cluster job ID from scheduler stdout |
| Scheduler query timeout | `120` | $\text{s}$ | `timeout=120` in `job_alive` of `scheduler.py`; timeout for a single `hep_q` or `condor_q` call |
| `_WORKER_UNSET` | `("DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "APPTAINERENV_DISPLAY", "APPTAINERENV_XAUTHORITY", "SINGULARITYENV_DISPLAY", "SINGULARITYENV_XAUTHORITY")` | None | `scheduler.py`; the `7` display environment variables cleared with `unset` at the top of job scripts |
| `_WORKER_BIND_VARIABLES` | `("APPTAINER_BIND", "APPTAINER_BINDPATH", "SINGULARITY_BIND", "SINGULARITY_BINDPATH", "BINDPATH", "RASER_SIF_BIND", "RASER_SIF_EXTRA_BINDS")` | None | `scheduler.py`; the `7` container bind environment variables filtered to drop X11 mount entries in job scripts |
| `JOB_ENDED` | `"raser: the job ran its slices"` | None | `workflow.py`; normal completion line prefix printed after a job finishes all requested stages |
| `_STARTS` | `4` | attempts | `_run_again` in `workflow.py`; maximum number of automatic relaunch attempts after a cluster job ends |
| `_PAUSE` | `30` | $\text{s}$ | `_run_again` in `workflow.py`; wait time between consecutive automatic relaunch attempts |
| `_WAITING_DEPTH` | `8` | levels | `_start_again` in `workflow.py`; maximum recursion depth for automatically relaunching external waiting commands |
| Experiment resume depth limit | Number of stages in the chain | levels | `_start_again` in `workflow.py`; maximum recursion depth for automatically relaunching this experiment's command |
| Ignored lock `errno` set | `{ENOLCK, ENOTSUP, EOPNOTSUPP, EINVAL}` | None | `_lock` in `workflow.py`; error numbers for which unsupported `flock` prints only a warning and continues |

### Locking and Device Field Preparation

1. **Dispatching single-job entry**: A single-job process dispatched by the main command jumps directly into `_run_job` to execute that job.
2. **Locking (`_lock`)**: Opens the lock file and calls `fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)`:
   - on `BlockingIOError`, closes the handle and raises `Running(f"{what} is run by another process now; run the command again when it is done")`. `Running` inherits from `SystemExit` and exits after printing only this line;
   - on `OSError` with `error.errno` in `{ENOLCK, ENOTSUP, EOPNOTSUPP, EINVAL}`, prints `warning: <path> cannot be locked here (<error.strerror>): nothing keeps another command off it` and returns `None`; any other `OSError` propagates unchanged.
3. **Preview return**: When `kwargs["dry_run"]` is true, prints the plan and returns immediately.
4. **Preparing device fields (`_make_shared`)**:
   - iterates over the device fields required by all scan points, processing identical inputs only once;
   - invokes the solver entry point for any missing device field (in `-b` mode, also passes this experiment's command and working directory as waiting on it); if `Running` is caught, prints `f"{name}: {running}"` and continues so downstream scan points enter the waiting state;
   - when neither `-b` nor `--dry-run` is active, if the device field is still unavailable after solving finishes, raises `RuntimeError(f"{name} was made in this process and is still not ready for a point of {root}: waiting would not help")`.
5. **Executing scan points and summarizing**: Launches jobs for each scan point in turn. If any scan point fails, raises `SystemExit("\n".join([f"{len(failed)} of {len(todo)} points failed:", *failed]))` once all points have been processed.

When running `raser field <experiment_folder>` standalone, the entry point calls `workflow.make_shared`: it reads `config.json` read-only and expands scan points using the current config plus command-line `--set`/`--scan`; when `dry_run` is true, it prints `<root>: <name> ready|to be made for <options>` for each point, and otherwise invokes `_make_shared` directly.

### Scan-Point Scheduling and Job Launch

For each scan point, execution proceeds in the following order:

1. **Filtering out jobs waiting on prerequisites**: If a required device field is unavailable or an upstream node being computed by another scan point has not finished writing, those jobs are removed from the pending list, a waiting notice is printed, and the point is recorded in `failed`.
2. **Recording resume information**: Skipped when `-b` is set and `RASER_SUBMIT_QUEUE` is non-empty; when `-b` is set and `RASER_SUBMIT_QUEUE` is unset or empty, records the original command tokens stripped of internal resume arguments along with `os.getcwd()`, then calls `_not_submitted` to filter pending jobs:
   - keeps any job that has no submission record;
   - skips directly if a submission record exists and environment variable `RASER_CLUSTER_JOB` is non-empty;
   - if a submission record exists and `RASER_CLUSTER_JOB` is unset, reads `"job"` from the first record and queries `scheduler.job_alive(job)` with deduplicated caching by job ID: if `False`, prints `is no more on the cluster`, deletes all submission records for that job, and keeps it; if `None`, prints `the scheduler cannot be asked; left as it is` and skips it; if `True`, skips it silently;
   - after the loop, if any jobs were skipped, prints `<location>: jobs <sorted_skipped_job_indices> are submitted already`;
   - if no jobs remain after filtering, moves on to the next scan point.
3. **Three-way job launch (`_start`)**: Let `single = kwargs.get("jobs") is None and not kwargs["batch"]` and `alone = len(todo) == 1`:
   - **Current-process mode (`single and alone`)**: Calls `_run_job` directly inside `with _logged(<job_log>):`. `_logged` uses `_Both` to mirror `sys.stdout` and `sys.stderr` to both the terminal and the log file; on `BaseException`, writes `traceback.format_exc()` to the log before re-raising unchanged, and restores standard streams in `finally`.
   - **Independent subprocess mode (`single and not alone`)**: Builds the job's subcommand tokens and calls `_own_process`, which invokes `jobs._run_local_job(words, <job_log>)`. `_run_local_job` runs the current Python interpreter with `subprocess.Popen(..., stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)` to line-buffer and forward output to both the terminal and the log. On a non-zero exit code, calls `jobs.last_line(log)` (collects non-empty lines, returning `"no log"` if the file is missing or `"an empty log"` if empty, scans backward for the first line matching `_RAISED`, or falls back to the last line) and raises `RuntimeError(f"the job failed: {jobs.last_line(log)} ({log})")`.
   - **Local process-pool or cluster mode (`not single`)**: When `-b` is set and `RASER_SUBMIT_QUEUE` is non-empty, first prints the host-queue notice line. Then calls `jobs.run_indexed_jobs(..., count=len(left), use_cluster=kwargs["batch"], mem=kwargs["mem"], destination=<first_command_word>, indices=left, ...)`:
     - when `use_cluster=False`, launches `ProcessPoolExecutor(max_workers=min(len(plan.commands), os.cpu_count() or 4))` to run `_run_local_job` in parallel. After all tasks finish, if any raised an exception, formats `\n  job <index>: <last_line(log)> (<log>)` for each failed job with a log and raises `RuntimeError` (chained from the first underlying exception);
     - when `use_cluster=True`, calls `scheduler.main(destination, command, mem, is_test=False)` for each job in turn; on success records it in `accepted` and invokes the `submitted(index, getattr(plan, "job_id", None))` callback to write the submission record; on failure records it in `failed` and continues submitting the remaining jobs. After the loop, if `failed` is non-empty, chooses `"queued"` or `"accepted"` based on whether `RASER_SUBMIT_QUEUE` is non-empty and raises `RuntimeError` (chained from the first underlying exception).
4. **Multi-point error summary**: When `_start` raises `Exception`, re-raises immediately if there is only one scan point; if there are multiple, prints the traceback, appends `f"  {folder}: {error!r}"` to `failed`, and continues with the remaining scan points.

### Cluster Script Generation, Submission, and Status Querying

1. **Validating and generating the job plan (`jobs.plan_indexed_jobs`)**: Checks `count > 0` (otherwise raises `ValueError("Indexed job count must be positive")`) and `mem > 0` (otherwise raises `ValueError("Indexed job memory level must be positive")`). Builds `(*command_prefix, *tail, "--job-index", str(index))` for each index in `range(count)` (when `indices is None`) or `indices`, returning an `IndexedJobPlan`; when called with `dry_run=True`, `jobs.run_indexed_jobs` returns this plan directly. Helper `jobs.command_tail(argv, command_prefix, remove_options)` strips the matching prefix, `remove_options` (both `--opt val` and `--opt=val` forms), and `-b`, `--batch`, `--dry-run`.
2. **Planning a single job script and submission command (`scheduler.plan_job`)**:
   - checks `batch_level > 0` (otherwise raises `ValueError("Batch memory level must be positive")`) and non-empty `_tokens(command)` (otherwise raises `ValueError("Batch worker command must contain tokens")`);
   - computes requested memory `memory_mb = 8000 * batch_level` ($\text{MB}$) and output directory `directory = project_path(destination_subfolder, "jobs")`;
   - constructs `command_name = "_".join(command_tokens).replace("/", "_")`. If `len(command_name.encode()) > 200`, takes the first `16` hex characters of the SHA-256 of its UTF-8 bytes as `digest`, truncates the prefix to the first `183` bytes (`decode(errors="ignore")`), and forms `<prefix>_<digest>`;
   - sets `job_file = directory / f"{command_name}.job"` and `worker = ("raser", *command_tokens)`, and reads `RASER_SCHEDULER` (default `"hep_sub"`):
     - for `"hep_sub"`, obtains `group_name = group or grp.getgrgid(os.stat(".").st_gid)[0]`, builds `("hep_sub", "-o", str(directory), "-e", str(directory), str(job_file), "-mem", str(memory_mb), "-g", group_name)`, and returns `ClusterJobPlan`;
     - for `"condor"`, reads `RASER_CONDOR_JOB_FLAVOUR` (default `"workday"`), raising `ValueError(f"Unknown HTCondor job flavour: {flavour}")` if not in `allowed_flavours`; builds `submit_description` with absolute paths using `directory.resolve()` and `job_file.resolve()` (containing `executable`, `output`, `error`, `log`, `request_memory`, `getenv = True`, `+JobFlavour`, and `queue`), sets `submit_file = directory / f"{command_name}.sub"` and `submit = ("condor_submit", str(submit_file))`, and returns `ClusterJobPlan`;
     - for any other value, raises `ValueError(f"Unknown scheduler: {scheduler}")`.
3. **Generating the worker-node script (`scheduler.worker_script`)**:
   - after writing `#!/bin/bash`, records `raser_x11_sources` (`/tmp/.X11-unix`, `/tmp/.X11-unix/`, `$HOME/.Xauthority`, `${XDG_RUNTIME_DIR:-}`, `${XAUTHORITY:-}`, `${APPTAINERENV_XAUTHORITY:-}`, `${SINGULARITYENV_XAUTHORITY:-}`);
   - runs `unset` to clear the `7` variables in `_WORKER_UNSET`, then runs `export RASER_CLUSTER_JOB=1`;
   - iterates over the `7` variables in `_WORKER_BIND_VARIABLES`, splits non-empty values on `,`, filters out entries whose source path `${raser_bind%%:*}` matches `raser_x11_sources`, and re-exports them;
   - when `REPO_ROOT is not None` (source tree), runs `cd <REPO_ROOT> || exit 1` and then `. env/setup_cvmfs.sh <route> || exit $?` or `. env/setup.sh || exit $?` depending on whether `RASER_ENV_ROUTE` is non-empty; when `REPO_ROOT is None` (installed package), runs `cd <os.getcwd()> || exit 1`;
   - ends by executing `shlex.join(worker_command)`.
4. **Writing to disk and submitting (`scheduler.main`, `gen_job`, `submit_job`)**:
   - when `is_test=True`, only prints the script, optional `.sub` body, and submission command to stdout and returns `plan`;
   - when `is_test=False`, `gen_job` creates parent directories, writes `<command_name>.job` in UTF-8 (with trailing newline), and sets permissions `0o755`; if `submit_file` is present, writes `.sub` in UTF-8;
   - `submit_job` checks `RASER_SUBMIT_QUEUE`: when non-empty, appends `shlex.join(plan.submit_command) + "\n"` and returns `None`; when unset, calls `subprocess.run(plan.submit_command, shell=False, check=True, capture_output=True, text=True)`, prints `result.stdout` verbatim, extracts the job ID with `submitted to cluster (\d+)` (`None` if unmatched), and returns `replace(plan, job_id=...)`.
5. **Atomically writing submission records (`workflow._note_submitted`)**: Returns immediately when `job is None`. Otherwise formats the JSON line `{"job": <job>, "time": "<YYYY-MM-DD HH:MM:SS>"}\n`, writes a temporary file `<record_name>.<pid>.part` in the same directory, atomically links it into place via `os.link(part, path)` (catching `FileExistsError` if a record already exists and preserving the old record), and deletes `.part` in `finally`.
6. **Querying cluster job liveness (`scheduler.job_alive`)**: Depending on `RASER_SCHEDULER` (default `"hep_sub"`), runs `["hep_q", "-u", getpass.getuser()]` or `["condor_q", str(job_id), "-af", "ClusterId"]` in a subprocess with `timeout=120`. Returns `None` on `OSError`, `subprocess.TimeoutExpired`, or non-zero exit code; otherwise collects `words[0].split(".")[0]` across all output lines whose first token starts with a digit into set `held` and returns `str(job_id) in held`.

### Single-Job Execution and Automatic Cluster Resume

1. **Running stages**: After a single-job process enters `workflow._run_job`, it runs the stages requested for this invocation in dependency order, skipping any already finished.
2. **Wrapping up**: Removes submission records for completed stages; prints `f"{JOB_ENDED}: {','.join(wanted)}"`; calls `_start_again(..., progress=<whether requested stages were newly completed>)`.
3. **Automatic cluster resume (`_start_again` and `_run_again`)**:
   - returns immediately if `RASER_CLUSTER_JOB` is unset or `progress` is false;
   - reads the current recursion depth `depth = int(os.environ.get("RASER_RESUBMIT_DEPTH", "0"))`;
   - **External waiting commands**: Reads each waiting command's tokens in turn: if `depth >= 8`, prints `not starting raser <words>: <depth> starts deep`; otherwise calls `_run_again(words, entry["cwd"], depth)` and removes the entry from the waiting list when it returns `True`;
   - **This experiment's command**: If an original command is recorded, first checks `depth >= <number of stages in the chain>` and prints `not starting the command again: <depth> starts deep, as many as the slices of the chain` and returns if reached; otherwise calls `_run_again(<original command tokens>, <original working directory>, depth)`;
   - `_run_again(words, cwd, depth)` prints `starting the command again: raser <words>`, sets `RASER_RESUBMIT_DEPTH` to `str(depth + 1)` in the subprocess environment, and loops over `attempt` $\in \{0, 1, 2, 3\}$: sleeps `time.sleep(30)` before any retry after the first attempt, spawns a `raser` subprocess in `cwd` (`check=False`), and returns `True` immediately on exit code `0`; if all `4` attempts return non-zero, prints `the command did not start again in 4 tries: give it again when the jobs it waits for are done` and returns `False`.

## Software Implementation

### Module and Function Responsibilities

- `src/raser/lifecycle/jobs.py`: Plan construction for indexed jobs, trailing CLI option stripping, and local/cluster batch dispatch. `command_tail` strips the command prefix, `--batch`/`--dry-run`, and specified options; `plan_indexed_jobs` validates job count and memory tier to build `IndexedJobPlan`; `_run_local_job` and `last_line` handle subprocess execution, dual terminal/log writing, and extracting Python exception summaries while skipping trailing C++ lines; `run_indexed_jobs` submits serially to the cluster via `scheduler.main` or executes locally in parallel via `ProcessPoolExecutor` according to `use_cluster`, summarizing failed jobs.
- `src/raser/lifecycle/scheduler.py`: Cluster job directory resolution, script generation, scheduler submission, and live status querying. `job_dir` resolves `<experiment>/jobs/`; `plan_job` builds a `ClusterJobPlan` for `hep_sub` or HTCondor (including `200`-byte script name truncation and memory conversion); `worker_script` and `gen_job` generate `0o755` bash scripts that strip X11 variables and container binds and export `RASER_CLUSTER_JOB=1`; `submit_job` writes to the host queue `RASER_SUBMIT_QUEUE` or invokes the scheduler and parses the cluster job ID; `main` coordinates planning, previewing, writing, and submission; `job_alive` queries whether a job is still present via `hep_q` or `condor_q`; `run_cmd` provides generic external command preview and execution.
- `src/raser/lifecycle/workflow.py` (job scheduling, locking, logging, and resume portion): `Running` and `_lock` implement non-blocking file locking; `_make_shared` and `make_shared` deduplicate and trigger missing device field solves; `_start`, `_logged` (`_Both`), and `_own_process` implement three-way launching; `_run_job` executes a single job and prints `JOB_ENDED`; `_note_submitted` and `_not_submitted` manage atomic submission-record writes and login-node resubmission decisions; `_start_again`, `_run_again`, and `waited_for_by` implement automatic cluster relaunch and external waiting lists.

### Core Data Structures

| Data structure | Defined in | Field | Type | Unit | Meaning |
| --- | --- | --- | --- | --- | --- |
| `IndexedJobPlan` | `jobs.py` | `commands` | `tuple[tuple[str, ...], ...]` | None | Full command token tuple for each indexed job (ending with `--job-index <index>`) |
| `IndexedJobPlan` | `jobs.py` | `backend` | `str` | None | Execution backend, `"cluster"` or `"local"` |
| `IndexedJobPlan` | `jobs.py` | `destination` | `str` | None | Subdirectory name owning the job script directory (first command word) |
| `IndexedJobPlan` | `jobs.py` | `memory_level` | `int` | tiers (`8000 MB`) | Memory tier requested for cluster jobs (`as_dict()` exports these four fields) |
| `ClusterJobPlan` | `scheduler.py` | `job_file` | `Path` | None | Path to the generated executable cluster script `<command_name>.job` |
| `ClusterJobPlan` | `scheduler.py` | `worker_command` | `tuple[str, ...]` | None | Command tokens `("raser", *command_tokens)` executed on the worker node |
| `ClusterJobPlan` | `scheduler.py` | `submit_command` | `tuple[str, ...]` | None | Scheduler submission command tokens (`hep_sub ...` or `condor_submit ...`) |
| `ClusterJobPlan` | `scheduler.py` | `submit_file` | `Path \| None` | None | Path to HTCondor's `<command_name>.sub` (`None` for `hep_sub`) |
| `ClusterJobPlan` | `scheduler.py` | `submit_description` | `str \| None` | None | Contents of the `.sub` file (`None` for `hep_sub`) |
| `ClusterJobPlan` | `scheduler.py` | `job_id` | `str \| None` | None | Cluster job ID returned by the scheduler (`None` when unsubmitted, queued, or unmatched; omitted by `as_dict()`) |
| `Running` | `workflow.py` | Inherits from `SystemExit` | Exception class | None | Raised when a lock is held by another process; exits after printing one occupancy message line |
| `_Both` | `workflow.py` | `stream`, `log` | Text streams | None | Dual-write proxy writing simultaneously to the terminal stream and job log in current-process mode |

## Interface

### Options and Environment Variables

The only job and cluster parameters configurable by users are the command-line options and environment variables listed below. All other parameters (memory base `8000 MB` per tier, process-pool fallback concurrency `4`, `200 B` script basename truncation limit and `16`-character digest, `120 s` scheduler query timeout, `4` automatic resume retries at `30 s` intervals, `8`-level external waiting recursion limit, experiment resume recursion limit equal to the number of stages in the chain, and the lists of cleared X11 variables and filtered mount paths) are hardcoded in the code.

| Option or key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `-s`, `--jobs` | None (treated as `1`) | jobs | Number of parallel jobs per scan point, with job indices `0` through `<count> - 1` |
| `--dry-run` | Off | None | Prints only the scan points, stages, and job statuses to be run and returns immediately; for `raser field <experiment_folder>`, prints whether each device field is `ready` or `to be made` |
| `-b`, `--batch` (subcommand option) | Off | None | Submits pending jobs to the cluster; submits job `0` when `-s` is omitted |
| `-b`, `--batch` (top-level global option) | `0` (count) | tiers (`8000 MB`) | Placed before the subcommand, stackable as `-b`, `-bb`, `-bbb`, etc.; enables cluster submission with memory tier $\max(\text{-mem},\, \text{count})$ |
| `-mem` | `1` | tiers (`8000 MB`) | Memory tier requested per cluster job; must be a positive integer; actually requests $8000 \times \text{tier}\ \text{MB}$ |
| `-t`, `--test` (top-level global option) | Off | None | May only be placed before the subcommand and takes effect only together with top-level `-b`/`--batch`: checks and previews submission details only |
| `RASER_SCHEDULER` | `"hep_sub"` | None | Cluster scheduler backend: `"hep_sub"` (invokes `hep_sub`/`hep_q`) or `"condor"` (invokes `condor_submit`/`condor_q`) |
| `RASER_CONDOR_JOB_FLAVOUR` | `"workday"` | None | Effective only when `RASER_SCHEDULER=condor`, written as `+JobFlavour` in `.sub`; allowed values are `"espresso"`, `"microcentury"`, `"longlunch"`, `"workday"`, `"tomorrow"`, `"testmatch"`, `"nextweek"` |
| `RASER_ENV_ROUTE` | Unset | None | Read only when submitting cluster jobs from a source tree: if non-empty (e.g., `conda`, `ubuntu`, `el9`), the script runs `. env/setup_cvmfs.sh <route>`; if unset or empty, it runs `. env/setup.sh` |
| `RASER_SUBMIT_QUEUE` | Unset | None | Path to the host submission queue file (automatically set by the `raser` wrapper in `env/setup.sh` on the SIF route); when non-empty, appends submission commands to this file for host submission and skips recording the original command |
| `RASER_CLUSTER_JOB` | Unset | None | Automatically exported as `"1"` by cluster job scripts to indicate execution on a cluster worker node; enables automatic resume after job completion and skips jobs with existing submission records; normally set automatically by the program |
| `RASER_RESUBMIT_DEPTH` | `"0"` | levels | Current recursion depth of automatic cluster command relaunches, incremented by `1` per level; normally set automatically by the program |

When dispatching jobs, the main command also passes a hidden internal option `--job-index <job>`.

### Files Read and Written

- **Nodes**: Jobs write each stage's results into `<experiment>/nodes/<stage>/<node_id>/`; half-written nodes carry a `.part` suffix and are renamed to their final names upon completion. Each node is locked individually. See [Slices and Reruns](slices.md) for nodes and `node.json`.
- **Job logs**: One plain-text log per job recording stdout and stderr (current-process mode contains only Python-layer output and tracebacks). After finishing all requested stages, the job prints `raser: the job ran its slices: <comma-separated stage names>` at the end; on local job failure, `jobs.last_line` reads the summary from it.
- **Submission records**: JSON written after direct cluster submission obtains a job ID, containing two string fields: `"job"` (cluster job ID) and `"time"` (local time formatted as `YYYY-MM-DD HH:MM:SS`). Written first to `<record_name>.<pid>.part` in the same directory, atomically placed via `os.link`, and `.part` is then removed. Deleted once the corresponding stage finishes or the login node confirms the job has left the cluster.
- **`<experiment>/jobs/<command_name>.job`**: UTF-8 executable bash script (mode `0o755`) written by `scheduler.gen_job`. It clears X11 environment variables and container binds, exports `RASER_CLUSTER_JOB=1`, changes directory and activates the environment according to source-tree or package-install mode, and executes `raser <job_command>`.
- **`<experiment>/jobs/<command_name>.sub`**: UTF-8 HTCondor submission description written by `scheduler.main` only when `RASER_SCHEDULER=condor`, recording absolute paths for `executable`, `output`, `error`, and `log`, memory request `request_memory` (in $\text{MB}$), `getenv = True`, `+JobFlavour`, and `queue`.
- **`<experiment>/jobs/<command_name>.out`, `.err` (and `.log`)**: Cluster job stdout, stderr, and scheduler event logs (plain text). `hep_sub` writes `.out`/`.err` carrying the cluster job ID under `<jobs_dir>` via `-o`/`-e`; `condor` writes `<command_name>.out`, `<command_name>.err`, and scheduler log `<command_name>.log` as specified in `.sub`.
- **Queue file pointed to by `RASER_SUBMIT_QUEUE`**: UTF-8 text appended by `scheduler.submit_job`, one `shlex.join`-escaped scheduler submission command per line, submitted line by line by the host `raser` wrapper after the container exits.

See [Experiments, Scan Points, and Seeds](experiments.md) and [Slices and Reruns](slices.md) for `config.json` and `points.json`.
