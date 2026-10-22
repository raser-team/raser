# PCB concept draft

_Non-normative design note_

The `PCB` class describes a board. Its project directory stores board products
that can be reused across application scenarios.

## 🧩 Proposed responsibility

The `PCB` definition covers board identity, materials, layers, component
placement, connectivity, and the mappings needed to keep geometric and
electrical representations aligned. It owns reusable products derived from
that definition:

- board GDML
- Geant4 representations and placements of board components
- board-level analog simulation definitions and results
- board-level digital simulation definitions and results

An application may assemble these products into a detector test, irradiation,
or readout scenario. The scenario inputs, run record, and measured or simulated
response remain application-owned.

## 🗂️ Candidate artifact groups

```text
<pcb>/
├── pcb.json
├── geometry/
│   └── <gdml-and-placement-products>
├── geant4/
│   └── <component-representations>
├── analog/
│   └── <simulation-definitions-and-results>
└── digital/
    └── <simulation-definitions-and-results>
```

These names are provisional ownership groups. A future contract will settle
the file formats and define a stable component identity and mapping across PCB
nets, physical placements, Geant4 volumes, analog nodes, and digital signals.

## ❓ Open design points

- identity and revision rules for a board and its mounted components
- the shared mapping between netlist, geometry, Geant4, analog, and digital
  representations
- how a PCB references reusable ASIC products while ASIC retains their definitions
- which simulation products are invariant board assets and which belong to a
  particular application scenario
