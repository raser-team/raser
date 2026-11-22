# 能量沉积环节（`stages/deposit`）

`src/raser/stages/deposit.py` 由 [仿真链与环节入口（`stages`）](README.md) 的 `raser deposit`（短命令 `raser dep`）或测试、应用实验命令调度，在八环节仿真链中与共享的 [场求解环节（`stages/field`）](field.md) 同处最前端。本环节读取 `config.json` 中 `deposit` 段的设置、[探测器组件（`components/device`）](../components/device.md) 的器件定义 `files["device"]`，以及 [能量沉积组件（`components/deposit`）](../components/deposit.md) 的粒子源或束流配置 `files["source"]` 与 Geant4 装置脚本 `files["g4setup"]`。它调用 [器件模型（`core/device`）](../core/device.md) 构造 `Detector` 实例，再调用 [能量沉积与电离（`core/deposit`）](../core/deposit.md) 模拟粒子在探测器中的能量沉积步并将沉积能量转化为电子-空穴对，在节点目录 `nodes/deposit/<节点号>/` 下写出 `deposit.h5` 与 `node.json`（也可在节点内附带绘出 Geant4 几何与径迹图 `g4_geometry.png`，或打开窗口检查装置），并由视图软链接 `points/<点名>/deposit/<作业号>` 指向该节点。写出的沉积步坐标、时间、能量和电子-空穴对数交给下游 [载流子输运与感应电流环节（`stages/current`）](current.md) 做载流子漂移，每个事例最早的沉积时刻（`truth`）交给 [统计分析环节（`stages/analysis`）](analysis.md) 计算时间分辨。

## 行为

### 单独运行沉积环节与节点复用

`raser deposit`（或 `raser dep`）在当前文件夹或给定路径的实验上跑到 `deposit` 环节为止。命令格式如下：

```bash
raser deposit [路径]
raser dep [路径]
```

不给路径时操作当前实验文件夹；传入路径时可为相对或绝对路径，指向含 `config.json` 的实验文件夹。常规模式下，`deposit` 环节对本环节用到的设置值、组件文件里用到的部分和随机种子（由作业种子派生，见[实验、扫描点与种子](../lifecycle/experiments.md#种子)）取指纹作为 `<节点号>`，按随机种子执行粒子输运与电离转化；每个节点单独加锁，写到一半的节点带 `.part` 后缀，写完后改为正式节点目录 `nodes/deposit/<节点号>/`，内含 `deposit.h5` 与记录输入、代码版本、运行环境和运行状态的 `node.json`。当 `deposit.plots` 大于 `0` 且使用 Geant4 源（`"beam"` 或 `"decay_source"`）时，同一次 Geant4 运行会用离屏驱动 `TSG_OFFSCREEN` 把器件、周边装置和前 `deposit.plots` 个记录事例的径迹画成该节点输出目录下的 `g4_geometry.png`。程序同时更新实验根目录下的参数表 `points.json`，并将视图软链接 `points/<点名>/deposit/<作业号>` 指向 `../../../nodes/deposit/<节点号>`。后续无论在哪个扫描点或哪次运行中执行整链或下游环节命令，只要 `deposit` 节点的输入指纹相同就照常复用；把设置改回原值时视图重新指回旧节点，代码版本与 `node.json` 记录不一致时只给一条提示、已有结果照常复用，节点与复用规则见 [片与重跑](../lifecycle/slices.md)。

例如只对器件 `HPK-Si-PiN` 的 `signal` 实验运行 `2` 个作业的能量沉积，每个作业记录 `200` 个有效事例：

```bash
raser deposit examples/HPK-Si-PiN/signal -s 2 --set deposit.events_per_job=200 --seed 1
```

该命令以 `examples/HPK-Si-PiN/signal` 为实验文件夹，仅运行到 `deposit` 环节，在 `examples/HPK-Si-PiN/signal/nodes/deposit/<节点号>/` 下写出 `deposit.h5`、`node.json` 与 `g4_geometry.png`，更新 `examples/HPK-Si-PiN/signal/points.json` 并建立 `points/<点名>/deposit/<作业号>` 软链接。

当运行整链偏压扫描命令时：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

`work/` 下没有 `HPK-Si-PiN` 时，命令在 `examples/HPK-Si-PiN/` 下就地运行。`deposit` 环节使用示例里的 `decay/Sr90` 放射源、`device_alone` 装置和 `fano = true`，为 `100 V`（视图 `points/voltage_100/deposit`）与 `200 V`（视图 `points/voltage_200/deposit`）两个扫描点收集有效事例并写入各自的 `deposit` 节点。以单个作业收集 `200` 个有效事例写出的 `deposit.h5` 为例，文件属性（`attrs`）为 `generated_events = 7359`（Geant4 总生成事例数，单位为事例）、`recorded_events = 200`（器件内非零沉积的有效记录事例数，单位为事例）、`generated_fraction = 0.017037086855465844`（`Sr90` 的 `15` 度发射半锥角对应立体角占比，无量纲）、`require = "any"`（槽位逻辑式，各槽位能量窗属性 `edep_min.<槽位>`、`edep_max.<槽位>` 与时间窗属性 `coincidence_window_ns` 只在设置对应值时写出），数据集（`datasets`）结构与示例形状如下：

| 数据集名 | 示例形状 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | 无 | 记录事例的 Geant4 编号 |
| `count` | `(200,)` | `int64` | 步 | 每个记录事例包含的沉积步数 |
| `detector` | `(5476,)` | `object`（变长字符串） | 无 | 沉积步所在探测器逻辑体名 |
| `x`, `y`, `z` | `(5476,)` | `float64` | `μm` | 沉积步中点局部坐标（`cflm` 下为起点坐标） |
| `x_start`, `y_start`, `z_start` | `(5476,)` | `float64` | `μm` | 沉积步起点局部坐标（可选列） |
| `t` | `(5476,)` | `float64` | `s` | 沉积步全局时间 |
| `e` | `(5476,)` | `float64` | `MeV` | 沉积能量 |
| `pairs` | `(5476,)` | `float64` | 对 | 转化的电子-空穴对数 |

这里的 `5476` 是 `200` 个记录事例的 `count` 之和，`x`、`y`、`z` 等按沉积步平铺存放，`current` 环节按 `count` 把它们重新切回逐个事例的沉积步列表，并把 `pairs` 交给载流子漂移计算。

### 按记录事例或生成事例运行与零事例提前结束

单个作业在 `deposit.events_per_job` 与 `deposit.generated_per_job` 之间二选一。使用 `deposit.events_per_job` 时，粒子源持续生成事例，直到满足记录条件（各槽位有源层内总沉积能量非零且落在各自能量窗内、通过 `deposit.require` 与 `deposit.coincidence_window_ns` 判选）的记录事例数达到目标值（最多生成 `deposit.generated_limit` 个源事例）；使用 `deposit.generated_per_job` 时，粒子源固定生成指定数目的源事例后停止，实际记录的有效事例数可少于该值甚至为 `0`。

当单个作业录得的有效事例数为 `0`（例如用 `deposit.generated_per_job` 生成少量事例且无一击中器件或落入能量窗）时，`deposit` 环节仍会在节点内写出记录了 `generated_events` 的 `deposit.h5`，随后抛出 `Ended` 提前结束本作业。生命周期捕获该异常后记录该次提前结束状态，下游环节随之跳过对该作业的计算。

### Geant4 装置与径迹可视化（`-g4_vis`）

命令行开启 `-g4_vis` 时，作业进入 Geant4 可视化模式。程序取 `deposit.events_per_job` 或 `deposit.generated_per_job` 的数值作为生成事例数，按 `--g4-vis-driver` 打开交互窗口或将装置与径迹导出为 PNG 图像，关窗或导图完成后立即以 `SystemExit` 退出。

在无图形界面的终端上检查 Geant4 装置和径迹时，用短别名 `raser dep` 配合离屏驱动：

```bash
raser dep examples/HPK-Si-PiN/signal --set deposit.events_per_job=5 -g4_vis --g4-vis-driver TSG_OFFSCREEN
```

命令生成 `5` 个事例并把几何与径迹导出为当前运行目录下的 `g4_geometry.png`，随后退出；在本地有图形界面时去掉 `--g4-vis-driver TSG_OFFSCREEN`，即用默认的 `TSG_QT_GLES` 打开可交互旋转的 Qt 窗口。

## 规则

### 内置常数与链配置常量

下表列出 `src/raser/stages/deposit.py`、`src/raser/stages/chain.py` 与 `src/raser/stages/stage_commands.py` 中同 `deposit` 环节相关的全部内置常数与模块级配置常量：

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `DEPOSIT_KEYS` | `("source", "g4setup", "events_per_job", "generated_per_job", "generated_limit", "edep_min", "edep_max", "require", "coincidence_window_ns", "fano", "plots")` | 无 | `stages/chain.py`，归属 `deposit` 环节计算节点指纹的设置键元组（另含按槽位覆盖的 `<槽位>.edep_min`、`<槽位>.edep_max`） |
| `COMPONENTS` | `{"source": "deposit", "g4setup": "deposit"}` | 无 | `stages/chain.py`，标准仿真链中 `deposit` 环节加载的设置键到组件目录（`components/deposit/`）的映射 |
| `READERS` | `{"g4setup": read_g4setup}` | 无 | `stages/chain.py`，非 JSON 组件类别的自定义读取器映射 |
| `STAGES["deposit"]` | `("dep", "the energy deposited by the source", (chain.deposit_arguments,))` | 无 | `stages/stage_commands.py`，`raser deposit` 子命令的短别名、帮助说明与命令行选项挂载函数元组 |

### 环节命令目标解析与调度（`stage_commands.py`）

执行 `raser deposit [路径]`（或 `raser dep [路径]`）时，`stage_commands.run("deposit", kwargs)` 按以下步骤执行：

1. **解析目标路径（`_experiment(target)`）**：
   - 不给路径时取当前文件夹；给定 `<target>` 时令 `folder = Path(target).expanduser()`、`config = folder / "config.json"`。
   - 若 `config.is_file()` 为真，读取 JSON 为 `record`，返回 `(folder.resolve(), record["workflow"].split(), record.get("device"))`。
2. **校验目标实验类是否包含 `deposit` 环节**：
   - 查找目标实验对应的实验类（每个测试或应用是继承 `raser` 实验基类的 Python 类，类内写明它由哪些环节组成），收集该实验包含的环节名列表 `names`。
   - 判断 `"deposit"` 是否属于 `{name.split(".")[0] for name in names}`。若不属于（即目标实验类不含 `deposit` 环节），抛出 `SystemExit`：
     ```text
     <folder>: the experiment <workflow> has no deposit slice; its slices: <names>
     ```
     原因是该实验不包含 `deposit` 环节；改用报错末尾列出的环节名或运行原实验命令即可。
3. **构造运行选项并展开集群目标路径**：
   - 计算工程根目录 `project = folder.parents[len(words) - 1]`。
   - 构造字典 `options = {**kwargs, "det_name": device, "until": "deposit", "_entry_command_prefix": (words[0],)}`。
   - 若 `(folder / "config.json").is_file()` 为真，取 `argv = kwargs.get("_argv") or []`，将其中等于 `kwargs["target"]` 的参数词替换为 `str(folder)` 写入 `options["_argv"]`。
4. **切入工程上下文与实验目录运行**：
   - 保存当前目录 `here = os.getcwd()`，进入 `project_root_context(project, kwargs["_components_of"][words[0]])`。
   - 若 `folder.is_dir()` 为真，执行 `os.chdir(folder)`；调用 `execute(workflow, options)` 启动生命周期，并在 `finally` 块中执行 `os.chdir(here)` 恢复原工作目录。

### 仿真链中 `deposit` 环节的组装与辅助回调（`chain.py`）

1. **接入八环节仿真链与运行入口（`_deposits`）**：
   - 八环节仿真链依次为 `field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis`。`deposit` 无上游环节，读取 `DEPOSIT_KEYS` 设置项及 `"source"`、`"g4setup"` 组件定义，并作为测量环节将随机种子纳入节点指纹。
   - 默认运行回调 `_deposits(kwargs)` 在环节执行时执行 `from . import deposit` 并调用 `deposit.deposits(kwargs)`（`cflm` 等自定义沉积的实验传入自己的 `deposit` 函数，环节名仍为 `"deposit"`）。
2. **加载 `g4setup` 脚本快照（`read_g4setup(selector)`）**：
   - 主命令准备 `files["g4setup"]` 组件快照并记入节点输入时调用 `READERS["g4setup"]`（即 `read_g4setup`）。
   - 若 `selector` 是以 `.json` 结尾的显式路径，或在遍历 `component_roots()` 查找 `deposit/<selector>.py` 时在首个命中根目录发现 `deposit/<selector>.json` 文件，抛出 `ValueError`：
     ```text
     ValueError: <stale>: a g4setup is a script now; write it as <name>.py with its keys in G4SETUP
     ```
     原因是 Geant4 装置已改为 Python 脚本；需将其改写为导出 `G4SETUP` 字典的 `.py` 文件，并移除同目录的 `.json` 文件。
   - 校验通过后，读取 `.py` 文件字节流并计算 SHA-256 哈希，在独立模块命名空间执行后返回 `{**module.G4SETUP, "file": str(selector), "sha256": module.SHA256}`。
3. **转发单作业可视化参数（`job_command(kwargs)`）**：
   - 若 `kwargs.get("g4_vis")` 为真，返回 `["-g4_vis", "--g4-vis-driver", kwargs["g4_vis_driver"]]` 追加到单作业命令；否则返回 `[]`。

### 单作业 `deposit` 环节执行流程（`deposit.py`）

进入单个作业的 `deposit` 环节时，生命周期已将该测量环节的随机种子（取值位于 $[1, 2^{31}-1]$；启用 `--same-seeds` 时各扫描点的同编号作业共用随机种子）写入 `kwargs["seed"]`（配置分段、扫描展开与随机种子规则见 [实验、扫描点与种子](../lifecycle/experiments.md)）。每个节点单独加锁，写到一半的节点带 `.part` 后缀，写完才改为正式节点名 `nodes/deposit/<节点号>/`。`deposits(kwargs)` 按以下严格顺序执行：

1. **构造器件模型并读取事例数选项**：
   - 取 `files = kwargs["_files"]`，调用 `my_d = bdv.Detector(kwargs["det_name"], files["device"])` 构造器件对象。
   - 读取 `events = kwargs.get("events_per_job")` 与 `generated = kwargs.get("generated_per_job")`。
2. **校验记录事例数与生成事例数二选一**：
   - 若 `(events is None) == (generated is None)` 为真（两者同时为 `None` 或同时非 `None`），立即抛出 `ValueError`：
     ```text
     ValueError: events_per_job (<events>) and generated_per_job (<generated>): a job records a number of events or generates one, so exactly one of them is set
     ```
     原因是单个作业只能指定目标记录事例数或指定生成事例数之一（例如手动修改了 `config.json` 的 `deposit` 段导致两者同时为空或同时非空）；在配置或命令中仅设置其一即可。
   - 读取 `limit = kwargs.get("generated_limit")`。
3. **分流 `-g4_vis` 可视化模式**：
   - 若 `kwargs.get("g4_vis")` 为真：
     - 取驱动名 `driver = kwargs["g4_vis_driver"]`，令 `picture = None`。
     - 若 `driver.upper() in ("TSG", "TSG_FILE", "TSG_OFFSCREEN")`，令 `picture = os.path.join(kwargs["_run_path"], "g4_geometry")`。
     - 调用 `view_geometry(my_d, files["source"], files.get("g4setup"), int(events if generated is None else generated), kwargs["seed"], driver, picture)`。
     - `view_geometry` 返回后立即执行 `raise SystemExit`，终止当前作业进程。
4. **准备常规运行径迹图路径与绘制事例数（`_picture(kwargs)`）**：
   - 若 `kwargs.get("g4_vis")` 为假，调用 `_picture(kwargs)`：计算 `drawn = int(kwargs.get("plots") or 0)`。
   - 若 `not drawn`（即 `drawn == 0`），返回 `(None, 0)`。
   - 若 `drawn != 0`，在本环节节点输出目录 `nodes/deposit/<节点号>/` 下准备图像输出路径 `g4_geometry`，返回该路径与 `drawn`。
5. **调用 `write_simulated_deposits` 模拟并落盘**：
   - 调用 `output(kwargs, "deposit")` 取得本环节节点目录 `nodes/deposit/<节点号>/` 下的 `deposit.h5` 输出路径。
   - 按各槽位构造 `windows`（每个槽位默认取 `(deposit.edep_min, deposit.edep_max)`，若给了 `deposit.<槽位>.edep_min` 或 `deposit.<槽位>.edep_max` 则覆盖对应一侧），读取 `require = kwargs["require"]` 与 `coincidence_window_ns = kwargs.get("coincidence_window_ns")`。
   - 调用 `recorded = write_simulated_deposits(output(kwargs, "deposit"), devices, files["source"], files.get("g4setup"), None if events is None else int(events), kwargs["seed"], windows, require, coincidence_window_ns, kwargs["fano"], None if generated is None else int(generated), GENERATED_LIMIT if limit is None else int(limit), *_picture(kwargs))`（单器件时 `devices` 为 `{"Device": my_d}`）。
   - `write_simulated_deposits` 按 `files["source"]["kind"]` 执行 Geant4 输运（`"beam"`、`"decay_source"`）或直线最小电离粒子计算（`"toy_mip"`），按 `windows`、`require` 与 `coincidence_window_ns` 筛选有效事例并调用 `ionized_pairs` 转化为电子-空穴对，将结果写入 `deposit.h5`，返回记录事例数 `recorded`。
6. **判定记录事例数并完成节点落盘**：
   - 若 `not recorded`（即 `recorded == 0`），执行 `raise Ended`。生命周期捕获 `Ended` 后记录提前结束状态，并跳过本作业后续所有环节。
   - 若 `recorded > 0`，`deposits(kwargs)` 返回 `None`，生命周期将写完的 `.part` 节点改为正式节点目录 `nodes/deposit/<节点号>/`（内含 `node.json`），并更新 `points.json` 与视图软链接 `points/<点名>/deposit/<作业号>`。

## 软件实现

### 源文件分工

- `src/raser/stages/deposit.py`：实现 `deposit` 环节的作业执行函数 `deposits(kwargs)` 与常规运行径迹图路径计算函数 `_picture(kwargs)`，完成 `Detector` 构造、事例数互斥检查、`-g4_vis` 可视化分流、`write_simulated_deposits` 调用与零事例 `Ended` 抛出。
- `src/raser/stages/chain.py`：定义 `DEPOSIT_KEYS`、`COMPONENTS`、`READERS`、可视化命令行开关挂载函数 `deposit_arguments(parser)`、可视化参数转发函数 `job_command(kwargs)` 与延迟导入函数 `_deposits(kwargs)`，将 `"deposit"` 组装进仿真链。
- `src/raser/stages/stage_commands.py`：在 `STAGES["deposit"]` 中注册 `raser deposit`（短命令 `dep`），通过 `_experiment(target)` 解析实验文件夹，在 `run("deposit", kwargs)` 中校验目标实验是否包含 `deposit` 环节并以 `until="deposit"` 调用生命周期 `execute`。
- `src/raser/stages/files.py`：实现 `_job(kwargs)` 与 `output(kwargs, name)`，返回 `deposit` 环节节点内 `deposit.h5` 的输出路径。

### 核心数据结构

| 数据结构 | 字段名 | 类型或固定值 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `files["g4setup"]`（`read_g4setup` 返回值） | `G4SETUP` 各键 | `dict` | `μm`、度、`g/cm^3` | 装置脚本导出的 `G4SETUP` 字典项（含 `maxstep`、`along_beam`、`object` 等） |
| `files["g4setup"]`（`read_g4setup` 返回值） | `"file"` | `str` | 无 | 传入的 `deposit.g4setup` 组件名称或 `.py` 文件路径 |
| `files["g4setup"]`（`read_g4setup` 返回值） | `"sha256"` | `str` | 无 | 装置脚本文件字节流的 64 位十六进制 SHA-256 摘要 |
| `kwargs`（`deposits` 入参字典） | `"det_name"` | `str` | 无 | 探测器名称，传给 `Detector(det_name, files["device"])` |
| `kwargs`（`deposits` 入参字典） | `"_files"` | `dict` | 无 | 组件快照字典，含 `"device"`、`"source"` 及可选 `"g4setup"` |
| `kwargs`（`deposits` 入参字典） | `"seed"` | `int` | 无 | 生命周期为本环节派生的随机种子（$[1, 2^{31}-1]$） |
| `kwargs`（`deposits` 入参字典） | `"job_index"` | `int \| None` | 无 | 当前作业号（从 `0` 起，缺省或 `None` 时 `_job` 取 `0`） |
| `kwargs`（`deposits` 入参字典） | `"_run_path"` | `str` | 无 | 当前运行目录路径（`-g4_vis` 离屏模式下写出 `g4_geometry.png` 的目录） |
| `kwargs`（`deposits` 入参字典） | `DEPOSIT_KEYS` 各键及 `<槽位>.edep_min`、`<槽位>.edep_max` | `str \| int \| float \| bool \| None` | 事例、`MeV`、`ns` | `config.json` 中 `deposit` 段与命令行合并后的本环节设置值（见下节接口表） |
| `kwargs`（`deposits` 入参字典） | `"g4_vis"`, `"g4_vis_driver"` | `bool`, `str` | 无 | 当次运行的可视化开关与 Geant4 驱动名 |

## 接口

### 命令行选项与配置键

使用者在本环节能设的只有下表列出的参数、命令行选项与 `config.json` 中 `deposit` 段的配置键（共用运行参数 `-s`、`--seed`、`--same-seeds`、`-b`、`-t`、`-mem`、`--dry-run`、`--scan`、`--set` 见 [命令行接口（`raser`）](../cli.md) 和 [实验、扫描点与种子](../lifecycle/experiments.md)）。`--set` 与 `--scan` 使用“段.键”作地址（如 `--set deposit.events_per_job=200`、`--scan deposit.source=decay/Sr90,bunch`）。表外参数（如环节名 `"deposit"`、常规运行离屏驱动 `TSG_OFFSCREEN`、节点路径与图像文件名 `g4_geometry.png`）都写死在代码里。除 `-g4_vis` 和 `--g4-vis-driver` 仅用于当次运行外，其余设置均来自 `config.json` 的 `deposit` 段并计入 `deposit` 节点的指纹与 `node.json`。改其中任何一个，包括 `deposit.plots`，`deposit` 及全部下游都算成新节点。表里配置键的“示例里的值”是 `examples/HPK-Si-PiN/signal/config.json` 写的值，括号里是别的示例写的不同值；这些键（含 `deposit.require`、`deposit.coincidence_window_ns`、`deposit.edep_min`、`deposit.edep_max`）都要在 `config.json` 里写出，缺键报错并指出缺的“段.键”（按槽位覆盖的 `deposit.<槽位>.edep_min`、`deposit.<槽位>.edep_max` 未写时沿用不带槽位的值）。命令行选项一行写的是不给这个选项时的取值。

| 段.键或命令行选项 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `[路径]`（仅 `raser deposit` / `dep` 位置参数） | 当前文件夹 | 无 | 含 `config.json` 的实验文件夹路径（不给路径时为当前文件夹） |
| `deposit.source` | `"decay/Sr90"`（`bmos` 示例为 `"bunch"`） | 无 | 粒子源或束流组件名称（在组件目录 `deposit/` 下查找 `<名称>.json`，见[能量沉积组件（`components/deposit`）](../components/deposit.md)）或 JSON 文件路径，支持 `"beam"`、`"decay_source"` 和 `"toy_mip"` |
| `deposit.g4setup` | `"device_alone"`（`timeres` 示例为 `"time_resolution"`） | 无 | Geant4 装置脚本名称（在组件目录 `deposit/` 下查找 `<名称>.py`，见[能量沉积组件（`components/deposit`）](../components/deposit.md)）或 `.py` 文件路径，决定沿束流排布的源、槽位与周围物体（`along_beam`）、最大步长 `maxstep`（`μm`）以及源的入射倾角 |
| `deposit.events_per_job` | `200`（`timeres` 示例为 `10000`，`telescope` 示例为 `1000`） | 事例 | 每个作业需记录的有效沉积事例数（不小于 `1` 的整数）；粒子源持续生成事例直到器件内录满该数目（受 `deposit.generated_limit` 约束），与 `deposit.generated_per_job` 互斥 |
| `deposit.generated_per_job` | `null`（不用） | 事例 | 每个作业由粒子源生成的总事例数（不小于 `1` 的整数），用于替代 `deposit.events_per_job`；粒子源固定生成该数目后停止，器件内实际记录的有效事例数可少于该值甚至为 `0` |
| `deposit.generated_limit` | `10000000` | 事例 | 使用 `deposit.events_per_job` 时，为凑够目标记录事例数允许单个作业最多生成的源事例数上限（不小于 `1` 的整数） |
| `deposit.edep_min` | `null`（不设下限） | `MeV` | 不带槽位时对所有槽位生效的最小总沉积能量下限（`null` 表示不检查）；槽位有源层内总沉积须大于 `0` 且不低于该值才算命中 |
| `deposit.edep_max` | `null`（不设上限） | `MeV` | 不带槽位时对所有槽位生效的最大总沉积能量上限（`null` 表示不检查）；槽位有源层内总沉积须不高于该值才算命中 |
| `deposit.<槽位>.edep_min` | 不写（沿用 `deposit.edep_min`） | `MeV` | 给指定槽位单独设置的最小总沉积能量下限，覆盖不带槽位的 `deposit.edep_min`；`null` 表示该槽位不检查下限 |
| `deposit.<槽位>.edep_max` | 不写（沿用 `deposit.edep_max`） | `MeV` | 给指定槽位单独设置的最大总沉积能量上限，覆盖不带槽位的 `deposit.edep_max`；`null` 表示该槽位不检查上限 |
| `deposit.require` | `"any"` | 无 | 记录事例的槽位逻辑式，以槽位名为操作数，运算为 `AND`、`OR` 与括号（`AND` 比 `OR` 结合得紧），`"any"`、`"all"` 分别为全部槽位相或、相与的简写；`timeres` 下设成 `"ref AND dut"` 可省下游计算但失去比较其他触发条件的事例，见[能量沉积与电离（`core/deposit`）](../core/deposit.md#多器件的记录条件) |
| `deposit.coincidence_window_ns` | `null`（不卡时间） | `ns` | 时间窗宽度（正数，`null` 表示不卡时间）；仅将命中时刻落在同一长度为该值的区间 $[t_0, t_0 + W]$ 内的槽位算作命中时 `deposit.require` 为真才记录 |
| `deposit.fano` | `true` | 无 | 控制电离电子-空穴对数是否开启 Fano 涨落抽样，取 `true` 或 `false`（`false` 时直接取平均电离对数） |
| `deposit.plots` | `100`（`timeres`、`bmos`、`cflm` 示例为 `0`） | 事例 | 每个作业画 `deposit` 自己的图：大于 `0` 时，Geant4 源在常规运行里离屏绘制几何和前 `N` 个记录事例的径迹（`g4_geometry.png`）；`0` 表示不画。`current` 的图由 `current.plots` 管，见[载流子输运与感应电流环节（`stages/current`）](current.md) |
| `-g4_vis` | `False` | 无 | 仅用于当次运行的命令行布尔开关；开启后只做 Geant4 几何与径迹可视化，传入的事例数取 `deposit.events_per_job` 或 `deposit.generated_per_job` 的值并按生成事例运行，完成后退出作业 |
| `--g4-vis-driver` | `"TSG_QT_GLES"` | 无 | 仅用于当次运行、配合 `-g4_vis` 使用的 Geant4 可视化驱动名；驱动名为 `"TSG"`、`"TSG_FILE"` 或 `"TSG_OFFSCREEN"`（不区分大小写）时直接导出 PNG 图像后退出，`"TSG_QT_GLES"`、`"OGL"` 等带窗口驱动打开可拖动旋转的交互窗口，关窗后退出 |

各选项在配置或运行出错时触发的终端报错如下：

- **`deposit.source` 的 `"kind"` 不受支持**：
  ```text
  ValueError: no simulation of deposits for a source of kind '<kind>'; known: ['toy_mip', 'beam', 'decay_source']
  ```
  原因是源 JSON 中的 `"kind"` 字段不在上述三类支持范围内；检查组件文件里的 `"kind"` 字段并改为合法值即可。
- **`deposit.g4setup` 指向或命中了旧版 `.json` 文件**：
  ```text
  ValueError: <stale>: a g4setup is a script now; write it as <name>.py with its keys in G4SETUP
  ```
  原因是装置定义已改为 Python 脚本；需将其改写为导出 `G4SETUP` 字典的 `.py` 文件，并移除同目录残留的 `.json` 文件。
- **`deposit.events_per_job` 与 `deposit.generated_per_job` 冲突或取值越界**：
  - 运行时两者同时为空或同时非空（例如手动修改了配置文件）：
    ```text
    ValueError: events_per_job (<events>) and generated_per_job (<generated>): a job records a number of events or generates one, so exactly one of them is set
    ```
    需在配置或命令中仅设置其中一个。
  - 取值小于 `1`：
    ```text
    ValueError: the recorded events asked for are <number>: at least 1
    ValueError: the generated events asked for are <number>: at least 1
    ```
    将 `deposit.events_per_job` 或 `deposit.generated_per_job` 改为不小于 `1` 的正整数即可。
- **`deposit.generated_limit` 达到上限仍未录满 `deposit.events_per_job` 或取值越界**：
  - 生成事例数达到上限仍未录满目标记录事例数：
    ```text
    RuntimeError: <recorded> of the <events> events asked for were recorded when the limit of <generated> generated events was reached: <ratio> of the generated events are recorded. Ask for fewer events, or raise generated_limit
    ```
    原因是记录率过低（如放射源立体角小、器件薄、能量窗过窄或记录条件苛刻）；可减小 `deposit.events_per_job`、放宽 `deposit.edep_min`/`deposit.edep_max`（或各槽位能量窗）、放宽 `deposit.require` / `deposit.coincidence_window_ns` 或调大 `deposit.generated_limit`。
  - 取值小于 `1`：
    ```text
    ValueError: the generated_limit asked for are <number>: at least 1
    ```
    将 `deposit.generated_limit` 改为不小于 `1` 的正整数即可。
- **`config.json` 缺少必填设置键或记录条件设置非法**：
  - `config.json` 缺少 `deposit` 段中要用的键（如 `deposit.require`、`deposit.coincidence_window_ns`、`deposit.edep_min`、`deposit.edep_max` 等）时抛 `ValueError`，报错指出缺少的“段.键”（如 `<config_path> has no deposit.require`）。
  - 某槽位能量窗下限大于上限、`deposit.require` 语法错误、出现非槽位名操作数或有槽位没用到、`deposit.coincidence_window_ns` 非正数时抛 `ValueError`，报错格式见 [能量沉积与电离（`core/deposit`）](../core/deposit.md#simulate_deposits-的分支)。
- **`--g4-vis-driver` 驱动不受当前环境支持或缺少图形会话**：
  ```text
  RuntimeError: Geant4 refused the command '<text>' (status <status>)
  ```
  原因是当前环境未编译该驱动，或在无显示器的集群节点上使用了默认窗口驱动 `TSG_QT_GLES`；改用 `--g4-vis-driver TSG_OFFSCREEN` 离屏出图即可。

### 读写的文件

除 `-g4_vis` 离屏导图落在当前运行目录下外，`deposit` 环节的产出均存放在实验目录的节点文件夹 `nodes/deposit/<节点号>/` 内，并由视图软链接 `points/<点名>/deposit/<作业号>` 指向对应节点。每个节点单独加锁，写到一半的节点带 `.part` 后缀，写完才改成正式名字。

- **`config.json` 的 `deposit` 段与组件定义 `files["device"]`、`files["source"]`、`files["g4setup"]`（输入，用到的部分记入 `nodes/deposit/<节点号>/node.json`）**：生命周期读取 `config.json` 中 `deposit` 段的设置值、器件 JSON、源 JSON 与 `read_g4setup` 返回的装置快照，取本环节用到的部分连同测量环节随机种子算出指纹（即 `<节点号>`）；`deposit` 环节从 `kwargs["_files"]` 读取器件、源与装置快照。其中 `files["g4setup"]` 同时记录脚本导出的 `G4SETUP` 与脚本文件的 `"sha256"` 摘要，修改脚本内容会改变节点指纹并生成新节点。
- **`nodes/deposit/<节点号>/deposit.h5`（输出，写它的环节：`deposit`）**：由 `deposit` 环节在常规模式下调用 `write_simulated_deposits` 写出（录得 `0` 个事例时也写出），文件里只有通过记录条件的事例（被记录的事例保留所有槽位的沉积步），通过视图软链接 `points/<点名>/deposit/<作业号>` 供下游 [载流子输运与感应电流环节（`stages/current`）](current.md) 与 [统计分析环节（`stages/analysis`）](analysis.md) 读取。文件为 HDF5 格式：属性包含 `generated_events`（`int`，单位：事例）、`recorded_events`（`int`，单位：事例）、`generated_fraction`（`float`，无量纲）、`require`（`str`，无量纲）、设置了对应槽位能量窗时的 `edep_min.<槽位>`、`edep_max.<槽位>`（`float`，单位：`MeV`）以及设置了时间窗时的 `coincidence_window_ns`（`float`，单位：`ns`）；数据集包含形状为 `(recorded_events,)` 的 `event`（`int64`，无量纲）和 `count`（`int64`，单位：步），以及形状为 `(sum(count),)` 的 `detector`（变长 `str`，无量纲，单器件写 `"Device"`，多器件写槽位名）、`x`/`y`/`z`（`float64`，单位：`μm`，标准 Geant4 为步中点局部坐标，`cflm` 为步起点局部坐标）、`t`（`float64`，单位：`s`）、`e`（`float64`，单位：`MeV`）、`pairs`（`float64`，单位：对），当所有记录事例均含步起点或产生时间展宽时另写出形状为 `(sum(count),)` 的可选数据集 `x_start`/`y_start`/`z_start`（`float64`，单位：`μm`）与 `t_fwhm`（`float64`，单位：`s`）。该文件的底层读写函数 `write_deposits` / `read_deposits` 规范见 [能量沉积与电离（`core/deposit`）](../core/deposit.md)。
- **`nodes/deposit/<节点号>/node.json`、`points.json` 与 `points/<点名>/deposit/<作业号>`（节点记录、参数表与视图软链接，写它的模块：生命周期框架）**：`node.json` 把生成该节点的输入（本环节用到的设置值、组件文件里用到的部分、上游节点号、随机种子，指纹由它们算出）原样记下，并另记代码版本、运行环境和运行状态。实验根目录下的 `points.json` 按行记录各扫描点的扫描轴取值以及 `deposit` 等各环节使用的节点号；`points/<点名>/deposit/<作业号>` 为指向 `../../../nodes/deposit/<节点号>` 的软链接。
- **`nodes/deposit/<节点号>/g4_geometry.png`（输出图像，写它的环节：`deposit`）**：在常规 Geant4 运行期间（未开启 `-g4_vis`、`deposit.plots` 大于 `0` 且 `source["kind"]` 为 `"beam"` 或 `"decay_source"`）由 `deposit` 环节用离屏驱动 `TSG_OFFSCREEN` 写出，存放在该环节自己的节点输出里，内容为器件、周围装置和前 `deposit.plots` 个记录事例径迹的 PNG 视图。
- **当前运行目录下的 `g4_geometry.png`（可视化输出图像，写它的环节：`deposit`）**：在开启 `-g4_vis` 且 `--g4-vis-driver` 为 `"TSG"`、`"TSG_FILE"` 或 `"TSG_OFFSCREEN"`（不区分大小写）时写出，位于 `kwargs["_run_path"]` 根目录下，内容为 Geant4 装置几何与指定数目生成事例径迹的离屏 PNG 视图。
