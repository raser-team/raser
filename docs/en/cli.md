# Command-Line Interface (`raser`)

`raser` is the unified command-line entry point; `cli` is solely responsible for dispatching commands and arguments to the corresponding stage, benchmark, application, or lifecycle module. Stage names and their short commands, along with `status`, `new`, `model`, and `device`, are reserved words and are not used as experiment folder names.

## Commands

| Command | What it does | Page |
| --- | --- | --- |
| `raser signal <device>` | Runs the signal benchmark on this device: completes the whole chain and gives charge collection efficiency | [bench/signal.md](bench/signal.md) |
| `raser timeres <device>` | Runs the Time Resolution benchmark on this device | [bench/timeres.md](bench/timeres.md) |
| `raser tct <device>` | Runs the Transient Current Technique benchmark on this device | [bench/tct.md](bench/tct.md) |
| `raser telescope <device>` | Replaces both middle devices under test in the beam telescope with this device and runs the spatial resolution benchmark | [bench/telescope.md](bench/telescope.md) |
| `raser bmos` | Runs the Beam Monitor Online System | [apps/bmos.md](apps/bmos.md) |
| `raser cflm` | Runs the CEPC Fast Luminosity Monitor | [apps/cflm.md](apps/cflm.md) |
| `raser hbf` | Runs Hydrogen–Boron Fusion (p–¹¹B) | [apps/hbf.md](apps/hbf.md) |
| `raser pimg` | Runs Proton Imaging | [apps/pimg.md](apps/pimg.md) |
| `raser field [path]` (short command `fld`) | Uses the current directory if no path is given, or the given relative or absolute path; computes electric field, weighting field, and IV/CV in the device | [stages/field.md](stages/field.md) |
| `raser deposit [path] [<source>]` (short command `dep`) | Runs the experiment in the current directory or at the given path up to `deposit` (computing particle energy deposition with Geant4), filling in missing upstream stages automatically; `<source>` is shorthand for `--set deposit.g4setup.source=<source>` | [stages/deposit.md](stages/deposit.md) |
| `raser current [path]` (short command `cur`) | Runs the experiment in the current directory or at the given path up to `current` (drifting carriers in the fields and computing induced currents on the electrodes), filling in missing upstream stages automatically | [stages/current.md](stages/current.md) |
| `raser readout [path]` (short command `rdo`) | Runs the experiment in the current directory or at the given path up to `readout` (feeding current into the device equivalent circuit and front-end amplifier to obtain waveforms), filling in missing upstream stages automatically | [stages/readout.md](stages/readout.md) |
| `raser digitizer [path]` (short command `digi`) | Runs the experiment in the current directory or at the given path up to `digitizer` (converting waveforms into digital waveforms according to oscilloscope or digitizer board sampling and quantization), filling in missing upstream stages automatically | [stages/digitizer.md](stages/digitizer.md) |
| `raser trigger [path]` (short command `trig`) | Runs the experiment in the current directory or at the given path up to `trigger` (deciding which events are recorded according to real trigger hardware conditions), filling in missing upstream stages automatically | [stages/trigger.md](stages/trigger.md) |
| `raser reconstruction [path]` (short command `reco`) | Runs the experiment in the current directory or at the given path up to `reconstruction` (extracting hit time and amplitude from waveforms, and performing track fitting in beam tests), filling in missing upstream stages automatically | [stages/reconstruction.md](stages/reconstruction.md) |
| `raser analysis [path]` (short command `ana`) | Runs the experiment in the current directory or at the given path up to `analysis` (summarizing efficiency and time resolution and writing trend plots under `<experiment>/analysis/`), filling in missing upstream stages automatically | [stages/analysis.md](stages/analysis.md) |
| `raser status [path]` | Prints the project's parameter table: status and node ID of each experiment, scan point, and stage | [lifecycle/slices.md](lifecycle/slices.md) |
| `raser new --from <example> <path>` | Copies all of `examples/<example>` into a new project with a complete configuration, independent of the example thereafter | [lifecycle/experiments.md](lifecycle/experiments.md) |
| `raser model --draw <model>` | Plots curves such as mobility and impact ionization coefficient versus electric field, temperature, and doping | [core/model.md](core/model.md) |
| `raser device --draw <device>` | Plots device geometry, electrodes, and doping | [core/device.md](core/device.md) |
| `raser <stage> --draw <object>` | Plots objects of that stage, for example `readout` plots schematics and impulse responses, and `field` plots meshes and doping at mesh nodes | [stages/README.md](stages/README.md) |

## Global Options

- `-b`: Submits jobs to the cluster queue.
- `-t`: Combined with `-b`, checks and previews submission details without actually submitting jobs.
- `-mem <tier>`: Combined with `-b`, requests `8000 × <tier>` MB of memory per job (default `1`); when `-bb`, `-bbb`, etc. are stacked, the tier is the larger of the count of `b` and `-mem`.
- `--help`: Prints help for the top-level command or a subcommand and exits.
- `--version`: Prints the current `raser` version number and exits.

## Shared Run Arguments

- `-s`: Sets the number of parallel jobs per scan point.
- `--seed`: Sets an integer random seed to make simulation results reproducible; defaults to the current timestamp if omitted.
- `--same-seeds`: Makes jobs with the same index across scan points share random seeds so upstream results unaffected by the scan are reused.
- `--set`: Modifies a setting in the configuration file using `"section.key"` as the address, for example `--set field.voltage=100`.
- `--scan`: Scans one or more settings using `"section.key"` as the address, for example `--scan field.voltage=100,200`; only the settings of the sections `field`, `deposit`, `current`, `readout` can be scanned, see [lifecycle/experiments.md](lifecycle/experiments.md).
- `--dry-run`: Prints only the scan points, stages, and job statuses to be run without starting computation.

Details of configuration file sectioning rules, scan-point expansion, and cluster job scheduling are in [lifecycle/experiments.md](lifecycle/experiments.md) and [lifecycle/jobs.md](lifecycle/jobs.md).
