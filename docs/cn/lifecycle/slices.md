# 片、过期判断、完成标记与状态查看

`src/raser/lifecycle/slices.py`、`src/raser/lifecycle/status.py`、`src/raser/lifecycle/workflow.py` 与 `src/raser/stages/chain.py` 将单个作业按阶段拆分为片（`Slice`），管理片间 `needs` 依赖、片读取的内容与过期判断、`.done` 完成标记、片重跑以及 `raser status` 进度查询。

## 输入

### 片定义（`Slice` 与 `Shared`）及仿真链展开

`Slice`（`src/raser/lifecycle/slices.py`）定义单作业的一个执行片段：

| 字段 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 片名，对应切片数据文件名与 `.done` 标记文件名前缀 |
| `run` | `Callable` | 必填 | 执行函数 `run(options) -> dict \| None`，返回值写入该片的 `.done` 文件 |
| `keys` | `tuple` | `()` | 直接影响该片输出的实验选项名元组 |
| `kinds` | `tuple` | `()` | 直接影响该片输出的组件文件类别元组 |
| `new_events` | `bool` | `True` | 扫描该片选项时是否生成独立事件；`True` 时（未启用 `--same-seeds`）各扫描点独立运行其上游片，`False` 时各扫描点共享同一份上游片 |
| `shared` | `Shared \| None` | `None` | 跨实验共享资源接口（含 `ready`、`start`、`stamp` 三个回调） |
| `needs` | `tuple \| None` | `None` | 直接读取其输出的上游片名元组；`None` 表示列表中的前一个片，`()` 表示无上游片依赖 |

`src/raser/stages/chain.py` 构建标准仿真链的片序列：

- 单器件单位置：

| 片名 | `needs` | `keys` | `kinds` | `new_events` | `shared` |
| --- | --- | --- | --- | --- | --- |
| `deposit` | `()` | `source`, `g4setup`, `events_per_job`, `generated_per_job`, `generated_limit`, `edep_min`, `edep_max`, `fano` | `source`, `g4setup` | `True` | `None` |
| `field` | `()` | `voltage`, `irradiation` | `()` | `True` | [`field.SHARED`](../stages/field.md) |
| `current` | `("deposit", "field")` | `plots` | `()` | `True` | `None` |
| `readout` | `("current", "field")` | `amplifier`, `sheet_resistance` | `()` | `False` | `None` |
| `reconstruction` | `("readout",)` | `threshold`, `amplitude_threshold`, `fractions`, `edge` | `()` | `False` | `None` |

- 多器件或多位置：首片为 `deposit`；每个器件生成独立的电场片（器件数大于 1 时命名为 `field.<device>`，拥有各自的共享电场接口）；每个位置依次生成 `current.<position>`、`readout.<position>` 与 `reconstruction.<position>`。

### 依赖传递与参数归属

每个片通过 `needs` 沿链路向前追溯全部上游片，某选项或组件文件只要被该片本身或其任一上游片读取，就会记入该片在 `run.json["slices"]` 中的输入快照；未显式归属到特定片的键（如 `device.*`）归属于所有根片（`deposit` 与 `field`）。

### 运行记录与磁盘标记文件

过期判断、片重跑与 `raser status` 读取以下文件与键：

- `<实验文件夹>/config.json`：读取实验设置与扫描列表。
- `<种子或扫描点文件夹>/run.json`：读取 `"slices"`（各片读取的参数快照与共享片摘要）、`"held_in"`（各片实际存放的扫描点目录）、`"commit"`、`"settings"`、`"seed"`、`"point"`、`"same_seeds"`、`"jobs"`、`"waiting"`。
- `<持有该片的文件夹>/batch/<slice_name>_<index>.done`：单作业在对应片上的完成标记及可选 JSON 返回值。
- `<种子或扫描点文件夹>/batch/job_<index>.done`：单作业的全部片完成标记。
- `<种子或扫描点文件夹>/batch/job_<index>.lock`、`batch/job_<index>.log`、`batch/<slice_name>_<index>.submitted`：由 `raser status` 读取以判定作业实时状态（详见[作业与集群提交](jobs.md)）。

## 输出

### 阶段切片数据文件 `batch/<slice_name>_<index>.h5`

各片在持有该片的文件夹（由 `held_in` 指定）下的 `batch/` 目录读写切片数据文件：

| 文件路径 | 写入片 |
| --- | --- |
| `batch/deposit_<job>.h5` | [`deposit`](../stages/deposit.md) |
| `batch/current_<job>.h5` 或 `batch/current.<position>_<job>.h5` | [`current`](../stages/current.md) / `current.<position>` |
| `batch/readout_<job>.h5` 或 `batch/readout.<position>_<job>.h5` | [`readout`](../stages/readout.md) / `readout.<position>` |
| `batch/reconstruction_<job>.h5` 或 `batch/reconstruction.<position>_<job>.h5` | [`reconstruction`](../stages/reconstruction.md) / `reconstruction.<position>` |

### 完成标记文件 `batch/<name>_<index>.done` 与被搁置为 `.stale` 的输出文件

- **片完成标记 `batch/<slice_name>_<index>.done`**：写在持有该片的文件夹的 `batch/` 下。实际执行的片先写入 `.done.part` 再原子替换：无返回值时为空文件，有返回值时写入 JSON（如 `field` 片记录共享场目录路径，多位置某位置无沉积记录 `{"events": 0}`，沉积数为 0 提前结束记录 `{"ended": true}`）；因上游 `ended` 而跳过的下游片直接通过 `touch()` 创建空 `.done` 标记。
- **整作业完成标记 `batch/job_<index>.done`**：当该作业的所有片均已完成时在当前种子或扫描点文件夹下创建空的 `batch/job_<index>.done`。
- **被搁置为 `.stale` 的输出文件**：若切片运行期间 `run.json` 被另一并发命令修改，本次刚生成的切片输出会被重命名为 `<原文件名>.stale` 并提示重新运行。

### 过期判断与片重跑

每次运行命令时，程序把当前计算的各片读取快照及共享片摘要与已有 `run.json` 对比：

- 只有读取快照或共享片摘要发生变化的片及其下游片会清除 `.done` 并在原地重跑；输入未变且所请求的全部作业索引均已留有 `.done` 的片才显示 `reused`，否则显示待运行索引。
- 若命令行 `settings` 变化或所有非共享片均需重跑，或（在未自定义 `outdated` 回调的默认判定下）代码 `commit` 变化、含未提交改动 `+dirty` 或记录的其余字段变化，则整次运行判为过期（如 `field` 工作流仅检查命令行 `settings`、选项、器件 `"field"` 配置与求解器实际读取的器件值）：带种子的运行将旧种子目录重命名为 `<label>_<YYYY_mmdd_HHMMSS>` 保留在一旁，无种子的运行原地替换。

### 看示例里发生了什么

在 [快速入门](../getting-started.md) 的示例中，首先带 `--dry-run` 运行：

```bash
raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1 --dry-run
```

终端输出每个扫描点待运行的片与作业索引：

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
work/HPK-Si-PiN/signal/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
```

这段输出表明：

- 实验展开为两个扫描点：`100 V` 对应 `voltage_100/seed_1`，默认偏压 `200 V` 对应根目录下的 `seed_1`。
- 每个扫描点都要跑 `0` 和 `1` 两个作业，每个作业依次包含 `deposit`、`field`、`current`、`readout`、`reconstruction` 五个片；其中 `field` 在启动作业前先检查共享场 `work/HPK-Si-PiN/field/` 是否就绪，未就绪时先自动调用 `raser field` 求解 `100 V` 与 `200 V` 的场，并将共享场摘要（示例 `seed_1/run.json` 中为 `"23679e6b10596a26"`）写入 `field` 及其下游 `current`、`readout`、`reconstruction` 的 `"shared"` 记录中。
- 因为扫描的是 `field` 切片的 `voltage`（且未启用 `--same-seeds`），两个偏压点各自独立保存 5 个切片的输出（`held_in` 中 5 个片均为空字符串 `""`）。

全部作业跑完后，执行 `raser status work/HPK-Si-PiN/signal` 查看进度：

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
work/HPK-Si-PiN/signal/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
```

两个扫描点的 2 个作业在每个切片上均已完成（`2/2 done`）。

### `raser status <experiment>` 状态说明

`raser status` 检查每个片（或无片工作流）下各作业的 `.done`、`.lock`、`.submitted`、`.log` 及共享片就绪情况，将每个作业归入以下 7 种状态之一（并提示尚无 `run.json`、与当前 `config.json` 相比已过期 `out of date`、正在被其他命令等待 `waited for by` 等情况）：

| 状态 | 判定条件 |
| --- | --- |
| `done` | 持有该片的文件夹下已存在 `batch/<slice>_<i>.done`（无片工作流为 `batch/job_<i>.done`） |
| `running` | 未完成，且另一进程正持有该文件夹下的 `batch/job_<i>.lock` |
| `submitted` | 未完成且未在本地运行，存在 `batch/<slice>_<i>.submitted`，且集群调度器确认该作业仍在集群中 |
| `uncertain` | 存在 `batch/<slice>_<i>.submitted`，且集群调度器无法查询（命令报错或超过 120 s 超时） |
| `failed` | 存在 `batch/<slice>_<i>.submitted` 但调度器确认已不在集群中（此时自动删除该 `.submitted`）；或存在 `batch/job_<i>.log` 且含片工作流日志缺少正常结束行 `"raser: the job ran its slices"` |
| `waiting` | 上游片存在未完成作业；对当前 `config.json` 请求的扫描点，依赖的共享片尚未就绪时亦为 `waiting`（额外发现的磁盘点仅检查上游片与标记文件） |
| `not started` | 上游片均已完成（或无上游片），且该作业未启动、未提交、无失败日志 |

## 选项表

| 命令 / 参数 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `raser status <experiment>` | 必填 | 无 | 查看实验文件夹 `<experiment>`（如 `work/<device>/<command>`）下各扫描点与各片的作业进度 |
| `raser deposit <target>`（别名 `dep`） | 必填 | 无 | 运行 `<target>`（实验文件夹，或器件名对应的 `work/<device>/signal`）直至 `deposit` 片 |
| `raser current <target>`（别名 `cur`） | 必填 | 无 | 运行 `<target>` 的仿真链直至 `current`（或所有 `current.<position>`）片 |
| `raser readout <target>`（别名 `rdo`） | 必填 | 无 | 运行 `<target>` 的仿真链直至 `readout`（或所有 `readout.<position>`）片 |
| `raser reconstruction <target>`（别名 `reco`） | 必填 | 无 | 运行 `<target>` 的仿真链直至 `reconstruction`（或所有 `reconstruction.<position>`）片 |

阶段命令 `raser deposit|current|readout|reconstruction` 同时接受该阶段及其上游阶段的全部选项（详见[命令行总览](../cli.md)）以及[实验与扫描点](experiments.md)中的公共运行选项。

## 常见报错

- `SystemExit: <target>: neither an experiment folder (a folder with a config.json) nor a device; give one of them, e.g. work/<device>/cce or HPK-Si-PiN`：传给阶段命令的 `<target>` 既非含 `config.json` 的实验文件夹，也未能找到对应器件文件（仅捕获 `FileNotFoundError`；若目标存在但不是可读器件文件，原异常继续抛出）。
- `SystemExit: <folder>: the experiment <workflow> has no <stage> slice; its slices: <names>`：目标实验的工作流片列表中不含所请求的 `<stage>` 阶段。
- `ValueError: no slice <until> in <named>`：请求的截断片名 `until` 既不匹配当前工作流中任何片的完整片名，也不匹配任何片首个 `.` 之前的阶段名前缀。
- ``FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>` ``：执行 `field` 片时，未找到对应器件、偏压和辐照注量的已就绪电场。
- `RuntimeError: <piece.name> was made in this process and is still not ready for a point of <root>: waiting would not help`：本地进程完成共享片构建后，共享片仍未就绪。
- `RuntimeError: <piece.name> of job <index> needs <earlier.name>, which is not done in <folder>`：片启动检查时，其上游片在对应持有文件夹下缺少 `.done` 标记。
- `RuntimeError: run.json changed while <piece.name> of job <index> ran: its output is set aside as .stale and not marked done; run the command again`：片运行期间 `run.json` 被并发命令改动，刚生成的输出文件已被重命名为 `.stale`。
- `SystemExit: <k> of <n> points failed:\n  <folder>: jobs <waiting> wait for <needed>`：扫描点的作业所依赖的共享片或跨扫描点上游片尚未完成。
- `SystemExit: <k> of <n> points failed:\n  <folder>: jobs <running> run there now; the new settings did not take effect there; run the command again when they are done`：运行文件夹需要重跑过期片时，该文件夹内仍有正在运行的作业持有 `batch/job_<i>.lock`。

## 相关页面

- [快速入门](../getting-started.md)
- [总纲](../architecture.md)
- [命令行总览](../cli.md)
- [实验与扫描点](experiments.md)
- [作业与集群提交](jobs.md)
- [电场环节](../stages/field.md)
- [沉积环节](../stages/deposit.md)
- [电流环节](../stages/current.md)
- [读出环节](../stages/readout.md)
- [重建环节](../stages/reconstruction.md)
- [分析环节](../stages/analysis.md)
