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
    "response": "brickwall",
    "bandwidth_GHz": 6,
    "aperture_jitter_ps": 0.15,
    "sampling_rate_GSps": 16,
    "full_scale_V": 0.04,
    "offset_V": -0.01,
    "trigger": {
        "mode": "edge",
        "source": "CH1",
        "level_V": -0.002,
        "slope": "falling"
    }
}
```

`toy.json` is the toy device: unlimited bandwidth and no aperture jitter, with round values for the remaining keys and the same `trigger` as `MXR608A`:

```json
{
    "channels": 64,
    "bits": 14,
    "max_sampling_rate_GSps": 20,
    "response": "none",
    "aperture_jitter_ps": 0,
    "sampling_rate_GSps": 20,
    "full_scale_V": 1.0,
    "offset_V": 0.0,
    "trigger": {
        "mode": "edge",
        "source": "CH1",
        "level_V": -0.002,
        "slope": "falling"
    }
}
```

The first six keys of `MXR608A` are fixed by the instrument itself and take values from the datasheet [1]; the next three are adjusted by the user on the front panel and take the settings used in the group's bench measurements (range $-30\ \text{mV}$ to $+10\ \text{mV}$); `trigger` is the trigger condition handled by the oscilloscope, also adjusted on the front panel and taking the settings used in the group's bench measurements (`CH1` falling edge, level $-2\ \text{mV}$). Aperture jitter `aperture_jitter_ps` is set to `0.15`: the datasheet specifies a within-channel intrinsic jitter of $150$–$181\ \text{fs}$ rms for 8-channel models [1]. Because the oscilloscope also handles triggering, its trigger conditions are written in `trigger` of the same file and read by the `trigger` stage (see [Trigger Conditions](#trigger-conditions)).

## Key Meanings

| Category | Key | Unit | Meaning | Value for `MXR608A` |
| --- | --- | --- | --- | --- |
| Fixed by device | `channels` | count | Number of channels per unit | `8` |
| Fixed by device | `bits` | bits | ADC bit depth $N$, `1` to `15` (codes are stored as `int16`) | `10` |
| Fixed by device | `max_sampling_rate_GSps` | $\text{GS/s}$ | Maximum sampling rate | `16` |
| Fixed by device | `response` | None | Bandwidth response, `"brickwall"` (ideal brick wall) or `"none"` (unlimited bandwidth) | `"brickwall"` |
| Fixed by device | `bandwidth_GHz` | $\text{GHz}$ | Analog bandwidth; written only when `response` is `"brickwall"` | `6` |
| Fixed by device | `aperture_jitter_ps` | $\text{ps}$ | Root-mean-square aperture jitter | `0.15` |
| Panel setting | `sampling_rate_GSps` | $\text{GS/s}$ | Sampling rate, not exceeding `max_sampling_rate_GSps` | `16` |
| Panel setting | `full_scale_V` | $\text{V}$ | Full scale | `0.04` |
| Panel setting | `offset_V` | $\text{V}$ | Range center | `-0.01` |
| Trigger | `trigger` | None | Trigger condition, see [Trigger Conditions](#trigger-conditions) | `CH1` falling edge, $-2\ \text{mV}$ |

The full scale covers [`offset_V` $-$ `full_scale_V`$/2$, `offset_V` $+$ `full_scale_V`$/2$], divided into $2^N$ levels with step size $\text{LSB} = $`full_scale_V`$/2^N$.

`digitizer.device` is a slot; quantities inside the component are addressed as "section.slot.key", written `digitizer.device.<key>`: use `--set digitizer.device.<key>=<value>` to change one value, for example `--set digitizer.device.full_scale_V=0.08`. Changing a panel-setting key this way is equivalent to changing a range on the oscilloscope panel; keys fixed by the device can also be overridden the same way to represent a hypothetical instrument while the library component retains the datasheet values. For an instrument that also handles triggering, its trigger conditions are also in `digitizer.device`, for example `digitizer.device.trigger.level_V`. The `digitizer` section holds analysis parameters and cannot be given to `--scan`. `name` cannot be modified with `--set`; to switch devices, write `--set digitizer.device=<component_name>`, which replaces the entire slot with that component file and drops any previously overridden keys. Settings of the stage itself are described in [Digitizer Stage](../stages/digitizer.md#settings).

## Trigger Conditions

`mode` in `trigger` selects the trigger mode, corresponding to the two modes on the oscilloscope front panel:

- **`"edge"`** (edge trigger): triggers when a source channel `source` crosses `level_V` ($\text{V}$) along `slope` (`"falling"` or `"rising"`).
- **`"pattern"`** (pattern trigger): lists channels under `channels`, each given a `level_V` ($\text{V}$) and a `state` (`"low"`: below the level, `"high"`: above the level); triggers at the instant when all channels are simultaneously in their respective states. For example:

  ```json
  "trigger": {
      "mode": "pattern",
      "channels": {
          "CH1": {"level_V": -0.002, "state": "low"},
          "CH2": {"level_V": -0.003, "state": "low"}
      }
  }
  ```

Channels are written as `CH1`, `CH2`, ..., where the $n$-th channel is the electrode at index $n-1$ in the `electrodes` attribute of `readout.h5`; when there are more electrodes than one instrument's `channels`, numbering continues onto the next instrument. See [Trigger (`core/trigger`)](../core/trigger.md) for the evaluation equations. Coincidence between multiple devices is handled by a standalone trigger device; see [Trigger Components](trigger.md).

## How the Program Uses the Component

1. **`digitizer` stage**: Locates the component from `digitizer.device` and uses each key as follows (equations in [Digitizer (`core/digitizer`)](../core/digitizer.md#physics)):
   - `response`, `bandwidth_GHz`: bandwidth response and bandwidth $B$.
   - `sampling_rate_GSps`: sampling interval $T_s = 10^{-9}/$`sampling_rate_GSps` ($\text{s}$).
   - `aperture_jitter_ps`: root-mean-square Gaussian aperture jitter $\sigma_a$ at each sampling instant.
   - `bits`, `full_scale_V`, `offset_V`: bit depth, voltage step per level, and offset for quantization.
   - `channels`: when the `readout` file contains more readout channels than this count, channels are grouped in blocks of `channels` following the order of `electrodes`, with one identical instrument per group and an independently drawn clock phase for each instrument.

   Keys of the component other than `trigger` enter the `digitizer` node's fingerprint; changing any one of them produces a new `digitizer` node. Digital waveforms are written into `nodes/digitizer/<node_id>/`.
2. **`trigger` stage**: When an instrument also handles triggering, reads `trigger` from the same component file. Only `trigger` enters the `trigger` node's fingerprint; changing it produces only a new `trigger` node, while the `digitizer` node is reused as normal.

See [Slices and Reruns](../lifecycle/slices.md) for nodes, fingerprints, and reuse.

## Built-in Components

| Component Name | Device | Source | Applicability |
| --- | --- | --- | --- |
| `MXR608A` | Keysight MXR608A oscilloscope ($6\ \text{GHz}$, 8 channels, $16\ \text{GSa/s}$, 10-bit ADC), handling both sampling and triggering | Device-fixed keys: datasheet [1]; panel-setting keys and trigger conditions: front-panel settings used in the group's bench measurements with this oscilloscope (sampling rate $16\ \text{GSa/s}$, range $-30$ to $+10\ \text{mV}$, `CH1` falling-edge trigger, level $-2\ \text{mV}$) | Device selected in examples such as `HPK-Si-PiN` |
| `toy` | Toy device with unlimited bandwidth and no aperture jitter | None | Used when oscilloscope details are not of concern |

Limitation: `MXR608A` uses a brick-wall filter, for which the datasheet gives a 10–90% rise time of $71.7\ \text{ps}$ ($0.43/B$) [1]; this module's ideal brick wall gives $0.446/B = 74\ \text{ps}$, and the shape of the transition band remains to be determined against the datasheet.

## References

- [1] Keysight Technologies, “Infiniium MXR-Series Oscilloscopes (A-Series)”, Data Sheet 7120-1115.EN, https://www.keysight.com/us/en/assets/7120-1115/data-sheets/Infiniium-MXR-Series.pdf
