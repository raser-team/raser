# Beam source

A Beam Source describes particles entering a Device or G4Setup. Its definition
contains the particle species, energy, entry point, direction, and spatial or
angular distribution. The application adds the event count and random seed for
the run.

Geant4 [Interaction](../../core/interaction.md) uses the Source definition and
the geometry selected by the application to generate primary particles. The
Source identity and resolved beam values are recorded in `run.json`.
