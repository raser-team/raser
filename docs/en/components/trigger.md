# Trigger Components (`components/trigger`)

`components/trigger/` holds trigger conditions for standalone trigger instruments, describing the criteria by which a real trigger device decides which events to record. The [`trigger`](../stages/trigger.md) stage reads components from here, selects qualifying events from the digital waveforms output by [`digitizer`](../stages/digitizer.md), and passes them to [`reconstruction`](../stages/reconstruction.md); whether an event is recorded is determined by the trigger condition. When a single instrument handles both sampling and triggering (such as an oscilloscope), the trigger conditions and sampling settings are placed together in the single file under [`components/digitizer/`](digitizer.md), and the `trigger` stage reads that file (see [Architecture Overview](../architecture.md#components)).

When looking up a component, the project folder's own component takes priority; if not found, it is searched by name in the component library.

## Component File

One component file describes one trigger device; its filename is the component name, selected by name via `device` in the `trigger` section of the experiment's `config.json`. Coincidence triggers requiring multiple devices to cross threshold simultaneously (such as [`timeres`](../bench/timeres.md)) also specify their coincidence conditions in the trigger component. `coincidence.json` in the library is a discriminator-plus-coincidence logic unit:

```json
{
    "level_V": -0.002,
    "slope": "falling",
    "require": "all",
    "coincidence_window_ns": null
}
```

## Key Meanings

| Key | Unit | Meaning | Value for `coincidence` |
| --- | --- | --- | --- |
| `level_V` | $\text{V}$ | Amplitude threshold. When given as a number, shared by all slots; when written as an object keyed by slot name, set per slot, e.g. `{"dut": -0.002, "ref": -0.005}` | `-0.002` |
| `slope` | None | Direction in which the threshold is crossed, `"falling"` or `"rising"` | `"falling"` |
| `require` | None | Logic expression of the coincidence condition | `"all"` |
| `coincidence_window_ns` | $\text{ns}$ | Coincidence window; `null` for no time constraint | `null` |

### Coincidence Conditions

The coincidence condition is defined once here, and `deposit` preselection refers to the same definition (see [Energy Deposition Stage](../stages/deposit.md)).

- **Slots and hits**: Operands of the logic expression are slot names from the experiment's device table (composed of letters, digits, `_`, and `-`). A slot hits when the waveform on any of its electrodes crosses `level_V` along `slope`; the hit time is the earliest of those crossing times. See [Trigger (`core/trigger`)](../core/trigger.md#level-crossing) for crossing evaluation and timing.
- **Logic expression**: Slot names are combined with `AND`, `OR`, and parentheses, e.g. `"dut AND (ref1 OR ref2)"`. `"all"` is shorthand for all slots joined with `AND`, and `"any"` is shorthand for all slots joined with `OR`. An error is raised if the expression contains a slot name absent from the device table or if a slot in the device table is missing from the expression.
- **Time window**: When `coincidence_window_ns` is $W$, only slots whose hit times fall within the same interval of width $W$ are counted together: the event is recorded only if there exists a time $t$ such that the slots with hit times in $[t - W,\ t]$ satisfy the logic expression, and the trigger time is the earliest such $t$. When `null`, all hitting slots are counted together, and the trigger time is the earliest time at which the logic expression holds.
- **`deposit` window**: The time window of `deposit` preselection is no narrower than `coincidence_window_ns` here.

- **At least $k$ of $N$**: `AT_LEAST(k: a, b, c)` evaluates to true when at least $k$ of slots `a`, `b`, `c` hit; it can be mixed with `AND` and `OR`, e.g. `"AT_LEAST(6: l1, l2, l3, l4, l5, l6, l7, l8) AND dut"`.

Whether an event is recorded is determined by the trigger conditions here; to adjust the trigger threshold, change the trigger condition. `reconstruction.threshold` and `reconstruction.amplitude_threshold` in the [`reconstruction`](../stages/reconstruction.md) section are reconstruction thresholds acting on events that have already been recorded: `reconstruction.threshold` is used for threshold-crossing timing; `reconstruction.amplitude_threshold` is the amplitude threshold for cluster seed channels, and recorded events in which a seed is found are marked `selected`.

`trigger.device` is a slot, and quantities inside a component are addressed as `"section.slot.key"`: those of a standalone trigger device are written `trigger.device.<key>`, modified individually with `--set trigger.device.<key>=<value>` or scanned with `--scan trigger.device.<key>=<value1>,<value2>`. For an oscilloscope that also handles triggering, its trigger conditions live in the `digitizer.device` slot and are written `digitizer.device.trigger.<key>`, for example `digitizer.device.trigger.level_V` (see [Digitizer Components](digitizer.md#trigger-conditions)). `name` cannot be modified with `--set` or `--scan`; to swap the device, write `--set trigger.device=<component_name>`, and to scan devices, write `--scan trigger.device=<component_name1>,<component_name2>`, which replaces the entire slot with that component file and drops any previously overridden keys. Settings of the stage itself are described in [Trigger Stage](../stages/trigger.md#settings).

## How the Program Uses the Component

The `trigger` stage reads the `trigger` section and trigger conditions, evaluates each event in turn, and writes recorded events into `nodes/trigger/<node_id>/`. When `trigger.device` selects a standalone trigger device, it evaluates the entire event once according to the coincidence condition and every position records the same set of events; when `trigger.device` is `null`, each position is evaluated by its own oscilloscope's trigger condition. The portion of the component it uses enters the `trigger` node's fingerprint: changing the trigger condition produces a new `trigger` node, causing downstream `reconstruction` and `analysis` to obtain new nodes as well, while the upstream `digitizer` node is reused as normal. See [Slices and Reruns](../lifecycle/slices.md) for nodes, fingerprints, and reuse.

## Built-in Components

| Component Name | Device | Source | Applicability |
| --- | --- | --- | --- |
| `coincidence` | Discriminator-plus-coincidence logic unit | None (general logic; threshold taken from `MXR608A` bench measurement trigger level $-2\ \text{mV}$) | Coincidence between multiple devices, e.g. `timeres` |

Trigger conditions for oscilloscopes that handle both sampling and triggering are stored under [`components/digitizer/`](digitizer.md#trigger-conditions).
