# Scientific Core

_RASER 5.0 reusable scientific calculations_

Core contains the sensor definitions and calculations assembled by RASER
applications. The package-level data flow is defined in
[Architecture](../architecture.md).

## Modules

| Module | Scientific content |
| --- | --- |
| [Device](device.md) | Sensor definition, default state, geometry, contacts, readout layout, electrical quantities, and model selections |
| [Field](field.md) | Semiconductor equations, mesh generation, numerical solving, TCAD conversion, and field-data I/O |
| [Interaction](interaction.md) | Geant4 energy deposition, laser excitation, and prescribed MIP carrier creation |
| [Current](current.md) | Carrier transport, trapping, gain, and induced electrode currents |
| [Frontend](frontend.md) | Sensor electrical modelling, AFE circuit assembly, and waveform calculation |
| [Metrics](metrics.md) | Waveform measurements, electrode combination, and event statistics |

## Drafts

- [PCB](draft/pcb.md)
- [ASIC](draft/asic.md)
- [ADC](draft/adc.md)
