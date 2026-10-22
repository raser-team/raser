# Applications

Applications describe sensor-use scenarios. Each application project selects
the reusable objects that form the setup, adds the conditions specific to the
scenario, and stores the resulting runs.

## Composition

The selected objects are recorded as typed [Components](../components/README.md).
A Device component supplies the sensor and its operating state. Source or Laser
components define the excitation. PCB, ASIC, AFE, and ADC components define the
electronics used by the measurement. A G4Setup component defines the Geant4
scene when surrounding geometry participates in the interaction.

The application passes these definitions to [Core](../core/README.md) and
records the resolved selection through [Runs](../supports/runs.md). Results that
depend on the scenario are stored in the application project.

## Application bindings

| Application | Bound components | Calculation |
| --- | --- | --- |
| [Signal](signal.md) | Device, Source, and frontend electronics | Particle interaction, induced current, and frontend waveform |
| [TCT](tct.md) | Device, Laser, and frontend electronics | Laser injection, induced current, and scan response |
| [Time resolution](timeres.md) | Device, Source, frontend electronics, ADC, and its G4Setup | Signal production and timing analysis in the time-resolution setup |
| [Charge collection](cce.md) | Device, Source, frontend electronics, ADC, and its G4Setup | Signal production and charge-distribution analysis |
| [BMOS](bmos.md) | Device, Source, frontend electronics, and its G4Setup | Beam-monitor response and amplitude distributions |
| [Lumi](lumi.md) | Device, Source, readout electronics, and its G4Setup | Luminosity-monitor transport, response, and aggregation |
| [Telescope](telescope.md) | Devices, Source, readout definitions, and its G4Setup | Multi-layer interaction and track reconstruction |

## Project data

An application project stores its component selections, named run
configurations, and run products:

```text
<application-project>/
├── components/
├── config/
└── <workflow>/
    └── <run-id>/
        ├── run.json
        ├── batch/
        └── analysis/
```

The detailed run layout is defined by [Run records](../supports/runs.md).
