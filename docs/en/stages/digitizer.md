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

`device` in the `digitizer` section selects an instrument whose settings live in its component file. To change a panel-adjusted quantity—for example, expanding the full scale of `MXR608A` from `0.04 V` to `0.08 V`:

```bash
raser digi --set digitizer.device.full_scale_V=0.08
```

Because this modifies a setting used by `digitizer`, a new `digitizer` node is produced, while `readout` and earlier nodes keep unchanged fingerprints and are reused as usual. The `digitizer` section holds analysis parameters and is not scanned: `--scan` on it raises an error; to use another value, change it with `--set` and run again, which reuses the events already measured and redoes only `digitizer` and the stages after it (see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md)).

### Full-Waveform Digitization per Event

`digitizer` samples and quantizes the full waveform of every event, writing all events from the `readout` node into the digital waveform file. The record window is the length of the upstream waveform; the oscilloscope sets only the sampling rate. Points exceeding the full-scale range are clipped to the maximum or minimum code, and the number of clipped points per electrode is recorded in the file.

### Noise-Only Channels

Two kinds of channels bypass `current` and `readout`, with `digitizer` directly drawing noise at the sampling points from that channel's electronics noise spectrum and quantizing it to obtain its digital waveform: one is channels not in the trigger condition whose deposited energy is below the user-specified energy cut; the other is slots in multi-position experiments that have no deposit step in that event (the particle missed the slot), regardless of whether the slot is in the trigger condition (a slot in the trigger condition still has this noise-only waveform evaluated against the threshold, so noise-induced false triggers arise naturally). The difference between the two kinds is that the former has energy deposition but the user chooses not to compute signal, whereas the latter has no deposit step and no signal to compute in that event. The former is decided upstream before `current`, while the latter is decided by this stage from the `detector` column of `deposit.h5`, and `digitizer` processes the given list; the noise spectrum is a shared experiment asset, computed once per device, bias, and amplifier chain. See [Digitizer (`core/digitizer`)](../core/digitizer.md#noise-only-channels) for the equations and decision function.

## Rules

### Execution Flow

1. **Read inputs**: Read the waveform file from the `readout` node, the `digitizer` section, and the digitizer component specified by `digitizer.device`. Components are looked up by name: components inside the project folder take precedence, falling back to the component library if not found.
2. **Grouping and phase**: All channels of one instrument share a single sampling clock. When the number of channels in the `readout.h5` attribute `electrodes` exceeds the component's `channels`, channels are grouped in order of `electrodes` by `channels` per group, with one instrument of the same model per group and an independently drawn clock phase for each instrument.
3. **Bandwidth and sampling**: Limit bandwidth according to the component's `response` (`"brickwall"` or `"none"`), and evaluate the voltage ($\text{V}$) via band-limited interpolation at sampling instants $t_k = t_0 + \varphi + k\,T_s + \delta_k$: $t_0$ is the event's `t0` in `readout.h5` ($\text{s}$), $T_s = 10^{-9}/$`sampling_rate_GSps` ($\text{s}$), $\varphi$ is uniformly distributed on $[0, T_s)$, and $\delta_k$ is Gaussian aperture jitter with RMS `aperture_jitter_ps` ($\text{ps}$). Take $\lfloor n_{\text{bin}}\,\Delta t / T_s \rfloor$ samples per electrode ($n_{\text{bin}}$ and $\Delta t$ are the bin count and bin width of the event's `readout` waveform). See [Digitizer (`core/digitizer`)](../core/digitizer.md) for the equations.
4. **Quantization**: $\text{LSB} = $`full_scale_V`$/2^N$ ($\text{V}$), where $N$ is the component's `bits`; code $= \lfloor(V - $`offset_V`$)/\text{LSB}\rfloor + 2^{N-1}$, clipped to $[0,\ 2^N - 1]$. The number of clipped points is recorded individually for each electrode.
5. **Noise-only channels**: Channels listed as noise-only for that event draw noise at the sampling points from their noise spectrum assets and then quantize it; the sample count and clock phase are the same as for the other channels in the event. In multi-position experiments, when a slot has no deposit step in an event recorded by `deposit`, all electrodes of that slot are listed as noise-only channels with the same sample count and clock phase as the other slots in that event.
6. **Write outputs**: Write the digital waveform file `digitizer.h5` and this stage's plots into the `digitizer` node (in multi-position experiments, each position's `digitizer.<position>.h5` contains all events recorded by `deposit`, with electrodes of events without deposit steps marked `noise_only`). Two plot types are produced: one `samples_<event>` for each of the first `digitizer.plots` events that store waveforms (the bandwidth-filtered analog waveform overlaid with the digitized samples), and one `codes` per node (a histogram of codes); neither is drawn when `digitizer.plots` is `0`.

### Seed

Random quantities in sampling (clock phase $\varphi$ and aperture jitter) and the noise of noise-only channels are drawn using `digitizer`'s own seed, derived from the job seed (see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md#seeds)). This seed enters the node fingerprint of this stage and is drawn independently from the seed used by `readout` for NGspice noise.

### Node Fingerprint

The fingerprint of this stage's node is composed of the setting values in the `digitizer` section, the keys of the selected digitizer component other than trigger conditions, `digitizer`'s own seed, the node ID of the upstream `readout` node, and the fingerprints of the noise spectrum assets used for noise-only channels.

## Software Implementation

- `src/raser/stages/digitizer.py`: Module for this stage; reads waveforms from the `readout` node, the `digitizer` section, and the component, calls `core/digitizer` for sampling and quantization according to the flow above, and writes the digital waveform file and plots. The function `digitized(kwargs, position=None)` takes the device name from `device`, the number of events to draw from `plots`, the seed from `seed`, and the content of the component as lifecycle hands it over (with the overrides of `--set digitizer.device.<key>=…` merged in); an error naming the missing one is raised if any of them is absent. In multi-position experiments there is one slice per position; when upstream left no `readout.<position>.h5` at a position, the slice writes no file and records 0 events. The list of noise-only channels is not connected yet: for now no event has noise-only channels.
- `src/raser/core/digitizer/`: Bandwidth filtering, sampling, and quantization computations; see [Digitizer (`core/digitizer`)](../core/digitizer.md).

## Interface

### Settings

The `digitizer` section of `config.json` has two keys: the slot `device` and `plots`. "Value in example" shows the value written in `examples/HPK-Si-PiN/signal/config.json`; if `config.json` is missing either key, an error is raised naming the missing `section.key`.

| Section.Key | Value in example | Unit | Meaning |
| --- | --- | --- | --- |
| `digitizer.device` | `"MXR608A"` | None | Selected digitizer component name, corresponding to `components/digitizer/<component_name>.json`; may also be written as an object with `name`, where the remaining keys override the same-named keys in the component file |
| `digitizer.plots` | `100` (`0` in the `timeres`, `bmos`, and `cflm` examples) | Events | Upper limit on the number of events per job for which `samples_<event>` is drawn |

Instrument settings are defined in the component file and addressed as `"section.slot.key"`: use `--set digitizer.device.<key>=<value>` to modify one, for example `--set digitizer.device.sampling_rate_GSps=8`. Fixed hardware keys of the instrument (such as `bits` and `response`) can also be overridden this way, effectively substituting a hypothetical instrument. `name` cannot be modified with `--set`: to switch instruments write `--set digitizer.device=<component_name>`, which replaces the entire slot with that component file and drops any previously overridden keys. See [Digitizer Components](../components/digitizer.md#key-meanings) for the name, unit, and meaning of each key. When a single instrument handles both sampling and triggering (such as an oscilloscope), its trigger conditions live in the same component file and are read by `trigger`, and its trigger keys also live under `digitizer.device`, for example `digitizer.device.trigger.level_V`. Common run parameters are documented in [Command-Line Interface (`raser`)](../cli.md), and configuration sections and scanning in [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md).

### Files Read and Written

- **Read: `readout.h5` in the `readout` node** (`readout.<position>.h5` inside the same node in multi-position experiments): Amplified waveforms written by the [Electronics Readout Stage (`stages/readout`)](readout.md), read-only for this stage.
- **Read: `deposit.h5` in the `deposit` node (multi-position experiments), noise-only channel list, and noise spectrum assets**: In multi-position experiments, which slots lack deposit steps in each event is determined from the `detector` column of `deposit.h5`; remaining noise-only channel indices are supplied by upstream; the noise spectrum of each output is computed by `readout` and stored as an asset, read-only for this stage.
- **Write: `nodes/digitizer/<node_id>/digitizer.h5`** (`digitizer.<position>.h5` inside the same node in multi-position experiments): Digital waveform file, following the sparse storage layout of `readout.h5` and storing the electrodes whose waveforms were stored in `readout.h5` and the noise-only channels; in multi-position experiments, each position's `digitizer.<position>.h5` contains all events recorded by `deposit`, with electrodes of events without deposit steps marked `noise_only`.

  | Kind | Name | Shape and type | Unit | Meaning |
  | --- | --- | --- | --- | --- |
  | Attribute (`attrs`) | `electrodes` | `(outputs,)`, variable-length string array | None | Readout channel names, copied verbatim from `readout.h5` |
  | Attribute (`attrs`) | `sampling_period` | scalar, `float64` | $\text{s}$ | Sampling period $T_s$ |
  | Attribute (`attrs`) | `lsb_V` | scalar, `float64` | $\text{V}$ | Voltage per step (LSB) |
  | Attribute (`attrs`) | `offset_V` | scalar, `float64` | $\text{V}$ | Range center |
  | Attribute (`attrs`) | `bits` | scalar, integer | bits | ADC resolution $N$ |
  | Attribute (`attrs`) | `channels` | scalar, integer | count | Number of channels per unit |
  | Attribute (`attrs`) | `pulse_edge` | `(outputs,)`, variable-length string array | None | Pulse edge direction matching `electrodes` one-to-one, copied verbatim from `readout.h5` |
  | Attribute (`attrs`) | `device` | scalar, string | None | Name of the digitizer component used |
  | Dataset (`datasets`) | `event` | `(events,)`, `int64` | None | Event ID |
  | Dataset (`datasets`) | `count` | `(events,)`, `int64` | samples | Number of sample points per electrode for the event |
  | Dataset (`datasets`) | `stored` | `(events,)`, `int64` | electrodes | Number of electrodes with stored digital waveforms in the event |
  | Dataset (`datasets`) | `index` | `(sum(stored),)`, `int64` | None | 0-based indices of stored electrodes in `electrodes`, partitioned by `stored` per event |
  | Dataset (`datasets`) | `t0` | `(sum(stored),)`, `float64` | $\text{s}$ | Timestamp of the first sample point for this electrode ($t_0 + \varphi$), including the clock phase of its instrument, partitioned by `stored` per event; electrodes on the same instrument share the same value |
  | Dataset (`datasets`) | `noise_only` | `(sum(stored),)`, `bool` | None | Whether this electrode is a noise-only channel |
  | Dataset (`datasets`) | `clipped` | `(sum(stored),)`, `int64` | samples | Number of points on this electrode clipped to the maximum or minimum code |
  | Dataset (`datasets`) | `code` | `(sum(stored * count),)`, `int16` | None | Codes flattened across events and stored electrodes, with `count` points per stored electrode of an event |

  Converting codes back to voltage: $V = (\texttt{code} - 2^{N-1} + 0.5)\cdot\texttt{lsb\_V} + \texttt{offset\_V}$ (in $\text{V}$), where $N$ is the attribute `bits`; for each electrode with a stored waveform, the nominal time of the $k$-th sample (0-based) is that electrode's `t0` $+ k\cdot$`sampling_period` (in $\text{s}$). For the $i$-th event (0-based), its codes start at the sum of `stored * count` over the preceding $i$ events in `code`, containing `count` points for each electrode listed in that event's `index` slice.
- **Write: plots of this stage**: `samples_<event>` and `codes`, stored in `plots/` of this stage's node; see [Figures](../supports/figures.md) for style.
- **Write: `nodes/digitizer/<node_id>/node.json`**: Records the inputs of this stage, code version, runtime environment, and run status. A partially written node carries the `.part` suffix and is renamed to its final name only after writing finishes.
- **Write: `points.json` and `points/<point>/digitizer/<job>`**: The parameter table records the `digitizer` node ID used by each point; the view symlink points to `../../../nodes/digitizer/<node_id>`.
