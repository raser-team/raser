# 命令行

_位于 `src/raser/cli/`_

---

## 命令

```bash
raser cce HPK-Si-PiN -s 4
raser tct signal HPK-Si-PiN SPA_top_Si_IR
```

前面是命令，`tct signal` 这样的命令有两个词；再后面是器件和选项。命令所属的应用：

| 命令 | 应用 |
| --- | --- |
| `bmos` | [`apps/bmos`](../apps/bmos.md) |
| `cce` | [`apps/cce`](../apps/cce.md) |
| `field` | [`apps/field`](../apps/field.md) |
| `lumi` | [`apps/lumi`](../apps/lumi.md) |
| `signal` | [`apps/signal`](../apps/signal.md) |
| `tct` | [`apps/tct`](../apps/tct.md) |
| `telescope` | [`apps/telescope`](../apps/telescope.md) |
| `timeres` | [`apps/timeres`](../apps/timeres.md) |

`raser --help` 列出全部命令，`raser <命令> --help` 列出一条命令的选项。

器件决定在哪里运行：`HPK-Si-PiN` 就在 `work/HPK-Si-PiN/` 下，组件文件先在 `work/HPK-Si-PiN/components/` 里找（见[路径](../supports/paths.md)）。

## 在实验文件夹里

```bash
cd work/HPK-Si-PiN/cce
raser -s 4 --seed 7        # 即 raser cce HPK-Si-PiN -s 4 --seed 7
```

当前文件夹里有实验的 `config.json` 时，命令和器件从它取，只写选项。

## 交给集群

`-b` 把命令交给集群。`b` 写几个，内存就是几个 8 GB。

cce、signal、tct 这类按任务跑的命令，每个任务一个作业，`-b` 写在命令前后都一样：

```bash
raser -bb cce HPK-Si-PiN -s 10
raser cce HPK-Si-PiN -s 10 -b -mem 2       # 同上
```

`field` 整条命令一个作业：

```bash
raser -bb field HPK-Si-PiN
```

`-t` 只看不交：对 `field` 打印作业脚本和提交命令，对按任务跑的命令等于 `--dry-run`。

任务怎么分、结果放在哪，见[任务](../lifecycle/jobs.md)和[运行记录](../lifecycle/runs.md)。
