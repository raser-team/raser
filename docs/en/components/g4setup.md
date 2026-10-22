# G4Setup component

A G4Setup component defines the Geant4 scene used by an application. It
contains the world, materials and volumes belonging to the apparatus, the
placement and orientation of referenced Device, PCB, and ASIC geometries, and
the sensitive-volume mappings used to return depositions to those objects.

The setup also supplies the Geant4 physics selection, production and step
settings, and coordinate transforms for the scenario. A Source component is
placed in this scene by the application that owns the run.

Signal can use the Geant4 description carried by its Device. Applications
whose apparatus changes the interaction bind their own G4Setup.
