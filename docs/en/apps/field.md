# Field

The Field application calculates the field data of a Device. It works on a
Device project, and its results are stored under that Device project.

## Setup

Device supplies the sensor structure and its default operating state. An
invocation may specify operating-state values such as the bias voltage. The
resolved state and the Field settings together form one Field configuration.

## Calculation

The Field application calls [Core Field](../core/field.md) for the selected
calculation:

- Static field: solve up to the specified bias voltage and store the field data
- Weighting field: solve the weighting potential for each readout electrode
- IV: record the current at each voltage point
- CV: record the capacitance at each voltage point
- TCAD import: convert a TCAD result into field data of the same format

Field data is stored under `<device>/field/` by the hash of the Field
configuration, where other applications read it with the same configuration.
