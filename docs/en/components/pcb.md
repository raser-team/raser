# PCB component

A PCB component binds a PCB project to an application setup. The PCB project
defines the board and owns its reusable geometric and electrical products; the
component records the board definition selected by the application.

The referenced PCB definition covers its materials, layers, component
placements, connectivity, GDML representation, Geant4 representation of board
components, and board-level analog and digital simulation definitions. The
application entry also records the placement and connections used in the
scenario.

The PCB project design is developed in the [PCB draft](../core/draft/pcb.md).
