# TCT

TCT calculates the transient response of a Device to laser injection. The
application project binds one Device component, one Laser component, and the
frontend electronics used by the TCT setup.

## Setup

The Device component selects the sensor state and Field configuration. The
Laser component supplies the absorption technique, direction, optical pulse,
focus, and spatial sampling. The frontend selection supplies the sensor and
readout circuit connected during the measurement.

A position scan adds the scan axis, positions, and the electrode responses
used for reconstruction. These values describe the TCT measurement and are
stored with its run.

## Calculation

1. Laser [Interaction](../core/interaction.md) converts the optical pulse into
   carrier populations inside the Device.
2. [Current](../core/current.md) transports those carriers through the selected
   Field data and calculates the electrode current sources.
3. [Frontend](../core/frontend.md) calculates the waveforms produced by the
   sensor and TCT electronics.
4. Position analysis combines the recorded waveforms with their injection
   positions to form response curves and position-resolution results.

Single injections and scan points use the same Device, Laser, Field, and
frontend definitions recorded for the run.
