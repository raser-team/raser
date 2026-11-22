# Beam Telescope Spatial Resolution Test (`bench/telescope`)

`telescope` (in the `raser_bench` package) is a benchmark class inheriting from the `raser` experiment base class (see [Architecture Overview](../architecture.md#experiments-are-python-classes)) that uses a beam telescope to measure the spatial resolution of a position-sensitive device under test (DUT) in the $x$ and $y$ directions. The telescope consists of a sequence of detector planes arranged along the beam axis, specified by a device list: every listed device is placed as a real device built from its device file—several upstream reference layers, the DUT in the middle, and several downstream reference layers. The reference layers default to `TAICHU3` (Taichu3 CMOS pixel detector), and by default two DUTs are placed in the middle; the device specified on the command line replaces both middle DUTs. The total number of layers in the telescope is arbitrary, the device in any layer can be replaced by another device, and each layer's board can be oriented in any of four directions in the $x$-$y$ plane.

`telescope` reads [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence: [`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md). All detector planes share a single [`deposit`](../stages/deposit.md) run simulating a high-energy particle beam traversing all layers sequentially. Each layer individually runs `field`, `current`, `readout`, `digitizer`, `trigger`, and `reconstruction`, where `reconstruction` clusters hits on each layer to determine hit positions and fits a straight track to the reference-layer hits to extrapolate to the DUT plane. Limitation: `analysis` currently only computes statistics for single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad aggregation for cflm) have not been implemented yet.

## Setup and Standard Practice

### Standard Practice and Physical Model

When measuring the spatial resolution of a position-sensitive detector in a beam test, the DUT is placed in the middle of a beam telescope composed of upstream and downstream high-precision pixel reference detectors (such as `TAICHU3`, MIMOSA26, or ALPIDE). After a high-energy particle beam traverses all detector planes, each layer performs connected-component clustering on hit pixels above threshold to compute the hit centroid; a straight track is fitted to the hit positions on the reference layers and extrapolated to the DUT plane, and the residuals between the measured DUT hit positions and the extrapolated positions are collected. The Gaussian standard deviation of the residual distribution reflects the spatial resolution of the DUT.

The telescope comprises $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers, defaulting to 3 + 2 + 3 (3 `TAICHU3` layers upstream and 3 downstream, with 2 DUTs in the middle). The total number of reference layers is $N_{\text{ref}} = N_{\text{front}} + N_{\text{back}}$ (with reference-layer index set $\mathcal{R}$), and the total number of telescope layers is $N = N_{\text{front}} + N_{\text{DUT}} + N_{\text{back}}$. In each layer's local coordinate system, [`reconstruction`](../stages/reconstruction.md) clusters hit pixels above threshold using pixel geometric center coordinates, an eight-neighbor connectivity criterion, and the arithmetic-mean centroid:

$$(x_{p}, y_{p}) = \bigl((i_x + 0.5)\,p_x,\; (i_y + 0.5)\,p_y\bigr), \qquad \Delta x^{2} + \Delta y^{2} \le p_x^{2} + p_y^{2} + \epsilon, \qquad (\bar{x}_{c}, \bar{y}_{c}) = \frac{1}{n_c}\sum_{m=1}^{n_c}(x_{p,m}, y_{p,m}) \tag{1}$$

Each layer's local cluster centroid is transformed into the global telescope $(x, y)$ coordinate system according to that layer board's orientation in the $x$-$y$ plane; the hit positions on reference layer $j$ ($j \in \mathcal{R}$) and DUT $d$ ($d = 1, \dots, N_{\text{DUT}}$) are denoted $(\bar{x}_{c,j}, \bar{y}_{c,j})$ and $(\bar{x}_{c,d}, \bar{y}_{c,d})$. [`reconstruction`](../stages/reconstruction.md) selects events in which both the reference layers and the DUT produce a single cluster, and performs ordinary least-squares straight-line fits in $x$-$z$ and $y$-$z$ using the sensitive-layer mid-plane coordinates $z_j + l_{z,j}/2$ and hit positions $(\bar{x}_{c,j}, \bar{y}_{c,j})$ of all $N_{\text{ref}}$ reference layers:

$$\hat{x}(z) = k_x z + b_x, \qquad \hat{y}(z) = k_y z + b_y \tag{2}$$

Extrapolating the reference track to the mid-plane $z_d + l_{z,d}/2$ of DUT $d$ yields the residuals $(r_{x,d}, r_{y,d})$ and $(r_{x,j}, r_{y,j})$ on the DUT and reference layers, and the fit residuals on the $N_{\text{ref}}$ reference layers give the reference track $\chi^2$:

$$\begin{aligned}
r_{x,d} &= \hat{x}\!\left(z_d + \frac{l_{z,d}}{2}\right) - \bar{x}_{c,d}, & r_{y,d} &= \hat{y}\!\left(z_d + \frac{l_{z,d}}{2}\right) - \bar{y}_{c,d}, \\
r_{x,j} &= \hat{x}\!\left(z_j + \frac{l_{z,j}}{2}\right) - \bar{x}_{c,j}, & r_{y,j} &= \hat{y}\!\left(z_j + \frac{l_{z,j}}{2}\right) - \bar{y}_{c,j}, & \chi^{2} &= \sum_{j \in \mathcal{R}}\left(\frac{r_{x,j}^{2}}{p_{x,j}^{2}/12} + \frac{r_{y,j}^{2}}{p_{y,j}^{2}/12}\right)
\end{aligned} \tag{3}$$

Gaussian fits to the $x$ and $y$ residual distributions of DUT $d$ yield the residual standard deviation $\sigma_{\text{Tol},d}$ ($\mu\text{m}$). $\sigma_{\text{Tol},d}$ includes both the intrinsic resolution of the DUT and the telescope extrapolation uncertainty; `telescope` outputs this distribution and its width.

The meaning and unit of each symbol are:

| Symbol | Meaning | Unit |
| --- | --- | --- |
| $N_{\text{front}}, N_{\text{back}}$ | Numbers of reference layers upstream and downstream of the DUT (default `3` each) | dimensionless |
| $N_{\text{ref}}$ | Total number of reference layers, $N_{\text{ref}} = N_{\text{front}} + N_{\text{back}}$ ($N_{\text{ref}} \ge 2$); $\mathcal{R}$ is the index set of all reference layers | dimensionless |
| $N_{\text{DUT}}$ | Number of DUT layers in the middle of the telescope (default `2`); $d = 1, \dots, N_{\text{DUT}}$ indexes the DUTs | dimensionless |
| $N$ | Total number of telescope layers, $N = N_{\text{front}} + N_{\text{DUT}} + N_{\text{back}}$ | dimensionless |
| $i_x, i_y$ | Column and row indices of a pixel within its device array (starting from `0`) | dimensionless |
| $p_x, p_y$ | Pixel pitch in the layer's local $x$ and $y$ directions | $\mu\text{m}$ |
| $p_{x,j}, p_{y,j}$ | Pixel pitch of reference layer $j$ mapped into the global telescope $x$ and $y$ directions according to its orientation | $\mu\text{m}$ |
| $(x_p, y_p)$ | Coordinates of a pixel geometric center in the layer-local frame; $(x_{p,m}, y_{p,m})$ is the center of the $m$-th pixel in a cluster | $\mu\text{m}$ |
| $\Delta x, \Delta y$ | Distance between two hit pixel centers on the same layer in local $x$ and $y$ | $\mu\text{m}$ |
| $\epsilon$ | Floating-point tolerance for the connectivity criterion, $10^{-7}$, ensuring all four orthogonal and four diagonal neighbors in the eight-neighborhood are considered connected | $\mu\text{m}^2$ |
| $n_c$ | Number of pixels in a single connected cluster | count |
| $(\bar{x}_c, \bar{y}_c)$ | Arithmetic-mean centroid coordinates of a cluster in the layer-local frame | $\mu\text{m}$ |
| $(\bar{x}_{c,j}, \bar{y}_{c,j}), (\bar{x}_{c,d}, \bar{y}_{c,d})$ | Cluster centroid coordinates of reference layer $j$ and DUT $d$ after transformation into the global telescope frame | $\mu\text{m}$ |
| $z_j, z_d$ | Front-surface position coordinate along the beam axis for reference layer $j$ and DUT $d$ | $\mu\text{m}$ |
| $l_{z,j}, l_{z,d}$ | Sensitive-layer thickness of reference layer $j$ and DUT $d$ | $\mu\text{m}$ |
| $k_x, k_y$ | Slopes of the fitted straight track from reference layers in the $x$-$z$ and $y$-$z$ planes | dimensionless |
| $b_x, b_y$ | Intercepts of the fitted straight track from reference layers in the $x$-$z$ and $y$-$z$ planes | $\mu\text{m}$ |
| $\hat{x}(z), \hat{y}(z)$ | Global transverse coordinates of the straight track extrapolated to beam-axis position $z$ ($\mu\text{m}$) | $\mu\text{m}$ |
| $r_{x,d}, r_{y,d}$ | $x$ and $y$ residuals between the extrapolated position and measured centroid at the mid-plane $z_d + l_{z,d}/2$ of DUT $d$ | $\mu\text{m}$ |
| $r_{x,j}, r_{y,j}$ | Track-fit $x$ and $y$ residuals at the mid-plane $z_j + l_{z,j}/2$ of reference layer $j$ ($j \in \mathcal{R}$) | $\mu\text{m}$ |
| $\chi^2$ | Reference-track fit chi-square normalized by the uniform pixel variances $p_{x,j}^2/12$ and $p_{y,j}^2/12$ of each reference layer | dimensionless |
| $\sigma_{\text{Tol},d}$ | Total Gaussian-fitted standard deviation of the $x$ or $y$ residual distribution of DUT $d$ | $\mu\text{m}$ |

Standard beam-telescope track fitting and spatial-resolution extraction are described in Ref. [1] (H. Jansen et al., “Performance of the EUDET-type beam telescopes”, *EPJ Tech. Instrum.* 3 (2016) 7, doi:10.1140/epjti/s40485-016-0033-2), and beam tests of the TaichuPix CMOS pixel sensor are reported in Ref. [2] (T. Wu et al., “Beam test of a 180 nm CMOS pixel sensor for the CEPC vertex detector”, *Nucl. Instrum. Methods Phys. Res. A* 1059 (2024) 168945, doi:10.1016/j.nima.2023.168945).

### Telescope Setup Geometry

The telescope consists of $N$ detector planes arranged sequentially along $+z$: $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers, defaulting to 3 + 2 + 3. The entire telescope is fully configuration-driven: the device list, number of layers, device per layer, and board orientations are all specified in configuration. The telescope is defined by a device list—every listed device is constructed as a physical volume in the Geant4 setup from its corresponding device file. The device given on the command line replaces both middle DUTs; besides the DUTs, any upstream or downstream reference layer may also be replaced by another device, and the layer count of each section can be freely adjusted via the device list.

Reference layers default to `TAICHU3` (`TAICHU3.json`): a silicon (`"Si"`) pixel detector with full dimensions $l_x = 1500\ \mu\text{m}$, $l_y = 1500\ \mu\text{m}$, $l_z = 20\ \mu\text{m}$, an array of $60 \times 60$ pixels (`3600` total), pixel pitch $p_x = p_y = 25.0\ \mu\text{m}$, a centered rectangular collection zone of $10.0 \times 10.0\ \mu\text{m}$ per pixel, operating temperature $300.0\ \text{K}$, default bias `-1.8` $\text{V}$, acceptor concentration `1e12` $\text{cm}^{-3}$, and donor concentration `0` $\text{cm}^{-3}$.

The setup used in the example configuration is `telescope` from [energy deposition components](../components/deposit.md#built-in-geant4-setups): 8 slots arranged along $+z$ in vacuum at equal $40\ \text{mm}$ spacing, with every slot's front-surface center on the beam axis and `rotation_z` set to `0`.

| Slot | Role | Default Device | Front-Surface $z$ ($\text{mm}$) | `rotation_z` (degrees) |
| --- | --- | --- | --- | --- |
| `ref1` | Reference layer | `TAICHU3` | `-140` | `0` |
| `ref2` | Reference layer | `TAICHU3` | `-100` | `0` |
| `ref3` | Reference layer | `TAICHU3` | `-60` | `0` |
| `dut1` | Device under test (DUT) | Device given on the command line | `-20` | `0` |
| `dut2` | Device under test (DUT) | Device given on the command line | `20` | `0` |
| `ref4` | Reference layer | `TAICHU3` | `60` | `0` |
| `ref5` | Reference layer | `TAICHU3` | `100` | `0` |
| `ref6` | Reference layer | `TAICHU3` | `140` | `0` |

The beam used in the example configuration is `beam/electron_5GeV_spread`: $5\ \text{GeV}$ electrons are emitted from $z = -400\ \text{mm}$ along $+z$ with a uniform aiming spread of $\pm 750\ \mu\text{m}$ in both $x$ and $y$ (aiming point at $z = 100\ \text{mm}$), covering the $1.5 \times 1.5\ \text{mm}$ sensitive area of the reference layers.

Each layer's detector board is mounted perpendicular to the beam axis $z$ and may be oriented in one of four directions in the $x$-$y$ plane (rotated by $0^\circ$, $90^\circ$, $180^\circ$, or $270^\circ$ around the $z$ axis). Following standard beam-telescope practice, this degree of freedom serves two needs:

- **Measuring spatial resolution in both $x$ and $y$**: strip detectors or non-square pixel detectors ($p_x \ne p_y$) have high position resolution only along a single sensitive coordinate or short pitch axis. Rotating a board by $90^\circ$ (for example, mounting the two DUTs orthogonally at $0^\circ$ and $90^\circ$, or rotating selected reference layers by $90^\circ$) allows measuring spatial resolution in both $x$ and $y$ within the same telescope coordinate frame, or providing high-precision track constraints along both orthogonal coordinates simultaneously.
- **Matching mechanical mounting and cable routing in beam tests**: constrained by support frames, cooling manifolds, and readout PCB routing in the beam area, adjacent detector boards are frequently installed rotated by $90^\circ$, $180^\circ$, or $270^\circ$ to stagger readout chips and cables. Specifying each layer's board orientation ensures that its local pixel coordinates transform accurately into the unified global telescope $(x, y)$ frame.

### Execution Steps

`telescope` executes the eight-stage chain in order:

1. **Solve or reuse shared fields per layer ([`field`](../stages/field.md))**: locates the electric field, weighting field, and equivalent circuit parameters for each device in the device list at its target bias `voltage` ($\text{V}$) and irradiation fluence `irradiation_flux` ($\text{cm}^{-2}$, $1\ \text{MeV}$ neutron-equivalent fluence), computing them before jobs start if not yet ready. Each device's shared field nodes are stored under `field/<node>/` in that device's project directory.
2. **Full-telescope energy deposition ([`deposit`](../stages/deposit.md))**: builds the $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers in the Geant4 telescope setup according to the device list and layer orientations. The high-energy particle beam traverses all $N$ planes along $+z$, recording energy deposition steps across all layers together, converting them into initial electron-hole pairs, and writing them to `deposit.h5` in the `deposit` node tagged by layer.
3. **Per-layer drift, readout, digitization, and triggering ([`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md))**: each layer independently drifts carriers in its solved field, computes induced currents and net charge on its pixel electrodes, and solves analog voltage waveforms through its device equivalent circuit and front-end amplifier chain, adding circuit thermal noise using the `readout` noise seed derived from the job seed. Each layer then generates quantized-code digital waveforms in the `digitizer` node according to the digitizer's analog bandwidth, sampling rate, and quantization bit depth (with clock phase and aperture jitter drawn from the `digitizer` seed derived from the job seed), and writes the `event` (`int64`) dataset of recorded event IDs via trigger selection to `trigger.h5` in the `trigger` node.
4. **Clustering and track fitting ([`reconstruction`](../stages/reconstruction.md))**: reads the events in `digitizer.h5` recorded by `trigger.h5`, converts quantized codes back to voltage ($\text{V}$) using `lsb_V` and `offset_V` with sampling times `t0 + k·sampling_period`; on each layer, extracts pixel signal features, finds cluster seeds using `amplitude_threshold` and marks events with a found seed as `selected`, and performs connected-component clustering on hit pixels above threshold via Eq. (1) to obtain the local hit position $(\bar{x}_c, \bar{y}_c)$ ($\mu\text{m}$) and cluster size $n_c$ (count); transforms hit positions into the global telescope frame according to each layer's orientation, fits a straight track to all $N_{\text{ref}}$ reference layers via Eq. (2), and extrapolates it to each DUT plane.
5. **Statistics ([`analysis`](../stages/analysis.md))**: Limitation: `analysis` currently only computes statistics for single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad aggregation for cflm) have not been implemented yet.

### Fast Run

When `reconstruction.hits = "deposit"`, `telescope` skips `field`, `current`, `readout`, `digitizer`, and `trigger`, and [`reconstruction`](../stages/reconstruction.md) reads the `deposit` node directly: pixels on a layer with deposited electron-hole pairs are recorded as hit pixels above threshold, while everything else follows step 4. Paired with the straight-line MIP source `toy/MIP_telescope` (without launching Geant4 and without multiple scattering), residuals come solely from pixel discretization, allowing quick scans of the DUT pixel pitch, layer spacing, and orientation to inspect the resolution given by geometry alone.

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, and equivalent circuit parameters at the target bias and irradiation fluence separately for each layer's device, stored under `field/<node>/` in the corresponding device project.
- [`deposit`](../stages/deposit.md): uses Geant4 in the beam-telescope setup to simulate a high-energy particle beam traversing the $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers, recording deposition steps for all layers together, converting them into initial electron-hole pairs, and writing `deposit.h5`.
- [`current`](../stages/current.md): simulates carrier drift, diffusion, and collection in each layer's solved field to compute the induced current and net induced charge on each electrode of that layer.
- [`readout`](../stages/readout.md): feeds each layer's electrode induced currents into its corresponding device equivalent circuit and front-end amplifier chain to solve output analog voltage waveforms with circuit thermal noise.
- [`digitizer`](../stages/digitizer.md): converts each layer's analog output waveforms into quantized-code digital waveforms according to the digitizer's analog bandwidth, sampling rate, and quantization bit depth.
- [`trigger`](../stages/trigger.md): applies trigger conditions to each layer's digital waveforms to select events to record, writing the event IDs of recorded events to `trigger.h5`.
- [`reconstruction`](../stages/reconstruction.md): reads the events in `digitizer.h5` recorded by `trigger`, converts quantized codes back to voltage ($\text{V}$) using `lsb_V` and `offset_V`, clusters hit pixels above threshold on each layer via Eq. (1) to obtain hit positions and marks events with a found seed as `selected`, then fits a straight track to reference-layer hits via Eq. (2) and extrapolates to the DUT planes.
- [`analysis`](../stages/analysis.md): Limitation: `analysis` currently only computes statistics for single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad aggregation for cflm) have not been implemented yet.

### Components

- [Detector components (`components/device`)](../components/device.md): provides definitions of the telescope reference-layer pixel detector (default `TAICHU3`, dimensions $1500 \times 1500 \times 20\ \mu\text{m}$, pitch $25.0 \times 25.0\ \mu\text{m}$) and the DUT placed in the middle; any layer in the list can use any device from the component library or a user project.
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides high-energy particle beam components and the beam-telescope Geant4 setup arranging multi-layer detector planes according to the device list.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides the front-end amplifier and termination load SPICE subcircuit chains used by each detector layer.
- [Digitizer components (`components/digitizer`)](../components/digitizer.md): provides analog bandwidth, sampling rate, and quantization bit-depth settings for each layer's readout waveforms (such as `MXR608A`).
- [Trigger components (`components/trigger`)](../components/trigger.md): provides trigger condition definitions for recording telescope events.

## Usage and Configuration

Pass the name of the DUT placed in the middle of the telescope on the command line to run the spatial resolution test (see [Command-Line Interface](../cli.md#commands)), or use `--set` and `--scan` to modify or scan settings such as bias voltage ($\text{V}$) and threshold ($\text{mV}$):

```bash
raser telescope <device>
raser telescope <device> --scan field.voltage=-100,-200
raser telescope <device> --set deposit.g4setup.devices.dut2.rotation_z=90
raser telescope <device> --set deposit.source=toy/MIP_telescope --set reconstruction.hits=deposit
```

The third line rotates the second DUT by $90^\circ$, and the fourth line is the fast run.

The experiment directory `<project>/telescope/config.json` records settings sectioned by stage (see [Architecture Overview](../architecture.md#project) for the format). The telescope device list is defined in the `telescope` experiment class, with 3 `TAICHU3` layers upstream and 3 downstream by default and two DUTs in the middle; the device given on the command line replaces the DUTs. The device list, per-layer orientations, and per-layer settings such as bias voltage are configured individually.

The table below lists the stage configuration keys shared between `telescope` and other benchmark pages; the `deposit` section is shared across all layers, while all other sections are configured per layer in the multi-layer telescope. "Example Value" shows the value written in `telescope/config.json` of an example project; if `config.json` is missing a required key, an error is raised naming the missing "section.key":

| Section.Key | Example Value | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `null` (uses bias from the corresponding device file) | $\text{V}$ | Bias voltage of that layer's device |
| `field.irradiation_flux` | `null` (uses irradiation fluence from the device file, or `0` if the device file has no irradiation block) | $\text{cm}^{-2}$ | Irradiation fluence of that layer's device ($1\ \text{MeV}$ neutron-equivalent fluence) |
| `deposit.source` | Beam component name | None | Incident particle beam component name or path |
| `deposit.g4setup` | `"telescope"` | None | Geant4 beam-telescope setup component name or path |
| `deposit.events_per_job` | `1000` | events | Number of valid deposited events to record per job (mutually exclusive with `deposit.generated_per_job`) |
| `deposit.generated_per_job` | `null` (unused) | events | Total number of events generated from the beam source per job (mutually exclusive with `deposit.events_per_job`) |
| `deposit.generated_limit` | `10000000` | events | Maximum number of generated source events allowed to reach `events_per_job` |
| `deposit.edep_min` | `null` (no lower bound) | $\text{MeV}$ | Lower bound on deposited energy for recorded events |
| `deposit.edep_max` | `null` (no upper bound) | $\text{MeV}$ | Upper bound on deposited energy for recorded events |
| `deposit.fano` | `true` | None | Whether to enable Fano fluctuation sampling when converting deposited energy to ionized pairs |
| `deposit.plots` | `100` | events | Number of leading recorded events per job for which Geant4 geometry and track plots are drawn |
| `current.plots` | `100` | events | Number of leading recorded events per job for which carrier drift path and current plots are drawn |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `readout.sheet_resistance` | `null` (uses sheet resistance of the resistive layer in the device file) | $\Omega$ | Overrides the resistive-layer sheet resistance for devices containing `resistive_layer` |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | Pixel signal threshold-crossing level and threshold for adding neighboring pixels to a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | Pulse amplitude threshold for cluster seed pixels; events recorded by `trigger` in which a seed is found are marked `selected` (whether an event is recorded is decided by `trigger` according to the trigger conditions) |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` | `null` (inherits `pulse_edge` written by the corresponding layer's `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` |
| `reconstruction.hits` | `"signal"` | None | Source of hit pixels: `"signal"` takes digital waveforms recorded by `trigger` crossing `reconstruction.threshold`; `"deposit"` takes pixels with deposited electron-hole pairs (fast run) |
| `reconstruction.plots` | `10` | events | Number of leading selected events per job for which track-fit plots are drawn |

The position and orientation of each slot in the setup `deposit.g4setup` are component-internal keys addressed as `deposit.g4setup.devices.<slot>.position` ($\mu\text{m}$) and `deposit.g4setup.devices.<slot>.rotation_z` (degrees).

## Outputs

Test results are stored under `<project>/telescope/` in the DUT's project directory (such as `work/<dut>/telescope/`); see [Architecture Overview](../architecture.md#results) for the storage layout. Each stage writes by input fingerprint to underlying nodes `<project>/telescope/nodes/<stage>/<node>/` (containing that stage's output files, stage plots, and `node.json`; one node per job from `deposit` through `reconstruction`, and one node per scan point for `analysis`), the upper layer generates per-scan-point symlink views at `<project>/telescope/points/<point>/<stage>/<job>` (`points/<point>/field` and `points/<point>/analysis` are each a single symlink) and records the parameter table in `<project>/telescope/points.json`; each scan point's single-point statistical summary and distribution plots are stored in its own `analysis` node (view `<project>/telescope/points/<point>/analysis/`), cross-point summaries and trend plots are stored under `<project>/telescope/analysis/`, while plots produced by each stage are placed in that stage's node outputs.

Shared field nodes for each telescope layer's device are stored under `field/<node>/` in that device's own project directory (such as `work/<dut>/field/<node>/` and `work/TAICHU3/field/<node>/`).

The main outputs written by each stage and by statistical analysis are:

- **Upstream stage nodes ([`deposit`](../stages/deposit.md) through [`reconstruction`](../stages/reconstruction.md))**: `deposit.h5` in the `deposit` node records energy deposition steps and ionized pairs across all $N$ planes (coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, ionized pairs in pairs). In the job nodes, each layer separately stores its corresponding induced currents and net collected charge (`current.<position>.h5`, time $\text{s}$, current $\text{A}$, charge $\text{C}$), front-end readout analog voltage waveforms (`readout.<position>.h5`, time $\text{s}$, voltage $\text{V}$), digitized quantized-code waveforms (`digitizer.<position>.h5`, quantized integer codes `code` [`int16`, dimensionless] and conversion attributes `lsb_V` [$\text{V}$], `offset_V` [$\text{V}$], `sampling_period` [$\text{s}$], `bits` [bits]; see [`stages/digitizer.md`](../stages/digitizer.md) for the format), triggered recorded events (`trigger.h5`, dataset `event` [`int64`] of recorded event IDs), and per-event clustered hit positions ($\mu\text{m}$), cluster sizes (count), and straight-track fit results (`reconstruction.<position>.h5`).
- **Spatial resolution statistics and plots ([`analysis`](../stages/analysis.md))**: Limitation: `analysis` currently only computes statistics for single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad aggregation for cflm) have not been implemented yet.

The `plots/` directory of each stage node contains the following plots (see [Plotting](../supports/figures.md) for conventions):

| Stage | Plot Name | Content | Count |
| --- | --- | --- | --- |
| deposit | `geometry` | Geant4 geometry of the telescope and tracks of the first `deposit.plots` events | One per node |
| reconstruction | `hitmap_<slot>` | 2D distribution of cluster centroids in layer-local coordinates across all recorded events on that layer (`x [μm]`, `y [μm]`, color scale for cluster count) | One per layer |
| reconstruction | `track_<event>` | Left: $x$-$z$; right: $y$-$z$. Cluster centroids of each layer (filled for reference layers, open for DUTs) and the fitted straight line from Eq. (2) (`z [mm]`, `x [μm]`, `y [μm]`) | First `reconstruction.plots` selected events |
| analysis | `residual_<slot>` | Left: $r_x$; right: $r_y$. DUT residual distributions (`Residual x [μm]`, `Events`) with Gaussian fit curves and $\sigma_{\text{Tol}}$ labeled | One per DUT |

![Electrons collected per pixel on one TAICHU3 layer](../images/telescope-pixel-charge.png)

Number of electrons collected by each pixel on one `TAICHU3` layer in a single event ($60 \times 60$ pixel array; horizontal axis `X` is pixel column index, depth axis `Y` is pixel row index, vertical axis is collected electron count, unit: count).
