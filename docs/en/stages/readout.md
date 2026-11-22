# Electronics Readout Stage (`stages/readout`)

`src/raser/stages/readout.py` is the 4th stage, `readout`, of the eight-stage simulation chain, dispatched by `raser readout` (short alias `raser rdo`) or by benchmark and application experiment commands. It consumes electrode induced currents from the [Carrier Transport and Induced Current Stage (`stages/current`)](current.md) node and device circuit parameters supplied by the [Field Solving Stage (`stages/field`)](field.md) field node under `<device_project>/field/<node_id>/`. This stage calls [Field Solving and Loading (`core/field`)](../core/field.md) to assemble the device equivalent circuit, and calls [Electronics Readout (`core/readout`)](../core/readout.md) to load the front-end amplifier chain, determine the pulse edge direction of each output channel, solve the transient output voltage waveform for every event, superpose circuit thermal noise, and write the waveforms into its own node `nodes/readout/<node_id>/`. The output waveforms are passed downstream to the [Digitization Stage (`stages/digitizer`)](digitizer.md) to be converted into digital waveforms via oscilloscope or digitizer-board sampling and quantization.

## Behavior

### Device Equivalent Circuit and Front-End Waveforms

This stage feeds the induced currents of each electrode into the device equivalent circuit and the front-end amplifier chain specified by `amplifier`, computes the voltage waveforms of each output channel for every event along with the device circuit parameter record and pulse edge directions (`"rising"` or `"falling"`), and writes them into the waveform file. `readout` has its own seed, derived from the job's seed (see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md#seeds)), controlling NGspice noise sampling, which enters this stage's node fingerprint just like the seeds of `deposit` and `current`; only seeded runs draw and superpose independent time-domain thermal noise for each stored channel. For each event, only output channels whose maximum absolute voltage swing is at least `1e-3` times the event's largest channel swing are stored; events with no nonzero induced current store `0` channels.

For example, scanning two bias voltages on the `HPK-Si-PiN` example:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

When `HPK-Si-PiN` is not present under `work/`, the command runs in place under `examples/HPK-Si-PiN/`, and the experiment folder is `examples/HPK-Si-PiN/signal`. `HPK-Si-PiN` is a standard single-electrode planar device whose device file directly specifies `capacitance_pF = 3.44162280284` (`3.44162280284e-12 F`), with a bias of `200 V` in the device file. At the `voltage_200` point using the example amplifier chain `SantaCruz+Gali52+Termination50`, inside the node pointed to by `points/voltage_200/readout/0`, job `0`'s `readout.h5` attributes (`attrs`) are:

- `dt = 5e-12` (in `s`)
- `electrodes = ['top']`
- `pulse_edge = ['falling']`
- `device_circuit = '{"junction_capacitance": {"farad": 3.44162280284e-12, "from": "device file"}, "between_electrodes": null, "bias_resistance": null, "coupling_capacitance": null, "undepleted_layer": null}'`

The datasets (`datasets`) are:

| Dataset name | Example shape | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | None | Geant4 event ID of each recorded event |
| `t0` | `(200,)` | `float64` | `s` | Left edge time of the first time bin |
| `count` | `(200,)` | `int64` | bins | Number of waveform sample points per event |
| `stored` | `(200,)` | `int64` | electrodes | Number of electrodes with stored waveforms in each event |
| `index` | `(196,)` | `int64` | None | Indices of stored electrodes in `electrodes` |
| `voltage` | `(245196,)` | `float64` | `V` | Bin-center output voltage concatenated sequentially across events and stored electrodes |

`device_circuit` shows that the junction capacitance comes directly from the device file (`"from": "device file"`); `undepleted_layer` is `null`, indicating that the device is fully depleted at `200 V`. `pulse_edge` is `['falling']` because the `top` electrode is biased at `+200 V` to collect electrons, and the two cascaded amplifier stages have non-inverting net polarity, so the output pulse goes downward. Among the `200` recorded events, `index` has length `196`, meaning `4` events had zero induced current on the `top` electrode (`stored = 0`), while the waveforms of the remaining `196` events are concatenated sequentially in `voltage`.

### Running Up to the Readout Stage with Upstream Nodes Shared Across Points

`raser readout` (or `raser rdo`) runs up through `readout` on the experiment in the current folder or at the given path, computing any missing `field`, `deposit`, and `current` nodes first:

```bash
raser readout [path]
raser rdo [path]
```

The amplifier chain is read only by `readout`. Adding a scan over two amplifier chains on the experiment above:

```bash
raser rdo examples/HPK-Si-PiN/signal --scan field.voltage=100,200 --scan readout.amplifier=SantaCruz+Gali52+Termination50,BroadBandCividec+Termination50 -s 2 --seed 1
```

When a scan affects only downstream settings, upstream nodes are shared across points. `deposit` and `current` still have $2$ jobs per bias ($4$ nodes in total) with unchanged fingerprints and are reused directly; `readout` has two biases times two chains with $2$ jobs per point ($8$ nodes in total), of which the $4$ for `SantaCruz+Gali52+Termination50` are already computed, so only the $4$ for `BroadBandCividec+Termination50` are newly computed. Downstream `digitizer`, `trigger`, and `reconstruction` read `readout`'s node ID and therefore also have $8$ nodes each; `analysis` has one node per scan point, for $4$ in total. Nodes are append-only, so reverting the chain points the view back to the original node. When the code version differs from the one recorded in the node, only a notice is printed and the result is still reused. Each node is locked individually, and a partially written node carries the `.part` suffix. See [Slices and Reruns](../lifecycle/slices.md) for node and reuse rules.

### Upstream Zero-Event Jobs and Empty Multi-Position Currents

When upstream `deposit` records `0` valid events in a job, `readout` skips that job accordingly. In a multi-position experiment, when a position has no deposit steps—and hence no current file—in a job, that position directly records `0` events while other positions in the same job run normally.

### Drawing Schematics and Impulse Responses

`raser readout --draw <object>` draws objects belonging to this stage: front-end circuit schematics and impulse responses. Front-end circuit schematics and impulse responses depend solely on the circuit and its parameters; they are assets stored under `work/<circuit>/` and referenced by `readout` across experiments.

A device with a resistive layer (its file has `resistive_layer`) has one more object, `network`: `raser readout --draw network [path]` solves only the device circuit and the amplifier chain of `readout.amplifier`, and reads no result of `deposit` or `current`. The impulse falls on a point of the device, given by its geometric coordinates $(x, y)$ in $\mu\text{m}$, in the coordinates of `current` ($0 \le x \le l_x$, $0 \le y \le l_y$); a device with strips takes $x$ alone. A charge of $1\ \text{fC}$ is injected at this point as a rectangular current pulse in the first time bin, shared linearly among the netlist nodes of the neighbouring RC nodes by its distances to their centres; the bins are $10\ \text{ps}$ wide and there are $2000$ of them; the sheet resistance is `readout.sheet_resistance`, or that of the device file when it is not given. With `--at <x>,<y>` the impulse falls on that point, and `network_waveforms.png` shows the output waveform of every read-out electrode (strip or pad); without it the point is scanned along $x$ in steps of one RC node width on the middle line of the device ($y = l_y/2$), `network_waveforms.png` shows the waveforms for the point in the middle of the scan, and `network_sharing.png` is drawn as well: the waveform amplitude and the waveform integral of every read-out electrode against the $x$ of the impulse. In both cases `network_schematic.png` is drawn: the circuit of the network of the device, with the values of its elements.

## Rules

### Built-in Constants

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `STAGES["readout"]` | `("rdo", "the waveforms of the electronics, after all before them", ...)` | None | `src/raser/stages/stage_commands.py`: short alias, help string, and argument-mounting functions for `raser readout` |
| `PART_EDGE` | `1e-3` | dimensionless | `src/raser/core/readout/job.py`: relative maximum voltage-swing threshold used by `write_waveforms` to decide which output channels to save and to determine convergence of local strip-row circuit expansion |

### Parsing and Launching Stage Commands (`stage_commands.run`)

1. **Mount arguments (`register`)**: Register `readout` (alias `rdo`), mount shared run parameters and this stage's command options (settings for upstream stages live in their own sections; see [Field Solving Stage (`stages/field`)](field.md), [Energy Deposition Stage (`stages/deposit`)](deposit.md), and [Carrier Transport and Induced Current Stage (`stages/current`)](current.md)), and set the execution entry point to `partial(run, "readout")`.
2. **Resolve experiment**: Read `config.json` in the experiment folder to identify its experiment class.
3. **Validate stage**: If the experiment class does not include the `readout` stage, exit with:

   ```text
   <folder>: the experiment <workflow> has no readout slice; its slices: <names>
   ```

4. **Launch**: Set the cutoff stage to `readout`, enter the project context of the experiment, change into the experiment folder to run, and restore the original directory afterward. When the experiment folder contains `config.json`, the target argument on the command line is rewritten to an absolute path so that cluster jobs rerunning the original command from the experiment folder can locate it.

If the device field is not ready when a job starts, the job raises:

```text
FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>`
```

Follow the message to run `raser field <det_name>` first, then rerun.

### Readout Calculation (`readout.waveforms`)

1. **Multi-position pre-check**: When a position is given and that position has no current file in this job, return `{"events": 0}` immediately.
2. **Construct device and electrode names**:
   - `my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])` (see [Detector Components (`components/device`)](../components/device.md) for device file keys).
   - `electrodes = electrode_names(my_d.read_out_contact, my_d.read_ele_num)`; see [Carrier Drift and Induced Current (`core/current`)](../core/current.md) for naming rules.
   - `part_of = None`, `sheet_ohm = kwargs.get("sheet_resistance")`.
3. **Assemble the device equivalent circuit**:
   - **Device file contains `resistive_layer` (resistive-layer device)**:
     1. Select `build = device_grid` (2D resistive mesh) if `my_d.is_pixel` is true, else `build = device_row` (1D resistive row).
     2. The field folder at the bias is taken as in steps 1 and 2 of a regular device below, `row, solved_f, undepleted = field_circuit(...)` (`row` is `None` for a device with a resistive layer); `circuit, values = build(my_d, electrodes, solved_f, sheet_ohm=sheet_ohm, solved_undepleted=undepleted)`: the sheet resistance is selected in order from `sheet_ohm` when not `None` (source `"chosen"`) → `resistive_layer["sheet_resistance"]` (`"device file"`) → estimation from aluminum-implanted layer parameters (`"implanted layer"`); the RC node capacitance is selected in order from `capacitance_pF` (`"device file"`) → the capacitance the field solved at the bias times the part of the device area one RC node takes, $p_x p_y / (l_x l_y)$ ($p_x / l_x$ for a resistive row; `"field"`) → the parallel-plate estimate of the device (`"parallel plate"`); where the device is not fully depleted at the bias, the capacitances and the current sources of the RC nodes go to one common undepleted node, from which the resistance and the capacitance of the undepleted layer of the whole device go to ground (see "Device circuit parameters" in [device field](../core/field.md)).
   - **`sheet_ohm` supplied for a device without a resistive layer**: raises

     ```text
     ValueError: <det_name> has no resistive layer to give a sheet resistance of <sheet_ohm> Ohm
     ```

     Remove the setting or scan for `readout.sheet_resistance` and rerun.
   - **Standard device**:
     1. **Irradiation fluence**: Take `my_d.irradiation_flux` ($\text{cm}^{-2}$); if `field.irradiation_flux` is not `null`, use `float(irradiation_flux)` instead.
     2. **Locate field (`solved_field(my_d, my_d.voltage, flux, mode)`)**: Filter the device's solved fields to those with irradiation fluence equal to `float(flux)` and solve mode equal to `field.mode`, compare device parameters with `changed`, and check that both potential and weighting field are solved at that bias. If missing, raises respectively:

        ```text
        FileNotFoundError: no <mode> field of <det_name> at the irradiation flux <flux> in <root> (flux and mode of those solved: <have>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode> --set field.irradiation_flux=<flux>`
        ValueError: the field in <folder> was solved for another device (<differing>); solve it again with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
        FileNotFoundError: the field in <folder> is not solved at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
        FileNotFoundError: the field in <folder> has no weighting field at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>` with the weighting field switched on in the field settings
        ```

        The four errors indicate, respectively: missing field for that fluence and mode; field solved for previous device parameters; missing electric potential at that bias; missing weighting field at that bias. Run the command shown at the end of the error message; if the weighting field is missing, enable weighting-field solving in the `field` section (modify field settings with `--set field.<key>=<value>`).
     3. **Read circuit parameters from the field (`row, solved_f, undepleted = field_circuit(folder, my_d)`)**:
        - When `my_d.is_strip and len(my_d.read_out_contact) == 1 and my_d.read_ele_num > 1` (a periodic row of strips with a single repeated readout contact): read `weightingfield/<electrode>/Capacitance_<bias>V.json` as `row` and set `solved_f = None`. If missing, raises:

          ```text
          FileNotFoundError: the field in <folder> has no capacitances between the strips of <det_name> at <voltage> V: <path> is missing, and the readout of a row of strips needs it. A field solved by raser stores it with its weighting field: switch the weighting field on in the field settings. A field imported from TCAD does not store it yet, so the strips of an imported field cannot be read out
          ```

          This file is written alongside DEVSIM weighting fields; enable weighting-field solving in the `field` section (modify field settings with `--set field.<key>=<value>`) to solve the weighting field with DEVSIM.
        - When `row is None`: if capacitance has been solved at that bias, read `specific_capacitance_pF * area_factor * 1e-12` ($\text{F}$) from `<float(voltage)>V.cv.json` as `solved_f`; otherwise `solved_f = None`.
        - `solved_undepleted(Path(folder), my_d.voltage, undepleted_area_cm2(my_d))` reads `<float(voltage)>V.undepleted.json`. If the undepleted bulk is not stored for that bias, raises:

          ```text
          FileNotFoundError: the field in <folder> has no undepleted bulk at <voltage> V (solved at: <solved>): solve it with `raser field <det_name> --set field.voltage=<voltage>`
          ```

     4. **Assemble circuit (`circuit, values = device_circuit(my_d, electrodes, solved_f, row=row, solved_undepleted=undepleted)`)**:
        - Reads `bias_resistance_ohm` ($\Omega$) and `coupling_capacitance_pF * 1e-12` ($\text{F}$) from the device file. If coupling capacitance is given without bias resistance, raises:

          ```text
          ValueError: A coupling capacitance needs a bias resistance: without it the electrode has no DC potential
          ```

          Add `bias_resistance_ohm` to the device file.
        - Undepleted-layer parameters `undepleted_layer_of(my_d, undepleted)`: if the device file supplies only one of `undepleted_resistance_ohm` and `undepleted_capacitance_pF`, raises:

          ```text
          ValueError: <det_name> gives <key> alone: the undepleted layer has both undepleted_resistance_ohm and undepleted_capacitance_pF
          ```

          Uses the device file values (source `"device file"`) when both are given, otherwise uses `undepleted` from the field (`"field"`).
        - Junction capacitance `junction_capacitance` is selected in order from device file `capacitance_pF * 1e-12` (`"device file"`) → field capacitance (`solved_f` when `row is None`, else `float(row["total"]) * float(my_d.l_y) * 1e-4`, source `"field"`) → parallel-plate estimate `my_d.capacitance * 1e-12` (`"parallel plate"`). If none of the three is available, raises:

          ```text
          ValueError: <det_name> has no capacitance: its device file gives none, its field was not asked for one, and the device has no estimate
          ```

          Add `capacitance_pF` to the device file, or enable CV solving in the `field` section (modify field settings with `--set field.<key>=<value>`) to solve capacitance.
        - When `row` is not `None`, requires `row["unit"] == "F/cm"`, otherwise raises `ValueError: The capacitances of the row are in <unit>`. Once verified, scales nearest-neighbor inter-strip capacitances by strip length `l_y * 1e-4` ($\text{cm}$), assembles `row_of_electrodes`, and defines `part_of(hit, margin) = part_of_row(my_d, electrodes, hit, margin, solved_f, row)`.
4. **Amplifier chain and pulse edge directions**:
   - `chain = named_chain(str(kwargs["amplifier"]))` splits `amplifier` on `"+"` and loads each `readout/<part>.cir` sequentially from component directories (see [Front-End Readout Circuit Components (`components/readout`)](../components/readout.md) for subcircuit syntax and built-in components). If missing, raises `FileNotFoundError: Cannot find RASER component readout/<part>.cir:`; check the spelling of the subcircuit name or confirm the file is placed under `readout/`.
   - `pulse_edges(my_d, chain, list(circuit.outputs))` returns the pulse edge directions matching `circuit.outputs` one-to-one.
5. **Solve and write (`write_waveforms`)**: Removes any existing waveform file at the same path, then solves transient voltages event by event, superposes time-domain thermal noise according to the seed, drops channels whose maximum absolute swing is `< 1e-3 * largest`, and writes the result.

## Software Implementation

### Source File Responsibilities

- `src/raser/stages/readout.py`: `waveforms(kwargs, position=None)` performs the multi-position pre-check, constructs `Detector` and electrode names, assembles the device equivalent circuit according to whether `resistive_layer` is present, loads the front-end subcircuit chain, determines pulse edge directions, and calls `write_waveforms`.
- `src/raser/stages/chain.py`: Defines the lazy-import entry point `_waveforms` for the `readout` module.
- `src/raser/stages/stage_commands.py`: Registers stage commands; resolves the target experiment, verifies it includes the target stage, sets the cutoff stage, and switches into the experiment folder to run.
- `src/raser/stages/files.py`: Provides input and output file paths for each stage in the current job.

### Core Data Structures

`readout.waveforms(kwargs, position)` reads the following from `kwargs`:

| Key | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `"det_name"` | `str` | None | Current device name |
| `"_files"` | `dict` | Device-key dependent | Component file contents; `_files["device"]` is the device configuration dictionary already updated with the run's bias voltage |
| `"amplifier"` | `str` | None | Front-end amplifier and termination-load subcircuit chain joined with `"+"` |
| `"sheet_resistance"` | `float \| None` | $\Omega$ | Sheet-resistance override for resistive-layer devices |
| `"irradiation_flux"` | `float \| None` | $\text{cm}^{-2}$ | Irradiation fluence of this run (`field.irradiation_flux`, $1\ \text{MeV}$ neutron-equivalent fluence); uses `my_d.irradiation_flux` when `None` |
| `"seed"` | `int \| None` | None | Random seed for thermal noise; `None` in unseeded workflows (such as `tct`), skipping noise addition |

`values` returned when assembling the device equivalent circuit (serialized into the `device_circuit` attribute of the waveform file):

| Key | Applicable device and structure | Unit | Meaning |
| --- | --- | --- | --- |
| `"junction_capacitance"` | Standard devices: `{"farad": float, "from": str}` | $\text{F}$ | Single-electrode depleted junction capacitance and source (`"device file"`, `"field"`, or `"parallel plate"`) |
| `"between_electrodes"` | Standard devices: `{"farad": list[float], "from": "field"} \| None` | $\text{F}$ | One-sided coupling capacitances to the $1, \dots, N$-th nearest neighboring strips in a strip row (`null` for non-strip-row devices) |
| `"bias_resistance"` | Standard devices: `{"ohm": float} \| None` | $\Omega$ | Per-electrode bias resistance (`null` if unconfigured) |
| `"coupling_capacitance"` | Standard devices: `{"farad": float} \| None` | $\text{F}$ | Per-electrode AC coupling capacitance (`null` if unconfigured) |
| `"undepleted_layer"` | Standard devices: `{"ohm": float, "farad": float, "from": str} \| None` | $\Omega$, $\text{F}$ | Undepleted-layer parallel resistance, capacitance, and source (`null` when fully depleted) |
| `"rc_node_capacitance"` | Resistive-layer devices: `{"farad": float, "from": str}` | $\text{F}$ | Capacitance from a single resistive-layer RC node to the backside, and its source |
| `"sheet_resistance"` | Resistive-layer devices: `{"ohm": float, "from": str}` | $\Omega$ | Resistive-layer sheet resistance and source (`"chosen"`, `"device file"`, or `"implanted layer"`) |
| `"coupling_per_area_f_m2"` | Resistive-layer devices: `float \| None` | $\text{F/m}^2$ | Coupling capacitance per unit area of the dielectric layer beneath readout strips or pads (`null` for direct contact) |

## Interface

### Options and Configuration Keys

Only the keys listed below are configurable in this stage; the relative swing threshold `PART_EDGE = 1e-3` for saving channels, and the frequency band and temperature of frequency-domain noise analysis are hardcoded. `--set` and `--scan` use `"section.key"` addresses, such as `--set readout.amplifier=BroadBandCividec+Termination50`. Shared run parameters (`-s`, `--seed`, `--same-seeds`, `--set`, `--scan`, `-b`, `-t`, `-mem`, `--dry-run`) are documented in [Command-Line Interface (`raser`)](../cli.md) and [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md); settings for upstream stages live in their own sections—see [Energy Deposition Stage (`stages/deposit`)](deposit.md) and [Carrier Transport and Induced Current Stage (`stages/current`)](current.md). The "Value in example" column for configuration keys shows what `examples/HPK-Si-PiN/signal/config.json` sets; if `config.json` is missing a required key, an error is raised naming the missing `"section.key"`. Rows for device file keys show how they are written in the device file.

| Section.key | Value in example | Unit | Meaning |
| --- | --- | --- | --- |
| `[path]` | Current folder | None | Experiment folder |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Chain of `readout/<name>.cir` subcircuits joined with `"+"`, where leading entries are two-port amplifier stages and the final entry is a one-port load |
| `readout.sheet_resistance` | `null` (uses the resistive-layer sheet resistance from the device file) | $\Omega$ | Overrides sheet resistance of a resistive-layer device; passing it for a standard device raises `ValueError` |
| `field.voltage` | `200.0` (uses the bias from the device file when set to `null`) | $\text{V}$ | Belongs to the `field` section: bias voltage used to locate the field and determine collected charge polarity |
| `field.irradiation_flux` | `null` (uses the irradiation fluence from the device file, or `0` if the device file has no irradiation block) | $\text{cm}^{-2}$ | Belongs to the `field` section: irradiation fluence used during field lookup |
| Device file keys `read_out_contact`, `read_ele_num`, `electrodes`, `l_y`, `p_x`, `p_y`, `x_ele_num`, `y_ele_num` | See the `components/device` page | $\mu\text{m}$ / count | Define readout electrode names, layout (`"pad"`, `"strip"`, `"pixel"`), strip length, and RC node dimensions |
| Device file key `capacitance_pF` | None (optional) | $\text{pF}$ | Directly specified single-electrode depleted junction capacitance (or resistive-layer RC node capacitance), taking precedence over field capacitance and parallel-plate estimates |
| Device file key `bias_resistance_ohm` | Omitted (optional) | $\Omega$ | Per-electrode bias resistance of a standard device; required whenever `coupling_capacitance_pF` is provided |
| Device file key `coupling_capacitance_pF` | Omitted (optional) | $\text{pF}$ | Per-electrode AC coupling capacitance of a standard device |
| Device file keys `undepleted_resistance_ohm`, `undepleted_capacitance_pF` | Omitted (optional) | $\Omega$, $\text{pF}$ | Parallel resistance and capacitance of the undepleted layer in a standard device; must be given as a pair, otherwise read from the field |
| Device file key `resistive_layer` | None (optional) | $\Omega$, $\text{cm}^{-2}$, $\mu\text{m}$, $^\circ\text{C}$ | Resistive-layer configuration block containing sheet resistance `sheet_resistance` (or Al-implantation parameters `implanted`, `thickness`, `anneal`), readout `strips` or `pads`, grounded contacts `grounded`, and optional dielectric `coupling` (`thickness`, `permittivity`) |

### Files Read and Written

- **Read: circuit files in the `<device_project>/field/<node_id>/` field node** (`<V>V.cv.json`, `<V>V.undepleted.json`, `weightingfield/<electrode>/Capacitance_<bias>V.json`). Standard devices read junction capacitance, undepleted-layer RC parameters, and strip-row inter-strip capacitances from these files; see [Field Solving and Loading (`core/field`)](../core/field.md) for formats.
- **Read: `current.h5` in the `current` node** (one `current.<position>.h5` per position in multi-position experiments). Reads `electrodes`, `dt` ($\text{s}$), and per-event induced currents; see [Carrier Drift and Induced Current (`core/current`)](../core/current.md) for the format.
- **Write: `nodes/readout/<node_id>/readout.h5`** (one file `readout.<position>.h5` per position in the same node in multi-position experiments). Written when upstream stages have recorded events and (in multi-position experiments) that position has a current file; any old file is removed first and events are appended one by one. See [Electronics Readout (`core/readout`)](../core/readout.md) for underlying I/O functions; HDF5 attributes and datasets are:

  | Kind | Name | Shape and type | Unit | Meaning |
  | --- | --- | --- | --- | --- |
  | Attribute (`attrs`) | `dt` | scalar, `float64` | $\text{s}$ | Sampling time-bin width |
  | Attribute (`attrs`) | `electrodes` | `(outputs,)`, variable-length string array | None | All possible output readout channel names of the circuit |
  | Attribute (`attrs`) | `pulse_edge` | `(outputs,)`, variable-length string array | None | Pulse edge direction matching `electrodes` one-to-one: `"rising"` or `"falling"` |
  | Attribute (`attrs`) | `device_circuit` | scalar, JSON string | $\text{F}$, $\Omega$, $\text{F/m}^2$ | Device equivalent-circuit parameter values and sources (structure in the `values` table above) |
  | Dataset (`datasets`) | `event` | `(events,)`, `int64` | None | Geant4 event ID of each recorded event |
  | Dataset (`datasets`) | `t0` | `(events,)`, `float64` | $\text{s}$ | Left edge time of the first time bin of each event |
  | Dataset (`datasets`) | `count` | `(events,)`, `int64` | bins | Number of waveform sample points for each event |
  | Dataset (`datasets`) | `stored` | `(events,)`, `int64` | channels | Number of channels with stored waveforms in this event (`0` for zero-current events) |
  | Dataset (`datasets`) | `index` | `(sum(stored),)`, `int64` | None | 0-based indices of stored channels in `electrodes`, partitioned by `stored` per event |
  | Dataset (`datasets`) | `voltage` | `(sum(stored * count),)`, `float64` (`gzip`-compressed) | $\text{V}$ | Bin-center output voltage flattened sequentially across events and stored channels, with `count` points per channel of an event |

- **Write: `nodes/readout/<node_id>/node.json`**. Records this node's inputs along with the code version, runtime environment, and run status.
- **Write: `points.json` and `points/<point>/readout/<job>`**. The parameter table records the `readout` node ID used by each point; the view symlink points to that node.
- **Write: `<device project>/network/<node>/`** (only with `--draw network`). `network.h5`, `node.json`, and under `plots/` `network_schematic.png`, `network_waveforms.png` and, for a scan, `network_sharing.png`; `network.h5` has the attributes `dt` ($\text{s}$), `charge` ($\text{C}$), `electrodes` and `device_circuit`, the dataset `point` of shape `(points, 2)` in $\mu\text{m}$, the $(x, y)$ of each impulse, and the dataset `voltage` of shape `(points, outputs, bins)` in $\text{V}$, the output voltage of each read-out electrode at the bin centres for the impulse on each point.
