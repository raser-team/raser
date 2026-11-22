# CEPC Fast Luminosity Monitor (`apps/cflm`)

`cflm` (CEPC Fast Luminosity Monitor, in the `raser_app` package) simulates the signal response left in `24` detector pads mounted on both sides of the outer wall of a copper beam pipe after lost electrons from collider bunches strike the beam pipe. Centered on a single detector pad device (Si or 4H-SiC), it reads [detector components (`components/device`)](../components/device.md), the packaged copper beam-pipe and lost-electron configuration `cflm_p1.json`, [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence: each job has `1` [`deposit`](../stages/deposit.md) node (running Geant4 once to compute energy deposition across all `24` pads and writing it to a single `deposit.h5`), and all pads share the same `1` [`field`](../stages/field.md) field node; [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), and [`reconstruction`](../stages/reconstruction.md) each have `1` node per job, writing `current.<pos>.h5`, `readout.<pos>.h5`, `digitizer.<pos>.h5`, `trigger.<pos>.h5`, and `reconstruction.<pos>.h5` separately inside the node for each of the `24` pad positions `<pos>` (`I_-3_0` through `II_2_1`); it outputs the induced current, readout voltage waveform, and reconstruction feature table on each pad. Limitation: `analysis` currently only aggregates single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad summaries for cflm) are not yet implemented.

## Setup and Standard Practice

### Standard Practice and Coordinate Transformation

In a circular electron-positron collider (CEPC), radiative Bhabha scattering or beam losses near the interaction region produce high-energy lost electrons that deviate from the beam envelope. These lost electrons strike the inner wall of the copper beam pipe at shallow grazing angles and initiate electromagnetic showers inside the pipe wall, with secondary electrons, positrons, and $\gamma$ photons emerging from the outer wall. The Fast Luminosity Monitor (CFLM) mounts symmetric arrays of fast radiation-hard semiconductor detector pads (such as 4H-SiC PiN diodes) on the left and right outer walls of the copper beam pipe to measure the pulse amplitude and arrival time on each pad bunch by bunch, monitoring collision luminosity and the spatial distribution of beam losses in real time.

In `src/raser_app/cflm/cflm_p1.py` and `deposits.py`, `24` detector pads of size $l_x \times l_y \times l_z$ (in $\mu\text{m}$) are arranged on both sides of the copper beam-pipe outer wall with position labels `<side>_<i>_<j>`. The center position $(x_{\text{pad}}, y_{\text{pad}}, z_{\text{pad}})$ of pad `(side, i, j)` in the global beam-pipe coordinate system (in $\mu\text{m}$) is:

$$x_{\text{pad}} = s_{\text{side}}\!\left(1000\,R_{\max} + \frac{l_z}{2}\right), \qquad y_{\text{pad}} = (i + 0.5)\,l_x, \qquad z_{\text{pad}} = 1000\,z_{\text{from}} + (j + 0.5)\,l_y \tag{1}$$

After rotating the pad logical volume by $3\pi/2\ \text{rad}$ ($270^\circ$) around the global $Z$ axis, it is placed flush against the outer wall of the copper pipe at $|X| = 1000\,R_{\max}$. The global step-start coordinates $(X, Y, Z)$ (in $\mu\text{m}$) recorded by Geant4 are transformed into the pad's local coordinate system $(x, y, z)$ (in $\mu\text{m}$) by `pad_frame`:

$$x = \frac{l_x}{2} - Y + (i + 0.5)\,l_x, \qquad y = \frac{l_y}{2} + Z - \bigl(1000\,z_{\text{from}} + (j + 0.5)\,l_y\bigr), \qquad z = s_{\text{side}}\,X - 1000\,R_{\max} \tag{2}$$

where:

- $\text{side} \in \{\text{"I"}, \text{"II"}\}$: identifier for the two sides of the beam pipe; the sign factor $s_{\text{side}}$ is $-1$ on side `"I"` ($-x$ side) and $+1$ on side `"II"` ($+x$ side);
- $i \in \{-3, -2, -1, 0, 1, 2\}$: index `pixelAreaYIndex` of the `6` pad rows along the vertical direction (global $y$ axis) (dimensionless);
- $j \in \{0, 1\}$: index `pixelAreaZIndex` of the `2` pad columns along the beam direction (global $z$ axis) (dimensionless);
- $R_{\max}$: outer radius `pipe.Rmax` of the copper beam pipe, $\text{mm}$ (default $31\ \text{mm}$, multiplied by $1000$ to give $31000\ \mu\text{m}$);
- $z_{\text{from}}$: starting $z$ coordinate `pads_from_z_mm` of the pad array along the beam direction, $\text{mm}$ (default $225\ \text{mm}$, multiplied by $1000$ to give $225000\ \mu\text{m}$);
- $l_x, l_y, l_z$: full three-dimensional dimensions of a single pad device (`Detector`), $\mu\text{m}$; in `cflmDetectorConstruction.pads`, the `G4Box` half-dimensions are defined as $(l_x/2,\, l_z/2,\, l_y/2)$ and rotated by $3\pi/2\ \text{rad}$ around the global $Z$ axis, aligning the pad's $l_x$ with global $y$, $l_y$ with global $z$ (beam direction), and thickness $l_z$ with global $\pm x$ (outward normal to the pipe wall);
- $(X, Y, Z)$: position of the Geant4 step start `point_in` in the global beam-pipe coordinate system, $\mu\text{m}$;
- $(x, y, z)$: pad-local coordinates written to `deposit.h5`, $\mu\text{m}$, with $x \in [0, l_x]$, $y \in [0, l_y]$, and depth $z \in [0, l_z]$ pointing inward into the pad from the entrance surface ($z = 0$) flush against the outer copper pipe wall.

Eq. (1) is implemented by `cflmDetectorConstruction.pads` in `src/raser_app/cflm/cflm_p1.py`, and Eq. (2) is implemented by `pad_frame` in `src/raser_app/cflm/deposits.py`. `cflm` uses the same UCSC (`SantaCruz`) plus wideband amplifier readout chain as the 4H-SiC PIN time-resolution study in Ref. [1] (T. Yang et al., “Time Resolution of the 4H-SiC PIN Detector”, *Front. Phys.* 10 (2022) 718071, doi:10.3389/fphy.2022.718071).

### Copper Beam Pipe, 24 Pads, and Lost-Electron Configuration (`cflm_p1.json`)

`src/raser_app/cflm/cflm_p1.json` and `cflm_p1.py` define the Geant4 beam-pipe geometry and lost-electron particle gun parameters:

- **World and copper beam pipe (`world`, `pipe`, `vacuum`)**:
  - World cube `world`: material `"G4_AIR"`, half-dimensions $2000\ \text{mm} \times 2000\ \text{mm} \times 2000\ \text{mm}$;
  - Copper beam pipe `pipe`: `G4Tubs` cylindrical tube, material `"G4_Cu"`, inner radius `Rmin = 28` $\text{mm}$, outer radius `Rmax = 31` $\text{mm}$ (wall thickness $3\ \text{mm}$), full length `Pipe_Z = 700` $\text{mm}$ (half-length $350\ \text{mm}$), starting azimuth `PipeSphi = 0` $\text{deg}$, span angle `PipeDphi = 360` $\text{deg}$, center coordinates `[0, 0, 250]` $\text{mm}$ (covering $z \in [-100, 600]\ \text{mm}$ along the beam axis);
  - Interior vacuum `vacuum`: `G4Tubs` cylinder, material `"G4_Galactic"`, inner radius `VACmin = 0` $\text{mm}$, outer radius `VACmax = 28` $\text{mm}$, full length `VAC_Z = 700` $\text{mm}$, center coordinates `[0, 0, 250]` $\text{mm}$.
- **24 detector pads (`detector_<side>_<i>_<j>`)**: on each side (`I` at $x \le -31\ \text{mm}$, `II` at $x \ge +31\ \text{mm}$), pads are arranged in $6\text{ rows} \times 2\text{ columns} = 12$ pads (`24` in total), starting along the beam direction at `pads_from_z_mm = 225` $\text{mm}$. `pad_material` supports only device material `material == "Si"` (using `"G4_Si"`) or `"SiC"` (building a `G4Material` with 4H-SiC density $3.21\ \text{g/cm}^3$ (Ioffe NSM database, M. E. Levinshtein, S. L. Rumyantsev, M. S. Shur (eds.), *Properties of Advanced Semiconductor Materials*, Wiley (2001)) and Si/C atomic percentages $50\% : 50\%$; any other material raises `ValueError`), with maximum step size `maxStep = 2` $\mu\text{m}$ inside each pad.
- **Lost-electron particle gun (`cflmPrimaryGeneratorAction`)**: each run simulates `BeamOn = 1` bunch (event), and each bunch emits `NumofGun = 3` lost electrons (`par_type = "e-"`) simultaneously via `G4ParticleGun`. The kinetic energy `par_energy` ($\text{GeV}$), starting position `par_in` ($\text{mm}$), and momentum direction vector `par_direct` (dimensionless direction components) of the 3 lost electrons are:

| Electron Index | Kinetic Energy `par_energy` ($\text{GeV}$) | Starting Coordinates `par_in` $[X_0, Y_0, Z_0]$ ($\text{mm}$) | Momentum Direction Vector `par_direct` $[d_x, d_y, d_z]$ |
| --- | --- | --- | --- |
| `0` | `21.906` | `[27.913, -2.7834, 98.2917]` | `[0.0321, -0.0023, 21.906]` |
| `1` | `25.9726` | `[-27.893, 2.647, 108.2917]` | `[-0.0483, 0.003, 25.9725]` |
| `2` | `24.7832` | `[27.8585, 2.8364, 78.2917]` | `[0.0434, 0.003, 24.7832]` |

Limitations: `RecordDetector` in `cflm_p1.py` records only the step-start position `point_in` and deposited energy `edep` of each deposition step and does not record the Geant4 global time; `deposits.py` therefore writes a fixed `0.0 s` for the time `t` of all deposition steps, omitting time-of-flight differences among different electrons and secondary shower particles reaching different pads. `cflm_p1.json` is always read from the packaged path and is not switched via `deposit.g4setup` or `deposit.source`.

### Execution Steps and Built-in Constants

`cflm` is defined in `src/raser_app/cflm/` and organizes all eight stages into nodes for all `24` pad positions `PADS` (`I_-3_0` through `II_2_1`): each scan point shares `1` single-pad `field` field node and `1` `analysis` node; each job has `1` `deposit` node (writing deposition across all `24` pads into a single `deposit.h5`), plus `1` node each for `current`, `readout`, `digitizer`, `trigger`, and `reconstruction` (each node writing a `.<pos>`-suffixed `.h5` file for every pad with deposition), executed in the following order:

1. **Simulate lost electrons in the bunch and write deposition across 24 pads (`deposit` node, `deposits.deposits`)**: constructs a single-pad `Detector`, reads `src/raser_app/cflm/cflm_p1.json`, and calls `cflm_p1.simulate_bunches(g4_dic, seed, my_d)` using the Geant4 `FTFP_BERT` physics list with `G4StepLimiterPhysics`. In `bunch_deposits`, it iterates over each bunch and all `24` pads, skipping placeholder steps with `energy <= 0` (pads with no deposit are filled with `[[0, 0, 0]]` and `[0]` in `simulate_bunches`), transforms all valid steps to pad-local coordinates $(x, y, z)$ via `pad_frame` (Eq. (2)), sets `detector` to `<side>_<i>_<j>` and time `t` to `0.0` $\text{s}$, calls `ionized_pairs(event, my_d.material)` (default `fano=True`) to sample electron-hole pair counts `pairs`, and writes `deposit.h5` in the `deposit` node. If no bunch has any valid deposition in any of the 24 pads (`not found.events`), it raises `Ended` to terminate the job early.
2. **Reuse or solve single-pad shared field (`field` node)**: reuses the electric field, weighting field, and equivalent circuit parameters of the single-pad device under `work/<det_name>/field/<node>/`, shared by all `24` pads; if no field is found, the required field is solved before jobs begin and stored in `field/` of the device project.
3. **24-channel carrier drift (`current` node)**: inside the job's `current` node, iterates over all `24` pad positions `<pos>` (`I_-3_0` through `II_2_1`), first checking whether `deposit.h5` contains deposition steps with `detector == <pos>`; if that pad has no deposition in this job, no corresponding `.h5` file is written; otherwise, calls `write_induced_currents(..., detector=position)` to drift only the deposition steps belonging to that pad and writes `current.<pos>.h5` (drawing plots under `nodes/current/<node>/<pos>/event_<event>/` when `current.plots > 0`).
4. **24-channel electronics readout, digitization, triggering, and event reconstruction (`readout`, `digitizer`, `trigger`, `reconstruction` nodes)**: each stage has `1` node per job; for each position `<pos>` that has an upstream `.h5` file, the respective nodes execute in sequence: `readout` calls `ngspice` to solve the front-end amplifier chain output voltage waveforms with frequency-domain thermal noise superimposed and writes `readout.<pos>.h5`; `digitizer` quantizes the waveforms into codes according to the analog bandwidth, sampling rate, and bit depth and writes `digitizer.<pos>.h5` (see [`stages/digitizer`](../stages/digitizer.md) for the format); `trigger` selects recorded events according to the trigger condition and writes `trigger.<pos>.h5` containing the event-number dataset `event` (`int64`); `reconstruction` reads the events in `digitizer.<pos>.h5` recorded by `trigger.<pos>.h5`, converts the quantized codes back to voltage ($\text{V}$, with sample timestamps `t0 + k·sampling_period`) using `lsb_V` and `offset_V`, subtracts the leading `200`-point baseline to extract amplitude and timing features, marks events where a cluster seed is found as `selected`, and writes `reconstruction.<pos>.h5`. Pads without upstream files do not have corresponding `.h5` files written.
5. **Analysis (`analysis` node)**: `1` `analysis` node per scan point. Limitation: `analysis` currently only aggregates single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad summaries for cflm) are not yet implemented.

In addition, `src/raser_app/cflm/` contains a set of helper scripts for secondary-particle distributions that run independently of the `raser cflm` simulation chain:

- `cflm_spd.py` (reads `cflm_spd.json`: world half-side $6000\ \text{mm}$, copper pipe full length `Pipe_Z = 6000` $\text{mm}$ centered at $z = 2000\ \text{mm}$, maximum step size $1\ \text{mm}$): without detector pads present, records the particle names and $(z, y)$ crossing coordinates of secondary particles exiting the copper beam pipe through the $x = -31\ \text{mm}$ and $x = +31\ \text{mm}$ planes, writing `<PosBaseName>_nx.txt` and `<PosBaseName>_px.txt`;
- `data_file.py`, `p1_sample.py`, `spd_dis.py`, `spd_plot.py`: `data_file.py` reads `lossposition_CEPC.xlsx` and writes `src/raser_app/cflm/input/datafile_p1.root` (the input directory is not tracked in the repository); the remaining scripts read this ROOT file or `SecondaryParticle_*_{nx,px}.txt` to sample Poisson hit counts or batch-rewrite `cflm_spd.json`, invoke `cflm_spd.main()`, and plot spatial distributions of secondary $\gamma$ and $e^-$.

The built-in constants in `cflm` are listed below:

| Constant or Fixed Item | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| `PADS` | `24` positions (`I_-3_0` through `II_2_1`) | count | `src/raser_app/cflm/__init__.py`, tuple of pad positions across 2 sides (`I`, `II`) $\times$ `6` rows (`i = -3..2`) $\times$ `2` columns (`j = 0..1`) |
| Stage node layout | `1` node per job for `deposit` through `reconstruction`; `1` node per scan point for `field` and `analysis` | nodes | `src/raser_app/cflm/__init__.py`, the `deposit` node writes a single `deposit.h5`, while the `current` through `reconstruction` nodes each write `.<pos>`-suffixed files for the `24` pad positions |
| World cube half-side | `2000` (`cflm_p1.py`); `6000` (`cflm_spd.py`) | $\text{mm}$ | `src/raser_app/cflm/cflm_p1.py`, `cflm_spd.py`, half-dimensions of the Geant4 world volume |
| Beam-pipe and pad rotation angle | `3 * pi / 2` (`270`) | $\text{rad}$ ($\text{deg}$) | `src/raser_app/cflm/cflm_p1.py`, rotation angle around the $Z$ axis aligning pad local coordinates flush against both outer walls of the copper pipe |
| Geant4 `"SiC"` density and stoichiometry | `3.21` (Ioffe NSM database, Levinshtein et al. (2001)), `50 : 50` | $\text{g/cm}^3$, `%` | `src/raser_app/cflm/cflm_p1.py`, fixed density and Si/C atomic percentages when constructing the SiC pad material |
| Fixed deposition-step time `t` | `0.0` | $\text{s}$ | `src/raser_app/cflm/deposits.py`, fixed timestamp written to `deposit.h5` because `cflm_p1` deposition steps carry no timestamps |

## Stages and Components Used

### Stages

- [`deposit`](../stages/deposit.md): replaces standard single-device deposition with `src/raser_app/cflm/deposits.py`, with `1` node per job, simulating lost-electron showers in the copper beam-pipe geometry and writing deposition steps for all `24` pads into a single `deposit.h5`.
- [`field`](../stages/field.md): reuses the field node of a single pad device under `work/<det_name>/field/<node>/`, shared by all `24` pads; if no field is found, it is solved before jobs begin and stored in `field/` of the device project.
- [`current`](../stages/current.md): `1` node per job; inside the node, filters deposition steps by each of the `24` pad positions `<pos>`, drifts carriers in the shared field, and writes `current.<pos>.h5` for each pad.
- [`readout`](../stages/readout.md): `1` node per job; inside the node, feeds induced currents of pads with deposits into the device equivalent circuit and front-end amplifier chain, solves output voltage waveforms with frequency-domain thermal noise superimposed, and writes `readout.<pos>.h5`.
- [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md): `1` node per job each; inside the nodes, performs digitization sampling and quantization on each pad's output waveform to write `digitizer.<pos>.h5`, then selects recorded events by the trigger condition to write `trigger.<pos>.h5`.
- [`reconstruction`](../stages/reconstruction.md): `1` node per job; inside the node, reads events in each pad's `digitizer.<pos>.h5` recorded by `trigger.<pos>.h5`, converts the quantized codes back to voltage ($\text{V}$), extracts pulse amplitude, `ToA`, `ToT`, `CoG`, `area`, and `CFD` feature tables, and writes `reconstruction.<pos>.h5`.
- [`analysis`](../stages/analysis.md): `1` node per scan point. Limitation: `analysis` currently only aggregates single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad summaries for cflm) are not yet implemented.

### Components

- [Detector components (`components/device`)](../components/device.md): provides single-pad dimensions `l_x`, `l_y`, `l_z` ($\mu\text{m}$), material `material` (`"Si"` or `"SiC"`), doping, bias voltage, and temperature definitions (such as `NJU-PiN.json`, `HPK-Si-PiN.json`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): the packaged `src/raser_app/cflm/cflm_p1.json` defines the copper beam pipe, vacuum, and parameters of the 3 high-energy lost electrons.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides SPICE amplifier stages and termination load subcircuits cascaded with `+` (default `SantaCruz+Gali52+Termination50`).
- [Digitizer components (`components/digitizer`)](../components/digitizer.md) and [trigger components (`components/trigger`)](../components/trigger.md): provides digitization sampling/quantization and trigger threshold definitions.

## Usage and Configuration

Run the `cflm` application, or use `--set` and `--scan` to scan bias voltage, device, front-end amplifier, and threshold parameters (the device is specified in `config.json`, not as a positional CLI argument, and can serve as a scan axis; see [Command-Line Interface](../cli.md#commands) for CLI usage):

```bash
raser cflm
raser cflm --scan field.voltage=-300,-500
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the configuration structure of the experiment directory `work/cflm/config.json` is shown below. Only the sections relevant to this page are excerpted here; `examples/cflm/config.json` specifies all eight sections in full.

```json
{
  "workflow": "cflm",
  "device": "NJU-PiN",
  "field": {
    "voltage": -500.0,
    "irradiation_flux": null
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

The configuration keys users can set in the `cflm` workflow and the setup keys in `src/raser_app/cflm/cflm_p1.json` are listed below (see [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md#settings) for details of each stage's settings). For stage settings, "Value in Example" lists the values written in `examples/cflm/config.json`, and an error naming the missing `section.key` is raised if a required key is missing from `config.json`; for `cflm_p1.json` keys, the values listed are those in the file:

| Section.Key | Value in Example | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `-500.0` (uses the bias voltage in the device file when `null`) | $\text{V}$ | Reverse bias voltage shared by all 24 pads |
| `field.irradiation_flux` | `null` (uses the irradiation fluence in the device file, or `0` if the device file has no irradiation block) | $\text{cm}^{-2}$ | Irradiation fluence shared by all 24 pads ($1\ \text{MeV}$ neutron-equivalent fluence) |
| `current.plots` | `0` | bunches | Number of leading bunches with deposition per pad position for which carrier drift path and current plots are drawn |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `readout.sheet_resistance` | `null` (uses the resistive-layer sheet resistance in the device file) | $\Omega$ | Overrides the resistive-layer sheet resistance for pad devices containing `resistive_layer` |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | Threshold-crossing level for extracting `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | Amplitude threshold for cluster seed channels; events recorded by `trigger` in which a seed is found are marked as `selected` (whether an event is recorded is decided by `trigger`) |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` | `null` (inherits `pulse_edge` written by `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` |
| `pipe`, `vacuum`, `world` (`cflm_p1.json`) | `G4_Cu` ($R_{\min}=28$, $R_{\max}=31$, $Z=700\ \text{mm}$), `G4_Galactic`, `"G4_AIR"` | $\text{mm}$, $\text{deg}$ | Copper beam pipe, interior vacuum cylinder, and world material definitions |
| `pads_from_z_mm` (`cflm_p1.json`) | `225` | $\text{mm}$ | Starting $z$ coordinate of the 24 pads along the beam direction |
| `BeamOn`, `NumofGun` (`cflm_p1.json`) | `1`, `3` | bunches, particles | Number of bunches simulated per job and number of lost electrons emitted simultaneously per bunch |
| `par_type`, `par_energy`, `par_in`, `par_direct`, `maxStep` (`cflm_p1.json`) | `"e-"`, `[21.906, 25.9726, 24.7832]`, 3 origin/direction sets, `2` | None, $\text{GeV}$, $\text{mm}$, dimensionless, $\mu\text{m}$ | Lost-electron particle type, per-particle kinetic energies, starting coordinates, momentum directions, and maximum step size inside pads |

All other parameters (naming of the 24 pad positions `I_-3_0` through `II_2_1` and the 6-row × 2-column index ranges, world cube half-side `2000 mm`, $Z$-axis rotation angle $3\pi/2\ \text{rad}$, fixed deposition-step time `0.0 s`, Fano sampling switch `fano = True`, drift time-window and time-step profiles, `ngspice` noise-analysis frequency range and `27 °C` temperature, and `200` reconstruction baseline points) are hardcoded in the source code.

## Outputs

Results are stored under `work/cflm/` (see [Architecture Overview](../architecture.md#results) for the storage layout): per-stage nodes are in `work/cflm/nodes/<stage>/<node>/` (each containing a `node.json`; one node per job from `deposit` through `reconstruction`, and one node per scan point for `analysis`), per-scan-point views are at `work/cflm/points/<point>/<stage>/<job>` (symlinks, with `points/<point>/field` and `points/<point>/analysis` each being a single symlink), the parameter table is `work/cflm/points.json`, cross-point statistics and trend plots are in `work/cflm/analysis/`, and the single-pad device's field nodes are stored under `work/<device>/field/<node>/`.

### Data and Plot Files

`<pos>` ranges over the `24` pad position names from `I_-3_0` through `II_2_1`:

| Filename | Writer Stage / Script | Content and Main Fields | Unit |
| --- | --- | --- | --- |
| `nodes/deposit/<node>/deposit.h5` | [`deposit`](../stages/deposit.md) (`src/raser_app/cflm/deposits.py`) | Energy deposition steps across all `24` pads recorded in one Geant4 run: attributes `generated_events` (equal to `BeamOn`), `recorded_events`, `generated_fraction`; datasets `event`, `count`, `detector` (`<side>_<i>_<j>`), pad-local coordinates `x`/`y`/`z`, fixed time `t = 0.0`, `e`, `pairs` | Coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, `pairs` in pairs |
| `nodes/current/<node>/current.<pos>.h5` | [`current`](../stages/current.md) | Induced current and net charge on pad `<pos>` for bunches with deposition (if that pad has no deposition, no corresponding `.h5` is written): attributes `electrodes`, `dt`; datasets `event`, `t0`, `count`, `pairs`, `sensitive_pairs`, `carriers_without_field`, `charge`, `stored`, `index`, `current` | `dt`, `t0` in $\text{s}$; `charge` in $\text{C}$; `current` in $\text{A}$ |
| `nodes/readout/<node>/readout.<pos>.h5` | [`readout`](../stages/readout.md) | Output voltage waveform on pad `<pos>` solved through the device equivalent circuit and front-end amplifier chain with frequency-domain thermal noise added (if no corresponding current file exists, no corresponding `.h5` is written): attributes `electrodes`, `dt`, `pulse_edge`, `device_circuit`; datasets `event`, `t0`, `count`, `stored`, `index`, `voltage` | `dt`, `t0` in $\text{s}$; `voltage` in $\text{V}$ |
| `nodes/digitizer/<node>/digitizer.<pos>.h5` | [`digitizer`](../stages/digitizer.md) | Digital waveform on pad `<pos>` after analog bandwidth filtering, sampling, and quantization (if no corresponding readout file exists, no corresponding `.h5` is written; see [`stages/digitizer`](../stages/digitizer.md) for the format): attributes `electrodes`, `sampling_period`, `lsb_V`, `offset_V`, `bits`, `pulse_edge`, `device`; datasets `event`, `t0`, `count`, `stored`, `index`, `clipped`, `code` | `sampling_period`, `t0` in $\text{s}$; `lsb_V`, `offset_V` in $\text{V}$; `bits` in bits; `code` dimensionless |
| `nodes/trigger/<node>/trigger.<pos>.h5` | [`trigger`](../stages/trigger.md) | Dataset `event` (`int64`) of recorded event numbers selected by the trigger condition on pad `<pos>` (if no corresponding digital waveform file exists, no corresponding `.h5` is written) | None |
| `nodes/reconstruction/<node>/reconstruction.<pos>.h5` | [`reconstruction`](../stages/reconstruction.md) | Reconstructed event feature table for pad `<pos>` from events in `digitizer.<pos>.h5` recorded by `trigger.<pos>.h5` (if no corresponding input exists, no corresponding `.h5` is written): attributes `electrodes`, `threshold`, `amplitude_threshold`, `fractions`, `edge`; datasets `event`, `selected`, `cluster_size`, `cluster_center`, `traced`, `baseline`, `noise`, `amplitude`, `above`, `ToA`, `ToT`, `CoG`, `area`, `CFD` | Voltage and thresholds $\text{V}$, time $\text{s}$, area $\text{V}\cdot\text{s}$ |
| `points/<point>/analysis/result.json`, `events.h5`, and per-point plots; `work/cflm/analysis/points.json`, `points.png` | [`analysis`](../stages/analysis.md) | Limitation: `analysis` currently only aggregates single-electrode results; multi-electrode and multi-position statistics (such as telescope residuals and per-pad summaries for cflm) are not yet implemented. | Charge $\text{C}$, voltage $\text{V}$, time $\text{s}$ |
| `nodes/current/<node>/<pos>/event_<event>/<det_model>_drift_path.pdf`, `.root` and `No_<k>electrode_basic_infor.pdf`, `.root` | [`current`](../stages/current.md) | When `current.plots > 0`, 3D/$x$-$z$ carrier drift path plots and electrode induced-current waveforms for the first `plots` bunches with deposition on each pad `<pos>` | Spatial coordinates $\mu\text{m}$, time `Time [s]`, current `Current [A]` |
| `<PosBaseName>_nx.txt`, `<PosBaseName>_px.txt` | Standalone script `cflm_spd.py` | List of secondary particles exiting the copper beam-pipe outer wall at $x = -31\ \text{mm}$ (`_nx`) and $x = +31\ \text{mm}$ (`_px`), three columns per line: `<particle_name> <z_coord> <y_coord>` | Both $z$ and $y$ coordinates in $\text{mm}$ |
