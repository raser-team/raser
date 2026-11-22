# Beam Monitor Online System (`apps/bmos`)

`bmos` (Beam Monitor Online System, in the `raser_app` package) is a configuration of [`signal`](../bench/signal.md) that switches to the multi-particle bunch source `bunch` (each event represents one bunch emitting `3` `80 MeV` protons simultaneously) and disables per-event plotting by default (`deposit.plots = 0`, `current.plots = 0`). Centered on the monitoring device placed in the beam path, it reads [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence—[`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md)—outputting the superimposed induced current pulses, readout voltage waveforms, charge collection efficiency, and time resolution produced by bunches in the monitoring device.

## Setup and Standard Practice

### Standard Practice and Physical Definitions

In academic practice for online beam monitoring (Beam Monitor Online System) on proton or heavy-ion accelerator beamlines, a radiation-hard wide-bandgap semiconductor detector (such as the 4H-SiC PiN diode `NJU-PiN-bmos`) is placed directly in the beam path. Bunch by bunch, it measures the superimposed transient induced current pulse and total collected charge produced when multiple charged particles in a bunch traverse the detector simultaneously, thereby monitoring the intensity (particle count), arrival time, and pulse amplitude distribution of each bunch online.

In RASER, a single bunch is simulated as a single Geant4 event. Suppose one bunch emits $M$ particles simultaneously, the set of deposition steps left in the device by the $m$-th particle and its secondaries is $\mathcal{S}_m$, and the number of initial electron-hole pairs converted from the $k$-th deposition step is $N_{\text{pairs}, k}$. Then the total number of initial electron-hole pairs $N_{\text{bunch}}$ generated in the device by one bunch and the bunch charge collection efficiency $\eta$ are:

$$N_{\text{bunch}} = \sum_{m=1}^{M}\sum_{k \in \mathcal{S}_m} N_{\text{pairs}, k}, \qquad \eta = \frac{\left|\sum_{j} Q_{j}\right|}{N_{\text{bunch}}\,e_0} \tag{1}$$

where:

- $M$: number of primary particles emitted simultaneously per bunch (per event), count (in the default `bunch.json`, $M = 3$);
- $N_{\text{pairs}, k}$: number of electron-hole pairs obtained for the $k$-th deposition step by dividing the deposited energy $E_k$ ($\text{MeV}$) by the mean ionization energy $\varepsilon_{\text{pair}}\times 10^{-6}$ with Fano sampling, pairs;
- $N_{\text{bunch}}$: total number of initial electron-hole pairs generated in the device by a single bunch (written to the `pairs` dataset of `current_<job>.h5`), pairs;
- $Q_j$: signed net charge induced on the $j$-th readout electrode during the drift of all carriers from that bunch, $\text{C}$;
- $e_0$: elementary charge; the code constant `ELEMENTARY_CHARGE` is $1.602176634\times 10^{-19}\ \text{C}$;
- $\eta$: single-bunch charge collection efficiency (dimensionless).

Eq. (1) is computed by `ionized_pairs` in [`core/deposit/ionization.py`](../core/deposit.md) and `collection_efficiency` in [`core/analysis/collection.py`](../core/analysis.md); the bunch arrival time difference $\Delta t = t_{\text{reco}} - t_{\text{truth}}$ and the truncated-Gaussian time-resolution fit are identical to Eq. (2) of [`signal`](../bench/signal.md#standard-practice-and-physical-definitions). A review of charged-particle beam monitoring with silicon carbide semiconductor detectors is given in Ref. [1] (M. De Napoli, “SiC detectors: A review on the use of silicon carbide as radiation detection material”, *Front. Phys.* 10 (2022) 898833, doi:10.3389/fphy.2022.898833).

### Bunch Source `bunch` and Setup Geometry

By default, `bmos` uses the `device_alone` Geant4 setup (`src/raser/components/g4setup/device_alone.py`) and the dedicated bunch source `bunch` (`src/raser/apps/bmos/components/source/bunch.json`):

- **Geant4 setup (`device_alone`)**: the world cube material is vacuum `"G4_Galactic"` (default half-side `WORLD_HALF_SIDE = 25000` $\mu\text{m}$); the monitoring device logical volume `"Device"` has its top surface centered at the origin $(0, 0, 0)\ \mu\text{m}$, occupying $x \in [-l_x/2, l_x/2]$, $y \in [-l_y/2, l_y/2]$, $z \in [0, l_z]\ \mu\text{m}$, with maximum step size `maxstep = 2` $\mu\text{m}$ inside the device; the reference source position is `at = [0, 0, -17000]` $\mu\text{m}$ ($17\ \text{mm}$ above the top surface), aiming at `towards = [0, 0, 0]` $\mu\text{m}$ with incidence angle `angle = 0` $\text{degree}$.
- **Bunch source (`bunch.json`)**: source kind `"kind": "beam"`, particle type `"par_type": "proton"` (proton), single-particle kinetic energy `"par_energy": 80` $\text{MeV}$, and transverse random offset half-widths `par_randx = 0`, `par_randy = 0` $\mu\text{m}$. The `"particles"` list contains `3` simultaneously emitted proton entries whose translation vectors `"offset"` relative to the reference origin `at` and aim point `towards` are:
  - Proton 1: `offset = [-1, 1, 0]` $\mu\text{m}$ (fired from `[-1, 1, -17000]` $\mu\text{m}$ along $+z$ toward `[-1, 1, 0]` $\mu\text{m}$);
  - Proton 2: `offset = [0, 1, 0]` $\mu\text{m}$ (fired from `[0, 1, -17000]` $\mu\text{m}$ along $+z$ toward `[0, 1, 0]` $\mu\text{m}$);
  - Proton 3: `offset = [1, 1, 0]` $\mu\text{m}$ (fired from `[1, 1, -17000]` $\mu\text{m}$ along $+z$ toward `[1, 1, 0]` $\mu\text{m}$).

  The three $80\ \text{MeV}$ protons enter the device simultaneously side by side along the $x$ direction with $1\ \mu\text{m}$ spacing in the $y = +1\ \mu\text{m}$ plane.

Limitations: the `3` protons of a bunch in `bunch.json` are emitted in parallel at the exact same initial time (`0.0 s`), without the longitudinal bunch length or transverse Gaussian angular divergence of a real accelerator bunch; the `current` stage drifts the carrier clusters produced by the `3` protons in the same bunch independently in the static applied electric field and linearly superimposes their induced currents, without plasma or space-charge mutual shielding effects between high-density tracks.

### Execution Steps and Built-in Constants

The workflow definition of `bmos` (`src/raser/apps/bmos/__init__.py:11-28`) directly reuses all slices and execution functions of `stages.chain`, only overriding `"source"` to `"bunch"` and `"plots"` to `0` in `defaults` and mounting the component path `"apps/bmos"`:

1. **Shared field check and solve (`field`)**: locates or automatically invokes `raser field` to solve the shared field of the monitoring device at the target bias `voltage` ($\text{V}$) and irradiation fluence `irradiation` ($\text{neq/cm}^2$).
2. **Single-bunch multi-particle Geant4 deposition (`deposit`)**: in each Geant4 event, `GeneralPrimaryGeneratorAction` loops over the `particles` list in `bunch.json` and calls `beam.GeneratePrimaryVertex(event)` for each particle (`beam` taken from `shot["guns"]`), emitting `3` `80 MeV` protons simultaneously; it aggregates all deposition steps of the entire bunch inside `"Device"`, records `1` valid bunch event whenever the total bunch deposited energy satisfies the energy window, and repeats until `events_per_job` (default `1`) bunches are recorded and written to `deposit_<job>.h5`.
3. **Drift, readout, reconstruction, and analysis (`current`, `readout`, `reconstruction`, `analysis`)**: drifts all electron-hole pair clusters from the same bunch in the solved field and sums them into a single bunch induced-current waveform written to `current_<job>.h5` (with `plots = 0` by default, so per-bunch drift plots are not drawn), then computes the bunch output voltage waveform, pulse features, charge collection efficiency, and time resolution through [`readout`](../stages/readout.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md). The steps and built-in constants (`WORLD_HALF_SIDE = 25000 um`, `GENERATED_LIMIT = 10000000`, `t_bin`/`delta_t`, `PART_EDGE = 1e-3`, `BASELINE_POINTS = 200`, `ELEMENTARY_CHARGE = 1.602176634e-19 C`, `MINIMUM_EVENTS = 20`, `ROUNDS = 6`) are identical to [`signal`](../bench/signal.md#execution-steps-and-built-in-constants).

## Stages and Components Used

### Stages

- [`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), [`analysis`](../stages/analysis.md): identical to [`signal`](../bench/signal.md#stages-and-components-used), except that [`deposit`](../stages/deposit.md) transports `3` `80 MeV` protons in a bunch per event and [`current`](../stages/current.md) disables per-bunch plotting by default (`plots = 0`).

### Components

- [Detector components (`components/device`)](../components/device.md): provides the online beam monitoring device definition (such as the dedicated 4H-SiC PiN device `NJU-PiN-bmos.json`, dimensions $5000 \times 5000 \times 100\ \mu\text{m}$, default bias `-500.0 V`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides the default multi-particle bunch source `bunch.json` (`src/raser/apps/bmos/components/source/bunch.json`) and the default Geant4 setup `device_alone.py`.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), [trigger components (`components/trigger`)](../components/trigger.md): provides the SPICE front-end amplifier chain (default `SantaCruz+Gali52+Termination50`), digitization sampling and quantization, and trigger threshold definitions.

## Usage and Configuration

Following the top-level design ([Architecture Overview](../architecture.md#experiments-are-python-classes), [Command-Line Interface](../cli.md#commands)), run the `bmos` application or use `--set` and `--scan` to scan bias voltage, device, and beam parameters:

```bash
raser bmos
raser bmos --scan field.voltage=-300,-500
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the configuration structure of the experiment directory `work/bmos/config.json` is:

```json
{
  "workflow": "bmos",
  "device": "NJU-PiN-bmos",
  "field": {
    "voltage": -500.0,
    "irradiation": null
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

The configuration keys that users can set in `bmos` are listed below (`src/raser/apps/bmos/__init__.py:11-21` and `src/raser/stages/chain.py:14-106`):

| Section.Key (Code Key) | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` (equivalent to `field.device.bias.voltage`) | `bias.voltage` from the device file | $\text{V}$ | Monitoring device reverse bias voltage (CLI `-vol`/`--voltage`) |
| `field.irradiation` (`irradiation`) | `None` (uses device `irradiation.irradiation_flux` if omitted, or `0` if absent) | $\text{neq/cm}^2$ | Monitoring device irradiation fluence (CLI `-irr`/`--irradiation`) |
| `deposit.source` (`source`) | `"bunch"` | None | Signal source component name or path (CLI optional positional argument `source`) |
| `deposit.g4setup` (`g4setup`) | `"device_alone"` | None | Geant4 setup component name or path (CLI `--g4setup`) |
| `deposit.events_per_job` (`events_per_job`) | `1` | events (bunches) | Number of valid deposited bunches to record per job (CLI `-evt`/`--events-per-job`, mutually exclusive with `generated_per_job`) |
| `deposit.generated_per_job` (`generated_per_job`) | `None` | events (bunches) | Total number of bunches generated from the source per job (CLI `-gen`/`--generated-per-job`, mutually exclusive with `events_per_job`) |
| `deposit.generated_limit` (`generated_limit`) | `None` (`10000000` at runtime) | events (bunches) | Maximum number of generated bunches allowed to reach `events_per_job` (CLI `--generated-limit`) |
| `deposit.edep_min` (`edep_min`) | `None` | $\text{MeV}$ | Lower bound on total deposited energy in the device for a recorded bunch (CLI `--edep-min`) |
| `deposit.edep_max` (`edep_max`) | `None` | $\text{MeV}$ | Upper bound on total deposited energy in the device for a recorded bunch (CLI `--edep-max`) |
| `deposit.fano` (`fano`) | `True` | None | Whether to enable Fano fluctuation sampling when converting deposited energy to ionized pairs |
| `deposit.plots` | `0` | events (bunches) | Number of leading recorded bunches per job for which Geant4 geometry and track plots are drawn |
| `current.plots` | `0` | events (bunches) | Number of leading recorded bunches per job for which carrier drift path and current plots are drawn |
| `readout.amplifier` (`amplifier`) | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` (CLI `-amp`/`--amplifier`) |
| `readout.sheet_resistance` (`sheet_resistance`) | `None` | $\Omega$ | Overrides the resistive-layer sheet resistance for devices containing `resistive_layer` (CLI `--sheet-resistance`) |
| `reconstruction.threshold` (`threshold`) | `10.0` | $\text{mV}$ | Threshold-crossing level for extracting `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster (CLI `-threshold`) |
| `reconstruction.amplitude_threshold` (`amplitude_threshold`) | `10.0` | $\text{mV}$ | Pulse amplitude threshold for finding cluster seeds (whether an event is recorded is decided by `trigger`) (CLI `-amplitude_threshold`) |
| `reconstruction.fractions` (`fractions`) | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` (`edge`) | `None` (inherits `pulse_edge` written by `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` (CLI `--edge`) |

All other parameters (default Geant4 world half-side `25000 um`, default maximum generated bunch limit `10000000`, material mean ionization energy and Fano factor, drift time-window and time-step profiles, thermal diffusion flag `diffusion = True`, `ngspice` noise-analysis frequency range and `27 °C` temperature, `200` reconstruction baseline points, minimum sample count `20` and maximum iteration rounds `6` for the truncated-Gaussian fit) are hardcoded in the source code.

## Outputs

Following the design in [Architecture Overview](../architecture.md#experiments-are-python-classes) and [Results](../architecture.md#results), outputs of application classes are stored under `work/bmos/` (underlying nodes in `work/bmos/nodes/<stage>/<node>/`, per-scan-point views in `work/bmos/points/<point>/<stage>`, parameter table in `work/bmos/points.json`, and cross-point statistics and trend plots in `work/bmos/analysis/`).

The filenames, fields, and units of the per-job data files (`deposit_<job>.h5`, `current_<job>.h5`, `readout_<job>.h5`, `reconstruction_<job>.h5`), the statistical results written by [`analysis`](../stages/analysis.md) (`result.json`, `events.h5`, `points.json`), and the plot files (`efficiency.png`, `amplitude.png`, `time_difference.png`, `resolution_of_fraction.png`, `points.png`, as well as `g4_geometry.png`, `<det_model>_drift_path.pdf`/`.root`, and `No_<k>electrode_basic_infor.pdf`/`.root` when `plots > 0`) are identical to [`signal`](../bench/signal.md#outputs), with each recorded event corresponding to one bunch.
