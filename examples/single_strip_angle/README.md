# Single-layer strip angle reconstruction

This example generates 36 training and 12 evaluation particles locally, then
trains a ridge model and a 24-unit neural network. It compares C, L+C, C+R and
L+C+R readouts. The three-channel view also supplies a signed neighbour-difference
peak and a sampled-difference baseline.

## Run

With RASER installed in its Python 3.11 environment, run from the repository root.

~~~bash
python examples/single_strip_angle/run.py --output work/single-strip-example
~~~

The new output directory contains generated NPZ waveforms and separate labels
under `data/`, trained models, predictions, evaluations and `comparison.json`.
The script checks that prediction and evaluation give identical event outputs,
then compares methods on common candidate IDs within each geometric group.
Each group retains its requested denominator, including empty groups.

## Analytic fixture

The generator is a software demonstration using three negative Gaussian pulses.
For channel side s = -1, 0, +1, the amplitude is a_s(1 + 0.06 s u) mV,
where a_s = 0.3, 1, 0.3 and u is the entrance coordinate in micrometres.
The delay is (0.9 + 0.5 s q) ns, where q = dx/dz. The pulse width is 0.16 ns.
Independent Gaussian noise has standard deviation 0.0004 mV per sample.
The time grid covers -12 to 8 ns with 1001 samples.

Training uses the Cartesian grid q = -0.45, 0, 0.45 and u = -5, 0, 5 um,
with four independent noise draws per point. Evaluation samples q uniformly
between -0.4 and 0.4 and u between -4 and 4 um using an independent random
stream. Seed 20261122 and the generator source hash are recorded locally in
`data/generation.json`. The response ID hashes the generator contract.

Crossing labels follow a straight line through a 50 um depth with 20 um cells,
centred on channel 2. They are geometry labels for grouping this fixture.
Three readout channels and one crossed cell are separate quantities.

The Gaussian formula encodes the slope in relative delays and the position in
relative amplitudes by construction. Its RMSE measures recovery of these
analytic parameters. Physical sensor performance requires detector-generated
signals and independently validated transport and electronics.

## Outputs

Ridge and network estimates are finite candidates. Their
`strict_accepted_fraction` is `null`, with independent acceptance calibration
remaining to be performed. The calibrated template workflow provides joint
angle-position regions and a strict decision, described in the
[single-layer guide](../../docs/en/apps/single-strip.md).
