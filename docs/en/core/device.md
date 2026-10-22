# Device

_RASER 5.0 sensor definition and project layout_

A Device describes one sensor. Its project contains `device.json`, including
the sensor's default state, and reusable data generated specifically for that
detector. Field data is kept in this project. Results that depend on a particle
source, scan, or other application scenario remain with the application.

---

## 📋 Responsibility

Device is the authority for sensor identity. Its definition contains the
information needed to decide whether two calculations use the same sensor,
together with the defaults used during application resolution. Loading
validates the relationships among coordinate mappings, contacts, the readout
array, electrical quantities, and model bindings. A coherent set forms
the runtime sensor definition; an incomplete set fails at the Device boundary.

Changing a Device definition creates a new definition revision. Choosing a
different operating state creates a resolved project or run state associated
with the existing definition revision. The Component and Runs contracts
resolve these values, and Device validates the result against `device.json`.

Device stores model bindings as part of the sensor definition. The Core module
named by a binding interprets that configuration, performs the calculation,
and owns the resulting numerical state.

The Device may be used directly with its defaults or referenced by a
[Device component](../components/device.md) in an application project.
The component supplies that project's Device state and Field values, while
`device.json` retains the canonical definition and defaults.

## 🗂️ Project layout

```text
<device>/
├── device.json
└── field/
    ├── <field-config-hash>/
    └── ...
```

`device.json` is the Device project's canonical definition.
Each directory under `field/` is named by the hash of the complete Field
configuration stored with its reusable assets. The configuration and hashing
rules are defined by [Field](field.md#configuration). Application runs remain
in the application project and reference the Device and Field configuration
they used.

## 📥 Definition contract

`device.json` provides a self-contained sensor definition. Its declarations
close against one another: sensitive volumes map into the detector-coordinate
domain, Field contact names resolve against the Device contacts, and readout
electrodes follow the declared two-axis array and electrode order. Each model
binding resolves to a complete configuration. The declared coordinate mapping
connects the separate Geant4 envelope and runtime domain.

The file also provides defaults for configuration resolution. Resolution
begins with these defaults, then applies Component and invocation replacements.
`field/` retains the complete configurations produced or imported for the
Device. `device.json` remains the source of defaults across Field production
and loading.

A [Device component](../components/device.md) replaces defaults for an
application project. A [run record](../supports/runs.md) resolves any narrower
invocation values and preserves the result. [Field](field.md) then turns the
resolved values into the configuration whose hash addresses the reusable data.

## 🔲 Readout geometry

The readout surface uses two orthogonal indexing axes. Pad, strip, and pixel
layouts share one two-axis array contract:

| Readout layout | Array contract |
| --- | --- |
| Pad | A `1 × 1` array |
| Strip | A `read_ele_num × 1` or `1 × read_ele_num` array with pitch on the segmented axis |
| Pixel | An `x_ele_num × y_ele_num` array with pitches `p_x` and `p_y` |

Gain devices add an explicit avalanche model and gain-region definition.
Devices with multidimensional Field data add contact geometry and the
corresponding mesh. They use the same ordered `(x, y)` readout array.

## 📐 Geometry, units, and coordinates

| Value | Unit or convention |
| --- | --- |
| `l_x`, `l_y`, `l_z`, pitches, gain boundary | µm |
| Bias voltage | V |
| Temperature | K |
| Capacitance | pF |
| Runtime point | Detector coordinates `(x, y, z)` in µm |
| Runtime bounds | `0 ≤ x ≤ l_x`, `0 ≤ y ≤ l_y`, `0 ≤ z ≤ l_z` unless explicitly mapped otherwise |

Runtime bounds are the sensor domain accepted by Field and carrier transport.
The Geant4 design has an independent envelope and placement and may contain
inactive layers, support structures, or an imported assembly.

The Geant4 contract identifies sensitive volumes and maps their coordinates
into detector coordinates. Carrier transport receives mapped depositions
inside the runtime domain. The mapping explicitly states the relationship
between the Geant4 envelope and runtime bounds, including equality when it
applies.

Solver-native units and axes may differ from the Device convention. Their
conversion is part of the Field contract; downstream transport receives
detector coordinates.

## ⚙️ Runtime Device contract

Device starts from `device.json`. An application resolves component and
run-level values according to [Runs](../supports/runs.md), then asks Device to
validate the result. The runtime Device combines the unchanged sensor
definition with that resolved state.

[Field configuration](field.md#configuration) places the resolved values in
`config.json` and uses its hash as the data-directory name. Applications record
the same configuration and hash in [run.json](../supports/runs.md). Device
passes resolved values to Field. Field derives the asset directory from the
configuration hash and restores its files.

Device may declare the sensor electrical values used as pre-input for sensor
modelling. Field AC results provide values associated with a calculated Field
configuration. [Frontend](frontend.md) uses the selected values to construct
the sensor netlist.

<!-- TODO: Define resolution between Device electrical values and Field AC results. -->

Gain activation requires both an avalanche-model binding and its gain-region
geometry.

## 🔗 Downstream contract

| Consumer | Device values used |
| --- | --- |
| [Field](field.md) | Structure, material, doping, contacts, mesh, operating conditions, and Field and Damage selections |
| [Interaction](interaction.md) | Geant4 geometry, sensitive-volume mapping, material, and runtime domain |
| [Carrier and current](current.md) | Runtime domain, material, temperature, contacts, readout array, and Gain and Transport selections |
| [Frontend](frontend.md) | Sensor electrical definition, readout electrodes, and Readout selection |
| [Metrics](metrics.md) | Device identity, geometry, pitches, and electrode count |

## ✍️ Extension contract

1. Define the runtime domain and detector-coordinate convention.
2. Define the Geant4 geometry and its mapping to that domain.
3. Declare both readout-axis counts, pitches, and contacts.
4. Declare `field_source`, `field_dimension`, and the Damage, Transport, Gain,
   and Readout model selections.
5. Declare capacitance explicitly in pF.
6. Supply a default Device state and Field values.
