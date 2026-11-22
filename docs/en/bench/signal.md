# Single-Device Signal Test (`bench/signal`)

`signal` (in the `raser_bench` package) is the baseline full-chain benchmark test for a single device, centered on the device under test specified on the command line. It reads a single device together with one source, setup, and electronics configuration from [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), executes all eight stages in sequence—[`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md)—and outputs the charge collection efficiency and time resolution relative to the true deposition time of the device under test. Time resolution relative to the true deposition time is not experimentally observable; to measure experimentally observable time resolution, use [`timeres`](timeres.md).

## Setup and Standard Practice

### Standard Practice and Physical Definitions

When testing the signal response and charge collection efficiency (CCE) of a single semiconductor detector in the laboratory, a radioactive source ($\beta$ source, $\alpha$ source), monoenergetic particle beam, or pulsed laser illuminates the reverse-biased device under test. The induced current on the readout electrode is converted to a voltage waveform through a front-end amplifier, digitizer, and trigger selection, and the charge collection efficiency is given by the ratio of collected charge to the initial charge ionized by the incident particle in the sensitive volume.

In RASER, the single-event charge collection efficiency $\eta$ and the time difference $\Delta t$ between the reconstructed timing timestamp and the true deposition time are:

$$\eta = \frac{\left|\sum_{j} Q_{j}\right|}{N_{\text{pairs}}\,e_0} \tag{1}$$

$$\Delta t = t_{\text{reco}} - t_{\text{truth}}, \qquad t_{\text{truth}} = \min_{k} t_{k} \tag{2}$$

where:

- $\eta$: single-event charge collection efficiency (dimensionless; $\eta > 1$ when avalanche multiplication is present);
- $Q_j$: signed net induced charge on the $j$-th readout electrode, $\text{C}$ (given by the `charge` dataset of `current_<job>.h5`, including underflow and overflow bins before and after the time window);
- $N_{\text{pairs}}$: total number of initial electron-hole pairs ionized inside the device in that event (before multiplication), pairs (given by the `pairs` dataset of `current_<job>.h5`);
- $e_0$: elementary charge; the code constant `ELEMENTARY_CHARGE` is $1.602176634\times 10^{-19}\ \text{C}$;
- $t_{\text{reco}}$: pulse timing timestamp extracted from the reconstructed waveform (threshold-crossing time `ToA`, time center of gravity `CoG`, or each constant-fraction timestamp `CFD10`–`CFD90`), $\text{s}$;
- $t_k$: global time of the $k$-th energy deposition step for that event in `deposit_<job>.h5`, $\text{s}$; $t_{\text{truth}}$ is the time `truth` of the earliest deposition step in that event, $\text{s}$;
- $\Delta t$: time difference of the reconstructed timestamp relative to the true earliest deposition time, $\text{s}$.

Eq. (1) is computed by `collection_efficiency(charge, pairs)` in [`core/analysis/collection.py`](../core/analysis.md) and summarized by `efficiency_spread` in [`stages/analysis/collection.py`](../stages/analysis.md) into sample mean `mean`, standard error of the mean `mean_error`, and sample standard deviation `spread` (degrees-of-freedom correction `ddof=1`). Eq. (2) is computed by `event_times` and `time_widths` in [`stages/analysis/timing.py`](../stages/analysis.md), which invokes `core_width` in [`core/analysis/resolution.py`](../core/analysis.md) on events recorded by `trigger` to perform iterative truncated-Gaussian maximum-likelihood fitting and report the core width `sigma` and `sigma68` (in $\text{s}$). Signal formation and charge collection measurement principles in semiconductor detectors are described in Ref. [1] (G. Lutz, *Semiconductor Radiation Detectors: Device Physics*, Springer (2007), doi:10.1007/978-3-540-71679-2).

Limitations: Eq. (2) directly uses the simulated true earliest deposition time $t_{\text{truth}}$ as reference, excluding reference-detector timing jitter and coincidence triggering, and is not directly observable in real experiments.

### Geant4 Setup Geometry

The default setup is `device_alone` (`src/raser/components/g4setup/device_alone.py`, see [`../components/deposit.md`](../components/deposit.md)): the world cube material is vacuum `"G4_Galactic"` (default half-side `WORLD_HALF_SIDE = 25000` $\mu\text{m}$), and the device logical volume `"Device"` sits alone at the world center with its top surface centered at the origin $(0, 0, 0)\ \mu\text{m}$, occupying $x \in [-l_x/2, l_x/2]$, $y \in [-l_y/2, l_y/2]$, $z \in [0, l_z]\ \mu\text{m}$, with maximum step size `maxstep = 2` $\mu\text{m}$ inside the device. The radioactive source or beam origin sits $17\ \text{mm}$ above the top surface (`at = [0, 0, -17000]` $\mu\text{m}$), aiming at the origin `towards = [0, 0, 0]` $\mu\text{m}$ with incidence angle `angle = 0` $\text{degree}$.

Charge collection efficiency is produced by this setup using the same batch of events as time resolution; measuring efficiency does not use a separate setup.

In addition, the `signal` component directory (`src/raser/bench/signal/components/g4setup/`) provides `Sr90_collimator` (in air `"G4_AIR"`, a $10000 \times 10000 \times 5000\ \mu\text{m}$ brass `"G4_BRASS"` collimator centered at $z = -14000\ \mu\text{m}$ spanning $z \in [-16500, -11500]\ \mu\text{m}$, with a centered circular hole of radius `tub_radius = 500` $\mu\text{m}$ and half-depth `tub_depth = 2600` $\mu\text{m}$) and `pcb_readout_gdml` (`"geant4_model": "gdml_import"`, importing external `pcb_readout.gdml` with world half-side `world_half_size_um = 2000000` $\mu\text{m}$).

### Four Types of Signal Sources

Changing the source simply changes the source component read by the `deposit` stage; the chain and outputs remain unchanged:

- **$\beta$ source**: defaults to `decay/Sr90` (`src/raser/components/source/decay/Sr90.json`, `"kind": "decay_source"`). Each event draws one stationary decay of $^{90}\text{Sr}$ (`[38, 90]`) or its daughter $^{90}\text{Y}$ (`[39, 90]`) with equal probability on a disk of radius `par_radius = 2500` $\mu\text{m}$ (diameter $5\ \text{mm}$), with decay products emitted isotropically inside a cone of half-opening angle `par_cone = 15` $\text{degree}$ around the axis (solid-angle fraction $f_{\text{gen}} = (1 - \cos 15^\circ)/2 \approx 0.017037$). Electrons penetrate the device so the entire track crosses the sensitive volume, approximating minimum ionizing particles.
- **$\alpha$ source**: for example `decay/Am241` (`src/raser/components/source/decay/Am241.json`, `"kind": "decay_source"`, `par_type = "alpha"`, monoenergetic kinetic energy `par_energy = 5.54` $\text{MeV}$). The $\alpha$ particles stop within a very shallow depth near the surface of the device, concentrating energy deposition near the entrance face.
- **Laser**: single-photon absorption (`"SPA"`) or two-photon absorption (`"TPA"`), incident from the top, bottom, or side (`"top"`, `"bottom"`, `"edge"`), generating carriers near the focus $(x_{\text{focus}}, y_{\text{focus}}, z_{\text{focus}}) = (\text{fx\_rel}\cdot l_x,\, \text{fy\_rel}\cdot l_y,\, \text{fz\_rel}\cdot l_z)$ (in $\mu\text{m}$). See [`../components/deposit.md`](../components/deposit.md) for laser component keys.

- **Beam**: monoenergetic particle beam (`"kind": "beam"`), for example the proton beam `beam/proton` (`src/raser/components/source/beam/proton.json`, `par_type = "proton"`, kinetic energy `par_energy = 1000.0` $\text{MeV}$, transverse random offset half-widths `par_randx = par_randy = 0` $\mu\text{m}$). One event may emit a single particle or emit multiple particles simultaneously via the `particles` list (see [`../apps/bmos.md`](../apps/bmos.md)).

![HPK-Si-PiN single-event carrier drift paths](../images/current-drift-path-HPK-Si-PiN.png)

Electron and hole drift paths for a single event in `HPK-Si-PiN` under the default `decay/Sr90` source: the $\beta$ electron traverses the entire device, and carriers generated along the track drift toward opposite electrodes.

![HPK-Si-PiN single-event induced current](../images/current-event-HPK-Si-PiN.png)

Induced current on the readout electrode for the same Sr90 $\beta$-electron event: electron component, hole component, and total current.

### Execution Steps and Built-in Constants

A single `signal` job executes in the following order:

1. **Check and solve shared field (`field`)**: before launching jobs, the main command calls `field.SHARED.ready` to check whether `<project>/field/` contains electric and weighting fields matching the current device, bias `voltage` ($\text{V}$), and irradiation fluence `irradiation` ($\text{neq/cm}^2$); if not ready, it runs `raser field` first. When the job executes the `field` slice, it writes `{"field": "<shared_field_dir>"}` to `field_<job>.done`.
2. **Energy deposition and ionized-pair generation (`deposit`)**: `stages/deposit.py` calls `write_simulated_deposits` to run Geant4 (or `toy_mip`). Only events with total deposited energy $E_{\text{tot}} > 0$ inside `"Device"` satisfying $\text{edep\_min} \le E_{\text{tot}} \le \text{edep\_max}$ (in $\text{MeV}$; when bounds are unset, only $E_{\text{tot}} > 0$ is required) are kept until `events_per_job` events are recorded (up to `generated_limit` generated source events, raising `RuntimeError` if not reached) or `generated_per_job` source events have been generated. In `ionized_pairs`, each step's deposited energy $E_k$ ($\text{MeV}$) is divided by the material mean ionization energy $\varepsilon_{\text{pair}}\times 10^{-6}$ ($\text{MeV}$) and sampled according to the `fano` switch to obtain electron-hole pair counts; coordinates are shifted by $+l_x/2, +l_y/2$ from Geant4's centered frame into $[0, l_x] \times [0, l_y] \times [0, l_z]\ \mu\text{m}$ and written to `deposit_<job>.h5`. If `0` events are recorded, `Ended` is raised to end the job early.
3. **Carrier drift and induced-current binning (`current`)**: `stages/current.py` loads `DevsimField` and calls `write_induced_currents` (with thermal diffusion enabled by default, `diffusion=True`) to advance electron and hole drift (including irradiation trapping and avalanche multiplication) inside the device and electrode-array bounds for each recorded event, accumulating induced current into time bins of width `t_bin` ($5\ \text{ps}$ in 1D, $50\ \text{ps}$ in 2D/3D) via the Shockley–Ramo theorem and writing `current_<job>.h5`, while drawing drift path and current plots for the first `plots` events.
4. **Equivalent circuit and front-end amplifier readout (`readout`)**: `stages/readout.py` constructs the device equivalent circuit `DeviceCircuit`, splits and loads the SPICE subcircuit chain specified by `amplifier` on `+`, and invokes `ngspice` to solve the transient response and frequency-domain thermal noise spectrum (synthesizing independent time-domain Gaussian thermal noise from the job-slice seed and adding it to the waveform), saving only channels whose maximum voltage swing is $\ge 10^{-3} V_{\max}$ to `readout_<job>.h5`.
5. **Digitization and triggering (`digitizer`, `trigger`)**: `digitizer` converts analog waveforms into digital waveforms according to the sampling and quantization settings of the digitizer component, and `trigger` selects which events to record according to the trigger conditions.
6. **Waveform feature extraction and clustering (`reconstruction`)**: `stages/reconstruction.py` multiplies `threshold` and `amplitude_threshold` in $\text{mV}$ by $10^{-3}$ to convert to $\text{V}$, subtracts the mean baseline of the leading `BASELINE_POINTS = 200` samples and flips polarity according to `edge`, extracts amplitude, `ToA`, `ToT`, `CoG`, `area`, and `CFD` timestamps for each entry in `fractions`, clusters across electrodes seeded by electrodes with amplitude at least `amplitude_threshold`, and writes `reconstruction_<job>.h5`.
7. **Collection efficiency and time resolution statistics (`analysis`)**: `stages/analysis` aggregates all finished jobs per scan point, computes the collection efficiency distribution and time resolution of selected events via Eqs. (1) and (2), and writes per-point `result.json`, `events.h5`, distribution plots, and multi-point comparison files `points.json` and `points.png`.

The built-in constants across the full chain are listed below:

| Constant Name | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | `src/raser/core/deposit/simulate_deposits.py:30`, default minimum half-side of the Geant4 world cube |
| `GENERATED_LIMIT` | `10000000` | events | `src/raser/core/deposit/generation.py:8`, maximum number of generated source events per job when `generated_limit` is unset |
| `PAIR_ENERGY_EV` | `"Si": 3.6`, `"SiC": 8.4`, `"Diamond": 13.1` | $\text{eV}$ | `src/raser/core/deposit/ionization.py:12-18`, mean ionization energy per electron-hole pair for each material |
| `FANO_FACTOR` | `"Si": 0.115`, `"SiC": 0.128`, `"Diamond": 0.382` | dimensionless | `src/raser/core/deposit/ionization.py:20-25`, Fano factor for ionized-pair fluctuations for each material |
| `t_bin`, `delta_t` | 1D: `5e-12`, `2e-12`; 2D/3D: `50e-12`, `20e-12` | $\text{s}$ | `src/raser/core/current/cal_current.py:30-50`, induced-current time-bin width and single drift time step |
| `PART_EDGE` | `1e-3` | dimensionless | `src/raser/core/readout/job.py:23`, minimum ratio of channel voltage swing to maximum channel swing required to save a waveform channel |
| `MILLIVOLT` | `1.0e-3` | $\text{V/mV}$ | `src/raser/stages/reconstruction.py:28`, conversion factor from $\text{mV}$ to $\text{V}$ for `threshold` and `amplitude_threshold` |
| `BASELINE_POINTS` | `200` | samples | `src/raser/core/reconstruction/event.py:7`, fixed number of leading waveform samples used to compute baseline mean and noise standard deviation |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | $\text{C}$ | `src/raser/core/analysis/collection.py:5`, elementary charge used in Eq. (1) to compute charge collection efficiency |
| `MINIMUM_EVENTS`, `ROUNDS` | `20`, `6` | events, rounds | `src/raser/core/analysis/resolution.py:8-9`, minimum sample count and maximum window-shrinking iteration rounds for truncated-Gaussian time-resolution fitting |
| `PICOSECOND` | `1.0e-12` | $\text{s/ps}$ | `src/raser/stages/analysis/plots.py:8`, seconds-to-picoseconds conversion factor for time-difference and time-resolution plots |

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, conductive-region flags, and junction capacitance / undepleted-bulk parameters of the device under test at the target bias and irradiation fluence, stored under `<project>/field/`.
- [`deposit`](../stages/deposit.md): simulates energy deposition steps in the device under test for the selected source and Geant4 setup and converts them into initial electron-hole pairs.
- [`current`](../stages/current.md): drifts, diffuses, and multiplies the deposited electron-hole pairs in the solved field, computing the time-domain induced current and net induced charge on each readout electrode.
- [`readout`](../stages/readout.md): feeds the induced current into the device equivalent circuit and SPICE front-end amplifier chain to solve output voltage waveforms and add circuit thermal noise.
- [`digitizer`](../stages/digitizer.md): converts analog output waveforms into digital waveforms according to the digitizer sampling rate and quantization bit depth.
- [`trigger`](../stages/trigger.md): filters recorded events according to the trigger device selection conditions.
- [`reconstruction`](../stages/reconstruction.md): subtracts the leading `200`-point baseline from readout waveforms and extracts pulse amplitude, `ToA`, `ToT`, `CoG`, `area`, `CFD`, and multi-electrode cluster features.
- [`analysis`](../stages/analysis.md): aggregates finished jobs per scan point, fits charge collection efficiency and time resolution relative to the true deposition time, and draws per-point distributions and cross-point trend plots.

### Components

- [Detector components (`components/device`)](../components/device.md): provides dimensions, material, doping, bias voltage, temperature, irradiation model, avalanche model, and equivalent circuit parameters of the device under test (such as `HPK-Si-PiN.json`, `NJU-PiN.json`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides radioactive sources and beams (such as default `decay/Sr90.json`, `decay/Am241.json`, `beam/proton.json`), lasers (such as `PIL037_top_SiC.json`), and Geant4 setups (such as default `device_alone.py`, `Sr90_collimator.py`).
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides SPICE amplifier stages and termination load subcircuits cascaded with `+` (default `SantaCruz+Gali52+Termination50`).
- [Digitizer components (`components/digitizer`)](../components/digitizer.md): provides sampling and quantization settings of an oscilloscope or digitizer board; for devices that also perform triggering (such as an oscilloscope `scope`), their trigger conditions are specified here as well.
- [Trigger components (`components/trigger`)](../components/trigger.md): provides trigger selection condition definitions for standalone trigger devices.

## Usage and Configuration

Run `signal` directly on the device under test (quick-start example; see [Getting Started Section 4](../getting-started.md#4-results-of-each-step-in-the-chain) for outputs and plots at each step of the chain):

```bash
raser signal HPK-Si-PiN
```

Set `source` in the `deposit` section of `config.json` or use `--set` on the command line to switch the signal source (for example, to the $\alpha$ source `decay/Am241`):

```bash
raser signal HPK-Si-PiN --set deposit.source=decay/Am241
```

Scanning bias voltage, source energy, or laser pulse energy and wavelength with `--scan` is all performed in `signal`; when the scan axis is the laser position relative to the device, use [`tct`](tct.md) instead:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the experiment directory `<project>/signal/config.json` records settings sectioned by stage:

```json
{
  "workflow": "signal",
  "device": "HPK-Si-PiN",
  "field": {
    "voltage": 200.0,
    "irradiation": null
  },
  "deposit": {
    "source": "decay/Sr90",
    "g4setup": "device_alone",
    "events_per_job": 200,
    "fano": true,
    "plots": 100
  },
  "current": {
    "plots": 100
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

The configuration keys users can set in `signal` are listed below (`src/raser/stages/chain.py:14-106`):

| Section.Key (Code Key) | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` (equivalent to `field.device.bias.voltage`) | `bias.voltage` from the device file | $\text{V}$ | Reverse bias voltage of the device under test (CLI `-vol`/`--voltage`) |
| `field.irradiation` (`irradiation`) | `None` (uses device `irradiation.irradiation_flux` if omitted, or `0` if absent) | $\text{neq/cm}^2$ | Irradiation fluence of the device under test (CLI `-irr`/`--irradiation`) |
| `deposit.source` (`source`) | `"decay/Sr90"` | None | Radioactive source or beam component name or path (CLI optional positional argument `source`) |
| `deposit.g4setup` (`g4setup`) | `"device_alone"` | None | Geant4 setup component name or path (CLI `--g4setup`) |
| `deposit.events_per_job` (`events_per_job`) | `1` | events | Number of valid deposited events to record per job (CLI `-evt`/`--events-per-job`, mutually exclusive with `generated_per_job`) |
| `deposit.generated_per_job` (`generated_per_job`) | `None` | events | Total number of events generated from the source per job (CLI `-gen`/`--generated-per-job`, mutually exclusive with `events_per_job`) |
| `deposit.generated_limit` (`generated_limit`) | `None` (`10000000` at runtime) | events | Maximum number of generated source events allowed to reach `events_per_job` (CLI `--generated-limit`) |
| `deposit.edep_min` (`edep_min`) | `None` | $\text{MeV}$ | Lower bound on total deposited energy in the device for a recorded event (CLI `--edep-min`) |
| `deposit.edep_max` (`edep_max`) | `None` | $\text{MeV}$ | Upper bound on total deposited energy in the device for a recorded event (CLI `--edep-max`) |
| `deposit.fano` (`fano`) | `True` | None | Whether to enable Fano fluctuation sampling when converting deposited energy to ionized pairs |
| `deposit.plots` | `100` | events | Number of leading recorded events per job for which Geant4 geometry and track plots are drawn |
| `current.plots` | `100` | events | Number of leading recorded events per job for which carrier drift path and current plots are drawn |
| `readout.amplifier` (`amplifier`) | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` (CLI `-amp`/`--amplifier`) |
| `readout.sheet_resistance` (`sheet_resistance`) | `None` | $\Omega$ | Overrides the resistive-layer sheet resistance for devices containing `resistive_layer` (CLI `--sheet-resistance`) |
| `reconstruction.threshold` (`threshold`) | `10.0` | $\text{mV}$ | Threshold-crossing level for extracting `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster (CLI `-threshold`) |
| `reconstruction.amplitude_threshold` (`amplitude_threshold`) | `10.0` | $\text{mV}$ | Pulse amplitude threshold for finding cluster seeds (whether an event is recorded is decided by `trigger`) (CLI `-amplitude_threshold`) |
| `reconstruction.fractions` (`fractions`) | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` (`edge`) | `None` (inherits `pulse_edge` written by `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` (CLI `--edge`) |

All other parameters (default Geant4 world half-side `WORLD_HALF_SIDE = 25000 um`, default maximum generated event limit `GENERATED_LIMIT = 10000000`, material mean ionization energy `PAIR_ENERGY_EV` and Fano factor `FANO_FACTOR`, drift time-window and time-step profiles `t_bin`/`delta_t`, thermal diffusion flag `diffusion = True`, `ngspice` frequency-domain noise start frequency `1e3 Hz` and temperature `27 °C`, minimum saved waveform swing ratio `PART_EDGE = 1e-3`, reconstruction baseline points `BASELINE_POINTS = 200`, initial truncated-Gaussian fit window `median ± 8 * MAD`, minimum sample count `MINIMUM_EVENTS = 20`, and maximum iteration rounds `ROUNDS = 6`) are hardcoded in the source code.

## Outputs

Results are stored under `<project>/signal/` inside the device project (such as `work/<device>/signal/` or `examples/<device>/signal/`); see [Architecture Overview](../architecture.md#results) for the storage layout: the lower layer stores stage outputs by input fingerprint under `<project>/signal/nodes/<stage>/<node>/` (containing the stage output files and `node.json`), the upper layer generates symlink views pointing to the corresponding nodes at `<project>/signal/points/<point>/<stage>` and records the parameter table in `<project>/signal/points.json`, cross-point statistics and trend plots are stored under `<project>/signal/analysis/`, and the device shared field is stored under `<project>/field/`.

### Data Files

| Filename | Writer Stage | Content and Main Fields | Unit |
| --- | --- | --- | --- |
| `deposit_<job>.h5` | [`deposit`](../stages/deposit.md) | Deposition step data: attributes `generated_events`, `recorded_events`, `generated_fraction`, `edep_min`/`edep_max`; datasets `event`, `count`, `detector`, `x`/`y`/`z`, `t`, `e`, `pairs` | Coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, `pairs` in pairs |
| `current_<job>.h5` | [`current`](../stages/current.md) | Induced current and net charge: attributes `electrodes`, `dt`; datasets `event`, `t0`, `count`, `pairs`, `sensitive_pairs`, `carriers_without_field`, `charge`, `stored`, `index`, `current` | `dt`, `t0` in $\text{s}$; `charge` in $\text{C}$; `current` in $\text{A}$ |
| `readout_<job>.h5` | [`readout`](../stages/readout.md) | Front-end readout voltage waveform: attributes `electrodes`, `dt`, `pulse_edge`, `device_circuit`; datasets `event`, `t0`, `count`, `stored`, `index`, `voltage` | `dt`, `t0` in $\text{s}$; `voltage` in $\text{V}$ |
| `reconstruction_<job>.h5` | [`reconstruction`](../stages/reconstruction.md) | Reconstructed event feature table: attributes `threshold`, `amplitude_threshold`, `fractions`, `edge`; datasets `event`, `selected`, `cluster_size`, `cluster_center`, `traced`, `baseline`, `noise`, `amplitude`, `above`, `ToA`, `ToT`, `CoG`, `area`, `CFD` | Voltage and thresholds $\text{V}$, time $\text{s}$, area $\text{V}\cdot\text{s}$ |
| `analysis/[<point>/]result.json` | [`analysis`](../stages/analysis.md) | Per-scan-point summary: `reconstruction` settings, `collection` (`events`, `mean`, `mean_error`, `spread`), and `timing` (`events`, `selected`, `polarity`, plus `mean`, `sigma`, `sigma_error`, `sigma68`, `window` for `ToA`, `CoG`, `CFD*`) | Thresholds $\text{mV}$, efficiency dimensionless, time and resolution $\text{s}$ |
| `analysis/[<point>/]events.h5` | [`analysis`](../stages/analysis.md) | 1D datasets for all selected events of one scan point: `job`, `event`, `ToA`, `ToT`, `amplitude`, `baseline`, `noise`, `truth`, `CoG`, `CFD<percent>` | Voltage $\text{V}$, time $\text{s}$ |
| `analysis/points.json` | [`analysis`](../stages/analysis.md) | Multi-scan-point comparison table (when finished points $> 1$): one entry per point with `"point"`, scan key values, `"events"`, `"efficiency"`, `"efficiency_error"`, `"selected"`, and `"sigma68"`, `"sigma"`, `"sigma_error"` for each timing channel | Efficiency dimensionless, time resolution $\text{s}$ |

### Plot Files

| Filename | Writer Stage | Content | Coordinate and Physical Quantity Units |
| --- | --- | --- | --- |
| `plots/job_<job>/g4_geometry.png` | [`deposit`](../stages/deposit.md) | Offscreen-rendered setup geometry and tracks for the first `deposit.plots` recorded events when `deposit.plots > 0` and a Geant4 source is used | Spatial dimensions $\mu\text{m}$ |
| `plots/job_<job>/event_<event>/<det_model>_drift_path.pdf`, `.root` | [`current`](../stages/current.md) | 3D device boundaries and carrier drift trajectories (top) and $x$-$z$ plane projection (bottom) for the first `current.plots` recorded events | Spatial axes $\mu\text{m}$ |
| `plots/job_<job>/event_<event>/No_<k>electrode_basic_infor.pdf`, `.root` | [`current`](../stages/current.md) | `electron`, `hole`, and `total` (plus avalanche gain) induced-current waveforms on each nonzero-current electrode $k$ for the first `current.plots` recorded events | Horizontal axis `Time [s]`, vertical axis `Current [A]` |
| `plots/job_<job>/event_<event>/cce.pdf`, `.root` | [`current`](../stages/current.md) | Distribution of electrons collected per electrode for `strip` or `pixel` devices over the first `current.plots` recorded events | Electrode index, collected charge converted to electron count (axis labeled `charge[Coulomb]`) |
| `analysis/[<point>/]efficiency.png` | [`analysis`](../stages/analysis.md) | `60`-bin histogram of charge collection efficiency for all recorded events in the scan point (when event count $\ge 2$), with a dashed line marking the mean | Horizontal axis dimensionless efficiency, vertical axis `events` |
| `analysis/[<point>/]amplitude.png` | [`analysis`](../stages/analysis.md) | `60`-bin histogram of pulse amplitude above baseline for all selected events in the scan point, with a dashed line marking `amplitude_threshold` | Horizontal axis `amplitude above the baseline [mV]`, vertical axis `events` |
| `analysis/[<point>/]time_difference.png` | [`analysis`](../stages/analysis.md) | `3 × 4` subplots showing `time - truth` distributions (`64` bins within `mean ± 8 * sigma`), final-round fit window shading, and truncated-Gaussian fit curves for `ToA`, `CoG`, and all `CFD*` channels | Horizontal axis `<channel> - truth [ps]`, vertical axis events |
| `analysis/[<point>/]resolution_of_fraction.png` | [`analysis`](../stages/analysis.md) | Time resolution `sigma` (with error bars) and `sigma68` versus constant fraction across all `CFD*` channels | Horizontal axis `fraction of the CFD` (dimensionless), vertical axis `width of time - truth [ps]` |
| `analysis/points.png` | [`analysis`](../stages/analysis.md) | Charge collection efficiency (left) and `CFD*` channel time resolution `sigma` (right) versus scan variable across scan points for a single numeric scan axis | Horizontal axis scan variable, left vertical axis dimensionless efficiency, right vertical axis `sigma of time - truth [ps]` |
