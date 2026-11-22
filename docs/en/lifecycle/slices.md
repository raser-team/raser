# Slices and Reruns

`src/raser/lifecycle/slices.py`, `src/raser/lifecycle/status.py`, `src/raser/lifecycle/workflow.py`, and `src/raser/stages/chain.py` manage dependencies among stages in the chain, result reuse, and `raser status`. They receive the scan points and sectioned configuration expanded by [Experiments, Scan Points, and Seeds](experiments.md) together with the stage composition declared by each experiment class; chain assembly is described in [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md). This module fingerprints each stage's inputs, decides which nodes are reused and which must be newly computed, and runs stages in dependency order within a single job. Jobs needing new computation are handed to [Jobs, Logs, Locks, Resuming, and Cluster Submission](jobs.md) to run locally or on a cluster; written nodes are read by downstream stages and [Statistical Analysis Stage (`stages/analysis`)](../stages/analysis.md).

## Behavior

### Stages in the Chain

There are eight stages in the chain, with equal standing. Each stage reads results written by its upstream stages:

| Stage | Upstream stage results read |
| --- | --- |
| `field` | None |
| `deposit` | None |
| `current` | `field`, `deposit` |
| `readout` | `field`, `current` |
| `digitizer` | `readout` |
| `trigger` | `digitizer` |
| `reconstruction` | `trigger` |
| `analysis` | `deposit`, `current`, `reconstruction` |

`field` and `deposit` are independent of each other and form the two roots of the chain. A device's field is an asset of that device, stored in `work/<device>/field/` and shared across all experiments on that device.

To run only up to a specific stage in the chain, invoke that stage's command, for example `raser readout [path]`, `raser digitizer [path]` (`digi`), or `raser trigger [path]` (`trig`). The program fills in missing upstream stages and stops at that stage. See [Command-Line Interface (`raser`)](../cli.md) for the command list.

### Nodes and Fingerprints

One result computed by a stage for a given set of inputs is a node, stored in `<experiment>/nodes/<stage>/<node_id>/`. `deposit` through `reconstruction` have one node per job, and `field` and `analysis` have one node per scan point; the upstream nodes of `analysis` are the per-job nodes of that point, so its fingerprint records which jobs it aggregated. A node's inputs consist of four items:

- the setting values used by this stage;
- the part of the component files used by this stage;
- the node IDs of its upstream nodes;
- the seeds of the measurement stages (`deposit`, `current`), as well as the own seeds of `readout` (NGspice noise) and `digitizer` (clock phase, aperture jitter), all derived from the job seed; the job seed is derived from the master seed, the job index, and the values of the measurement-related scan axes (see [Experiments, Scan Points, and Seeds](experiments.md#seeds)).

The fingerprint is computed from these inputs, and the fingerprint is the node ID. The node folder contains the files written by this stage and a `node.json`. `node.json` records the inputs verbatim, and additionally records the code version, runtime environment, and run status. A device's field is likewise a node, stored under `work/<device>/field/`.

Upstream node IDs are inputs to downstream stages. When a node changes, every stage that reads it directly or indirectly receives a new node ID, while the node IDs of all other stages remain unchanged. For example, changing only one setting in the `readout` section reuses the `field`, `deposit`, and `current` nodes as usual, while `readout` and the downstream `digitizer`, `trigger`, `reconstruction`, and `analysis` stages are computed as new nodes.

### Reuse

Nodes with the same fingerprint are reused regardless of which scan point or run computed them. Rerunning the same command verbatim (with the same `--seed`) directly reuses completed nodes and computes only the missing ones.

Nodes are append-only. Changing a setting back points the view back to the original node and reuses it directly. For example, changing the number of events per job from 20 to 40 computes everything into new nodes while leaving the old nodes intact; changing it back to 20 points the views back to the old nodes and reuses all of them directly.

### Sharing Nodes Across Scan Points

When a scan affects only downstream settings, upstream nodes are shared across scan points. Changing bias voltage is a new measurement, so each bias is measured separately.

Scan two things simultaneously on `signal`: `field.voltage=100,200`, and two values of a resistor in `readout`.

| Stage | Number of nodes | Reason |
| --- | --- | --- |
| `deposit`, `current` | 2 | Changing bias is a new measurement, so each bias is measured separately; only `readout` reads the resistor, so both resistor values share these two nodes |
| `readout` and downstream | 4 | Two bias values times two resistor values |

When `--same-seeds` is passed, jobs with the same index across scan points share random seeds, so upstream results unaffected by the scan are reused across points.

On each run, the program computes the parameter table `points.json` from `config.json`: one row per scan point, recording the values of all scan axes and the node ID used for each stage.

### Views

`<experiment>/points/<point>/<stage>/` is a folder containing one symlink per job at that scan point, named by the job index and pointing to that job's node at that stage; `field` and `analysis` have only one node per point, so `points/<point>/field` and `points/<point>/analysis` are symlinks directly. Point names are derived from scan-axis values, such as `voltage_100`, serving as human-readable entry points. After changing settings or adding a scan axis, the point name may stay the same while the node it points to updates accordingly, so parameters and results always match.

### Code Version

When the code version differs from the one recorded in a node, only a notice is printed and the result is still reused as usual.

### Locking

Each node is locked individually. A node being written carries a `.part` suffix and is renamed to its final name only when writing finishes, so every node with a final name is a complete result.

### Early Termination

When a stage leaves nothing computable for downstream stages, the job ends there. For example, if `deposit` records zero events, downstream stages are marked done directly.

### Checking Progress

`raser status [path]` prints the project's parameter table: the status and node ID of each experiment, scan point, and stage.

```bash
raser status work/my-PiN
```

Each cell shows the status and node ID of that point at that stage. Status is formatted as `<completed_jobs>/<total_jobs> done`, for example `2/2 done`; unfinished jobs are listed by job index grouped by status after a semicolon. A job has seven possible statuses:

- **`done`**: This job's result at this stage has finished writing.
- **`running`**: Currently running.
- **`submitted`**: Submitted to the cluster, and the scheduler confirms it is still on the cluster.
- **`uncertain`**: Submitted, but querying the scheduler failed or timed out after `120 s`, so its state cannot be confirmed.
- **`failed`**: Submitted but no longer found on the cluster while the result is unfinished; or a local job left a log without completing.
- **`waiting`**: An upstream stage has not finished writing, or a required field is not ready yet.
- **`not started`**: All upstream stages have finished writing, and this job has not been started, has not been submitted, and has no failure log.

Adding `--dry-run` before running prints only the scan points, stages, and job statuses to be run and returns immediately.

## Rules

### Propagation of Node IDs

1. A stage has only four inputs: the setting values used by this stage, the part of the component files it uses, the node IDs of the upstream nodes it directly reads, and the seeds of the measurement stages (`deposit`, `current`) as well as the own seeds of `readout` (NGspice noise) and `digitizer` (clock phase, aperture jitter).
2. The node ID is the fingerprint of these four inputs. The code version, runtime environment, and run status are recorded separately in `node.json`.
3. Upstream node IDs enter downstream inputs, so changes propagate downward along the table in "Stages in the Chain": when a stage's node ID changes, the node IDs of stages that read it change too, all the way to the end of the chain.

### Reuse and Sharing

1. Before computing a stage for a scan point, its node ID is computed first. If a node with that node ID already exists, it is reused directly.
2. If two scan points have identical inputs at a stage, their node IDs are identical and both points share that single node.
3. Nodes are append-only. Changing settings back restores the original node ID and points the view back to the original node.
4. When the code version differs from the one recorded in a node, the node is still reused as usual and only a notice is printed.

## Software Implementation

### Module and File Responsibilities

- `src/raser/lifecycle/slices.py`: Dependency queries among stages (who reads whom, transitive closure of upstream stages), and running stages one by one in dependency order within a single job.
- `src/raser/lifecycle/nodes.py`: The nodes themselves: the canonical form of the inputs and the fingerprint (`fingerprint`, `node_of`), job seeds and stage seeds (`job_seed`, `stage_seed`), locking and writing a node (`lock`, `start`, `finish`, `found`), view links (`link_view`) and the parameter table (`write_points`).
- `src/raser/lifecycle/workflow.py`: Deciding which results are reused and which are newly computed, coordinating sharing across scan points, and ordering scan-point execution.
- `src/raser/lifecycle/status.py`: The `raser status` subcommand.
- `src/raser/stages/chain.py`: Assembling the stages into the standard chain.

## Interface

### Options

| Option | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `raser status [path]` | None | None | Prints the project's parameter table: status and node ID of each experiment, scan point, and stage |
| `--seed` | None | None | Integer random seed to make simulation results reproducible |
| `--same-seeds` | Off | None | Makes jobs with the same index across scan points share random seeds so upstream results unaffected by the scan are reused across points |
| `--dry-run` | Off | None | Prints only the scan points, stages, and job statuses to be run and returns immediately |

`--set` and `--scan` use `"section.key"` as the address, for example `--set field.voltage=100` and `--scan field.voltage=100,200`; see [Experiments, Scan Points, and Seeds](experiments.md) for scan syntax.

### Files Read and Written

- `<experiment>/config.json`: Read-only in this module. Lists all settings used by the run, separated into the eight sections `field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, and `analysis`; see [Experiments, Scan Points, and Seeds](experiments.md) for the format.
- `<experiment>/points.json`: Parameter table. Computed from `config.json` on each run, one row per scan point, listing scan-axis values and the node ID used for each stage. Printed by `raser status`.
- `<experiment>/nodes/<stage>/<node_id>/`: Node directory. Contains the files written by this stage and `node.json`; carries a `.part` suffix while being written.
- `work/<device>/field/<node_id>/`: Device field node referenced by all experiments on that device.
- `<experiment>/points/<point>/<stage>/<job>`: View, a symlink pointing to that job's node at that stage; `points/<point>/field` and `points/<point>/analysis` are each a single symlink.

Formats of data files written by each stage inside its node are documented in [Field Solving and Loading (`core/field`)](../core/field.md), [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md), [Carrier Drift and Induced Current (`core/current`)](../core/current.md), [Electronics Readout (`core/readout`)](../core/readout.md), [Digitizer (`core/digitizer`)](../core/digitizer.md), [Trigger Stage (`stages/trigger`)](../stages/trigger.md), and [Event Reconstruction (`core/reconstruction`)](../core/reconstruction.md).

### Format of `node.json` and `points.json`

The node ID is the first `12` hex digits of the fingerprint; the fingerprint is the SHA-256 of the canonical JSON of the inputs. Canonical JSON: keys in alphabetical order, no spaces; a float with an integer value is written as an integer (`100.0` and `100` are the same value), other floats are kept as they are; a boolean is not a number; `NaN` and infinity raise an error. A file a component refers to by path (mesh, macro, `.cir`, GDML) enters the inputs as the SHA-256 of its content, not as its path.

Keys of `node.json`:

| Key | Type | In the fingerprint | Meaning |
| --- | --- | --- | --- |
| `stage` | string | no | Stage name |
| `node` | string | no | Node ID |
| `fingerprint` | string | no | Full fingerprint, `64` hex digits; checked before reuse, an error if the name matches and the fingerprint does not |
| `inputs.settings` | object | yes | Keys and values this stage reads from its section of `config.json` |
| `inputs.components` | object | yes | Slot → the part of the component file that is used |
| `inputs.upstream` | object | yes | Upstream stage read directly → node ID; fields are listed by slot; `analysis` lists the node IDs of the jobs of this point |
| `inputs.seed` | integer | yes | Seed of this stage, only for `deposit`, `current`, `readout`, `digitizer` |
| `job` | object | no | Job number `index` and master seed `master_seed` |
| `code` | string | no | Code version, with `+dirty` when the working tree has uncommitted changes |
| `environment` | object | no | Runtime environment |
| `state` | string | no | `running` (being written in `.part`), `done`, `ended` (upstream left nothing to compute, the node holds no data file), `failed` |
| `notes` | object | no | What the stage left after running |

What a stage records for itself goes under top-level keys of its own, such as `axes`, `read`, `solved` of `field`, merged with the keys above when written.

`points.json` is an object keyed by point name, with two entries per point: `values` holds the "section.key" and value of each scan axis; `nodes` holds the node IDs of each stage, one node ID for `field` and `analysis`, and a list of node IDs ordered by job number for `deposit` through `reconstruction`.

```json
{
  "voltage_100": {
    "values": {"field.voltage": 100},
    "nodes": {"field": "c41f0a9d2b7e", "deposit": ["3f9a0c1d22e4", "8b02e6f4a1c9"], "analysis": "e07d5b3a914c"}
  }
}
```

The lock file of a node is `.<node_id>.lock` beside the node directory.
