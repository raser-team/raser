# Single-layer strip waveform reconstruction

`raser telescope joint-strip` reconstructs a signed projected slope and,
for ridge, MLP and template estimators, a transverse entrance position.
The angle is `atan(dx/dz)` in degrees. The entrance coordinate is in µm
relative to `entrance_reference_um` at the plane `entrance_z_um`.

## Device and signal preparation

The packaged `strip_ayyouby` device has three 18 µm metal strips at 20 µm
pitch and a 50 µm active depth. Its default buried Gaussian peak concentration
is 3×10¹⁶ cm⁻³, with −200 V on the back electrode. The Gaussian exponent
contains the coefficient 1/2. The concentration multiplier specifies the
implant profile. Signal gain is calculated at the selected operating point.

The usual field and signal commands generate the source waveforms. The default
MIP source crosses the sensor centre normally. The reconstruction consumes
the explicitly declared NPZ arrays described below.

~~~bash
raser field strip_ayyouby
raser field -wf strip_ayyouby
raser signal strip_ayyouby toy/MIP
~~~

Device, field, source, numerical transport and frontend settings define one
response. The waveform manifest records a SHA256 `response_id` for that
contract. Calibration and prediction require equal response and readout
contracts. A changed detector or operating point requires its own response ID and calibration.

## Input

~~~json
{
  "schema": "raser-joint-strip-dataset-v1",
  "kind": "strip",
  "response_id": "<64 lowercase hexadecimal characters>",
  "waveform_kind": "frontend_mV",
  "channels": ["1", "2", "3"],
  "positions_um": [[-20, 0], [0, 0], [20, 0]],
  "entrance_reference_um": 29,
  "entrance_z_um": 0,
  "events": [
    {"event_id": "run1-event1", "particle_id": "particle1", "waveforms": "events/event1.npz"}
  ]
}
~~~

The NPZ supplies `frontend_time_s_1` and `frontend_mV_1`, with corresponding
arrays for the other declared channels. Times are in seconds and voltages
are signed mV. The loader hashes exactly the observed channels.
The L, C and R channel IDs are `1`, `2` and `3` in increasing local x order.
Regression supports the observed subsets C, L+C, C+R and L+C+R.
The differential models use all three channels for alignment and normalization.

Separate label JSON is used during fitting and scoring.

~~~json
{
  "events": {
    "run1-event1": {
      "slopes": [0.12],
      "entrance_um": [-1.0],
      "projected_cell_crossings": ["2"]
    }
  }
}
~~~

Each physical particle and all of its readout, noise and transport variants
belong to one data partition. `particle_id` groups these variants.
For the original one-record-per-particle manifests it defaults to `event_id`.
Calibration and prediction reject overlapping event IDs, observed waveform
hashes and particle IDs.

## Regression and differential controls

~~~bash
raser telescope joint-strip calibrate --estimator ridge \
  --dataset train.json --labels train-labels.json --output ridge.npz
raser telescope joint-strip calibrate --estimator mlp \
  --dataset train.json --labels train-labels.json --output mlp.npz
raser telescope joint-strip predict \
  --dataset test.json --model mlp.npz --output prediction.json
raser telescope joint-strip evaluate \
  --dataset test.json --labels test-labels.json --model mlp.npz --output evaluation.json
~~~

`difference-peak` fits the signed extremum of R−L by least squares.
`difference-waveform` applies ridge regression to all 32 sampled differences.
Both estimate slope. `ridge` and `mlp` jointly estimate slope and entrance
offset. `--representation summary` selects 20 observables. The default
`waveform` representation retains the same 20 observables, four combined
shape moments and 32 samples per channel, giving 120 values.

The baseline window is [−10, −1] ns. The pulse window is [−0.5, 5] ns.
The default shape grid has 32 uniformly spaced samples between −0.3 and
2.5 ns relative to the half-height time of the largest valid observed pulse.
The normalizing denominator is the sum of oriented observed peak amplitudes.
Masked channels occupy zero-filled slots. Changing a readout view can change
this alignment and denominator, and requires a separately trained model.

The 20 summary values comprise six signed-lobe area fractions, three peak
fractions, two adjacent time differences, three rise times, three timing-valid
flags, log total peak amplitude, log minimum valid timing SNR and active-channel
count. The four moments are the mean and first time moment of R−L and R+L−2C.
Current signals and calibrated collected charge have distinct units from
these voltage-area fractions.

Means and standard deviations are fitted on training data. Regression inputs
are standardized and clipped at ±8, except for the peak least-squares control.
Ridge uses penalty 0.1 with an unpenalized intercept and a mean squared loss.
The MLP has 24 tanh units, two linear outputs, Adam learning rate 0.003,
batch size 64, and 220 epochs. The seed and epoch count have explicit CLI
options. The model stores its numerical parameters, feature configuration,
response contract, source-code hashes and training identities.

## Joint template and independent intervals

~~~bash
raser telescope joint-strip calibrate --estimator template \
  --dataset train.json --labels train-labels.json \
  --interval-dataset interval.json --interval-labels interval-labels.json \
  --output template.npz
raser telescope joint-strip predict \
  --dataset test.json --model template.npz --output template-prediction.json
~~~

The template accepts two or three explicitly observed channels. Its training
spans a Cartesian product of slopes and entrance positions with independent
particles at each point. It uses absolute lobe areas and a 256-sample aligned
pulse window per channel, then fits a training-only pulse PCA.
Independent interval data calibrate the 68% and 95% joint regions and a 99%
response-support cut. A strict decision requires in-support response, a single
connected 95% joint region and an interior region with respect to the
calibration boundaries. Candidate angle and position remain available when
the strict decision fails. Current integrals are reported in fC and frontend
voltage integrals in mV ns.

## Evaluation and reproducibility

Every manifest event enters the requested denominator. Output separates
waveform usability, finite candidates, model support and strict decisions.
Regression has an independently uncalibrated strict decision represented
by `null`. Template evaluation reports its accepted counts, interval coverage
and rejection reasons. Geometric crossing groups are applied during
evaluation using the supplied labels.

Candidate angular RMSE is `sqrt(mean((predicted_angle - true_angle)**2))`
over the stated candidate set. Bias, residual standard deviation, absolute
error tails and entrance-position error are reported separately.
The example runner compares methods on the intersection of candidate event
IDs within each geometric group.

The [locally generated example](../../../examples/single_strip_angle/README.md)
uses synthetic Gaussian pulses to exercise the software workflow. Its scores
describe recovery of parameters encoded in that analytic generator.
Independent physical performance claims require the associated numerical,
frontend and held-out-particle validation.
