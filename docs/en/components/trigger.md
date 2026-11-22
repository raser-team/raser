# Trigger Components (`components/trigger`)

`components/trigger/` holds trigger conditions for standalone trigger instruments, describing the criteria by which a real trigger device decides which events to record. The [`trigger`](../stages/trigger.md) stage reads components from here, selects qualifying events from the digital waveforms output by [`digitizer`](../stages/digitizer.md), and passes them to [`reconstruction`](../stages/reconstruction.md); whether an event is recorded is determined by the trigger condition. When a single instrument handles both sampling and triggering (such as an oscilloscope), the trigger conditions and sampling settings are placed together in the single file under [`components/digitizer/`](digitizer.md), and the `trigger` stage reads that file (see [Architecture Overview](../architecture.md#components)).

When looking up a component, the project folder's own component takes priority; if not found, it is searched by name in the component library.

## Component File

One component file describes one trigger device; its filename is the component name, selected by name in the `trigger` section of the experiment's `config.json`. Coincidence triggers requiring multiple devices to cross threshold simultaneously (such as [`timeres`](../bench/timeres.md)) also specify their coincidence conditions in the trigger component.

## Key Meanings

A trigger component sets the following categories of quantities:

- **Amplitude threshold**: events whose waveform crosses the threshold are recorded, and those that do not are discarded (for example, the `HPK-Si-PiN` example; see [Trigger Stage](../stages/trigger.md#amplitude-threshold-triggering)).
- **Coincidence condition**: which devices must all cross the amplitude threshold in the same event for that event to be recorded (for example, the two-device coincidence in `timeres`).

Whether an event is recorded is determined by the trigger conditions here; to adjust the trigger threshold, change the trigger condition. `threshold` and `amplitude_threshold` in the [`reconstruction`](../stages/reconstruction.md) section are reconstruction thresholds acting on events that have already been recorded: `threshold` is used for threshold-crossing timing, and `amplitude_threshold` is used only to find cluster seeds.

Quantities inside a component are addressed as "section.component.key": those of a standalone trigger device are written `trigger.<component_name>.<key>`, modified individually with `--set trigger.<component_name>.<key>=<value>` or scanned with `--scan trigger.<component_name>.<key>=<value1>,<value2>`. For an oscilloscope that also handles triggering, its trigger conditions belong to its component in the `digitizer` section and are written `digitizer.MXR608A.<key>` (see [Digitizer Components](digitizer.md#key-meanings)). Settings of the stage itself are described in [Trigger Stage](../stages/trigger.md#settings).

## How the Program Uses the Component

The `trigger` stage reads the `trigger` section and trigger conditions, evaluates each event in turn, and writes recorded events into `nodes/trigger/<node_id>/`. The portion of the component it uses enters the `trigger` node's fingerprint: changing the trigger condition produces a new `trigger` node, causing downstream `reconstruction` and `analysis` to obtain new nodes as well, while the upstream `digitizer` node is reused as normal. See [Slices and Reruns](../lifecycle/slices.md) for nodes, fingerprints, and reuse.

## Built-in Components

All trigger conditions in the library are stored alongside the oscilloscopes that handle both sampling and triggering under [`components/digitizer/`](digitizer.md#built-in-components).
