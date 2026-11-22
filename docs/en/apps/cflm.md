# CEPC Fast Luminosity Monitor (`apps/cflm`)

`cflm` (CEPC Fast Luminosity Monitor, in the `raser_app` package) simulates the signal response left in `24` detector pads mounted on both sides of the outer wall of a copper beam pipe after lost electrons from collider bunches strike the beam pipe. Centered on a single detector pad device (Si or 4H-SiC), it reads [detector components (`components/device`)](../components/device.md), the packaged copper beam-pipe and lost-electron configuration `cflm_p1.json`, and [front-end readout circuit components (`components/readout`)](../components/readout.md). A dedicated [`deposit`](../stages/deposit.md) slice runs Geant4 once to compute energy deposition across all `24` pads; then all pads share the same [`field`](../stages/field.md) shared field and follow the multi-position expansion mechanism of [`stages/chain`](../stages/README.md) to execute [`current`](../stages/current.md) (`current.<pos>`), [`readout`](../stages/readout.md) (`readout.<pos>`), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md) (`reconstruction.<pos>`), and [`analysis`](../stages/analysis.md) separately for each of the `24` pad positions `<pos>` (`I_-3_0` through `II_2_1`), outputting the induced current, readout voltage waveform, and reconstruction feature table on each pad.

## Setup and Standard Practice

### Standard Practice and Coordinate Transformation

In a circular electron-positron collider (CEPC), radiative Bhabha scattering or beam losses near the interaction region produce high-energy lost electrons that deviate from the beam envelope. These lost electrons strike the inner wall of the copper beam pipe at shallow grazing angles and initiate electromagnetic showers inside the pipe wall, with secondary electrons, positrons, and $\gamma$ photons emerging from the outer wall. The Fast Luminosity Monitor (CFLM) mounts symmetric arrays of fast radiation-hard semiconductor detector pads (such as 4H-SiC PiN diodes) on the left and right outer walls of the copper beam pipe to measure the pulse amplitude and arrival time on each pad bunch by bunch, monitoring collision luminosity and the spatial distribution of beam losses in real time.

In RASER's `src/raser/apps/cflm/cflm_p1.py` (lines 194–214) and `deposits.py` (lines 23–37), `24` detector pads of size $l_x \times l_y \times l_z$ (in $\mu\text{m}$) are arranged on both sides of the copper beam-pipe outer wall with position labels `<side>_<i>_<j>`. The center position $(x_{\text{pad}}, y_{\text{pad}}, z_{\text{pad}})$ of pad `(side, i, j)` in the global beam-pipe coordinate system (in $\mu\text{m}$) is:

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
- $(x, y, z)$: pad-local coordinates written to `deposit_<job>.h5`, $\mu\text{m}$, with $x \in [0, l_x]$, $y \in [0, l_y]$, and depth $z \in [0, l_z]$ pointing inward into the pad from the entrance surface ($z = 0$) flush against the outer copper pipe wall.

Eq. (1) is implemented by `cflmDetectorConstruction.pads` (`src/raser/apps/cflm/cflm_p1.py:194`), and Eq. (2) is implemented by `pad_frame` (`src/raser/apps/cflm/deposits.py:23`). `cflm` uses the same UCSC (`SantaCruz`) plus wideband amplifier readout chain as the 4H-SiC PIN time-resolution study in Ref. [1] (T. Yang et al., “Time Resolution of the 4H-SiC PIN Detector”, *Front. Phys.* 10 (2022) 718071, doi:10.3389/fphy.2022.718071).

### Copper Beam Pipe, 24 Pads, and Lost-Electron Configuration (`cflm_p1.json`)

`src/raser/apps/cflm/cflm_p1.json` and `cflm_p1.py` define the Geant4 beam-pipe geometry and lost-electron particle gun parameters:

- **World and copper beam pipe (`world`, `pipe`, `vacuum`)**:
  - World cube `world`: material `"G4_AIR"`, half-dimensions $2000\ \text{mm} \times 2000\ \text{mm} \times 2000\ \text{mm}$;
  - Copper beam pipe `pipe`: `G4Tubs` cylindrical tube, material `"G4_Cu"`, inner radius `Rmin = 28` $\text{mm}$, outer radius `Rmax = 31` $\text{mm}$ (wall thickness $3\ \text{mm}$), full length `Pipe_Z = 700` $\text{mm}$ (half-length $350\ \text{mm}$), starting azimuth `PipeSphi = 0` $\text{deg}$, span angle `PipeDphi = 360` $\text{deg}$, center coordinates `[0, 0, 250]` $\text{mm}$ (covering $z \in [-100, 600]\ \text{mm}$ along the beam axis);
  - Interior vacuum `vacuum`: `G4Tubs` cylinder, material `"G4_Galactic"`, inner radius `VACmin = 0` $\text{mm}$, outer radius `VACmax = 28` $\text{mm}$, full length `VAC_Z = 700` $\text{mm}$, center coordinates `[0, 0, 250]` $\text{mm}$.
- **24 detector pads (`detector_<side>_<i>_<j>`)**: on each side (`I` at $x \le -31\ \text{mm}$, `II` at $x \ge +31\ \text{mm}$), pads are arranged in $6\text{ rows} \times 2\text{ columns} = 12$ pads (`24` in total), starting along the beam direction at `pads_from_z_mm = 225` $\text{mm}$. `pad_material` supports only device material `material == "Si"` (using `"G4_Si"`) or `"SiC"` (building a `G4Material` with density $3.2\ \text{g/cm}^3$ and Si/C atomic percentages $50\% : 50\%$; any other material raises `ValueError`), with maximum step size `maxStep = 2` $\mu\text{m}$ inside each pad.
- **Lost-electron particle gun (`cflmPrimaryGeneratorAction`)**: each run simulates `BeamOn = 1` bunch (event), and each bunch emits `NumofGun = 3` lost electrons (`par_type = "e-"`) simultaneously via `G4ParticleGun`. The kinetic energy `par_energy` ($\text{GeV}$), starting position `par_in` ($\text{mm}$), and momentum direction vector `par_direct` (dimensionless direction components) of the 3 lost electrons are:

| Electron Index | Kinetic Energy `par_energy` ($\text{GeV}$) | Starting Coordinates `par_in` $[X_0, Y_0, Z_0]$ ($\text{mm}$) | Momentum Direction Vector `par_direct` $[d_x, d_y, d_z]$ |
| --- | --- | --- | --- |
| `0` | `21.906` | `[27.913, -2.7834, 98.2917]` | `[0.0321, -0.0023, 21.906]` |
| `1` | `25.9726` | `[-27.893, 2.647, 108.2917]` | `[-0.0483, 0.003, 25.9725]` |
| `2` | `24.7832` | `[27.8585, 2.8364, 78.2917]` | `[0.0434, 0.003, 24.7832]` |

Limitations: `RecordDetector` in `cflm_p1.py` records only the step-start position `point_in` and deposited energy `edep` of each deposition step and does not record the Geant4 global time; `deposits.py` therefore writes a fixed `0.0 s` for the time `t` of all deposition steps, omitting time-of-flight differences among different electrons and secondary shower particles reaching different pads. `cflm_p1.json` is always read from the packaged path and is not wired to the `--g4setup` or `source` CLI options. `raser analysis` currently reads only unsuffixed single-position files and cannot yet directly aggregate the 24 `.<pos>`-suffixed outputs of `cflm`.

### Execution Steps and Built-in Constants

Via `DEVICES = {"pad": (None, list(PADS))}` and `chain.expand(DEVICES, deposit=_deposits)` (`src/raser/apps/cflm/__init__.py:15-28`), `cflm` expands each job into `1` `deposit` slice, `1` shared `field` slice, and `current.<pos>`, `readout.<pos>`, `reconstruction.<pos>` for each of the `24` pad positions (`74` slices in total), executed in the following order:

1. **Simulate lost electrons in the bunch and write deposition across 24 pads (`deposit` slice, `deposits.deposits`)**: constructs a single-pad `Detector`, reads `apps/cflm/cflm_p1.json`, and calls `cflm_p1.simulate_bunches(g4_dic, seed, my_d)` using the Geant4 `FTFP_BERT` physics list with `G4StepLimiterPhysics`. In `bunch_deposits`, it iterates over each bunch and all `24` pads, skipping placeholder steps with `energy <= 0` (pads with no deposit are filled with `[[0, 0, 0]]` and `[0]` in `simulate_bunches`), transforms all valid steps to pad-local coordinates $(x, y, z)$ via `pad_frame` (Eq. (2)), sets `detector` to `<side>_<i>_<j>` and time `t` to `0.0` $\text{s}$, calls `ionized_pairs(event, my_d.material)` (default `fano=True`) to sample electron-hole pair counts `pairs`, and writes `batch/deposit_<job>.h5`. If no bunch has any valid deposition in any of the 24 pads (`not found.events`), it raises `Ended` to terminate the job early.
2. **Locate single-pad shared field (`field` slice)**: locates (or automatically runs `raser field` when not ready) the electric field, weighting field, and equivalent circuit parameters of the single-pad device under `work/<det_name>/field/`, shared by all 24 pad positions.
3. **24-channel carrier drift (`current.<pos>` slices)**: for each position `<pos>` (`I_-3_0` through `II_2_1`), first checks whether `deposit_<job>.h5` contains deposition steps with `detector == <pos>`; if that pad has no deposition in this job, immediately returns `{"events": 0}` to `batch/current.<pos>_<job>.done` without writing an `.h5` file. Otherwise, calls `write_induced_currents(..., detector=position)` to drift only the deposition steps belonging to that pad and writes `batch/current.<pos>_<job>.h5` (and draws plots under `plots/job_<job>_<pos>/event_<event>/` when `current.plots > 0`).
4. **24-channel electronics readout and event reconstruction (`readout.<pos>`, `reconstruction.<pos>` slices)**: for each position `<pos>`, if the corresponding upstream `.h5` file is absent, directly returns `{"events": 0}` to `.done`; otherwise runs `ngspice` to solve the front-end amplifier chain output voltage waveforms and writes `batch/readout.<pos>_<job>.h5`, then subtracts the leading `200`-point baseline to extract amplitude and timing features and writes `batch/reconstruction.<pos>_<job>.h5`.

In addition, `src/raser/apps/cflm/` contains a set of helper scripts for secondary-particle distributions that run independently of the `raser cflm` simulation chain:

- `cflm_spd.py` (reads `cflm_spd.json`: world half-side $6000\ \text{mm}$, copper pipe full length `Pipe_Z = 6000` $\text{mm}$ centered at $z = 2000\ \text{mm}$, maximum step size $1\ \text{mm}$): without detector pads present, records the particle names and $(z, y)$ crossing coordinates of secondary particles exiting the copper beam pipe through the $x = -31\ \text{mm}$ and $x = +31\ \text{mm}$ planes, writing `<PosBaseName>_nx.txt` and `<PosBaseName>_px.txt`;
- `data_file.py`, `p1_sample.py`, `spd_dis.py`, `spd_plot.py`: `data_file.py` reads `lossposition_CEPC.xlsx` and writes `src/raser/apps/cflm/input/datafile_p1.root` (the input directory is not tracked in the repository); the remaining scripts read this ROOT file or `SecondaryParticle_*_{nx,px}.txt` to sample Poisson hit counts or batch-rewrite `cflm_spd.json`, invoke `cflm_spd.main()`, and plot spatial distributions of secondary $\gamma$ and $e^-$.

The built-in constants in `cflm` are listed below:

| Constant or Fixed Item | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| `PADS` | `24` positions (`I_-3_0` through `II_2_1`) | count | `src/raser/apps/cflm/__init__.py:15`, tuple of pad positions across 2 sides (`I`, `II`) $\times$ `6` rows (`i = -3..2`) $\times$ `2` columns (`j = 0..1`) |
| Total expanded slices | `74` (`1` `deposit` + `1` `field` + `24 × 3`) | slices | `src/raser/apps/cflm/__init__.py:27`, total number of job slices expanded by `chain.expand` for the 24 pad positions |
| World cube half-side | `2000` (`cflm_p1.py`); `6000` (`cflm_spd.py`) | $\text{mm}$ | `src/raser/apps/cflm/cflm_p1.py:118-121`, `cflm_spd.py:43-46`, half-dimensions of the Geant4 world volume |
| Beam-pipe and pad rotation angle | `3 * pi / 2` (`270`) | $\text{rad}$ ($\text{deg}$) | `src/raser/apps/cflm/cflm_p1.py:98-99`, rotation angle around the $Z$ axis aligning pad local coordinates flush against both outer walls of the copper pipe |
| Geant4 `"SiC"` density and stoichiometry | `3.2`, `50 : 50` | $\text{g/cm}^3$, `%` | `src/raser/apps/cflm/cflm_p1.py:220-222`, fixed density and Si/C atomic percentages when constructing the SiC pad material |
| Fixed deposition-step time `t` | `0.0` | $\text{s}$ | `src/raser/apps/cflm/deposits.py:59`, fixed timestamp written to `deposit_<job>.h5` because `cflm_p1` deposition steps carry no timestamps |

## Stages and Components Used

### Stages

- [`deposit`](../stages/deposit.md): replaces standard single-device deposition with `src/raser/apps/cflm/deposits.py`, simulating lost-electron showers in the copper beam-pipe geometry and writing deposition steps for all 24 pads into a single `deposit_<job>.h5`.
- [`field`](../stages/field.md): solves or reuses the electric field, weighting field, and equivalent circuit parameters of a single pad device under `work/<det_name>/field/`, shared by all 24 pads.
- [`current`](../stages/current.md): expanded by position into 24 `current.<pos>` slices, each filtering deposition steps for its pad, drifting carriers in the shared field, and writing that pad's induced current.
- [`readout`](../stages/readout.md): expanded by position into 24 `readout.<pos>` slices, feeding induced currents of pads with deposits into the device equivalent circuit and front-end amplifier chain to solve output voltage waveforms with frequency-domain thermal noise superimposed.
- [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md): following the top-level design, performs digitization sampling/quantization and trigger selection on the 24 output waveforms.
- [`reconstruction`](../stages/reconstruction.md): expanded by position into 24 `reconstruction.<pos>` slices, extracting pulse amplitude, `ToA`, `ToT`, `CoG`, `area`, and `CFD` feature tables from each pad's readout waveforms.
- [`analysis`](../stages/analysis.md): following the top-level design, aggregates hit rates, collected charge, and timing responses across the pads.

### Components

- [Detector components (`components/device`)](../components/device.md): provides single-pad dimensions `l_x`, `l_y`, `l_z` ($\mu\text{m}$), material `material` (`"Si"` or `"SiC"`), doping, bias voltage, and temperature definitions (such as `NJU-PiN.json`, `HPK-Si-PiN.json`).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): the packaged `src/raser/apps/cflm/cflm_p1.json` defines the copper beam pipe, vacuum, and parameters of the 3 high-energy lost electrons.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md): provides SPICE amplifier stages and termination load subcircuits cascaded with `+` (default `SantaCruz+Gali52+Termination50`).
- [Digitizer components (`components/digitizer`)](../components/digitizer.md) and [trigger components (`components/trigger`)](../components/trigger.md): provides digitization sampling/quantization and trigger threshold definitions.

## Usage and Configuration

Following the top-level design ([Command-Line Interface](../cli.md#commands)), run the `cflm` application or scan bias voltage, front-end amplifier, and threshold parameters:

```bash
raser cflm
raser cflm NJU-PiN --scan field.voltage=-300,-500
```

Following the sectioned format in [Architecture Overview](../architecture.md#project), the configuration structure of the experiment directory `work/cflm/config.json` is:

```json
{
  "workflow": "cflm",
  "device": "NJU-PiN",
  "field": {
    "voltage": -500.0,
    "irradiation": null
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

The configuration keys users can set in the `cflm` workflow and the setup keys in `cflm_p1.json` are listed below (`src/raser/apps/cflm/__init__.py:29-49`, `cflm_p1.json:1-80`):

| Section.Key (Code Key) | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` (equivalent to `field.device.bias.voltage`) | `bias.voltage` from the device file | $\text{V}$ | Reverse bias voltage shared by all 24 pads (CLI `-vol`/`--voltage`) |
| `field.irradiation` (`irradiation`) | `None` (uses device `irradiation.irradiation_flux` if omitted, or `0` if absent) | $\text{neq/cm}^2$ | Irradiation fluence shared by all 24 pads (CLI `-irr`/`--irradiation`) |
| `current.plots` | `0` | bunches | Number of leading bunches with deposition per pad position for which carrier drift path and current plots are drawn |
| `readout.amplifier` (`amplifier`) | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` (CLI `-amp`/`--amplifier`) |
| `readout.sheet_resistance` (`sheet_resistance`) | `None` | $\Omega$ | Overrides the resistive-layer sheet resistance for pad devices containing `resistive_layer` (CLI `--sheet-resistance`) |
| `reconstruction.threshold` (`threshold`) | `10.0` | $\text{mV}$ | Threshold-crossing level for extracting `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster (CLI `-threshold`) |
| `reconstruction.amplitude_threshold` (`amplitude_threshold`) | `10.0` | $\text{mV}$ | Pulse amplitude threshold for finding cluster seeds (whether an event is recorded is decided by `trigger`) (CLI `-amplitude_threshold`) |
| `reconstruction.fractions` (`fractions`) | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | List of amplitude fractions for constant-fraction timing (`CFD`); each entry must lie in the open interval `(0, 1)` |
| `reconstruction.edge` (`edge`) | `None` (inherits `pulse_edge` written by `readout`) | None | Pulse edge direction on which thresholds act, `"rising"` or `"falling"` (CLI `--edge`) |
| `pipe`, `vacuum`, `world` (`cflm_p1.json`) | `G4_Cu` ($R_{\min}=28$, $R_{\max}=31$, $Z=700\ \text{mm}$), `G4_Galactic`, `"G4_AIR"` | $\text{mm}$, $\text{deg}$ | Copper beam pipe, interior vacuum cylinder, and world material definitions |
| `pads_from_z_mm` (`cflm_p1.json`) | `225` | $\text{mm}$ | Starting $z$ coordinate of the 24 pads along the beam direction |
| `BeamOn`, `NumofGun` (`cflm_p1.json`) | `1`, `3` | bunches, particles | Number of bunches simulated per job and number of lost electrons emitted simultaneously per bunch |
| `par_type`, `par_energy`, `par_in`, `par_direct`, `maxStep` (`cflm_p1.json`) | `"e-"`, `[21.906, 25.9726, 24.7832]`, 3 origin/direction sets, `2` | None, $\text{GeV}$, $\text{mm}$, dimensionless, $\mu\text{m}$ | Lost-electron particle type, per-particle kinetic energies, starting coordinates, momentum directions, and maximum step size inside pads |

All other parameters (naming of the 24 pad positions `I_-3_0` through `II_2_1` and the 6-row × 2-column index ranges, world cube half-side `2000 mm`, $Z$-axis rotation angle $3\pi/2\ \text{rad}$, fixed deposition-step time `0.0 s`, Fano sampling switch `fano = True`, drift time-window and time-step profiles, `ngspice` noise-analysis frequency range and `27 °C` temperature, and `200` reconstruction baseline points) are hardcoded in the source code.

## Outputs

Following the design in [Architecture Overview](../architecture.md#results), outputs of application classes are stored under `work/cflm/` (organized into `nodes/<stage>/<node>/`, `points/<point>/<stage>`, `points.json`, and `work/cflm/analysis/`).

### Data and Plot Files

`<pos>` ranges over the `24` pad position names from `I_-3_0` through `II_2_1`:

| Filename | Writer Slice / Script | Content and Main Fields | Unit |
| --- | --- | --- | --- |
| `batch/deposit_<job>.h5` | `deposit` (`apps/cflm/deposits.py`) | Energy deposition steps across all 24 pads recorded in one Geant4 run: attributes `generated_events` (equal to `BeamOn`), `recorded_events`, `generated_fraction`; datasets `event`, `count`, `detector` (`<side>_<i>_<j>`), pad-local coordinates `x`/`y`/`z`, fixed time `t = 0.0`, `e`, `pairs` | Coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, `pairs` in pairs |
| `batch/current.<pos>_<job>.h5` | [`current.<pos>`](../stages/current.md) | Induced current and net charge on pad `<pos>` for bunches with deposition (if that pad has no deposition, no `.h5` is written and `current.<pos>_<job>.done` records `{"events": 0}`): attributes `electrodes`, `dt`; datasets `event`, `t0`, `count`, `pairs`, `sensitive_pairs`, `carriers_without_field`, `charge`, `stored`, `index`, `current` | `dt`, `t0` in $\text{s}$; `charge` in $\text{C}$; `current` in $\text{A}$ |
| `batch/readout.<pos>_<job>.h5` | [`readout.<pos>`](../stages/readout.md) | Output voltage waveform on pad `<pos>` solved through the device equivalent circuit and front-end amplifier chain with frequency-domain thermal noise added (if the upstream current file is absent, no `.h5` is written and `.done` records `{"events": 0}`): attributes `electrodes`, `dt`, `pulse_edge`, `device_circuit`; datasets `event`, `t0`, `count`, `stored`, `index`, `voltage` | `dt`, `t0` in $\text{s}$; `voltage` in $\text{V}$ |
| `batch/reconstruction.<pos>_<job>.h5` | [`reconstruction.<pos>`](../stages/reconstruction.md) | Reconstructed event feature table for pad `<pos>` (if the upstream readout file is absent, no `.h5` is written and `.done` records `{"events": 0}`): attributes `threshold`, `amplitude_threshold`, `fractions`, `edge`; datasets `event`, `selected`, `cluster_size`, `cluster_center`, `traced`, `baseline`, `noise`, `amplitude`, `above`, `ToA`, `ToT`, `CoG`, `area`, `CFD` | Voltage and thresholds $\text{V}$, time $\text{s}$, area $\text{V}\cdot\text{s}$ |
| `plots/job_<job>_<pos>/event_<event>/<det_model>_drift_path.pdf`, `.root` and `No_<k>electrode_basic_infor.pdf`, `.root` | [`current.<pos>`](../stages/current.md) | When `current.plots > 0`, 3D/$x$-$z$ carrier drift path plots and electrode induced-current waveforms for the first `plots` bunches with deposition on each pad `<pos>` | Spatial coordinates $\mu\text{m}$, time `Time [s]`, current `Current [A]` |
| `<PosBaseName>_nx.txt`, `<PosBaseName>_px.txt` | Standalone script `cflm_spd.py` | List of secondary particles exiting the copper beam-pipe outer wall at $x = -31\ \text{mm}$ (`_nx`) and $x = +31\ \text{mm}$ (`_px`), three columns per line: `<particle_name> <z_coord> <y_coord>` | Both $z$ and $y$ coordinates in $\text{mm}$ |
