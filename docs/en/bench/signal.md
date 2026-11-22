# Single-Device Signal Test (`bench/signal`)

`signal` (in the `raser_bench` package) is the baseline full-chain benchmark test for a single device, centered on the device under test specified on the command line. It reads a single device together with one source, setup, and electronics configuration from [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), executes all eight stages in sequence—[`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md)—and outputs the charge collection efficiency of the device under test, as well as the time-difference distributions and time resolution of each timing quantity relative to the true deposition time. Time resolution relative to the true deposition time is not experimentally observable; to measure experimentally observable time resolution, use [`timeres`](timeres.md).

## Setup and Standard Practice

### Standard Practice and Physical Definitions

When testing the signal response and charge collection efficiency (CCE) of a single semiconductor detector in the laboratory, a radioactive source ($\beta$ source, $\alpha$ source), monoenergetic particle beam, or pulsed laser illuminates the reverse-biased device under test. The induced current on the readout electrode is converted to a voltage waveform through a front-end amplifier, digitizer, and trigger selection, and the charge collection efficiency is given by the ratio of collected charge to the initial charge ionized by the incident particle in the sensitive volume.

In RASER, the single-event charge collection efficiency $\eta$ and the time difference $\Delta t$ between the reconstructed timing timestamp and the true deposition time are:

$$\eta = \frac{\left|\sum_{j} Q_{j}\right|}{N_{\text{pairs}}\,e_0} \tag{1}$$

$$\Delta t = t_{\text{reco}} - t_{\text{truth}}, \qquad t_{\text{truth}} = \min_{k} t_{k} \tag{2}$$

where:

- $\eta$: single-event charge collection efficiency (dimensionless; $\eta > 1$ when avalanche multiplication is present);
- $Q_j$: signed net induced charge on the $j$-th readout electrode, $\text{C}$ (given by the `charge` dataset of `current.h5` in the `current` node, including underflow and overflow bins before and after the time window);
- $N_{\text{pairs}}$: total number of initial electron-hole pairs ionized inside the device in that event (before multiplication), pairs (given by the `pairs` dataset of `current.h5` in the `current` node);
- $e_0$: elementary charge; the code constant `ELEMENTARY_CHARGE` is $1.602176634\times 10^{-19}\ \text{C}$;
- $t_{\text{reco}}$: pulse timing timestamp extracted from the reconstructed waveform (threshold-crossing time `ToA`, time center of gravity `CoG`, or each constant-fraction timestamp `CFD10`–`CFD90`), $\text{s}$;
- $t_k$: global time of the $k$-th energy deposition step for that event in `deposit.h5` of the `deposit` node, $\text{s}$; $t_{\text{truth}}$ is the time `truth` of the earliest deposition step in that event, $\text{s}$;
- $\Delta t$: time difference of the reconstructed timestamp relative to the true earliest deposition time, $\text{s}$.

Eq. (1) is computed by `collection_efficiency(charge, pairs)` in [`core/analysis/collection.py`](../core/analysis.md) over all events in the `current` node and summarized by `efficiency_spread` in [`stages/analysis/collection.py`](../stages/analysis.md) into sample mean `mean`, standard error of the mean `mean_error`, and sample standard deviation `spread` (degrees-of-freedom correction `ddof=1`). Eq. (2) is computed by `event_times` and `time_widths` in [`stages/analysis/timing.py`](../stages/analysis.md), which invokes `core_width` in [`core/analysis/resolution.py`](../core/analysis.md) on `selected` events recorded by `trigger` that have a cluster seed found in `reconstruction` to perform iterative truncated-Gaussian maximum-likelihood fitting and report the core width `sigma` and `sigma68` (in $\text{s}$). Signal formation and charge collection measurement principles in semiconductor detectors are described in Ref. [1] (G. Lutz, *Semiconductor Radiation Detectors: Device Physics*, Springer (2007), doi:10.1007/978-3-540-71679-2).

Limitations: Eq. (2) directly uses the simulated true earliest deposition time $t_{\text{truth}}$ as reference, excluding reference-detector timing jitter and coincidence triggering, and is not directly observable in real experiments.

### Geant4 Setup Geometry

The default setup is `device_alone` (`raser/components/deposit/device_alone.py`, see [`../components/deposit.md`](../components/deposit.md)): the world cube material is vacuum `"G4_Galactic"`, centered at the midpoint of the `along_beam` line with half-side at least `WORLD_HALF_SIDE = 25000` $\mu\text{m}$. The world coordinate origin $(0, 0, 0)\ \mu\text{m}$ sits on the source (at the center of the collimator exit plane when carrying a collimator, with the collimator body on the $z < 0$ side and all `gap`s in the setup measured from the collimator exit plane), the $z$ axis points downstream along the beam, and the incidence angle is `angle = 0` $\text{degree}$; the setup uses `"along_beam": ["source", {"gap": 17000}, {"slot": "Device"}]` (`"materials": {}`, `"objects": {}`) to place the device under test logical volume `"Device"` $17\ \text{mm}$ downstream of the source, with its front surface centered at $(0, 0, 17000)\ \mu\text{m}$, its active layer spanning $x \in [-l_x/2, l_x/2]$, $y \in [-l_y/2, l_y/2]$, $z \in [17000, 17000 + l_z]\ \mu\text{m}$ (any layers outside the active layer follow immediately downstream), and maximum step size `maxstep = 2` $\mu\text{m}$ inside the device.

Charge collection efficiency is produced by this setup using the same batch of events as time resolution; measuring efficiency does not use a separate setup.

The `source` block of `device_alone` is `{"name": "decay/Sr90", "angle": 0}`, so collimated-source measurements directly use the copper-collimated `decay/Sr90`. In addition, the `signal` component directory (`src/raser_bench/signal/components/deposit/`, see [`../components/deposit.md`](../components/deposit.md)) provides `pcb_readout_gdml` (`"geant4_model": "gdml_import"`, importing external `pcb_readout.gdml` with world half-side `world_half_size_um = 2000000` $\mu\text{m}$, and a `source` block likewise `{"name": "decay/Sr90", "angle": 0}`).

### Four Types of Signal Sources

Changing the source simply changes the source component named by the setup's `source` block; the chain and outputs remain unchanged:

- **$\beta$ source**: `device_alone` names `decay/Sr90` (`raser/components/deposit/decay/Sr90.json`, `"kind": "decay_source"`). Each event draws one stationary decay of $^{90}\text{Sr}$ (`[38, 90]`) or its daughter $^{90}\text{Y}$ (`[39, 90]`) with equal probability on the entrance face of the copper collimator carried by `decay/Sr90` (`par_radius = 0`, bore radius `500` $\mu\text{m}$, length `3000` $\mu\text{m}$, outer side `8000` $\mu\text{m}$; see [`../components/deposit.md`](../components/deposit.md)), and the experiment launches particles from the emission distribution at the collimator exit plane. Electrons penetrate the device so the entire track crosses the sensitive volume, approximating minimum ionizing particles.
- **$\alpha$ source**: for example `decay/Am241` (`raser/components/deposit/decay/Am241.json`, `"kind": "decay_source"`, `par_type = "alpha"`, monoenergetic kinetic energy `par_energy = 5.54` $\text{MeV}$). The $\alpha$ particles stop within a very shallow depth near the surface of the device, concentrating energy deposition near the entrance face.
- **Laser**: single-photon absorption (`"SPA"`) or two-photon absorption (`"TPA"`), incident from the top, bottom, or side (`"top"`, `"bottom"`, `"edge"`), generating carriers near the focus $(x_{\text{focus}}, y_{\text{focus}}, z_{\text{focus}}) = (\text{fx\_rel}\cdot l_x,\, \text{fy\_rel}\cdot l_y,\, \text{fz\_rel}\cdot l_z)$ (in $\mu\text{m}$). See [`../components/deposit.md`](../components/deposit.md) for laser component keys.

- **Beam**: monoenergetic particle beam (`"kind": "beam"`), for example the proton beam `beam/proton` (`raser/components/deposit/beam/proton.json`, `par_type = "proton"`, kinetic energy `par_energy = 1000.0` $\text{MeV}$, transverse random offset half-widths `par_randx = par_randy = 0` $\mu\text{m}$). One event may emit a single particle or emit multiple particles simultaneously via the `particles` list (see [`../apps/bmos.md`](../apps/bmos.md)).

![HPK-Si-PiN single-event carrier drift paths](../../images/current/drift-path-HPK-Si-PiN.png)

Electron and hole drift paths for a single event in `HPK-Si-PiN` under the `decay/Sr90` source named by `device_alone`: the $\beta$ electron traverses the entire device, and carriers generated along the track drift toward opposite electrodes.

![HPK-Si-PiN single-event induced current](../../images/current/event-HPK-Si-PiN.png)

Induced current on the readout electrode for the same Sr90 $\beta$-electron event: electron component, hole component, and total current.

### Execution Steps and Built-in Constants

A single `signal` job executes in the following order:

1. **Check and solve shared field (`field`)**: before jobs start, the main command checks whether `<project>/field/` contains a field node matching the current device, bias `voltage` ($\text{V}$), and irradiation fluence `irradiation_flux` ($\text{cm}^{-2}$, $1\ \text{MeV}$ neutron-equivalent fluence); if not ready, it computes the field before jobs start and stores it in `<project>/field/<node>/` (carrying a `.part` suffix while writing, and finalized on disk with `node.json` upon completion). The experiment records that node ID in `points.json` and points the symlink view `points/<point>/field` to it.
2. **Energy deposition and ionized-pair generation (`deposit`)**: `stages/deposit.py` calls `write_simulated_deposits` to run Geant4 (or `toy_mip`). Only events with total deposited energy $E_{\text{tot}} > 0$ inside `"Device"` satisfying $\text{edep\_min} \le E_{\text{tot}} \le \text{edep\_max}$ (in $\text{MeV}$; when bounds are unset, only $E_{\text{tot}} > 0$ is required) are kept until `events_per_job` events are recorded (up to `generated_limit` generated source events, raising `RuntimeError` if not reached) or `generated_per_job` source events have been generated. In `ionized_pairs`, each step's deposited energy $E_k$ ($\text{MeV}$) is divided by the material mean ionization energy $\varepsilon_{\text{pair}}\times 10^{-6}$ ($\text{MeV}$) and sampled according to the `fano` switch to obtain electron-hole pair counts; step coordinates are transformed from Geant4 world coordinates to device coordinates $[0, l_x] \times [0, l_y] \times [0, l_z]\ \mu\text{m}$ via the inverse of Eq. (18) (see [`core/deposit`](../core/deposit.md#line-along-the-beam)) and written to `deposit.h5` in the `deposit` node, and geometry and track plots are drawn inside the node according to `deposit.plots`. If `0` events are recorded, `Ended` is raised to end the job early.
3. **Carrier drift and induced-current binning (`current`)**: `stages/current.py` loads `DevsimField` and calls `write_induced_currents` (with thermal diffusion enabled by default, `diffusion=True`) to advance electron and hole drift (including irradiation trapping and avalanche multiplication) inside the device and electrode-array bounds for each recorded event, accumulating induced current into time bins of width `t_bin` ($5\ \text{ps}$ in 1D, $50\ \text{ps}$ in 2D/3D) via the Shockley–Ramo theorem and writing `current.h5` in the `current` node, while drawing drift path and current plots inside the node for the first `current.plots` events.
4. **Equivalent circuit and front-end amplifier readout (`readout`)**: `stages/readout.py` constructs the device equivalent circuit `DeviceCircuit`, splits and loads the SPICE subcircuit chain specified by `amplifier` on `+`, and invokes `ngspice` to solve the transient response and frequency-domain thermal noise spectrum (synthesizing independent time-domain Gaussian thermal noise from the `readout` noise seed derived from the job seed and adding it to the waveform), saving only channels whose maximum voltage swing is $\ge 10^{-3} V_{\max}$ to `readout.h5` in the `readout` node.
5. **Digitization and triggering (`digitizer`, `trigger`)**: `digitizer` converts analog waveforms into quantized codes according to the analog bandwidth, sampling, and quantization settings of the digitizer component (default `MXR608A`, with clock phase and aperture jitter drawn from the `digitizer` seed derived from the job seed) and writes them to `digitizer.h5` in the `digitizer` node; `trigger` decides which events to record according to the trigger conditions and writes the `event` (`int64`) dataset of recorded event IDs to `trigger.h5` in the `trigger` node.
6. **Waveform feature extraction and clustering (`reconstruction`)**: `stages/reconstruction.py` reads the events in `digitizer.h5` recorded by `trigger.h5`, converts quantized codes back to voltage ($\text{V}$) using `lsb_V` and `offset_V` with sampling times `t0 + k·sampling_period`, multiplies `threshold` and `amplitude_threshold` in $\text{mV}$ by $10^{-3}$ to convert to $\text{V}$, subtracts the mean baseline of the [$N_{\text{base}}$](../core/reconstruction.md#baseline-subtraction-and-polarity-inversion) samples in the pre-window and flips polarity according to `edge`, extracts amplitude, `ToA`, `ToT`, `CoG`, `area`, and `CFD` timestamps for each entry in `fractions`, clusters across electrodes seeded by electrodes with amplitude at least `amplitude_threshold`, marks events with a found seed as `selected`, and writes `reconstruction.h5` in the `reconstruction` node.
7. **Collection efficiency and time resolution statistics (`analysis`)**: `stages/analysis` aggregates all finished jobs per scan point, computes the collection efficiency distribution via Eq. (1) over all events in the `current` nodes and the time resolution via Eq. (2) over `selected` events, writes per-point `result.json`, `events.h5`, and distribution plots to each scan point's `analysis` node (`nodes/analysis/<node>/`, view `points/<point>/analysis/`), and writes multi-point comparison files `points.json`, `trend.png` and `trend.pdf` under `<experiment>/analysis/`.

The built-in constants across the full chain are listed below:

| Constant Name | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | `src/raser/core/deposit/simulate_deposits.py`, default minimum half-side of the Geant4 world cube |
| `PAIR_ENERGY_EV` | `"Si": 3.6`, `"SiC": 7.83`, `"Diamond": 13.1` | $\text{eV}$ | `src/raser/core/deposit/ionization.py`, mean ionization energy per electron-hole pair for each material; Si takes an approximation to $3.65\ \text{eV}$ from PDG Section 35.8 Table 35.10 (S. Navas et al., Phys. Rev. D 110 (2024) 030001, doi:10.1103/PhysRevD.110.030001), and 4H-SiC takes $(7.83 \pm 0.02)\ \text{eV}$ (A. Gsponer et al., NIM A 1064 (2024) 169412, doi:10.1016/j.nima.2024.169412) |
| `FANO_FACTOR` | `"Si": 0.115`, `"SiC": 0.128`, `"Diamond": 0.382` | dimensionless | `src/raser/core/deposit/ionization.py`, Fano factor for ionized-pair fluctuations for each material; Si takes the asymptotic value 0.115 (K. Ramanathan, N. Kurinsky, Phys. Rev. D 102 (2020) 063026, doi:10.1103/PhysRevD.102.063026; experimental measurement 0.1161 in B. G. Lowe, NIM A 399 (1997) 354, doi:10.1016/S0168-9002(97)00965-0), and 4H-SiC takes 0.128 (S. K. Chaudhuri, K. J. Zavalla, K. C. Mandal, Appl. Phys. Lett. 102 (2013) 031109, doi:10.1063/1.4776703) |
| `t_bin`, `delta_t` | 1D: `5e-12`, `2e-12`; 2D/3D: `50e-12`, `20e-12` | $\text{s}$ | `src/raser/core/current/cal_current.py`, induced-current time-bin width and single drift time step |
| `PART_EDGE` | `1e-3` | dimensionless | `src/raser/core/readout/job.py`, minimum ratio of channel voltage swing to maximum channel swing required to save a waveform channel |
| `MILLIVOLT` | `1.0e-3` | $\text{V/mV}$ | `src/raser/stages/reconstruction.py`, conversion factor from $\text{mV}$ to $\text{V}$ for `threshold` and `amplitude_threshold` |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | $\text{C}$ | `src/raser/core/analysis/collection.py`, elementary charge used in Eq. (1) to compute charge collection efficiency |
| `MINIMUM_EVENTS`, `ROUNDS` | `20`, `6` | events, rounds | `src/raser/core/analysis/resolution.py`, minimum sample count and maximum window-shrinking iteration rounds for truncated-Gaussian time-resolution fitting |
| `PICOSECOND` | `1.0e-12` | $\text{s/ps}$ | `src/raser/stages/analysis/plots.py`, seconds-to-picoseconds conversion factor for time-difference and time-resolution plots |

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, conductive-region flags, and junction capacitance / undepleted-bulk parameters of the device under test at the target bias and irradiation fluence, stored under `<project>/field/<node>/`.
- [`deposit`](../stages/deposit.md): simulates energy deposition steps in the device under test for the selected source and Geant4 setup, converts them into initial electron-hole pairs, and writes `deposit.h5`.
- [`current`](../stages/current.md): drifts, diffuses, and multiplies the deposited electron-hole pairs in the solved field, computing the time-domain induced current and net induced charge on each readout electrode, and writes `current.h5`.
- [`readout`](../stages/readout.md): feeds the induced current into the device equivalent circuit and SPICE front-end amplifier chain to solve output voltage waveforms and add circuit thermal noise, and writes `readout.h5`.
- [`digitizer`](../stages/digitizer.md): converts analog output waveforms into quantized-code digital waveforms according to the digitizer analog bandwidth, sampling rate, and quantization bit depth, and writes `digitizer.h5`.
- [`trigger`](../stages/trigger.md): filters recorded events according to the trigger device selection conditions and writes the event IDs of recorded events to `trigger.h5`.
- [`reconstruction`](../stages/reconstruction.md): reads the events in `digitizer.h5` recorded by `trigger`, converts quantized codes back to voltage ($\text{V}$) using `lsb_V` and `offset_V`, subtracts the baseline in the pre-window, extracts pulse amplitude, `ToA`, `ToT`, `CoG`, `area`, `CFD`, and multi-electrode cluster features, marks events with a found seed as `selected`, and writes `reconstruction.h5`.
- [`analysis`](../stages/analysis.md): aggregates finished jobs per scan point, fits charge collection efficiency and time resolution relative to the true deposition time, writes per-point results and distribution plots to each scan point's `analysis` node, and writes cross-point statistics and trend plots under `<experiment>/analysis/`.

### Components

- [Detector components (`components/device`)](../components/device.md): provides dimensions, material, doping, bias voltage, temperature, irradiation model, avalanche model, and equivalent circuit parameters of the device under test (such as `HPK-Si-PiN.json`, `NJU-PiN.json`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides radioactive sources and beams (such as `decay/Sr90.json`, `decay/Am241.json`, `beam/proton.json`), lasers (such as `PIL037_top_SiC.json`), and Geant4 setups (such as default `device_alone.py`, `pcb_readout_gdml.py`).
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides SPICE amplifier stages and termination load subcircuits cascaded with `+` (default `SantaCruz+Gali52+Termination50`).
- [Digitizer components (`components/digitizer`)](../components/digitizer.md): provides sampling and quantization settings of an oscilloscope or digitizer board; for devices that also perform triggering (such as an oscilloscope `MXR608A`), their trigger conditions are specified here as well.
- [Trigger components (`components/trigger`)](../components/trigger.md): provides trigger selection condition definitions for standalone trigger devices.

## Usage and Configuration

Run `signal` directly on the device under test (quick-start example; see [Getting Started Section 4](../getting-started.md#4-results-of-each-step-in-the-chain) for outputs and plots at each step of the chain); when `HPK-Si-PiN` is not present under `work/`, it runs `examples/HPK-Si-PiN/` in place and stores results under `examples/HPK-Si-PiN/`:

```bash
raser signal HPK-Si-PiN
```

Use `--set deposit.g4setup.source=<source name>` on the command line to switch the signal source (for example, to the $\alpha$ source `decay/Am241`); the setup's `angle` is kept:

```bash
raser signal HPK-Si-PiN --set deposit.g4setup.source=decay/Am241
```

Scanning bias voltage, source energy, or laser pulse energy and wavelength with `--scan` is all performed in `signal`; when the scan axis is the laser position relative to the device, use [`tct`](tct.md) instead:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the experiment directory `examples/HPK-Si-PiN/signal/config.json` records settings sectioned by stage. Only the sections relevant to this page are excerpted below; `examples/HPK-Si-PiN/signal/config.json` writes out all eight sections in full.

```json
{
  "workflow": "signal",
  "device": "HPK-Si-PiN",
  "field": {
    "voltage": 200.0,
    "irradiation_flux": null
  },
  "deposit": {
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

The configuration keys users can set in `signal` are listed below (see [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md) for the remaining settings in `digitizer`, `trigger`, and other sections). "Example Value" shows the value written in `examples/HPK-Si-PiN/signal/config.json`; if `config.json` is missing a required key, an error is raised naming the missing "section.key".

| Section.Key | Example Value | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `200.0` (uses bias from the device file if set to `null`) | $\text{V}$ | Reverse bias voltage of the device under test |
| `field.irradiation_flux` | `null` (uses irradiation fluence from the device file, or `0` if the device file has no irradiation block) | $\text{cm}^{-2}$ | Irradiation fluence of the device under test ($1\ \text{MeV}$ neutron-equivalent fluence) |
| `deposit.g4setup` | `"device_alone"` | None | Geant4 setup component name or path; the setup's `source` block names the source it uses |
| `deposit.g4setup.source` | not written (`"decay/Sr90"` from `device_alone`) | None | Replaces the whole source: radioactive source or beam component name or path; the setup's `angle` is kept |
| `deposit.events_per_job` | `200` | events | Number of valid deposited events to record per job (mutually exclusive with `deposit.generated_per_job`) |
| `deposit.generated_per_job` | `null` (unused) | events | Total number of events generated from the source per job (mutually exclusive with `deposit.events_per_job`) |
| `deposit.generated_limit` | `10000000` | events | Maximum number of generated source events allowed to reach `events_per_job` |
| `deposit.edep_min` | `null` (no lower bound) | $\text{MeV}$ | Lower bound on total deposited energy in the device for a recorded event |
| `deposit.edep_max` | `null` (no upper bound) | $\text{MeV}$ | Upper bound on total deposited energy in the device for a recorded event |
| `deposit.fano` | `true` | None | Whether to enable Fano fluctuation sampling when converting deposited energy to ionized pairs |
| `deposit.plots` | `100` | events | Number of leading recorded events per job for which Geant4 geometry and track plots are drawn |
| `current.plots` | `100` | events | Number of leading recorded events per job for which carrier drift path and current plots are drawn |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `readout.sheet_resistance` | `null` (uses sheet resistance of the resistive layer in the device file) | $\Omega$ | Overrides the resistive-layer sheet resistance for devices containing `resistive_layer` |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | Threshold-crossing level for extracting `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | Pulse amplitude threshold for cluster seed channels; events recorded by `trigger` in which a seed is found are marked `selected` (whether an event is recorded is decided by `trigger` according to the trigger conditions) |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` | `null` (inherits `pulse_edge` written by `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` |

All other parameters (default Geant4 world half-side `WORLD_HALF_SIDE = 25000 um`, material mean ionization energy `PAIR_ENERGY_EV` and Fano factor `FANO_FACTOR`, drift time-window and time-step profiles `t_bin`/`delta_t`, thermal diffusion flag `diffusion = True`, `ngspice` frequency-domain noise start frequency `1e3 Hz` and temperature `27 °C`, minimum saved waveform swing ratio `PART_EDGE = 1e-3`, initial truncated-Gaussian fit window `median ± 8 * MAD`, minimum sample count `MINIMUM_EVENTS = 20`, and maximum iteration rounds `ROUNDS = 6`) are hardcoded in the source code.

## Outputs

Results are stored under `<project>/signal/` inside the device project (the example above runs in place at `examples/HPK-Si-PiN/signal/`, and user-created projects at `work/<device>/signal/`); see [Architecture Overview](../architecture.md#results) for the storage layout: the lower layer stores stage outputs by input fingerprint under `<project>/signal/nodes/<stage>/<node>/` (containing the stage output files, stage plots, and `node.json`; one node per job from `deposit` through `reconstruction`, and one node per scan point for `analysis`), the upper layer generates symlink views at `<project>/signal/points/<point>/<stage>/<job>` (`points/<point>/field` and `points/<point>/analysis` are each a single symlink) and records the parameter table in `<project>/signal/points.json`, cross-point statistics and trend plots are stored under `<project>/signal/analysis/`, and device shared field nodes are stored under `<project>/field/<node>/`.

### Data Files

| Path | Writer Stage | Content and Main Fields | Unit |
| --- | --- | --- | --- |
| `nodes/deposit/<node>/deposit.h5` | [`deposit`](../stages/deposit.md) | Deposition step data: attributes `generated_events`, `recorded_events`, `emission_probability` (`1.0` for sources without an emission distribution), `edep_min`/`edep_max`; datasets `event`, `count`, `detector`, `x`/`y`/`z`, `t`, `e`, `pairs` | Coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, `pairs` in pairs |
| `nodes/current/<node>/current.h5` | [`current`](../stages/current.md) | Induced current and net charge: attributes `electrodes`, `dt`; datasets `event`, `t0`, `count`, `pairs`, `sensitive_pairs`, `carriers_without_field`, `charge`, `stored`, `index`, `current` | `dt`, `t0` in $\text{s}$; `charge` in $\text{C}$; `current` in $\text{A}$ |
| `nodes/readout/<node>/readout.h5` | [`readout`](../stages/readout.md) | Front-end readout voltage waveform: attributes `electrodes`, `dt`, `pulse_edge`, `device_circuit`; datasets `event`, `t0`, `count`, `stored`, `index`, `voltage` | `dt`, `t0` in $\text{s}$; `voltage` in $\text{V}$ |
| `nodes/digitizer/<node>/digitizer.h5` | [`digitizer`](../stages/digitizer.md) | Digitized quantized-code waveform: attributes `electrodes`, `sampling_period`, `lsb_V`, `offset_V`, `bits`, `pulse_edge`, `device`; datasets `event`, `t0`, `count`, `stored`, `index`, `clipped`, `code` (`int16`) | `sampling_period`, `t0` in $\text{s}$; `lsb_V`, `offset_V` in $\text{V}$; `bits` in bits; `code` dimensionless |
| `nodes/trigger/<node>/trigger.h5` | [`trigger`](../stages/trigger.md) | Triggered recorded events: dataset `event` (`int64`, event IDs of recorded events) | dimensionless |
| `nodes/reconstruction/<node>/reconstruction.h5` | [`reconstruction`](../stages/reconstruction.md) | Reconstructed event feature table: attributes `electrodes`, `threshold`, `amplitude_threshold`, `fractions`, `edge`; datasets `event`, `selected`, `cluster_size`, `cluster_center`, `traced`, `baseline`, `noise`, `amplitude`, `above`, `ToA`, `ToT`, `CoG`, `area`, `CFD` | Voltage and thresholds $\text{V}$, time $\text{s}$, area $\text{V}\cdot\text{s}$ |
| `nodes/analysis/<node>/result.json` (view `points/<point>/analysis/result.json`) | [`analysis`](../stages/analysis.md) | Per-scan-point summary: `reconstruction` settings, `collection` (`events`, `mean`, `mean_error`, `spread`), and `timing` (`events`, `selected`, `polarity`, plus `mean`, `sigma`, `sigma_error`, `sigma68`, `window` for `ToA`, `CoG`, `CFD*`) | Thresholds $\text{mV}$, efficiency dimensionless, time and resolution $\text{s}$ |
| `nodes/analysis/<node>/events.h5` (view `points/<point>/analysis/events.h5`) | [`analysis`](../stages/analysis.md) | 1D datasets for all `selected` events of one scan point: `job`, `event`, `ToA`, `ToT`, `amplitude`, `baseline`, `noise`, `truth`, `CoG`, `CFD<percent>` | Voltage $\text{V}$, time $\text{s}$ |
| `analysis/points.json` | [`analysis`](../stages/analysis.md) | Multi-scan-point comparison table (when finished points $> 1$): one entry per point with `"point"`, scan key values, `"events"`, `"efficiency"`, `"efficiency_error"`, `"selected"`, and `"sigma68"`, `"sigma"`, `"sigma_error"` for each timing channel | Efficiency dimensionless, time resolution $\text{s}$ |

### Plot Files

| Path | Writer Stage | Content | Coordinate and Physical Quantity Units |
| --- | --- | --- | --- |
| `nodes/deposit/<node>/plots/g4_geometry.png` | [`deposit`](../stages/deposit.md) | Offscreen-rendered setup geometry and tracks for the first `deposit.plots` recorded events when `deposit.plots > 0` and a Geant4 source is used | Spatial dimensions $\mu\text{m}$ |
| `nodes/current/<node>/plots/drift_path_<event>.png`, `.pdf`, `.root` | [`current`](../stages/current.md) | 3D device boundaries and carrier drift trajectories (top) and $x$-$z$ plane projection (bottom) for the first `current.plots` recorded events | Spatial axes $\mu\text{m}$ |
| `nodes/current/<node>/plots/current_<event>.png`, `.pdf`, `.root` (`current_<event>_electrode_<k>` with several readout electrodes) | [`current`](../stages/current.md) | `electrons`, `holes`, and `total` (plus avalanche gain) induced-current waveforms on each nonzero-current electrode $k$ for the first `current.plots` recorded events | Horizontal axis `Time [ns]`, vertical axis `Current [μA]` |
| `nodes/current/<node>/plots/charge_per_electrode_<event>.png`, `.pdf`, `.root` | [`current`](../stages/current.md) | Distribution of charge collected per electrode for `strip` or `pixel` devices over the first `current.plots` recorded events | Electrode index (dimensionless), charge `Charge [fC]` |
| `nodes/analysis/<node>/plots/efficiency.png`, `.pdf` (view `points/<point>/analysis/plots/efficiency.png`, `.pdf`) | [`analysis`](../stages/analysis.md) | `60`-bin histogram of charge collection efficiency for all events in the scan point's `current` nodes (when event count $\ge 2$), with a black dashed line marking the mean; the legend reports the event count `<N> events` and the mean `mean <mean>` | Horizontal axis `Charge collection efficiency` (dimensionless), vertical axis `Events` |
| `nodes/analysis/<node>/plots/amplitude.png`, `.pdf` (view `points/<point>/analysis/plots/amplitude.png`, `.pdf`) | [`analysis`](../stages/analysis.md) | `60`-bin histogram of pulse amplitude above baseline for all `selected` events in the scan point, with a black dashed line marking `amplitude_threshold`; the legend reports `<n> of <N> events` and `threshold <threshold> mV` | Horizontal axis `Amplitude [mV]`, vertical axis `Events` |
| `nodes/analysis/<node>/plots/time_difference.png`, `.pdf` (view `points/<point>/analysis/plots/time_difference.png`, `.pdf`) | [`analysis`](../stages/analysis.md) | `3 × 4` subplots showing `time - truth` distributions (`64` bins within `mean ± 8 * sigma`), final-round fit window shading, and black truncated-Gaussian fit curves for `ToA`, `CoG`, and all `CFD*` channels; each subplot title is the channel name and its upper left corner shows `sigma68`, `sigma` and the in-window count | Horizontal axis `<channel> - truth [ps]`, vertical axis `Events` |
| `nodes/analysis/<node>/plots/resolution_of_fraction.png`, `.pdf` (view `points/<point>/analysis/plots/resolution_of_fraction.png`, `.pdf`) | [`analysis`](../stages/analysis.md) | Time resolution `sigma` (black filled circles with error bars) and `sigma68` (black open squares) versus constant fraction across all `CFD*` channels | Horizontal axis `CFD fraction` (dimensionless), vertical axis `Time resolution [ps]` |
| `analysis/trend.png`, `.pdf` | [`analysis`](../stages/analysis.md) | Charge collection efficiency (left) and `CFD*` channel time resolution `sigma` (right) versus scan variable across scan points for a single numeric scan axis, one line per `CFD*` channel in the right panel | Horizontal axis scan variable name, left vertical axis `Charge collection efficiency` (dimensionless), right vertical axis `Time resolution [ps]` |
