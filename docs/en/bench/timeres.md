# Time Resolution Test (`bench/timeres`)

`timeres` (Time Resolution, in the `raser_bench` package) is a benchmark class inheriting from the `raser` experiment base class (see [Architecture Overview](../architecture.md#experiments-are-python-classes)) that outputs the time-difference distribution between the device under test (DUT) and a reference device, as well as each device's time-difference distribution relative to its true deposition time; three devices can also be placed to solve for each device's individual time resolution from the three pairwise time differences (see [Three Devices](#three-devices)). The devices are specified by a device list—every listed device is built as a real device from its device file; the default is the command-line DUT plus the reference device `HPK-Si-LGAD`. Because β particles must traverse every device in the list sequentially to trigger, the list should not be too long. All devices are placed inside the same `time_resolution` Geant4 setup, where particles emitted from the same $\beta$ radioactive source (default `decay/Sr90`) pass through the reference device and the DUT in sequence.

`timeres` reads [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence: [`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md). Apart from [`deposit`](../stages/deposit.md), which is shared by both devices, each device individually runs `field`, `current`, `readout`, `digitizer`, `trigger`, and `reconstruction`, with `trigger` requiring both devices to exceed the amplitude threshold in the same event (coincidence). By default each job records `10000` valid events and disables per-event plotting (`deposit.plots = 0`, `current.plots = 0`), producing the DUT time resolution for leading-edge timing (`ToA`), center-of-gravity timing (`CoG`), and each constant-fraction timing (`CFD`) fraction.

## Setup and Standard Practice

### Standard Practice and Physical Model

When measuring the time resolution of a fast semiconductor detector (such as an LGAD, 4H-SiC PiN, or SiC LGAD) in the laboratory with a $^{90}\text{Sr}$ $\beta$ radioactive source, the device under test (DUT) and a reference detector are aligned vertically along the particle incidence axis and mounted on upper and lower readout PCBs with centered collimating holes. Two-device coincidence triggering selects $\beta$ electrons penetrating both devices simultaneously, measuring the difference in pulse arrival times between the two devices event by event.

For every event passing the two-device coincidence and every timing channel (`ToA`, `CoG`, `CFD10`–`CFD90`), `timeres` produces three time differences:

$$\Delta t = t_{\text{DUT}} - t_{\text{ref}}, \qquad \Delta t_{\text{DUT}} = t_{\text{DUT}} - t_{\text{truth,DUT}}, \qquad \Delta t_{\text{ref}} = t_{\text{ref}} - t_{\text{truth,ref}} \tag{1}$$

The first is experimentally observable, while the latter two exist only in simulation and measure each device relative to its true deposition time. Each of the three distributions is fitted with the same iterative truncated-Gaussian fit (`core_width` and `truncated_gaussian` in [`core/analysis/resolution.py`](../core/analysis.md)) to extract its core width by minimizing the negative log-likelihood inside an iteratively shrinking window $[a, b]$:

$$\mathcal{L}(\mu, \sigma) = \frac{1}{2}\sum_{i=1}^{n}\left(\frac{x_i - \mu}{\sigma}\right)^{2} + n\ln\sigma + n\ln\!\left[\frac{1}{2}\operatorname{erf}\!\left(\frac{b - \mu}{\sqrt{2}\sigma}\right) - \frac{1}{2}\operatorname{erf}\!\left(\frac{a - \mu}{\sqrt{2}\sigma}\right)\right] \tag{2}$$

where:

- $t_{\text{DUT}}$, $t_{\text{ref}}$: reconstructed timing timestamps of the DUT and reference device in a given timing channel for the same coincidence event, $\text{s}$;
- $t_{\text{truth,DUT}}$, $t_{\text{truth,ref}}$: true global time of the earliest energy deposition step in the DUT and in the reference device for that event, $\text{s}$;
- $\Delta t$, $\Delta t_{\text{DUT}}$, $\Delta t_{\text{ref}}$: the three time differences defined above, $\text{s}$;
- $x_i$: the $i$-th sample falling inside the current fit window $[a, b]$ (in $\text{s}$), taken from whichever of the three time differences is being fitted, $\text{s}$; $n$ is the number of samples inside the window (dimensionless);
- $\mu$, $\sigma$: mean and standard deviation (core width) of the truncated-Gaussian distribution, $\text{s}$; `sigma68` (half the distance between the $16\%$ and $84\%$ quantiles inside the window, $\text{s}$) is reported alongside them.

Eq. (2) is implemented by [`stages/analysis`](../stages/analysis.md) calling `core_width` and `truncated_gaussian` in [`core/analysis/resolution.py`](../core/analysis.md). Measuring time differences by coincidence between a reference device and a DUT is described in Ref. [1] (N. Cartiglia et al., “Beam test results of a 16 ps timing system based on ultra-fast silicon detectors”, *Nucl. Instrum. Methods Phys. Res. A* 850 (2017) 83, doi:10.1016/j.nima.2017.01.021, which uses a 180 GeV/c π beam) and the 4H-SiC PIN detector time-resolution study in Ref. [2] (T. Yang et al., “Time Resolution of the 4H-SiC PIN Detector”, *Front. Phys.* 10 (2022) 718071, doi:10.3389/fphy.2022.718071).

### `time_resolution` Setup Geometry

By default, `timeres` loads the Geant4 setup `time_resolution` (`src/raser/bench/timeres/components/g4setup/time_resolution.py`). The world material is vacuum `"G4_Galactic"` with default half-side `WORLD_HALF_SIDE = 25000` $\mu\text{m}$. The default $\beta$ source `decay/Sr90` disk is centered at $z = -17000\ \mu\text{m}$ ($17\ \text{mm}$ above the top surface of the DUT), with disk radius `par_radius = 2500` $\mu\text{m}$ and emission half-cone angle `par_cone = 15` $\text{degree}$, aiming at the origin `towards = [0, 0, 0]` $\mu\text{m}$ with incidence angle `angle = 0` $\text{degree}$.

Along $+z$, the setup places in order an aluminum foil `Al`, the reference device, an upper PCB `pcb1` with a centered circular hole, the DUT, and a lower PCB `pcb2` with a centered circular hole. `Al`, `pcb1`, and `pcb2` keep the dimensions, materials, and positions defined in `time_resolution.py`. The reference device is built as a physical volume from its device file (default `HPK-Si-LGAD`: material `"Si"`, dimensions $1300 \times 1300 \times 50\ \mu\text{m}$) centered at $(0, 0, -10000)\ \mu\text{m}$; the DUT is built from its device file with its top surface centered at the origin $(0, 0, 0)\ \mu\text{m}$, occupying $x \in [-l_x/2, l_x/2]$, $y \in [-l_y/2, l_y/2]$, $z \in [0, l_z]\ \mu\text{m}$. Both devices use maximum step size `maxstep = 2` $\mu\text{m}$.

Geant4 fully simulates energy deposition, multiple scattering, and secondary particle production as $\beta$ electrons traverse the aluminum foil, reference device, upper PCB, DUT, and lower PCB, recording energy deposition steps inside both the reference device and the DUT simultaneously. The dimensions and coordinates of every volume along $+z$ are listed below:

| Volume | Type | Material and Density | Full Size `side_x × side_y × side_z` ($\mu\text{m}$) | Center `position_z` ($\mu\text{m}$) | $z$-Axis Span ($\mu\text{m}$) | Centered Hole `tub_radius`, `tub_depth` ($\mu\text{m}$) |
| --- | --- | --- | --- | --- | --- | --- |
| `Al` | Surrounding volume (`elemental`) | `"G4_Al"` | $5000 \times 5000 \times 10$ | `-15000` | $[-15005,\, -14995]$ | None |
| Reference device (default `HPK-Si-LGAD`) | Active device | From device file (default `"G4_Si"`) | From device file (default $1300 \times 1300 \times 50$) | `-10000` | $[-10000 - l_{z,\text{ref}}/2,\, -10000 + l_{z,\text{ref}}/2]$ (default $[-10025,\, -9975]$) | None |
| `pcb1` | Surrounding volume (`binary_compounds`) | `"SiO2"` (Si/O atomic ratio `33.4:66.6`, `2.2 g/cm^3`) | $20000 \times 20000 \times 1500$ | `-8933.5` | $[-9683.5,\, -8183.5]$ | `500`, `1500` |
| DUT (given on CLI) | Active device | From device file | $l_x \times l_y \times l_z$ | $l_z / 2$ | $[0,\, l_z]$ | None |
| `pcb2` | Surrounding volume (`binary_compounds`) | `"SiO2"` (Si/O atomic ratio `33.4:66.6`, `2.2 g/cm^3`) | $20000 \times 20000 \times 1500$ | `1100` | $[350,\, 1850]$ | `500`, `1500` |

### Three Devices

When the device list contains three devices, they may be one DUT plus two reference devices or three DUTs—the algorithm is identical. The three devices are arranged sequentially along the $+z$ incidence axis, each built from its own device file, with surrounding aluminum foil and PCBs placed following the two-device layout. An event is recorded only when all three devices exceed the amplitude threshold in the same event.

Label the three devices 1, 2, and 3. For each timing channel, [`analysis`](../stages/analysis.md) fits the three pairwise time-difference distributions $\Delta t_{12} = t_1 - t_2$, $\Delta t_{13} = t_1 - t_3$, and $\Delta t_{23} = t_2 - t_3$ to obtain core widths $\sigma_{12}$, $\sigma_{13}$, and $\sigma_{23}$. When the timings of the three devices are mutually independent:

$$\sigma_{12}^2 = \sigma_1^2 + \sigma_2^2, \qquad \sigma_{13}^2 = \sigma_1^2 + \sigma_3^2, \qquad \sigma_{23}^2 = \sigma_2^2 + \sigma_3^2 \tag{3}$$

Solving for the individual time resolutions of the three devices gives:

$$\sigma_1^2 = \frac{\sigma_{12}^2 + \sigma_{13}^2 - \sigma_{23}^2}{2}, \qquad \sigma_2^2 = \frac{\sigma_{12}^2 + \sigma_{23}^2 - \sigma_{13}^2}{2}, \qquad \sigma_3^2 = \frac{\sigma_{13}^2 + \sigma_{23}^2 - \sigma_{12}^2}{2} \tag{4}$$

where:

- $t_1$, $t_2$, $t_3$: reconstructed timing timestamps of the three devices in a given timing channel for the same event, $\text{s}$;
- $\sigma_{12}$, $\sigma_{13}$, $\sigma_{23}$: core widths of the three pairwise time-difference distributions fitted with Eq. (2), $\text{s}$;
- $\sigma_1$, $\sigma_2$, $\sigma_3$: individual time resolutions of the three devices, $\text{s}$.

Statistical fluctuations can make the right-hand side of Eq. (4) less than $0$. In that case the computed value is still output along with a warning.

Each of the three devices' time-difference distributions relative to its own true deposition time is still produced and fitted in the same way as for two devices. Thus, with three devices, each timing channel has six distributions in total: the three pairwise time differences $\Delta t_{12}$, $\Delta t_{13}$, $\Delta t_{23}$, plus $t_1 - t_{\text{truth},1}$, $t_2 - t_{\text{truth},2}$, and $t_3 - t_{\text{truth},3}$.

### Execution Steps and Built-in Constants

`timeres` executes in the following steps:

1. **Solve or reuse shared fields (`field`)**: locates the electric field, weighting field, and equivalent circuit parameters separately for the DUT and the reference device at their target biases `voltage` ($\text{V}$) and irradiation fluences `irradiation` ($\text{neq/cm}^2$), automatically running `raser field` if not yet ready. Each device's shared field is stored under `field/` in its own device project.
2. **Simulate two-device deposition in `time_resolution` (`deposit`)**: builds both the reference device and DUT volumes from their respective device files together with `Al`, `pcb1`, and `pcb2`. Emits decay products from `decay/Sr90`, records valid deposited events up to the default `events_per_job = 10000` events (generating at most `GENERATED_LIMIT = 10000000` source events), samples electron-hole pairs via `ionized_pairs`, and writes them into a single `deposit_<job>.h5`, distinguishing steps in the reference device and the DUT by the `detector` field.
3. **Independent drift, readout, and digitization for both devices (`current`, `readout`, `digitizer`)**: the DUT and reference device each drift carriers in their respective solved fields to compute induced currents (default `current.plots = 0`, disabling per-event plots), solve output voltage waveforms with frequency-domain thermal noise through their respective equivalent circuits and front-end amplifier chains (default `SantaCruz+Gali52+Termination50`), and generate two channels of digital waveforms according to the digitizer sampling and quantization settings.
4. **Two-device coincidence trigger (`trigger`)**: inspects the digital waveforms of the reference device and DUT for the same event; under the trigger component's coincidence condition, all devices in the list must exceed the amplitude threshold in the same event. Only events passing coincidence are retained and passed downstream.
5. **Independent pulse timing extraction (`reconstruction`)**: for coincidence events, subtracts the leading `BASELINE_POINTS = 200` baseline points and flips polarity on each device's waveform, then linearly interpolates between adjacent samples to compute threshold-crossing arrival time `ToA`, time over threshold `ToT`, above-threshold time center of gravity `CoG`, and constant-fraction timestamps `CFD10`–`CFD90` crossing `fractions` (default `9` levels from `0.1` to `0.9`) times the peak `amplitude`.
6. **Iterative truncated-Gaussian fitting (`analysis`)**: aggregates coincidence events across all finished jobs and constructs the three sample sets of Eq. (1) (or the six sample sets listed above for three devices) for each timing channel (`ToA`, `CoG`, `CFD10`–`CFD90`), filtering out `NaN` values and recording `timing.error` if fewer than `MINIMUM_EVENTS = 20` samples remain. For each sample set, sets the initial window $[a, b]$ to the median plus or minus $8$ times the median absolute deviation, $\text{median} \pm 8\,\text{MAD}$, and executes `core_width` for up to `ROUNDS = 6` iterations: selects samples inside the window (raising `TooFewValues` if fewer than `20` in the first round, or stopping and returning the previous round's result if fewer than `20` in later rounds), minimizes Eq. (2) with `L-BFGS-B` (mean constrained to $[a, b]$) to obtain $(\mu, \sigma)$, and inverts the second-order central-difference Hessian with step `step = 1e-4` to get standard errors. Iteration stops upon convergence when $|\sigma - \sigma_{\text{prev}}| \le 5\times 10^{-3}\,\sigma_{\text{prev}}$, when the new window $[\mu - 2\sigma, \mu + 2\sigma]$ extends outside the previous window, or when the window-width reduction is $\le 10^{-3}(b - a)$. Each sample set yields a core width, and `result.json`, `events.h5`, distribution plots, and trend plots are written.

The built-in constants in `timeres` are listed below:

| Constant or Fixed Item | Value | Unit | Meaning |
| --- | --- | --- | --- |
| Default `events_per_job`, `deposit.plots`, `current.plots` | `10000`, `0`, `0` | events | Default recorded events per job and default plotted event counts in `timeres` for the two stages |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | Default minimum half-side of the Geant4 world cube |
| `maxstep` | `2` | $\mu\text{m}$ | Maximum step size limit inside the DUT and reference device logical volumes |
| `GENERATED_LIMIT` | `10000000` | events | Maximum number of generated source events allowed per job to reach `events_per_job` |
| `BASELINE_POINTS` | `200` | samples | Number of leading waveform samples used for baseline subtraction and noise calculation in reconstruction |
| `MINIMUM_EVENTS` | `20` | events | Minimum number of valid samples required by `core_width` for truncated-Gaussian fitting |
| `ROUNDS` | `6` | rounds | Maximum number of iteration rounds in which `core_width` updates the fit window to $\mu \pm 2\sigma$ |
| Initial-window MAD multiplier | `8` | dimensionless | First-round fit window is set to $\text{median} \pm 8\,\text{MAD}$ |
| Fit convergence thresholds | `5e-3`, `1e-3` | dimensionless | Relative-change convergence threshold for $\sigma$ and minimum relative window-width reduction |
| Hessian finite-difference step `step` | `1e-4` | dimensionless | Step size for second-order central differences of the normalized log-likelihood to compute parameter errors |

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, and equivalent circuit parameters at the target bias and irradiation fluence separately for the DUT and reference device, stored under `field/` in each device's own project.
- [`deposit`](../stages/deposit.md): uses Geant4 in the `time_resolution` setup to simulate particles traversing the aluminum foil, reference device, upper PCB, DUT, and lower PCB sequentially, recording energy deposition in both devices simultaneously up to `10000` valid events per job by default.
- [`current`](../stages/current.md): drifts carriers separately in the solved fields of the DUT and reference device to compute induced currents and net charge on their respective readout electrodes, with per-event plotting off by default (`current.plots = 0`).
- [`readout`](../stages/readout.md): feeds each device's induced current into its own device equivalent circuit and front-end amplifier chain to solve output voltage waveforms with frequency-domain thermal noise.
- [`digitizer`](../stages/digitizer.md): converts each device's analog output waveform into a digital waveform according to the oscilloscope or digitizer-board sampling and quantization settings.
- [`trigger`](../stages/trigger.md): performs two-device coincidence triggering on the digital waveforms of both devices, recording an event only when both devices exceed the amplitude threshold in the same event.
- [`reconstruction`](../stages/reconstruction.md): subtracts baseline and flips polarity separately on the DUT and reference-device waveforms of coincidence events, extracting amplitude, `ToA`, `ToT`, `CoG`, and `9` levels of `CFD` timestamps for each device.
- [`analysis`](../stages/analysis.md): fits the three time-difference distributions of Eq. (1) for each timing channel and outputs summary tables, event tables, distribution plots, and cross-point trend plots.

### Components

- [Detector components (`components/device`)](../components/device.md): provides geometry, material, doping, bias voltage, temperature, irradiation, and avalanche multiplication parameters for the DUT and reference device. The reference device defaults to `HPK-Si-LGAD` (`HPK-Si-LGAD.json`), and the DUT is given on the command line (such as `HPK-Si-PiN`, `NJU-PiN`, `SICAR-1`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides the default Geant4 setup `time_resolution` (`src/raser/bench/timeres/components/g4setup/time_resolution.py`) and the default $\beta$ radioactive source `decay/Sr90` (`decay/Sr90.json`).
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides SPICE amplifier stages and termination load subcircuits cascaded with `+` (default `SantaCruz+Gali52+Termination50`).
- [Digitizer components (`components/digitizer`)](../components/digitizer.md): provides sampling and quantization settings of an oscilloscope or digitizer board (such as `scope`).
- [Trigger components (`components/trigger`)](../components/trigger.md): trigger condition definitions; `timeres` requires both (or all three) devices to exceed the amplitude threshold in the same event.

## Usage and Configuration

Run the time-resolution test directly on a DUT, or use `--scan` to scan parameters such as bias voltage and thresholds; the device passed on the command line replaces the DUT role while the reference device defaults to `HPK-Si-LGAD`:

```bash
raser timeres HPK-Si-PiN
raser timeres NJU-PiN
raser timeres NJU-PiN --scan field.voltage=-300,-500
```

The experiment directory `<project>/timeres/config.json` stores settings sectioned by stage (see [Architecture Overview](../architecture.md#project) for the format). The device list is defined in the `timeres` experiment class, where the command-line device replaces the DUT and the reference device defaults to `HPK-Si-LGAD`. Bias voltage, irradiation fluence, amplifier chain, trigger threshold, and reconstruction threshold are configured individually for each device in the list. The table below lists the keys for one device; with multiple devices, each device has its own set:

| Section.Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `bias.voltage` from the DUT device file | $\text{V}$ | DUT bias voltage |
| `field.irradiation` | `None` (uses device `irradiation.irradiation_flux` if omitted, or `0` if absent) | $\text{neq/cm}^2$ | DUT irradiation fluence |
| `deposit.source` | `"decay/Sr90"` | None | Radioactive source or beam component name or path |
| `deposit.g4setup` | `"time_resolution"` | None | Geant4 setup component name or path |
| `deposit.events_per_job` | `10000` | events | Number of valid deposited events to record per job (mutually exclusive with `deposit.generated_per_job`) |
| `deposit.generated_per_job` | `None` | events | Total number of events generated from the source per job (mutually exclusive with `deposit.events_per_job`) |
| `deposit.generated_limit` | `None` (`10000000` at runtime) | events | Maximum number of generated source events allowed to reach `events_per_job` |
| `deposit.edep_min` | `None` | $\text{MeV}$ | Lower bound on deposited energy for recorded events |
| `deposit.edep_max` | `None` | $\text{MeV}$ | Upper bound on deposited energy for recorded events |
| `deposit.fano` | `True` | None | Whether to enable Fano fluctuation sampling when converting deposited energy to ionized pairs |
| `deposit.plots` | `0` | events | Number of leading recorded events per job for which Geant4 geometry and track plots are drawn |
| `current.plots` | `0` | events | Number of leading recorded events per job for which carrier drift path and current plots are drawn |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | Threshold-crossing level for extracting `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | Pulse amplitude threshold for finding cluster seeds; whether an event is recorded is decided by `trigger` according to the trigger component |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` | `None` (each device inherits `pulse_edge` written by its own `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` |

All other parameters (dimensions, materials, and positions of `Al`, `pcb1`, and `pcb2` in `time_resolution.py`, reference-device center coordinate `z = -10000 um`, default world half-side `25000 um`, maximum step size `2 um` inside both devices, default maximum generated event limit `10000000`, material mean ionization energies and Fano factors, drift time-window and time-step profiles, `ngspice` noise-analysis frequency range and `27 °C` temperature, `200` reconstruction baseline points, initial truncated-Gaussian fit window `median ± 8 * MAD`, minimum sample count `20`, and maximum iteration rounds `6`) are fixed in the code and default setup script.

## Outputs

Results are stored under `<project>/timeres/` inside the DUT's project directory (such as `work/<dut>/timeres/`); see [Architecture Overview](../architecture.md#results) for the storage layout. Each stage writes by input fingerprint to `<project>/timeres/nodes/<stage>/<node>/`, per-scan-point symlink views are created at `<project>/timeres/points/<point>/<stage>` with the parameter table recorded in `<project>/timeres/points.json`, and single-point and cross-point time-resolution statistics and trend plots are stored under `<project>/timeres/analysis/`. The shared fields of the DUT and reference device are stored under `field/` in each device's own project directory (such as `work/<dut>/field/` and `work/HPK-Si-LGAD/field/`).

### Data and Plot Files

Upstream stage data files follow the same format as [`signal`](signal.md#outputs), with one copy for each of the two devices; `deposit_<job>.h5` distinguishes deposition steps of the two devices by `detector`. [`analysis`](../stages/analysis.md) writes:

- `analysis/[<point>/]result.json`: total event count, coincidence event count, and the core width, `sigma68`, and fit error (in $\text{s}$) for each of the three time-difference distributions ($t_{\text{DUT}} - t_{\text{ref}}$, $t_{\text{DUT}} - t_{\text{truth,DUT}}$, $t_{\text{ref}} - t_{\text{truth,ref}}$) in every timing channel `ToA`, `CoG`, `CFD10`–`CFD90`.
- `analysis/[<point>/]events.h5`: `ToA`, `ToT`, `amplitude`, `baseline`, `noise`, `truth`, `CoG`, and `CFD10`–`CFD90` for both devices on every coincidence event, with voltages in $\text{V}$ and times in $\text{s}$.
- `analysis/[<point>/]time_difference.png`: distributions of the three time differences, final-round fit windows, and truncated-Gaussian fit curves for each timing channel, with horizontal axis in $\text{ps}$.
- `analysis/[<point>/]resolution_of_fraction.png`: core widths of the three distributions versus constant fraction across all `CFD*` channels, with vertical axis in $\text{ps}$.
- With three devices, `result.json` reports for each timing channel the core widths $\sigma_{12}$, $\sigma_{13}$, $\sigma_{23}$ of the three pairwise time-difference distributions, the individual resolutions $\sigma_1$, $\sigma_2$, $\sigma_3$ solved via Eq. (4), and the core widths of each device's time difference relative to its own true deposition time; `time_difference.png` plots all six distributions (three pairwise time differences plus three individual differences relative to true deposition time).
- `analysis/points.json`, `analysis/points.png`: multi-scan-point comparison table of the core widths of the three distributions for every timing channel (in $\text{s}$) and trend curves versus the scan variable (in $\text{ps}$).
