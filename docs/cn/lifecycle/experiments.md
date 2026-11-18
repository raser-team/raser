# 实验、扫描点与种子

`src/raser/lifecycle/workflow.py` 与 `src/raser/core/seeding.py` 管理实验文件夹、`config.json` 实验配置、`--set` 与 `--scan` 参数扫描点展开、种子文件夹与 `run.json` 运行记录，以及作业与片的随机数种子派生。

## 输入

### 实验配置文件 `<实验文件夹>/config.json`

程序按以下规则定位实验根目录并读取 `config.json`：若工作流自带固定输出目录（如 [`analysis`](../stages/analysis.md) 指向 `<experiment>/analysis`）则直接使用该目录；否则优先检查当前工作目录的 `config.json` 是否与当前命令匹配，再不然落到 `<project_root>/<workflow...>`（未设 `RASER_PROJECT_PATH` 且仅传普通器件名时，默认为 `<work_root>/<device>/<workflow...>`；在已含 `config.json` 的实验目录内可直接运行 `raser <选项>`）。

`config.json` 包含以下键：

| 键名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `"workflow"` | `str` | 无 | 工作流命令名，如 `"signal"`、`"cce"`、`"telescope taichu_v1"` |
| `"device"` | `str` | 无 | 器件名（仅带器件的工作流包含此键） |
| `"set"` | `dict[str, Any]` | 随参数而定 | 实验固定设置的参数或文件内点分地址键值表 |
| `"scan"` | `dict[str, list]` | 随参数而定 | 扫描参数或文件内点分地址到扫描值列表的映射 |
| `"names"` | `dict[str, str]` | 无 | 可选；参数或文件内点分地址到短名称的映射，用于 `--set`、`--scan` 及扫描点文件夹命名 |
| `"same_seeds"` | `bool` | 无 | 跨扫描点同种子开关，实际取值取命令行 `--same-seeds` 或本键；本键只在新建 `config.json` 时写入（仅带种子的工作流包含此键） |

### 器件与组件文件

每个扫描点读取实验使用的器件文件（存入 `files["device"]`，多器件时按器件名分别存入）以及源、`g4setup` 等组件文件（存入 `files[kind]`）。

### 参数合并、互斥组与文件内点分地址

每个扫描点的参数按从低到高三层优先级合并：工作流默认值、`config.json` 的 `"set"`、命令行参数（含命令专属选项与 `--set`）。命令行给出固定值的键在该次运行中不再扫描。

- **互斥选项组**：如 `("events_per_job", "generated_per_job")`。同一组参数由给出其中一项的最高优先级层决定，低层中的同组其余键会被移除。
- **文件内点分地址**：名称中含 `.` 的键视为 `files` 内的点分路径（如 `device.bias.voltage`）；单器件链将顶层选项 `voltage` 映射到 `device.bias.voltage`。当选项非 `None` 时覆盖 `files` 对应叶节点，为 `None` 时从 `files` 读取原值。

### 已有运行记录 `<种子或扫描点文件夹>/run.json`

运行前若目标种子或扫描点文件夹下已存在 `run.json`，读取其中的运行记录用于过期判断、片复用与续跑。

## 输出

### 实验配置文件 `<实验文件夹>/config.json`

新建实验时创建 `config.json` 并写入 `"workflow"`、`"device"`（带器件工作流）、`"set"`、`"scan"` 与 `"same_seeds"`（带种子工作流）；已有实验再传入 `--set` 或 `--scan` 时将新条目合并进 `config.json` 并清除同键或同互斥组的旧条目，普通命令选项只对本次运行生效。

### 扫描点文件夹与种子文件夹

- **扫描点文件夹 `<实验文件夹>/<point>`**：
  - 将所有扫描键的取值做笛卡尔积，并与基准无扫描运行逐键比较（基准点取三层合并后的固定值；没有固定值的扫描点分地址取组件文件原始值，实际扫描点取当前组合的扫描值）。
  - 所有扫描键值均等于基准点取值时，点目录名为空，直接使用 `<实验文件夹>`；存在差异时将差异项按 `<label>_<text>` 拼接为子文件夹名（`<label>` 优先取 `config.json` 的 `"names"` 短名，其次取点分地址末两段或键名本身；数值按 `"%g" % value` 格式化）。
- **种子文件夹 `<实验文件夹>/[<point>/]<seed_folder>`**：
  - 带种子的工作流：传入 `--seed <N>` 时文件夹名为 `seed_<N>`；省略 `--seed` 时以时间戳 `YYYY_mmdd_HHMMSS` 命名并随机抽取 31 位整数作为种子。当固定种子文件夹因过期重跑时，旧文件夹被重命名为 `<label>_<YYYY_mmdd_HHMMSS>` 保留在一旁。
  - 无种子工作流（如 `field`、`tct`、`analysis`）：运行直接落在扫描点文件夹 `<实验文件夹>/[<point>]` 下。

### 运行记录文件 `<种子或扫描点文件夹>/run.json`

`run.json` 记录单次运行的全部上下文，作业执行时从所在文件夹的 `run.json` 读取参数、文件快照与切片信息：

| 键名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `"seed"` | `int` | 无 | 运行种子（带种子工作流写入） |
| `"point"` | `str` | 无 | 扫描点相对文件夹名，无扫描运行（或等于默认值）时为 `""` |
| `"same_seeds"` | `bool` | 无 | 是否开启跨扫描点同种子（带种子工作流写入） |
| `"commit"` | `str` | 无 | 源码树下为 Git HEAD 提交哈希（有未提交改动时附加 `"+dirty"`）；包安装模式下为 `"raser <__version__>"` |
| `"options"` | `dict[str, Any]` | 随参数而定 | 合并三层配置并与文件内点分地址同步后的完整选项表 |
| `"files"` | `dict[str, Any]` | 随文件而定 | 写入了 `options` 覆盖值后的器件 JSON 与组件数据（JSON 组件内容或专用读取函数返回值；如 `g4setup` 保存脚本中的 `G4SETUP`、`"file"` 与 `"sha256"`） |
| `"settings"` | `dict[str, Any]` | 无 | 命令行附加设置（如 `field` 的 `umf` 与 `imported`） |
| `"slices"` | `dict[str, dict]` | 无 | 每个片读取的 `"options"`、`"files"` 及共享片摘要 `"shared"`（详见[片与状态查看](slices.md)） |
| `"held_in"` | `dict[str, str]` | 无 | 每个片名到持有该片输出的扫描点文件夹名的映射（详见[片与状态查看](slices.md)） |
| `"jobs"` | `int` | 个 | 当前运行记录中请求过的最大作业数（未过期续跑时保留历次最大值，过期重跑建立新记录时重新计数） |
| `"command"` | `list[str]` | 无 | 集群模式下记录的命令行词列表 |
| `"cwd"` | `str` | 无 | 集群模式下记录的命令启动工作目录路径 |
| `"waiting"` | `list[dict]` | 无 | 集群模式下等待当前共享作业完成的命令列表 |

### 看示例里发生了什么

以 [快速入门](../getting-started.md) 中的运行 `raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1` 为例：

1. **实验配置文件 `work/HPK-Si-PiN/signal/config.json` 原文**：

   ```json
   {
     "workflow": "signal",
     "device": "HPK-Si-PiN",
     "set": {
       "events_per_job": 200
     },
     "scan": {
       "voltage": [
         100,
         200
       ]
     },
     "same_seeds": false
   }
   ```

   命令中 `-evt 200` 属于被扫描或固定设置的实验参数，`--scan voltage=100,200` 写入 `"scan"`，`--seed 1` 决定种子文件夹名而非写入 `config.json`。

2. **扫描点文件夹命名**：

   `HPK-Si-PiN` 器件文件里的默认偏压是 `200 V`，因此 `200 V` 这个点与默认运行完全一致，点文件夹名为 `""`，结果直接落在实验根目录下的 `work/HPK-Si-PiN/signal/seed_1/`；`100 V` 与默认偏压不同，落在 `work/HPK-Si-PiN/signal/voltage_100/seed_1/`。随后的 `raser analysis work/HPK-Si-PiN/signal` 采用完全相同的规则：`200 V` 结果在 `analysis/` 根下，`100 V` 在 `analysis/voltage_100/`。

3. **`work/HPK-Si-PiN/signal/seed_1/run.json` 顶层键**：

   该次运行写出的顶层键为：

   ```text
   ['seed', 'point', 'same_seeds', 'commit', 'options', 'files', 'slices', 'held_in', 'jobs']
   ```

   其中 `"seed": 1`、`"point": ""`、`"same_seeds": false`、`"jobs": 2`；`"options"` 中记有 `"voltage": 200`、`"events_per_job": 200`、`"source": "decay/Sr90"`、`"g4setup": "device_alone"`、`"amplifier": "SantaCruz+Gali52+Termination50"` 等完整参数；`"held_in"` 中 `deposit`、`field`、`current`、`readout`、`reconstruction` 均映射为 `""`。

### 随机数种子派生与已完结作业收集

- **作业与片的随机种子派生**：在每个作业或片启动前，程序默认按 `[seed, point, job_index, slice_name]`（开启 `--same-seeds` 时省略 `point`）拼出路径串并做 SHA-256 哈希，映射为 $[1, 2^{31}-1]$ 内的整数同时设置 Python `random` 与 `ROOT.gRandom`；命名随机流 `seeding.stream(name)` 在此基础上再次派生独立种子，使开启 `--same-seeds` 的各扫描点在同一作业与切片下使用相同的随机种子；当上游切片读取的扫描值也相同时，各点共享该上游切片输出。
- **已完结作业收集**：`finished` 与 `finished_in` 遍历每个扫描点下未过期的 `run.json`（按名称跳过以 `seed_` 开头且与所记种子不符的重跑保留目录，如 `seed_<n>_<timestamp>`；另存的时间戳目录仍会按选项与文件是否过期参与筛选），收集其中拥有 `batch/job_<index>.done` 的全部作业，供 `raser analysis` 汇总使用。

## 选项表

以下公共运行选项注册到各实验与阶段命令：

| 选项 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `-s`, `--jobs` | `None`（按 `1` 处理） | 个 | 每个扫描点运行的作业数（由带种子工作流及四个环节命令注册；目标工作流无种子时在点目录内运行） |
| `--seed` | `None`（随机抽取 31 位整数） | 无 | 指定运行种子整数 `<N>`，种子文件夹命名为 `seed_<N>`（由带种子工作流及四个环节命令注册；目标工作流无种子时在点目录运行，无独立种子文件夹） |
| `--same-seeds` | `False` | 无 | 各扫描点在同一作业索引和片名下使用相同的派生种子，上游片读取的扫描值相同时共享该片输出；实际取值取本选项或 `config.json` 的 `"same_seeds"`（由带种子工作流及四个环节命令注册） |
| `--set` | `[]` | 无 | 设置单个参数或文件内点分地址 `address=value`；值按 JSON 解析，解析不了时保留原字符串；可重复给出，普通实验运行写入 `config.json` 的 `"set"`（`--dry-run` 及 `raser field <实验目录>` 仅用于选择本次点，不修改实验配置） |
| `--scan` | `[]` | 无 | 扫描参数或文件内点分地址 `address=v1,v2,...`；先按 `,` 切分，各值按 JSON 解析，解析不了时保留原字符串；可重复给出，普通实验运行写入 `config.json` 的 `"scan"`（`--dry-run` 及 `raser field <实验目录>` 仅用于选择本次点，不修改实验配置） |
| `-b`, `--batch` | `False` | 无 | 将作业提交到集群运行（详见[作业与集群提交](jobs.md)） |
| `-mem` | `1` | `8000 MB` | 每个集群作业申请的内存档位（详见[作业与集群提交](jobs.md)） |
| `--dry-run` | `False` | 无 | 打印各扫描点待运行的作业与片列表后直接返回（`raser field <实验目录>` 打印各点共享片是否就绪） |

## 常见报错

- `ValueError: <keys>: given to --set and to --scan at once; give it to one of them`：同一参数或地址（含通过 `"names"` 映射的短名）在一次命令中同时传给了 `--set` 和 `--scan`。
- `ValueError: <key1> and <key2> are given at once in <where>; give one of them`：同一互斥组中的两个非 `None` 键在当前检查到的配置层中同时给出（`_points` 按命令行、`config.json` 的 `"set"`、默认值由高到低查找并止于首个有效层；工作流构造时还会以 `<where> = "the defaults of <工作流名>"` 检查默认值）。
- `ValueError: <key> is scanned and another key of its group is given; give one of them`：命令行用 `--scan` 扫描互斥组中的某个键，同时又在命令行给出了同组另一键的固定值。
- `ValueError: <key1> and <key2> are scanned at once; scan one of them`：同一互斥组中的两个键同时出现在扫描列表中。
- `ValueError: <address>: no '<step>' in <walked>`：`--set`、`--scan` 或 `Workflow.in_file` 指定的点分地址在 `files` 对应结构中缺少中间层级，或显式点分键缺少末级键（对于 `Workflow.in_file` 普通映射如 `voltage → device.bias.voltage`，若仅末级键缺失，读取时抛出 `KeyError`，写入时创建该键）。
- `ValueError: <key> = <value>: the folder of this value would be named '<text>', which holds more than letters, digits and ._+-; scan or set a number or a short name, and give an expression such as a doping profile a parameter with a name in its file`：扫描值或设置值格式化后的名称含有字母、数字及 `._+-` 以外的字符。
- `ValueError: <key>: <v1> and <v2> would both be the folder '<text>'`：同一扫描键的两个不同取值格式化后生成相同的文件夹名片段。
- `ValueError: <key1> and <key2> would both be '<label>' in the names of folders: give one of them a name under "names" in config.json`：两个扫描键生成的标签 `<label>` 重名，需在 `config.json` 的 `"names"` 中为其中一个指定短名。
- `ValueError: <other> and <current> would both be the folder '<name>'; scan values that do not hold the names of other scanned options`：两组不同扫描参数组合拼接出了相同的扫描点文件夹名。
- `ValueError: <root>: no seed folder <label> to go on in`：续跑时在实验目录及其扫描点子目录下均未找到 `<label>/run.json`。
- `ValueError: <root>: not an experiment folder, no config.json that names a workflow`：调用 `finished_in(root)` 时，目标文件夹下缺少含 `"workflow"` 键的 `config.json`。
- `ValueError: <root>: no command runs its workflow '<workflow>'`：`config.json` 中的 `"workflow"` 未注册。

## 相关页面

- [快速入门](../getting-started.md)
- [总纲](../architecture.md)
- [命令行总览](../cli.md)
- [片与状态查看](slices.md)
- [作业与集群提交](jobs.md)
- [器件定义](../core/device.md)
- [分析环节](../stages/analysis.md)
- [路径与运行支撑](../supports/README.md)
