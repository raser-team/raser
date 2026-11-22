# Digitizer (`core/digitizer`)

`src/raser/core/digitizer/` is the underlying module of the [digitizer stage (`stages/digitizer`)](../stages/digitizer.md). It takes the amplified electrode voltage waveforms produced by [electronics readout](readout.md) and, according to the oscilloscope or digitizer-board settings in the [digitizer component](../components/digitizer.md), applies analog bandwidth filtering, sampling, and quantization in sequence to produce the codes for each event and the clipped sample count for each electrode. The digitizer stage writes the result to a digital waveform file and passes it to the [trigger stage (`stages/trigger`)](../stages/trigger.md).

## Physics

### Bandwidth

The instrument's analog front end has finite bandwidth, which slows down fast waveform edges. This module represents it with a Gaussian-response low-pass filter whose magnitude frequency response is:

$$|H(f)| = \exp\!\left(-\frac{\ln 2}{2}\left(\frac{f}{B}\right)^2\right) \tag{1}$$

The corresponding impulse response is a Gaussian function, with temporal width and step-response rise time given by:

$$\sigma_t = \frac{\sqrt{\ln 2}}{2\pi B} \tag{2}$$

$$t_r^{10\text{–}90} \approx \frac{0.34}{B} \tag{3}$$

where:

- $f$: frequency, $\text{Hz}$;
- $B$: analog bandwidth, i.e., the frequency where $|H(B)| = 1/\sqrt{2}$ ($-3\ \text{dB}$), $\text{Hz}$, taken from the component's `bandwidth_GHz` (multiplied by $10^9$);
- $H(f)$: frequency response of the filter (dimensionless);
- $\sigma_t$: standard deviation of the impulse response $h(t) \propto \exp(-t^2 / 2\sigma_t^2)$, $\text{s}$;
- $t_r^{10\text{–}90}$: time for the step response to rise from $10\%$ to $90\%$ of its final value, $\text{s}$.

The response shape is fixed to Gaussian. The bandwidths of the amplifier and this module act in cascade: waveforms pass first through the `readout` amplifier chain and then through this module's Gaussian filter, so the output rise time is jointly determined by both filtering stages. Sources for Eqs. (1)–(3) are to be added.

### Sampling

The instrument's sampling clock is free-running and unsynchronized with the signal, so the phase of the first sample relative to the signal is random for each event; each sampling instant also carries aperture jitter. The $k$-th sampling time is:

$$t_k = t_0 + \varphi + k\,T_s + \delta_k,\qquad \varphi \sim U[0, T_s),\qquad \delta_k \sim \mathcal{N}(0, \sigma_a^2) \tag{4}$$

where:

- $t_k$: $k$-th sampling instant ($k = 0, 1, \dots$), $\text{s}$;
- $t_0$: start time `t0` of the event in the `readout` waveform, $\text{s}$;
- $T_s$: sampling period, $\text{s}$, equal to the reciprocal of the component's `sampling_rate_GSps` ($\text{GS/s}$);
- $\varphi$: clock phase for that event and instrument, $\text{s}$, uniformly distributed on $[0, T_s)$;
- $\delta_k$: aperture jitter at the $k$-th sample, $\text{s}$, following a zero-mean Gaussian distribution;
- $\sigma_a$: root-mean-square aperture jitter, $\text{s}$, taken from the component's `aperture_jitter_ps` (multiplied by $10^{-12}$).

All channels of the same instrument share $\varphi$. For the effect of aperture jitter on sampling systems, see Ref. [1].

### Quantization

An $N$-bit ADC divides the full scale into $2^N$ levels, clipping points outside full scale to the maximum or minimum code:

$$\text{LSB} = \frac{V_{\text{FS}}}{2^N} \tag{5}$$

$$c = \min\!\left(\max\!\left(\left\lfloor \frac{V - V_{\text{off}}}{\text{LSB}} \right\rfloor + 2^{N-1},\ 0\right),\ 2^N - 1\right) \tag{6}$$

$$\hat V = \left(c - 2^{N-1} + 0.5\right)\text{LSB} + V_{\text{off}} \tag{7}$$

$$\sigma_q = \frac{\text{LSB}}{\sqrt{12}} \tag{8}$$

where:

- $V_{\text{FS}}$: full-scale range, $\text{V}$, taken from the component's `full_scale_V`;
- $N$: ADC bit depth (dimensionless), taken from the component's `bits`;
- $\text{LSB}$: voltage per code step, $\text{V}$;
- $V$: voltage at the sampling instant, $\text{V}$;
- $V_{\text{off}}$: center of the range, $\text{V}$, taken from the component's `offset_V`;
- $c$: code, an integer in $0, 1, \dots, 2^N - 1$;
- $\hat V$: voltage reconstructed from the code, $\text{V}$, taken at the midpoint of the bin;
- $\sigma_q$: root-mean-square quantization error $V - \hat V$ on unclipped samples, $\text{V}$.

For Eq. (8), see Ref. [2].

## Algorithm

Each event is processed in the following order:

1. **Read**: Take the voltage sequences (`voltage` in the `readout` file, with time step `dt`) of all electrodes stored for that event, the event start time `t0`, and the component keys.
2. **Bandwidth**: Pass each electrode's voltage sequence through the Gaussian low-pass filter of Eq. (1) with $B = $`bandwidth_GHz`$\times 10^9\ \text{Hz}$.
3. **Sampling**:
   1. When the number of readout channels in the `readout` file's `electrodes` attribute exceeds `channels`, group them into blocks of `channels` in the order of `electrodes`, assigning one identical instrument per group.
   2. Draw one clock phase $\varphi$ from $U[0, T_s)$ per instrument, where $T_s = 10^{-9}/$`sampling_rate_GSps` $\text{s}$.
   3. Compute the sampling instants according to Eq. (4), drawing an aperture jitter from $\mathcal{N}(0, \sigma_a^2)$ for each sample.
   4. Linearly interpolate on the filtered voltage sequence to obtain the voltage at each sampling instant.
4. **Quantization**: Convert each sampled voltage into a code via Eqs. (5) and (6); count, per electrode, the number of samples whose pre-clipping code in Eq. (6) is $< 0$ or $> 2^N - 1$ as the clipped count.
5. **Output**: Pass the codes, clipped counts, and the event's first sampling instant $t_0 + \varphi$ to the digitizer stage to write into the digital waveform file.

The random quantities $\varphi$ and $\delta_k$ are drawn using `digitizer`'s own seed, independent of `readout`'s seed.

## Software Implementation

### Module and Function Responsibilities

- `__init__.py`: package docstring declaring that this package covers sampling, quantization, and the underlying digital circuitry.
- Sampling and quantization functions (to be added in the future, implemented in numpy): take the voltage waveforms of an event and the settings as input, and output codes and clipped sample counts.
- `regincr.py`, `regincr_sim.py`: legacy: existing `pymtl3` example in the package, retained as a reference for future pure digital logic (such as FPGA trigger logic), run directly in Python by calling `regincr_sim.main()`. `RegIncr` is an 8-bit register incrementer that latches its input every clock cycle and outputs the latched value plus 1; `main()` simulates 7 clock cycles using a hard-coded input sequence, writes the VCD waveform to `<project_root>/digitizer/fpga/regincr_sim.vcd` (where `<project_root>` comes from the environment variable `RASER_PROJECT_PATH`, defaulting to the current directory), and prints per-cycle port values and a text waveform to standard output.

## Interface

### Settings

All settings used by this module come from the [digitizer component](../components/digitizer.md): `channels`, `bits`, `bandwidth_GHz`, `aperture_jitter_ps`, `sampling_rate_GSps`, `full_scale_V`, and `offset_V`; the units and meanings of each key are given in "Key Meanings" on that page. The bandwidth response shape is fixed to Gaussian. When running `raser digitizer`, the digitizer stage reads the component and passes it to this module; see the [digitizer stage](../stages/digitizer.md#settings) for how to configure it.

### Input

The waveform file of the `readout` node written by the [electronics readout stage (`stages/readout`)](../stages/readout.md): this module uses attributes `electrodes`, `dt` ($\text{s}$), and `pulse_edge`, and datasets `event`, `t0` ($\text{s}$), `count`, `stored`, `index`, and `voltage` ($\text{V}$). See [electronics readout (`core/readout`)](readout.md) for the format.

### Output: `digitizer_<job>.h5`

The digitizer stage writes this module's output to `nodes/digitizer/<node>/digitizer_<job>.h5`, following the sparse storage layout of `readout` waveform files by storing only the electrodes that have waveforms saved in the `readout` file.

**File Attributes**

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `electrodes` | variable-length string array | none | Readout channel names, copied verbatim from the `readout` file |
| `sampling_period` | `float64` | $\text{s}$ | Sampling period $T_s$ |
| `lsb_V` | `float64` | $\text{V}$ | Voltage per code step $\text{LSB}$ |
| `offset_V` | `float64` | $\text{V}$ | Center of the range $V_{\text{off}}$ |
| `bits` | integer | bits | ADC bit depth $N$ |
| `pulse_edge` | variable-length string array | none | Pulse direction corresponding one-to-one with `electrodes`, copied verbatim from the `readout` file |
| `device` | string | none | Name of the digitizer component used |

**Datasets**

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | none | Event ID |
| `t0` | `(events,)`, `float64` | $\text{s}$ | Time of the first sample $t_0 + \varphi$, already including clock phase |
| `count` | `(events,)`, `int64` | samples | Number of samples per electrode for the event |
| `stored` | `(events,)`, `int64` | count | Number of electrodes with stored digital waveforms in the event |
| `index` | `(sum(stored),)`, `int64` | none | 0-based index of each stored electrode in `electrodes`, partitioned by `stored` across events |
| `clipped` | `(sum(stored),)`, `int64` | samples | Number of samples on that electrode clipped to the maximum or minimum code |
| `code` | `(sum(stored * count),)`, `int16` | none | Codes $c$, flattened in order of events and stored electrodes, with each electrode occupying `count` samples of its event |

Codes are converted back to voltage according to Eq. (7): $\hat V = (\texttt{code} - 2^{N-1} + 0.5)\cdot\texttt{lsb\_V} + \texttt{offset\_V}$, with $N$ taken from attribute `bits`.

## References

- [1] M. Shinagawa, Y. Akazawa, T. Wakimoto, “Jitter analysis of high-speed sampling systems”, IEEE J. Solid-State Circuits 25 (1990) 220, doi:10.1109/4.50307
- [2] W. R. Bennett, “Spectra of Quantized Signals”, Bell Syst. Tech. J. 27 (1948) 446, doi:10.1002/j.1538-7305.1948.tb01340.x
