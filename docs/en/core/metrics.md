# Metrics

_RASER 5.0 waveform measurements and event statistics_

Metrics calculates quantities from sampled waveforms and combines electrode
measurements into event-level observables. Its inputs include the waveform
samples, their time axis, the readout layout, and the selected thresholds.

## Waveform measurements

For a waveform `V(t)`, the amplitude is its largest absolute excursion. The
time of arrival (ToA) is the leading-edge threshold crossing, and the time over
threshold (ToT) is the interval between the leading and trailing crossings.

For a constant-fraction value `f`, the CFD time satisfies

```math
|V(t_{\mathrm{CFD}})|=fA,
```

where `A` is the waveform amplitude. Linear interpolation between adjacent
samples gives the crossing time. The waveform integral is recorded as charge.

<!-- TODO: Define the conversion from Frontend waveform integral to physical charge. -->

Each electrode therefore contributes amplitude, ToA, ToT, charge, and CFD
time. The channel threshold selects electrode measurements, while the event
amplitude threshold selects events for combined observables.

## Electrode combination

Accepted electrodes are combined according to the two-axis readout layout
declared by Device. Adjacent electrodes carrying signal form a cluster. The
cluster size is the number of electrodes in that group.

Amplitude, charge, and ToT may each provide the weights `w_k` for the cluster
position

```math
\mathbf r_{\mathrm{cluster}}
=\frac{\sum_k w_k\mathbf r_k}{\sum_k w_k},
```

where `r_k` is the position of electrode `k`. A supplied interaction position
gives the corresponding reconstruction residual. Event ToA and CFD time use
the earliest accepted electrode crossing.

## Event data

The event record contains the combined ToA, ToT, amplitude, charge, CFD time,
cluster size, reconstructed position, and reconstruction residual.

Undefined timing or position values are represented explicitly in the event
record. Counts and physical zero values retain their numerical meaning.

## Statistical analysis

Waveform statistics accumulate the event records. Timing distributions provide
ToA and CFD resolution through their fitted width. Amplitude, charge, and ToT
distributions provide their fitted location and width. Cluster-size and
reconstructed-position distributions describe the spatial response.

When interaction positions are available, Metrics compares reconstructed and
input positions and forms the corresponding residual distribution. The same
event data support eta calibration between measured charge sharing and
position within the electrode pitch.

The statistical output contains event counts and the fitted parameters of each
distribution. Figures present these distributions and their fit results.
