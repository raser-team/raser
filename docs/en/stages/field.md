# Field Solving Stage (`stages/field`)

This stage is driven by `raser field [path]` (short alias `raser fld`; see [Command-Line Interface (`raser`)](../cli.md)), and also stands at the front of the eight-stage simulation chain (`field`, `deposit`, `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, `analysis`) in [Simulation Chain and Stage Entry Points (`stages`)](README.md) alongside the [Energy Deposition Stage (`stages/deposit`)](deposit.md). This stage invokes DEVSIM to solve (or imports from Sentaurus TDR files) the device's electric potential, electric field, carrier concentrations, trapping rates, conductive-region flags, readout electrode weighting fields, IV/CV/noise curves, and annotated device parameter circuit diagrams (junction capacitance, coupling capacitance, undepleted layer) at a given bias voltage and irradiation fluence; it also supports drawing meshes and doping on mesh nodes via `raser field --draw <object>`. Solved fields are stored as device assets keyed by input fingerprint in shared field nodes under `work/<device>/field/nodes/<node_id>/` (or `examples/<device>/field/nodes/<node_id>/` when running examples in place), recorded by node ID in each experiment's `points.json` parameter table and referenced via the `points/<point>/field` symlink view (see [Architecture Overview](../architecture.md#results) for result layout). It delivers electric fields, weighting fields, conductive regions, and trapping rates to the [Carrier Transport and Induced Current Stage (`stages/current`)](current.md) for carrier drift, and delivers the device parameter circuit diagram together with junction capacitance, inter-strip capacitance, and undepleted-layer parameters to the [Electronics Readout Stage (`stages/readout`)](readout.md) to assemble the device equivalent circuit; whenever the field node ID changes, those downstream stages as well as the [Digitization Stage (`stages/digitizer`)](digitizer.md), [Trigger Stage (`stages/trigger`)](trigger.md), [Event Reconstruction Stage (`stages/reconstruction`)](reconstruction.md), and [Statistical Analysis Stage (`stages/analysis`)](analysis.md) compute new nodes accordingly.

## Behavior

### Standalone Solving, Import, Plotting, and Per-Experiment Completion

When running `raser field [path]` (or `raser fld [path]`) standalone, omitting the path uses the current folder, while providing a path accepts either a relative or an absolute path. Passing `--draw <object>` draws only the mesh and the doping on mesh nodes; for normal solving, the command distinguishes two target types depending on whether the target path belongs to an experiment (contains an experiment `config.json`):

- **Device or project path**: Locates the device definition according to the rules in [Device Model (`core/device`)](../core/device.md) (using the project folder's own device file if present, or searching the built-in [Detector Components (`components/device`)](../components/device.md) when given only a name), and solves or imports the field node under `work/<device>/field/nodes/<node_id>/` (or `field/nodes/<node_id>/` under the corresponding project root). Device geometry lives in the device file, while meshes belong to `field`: a single device can have multiple meshes, and which one is used is specified by settings in the `field` section. Solver switches—IV sweep, single-point capacitance, weighting field, noise, UMFPACK linear solver, TCAD import, and its coordinate flip—are also settings in the `field` section, modified with `--set field.<key>=<value>`. When combined with `--set` or `--scan`, settings are addressed as `"section.key"` (such as `field.voltage`, `field.irradiation_flux`, `field.mode`).
- **Experiment folder path**: When an experiment `config.json` exists under the target, the command reads its experiment class definition, device, and sectioned configuration, switches to the experiment's project root and component paths, and checks and completes any unready shared field nodes scan point by scan point. Passing `--scan` or `--set` filters only the points prepared by this invocation (leaving the experiment's `config.json` untouched); passing `--dry-run` prints only whether each point's shared field is `ready` or `to be made`.

Passing the shared field folder itself as the target aborts immediately:

```text
<folder>: this is the field itself; give its device, raser field <device>
```

Cause: the target passed is the shared field folder itself. Pass the device name shown at the end of the error (`raser field <device>`) instead.

Minimal example: after creating a project with `raser new --from HPK-Si-PiN work/my-PiN`, preview whether the shared fields for all scan points of the experiment are ready, then compute single-point small-signal capacitance on the saved `200.0V.devsim` (`--set field.<key>=<value>` enables the single-point capacitance switch in the `field` section):

```bash
raser field work/my-PiN/signal --dry-run
raser field my-PiN --set field.voltage=200 --set field.<key>=<value>
```

The first command prints `<experiment_folder_abspath>: field ready for <options>` or `to be made` for each scan point. The second command loads `200.0V.devsim`, writes `200.0V.cv.json`, records `200.0` under solved `capacitance`, and prints the written point record dictionary to the terminal:

```text
{'voltage_V': 200.0, 'specific_capacitance_pF': ..., 'per': 'cm^2', 'area_factor': 0.0169, 'frequency_Hz': 1000.0}
```

### Three Solving Paths and Subtasks

Every non-`--dry-run` field-solving job first checks `field.mode`, then dispatches according to the `field` section settings along one of three paths: external TCAD import, HEMT DC transport, or standard DEVSIM solving. When `field.mode` is `"fast"` and `devsim` is not installed, the job prints `devsim is not installed: the field of <det_name> is found in the fast mode, not the full one` at startup. Only `"full"` mode is currently implemented; when `field.mode` is `"semi_fast"` or `"fast"`, it immediately raises:

```text
NotImplementedError: the <mode> mode of a field is not there yet: only field.mode 'full' is
```

Cause: only `"full"` mode is implemented at present. Set `field.mode` to `"full"` in an environment where DEVSIM is installed.

Behavior of the three solving paths:

- **External TCAD import**: Skips the DEVSIM bias sweep, imports bulk fields and conductive regions from a Sentaurus TDR (HDF5) file, and solves the weighting potential of each readout electrode on that mesh; after writing to disk and updating `axes`, `read`, and `solved` records, prints `<field_dir>: the field of <TCAD_FILE> at <bias> V` and ends the job.
- **HEMT DC transport branch**: When the device JSON sets `hemt_physics.transport_model == "drift_diffusion_v1"`, dispatches to the standalone 2D HEMT DC transfer-characteristic solver, prints `<det_name> is solved by its own transport solver: only its DC sweep is run, without CV, weighting field or noise` (appending `; <switches> dropped` and discarding those switches if the single-point capacitance, weighting-field, or noise switches are also enabled), writes `HEMT_TRANSPORT_*` outputs, and ends the job.
- **Standard DEVSIM solving**: Determines the subtasks to run in the fixed order `iv` → `cv` → `wf`. Before launching DEVSIM, the job checks `"solved"` in the node record (the checkpoints saved as DEVSIM ramps from 0 V to the target bias and the completed subtasks); one field node corresponds to one target bias, and intermediate bias files stored inside the node are checkpoints along the ramp. Any subtask whose target bias is already in the corresponding list is skipped. If all requested subtasks are already complete, the job prints `<field_dir>: already solved` and exits; when multiple subtasks execute sequentially, DEVSIM device state is cleared between them while preserving the selected linear solver parameters.

| Subtask enabled in `field` section | What it does | `solved` keys checked and recorded |
| --- | --- | --- |
| None of the three enabled (full solve) | Sweeps from `0 V` to the target bias (including CV curve along the sweep), solves the single-point capacitance at the target bias, then solves weighting fields for all readout electrodes | `"potential"`, `"undepleted"`, `"capacitance"`, `"weighting"` |
| IV sweep | Sweeps from `0 V` to the target bias and plots the IV curve | `"potential"`, `"undepleted"` |
| Single-point capacitance | Loads the saved `<V>V.devsim`, solves single-point small-signal capacitance, and writes `<V>V.cv.json` | `"capacitance"` |
| Weighting field | Reads `Conductive_<V>V.pkl` at the same bias and solves weighting fields for all readout electrodes (single-unit-cell strip electrodes also compute inter-strip mutual capacitance) | `"weighting"` |

If the single-point capacitance subtask cannot find the corresponding `<voltage>V.devsim` state archive in the directory, the job aborts with:

```text
FileNotFoundError: no field saved at <voltage> V in <folder>: <have>
```

Cause: single-point capacitance relies on the `<V>V.devsim` archive saved during a bias sweep. Run `raser field <device> --set field.voltage=<voltage>` for an IV sweep or full solve to save that bias first, then compute single-point capacitance.

If the weighting-field subtask cannot find the conductive-region file at the same bias, the job aborts with:

```text
FileNotFoundError: the weighting field at <v_goal> V needs the field solved at that bias: <conductive_file> is missing; solve it with `raser field <simname> --set field.voltage=<v_goal>`
```

Cause: weighting-field solving requires `Conductive_<V>V.pkl` at the same bias to merge conductive regions. Solve the electric potential at that bias as prompted, then solve the weighting field.

### Shared Field Completion, Waiting, and Handoff in the Simulation Chain

In benchmark, application, or downstream stage commands (such as `raser signal`, `raser current`, `raser readout`, `raser digitizer`, `raser trigger`, `raser reconstruction`, `raser analysis`), each experiment is a Python class inheriting from the `raser` experiment base class that declares its stages, devices, and device roles. Before launching experiment jobs, the main command deduplicates shared field requirements across scan points and checks each with `ready`; for any unready field, it prints `solving the field first: raser field <device> --set field.voltage=<V> ...` and solves it first in an isolated single-job process (running locally or submitted to the cluster with `-b` following the main command, leaving existing `field` configurations intact).

If another process is currently solving the same shared field node (node lock contention), the main command prints `<stage>: <locked_target> is run by another process now; run the command again when it is done`, and downstream experiment jobs enter a waiting state (downstream jobs likewise wait when a cluster `-b` shared field job has not yet completed):

```text
<folder>: jobs <waiting> wait for <name>, shared with other experiments; run the command again when it is done
```

Cause: the shared field node required by that scan point is not yet ready or is being solved by another process. In local runs, wait until the other process finishes and rerun the original command; in cluster `-b` mode (when not using a host submission queue), completion of the field job automatically relaunches the waiting downstream experiment command—see [Jobs, Logs, Locks, Resuming, and Cluster Submission](../lifecycle/jobs.md) for job logs and automatic cluster resume.

If the shared field is still reported as unready after `raser field` completes inside the local process, the main command aborts immediately:

```text
RuntimeError: field was made in this process and is still not ready for a point of <root>: waiting would not help
```

Cause: the just-completed field solve is missing the bias voltage or assets required by the current scan point. Inspect the field solve logs and node record to identify what is missing.

Once the shared field node is ready, the experiment records that scan point's `field` node ID in `points.json` and points the view symlink `points/<point>/field` to `work/<device>/field/nodes/<node_id>/`. When a job executes the `field` stage check, it verifies readiness again; if no ready field matching the current bias voltage and irradiation fluence is found, the job aborts with:

```text
FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>`
```

Cause: the shared field has not been solved, lacks the potential or weighting field at that bias, or the device file changed in the meantime. Run `raser field <det_name>` (with `--set field.voltage=<value>` or `--set field.irradiation_flux=<value>` if needed) or rerun the original chain command to complete it.

Minimal example: in the [Getting Started](../getting-started.md) example, when the field nodes of `HPK-Si-PiN` have not yet been solved, running:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

causes the main command to print before launching signal jobs:

```text
solving the field first: raser field HPK-Si-PiN --set field.voltage=100.0
solving the field first: raser field HPK-Si-PiN --set field.voltage=200.0
```

The program launches two single-job processes sequentially to solve the `100 V` and `200 V` fields, storing the results under `field/` of the `HPK-Si-PiN` project, with each target bias as its own field node:

- Each field node's `node.json` records its inputs (setting values of the `field` stage and the parts of the device read), code version, runtime environment, and run status.
- Together, the two nodes write bulk-field `.pkl` files (`Potential`, `Electrons`, `Holes`, `TrappingRate_n`, `TrappingRate_p`, `Conductive`, and `NetDoping_0V.pkl`), `.devsim` and `.dd` archives for `0V`/`100.0V`/`200.0V`, `HPK-Si-PiN.dat`, `0.0V`/`100.0V`/`200.0V.undepleted.json` (both `100.0 V` and `200.0 V` are fully depleted, so `undepleted_width_um` and `specific_resistance_ohm_cm2` are `0.0` and `specific_capacitance_pF` is `null`), `weightingfield/top/Potential_100V.pkl` and `Potential_200V.pkl` with the weighting-field plots in `plots/`, and device parameter circuit diagram assets annotated with junction capacitance, coupling capacitance, and undepleted-layer values.
- The curve data are `simIV0to100.0.root`, `simIV0to200.0.root`, `simCV0to100.0.root`, `simCV0to200.0.root`; the 1D profile plots are all in `plots/`, each with `.png` and `.pdf`: `iv`, `cv`, `doping`, and `electric_field_0V`, `electric_field_100V`, `electric_field_200V`, `potential_0V`, `potential_100V`, `potential_200V`, `weighting_potential_top_100V`, `weighting_potential_top_200V`, `weighting_field_top_100V`, `weighting_field_top_200V` (no irradiation, so no trapping-rate plots).
- The experiment records the `field` node IDs for the `voltage_100` and `voltage_200` scan points in `points.json`, and points the symlinks `points/voltage_100/field` and `points/voltage_200/field` to their corresponding field nodes (use `raser status` to inspect the status and node ID of each stage at each point in the parameter table).
- The field folder has a human-readable view of its own: `field/points/voltage_100` and `field/points/voltage_200` link to these two nodes, and `field/points.json` records the bias, irradiation flux, field mode and node ID of each point.

![HPK-Si-PiN IV curve](../../images/field/iv-HPK-Si-PiN.png)

Dark current (IV) curve of `HPK-Si-PiN` from the reverse bias sweep.

![HPK-Si-PiN CV curve](../../images/field/cv-HPK-Si-PiN.png)

CV curve of `HPK-Si-PiN` capacitance versus reverse bias voltage.

![HPK-Si-PiN 200 V 1D electric field profile](../../images/field/efield-HPK-Si-PiN-200V.png)

1D electric field profile of `HPK-Si-PiN` along depth at `200 V` bias.

### Node Fingerprint Reuse, Staleness Notices, and Downstream Propagation

A field node's identity is determined by its input fingerprint (see [Slices and Reruns](../lifecycle/slices.md) and [Architecture Overview](../architecture.md#nodes)):

- **Input fingerprint and append-only storage**: The inputs of a `field` node consist of the setting values used by this stage (bias voltage, irradiation fluence, field mode, selected mesh and its file's SHA-256, UMFPACK linear-solver switch, SHA-256 of the TCAD import file, etc.) and the part of the device component file used by `field` (including the device `"field"` section and the device attributes and JSON keys recorded via `Reading` during solving); the `field` fingerprint is computed solely from these two inputs. Because bias voltage is in the fingerprint, each bias voltage is its own field node: solving an additional bias adds a new node while existing bias nodes and experiments reading them continue to be reused. The fingerprint computed from these inputs is the node ID. Any existing field node with a matching fingerprint is reused regardless of which point or run produced it. Nodes are append-only: changing a setting produces a new node while keeping the old one; reverting the setting points `points.json` and the `points/<point>/field` view back to the old node.
- **Per-node locking and `.part` suffix**: Each node is locked individually. A partially written field node carries the `.part` suffix and is renamed to its final node name only upon completion, so final node names always hold complete results.
- **Views and point names**: nodes are kept in `field/nodes/<node_id>/`; people look at `field/points/<point>`, which links to the node of that point now, and `field/points.json` records the bias, irradiation flux, field mode and node ID of each point. A point is named by these three, written as `<key>_<value>` in the order `irradiation_flux`, `mode`, `voltage` and joined by `_`, the values written as in the point names of an experiment: the bias always; the irradiation flux only when it is not the one of the device file; the field mode only when it is not `"full"`. For example `voltage_200`, `irradiation_flux_1e+15_voltage_200`. When what the field reads from the device file changes, the same point name gets a new node and the view links to it, the old node staying in `nodes/`; changed back, the view links to the old node again. `raser field` and the fields an experiment solves first update the views.
- **Notice-only code version mismatch**: Code version, runtime environment, and run status are recorded separately in `node.json` and excluded from the fingerprint. When the current code version differs from the one recorded in `node.json`, only a notice is printed and the existing field node is still reused.
- **Downstream stage propagation**: Downstream stages include the node IDs of their upstream nodes in their own input fingerprints. When the `field` node switches to a new node ID due to changed inputs, the fingerprints of dependent stages (`current`, `readout`, `digitizer`, `trigger`, `reconstruction`, `analysis`) change accordingly and produce new nodes, while `deposit` nodes depend only on their own inputs and are reused as usual.

## Rules

### Built-in Constants

The table below lists the built-in constants and hardcoded thresholds related to the field stage in `src/raser/stages/field/__init__.py`, `src/raser/core/field/`, and `src/raser/lifecycle/workflow.py`:

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `HAS_DEVSIM` | `importlib.util.find_spec("devsim") is not None` | None | `core/field/solved.py` (imported by `stages/field/__init__.py`); whether `devsim` is installed in the current environment |
| `DEFAULT_MODE` | `"full"` if `HAS_DEVSIM` is true, else `"fast"` | None | `core/field/solved.py` (imported by `stages/field/__init__.py`); mode used when `ready` calls `solved_field` to look up a shared field |
| Fallback fluence without irradiation | `0` | $\text{cm}^{-2}$ | `core/device/build_device.py`, `core/field/solved.py`; default fluence when the device JSON has no `"irradiation"` section |
| `per` dimension mapping | `{1: "cm^2", 2: "cm", 3: "device"}` | None | `_capacitance` in `stages/field/__init__.py`; normalization basis for specific capacitance written into `<voltage>V.cv.json` according to `my_d.dimension` |
| Default `area_factor` | `1.0` | 1D $\text{cm}^2$, 2D $\text{cm}$, 3D dimensionless | `_capacitance` in `stages/field/__init__.py`; default conversion factor when `area_factor` is omitted from the device JSON |
| Preserved DEVSIM parameters | `("direct_solver", "solver_callback")` | None | `_empty_devsim` in `stages/field/__init__.py`; global parameter names preserved across `devsim.reset_devsim()` |
| `_STARTS` | `4` | attempts | `_run_again` in `lifecycle/workflow.py`; maximum attempts to relaunch a waiting command after a cluster job completes |
| `_PAUSE` | `30` | $\text{s}$ | `_run_again` in `lifecycle/workflow.py`; delay between retry attempts when relaunching a waiting command on a cluster |
| `_WAITING_DEPTH` | `8` | levels | `_start_again` in `lifecycle/workflow.py`; maximum recursion depth for chained cluster relaunches of waiting commands (`RASER_RESUBMIT_DEPTH`) |

### Entry Routing and Target Resolution

When executing `raser field [path] [options...]`, routing proceeds in the following order:

1. **Establish project context**: `register` attaches the execution entry point to the parser. `cli/raser.py` infers the target's project root and enters `project_root_context` (see [Common Infrastructure (`supports`)](../supports/README.md) for path resolution; omitting the path uses the current folder). If `--draw <object>` is present, draw the mesh and doping on mesh nodes directly and return.
2. **Detect target type (`run(kwargs)`)**: Check whether an experiment `config.json` exists under the target path:
   - **False (device name or device path)**: Locate `work/<device>/field/` (or the current `field` directory) and enter field-node solving using the `field` section settings.
   - **True (existing experiment folder)**: Read the experiment's `config.json`.
3. **Reject the field folder itself**: If the target is itself a field folder, raise `SystemExit(f"{folder}: this is the field itself; give its device, raser field {config['device']}")`.
4. **Prepare shared fields for an experiment**: Load the corresponding experiment class definition from `config.json`, enter that experiment's project root and component context, and invoke `make_shared`:
   - Expand target scan points from the experiment's sectioned `config.json` together with any `--set` or `--scan` passed on the command line (using `"section.key"` addresses such as `field.voltage`), leaving the experiment's `config.json` **unchanged**.
   - Collect the shared field requirements across all scan points.
   - If `kwargs["dry_run"]` is true: check `ready(options, files) is not None` point by point, print `f"{root}: {piece.name} {state} for {options}"` (`state` is `"ready"` or `"to be made"`), and return.
   - Otherwise call `_make_shared` to solve all unready shared field nodes.

### Node Fingerprint, Locking, and Process Launch

When solving a field node, input checking, locking, and job-process launch follow this order:

1. **Extract fingerprint items for solver switches (`settings(kwargs)`)**: Initialize `imported = None`; if TCAD import is enabled (`kwargs.get("input") is not None`), compute the full 64-character lowercase hexadecimal SHA-256 digest of `Path(kwargs["input"]).read_bytes()` and assign it to `imported`. Return `{"umf": bool(kwargs.get("umf")), "imported": imported}`; when neither UMFPACK nor TCAD import is enabled, this is `{"umf": False, "imported": None}`.
2. **Check node fingerprint and reuse**: Hash the setting values used by the `field` stage (including `settings`, the selected mesh, and its file's SHA-256 hash) together with the parts of the device component file read by `field` (the device `"field"` section, plus device attributes and top-level and first-level nested JSON keys recorded into `"read"` by `Reading`) to produce `<node_id>`:
   - If the corresponding field node already exists under `work/<device>/field/nodes/<node_id>/` and has completed solving, reuse it directly; if the current code version differs from `node.json`, print a notice and still reuse the result.
   - If solving or completing subtasks is needed, acquire an individual lock on that node (partially written nodes carry the `.part` suffix and are renamed to their final name upon completion) and record inputs, code version, runtime environment, and run status in `node.json`.
3. **Launch job and build child command (`job_command(kwargs)`)**:
   - For a single target without `jobs` and without `-b`, call `_run_job` directly in the current process through `_logged`; for multiple targets or `jobs=1` (passed by chain `start` so DEVSIM loads only in a separate subprocess or cluster job) without `-b`, spawn an isolated subprocess; with `-b`, submit to the cluster.
   - When launching an isolated subprocess or cluster job, `job_command(kwargs)` builds the child command `raser field <path>` and passes this node's `field` section settings (bias voltage, solver switches, absolute path of the TCAD import file, etc.) to it via `--set field.<key>=<value>`.

### Job Solving Dispatch

Holding the node lock, a field-solving job enters `solve(kwargs)` and executes in the following strict order:

1. **Validate `field.mode`**:
   - If `kwargs["mode"] == "fast"` and `not HAS_DEVSIM`, print `f"devsim is not installed: the field of {kwargs['det_name']} is found in the fast mode, not the full one"`.
   - If `kwargs["mode"] != "full"`, raise `NotImplementedError(f"the {kwargs['mode']} mode of a field is not there yet: only field.mode 'full' is")`.
2. **External TCAD import branch**: If `kwargs["input"] is not None`, call `_import(kwargs)`:
   - Construct `my_d = Detector(kwargs["det_name"], kwargs["_files"]["device"])`;
   - Call `bias = tcad.import_field(kwargs["input"], my_d, kwargs["_run_path"], kwargs["bias"], kwargs["flip"])` to import bulk fields, generate conductive regions, solve weighting fields for each readout electrode, and update `axes`, `read`, and `solved` in the node record;
   - Print `f"{kwargs['_run_path']}: the field of {kwargs['input']} at {bias} V"` and return immediately (skipping `_solved` checks and UMFPACK loading).
3. **HEMT DC transport branch**: Read `physics = kwargs["_files"]["device"].get("hemt_physics", {})`. If `physics.get("transport_model") == "drift_diffusion_v1"`:
   - Collect the enabled single-point capacitance (`kwargs["cv"] is not None`), weighting-field (`kwargs["wf"]`), and noise (`kwargs["noise"]`) switches into `dropped`;
   - Print `f"{kwargs['det_name']} is solved by its own transport solver: only its DC sweep is run, without CV, weighting field or noise"` (appending `f"; {' '.join(dropped)} dropped"` when `dropped` is non-empty);
   - Call `_ramp_or_weighting({**kwargs, "noise": False}, cv=False, wf=False)` and return immediately.
4. **Select linear solver and resolve bias and solver config**:
   - If `kwargs["umf"]` is true, import `devsim.umfpack.umfshim` to set this process's DEVSIM linear solver to UMFPACK.
   - `_bias(kwargs)`: returns `float(kwargs["bias"])` ($\text{V}$) if `kwargs["bias"] is not None`, otherwise `Detector(kwargs["det_name"], kwargs["_files"]["device"]).voltage` ($\text{V}$).
   - `_solver(kwargs)`: deep-copies `core/field/solver_section.SOLVER` and recursively deep-merges `kwargs["_files"]["device"].get("field", {}).get("solver", {})` on top of it (recursively merging when both sides of a key are `dict`, otherwise replacing directly).
5. **Plan subtasks and skip completed ones**:
   - Build `named` in order: add `"iv"` if `kwargs["iv"]`, `"cv"` if `kwargs["cv"] is not None`, and `"wf"` if `kwargs["wf"]`.
   - Set `cv_at = _bias(kwargs)` (when `kwargs["cv"] is True`) or `kwargs["cv"]` ($\text{V}$).
   - Call `_solved(kwargs, asset, at)` to read `"solved"` from the current field node record and evaluate:
     - `have["iv"] = _bias(kwargs) in solved.get("potential", [])`;
     - `have["cv"] = cv_at in solved.get("capacitance", [])`;
     - `have["wf"] = _bias(kwargs) in solved.get("weighting", [])`.
   - Set `left = [part for part in (named or ["iv", "cv", "wf"]) if not have[part]]`. If `left` is empty, print `f"{kwargs['_run_path']}: already solved"` and return.
6. **Solve remaining subtasks sequentially and reset DEVSIM state**: Iterate `done, part in enumerate(left)`:
   - When `done > 0`, call `_empty_devsim()`: read `"direct_solver"` and `"solver_callback"` if present in `devsim.get_parameter_list()`, call `devsim.reset_devsim()`, and restore those two parameters in DEVSIM.
   - When `part == "cv"`, call `_capacitance(kwargs)`:
     1. Set `my_d = Detector(kwargs["det_name"], kwargs["_files"]["device"])`, `voltage = _bias(kwargs)` (when `kwargs["cv"] is True`) or `float(kwargs["cv"])` ($\text{V}$), and `folder = Path(kwargs["_run_path"])`;
     2. Call `value, frequency = saved_point.capacitance(my_d, folder, voltage, _solver(kwargs))` to load `folder / f"{float(voltage)}V.devsim"` (raising `FileNotFoundError` if missing);
     3. Build `point = {"voltage_V": voltage, "specific_capacitance_pF": value, "per": {1: "cm^2", 2: "cm", 3: "device"}[my_d.dimension], "area_factor": float(my_d.device_dict.get("area_factor", 1.0)), "frequency_Hz": frequency}`;
     4. Write `point` to `folder / f"{voltage}V.cv.json"`, call `save_solved(str(folder), "capacitance", voltage)` to update the node record, and print `point`.
   - When `part` is `"iv"` or `"wf"`, call `_ramp_or_weighting(kwargs, cv=not named, wf=(part == "wf"))`, merging `target=kwargs["det_name"]`, `bias=_bias(kwargs)`, `cv`, `wf`, `solver=_solver(kwargs)`, and `_field_directory=kwargs["_run_path"]` before passing to `solver_section.main`.
7. **Atomic persistence and cluster wakeup**: After `solve` returns, finalize the partially written `.part` node and update its run status. When running in a cluster job environment (`RASER_CLUSTER_JOB` is non-empty), `_start_again` reads the list of downstream commands waiting on this field: for each waiting entry, if `RASER_RESUBMIT_DEPTH < _WAITING_DEPTH` (`8`), it retries up to `_STARTS` (`4`) times at intervals of `_PAUSE` (`30` $\text{s}$) with depth `+1` to re-execute `raser <command>` under `entry["cwd"]`, removing the entry from the waiting list once relaunch succeeds.

### Shared Field Checking, Completion, and Handoff in the Simulation Chain

The eight-stage simulation chain and multi-device experiments interact with shared field nodes through `chain.py` and `stages/field` in the following steps:

1. **Experiment class assembly and device view switching (`_of`)**:
   - Each experiment class declares its stages, devices, and device roles (such as device under test and reference device), without specifying setting values. Along the chain, `current` reads `deposit` and `field` nodes, `readout` reads `current` and `field` nodes, followed sequentially by `digitizer`, `trigger`, `reconstruction`, and `analysis`. Multi-device experiments switch configuration and component views to the corresponding device via `_of(kwargs, device)`.
2. **Resolve run irradiation fluence (`_flux_of_run(my_d, options)`)**: If the `field` section specifies an irradiation fluence, return `float(...)` ($\text{cm}^{-2}$); otherwise return `float(my_d.irradiation_flux)` (`0.0` $\text{cm}^{-2}$ when there is no irradiation section).
3. **Check shared field node readiness (`ready(options, files)`)**:
   - Construct `my_d = Detector(device["det_name"], device)` from `device = files["device"]`.
   - Call `solved_field(my_d, my_d.voltage, _flux_of_run(my_d, options))` (using `DEFAULT_MODE`) under `work/<device>/field/` to match fluence, mode, `read` consistency (calling `changed(old["read"], Detector(device["det_name"], device))` to compare `"attributes"`, `"keys"`, and SHA-256 hashes of external mesh `"files"` item by item), and verify that both `solved.potential` and `solved.weighting` contain `float(my_d.voltage)`; return `None` if mismatched or incomplete, or the matched field node directory `folder` if ready.
4. **Deduplicated completion and waiting (`_make_shared` and `start`)**:
   - The main command iterates over the shared fields required by all pending scan points, deduplicating by device and `field`-section settings; whenever a requirement has not been started in this invocation and `ready(options, files) is None`, it calls `start(kwargs, options, files)`:
     1. Builds `raser field <device> --set field.voltage=<bias>` arguments (also passing irradiation fluence if it differs from the device file, or any device-file keys other than bias modified by the scan point).
     2. Sets `batch=kwargs["batch"]`, `mem=kwargs["mem"]`, `jobs=1` (ensuring execution in an isolated subprocess or cluster job where DEVSIM loads exclusively), `_argv=words`, `_entry_command_prefix=("field",)`, and `_waiting=kwargs.get("_waiting")` (non-empty only under `-b`).
     3. Prints `"solving the field first: " + " ".join(["raser", *words])` and launches the field solve.
   - If `start` raises `Running` because another process holds the node lock, `_make_shared` prints `f"{piece.name}: {running}"` and skips it; the main command subsequently sees `ready` return `None`, moves the corresponding downstream jobs into the waiting state, and prints the waiting message.
   - When neither `-b` nor `--dry-run` is active, `ready(options, files)` is rechecked after `start` returns; if still `None`, raises `RuntimeError(f"{piece.name} was made in this process and is still not ready for a point of {root}: waiting would not help")`.
5. **Parameter table recording, view symlinking, and in-job verification (`chain._field`)**:
   - Once the shared field node is ready, the main command records that field node's `<node_id>` in the experiment's `points.json`, points the symlink `points/<point>/field` to that field node, and passes `<node_id>` as an upstream node ID to `current` and `readout` for their node fingerprint calculations.
   - When a job runs the `field` check, `_field(kwargs, device)` first switches to the target device view via `_of(kwargs, device)` and calls `ready(kwargs, kwargs["_files"])`; if it returns `None`, raises `FileNotFoundError(f"no field of {kwargs['det_name']} ready for this run: solve it with `raser field {kwargs['det_name']}`")`.

## Software Implementation

### Source File Responsibilities

- `src/raser/stages/field/__init__.py`: Implements `raser field` (`fld`) command registration and entry routing (`register`, `run`), field-solving dispatch (`solve`, `settings`, `job_command`), solving helpers and single-point capacitance output (`_solver`, `_bias`, `_solved`, `_ramp_or_weighting`, `_capacitance`, `_import`, `_empty_devsim`), and shared-field readiness checking and completion interfaces for the simulation chain (`_flux_of_run`, `ready`, `start`).
- `src/raser/stages/chain.py`: Connects `field` to downstream `current`, `readout`, `digitizer`, `trigger`, `reconstruction`, and `analysis` in the simulation chain, providing single/multi-device view switching `_of` and field readiness verification `_field`.
- `src/raser/lifecycle/` (`workflow.py`, `slices.py`): Manages sectioned `config.json` loading, `points.json` parameter table and `points/<point>/<stage>/<job>` view updates, node fingerprint calculation and `node.json` I/O, per-node locking and `.part` atomic persistence, shared-field pre-checks and deduplicated completion (`make_shared`, `_make_shared`), as well as local process wrapping and cluster wakeup of waiting commands (`_start`, `_run_job`, `_start_again`).
- `src/raser/core/field/` (`solved.py`, `reading.py`, `solver_section.py`, `saved_point.py`, `tcad.py`, `save_milestone.py`, `circuit_parameters.py`, `device_circuit.py`): Low-level modules called directly by this stage, providing shared-field lookup (`solved_field`), tracked device-parameter comparison (`Reading`, `changed`), default solver configuration and DEVSIM entry point (`SOLVER`, `main`), single-point capacitance solving (`capacitance`), Sentaurus TDR import (`import_field`), solve-status updating (`save_solved`), and parametrized device equivalent-circuit construction.

### Core Data Structures

| Data structure | Field | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `settings` dict | `umf` | `bool` | None | Whether the UMFPACK linear-solver switch is enabled |
| `settings` dict | `imported` | `str \| None` | None | Full 64-character SHA-256 hash of the TCAD-imported TDR file, or `None` if not importing |
| `point` capacitance dict | `voltage_V` | `float` | $\text{V}$ | Bias voltage of the single-point small-signal capacitance solve |
| `point` capacitance dict | `specific_capacitance_pF` | `float` | 1D $\text{pF/cm}^2$, 2D $\text{pF/cm}$, 3D $\text{pF}$ | Mesh specific capacitance (device capacitance in 3D) |
| `point` capacitance dict | `per` | `str` | None | Normalization basis for specific capacitance: `"cm^2"`, `"cm"`, or `"device"` |
| `point` capacitance dict | `area_factor` | `float` | 1D $\text{cm}^2$, 2D $\text{cm}$, 3D dimensionless | Device area or length conversion factor (defaults to `1.0`) |
| `point` capacitance dict | `frequency_Hz` | `float` | $\text{Hz}$ | Small-signal AC solve frequency |

## Interface

### Options and Configuration Keys

The command is `raser field [path]`: omitting the path uses the current folder, while providing a path accepts a relative or absolute path, which may be a device name, a device project path, or an experiment folder path containing `config.json`; passing a field folder itself aborts. `--draw <object>` draws only the mesh and doping on mesh nodes. Shared run, scan, and cluster options `-b`/`--batch`, `-t`, `-mem`, `--dry-run`, `--scan`, `--set` are documented in [Command-Line Interface (`raser`)](../cli.md) and [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md).

Settings in the `field` section are read from the experiment's `config.json` and modified with `--set field.<key>=<value>` or `--scan field.<key>=<value1>,<value2>`. The code keeps no defaults: the "Value in example" column shows what `examples/HPK-Si-PiN/signal/config.json` sets; if `config.json` is missing a required key, an error is raised naming the missing `"section.key"`.

| Section.key | Value in example | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `200.0` (uses `bias.voltage` from the device file when set to `null`) | $\text{V}$ | Target bias voltage (`float`); when a field is missing, chain commands invoke `raser field` with `--set field.voltage=<value>`; during TCAD import, verifies the TDR contact voltage or specifies the bias when absent in the TDR |
| `field.irradiation_flux` | `null` (uses the irradiation fluence from the device file, or `0` if the device file has no irradiation block) | $\text{cm}^{-2}$ | Irradiation fluence (`float`, $1\ \text{MeV}$ neutron-equivalent fluence) |
| `field.mode` | `"full"` | None | Field acquisition mode: `"full"`, `"semi_fast"`, or `"fast"`; currently only `"full"` is implemented |

The `field` section also has the following categories of settings, which do the following:

- **Mesh**: A single device can have multiple meshes, and which one is used is specified by settings in the `field` section.
- **Subtasks**: IV sweep ramps from `0 V` to the target bias to solve electric potential and electric field and output IV curves; single-point capacitance reloads that bias from an existing `<V>V.devsim` to perform a small-signal capacitance solve and write `<V>V.cv.json`; weighting field reads `Conductive_<V>V.pkl` at the same bias to solve weighting fields for all readout electrodes (single-unit-cell periodic strip electrodes also compute inter-strip mutual capacitance). When none of the three is enabled, a full solve is run: a bias sweep with CV along the sweep, the single-point capacitance at the target bias, then weighting fields.
- **Noise**: Additionally solves and plots device noise current at each bias-sweep curve sample point (dropped under the HEMT `drift_diffusion_v1` branch).
- **UMFPACK**: Loads `devsim.umfpack.umfshim` before solving to switch to the UMFPACK linear solver.
- **TCAD import**: Given a Sentaurus TDR file, skips the DEVSIM bias sweep, imports bulk fields, and solves weighting fields on its mesh; coordinate flip is used only with TCAD import, reversing node coordinate column order and swapping the `x` and `y` axes in 2D plots.

Single-job execution per field node, fixed subtask order `iv → cv → wf`, computing CV along the sweep in a full solve, supporting only `"full"` for `field.mode`, the list of DEVSIM reset-preserved parameters, and the cluster wakeup retry count and recursion-depth cap are hardcoded.

Keys read by `field` from the device file:

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `field.solver` | `SOLVER` (see [Field Solving and Loading (`core/field`)](../core/field.md)) | Subkey-dependent | Deeply merges onto and overrides the solver configuration `SOLVER` |
| `hemt_physics.transport_model` | None (uses standard path when unset) | None | When set to `"drift_diffusion_v1"`, dispatches to the 2D HEMT DC transport branch and drops the single-point capacitance, weighting-field, and noise switches |
| `area_factor` | `1.0` | 1D $\text{cm}^2$, 2D $\text{cm}$, 3D dimensionless | Device area/length conversion factor written by `_capacitance` into `<V>V.cv.json` |

### Files Read and Written

The shared field node files below reside inside `<field_node_dir>` (i.e., `work/<device>/field/nodes/<node_id>/`, or `examples/<device>/field/nodes/<node_id>/` when running examples in place; while being written, the directory carries the `.part` suffix and an individual lock), and are referenced by experiments via `<experiment_folder>/points.json` and `<experiment_folder>/points/<point>/field`.

#### Files Directly Read and Written by This Stage

- **Input files read**:
  - Device JSON (`device.json` inside the project or built-in component `<device>.json`): read by this stage; the parts used by `field` enter the field node input fingerprint and are recorded in `node.json`.
  - `<experiment_folder>/config.json`: full configuration file sectioned into eight stages; its `field` section and experiment settings are read during `raser field <experiment_folder>` or when chain commands complete shared fields.
  - TCAD-imported TDR file (Sentaurus TDR, HDF5): read in full by `settings` to compute its 64-character SHA-256 hash, and read by `tcad.import_field` for mesh, electrode voltages, and bulk fields.
  - `<field_node_dir>/<voltage>V.devsim` and `<field_node_dir>/Conductive_<V>V.pkl`: read respectively by the single-point capacitance (`saved_point.capacitance`) and weighting-field (`solver_section.main`) subtasks.
- **`<field_node_dir>/node.json`** (writers: lifecycle node management and field-solving job): JSON object recording verbatim the field node's inputs (the setting values used by the `field` stage and the parts of the device component file used, from which the fingerprint is computed), along with the code version, runtime environment, and run status.
- **`<field_node_dir>/<voltage>V.cv.json`** (filename keeps float format, e.g. `200.0V.cv.json`; writer: single-point capacitance subtask `_capacitance`): JSON object containing `voltage_V` (`float`, $\text{V}$), `specific_capacitance_pF` (`float`, 1D $\text{pF/cm}^2$, 2D $\text{pF/cm}$, 3D $\text{pF}$), `per` (`str`, `"cm^2"`/`"cm"`/`"device"`, None), `area_factor` (`float`, 1D $\text{cm}^2$, 2D $\text{cm}$, 3D dimensionless), and `frequency_Hz` (`float`, $\text{Hz}$).
- **Device parameter circuit diagram assets** (writer: `field` stage, under `work/<device>/field/`): parametrized device circuit diagrams annotated with junction capacitance, coupling capacitance, and undepleted-layer values, stored as device assets for the `readout` stage to connect into the device circuit.
- **`work/<device>/field/points.json` and `work/<device>/field/points/<point>`** (writer: this stage): the parameter table and the views of the fields. `points.json` is an object keyed by point name; each point has `values` (the values of `voltage`, `irradiation_flux` and `mode`) and `node` (the node ID); `points/<point>` is a symlink to `../nodes/<node_id>`.
- **`<experiment_folder>/points.json` and `<experiment_folder>/points/<point>/field`** (writer: lifecycle experiment scheduler): `points.json` is the experiment parameter table, one row per scan point, recording scan-axis values and each stage's node ID including `field` (printed by `raser status`); `points/<point>/field` is a symlink view pointing to `work/<device>/field/nodes/<node_id>/`.

#### Field Data, Archives, and Plots Written by `core/field`

Inside `<field_node_dir>`, `.pkl` files and `Capacitance_<V>V.json` drop the decimal point for integer biases (such as `Potential_200V.pkl`), whereas nonzero `.devsim`, `.dd`, and all `.undepleted.json` and `.cv.json` files retain float formatting (such as `200.0V.undepleted.json`), and zero-bias archives are named `0V.devsim` and `0V.dd`. Bulk-field `.pkl` files (`Potential`, `Electrons`, `Holes`, `TrappingRate_n`, `TrappingRate_p`, `Conductive`, and `NetDoping_0V.pkl`, or `NetDoping_<V>V.pkl` under TCAD), undepleted-layer files `<V>V.undepleted.json`, DEVSIM and Tecplot archives (`0V`/`<V>V.devsim`, `0V`/`<V>V.dd`, `last_solvable.dd`, `<det_name>.dat`, `converted.devsim`) written during DEVSIM bias sweeps (at `0 V`, every `saved_voltage_interval` checkpoint, and target bias) or TCAD imports; weighting fields `weightingfield/<electrode>/Potential_<V>V.pkl`, `weightingfield/weightingfield.dat`, and single-unit-cell strip mutual capacitances `weightingfield/<electrode>/Capacitance_<V>V.json` written by the weighting-field subtask (including full solves) or TCAD imports; IV/CV/noise curve data (`simIV*`, `simCV*`, `simnoise*`) and multi-dimensional field profile plots (1D ones are stored in `plots/`: `iv`, `cv`, `noise`, `doping`, `potential_<V>V`, `electric_field_<V>V`, `trapping_rate_<V>V`, `weighting_potential_<electrode>_<V>V`, `weighting_field_<electrode>_<V>V`, each with `.png` and `.pdf`); and `HEMT_TRANSPORT_*` outputs (`IdVg.csv`, `final_profile.csv`, `final.devsim`, `IdVg.png`/`.pdf`, `summary.json`) written by the HEMT `drift_diffusion_v1` branch—their internal formats, keys, shapes, types, and units, as well as physical solving and interpolation details, are documented in [Field Solving and Loading (`core/field`)](../core/field.md).
