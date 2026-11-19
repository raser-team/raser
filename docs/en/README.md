# RASER English Documentation

RASER (Radiation Semiconductor, version `5.0`, Python `3.11`) is semiconductor detector simulation software. Through the command-line entry point `raser`, it connects device field solving, energy deposition, induced current calculation, readout electronics simulation, waveform reconstruction, result analysis, and experiment workflows.

## Contents

### Overview and Getting Started

- [README.md](README.md): English documentation index and one-line overview.
- [getting-started.md](getting-started.md): First run on a device (`HPK-Si-PiN`) after installing and activating the environment.
- [architecture.md](architecture.md): Source directory layers, `importlinter` dependency contracts in `pyproject.toml`, chain stages and order, slice files handed off between stages, and how experiments relate to stages.
- [cli.md](cli.md): All `raser` commands, short aliases, module registry, and common options.

### Lifecycle (`lifecycle`)

- [lifecycle/experiments.md](lifecycle/experiments.md): Experiment folders, `config.json`, `run.json`, scan points, `--set`/`--scan`, seeds, and `--same-seeds`.
- [lifecycle/slices.md](lifecycle/slices.md): Slices (`Slice`), `needs` dependencies, staleness checks, `.done` markers, reruns, and `raser status`.
- [lifecycle/jobs.md](lifecycle/jobs.md): Job splitting, log files, file locks, resuming runs, and cluster submission.

### Simulation Chain Stages (`stages`)

- [stages/README.md](stages/README.md): `src/raser/stages/chain.py`, `files.py`, `stage_commands.py`; job slice chain order, slice data file paths, and stage command entry points.
- [stages/field.md](stages/field.md): `stages/field`; commands, options, and shared slice outputs for solving device electric potential, electric field, weighting field, and IV/CV curves (or importing a single-bias TCAD field solution with `-ext` and solving the weighting potential from it).
- [stages/deposit.md](stages/deposit.md): `stages/deposit`; commands and slices for calculating energy deposition and ionized electron-hole pairs from a radioactive source or beam in the device.
- [stages/current.md](stages/current.md): `stages/current`; commands and slices for drifting carriers in solved fields and calculating induced currents on readout electrodes.
- [stages/readout.md](stages/readout.md): `stages/readout`; commands and slices for solving the device equivalent circuit and amplifier chain output voltage waveforms.
- [stages/reconstruction.md](stages/reconstruction.md): `stages/reconstruction`; commands and slices for extracting baseline, amplitude, timing quantities, pulse area, and cluster features from readout waveforms.
- [stages/analysis.md](stages/analysis.md): `stages/analysis`; summarizing charge collection efficiency and time resolution across experiment scan points and writing statistics files and plots.

### Core (`core`)

- [core/model.md](core/model.md): `core/model`; semiconductor material parameters, band structure, doping, mobility, recombination, incomplete ionization, and impact ionization formulas.
- [core/device.md](core/device.md): `core/device`; building `Detector` objects from device JSON definitions, electrode layout, capacitance calculation, and geometric boundaries.
- [core/field.md](core/field.md): `core/field`; DEVSIM potential/electric field/weighting field/IV/CV solving, TCAD import, interpolated field lookup `DevsimField`, and device equivalent SPICE circuit construction.
- [core/deposit.md](core/deposit.md): `core/deposit`; Geant4 particle transport, simplified MIP tracks, laser absorption, ionization pair calculation, and `deposit_<job>.h5` I/O.
- [core/current.md](core/current.md): `core/current`; carrier drift, diffusion, trapping, avalanche multiplication, Shockley-Ramo induced current calculation, and `current_<job>.h5` I/O.
- [core/readout.md](core/readout.md): `core/readout`; SPICE amplifier chain transient solving, thermal noise spectrum sampling, pulse edge detection, and `readout_<job>.h5` I/O.
- [core/digitizer.md](core/digitizer.md): `core/digitizer`; register incrementer digital circuit model and simulation based on `pymtl3`.
- [core/reconstruction.md](core/reconstruction.md): `core/reconstruction`; waveform pulse polarity conversion, baseline subtraction, timing quantities (`ToA`, `ToT`, `CoG`, `CFD`), pulse area, clustering algorithms, and `reconstruction_<job>.h5` I/O.
- [core/analysis.md](core/analysis.md): `core/analysis`; charge collection efficiency calculation, iterative truncated Gaussian fit core width `core_width`, and `WaveformStatistics`.

### Component Definitions (`components`)

- [components/device.md](components/device.md): `components/device`; device JSON definitions and meshing scripts for planar, strip, pixel, 3D, LGAD, and HEMT devices.
- [components/source.md](components/source.md): `components/source`; source JSON definitions for beam (`beam`), radioactive decay (`decay`), and simplified minimum ionizing particle (`toy`) sources.
- [components/laser.md](components/laser.md): `components/laser`; TCT laser injection parameter JSON definitions and silicon absorption coefficient tables.
- [components/g4setup.md](components/g4setup.md): `components/g4setup` and `components/g4macro`; Geant4 geometry environment Python scripts (`G4SETUP`) and visualization macros.
- [components/afe.md](components/afe.md): `components/afe`; front-end amplifier and termination circuit SPICE subcircuit files (`.cir`).
- [components/adc.md](components/adc.md): `components/adc`; `scope.json` containing the two keys `threshold` and `amplitude_threshold`.

### Benchmark Experiments (`bench`)

- [bench/cce.md](bench/cce.md): `raser cce`, charge collection experiment workflow.
- [bench/signal.md](bench/signal.md): `raser signal`, single-device signal simulation workflow.
- [bench/tct.md](bench/tct.md): `raser tct`, transient current technique (TCT) laser pulse simulation workflow.
- [bench/telescope.md](bench/telescope.md): `raser telescope`, beam telescope (`taichu_v1`, `taichu_v2`) spatial resolution simulation workflow.
- [bench/timeres.md](bench/timeres.md): `raser timeres`, time resolution experiment workflow.

### Specialized Applications (`apps`)

- [apps/bmos.md](apps/bmos.md): `raser bmos`, Beam Monitoring Online System (BMOS) bunch pulse simulation workflow.
- [apps/cflm.md](apps/cflm.md): `raser cflm`, CEPC Fast Luminosity Monitor (CFLM) 24-pad bunch-loss electron simulation workflow.

### Engineering Infrastructure (`supports`)

- [supports/README.md](supports/README.md): `supports`; runtime path resolution, output directory boundary checks, missing dependency exceptions, process cleanup callbacks, and memory statistics decorator.
