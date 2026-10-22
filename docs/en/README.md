# RASER documentation

RASER is organized around reusable sensor definitions and applications that
place those sensors in measurement or simulation scenarios.

## Design

| Document | Subject |
| --- | --- |
| [Architecture](architecture.md) | Code layers, project types, and scientific data flow |
| [Getting started](getting-started.md) | Environment setup and first commands |
| [CLI](cli/README.md) | Command routing and project selection |

## Scientific Core

| Document | Subject |
| --- | --- |
| [Device](core/device.md) | Sensor definition, defaults, geometry, and Device project data |
| [Field](core/field.md) | Semiconductor physics, meshing, solving, conversion, and Field data |
| [Interaction](core/interaction.md) | Particle, laser, and prescribed carrier generation |
| [Current](core/current.md) | Carrier transport, gain, and induced electrode currents |
| [Frontend](core/frontend.md) | Sensor electrical model and frontend circuit calculation |
| [Metrics](core/metrics.md) | Waveform and readout observables |

PCB, ASIC, and ADC designs are maintained under
[`core/draft/`](core/draft/).

## Applications

| Document | Scenario |
| --- | --- |
| [Signal](apps/signal.md) | Particle-source response of a Device |
| [TCT](apps/tct.md) | Laser transient-current and position scans |
| [Time resolution](apps/timeres.md) | Timing measurement with its own apparatus |
| [Charge collection](apps/cce.md) | Charge measurement with its own apparatus |
| [BMOS](apps/bmos.md) | Beam-monitor response |
| [Lumi](apps/lumi.md) | Luminosity-monitor simulation |
| [Telescope](apps/telescope.md) | Multi-layer tracking and reconstruction |

The [Applications overview](apps/README.md) lists the components bound by each
scenario.

## Components

| Document | Selected object |
| --- | --- |
| [Device component](components/device.md) | Device project and application-selected sensor state |
| [PCB component](components/pcb.md) | PCB project and application-selected board definition |
| [ASIC component](components/asic.md) | ASIC project and application-selected chip definition |
| [G4Setup component](components/g4setup.md) | Application Geant4 scene and object placements |
| [AFE component](components/afe.md) | Analog front-end circuit selection |
| [ADC component](components/adc.md) | Waveform digitization selection |
| [Source components](components/source/README.md) | Beam and decay sources |
| [Laser component](components/laser.md) | Optical injection |

## Supports

| Document | Subject |
| --- | --- |
| [Supports](supports/README.md) | Shared runtime services |
| [Paths](supports/paths.md) | Project context and definition lookup |
| [Runs](supports/runs.md) | Resolved run configuration and records |
| [Jobs](supports/jobs.md) | Local and cluster execution |
| [Output](supports/output.md) | Artifact paths and writers |
