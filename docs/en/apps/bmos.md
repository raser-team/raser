# Beam Monitor Online System Application (`apps/bmos`)

`raser bmos` is the dedicated application workflow for the Beam Monitor Online System. On top of the standard five-slice simulation chain (`deposit`, `field`, `current`, `readout`, `reconstruction`), it sets the default signal source to the multi-particle bunch source `bunch` (each Geant4 event emits 3 `80 MeV` protons simultaneously spaced `1 um` apart laterally) and turns off per-event plotting by default (`--plots 0`), writing the experiment directory to `work/<det_name>/bmos/`.

```mermaid
flowchart LR
    SRC["Bunch source bunch.json<br/>3 × 80 MeV protons / event"] --> DEP["deposit<br/>Energy deposition and ionized pairs"]
    DEV["Device and amplifier config"] --> DEP
    DEV --> FLD["field (shared)<br/>work/&lt;det_name&gt;/field/"]
    DEP -- "deposit_&lt;job&gt;.h5" --> CUR["current<br/>Default --plots 0"]
    FLD --> CUR
    CUR -- "current_&lt;job&gt;.h5" --> RDO["readout"]
    FLD --> RDO
    RDO -- "readout_&lt;job&gt;.h5" --> RECO["reconstruction"]
    DEP -.-> ANA["raser analysis work/&lt;det_name&gt;/bmos"]
    CUR -.-> ANA
    RECO -.-> ANA
```

## Command

```bash
raser bmos <det_name> [source] [options]
```

## Inputs

- **Component search paths**: Mounts `src/raser/apps/bmos/components` (providing `source/bunch.json`) plus project and global `components/` (see [`../supports/README.md`](../supports/README.md)).
- **Default bunch source `src/raser/apps/bmos/components/source/bunch.json`** ([`../components/source.md`](../components/source.md)):
  - `"kind": "beam"`, `"par_type": "proton"`, `"par_energy": 80` (`MeV`).
  - `"particles"` contains 3 particle items with `"offset"` values `[-1, 1, 0]`, `[0, 1, 0]`, `[1, 1, 0]` (`um`); each Geant4 event represents one bunch emitting these 3 `80 MeV` protons simultaneously.
- **Device, Geant4 setup, and front-end circuit**: `<det_name>.json` ([`../components/device.md`](../components/device.md)), `<g4setup>.py` (default `"device_alone"`, [`../components/g4setup.md`](../components/g4setup.md)), and `<part>.cir` specified by `--amplifier` ([`../components/afe.md`](../components/afe.md)).
- **Shared field directory `work/<det_name>/field/`**: If the field at the target bias and irradiation flux is not ready yet, the workflow automatically calls [`raser field`](../stages/field.md) before launching jobs.

## Outputs

The experiment directory is `work/<det_name>/bmos/`; see [Getting Started](../getting-started.md), [`../lifecycle/experiments.md`](../lifecycle/experiments.md), and [`../lifecycle/slices.md`](../lifecycle/slices.md) for the directory layout and output format of the standard five-slice chain. Each job `<job>` writes in order under the point directory `batch/` holding the slices:

- `deposit_<job>.h5`: energy deposition (`MeV`), coordinates (`um`), time (`s`), and ionized electron-hole pairs inside the detector for each recorded bunch (event) (see [`../stages/deposit.md`](../stages/deposit.md)).
- `current_<job>.h5`: induced current time series per readout electrode (`A`), time step `dt` (`s`), and integrated charge `charge` (`C`); when `--plots` is greater than `0`, writes carrier drift path plots and current plots for the first `plots` events under `plots/job_<job>/event_<number>/` (see [`../stages/current.md`](../stages/current.md)).
- `readout_<job>.h5`: output voltage waveform `voltage` (`V`) after front-end electronics and noise, time step `dt` (`s`), `pulse_edge`, and `device_circuit` (JSON string, omitted when no device circuit values are given) (see [`../stages/readout.md`](../stages/readout.md)).
- `reconstruction_<job>.h5`: baseline, noise, amplitude (`V`), threshold-crossing time `ToA` on the selected edge (defaulting to `pulse_edge` from `readout`), `ToT`, center of gravity `CoG`, constant fraction timing `CFD` (`s`), main-lobe `area` (`V s`), and cluster size and centroid per event and electrode (see [`../stages/reconstruction.md`](../stages/reconstruction.md)).

When `-g4_vis` is enabled, it renders geometry and tracks for a number of generated events equal to `-evt` (or `-gen`, default `1` generated event); if `--g4-vis-driver` (case-insensitive) is `"TSG"`, `"TSG_FILE"`, `"TSG_OFFSCREEN"` (writes `g4_geometry.png`), or starts with `"OGL"`, it writes `g4_geometry` image in the run directory (other drivers starting with `"TSG"` raise `ValueError: the driver '<driver>' writes no picture to a given path; use a TSG or an OGL driver, or no output`), and then the job exits with `SystemExit`.

## Options

| Option | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `det_name` | None (required positional argument) | None | Detector component name or path |
| `source` | `"bunch"` | None | Signal source component name or path (optional positional argument) |
| `--g4setup` | `"device_alone"` | None | Geant4 geometry environment component name or path |
| `-evt`, `--events-per-job` | `1` | events | Number of recorded events per job (mutually exclusive with `-gen`) |
| `-gen`, `--generated-per-job` | `None` | events | Number of generated source events per job (replaces `-evt`) |
| `--generated-limit` | `None` (`10000000` at runtime) | events | Maximum generated source events allowed to record `-evt` events |
| `--edep-min` | `None` | `MeV` | Minimum total deposited energy inside the detector for a recorded event |
| `--edep-max` | `None` | `MeV` | Maximum total deposited energy inside the detector for a recorded event |
| `fano` (set via `--set`/`--scan`) | `True` | None | Whether to sample electron-hole pair counts per deposit step with the Fano factor |
| `-g4_vis` | `False` | None | Launch Geant4 geometry and track visualization (renders `-evt` or `-gen` generated events), then exit the job with `SystemExit` |
| `--g4-vis-driver` | `"OGL"` | None | Geant4 visualization driver name used by `-g4_vis` |
| `--plots` | `0` | events | First N recorded events per job to plot drift paths and currents |
| `-vol`, `--voltage` | Taken from `device.bias.voltage` | `V` | Detector bias voltage (written to `device.bias.voltage`) |
| `-irr`, `--irradiation` | `None` (taken from device `irradiation_flux` when omitted; `0` if absent) | `neq/cm^2` | Irradiation fluence |
| `-amp`, `--amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier stages and termination load joined by `+` |
| `--sheet-resistance` | `None` | `Ohm` | Override sheet resistance of the resistive layer in the device file |
| `-threshold` | `10.0` | `mV` | Threshold for pulse timing and area calculation |
| `-amplitude_threshold` | `10.0` | `mV` | Amplitude threshold for event selection and cluster seed finding |
| `fractions` (set via `--set`/`--scan`) | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | None | Amplitude fraction list for Constant Fraction Discrimination (CFD) |
| `--edge` | `None` (uses `pulse_edge` exported by `readout`) | None | Trigger edge: `"rising"` or `"falling"` |
| `-s`, `--jobs` | `None` (single job) | jobs | Number of indexed jobs to run concurrently or submit |
| `--seed` | Randomly generated 31-bit integer | None | Master random seed |
| `--same-seeds` | `False` | None | Whether scan points share the same batch of random seeds |
| `-b`, `--batch` | `False` | None | Submit jobs to cluster queue |
| `-mem` | `1` | tier | Cluster job memory tier |
| `--dry-run` | `False` | None | Print points, slices, and job list to run and return immediately |
| `--scan` | `[]` | None | Scan parameter `address=value1,value2,...` (repeatable) |
| `--set` | `[]` | None | Fix single parameter `address=value` (repeatable) |

## Common Errors

| Error Message | Trigger Condition |
| --- | --- |
| `ValueError: events_per_job and generated_per_job are given at once in the command line; give one of them` | Both `-evt` and `-gen` are given on the command line (or `in the "set" of config.json` if both are in `"set"` of `config.json`) |
| `ValueError: events_per_job (<events>) and generated_per_job (<generated>): a job records a number of events or generates one, so exactly one of them is set` | Both `events_per_job` and `generated_per_job` end up unset |
| `RuntimeError: <recorded> of the <events> events asked for were recorded when the limit of <generated> generated events was reached ...` | Generated source events reach `generated_limit` before recording the requested `events_per_job` events |
| `` FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>` `` | No ready solved field is found when the field slice runs |
| `ValueError: <det_name> has no resistive layer to give a sheet resistance of <sheet_ohm> Ohm` | `--sheet-resistance` is passed for a detector without `resistive_layer` |

## Related Pages

- [`../getting-started.md`](../getting-started.md)
- [`../cli.md`](../cli.md)
- [`../lifecycle/experiments.md`](../lifecycle/experiments.md)
- [`../lifecycle/slices.md`](../lifecycle/slices.md)
- [`../components/device.md`](../components/device.md)
- [`../components/source.md`](../components/source.md)
- [`../components/g4setup.md`](../components/g4setup.md)
- [`../components/afe.md`](../components/afe.md)
- [`../stages/deposit.md`](../stages/deposit.md)
- [`../stages/field.md`](../stages/field.md)
- [`../stages/current.md`](../stages/current.md)
- [`../stages/readout.md`](../stages/readout.md)
- [`../stages/reconstruction.md`](../stages/reconstruction.md)
- [`../stages/analysis.md`](../stages/analysis.md)
