# Digitizer and Oscilloscope Components (`components/adc`)

`src/raser/components/adc/` stores oscilloscope threshold configuration JSON files; currently the directory contains only `scope.json`. On the simulation chain, threshold-crossing and amplitude-selection parameters are set via the `-threshold` and `-amplitude_threshold` CLI options of the [`reconstruction`](../stages/reconstruction.md) stage (for the full signal simulation flow, see [Getting Started](../getting-started.md)).

## File Format

`src/raser/components/adc/scope.json` reads:

```json
{
    "threshold" : 50,
    "amplitude_threshold" : 100
}
```

| Key | Value in `scope.json` | Description |
| --- | --- | --- |
| `threshold` | `50` | Oscilloscope threshold configuration entry |
| `amplitude_threshold` | `100` | Oscilloscope amplitude-selection threshold configuration entry |

## Built-in Components

`src/raser/components/adc/` contains the following 1 JSON file:

| Component Name | File Path |
| --- | --- |
| `scope` | `src/raser/components/adc/scope.json` |

## Related Pages

- [Getting Started](../getting-started.md)
- [`../stages/reconstruction.md`](../stages/reconstruction.md)
- [`../core/digitizer.md`](../core/digitizer.md)
- [`../supports/README.md`](../supports/README.md)
