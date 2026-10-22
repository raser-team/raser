# Indexed and cluster jobs

_RASER 5.0 execution mechanics in `src/raser/supports/jobs.py` and `batchjob.py`_

---

## 📋 Responsibility

Jobs expands one logical run into indexed local workers or cluster
submissions. The owning application supplies a structured command, worker
count, backend, resource request, destination, and shared run ID. The
application also supplies event physics, workflow defaults, and collection
metrics through its recorded configuration.

## ⚙️ Indexed execution

Every worker receives the same recorded run ID and one unique zero-based
index. Each worker command equals the normalized command followed by
`--job <index>`.

| Backend | Execution contract | Completion meaning |
| --- | --- | --- |
| Local | Invoke the active Python environment with bounded concurrency | Every worker exited successfully |
| Cluster | Write and submit one safely quoted `raser` command per index | Every requested job was accepted |
| Dry run | Return the worker and scheduler plans | Filesystem and scheduler remain unchanged |

Local concurrency is bounded by requested workers and available CPUs. Command
arguments remain a token sequence through local execution and planning; shell
quoting occurs once when the cluster job file is written.

## 📤 Cluster adapter

Real cluster submission requires the activated route to provide `IMGFILE`.
Generated jobs execute `raser` inside that Apptainer image and keep job files
and scheduler output under the active project.

Submission and worker execution are separate phases. A successful submitter
reports accepted indices. Worker completion and application collection produce
their own later records.

## 🔗 Boundary

The CLI exposes global batch routing while applications may request
workflow-owned indexed execution. Both use these mechanics with explicit
commands. Scheduled workers return through the same
[CLI route](../cli/raser.md) and read the existing [run record](runs.md).

## ⚠️ Failure contract

Non-positive counts or memory fail before execution. Local worker errors
propagate. Missing images, job-file errors, scheduler rejection, and partial
submission report accepted and pending indices before failing. Every retry
retains the run identity and normalized inputs.
