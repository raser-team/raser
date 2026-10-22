# Lumi

Lumi describes a luminosity-monitor scenario. Its project binds the monitor
Devices, the incident Source, the readout electronics, and a G4Setup containing
the beam pipe, materials, and sensor placements.

## Calculation

Lumi transports the selected primary sample through its G4Setup and records
the particles reaching the monitor sensors. Device response converts those
interactions into electrode currents and readout signals. The electronics
selection converts the signals into the samples used for bunch and luminosity
aggregation.

The application stores the primary sample, transported interactions, sensor
responses, readout samples, and luminosity results under one recorded setup.
