# Runtime paths

_RASER 5.0 path and context contract in `src/raser/supports/paths.py`_

---

## 📋 Responsibility

Paths gives every caller one interpretation of work roots, active projects,
component roots, packaged application assets, and logical namespaces. It
calculates locations from explicit path inputs. Component schemas, scientific
models, and workflow results remain with their owning callers.

## 🗂️ Runtime roots

| Variable | Input meaning | Default meaning |
| --- | --- | --- |
| `RASER_WORK_PATH` | Parent of named projects | Repository work directory |
| `RASER_PROJECT_PATH` | Active project for the invocation | Current directory |
| `RASER_COMPONENT_PATH` | Additional ordered component roots | Empty root list |

Path helpers return `Path` values. Filesystem mutations are delegated to
[Output](output.md) or an explicit owning caller.

## 🔍 Project inference

| Selector | Active project |
| --- | --- |
| Existing `RASER_PROJECT_PATH` | Explicit environment value |
| Bare project or detector name | `<work-root>/<name>` |
| Path below `components/` | Directory above `components/` |
| Explicit route-selector file | Its parent, or the directory above its `components/` segment |
| Missing project selector | Current project context |

Each route declares at most one context selector. Auxiliary inputs such as
`--config` leave the detector or target selected by that route unchanged.
Explicit context takes precedence over inference.

The CLI activates context before creating any context-derived arguments and
restores the previous values after dispatch, including on exceptions. Nested
contexts restore the immediately preceding state.

## 📦 Component lookup

Symbolic component entries use this order:

1. `<project>/components/`
2. application component roots selected for the command
3. roots in `RASER_COMPONENT_PATH`
4. packaged definitions under `src/raser/components/`

Root deduplication preserves first occurrence. The first existing candidate
wins. Required symbolic or explicit inputs raise `FileNotFoundError` with the
requested identity and attempted locations. Optional lookup returns `None`
where absence has defined meaning.

Packaged application configuration is resolved by application and relative
asset name through a namespace separate from reusable
[Component](../components/README.md) lookup.

## 🔗 Dependency direction

Environment setup establishes default roots. [CLI routing](../cli/raser.md)
activates one temporary context. Applications and Core then request paths
through the explicit Supports interface.

## ⚠️ Failure contract

Missing required inputs, parent-escaping or invalid logical segments, unknown
application assets, and filesystem resolution errors remain visible. Context
cleanup restores prior environment values before re-raising a dispatch error.
