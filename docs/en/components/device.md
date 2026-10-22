# Device component

A Device component binds a [Device project](../core/device.md) to an
application project. It records the Device reference and the operating state
selected for that application.

## Definition

```text
<application-project>/components/device/<name>.json
```

The entry contains:

- its name in the application project
- a symbolic name or path identifying the Device project
- selected bias, temperature, and irradiation state
- selected Field configuration values

Resolution starts from the defaults in `device.json`, applies the values in
the Device component, and then applies named run and invocation values through
[Run records](../supports/runs.md). The resolved state addresses one Field
configuration stored by the Device project.

The application records the Device reference, definition revision, resolved
state, Field configuration, and Field configuration hash in `run.json`.
