# Transient Current Technique Test (`bench/tct`)

`tct` (Transient Current Technique, in the `raser_bench` package) is centered on the device under test specified on the command line and uses the focal position of a fixed laser relative to the device as the scan axis. It reads device, laser, and front-end circuit configurations from [detector components (`components/device`)](../components/device.md), the laser definitions in [energy deposition components (`components/deposit`)](../components/deposit.md), and [front-end readout circuit components (`components/readout`)](../components/readout.md), moves the laser position relative to the device point by point, runs the same chain as [`signal`](signal.md) at each position, and outputs the initial carrier distribution, induced-current waveforms, readout voltage waveforms, and curves of collected charge and signal versus position.

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
- $\alpha$: linear (single-photon) absorption coefficient `alpha`, $\text{m}^{-1}$ (when omitted from the component file, obtained by log interpolation of `components/laser/absorption/<material>.txt` multiplied by $100$);
- $\beta_2$: two-photon absorption coefficient `beta_2`, $\text{m/W}$;
- $E_{\text{pulse}}$: single laser pulse energy `pulse_energy`, $\text{J}$; $E_{\text{ph}}$ is the single-photon energy, $\text{J}$ ($h = 6.626\times 10^{-34}\ \text{J}\cdot\text{s}$, $c = 2.998\times 10^{8}\ \text{m/s}$);
- $\text{FWHM}_t$: laser temporal pulse full width at half maximum `temporal_FWHM`, $\text{s}$;
- $(dN/ds_{\text{m}})_{\text{SPA}}$, $(dN/ds_{\text{m}})_{\text{TPA}}$: electron-hole pairs generated per meter at path coordinate $s$ by single-photon and two-photon absorption, $\text{m}^{-1}$;
- $P(t)$: laser temporal pulse envelope `timePulse(t)`, $\text{s}^{-1}$; $p_k$ is the dimensionless pulse weight integrated over integer time-bin offset $k$ by `pulse_in_bins`;
- $I_{e,a}$, $I^{\text{conv}}_{e,b}$: bin-averaged induced current on electrode $e$ in time bins $a$ and $b$ before and after convolution, $\text{A}$; $n_{\text{bin}}$ is the total number of time bins in the window (dimensionless).

Eqs. (1)–(4) are implemented by `LaserInjection` and `absorption_coefficient` in [`core/deposit/laser.py`](../core/deposit.md); Eq. (5) is implemented by `pulse_in_bins`, `CalCurrentLaser`, and `write_laser_currents` in [`core/current/cal_current.py`](../core/current.md). Standard TCT and Edge-TCT methods for measuring internal electric fields and charge collection in semiconductor detectors are described in Ref. [1] (V. Eremin, N. Strokan, E. Verbitskaya, Z. Li, “Development of transient current and charge techniques for the measurement of effective net concentration of ionized charges (Neff) in the space charge region of p-n junction detectors”, *Nucl. Instrum. Methods Phys. Res. A* 372 (1996) 388, doi:10.1016/0168-9002(95)01295-8) and Ref. [2] (G. Kramberger et al., “Investigation of Irradiated Silicon Detectors by Edge-TCT”, *IEEE Trans. Nucl. Sci.* 57 (2010) 2294, doi:10.1109/TNS.2010.2051957).

### Incidence Directions and Beam-Path Geometry

`LaserInjection._beam_frame` (`src/raser/core/deposit/laser.py:163-176`) supports three laser incidence directions without launching Geant4, constructing the optical path directly in the device coordinate system $[0, l_x] \times [0, l_y] \times [0, l_z]$ (in $\mu\text{m}$):

- **Top incidence (`"direction": "top"`)**: the beam enters from the top face $z = 0$ along $+z$, with total path length inside the device $L = l_z$ ($\mu\text{m}$), focus distance from the entrance surface $s_{\text{focus}} = z_{\text{focus}}$, and beam cross section centered at $(x_{\text{focus}}, y_{\text{focus}})$; typically scans lateral positions `fx_rel`, `fy_rel` and focus depth `fz_rel`.
- **Bottom incidence (`"direction": "bottom"`)**: the beam enters from the bottom face $z = l_z$ along $-z$, with total path length inside the device $L = l_z$ ($\mu\text{m}$), focus distance from the entrance surface $s_{\text{focus}} = l_z - z_{\text{focus}}$, beam cross section centered at $(x_{\text{focus}}, y_{\text{focus}})$, and path distance $s$ corresponding to device coordinate $z = l_z - s$.
- **Edge incidence (`"direction": "edge"`)**: the beam enters from the side face $x = 0$ along $+x$, with total path length inside the device $L = l_x$ ($\mu\text{m}$), focus distance from the entrance surface $s_{\text{focus}} = x_{\text{focus}}$, and beam cross section centered at $(y_{\text{focus}}, z_{\text{focus}})$; primarily scans beam depth `fz_rel` (or focal depth `fx_rel` along the beam direction).

Limitations: `write_laser_currents` calls `CalCurrentLaser` with `diffusion=False` hardcoded, turning off carrier thermal diffusion; the `tct` workflow sets `seeds=False` and passes `seed=None` to `readout`, so frequency-domain electronics thermal noise is not added; under `"TPA"` mode, although the temporal width of two-photon-generated carrier clusters is $\text{FWHM}_t / \sqrt{2}$, `CalCurrentLaser` still convolves the total current uniformly with `timePulse` of single-photon width `temporal_FWHM`; plasma screening of the local electric field by high-density photogenerated carriers is not included.

### Execution Steps and Built-in Constants

Job `0` of each `tct` scan point executes in the following order (`src/raser/bench/tct/tct_signal.py:18-36`):

1. **Generate laser carrier groups (`LaserInjection`)**: in the `current` slice, constructs `Detector` from `files["device"]` and `LaserInjection` from `files["laser"]`. For each active absorption mechanism (single-photon when $\alpha \ne 0$, plus two-photon when `tech == "TPA"`), evaluates the total pair count $N_{\text{tot}}$ by trapezoidal integration over $\lceil 50 L / \min(L, l_R, 10^6/\alpha) \rceil + 1$ sample points along the full optical path $L$. The beam cross section is partitioned into `4` equal-fraction concentric rings (normalized radii $\rho_r = \sqrt{-\ln(1 - (r + 0.5)/4)/k}$, $r = 0, 1, 2, 3$, with $k = 2$ for single-photon and $k = 4$ for two-photon) and `8` equal-angle sectors ($\phi_m = (m + 0.5)\pi/4$, $m = 0, \dots, 7$), yielding `32` cells per slab, and sliced along the beam path into $N_{\text{slab}} = \lceil \max(N_{\text{tot}} / \text{pairs\_per\_group},\, \text{groups}) / 32 \rceil$ equal-fraction slabs. At the center of each cell lying within the lateral device boundaries, a carrier group carrying $N_{\text{tot}} / (32 N_{\text{slab}})$ electron-hole pairs is placed at time `central_time` ($\text{s}$).
2. **Diffusionless drift, pulse convolution, and plotting (`write_laser_currents`)**: calls `stages.current.solved` to load the shared field `DevsimField`, performs drift, avalanche multiplication, and Shockley–Ramo induced-current binning for all carrier groups inside `CalCurrentLaser(my_d, my_f, my_l, diffusion=False)`, then computes the pulse weight matrix of Eq. (5) with $S = \max(1, \lceil 20\,\Delta t_{\text{bin}} / \text{FWHM}_t \rceil)$ samples per bin, right-multiplies the current waveforms, writes the result as event `0` to `batch/current_0.h5`, and plots the nonzero-electrode induced-current waveforms together with the initial carrier distributions from `draw_nocarrier3D` and `draw_nocarrier2D` under `plots/`.
3. **Noiseless front-end circuit readout (`readout.waveforms`)**: the `readout` slice reads `batch/current_0.h5`, assembles the device equivalent circuit and `amplifier` subcircuit chain, runs `ngspice` with `seed=None` (no thermal noise) to solve the output voltage waveforms, and writes `batch/readout_0.h5`.

The built-in constants in `tct` are listed below:

| Constant or Fixed Item | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| Photon energy constants $h$, $c$ | `6.626e-34`, `2.998e8` | $\text{J}\cdot\text{s}$, $\text{m/s}$ | `src/raser/core/deposit/laser.py:137`, Planck constant and speed of light used to compute single-photon energy $E_{\text{ph}} = h c / \lambda$ |
| Optical-path integration subdivision factor | `50` | steps | `src/raser/core/deposit/laser.py:198-199`, integration sampling multiplier applied to the optical path length divided by the smallest characteristic scale $\min(L, l_R, 10^6/\alpha)$ |
| `rings`, `sectors` | `4`, `8` | rings, sectors | `src/raser/core/deposit/laser.py:206`, numbers of equal-fraction concentric rings and angular sectors partitioning the laser cross section (`32` groups per slab) |
| Carrier distribution histogram bins | `50 × 50 × 50` (3D), `50 × 50` (2D) | bins | `src/raser/core/deposit/laser.py:236-239, 269-271`, histogram binning of `draw_nocarrier3D` and `draw_nocarrier2D` |
| Per-bin pulse convolution sampling multiplier | `20` | points | `src/raser/core/current/cal_current.py:691`, `pulse_in_bins` requires midpoint-rule spacing inside each bin not to exceed $\text{FWHM}_t / 20$ |
| `t_bin`, `delta_t` | 1D: `5e-12`, `2e-12`; 2D/3D: `50e-12`, `20e-12` | $\text{s}$ | `src/raser/core/current/cal_current.py:30-50`, induced-current time-bin width and single drift step |
| `diffusion` | `False` | None | `src/raser/core/current/cal_current.py:833`, `write_laser_currents` hardcodes carrier thermal diffusion off |
| `seeds` | `False` | None | `src/raser/bench/tct/__init__.py:55`, `tct` is a seedless workflow, so `readout` does not add frequency-domain thermal noise |

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, and device equivalent circuit parameters of the device under test at the target bias and irradiation fluence under `<project>/field/`.
- [`deposit`](../stages/deposit.md): holds deposit-section parameters such as the laser focal position in the top-level sectioned configuration.
- [`current`](../stages/current.md): drifts carrier groups generated by the laser pulse in the solved field without diffusion, convolves them with the Gaussian laser temporal envelope, and writes the event `0` induced-current file, carrier distribution plots, and current waveform plots.
- [`readout`](../stages/readout.md): feeds the convolved induced current into the device equivalent circuit and front-end amplifier chain and solves output voltage waveforms with `ngspice` without noise.
- [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), [`analysis`](../stages/analysis.md): following the top-level design, each focal scan point completes the same downstream stages as [`signal`](signal.md), and [`analysis`](../stages/analysis.md) aggregates and plots collected charge and signal versus focal position under `<project>/tct/analysis/`.

### Components

- [Detector components (`components/device`)](../components/device.md): provides dimensions `l_x`, `l_y`, `l_z` ($\mu\text{m}$), material `material`, doping, bias voltage, temperature, irradiation, and avalanche parameters of the device under test (such as `HPK-Si-PiN.json`, `NJU-PiN.json`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides laser component JSONs (such as default top infrared silicon laser `LA01IR_top_Si.json`, edge `LA01IR_edge_Si.json`, red `LA01R_top_Si.json` / `LA01R_bottom_Si.json`, SiC UV laser `PIL037_top_SiC.json` / `PIL037_edge_SiC.json`, silicon two-photon laser `TPA1550_top_Si.json` / `TPA1550_edge_Si.json`) and the intrinsic silicon band-to-band absorption table `absorption/Si.txt`.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides SPICE amplifier stages and termination load subcircuits cascaded with `+` (default `SantaCruz+Gali52+Termination50`).

## Usage and Configuration

`tct` and [`signal`](signal.md) are separated by scan axis: when scanning the laser position relative to the device (`fx_rel`, `fy_rel`, `fz_rel`), use `tct`; when scanning properties of the laser itself (pulse energy `pulse_energy`, wavelength `wavelength`) or device settings (bias `voltage`, irradiation `irradiation`), use [`signal`](signal.md).

Run `tct` on the device under test with the position scan axis written in the `deposit` section of `config.json` or given on the command line via `--scan` (for example, scanning the focal depth fraction `fz_rel` relative to device thickness):

```bash
raser tct <device>
raser tct NJU-PiN --set deposit.laser=PIL037_top_SiC --scan deposit.laser.fz_rel=0.1,0.3,0.5,0.7,0.9
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the configuration structure of the experiment directory `<project>/tct/config.json` is:

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

The configuration keys users can set in `tct` are listed below (`src/raser/bench/tct/__init__.py:15-56`, `transient_current.json:1-5`, and [`../components/deposit.md`](../components/deposit.md#laser-and-absorption-coefficient-table)):

| Section.Key (Code Key) | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `deposit.laser` (`laser`) | `"LA01IR_top_Si"` | None | Laser component name or path (CLI optional positional argument `laser`) |
| `deposit.laser.fx_rel` | From laser component file (`0.25` for `LA01IR_top_Si`) | dimensionless | Relative coordinate of the laser focus along device $x$; absolute position $x_{\text{focus}} = \text{fx\_rel}\cdot l_x$ ($\mu\text{m}$) |
| `deposit.laser.fy_rel` | From laser component file (`0.5` for `LA01IR_top_Si`) | dimensionless | Relative coordinate of the laser focus along device $y$; absolute position $y_{\text{focus}} = \text{fy\_rel}\cdot l_y$ ($\mu\text{m}$) |
| `deposit.laser.fz_rel` | From laser component file (`0.0` for `LA01IR_top_Si`) | dimensionless | Relative coordinate of the laser focus along device depth $z$; absolute position $z_{\text{focus}} = \text{fz\_rel}\cdot l_z$ ($\mu\text{m}$) |
| `field.voltage` (equivalent to `field.device.bias.voltage`) | `bias.voltage` from the device file | $\text{V}$ | Reverse bias voltage of the device under test (CLI `-vol`/`--voltage`) |
| `readout.amplifier` (`amplifier`) | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` (CLI `-amp`/`--amplifier`) |
| `deposit.<laser_key>` (`laser.<laser_key>`) | From laser component file | Key-dependent | Overrides `direction`, `tech`, `wavelength` ($\text{nm}$), `refractionIndex`, `alpha` ($\text{m}^{-1}$), `beta_2` ($\text{m/W}$), `temporal_FWHM` ($\text{s}$), `pulse_energy` ($\text{J}$), `spacial_FWHM` ($\mu\text{m}$), `l_Rayleigh` ($\mu\text{m}$), `central_time` ($\text{s}$), `pairs_per_group` (pairs), or `groups` (groups) in the laser component |

All other parameters (`4` concentric rings $\times$ `8` sectors for laser cross-section partitioning, `50`-fold optical-path integration subdivision, `20`-fold per-bin midpoint sampling for pulse convolution, carrier drift time-window and time-step profiles `t_bin`/`delta_t`, thermal diffusion disabled `diffusion = False`, seedless execution with readout thermal noise off `seeds = False`, and `50`-bin histograms for 3D/2D initial carrier distributions) are hardcoded in the source code.

## Outputs

Each laser position is a scan point, and stage outputs are stored under `<project>/tct/` just as in [`signal`](signal.md) (see [Architecture Overview](../architecture.md#results)): underlying nodes are stored in `<project>/tct/nodes/<stage>/<node>/`, accessed through the `<project>/tct/points/<point>/<stage>` symlink views and `<project>/tct/points.json`, and [`analysis`](../stages/analysis.md) plots collected charge and signal versus focal position under `<project>/tct/analysis/`.

### Data Files

| Filename | Writer Stage | Content and Main Fields | Unit |
| --- | --- | --- | --- |
| `batch/current_0.h5` | [`current`](../stages/current.md) | Induced-current file for a single laser pulse (recorded as `event = 0`) after convolution with the pulse temporal envelope: attributes `electrodes`, `dt`; datasets `event`, `t0`, `count`, `pairs`, `sensitive_pairs`, `carriers_without_field`, `charge`, `stored`, `index`, `current` | `dt`, `t0` in $\text{s}$; `charge` in $\text{C}$; `current` in $\text{A}$; `pairs` in pairs |
| `batch/readout_0.h5` | [`readout`](../stages/readout.md) | Noiseless output voltage waveform of a single laser pulse through the device equivalent circuit and front-end amplifier chain: attributes `electrodes`, `dt`, `pulse_edge`, `device_circuit`; datasets `event`, `t0`, `count`, `stored`, `index`, `voltage` | `dt`, `t0` in $\text{s}$; `voltage` in $\text{V}$ |

### Plot Files

| Filename | Writer Stage / Function | Content | Coordinate and Physical Quantity Units |
| --- | --- | --- | --- |
| `plots/No_<k>electrode_basic_infor.pdf`, `.root` | [`current`](../stages/current.md) (`draw_currents`) | Induced-current waveforms (`electron`, `hole`, `total`, plus `electron gain`, `hole gain` when avalanche is enabled) on the $k$-th nonzero-current electrode (starting from `1`) after convolution with the laser temporal pulse | Horizontal axis `Time [s]`, vertical axis `Current [A]` |
| `plots/nocarrier_<fx_rel>_<fy_rel>_<fz_rel>.pdf` | [`current`](../stages/current.md) (`LaserInjection.draw_nocarrier3D`) | 3D logarithmic distribution histogram (`TH3D`, `50 × 50 × 50` bins; relative coordinates in filename rounded to `5` decimal places) of initial carrier groups generated inside the device by the laser pulse | Axes `Depth [um]`, `Width [um]`, `Thick [um]`; bin weight in electron-hole pairs |
| `plots/nocarrier2D_<fx_rel>_<fy_rel>_<fz_rel>.pdf` | [`current`](../stages/current.md) (`LaserInjection.draw_nocarrier2D`) | 2D logarithmic distribution plot (`TH2D`, `50 × 50` bins, `COLZ` color scale) of initial carrier groups generated in the device $x$-$z$ plane by the laser pulse | Horizontal axis `x axis [um]`, vertical axis `z axis [um]`, color scale `Carriers` (pairs) |

![NJU-PiN laser-injected 2D carrier distribution](../images/tct-carriers-2d-NJU-PiN.png)

Logarithmic 2D distribution of initial carrier groups in the $x$-$z$ plane output by `draw_nocarrier2D` for `NJU-PiN` illuminated by the top UV laser `PIL037_top_SiC`.

![NJU-PiN TCT induced current waveform](../images/tct-current-NJU-PiN.png)

Electron component, hole component, and total induced-current waveforms on the readout electrode output by `write_laser_currents` for `NJU-PiN` in a `tct` test.
