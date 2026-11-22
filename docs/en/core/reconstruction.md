# Event Reconstruction (`core/reconstruction`)

`src/raser/core/reconstruction/` takes the events recorded by the [trigger stage](../stages/trigger.md): it reads the quantized codes of the events listed in `trigger.h5` from `digitizer.h5` written by [digitization](digitizer.md), converts them back to voltage ($\text{V}$) using `lsb_V` and `offset_V`, and assigns the $k$-th sample the time `t0 + k·sampling_period` ($\text{s}$). For each waveform, the package subtracts the pre-pulse baseline and estimates the electronic baseline noise, inverts negative pulses to positive pulses according to the chosen trigger edge of each electrode, extracts peak amplitude, leading-edge time-over-threshold arrival time (`ToA`), time-over-threshold duration (`ToT`), center-of-gravity time over threshold (`CoG`), positive main-lobe integral area (`area`), constant-fraction discrimination (`CFD`), and multi-electrode cluster size and spatial center of gravity, and writes `reconstruction.h5` (`reconstruction.<position>.h5` for multi-position experiments; it also provides the standalone single-event reconstruction class `InputWaveform` for strip detectors). The output event summary table `EventTable` is passed to [statistical analysis](analysis.md).

## Physics

### Baseline Subtraction and Polarity Inversion

Discrete voltage waveforms produced by readout electronics contain a quiescent front-end DC offset and random electronic noise, and pulses may appear as rising edges (positive pulses) or falling edges (negative pulses) depending on the collected carrier polarity and amplifier inversion. Before feature extraction, the baseline mean and baseline noise (population standard deviation) are computed from the quiescent pre-pulse sample segment, the baseline is subtracted from the raw waveform, and the result is multiplied by the edge polarity sign so that pulses are uniformly converted into positive pulses above baseline:

$$t_i = t_0 + i\,\Delta t \tag{1}$$

$$B = \frac{1}{N_{\text{base}}} \sum_{i=0}^{N_{\text{base}}-1} V_i, \qquad \sigma_{\text{noise}} = \sqrt{\frac{1}{N_{\text{base}}} \sum_{i=0}^{N_{\text{base}}-1} (V_i - B)^2} \tag{2}$$

$$v_i = s_{\text{edge}}\,(V_i - B) \tag{3}$$

where:

- $t_i$: nominal time of the $i$-th sample ($i = 0, 1, \dots, N-1$), $\text{s}$;
- $t_0$: time of the first sample for that electrode (`t0` in `digitizer.h5`, already including clock phase), $\text{s}$;
- $\Delta t$: sampling period (`sampling_period` in `digitizer.h5`), $\text{s}$;
- $V_i$: voltage converted back from the code at the $i$-th sample (`samples`), $V_i = (c_i - 2^{N_{\text{bit}}-1} + 0.5)\cdot$`lsb_V`$ + $`offset_V`, $\text{V}$, where $c_i$ is the code and $N_{\text{bit}}$ is the attribute `bits`;
- $N_{\text{base}}$: number of pre-pulse baseline samples (dimensionless), fixed in code to the constant `BASELINE_POINTS = 200`;
- $B$: pre-pulse baseline mean (`baseline`), $\text{V}$;
- $\sigma_{\text{noise}}$: pre-pulse baseline noise population standard deviation (`noise`), $\text{V}$;
- $s_{\text{edge}}$: trigger-edge polarity factor (dimensionless), given by `EDGE_SIGN`: $+1.0$ for `"rising"` and $-1.0$ for `"falling"`;
- $v_i$: net voltage sample after baseline subtraction and inversion to positive polarity (`net`), $\text{V}$.

Baseline subtraction and noise estimation correspond to `net_pulse(samples, baseline_points=BASELINE_POINTS)` in `event.py`, with default `baseline_points = 200`. Sample-time computation and polarity inversion are executed in `event_table` of `event_table.py`; the edge direction of each electrode is determined by `chosen_edges`, which retains the `pulse_edge` recorded for each electrode in the input waveform file (derived by the readout chain from the device and electronics) when `reconstruction.edge` is `null`. When the chosen edge is opposite to the actual direction of an electrode's pulse, that electrode's pulse remains below baseline: `amplitude` is the largest sample above baseline—only of the order of noise or overshoot—and is normally below `threshold`, so `above = False` and the timing and area columns are `NaN`; if an overshoot reaches `threshold`, timing quantities are computed from the overshoot. `InputWaveform` assumes its input `voltage` is already a baseline-subtracted positive pulse. For baseline restoration and noise characterization of semiconductor detector pulses, see Ref. [1].

### Peak Amplitude and Fixed-Threshold Crossing Timing (ToA and ToT)

Leading-edge fixed-threshold discrimination generates a timestamp when a pulse crosses a preset voltage threshold $V_{\text{th}}$. The maximum sample of the net waveform gives the peak amplitude; searching backward and forward from the peak sample for the first sample below threshold and linearly interpolating along the segment connecting the adjacent samples across the threshold yield the leading-edge time of arrival (`ToA`) and the trailing-edge crossing time, whose difference is the time over threshold (`ToT`):

$$A = v_{i_{\text{peak}}}, \qquad i_{\text{peak}} = \operatorname{argmax}_{0 \le i < N} v_i \tag{4}$$

$$t_{\text{cross}}(V_{\text{th}};\, i_{\text{below}},\, i_{\text{above}}) = t_{i_{\text{below}}} + \frac{V_{\text{th}} - v_{i_{\text{below}}}}{v_{i_{\text{above}}} - v_{i_{\text{below}}}}\bigl(t_{i_{\text{above}}} - t_{i_{\text{below}}}\bigr) \tag{5}$$

$$t_{\text{ToA}} = t_{\text{cross}}\bigl(V_{\text{th}};\, i_{\text{lead}},\, i_{\text{lead}} + 1\bigr) \tag{6}$$

$$t_{\text{ToT}} = t_{\text{cross}}\bigl(V_{\text{th}};\, i_{\text{trail}},\, i_{\text{trail}} - 1\bigr) - t_{\text{ToA}} \tag{7}$$

where:

- $A$: maximum pulse amplitude above baseline (`amplitude`), $\text{V}$;
- $i_{\text{peak}}$: index of the peak sample (`peak`, dimensionless; on ties for the maximum, the first index is taken);
- $V_{\text{th}}$: fixed voltage threshold (`threshold`), $\text{V}$;
- $i_{\text{below}}, i_{\text{above}}$: indices of adjacent samples straddling the threshold (dimensionless), satisfying $v_{i_{\text{below}}} < V_{\text{th}} \le v_{i_{\text{above}}}$;
- $t_{\text{cross}}$: linearly interpolated time at which the line joining two adjacent samples crosses $V_{\text{th}}$, $\text{s}$;
- $i_{\text{lead}}$: first sample index with $v_i < V_{\text{th}}$ encountered when searching backward from $i_{\text{peak}} - 1$ to $0$ (dimensionless);
- $i_{\text{trail}}$: first sample index with $v_i < V_{\text{th}}$ encountered when searching forward from $i_{\text{peak}} + 1$ to $N - 1$ (dimensionless);
- $t_{\text{ToA}}$: leading-edge threshold-crossing arrival time (`ToA`), $\text{s}$;
- $t_{\text{ToT}}$: duration of the pulse above threshold (`ToT`), $\text{s}$.

Peak amplitude is computed by `get_amplitude` in `event.py`, and threshold-crossing interpolation, arrival time, and time over threshold are computed by `crossing`, `get_ToA`, and `get_ToT`, respectively. Timing calculations run only when $A \ge V_{\text{th}}$ (`above = True`); in the example `config.json`, `reconstruction.threshold` is set to `10.0` $\text{mV}$ ($0.01\ \text{V}$ after conversion; see [../stages/reconstruction.md](../stages/reconstruction.md)). For leading-edge discrimination and `ToT` measurement principles, see Refs. [1, 2].

### Constant-Fraction Discrimination (CFD)

Fixed-threshold timing introduces amplitude time walk due to pulse-height fluctuations. Constant-fraction discrimination (`CFD`) sets the discrimination threshold to a fixed fraction $f \in (0, 1)$ of each pulse's peak amplitude, locates the pair of adjacent bins straddling the target height $f A$ on the leading edge before the peak, and linearly interpolates to eliminate time walk from amplitude variations among identically shaped pulses:

$$V_{\text{CFD}} = f\,A = f\,v_{i_{\text{peak}}} \tag{8}$$

$$t_{\text{CFD}}(f) = \begin{cases} t_{i-1}, & v_i = v_{i-1} \\ t_{i-1} + \dfrac{V_{\text{CFD}} - v_{i-1}}{v_i - v_{i-1}}\bigl(t_i - t_{i-1}\bigr), & v_i \ne v_{i-1} \end{cases} \tag{9}$$

where:

- $f$: constant-fraction discrimination fraction (`CFD` or an element of `fractions`, dimensionless), satisfying $0 < f < 1$;
- $A = v_{i_{\text{peak}}}$: peak pulse amplitude, $\text{V}$ (requiring $A > 0$);
- $V_{\text{CFD}}$: constant-fraction trigger target voltage (`target`), $\text{V}$;
- $i$: first sample index satisfying $v_{i-1} \le V_{\text{CFD}} \le v_i$ encountered when searching backward from $i_{\text{peak}}$ to $1$ (dimensionless);
- $t_{\text{CFD}}(f)$: constant-fraction timing timestamp for fraction $f$ (`CFD` or `CFD50`), $\text{s}$.

Constant-fraction timing is computed by `get_CFD50(times, samples, CFD, peak)` in `event.py`. `InputWaveform` defaults to the module constant `CFD = 0.5` (corresponding to dictionary key `CFD_LABEL = "CFD50"`); `electrode_row` (called by `event_table` for every stored electrode) invokes `get_CFD50` for each fraction in `fractions`, which is set to `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` in the example `config.json` (see [../stages/reconstruction.md](../stages/reconstruction.md)). For constant-fraction discrimination principles, see Refs. [1, 3].

### Center-of-Gravity Time (CoG) and Pulse Integrals (area and charge)

The temporal concentration of a pulse is characterized by the center of gravity (`CoG`) over the interval above threshold, while the total pulse strength is characterized by the main-lobe integral area (`area`) or the sum of absolute discrete samples (`charge`). Starting from the peak index $i_{\text{peak}}$, the code expands leftward and rightward across the contiguous interval $[i_{\text{first}}^{\text{th}},\, i_{\text{last}}^{\text{th}}]$ where $v_i \ge V_{\text{th}}$ and the contiguous positive main-lobe interval $[i_{\text{first}}^{0},\, i_{\text{last}}^{0}]$ where $v_i > 0$, evaluating:

$$t_{\text{CoG}} = \frac{\sum_{i = i_{\text{first}}^{\text{th}}}^{i_{\text{last}}^{\text{th}}} t_i\,v_i}{\sum_{i = i_{\text{first}}^{\text{th}}}^{i_{\text{last}}^{\text{th}}} v_i} \tag{10}$$

$$S_{\text{area}} = \Delta t \sum_{i = i_{\text{first}}^{0}}^{i_{\text{last}}^{0}} v_i \tag{11}$$

$$Q_{\text{sum}} = \sum_{i = 0}^{N - 1} |v_i| \tag{12}$$

where:

- $i_{\text{first}}^{\text{th}}, i_{\text{last}}^{\text{th}}$: start and end sample indices of the contiguous interval containing $i_{\text{peak}}$ with $v_i \ge V_{\text{th}}$ (dimensionless);
- $t_{\text{CoG}}$: sample-weighted center-of-gravity time over the interval above threshold (`CoG`), $\text{s}$;
- $i_{\text{first}}^{0}, i_{\text{last}}^{0}$: start and end sample indices of the contiguous positive main lobe containing $i_{\text{peak}}$ with $v_i > 0$ (above baseline) (dimensionless);
- $S_{\text{area}}$: rectangular numerical integral area of the positive main lobe (`area`), $\text{V}\cdot\text{s}$;
- $Q_{\text{sum}}$: discrete sum of absolute sample values across the entire waveform (`InputWaveform.charge`), $\text{V}$.

Center-of-gravity time is computed by `get_CoG` in `event.py` and main-lobe integral area by `lobe_area` in `event_table.py`; both are called by `electrode_row` when $A \ge V_{\text{th}}$. The discrete absolute sum Eq. (12) is computed by `get_charge` in `event.py` and is used only by `InputWaveform`. For pulse integration and centroid timing measurements, see Ref. [1].

### Multi-Electrode Clustering and Spatial Center of Gravity (cluster)

When charge sharing or capacitive coupling occurs between adjacent readout electrodes, a single incident particle induces above-threshold signals on multiple neighboring electrodes. Multi-electrode clustering takes electrodes whose amplitude reaches the seed threshold $V_{\text{amp}}$ as seeds and merges each seed together with its immediate left and right neighbors (differing by $1$ in the electrode list index) that exceed the neighbor threshold into the cluster member set $\mathcal{M}$, from which the cluster electrode count, summed feature, 1D electrode-index center of gravity, and spatial error relative to the true hit position are calculated:

$$N_{\text{clu}} = |\mathcal{M}|, \qquad W_{\text{clu}} = \sum_{j \in \mathcal{M}} w_j, \qquad x_{\text{clu}} = \frac{\sum_{j \in \mathcal{M}} j\,w_j}{\sum_{j \in \mathcal{M}} w_j} \tag{13}$$

$$\Delta x_{\text{clu}} = x_{\text{clu}} - \frac{x_{\text{true}}}{p_x} \tag{14}$$

where:

- $\mathcal{M}$: set of readout electrode indices merged into the cluster (starting from $0$, dimensionless);
- $w_j$: feature weight of electrode $j$ (peak amplitude $A_j$ [$\text{V}$] in `cluster` of `event_table.py`; separately `ToT` [$\text{s}$], `amplitude` [$\text{V}$], or `charge` [$\text{V}$] in `InputWaveform` of `event.py`);
- $N_{\text{clu}}$: number of electrodes in the cluster (`cluster_size`), count;
- $W_{\text{clu}}$: sum of the feature over all member electrodes in the cluster (aggregated `"ToT"`, `"amplitude"`, `"charge"` in `InputWaveform`), in the same units as $w_j$;
- $x_{\text{clu}}$: 1D weighted center of the cluster (`cluster_center` or `gravity_center_*`), in units of electrode index starting from $0$ (dimensionless);
- $x_{\text{true}}$: true $x$ coordinate of the incident particle (`original_x`), in the same units as the electrode pitch $p_x$ (`pitch_x`);
- $\Delta x_{\text{clu}}$: difference between the reconstructed electrode center of gravity and the normalized true coordinate (`gravity_center_*_error`), in units of electrode pitch $p_x$ (dimensionless).

Clustering in the job-level event table is computed by `cluster(amplitudes, threshold, amplitude_threshold)` in `event_table.py`, which outputs only $N_{\text{clu}}$ and the amplitude-weighted $x_{\text{clu}}$; in the example `config.json`, both `reconstruction.amplitude_threshold` and `reconstruction.threshold` are set to `10.0` $\text{mV}$ (see [../stages/reconstruction.md](../stages/reconstruction.md)). The single-event class `InputWaveform` calls `get_total_amp` and `get_gravity_center_and_cluster_size` in `event.py` to evaluate Eq. (13), computes position errors via Eq. (14) in `get_total_data`, and obtains `ToA` and `CFD50` via `get_conjoined_time`; its `data` dictionary is passed to `WaveformStatistics.fill_data` in [statistical analysis](analysis.md), with keys matching those read by `fill_data` and `draw`. For charge sharing and centroid position reconstruction in microstrip detectors, see Ref. [4].

### Pixel Clusters

On a pixel device, clusters are found on the 2D pixel array: pixels above threshold are grouped by eight-neighbor connectivity, and only a group holding a seed pixel (amplitude reaching the seed threshold $V_{\text{amp}}$) counts as a cluster; the cluster position is the arithmetic mean of the geometric centers of its pixels, and the hit time of this layer is the timing of the pixel with the largest amplitude in the cluster (the seed):

$$(x_p, y_p) = \bigl((i_x + 0.5)\,p_x,\ (i_y + 0.5)\,p_y\bigr), \qquad (\bar{x}_c, \bar{y}_c) = \frac{1}{n_c}\sum_{m=1}^{n_c}(x_{p,m}, y_{p,m}) \tag{15}$$

where:

- $i_x, i_y$: pixel column and row indices (starting from $0$); the electrode list index is $k = i_x\,n_y + i_y$, where $n_y$ is the device's `y_ele_num`;
- $p_x, p_y$: device pixel pitches `p_x` and `p_y`, $\mu\text{m}$;
- $n_c$: number of pixels in the cluster, count;
- $(\bar{x}_c, \bar{y}_c)$: cluster position in device coordinates, $\mu\text{m}$.

Implemented in `pixel_clusters.py`. The seed, the cluster position, and the hit time are quantities of this device alone; joining the clusters of several devices into a track is done in [statistical analysis](analysis.md).

## Algorithm

### Built-in Constants

The table below lists all built-in constants and hard-coded values in `event.py` and `event_table.py`. All are module constants or hard-coded literals inside functions, with no corresponding keys in device or component files:

| Constant or Hard-Coded Name | Value (by Case) | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| `BASELINE_POINTS` | `200` | samples (count) | `event.py`: number of leading samples used by `net_pulse` to compute the baseline mean `baseline` and standard deviation `noise` |
| `EDGE_SIGN` | `"rising"`: `1.0`; `"falling"`: `-1.0` | dimensionless | `event_table.py`: polarity multiplier that flips the baseline-subtracted waveform `net` into a positive pulse |
| `CFD` | `0.5` | dimensionless | `event.py`: default constant-fraction timing fraction in the `InputWaveform` constructor |
| `CFD_LABEL` | `"CFD50"` | none | `event.py`: dictionary key name storing the constant-fraction timing result in `InputWaveform.data` |
| `EVENT_COLUMNS` | `("event", "selected", "cluster_size", "cluster_center")` | none | `event_table.py`: tuple of per-event 1D dataset column names in `EventTable` |
| `ELECTRODE_COLUMNS` | `("traced", "baseline", "noise", "amplitude", "above", "ToA", "ToT", "CoG", "area")` | none | `event_table.py`: tuple of per-event, per-electrode 2D dataset column names in `EventTable` |
| `KINDS` | `"event"`, `"cluster_size"`: `"int64"`; `"selected"`, `"traced"`, `"above"`: `"bool"`; default for remaining columns: `"float64"` | none | `event_table.py`: NumPy dtype mapping used by `event_table` for each column |
| `InputWaveform` multi-electrode seed thresholds | `ToT` clustering: `10e-9`; `amplitude` clustering: `amplitude_threshold`; `charge` clustering: `0.0` | $\text{s}$ / $\text{V}$ / $\text{V}$ | `event.py`: hard-coded thresholds passed by `InputWaveform.get_total_data` to `get_total_amp` and `get_gravity_center_and_cluster_size` |

### Per-Electrode Edge Determination and Input Validation

Before building the event table, the program determines each electrode's pulse edge through `chosen_edges` and validates all input arguments at the entry of `event_table`:

1. **Determine one edge per electrode (`chosen_edges(given, derived, electrodes)`)**:
   - If `given is None`, retain the derived edge list recorded per electrode in the readout file `list(derived)` and return an empty note list `notes = []`.
   - If `given` is not `None` and `given not in EDGE_SIGN` (i.e., neither `"rising"` nor `"falling"`), raise `ValueError("edge <given!r>: the thresholds are set on a rising (positive pulses) or a falling (negative pulses) edge")`.
   - If `given` is `"rising"` or `"falling"`, set every electrode's edge to `[given] * len(electrodes)`; iterate over `zip(electrodes, derived)` and, for every electrode where `edge != given`, append the notice `"edge <given> given for <name>, whose pulse is <edge>: its pulses are not seen as the readout makes them"` to `notes` and return it (the stage function `reconstruct` prints each notice without aborting the run).
2. **Validate the electrode edge list (`event_table`)**: Check that `edges` satisfies `len(edges) == len(waveforms.electrodes)` and that every entry belongs to `EDGE_SIGN`. Otherwise raise `ValueError("edges <edges>: one of rising or falling for each of <waveforms.electrodes>")`. After validation, build the per-electrode polarity sign list `polarity = [EDGE_SIGN[edge] for edge in edges]` and electrode-name index map `place = {name: k for k, name in enumerate(waveforms.electrodes)}`.
3. **Validate constant-fraction range (`event_table`)**: Collect `wrong = [part for part in fractions if not 0 < part < 1]`. If `wrong` is non-empty (values $\le 0$, $\ge 1$, or `NaN`), raise `ValueError("fractions <wrong>: a constant fraction lies between 0 and 1")`.
4. **Validate non-empty event list (`event_table`)**: If `not waveforms.events` (the input `Waveforms` object holds no events), raise `ValueError("the readout holds no event")`.

### Single-Electrode Baseline Subtraction, Edge Search, and Interpolated Feature Extraction

`event_table` iterates over each event `record` in `waveforms.events` (with total electrode count $W = \text{len}(\text{waveforms.electrodes})$ and sample count $N = \text{record.voltage.shape}[1]$ for the current event), processing electrode waveforms in the following order:

1. **Compute sample times and prefill untraced electrodes**: For each stored electrode, compute the length-$N$ sample-time array `times = t0 + np.arange(N) * waveforms.dt` by Eq. (1), where `t0` is that electrode's `t0` in `digitizer.h5` and `waveforms.dt` is `sampling_period`. Initialize all $W$ electrodes with the untraced default dictionary `untraced`: `traced = False`, `above = False`, and `NaN` for all numeric columns (`baseline`, `noise`, `amplitude`, `ToA`, `ToT`, `CoG`, `area`) and all `len(fractions)` `CFD` values. Electrodes absent from `record.electrodes` (channels whose waveforms were not saved by the readout stage) keep this default state.
2. **Subtract the leading 200-sample baseline and compute noise (`net_pulse(samples, baseline_points=200)`)**: For each stored electrode `name` (at global column index $k = \text{place}[\text{name}]$) and sample array `samples` in `zip(record.electrodes, record.voltage)`:
   - Convert `samples` to a `float64` array;
   - If $\text{len}(\text{samples}) \le \text{baseline\_points}$ (i.e., $N \le 200$), raise `ValueError("<len(samples)> samples, not more than the <baseline_points> of the baseline")`;
   - Compute the mean `baseline = samples[:200].mean()` and population standard deviation `noise = samples[:200].std()` (`ddof=0`) over the first $200$ points, obtaining `net = samples - baseline`.
3. **Invert pulse polarity and locate the peak (`get_amplitude`)**: Multiply the net waveform by the electrode's edge sign, $\text{net}^{+} = \text{polarity}[k] \cdot \text{net}$, and pass it to `electrode_row`. Call `get_amplitude` to find `peak = int(np.argmax(net+))` and `amplitude = net+[peak]`.
4. **Threshold check and below-threshold rejection (`electrode_row`)**:
   - If `amplitude < threshold`, reject timing and area extraction for this electrode: return `above = False`, the measured `amplitude`, and `NaN` for `ToA`, `ToT`, `CoG`, `area`, and all `len(fractions)` `CFD` entries (the caller merges `traced = True`, `baseline`, and `noise`).
   - Otherwise (i.e., `amplitude >= threshold`; edge case: if `amplitude` is `NaN`, `NaN < threshold` is false so execution also enters this branch), set `above = True` and run steps 5 through 9 in sequence.
5. **Leading-edge threshold search and linear interpolation (`get_ToA` and `crossing`)**:
   - Step backward from $i = \text{peak} - 1$ down to $0$ by $-1$;
   - At the first index $i$ with $\text{net}^{+}[i] < \text{threshold}$, immediately call `crossing(times, net+, threshold, below=i, above=i + 1)`: because $i$ is the first sample below threshold looking backward from the peak, $\text{net}^{+}[i+1] \ge \text{threshold}$ and the denominator $\text{net}^{+}[i+1] - \text{net}^{+}[i] > 0$ are guaranteed, returning the linearly interpolated crossing time via Eqs. (5) and (6);
   - **Rejection case**: If $\text{peak} = 0$, or if $\text{net}^{+}[i] \ge \text{threshold}$ all the way down to $i = 0$ (the pulse is already above threshold at the first bin center with no rising crossing), `get_ToA` returns `None` and `electrode_row` records `ToA` as `NaN`.
6. **Trailing-edge threshold search and `ToT` calculation (`get_ToT`)**:
   - Internally call `start = get_ToA(times, net+, threshold, peak)`; if `start is None` (no leading-edge crossing), return `0.0` immediately;
   - Otherwise step forward from $i = \text{peak} + 1$ up to $N - 1$ by $+1$;
   - At the first index $i$ with $\text{net}^{+}[i] < \text{threshold}$, call `crossing(times, net+, threshold, below=i, above=i - 1)` to find the trailing-edge crossing time and return its difference with `start` (here `below = i`, `above = i - 1`, so the fraction `part` $\in (0, 1]$ multiplies the negative time difference $\text{times}[i-1] - \text{times}[i] = -\Delta t$, placing the crossing between $\text{times}[i-1]$ and $\text{times}[i]$);
   - **Unfallen trailing-edge boundary case**: If $\text{peak} = N - 1$, or if the waveform never drops below `threshold` up to the end $i = N - 1$, `get_ToT` returns the float `0.0`.
7. **Above-threshold interval expansion and center-of-gravity time (`get_CoG`)**:
   - Initialize `first = peak`, `last = peak`;
   - Decrement `first` while $\text{first} > 0$ and $\text{net}^{+}[\text{first} - 1] \ge \text{threshold}$; increment `last` while $\text{last} < N - 1$ and $\text{net}^{+}[\text{last} + 1] \ge \text{threshold}$;
   - Slice `weights = net+[first:last + 1]` and return `np.sum(times[first:last + 1] * weights) / np.sum(weights)` per Eq. (10).
8. **Positive main-lobe expansion and integral area (`lobe_area`)**:
   - Initialize `first = peak`, `last = peak`;
   - Decrement `first` while $\text{first} > 0$ and $\text{net}^{+}[\text{first} - 1] > 0$; increment `last` while $\text{last} < N - 1$ and $\text{net}^{+}[\text{last} + 1] > 0$;
   - Return `float(np.sum(net+[first:last + 1]) * dt)` per Eq. (11).
9. **Constant-fraction search and linear interpolation (`get_CFD50`)**:
   For each fraction `part` in `fractions`:
   - Compute the target height $\text{target} = \text{net}^{+}[\text{peak}] \cdot \text{part}$;
   - **Non-positive peak rejection case**: If $\text{net}^{+}[\text{peak}] \le 0$ (possible only when `threshold <= 0`), return `None` and record the corresponding `CFD` entry as `NaN`;
   - Otherwise step backward from $i = \text{peak}$ down to $1$ by $-1$, take adjacent samples $\text{previous\_content} = \text{net}^{+}[i - 1]$ and $\text{content} = \text{net}^{+}[i]$, and test the closed-interval condition $\text{previous\_content} \le \text{target} \le \text{content}$:
     - If satisfied and $\text{content} == \text{previous\_content}$, return the left bin timestamp `times[i - 1]`;
     - If satisfied and $\text{content} \ne \text{previous\_content}$, return the linearly interpolated crossing time per Eq. (9);
   - **Miss rejection case**: If no adjacent pair down to $i = 1$ satisfies $\text{net}^{+}[i - 1] \le \text{target} \le \text{net}^{+}[i]$ (for instance, the first bin is already above `target`), return `None` and record the corresponding `CFD` entry as `NaN`.

### Multi-Electrode Clustering and Event Selection Rules

After computing all electrode rows for an event, `event_table` extracts `amplitudes = [row["amplitude"] for row in rows]` and calls `cluster(amplitudes, threshold, amplitude_threshold)`:

1. **Find seed electrodes**: Collect all electrode indices $k \in \{0, \dots, W - 1\}$ satisfying $\text{amplitudes}[k] \ge \text{amplitude\_threshold}$ into `seeds` (untraced electrodes have `amplitude` equal to `NaN`, for which the comparison is false).
2. **Merge immediate left and right above-threshold neighbors**: For each seed $k \in \text{seeds}$, inspect $j \in \{k - 1, k, k + 1\}$. If $j = k$, or if $0 \le j < W$ and $\text{amplitudes}[j] \ge \text{threshold}$, add $j$ to the set and sort in ascending order into `members`.
3. **No-seed rejection and feature output**:
   - If `members` is empty (`seeds` is empty), return `(0, NaN)`; the event gets `selected = False`, `cluster_size = 0`, and `cluster_center = NaN`;
   - If `members` is non-empty, compute the amplitude-weighted index center of gravity using `amplitudes[j]` per Eq. (13) and return `(len(members), center)`; the event gets `selected = True`.
4. **Assemble arrays**: After all events are processed, convert each column to a NumPy array with dtype `KINDS.get(name, "float64")`, reshape `CFD` to the 3D shape `(len(waveforms.events), W, len(fractions))`, and return the wrapped `EventTable`.

`cluster` takes $k - 1$ and $k + 1$ in the 1D electrode list as immediate neighbors, and merges all seeds reaching `amplitude_threshold` together with their immediate neighbors within the same event into a single cluster.

### Single-Event Standalone Reconstruction Class `InputWaveform`

`InputWaveform(voltage, t0, dt, original_x, threshold, amplitude_threshold, pitch_x, pitch_y, CFD=0.5)` (`event.py`) allows Python scripts to extract single-event quantities directly from a baseline-subtracted, positive-polarity 2D voltage matrix `voltage` of shape `(read_ele_num, bins)`:

1. **Single-electrode scan**: Compute `times = t0 + np.arange(len(voltage[0])) * dt` by Eq. (1) (`dt` is the sampling period). For each electrode $i \in \{0, \dots, \text{read\_ele\_num} - 1\}$, call `get_amplitude(voltage[i])` to obtain `(amplitude[i], peak_time[i])` (where `peak_time[i]` stores the integer peak bin index `peak`):
   - If $\text{amplitude}[i] < \text{threshold}$, reject the electrode, setting `amplitude[i]`, `ToT[i]`, and `charge[i]` to `0` and `ToA[i]` and `CFD50[i]` to `None`;
   - Otherwise call `get_ToA`, `get_ToT`, `get_charge` (computing `np.sum(np.abs(voltage[i]))` via Eq. (12)), and `get_CFD50` (with fraction `CFD`).
2. **Multi-channel feature summary (`get_total_data`)**: Initialize `self.data = {}`, unconditionally set `self.data["original_x"] = original_x` at the end, and assign the remaining 14 keys according to three cases:
   - **Below-seed-threshold rejection case ($\max(\text{self.amplitude}) < \text{self.amplitude\_threshold}$)**: Set `"cluster_size_ToT"`, `"cluster_size_amplitude"`, and `"cluster_charge"` to `0`, and set all remaining 11 keys (`"ToA"`, `"ToT"`, `"amplitude"`, `"charge"`, `CFD_LABEL`, the 3 `"gravity_center_*"`, and the 3 `"gravity_center_*_error"`) to `None`.
   - **Single-electrode degenerate case ($\max(\text{self.amplitude}) \ge \text{self.amplitude\_threshold}$ and $\text{read\_ele\_num} == 1$)**: Set `"ToA"`, `"ToT"`, `"amplitude"`, `"charge"`, and `CFD_LABEL` to the values of electrode `0`; set all 3 `"gravity_center_*"` and all 3 `"gravity_center_*_error"` to `0`; set `"cluster_size_ToT"`, `"cluster_size_amplitude"`, and `"cluster_charge"` to `1`.
   - **Multi-electrode strip case ($\text{read\_ele\_num} > 1$)**:
     - `"ToA"` and `CFD_LABEL` call `get_conjoined_time(time_list, self.amplitude)`: among all electrodes with `time_list[idx] is not None` and `amplitude[idx] > 0`, return the time of the electrode with the largest `amplitude[idx]` (`None` if no valid electrode exists; when `get_conjoined_time` is called without `amplitude_list`, it returns `min` when `remove_none(time_list)` is non-empty).
     - Call `get_total_amp(amp_list, amp_thres)` and `get_gravity_center_and_cluster_size(amp_list, amp_thres)` separately for `(self.ToT, 10e-9)`, `(self.amplitude, self.amplitude_threshold)`, and `(self.charge, 0.0)`: if $\max(\text{amp\_list}) == 0$ or no seed electrode strictly satisfies $\text{amp\_list}[i] > \text{amp\_thres}$, the total returns `None` and the center and cluster size return `(None, 0)`; otherwise merge all seeds $i$ with $\text{amp\_list}[i] > \text{amp\_thres}$ and their left/right neighbors satisfying $\text{amp\_list}[i \pm 1] > 0$ into `new_seeds`, and evaluate the sum, weighted index centroid, and member count via Eq. (13) (where `"cluster_charge"` stores the member electrode count `len(new_seeds)` of the `charge` cluster).
     - For the `ToT`, `amplitude`, and `charge` centroids, if not `None`, compute `gravity_center_* - original_x / pitch_x` per Eq. (14) and store it in `"gravity_center_*_error"`; otherwise store `None`.

`InputWaveform` targets 1D spatial-resolution strip detectors (code comments: `only available for strip detector`, `assume strip, one dimensional spacial resolution`); multi-electrode `ToA` and `CFD50` take the timing of the maximum-amplitude channel via `get_conjoined_time`; the clustering seed thresholds for `ToT` and `charge` are hard-coded to `10e-9` $\text{s}$ and `0.0` $\text{V}$; `threshold`, `amplitude_threshold`, and `CFD` are supplied as constructor arguments.

### Pixel Clustering (`pixel_clusters.py`)

When the device's `electrodes` is `"pixel"`, the event table carries five more columns of pixel-cluster quantities, given by `pixel_cluster_columns(fired, weight, seed_threshold, p_x, p_y)`: `fired` is the boolean array of pixels above threshold per event and `weight` is the quantity used to find the seed, both of shape `(events, n_x, n_y)`; `seed_threshold` is the seed threshold:

1. **Obtain pixels above threshold and the seed quantity**, from either of two sources:
   - `fired_from_table(table, n_x, n_y)`: `fired` takes `above` from the event table and `weight` takes `amplitude` ($\text{V}$), reshaped to `(events, n_x, n_y)` according to $k = i_x\,n_y + i_y$, and `seed_threshold` takes `amplitude_threshold`; raises `ValueError` if the number of electrodes does not equal $n_x n_y$.
   - `fired_from_deposits(deposits, slot, device)`: for deposit steps in the deposit file whose detector name equals `slot`, marks the pixel $(\lfloor x/p_x \rfloor, \lfloor y/p_y \rfloor)$ of each step with `pairs > 0` inside the device as above threshold, `weight` takes the sum of electron-hole pairs inside that pixel, and `seed_threshold` takes `0`; one row per recorded event, with the entire row `False` for events with no deposits in that slot.
2. **Clustering and seeding** (`pixel_clusters(fired_event, weight_event, seed_threshold, p_x, p_y)`): finds eight-neighbor connected components in an event's `(n_x, n_y)` boolean array and keeps only components holding a pixel with `weight >= seed_threshold`; computes $(\bar{x}_c, \bar{y}_c, n_c)$ for each component via Eq. (15), takes as seed the pixel with the largest `weight` in the component (the smaller electrode index on a tie), and sorts components in ascending order of the seed's electrode index $k$.
3. **Write the columns**: `clusters` is the number of clusters; with exactly `1` cluster, `cluster_x`, `cluster_y`, `cluster_pixels`, and `cluster_seed` take that cluster's $\bar{x}_c$, $\bar{y}_c$, $n_c$, and the seed's electrode index $k$, otherwise they are `NaN`, `NaN`, `0`, and `-1`. The hit time of this layer is the timing in the seed's column: `ToA[:, cluster_seed]`, `CFD[:, cluster_seed, :]`, and so on.

`table_from_deposits(deposits, slot, device)` uses `fired_from_deposits` to give an event table that holds only `event`, `selected` (`clusters > 0`), and these five columns, without waveform and timing quantities.

## Software Implementation

### Module and Function Responsibilities

- `event.py`: implements single-electrode baseline subtraction, linearly interpolated threshold crossings, constant-fraction timing, center-of-gravity time calculation, and the standalone single-event reconstruction class. `net_pulse` computes and subtracts the leading 200-sample baseline and returns baseline noise; `get_amplitude`, `crossing`, `get_ToA`, `get_ToT`, `get_CFD50`, `get_CoG`, and `get_charge` extract features from a single positive waveform; `InputWaveform`, together with `get_conjoined_time`, `get_total_amp`, `get_gravity_center_and_cluster_size`, and `remove_none`, aggregates single-event features across multiple strip channels.
- `pixel_clusters.py`: implements 2D clustering for pixel devices. `pixel_clusters` clusters using eight-neighbor connectivity; `fired_from_table` and `fired_from_deposits` give the pixels above threshold; `pixel_cluster_columns` gives the five event-table columns; `table_from_deposits` gives an event table directly from the deposit file; `draw_hitmap` draws the hit map.
- `event_table.py`: implements job-level multi-event feature extraction, multi-electrode clustering, and `reconstruction.h5` file I/O. `lobe_area` computes the positive main-lobe integral area containing the peak; `electrode_row` assembles the threshold check and all feature columns for one electrode; `cluster` performs 1D multi-electrode clustering and computes the amplitude-weighted center; `chosen_edges` resolves and validates per-electrode trigger edges; `event_table` reconstructs an entire job's `Waveforms` into an `EventTable`; `write_event_table` and `read_event_table` perform one-shot writing and reading of the HDF5 event table file.
- `draw.py`: provides `draw_features`, calling `raser.supports.figures` to mark the baseline, amplitude, `ToA` on the threshold line, and `CFD` times for each fraction in `reconstruction.fractions` on the rising-edge segment of the digital waveform, saving them as `.png` and `.pdf`.

### Core Data Structures

- `EventTable` (`event_table.py`): single-job reconstruction result dataclass (`@dataclass`), supporting `len(table)` to return the number of event rows, with fields:
  - `electrodes` (`list[str]`, unitless): list of readout electrode names matching the electrode column order of 2D and 3D datasets;
  - `threshold` (`float`, $\text{V}$): voltage threshold above baseline for crossing times, center-of-gravity time, main-lobe area, and adding neighbor electrodes to a cluster;
  - `amplitude_threshold` (`float`, $\text{V}$): amplitude threshold above baseline for cluster seed electrodes; events recorded by `trigger` in which a seed is found are marked `selected`;
  - `fractions` (`tuple[float, ...]`, dimensionless): tuple of constant-fraction timing fractions;
  - `edges` (`list[str]`, unitless): list of trigger-edge directions used for each electrode, with entries `"rising"` or `"falling"`;
  - `columns` (`dict[str, np.ndarray]`): dictionary mapping the 14 column names from `EVENT_COLUMNS`, `ELECTRODE_COLUMNS`, and `"CFD"` to their NumPy arrays, whose shapes, types, and units are listed in the `reconstruction.h5` dataset table below.
- `InputWaveform` (`event.py`): standalone single-event reconstruction object with attributes:
  - `times` (`np.ndarray`, shape `(bins,)`, $\text{s}$): sample timestamps;
  - `waveforms` (`list[np.ndarray]`, length `read_ele_num`, $\text{V}$): positive-polarity voltage waveforms above baseline for each electrode;
  - `read_ele_num` (`int`, count): number of readout electrodes;
  - `pitch_x`, `pitch_y` (`float`, same units as `original_x`): electrode pitch along $x$ and $y$;
  - `CFD` (`float`, dimensionless): constant-fraction timing fraction (default `0.5`);
  - `threshold`, `amplitude_threshold` (`float`, $\text{V}$): per-electrode crossing threshold and cluster seed amplitude threshold;
  - `original_x` (`float`, same units as `pitch_x`): true $x$ coordinate of the incident track;
  - `peak_time` (`list[int]`, dimensionless): list of peak sample indices per electrode;
  - `ToA`, `ToT`, `CFD50` (`list[float | None]`, $\text{s}$): per-electrode lists of arrival time, time over threshold, and 50% constant-fraction timing;
  - `amplitude`, `charge` (`list[float]`, $\text{V}$): per-electrode lists of peak amplitude and sum of absolute sample values;
  - `data` (`dict[str, float | int | None]`): single-event summary dictionary containing `"ToA"` ($\text{s}$), `"ToT"` ($\text{s}$), `"amplitude"` ($\text{V}$), `"charge"` ($\text{V}$), `"CFD50"` ($\text{s}$), `"gravity_center_ToT"` / `"_amplitude"` / `"_charge"` (0-based electrode index), `"cluster_size_ToT"` / `"_amplitude"` / `"cluster_charge"` (count), `"gravity_center_ToT_error"` / `"_amplitude_error"` / `"_charge_error"` (relative position error in units of `pitch_x`), and `"original_x"` (same units as `pitch_x`).

## Interface

Users can configure only the 4 settings listed in the table below, written in the `reconstruction` section of `config.json` and modified via `--set` or `--scan`; all other parameters (baseline sample count `BASELINE_POINTS = 200`, edge polarity factors `EDGE_SIGN`, and internal `InputWaveform` thresholds) are hard-coded. For commands and usage, see [../stages/reconstruction.md](../stages/reconstruction.md).

### Reconstruction Configuration Keys and Function Arguments

`reconstruct` in [../stages/reconstruction.md](../stages/reconstruction.md) accepts `reconstruction.threshold` and `reconstruction.amplitude_threshold` in $\text{mV}$ and multiplies them by `MILLIVOLT = 1.0e-3` to convert to $\text{V}$ before passing them to `event_table`:

| Section.Key / Parameter Name | Value in Example | Unit | Meaning |
| --- | --- | --- | --- |
| `reconstruction.threshold` | `10.0` | `config.json`: $\text{mV}$; `event_table` and file attribute: $\text{V}$ | Threshold above baseline for single-electrode crossing check (`above`), `ToA`, `ToT`, `CoG`, `area`, and adding neighboring electrodes to a cluster |
| `reconstruction.amplitude_threshold` | `10.0` | `config.json`: $\text{mV}$; `event_table` and file attribute: $\text{V}$ | Peak amplitude threshold above baseline for cluster seed electrodes; events recorded by `trigger` in which a seed is found are marked `selected` |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | dimensionless | Sequence of amplitude fractions for constant-fraction discrimination (`CFD`); every element must lie strictly in the open interval $(0, 1)$ |
| `reconstruction.edge` | `null` (inherits `pulse_edge` from the input waveform file) | none | Trigger-edge direction, `"rising"`, `"falling"`, or `null`; when `null`, `chosen_edges` retains the `pulse_edge` attribute of the input waveform file |

### Input File Attributes and Datasets

`event_table` receives the digital waveforms of events recorded by `trigger`: it reads the `event` dataset (`(recorded,)`, `int64`, IDs of recorded events) from `trigger.h5` of the `trigger` node, fetches those events from `digitizer.h5` of the `digitizer` node (`digitizer.<position>.h5` for multi-position experiments; see [digitizer](digitizer.md#output-digitizerh5) for the format), and reconstructs them into a `Waveforms(electrodes, dt, events, pulse_edge)` object using the sample times of Eq. (1) and voltages converted back from the codes, with `dt` taken from `sampling_period`; each row of the event table corresponds to one of those events. The attributes and datasets of `digitizer.h5` are:

**Input File Attributes**

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `electrodes` | string array | none | List of all readout electrode names in the circuit, determining the column order of `EventTable.electrodes` |
| `sampling_period` | `float64` | $\text{s}$ | Sampling period $\Delta t$ |
| `lsb_V` | `float64` | $\text{V}$ | Voltage per code step, used to convert codes back to voltage |
| `offset_V` | `float64` | $\text{V}$ | Center of the range, used to convert codes back to voltage |
| `bits` | integer | bits | ADC bit depth $N_{\text{bit}}$ |
| `pulse_edge` | string array | none | Per-electrode pulse-edge direction (`"rising"` or `"falling"`) derived by the readout chain, used by `chosen_edges` as the default edge and comparison baseline |
| `device` | string | none | Name of the digitizer component used |

**Input Datasets**

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | none | Event ID, restored to `EventWaveforms.event` |
| `count` | `(events,)`, `int64` | samples | Number of samples $N$ in each stored waveform of the event |
| `stored` | `(events,)`, `int64` | count | Number of electrodes $M$ with stored digital waveforms in the event |
| `index` | `(sum(stored),)`, `int64` | none | 0-based index of each stored electrode in `electrodes`, restored to `EventWaveforms.electrodes` |
| `t0` | `(sum(stored),)`, `float64` | $\text{s}$ | Time of the first sample for that electrode, already including the clock phase of its instrument |
| `clipped` | `(sum(stored),)`, `int64` | samples | Number of samples on that electrode clipped to the maximum or minimum code |
| `code` | `(sum(stored * count),)`, `int16` | none | Codes of each stored electrode, sliced per event, converted back to voltage, and reshaped to `(M, N)` as `EventWaveforms.voltage` ($\text{V}$) |

### Output `reconstruction.h5` File Format

The file is written to `nodes/reconstruction/<node>/reconstruction.h5` (`reconstruction.<position>.h5` in the same node for multi-position experiments) in one shot by `write_event_table(path, table)` and read back as an `EventTable` object by `read_event_table(path)`.

**File Attributes**

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `electrodes` | string array | none | List of readout electrode names, matching the electrode dimension order of 2D and 3D datasets |
| `threshold` | `float64` | $\text{V}$ | Threshold (above baseline) for crossing times, center-of-gravity time, main-lobe area, and neighbor electrode clustering |
| `amplitude_threshold` | `float64` | $\text{V}$ | Amplitude threshold (above baseline) for cluster seed electrodes |
| `fractions` | 1D `float64` array, shape `(fractions,)` | dimensionless | Array of constant-fraction timing fractions, matching the 3rd dimension order of the `CFD` dataset |
| `edge` | string array | none | Trigger-edge direction actually used for each electrode, with entries `"rising"` or `"falling"` (corresponding to `EventTable.edges`) |

**Datasets**

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | none | Geant4 event ID |
| `selected` | `(events,)`, `bool` | none | Whether a cluster seed is found in the event recorded by `trigger` (i.e., `cluster_size > 0`, at least one electrode with `amplitude >= amplitude_threshold`) |
| `cluster_size` | `(events,)`, `int64` | count | Number of electrodes in the cluster (`0` when no cluster exists) |
| `cluster_center` | `(events,)`, `float64` | electrode index (0-based) | Amplitude-weighted electrode-index center of the cluster (`NaN` when no cluster exists) |
| `clusters` | `(events,)`, `int64` | count | Pixel devices only: number of 2D clusters (Eq. (15)) |
| `cluster_x`, `cluster_y` | `(events,)`, `float64` | $\mu\text{m}$ | Pixel devices only: cluster position in device coordinates; `NaN` when the number of clusters is not `1` |
| `cluster_pixels` | `(events,)`, `int64` | count | Pixel devices only: number of pixels in the cluster; `0` when the number of clusters is not `1` |
| `cluster_seed` | `(events,)`, `int64` | none | Pixel devices only: electrode index of the pixel with the largest amplitude in the cluster; the hit time of this layer is taken from that electrode's `ToA`, `CFD`, and other columns; `-1` when the number of clusters is not `1` |
| `traced` | `(events, len(electrodes))`, `bool` | none | Whether the input `digitizer.h5` stores a waveform for that electrode in the event; when `False`, all numeric columns of that electrode are `NaN` and `above` is `False` |
| `baseline` | `(events, len(electrodes))`, `float64` | $\text{V}$ | Arithmetic mean of the leading `200` samples of the raw waveform |
| `noise` | `(events, len(electrodes))`, `float64` | $\text{V}$ | Population standard deviation of the leading `200` samples of the raw waveform |
| `amplitude` | `(events, len(electrodes))`, `float64` | $\text{V}$ | Maximum sample value after baseline subtraction and polarity inversion according to `edge` |
| `above` | `(events, len(electrodes))`, `bool` | none | Whether the pulse reaches `threshold` (`False` when no waveform is stored or `amplitude < threshold`; when `False`, `ToA`, `ToT`, `CoG`, `area`, and `CFD` are all `NaN`) |
| `ToA` | `(events, len(electrodes))`, `float64` | $\text{s}$ | Linearly interpolated leading-edge crossing time at `threshold` (`NaN` if no crossing is found or `above` is false) |
| `ToT` | `(events, len(electrodes))`, `float64` | $\text{s}$ | Duration from `ToA` to the trailing-edge crossing of `threshold` (`0.0` if the waveform does not fall below threshold before the end of the record or if `ToA` is absent; `NaN` if `above` is false) |
| `CoG` | `(events, len(electrodes))`, `float64` | $\text{s}$ | Sample-weighted center-of-gravity time over the contiguous interval containing the peak with net voltage $\ge \text{threshold}$ |
| `area` | `(events, len(electrodes))`, `float64` | $\text{V}\cdot\text{s}$ | Rectangular integral area of the contiguous positive main lobe containing the peak with net voltage $> 0$ |
| `CFD` | `(events, len(electrodes), len(fractions))`, `float64` | $\text{s}$ | Linearly interpolated leading-edge crossing times at each `fractions * amplitude` (`NaN` if no crossing is found, peak $\le 0$, or `above` is false) |

The constant-fraction timestamp at fraction $f$ for the $k$-th electrode (0-based in the order of attribute `electrodes`) is `CFD[:, k, j]`, where $j$ is the index of $f$ in attribute `fractions`. `ToA`, `CoG`, and `CFD` lie on the same time axis as the input event's `t0` (Eq. (1)), while `t0` stays in the input waveform file.

### Plot Output

`event_table` takes two required arguments `plots` (`int`, maximum number of events for which feature plots are drawn per job, count) and `plot_path` (`str | Path`, output image directory path, unitless; passed by the [event reconstruction stage](../stages/reconstruction.md) as `reconstruction.plots` and the node's `plots/` directory). When `plots <= 0`, no plots are drawn and `plot_path` is unused; when `plots > 0`, for the first `plots` events in each job the program calls `draw_features` in `core/reconstruction/draw.py` to plot each electrode with a stored digital waveform in that event and saves them via `raser.supports.figures` under `plot_path` as both `.png` (200 dpi) and `.pdf` files: when a single electrode has a stored waveform, the filename is `features_<event>` (`<event>` is `record.event`, unitless); when multiple electrodes have stored waveforms, one plot is drawn per electrode with `_electrode_<number>` appended (`<number>` is the `1`-based index of that electrode in `waveforms.electrodes`, dimensionless).

Each plot uses the sample time `Time [ns]` as the horizontal axis (computed from $t_0$ [$\text{s}$] and the sampling period $\Delta t$ [$\text{s}$] via Eq. (1) and converted to $\text{ns}$) and voltage `Amplitude [mV]` as the vertical axis (converted from $\text{V}$ to $\text{mV}$). Only the rising-edge segment of the pulse is shown—from before the threshold crossing to after the peak—plotting the voltage converted back from the `digitizer` quantized codes in its original polarity without inversion or baseline subtraction (solid black line). The following reconstructed quantities are marked on this waveform segment (quantities that were not computed and equal `NaN` are omitted):

- **Baseline**: the baseline mean (`baseline` in Eq. (2)) is drawn as a horizontal gray dotted line, labeled `baseline` in the legend;
- **Amplitude**: the voltage at the peak (baseline plus `amplitude` with the original polarity, Eq. (4)) is drawn as a horizontal gray dashed line, labeled `amplitude` in the legend;
- **Threshold and `ToA`**: the timing threshold `threshold` (see [Peak Amplitude and Fixed-Threshold Crossing Timing (ToA and ToT)](#peak-amplitude-and-fixed-threshold-crossing-timing-toa-and-tot)) is drawn as a horizontal red dashed line; the leading-edge threshold-crossing time $t_{\text{ToA}}$ (`ToA` in Eq. (6)) is marked with a red square on the threshold line, labeled `ToA` in the legend;
- **Constant-fraction discrimination (`CFD`)**: one point is plotted for each fraction $f$ in `reconstruction.fractions`, placed on the rising edge at time $t_{\text{CFD}}(f)$ (`CFD` in Eqs. (8)–(9), see [Constant-Fraction Discrimination (CFD)](#constant-fraction-discrimination-cfd)) and voltage equal to baseline plus $f$ times the amplitude; the percentage (e.g., `30%`) is annotated beside each point without vertical lines, and the legend shows `CFD` with the range of fractions.

| Filename | Content | Unit |
| --- | --- | --- |
| `features_<event>.png`, `.pdf` (or with `_electrode_<number>`) | Rising-edge segment of the digital waveform (original polarity), marking baseline, amplitude, `ToA` square on the threshold line, and `CFD` points for each fraction in `reconstruction.fractions` (`NaN` omitted); one plot per stored-waveform electrode when multiple are stored, with `<number>` starting from `1` | `Time [ns]`, `Amplitude [mV]` |

`draw_hitmap(table, device, path)` in `pixel_clusters.py` draws `hitmap` (`hitmap_<slot>` in a multi-slot experiment): the 2D distribution of $(\bar{x}_c, \bar{y}_c)$ over all events with `1` cluster, one cell per pixel.

After aggregation, `InputWaveform.data` is plotted by `WaveformStatistics.draw` in [statistical analysis](analysis.md): Gaussian-fitted timing resolution plots, Landau-fitted amplitude and charge plots, cluster-size distributions, spatial center-of-gravity error plots, and $\eta$ calibration plots.

## References

- [1] H. Spieler, *Semiconductor Detector Systems*, Oxford University Press (2005), ISBN 978-0-19-852784-8, doi:10.1093/acprof:oso/9780198527848.001.0001
- [2] I. Kipnis, T. Collins, J. DeWitt, S. Dow, A. Frey, A. Grillo, R. Johnson, W. Kroeger, A. Leona, L. Luo, et al., “A time-over-threshold machine: the readout integrated circuit for the BABAR Silicon Vertex Tracker”, IEEE Trans. Nucl. Sci. 44 (1997) 289, doi:10.1109/23.603658
- [3] D. A. Gedcke, W. J. McDonald, “Design of the Constant Fraction of Pulse Height Trigger for Optimum Time Resolution”, Nucl. Instrum. Methods 58 (1968) 253, doi:10.1016/0029-554X(68)90473-4
- [4] R. Turchetta, “Spatial resolution of silicon microstrip detectors”, Nucl. Instrum. Methods Phys. Res. A 335 (1993) 44, doi:10.1016/0168-9002(93)90255-G
