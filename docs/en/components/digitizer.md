# Digitizer Components (`components/digitizer`)

`components/digitizer/` holds oscilloscope or digitizer-board settings; each file describes how a real instrument converts the analog voltage waveforms output by [`readout`](../stages/readout.md) into digital waveforms: analog bandwidth, sampling, and quantization. The [`digitizer`](../stages/digitizer.md) stage reads the component here specified by `device` in the `digitizer` section, producing digital waveforms handed off to [`trigger`](../stages/trigger.md). When a single instrument handles both sampling and triggering (such as an oscilloscope), its settings are stored once here, and both the `digitizer` and `trigger` stages read this same file (see [Architecture Overview](../architecture.md#components)).

When looking up a component, the project folder's own component takes priority; if not found, it is searched by name in the component library.

## Component File

A component file `components/digitizer/<device>.json` describes one instrument; its filename stem is the component name, selected by name via `device` in the `digitizer` section of the experiment's `config.json`. `MXR608A.json` in the library is as follows:

```json
{
    "channels": 8,
    "bits": 10,
    "max_sampling_rate_GSps": 16,
    "bandwidth_GHz": 6,
    "aperture_jitter_ps": 0.15,
    "sampling_rate_GSps": 16,
    "full_scale_V": 0.04,
    "offset_V": -0.01,
    "trigger_level_V": -0.01,
    "trigger_slope": "falling"
}
```

The first five keys are fixed by the instrument itself and take values from the datasheet [1]; the next three are adjusted by the user on the front panel and take the settings used in the group's bench measurements (range $-30\ \text{mV}$ to $+10\ \text{mV}$); the last two keys are the trigger conditions handled by the oscilloscope, also adjusted on the front panel. Aperture jitter `aperture_jitter_ps` is set to `0.15`: the datasheet specifies a within-channel intrinsic jitter of $150$–$181\ \text{fs}$ rms for 8-channel models [1]. Because the oscilloscope also handles triggering, its trigger conditions are written in the same file and read by `trigger` (see [Trigger Components](trigger.md#key-meanings)).

## Key Meanings

| Category | Key | Unit | Meaning | Value for `MXR608A` |
| --- | --- | --- | --- | --- |
| Fixed by device | `channels` | count | Number of channels per unit | `8` |
| Fixed by device | `bits` | bits | ADC bit depth $N$ | `10` |
| Fixed by device | `max_sampling_rate_GSps` | $\text{GS/s}$ | Maximum sampling rate | `16` |
| Fixed by device | `bandwidth_GHz` | $\text{GHz}$ | Analog bandwidth ($-3\ \text{dB}$ point), Gaussian response | `6` |
| Fixed by device | `aperture_jitter_ps` | $\text{ps}$ | Root-mean-square aperture jitter | `0.15` |
| Panel setting | `sampling_rate_GSps` | $\text{GS/s}$ | Sampling rate, not exceeding `max_sampling_rate_GSps` | `16` |
| Panel setting | `full_scale_V` | $\text{V}$ | Full scale | `0.04` |
| Panel setting | `offset_V` | $\text{V}$ | Range center | `-0.01` |
| Trigger | `trigger_level_V` | $\text{V}$ | Amplitude threshold: an event is recorded when the waveform on any channel crosses it | `-0.01` |
| Trigger | `trigger_slope` | None | Direction in which the threshold is crossed, `"rising"` or `"falling"` | `"falling"` |

The full scale covers [`offset_V` $-$ `full_scale_V`$/2$, `offset_V` $+$ `full_scale_V`$/2$], divided into $2^N$ levels with step size $\text{LSB} = $`full_scale_V`$/2^N$.

`digitizer.device` is a slot; quantities inside the component are addressed as "section.slot.key", written `digitizer.device.<key>`: use `--set digitizer.device.<key>=<value>` to change one value, and `--scan digitizer.device.<key>=<value1>,<value2>` to scan, for example `--set digitizer.device.full_scale_V=0.08`. Changing a panel-setting key this way is equivalent to changing a range on the oscilloscope panel; keys fixed by the device can also be overridden the same way to represent a hypothetical instrument while the library component retains the datasheet values. For an instrument that also handles triggering, its trigger conditions are also in `digitizer.device`, for example `digitizer.device.trigger_level_V`. `name` cannot be modified with `--set` or `--scan`; to switch devices, write `--set digitizer.device=<component_name>`, and to scan devices, write `--scan digitizer.device=<component_name1>,<component_name2>`, which replaces the entire slot with that component file and drops any previously overridden keys. Settings of the stage itself are described in [Digitizer Stage](../stages/digitizer.md#settings).

## How the Program Uses the Component

1. **`digitizer` stage**: Locates the component from `digitizer.device` and uses each key as follows (equations in [Digitizer (`core/digitizer`)](../core/digitizer.md#physics)):
   - `bandwidth_GHz`: $-3\ \text{dB}$ point $B$ of the Gaussian low-pass filter.
   - `sampling_rate_GSps`: sampling interval $T_s = 10^{-9}/$`sampling_rate_GSps` ($\text{s}$).
   - `aperture_jitter_ps`: root-mean-square Gaussian aperture jitter $\sigma_a$ at each sampling instant.
   - `bits`, `full_scale_V`, `offset_V`: bit depth, voltage step per level, and offset for quantization.
   - `channels`: when the `readout` file contains more readout channels than this count, channels are grouped in blocks of `channels` following the order of `electrodes`, with one identical instrument per group and an independently drawn clock phase for each instrument.

   Keys of the component used by `digitizer` enter the `digitizer` node's fingerprint; changing any one of them produces a new `digitizer` node. Digital waveforms are written into `nodes/digitizer/<node_id>/`.
2. **`trigger` stage**: When an instrument also handles triggering, reads the trigger conditions `trigger_level_V` and `trigger_slope` from the same component file. This part enters the `trigger` node's fingerprint; changing it produces a new `trigger` node.

See [Slices and Reruns](../lifecycle/slices.md) for nodes, fingerprints, and reuse.

## Built-in Components

| Component Name | Device | Source | Applicability |
| --- | --- | --- | --- |
| `MXR608A` | Keysight MXR608A oscilloscope ($6\ \text{GHz}$, 8 channels, $16\ \text{GSa/s}$, 10-bit ADC), handling both sampling and triggering | Device-fixed keys: datasheet [1]; panel-setting keys: front-panel settings used in the group's bench measurements with this oscilloscope (sampling rate $16\ \text{GSa/s}$, range $-30$ to $+10\ \text{mV}$) | Default device for experiments such as `HPK-Si-PiN` |

Limitation: `MXR608A` uses a brick-wall filter, for which the datasheet gives a 10–90% rise time of $71.7\ \text{ps}$ ($0.43/B$) [1]; this module's Gaussian response gives $56.7\ \text{ps}$ via $0.34/B$ [2], faster than the real instrument.

## References

- [1] Keysight Technologies, “Infiniium MXR-Series Oscilloscopes (A-Series)”, Data Sheet 7120-1115.EN, https://www.keysight.com/us/en/assets/7120-1115/data-sheets/Infiniium-MXR-Series.pdf
- [2] Keysight Technologies, “Understanding Oscilloscope Frequency Response and Its Effect on Rise-Time Accuracy”, Application Note 5988-8008EN
