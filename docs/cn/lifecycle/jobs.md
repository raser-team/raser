# 任务

_位于 `src/raser/lifecycle/jobs.py` 和 `scheduler.py` 的本地与集群执行_

---

## 输入

[运行记录](runs.md#运行)里的一条命令为每个点建一个种子文件夹。一个种子文件夹的计算再分成若干个任务，编号从 0 开始；`-s 4` 就是每个种子文件夹 4 个任务。

| 选项 | 含义 |
| --- | --- |
| `-s <n>` | 任务数；不给时为 1 |
| `-b` | 提交到集群；不给时在本机运行 |
| `-mem <n>` | 集群任务的内存，单位 8 GB；默认 1 |

## 运行

以 `raser cce HPK-Si-PiN -s 4 --seed 42` 为例。RASER 先建好种子文件夹 `seed_42/`，再为 4 个任务各生成一条内部命令并执行：

```bash
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 0
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 1
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 2
raser cce HPK-Si-PiN --job-dir work/HPK-Si-PiN/cce/seed_42 --job-index 3
```

有扫描时，每个点的种子文件夹各有这样一组任务。

任务的全部输入读自种子文件夹里的 [`run.json`](runs.md#输出)。

**本机**：各任务作为独立进程并行运行，同时运行的个数不超过任务数和 CPU 数。

**集群**：每个任务生成一份任务脚本并提交。脚本先进入 RASER 目录、重新启用环境，再执行任务命令；脚本和调度器的输出放在 `work/<应用>/jobs/`。

| 环境变量 | 含义 |
| --- | --- |
| `RASER_SCHEDULER` | `hep_sub`（默认）或 `condor` |
| `RASER_CONDOR_JOB_FLAVOUR` | HTCondor 的 JobFlavour；默认 `workday` |

## 输出

任务向种子文件夹的 `batch/` 写入产物，完成后写一份 `job_<编号>.json`，记完成时间和 commit：

```text
work/HPK-Si-PiN/cce/seed_42/
├── run.json
└── batch/
    ├── job_0.json
    └── stats_0.root
```

同一个种子文件夹再次运行时，只跑没有完成的任务。

带汇总的工作流在本机任务全部结束后汇总到 `analysis/`。集群任务结束后，用 `--collect` 汇总，汇总的位置见[运行记录](runs.md#输出)：

```bash
raser cce HPK-Si-PiN --collect
```

## 失败

任务数或内存不是正数时，在运行前报错。本机任务失败时报出失败的编号；集群提交失败时报出已接受和失败的编号。
