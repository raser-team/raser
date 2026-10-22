# Source components

A Source component defines the particle input used by an application. Signal
binds a Source to the Geant4 description of its Device. Applications with a
larger apparatus bind a Source to their G4Setup.

## Families and entries

| Family | Definition |
| --- | --- |
| [Beam](beam.md) | Particle species, energy, incidence, and beam distribution |
| [Decay](decay.md) | Radioactive source and its emitted-particle distribution |

Am241, Sr90, and Fe55 are concrete Source entries within the decay family.
Their isotope-specific spectra and geometry belong to the corresponding
entries.

[Laser](../laser.md) is a separate component type because its optical parameters
enter the laser Interaction directly.
