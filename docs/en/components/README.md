# Components

Components record the objects selected by an application project. Each entry
has a concrete type and contains the reference and project-level values needed
to use that object in the scenario.

## Component types

| Type | Meaning in an application project |
| --- | --- |
| [Device](device.md) | A sensor project and the sensor state selected for this scenario |
| [PCB](pcb.md) | A board project and the board definition selected for this scenario |
| [ASIC](asic.md) | A chip project and the chip definition selected for this scenario |
| [G4Setup](g4setup.md) | The Geant4 scene, placements, and sensitive-volume mappings for the scenario |
| [AFE](afe.md) | The analog front-end connected to the sensor electrical model |
| [ADC](adc.md) | The digitization definition applied to frontend waveforms |
| [Source](source/README.md) | A particle or decay source used by an Interaction |
| [Laser](laser.md) | An optical injection used by a TCT Interaction |

## Project layout

```text
<application-project>/
└── components/
    ├── device/
    ├── pcb/
    ├── asic/
    ├── g4setup/
    ├── afe/
    ├── adc/
    ├── source/
    └── laser/
```

An application binds the component types required by its setup. Named run
configuration and invocation values refine that selection through
[Run records](../supports/runs.md).

A Device, PCB, or ASIC entry refers to the project that owns the object's
definition and reusable products. The component records the state adopted by
the application project. G4Setup, Source, Laser, AFE, and ADC entries describe
the corresponding parts of the application setup or refer to reusable
definitions supplied by their owners.
