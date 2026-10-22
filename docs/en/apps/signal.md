# Signal

Signal calculates the electrical response of a Device to a particle Source.
The application project binds one Device component, one Source component, and
the frontend electronics used to read the sensor.

## Setup

The Device component selects the sensor state and Field configuration. The
Source component supplies the particle definition and its incidence on the
Device Geant4 geometry. The frontend selection identifies the sensor
electrical model and the AFE, PCB, or ASIC circuit connected to its electrodes.

Run configuration supplies the event count, seed, execution mode, and any
values selected for that run. The resolved setup is recorded in `run.json`.

## Calculation

For each event, Signal performs the following calculation:

1. [Interaction](../core/interaction.md) places the Source in the Device
   Geant4 description and produces carrier populations from the deposited
   energy.
2. [Current](../core/current.md) transports the carriers through the selected
   Field data and produces an induced current source for each electrode.
3. [Frontend](../core/frontend.md) connects those sources to the sensor and
   selected electronics netlists and calculates the readout waveforms.

Signal stores interaction data, electrode currents, and frontend waveforms for
each event. Applications such as [Charge collection](cce.md) and
[Time resolution](timeres.md) may use this calculation with their own setup
and analysis definitions.
