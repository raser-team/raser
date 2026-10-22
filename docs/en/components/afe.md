# AFE component

An AFE component selects the analog front-end used by an application. It
identifies the circuit definition, its input and output nodes, and the
parameters required to calculate its response.

[Frontend](../core/frontend.md) connects the AFE to the sensor netlist produced
from Device electrical values or Field AC results. The joint circuit contains
the electrode current sources, sensor coupling, bias and AC-coupling elements,
and the AFE input and feedback loads. The resulting waveforms therefore carry
the response of the selected sensor and front-end connection.

An AFE definition may be a reusable circuit asset owned by an ASIC or PCB
project, or a circuit definition stored for the application setup.
