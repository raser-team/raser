# Command-line interface

_RASER 5.0 installed entry point under `src/raser/cli/`_

The supported entry point is `raser`. User instructions use this installed
command; source-tree module invocations remain implementation details.

---

## ⌨️ Command surface

```bash
raser --help
raser <command> --help
```

| Public command | Owning package |
| --- | --- |
| `bmos` | [`apps/bmos`](../apps/bmos.md) |
| `cce` | [`apps/cce`](../apps/cce.md) |
| `field` | [`apps/field`](../apps/field.md) |
| `lumi` | [`apps/lumi`](../apps/lumi.md) |
| `signal` | [`apps/signal`](../apps/signal.md) |
| `tct` | [`apps/tct`](../apps/tct.md) |
| `telescope` | [`apps/telescope`](../apps/telescope.md) |
| `timeres` | [`apps/timeres`](../apps/timeres.md) |

CLI help is the authoritative syntax and option reference. Unregistered
top-level forms fail explicitly.

## 🔀 Routing

[`raser.py`](raser.md) owns parsing, route descriptors, lazy import, temporary
project/component context, process exit status, global batch dispatch, and
runtime cleanup. Applications receive the parsed top-level argument values
from the router.

Each route declares at most one project selector. Project inference and
component lookup follow [Supports paths](../supports/paths.md).

## 📁 Inside an experiment folder

When the current folder holds an experiment's `config.json`, the command
words and the Device come from it and the command line gives only options:

```bash
cd work/HPK-Si-PiN/cce
raser -s 4 --seed 7
raser -bb -s 4
```

The first line is `raser cce HPK-Si-PiN -s 4 --seed 7`. The global options
`-b` and `-t` come first.

## ⚙️ Batch boundaries

Global `raser -t -b <command>` submits one complete command. An application's
indexed mode expands one recorded run into workers. These are separate parser
and ownership boundaries; see [Jobs](../lifecycle/jobs.md) and
[Runs](../lifecycle/runs.md).
