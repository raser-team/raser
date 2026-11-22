# Beam Telescope Spatial Resolution Test (`bench/telescope`)

`telescope` (in the `raser_bench` package) is a benchmark class inheriting from the `raser` experiment base class (see [Architecture Overview](../architecture.md#experiments-are-python-classes)) that uses a beam telescope to measure the spatial resolution of a position-sensitive device under test (DUT) in the $x$ and $y$ directions. The telescope consists of a sequence of detector planes arranged along the beam axis, specified by a device list: every listed device is placed as a real device built from its device file—several upstream reference layers, the DUT in the middle, and several downstream reference layers. The reference layers default to `TAICHU3` (Taichu3 CMOS pixel detector), and by default two DUTs are placed in the middle; the device specified on the command line replaces both middle DUTs. The total number of layers in the telescope is arbitrary, the device in any layer can be replaced by another device, and each layer's board can be oriented in any of four directions in the $x$-$y$ plane.

`telescope` reads [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence: [`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md). All detector planes share a single [`deposit`](../stages/deposit.md) run simulating a high-energy particle beam traversing all layers sequentially. Each layer individually runs `field`, `current`, `readout`, `digitizer`, `trigger`, and `reconstruction`, where `reconstruction` clusters hits on each layer to determine hit positions and fits a straight track to the reference-layer hits to extrapolate to the DUT plane; `analysis` fits the residual widths to obtain the DUT spatial resolution in the $x$ and $y$ directions.

## Setup and Standard Practice

### Standard Practice and Physical Model

When measuring the spatial resolution of a position-sensitive detector in a beam test, the DUT is placed in the middle of a beam telescope composed of upstream and downstream high-precision pixel reference detectors (such as `TAICHU3`, MIMOSA26, or ALPIDE). After a high-energy particle beam traverses all detector planes, each layer performs connected-component clustering on hit pixels above threshold to compute the hit centroid; a straight track is fitted to the hit positions on the reference layers and extrapolated to the DUT plane, and the residuals between the measured DUT hit positions and the extrapolated positions are collected. The Gaussian standard deviation of the residual distribution reflects the spatial resolution of the DUT.

The telescope comprises $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers, defaulting to 3 + 2 + 3 (3 `TAICHU3` layers upstream and 3 downstream, with 2 DUTs in the middle). The total number of reference layers is $N_{\text{ref}} = N_{\text{front}} + N_{\text{back}}$ (with reference-layer index set $\mathcal{R}$), and the total number of telescope layers is $N = N_{\text{front}} + N_{\text{DUT}} + N_{\text{back}}$. In each layer's local coordinate system, [`reconstruction`](../stages/reconstruction.md) clusters hit pixels above threshold using pixel geometric center coordinates, an eight-neighbor connectivity criterion, and the arithmetic-mean centroid:

$$(x_{p}, y_{p}) = \bigl((i_x + 0.5)\,p_x,\; (i_y + 0.5)\,p_y\bigr), \qquad \Delta x^{2} + \Delta y^{2} \le p_x^{2} + p_y^{2} + \epsilon, \qquad (\bar{x}_{c}, \bar{y}_{c}) = \frac{1}{n_c}\sum_{m=1}^{n_c}(x_{p,m}, y_{p,m}) \tag{1}$$

Each layer's local cluster centroid is transformed into the global telescope $(x, y)$ coordinate system according to that layer board's orientation in the $x$-$y$ plane; the hit positions on reference layer $j$ ($j \in \mathcal{R}$) and DUT $d$ ($d = 1, \dots, N_{\text{DUT}}$) are denoted $(\bar{x}_{c,j}, \bar{y}_{c,j})$ and $(\bar{x}_{c,d}, \bar{y}_{c,d})$. [`reconstruction`](../stages/reconstruction.md) selects events in which both the reference layers and the DUT produce a single cluster, and performs ordinary least-squares straight-line fits in $x$-$z$ and $y$-$z$ using the plane coordinates $z_j$ and hit positions $(\bar{x}_{c,j}, \bar{y}_{c,j})$ of all $N_{\text{ref}}$ reference layers:

$$\hat{x}(z) = k_x z + b_x, \qquad \hat{y}(z) = k_y z + b_y \tag{2}$$

Extrapolating the reference track to the mid-plane $z_d + l_{z,d}/2$ of DUT $d$ yields the residuals $(r_{x,d}, r_{y,d})$ of the DUT hit position relative to the extrapolated position, and the fit residuals on the $N_{\text{ref}}$ reference layers give the reference track $\chi^2$:

$$r_{x,d} = k_x\!\left(z_d + \frac{l_{z,d}}{2}\right) + b_x - \bar{x}_{c,d}, \qquad r_{y,d} = k_y\!\left(z_d + \frac{l_{z,d}}{2}\right) + b_y - \bar{y}_{c,d}, \qquad \chi^{2} = \sum_{j \in \mathcal{R}}\left(\frac{r_{x,j}^{2}}{p_{x,j}^{2}/12} + \frac{r_{y,j}^{2}}{p_{y,j}^{2}/12}\right) \tag{3}$$

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
| $z_j, z_d$ | Detector-plane position coordinate along the beam axis for reference layer $j$ and DUT $d$ | $\mu\text{m}$ |
| $l_{z,j}, l_{z,d}$ | Sensitive-layer thickness of reference layer $j$ and DUT $d$ | $\mu\text{m}$ |
| $k_x, k_y$ | Slopes of the fitted straight track from reference layers in the $x$-$z$ and $y$-$z$ planes | dimensionless |
| $b_x, b_y$ | Intercepts of the fitted straight track from reference layers in the $x$-$z$ and $y$-$z$ planes | $\mu\text{m}$ |
| $\hat{x}(z), \hat{y}(z)$ | Global transverse coordinates of the straight track extrapolated to beam-axis position $z$ ($\mu\text{m}$) | $\mu\text{m}$ |
| $r_{x,d}, r_{y,d}$ | $x$ and $y$ residuals between the extrapolated position and measured centroid at the mid-plane $z_d + l_{z,d}/2$ of DUT $d$ | $\mu\text{m}$ |
| $r_{x,j}, r_{y,j}$ | Track-fit $x$ and $y$ residuals on reference layer $j$ ($j \in \mathcal{R}$) | $\mu\text{m}$ |
| $\chi^2$ | Reference-track fit chi-square normalized by the uniform pixel variances $p_{x,j}^2/12$ and $p_{y,j}^2/12$ of each reference layer | dimensionless |
| $\sigma_{\text{Tol},d}$ | Total Gaussian-fitted standard deviation of the $x$ or $y$ residual distribution of DUT $d$ | $\mu\text{m}$ |

Standard beam-telescope track fitting and spatial-resolution extraction are described in Ref. [1] (H. Jansen et al., “Performance of the EUDET-type beam telescopes”, *EPJ Tech. Instrum.* 3 (2016) 7, doi:10.1140/epjti/s40485-016-0033-2), and beam tests of the TaichuPix CMOS pixel sensor are reported in Ref. [2] (T. Wu et al., “Beam test of a 180 nm CMOS pixel sensor for the CEPC vertex detector”, *Nucl. Instrum. Methods Phys. Res. A* 1059 (2024) 168945, doi:10.1016/j.nima.2023.168945).

### Telescope Setup Geometry

The telescope consists of $N$ detector planes arranged sequentially along $+z$: $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers, defaulting to 3 + 2 + 3. The entire telescope is fully configuration-driven: the device list, number of layers, device per layer, and board orientations are all specified in configuration. The telescope is defined by a device list—every listed device is constructed as a physical volume in the Geant4 setup from its corresponding device file. The device given on the command line replaces both middle DUTs; besides the DUTs, any upstream or downstream reference layer may also be replaced by another device, and the layer count of each section can be freely adjusted via the device list.

Reference layers default to `TAICHU3` (`TAICHU3.json`): a silicon (`"Si"`) pixel detector with full dimensions $l_x = 1500\ \mu\text{m}$, $l_y = 1500\ \mu\text{m}$, $l_z = 20\ \mu\text{m}$, an array of $60 \times 60$ pixels (`3600` total), pixel pitch $p_x = p_y = 25.0\ \mu\text{m}$, a centered rectangular collection zone of $10.0 \times 10.0\ \mu\text{m}$ per pixel, operating temperature $300.0\ \text{K}$, default bias `-1.8` $\text{V}$, acceptor concentration `1e12` $\text{cm}^{-3}$, and donor concentration `0` $\text{cm}^{-3}$.

Each layer's detector board is mounted perpendicular to the beam axis $z$ and may be oriented in one of four directions in the $x$-$y$ plane (rotated by $0^\circ$, $90^\circ$, $180^\circ$, or $270^\circ$ around the $z$ axis). Following standard beam-telescope practice, this degree of freedom serves two needs:

- **Measuring spatial resolution in both $x$ and $y$**: strip detectors or non-square pixel detectors ($p_x \ne p_y$) have high position resolution only along a single sensitive coordinate or short pitch axis. Rotating a board by $90^\circ$ (for example, mounting the two DUTs orthogonally at $0^\circ$ and $90^\circ$, or rotating selected reference layers by $90^\circ$) allows measuring spatial resolution in both $x$ and $y$ within the same telescope coordinate frame, or providing high-precision track constraints along both orthogonal coordinates simultaneously.
- **Matching mechanical mounting and cable routing in beam tests**: constrained by support frames, cooling manifolds, and readout PCB routing in the beam area, adjacent detector boards are frequently installed rotated by $90^\circ$, $180^\circ$, or $270^\circ$ to stagger readout chips and cables. Specifying each layer's board orientation ensures that its local pixel coordinates transform accurately into the unified global telescope $(x, y)$ frame.

### Execution Steps

`telescope` executes the eight-stage chain in order:

1. **Solve or reuse shared fields per layer ([`field`](../stages/field.md))**: locates the electric field, weighting field, and equivalent circuit parameters for each device in the device list at its target bias `voltage` ($\text{V}$) and irradiation fluence `irradiation` ($\text{neq/cm}^2$), automatically computing them if not yet ready. Each device's shared field is stored under `field/` in that device's project directory.
2. **Full-telescope energy deposition ([`deposit`](../stages/deposit.md))**: builds the $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers in the Geant4 telescope setup according to the device list and layer orientations. The high-energy particle beam traverses all $N$ planes along $+z$, recording energy deposition steps across all layers together and converting them into initial electron-hole pairs tagged by layer.
3. **Per-layer drift, readout, digitization, and triggering ([`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md))**: each layer independently drifts carriers in its solved field, computes induced currents and net charge on its pixel electrodes, and solves analog voltage waveforms with circuit thermal noise through its device equivalent circuit and front-end amplifier chain. Each layer then produces digital waveforms according to the digitizer sampling rate and bit depth and retains recorded events via trigger selection.
4. **Clustering and track fitting ([`reconstruction`](../stages/reconstruction.md))**: on each layer, extracts pixel signal features for recorded events and performs connected-component clustering on hit pixels above threshold via Eq. (1) to obtain the local hit position $(\bar{x}_c, \bar{y}_c)$ ($\mu\text{m}$) and cluster size $n_c$ (count); transforms hit positions into the global telescope frame according to each layer's orientation, fits a straight track to all $N_{\text{ref}}$ reference layers via Eq. (2), and extrapolates it to each DUT plane.
5. **Spatial resolution extraction ([`analysis`](../stages/analysis.md))**: accumulates the $x$ and $y$ residual distributions of the DUTs via Eq. (3) and fits Gaussian widths to obtain the residual standard deviations $\sigma_{\text{Tol}}$ ($\mu\text{m}$) in $x$ and $y$.

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, and equivalent circuit parameters at the target bias and irradiation fluence separately for each layer's device, stored under `field/` in the corresponding device project.
- [`deposit`](../stages/deposit.md): uses Geant4 in the beam-telescope setup to simulate a high-energy particle beam traversing the $N_{\text{front}}$ upstream reference layers, $N_{\text{DUT}}$ central DUTs, and $N_{\text{back}}$ downstream reference layers, recording deposition steps for all layers together and converting them into initial electron-hole pairs.
- [`current`](../stages/current.md): simulates carrier drift, diffusion, and collection in each layer's solved field to compute the induced current and net induced charge on each electrode of that layer.
- [`readout`](../stages/readout.md): feeds each layer's electrode induced currents into its corresponding device equivalent circuit and front-end amplifier chain to solve output analog voltage waveforms with circuit thermal noise.
- [`digitizer`](../stages/digitizer.md): converts each layer's analog output waveforms into digital waveforms according to the digitizer sampling rate and quantization bit depth.
- [`trigger`](../stages/trigger.md): applies trigger conditions to each layer's digital waveforms to select events to record.
- [`reconstruction`](../stages/reconstruction.md): clusters hit pixels above threshold on each layer via Eq. (1) to obtain hit positions, then fits a straight track to reference-layer hits via Eq. (2) and extrapolates to the DUT planes.
- [`analysis`](../stages/analysis.md): computes the $x$ and $y$ residual distributions of the DUTs via Eq. (3), fits their widths, and outputs single-point and cross-scan-point summaries.

### Components

- [Detector components (`components/device`)](../components/device.md): provides definitions of the telescope reference-layer pixel detector (default `TAICHU3`, dimensions $1500 \times 1500 \times 20\ \mu\text{m}$, pitch $25.0 \times 25.0\ \mu\text{m}$) and the DUT placed in the middle; any layer in the list can use any device from the component library or a user project.
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides high-energy particle beam components and the beam-telescope Geant4 setup arranging multi-layer detector planes according to the device list.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides the front-end amplifier and termination load SPICE subcircuit chains used by each detector layer.
- [Digitizer components (`components/digitizer`)](../components/digitizer.md): provides sampling rate and quantization bit-depth settings for each layer's readout waveforms.
- [Trigger components (`components/trigger`)](../components/trigger.md): provides trigger condition definitions for recording telescope events.

## Usage and Configuration

Pass the name of the DUT placed in the middle of the telescope on the command line to run the spatial resolution test (see [Command-Line Interface](../cli.md#commands)), or use `--set` and `--scan` to modify or scan settings such as bias voltage ($\text{V}$) and threshold ($\text{mV}$):

```bash
raser telescope <device>
raser telescope <device> --scan field.voltage=-100,-200
```

The experiment directory `<project>/telescope/config.json` records settings sectioned by stage (see [Architecture Overview](../architecture.md#project) for the format). The telescope device list is defined in the `telescope` experiment class, with 3 `TAICHU3` layers upstream and 3 downstream by default and two DUTs in the middle; the device given on the command line replaces the DUTs. The device list, per-layer orientations, and per-layer settings such as bias voltage are configured individually.

The table below lists the stage configuration keys shared between `telescope` and other benchmark pages; the `deposit` section is shared across all layers, while all other sections are configured per layer in the multi-layer telescope:

| Section.Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `bias.voltage` from the corresponding device file | $\text{V}$ | Bias voltage of that layer's device |
| `field.irradiation` | `None` (uses device `irradiation.irradiation_flux` if omitted, or `0` if absent) | $\text{neq/cm}^2$ | Irradiation fluence of that layer's device |
| `deposit.source` | Default beam component | None | Incident particle beam component name or path |
| `deposit.g4setup` | Default telescope setup component | None | Geant4 beam-telescope setup component name or path |
| `deposit.events_per_job` | `1000` | events | Number of valid deposited events to record per job (mutually exclusive with `deposit.generated_per_job`) |
| `deposit.generated_per_job` | `None` | events | Total number of events generated from the beam source per job (mutually exclusive with `deposit.events_per_job`) |
| `deposit.generated_limit` | `None` (`10000000` at runtime) | events | Maximum number of generated source events allowed to reach `events_per_job` |
| `deposit.edep_min` | `None` | $\text{MeV}$ | Lower bound on deposited energy for recorded events |
| `deposit.edep_max` | `None` | $\text{MeV}$ | Upper bound on deposited energy for recorded events |
| `deposit.fano` | `True` | None | Whether to enable Fano fluctuation sampling when converting deposited energy to ionized pairs |
| `deposit.plots` | `100` | events | Number of leading recorded events per job for which Geant4 geometry and track plots are drawn |
| `current.plots` | `100` | events | Number of leading recorded events per job for which carrier drift path and current plots are drawn |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `readout.sheet_resistance` | `None` | $\Omega$ | Overrides the resistive-layer sheet resistance for devices containing `resistive_layer` |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | Pixel signal threshold-crossing level and threshold for adding neighboring pixels to a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | Pulse amplitude threshold for event selection and cluster-seed identification |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` | `None` (inherits `pulse_edge` written by the corresponding layer's `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` |

## Outputs

Test results are stored under `<project>/telescope/` in the DUT's project directory (such as `work/<dut>/telescope/`); see [Architecture Overview](../architecture.md#results) for the storage layout. Each stage writes by input fingerprint to underlying nodes `<project>/telescope/nodes/<stage>/<node>/` (containing that stage's output files and `node.json`), the upper layer generates per-scan-point symlink views at `<project>/telescope/points/<point>/<stage>` pointing to the corresponding nodes and records the parameter table in `<project>/telescope/points.json`; per-point statistical summaries and cross-point trend plots are stored under `<project>/telescope/analysis/`, while plots produced by each stage are placed in that stage's node outputs.

Shared fields for each telescope layer's device are stored under `field/` in that device's own project directory (such as `work/<dut>/field/` and `work/TAICHU3/field/`).

The main outputs written by each stage and by statistical analysis are:

- **Upstream stage nodes ([`deposit`](../stages/deposit.md) through [`reconstruction`](../stages/reconstruction.md))**: the `deposit` node records energy deposition steps and ionized pairs across all $N$ planes (coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, ionized pairs in pairs). Each layer's `current`, `readout`, `digitizer`, `trigger`, and `reconstruction` nodes respectively store that layer's electrode induced currents and net collected charge (time $\text{s}$, current $\text{A}$, charge $\text{C}$), front-end readout analog voltage waveforms (time $\text{s}$, voltage $\text{V}$), digitized waveforms (voltage $\text{V}$), triggered events, and per-event clustered hit positions ($\mu\text{m}$) and cluster sizes (count).
- **Spatial resolution statistics and plots ([`analysis`](../stages/analysis.md))**: reports the $x$ and $y$ residual distributions (horizontal axis residual $\mu\text{m}$, vertical axis events) and Gaussian fit results for each DUT, giving the residual standard deviations $\sigma_{\text{Tol}}$ ($\mu\text{m}$); for multi-point scans, outputs per-point spatial resolution summaries and trend plots under `<project>/telescope/analysis/`.

![Electrons collected per pixel on one TAICHU3 layer](../images/telescope-pixel-charge.png)

Number of electrons collected by each pixel on one `TAICHU3` layer in a single event ($60 \times 60$ pixel array; horizontal axis `X` is pixel column index, depth axis `Y` is pixel row index, vertical axis is collected electron count, unit: count).
