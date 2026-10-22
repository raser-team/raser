# ASIC concept draft

_Non-normative design note_

The `ASIC` class describes one chip across circuit and geometric simulation.
Its project directory stores products that can be referenced by PCB
definitions and application scenarios.

## 🧩 Proposed responsibility

The ASIC definition owns the identity and mappings that connect:

- circuit simulation definitions and reusable results
- physical geometry and material description
- pads, bumps, and flip-chip assembly details
- channel identities shared with the mounted PCB and sensor

Circuit behaviour and geometric form are two representations of the same ASIC.
Their ports, channels, coordinate frames, and revisions must remain traceable
to one definition.

## 🗂️ Candidate artifact groups

```text
<asic>/
├── asic.json
├── circuit/
│   └── <simulation-definitions-and-results>
├── geometry/
│   └── <geometric-products>
└── assembly/
    └── <flip-chip-and-bump-products>
```

These groups are provisional ownership categories. A future contract will
settle the serializer and API. A PCB may reference a particular ASIC
definition and compatible products, while ASIC retains their ownership.

## ❓ Open design points

- the common channel and port identity across circuit, geometry, and assembly
- version binding among ASIC, bump layout, PCB footprint, and sensor channels
- the boundary between reusable circuit characterization and scenario-specific
  readout simulation
- the runtime composition contract used by PCB and detector applications
