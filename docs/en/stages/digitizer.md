# Digitization Stage (`stages/digitizer`)

`digitizer` is the 5th stage of the simulation chain, positioned after the [Electronics Readout Stage (`stages/readout`)](readout.md) and before the [Trigger Stage (`stages/trigger`)](trigger.md), with the command `raser digitizer` (short alias `raser digi`). It reads the amplified waveforms in the `readout` node, the `digitizer` section of `config.json`, and the [Digitizer Components (`components/digitizer`)](../components/digitizer.md) selected in the `digitizer` section—that is, the configuration of an oscilloscope or digitizer board. It passes each electrode's waveform sequentially through the device's analog bandwidth, sampling, and quantization to produce the full-length digital waveform for each event, delegating computation to [Digitizer (`core/digitizer`)](../core/digitizer.md). The digital waveforms are written into this stage's node `nodes/digitizer/<node_id>/`, pointed to by the view `points/<point>/digitizer/<job>`, and handed off to `trigger`. Everything in a real instrument belonging to analog bandwidth, sampling, and quantization belongs here.

## Behavior

### Running Up to Digitization

`raser digitizer` runs up to `digitizer` on the experiment in the current folder or at the given path, automatically computing any missing upstream stages:

```bash
raser digitizer [path]
raser digi [path]
```

Omitting the path uses the current folder; providing a path accepts either a relative or an absolute path. Upstream `field`, `deposit`, `current`, and `readout` nodes with matching fingerprints are reused regardless of which point or run produced them; missing ones are computed first in chain order. `digitizer` nodes are likewise reused by fingerprint. When the code version differs from the one recorded in the node, only a notice is printed and the result is still reused. See [Slices and Reruns](../lifecycle/slices.md) for nodes, the parameter table, and reuse.

### Switching Devices and Changing Panel Settings

`device` in the `digitizer` section selects an instrument whose settings live in its component file. To change a panel-adjusted quantity—for example, expanding the full scale of `MXR608A` from `0.04 V` to `0.08 V`, or scanning two full-scale ranges:

```bash
raser digi --set digitizer.device.full_scale_V=0.08
raser digi --scan digitizer.device.full_scale_V=0.04,0.08
```

Because this modifies a setting used by `digitizer`, a new `digitizer` node is produced, while `readout` and earlier nodes keep unchanged fingerprints and are reused as usual.

### Full-Waveform Digitization per Event

`digitizer` samples and quantizes the full waveform of every event, writing all events from the `readout` node into the digital waveform file. Points exceeding the full-scale range are clipped to the maximum or minimum code, and the number of clipped points per electrode is recorded in the file.

## Rules

### Execution Flow

1. **Read inputs**: Read the waveform file from the `readout` node, the `digitizer` section, and the digitizer component specified by `digitizer.device`. Components are looked up by name: components inside the project folder take precedence, falling back to the component library if not found.
2. **Bandwidth**: Each electrode's waveform passes through a Gaussian low-pass filter whose $-3\ \text{dB}$ point is the component's `bandwidth_GHz` ($\text{GHz}$); see [Digitizer (`core/digitizer`)](../core/digitizer.md#bandwidth) for the response formula.
3. **Sampling**:
   - All channels of one instrument share a single sampling clock. When the number of readout channels in the `readout` file attribute `electrodes` exceeds the component's `channels`, channels are grouped in order of `electrodes` by `channels` per group, with one instrument of the same model per group and an independently drawn clock phase for each instrument.
   - For each event and each instrument, draw a clock phase $\varphi$ uniformly distributed on $[0, T_s)$, where $T_s = 10^{-9}/$`sampling_rate_GSps` ($\text{s}$) is the sampling period; the sampling instants are $t_k = t_0 + \varphi + k\,T_s$ (with $t_0$ taken from the event's `t0` in `readout.h5`, in $\text{s}$, $k = 0, 1, \dots$), with an additional Gaussian aperture jitter of RMS `aperture_jitter_ps` ($\text{ps}$, multiplied by $10^{-12}$ to convert to $\text{s}$) added to each sample point.
   - Linearly interpolate the bandwidth-filtered waveform to obtain the voltage ($\text{V}$) at each sampling instant.
4. **Quantization**: $\text{LSB} = $`full_scale_V`$/2^N$ ($\text{V}$), where $N$ is the component's `bits`; code $= \lfloor(V - $`offset_V`$)/\text{LSB}\rfloor + 2^{N-1}$, clipped to $[0,\ 2^N - 1]$. The number of clipped points is recorded individually for each electrode.
5. **Write outputs**: Write the digital waveform file `digitizer.h5` and this stage's plots into the `digitizer` node. Two plot types are produced: an overlay of the bandwidth-filtered analog waveform and sampled points for the first few events, and a histogram of codes.

### Seed

Random quantities in sampling (clock phase $\varphi$ and aperture jitter) are drawn using `digitizer`'s own seed, derived from the job seed (see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md#seeds)). This seed enters the node fingerprint of this stage and is drawn independently from the seed used by `readout` for NGspice noise.

### Node Fingerprint

The fingerprint of this stage's node is composed of the setting values in the `digitizer` section, the keys of the selected digitizer component used by `digitizer`, `digitizer`'s own seed, and the node ID of the upstream `readout` node.

## Software Implementation

- `src/raser/stages/digitizer.py`: Module for this stage; reads waveforms from the `readout` node, the `digitizer` section, and the component, calls `core/digitizer` for sampling and quantization according to the flow above, and writes the digital waveform file and plots.
- `src/raser/core/digitizer/`: Bandwidth filtering, sampling, and quantization computations; see [Digitizer (`core/digitizer`)](../core/digitizer.md).

## Interface

### Settings

The `digitizer` section of `config.json` has only one key, the slot `device`. "Value in example" shows the value written in `examples/HPK-Si-PiN/signal/config.json`; if `config.json` is missing this key, an error is raised naming the missing `section.key`.

| Section.Key | Value in example | Unit | Meaning |
| --- | --- | --- | --- |
| `digitizer.device` | `"MXR608A"` | None | Selected digitizer component name, corresponding to `components/digitizer/<component_name>.json`; may also be written as an object with `name`, where the remaining keys override the same-named keys in the component file |

Instrument settings are defined in the component file and addressed as `"section.slot.key"`: use `--set digitizer.device.<key>=<value>` to modify one, or `--scan digitizer.device.<key>=<value1>,<value2>` to scan it, for example `--set digitizer.device.sampling_rate_GSps=8`. Fixed hardware keys of the instrument (such as `bits` and `bandwidth_GHz`) can also be overridden this way, effectively substituting a hypothetical instrument. `name` cannot be modified with `--set` or `--scan`: to switch instruments write `--set digitizer.device=<component_name>`, and to scan instruments write `--scan digitizer.device=<component_name1>,<component_name2>`, which replaces the entire slot with that component file and drops any previously overridden keys. See [Digitizer Components](../components/digitizer.md#key-meanings) for the name, unit, and meaning of each key. When a single instrument handles both sampling and triggering (such as an oscilloscope), its trigger conditions live in the same component file and are read by `trigger`, and its trigger keys also live under `digitizer.device`, for example `digitizer.device.trigger_level_V`. Common run parameters are documented in [Command-Line Interface (`raser`)](../cli.md), and configuration sections and scanning in [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md).

### Files Read and Written

- **Read: `readout.h5` in the `readout` node** (`readout.<position>.h5` inside the same node in multi-position experiments): Amplified waveforms written by the [Electronics Readout Stage (`stages/readout`)](readout.md), read-only for this stage.
- **Write: `nodes/digitizer/<node_id>/digitizer.h5`** (`digitizer.<position>.h5` inside the same node in multi-position experiments): Digital waveform file, following the sparse storage layout of `readout.h5` and storing only the electrodes whose waveforms were stored in `readout.h5`.

  | Kind | Name | Shape and type | Unit | Meaning |
  | --- | --- | --- | --- | --- |
  | Attribute (`attrs`) | `electrodes` | `(outputs,)`, variable-length string array | None | Readout channel names, copied verbatim from `readout.h5` |
  | Attribute (`attrs`) | `sampling_period` | scalar, `float64` | $\text{s}$ | Sampling period $T_s$ |
  | Attribute (`attrs`) | `lsb_V` | scalar, `float64` | $\text{V}$ | Voltage per step (LSB) |
  | Attribute (`attrs`) | `offset_V` | scalar, `float64` | $\text{V}$ | Range center |
  | Attribute (`attrs`) | `bits` | scalar, integer | bits | ADC resolution $N$ |
  | Attribute (`attrs`) | `pulse_edge` | `(outputs,)`, variable-length string array | None | Pulse edge direction matching `electrodes` one-to-one, copied verbatim from `readout.h5` |
  | Attribute (`attrs`) | `device` | scalar, string | None | Name of the digitizer component used |
  | Dataset (`datasets`) | `event` | `(events,)`, `int64` | None | Event ID |
  | Dataset (`datasets`) | `count` | `(events,)`, `int64` | samples | Number of sample points per electrode for the event |
  | Dataset (`datasets`) | `stored` | `(events,)`, `int64` | electrodes | Number of electrodes with stored digital waveforms in the event |
  | Dataset (`datasets`) | `index` | `(sum(stored),)`, `int64` | None | 0-based indices of stored electrodes in `electrodes`, partitioned by `stored` per event |
  | Dataset (`datasets`) | `t0` | `(sum(stored),)`, `float64` | $\text{s}$ | Timestamp of the first sample point for this electrode ($t_0 + \varphi$), including the clock phase of its instrument, partitioned by `stored` per event; electrodes on the same instrument share the same value |
  | Dataset (`datasets`) | `clipped` | `(sum(stored),)`, `int64` | samples | Number of points on this electrode clipped to the maximum or minimum code |
  | Dataset (`datasets`) | `code` | `(sum(stored * count),)`, `int16` | None | Codes flattened across events and stored electrodes, with `count` points per stored electrode of an event |

  Converting codes back to voltage: $V = (\texttt{code} - 2^{N-1} + 0.5)\cdot\texttt{lsb\_V} + \texttt{offset\_V}$ (in $\text{V}$), where $N$ is the attribute `bits`; for each electrode with a stored waveform, the nominal time of the $k$-th sample (0-based) is that electrode's `t0` $+ k\cdot$`sampling_period` (in $\text{s}$). For the $i$-th event (0-based), its codes start at the sum of `stored * count` over the preceding $i$ events in `code`, containing `count` points for each electrode listed in that event's `index` slice.
- **Write: plots of this stage**: Overlays of bandwidth-filtered analog waveforms with sampled points for the first few events, and histograms of codes, stored in this stage's node.
- **Write: `nodes/digitizer/<node_id>/node.json`**: Records the inputs of this stage, code version, runtime environment, and run status. A partially written node carries the `.part` suffix and is renamed to its final name only after writing finishes.
- **Write: `points.json` and `points/<point>/digitizer/<job>`**: The parameter table records the `digitizer` node ID used by each point; the view symlink points to `../../../nodes/digitizer/<node_id>`.
