# Output ownership

_RASER 5.0 filesystem operations in `src/raser/supports/output.py`_

---

## 📋 Responsibility

Output maps a declared owner and relative labels beneath the active project,
creates explicitly requested directories, and performs narrow file operations.
The caller supplies filenames, serializes domain data, and determines workflow
completion.

## 🗂️ Namespaces

| Owner | Namespace |
| --- | --- |
| Application workflow | `<project>/<workflow>/<run_id>/...` |
| Direct Core command | `<project>/<core-subsystem>/...` |
| External caller | `<project>/<declared-owner>/...` |

Labels are relative path segments confined beneath the active project.
Absolute and parent-escaping labels fail validation.

An application creates its run root and passes explicit artifact destinations
to Core. A direct Core command may ask Core to derive a subsystem
namespace. Application calls supply their artifact destinations explicitly.

## ⚙️ Operations

Path calculation and mutation remain separate contracts:

- [Paths](paths.md) calculates project and logical locations
- Output creates the requested directory or removes the requested file
- the caller owns file format, serialization, and scientific validation
- permission, existence, and I/O failures propagate

Generated data belongs under the active project or another destination
explicitly owned by the caller.

## ⚠️ Failure contract

Absolute or parent-escaping labels fail before mutation. An operation outside
the active project is rejected. Overwrite and removal require an explicit
permitting operation. Partial filesystem work remains visible to the caller.
