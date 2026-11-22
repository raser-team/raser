# Statistical Analysis Stage (`stages/analysis`)

`src/raser/stages/analysis/` is the 8th stage of the simulation chain, invoked by `raser analysis` (short alias `raser ana`) and dispatched by the [Command-Line Interface (`raser`)](../cli.md). It reads the nodes of the [Energy Deposition Stage (`stages/deposit`)](deposit.md), [Carrier Transport and Induced Current Stage (`stages/current`)](current.md), and [Event Reconstruction Stage (`stages/reconstruction`)](reconstruction.md) at the same scan point, and calls [Statistical Analysis (`core/analysis`)](../core/analysis.md) to compute charge collection efficiency, energy resolution estimators and pulse time resolution. Each scan point's result is an `analysis` node viewed through `points/<point>/analysis`; cross-point summary tables and trend plots are written under `<experiment_folder>/analysis/`. See [Architecture Overview](../architecture.md#results) for how results are stored.

## Behavior

### Running

`raser analysis [path]` runs up through `analysis` on the experiment in the current folder or at the given path, computing any missing upstream stages automatically. Benchmark commands such as `raser signal` run the entire chain, with `analysis` as the final step.

The example below first scans two bias voltages on `HPK-Si-PiN`, with `2` jobs per point and `200` events per job (the event count per job is stored in the `deposit` section of `config.json`), and then reruns statistical analysis standalone:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --seed 1
raser analysis examples/HPK-Si-PiN/signal
```

When `HPK-Si-PiN` is not present under `work/`, the first command runs in place under `examples/HPK-Si-PiN/`, with the experiment folder `examples/HPK-Si-PiN/signal`. Along the chain, `digitizer` samples and quantizes each job's waveforms and writes `digitizer.h5`; `trigger` writes the IDs of events exceeding the amplitude threshold into `trigger.h5`, and only those events enter `reconstruction`. In the second command, all upstream node fingerprints match the previous run and are reused; the `analysis` node is likewise reused when its fingerprint matches. After each point finishes writing, its `result.json` path is printed; when the sample size is insufficient, the missing result and its reason are printed first.

### Per-Point Statistics and Distribution Plots

Each scan point aggregates all finished jobs that measured the same thing, whatever their seed, events per job and `plots`; the rule is in [Slices and Reruns](../lifecycle/slices.md). The program first computes charge collection efficiency across all events (drawing `efficiency.png` and `efficiency.pdf` when the event count is at least `2`). It then extracts the timing quantities of selected events and the earliest deposit time `truth` from single-electrode reconstruction results, writes `events.h5`, and draws `amplitude.png` and `amplitude.pdf`. Finally, it computes the core width of `time - truth` for `ToA`, `CoG`, and all `CFD*` channels, and draws `time_difference` and `resolution_of_fraction`, each as `.png` and `.pdf`.

The job completes normally when sample sizes are insufficient: if there are fewer than `2` events for efficiency, `0` events in the entire point, or fewer than `20` valid samples in any timing channel, the reason is written into the corresponding `error` field of `result.json` and the affected plots are skipped. When a job records `0` events in `deposit`, its downstream stages are skipped accordingly and it is also skipped during analysis.

Each point also gets two energy resolution estimators for each of the collected charge and the read-out amplitude (formulas in [Statistical Analysis](../core/analysis.md#energy-resolution-estimators)), written to `energy_resolution` in `result.json`: FWHM/mean of the whole sample, `resolution`, and FWHM/mean of the core samples within the median ± 5 σ_MAD, `core_resolution`, where σ_MAD = 1.4826 × the median absolute deviation and the factor `5` has no source. The collected charge is the absolute value of the algebraic sum of the net charges of the electrodes of all recorded events and does not depend on the reconstruction; the read-out amplitude is `amplitude` of the selected events, baseline subtracted, and holds only events not below the amplitude threshold, so its distribution is cut off at the lower end by the threshold. With fewer than `2` samples, or when more than half of the samples equal the median so that the core cannot be determined, the quantity gets only `events` and `error`; the other results are unaffected and the message of missing results printed at the end of the point does not mention it. Each point also writes, to `deposited_energy` in `result.json`, the number of events, the mean and the sample standard deviation (`ddof=1`, $\text{MeV}$) of the energy that all recorded events deposited in the sensitive layers (the sum of `e` over the deposit steps); with fewer than `2` events only `events` and `error`.

In multi-position timing experiments, each slot of every event recorded by `trigger` is classified into two categories according to `digitizer`'s `noise_only` flag: **S** (signal, where the slot is hit in that event and signal in its waveform) and **B** (background, where the slot is a noise-only channel in that event and crossed the threshold on noise). In `result.json` under `timing`, each slot records `signal` (the S event count) and `noise_only` (the B event count); for the inter-slot time difference $\Delta t = t_{\text{DUT}} - t_{\text{ref}}$ of each timing channel, two sets of core widths, `sigma68`, and fit errors are reported—one for events where both slots are S and one for all recorded events (S + B)—whereas time differences relative to the true deposition time are defined only for S (B has no `truth`) and use S only. `events.h5` adds one `noise_only` (`bool`) column per slot, and each $\Delta t$ subplot in `time_difference` overlays three curves—S + B (all recorded events), S, and B—with their respective event counts in the legend and the fit curve drawn for S.

In the example above (`2` jobs and `400` events per point), key results in `result.json` for the two points are:

- `200 V` (`examples/HPK-Si-PiN/signal/points/voltage_200/analysis/result.json`): across all `400` events, charge collection efficiency `mean = 0.9348` (`0.9347645480767679`), `mean_error = 0.007225`, `spread = 0.1445`; `276` selected events recorded by `trigger` with a cluster seed at or above the `10 mV` amplitude threshold (`polarity = -1.0`); `ToA` retains `241` events inside the window after `5` iteration rounds, giving `sigma = 123.99 ps` (`1.2399e-10 s`) and `sigma68 = 123.69 ps`, while `CFD30` gives `sigma = 33.35 ps` and `sigma68 = 31.66 ps`.
- `100 V` (`examples/HPK-Si-PiN/signal/points/voltage_100/analysis/result.json`): across `400` events, collection efficiency `mean = 0.9195` (`0.9194852059626839`), `mean_error = 0.008746`, `spread = 0.1749`; `257` selected events, with `CFD30` giving `sigma = 43.58 ps` and `sigma68 = 38.87 ps`.

The three distribution plots at `200 V` are shown below:

![HPK-Si-PiN charge collection efficiency distribution](../../images/analysis/efficiency-HPK-Si-PiN.png)

Histogram of charge collection efficiency for `400` events at `200 V`, with the dashed line marking the mean collection efficiency `0.9348`.

![HPK-Si-PiN pulse amplitude distribution](../../images/analysis/amplitude-HPK-Si-PiN.png)

Histogram of pulse amplitudes for the `276` selected events (recorded by `trigger` with cluster seed amplitude at or above `10 mV`) at `200 V`, with the dashed line marking the amplitude threshold.

![HPK-Si-PiN time difference distribution and truncated Gaussian fit](../../images/analysis/time-difference-HPK-Si-PiN.png)

Time-difference distributions relative to `truth`, shaded fit windows, and truncated Gaussian fit curves for `ToA`, `CoG`, and `CFD10`–`CFD90` at `200 V`.

### Cross-Point Summary and Trend Plot

When more than `1` scan point has results, the program writes `points.json` under `<experiment_folder>/analysis/`. It retains only the scan options whose values differ across points and gathers each point's efficiency and time resolution. When there is exactly `1` scan option with differing values and all of its values are non-boolean numbers, it also draws the side-by-side two-panel plot `trend.png` and `trend.pdf` sorted in ascending order of that variable.

An excerpt of `examples/HPK-Si-PiN/signal/analysis/points.json` written by the example above is shown below (`CoG` and `CFD10`–`CFD90` channels share the same structure as `ToA` and are omitted here):

```json
[
  {
    "point": "voltage_100",
    "field.voltage": 100,
    "events": 400,
    "efficiency": 0.9194852059626839,
    "efficiency_error": 0.00874583566620318,
    "selected": 257,
    "ToA": {
      "sigma68": 1.4373747887851763e-10,
      "sigma": 1.4600067149809272e-10,
      "sigma_error": 1.0200597423600211e-11
    }
  },
  {
    "point": "voltage_200",
    "field.voltage": 200,
    "events": 400,
    "efficiency": 0.9347645480767679,
    "efficiency_error": 0.007224687825783201,
    "selected": 276,
    "ToA": {
      "sigma68": 1.2368887903341034e-10,
      "sigma": 1.2399174526244709e-10,
      "sigma_error": 9.047206914503263e-12
    }
  }
]
```

The corresponding `examples/HPK-Si-PiN/signal/analysis/trend.png` is:

![HPK-Si-PiN charge collection efficiency and time resolution vs. bias voltage](../../images/analysis/trend-HPK-Si-PiN.png)

Comparison of charge collection efficiency (left) and time resolution of each `CFD` channel (right) across the `100 V` and `200 V` bias points.

Under the same conditions `energy_resolution.png` and `energy_resolution.pdf` are also written: the collected charge on the left and the read-out amplitude on the right, each showing `resolution` (black circles, solid line) and `core_resolution` (blue squares, dashed line) against the scanned variable. The rows of `points.json` of the example above also carry `energy_resolution`, which the excerpt does not show.

When more than `1` scan point has a result, two more figures are written with one curve per point: `currents.png` and `currents.pdf` show the induced current averaged over all recorded events of the point against time; `deposited_energy.png` and `deposited_energy.pdf` show the histogram of the energy that all recorded events of the point deposited in the sensitive layers, with the same `60` bins for all points. These two figures do not require exactly one numeric varying option: the curves are named with the values of the varying options of the points, and with exactly one varying option that is a number the curves are in ascending order of it and in graded colours. A point without a recorded event has no curve, and a figure that would have no curve is not drawn.

## Rules

### Nodes

The inputs of an `analysis` node are only the setting values used from the `analysis` section of `config.json` and the node IDs of `deposit`, `current`, and `reconstruction` at that scan point. Matching fingerprints are reused. Whenever any upstream node changes, the node ID changes accordingly and `analysis` recomputes a new node. Each node is locked individually and carries the `.part` suffix while partially written. When the code version differs from the one recorded in `node.json`, only a notice is printed and the result is still reused.

### Built-in Constants

The table below lists all built-in constants and hardcoded parameters used in `src/raser/stages/analysis/`:

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `PICOSECOND` | `1.0e-12` | $\text{s}$ | `plots.py`, `across_points.py`; converts time differences, fit windows, and time resolutions from $\text{s}$ to $\text{ps}$ |
| `MILLIVOLT` | `1.0e-3` | $\text{V}$ | `plots.py`; converts pulse amplitudes and amplitude thresholds from $\text{V}$ to $\text{mV}$ (`table_setting` in `timing.py` similarly divides by `1.0e-3` to convert to $\text{mV}$ and applies `round(..., 9)`) |
| `KEV_PER_MEV` | `1.0e3` | $\text{keV}/\text{MeV}$ | `across_points.py`; converts the deposited energy from $\text{MeV}$ to $\text{keV}$ |
| `EDGE_SIGN` | `{"rising": 1.0, "falling": -1.0}` | None | Imported from `raser.core.reconstruction.event_table`; used in `event_times` in `timing.py` to map the first electrode's pulse edge to polarity sign `polarity` |
| Minimum events for efficiency (literal) | `2` | events | `efficiency_spread` in `collection.py`; minimum event count required to compute mean collection efficiency, standard error of the mean, and sample standard deviation (`ddof=1`) |
| Minimum samples for energy resolution (literal) | `2` | samples | `fwhm_over_mean` in `core/analysis/resolution.py`; minimum number of samples for FWHM/mean of the collected charge and of the read-out amplitude |
| `MINIMUM_EVENTS` | `20` | events | Defined in `raser.core.analysis.resolution`; enforced when `time_widths` in `timing.py` calls `core_width`; lower bound on non-`NaN` samples per channel and on samples inside the first-round window |
| Distribution plot binning and curve sample counts (literals) | `60` bins for efficiency, amplitude and cross-point deposited-energy histograms; `64` bins within `mean ± 8 * sigma`, `200` fit curve points, and at most `3 × 4` subplots for time differences | bins / points / panels | `plots.py`, `across_points.py`; hardcoded in `draw_efficiencies`, `draw_amplitudes`, `draw_differences`, and `write_signals` |
| Figure sizes and resolutions (literals) | Single plot `(6, 4)`, `150 dpi`; time difference `(16, 10)`, `130 dpi`; cross-point plot `(11, 4)`, `150 dpi` | $\text{in}$ / $\text{dpi}$ | `plots.py`, `across_points.py`; fixed canvas sizes and resolutions for exported PNGs |

### Zero-Event Jobs and Missing Files

`job_file(folder, index, name)` in `files.py` locates `<name>.h5` in a job's `<name>` node via the view `points/<point>/<name>/<job>`. If the file exists, it is returned directly. Otherwise it reads `deposit.h5` in the same job's `deposit` node (via `read_deposits`) and counts `recorded = len(deposits.events)`:

- When `recorded == 0`, returns `None` and silently skips that zero-event job;
- When `recorded > 0`, raises:

  ```text
  FileNotFoundError: <path>: job <index> recorded <recorded> events but left no <name> file
  ```

  Cause: the job should have produced a downstream file that is missing (for example, deleted by mistake); restore the missing file.

Limitation: multi-position chains write only files with a `.<position>` suffix; `analysis` does not currently read them and raises the error above on such jobs; multi-position statistics are not yet implemented.

### Per-Point Statistics and Plotting

For each scan point, `collect` calls `write_point(jobs, <point_output_folder>)`, executing the following steps:

1. **Read and validate reconstruction tables (`point_tables`)**: Iterate `(place, (folder, index))` over `enumerate(jobs)` and call `job_file(folder, index, "reconstruction")`; skip when `None`, otherwise call `read_event_table` and append `(place, folder, index, table)` to `tables` (so `place` preserves the positional index of zero-event jobs in `jobs`). Then compute `table_setting(table)` for every table:
   ```python
   (round(table.threshold / 1.0e-3, 9), round(table.amplitude_threshold / 1.0e-3, 9), table.fractions, tuple(table.edges))
   ```
   If the set of settings across jobs has size greater than `1`, raise:
   ```text
   ValueError: the jobs of the point were reconstructed with different settings: <settings>
   ```
   Cause: jobs within the same scan point used different reconstruction parameters; rerun reconstruction with uniform settings before analyzing.
2. **Verify current files and compute per-event collection efficiency (`event_efficiencies`)**: Collection efficiency is computed over all events in the job's `current` node, without passing through trigger; the reconstruction table contains only events recorded by `trigger`, which is a subset of the events in the current file. For each `(place, folder, index, table)` in `tables`, call `job_file(folder, index, "current")` and `read_currents(path).events`, letting `numbers = {event.event for event in events}` and `rows = {int(number) for number in table.columns["event"]}`:
   - If `rows - numbers` is non-empty, raise:

     ```text
     ValueError: <path>: events <list> are in the reconstruction of the job, not in its currents
     ```

     where `<list>` is `sorted(rows - numbers)`; cause: the job's reconstruction table was not produced from this current file; rerun `current` and downstream stages for that job. Events present in the current file but absent from the reconstruction table are events not recorded by trigger, which is normal.
   - Otherwise call `collection_efficiency([event.charge for event in events], [event.pairs for event in events])` to compute the dimensionless collection efficiency of each event in the current file, concatenating all jobs into a 1D array `efficiencies` (returning an empty array when `tables` is empty).
3. **Record reconstruction parameters and compute efficiency spread (`efficiency_spread`)**: When `tables` is non-empty, write `table_setting(tables[0][3])` into `result["reconstruction"]` (both thresholds in `mV`). Count `count = len(efficiencies)`:
   - If `count < 2`, `efficiency_spread` raises `TooFewValues` with message `<count> events in the point, a mean and a spread need at least 2`. `write_point` catches it, writes `result["collection"] = {"events": count, "error": str(too_few)}`, appends `no efficiency: <too_few>` to `missing`, and skips `efficiency.png`.
   - If `count >= 2`, compute sample standard deviation `spread = float(np.std(efficiencies, ddof=1))`, mean `mean = float(np.mean(efficiencies))`, and standard error of the mean `mean_error = spread / np.sqrt(count)`, store them in `result["collection"]`, and call `plots.draw_efficiencies` to draw `efficiency.png` (`60`-bin histogram with a dashed line at the mean, `150 dpi`).
4. **Early return when the point has 0 events**: If `len(efficiencies) == 0`, write `result["timing"] = {"events": 0, "selected": 0, "error": "the jobs recorded no event"}`, append `"no time resolution: the jobs recorded no event"` to `missing`, write `result.json`, and return `"; ".join(missing)`.
5. **Extract single-electrode selected-event times and truth (`event_times`)**:
   - Limitation: `analysis` currently computes statistics only for single-electrode results; multi-electrode statistics are not yet implemented. First check every table in `tables`; if any satisfies `len(table.electrodes) > 1`, raise:

     ```text
     NotImplementedError: <len> electrodes; the time of an event with several electrodes is not settled
     ```

     Cause: `analysis` currently defines event time only for single-electrode devices.
   - For each `(place, folder, index, table)`, locate the job's deposit file `deposits` via `slice_file(folder, index, "deposit")` and build the mapping `earliest = {event.event: min(event.t) for event in read_deposits(str(deposits)).events}` (in `s`). Check every event ID `number` in `table.columns["event"]` (including unselected events); if `number not in earliest`, raise:

     ```text
     ValueError: <deposits>: event <number> is not among the deposits of the job
     ```

     Cause: the deposit file and reconstruction table of the same job do not match; clean and rerun that job.
   - Using the boolean mask `chosen = table.columns["selected"]`, extract for selected events: `job` (filled with `float(place)`), `event`, electrode `0`'s `ToA`, `ToT`, `amplitude`, `baseline`, `noise`, `CoG`, `truth` (`earliest[number]`), and `CFD<round(100 * part)>` for each constant fraction `(k, part)` (taking `rows["CFD"][chosen, 0, k]`; if two fractions round to the same integer percentage, their data are concatenated into the same-named array in order). Concatenate all jobs column-wise, compute total event count `count = sum(len(table) for *_, table in tables)`, and set polarity sign `polarity = EDGE_SIGN[tables[0][3].edges[0]]`.
6. **Write `events.h5` and amplitude histogram**: Create `events.h5`, converting `job` and `event` to `int64` and keeping all other columns as `float64` in identically named 1D datasets. Initialize `result["timing"] = {"events": count, "selected": len(times["truth"]), "polarity": polarity}`, and call `plots.draw_amplitudes` to draw `amplitude.png` and `amplitude.pdf` (dividing both amplitudes and `tables[0][3].amplitude_threshold` by `figures.UNIT["mV"]` to convert to `mV`, `60`-bin histogram with the legend `<n> of <N> events`, a black dashed line at the threshold with the legend `threshold <threshold> mV`).
7. **Compute per-channel time resolution and draw timing plots (`time_widths`)**: Iterate channel `name` over `["ToA", "CoG"]` followed by all `CFD*` keys in `times`:
   - Compute time difference `difference = times[name] - times["truth"]` (`s`), set `found = ~np.isnan(difference)`, call `core_width(difference[found])` (see `core/analysis` for the algorithm), and attach `"missing": int(np.sum(~found))`.
   - If any channel raises `TooFewValues` (`<len> values, fewer than 20` or `<inside> of <len> values are inside [<low>, <high>], fewer than 20`), `write_point` catches it, writes `result["timing"]["error"] = str(too_few)`, appends `no time resolution: <too_few>` to `missing`, and skips the `time_difference` and `resolution_of_fraction` figures.
   - If there are at least `20` samples but the fitting layer raises another exception (such as `ValueError: all values in the window are equal`, `ValueError: the window [<low>, <high>] is empty`, or non-convergence `ArithmeticError: the fit in [<low>, <high>] did not converge: <message>`), the exception propagates directly and aborts the job; inspect the waveforms and reconstruction thresholds at that point or increase statistics and rerun.
   - When all channels fit successfully, write `result["timing"]["times"] = widths` and draw two plots:
     - `plots.draw_differences` writes `time_difference.png` and `time_difference.pdf`: with `figures.new(3, 4)`, plots up to the first `12` channels (`ToA`, `CoG`, and the first `10` `CFD*` channels, hiding unused axes) on a `3 × 4` grid. For each channel, non-`NaN` `difference` values are divided by `figures.UNIT["ps"]` to convert to `ps`, binned into `64` uniform bins (`65` edges, filled with `figures.HISTOGRAM`) over `[mean - 8 * sigma, mean + 8 * sigma]`, shaded in light gray across the final-round window `[low, high]`, and overlaid with the normalized truncated Gaussian curve as a black solid line evaluated at `200` evenly spaced points over `[low, high]`. The horizontal axis reads `<channel> - truth [ps]`, the vertical axis `Events`, the subplot title only the channel name, and the upper left corner of each subplot (`fontsize` `9`) shows `sigma68`, `sigma ± sigma_error` and the in-window count `<window_events> of <events> events in the window`:
       $$y(x) = N_{\text{win}}\,\Delta x_{\text{bin}}\,\frac{\exp\!\left(-\frac{(x - \mu)^2}{2\sigma^2}\right)}{\sqrt{2\pi}\,\sigma \cdot \frac{1}{2}\left[\operatorname{erf}\!\left(\frac{\text{high} - \mu}{\sqrt{2}\,\sigma}\right) - \operatorname{erf}\!\left(\frac{\text{low} - \mu}{\sqrt{2}\,\sigma}\right)\right]}$$
       where $x$ is the time difference ($\text{ps}$), $\mu$ and $\sigma$ are the channel's final-round fitted `mean` and `sigma` ($\text{ps}$), $N_{\text{win}}$ is the number of events inside the final-round window `window_events` (events), $\Delta x_{\text{bin}}$ is the histogram bin width ($\text{ps}$), and $y(x)$ is the expected number of events per bin (events). The plot is saved at `130 dpi`.
     - `plots.draw_fractions` writes `resolution_of_fraction.png` and `resolution_of_fraction.pdf`: selects all `CFD*` channels, recovers each constant fraction via `int(name[3:]) / 100`, plots `sigma ± sigma_error` (`ps`) as black filled circles with error bars (legend `sigma of the Gaussian`) and `sigma68` (`ps`) as black open squares (legend `sigma68`), labels the axes `CFD fraction` and `Time resolution [ps]`, and sets the lower y-axis limit to `0`.
8. **Persist per-point result and print summary**: Write `result.json` with 2-space indentation and return `"; ".join(missing) or None`. Back in `collect`, if the return value is not `None`, print `<point_output_folder>: <error>` first, then print the path to `result.json`, and retain that point's options and parsed `result.json` for the cross-point summary.

### Energy Resolution Estimators

After the efficiency, and before the early end of a point with `0` events, `write_point` calls `energy_spread` on `event_energies(jobs)` and stores the result in `result["deposited_energy"]`; it then calls `energy_resolution` on the collected charge of all recorded events from `event_charges(tables)` and stores the result in `result["energy_resolution"]["charge"]`; when there are recorded events it does the same for `times["amplitude"]` of the selected events and stores it in `result["energy_resolution"]["amplitude"]`. `event_charges` and `event_efficiencies` share one check: every event of the reconstruction table must be in the current file of the job, or the same `ValueError` is raised; the collected charge is taken of the events of the reconstruction table only, those the `trigger` recorded. `energy_resolution(values)` calls `mad_core_resolution` of `core/analysis` and turns only `TooFewValues` and `NoSpread` into `{"events": len(values), "error": <reason>}`; any other `ValueError`, such as non-finite values or a mean of `0`, propagates and fails the point.

### Cross-Point Summary

After all scan points are processed, if more than `1` point has results, `collect` calls `write_points(done, results, folder)`:

- Call `scanned_options(done)`: take the sorted union of `options` keys across all points and keep the list `scanned` of keys satisfying `len({json.dumps(options.get(key)) for _, options in done}) > 1`.
- Build one record row per point containing `"point"`, the current value of each varying scan option, `"events"`, `"efficiency"` (`None` if `mean` is absent), `"efficiency_error"` (`None` if `mean_error` is absent), `"selected"`, and `{"sigma68", "sigma", "sigma_error"}` (in `s`) for every channel in `timing.times` (written only when `times` exists); write `points.json` with 2-space indentation.
- Each row also gets `"energy_resolution"`: for each of `charge` and `amplitude` that has a result (no `error`), `{"resolution", "core_resolution"}`; a quantity without a result is omitted.
- Decide whether to plot: check `len(scanned) == 1` and `isinstance(row[scanned[0]], (int, float)) and not isinstance(row[scanned[0]], bool)` for every row. Return immediately if not satisfied.
- When satisfied, sort rows in ascending order of `key = scanned[0]` and create a `1 × 2` figure with `figures.new(1, 2)`: the left panel filters rows with `row["efficiency"] is not None` and plots efficiency as black dots joined by a line with error bars, vertical axis `Charge collection efficiency`; the right panel filters rows with `"ToA" in row` as `timed`, and when `timed` is non-empty takes all `CFD*` channel names from `timed[0]`, plotting `sigma / figures.UNIT["ps"]` with error bars `sigma_error / figures.UNIT["ps"]` (`ps`) per channel in the colours of `figures.series(number of channels, True)`, vertical axis `Time resolution [ps]`, and sets the lower y-axis limit to `0`; both horizontal axes carry the scan key itself. The figure is saved as `trend.png` and `trend.pdf`.
- Under the same condition, draw `energy_resolution` with `figures.new(1, 2)`: the left and right panels are `charge` and `amplitude`; each takes the rows that have a result for the quantity and plots `resolution` (black circles, solid line, legend `FWHM / mean`) and `core_resolution` (squares in the colour `figures.HISTOGRAM`, dashed line, legend `FWHM / mean of the core`) against the scan key; the horizontal axis is the scan key name, the vertical axis `Energy resolution of the charge` or `Energy resolution of the amplitude`, lower limit `0`; saved as `energy_resolution.png` and `energy_resolution.pdf`.
- Then call `write_signals(done, done_jobs, folder)` (`done_jobs` are the job lists of the points) to draw `currents` and `deposited_energy`; exactly one varying option is not required. A curve is named with `<key> = <value>` of each varying option joined with `, ` (the point name when no option varies); with exactly one varying option whose values are all non-boolean numbers the curves are in ascending order of it and take the graded colours of `figures.series(points, True)`, otherwise they keep the order of the points and take the colours of `figures.series(points, False)`.
  - `currents`: call `mean_current(jobs)` for each point. Each job's `current.h5` is read through `job_file(folder, index, "current")`; a `0`-event job that returns `None` is skipped, and `dt` differing between jobs raises `ValueError: <path>: time bins of <dt> s, those of the other jobs are <step> s wide`. The current of an event is the sum of the currents of its electrodes ($\text{A}$). The bin centres of the common time axis are `start + (j + 0.5) * dt` ($\text{s}$, counted from the generation of the primary), `start` being the earliest event `t0` of the point. An event whose `t0` is $p = (t_0 - \text{start})/\text{dt}$ bins after `start` (rounded to $10^{-9}$ bins, so that whole-bin offsets are not blurred by floating point) has, with $i = \lfloor p \rfloor$ and $f = p - i$, its current $c_k$ of bin $k$ shared in proportion to the overlap between bin $i + k$ of the common axis ($(1 - f)\,c_k$) and bin $i + k + 1$ ($f\,c_k$), which keeps the charge of the event. Where an event has no bin its current is $0$ and it still counts in the denominator: the mean current is the sum over the events divided by the number of recorded events of the point. A point without a recorded event has no curve, and with no curve no figure is drawn. Horizontal axis `Time [ns]`, vertical axis `Mean induced current [μA]`.
  - `deposited_energy`: call `event_energies(jobs)` for each point and read `deposit.h5`; each recorded event takes the sum of `e` over all its deposit steps ($\text{MeV}$; the file holds only deposits in the sensitive layers, those of all detectors are added), multiplied by `KEV_PER_MEV` into $\text{keV}$. A point with `0` events has no curve, and with no curve no figure is drawn. `np.histogram_bin_edges` takes `60` equal bins over all events of all points, and every point draws a `histtype="step"` histogram with those same edges, legend `<curve name>: <N> events`. Horizontal axis `Deposited energy [keV]`, vertical axis `Events`.

## Software Implementation

### Module and File Responsibilities

- `src/raser/stages/analysis/__init__.py`: Registers subcommand `analysis` (short alias `ana`) and implements job function `collect` (orchestrating per-point analysis and cross-point aggregation).
- `src/raser/stages/analysis/files.py`: Provides `slice_file` and `job_file` to locate upstream files of a job and inspect `deposit.h5` in that job's `deposit` node when a file is missing, distinguishing valid zero-event jobs from missing-file errors.
- `src/raser/stages/analysis/collection.py`: Provides `event_efficiencies` and `efficiency_spread`, verifying that event IDs match between current and reconstruction files, calling `collection_efficiency` to compute per-event collection efficiency, and summarizing mean, standard error of the mean, and sample standard deviation. It also provides `event_charges` (collected charge per event, sharing the event-number check with `event_efficiencies`) and `energy_resolution` (calls `mad_core_resolution` on a set of samples and turns too few samples and no core into `error`).
- `src/raser/stages/analysis/signals.py`: Provides `event_energies` (energy deposited in the sensitive layers per event), `energy_spread` (mean and sample standard deviation) and `mean_current` (the induced current averaged over all recorded events of a point, merged onto a common time axis in proportion to the overlap).
- `src/raser/stages/analysis/timing.py`: Provides `table_setting`, `point_tables`, `event_times`, `time_widths`, and the standalone summary interface `point_resolution`, handling per-point reconstruction parameter consistency checks, single-electrode checks, earliest deposit time `truth` extraction, and core-width fitting per timing channel.
- `src/raser/stages/analysis/point.py`: Provides `write_point`, chaining single-point table loading, efficiency calculation, time extraction, writing `events.h5` and `result.json`, and drawing the four single-point plots, while catching `TooFewValues` into result `error` fields.
- `src/raser/stages/analysis/plots.py`: Encapsulates `matplotlib` plotting functions for the four single-point distribution plots: `draw_efficiencies`, `draw_amplitudes`, `draw_differences`, and `draw_fractions`.
- `src/raser/stages/analysis/across_points.py`: Provides `scanned_options` and `write_points` to extract varying options across points, write `points.json`, and draw `trend` for a single numeric scan variable. It also writes the `energy_resolution` plot of the collected charge and the read-out amplitude under the same condition. It also provides `write_signals`, which writes the overlay of the mean induced currents of the points, `currents`, and that of their deposited energies, `deposited_energy`.
- Job scheduling, node reuse, and locking are handled by `src/raser/lifecycle/`.

### Core Data Structures

| Data structure | Field or element | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| Single-job reconstruction entry (element returned by `point_tables`) | `(place, folder, index, table)` | `(int, Path, int, EventTable)` | None (thresholds inside `table` are in $\text{V}$) | 0-based index of the job in `jobs`, job folder, job ID, and loaded `EventTable` |
| Reconstruction setting key (return value of `table_setting`) | `(threshold, amplitude_threshold, fractions, edge)` | `(float, float, tuple[float, ...], tuple[str, ...])` | $\text{mV}$, $\text{mV}$, None, None | Hashable 4-tuple used to validate consistency within a point (both thresholds rounded to `9` decimal places) |
| Selected-event time dict `times` (returned by `event_times`) | `job`, `event` | `ndarray` (`float64`, cast to `int64` when writing `events.h5`) | None | Job index and Geant4 event ID of each selected event |
| Selected-event time dict `times` (returned by `event_times`) | `ToA`, `ToT`, `truth`, `CoG`, `CFD<percent>` | `ndarray` (`float64`) | $\text{s}$ | Reconstructed times, time over threshold, and earliest deposit truth time of selected events |
| Selected-event time dict `times` (returned by `event_times`) | `amplitude`, `baseline`, `noise` | `ndarray` (`float64`) | $\text{V}$ | Maximum pulse amplitude above baseline, baseline mean, and baseline population standard deviation of selected events |
| Per-point result dict `result` (`point.py`) | `reconstruction`, `collection`, `energy_resolution`, `deposited_energy`, `timing` | `dict` | `reconstruction` thresholds in $\text{mV}$; `collection` dimensionless; `timing.times` time quantities in $\text{s}$ | In-memory summary structure mapping one-to-one to per-point `result.json` |
| Cross-point summary row `row` (`across_points.py`) | `point`, `<varying_scan_option>`, `events`, `efficiency`, `efficiency_error`, `selected`, `energy_resolution`, `<channel>` | `dict` | Option in its original unit; efficiency dimensionless; channel `sigma68`/`sigma`/`sigma_error` in $\text{s}$ | Dictionary mapping one-to-one to each scan-point element in `points.json` |

## Interface

### Command-Line and Run Options

`raser analysis [path]`: omits path to use the current folder, or takes a relative or absolute path such as `examples/HPK-Si-PiN/signal`. Global options and shared run parameters are documented in [Command-Line Interface](../cli.md):

| Option | Default | Meaning |
| --- | --- | --- |
| `-b` | Off | Submit jobs to the cluster queue (see [Jobs, Logs, Locks, Resuming, and Cluster Submission](../lifecycle/jobs.md) for cluster mechanics) |
| `-t` | Off | Used with `-b` to check and preview submission info only |
| `-mem` | `1` | Memory tier for cluster submission |
| `-s`, `--seed`, `--same-seeds` | See [Command-Line Interface](../cli.md) | Applied to any upstream measurement stages that need to be computed |
| `--set` | None | Modify a setting addressed as `"section.key"`, for example `--set field.voltage=100` |
| `--scan` | None | Scan a setting addressed as `"section.key"`, for example `--scan field.voltage=100,200` |
| `--dry-run` | Off | Print only the scan points, stages, and job states to be run |

The minimum event count `2` for collection efficiency, the minimum event count `20` and maximum `6` rounds for truncated Gaussian fitting, histogram bin counts and fit-curve point counts, the `3 × 4` subplot cap, and PNG resolutions are all hardcoded. The timing threshold, cluster seed amplitude threshold, constant fractions, and pulse edge direction belong to the `reconstruction` section; `analysis` reads the values recorded in `reconstruction.h5` inside the `reconstruction` node directly, and changing them updates the `reconstruction` node ID so `analysis` recomputes automatically.

### Input Files

- **`<experiment_folder>/points.json`**: Parameter table giving the node ID of each stage at every scan point.
- **`deposit.h5` in the `deposit` node**: File format documented in [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md). This stage reads only the event count `len(events)` the earliest deposit-step time `min(event.t)` ($\text{s}$) of each event, and the sum of the deposit-step energies `e` ($\text{MeV}$) of each event.
- **`current.h5` in the `current` node**: File format documented in [Carrier Drift and Induced Current (`core/current`)](../core/current.md). This stage reads per-event `event`, `charge` ($\text{C}$), and `pairs` (pairs); the cross-point current plot also reads `dt`, the `t0` ($\text{s}$) of each event and the current `current` ($\text{A}$) of each electrode.
- **`reconstruction.h5` in the `reconstruction` node**: File format documented in [Event Reconstruction (`core/reconstruction`)](../core/reconstruction.md). This stage reads attributes `electrodes`, `threshold` ($\text{V}$), `amplitude_threshold` ($\text{V}$), `fractions`, and `edge`, and datasets `event`, `selected`, `ToA`, `ToT`, `amplitude`, `baseline`, `noise`, `CoG`, and `CFD`.

### Output Files

Per-point results are written in that point's `analysis` node and accessed via `points/<point>/analysis/`; the node also contains `node.json`. Cross-point results are written under `<experiment_folder>/analysis/`.

#### `points/<point>/analysis/result.json`

One per scan point (2-space indented JSON):

| Top-level key | Subkey | Type | Unit | Write condition and meaning |
| --- | --- | --- | --- | --- |
| `reconstruction` | `threshold`, `amplitude_threshold`, `fractions`, `edge` | `float`, `float`, `list[float]`, `list[str]` | $\text{mV}$, $\text{mV}$, None, None | Written when at least `1` job has events; both thresholds rounded via `round(val / 1e-3, 9)` |
| `collection` | `events` | `int` | events | Always written; total number of events at this point |
| `collection` | `mean`, `mean_error`, `spread` | `float` | None | Written when `events >= 2`; mean charge collection efficiency, standard error of the mean, and sample standard deviation (`ddof=1`) |
| `collection` | `error` | `str` | None | Written instead of `mean`/`mean_error`/`spread` when `events < 2`, with literal text `<count> events in the point, a mean and a spread need at least 2` |
| `timing` | `events`, `selected` | `int` | events | Always written; total event count and selected event count |
| `timing` | `polarity` | `float` | None | Written when at least `1` event exists; `+1.0` for `"rising"`, `-1.0` for `"falling"` |
| `timing` | `<slot>.signal`, `<slot>.noise_only` | `int` | events | Written in multi-position timing experiments; counts of S (hit) and B (noise-only channel) among recorded events for each slot |
| `timing` | `times.<channel>` | `dict` | See meaning | Written when all channels fit successfully; `<channel>` is `"ToA"`, `"CoG"`, and each `"CFD<percent>"`, containing `events` (`int`, events), `window` (`[low, high]`, $\text{s}$), `window_events` (`int`, events), `rounds` (`int`, rounds), `mean`, `mean_error`, `sigma`, `sigma_error`, `sigma68` (all `float`, $\text{s}$), and `missing` (`int`, events, number of `NaN` selected events); in multi-position timing experiments, $\Delta t = t_{\text{DUT}} - t_{\text{ref}}$ reports two sets of core widths, `sigma68`, and fit errors—for events where both slots are S and for all recorded events (S + B)—while time differences relative to `truth` use S only |
| `timing` | `error` | `str` | None | Written as `"the jobs recorded no event"` when the point has `0` events; when events exist but any channel raises `TooFewValues`, written instead of `times` as `<len> values, fewer than 20` or `<inside> of <len> values are inside [<low>, <high>], fewer than 20` |
| `energy_resolution` | `charge` | `dict` | see meaning | Always written; `mad_core_resolution` of the collected charge ($\text{C}$, absolute value of the algebraic sum of the net charges of the electrodes) of all recorded events: `events` (count), `mean`, `sigma`, `median`, `mad_sigma`, `core_mean`, `core_sigma` ($\text{C}$), `core_events` (count), `resolution`, `core_resolution` (dimensionless); only `events` and `error` with fewer than `2` samples or when more than half of the samples equal the median |
| `energy_resolution` | `amplitude` | `dict` | see meaning | Written when the point has at least `1` recorded event; `mad_core_resolution` of the read-out amplitude of the selected events, keys as `charge`, with quantities that carry a unit in $\text{V}$; may likewise have only `events` and `error` |
| `deposited_energy` | `events`, `mean`, `std` | `int`, `float`, `float` | events, $\text{MeV}$, $\text{MeV}$ | Always written; number of events, mean and sample standard deviation (`ddof=1`) of the energy all recorded events deposited in the sensitive layers (sum of `e` over the deposit steps); with `events < 2` only `events` and `error`, the latter reading `<count> events in the point, a mean and a spread need at least 2` |

#### `points/<point>/analysis/events.h5`

Written when the scan point has at least `1` event. Contains 1D datasets for all `selected` events at that point:

| Dataset name | Shape and type | Unit | Meaning |
| --- | --- | --- | --- |
| `job` | `(selected,)`, `int64` | None | 0-based index of the event's job in the point's job list |
| `event` | `(selected,)`, `int64` | None | Geant4 event ID within its job |
| `ToA` | `(selected,)`, `float64` | $\text{s}$ | Time of arrival over threshold |
| `ToT` | `(selected,)`, `float64` | $\text{s}$ | Time over threshold |
| `amplitude` | `(selected,)`, `float64` | $\text{V}$ | Maximum pulse amplitude above baseline |
| `baseline` | `(selected,)`, `float64` | $\text{V}$ | Baseline mean |
| `noise` | `(selected,)`, `float64` | $\text{V}$ | Baseline population standard deviation |
| `truth` | `(selected,)`, `float64` | $\text{s}$ | Time of the event's earliest energy deposit step in `deposit` |
| `CoG` | `(selected,)`, `float64` | $\text{s}$ | Time center of gravity over the above-threshold interval |
| `CFD<percent>` | `(selected,)`, `float64` (multiplied in length if same-named fractions concatenate) | $\text{s}$ | Constant fraction discrimination time, where `<percent>` is `round(100 * part)` |
| `noise_only` (one column per slot for multi-position) | `(selected,)`, `bool` | None | Written in multi-position timing experiments; whether that slot is a noise-only channel in that event (`True` for B, `False` for S) |

#### `<experiment_folder>/analysis/points.json`

Written when more than `1` scan point has results (2-space indented JSON array, one object per point):

| Key | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `point` | `str` | None | Point name |
| `<varying_scan_option>` | Original option type | Original option unit | Lists only option keys whose values differ across points (in lexicographical order) |
| `events` | `int` | events | Total number of events at this point |
| `efficiency`, `efficiency_error` | `float \| null` | None | Mean collection efficiency and standard error of the mean; `null` if no efficiency result exists |
| `selected` | `int` | events | Number of selected events |
| `<channel>` (`ToA`, `CoG`, `CFD<percent>`) | `{"sigma68", "sigma", "sigma_error"}` (each `float`) | $\text{s}$ | Written when `timing.times` is present for this point |
| `energy_resolution` | `dict` | dimensionless | Always written; for each of `charge` and `amplitude` that has a result `{"resolution", "core_resolution"}`, omitted for one without |

#### Plot Outputs

| File path | Generation condition | Content | Axis units |
| --- | --- | --- | --- |
| `points/<point>/analysis/plots/efficiency.png`, `.pdf` | Event count $\ge 2$ | `60`-bin histogram of charge collection efficiency for all events with a black dashed mean line; the legend reports the event count `<N> events` and the mean `mean <mean>` | Horizontal `Charge collection efficiency` (dimensionless), vertical `Events` |
| `points/<point>/analysis/plots/amplitude.png`, `.pdf` | Event count $\ge 1$ | `60`-bin histogram of maximum pulse amplitude above baseline for selected events with a black dashed line at `amplitude_threshold`; the legend reports the selected and total counts `<n> of <N> events` and the threshold `threshold <threshold> mV` | Horizontal `Amplitude [mV]`, vertical `Events` |
| `points/<point>/analysis/plots/time_difference.png`, `.pdf` | All `timing.times` computed | Up to `3 × 4` subplots showing time-difference distributions relative to `truth` (`64` bins over `mean ± 8 * sigma`), shaded final-round fit window, and black truncated Gaussian fit curve for `ToA`, `CoG`, and the first `10` `CFD*` channels; each subplot title is the channel name and its upper left corner shows `sigma68`, `sigma` and the in-window count; in multi-position timing experiments, each $\Delta t$ subplot overlays three curves—S + B (all recorded events), S, and B—with their respective event counts in the legend and the fit curve drawn for S, while distributions relative to `truth` use S only | Horizontal `<channel> - truth [ps]`, vertical `Events` |
| `points/<point>/analysis/plots/resolution_of_fraction.png`, `.pdf` | All `timing.times` computed | Truncated Gaussian fit `sigma` (black filled circles with error bars) and `sigma68` (black open squares) versus constant fraction across all `CFD*` channels | Horizontal `CFD fraction` (dimensionless), vertical `Time resolution [ps]` |
| `<experiment_folder>/analysis/trend.png`, `.pdf` | More than `1` scan point with results, exactly `1` varying option, and all its values are non-boolean numbers | Side-by-side two-panel plot sorted ascending by the scan variable: left panel shows collection efficiency with error bars; right panel shows `sigma` with error bars for each `CFD*` channel, one line per channel | Horizontal the scan-option name; left vertical `Charge collection efficiency`, right vertical `Time resolution [ps]` |
| `<experiment_folder>/analysis/energy_resolution.png`, `.pdf` | As `trend` | In ascending order of the scanned variable, the collected charge on the left and the read-out amplitude on the right, each showing `resolution` (black circles, solid line) and `core_resolution` (blue squares, dashed line); a point without a result for the quantity is left out of its panel | Horizontal axis the scan option name; vertical axis `Energy resolution of the charge`, `Energy resolution of the amplitude` (dimensionless, lower limit `0`) |
| `<experiment_folder>/analysis/currents.png`, `.pdf` | More than `1` scan point has a result and at least one point has a recorded event | One curve per point: the induced current (sum of the currents of the electrodes) averaged over all recorded events of the point against time; input is `current.h5` in the `current` node of each job; a point without a recorded event is left out | Horizontal axis `Time [ns]` (counted from the generation of the primary, bin centres), vertical axis `Mean induced current [μA]` |
| `<experiment_folder>/analysis/deposited_energy.png`, `.pdf` | More than `1` scan point has a result and at least one point has a recorded event | One step histogram per point: the distribution of the energy all recorded events of the point deposited in the sensitive layers, `60` bins shared by all points; input is `deposit.h5` in the `deposit` node of each job; legend `<curve name>: <N> events`; a point without a recorded event is left out | Horizontal axis `Deposited energy [keV]`, vertical axis `Events` |
