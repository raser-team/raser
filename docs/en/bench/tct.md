# Transient Current Technique Test (`bench/tct`)

`tct` (Transient Current Technique, in the `raser_bench` package) is centered on the device under test specified on the command line and uses the focal position of a fixed laser relative to the device as the scan axis. It reads device, laser, and electronics configurations from [detector components (`components/device`)](../components/device.md), the laser definitions in [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), moves the laser position relative to the device point by point, executes the same eight stages as [`signal`](signal.md) at each position, and outputs the initial carrier distribution, induced-current waveforms, readout voltage waveforms, digital waveforms, reconstructed features, and curves of collected charge and signal versus position at each focal position.

## Setup and Standard Practice

### Standard Practice and Physical Model

In Transient Current Technique (TCT) measurements, a focused picosecond or femtosecond pulsed laser illuminates a semiconductor detector from the top face (Top-TCT), bottom face (Bottom-TCT), or polished edge (Edge-TCT). A three-axis precision translation stage shifts the laser focus coordinates relative to the device point by point, recording the transient induced-current waveforms and integrated charge produced as electron-hole pairs excited at each spatial position drift in the electric field, thereby measuring the internal electric field profile, depletion thickness, carrier drift velocity, and spatial variation of charge collection.

In RASER, the absolute coordinates $(x_{\text{focus}}, y_{\text{focus}}, z_{\text{focus}})$ of the laser focus in the device coordinate system $[0, l_x] \times [0, l_y] \times [0, l_z]$ (in $\mu\text{m}$) and the Gaussian beam radius $w(s)$ along the beam-path coordinate $s$ (in $\mu\text{m}$) are:

$$(x_{\text{focus}},\, y_{\text{focus}},\, z_{\text{focus}}) = \bigl(\text{fx\_rel}\cdot l_x,\; \text{fy\_rel}\cdot l_y,\; \text{fz\_rel}\cdot l_z\bigr) \tag{1}$$

$$w_0 = \frac{\text{FWHM}_{\text{sp}}}{\sqrt{2\ln 2}}, \qquad l_R = \frac{\pi w_0^2 n}{\lambda}, \qquad w^2(s) = w_0^2\!\left[1 + \left(\frac{s - s_{\text{focus}}}{l_R}\right)^2\right] \tag{2}$$

The electron-hole pair line densities (per meter) integrated over the beam cross section at path position $s$ for single-photon absorption (`"SPA"`) and two-photon absorption (`"TPA"`) are respectively:

$$\left(\frac{dN}{ds_{\text{m}}}\right)_{\text{SPA}} = \alpha\,\frac{E_{\text{pulse}}}{E_{\text{ph}}}\,\exp\!\left(-\alpha\,s \times 10^{-6}\right), \qquad E_{\text{ph}} = \frac{h c}{\lambda \times 10^{-6}} \tag{3}$$

$$\left(\frac{dN}{ds_{\text{m}}}\right)_{\text{TPA}} = \frac{\beta_2\,E_{\text{pulse}}^2\,\exp\!\left(-2\alpha\,s \times 10^{-6}\right)}{2\,E_{\text{ph}}\,\pi\,w^2(s)\times 10^{-12}}\sqrt{\frac{2\ln 2}{\pi}}\,\frac{1}{\text{FWHM}_t} \tag{4}$$

Convolving the instantaneous-injection drift induced current $I_{e,a}$ (in $\text{A}$) in time bin $a$ on electrode $e$ discretely with the normalized Gaussian laser temporal pulse $P(t)$ gives the output current waveform $I^{\text{conv}}_{e,b}$:

$$P(t) = \frac{2\sqrt{\ln 2}}{\sqrt{\pi}\,\text{FWHM}_t}\exp\!\left(-\frac{4\ln 2\,t^2}{\text{FWHM}_t^2}\right), \qquad I^{\text{conv}}_{e, b} = \sum_{a=0}^{n_{\text{bin}}-1} I_{e, a}\,p_{a - b} \tag{5}$$

where:

- $l_x, l_y, l_z$: full dimensions of the device under test along the $x$, $y$, and $z$ directions, $\mu\text{m}$;
- $\text{fx\_rel}, \text{fy\_rel}, \text{fz\_rel}$: dimensionless normalized coordinates of the focus relative to the device dimensions;
- $\text{FWHM}_{\text{sp}}$: spatial full width at half maximum `spacial_FWHM` of the Gaussian spot at focus, $\mu\text{m}$;
- $w_0$, $w(s)$: beam waist radius at focus and beam radius at path coordinate $s$, $\mu\text{m}$;
- $n$: refractive index `refractionIndex` of the device material at the laser wavelength (dimensionless);
- $\lambda$: laser wavelength, $\mu\text{m}$ (obtained by multiplying `wavelength` [$\text{nm}$] from the component file by $10^{-3}$);
- $l_R$: Rayleigh length `l_Rayleigh` inside the medium, $\mu\text{m}$ (computed from Eq. (2) when not explicitly given in the component file);
- $s_{\text{focus}}$: distance from the entrance surface to the focus along the beam propagation direction, $\mu\text{m}$;
- $\alpha$: linear (single-photon) absorption coefficient `alpha`, $\text{m}^{-1}$ (when omitted from the component file: for silicon, obtained by log interpolation of `raser/components/deposit/absorption/Si.txt` multiplied by $100$; for silicon carbide, calculated from the 4H-SiC indirect absorption model at the device temperature, see [`core/deposit`](../core/deposit.md) Eqs. (7a) and (7b));
- $\beta_2$: two-photon absorption coefficient `beta_2`, $\text{m/W}$;
- $E_{\text{pulse}}$: single laser pulse energy `pulse_energy`, $\text{J}$; $E_{\text{ph}}$ is the single-photon energy, $\text{J}$ ($h = 6.626\times 10^{-34}\ \text{J}\cdot\text{s}$, $c = 2.998\times 10^{8}\ \text{m/s}$);
- $\text{FWHM}_t$: laser temporal pulse full width at half maximum `temporal_FWHM`, $\text{s}$;
- $(dN/ds_{\text{m}})_{\text{SPA}}$, $(dN/ds_{\text{m}})_{\text{TPA}}$: electron-hole pairs generated per meter at path coordinate $s$ by single-photon and two-photon absorption, $\text{m}^{-1}$;
- $P(t)$: laser temporal pulse envelope `timePulse(t)`, $\text{s}^{-1}$; $p_k$ is the dimensionless pulse weight integrated over integer time-bin offset $k$ by `pulse_in_bins`;
- $I_{e,a}$, $I^{\text{conv}}_{e,b}$: bin-averaged induced current on electrode $e$ in time bins $a$ and $b$ before and after convolution, $\text{A}$; $n_{\text{bin}}$ is the total number of time bins in the window (dimensionless).

Eqs. (1)–(4) are implemented by `LaserInjection` and `absorption_coefficient` in [`core/deposit/laser.py`](../core/deposit.md); Eq. (5) is implemented by `pulse_in_bins`, `CalCurrentLaser`, and `write_laser_currents` in [`core/current/cal_current.py`](../core/current.md). Standard TCT and Edge-TCT methods for measuring internal electric fields and charge collection in semiconductor detectors are described in Ref. [1] (V. Eremin, N. Strokan, E. Verbitskaya, Z. Li, “Development of transient current and charge techniques for the measurement of effective net concentration of ionized charges (Neff) in the space charge region of p-n junction detectors”, *Nucl. Instrum. Methods Phys. Res. A* 372 (1996) 388, doi:10.1016/0168-9002(95)01295-8) and Ref. [2] (G. Kramberger et al., “Investigation of Irradiated Silicon Detectors by Edge-TCT”, *IEEE Trans. Nucl. Sci.* 57 (2010) 2294, doi:10.1109/TNS.2010.2051957).

### Incidence Directions and Beam-Path Geometry

`LaserInjection._beam_frame` supports three laser incidence directions without launching Geant4, constructing the optical path directly in the device coordinate system $[0, l_x] \times [0, l_y] \times [0, l_z]$ (in $\mu\text{m}$):

- **Top incidence (`"direction": "top"`)**: the beam enters from the top face $z = 0$ along $+z$, with total path length inside the device $L = l_z$ ($\mu\text{m}$), focus distance from the entrance surface $s_{\text{focus}} = z_{\text{focus}}$, and beam cross section centered at $(x_{\text{focus}}, y_{\text{focus}})$; typically scans lateral positions `fx_rel`, `fy_rel` and focus depth `fz_rel`.
- **Bottom incidence (`"direction": "bottom"`)**: the beam enters from the bottom face $z = l_z$ along $-z$, with total path length inside the device $L = l_z$ ($\mu\text{m}$), focus distance from the entrance surface $s_{\text{focus}} = l_z - z_{\text{focus}}$, beam cross section centered at $(x_{\text{focus}}, y_{\text{focus}})$, and path distance $s$ corresponding to device coordinate $z = l_z - s$.
- **Edge incidence (`"direction": "edge"`)**: the beam enters from the side face $x = 0$ along $+x$, with total path length inside the device $L = l_x$ ($\mu\text{m}$), focus distance from the entrance surface $s_{\text{focus}} = x_{\text{focus}}$, and beam cross section centered at $(y_{\text{focus}}, z_{\text{focus}})$; primarily scans beam depth `fz_rel` (or focal depth `fx_rel` along the beam direction).

Limitations: `write_laser_currents` calls `CalCurrentLaser` with `diffusion=False` hardcoded, turning off carrier thermal diffusion; under `"TPA"` mode, although the temporal width of two-photon-generated carrier clusters is $\text{FWHM}_t / \sqrt{2}$, `CalCurrentLaser` still convolves the total current uniformly with `timePulse` of single-photon width `temporal_FWHM`; plasma screening of the local electric field by high-density photogenerated carriers is not included.

### Execution Steps and Built-in Constants

A job for a single `tct` scan point executes all eight stages in the following order:

1. **Check and solve shared field (`field`)**: before jobs start, the main command checks whether `<project>/field/` contains a field node matching the current device, bias `voltage` ($\text{V}$), and irradiation fluence `irradiation_flux` ($\text{cm}^{-2}$, $1\ \text{MeV}$ neutron-equivalent fluence); if not ready, it computes the field before jobs start and stores it in `<project>/field/<node>/` (carrying a `.part` suffix while writing, and containing `node.json`).
2. **Generate laser carrier groups (`deposit`)**: the `deposit` stage constructs `Detector` from the device file and `LaserInjection` from the laser component. For each active absorption mechanism (single-photon when $\alpha \ne 0$, plus two-photon when `tech == "TPA"`), it evaluates the total pair count $N_{\text{tot}}$ by trapezoidal integration over $\lceil 50 L / \min(L, l_R, 10^6/\alpha) \rceil + 1$ sample points along the full optical path $L$. The beam cross section is partitioned into `4` equal-fraction concentric rings (normalized radii $\rho_r = \sqrt{-\ln(1 - (r + 0.5)/4)/k}$, $r = 0, 1, 2, 3$, with $k = 2$ for single-photon and $k = 4$ for two-photon) and `8` equal-angle sectors ($\phi_m = (m + 0.5)\pi/4$, $m = 0, \dots, 7$), yielding `32` cells per slab, and sliced along the beam path into $N_{\text{slab}} = \lceil \max(N_{\text{tot}} / \text{pairs\_per\_group},\, \text{groups}) / 32 \rceil$ equal-fraction slabs. At the center of each cell lying within the lateral device boundaries, a carrier group carrying $N_{\text{tot}} / (32 N_{\text{slab}})$ electron-hole pairs is placed at time `central_time` ($\text{s}$), written to `deposit.h5` in the `deposit` node via `laser_deposits`, and initial carrier distribution plots are drawn inside the node by `draw_nocarrier3D` and `draw_nocarrier2D`.
3. **Diffusionless drift, pulse convolution, and plotting (`current`)**: the `current` stage reads `deposit.h5` from the `deposit` node and loads the shared field `DevsimField`, performs drift, avalanche multiplication, and Shockley–Ramo induced-current binning for all carrier groups inside `CalCurrentLaser` (`diffusion=False`), then computes the pulse weight matrix of Eq. (5) with $S = \max(1, \lceil 20\,\Delta t_{\text{bin}} / \text{FWHM}_t \rceil)$ samples per bin, right-multiplies the current waveforms, writes `current.h5` in the `current` node, and plots the nonzero-electrode induced-current waveforms inside the node.
4. **Front-end circuit readout (`readout`)**: the `readout` stage reads `current.h5` from the `current` node, assembles the device equivalent circuit and `amplifier` subcircuit chain, runs `ngspice` to solve the output voltage waveforms, adds frequency-domain thermal noise using the `readout` noise seed derived from the job seed, and writes `readout.h5` in the `readout` node.
5. **Digitization and triggering (`digitizer`, `trigger`)**: `digitizer` converts analog waveforms into quantized codes according to the analog bandwidth, sampling, and quantization settings of the digitizer component (default `MXR608A`, with clock phase and aperture jitter drawn from the `digitizer` seed derived from the job seed) and writes them to `digitizer.h5` in the `digitizer` node; `trigger` decides which events to record according to the trigger conditions and writes the `event` (`int64`) dataset of recorded event IDs to `trigger.h5` in the `trigger` node.
6. **Waveform feature extraction (`reconstruction`)**: the `reconstruction` stage reads the events in `digitizer.h5` recorded by `trigger.h5`, converts quantized codes back to voltage ($\text{V}$) using `lsb_V` and `offset_V` with sampling times `t0 + k·sampling_period`, subtracts the baseline, flips pulse polarity, extracts amplitude, timing quantities, area, and cluster features, marks events with a found seed as `selected`, and writes `reconstruction.h5` in the `reconstruction` node.
7. **Per-point and position-scan aggregation (`analysis`)**: the `analysis` stage aggregates the results of each focal scan point, writes per-point `result.json`, `events.h5`, and distribution plots to each scan point's `analysis` node (`nodes/analysis/<node>/`, view `points/<point>/analysis/`), and writes the cross-position summary table `points.json` and trend plots `points.png` of collected charge and signal versus focal position under `<project>/tct/analysis/`.

The built-in constants in `tct` are listed below:

| Constant or Fixed Item | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| Photon energy constants $h$, $c$ | `6.626e-34`, `2.998e8` | $\text{J}\cdot\text{s}$, $\text{m/s}$ | `src/raser/core/deposit/laser.py`, Planck constant and speed of light used to compute single-photon energy $E_{\text{ph}} = h c / \lambda$ |
| Optical-path integration subdivision factor | `50` | steps | `src/raser/core/deposit/laser.py`, integration sampling multiplier applied to the optical path length divided by the smallest characteristic scale $\min(L, l_R, 10^6/\alpha)$ |
| `rings`, `sectors` | `4`, `8` | rings, sectors | `src/raser/core/deposit/laser.py`, numbers of equal-fraction concentric rings and angular sectors partitioning the laser cross section (`32` groups per slab) |
| Carrier distribution histogram bins | `50 × 50 × 50` (3D) | bins | `src/raser/core/deposit/laser.py`, bins on which `draw_nocarrier3D` evaluates the volume density |
| Carrier density map grid and transverse range | `200 × 200`, `2` times the maximum spot radius on each side of the optical axis | points, dimensionless | `src/raser/core/deposit/laser.py`, grid point counts and transverse plotting range for volume density calculation in `draw_nocarrier2D` |
| Per-bin pulse convolution sampling multiplier | `20` | points | `src/raser/core/current/cal_current.py`, `pulse_in_bins` requires midpoint-rule spacing inside each bin not to exceed $\text{FWHM}_t / 20$ |
| `t_bin`, `delta_t` | 1D: `5e-12`, `2e-12`; 2D/3D: `50e-12`, `20e-12` | $\text{s}$ | `src/raser/core/current/cal_current.py`, induced-current time-bin width and single drift step |
| `diffusion` | `False` | None | `src/raser/core/current/cal_current.py`, `write_laser_currents` hardcodes carrier thermal diffusion off |

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, and device equivalent circuit parameters of the device under test at the target bias and irradiation fluence under `<project>/field/<node>/`.
- [`deposit`](../stages/deposit.md): reads the laser component, generates laser-injected electron-hole pair carrier groups at each focal position via Eqs. (1)–(4), writes `deposit.h5`, and draws initial carrier distribution plots.
- [`current`](../stages/current.md): reads the laser carrier groups in `deposit.h5`, drifts them in the solved field without diffusion, convolves them with the Gaussian laser temporal envelope via Eq. (5), and writes `current.h5` and current waveform plots.
- [`readout`](../stages/readout.md): feeds the convolved induced current into the device equivalent circuit and front-end amplifier chain, solves output voltage waveforms with `ngspice` and adds circuit thermal noise, and writes `readout.h5`.
- [`digitizer`](../stages/digitizer.md): converts analog waveforms into quantized-code digital waveforms according to the analog bandwidth, sampling rate, and quantization bit depth of the digitizer component (default `MXR608A`), and writes `digitizer.h5`.
- [`trigger`](../stages/trigger.md): selects recorded events according to the trigger conditions and writes the `event` (`int64`) dataset of event IDs to `trigger.h5`.
- [`reconstruction`](../stages/reconstruction.md): reads the events in `digitizer.h5` recorded by `trigger`, converts quantized codes back to voltage ($\text{V}$) using `lsb_V` and `offset_V`, extracts pulse amplitude, timing quantities, area, and cluster features, marks events with a found seed as `selected`, and writes `reconstruction.h5`.
- [`analysis`](../stages/analysis.md): aggregates the results of each focal scan point into its own `analysis` node, and writes the cross-position summary table and trend plots of collected charge and signal versus focal position under `<project>/tct/analysis/`.

### Components

- [Detector components (`components/device`)](../components/device.md): provides dimensions `l_x`, `l_y`, `l_z` ($\mu\text{m}$), material `material`, doping, bias voltage, temperature, irradiation, and avalanche parameters of the device under test (such as `HPK-Si-PiN.json`, `NJU-PiN.json`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides laser component JSONs (such as default top infrared silicon laser `LA01IR_top_Si.json`, edge `LA01IR_edge_Si.json`, red `LA01R_top_Si.json` / `LA01R_bottom_Si.json`, SiC UV laser `PIL037_top_SiC.json` / `PIL037_edge_SiC.json`, silicon two-photon laser `TPA1550_top_Si.json` / `TPA1550_edge_Si.json`) and the intrinsic silicon band-to-band absorption table `raser/components/deposit/absorption/Si.txt`.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides SPICE amplifier stages and termination load subcircuits cascaded with `+` (default `SantaCruz+Gali52+Termination50`).
- [Digitizer components (`components/digitizer`)](../components/digitizer.md): provides sampling and quantization settings of an oscilloscope or digitizer board (default `MXR608A`).
- [Trigger components (`components/trigger`)](../components/trigger.md): provides trigger selection condition definitions for standalone trigger devices.

## Usage and Configuration

`tct` and [`signal`](signal.md) are separated by scan axis: when scanning the laser position relative to the device (`fx_rel`, `fy_rel`, `fz_rel`), use `tct`; when scanning properties of the laser itself (pulse energy `pulse_energy`, wavelength `wavelength`) or device settings (bias `voltage`, irradiation fluence `irradiation_flux`), use [`signal`](signal.md).

Run `tct` on the device under test with the position scan axis written in the `deposit` section of `config.json` or given on the command line via `--scan` (for example, scanning the focal depth fraction `fz_rel` relative to device thickness):

```bash
raser tct <device>
raser tct NJU-PiN --set deposit.laser=PIL037_top_SiC --scan deposit.laser.fz_rel=0.1,0.3,0.5,0.7,0.9
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the configuration structure of the experiment directory `<project>/tct/config.json` is shown below. Only the sections relevant to this page are excerpted below; `examples/NJU-PiN/tct/config.json` writes out all eight sections in full.

```json
{
  "workflow": "tct",
  "device": "NJU-PiN",
  "field": {
    "voltage": -500.0
  },
  "deposit": {
    "laser": {
      "name": "PIL037_top_SiC",
      "fx_rel": 0.5,
      "fy_rel": 0.5,
      "fz_rel": [0.1, 0.3, 0.5, 0.7, 0.9]
    }
  },
  "readout": {
    "amplifier": "SantaCruz+Gali52+Termination50"
  }
}
```

When `laser` in the `deposit` section is written as an object containing `name`, `name` selects the laser component and the remaining keys override the identically named keys in that component file, corresponding one-to-one with `deposit.laser.fz_rel` on the command line; when only selecting a component without modifying keys, write it as a string `"laser": "PIL037_top_SiC"`.

The configuration keys users can set in `tct` are listed below (see [Energy Deposition Components (`components/deposit`)](../components/deposit.md#laser-and-absorption-coefficient-table) for laser component key definitions, and [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md) for settings of the remaining stages in their respective sections). "Example Value" shows the value written in `examples/NJU-PiN/tct/config.json`; if `config.json` is missing a required key, an error is raised naming the missing "section.key":

| Section.Key | Example Value | Unit | Meaning |
| --- | --- | --- | --- |
| `deposit.laser` | `{"name": "PIL037_top_SiC", …}` | None | Laser component name or path; when written as an object containing `name`, the remaining keys override the identically named keys in the component file |
| `deposit.laser.fx_rel` | `0.5` | dimensionless | Relative coordinate of the laser focus along device $x$; absolute position $x_{\text{focus}} = \text{fx\_rel}\cdot l_x$ ($\mu\text{m}$) |
| `deposit.laser.fy_rel` | `0.5` | dimensionless | Relative coordinate of the laser focus along device $y$; absolute position $y_{\text{focus}} = \text{fy\_rel}\cdot l_y$ ($\mu\text{m}$) |
| `deposit.laser.fz_rel` | `[0.1, 0.3, 0.5, 0.7, 0.9]` (scan axis) | dimensionless | Relative coordinate of the laser focus along device depth $z$; absolute position $z_{\text{focus}} = \text{fz\_rel}\cdot l_z$ ($\mu\text{m}$) |
| `field.voltage` | `-500.0` (uses bias from the device file if set to `null`) | $\text{V}$ | Reverse bias voltage of the device under test |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `deposit.laser.<laser_key>` | omitted (uses value from laser component file) | Key-dependent | Overrides `direction`, `tech`, `wavelength` ($\text{nm}$), `refractionIndex`, `alpha` ($\text{m}^{-1}$), `beta_2` ($\text{m/W}$), `temporal_FWHM` ($\text{s}$), `pulse_energy` ($\text{J}$), `spacial_FWHM` ($\mu\text{m}$), `l_Rayleigh` ($\mu\text{m}$), `central_time` ($\text{s}$), `pairs_per_group` (pairs), or `groups` (groups) in the laser component |

All other parameters (`4` concentric rings $\times$ `8` sectors for laser cross-section partitioning, `50`-fold optical-path integration subdivision, `20`-fold per-bin midpoint sampling for pulse convolution, carrier drift time-window and time-step profiles `t_bin`/`delta_t`, thermal diffusion disabled `diffusion = False`, `50`-bin histogram for the 3D initial carrier distribution, and `200 × 200` grid for the 2D density map) are hardcoded in the source code.

## Outputs

Each laser position is a scan point, and stage outputs are stored under `<project>/tct/` just as in [`signal`](signal.md) (see [Architecture Overview](../architecture.md#results)): underlying nodes are stored in `<project>/tct/nodes/<stage>/<node>/` (containing the stage output files, stage plots, and `node.json`; one node per job from `deposit` through `reconstruction`, and one node per scan point for `analysis`), accessed through the `<project>/tct/points/<point>/<stage>/<job>` symlink views (`points/<point>/field` and `points/<point>/analysis` are each a single symlink) and `<project>/tct/points.json`, and [`analysis`](../stages/analysis.md) writes per-point results and distribution plots in each point's `analysis` node and writes the cross-position summary table and trend plots of collected charge and signal versus focal position under `<project>/tct/analysis/`. Device shared field nodes are stored under `<project>/field/<node>/`.

### Data Files

| Path | Writer Stage | Content and Main Fields | Unit |
| --- | --- | --- | --- |
| `nodes/deposit/<node>/deposit.h5` | [`deposit`](../stages/deposit.md) | Laser-injected carrier groups (recorded as event `event = 0`): attributes `generated_events`, `recorded_events`, `generated_fraction`; datasets `event`, `count`, `detector`, `x`/`y`/`z`, `x_start`/`y_start`/`z_start`, `t`, `t_fwhm`, `e`, `pairs` | Coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, `pairs` in pairs |
| `nodes/current/<node>/current.h5` | [`current`](../stages/current.md) | Induced-current file after convolution with the pulse temporal envelope: attributes `electrodes`, `dt`; datasets `event`, `t0`, `count`, `pairs`, `sensitive_pairs`, `carriers_without_field`, `charge`, `stored`, `index`, `current` | `dt`, `t0` in $\text{s}$; `charge` in $\text{C}$; `current` in $\text{A}$; `pairs` in pairs |
| `nodes/readout/<node>/readout.h5` | [`readout`](../stages/readout.md) | Output voltage waveform solved through the device equivalent circuit and front-end amplifier chain: attributes `electrodes`, `dt`, `pulse_edge`, `device_circuit`; datasets `event`, `t0`, `count`, `stored`, `index`, `voltage` | `dt`, `t0` in $\text{s}$; `voltage` in $\text{V}$ |
| `nodes/digitizer/<node>/digitizer.h5` | [`digitizer`](../stages/digitizer.md) | Digitized quantized-code waveform: attributes `electrodes`, `sampling_period`, `lsb_V`, `offset_V`, `bits`, `pulse_edge`, `device`; datasets `event`, `t0`, `count`, `stored`, `index`, `clipped`, `code` (`int16`) | `sampling_period`, `t0` in $\text{s}$; `lsb_V`, `offset_V` in $\text{V}$; `bits` in bits; `code` dimensionless |
| `nodes/trigger/<node>/trigger.h5` | [`trigger`](../stages/trigger.md) | Triggered recorded events: dataset `event` (`int64`, event IDs of recorded events) | dimensionless |
| `nodes/reconstruction/<node>/reconstruction.h5` | [`reconstruction`](../stages/reconstruction.md) | Reconstructed event feature table: attributes `electrodes`, `threshold`, `amplitude_threshold`, `fractions`, `edge`; datasets `event`, `selected`, `cluster_size`, `cluster_center`, `traced`, `baseline`, `noise`, `amplitude`, `above`, `ToA`, `ToT`, `CoG`, `area`, `CFD` | Voltage and thresholds $\text{V}$, time $\text{s}$, area $\text{V}\cdot\text{s}$ |
| `nodes/analysis/<node>/result.json`, `events.h5` (view `points/<point>/analysis/`) | [`analysis`](../stages/analysis.md) | Per-focal-point summary result and `selected` event feature table | Voltage $\text{V}$, thresholds $\text{mV}$, time $\text{s}$, efficiency dimensionless |
| `analysis/points.json` | [`analysis`](../stages/analysis.md) | Cross-focal-position scan summary table recording collected charge and signal features at each focal position | Relative coordinates dimensionless, charge $\text{C}$, voltage $\text{V}$, time $\text{s}$ |

### Plot Files

| Path | Writer Stage / Function | Content | Coordinate and Physical Quantity Units |
| --- | --- | --- | --- |
| `nodes/deposit/<node>/plots/pair_density_3d.png`, `.pdf`, `.root` | [`deposit`](../stages/deposit.md) (`LaserInjection.draw_nocarrier3D`) | 3D volume density (`TH3D`, `50 × 50 × 50` bins, evaluated at the bin centres from the absorption formulas, bins under `10%` of the highest value left empty) of initial electron-hole pairs generated inside the device by the laser pulse | Axes `x [μm]`, `y [μm]`, `z [μm]`; bin content in pairs per $\mu\text{m}^3$ |
| `nodes/deposit/<node>/plots/pair_density.png`, `.pdf`, `.root` | [`deposit`](../stages/deposit.md) (`LaserInjection.draw_nocarrier2D`) | Volume density of initial electron-hole pairs on the $y = \text{fy\_rel}\cdot l_y$ $x$-$z$ plane (passing through the optical axis), evaluated on a `200 × 200` grid from the absorption formulas (`TH2D`, `COLZ` color scale) | Horizontal axis `x [μm]`, vertical axis `z [μm]`, color scale `Pair density [μm⁻³]` |
| `nodes/current/<node>/plots/current_0.png`, `.pdf`, `.root` (`current_0_electrode_<k>` with several readout electrodes) | [`current`](../stages/current.md) (`draw_currents`) | Induced-current waveforms (`electrons`, `holes`, `total`, plus `gain electrons`, `gain holes` when avalanche is enabled) on the $k$-th nonzero-current electrode (starting from `1`) after convolution with the laser temporal pulse | Horizontal axis `Time [ns]`, vertical axis `Current [μA]` |
| `analysis/points.png` | [`analysis`](../stages/analysis.md) | Curves of collected charge and signal versus focal position across a focal-position scan | Horizontal axis relative focal position (dimensionless), vertical axis labeled with the unit of the corresponding physical quantity |

![NJU-PiN laser-injected 2D carrier distribution](../images/tct-carriers-2d-NJU-PiN.png)

Volume density of initial electron-hole pairs on the $x$-$z$ plane passing through the optical axis, output by `draw_nocarrier2D` for `NJU-PiN` illuminated by the top UV laser `PIL037_top_SiC`.

![NJU-PiN TCT induced current waveform](../images/tct-current-NJU-PiN.png)

Electron component, hole component, and total induced-current waveforms on the readout electrode output by `write_laser_currents` for `NJU-PiN` in a `tct` test.
