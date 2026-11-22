# Statistical Analysis (`core/analysis`)

`src/raser/core/analysis/` takes the net induced charge per readout electrode and initial electron-hole pair count written by [carrier transport](current.md), the pulse timing features and single-event dictionary `InputWaveform.data` extracted by [event reconstruction](reconstruction.md), the earliest deposition time recorded by [energy deposition](deposit.md), and the `Detector` geometric attributes provided by [device definition](device.md). The package computes per-event charge collection efficiency, extracts the core width of a distribution as resolution using iterative unbinned truncated-Gaussian maximum-likelihood fitting, and uses PyROOT to produce binned Gaussian fits, Landau fits, and $\eta$ position-calibration plots for single-event waveform features. The computed per-event collection efficiencies and distribution core widths are passed to the [statistical analysis stage](../stages/analysis.md) to aggregate and write single-point and cross-point result files and distribution plots, while `WaveformStatistics` writes `.pdf`, `.C`, and optional `.png` statistical figures directly to disk.

## Physics

### Charge Collection Efficiency

The charge collection efficiency (CCE) of a semiconductor detector in a single event is defined as the ratio of the absolute value of the algebraic sum of signed net induced charges collected on all readout electrodes to the total charge of the initial ionized electron-hole pairs prior to avalanche multiplication. This definition is independent of the polarity of the carriers collected by the electrodes; when avalanche multiplication is present in the device, the collection efficiency can exceed $1$:

$$\eta = \frac{\left|\sum_{j=1}^{N_{\text{ele}}} Q_j\right|}{N_{\text{pairs}}\,e} \tag{1}$$

where:

- $\eta$: charge collection efficiency of a single event (dimensionless);
- $Q_j$: signed net induced charge on the $j$-th readout electrode in that event, $\text{C}$ (written by [current.md](current.md));
- $N_{\text{ele}}$: total number of readout electrodes (dimensionless);
- $N_{\text{pairs}}$: total number of initial electron-hole pairs generated in that event before avalanche multiplication, pairs (ionized by [deposit.md](deposit.md) and recorded via [current.md](current.md));
- $e$: elementary charge, taken in code as the constant `ELEMENTARY_CHARGE` equal to $1.602176634\times 10^{-19}\ \text{C}$.

Eq. (1) is computed by `collection_efficiency(charge, pairs)` in `collection.py`. For the definition of charge collection efficiency in semiconductor radiation detectors, see Ref. [1]; for the exact SI value of the elementary charge, see Ref. [2].

### Core Width of a Distribution and Truncated-Gaussian Fitting

Distributions of detector timing residuals (such as reconstructed time minus earliest deposition time, $t_{\text{reco}} - t_{\text{truth}}$) frequently exhibit non-Gaussian long tails, so time resolution is characterized by the width of the distribution core. The code first builds a robust initial window around the sample median, then uses only samples falling within a finite window $[a, b]$ to model the conditional probability density as a Gaussian truncated and normalized on $[a, b]$, recovers the mean $\mu$ and standard deviation $\sigma$ of the underlying untruncated Gaussian via unbinned maximum-likelihood estimation, and simultaneously reports the non-parametric core half-width $\sigma_{68}$ as half the spacing between the $16\%$ and $84\%$ quantiles of the in-window samples:

$$m = \operatorname{median}(X), \qquad \text{MAD} = \operatorname{median}\bigl(|X - m|\bigr), \qquad [a_1, b_1] = [m - 8\,\text{MAD},\, m + 8\,\text{MAD}] \tag{2}$$

$$p(x \mid \mu, \sigma; a, b) = \frac{1}{\sqrt{2\pi}\,\sigma\,P_{\text{in}}(\mu, \sigma; a, b)}\exp\!\left(-\frac{(x - \mu)^2}{2\sigma^2}\right), \qquad x \in [a, b] \tag{3}$$

$$P_{\text{in}}(\mu, \sigma; a, b) = \frac{1}{2}\left[\operatorname{erf}\!\left(\frac{b - \mu}{\sqrt{2}\,\sigma}\right) - \operatorname{erf}\!\left(\frac{a - \mu}{\sqrt{2}\,\sigma}\right)\right] \tag{4}$$

$$\mathcal{L}(\tilde{\mu}, \ln\tilde{\sigma}) = \frac{1}{2}\sum_{i=1}^{n}\left(\frac{\tilde{x}_i - \tilde{\mu}}{\tilde{\sigma}}\right)^2 + n\bigl(\ln\tilde{\sigma} + \ln P_{\text{in}}(\tilde{\mu}, \tilde{\sigma}; \tilde{a}, \tilde{b})\bigr) \tag{5}$$

$$\sigma_{\mu} = s\sqrt{\bigl(H^{-1}\bigr)_{00}}, \qquad \sigma_{\sigma} = \sigma\sqrt{\bigl(H^{-1}\bigr)_{11}} \tag{6}$$

$$\sigma_{68} = \frac{q_{0.84}(X_{\text{in}}) - q_{0.16}(X_{\text{in}})}{2} \tag{7}$$

where:

- $X$: full 1D input sequence of observed samples, in the units of the input quantity (in [../stages/analysis.md](../stages/analysis.md), the time difference $t_{\text{reco}} - t_{\text{truth}}$ in $\text{s}$);
- $m, \text{MAD}$: median and median absolute deviation of the full sample $X$, in the units of the input quantity; $[a_1, b_1]$ are the default initial window bounds;
- $a, b$: lower bound `low` and upper bound `high` of the current fitting window, in the units of the input quantity;
- $X_{\text{in}} = \{x_1, \dots, x_n\}$: subset of samples lying inside the closed interval $[a, b]$, where $n$ is the number of in-window samples (dimensionless);
- $s$: population standard deviation `np.std(values)` (`ddof=0`) of the in-window subsample $X_{\text{in}}$, in the units of the input quantity; $\tilde{x}_i = x_i / s$, $\tilde{a} = a / s$, and $\tilde{b} = b / s$ are dimensionless quantities scaled by $s$;
- $\mu, \sigma$: mean and standard deviation (core width) of the full Gaussian before truncation, in the units of the input quantity; $\tilde{\mu} = \mu / s$ and $\tilde{\sigma} = \sigma / s = \exp(\ln\tilde{\sigma})$ are the scaled dimensionless fit parameters;
- $P_{\text{in}}$: cumulative probability of the full Gaussian within the window $[a, b]$ (dimensionless, denoted `inside` in code), where $\operatorname{erf}$ is the error function;
- $\mathcal{L}(\tilde{\mu}, \ln\tilde{\sigma})$: unbinned negative log-likelihood function with parameter-independent constant terms omitted (dimensionless);
- $H$: $2\times 2$ Hessian (curvature) matrix of $\mathcal{L}$ with respect to $(\tilde{\mu}, \ln\tilde{\sigma})$ at the minimum (dimensionless); $\sigma_{\mu}$ and $\sigma_{\sigma}$ are the standard errors of the mean (`mean_error`) and core width (`sigma_error`) restored via the inverse Hessian and exponential error propagation, in the units of the input quantity;
- $q_{0.16}(X_{\text{in}}), q_{0.84}(X_{\text{in}})$: $16\%$ and $84\%$ quantiles of the in-window subsample $X_{\text{in}}$, in the units of the input quantity; $\sigma_{68}$ is the quantile half-width, in the units of the input quantity (equal to $\sigma$ for an ideal untruncated Gaussian distribution).

Single-round truncated-Gaussian maximum-likelihood fitting is solved by `truncated_gaussian(values, low, high)` in `resolution.py` using the `"L-BFGS-B"` algorithm of `scipy.optimize.minimize`; multi-round window-shrinking iteration is executed by `core_width(values, window=None)`, which uses Eq. (2) as the initial window when `window=None` and shrinks the window after each round to $[\mu - 2\sigma,\, \mu + 2\sigma]$ for at most `ROUNDS = 6` rounds. For maximum-likelihood parameter estimation of doubly truncated normal distributions, see Ref. [3]; for unbinned likelihood fitting and curvature covariance estimation, see Ref. [4]; for the bound-constrained limited-memory quasi-Newton algorithm L-BFGS-B, see Ref. [5].

### Straight Tracks and Residuals

When several devices are arranged along a beam as a telescope (see [Beam Telescope](../bench/telescope.md)), the cluster positions of each slot (`cluster_x`, `cluster_y` of [event reconstruction](reconstruction.md)) are transformed into global coordinates according to the slot's placement (Eqs. (17)–(18) of [Energy Deposition and Ionization](deposit.md#line-along-the-beam), evaluated at the mid-plane $z = l_z/2$ in device coordinates):

$$\begin{pmatrix} X \\ Y \end{pmatrix} = \begin{pmatrix} P_x \\ P_y \end{pmatrix} + \begin{pmatrix} \cos\phi & -\sin\phi \\ \sin\phi & \cos\phi \end{pmatrix}\begin{pmatrix} s\,(\bar{x}_c - l_x/2) \\ \bar{y}_c - l_y/2 \end{pmatrix}, \qquad Z = P_z + s\,\frac{l_z}{2} \tag{12}$$

For events in which every slot has exactly one cluster, an unweighted least-squares straight-line fit is performed separately on $(Z_j, X_j)$ and $(Z_j, Y_j)$ over the reference-layer set $\mathcal{R}$, followed by the residual at each slot and the chi-square of the reference track:

$$k_x = \frac{\sum_{j \in \mathcal{R}}(Z_j - \bar{Z})(X_j - \bar{X})}{\sum_{j \in \mathcal{R}}(Z_j - \bar{Z})^2}, \qquad b_x = \bar{X} - k_x \bar{Z} \tag{13}$$

$$r_{x,s} = k_x Z_s + b_x - X_s, \qquad r_{y,s} = k_y Z_s + b_y - Y_s, \qquad \chi^2 = \sum_{j \in \mathcal{R}}\left(\frac{r_{x,j}^2}{q_{x,j}^2/12} + \frac{r_{y,j}^2}{q_{y,j}^2/12}\right) \tag{14}$$

where:

- $(\bar{x}_c, \bar{y}_c)$: cluster position in the slot's device coordinates, $\mu\text{m}$;
- $\mathbf{P}$: world coordinates of the front-surface center of the slot's device, accumulated from `along_beam` by Eq. (17), $\mu\text{m}$; $\phi$: the slot's `rotation_z` (degrees); $s$: $+1$ when the slot's `facing` is `"upstream"` and $-1$ when it is `"downstream"`; $l_x, l_y, l_z$: dimensions of the device in that slot, $\mu\text{m}$;
- $(X, Y, Z)$: global coordinates of the cluster, $\mu\text{m}$; $\bar{X}, \bar{Z}$: arithmetic means of $X_j$ and $Z_j$ over the reference layers; $k_y$ and $b_y$ replace $X$ with $Y$ in Eq. (13);
- $k_x, k_y$: track slopes (dimensionless); $b_x, b_y$: track intercepts, $\mu\text{m}$;
- $r_{x,s}, r_{y,s}$: residual at slot $s$ (reference layer or DUT), track position minus cluster position, $\mu\text{m}$;
- $q_{x,j}, q_{y,j}$: pixel pitch of reference layer $j$ along the global $x$ and $y$ directions, $\mu\text{m}$: $(p_x, p_y)$ when $\phi$ is $0$ or $180$, and $(p_y, p_x)$ when $\phi$ is $90$ or $270$;
- $\chi^2$: sum of reference-layer residuals normalized by the uniform pixel variance (dimensionless).

The width of the DUT residual distributions along $x$ and $y$ is obtained with the truncated-Gaussian fit of the previous section, giving the residual standard deviation $\sigma_{\text{Tol}}$. Implemented in `tracking.py`. For beam-telescope track fitting and residuals, see Ref. [9].

### Waveform Statistics and Position Calibration

For multi-event feature collections produced by the single-event reconstruction class `InputWaveform` (see [reconstruction.md](reconstruction.md) for its definition and feature extraction algorithms), `core/analysis` fits binned histograms with a Gaussian for timing quantities and spatial centroid residuals, with a Landau distribution for pulse charge, amplitude, and time over threshold, and constructs the 2D $\eta$ position-calibration relation between the intra-cell offset of the true hit position relative to the electrode pitch and the intra-cell offset of the reconstructed centroid:

$$f_{\text{gaus}}(x) = C \exp\!\left(-\frac{(x - \mu)^2}{2\sigma^2}\right) \tag{8}$$

$$\sigma_{\text{ps}} = 10^{12}\,\sigma, \qquad \sigma_{\sigma,\text{ps}} = 10^{12}\,\sigma_{\sigma} \tag{9}$$

$$f_{\text{landau}}(x) = C\,\phi_{\text{Landau}}\!\left(\frac{x - \text{MPV}}{\xi}\right) \tag{10}$$

$$\delta x_{\text{orig},i} = \frac{x_{\text{orig},i}}{p_x} - \operatorname{round}\!\left(\frac{x_{\text{orig},i}}{p_x}\right), \qquad \delta g_i = g_i - \operatorname{round}(g_i) \tag{11}$$

where:

- $f_{\text{gaus}}(x), f_{\text{landau}}(x)$: Gaussian and Landau fit functions for the binned histograms (events/bin, dimensionless);
- $C$: histogram fit amplitude constant (ROOT parameter `0`, dimensionless);
- $\mu, \sigma$: binned Gaussian fit mean (ROOT parameter `1`) and standard deviation (ROOT parameter `2`), in the same units as the fitted quantity ($\text{s}$ for `ToA` and `CFD50`; multiples of electrode pitch, dimensionless, for centroid residuals `gravity_center_*_error`);
- $\sigma_{\text{ps}}, \sigma_{\sigma,\text{ps}}$: timing standard deviation $\sigma$ and its fit uncertainty $\sigma_\sigma$ converted from $\text{s}$ by multiplying by $10^{12}$ for display in the legend of `time_resolution_fit`, $\text{ps}$;
- $\text{MPV}, \xi$: location parameter (most probable value parameter, ROOT parameter `1`, printed as `mpv` and assigned to variable `mean` in code) and scale width parameter (ROOT parameter `2`, denoted `sigma` in code) of the Landau distribution, uniformly labeled `a.u.` in plot legends (`ToT` is supplied in $\text{s}$, while `amplitude` and `charge` follow the input voltage units of `InputWaveform`); $\phi_{\text{Landau}}$ is the standard Landau kernel;
- $x_{\text{orig},i}$: true track horizontal coordinate `original_x` of event $i$, $\mu\text{m}$;
- $p_x$: effective readout electrode pitch `pitch_x` along $x$, $\mu\text{m}$;
- $g_i$: 1D cluster center of gravity `gravity_center_*` of event $i$ weighted by `ToT`, `amplitude`, or `charge` (continuous 0-based electrode index, dimensionless, provided by `get_gravity_center_and_cluster_size` in [reconstruction.md](reconstruction.md));
- $\delta x_{\text{orig},i}, \delta g_i$: normalized intra-cell offsets of the true position and reconstructed centroid relative to the nearest integer electrode center (dimensionless, in $[-0.5, 0.5]$).

Eqs. (8) and (10) are fitted by `fit_data_normal` and `fit_data_landau` in `waveform_stats.py` using `ROOT.TF1` built-in models `'gaus'` and `'landau'` (with `TH1.Fit` option `"ROQ+"`); Eqs. (9) and (11) are implemented by `WaveformStatistics.time_resolution_fit` and `WaveformStatistics.ita_calibration`, respectively. For the Landau distribution of ionization energy loss in thin layers, see Ref. [6]; for charge-sharing centroids and $\eta$ position calibration in semiconductor strip detectors, see Ref. [7]; for the ROOT data analysis and fitting framework, see Ref. [8].

## Algorithm

### Built-in Constants

The table below lists all built-in physical constants and hard-coded algorithmic values in `collection.py`, `resolution.py`, and `waveform_stats.py`. All are module constants or in-function literals with no corresponding configuration keys in device or component files:

| Constant or Hard-Coded Value | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | $\text{C}$ | Elementary charge $e$ used in `collection.py` to convert total initial ionization charge |
| `ROUNDS` | `6` | rounds | Maximum number of window-shrinking iterations in `core_width` (`resolution.py`) |
| `MINIMUM_EVENTS` | `20` | count | Minimum total sample count and minimum per-round in-window sample count required by `core_width` (`resolution.py`) |
| Initial-window half-width multiplier | `8` | dimensionless | Multiple of `deviation` ($\text{MAD}$) around `median` used by `core_width` when `window=None` |
| Shrunk-window half-width multiplier | `2` | dimensionless | Multiple of `sigma` around `mean` used by `core_width` after each round to set the next window bounds `mean ± 2 * sigma` |
| `sigma` convergence tolerance | `5e-3` | dimensionless | Relative change threshold ($0.5\%$) used by `core_width` to declare `sigma` converged between consecutive rounds |
| Window-shrinking tolerance | `1e-3` | dimensionless | Relative width reduction threshold ($0.1\%$) below which `core_width` stops shrinking the window |
| Quantile interval | `[0.16, 0.84]` | dimensionless | Quantile endpoints used by `core_width` to compute `sigma68` from in-window samples |
| `step` | `1e-4` | dimensionless | Dimensionless parameter step used by `truncated_gaussian` for the second-order central-difference Hessian of the negative log-likelihood |
| `CFD_LABEL` | `"CFD50"` | none | Constant-fraction timing channel key name imported into `waveform_stats.py` from `raser.core.reconstruction.event` |
| Waveform plot cap | `100` (`count > 100`) | waveforms | Maximum number of overlaid waveforms plotted per readout electrode by `WaveformStatistics.draw(vis=True)` (at most `101` added) |
| `n2_bin` (standard / `CFD50`) | `100` / `30` | bins | `TH1F` bin counts in `time_resolution_fit` (`100` bins by default; `30` bins over the sorted `[2%, 98%]` quantile interval when `model == "CFD50"` and sample count $\ge 20$), `amplitude_fit` (`100` bins), and `gravity_center_error_fit` (`100` bins) |
| `n2_bin` (centroid distribution) | `400` (`10*40`) | bins | Fixed `TH1F` bin count for the 1D centroid histogram in `gravity_center_fill` |
| Cluster-size binning | `11`, `[0, 11)` | bins, count | Bin count and bounds of the integer histogram `TH1I` in `cluster_size_fill` |
| Centroid-residual half-window width | `1` | electrode pitches | Half-width around the median sample `mid` defining the fitting range `[mid - 1, mid + 1]` in `gravity_center_error_fit` |
| `n_x`, `n_y`, `[x_min, x_max]`, `[y_min, y_max]` | `20`, `20`, `[-0.5, 0.5]`, `[0.5, -0.5]` | bins, electrode pitches | Bin counts and axis bounds of the 2D histogram `TH2F` in `ita_calibration` |

### Charge Collection Efficiency Calculation and Small-Sample Handling

`collection_efficiency(charge, pairs)` (`collection.py`) executes the following steps:

1. **Array conversion and shape validation**: Convert inputs to double-precision arrays `charge = np.asarray(charge, dtype="float64")` and `pairs = np.asarray(pairs, dtype="float64")`. If `charge.ndim != 2` or `pairs.shape != charge.shape[:1]`, raise `ValueError: charge has shape <charge.shape> and pairs <pairs.shape>, expected (events, electrodes) and (events,)`.
2. **Positive initial-pair check**: Check `np.any(pairs <= 0)`. If any event has `pairs <= 0`, extract all zero- or negative-pair indices `np.flatnonzero(pairs <= 0).tolist()` and raise `ValueError: events <indices> have no pairs`.
3. **Compute per-event collection efficiency**: Return `np.abs(charge.sum(axis=1)) / (pairs * ELEMENTARY_CHARGE)` per Eq. (1), with output shape `(events,)`.
4. **Point aggregation and small-sample handling**: Downstream in `efficiency_spread(efficiencies)` of [../stages/analysis.md](../stages/analysis.md), if the number of recorded events aggregated for a scan point is `count = len(efficiencies) < 2`, `TooFewValues: <count> events in the point, a mean and a spread need at least 2` is raised; the stage entry point `write_point` catches this exception, records `{"events": count, "error": str(too_few)}` in the `"collection"` section of `result.json`, and skips generating `efficiency.png`. When `count >= 2`, the unbiased sample standard deviation `spread = float(np.std(efficiencies, ddof=1))` and the standard error of the mean `spread / np.sqrt(count)` are computed.

### Single-Round Truncated-Gaussian Fit and Fit-Failure Handling

`truncated_gaussian(values, low, high)` (`resolution.py`) fits the sample array `values` already filtered to `[low, high]` in the following order:

1. **Scale normalization and constant-sample check**: Compute the population standard deviation of the in-window samples `scale = float(np.std(values))`. If `scale == 0`, raise `ValueError: all values in the window are equal`. Otherwise set `x = np.asarray(values, dtype="float64") / scale`, `a = low / scale`, `b = high / scale`, and `n = len(x)`.
2. **Bound-constrained negative log-likelihood minimization**: Define the parameter vector `parameters = [mean, ln_sigma]`, where $\tilde{\sigma} = \exp(\text{parameters}[1])$. At each evaluation, compute the standardized residuals `z = (x - mean) / sigma` and the in-window cumulative probability `inside` from Eq. (4), returning `float(0.5 * np.dot(z, z) + n * (parameters[1] + math.log(inside)))` per Eq. (5). Call `scipy.optimize.minimize` with initial guess `[float(x.mean()), 0.0]`, `method="L-BFGS-B"`, and `bounds=[(a, b), (None, None)]` to constrain the mean within `[a, b]`.
3. **Raise on non-convergence**: If the optimizer returns `not fit.success`, immediately raise `ArithmeticError: the fit in [<low>, <high>] did not converge: <fit.message>`.
4. **Central-difference Hessian inversion and rescaling**: At the optimal parameters `fit.x`, take `step = 1e-4` and iterate over symmetric index pairs `(i, j) in ((0, 0), (0, 1), (1, 1))` with $\mathbf{d}_i = \text{step}\cdot\mathbf{e}_i$ and $\mathbf{d}_j = \text{step}\cdot\mathbf{e}_j$, computing the $2\times 2$ curvature matrix `curvature` via the four-point second-order central difference:
   $$\text{curvature}[i, j] = \text{curvature}[j, i] = \frac{\mathcal{L}(\hat{\boldsymbol{\theta}} + \mathbf{d}_i + \mathbf{d}_j) - \mathcal{L}(\hat{\boldsymbol{\theta}} + \mathbf{d}_i - \mathbf{d}_j) - \mathcal{L}(\hat{\boldsymbol{\theta}} - \mathbf{d}_i + \mathbf{d}_j) + \mathcal{L}(\hat{\boldsymbol{\theta}} - \mathbf{d}_i - \mathbf{d}_j)}{4 \times (10^{-4})^2}$$
   Compute the square roots of the diagonal of the inverse `mean_error, ln_sigma_error = np.sqrt(np.diag(np.linalg.inv(curvature)))`, set `mean = fit.x[0]` and `sigma = math.exp(fit.x[1])`, and return the rescaled tuple `(mean * scale, mean_error * scale, sigma * scale, sigma * ln_sigma_error * scale)`.

### Multi-Round Window-Shrinking Iteration for Core Width and Insufficient-Event Handling

`core_width(values, window=None)` (`resolution.py`) iteratively extracts the distribution core width as follows:

1. **Input dimension and total sample-count check**: Convert `values` to a `float64` array. If `values.ndim != 1`, raise `ValueError: values have shape <values.shape>, expected (events,)`. If the total sample count `len(values) < MINIMUM_EVENTS` (`20`), raise `TooFewValues: <len(values)> values, fewer than 20`.
2. **Set and validate the initial window**:
   - If `window is None`, compute `median = np.median(values)` and `deviation = np.median(np.abs(values - median))`, and set `low = median - 8 * deviation` and `high = median + 8 * deviation` per Eq. (2) (code comment notes: the initial window is not clamped to the sample min/max so that with small samples, window endpoints anchored on extreme data points do not make the distribution appear flat to the fit);
   - If `window` is not `None`, unpack `low, high = window`.
   - If `not low < high` (including `low >= high` or `NaN`), raise `ValueError: the window [<low>, <high>] is empty`.
3. **Iterative window-shrinking fits (at most `ROUNDS = 6` rounds)**: Initialize `fit = None`, and for `round_ = 1, ..., 6`:
   - **Select in-window samples**: Filter the closed-interval subset `inside = values[(values >= low) & (values <= high)]`.
   - **Check in-window sample count**: If `len(inside) < MINIMUM_EVENTS` (`20`):
     - If `fit is None` (fewer than `20` samples even in the first round), raise `TooFewValues: <len(inside)> of <len(values)> values are inside [<low>, <high>], fewer than 20`;
     - If `fit is not None` (fewer than `20` samples after shrinking in a later round), immediately `break` out of the loop and return the completed `fit` from the previous round.
   - **Single-round fit and statistics recording**: Set `previous = fit`, call `truncated_gaussian(inside, low, high)` to obtain `mean, mean_error, sigma, sigma_error`, compute `sigma68 = float(np.diff(np.quantile(inside, [0.16, 0.84]))[0] / 2)` per Eq. (7), and store the current round's result dictionary `fit` (with keys `"events"`, `"window"`, `"window_events"`, `"rounds"`, `"mean"`, `"mean_error"`, `"sigma"`, `"sigma_error"`, `"sigma68"`).
   - **Check three convergence and stopping criteria**:
     1. If `previous is not None` and `abs(sigma - previous["sigma"]) <= 5e-3 * previous["sigma"]`, `break` to stop iterating;
     2. Compute the next candidate window `new_low = mean - 2 * sigma`, `new_high = mean + 2 * sigma`; if `new_low < low` or `new_high > high` (either bound extends outside the current window), `break` to stop iterating;
     3. If `(high - low) - (new_high - new_low) <= 1e-3 * (high - low)` (the window width shrinks by no more than $0.1\%$), `break` to stop iterating.
   - **Update the window**: Set `low, high = new_low, new_high` and proceed to the next round.
4. **Return and downstream exception handling**: Return `fit` after the loop ends. In `time_widths` and `write_point` of [../stages/analysis.md](../stages/analysis.md), `NaN` samples are dropped from each timing channel before calling `core_width`: if `TooFewValues` is raised, `write_point` catches it, records the reason in `timing.error` of `result.json`, and skips drawing timing distribution plots; if at least `20` samples exist but `truncated_gaussian` raises `ArithmeticError` or `ValueError`, or if the sample MAD is `0` causing `core_width` itself to raise `ValueError: the window [...] is empty`, the exception propagates upward and aborts the job. A MAD of `0` means more than half of the `time - truth` values on that channel are identical, and both bounds shown in the error message equal that value; `events.h5` and `amplitude.png` have already been written at that point, so those identical differences between that channel and `truth` can be inspected in `events.h5`, and `core_width(values, window=(low, high))` can then be called in Python with an explicit initial window.

### Track Fitting and DUT Residual Widths (`tracking.py`)

`track_events(hits, placements, roles)` joins the reconstruction results of all slots of one job into tracks. All three arguments are dictionaries keyed by slot name, with slot order taken from `placements`; the function uses only the passed-in data. `hits[slot]` is `SlotHits(event, clusters, cluster_x, cluster_y)`, taken from the columns of the same names in that slot's event table. `placements[slot]` is `Placement(front, facing, rotation_z, l_x, l_y, l_z, p_x, p_y)`, where `front` is $\mathbf{P}$ of Eq. (12) (`[x, y, z]`, $\mu\text{m}$), worked out by the caller from the setup's `along_beam`. `roles[slot]` is `"reference"` or `"dut"`.

1. **Input validation**: if the slot names of the three dictionaries differ, raise `ValueError` (`the slots of hits, placements and roles differ`); if there are fewer than `2` reference layers, or if all reference layers have the same $Z$, raise `ValueError` (`a track needs reference layers at two or more z`); if `rotation_z` is not `0`, `90`, `180`, or `270`, or `facing` is not `"upstream"` or `"downstream"`, raise `ValueError`.
2. **Event alignment**: the union of event IDs across all slots, sorted in ascending order, gives the rows of the result; for an event not recorded at a slot, that slot's cluster count is `0`.
3. **Selection**: events in which every slot has exactly `1` cluster are marked `selected = True`.
4. **Coordinate transformation and fitting**: slots with `1` cluster compute $(X, Y)$ via Eq. (12), otherwise `NaN`. Selected events compute $k_x, b_x, k_y, b_y$ via Eq. (13) and the residuals at all slots and $\chi^2$ via Eq. (14); for unselected events these quantities are `NaN`.
5. Return `TrackEvents`: `slots`, `roles`, `z` (the $Z$ of each slot), and the columns `event`, `selected`, `x`, `y` (`(events, slots)`), `kx`, `bx`, `ky`, `by`, `chi2` (`(events,)`), `residual_x`, `residual_y` (`(events, slots)`).

`residual_widths(tracks)` reads the `TrackEvents` of all jobs at a scan point. If `slots` or `roles` differ across jobs, it raises `ValueError`. For each slot with role `"dut"`, it concatenates `residual_x` and `residual_y` of the selected events of all jobs into separate columns, calls `core_width` on each, and returns `{slot: {"x": result, "y": result}}`, where each result is the dictionary returned by `core_width`, in $\mu\text{m}$, and `"sigma"` is $\sigma_{\text{Tol}}$ along that direction. If `core_width` raises `TooFewValues`, the result for that direction becomes `{"events": number of values, "error": error text}`.

### Waveform Statistics Accumulation and ROOT Histogram Fitting

`WaveformStatistics` (`waveform_stats.py`) processes single-event `InputWaveform.data` dictionaries and produces ROOT statistical plots in the following steps:

1. **Set electrode count and pitches from the device model (`__init__`)**: Read `det_model = my_d.det_model.lower()`:
   - If `det_model == 'planar'` or `det_model == 'lgad'`: set `my_d.read_ele_num` to `1`, `self.pitch_x = my_d.l_x`, and `self.pitch_y = my_d.l_y`;
   - If `'strip' in det_model`: keep `my_d.read_ele_num` unchanged, set `self.pitch_x = my_d.p_x` and `self.pitch_y = my_d.l_y`;
   - If `'pixel' in det_model`: set `my_d.read_ele_num` to `my_d.x_ele_num * my_d.y_ele_num`, `self.pitch_x = my_d.p_x`, and `self.pitch_y = my_d.p_y`;
   - Otherwise raise `ValueError: Unsupported detector model for waveform statistics: <my_d.det_model>`.
   Then initialize `self.data = {}` and `self.waveforms = [[] for i in range(my_d.read_ele_num)]`.
2. **Append single-event features (`fill_data`)**: For every `key` in the input dictionary `data`, append `data[key]` to `self.data[key]`.
3. **Validate output tag and optionally plot overlaid waveforms (`draw(output_path, tag, vis=False)`)**:
   - If `tag is None`, raise `ValueError: Waveform statistics output tag must be explicit`.
   - Create directory `Path(output_path).mkdir(parents=True, exist_ok=True)`.
   - If `vis == True`, for each electrode $j \in [0, \text{read\_ele\_num} - 1]$, iterate through `self.waveforms[j]` breaking when `count > 100` (at most the first `101` waveforms per electrode), build a `ROOT.TMultiGraph`, and save `waveform_electrode_<j>.pdf` and `.png`.
4. **Binned Gaussian fit of timing distributions (`time_resolution_fit`)**: Filter `None` via `remove_none` on `self.data["ToA"]` and `self.data["CFD50"]` in turn:
   - Take `x2_min = min(data)` and `x2_max = sorted(data)[len(data) - 1]` (if `data` is empty, catch `ValueError`, print `"No valid data for <model>"`, and set `x2_min = 0`, `x2_max = 0`), with default `n2_bin = 100`.
   - If `model == "CFD50"` and `len(data) >= 20`, set `x2_min` and `x2_max` to the elements of `sorted_data` at indices `int(0.02 * (len(sorted_data) - 1))` and `int(0.98 * (len(sorted_data) - 1))`, and set `n2_bin = 30`.
   - Fill `ROOT.TH1F("", "", n2_bin, x2_min, x2_max)`, call `fit_data_normal` to fit `'gaus'` (option `"ROQ+"`) on `[x2_min, x2_max]`, multiply `sigma` and `sigma_error` by `1e12` to convert to $\text{ps}$ per Eq. (9), and write `<tag>_<model>.pdf` and `.C`. Both the input and return values of the fit are in $\text{s}$, becoming $\text{ps}$ after multiplication by `1e12`.
5. **Binned Landau fit of charge, amplitude, and time over threshold (`amplitude_fit`)**: Filter `None` on `self.data["charge"]`, `self.data["amplitude"]`, and `self.data["ToT"]` in turn, fill a `100`-bin `ROOT.TH1F` over `[min(data), max(data)]` (setting `[0, 0]` when catching `ValueError` on an empty list), call `fit_data_landau` to fit `'landau'` (option `"ROQ+"`) on `[x2_min, x2_max]`, print `%.3g #pm %.3g a.u.` in the legend (Landau `mpv` and `sigma`), and write `<tag>_<model>.pdf` and `.C`.
6. **Cluster centroid and cluster size histograms (`gravity_center_fill`, `cluster_size_fill`)**:
   - `gravity_center_fill` filters `None` on `"gravity_center_ToT"`, `"gravity_center_amplitude"`, and `"gravity_center_charge"` in turn over `[min(data), max(data)]`; if empty (`IndexError` or `ValueError`), print `"No valid data for <model>"` and return immediately. When non-empty, fill a `400`-bin `ROOT.TH1F` and write `<tag>_<model>.pdf` and `.C`. The bin count `n2_bin = 10*40` is chosen for strip detectors and hard-coded.
   - `cluster_size_fill` filters `None` on `self.data["cluster_size_ToT"]`, `self.data["cluster_size_amplitude"]`, and `self.data["cluster_charge"]` (written with filename label `"cluster_size_charge"`), fills a `ROOT.TH1I` with `11` bins over `[0, 11)`, and writes `<tag>_<model>.pdf` and `.C`.
7. **Binned Gaussian fit of centroid position residuals (`gravity_center_error_fit`)**: Filter `None` on `"gravity_center_ToT_error"`, `"gravity_center_amplitude_error"`, and `"gravity_center_charge_error"` in turn and take the sorted median `mid = sorted(data)[int(len(data) / 2)]`; if empty (`IndexError`), print `"No valid data for <model>"` and return immediately. When non-empty, fill a `100`-bin `ROOT.TH1F` on `[mid - 1, mid + 1]`, fit `'gaus'` via `fit_data_normal`, and write `<tag>_<model>.pdf` and `.C`.
8. **2D $\eta$ position-calibration histogram (`ita_calibration`)**: Pair `"gravity_center_ToT"`, `"gravity_center_amplitude"`, and `"gravity_center_charge"` with `self.data["original_x"]` in turn, discard events whose centroid is `None`, fill a `20 × 20`-bin `ROOT.TH2F("", "", 20, -0.5, 0.5, 20, 0.5, -0.5)` according to Eq. (11), draw with `"COLZ"`, and write `<tag>_<model>.pdf` and `.C`. The vertical axis bounds are passed as `y_min = 0.5` and `y_max = -0.5`.

## Software Implementation

### Module and Function Responsibilities

- `collection.py`: defines the elementary charge constant `ELEMENTARY_CHARGE` and implements the per-event charge collection efficiency function `collection_efficiency`.
- `resolution.py`: defines the constants `ROUNDS`, `MINIMUM_EVENTS`, and the insufficient-sample exception class `TooFewValues`, and implements single-window unbinned truncated-Gaussian maximum-likelihood fitting `truncated_gaussian` and multi-round window-shrinking core-width estimation `core_width`.
- `tracking.py`: implements the experiment-level statistics of the telescope. `track_events` transforms the clusters of each slot into global coordinates, fits straight tracks, and computes residuals; `residual_widths` gives the core width of each DUT's residuals; `draw_track` and `draw_residual` draw the plots.
- `waveform_stats.py`: implements the PyROOT binned Gaussian fit `fit_data_normal`, the binned Landau fit `fit_data_landau`, and the statistical plotting class `WaveformStatistics` for single-event reconstruction dictionaries.

### Core Data Structures

- Return dictionary of `core_width` (`resolution.py`): fit result dictionary for the core width of a single channel's distribution, containing total input sample count `"events"` (count), final-round fitting window `"window"` (two-element float tuple `(low, high)`, in the same units as input `values`), in-window sample count of the final round `"window_events"` (count), number of rounds actually performed `"rounds"` (rounds), truncated-Gaussian fitted mean `"mean"` and standard error `"mean_error"` (same units as input), truncated-Gaussian fitted standard deviation `"sigma"` and standard error `"sigma_error"` (same units as input), and half the $16\%$–$84\%$ quantile span of the final-round in-window samples `"sigma68"` (same units as input).
- `TooFewValues` (`resolution.py`): exception class inheriting from `ValueError`, indicating that the total sample count or first-round in-window sample count is below the statistical minimum (`< 20` in `core_width`, `< 2` in `efficiency_spread` of `stages/analysis`), representing a statistical-outcome state rather than a fitting-algorithm crash.
- `WaveformStatistics` (`waveform_stats.py`): multi-event waveform feature accumulator and ROOT plotting instance containing the device object `detector` (`Detector`), effective readout electrode pitches `pitch_x` and `pitch_y` ($\mu\text{m}$), crossing threshold `threshold` and amplitude threshold `amplitude_threshold` (same voltage units as `InputWaveform`), output directory path string `output_path` (populated after calling `draw`), feature dictionary `data` collecting per-event values by name (`"ToA"`, `"CFD50"`, `"ToT"` [$\text{s}$]; `"amplitude"`, `"charge"` [same voltage units as input]; `"gravity_center_*"`, `"gravity_center_*_error"` [multiples of electrode pitch, dimensionless]; `"cluster_size_*"`, `"cluster_charge"` [count]; `"original_x"` [$\mu\text{m}$]), and per-electrode list `waveforms` storing `(t, v)` traces (time in $\text{s}$, voltage in the input waveform's units).

## Interface

For the command-line entry point and multi-point experiment aggregation workflow, see [../stages/analysis.md](../stages/analysis.md). All inputs to `collection_efficiency` and `core_width` come from function arguments; the statistical analysis stage calls `core_width` with default `window=None`, so an explicit initial window can be given only when calling it directly from Python (the reconstruction thresholds, constant-fraction list, and edge directions needed by [../stages/analysis.md](../stages/analysis.md) are read from the attributes of upstream `reconstruction.h5`). When instantiating `WaveformStatistics(my_d, threshold, amplitude_threshold)` in Python, the device keys listed below are read from the `Detector` instance; all other parameters—number of fit rounds, minimum event count, window multipliers, Hessian step size, and histogram binning—are hard-coded.

### Keys Read from Device Files

| Key or Derived Attribute | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `det_model` | none (required by `WaveformStatistics`) | none | Device model identifier; lowercased value must be `'planar'`, `'lgad'`, or contain `'strip'` or `'pixel'`, determining the readout electrode count and `pitch_x`, `pitch_y` |
| `l_x`, `l_y` | none (required) | $\mu\text{m}$ | Used as `pitch_x` and `pitch_y` for `'planar'` or `'lgad'`; `l_y` is used as `pitch_y` for `'strip'` |
| `p_x`, `p_y` | see [device.md](device.md) | $\mu\text{m}$ | `p_x` is used as `pitch_x` for `'strip'` or `'pixel'`; `p_y` is used as `pitch_y` for `'pixel'` |
| `read_ele_num` | see [device.md](device.md) | count | Total number of readout electrodes; overwritten in place by `WaveformStatistics.__init__` to `1` for `'planar'`/`'lgad'` and to `x_ele_num * y_ele_num` for `'pixel'` |
| `x_ele_num`, `y_ele_num` | see [device.md](device.md) | count | Used in `'pixel'` mode to compute the total readout electrode count `x_ele_num * y_ele_num` |

### Input and Output Files

When [../stages/analysis.md](../stages/analysis.md) invokes `collection_efficiency` and `core_width`, it reads HDF5 files from the `deposit`, `current`, and `reconstruction` nodes of the same scan point, accessed via `points/<point>/deposit/`, `points/<point>/current/`, and `points/<point>/reconstruction/`. Single-point outputs `events.h5` and `result.json` are written into that point's `analysis` node, accessed via `points/<point>/analysis/`; the cross-point output `points.json` is written under `<experiment>/analysis/`.

#### Attributes and Datasets of Upstream Input Files

| Source File | Name and Category | Shape and Type | Unit | Purpose |
| --- | --- | --- | --- | --- |
| `current.h5` ([current.md](current.md)) | Dataset `event` | `(events,)`, `int64` | none | Verified to match the event ID set of `reconstruction.h5` exactly |
| `current.h5` ([current.md](current.md)) | Dataset `charge` | `(events, len(electrodes))`, `float64` | $\text{C}$ | Passed as `charge` to `collection_efficiency(charge, pairs)` |
| `current.h5` ([current.md](current.md)) | Dataset `pairs` | `(events,)`, `float64` | pairs | Passed as `pairs` to `collection_efficiency(charge, pairs)` |
| `reconstruction.h5` ([reconstruction.md](reconstruction.md)) | Attribute `electrodes` | string array | none | Checks the single-electrode constraint (`len(electrodes) == 1`) |
| `reconstruction.h5` ([reconstruction.md](reconstruction.md)) | Attributes `threshold`, `amplitude_threshold`, `fractions`, `edge` | `float64`, `float64`, `float64[]`, string array | $\text{V}$, $\text{V}$, dimensionless, none | Verifies that reconstruction parameters agree across all jobs of the scan point, and divides both thresholds by `1e-3` to write them in $\text{mV}$ to `result.json` |
| `reconstruction.h5` ([reconstruction.md](reconstruction.md)) | Datasets `event`, `selected` | `(events,)`, `int64` / `bool` | none | Filters selected events satisfying `selected == True` |
| `reconstruction.h5` ([reconstruction.md](reconstruction.md)) | Datasets `ToA`, `ToT`, `CoG`, `amplitude`, `baseline`, `noise` | `(events, electrodes)`, `float64` | first three $\text{s}$, last three $\text{V}$ | Extracts timing and waveform voltage quantities on electrode `0` for selected events |
| `reconstruction.h5` ([reconstruction.md](reconstruction.md)) | Dataset `CFD` | `(events, electrodes, fractions)`, `float64` | $\text{s}$ | Extracts `CFD<round(100*part)>` timestamps on electrode `0` for each constant fraction `part` of selected events |
| `deposit.h5` ([deposit.md](deposit.md)) | Datasets `event`, `count`, `t` | `(recorded_events,)`, `int64` / `(sum(count),)`, `float64` | none, steps, $\text{s}$ | Takes the minimum `t` across all deposition steps of each event as the true reference time `truth` ($\text{s}$), passing `time - truth` to `core_width` |

Limitation: for single-slot experiments, `analysis` currently computes statistics only for single-electrode results; multi-electrode statistics (such as summaries across cflm pads) are not yet implemented.

A multi-slot telescope reads `reconstruction.<slot>.h5` of every slot in the `reconstruction` nodes of all jobs at the same scan point and passes the four columns `event`, `clusters`, `cluster_x`, `cluster_y` to `track_events`; the seed and the hit time of each layer are given by `reconstruction` and only read here. `events.h5` then holds one row per selected event, with datasets `job`, `event`, `kx`, `ky` (dimensionless), `bx`, `by` ($\mu\text{m}$), `chi2` (dimensionless), and for every slot `x.<slot>`, `y.<slot>`, `residual_x.<slot>`, `residual_y.<slot>` ($\mu\text{m}$); `residual.<slot>.x` and `residual.<slot>.y` in `result.json` are the results of `residual_widths` for each DUT.

#### Output File `events.h5`

When the total number of recorded events at a scan point is $\ge 1$, `points/<point>/analysis/events.h5` is written. The file has no HDF5 attributes and contains the following 1D datasets whose length equals the number of selected events `selected`:

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `job` | `(selected,)`, `int64` | none | 0-based index of the event's job in the scan point's job list `jobs` |
| `event` | `(selected,)`, `int64` | none | Geant4 event ID within its job |
| `ToA` | `(selected,)`, `float64` | $\text{s}$ | Arrival time at which the pulse crosses `threshold` (`NaN` if not found) |
| `ToT` | `(selected,)`, `float64` | $\text{s}$ | Duration of the pulse above `threshold` |
| `amplitude` | `(selected,)`, `float64` | $\text{V}$ | Maximum pulse amplitude above baseline |
| `baseline` | `(selected,)`, `float64` | $\text{V}$ | Arithmetic mean of the leading `200` samples of the waveform |
| `noise` | `(selected,)`, `float64` | $\text{V}$ | Population standard deviation of the leading `200` samples of the waveform |
| `truth` | `(selected,)`, `float64` | $\text{s}$ | Time of the earliest deposition step of the event in `deposit.h5` |
| `CoG` | `(selected,)`, `float64` | $\text{s}$ | Sample-weighted center-of-gravity time over the interval above threshold |
| `CFD<percent>` | `(selected,)`, `float64` | $\text{s}$ | Constant-fraction timing timestamp, where `<percent>` is `round(100 * part)` (`NaN` if not found) |

#### Statistics in Output Files `result.json` and `points.json`

In the table below, `result.json` refers to `points/<point>/analysis/result.json` and `points.json` refers to `<experiment>/analysis/points.json`.

| File and Key Path | Type or Shape | Unit | Meaning |
| --- | --- | --- | --- |
| `result.json`: `reconstruction.threshold`, `amplitude_threshold` | `float` | $\text{mV}$ | Reconstruction crossing threshold and cluster-seed channel amplitude threshold (written when recorded events exist) |
| `result.json`: `reconstruction.fractions`, `edge` | `list[float]`, `list[str]` | dimensionless, none | Constant-fraction timing fraction list and per-electrode pulse-edge directions (written when recorded events exist) |
| `result.json`: `collection.events` | `int` | count | Total number of recorded events at the scan point |
| `result.json`: `collection.mean`, `mean_error`, `spread` | `float` | dimensionless | Mean, standard error of the mean, and sample standard deviation (`ddof=1`) of `collection_efficiency` over all recorded events (written when `events >= 2`) |
| `result.json`: `collection.error` | `str` | none | `TooFewValues` message written in place of `mean`, `mean_error`, and `spread` when `events < 2` |
| `result.json`: `timing.events`, `selected` | `int` | count | Total number of recorded events and number of selected events at the scan point |
| `result.json`: `timing.polarity` | `float` | dimensionless | Pulse-edge polarity sign: `1.0` for `"rising"`, `-1.0` for `"falling"` (written when recorded events exist) |
| `result.json`: `timing.times.<channel>` | `dict` | see right | `<channel>` is `"ToA"`, `"CoG"`, or each `"CFD<percent>"`; contains `"events"` (count), `"window"` (`[low, high]`, $\text{s}$), `"window_events"` (count), `"rounds"` (rounds), `"mean"`, `"mean_error"`, `"sigma"`, `"sigma_error"`, `"sigma68"` (all $\text{s}$) computed by `core_width` on non-`NaN` `time - truth` values, plus `"missing"` (count of selected events where the channel is `NaN`) |
| `result.json`: `timing.error` | `str` | none | Explanation written in place of `timing.times` when the point has `0` events or any timing channel triggers `TooFewValues` |
| `points.json`: `[i].point`, `[i].<scanned_key>` | `str`, depends on option | none, depends on option | Written when more than `1` scan point has results; point name and values of scan options that vary across points |
| `points.json`: `[i].events`, `efficiency`, `efficiency_error`, `selected` | `int`, `float \| null` | count, dimensionless | Total recorded events, mean charge collection efficiency and standard error (`null` when unavailable), and selected event count at that point |
| `points.json`: `[i].<channel>` | `dict` | $\text{s}$ | `{"sigma68", "sigma", "sigma_error"}` for each timing channel at that point (omitted when timing resolution is unavailable at that point) |

### Plot Output

The table below lists the ROOT statistical plots generated directly by `WaveformStatistics.draw(output_path, tag, vis)` and the Matplotlib statistical plots generated by [../stages/analysis.md](../stages/analysis.md) from the outputs of `collection_efficiency` and `core_width`; among the latter, `points.png` is written under `<experiment>/analysis/` and the rest under `points/<point>/analysis/`:

| Filename | Content | Axis Units |
| --- | --- | --- |
| `waveform_electrode_<j>.pdf`, `.png` | Up to the first `101` overlaid waveforms (`TMultiGraph`) for electrode $j$, drawn by `WaveformStatistics.draw(vis=True)` | Horizontal axis $\text{s}$; vertical axis follows input waveform voltage units |
| `<tag>_ToA.pdf`, `.C`; `<tag>_CFD50.pdf`, `.C` | 1D timing histogram (`100` bins for `ToA`; `30` bins over the `[2%, 98%]` quantile interval for `CFD50` when sample count $\ge 20$) and `'gaus'` fit curve drawn by `WaveformStatistics.time_resolution_fit`, with $\sigma \pm \sigma_\sigma$ ($\text{ps}$) in the legend | Horizontal axis `<model> [s]`, vertical axis `Events` (count) |
| `<tag>_charge.pdf`, `.C`; `<tag>_amplitude.pdf`, `.C`; `<tag>_ToT.pdf`, `.C` | `100`-bin 1D histogram and `'landau'` fit curve drawn by `WaveformStatistics.amplitude_fit`, with `mpv ± sigma a.u.` in the legend | Horizontal axis `<model> [a.u.]` (filled `ToT` values are in $\text{s}$), vertical axis `Events` (count) |
| `<tag>_gravity_center_ToT.pdf`, `.C`; `..._amplitude.pdf`, `.C`; `..._charge.pdf`, `.C` | `400`-bin 1D cluster-centroid histogram drawn by `WaveformStatistics.gravity_center_fill` when data are non-empty | Horizontal axis `<model>` (electrode index, dimensionless), vertical axis `Events` (count) |
| `<tag>_cluster_size_ToT.pdf`, `.C`; `..._amplitude.pdf`, `.C`; `..._charge.pdf`, `.C` | `11`-bin integer cluster-size histogram `TH1I` over `[0, 11)` drawn by `WaveformStatistics.cluster_size_fill` | Horizontal axis `<model>` (electrode count), vertical axis `Events` (count) |
| `<tag>_gravity_center_ToT_error.pdf`, `.C`; `..._amplitude_error.pdf`, `.C`; `..._charge_error.pdf`, `.C` | `100`-bin 1D position-residual histogram over `mid ± 1` around the median and `'gaus'` fit curve drawn by `WaveformStatistics.gravity_center_error_fit` when data are non-empty | Horizontal axis `<model>` (multiples of electrode pitch, dimensionless), vertical axis `Events` (count) |
| `<tag>_ita_calibration_ToT.pdf`, `.C`; `..._amplitude.pdf`, `.C`; `..._charge.pdf`, `.C` | `20 × 20`-bin 2D $\eta$ position-calibration plot `TH2F` (`"COLZ"`) drawn by `WaveformStatistics.ita_calibration` | Horizontal axis `Original x` (`[-0.5, 0.5]`, electrode pitches), vertical axis `Reconstructed x` (`[0.5, -0.5]`, electrode pitches) |
| `track_<event>` | `draw_track` in `tracking.py` draws one for each of the first `analysis.plots` selected events: $X$-$Z$ on the left and $Y$-$Z$ on the right, filled markers for reference layers, open markers for DUTs, and the straight line of Eq. (13) | Horizontal axis `z [mm]`, vertical axes `x [μm]`, `y [μm]` |
| `residual_<slot>` | `draw_residual` in `tracking.py` draws one for each DUT: `residual_x` on the left and `residual_y` on the right, a `64`-bin histogram within `mean ± 8 * sigma`, the last-round window shaded, and the truncated-Gaussian curve, with $\sigma_{\text{Tol}}$ in the legend | Horizontal axes `Residual x [μm]`, `Residual y [μm]`, vertical axis `Events` |
| `efficiency.png` | `60`-bin charge collection efficiency histogram over all recorded events with a dashed vertical mean line, drawn by `stages/analysis` when recorded events $\ge 2$ | Horizontal axis `charge collection efficiency` (dimensionless), vertical axis `events` (count) |
| `amplitude.png` | `60`-bin pulse amplitude histogram of selected events with a dashed vertical `amplitude_threshold` line, drawn by `stages/analysis` when recorded events $\ge 1$ | Horizontal axis `amplitude above the baseline [mV]`, vertical axis `events` (count) |
| `time_difference.png` | `3 × 4` grid of `64`-bin time-difference histograms within `mean ± 8 * sigma` for `ToA`, `CoG`, and the first `10` `CFD*` channels, showing the final-round window shading and truncated-Gaussian curve, drawn by `stages/analysis` when timing fits succeed | Horizontal axis `<channel> - truth [ps]`, vertical axis event count |
| `resolution_of_fraction.png` | Truncated-Gaussian `sigma` (with error bars) and `sigma68` versus constant fraction across all `CFD*` channels, drawn by `stages/analysis` | Horizontal axis `fraction of the CFD` (dimensionless), vertical axis `width of time - truth [ps]` |
| `points.png` | Collection efficiency (left) and `sigma` of each `CFD*` channel (right) versus the scan variable, drawn by `stages/analysis` when multiple scan points exist and the sole varying scan parameter is numeric | Horizontal axis `<scanned_key>`, left vertical axis `charge collection efficiency` (dimensionless), right vertical axis `sigma of time - truth [ps]` |

## References

- [1] H. Spieler, *Semiconductor Detector Systems*, Oxford University Press (2005), ISBN 978-0-19-852784-8, doi:10.1093/acprof:oso/9780198527848.001.0001
- [2] E. Tiesinga, P. J. Mohr, D. B. Newell, B. N. Taylor, “CODATA recommended values of the fundamental physical constants: 2018”, Rev. Mod. Phys. 93 (2021) 025010, doi:10.1103/RevModPhys.93.025010
- [3] A. C. Cohen, “Estimating the Mean and Variance of Normal Populations from Singly Truncated and Doubly Truncated Samples”, Ann. Math. Statist. 21 (1950) 557, doi:10.1214/aoms/1177729751
- [4] F. James, *Statistical Methods in Experimental Physics*, 2nd ed., World Scientific (2006), doi:10.1142/6096
- [5] R. H. Byrd, P. Lu, J. Nocedal, C. Zhu, “A Limited Memory Algorithm for Bound Constrained Optimization”, SIAM J. Sci. Comput. 16 (1995) 1190, doi:10.1137/0916069
- [6] L. D. Landau, “On the energy loss of fast particles by ionisation”, in *Collected Papers of L. D. Landau*, Elsevier (1965) 417, doi:10.1016/B978-0-08-010586-4.50061-4
- [7] E. Belau, R. Klanner, G. Lutz, E. Neugebauer, H. J. Seebrunner, A. Wylie, T. Böhringer, L. Hubbeling, P. Weilhammer, J. Kemmer, U. Kötz, M. Riebesell, “Charge collection in silicon strip detectors”, Nucl. Instrum. Methods Phys. Res. 214 (1983) 253, doi:10.1016/0167-5087(83)90591-4
- [8] R. Brun, F. Rademakers, “ROOT — An object oriented data analysis framework”, Nucl. Instrum. Methods Phys. Res. A 389 (1997) 81, doi:10.1016/S0168-9002(97)00048-X
- [9] H. Jansen et al., “Performance of the EUDET-type beam telescopes”, EPJ Tech. Instrum. 3 (2016) 7, doi:10.1140/epjti/s40485-016-0033-2
