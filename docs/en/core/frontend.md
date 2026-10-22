# Frontend

_RASER 5.0 sensor and AFE circuit simulation_

Frontend connects the induced current sources of a Device to its sensor
electrical model and the selected analog front-end (AFE). A joint circuit
solution produces the signals at the requested AFE output nodes.

## Sensor electrical inputs

The sensor electrical inputs describe the network connected to the readout
electrodes. They include bulk capacitance, inter-electrode coupling, bias
resistance, AC coupling capacitance, and the values required by the selected
sensor model.

These values may come from a Field AC calculation associated with the selected
Field configuration or from values declared by Device. The selected values and
their operating conditions are passed to sensor modelling together.

## Sensor modelling

Sensor modelling translates its electrical inputs into a circuit netlist. The
netlist exposes the readout electrodes, bias connections, and reference nodes
required by the AFE. Contact and electrode names follow the Device definition.

Inter-electrode coupling is represented inside this netlist together with the
other sensor impedances. The resulting signal distribution is therefore
evaluated under the impedance presented by the connected AFE.

A sensor netlist declares the node used by each Current source and the node
presented to each AFE channel. The resistive-sheet generator uses sheet size,
grid dimensions, sheet resistance, backplane capacitance, bias resistance,
bias-contact positions, coupling capacitance, and readout-contact positions.
These declarations generate the sheet resistors and sensor capacitors joined
to the AFE input nodes.

<!-- TODO: Define the representation of frequency-dependent Field AC results. -->

## AFE modelling

The AFE netlist defines its input impedance, feedback, transfer response,
bandwidth, noise sources, and output nodes. It may be supplied directly or
generated from a parameterized AFE definition.

Frontend also accepts a one-sided AFE output-noise spectrum. The spectrum may
come from an ngspice noise analysis or from explicit input-referred voltage,
current, flicker, transimpedance, and bandwidth values. Device capacitance
enters the input-referred calculation with the AFE parameters.

The spectrum is sampled onto the waveform frequency grid and transformed into
a real time-domain waveform. The random seed, spectral-density unit, frequency
range, mean, and any requested RMS normalization are explicit inputs.

Frontend converts each electrode current from Current into a circuit current
source while preserving its sign and time axis. Piecewise-linear sources are
used by the current ngspice route.

## Circuit assembly and solution

Frontend connects each induced current source to its sensor electrode, joins
the sensor output terminals to the corresponding AFE inputs, and applies the
configured bias and reference connections. The assembled netlist is solved in
the transient domain.

The joint solution includes the sensor coupling network, the load presented by
the AFE input, and the response of the following AFE stages. Electrode
cross-talk is obtained from this solution.

## Frontend output

Frontend returns the voltage or current waveform at each requested AFE output
node. Every waveform carries its time samples, numerical unit, and associated
readout electrode. These waveforms provide the analog input to the ADC and the
waveform input used by Metrics.
