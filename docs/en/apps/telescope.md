# Telescope

Telescope describes a multi-layer tracking setup. Its project binds the
Devices used by the layers, a particle Source, the readout definitions, and a
G4Setup containing the layer placements and surrounding geometry.

## Setup

The G4Setup gives every layer its Device reference, placement, orientation,
and sensitive-volume mapping. The Source defines the incident particles. The
selected readout definitions supply the channel measurements used for hit and
cluster construction.

ACTS configuration may be attached to the Telescope setup for ACTS transport,
digitization, seeding, and track reconstruction.

## Calculation

Geant4 interaction produces energy deposits in the telescope layers. Device
response maps those deposits to readout channels. Telescope constructs hits
and clusters, fits tracks across the ordered layers, and derives per-layer
residual and resolution results. Parameter studies vary recorded setup values
while retaining the corresponding G4Setup and Device definitions.
