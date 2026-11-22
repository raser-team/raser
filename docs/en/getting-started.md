# Getting Started

This page starts from installation, runs the `HPK-Si-PiN` example in one command, examines the result of each step in chain order, and then shows how to create your own project and change parameters.

## 1. Installation

```bash
env/install_conda.sh
```

## 2. Activation

Activate the environment in a local terminal, or use the CVMFS activation script on a cluster, then check the version:

```bash
source env/setup.sh
# On a cluster:
source env/setup_cvmfs.sh

raser --version
```

## 3. First Run

```bash
raser signal HPK-Si-PiN
```

This simulates electrons emitted from an Sr90 radioactive source passing through `HPK-Si-PiN`: the electrons deposit charge in the device, the charge drifts to induce current, and the signal is amplified, sampled, triggered, and recorded, finally yielding the charge collection efficiency and the time resolution relative to the true time. All settings are written in `examples/HPK-Si-PiN/signal/config.json`, and the results are also stored under `examples/HPK-Si-PiN/`.

## 4. Results of Each Step in the Chain

This command runs through all eight stages of the chain in order. Below we inspect what each step computes in the same order.

### 4.1 field

The first time this device is used, its electric field, IV, and CV are computed and stored in `examples/HPK-Si-PiN/field/`; other experiments on this device share the same field.

![HPK-Si-PiN IV curve](images/field-iv-HPK-Si-PiN.png)

Dark current under reverse bias.

![HPK-Si-PiN CV curve](images/field-cv-HPK-Si-PiN.png)

Capacitance decreases with bias voltage and flattens out once the device is fully depleted.

![HPK-Si-PiN 200 V 1D electric field profile](images/field-efield-HPK-Si-PiN-200V.png)

Electric field along the depth of the device at `200 V`.

### 4.2 deposit and current

`deposit` uses Geant4 to compute how much energy the electrons leave in the device and where; `current` drifts those charges in the electric field and computes the induced current on the electrodes.

![HPK-Si-PiN single-event carrier drift path](images/current-drift-path-HPK-Si-PiN.png)

Drift trajectories of electrons and holes in a single event.

![HPK-Si-PiN single-event induced current](images/current-event-HPK-Si-PiN.png)

Induced current on the readout electrode for the same event: electron component, hole component, and total current.

### 4.3 readout

`readout` feeds the induced current into the device equivalent circuit and then through the front-end amplifier to compute the voltage waveform at the amplifier output. The amplifier used in this example is the SantaCruz board plus Gali52, terminated in 50 Ω:

![SantaCruz amplifier schematic](images/afe-schematic-SantaCruz.png)

Amplifier noise is also computed in this step and superimposed on the output waveform.

### 4.4 digitizer

Like an oscilloscope or digitizer board, `digitizer` samples points at a fixed sampling rate and quantizes the voltage at each point into a finite number of levels to produce a digital waveform. The sampling rate and bit depth are specified in the `digitizer` section of the configuration.

### 4.5 trigger

Like real trigger hardware, `trigger` decides which events are recorded. This example triggers on an amplitude threshold: events whose waveform crosses the threshold are recorded, and those that do not are discarded.

### 4.6 reconstruction

For each recorded event, `reconstruction` extracts these quantities from the waveform: baseline, amplitude, time of arrival (ToA), constant-fraction discrimination time (CFD), pulse area, and time over threshold.

### 4.7 analysis

`analysis` summarizes all events.

![HPK-Si-PiN charge collection efficiency distribution](images/analysis-efficiency-HPK-Si-PiN.png)

Distribution of charge collection efficiency; the dashed line is the mean.

![HPK-Si-PiN pulse amplitude distribution](images/analysis-amplitude-HPK-Si-PiN.png)

Pulse amplitude of recorded events; the dashed line is the amplitude threshold.

![HPK-Si-PiN time difference distribution and truncated Gaussian fit](images/analysis-time-difference-HPK-Si-PiN.png)

Difference between the times given by various timing methods and the true deposition time. Because simulation knows each event's true deposition time, time resolution can be computed this way; in an experiment the true time is unavailable, so measuring time resolution requires a reference device—see `timeres`.

The results of each step are organized by scan point under `examples/HPK-Si-PiN/signal/points/<point>/<stage>/`, and statistics and trend plots are placed under `examples/HPK-Si-PiN/signal/analysis/`; see [architecture.md](architecture.md#results) for how they are stored.

## 5. Creating Your Own Project

Copy the example project to `work/my-PiN` with its full configuration so that it is independent of the example thereafter, then run `signal` on your project:

```bash
raser new --from HPK-Si-PiN work/my-PiN
raser signal my-PiN
```

Results are stored in `work/my-PiN/signal/` (containing `points.json`, `nodes/`, `points/<point>/`, and `analysis/`), and the device field is stored in `work/my-PiN/field/`.

## 6. Changing Settings and Running Again

Change a single bias setting and run again; new nodes are written into `work/my-PiN/signal/nodes/`, and `work/my-PiN/signal/points.json` and the `work/my-PiN/signal/points/<point>/` views are updated:

```bash
raser signal my-PiN --set field.voltage=100
```

Scan multiple bias voltages, inspect each stage's results per point under `work/my-PiN/signal/points/voltage_100/` and `work/my-PiN/signal/points/voltage_200/`, and view trend plots under `work/my-PiN/signal/analysis/`:

```bash
raser signal my-PiN --scan field.voltage=100,200
```

![HPK-Si-PiN charge collection efficiency and time resolution vs. bias](images/analysis-points-HPK-Si-PiN.png)

Print the parameter table of `work/my-PiN` (status and node ID of each experiment, scan point, and stage):

```bash
raser status work/my-PiN
```

Without running simulation, plot only the device's own geometry, electrodes, and doping:

```bash
raser device --draw HPK-Si-PiN
```

Add `--seed <integer>` to make results reproducible (for more options and scan usage, see [cli.md](cli.md) and [lifecycle/experiments.md](lifecycle/experiments.md)).
