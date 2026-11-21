# Shared supports

_RASER 5.0 engineering infrastructure under `src/raser/supports/`_

Supports provides mechanisms shared by the CLI, Applications, and Core.
Scientific models, physical processes, workflow defaults, and analysis policy
remain with their owning layers.

---

## 📦 Modules

| Module | Responsibility | Detailed contract |
| --- | --- | --- |
| `paths.py` | Work/project roots, component lookup, and app assets | [Paths](paths.md) |
| `output.py` | Owned directories and small filesystem operations | [Output](output.md) |

`io_decorator.py`, `memory_decorator.py`, and `root_tree.py` provide narrow
diagnostic or format utilities. They remain mechanisms: callers decide when a
measurement, conversion, or serialization belongs in a workflow.

Scientific interpolation, convolution, fitting, and other numerical behavior
belongs to the relevant Core capability contract.

## 📋 Boundary

Callers supply scientific intent and normalized data. Supports may resolve a
path, create a requested destination, or convert one declared format. Every call
carries explicit policy inputs as normalized values.

Applications own collectors and artifact schemas. Application collectors
classify missing event files and select Core metrics.

## 🔗 Dependency direction

```text
CLI ───────────────┐
Applications ──────┼──> Supports ──> filesystem
Core ──────────────┘
```

Dependency edges from CLI, Applications, and Core terminate at Supports.
Cross-module helpers accept explicit typed values and preserve visible errors.
