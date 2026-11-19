# Getting Started: Environment Activation and First Run

This page explains how to activate the RASER runtime environment after installation, run the full **signal scan simulation → check status → statistical analysis** workflow with the built-in silicon planar detector `HPK-Si-PiN`, and inspect the output files and plots in each output directory.

## Activate the Runtime Environment

If the environment is not installed yet, run `env/install_conda.sh` from the repository root to set up local Conda and Python dependencies. Once installed, activate the environment each time you open a new terminal:

```bash
# Local Conda environment
source env/setup.sh

# Or on a cluster node with /cvmfs mounted / a SIF container image configured
source env/setup_cvmfs.sh
```

After activation, verify that `raser` works and view the subcommand list:

```bash
raser --version
raser --help
```

## Step 1: Run a Signal Scan Simulation (`raser signal`)

Scan bias voltages `100 V` and `200 V` on `HPK-Si-PiN`, running `2` parallel jobs per voltage (`-s 2`) with `200` valid events per job (`-evt 200`) and a fixed random seed `--seed 1`. Before the actual run, add `--dry-run` to preview the scan points and job list, then start the simulation:

```bash
raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1
```

By default, this uses the `decay/Sr90` radioactive source, the `device_alone` geometry, and the `SantaCruz+Gali52+Termination50` amplifier chain. During execution, the terminal first prints the slice and job plan for each scan point, detects that the field is not solved yet and automatically calls `raser field` to compute the required bias fields, and then finishes the five slices for each job (the absolute path prefix before `work/` is omitted below):

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
work/HPK-Si-PiN/signal/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
the field is not ready: raser field HPK-Si-PiN -bias 100.0
work/HPK-Si-PiN/field: jobs [0]
...
the field is not ready: raser field HPK-Si-PiN -bias 200.0
work/HPK-Si-PiN/field: jobs [0]
...
raser: the job ran its slices: deposit,field,current,readout,reconstruction
```

Several facts are directly visible from this run:

- **Automatic solving of the shared field**: When the `100 V` and `200 V` fields have not been computed beforehand, `raser signal` first prints `the field is not ready: raser field HPK-Si-PiN -bias 100.0` (and `200.0`), calls `raser field` itself to solve them and write to `work/HPK-Si-PiN/field/`, and then continues the signal simulation chain.
- **Location of the default bias point**: `200 V` is the default bias in the `HPK-Si-PiN` device file, so results for `200 V` go into the experiment root `work/HPK-Si-PiN/signal/seed_1/`, while `100 V` goes into `work/HPK-Si-PiN/signal/voltage_100/seed_1/`.
- **Generated and recorded event counts**: Under this geometry and source, each of the four jobs records `200` valid deposition events (job `0` at `200 V` generates `7359` events; `generated_fraction` is about `0.017`, the fraction of source emission directions simulated).

After the run finishes, inspect the outputs and plots in the following directories:

- **Shared field directory `work/HPK-Si-PiN/field/`**: Stores `run.json`, potential and carrier `.pkl` data at each bias (`0 V`, `100 V`, `200 V`), weighting fields under `weightingfield/top/`, `100.0V.undepleted.json`, `200.0V.undepleted.json`, and IV, CV, and 1D electric field distribution plots.

![HPK-Si-PiN IV curve](../cn/images/field-iv-HPK-Si-PiN.png)

Dark current (IV) curve from the reverse-bias scan, used to check device breakdown and leakage current versus voltage.

![HPK-Si-PiN CV curve](../cn/images/field-cv-HPK-Si-PiN.png)

Capacitance versus bias voltage (CV) curve, showing gradual depletion of the device with increasing reverse bias until the capacitance flattens out.

![HPK-Si-PiN 200 V 1D electric field profile](../cn/images/field-efield-HPK-Si-PiN-200V.png)

1D electric field profile along depth in `HPK-Si-PiN` at `200 V` bias.

- **Experiment directory `work/HPK-Si-PiN/signal/`**: `config.json` is written at the top level. Each scan-point seed directory contains the run record `run.json`, `batch/` (`deposit_<job>.h5`, `current_<job>.h5`, `readout_<job>.h5`, `reconstruction_<job>.h5`, `.done` markers, and `job_<job>.log`), and `plots/job_<job>/event_<event_number>/` (by default, plots for the first `100` recorded events: carrier drift path `planar_drift_path.pdf`/`.root` and electrode induced current `No_1electrode_basic_infor.pdf`/`.root`).

![HPK-Si-PiN single-event carrier drift path](../cn/images/current-drift-path-HPK-Si-PiN.png)

Carrier drift path plot for a single `HPK-Si-PiN` event (showing deposition points and electron and hole trajectories in the 3D device volume and local planar projections).

![HPK-Si-PiN single-event induced current](../cn/images/current-event-HPK-Si-PiN.png)

Induced current plot for a single `HPK-Si-PiN` event, showing electron and hole components and the total induced current over time.

## Step 2: Check Run Status (`raser status`)

Check job completion progress across scan points and slices under the experiment directory at any time:

```bash
raser status work/HPK-Si-PiN/signal
```

The output is as follows (the absolute path prefix before `work/` is omitted below):

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
work/HPK-Si-PiN/signal/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
```

The `2` jobs at both bias points show `2/2 done` across all 5 slices.

## Step 3: Statistical Analysis (`raser analysis`)

Once the jobs finish, run the analysis command (short command `raser ana`) on the experiment folder:

```bash
raser analysis work/HPK-Si-PiN/signal
```

Terminal output (the absolute path prefix before `work/` is omitted below):

```text
work/HPK-Si-PiN/signal/analysis: jobs [0]
work/HPK-Si-PiN/signal/analysis/voltage_100/result.json
work/HPK-Si-PiN/signal/analysis/result.json
```

As with the simulation directory, analysis results for the default bias `200 V` are written directly under the root `work/HPK-Si-PiN/signal/analysis/`, while results for `100 V` are written under `work/HPK-Si-PiN/signal/analysis/voltage_100/`:

- **`result.json`**: Summarizes charge collection efficiency and time resolution (in units of `s`). At `200 V`, the mean collection efficiency across all `400` recorded events is `0.9348` (spread `0.1445`), and `276` events have amplitude at or above the `10 mV` threshold, with `CFD30` time resolution `sigma` of `33.35 ps` and `sigma68` of `31.66 ps`; at `100 V`, the mean collection efficiency is `0.9195` with `257` selected events.
- **`events.h5`**: Detailed table of amplitude, baseline, noise, and timing quantities for all selected events.
- **`points.json` and `points.png`**: Multi-bias summary data and trend plot written under the `analysis/` root.
- **Single-point statistical plots**: `efficiency.png`, `amplitude.png`, `time_difference.png`, and `resolution_of_fraction.png`.

![HPK-Si-PiN charge collection efficiency distribution](../cn/images/analysis-efficiency-HPK-Si-PiN.png)

Charge collection efficiency histogram for the `400` recorded events at `200 V`; the dashed line marks the mean collection efficiency `0.9348`.

![HPK-Si-PiN pulse amplitude distribution](../cn/images/analysis-amplitude-HPK-Si-PiN.png)

Pulse amplitude histogram for the `276` selected events at `200 V` with amplitude at or above the `10 mV` threshold; the dashed line marks the amplitude threshold set for reconstruction.

![HPK-Si-PiN time difference distribution and truncated Gaussian fit](../cn/images/analysis-time-difference-HPK-Si-PiN.png)

Time difference distributions relative to the true deposition time (`truth`) and truncated Gaussian fits for `ToA`, `CoG`, and `CFD10`–`CFD90` at `200 V`, used to read out time resolutions `sigma` and `sigma68`.

![HPK-Si-PiN charge collection efficiency and time resolution vs. bias](../cn/images/analysis-points-HPK-Si-PiN.png)

Comparison of charge collection efficiency (left) and `CFD` channel time resolutions (right) between the `100 V` and `200 V` scan points.

## Practical Tips

- **Run only up to a specific stage**: To run only the first few steps of the chain, run `raser deposit|current|readout|reconstruction <target>` (short commands `dep|cur|rdo|reco`); missing upstream steps are filled in automatically.
- **Solve the field separately**: You can also run `raser field HPK-Si-PiN` in advance to solve the field at the default bias for all later experiments on the same device.
- **Preview before running**: Append `--dry-run` to any run command to preview the jobs and slice status for each scan point without starting the simulation.
- **Shorthand inside an experiment directory**: After `cd work/HPK-Si-PiN/signal`, you can run `raser -evt 200 -s 2` directly; the program automatically identifies the workflow and device from `config.json` in the current directory.

## Next Steps

- All commands and module mappings: [Command-Line Interface (`raser`)](cli.md)
- Parameter settings, scans (`--set` / `--scan`), and multi-seed management: [Experiments, Scan Points, and Seeds](lifecycle/experiments.md)
- Full parameter description of the `signal` workflow: [Single-Detector Signal Testbench](bench/signal.md)
- Chain slice reuse and file layout: [Architecture Overview](architecture.md), [Slices, Staleness Checks, and Status](lifecycle/slices.md)
- Batch jobs and cluster submission: [Jobs and Cluster Submission](lifecycle/jobs.md)
