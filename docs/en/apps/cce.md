# Charge collection

The Charge-collection application studies the charge measured from a Device in
a defined irradiation setup. Its project binds a Device, a Source, frontend
electronics, an ADC definition, and a G4Setup for the measurement.

## Calculation

The G4Setup and Source define the particle interaction. The application uses
the [Signal](signal.md) calculation to produce carrier, current, and waveform
data for each event. [Metrics](../core/metrics.md) derives charge and amplitude
observables from the recorded channels.

Charge-collection analysis combines the event observables into distributions
and summary values. Each result retains the Device state, Field configuration,
Source, G4Setup, frontend, and ADC selected for the run.
