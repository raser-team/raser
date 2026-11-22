# Digitizer (`core/digitizer`)

`src/raser/core/digitizer/` is the underlying module of the [digitizer stage (`stages/digitizer`)](../stages/digitizer.md). It takes the amplified electrode voltage waveforms produced by [electronics readout](readout.md) and, according to the oscilloscope or digitizer-board settings in the [digitizer component](../components/digitizer.md), applies analog bandwidth, sampling, and quantization in sequence to produce the codes for each event and the clipped sample count for each electrode. The digitizer stage writes the result to a digital waveform file and passes it to the [trigger stage (`stages/trigger`)](../stages/trigger.md).

## Physics

### Bandwidth

The component's `response` selects the bandwidth response:

$$|H(f)| = \begin{cases} 1, & f \le B \\ 0, & f > B \end{cases}\quad(\texttt{"brickwall"}),\qquad |H(f)| = 1\quad(\texttt{"none"}) \tag{1}$$

where:

- $f$: frequency, $\text{Hz}$;
- $B$: analog bandwidth, $\text{Hz}$, taken from the component's `bandwidth_GHz` (multiplied by $10^9$);
- $H(f)$: response (dimensionless), zero-phase.

`"brickwall"` is an ideal brick wall, with a step-response $10\%$–$90\%$ rise time of $0.446/B$ ($74\ \text{ps}$ at $B = 6\ \text{GHz}$) and about $9\%$ pre- and post-ringing. `MXR608A` uses brick-wall filtering, for which the datasheet gives a rise time of $71.7\ \text{ps}$ ($0.43/B$) [1]. The ideal brick wall is an approximation to be verified: the shape of the transition band remains to be determined against the datasheet. `"none"` imposes no bandwidth limit and is used for the toy device.

### Sampling

The instrument's sampling clock is free-running and unsynchronized with the signal, so the phase of the first sample relative to the signal is random for each event; each sampling instant also carries aperture jitter. The $k$-th sampling time is:

$$t_k = t_0 + \varphi + k\,T_s + \delta_k,\qquad \varphi \sim U[0, T_s),\qquad \delta_k \sim \mathcal{N}(0, \sigma_a^2),\qquad k = 0, 1, \dots, K-1,\qquad K = \left\lfloor \frac{n_{\text{bin}}\,\Delta t}{T_s} \right\rfloor \tag{2}$$

where:

- $t_0$: left edge `t0` of the event's first time bin in the `readout` waveform, $\text{s}$; `readout` voltages are evaluated at the bin centers $t_0 + (i + \tfrac12)\Delta t$;
- $T_s$: sampling period, $T_s = 10^{-9}/$`sampling_rate_GSps`, $\text{s}$;
- $\varphi$: clock phase for that event and instrument, $\text{s}$; shared by all channels of the same instrument;
- $\delta_k$: aperture jitter at the $k$-th sample, $\text{s}$; $\sigma_a$ is taken from the component's `aperture_jitter_ps` (multiplied by $10^{-12}$), see Ref. [2];
- $n_{\text{bin}}$, $\Delta t$: number of time bins and bin width ($\text{s}$) of the event's `readout` waveform;
- $K$: number of samples per electrode, the same for all electrodes in an event.

The record window is determined by the length of the upstream waveform.

### Quantization

An $N$-bit ADC divides the full scale into $2^N$ levels, clipping points outside full scale to the maximum or minimum code:

$$\text{LSB} = \frac{V_{\text{FS}}}{2^N} \tag{3}$$

$$c = \min\!\left(\max\!\left(\left\lfloor \frac{V - V_{\text{off}}}{\text{LSB}} \right\rfloor + 2^{N-1},\ 0\right),\ 2^N - 1\right) \tag{4}$$

$$\hat V = \left(c - 2^{N-1} + 0.5\right)\text{LSB} + V_{\text{off}} \tag{5}$$

where:

- $V_{\text{FS}}$: full-scale range, $\text{V}$, taken from the component's `full_scale_V`;
- $N$: ADC bit depth, taken from the component's `bits`;
- $V$: voltage at the sampling instant, $\text{V}$;
- $V_{\text{off}}$: center of the range, $\text{V}$, taken from the component's `offset_V`;
- $c$: code, taking values $0, 1, \dots, 2^N - 1$;
- $\hat V$: voltage reconstructed from the code, $\text{V}$, taken at the midpoint of the bin.

On unclipped samples, the root-mean-square quantization error $V - \hat V$ is $\text{LSB}/\sqrt{12}$ (Ref. [3]).

### Noise-Only Channels

The `readout` noise is stationary Gaussian noise drawn from the single-sided amplitude spectral density $S_V(f)$, added linearly to the signal, and uncorrelated across outputs (see [Electronics Readout](readout.md#frequency-domain-thermal-noise-from-a-given-spectrum-and-time-domain-synthesis)). A channel with noise only remains a stationary Gaussian sequence after bandwidth limiting and sampling, with spectrum:

$$S_d^2(f) = \sum_{m=-\infty}^{\infty} S_V^2\!\left(|f + m f_s|\right)\,\bigl|H(f + m f_s)\bigr|^2,\qquad 0 \le f \le \frac{f_s}{2} \tag{6}$$

where:

- $f_s = 1/T_s$: sampling rate, $\text{Hz}$;
- $S_V(f)$: noise spectrum asset of that channel (see "Interface"), $\text{V}/\sqrt{\text{Hz}}$, taken as zero outside the asset frequency band;
- $S_d(f)$: single-sided amplitude spectral density of the sampled sequence, $\text{V}/\sqrt{\text{Hz}}$.

A noise-only channel uses the same synthesis method as `readout` (Eqs. (5)–(9) of [Electronics Readout](readout.md#frequency-domain-thermal-noise-from-a-given-spectrum-and-time-domain-synthesis)) to directly draw $K$ sampled voltages with spectrum $S_d$ and step $T_s$, and then quantizes them by Eq. (4); aperture jitter does not alter the statistics of stationary noise and is omitted here. Whether a channel takes the noise-only path is decided upstream before `current`; see "Interface" for the decision function.

## Algorithm

Each event is processed in the following order:

1. **Read**: Take the voltage sequences (`voltage` in the `readout` file, with time step `dt`) of all electrodes stored for that event, `t0`, and the component keys.
2. **Grouping and phase**: When the number of channels in the `readout` file's `electrodes` attribute exceeds `channels`, group them into blocks of `channels` in the order of `electrodes`, assigning one identical instrument per group. Draw one $\varphi$ from $U[0, T_s)$ per instrument, and draw one $\delta_k$ from $\mathcal{N}(0, \sigma_a^2)$ for each sample of each electrode.
3. **Bandwidth and sampling**: Subtract the straight line $l(t)$ connecting the first and last points from each electrode's voltage sequence, take the discrete Fourier transform of the remainder to obtain $X_j$, and evaluate at each sampling instant of Eq. (2):

   $$V(t) = l(t) + \frac{1}{n_{\text{bin}}}\operatorname{Re}\sum_{j} w_j\,X_j\,|H(f_j)|\,\mathrm{e}^{\mathrm{i}2\pi f_j (t - t_{c})} \tag{7}$$

   where $f_j = j/(n_{\text{bin}}\Delta t)$, $t_c = t_0 + \Delta t/2$, $w_0 = 1$, $w_j = 2$ for interior frequencies, and $w = 1$ at the Nyquist frequency when $n_{\text{bin}}$ is even. Eq. (7) is band-limited interpolation: the `readout` waveform contains only components below its Nyquist frequency, so band-limited interpolation is exact for it.
4. **Quantization**: Convert to codes via Eqs. (3) and (4); count, per electrode, the number of samples whose pre-clipping code is $< 0$ or $> 2^N - 1$ as the clipped count.
5. **Noise-only channels**: For each channel listed as noise-only in that event, obtain $S_d$ from its noise spectrum asset via Eq. (6), draw $K$ voltages, and quantize them; $K$ and $\varphi$ are the same as for the other channels in the event. $S_d$ is computed only once for the same spectrum.
6. **Output**: Pass the codes, clipped counts, and each electrode's first sampling instant $t_0 + \varphi$ to the digitizer stage to write into the digital waveform file.

$\varphi$, $\delta_k$, and noise-only samples are drawn using `digitizer`'s own seed. This seed is derived from the job's seed (see [experiments, scan points, and seeds](../lifecycle/experiments.md#seeds)), enters the `digitizer` node's fingerprint, and is independent of `readout`'s seed. Each instrument's $\varphi$ is determined by the seed, event ID, and instrument ID; each electrode's $\delta_k$ and noise-only samples are determined by the seed, event ID, and the electrode's index in `electrodes`.

## Software Implementation

### Module and Function Responsibilities

- `__init__.py`: package docstring.
- `settings.py`: `DigitizerSettings`, constructed from the component dictionary; raises an error on missing keys, extra keys, or out-of-range values.
- `bandwidth.py`: response of Eq. (1) and band-limited interpolation of Eq. (7).
- `sampling.py`: grouping, clock phase, and Eq. (2).
- `quantize.py`: Eqs. (3)–(5).
- `noise_only.py`: Eq. (6), codes for noise-only channels, and the decision function `noise_only_channels`.
- `digital_waveforms.py`: writing and reading digital waveform files.
- `job.py`: `write_digitized`, a single job from a `readout` file to a digital waveform file.
- `draw.py`: plots for this stage.
- `regincr.py`, `regincr_sim.py`: legacy: `pymtl3` 8-bit register-incrementer example kept as reference for future pure-digital logic, unrelated to sampling and quantization.

## Interface

### Settings

This module uses the keys of the component other than the trigger conditions: `channels`, `bits`, `max_sampling_rate_GSps`, `response`, `bandwidth_GHz`, `aperture_jitter_ps`, `sampling_rate_GSps`, `full_scale_V`, and `offset_V`; see [digitizer component](../components/digitizer.md#key-meanings) for their units and meanings.

### Input

`readout.h5` of the `readout` node (`readout.<position>.h5` in the same node for multi-position experiments), written by the [electronics readout stage (`stages/readout`)](../stages/readout.md): this module uses attributes `electrodes`, `dt` ($\text{s}$), and `pulse_edge`, and datasets `event`, `t0` ($\text{s}$), `count`, `stored`, `index`, and `voltage` ($\text{V}$).

Noise-only channels additionally require:

- **Noise spectrum asset**: a device, bias, and amplifier chain uniquely determine the noise spectrum $S_V(f)$ of each output, computed by `readout` and shared across experiments; read-only for this module.
- **Noise-only channel list**: indices of electrodes listed as noise-only for each event, supplied by upstream.
- **`noise_only_channels(deposited_keV, trigger_places, cut_keV)`**: `deposited_keV` is the deposited energy ($\text{keV}$, indexed by electrode) in the region corresponding to each electrode for that event, `trigger_places` are the electrode indices used by the trigger, and `cut_keV` is the user-specified energy cut; returns the indices of electrodes whose deposited energy is below the cut and not in `trigger_places`.

### Output: `digitizer.h5`

The digitizer stage writes this module's output to `nodes/digitizer/<node_id>/digitizer.h5` (`digitizer.<position>.h5` in the same node for multi-position experiments), following the sparse storage layout of `readout` waveform files: storing the electrodes that have waveforms saved in the `readout` file and the noise-only channels.

**File Attributes**

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `electrodes` | variable-length string array | none | Readout channel names, copied verbatim from the `readout` file |
| `sampling_period` | `float64` | $\text{s}$ | Sampling period $T_s$ |
| `lsb_V` | `float64` | $\text{V}$ | Voltage per code step $\text{LSB}$ |
| `offset_V` | `float64` | $\text{V}$ | Center of the range $V_{\text{off}}$ |
| `bits` | integer | bits | ADC bit depth $N$ |
| `channels` | integer | count | Number of channels per unit |
| `pulse_edge` | variable-length string array | none | Pulse direction corresponding one-to-one with `electrodes`, copied verbatim from the `readout` file |
| `device` | string | none | Name of the digitizer component used |

**Datasets**

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | none | Event ID |
| `count` | `(events,)`, `int64` | samples | Number of samples $K$ per electrode for the event |
| `stored` | `(events,)`, `int64` | count | Number of electrodes with stored digital waveforms in the event |
| `index` | `(sum(stored),)`, `int64` | none | 0-based index of each stored electrode in `electrodes`, partitioned by `stored` across events |
| `t0` | `(sum(stored),)`, `float64` | $\text{s}$ | Time of the first sample $t_0 + \varphi$ for that electrode; electrodes on the same instrument share the same value |
| `noise_only` | `(sum(stored),)`, `bool` | none | Whether that electrode is a noise-only channel |
| `clipped` | `(sum(stored),)`, `int64` | samples | Number of samples on that electrode clipped to the maximum or minimum code |
| `code` | `(sum(stored * count),)`, `int16` | none | Codes $c$, flattened in order of events and stored electrodes, with each electrode occupying `count` samples of its event |

Codes are converted back to voltage via Eq. (5); the time of the $k$-th sample on an electrode is that electrode's `t0` $+ k\cdot$`sampling_period`.

## References

- [1] Keysight Technologies, “Infiniium MXR-Series Oscilloscopes (A-Series)”, Data Sheet 7120-1115.EN, https://www.keysight.com/us/en/assets/7120-1115/data-sheets/Infiniium-MXR-Series.pdf
- [2] M. Shinagawa, Y. Akazawa, T. Wakimoto, “Jitter analysis of high-speed sampling systems”, IEEE J. Solid-State Circuits 25 (1990) 220, doi:10.1109/4.50307
- [3] W. R. Bennett, “Spectra of Quantized Signals”, Bell Syst. Tech. J. 27 (1948) 446, doi:10.1002/j.1538-7305.1948.tb01340.x
