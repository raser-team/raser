# Beam Monitor Online System (`apps/bmos`)

`bmos` (Beam Monitor Online System, in the `raser_app` package) is a configuration of [`signal`](../bench/signal.md) that switches to the multi-particle bunch source `bunch` (each event represents one bunch emitting `3` `80 MeV` protons simultaneously) and disables per-event plotting in the example (`deposit.plots = 0`, `current.plots = 0`). Centered on the monitoring device placed in the beam path, it reads [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence—[`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md)—outputting the superimposed induced current pulses, readout voltage waveforms, charge collection efficiency, and time resolution produced by bunches in the monitoring device.

## Setup and Standard Practice

### Standard Practice and Physical Definitions

In academic practice for online beam monitoring (Beam Monitor Online System) on proton or heavy-ion accelerator beamlines, a radiation-hard wide-bandgap semiconductor detector (such as the 4H-SiC PiN diode `NJU-PiN-bmos`) is placed directly in the beam path. Bunch by bunch, it measures the superimposed transient induced current pulse and total collected charge produced when multiple charged particles in a bunch traverse the detector simultaneously, thereby monitoring the intensity (particle count), arrival time, and pulse amplitude distribution of each bunch online.

In RASER, a single bunch is simulated as a single Geant4 event. Suppose one bunch emits $M$ particles simultaneously, the set of deposition steps left in the device by the $m$-th particle and its secondaries is $\mathcal{S}_m$, and the number of initial electron-hole pairs converted from the $k$-th deposition step is $N_{\text{pairs}, k}$. Then the total number of initial electron-hole pairs $N_{\text{bunch}}$ generated in the device by one bunch and the bunch charge collection efficiency $\eta$ are:

$$N_{\text{bunch}} = \sum_{m=1}^{M}\sum_{k \in \mathcal{S}_m} N_{\text{pairs}, k}, \qquad \eta = \frac{\left|\sum_{j} Q_{j}\right|}{N_{\text{bunch}}\,e_0} \tag{1}$$

where:

- $M$: number of primary particles emitted simultaneously per bunch (per event), count (in the default `bunch.json`, $M = 3$);
- $N_{\text{pairs}, k}$: number of electron-hole pairs obtained for the $k$-th deposition step by dividing the deposited energy $E_k$ ($\text{MeV}$) by the mean ionization energy $\varepsilon_{\text{pair}}\times 10^{-6}$ with Fano sampling, pairs;
- $N_{\text{bunch}}$: total number of initial electron-hole pairs generated in the device by a single bunch (written to the `pairs` dataset of `current.h5`), pairs;
- $Q_j$: signed net charge induced on the $j$-th readout electrode during the drift of all carriers from that bunch, $\text{C}$;
- $e_0$: elementary charge; the code constant `ELEMENTARY_CHARGE` is $1.602176634\times 10^{-19}\ \text{C}$;
- $\eta$: single-bunch charge collection efficiency (dimensionless).

Eq. (1) is computed by `ionized_pairs` in [`core/deposit/ionization.py`](../core/deposit.md) and `collection_efficiency` in [`core/analysis/collection.py`](../core/analysis.md); the bunch arrival time difference $\Delta t = t_{\text{reco}} - t_{\text{truth}}$ and the truncated-Gaussian time-resolution fit are identical to Eq. (2) of [`signal`](../bench/signal.md#standard-practice-and-physical-definitions). A review of charged-particle beam monitoring with silicon carbide semiconductor detectors is given in Ref. [1] (M. De Napoli, “SiC detectors: A review on the use of silicon carbide as radiation detection material”, *Front. Phys.* 10 (2022) 898833, doi:10.3389/fphy.2022.898833).

### Bunch Source `bunch` and Setup Geometry

By default, `bmos` uses the `device_alone` Geant4 setup (`raser/components/deposit/device_alone.py`) and the dedicated bunch source `bunch` (`src/raser_app/bmos/components/deposit/bunch.json`; see [energy deposition components (`components/deposit`)](../components/deposit.md) for both):

- **Geant4 setup (`device_alone`)**: the world cube material is vacuum `"G4_Galactic"` (default half-side `WORLD_HALF_SIDE = 25000` $\mu\text{m}$); the monitoring device logical volume `"Device"` has its top surface centered at the origin $(0, 0, 0)\ \mu\text{m}$, occupying $x \in [-l_x/2, l_x/2]$, $y \in [-l_y/2, l_y/2]$, $z \in [0, l_z]\ \mu\text{m}$, with maximum step size `maxstep = 2` $\mu\text{m}$ inside the device; the reference source position is `at = [0, 0, -17000]` $\mu\text{m}$ ($17\ \text{mm}$ above the top surface), aiming at `towards = [0, 0, 0]` $\mu\text{m}$ with incidence angle `angle = 0` $\text{degree}$.
- **Bunch source (`bunch.json`)**: source kind `"kind": "beam"`, particle type `"par_type": "proton"` (proton), single-particle kinetic energy `"par_energy": 80` $\text{MeV}$, and transverse random offset half-widths `par_randx = 0`, `par_randy = 0` $\mu\text{m}$. The `"particles"` list contains `3` simultaneously emitted proton entries whose translation vectors `"offset"` relative to the reference origin `at` and aim point `towards` are:
  - Proton 1: `offset = [-1, 1, 0]` $\mu\text{m}$ (fired from `[-1, 1, -17000]` $\mu\text{m}$ along $+z$ toward `[-1, 1, 0]` $\mu\text{m}$);
  - Proton 2: `offset = [0, 1, 0]` $\mu\text{m}$ (fired from `[0, 1, -17000]` $\mu\text{m}$ along $+z$ toward `[0, 1, 0]` $\mu\text{m}$);
  - Proton 3: `offset = [1, 1, 0]` $\mu\text{m}$ (fired from `[1, 1, -17000]` $\mu\text{m}$ along $+z$ toward `[1, 1, 0]` $\mu\text{m}$).

  The three $80\ \text{MeV}$ protons enter the device simultaneously side by side along the $x$ direction with $1\ \mu\text{m}$ spacing in the $y = +1\ \mu\text{m}$ plane.

Limitations: the `3` protons of a bunch in `bunch.json` are emitted in parallel at the exact same initial time (`0.0 s`), without the longitudinal bunch length or transverse Gaussian angular divergence of a real accelerator bunch; the `current` stage drifts the carrier clusters produced by the `3` protons in the same bunch independently in the static applied electric field and linearly superimposes their induced currents, without plasma or space-charge mutual shielding effects between high-density tracks.

### Execution Steps and Built-in Constants

`bmos` is defined in `src/raser_app/bmos/` and directly reuses the execution flow of the eight-stage chain; in `examples/bmos/config.json`, `deposit.source` is set to `"bunch"`, `deposit.plots` and `current.plots` are set to `0`, and the `src/raser_app/bmos/components/` component path is mounted:

1. **Shared field check and solve (`field`)**: reuses the field node of the monitoring device at the target bias `field.voltage` ($\text{V}$) and irradiation fluence `field.irradiation_flux` ($\text{cm}^{-2}$, $1\ \text{MeV}$ neutron-equivalent fluence); if no field is found, the required field is solved before jobs begin and stored in `field/` of the device project.
2. **Single-bunch multi-particle Geant4 deposition (`deposit`)**: in each Geant4 event, `GeneralPrimaryGeneratorAction` loops over the `particles` list in `bunch.json` and calls `beam.GeneratePrimaryVertex(event)` for each particle (`beam` taken from `shot["guns"]`), emitting `3` `80 MeV` protons simultaneously; it aggregates all deposition steps of the entire bunch inside `"Device"`, records `1` valid bunch event whenever the total bunch deposited energy satisfies the energy window, and repeats until `deposit.events_per_job` (`1` in the example) bunches are recorded and written to `deposit.h5` in the `deposit` node.
3. **Drift, readout, digitization, triggering, reconstruction, and analysis (`current`, `readout`, `digitizer`, `trigger`, `reconstruction`, `analysis`)**: drifts all electron-hole pair clusters from the same bunch in the solved field and sums them into a single bunch induced-current waveform written to `current.h5` in the `current` node (`current.plots = 0` in the example, so per-bunch drift plots are not drawn); then [`readout`](../stages/readout.md) writes analog voltage waveforms to `readout.h5`, [`digitizer`](../stages/digitizer.md) quantizes the waveforms into codes according to the sampling rate and bit depth and writes them to `digitizer.h5`, and [`trigger`](../stages/trigger.md) selects recorded events according to the trigger condition and writes them to `trigger.h5` (containing the event-number dataset `event`, `int64`); [`reconstruction`](../stages/reconstruction.md) reads the events recorded by `trigger` from `digitizer.h5`, converts the quantized codes back to voltage ($\text{V}$, with sample timestamps `t0 + k·sampling_period`) using `lsb_V` and `offset_V`, extracts pulse features, and writes `reconstruction.h5` marking events where a cluster seed is found as `selected`; finally, [`analysis`](../stages/analysis.md) computes charge collection efficiency using all events in the `current` node and time resolution using `selected` events. The steps and built-in constants (`WORLD_HALF_SIDE = 25000 um`, `t_bin`/`delta_t`, `PART_EDGE = 1e-3`, `BASELINE_POINTS = 200`, `ELEMENTARY_CHARGE = 1.602176634e-19 C`, `MINIMUM_EVENTS = 20`, `ROUNDS = 6`) are identical to [`signal`](../bench/signal.md#execution-steps-and-built-in-constants).

## Stages and Components Used

### Stages

- [`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), [`analysis`](../stages/analysis.md): identical to [`signal`](../bench/signal.md#stages-and-components-used), except that [`deposit`](../stages/deposit.md) transports `3` `80 MeV` protons in a bunch per event with plotting disabled in the example (`deposit.plots = 0`), and [`current`](../stages/current.md) disables per-bunch plotting in the example (`current.plots = 0`).

### Components

- [Detector components (`components/device`)](../components/device.md): provides the online beam monitoring device definition (such as the dedicated 4H-SiC PiN device `NJU-PiN-bmos.json`, dimensions $5000 \times 5000 \times 100\ \mu\text{m}$, default bias `-500.0 V`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides the default multi-particle bunch source `bunch.json` (`src/raser_app/bmos/components/deposit/bunch.json`) and the default Geant4 setup `device_alone.py` (`raser/components/deposit/device_alone.py`).
- [Front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), [trigger components (`components/trigger`)](../components/trigger.md): provides the SPICE front-end amplifier chain (default `SantaCruz+Gali52+Termination50`), digitization sampling and quantization, and trigger threshold definitions.

## Usage and Configuration

Run the `bmos` application, or use `--set` and `--scan` to modify and scan bias voltage, device, and beam parameters (the device is specified in `config.json` and can serve as a scan axis; see [Architecture Overview](../architecture.md#experiments-are-python-classes) and [Command-Line Interface](../cli.md#commands) for CLI usage):

```bash
raser bmos
raser bmos --scan field.voltage=-300,-500
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the configuration structure of the experiment directory `work/bmos/config.json` is shown below. Only the sections relevant to this page are excerpted here; `examples/bmos/config.json` specifies all eight sections in full.

```json
{
  "workflow": "bmos",
  "device": "NJU-PiN-bmos",
  "field": {
    "voltage": -500.0,
    "irradiation_flux": null
  },
  "deposit": {
    "source": "bunch",
    "g4setup": "device_alone",
    "events_per_job": 1,
    "fano": true,
    "plots": 0
  },
  "current": {
    "plots": 0
  },
  "readout": {
    "amplifier": "SantaCruz+Gali52+Termination50",
    "sheet_resistance": null
  },
  "reconstruction": {
    "threshold": 10.0,
    "amplitude_threshold": 10.0,
    "fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    "edge": null
  }
}
```

The configuration keys that users can set in `bmos` are listed below (see [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md#settings) for details of each stage's settings). "Value in Example" lists the values written in `examples/bmos/config.json`; if a required key is missing from `config.json`, an error is raised naming the missing `section.key`:

| Section.Key | Value in Example | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `-500.0` (uses the bias voltage in the device file when `null`) | $\text{V}$ | Monitoring device reverse bias voltage |
| `field.irradiation_flux` | `null` (uses the irradiation fluence in the device file, or `0` if the device file has no irradiation block) | $\text{cm}^{-2}$ | Monitoring device irradiation fluence ($1\ \text{MeV}$ neutron-equivalent fluence) |
| `deposit.source` | `"bunch"` | None | Signal source component name or path |
| `deposit.g4setup` | `"device_alone"` | None | Geant4 setup component name or path |
| `deposit.events_per_job` | `1` | events (bunches) | Number of valid deposited bunches to record per job (mutually exclusive with `deposit.generated_per_job`) |
| `deposit.generated_per_job` | `null` (unused) | events (bunches) | Total number of bunches generated from the source per job (mutually exclusive with `deposit.events_per_job`) |
| `deposit.generated_limit` | `10000000` | events (bunches) | Maximum number of generated bunches allowed to reach `deposit.events_per_job` |
| `deposit.edep_min` | `null` (no lower bound) | $\text{MeV}$ | Lower bound on total deposited energy in the device for a recorded bunch |
| `deposit.edep_max` | `null` (no upper bound) | $\text{MeV}$ | Upper bound on total deposited energy in the device for a recorded bunch |
| `deposit.fano` | `true` | None | Whether to enable Fano fluctuation sampling when converting deposited energy to ionized pairs |
| `deposit.plots` | `0` | events (bunches) | Number of leading recorded bunches per job for which Geant4 geometry and track plots are drawn |
| `current.plots` | `0` | events (bunches) | Number of leading recorded bunches per job for which carrier drift path and current plots are drawn |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `readout.sheet_resistance` | `null` (uses the resistive-layer sheet resistance in the device file) | $\Omega$ | Overrides the resistive-layer sheet resistance for devices containing `resistive_layer` |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | Threshold-crossing level for extracting `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | Amplitude threshold for cluster seed channels; events recorded by `trigger` in which a seed is found are marked as `selected` (whether an event is recorded is decided by `trigger`) |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` | `null` (inherits `pulse_edge` written by `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` |

All other parameters (default Geant4 world half-side `25000 um`, material mean ionization energy and Fano factor, drift time-window and time-step profiles, thermal diffusion flag `diffusion = True`, `ngspice` noise-analysis frequency range and `27 °C` temperature, `200` reconstruction baseline points, minimum sample count `20` and maximum iteration rounds `6` for the truncated-Gaussian fit) are hardcoded in the source code.

## Outputs

Results are stored under `work/bmos/` (see [Architecture Overview](../architecture.md#results) for the storage layout): per-stage nodes are in `work/bmos/nodes/<stage>/<node>/` (each containing a `node.json`; one node per job from `deposit` through `reconstruction`, and one node per scan point for `analysis`), per-scan-point views are at `work/bmos/points/<point>/<stage>/<job>` (symlinks, with `points/<point>/field` and `points/<point>/analysis` each being a single symlink), the parameter table is `work/bmos/points.json`, cross-point statistics and trend plots are in `work/bmos/analysis/`, and the monitoring device's field nodes are stored under `work/<device>/field/<node>/`.

The data files written inside each job's per-stage nodes are `deposit.h5`, `current.h5`, `readout.h5`, `digitizer.h5` (quantized codes; see [`stages/digitizer`](../stages/digitizer.md) for the format), `trigger.h5` (the `int64` dataset `event` of recorded event numbers; see [`stages/trigger`](../stages/trigger.md)), and `reconstruction.h5`; plots produced by each stage are placed inside that stage's node (such as `nodes/deposit/<node>/g4_geometry.png` when `deposit.plots > 0`, and `drift_path_<event>` and `current_<event>`, each as `.png`, `.pdf`, `.root`, under `nodes/current/<node>/plots/` when `current.plots > 0`). Each scan point's [`analysis`](../stages/analysis.md) node (accessed via `points/<point>/analysis/`) writes the single-point statistical results (`result.json`, `events.h5`) and single-point plots (`efficiency`, `amplitude`, `time_difference`, `resolution_of_fraction`, each as `.png` and `.pdf`), while the cross-point summary table `points.json` and trend plot `trend.png` and `trend.pdf` are written under `work/bmos/analysis/`. The fields and units of each file are identical to [`signal`](../bench/signal.md#outputs), with each recorded event corresponding to one bunch.
