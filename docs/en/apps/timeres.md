# Time resolution

The Time-resolution application describes the source, apparatus, readout, and
analysis used for a timing measurement. Its project binds a Device, a Source,
frontend electronics, an ADC definition, and a G4Setup dedicated to the
measurement.

## Setup

The G4Setup places the Device and the surrounding materials in the experiment
geometry. The Source defines the incident particles. The frontend components
describe the sensor load and analog response, while the ADC supplies the
sampled waveform and threshold values used by timing analysis.

The selected Device state, Field configuration, Source, G4Setup, frontend, and
ADC are recorded together for each run.

## Calculation

Time resolution uses the [Signal](signal.md) calculation to produce event
waveforms in its G4Setup. [Metrics](../core/metrics.md) extracts amplitude,
time of arrival, time over threshold, constant-fraction time, charge, and
position data from the recorded channels. The application then builds the
timing distributions and resolution results for the selected setup.
