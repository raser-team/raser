# Jobs

_Local and cluster execution in `src/raser/lifecycle/jobs.py` and `scheduler.py`_

---

## Input

One command in [Run records](runs.md#run) creates a seed folder for every point.
The computation of a seed folder is then split into several jobs, numbered from
0; `-s 4` means 4 jobs per seed folder.

| Option | Meaning |
| --- | --- |
| `-s <n>` | Number of jobs; 1 when omitted |
| `-b` | Submit to the cluster; run on this machine when omitted |
| `-mem <n>` | Memory of a cluster job in units of 8 GB; 1 by default |

## Run

Take `raser cce HPK-Si-PiN -s 4 --seed 42`. RASER first creates the seed folder
`seed_42/`, then generates and executes one internal command for each of the 4
jobs:

```bash
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 0
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 1
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 2
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 3
```

With a scan, the seed folder of every point has such a set of jobs.

A job reads all its inputs from [`run.json`](runs.md#output) in the seed folder.

**Local**: the jobs run in parallel as separate processes; the number running
at once is at most the number of jobs and the number of CPUs.

**Cluster**: every job gets a job script, which is then submitted. The script
enters the RASER directory, activates the environment again, and executes the
job command; scripts and scheduler output are kept in `work/<application>/jobs/`.

| Environment variable | Meaning |
| --- | --- |
| `RASER_SCHEDULER` | `hep_sub` (default) or `condor` |
| `RASER_CONDOR_JOB_FLAVOUR` | HTCondor JobFlavour; `workday` by default |

## Output

A job writes its products to `batch/` of the seed folder and, when it finishes,
a `job_<index>.json` with the finish time and commit:

```text
work/HPK-Si-PiN/cce/seed_42/
├── run.json
└── batch/
    ├── job_0.json
    └── stats_0.root
```

Running the same seed folder again runs only the unfinished jobs.

A workflow with a summary writes it to `analysis/` after all local jobs end. After cluster jobs
end, `--collect` summarises; [Run records](runs.md#output) shows where:

```bash
raser cce HPK-Si-PiN --collect
```

## Failure

A non-positive job count or memory value fails before anything runs. Failed
local jobs are reported by index; a failed cluster submission reports the
accepted and the failed indices.
