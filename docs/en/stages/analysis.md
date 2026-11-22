# Statistical Analysis Stage (`stages/analysis`)

`src/raser/stages/analysis/` is the 8th stage of the simulation chain, invoked by `raser analysis` (short alias `raser ana`) and dispatched by the [Command-Line Interface (`raser`)](../cli.md). It reads the nodes of the [Energy Deposition Stage (`stages/deposit`)](deposit.md), [Carrier Transport and Induced Current Stage (`stages/current`)](current.md), and [Event Reconstruction Stage (`stages/reconstruction`)](reconstruction.md) at the same scan point, and calls [Statistical Analysis (`core/analysis`)](../core/analysis.md) to compute charge collection efficiency and pulse time resolution. Each scan point's result is an `analysis` node viewed through `points/<point>/analysis`; cross-point summary tables and trend plots are written under `<experiment_folder>/analysis/`. See [Architecture Overview](../architecture.md#results) for how results are stored.

## Behavior

### Running

`raser analysis [path]` runs up through `analysis` on the experiment in the current folder or at the given path, computing any missing upstream stages automatically. Benchmark commands such as `raser signal` run the entire chain, with `analysis` as the final step.

The example below first scans two bias voltages on `HPK-Si-PiN`, with `2` jobs per point and `200` events per job (the event count per job is stored in the `deposit` section of `config.json`), and then reruns statistical analysis standalone:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --seed 1
raser analysis work/HPK-Si-PiN/signal
```

In the second command, all upstream node fingerprints match the previous run and are reused; the `analysis` node is likewise reused when its fingerprint matches. After each point finishes writing, its `result.json` path is printed; when the sample size is insufficient, the missing result and its reason are printed first.

### Per-Point Statistics and Distribution Plots

Each scan point aggregates all jobs it uses. The program first computes charge collection efficiency across all events (drawing `efficiency.png` when the event count is at least `2`). It then extracts the timing quantities of selected events and the earliest deposit time `truth` from single-electrode reconstruction results, writes `events.h5`, and draws `amplitude.png`. Finally, it computes the core width of `time - truth` for `ToA`, `CoG`, and all `CFD*` channels, and draws `time_difference.png` and `resolution_of_fraction.png`.

The job completes normally when sample sizes are insufficient: if there are fewer than `2` events for efficiency, `0` events in the entire point, or fewer than `20` valid samples in any timing channel, the reason is written into the corresponding `error` field of `result.json` and the affected plots are skipped. When a job records `0` events in `deposit`, its downstream stages are skipped accordingly and it is also skipped during analysis.

In the example above (`2` jobs and `400` events per point), key results in `result.json` for the two points are:

- `200 V` (`work/HPK-Si-PiN/signal/points/voltage_200/analysis/result.json`): across all `400` events, charge collection efficiency `mean = 0.9348` (`0.9347645480767679`), `mean_error = 0.007225`, `spread = 0.1445`; `276` selected events exceed the `10 mV` amplitude threshold (`polarity = -1.0`); `ToA` retains `241` events inside the window after `5` iteration rounds, giving `sigma = 123.99 ps` (`1.2399e-10 s`) and `sigma68 = 123.69 ps`, while `CFD30` gives `sigma = 33.35 ps` and `sigma68 = 31.66 ps`.
- `100 V` (`work/HPK-Si-PiN/signal/points/voltage_100/analysis/result.json`): across `400` events, collection efficiency `mean = 0.9195` (`0.9194852059626839`), `mean_error = 0.008746`, `spread = 0.1749`; `257` selected events, with `CFD30` giving `sigma = 43.58 ps` and `sigma68 = 38.87 ps`.

The three distribution plots at `200 V` are shown below:

![HPK-Si-PiN charge collection efficiency distribution](../images/analysis-efficiency-HPK-Si-PiN.png)

Histogram of charge collection efficiency for `400` events at `200 V`, with the dashed line marking the mean collection efficiency `0.9348`.

![HPK-Si-PiN pulse amplitude distribution](../images/analysis-amplitude-HPK-Si-PiN.png)

Histogram of pulse amplitudes for the `276` selected events reaching or exceeding the `10 mV` threshold at `200 V`, with the dashed line marking the amplitude threshold.

![HPK-Si-PiN time difference distribution and truncated Gaussian fit](../images/analysis-time-difference-HPK-Si-PiN.png)

Time-difference distributions relative to `truth`, shaded fit windows, and truncated Gaussian fit curves for `ToA`, `CoG`, and `CFD10`–`CFD90` at `200 V`.

### Cross-Point Summary and Trend Plot

When more than `1` scan point has results, the program writes `points.json` under `<experiment_folder>/analysis/`. It retains only the scan options whose values differ across points and gathers each point's efficiency and time resolution. When there is exactly `1` scan option with differing values and all of its values are non-boolean numbers, it also draws the side-by-side two-panel plot `points.png` sorted in ascending order of that variable.

An excerpt of `work/HPK-Si-PiN/signal/analysis/points.json` written by the example above is shown below (`CoG` and `CFD10`–`CFD90` channels share the same structure as `ToA` and are omitted here):

```json
[
  {
    "point": "voltage_100",
    "voltage": 100,
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
    "voltage": 200,
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

The corresponding `work/HPK-Si-PiN/signal/analysis/points.png` is:

![HPK-Si-PiN charge collection efficiency and time resolution vs. bias voltage](../images/analysis-points-HPK-Si-PiN.png)

Comparison of charge collection efficiency (left) and time resolution of each `CFD` channel (right) across the `100 V` and `200 V` bias points.

## Rules

### Nodes

The inputs of an `analysis` node are only the setting values used from the `analysis` section of `config.json` and the node IDs of `deposit`, `current`, and `reconstruction` at that scan point. Matching fingerprints are reused. Whenever any upstream node changes, the node ID changes accordingly and `analysis` recomputes a new node. Each node is locked individually and carries the `.part` suffix while partially written. When the code version differs from the one recorded in `node.json`, only a notice is printed and the result is still reused.

### Built-in Constants

The table below lists all built-in constants and hardcoded parameters used in `src/raser/stages/analysis/`:

| Constant name | Value | Unit | Definition location and meaning |
| --- | --- | --- | --- |
| `PICOSECOND` | `1.0e-12` | $\text{s}$ | `plots.py`, `across_points.py`; converts time differences, fit windows, and time resolutions from $\text{s}$ to $\text{ps}$ |
| `MILLIVOLT` | `1.0e-3` | $\text{V}$ | `plots.py`; converts pulse amplitudes and amplitude thresholds from $\text{V}$ to $\text{mV}$ (`table_setting` in `timing.py` similarly divides by `1.0e-3` to convert to $\text{mV}$ and applies `round(..., 9)`) |
| `EDGE_SIGN` | `{"rising": 1.0, "falling": -1.0}` | None | Imported from `raser.core.reconstruction.event_table`; used in `event_times` in `timing.py` to map the first electrode's pulse edge to polarity sign `polarity` |
| Minimum events for efficiency (literal) | `2` | events | `efficiency_spread` in `collection.py`; minimum event count required to compute mean collection efficiency, standard error of the mean, and sample standard deviation (`ddof=1`) |
| `MINIMUM_EVENTS` | `20` | events | Defined in `raser.core.analysis.resolution`; enforced when `time_widths` in `timing.py` calls `core_width`; lower bound on non-`NaN` samples per channel and on samples inside the first-round window |
| Distribution plot binning and curve sample counts (literals) | `60` bins for efficiency and amplitude histograms; `64` bins within `mean ± 8 * sigma`, `200` fit curve points, and at most `3 × 4` subplots for time differences | bins / points / panels | `plots.py`; hardcoded in `draw_efficiencies`, `draw_amplitudes`, and `draw_differences` |
| Figure sizes and resolutions (literals) | Single plot `(6, 4)`, `150 dpi`; time difference `(16, 10)`, `130 dpi`; cross-point plot `(11, 4)`, `150 dpi` | $\text{in}$ / $\text{dpi}$ | `plots.py`, `across_points.py`; fixed canvas sizes and resolutions for exported PNGs |

### Zero-Event Jobs and Missing Files

`job_file(folder, index, name)` in `files.py` locates `<name>_<job>.h5` for a job. If the file exists, it is returned directly. Otherwise it reads `deposit_<job>.h5` of the same job (via `read_deposits`) and counts `recorded = len(deposits.events)`:

- When `recorded == 0`, returns `None` and silently skips that zero-event job;
- When `recorded > 0`, raises:

  ```text
  FileNotFoundError: <path>: job <index> recorded <recorded> events but left no <name> file
  ```

  Cause: the job should have produced a downstream file that is missing (deleted by mistake, or produced by a multi-position chain that wrote only files with a `.<position>` suffix); restore the missing file, or read the position-suffixed files directly for multi-position outputs.

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
2. **Verify current files and compute per-event collection efficiency (`event_efficiencies`)**: For each `(place, folder, index, table)` in `tables`, call `job_file(folder, index, "current")` and `read_currents(path).events`. Compare `sorted(event.event for event in events)` with `sorted(int(number) for number in table.columns["event"])`:
   - If they differ, raise:

     ```text
     ValueError: <path>: events <list> are in the currents or in the reconstruction of the job, not in both
     ```

     where `<list>` is the symmetric difference `sorted(set(numbers) ^ set(rows))`; cause: the event sets in the job's current file and reconstruction table disagree; rerun `current` and downstream stages for that job.
   - If they match, call `collection_efficiency([event.charge for event in events], [event.pairs for event in events])` to compute the dimensionless collection efficiency of each event, concatenating all jobs into a 1D array `efficiencies` (returning an empty array when `tables` is empty).
3. **Record reconstruction parameters and compute efficiency spread (`efficiency_spread`)**: When `tables` is non-empty, write `table_setting(tables[0][3])` into `result["reconstruction"]` (both thresholds in `mV`). Count `count = len(efficiencies)`:
   - If `count < 2`, `efficiency_spread` raises `TooFewValues` with message `<count> events in the point, a mean and a spread need at least 2`. `write_point` catches it, writes `result["collection"] = {"events": count, "error": str(too_few)}`, appends `no efficiency: <too_few>` to `missing`, and skips `efficiency.png`.
   - If `count >= 2`, compute sample standard deviation `spread = float(np.std(efficiencies, ddof=1))`, mean `mean = float(np.mean(efficiencies))`, and standard error of the mean `mean_error = spread / np.sqrt(count)`, store them in `result["collection"]`, and call `plots.draw_efficiencies` to draw `efficiency.png` (`60`-bin histogram with a dashed line at the mean, `150 dpi`).
4. **Early return when the point has 0 events**: If `len(efficiencies) == 0`, write `result["timing"] = {"events": 0, "selected": 0, "error": "the jobs recorded no event"}`, append `"no time resolution: the jobs recorded no event"` to `missing`, write `result.json`, and return `"; ".join(missing)`.
5. **Extract single-electrode selected-event times and truth (`event_times`)**:
   - First check every table in `tables`; if any satisfies `len(table.electrodes) > 1`, raise:

     ```text
     NotImplementedError: <len> electrodes; the time of an event with several electrodes is not settled
     ```

     Cause: this stage currently defines event time only for single-electrode devices; multi-electrode timing analysis must be performed by reading `reconstruction_<job>.h5` directly.
   - For each `(place, folder, index, table)`, locate the job's deposit file `deposits` via `slice_file(folder, index, "deposit")` and build the mapping `earliest = {event.event: min(event.t) for event in read_deposits(str(deposits)).events}` (in `s`). Check every event ID `number` in `table.columns["event"]` (including unselected events); if `number not in earliest`, raise:

     ```text
     ValueError: <deposits>: event <number> is not among the deposits of the job
     ```

     Cause: the deposit file and reconstruction table of the same job do not match; clean and rerun that job.
   - Using the boolean mask `chosen = table.columns["selected"]`, extract for selected events: `job` (filled with `float(place)`), `event`, electrode `0`'s `ToA`, `ToT`, `amplitude`, `baseline`, `noise`, `CoG`, `truth` (`earliest[number]`), and `CFD<round(100 * part)>` for each constant fraction `(k, part)` (taking `rows["CFD"][chosen, 0, k]`; if two fractions round to the same integer percentage, their data are concatenated into the same-named array in order). Concatenate all jobs column-wise, compute total event count `count = sum(len(table) for *_, table in tables)`, and set polarity sign `polarity = EDGE_SIGN[tables[0][3].edges[0]]`.
6. **Write `events.h5` and amplitude histogram**: Create `events.h5`, converting `job` and `event` to `int64` and keeping all other columns as `float64` in identically named 1D datasets. Initialize `result["timing"] = {"events": count, "selected": len(times["truth"]), "polarity": polarity}`, and call `plots.draw_amplitudes` to draw `amplitude.png` (dividing both amplitudes and `tables[0][3].amplitude_threshold` by `MILLIVOLT` to convert to `mV`, `60`-bin histogram with a dashed line at the threshold, `150 dpi`).
7. **Compute per-channel time resolution and draw timing plots (`time_widths`)**: Iterate channel `name` over `["ToA", "CoG"]` followed by all `CFD*` keys in `times`:
   - Compute time difference `difference = times[name] - times["truth"]` (`s`), set `found = ~np.isnan(difference)`, call `core_width(difference[found])` (see `core/analysis` for the algorithm), and attach `"missing": int(np.sum(~found))`.
   - If any channel raises `TooFewValues` (`<len> values, fewer than 20` or `<inside> of <len> values are inside [<low>, <high>], fewer than 20`), `write_point` catches it, writes `result["timing"]["error"] = str(too_few)`, appends `no time resolution: <too_few>` to `missing`, and skips `time_difference.png` and `resolution_of_fraction.png`.
   - If there are at least `20` samples but the fitting layer raises another exception (such as `ValueError: all values in the window are equal`, `ValueError: the window [<low>, <high>] is empty`, or non-convergence `ArithmeticError: the fit in [<low>, <high>] did not converge: <message>`), the exception propagates directly and aborts the job; inspect the waveforms and reconstruction thresholds at that point or increase statistics and rerun.
   - When all channels fit successfully, write `result["timing"]["times"] = widths` and draw two plots:
     - `plots.draw_differences` writes `time_difference.png`: plots up to the first `12` channels (`ToA`, `CoG`, and the first `10` `CFD*` channels, hiding unused axes) on a `3 × 4` grid. For each channel, non-`NaN` `difference` values are divided by `PICOSECOND` to convert to `ps`, binned into `64` uniform bins (`65` edges) over `[mean - 8 * sigma, mean + 8 * sigma]`, shaded in light gray across the final-round window `[low, high]`, and overlaid with the normalized truncated Gaussian curve evaluated at `200` evenly spaced points over `[low, high]`:
       $$y(x) = N_{\text{win}}\,\Delta x_{\text{bin}}\,\frac{\exp\!\left(-\frac{(x - \mu)^2}{2\sigma^2}\right)}{\sqrt{2\pi}\,\sigma \cdot \frac{1}{2}\left[\operatorname{erf}\!\left(\frac{\text{high} - \mu}{\sqrt{2}\,\sigma}\right) - \operatorname{erf}\!\left(\frac{\text{low} - \mu}{\sqrt{2}\,\sigma}\right)\right]}$$
       saved at `130 dpi`.
     - `plots.draw_fractions` writes `resolution_of_fraction.png`: selects all `CFD*` channels, recovers each constant fraction via `int(name[3:]) / 100`, plots `sigma ± sigma_error` (`ps`) with error bars and `sigma68` (`ps`) with open square markers, sets the lower y-axis limit to `0`, and saves at `150 dpi`.
8. **Persist per-point result and print summary**: Write `result.json` with 2-space indentation and return `"; ".join(missing) or None`. Back in `collect`, if the return value is not `None`, print `<point_output_folder>: <error>` first, then print the path to `result.json`, and retain that point's options and parsed `result.json` for the cross-point summary.

### Cross-Point Summary

After all scan points are processed, if more than `1` point has results, `collect` calls `write_points(done, results, folder)`:

- Call `scanned_options(done)`: take the sorted union of `options` keys across all points and keep the list `scanned` of keys satisfying `len({json.dumps(options.get(key)) for _, options in done}) > 1`.
- Build one record row per point containing `"point"`, the current value of each varying scan option, `"events"`, `"efficiency"` (`None` if `mean` is absent), `"efficiency_error"` (`None` if `mean_error` is absent), `"selected"`, and `{"sigma68", "sigma", "sigma_error"}` (in `s`) for every channel in `timing.times` (written only when `times` exists); write `points.json` with 2-space indentation.
- Decide whether to plot: check `len(scanned) == 1` and `isinstance(row[scanned[0]], (int, float)) and not isinstance(row[scanned[0]], bool)` for every row. Return immediately if not satisfied.
- When satisfied, sort rows in ascending order of `key = scanned[0]` and create a `1 × 2` figure (`(11, 4)` in): the left panel filters rows with `row["efficiency"] is not None` and plots efficiency with error bars; the right panel filters rows with `"ToA" in row` as `timed`, and when `timed` is non-empty takes all `CFD*` channel names from `timed[0]`, plotting `sigma / PICOSECOND` with error bars `sigma_error / PICOSECOND` (`ps`) per channel, sets the lower y-axis limit to `0`, and saves `points.png` at `150 dpi`.

## Software Implementation

### Module and File Responsibilities

- `src/raser/stages/analysis/__init__.py`: Registers subcommand `analysis` (short alias `ana`) and implements job function `collect` (orchestrating per-point analysis and cross-point aggregation).
- `src/raser/stages/analysis/files.py`: Provides `slice_file` and `job_file` to locate upstream files of a job and inspect `deposit_<job>.h5` when a file is missing, distinguishing valid zero-event jobs from missing-file errors.
- `src/raser/stages/analysis/collection.py`: Provides `event_efficiencies` and `efficiency_spread`, verifying that event IDs match between current and reconstruction files, calling `collection_efficiency` to compute per-event collection efficiency, and summarizing mean, standard error of the mean, and sample standard deviation.
- `src/raser/stages/analysis/timing.py`: Provides `table_setting`, `point_tables`, `event_times`, `time_widths`, and the standalone summary interface `point_resolution`, handling per-point reconstruction parameter consistency checks, single-electrode checks, earliest deposit time `truth` extraction, and core-width fitting per timing channel.
- `src/raser/stages/analysis/point.py`: Provides `write_point`, chaining single-point table loading, efficiency calculation, time extraction, writing `events.h5` and `result.json`, and drawing the four single-point plots, while catching `TooFewValues` into result `error` fields.
- `src/raser/stages/analysis/plots.py`: Encapsulates `matplotlib` plotting functions for the four single-point distribution plots: `draw_efficiencies`, `draw_amplitudes`, `draw_differences`, and `draw_fractions`.
- `src/raser/stages/analysis/across_points.py`: Provides `scanned_options` and `write_points` to extract varying options across points, write `points.json`, and draw `points.png` for a single numeric scan variable.
- Job scheduling, node reuse, and locking are handled by `src/raser/lifecycle/`.

### Core Data Structures

| Data structure | Field or element | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| Single-job reconstruction entry (element returned by `point_tables`) | `(place, folder, index, table)` | `(int, Path, int, EventTable)` | None (thresholds inside `table` are in $\text{V}$) | 0-based index of the job in `jobs`, job folder, job ID, and loaded `EventTable` |
| Reconstruction setting key (return value of `table_setting`) | `(threshold, amplitude_threshold, fractions, edge)` | `(float, float, tuple[float, ...], tuple[str, ...])` | $\text{mV}$, $\text{mV}$, None, None | Hashable 4-tuple used to validate consistency within a point (both thresholds rounded to `9` decimal places) |
| Selected-event time dict `times` (returned by `event_times`) | `job`, `event` | `ndarray` (`float64`, cast to `int64` when writing `events.h5`) | None | Job index and Geant4 event ID of each selected event |
| Selected-event time dict `times` (returned by `event_times`) | `ToA`, `ToT`, `truth`, `CoG`, `CFD<percent>` | `ndarray` (`float64`) | $\text{s}$ | Reconstructed times, time over threshold, and earliest deposit truth time of selected events |
| Selected-event time dict `times` (returned by `event_times`) | `amplitude`, `baseline`, `noise` | `ndarray` (`float64`) | $\text{V}$ | Maximum pulse amplitude above baseline, baseline mean, and baseline population standard deviation of selected events |
| Per-point result dict `result` (`point.py`) | `reconstruction`, `collection`, `timing` | `dict` | `reconstruction` thresholds in $\text{mV}$; `collection` dimensionless; `timing.times` time quantities in $\text{s}$ | In-memory summary structure mapping one-to-one to per-point `result.json` |
| Cross-point summary row `row` (`across_points.py`) | `point`, `<varying_scan_option>`, `events`, `efficiency`, `efficiency_error`, `selected`, `<channel>` | `dict` | Option in its original unit; efficiency dimensionless; channel `sigma68`/`sigma`/`sigma_error` in $\text{s}$ | Dictionary mapping one-to-one to each scan-point element in `points.json` |

## Interface

### Command-Line and Run Options

`raser analysis [path]`: omits path to use the current folder, or takes a relative or absolute path such as `work/HPK-Si-PiN/signal`. Global options and shared run parameters are documented in [Command-Line Interface](../cli.md):

| Option | Default | Meaning |
| --- | --- | --- |
| `-b` | Off | Submit jobs to the cluster queue (see [Jobs, Logs, Locks, Resuming, and Cluster Submission](../lifecycle/jobs.md) for cluster mechanics) |
| `-t` | Off | Used with `-b` to check and preview submission info only |
| `-mem` | `1` | Memory tier for cluster submission |
| `-s`, `--seed`, `--same-seeds` | See [Command-Line Interface](../cli.md) | Applied to any upstream measurement stages that need to be computed |
| `--set` | None | Modify a setting addressed as `"section.key"`, for example `--set field.voltage=100` |
| `--scan` | None | Scan a setting addressed as `"section.key"`, for example `--scan field.voltage=100,200` |
| `--dry-run` | Off | Print only the scan points, stages, and job states to be run |

The minimum event count `2` for collection efficiency, the minimum event count `20` and maximum `6` rounds for truncated Gaussian fitting, histogram bin counts and fit-curve point counts, the `3 × 4` subplot cap, and PNG resolutions are all hardcoded. The timing threshold, event-selection amplitude threshold, constant fractions, and pulse edge direction belong to the `reconstruction` section; `analysis` reads the values recorded in `reconstruction_<job>.h5` directly, and changing them updates the `reconstruction` node ID so `analysis` recomputes automatically.

### Input Files

- **`<experiment_folder>/points.json`**: Parameter table giving the node ID of each stage at every scan point.
- **`deposit_<job>.h5` in the `deposit` node**: File format documented in [Energy Deposition and Ionization (`core/deposit`)](../core/deposit.md). This stage reads only the event count `len(events)` and the earliest deposit-step time `min(event.t)` ($\text{s}$) of each event.
- **`current_<job>.h5` in the `current` node**: File format documented in [Carrier Drift and Induced Current (`core/current`)](../core/current.md). This stage reads only per-event `event`, `charge` ($\text{C}$), and `pairs` (pairs).
- **`reconstruction_<job>.h5` in the `reconstruction` node**: File format documented in [Event Reconstruction (`core/reconstruction`)](../core/reconstruction.md). This stage reads attributes `electrodes`, `threshold` ($\text{V}$), `amplitude_threshold` ($\text{V}$), `fractions`, and `edge`, and datasets `event`, `selected`, `ToA`, `ToT`, `amplitude`, `baseline`, `noise`, `CoG`, and `CFD`.

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
| `timing` | `times.<channel>` | `dict` | See meaning | Written when all channels fit successfully; `<channel>` is `"ToA"`, `"CoG"`, and each `"CFD<percent>"`, containing `events` (`int`, events), `window` (`[low, high]`, $\text{s}$), `window_events` (`int`, events), `rounds` (`int`, rounds), `mean`, `mean_error`, `sigma`, `sigma_error`, `sigma68` (all `float`, $\text{s}$), and `missing` (`int`, events, number of `NaN` selected events) |
| `timing` | `error` | `str` | None | Written as `"the jobs recorded no event"` when the point has `0` events; when events exist but any channel raises `TooFewValues`, written instead of `times` as `<len> values, fewer than 20` or `<inside> of <len> values are inside [<low>, <high>], fewer than 20` |

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

#### Plot Outputs

| File path | Generation condition | Content | Axis units |
| --- | --- | --- | --- |
| `points/<point>/analysis/efficiency.png` | Event count $\ge 2$ | `60`-bin histogram of charge collection efficiency for all events with a dashed mean line; title reports event count and mean | Horizontal dimensionless, vertical events |
| `points/<point>/analysis/amplitude.png` | Event count $\ge 1$ | `60`-bin histogram of maximum pulse amplitude above baseline for selected events with a dashed line at `amplitude_threshold`; title reports selected count, total count, and threshold | Horizontal $\text{mV}$, vertical events |
| `points/<point>/analysis/time_difference.png` | All `timing.times` computed | Up to `3 × 4` subplots showing time-difference distributions relative to `truth` (`64` bins over `mean ± 8 * sigma`), shaded final-round fit window, and truncated Gaussian fit curve for `ToA`, `CoG`, and the first `10` `CFD*` channels | Horizontal $\text{ps}$, vertical events |
| `points/<point>/analysis/resolution_of_fraction.png` | All `timing.times` computed | Truncated Gaussian fit `sigma` (with error bars) and `sigma68` versus constant fraction across all `CFD*` channels | Horizontal constant fraction (dimensionless), vertical $\text{ps}$ |
| `<experiment_folder>/analysis/points.png` | More than `1` scan point with results, exactly `1` varying option, and all its values are non-boolean numbers | Side-by-side two-panel plot sorted ascending by the scan variable: left panel shows collection efficiency with error bars; right panel shows `sigma` with error bars for each `CFD*` channel | Horizontal original scan-option unit; left vertical dimensionless, right vertical $\text{ps}$ |
