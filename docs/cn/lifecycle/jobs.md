# 作业、日志、锁、断点续跑与集群提交

`src/raser/lifecycle/jobs.py`、`src/raser/lifecycle/scheduler.py` 与 `src/raser/lifecycle/workflow.py` 管理本地与集群作业的拆分与运行、作业日志、三把文件锁、断点续跑，以及向 `hep_sub` 或 HTCondor 集群提交作业和自动续跑。

## 输入

### 运行记录与已提交标记

- `<种子或扫描点文件夹>/run.json`：每个作业启动时读取其中的 `"options"`、`"files"`、`"seed"`、`"point"`、`"same_seeds"` 与 `"held_in"`；集群作业完成后的自动续跑读取 `"command"`、`"cwd"` 与 `"waiting"`。
- `<种子或扫描点文件夹>/batch/<name>_<index>.submitted`：记录已提交到集群但尚未完成的片（无片工作流为 `job`），内容为含 `"job"`（集群作业号）和 `"time"`（提交时间 `YYYY-MM-DD HH:MM:SS`）的 JSON。

### 环境变量

集群规划、提交与续跑读取以下环境变量：

| 环境变量 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `RASER_SCHEDULER` | `"hep_sub"` | 无 | 集群调度器类型，可选 `"hep_sub"` 或 `"condor"` |
| `RASER_CONDOR_JOB_FLAVOUR` | `"workday"` | 无 | `RASER_SCHEDULER=condor` 时写入 `.sub` 的 `+JobFlavour`，可选 `"espresso"`、`"microcentury"`、`"longlunch"`、`"workday"`、`"tomorrow"`、`"testmatch"`、`"nextweek"` |
| `RASER_ENV_ROUTE` | 未设置 | 无 | 集群节点源码树激活的环境路线名（设置时执行 `. env/setup_cvmfs.sh <route>`，未设置时执行 `. env/setup.sh`） |
| `RASER_SUBMIT_QUEUE` | 未设置 | 无 | 容器内提交命令队列文件路径；设置后将提交命令追加写入该文件供宿主机提交 |
| `RASER_CLUSTER_JOB` | 未设置 | 无 | 集群作业脚本中导出为 `"1"`，标识当前进程运行在集群工作节点上 |
| `RASER_RESUBMIT_DEPTH` | `"0"` | 次 | 集群作业完成时自动重启命令的当前深度 |

## 输出

### 本地与集群作业执行方式

根据命令行参数与扫描点数目，待运行作业按以下方式启动：

- **本地单点单作业（省略 `-s` 且未传 `-b`，仅 1 个扫描点）**：在当前进程内直接运行作业 `0`，输出同时写入终端与 `batch/job_0.log`。
- **本地多点单作业（省略 `-s` 且未传 `-b`，多个扫描点）**：每个扫描点启动独立子进程运行作业 `0`，输出写入各自的 `batch/job_0.log`；某点失败时先继续其余点再汇总报错。
- **本地多作业进程池（传入 `-s <N>` 且未传 `-b`）**：通过 `ProcessPoolExecutor` 并行运行各待跑作业索引，最大并发进程数为 `min(待运行作业数, CPU 核数)`，各作业输出分别写入 `batch/job_<index>.log`。
- **集群批量提交（传入 `-b` / `--batch`）**：为每个待运行作业生成集群脚本并提交到 `hep_sub` 或 `condor_submit`。

### 作业日志 `batch/job_<index>.log` 与异常提取

- 本地运行的每个作业将日志写入 `<种子或扫描点文件夹>/batch/job_<index>.log`。
- 含片工作流完成本次请求的全部片后，向标准输出打印正常结束标记 `raser: the job ran its slices: <逗号分隔的片名列表>`。本地作业退出码非零时，主命令从日志末尾反向扫描提取最后一行 Python 异常行（跳过末尾的 Geant4/ROOT C++ 输出）。

### 看示例里发生了什么

在 [快速入门](../getting-started.md) 的示例中，运行 `raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1` 时，每个扫描点启动 `0` 和 `1` 两个本地并行作业，在 `work/HPK-Si-PiN/signal/seed_1/batch/`（以及 `voltage_100/seed_1/batch/`）下生成各切片的 `.done` 标记和作业日志：

1. **`<片>_<作业>.done` 的样子**：
   - `deposit_0.done`、`current_0.done`、`readout_0.done`、`reconstruction_0.done` 以及整作业完成标记 `job_0.done` 均为空文件（切片返回空或无额外信息）。
   - `field_0.done`（及 `field_1.done`）写出了共享场目录的 JSON 路径（实际运行中记录绝对路径）：

     ```json
     {"field": "work/HPK-Si-PiN/field"}
     ```

2. **`job_<作业>.log` 的样子**：
   `work/HPK-Si-PiN/signal/seed_1/batch/job_0.log` 记录了 Geant4 初始化、各事例的载流子数与绘图文件路径，并在末尾打印整作业完成的切片列表（此处略去大段 Geant4 与 ROOT 重复输出）：

   ```text
   ...
   2026-11-18 21:47:43,887 - INFO - DevsimField initialization complete, resolution: {'z': 0.05, 'x': 10000.0, 'y': 10000.0} um
   2026-11-18 21:47:43,889 - INFO - current calculation start...
   2026-11-18 21:47:43,889 - INFO - carriers inside the detector: 27 electrons, 27 holes
   Info in <TCanvas::Print>: pdf file work/HPK-Si-PiN/signal/seed_1/plots/job_0/event_4/planar_drift_path.pdf has been created
   ...
   2026-11-18 21:48:15,582 - INFO - clusters stopped: collected 5726 (1.92481e+06 carriers), left_device 5226 (1.8019e+06 carriers)
   ...
   raser: the job ran its slices: deposit,field,current,readout,reconstruction
   ```

### 三把文件锁（`fcntl.flock`）

RASER 通过非阻塞排他锁协调并发进程：

| 锁文件路径 | 持有阶段 | 作用 |
| --- | --- | --- |
| `<实验文件夹父目录>/.<实验文件夹名>.config.lock` | 首次无锁读取 `config.json` 确定实验目录之后，获取锁并重读 `config.json`，至获取全部点目录锁并写完 `config.json` 后释放（`--dry-run` 不加锁） | 串行化并发命令对同一实验 `config.json` 的读写与合并 |
| `<种子或扫描点文件夹父目录>/.<种子或扫描点文件夹名>.lock` | 写入 `config.json` 前获取，至所有扫描点的作业启动或本地执行完毕后释放 | 保护种子或扫描点文件夹（置于文件夹旁侧，使重跑重命名旧文件夹时锁依然有效） |
| `<种子或扫描点文件夹>/batch/job_<index>.lock` | 单个作业进程入口获取，作业退出时释放 | 阻止同一作业索引被并发执行；重跑过期片前检查是否有作业正在运行 |

当底层文件系统不支持 `flock` 时，终端输出警告并继续运行。

### 集群作业脚本与提交文件

`scheduler.plan_job` 在 `work/<device>/<command>/jobs/` 下规划作业脚本 `<command_name>.job`（超过 200 字节时截断并拼接摘要）与提交描述并返回 `ClusterJobPlan`，由 `scheduler.main` 在非预览模式下实际写出 `.job` 与 `.sub` 文件。脚本会清理显示环境变量、导出 `RASER_CLUSTER_JOB=1`、过滤 X11 容器绑定挂载、激活本地或 `/cvmfs` 环境并执行作业命令；每个作业申请内存为 `8000 * batch_level` MB。

- **`hep_sub` 后端（默认）**：执行 `hep_sub -o <job_dir> -e <job_dir> <job_file> -mem <memory_mb> -g <group_name>`。
- **`condor` 后端（`RASER_SCHEDULER=condor`）**：生成 `<job_dir>/<command_name>.sub` 并执行 `condor_submit`。
- **宿主机提交队列（`RASER_SUBMIT_QUEUE` 非空时）**：将提交命令追加写入该队列文件，由宿主机统一提交；等待上游的命令在依赖完成后需手动再执行一次。

### 断点续跑与集群自动续跑

1. **本地与登录节点断点续跑**：
   - 对同一固定种子 `--seed <N>` 再次运行或增大 `-s` 作业数时，在旧运行及对应切片未过期、仍可复用的前提下，已留有 `.done` 的作业与切片直接跳过，只补跑新增或未完成的部分。
   - 集群模式下提交成功会创建 `.submitted` 标记（完成后删除）；再次在登录节点提交 `-b` 时会自动查询调度器，仍在队列中的作业跳过，已不在队列中的判定为失败并自动重提，调度器无法查询时保留原状。
2. **集群工作节点自动续跑**：
   - 含片工作流在集群作业新增至少一个切片完成标记后、无片工作流在作业正常完成后，会自动拉起 `run.json` 中记录的 `"waiting"`（如等待共享场求解的命令），含片工作流还会拉起本实验等待跨点上游片的 `"command"`（带 `--seed-folder`），单次最多尝试 4 次（仅在再次尝试前等待 30 s）且递归深度受限制；若达到深度上限或 4 次均未启动成功，终端会打印提示，待前置作业完成后手动再运行一次原命令即可。

## 选项表

| 选项 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `-s`, `--jobs` | `None`（按 `1` 处理） | 个 | 每个扫描点运行的作业数量，作业索引为 `0 .. N-1`（由带种子工作流及四个环节命令注册） |
| `-b`, `--batch` | `False`（全局计数 `0`） | 无 | 提交作业到集群；放在子命令前的全局 `-b`、`-bb` 等同时将 `mem` 设为 `max(mem, b的个数)` |
| `-mem` | `1` | `8000 MB` | 每个集群作业申请的内存档位，实际申请 `8000 * mem` MB |
| `-t`, `--test` | `False` | 无 | 放在子命令前的全局选项；只在同时带顶层 `-b` 时把 `dry_run` 设为真 |
| `--dry-run` | `False` | 无 | 打印各扫描点待运行的作业与片列表后直接返回（`raser field <实验目录>` 打印各点共享片是否就绪） |

## 常见报错

- `Running: <what> is run by another process now; run the command again when it is done`：实验配置锁 `.config.lock`、运行文件夹锁 `.<folder>.lock` 或单作业锁 `batch/job_<index>.lock` 正被另一进程持有。
- `RuntimeError: Local jobs failed for indices <list>\n  job <index>: <last_line> (<log>)`：本地进程池中有一个或多个作业退出码非零，报错列出失败索引、日志中提取的最后异常行及日志路径。
- `RuntimeError: the job failed: <last_line> (<log>)`：本地多扫描点单作业模式下，某个扫描点的子进程退出码非零。
- `RuntimeError: Cluster accepted indices <accepted>; failed indices <failed>`（设置 `RASER_SUBMIT_QUEUE` 时为 `Cluster queued indices <accepted>; failed indices <failed>`）：批量向集群提交作业时，部分作业索引提交失败。
- `ValueError: Unknown scheduler: <scheduler>`：环境变量 `RASER_SCHEDULER` 设为了 `"hep_sub"` 和 `"condor"` 以外的值。
- `ValueError: Unknown HTCondor job flavour: <flavour>`：`RASER_SCHEDULER=condor` 时，环境变量 `RASER_CONDOR_JOB_FLAVOUR` 不在允许的 7 个类别之中。
- `ValueError: Indexed job count must be positive` / `ValueError: Indexed job memory level must be positive`：`plan_indexed_jobs` 收到的作业数 `count <= 0` 或内存档位 `mem <= 0`。
- `ValueError: Batch memory level must be positive` / `ValueError: Batch worker command must contain tokens`：`scheduler.plan_job` 收到的 `batch_level <= 0` 或命令词列表为空。

## 相关页面

- [快速入门](../getting-started.md)
- [总纲](../architecture.md)
- [命令行总览](../cli.md)
- [实验与扫描点](experiments.md)
- [片与状态查看](slices.md)
- [路径与运行支撑](../supports/README.md)
