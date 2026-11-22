# RASER English Documentation

RASER is full-chain simulation software for semiconductor radiation detectors, connecting device field solving, particle energy deposition, carrier drift, front-end readout, digitization, triggering, reconstruction, and statistical analysis through a single command-line interface.

## Overview

- [README.md](README.md): English documentation index.
- [getting-started.md](getting-started.md): Installing and activating the environment, running the `HPK-Si-PiN` example, inspecting results through views, and creating your own project.
- [architecture.md](architecture.md): Layout, experiment classes, projects, results, chain, components, and assets.
- [cli.md](cli.md): `raser` command dispatch, full command list, global options, and shared run arguments.

## lifecycle

- [lifecycle/experiments.md](lifecycle/experiments.md): Projects and experiment folders, `config.json`, `run.json`, `--set` and `--scan` parameter scans, and random seeds.
- [lifecycle/slices.md](lifecycle/slices.md): Stage slice dependencies, code version notices, completion markers, and `raser status` status inspection.
- [lifecycle/jobs.md](lifecycle/jobs.md): Parallel job splitting, logs, file locks, resuming, and cluster submission.

## Stages (stages)

The eight stages are ordered along the simulation chain with equal standing; see [stages/README.md](stages/README.md) for the overview (chain assembly, slice data file paths, and stage command entry points):

1. [stages/field.md](stages/field.md): `field` stage, computing the electric field, weighting field, IV/CV, and device equivalent circuit parameters in the device.
2. [stages/deposit.md](stages/deposit.md): `deposit` stage, computing particle energy deposition and ionized electron-hole pairs with Geant4.
3. [stages/current.md](stages/current.md): `current` stage, drifting carriers in the fields and computing induced currents on the electrodes.
4. [stages/readout.md](stages/readout.md): `readout` stage, feeding the current into the device equivalent circuit and front-end amplifier to obtain waveforms.
5. [stages/digitizer.md](stages/digitizer.md): `digitizer` stage, converting waveforms into digital waveforms according to the sampling and quantization of an oscilloscope or digitizer board.
6. [stages/trigger.md](stages/trigger.md): `trigger` stage, deciding which events are recorded according to the conditions of real trigger hardware.
7. [stages/reconstruction.md](stages/reconstruction.md): `reconstruction` stage, extracting hit time and amplitude from waveforms, and performing track fitting in beam tests.
8. [stages/analysis.md](stages/analysis.md): `analysis` stage, summarizing efficiency and time resolution across scan points and producing trend plots under `<experiment>/analysis/`.

## core

- [core/model.md](core/model.md): Semiconductor physical model registry, including band structure, doping, mobility, recombination, and impact ionization models.
- [core/device.md](core/device.md): Parsing of device geometry, electrode layout, and doping definitions.
- [core/field.md](core/field.md): DEVSIM electric potential, electric field, weighting field, and IV/CV solving, TCAD import, and device equivalent circuit construction.
- [core/deposit.md](core/deposit.md): Geant4 particle transport, laser absorption, and ionized electron-hole pair calculation.
- [core/current.md](core/current.md): Carrier drift, diffusion, trapping, avalanche multiplication, and Shockley-Ramo induced current calculation.
- [core/readout.md](core/readout.md): SPICE front-end circuit transient solving and noise superposition.
- [core/digitizer.md](core/digitizer.md): Waveform sampling, quantization, and digital circuit simulation.
- [core/reconstruction.md](core/reconstruction.md): Baseline subtraction, timing quantities (`ToA`, `ToT`, `CoG`, `CFD`), pulse area, and cluster reconstruction algorithms.
- [core/analysis.md](core/analysis.md): Charge collection efficiency statistics and truncated Gaussian fitting for time resolution.

## components

Components are reusable definitions stored under `raser/components/`, organized into folders by the stage that reads them:

- [components/device.md](components/device.md): Device geometry, electrodes, doping, and selected physical models.
- [components/deposit.md](components/deposit.md): Sources of incident particles: Geant4 setups, radioactive sources and beams, and lasers.
- [components/readout.md](components/readout.md): Front-end amplifiers and termination circuits.
- [components/digitizer.md](components/digitizer.md): Sampling and quantization settings of oscilloscopes and digitizer boards.
- [components/trigger.md](components/trigger.md): Trigger conditions.

## Benchmarks (bench)

Official benchmark classes all live in the `raser_bench` package; each benchmark is a Python class inheriting from the `raser` experiment base class, and its output is placed under `work/<device>/<bench>/`:

- [bench/signal.md](bench/signal.md): `raser signal`, single-device full-chain signal benchmark giving charge collection efficiency.
- [bench/timeres.md](bench/timeres.md): `raser timeres`, Time Resolution benchmark.
- [bench/tct.md](bench/tct.md): `raser tct`, Transient Current Technique benchmark scanning the laser position relative to the device.
- [bench/telescope.md](bench/telescope.md): `raser telescope`, beam telescope spatial resolution benchmark using TAICHU as the default reference device.

## Applications (apps)

Official application classes all live in the `raser_app` package; each application is a Python class inheriting from the `raser` experiment base class, and its output is placed under `work/<app>/`:

- [apps/bmos.md](apps/bmos.md): `raser bmos`, Beam Monitor Online System application.
- [apps/cflm.md](apps/cflm.md): `raser cflm`, CEPC Fast Luminosity Monitor application.
- [apps/hbf.md](apps/hbf.md): `raser hbf`, Hydrogen–Boron Fusion (p–¹¹B) application.
- [apps/pimg.md](apps/pimg.md): `raser pimg`, Proton Imaging application.

## supports

- [supports/README.md](supports/README.md): Engineering infrastructure including path resolution, output boundary checks, missing dependency notices, and process cleanup.
