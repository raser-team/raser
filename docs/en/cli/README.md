# Command line

_Under `src/raser/cli/`_

---

## Commands

```bash
raser cce HPK-Si-PiN -s 4
raser tct signal HPK-Si-PiN SPA_top_Si_IR
```

The command comes first, two words for commands such as `tct signal`; the
device and the options follow. The application each command belongs to:

| Command | Application |
| --- | --- |
| `bmos` | [`apps/bmos`](../apps/bmos.md) |
| `cce` | [`apps/cce`](../apps/cce.md) |
| `field` | [`apps/field`](../apps/field.md) |
| `lumi` | [`apps/lumi`](../apps/lumi.md) |
| `signal` | [`apps/signal`](../apps/signal.md) |
| `tct` | [`apps/tct`](../apps/tct.md) |
| `telescope` | [`apps/telescope`](../apps/telescope.md) |
| `timeres` | [`apps/timeres`](../apps/timeres.md) |

`raser --help` lists all commands; `raser <command> --help` lists the options
of one.

The device decides where a command runs: `HPK-Si-PiN` runs under
`work/HPK-Si-PiN/`, and component files are looked up first in
`work/HPK-Si-PiN/components/` (see [paths](../supports/paths.md)).

## Inside an experiment folder

```bash
cd work/HPK-Si-PiN/cce
raser -s 4 --seed 7        # same as raser cce HPK-Si-PiN -s 4 --seed 7
```

When the current folder holds an experiment's `config.json`, the command and
the device come from it; only options are written.

## To the cluster

`-b` hands a command to the cluster. As many `b`s as you write, that many
times 8 GB of memory.

Commands that run in jobs, such as cce, signal and tct, submit one cluster job
per job, with `-b` before or after the command alike:

```bash
raser -bb cce HPK-Si-PiN -s 10
raser cce HPK-Si-PiN -s 10 -b -mem 2       # the same
```

`field` is submitted as one job for the whole command:

```bash
raser -bb field HPK-Si-PiN
```

`-t` shows without submitting: for `field` it prints the job script and the
submit command, for commands that run in jobs it is `--dry-run`.

How jobs are split and where results go: [jobs](../lifecycle/jobs.md) and
[runs](../lifecycle/runs.md).
