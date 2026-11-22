# 场求解环节（`stages/field`）

本环节由命令 `raser field [路径]`（短别名 `raser fld`，详见[命令行接口（`raser`）](../cli.md)）驱动，也在[仿真链与环节入口（`stages`）](README.md)的八环节仿真链（`field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis`）中与[能量沉积环节（`stages/deposit`）](deposit.md)同处最前端。本环节调度 DEVSIM 求解（或从 Sentaurus TDR 文件导入）器件在给定偏压与辐照注量下的电势、电场、载流子浓度、俘获率、导电区标志、读出电极权重场、IV/CV/噪声曲线，以及标上数值的器件参数电路图（结电容、耦合电容、未耗尽层），也支持通过 `raser field --draw <对象>` 绘制网格和网格节点上的掺杂。算出的场作为器件资产，按输入指纹存放在各实验共用的场节点 `work/<器件>/field/<节点号>/`（就地运行示例时为 `examples/<器件>/field/<节点号>/`）下，由实验的 `points.json` 参数表记录节点号并通过 `points/<点名>/field` 软链接视图引用（结果布局见[架构总纲](../architecture.md#结果)）。它向[载流子输运与感应电流环节（`stages/current`）](current.md)交付电场、权重场、导电区与俘获率以漂移载流子，向[电子学读出环节（`stages/readout`）](readout.md)交付器件参数电路图及结电容、条间互容和未耗尽层参数以组装器件等效电路；场节点号变化时，上述下游环节以及[数字化环节（`stages/digitizer`）](digitizer.md)、[触发环节（`stages/trigger`）](trigger.md)、[事件重建环节（`stages/reconstruction`）](reconstruction.md)和[统计分析环节（`stages/analysis`）](analysis.md)随之算出新节点。

## 行为

### 独立求解、导入、绘图与按实验补算

独立运行 `raser field [路径]`（或 `raser fld [路径]`）时，不给路径即取当前文件夹，给出时取相对或绝对路径。传入 `--draw <对象>` 时只绘制网格和网格节点上的掺杂；常规求解时根据目标路径是否属于某个实验（含实验 `config.json`）区分两类目标：

- **器件或工程路径**：按[器件模型（`core/device`）](../core/device.md)的规则查找器件定义（project 文件夹里有自己的器件文件就用自己的，只写名字时到内置[探测器组件（`components/device`）](../components/device.md)里找），在 `work/<器件>/field/<节点号>/`（或对应 project 根目录下的 `field/<节点号>/`）下求解或导入场节点。器件的几何写在器件文件里，网格属于 `field`：同一个器件可以有几套网格，用哪一套由 `field` 段的设置指定。IV 扫描、单点电容、权重场、噪声、UMFPACK 线性求解器、TCAD 导入及其坐标翻转这些求解开关也是 `field` 段的设置，用 `--set field.<键>=<值>` 改。配合 `--set` 或 `--scan` 时按“段.键”地址（如 `field.voltage`、`field.irradiation_flux`、`field.mode`）传入设置。
- **实验文件夹路径**：当目标下存在实验的 `config.json` 时，命令读取其中的实验类定义、器件与分段配置，切到该实验所属的工程根目录与组件路径，逐扫描点检查并补算尚未就绪的共享场节点。配合 `--scan` 或 `--set` 仅筛选本次命令要准备的点（实验的 `config.json` 保持原样）；配合 `--dry-run` 只打印各点共享场是 `ready` 还是 `to be made`。

如果把共享场文件夹本身作为目标传入，命令立即中止：

```text
<folder>: this is the field itself; give its device, raser field <device>
```

原因：传入的是共享场文件夹本身。改传报错末尾给出的器件名（`raser field <device>`）即可。

最小示例：用 `raser new --from HPK-Si-PiN work/my-PiN` 建好 project 后，先预览实验各扫描点的共享场是否就绪，再在已保存的 `200.0V.devsim` 上补算单点小信号电容（`--set field.<键>=<值>` 打开 `field` 段的单点电容开关）：

```bash
raser field work/my-PiN/signal --dry-run
raser field my-PiN --set field.voltage=200 --set field.<键>=<值>
```

第一条命令逐点打印 `<实验文件夹绝对路径>: field ready for <options>` 或 `to be made`。第二条命令加载 `200.0V.devsim`，写出 `200.0V.cv.json` 并把 `200.0` 记入已完成求解的 `capacitance`，同时在终端打印写入的点记录字典：

```text
{'voltage_V': 200.0, 'specific_capacitance_pF': ..., 'per': 'cm^2', 'area_factor': 0.0169, 'frequency_Hz': 1000.0}
```

### 三条求解路径与子任务

每次非 `--dry-run` 的场求解作业先核对 `field.mode`，再按 `field` 段的设置走外部 TCAD 导入、HEMT 直流输运或常规 DEVSIM 求解三条路径之一。`field.mode` 为 `"fast"` 且未安装 `devsim` 时，作业开始时先打印 `devsim is not installed: the field of <det_name> is found in the fast mode, not the full one`。当前只实现了 `"full"` 模式，`field.mode` 为 `"semi_fast"` 或 `"fast"` 时直接报错：

```text
NotImplementedError: the <mode> mode of a field is not there yet: only field.mode 'full' is
```

原因：当前只实现了 `"full"` 模式。请在已安装 DEVSIM 的环境下把 `field.mode` 设为 `"full"`。

三条求解路径的行为如下：

- **外部 TCAD 导入**：跳过 DEVSIM 偏压扫描，导入 Sentaurus TDR（HDF5）文件中的体区场与导电区，并在该网格上求解各读出电极权重电势；写盘并更新 `axes`、`read` 与 `solved` 记录后，打印 `<场目录>: the field of <TCAD_FILE> at <bias> V` 结束作业。
- **HEMT 直流输运分支**：当器件 JSON 设置 `hemt_physics.transport_model == "drift_diffusion_v1"` 时，转入独立的二维 HEMT 直流转移特性求解器，终端打印 `<det_name> is solved by its own transport solver: only its DC sweep is run, without CV, weighting field or noise`（若同时打开了单点电容、权重场或噪声开关，末尾追加 `; <开关> dropped` 并丢弃这些开关），写出 `HEMT_TRANSPORT_*` 结果后结束作业。
- **常规 DEVSIM 求解**：按固定顺序 `iv` → `cv` → `wf` 决定本次执行的子任务。启动 DEVSIM 前，作业逐项核对节点记录中的 `"solved"`（DEVSIM 从 0 V 升压到目标偏压途中的存盘点与已做的子任务）；一个场节点对应一个目标偏压，节点里存的中间偏压文件是升压途中的存盘点。目标偏压已在对应列表中的子任务直接跳过。若本次请求的全部子任务均已完成，作业打印 `<场目录>: already solved` 后结束；连续执行多个子任务时，两项之间会清空 DEVSIM 器件状态，同时保留已选定的线性求解器参数。

| `field` 段打开的子任务 | 做什么 | 核对并记录的 `solved` 键 |
| --- | --- | --- |
| 三个子任务都未打开（整套求解） | 从 `0 V` 扫到目标偏压（含沿途 CV 曲线），再求解各读出电极权重场 | `"potential"`、`"undepleted"`、`"weighting"` |
| IV 扫描 | 从 `0 V` 扫到目标偏压并绘制 IV 曲线 | `"potential"`、`"undepleted"` |
| 单点电容 | 加载已保存的 `<V>V.devsim`，在单点求解小信号电容并写出 `<V>V.cv.json` | `"capacitance"` |
| 权重场 | 读取同偏压的 `Conductive_<V>V.pkl`，求解各读出电极权重场（单晶胞条形电极另算条间互容） | `"weighting"` |

单点电容子任务若在目录中找不到对应的 `<voltage>V.devsim` 状态归档，作业报错中止：

```text
FileNotFoundError: no field saved at <voltage> V in <folder>: <have>
```

原因：单点电容依赖偏压扫描保存的 `<V>V.devsim` 归档。先用 `raser field <device> --set field.voltage=<voltage>` 做 IV 扫描或整套求解，保存该偏压后再求单点电容。

权重场子任务若找不到同偏压的导电区文件，作业报错中止：

```text
FileNotFoundError: the weighting field at <v_goal> V needs the field solved at that bias: <conductive_file> is missing; solve it with `raser field <simname> --set field.voltage=<v_goal>`
```

原因：权重场求解需要同偏压的 `Conductive_<V>V.pkl` 来合并导电区。先按提示求解该偏压的电势场，再求权重场。

### 仿真链中的共享场补算、等待与交付

在测试、应用或下游环节命令（如 `raser signal`、`raser current`、`raser readout`、`raser digitizer`、`raser trigger`、`raser reconstruction`、`raser analysis`）中，每个实验是一个继承 `raser` 实验基类的 Python 类，写明它包含的环节、器件与各器件角色。主命令在启动实验作业前，对去重后的各扫描点共享场需求逐项调用 `ready` 检查；未就绪时打印 `solving the field first: raser field <device> --set field.voltage=<V> ...`，以独立单作业进程（随主命令在本地运行或 `-b` 提交集群，已有的 `field` 配置保持原样）先行补算。

如果另一进程正在求解同一个共享场节点（节点锁冲突），主命令打印 `<环节名>: <被占用对象> is run by another process now; run the command again when it is done`，随后下游实验作业进入等待（集群 `-b` 提交共享场尚未完成时同样进入等待）：

```text
<folder>: jobs <waiting> wait for <name>, shared with other experiments; run the command again when it is done
```

原因：该扫描点依赖的共享场节点尚未就绪或正由另一进程求解。本地运行需等对方结束后重跑原命令；集群 `-b` 模式下（未走宿主机提交队列时），场作业完成后会自动重新拉起等待它的下游实验命令，作业日志与集群自动续跑见[作业、日志、锁、断点续跑与集群提交](../lifecycle/jobs.md)。

如果本地进程跑完 `raser field` 后该共享场仍判定未就绪，主命令直接报错中止：

```text
RuntimeError: field was made in this process and is still not ready for a point of <root>: waiting would not help
```

原因：刚跑完的场求解结果里缺少当前扫描点所需的偏压或资产。检查场求解日志与节点记录查明缺少什么。

共享场节点就绪后，实验把该扫描点对应的 `field` 节点号记入 `points.json`，并将视图软链接 `points/<点名>/field` 指向 `work/<器件>/field/<节点号>/`。作业执行 `field` 环节校验时再次确认该场节点就绪；若未找到满足当前偏压与辐照注量的就绪场，作业报错中止：

```text
FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>`
```

原因：共享场尚未求解、缺少该偏压的电势或权重场，或期间器件文件已变动。按提示运行 `raser field <det_name>`（必要时附带 `--set field.voltage=<值>` 或 `--set field.irradiation_flux=<值>`）或重跑原链命令补算。

最小示例：在[快速入门](../getting-started.md)的示例里，当 `HPK-Si-PiN` 的场节点尚未求解时，运行：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

主命令在启动信号作业前依次打印：

```text
solving the field first: raser field HPK-Si-PiN --set field.voltage=100.0
solving the field first: raser field HPK-Si-PiN --set field.voltage=200.0
```

程序先后启动两个单作业进程求解 `100 V` 与 `200 V` 的场，结果存放在 `HPK-Si-PiN` project 的 `field/` 下，两个目标偏压各是一个场节点：

- 场节点的 `node.json` 记下输入（`field` 环节设置值与读取的器件部分）、代码版本、运行环境与运行状态。
- 两个节点合起来写出的文件有体区场 `.pkl`（`Potential`、`Electrons`、`Holes`、`TrappingRate_n`、`TrappingRate_p`、`Conductive` 及 `NetDoping_0V.pkl`）、`0V`/`100.0V`/`200.0V` 的 `.devsim` 与 `.dd` 归档、`HPK-Si-PiN.dat`、`0.0V`/`100.0V`/`200.0V.undepleted.json`（`100.0 V` 与 `200.0 V` 均已全耗尽，`undepleted_width_um` 与 `specific_resistance_ohm_cm2` 均为 `0.0`，`specific_capacitance_pF` 为 `null`）、`weightingfield/top/Potential_100V.pkl`、`Potential_200V.pkl` 和 `plots/` 里对应的权重场图，以及标上结电容、耦合电容与未耗尽层数值的器件参数电路图资产。
- 曲线数据为 `simIV0to100.0.root`、`simIV0to200.0.root`、`simCV0to100.0.root`、`simCV0to200.0.root`；一维分布图都在 `plots/` 里，各有 `.png` 与 `.pdf`：`iv`、`cv`、`doping`，以及 `electric_field_0V`、`electric_field_100V`、`electric_field_200V`、`potential_0V`、`potential_100V`、`potential_200V`、`weighting_potential_top_100V`、`weighting_potential_top_200V`、`weighting_field_top_100V`、`weighting_field_top_200V`（未加辐照，不画俘获率图）。
- 实验在 `points.json` 中为 `voltage_100` 和 `voltage_200` 两个扫描点记下各自的 `field` 节点号，并将 `points/voltage_100/field`、`points/voltage_200/field` 软链接指向对应的场节点（可用 `raser status` 查看参数表中各点各环节的状态和节点号）。

![HPK-Si-PiN IV 曲线](../../images/field/iv-HPK-Si-PiN.png)

`HPK-Si-PiN` 反向偏压扫描得到的暗电流（IV）曲线。

![HPK-Si-PiN CV 曲线](../../images/field/cv-HPK-Si-PiN.png)

`HPK-Si-PiN` 电容随反向偏压变化的 CV 曲线。

![HPK-Si-PiN 200 V 一维电场分布](../../images/field/efield-HPK-Si-PiN-200V.png)

`200 V` 偏压下 `HPK-Si-PiN` 沿深度方向的一维电场分布。

### 节点指纹复用、过期提示与下游联动

场节点的身份由它的输入指纹决定（详见[片与重跑](../lifecycle/slices.md)与[架构总纲](../architecture.md#节点)）：

- **输入指纹与只增不减**：`field` 节点的输入包括本环节用到的设置值（偏压、辐照注量、场模式、所选网格及其文件的 SHA-256、UMFPACK 线性求解器开关、TCAD 导入文件的 SHA-256 等）和器件组件文件里 `field` 用到的那一部分（含器件 `"field"` 段及求解期间经 `Reading` 读取的器件属性与 JSON 键）；`field` 的指纹只由这两部分输入算出。偏压在指纹里，每个偏压是一个场节点：补算一个新偏压就多一个节点，已有偏压的节点和读它们的实验照常复用。对这些输入取指纹，指纹就是节点号。指纹相同就复用已有场节点，不论它是在哪个点、哪次运行里算出来的。节点只增不减：修改设置后算出新节点，旧节点保留；把设置改回去，`points.json` 和 `points/<点名>/field` 视图重新指回旧节点。
- **单节点加锁与 `.part` 后缀**：每个节点单独加锁。写到一半的场节点带 `.part` 后缀，写完才改成正式节点名，正式节点名下总是完整的结果。
- **代码版本不一致只提示**：代码版本、运行环境和运行状态另记在 `node.json` 里，指纹只取输入。当前代码版本和 `node.json` 记录的不一致时，只给一条提示，已有场节点照常复用。
- **下游环节联动**：下游环节把上游各节点的节点号纳入自己的输入指纹。当 `field` 节点因输入改变而切换为新节点号时，依赖它的 `current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 指纹随之改变并算出新节点；`deposit` 节点只取自己的输入，照常复用。

## 规则

### 内置常数

下表列出 `src/raser/stages/field/__init__.py`、`src/raser/core/field/` 与 `src/raser/lifecycle/workflow.py` 中与场环节相关的内置常数与写死阈值：

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `HAS_DEVSIM` | `importlib.util.find_spec("devsim") is not None` | 无 | `core/field/solved.py`（`stages/field/__init__.py` 导入）；当前环境是否安装 `devsim` |
| `DEFAULT_MODE` | `HAS_DEVSIM` 为真时 `"full"`，否则 `"fast"` | 无 | `core/field/solved.py`（`stages/field/__init__.py` 导入）；`ready` 调 `solved_field` 查找共享场时用的模式 |
| 无辐照回退注量 | `0` | $\text{cm}^{-2}$ | `core/device/build_device.py`、`core/field/solved.py`；器件 JSON 无 `"irradiation"` 段时的默认注量 |
| `per` 维度映射 | `{1: "cm^2", 2: "cm", 3: "device"}` | 无 | `stages/field/__init__.py` `_capacitance`；按 `my_d.dimension` 写入 `<voltage>V.cv.json` 的比电容归一化基准 |
| 缺省 `area_factor` | `1.0` | 1D $\text{cm}^2$，2D $\text{cm}$，3D 无量纲 | `stages/field/__init__.py` `_capacitance`；器件 JSON 未给出 `area_factor` 时的默认换算因子 |
| DEVSIM 保留参数 | `("direct_solver", "solver_callback")` | 无 | `stages/field/__init__.py` `_empty_devsim`；调用 `devsim.reset_devsim()` 前后保留的全局参数名 |
| `_STARTS` | `4` | 次 | `lifecycle/workflow.py` `_run_again`；集群作业完成后重新拉起等待命令的最大尝试次数 |
| `_PAUSE` | `30` | $\text{s}$ | `lifecycle/workflow.py` `_run_again`；集群重试拉起等待命令的间隔时间 |
| `_WAITING_DEPTH` | `8` | 层 | `lifecycle/workflow.py` `_start_again`；集群作业链式拉起等待命令的最大递归深度（`RASER_RESUBMIT_DEPTH`） |

### 入口路由与目标解析

执行 `raser field [路径] [选项...]` 时，按以下顺序路由：

1. **建立工程上下文**：`register` 在解析器中挂接运行入口。`cli/raser.py` 推算目标所属的工程根目录并进入 `project_root_context`（路径解析见[公共基础设施（`supports`）](../supports/README.md)；不给路径时取当前文件夹）。若带有 `--draw <对象>`，直接绘制网格与网格节点上的掺杂后返回。
2. **检测目标类型（`run(kwargs)`）**：检查目标路径下是否存在实验的 `config.json`：
   - **为假（器件名或器件路径）**：定位 `work/<器件>/field/`（或当前所在的 `field` 目录），按 `field` 段设置进入场节点求解。
   - **为真（已有实验文件夹）**：读取实验的 `config.json`。
3. **拦截场文件夹自身**：若目标本身就是场文件夹，抛出 `SystemExit(f"{folder}: this is the field itself; give its device, raser field {config['device']}")`。
4. **为实验准备共享场**：根据 `config.json` 加载对应的实验类定义，进入该实验所属的工程根目录与组件上下文，调用 `make_shared`：
   - 按实验 `config.json` 的分段设置以及本次命令传入的 `--set`、`--scan`（“段.键”地址，如 `field.voltage`）展开目标扫描点，实验的 `config.json` **保持原样**。
   - 收集各扫描点所需的共享场需求。
   - 若 `kwargs["dry_run"]` 为真：逐点检查 `ready(options, files) is not None`，打印 `f"{root}: {piece.name} {state} for {options}"`（`state` 为 `"ready"` 或 `"to be made"`）后返回。
   - 否则调用 `_make_shared` 补算全部未就绪的共享场节点。

### 节点指纹、加锁与进程启动

求解场节点时，按以下顺序核对输入、加锁并启动作业进程：

1. **提取求解开关的指纹项（`settings(kwargs)`）**：令 `imported = None`；若打开了 TCAD 导入（`kwargs.get("input") is not None`），读取 `Path(kwargs["input"]).read_bytes()` 的完整 64 位小写十六进制 SHA-256 摘要赋给 `imported`。返回 `{"umf": bool(kwargs.get("umf")), "imported": imported}`；UMFPACK 与 TCAD 导入都未打开时为 `{"umf": False, "imported": None}`。
2. **核对节点指纹与复用**：将 `field` 环节用到的设置值（含 `settings`、所选网格及其文件的 SHA-256 哈希）与器件组件文件中 `field` 读取的部分（器件 `"field"` 段，以及 `Reading` 记录进 `"read"` 的器件属性、顶层与一级嵌套 JSON 键）汇总取指纹作为 `<节点号>`：
   - 若对应场节点在 `work/<器件>/field/<节点号>/` 下已存在且已完成求解，直接复用该节点；若当前代码版本与 `node.json` 记录不一致，打印一条提示，结果照常复用。
   - 若需要求解或补算子任务，对该节点单独加锁（写到一半的节点带 `.part` 后缀，写完才改为正式名字），并在 `node.json` 中记录输入、代码版本、运行环境与运行状态。
3. **启动作业与构造子命令（`job_command(kwargs)`）**：
   - 单个目标、未传 `jobs` 且非 `-b` 时，在当前进程通过 `_logged` 直接调用 `_run_job`；多目标或 `jobs=1`（仿真链 `start` 传入，确保 DEVSIM 只在独立子进程或集群作业里加载）且非 `-b` 时启动独立子进程；`-b` 时提交到集群。
   - 启动独立子进程或集群作业时，由 `job_command(kwargs)` 构造子命令 `raser field <路径>`，并把本节点的 `field` 段设置（偏压、求解开关、TCAD 导入文件的绝对路径等）以 `--set field.<键>=<值>` 传给子命令。

### 作业求解调度

场求解作业持节点锁进入 `solve(kwargs)`，按以下严格顺序执行：

1. **校验 `field.mode`**：
   - 若 `kwargs["mode"] == "fast"` 且 `not HAS_DEVSIM`，打印 `f"devsim is not installed: the field of {kwargs['det_name']} is found in the fast mode, not the full one"`。
   - 若 `kwargs["mode"] != "full"`，抛出 `NotImplementedError(f"the {kwargs['mode']} mode of a field is not there yet: only field.mode 'full' is")`。
2. **外部 TCAD 导入分支**：若 `kwargs["input"] is not None`，调用 `_import(kwargs)`：
   - 构造 `my_d = Detector(kwargs["det_name"], kwargs["_files"]["device"])`；
   - 调用 `bias = tcad.import_field(kwargs["input"], my_d, kwargs["_run_path"], kwargs["bias"], kwargs["flip"])` 导入体区场、生成导电区、求解各读出电极权重场并更新节点记录中的 `axes`、`read` 与 `solved`；
   - 打印 `f"{kwargs['_run_path']}: the field of {kwargs['input']} at {bias} V"` 并直接返回（跳过 `_solved` 检查与 UMFPACK 加载）。
3. **HEMT 直流输运分支**：取 `physics = kwargs["_files"]["device"].get("hemt_physics", {})`。若 `physics.get("transport_model") == "drift_diffusion_v1"`：
   - 收集打开的单点电容（`kwargs["cv"] is not None`）、权重场（`kwargs["wf"]`）、噪声（`kwargs["noise"]`）开关组成 `dropped`；
   - 打印 `f"{kwargs['det_name']} is solved by its own transport solver: only its DC sweep is run, without CV, weighting field or noise"`（`dropped` 非空时追加 `f"; {' '.join(dropped)} dropped"`）；
   - 调用 `_ramp_or_weighting({**kwargs, "noise": False}, cv=False, wf=False)` 并直接返回。
4. **切线性求解器与解析偏压、求解器配置**：
   - 若 `kwargs["umf"]` 为真，导入 `devsim.umfpack.umfshim` 将本进程 DEVSIM 线性求解器设为 UMFPACK。
   - `_bias(kwargs)`：若 `kwargs["bias"] is not None`，取 `float(kwargs["bias"])`（$\text{V}$）；否则取 `Detector(kwargs["det_name"], kwargs["_files"]["device"]).voltage`（$\text{V}$）。
   - `_solver(kwargs)`：深拷贝 `core/field/solver_section.SOLVER`，将 `kwargs["_files"]["device"].get("field", {}).get("solver", {})` 递归深度合并到其上（同键且两端均为 `dict` 时递归合并，否则直接替换）。
5. **规划子任务并跳过已完成项**：
   - 按顺序生成 `named`：`kwargs["iv"]` 为真加 `"iv"`、`kwargs["cv"] is not None` 加 `"cv"`、`kwargs["wf"]` 为真加 `"wf"`。
   - 令 `cv_at = _bias(kwargs)`（当 `kwargs["cv"] is True`）或 `kwargs["cv"]`（$\text{V}$）。
   - 调用 `_solved(kwargs, asset, at)` 读取当前场节点记录中的 `"solved"`，判断：
     - `have["iv"] = _bias(kwargs) in solved.get("potential", [])`；
     - `have["cv"] = cv_at in solved.get("capacitance", [])`；
     - `have["wf"] = _bias(kwargs) in solved.get("weighting", [])`。
   - 令 `left = [part for part in (named or ["iv", "wf"]) if not have[part]]`。若 `left` 为空，打印 `f"{kwargs['_run_path']}: already solved"` 并返回。
6. **逐项求解并清空 DEVSIM 状态**：遍历 `done, part in enumerate(left)`：
   - 若 `done > 0`，调用 `_empty_devsim()`：从 `devsim.get_parameter_list()` 读取存在的 `"direct_solver"` 与 `"solver_callback"`，调用 `devsim.reset_devsim()`，再把这两个参数写回 DEVSIM。
   - 若 `part == "cv"`，调用 `_capacitance(kwargs)`：
     1. 令 `my_d = Detector(kwargs["det_name"], kwargs["_files"]["device"])`、`voltage = _bias(kwargs)`（`kwargs["cv"] is True`）或 `float(kwargs["cv"])`（$\text{V}$）、`folder = Path(kwargs["_run_path"])`；
     2. 调用 `value, frequency = saved_point.capacitance(my_d, folder, voltage, _solver(kwargs))` 加载 `folder / f"{float(voltage)}V.devsim"`（缺失时抛出 `FileNotFoundError`）；
     3. 构造 `point = {"voltage_V": voltage, "specific_capacitance_pF": value, "per": {1: "cm^2", 2: "cm", 3: "device"}[my_d.dimension], "area_factor": float(my_d.device_dict.get("area_factor", 1.0)), "frequency_Hz": frequency}`；
     4. 将 `point` 写入 `folder / f"{voltage}V.cv.json"`，调用 `save_solved(str(folder), "capacitance", voltage)` 更新节点记录，并打印 `point`。
   - 若 `part` 为 `"iv"` 或 `"wf"`，调用 `_ramp_or_weighting(kwargs, cv=not named, wf=(part == "wf"))`，将 `target=kwargs["det_name"]`、`bias=_bias(kwargs)`、`cv`、`wf`、`solver=_solver(kwargs)`、`_field_directory=kwargs["_run_path"]` 合并后传给 `solver_section.main`。
7. **原子落盘与集群唤醒**：`solve` 返回后，将写到一半带 `.part` 后缀的节点完成落盘并更新运行状态。若处于集群作业环境（`RASER_CLUSTER_JOB` 非空），`_start_again` 读取等待该场的下游命令列表：对每条等待记录，若 `RASER_RESUBMIT_DEPTH < _WAITING_DEPTH`（`8`），以深度 `+1` 重试最多 `_STARTS`（`4`）次、每次间隔 `_PAUSE`（`30` $\text{s}$）在 `entry["cwd"]` 下重新执行 `raser <command>`；拉起成功后将该条目从等待列表中移除。

### 仿真链共享场检查、补算与交付

八环节仿真链及多器件实验通过 `chain.py` 与 `stages/field` 按以下步骤与共享场节点交互：

1. **实验类组装与器件视图切换（`_of`）**：
   - 实验类声明其包含的环节、器件、各器件角色（如被测器件、参考器件），不写设置的取值。链上 `current` 读取 `deposit` 和 `field` 节点，`readout` 读取 `current` 和 `field` 节点，其后依次衔接 `digitizer`、`trigger`、`reconstruction`、`analysis`。多器件实验通过 `_of(kwargs, device)` 将配置与组件视图切换到对应器件。
2. **确定运行辐照注量（`_flux_of_run(my_d, options)`）**：若 `field` 段配置给出了辐照注量，返回 `float(...)`（$\text{cm}^{-2}$）；否则返回 `float(my_d.irradiation_flux)`（无辐照段时为 `0.0` $\text{cm}^{-2}$）。
3. **检查共享场节点就绪（`ready(options, files)`）**：
   - 取 `device = files["device"]` 构造 `my_d = Detector(device["det_name"], device)`。
   - 调用 `solved_field(my_d, my_d.voltage, _flux_of_run(my_d, options))`（使用 `DEFAULT_MODE`）在 `work/<器件>/field/` 下匹配注量、模式、`read` 一致性（调用 `changed(old["read"], Detector(device["det_name"], device))` 逐项比对 `"attributes"`、`"keys"` 与外部网格文件 `"files"` 的 SHA-256 哈希）以及 `solved.potential`、`solved.weighting` 是否均含 `float(my_d.voltage)`；不匹配或未完成时返回 `None`，就绪时返回命中场节点目录 `folder`。
4. **去重补算与等待（`_make_shared` 与 `start`）**：
   - 主命令遍历每个待运行扫描点所需的共享场，按器件与 `field` 段设置去重；当某组需求未在本次命令中启动且 `ready(options, files) is None` 时，调用 `start(kwargs, options, files)`：
     1. 组装 `raser field <device> --set field.voltage=<偏压>` 命令参数（若辐照注量不同于器件文件里的值，或扫描点改了器件文件里偏压以外的值，一并传入）。
     2. 写入 `batch=kwargs["batch"]`、`mem=kwargs["mem"]`、`jobs=1`（确保在独立子进程或集群作业中执行，DEVSIM 只在那里加载）、`_argv=words`、`_entry_command_prefix=("field",)`、`_waiting=kwargs.get("_waiting")`（仅 `-b` 时非空）。
     3. 打印 `"solving the field first: " + " ".join(["raser", *words])`，启动场求解。
   - 若 `start` 因另一进程持有节点锁而抛出 `Running`，`_make_shared` 打印 `f"{piece.name}: {running}"` 并跳过；随后主命令检测到 `ready` 为 `None`，将对应下游作业移入等待并打印等待提示。
   - 若非 `-b` 且非 `--dry-run`，`start` 返回后再次检查 `ready(options, files)`；仍为 `None` 时抛出 `RuntimeError(f"{piece.name} was made in this process and is still not ready for a point of {root}: waiting would not help")`。
5. **参数表记录、视图链接与作业内校验（`chain._field`）**：
   - 共享场节点就绪后，主命令将该场节点的 `<节点号>` 写入实验的 `points.json`，将 `points/<点名>/field` 软链接指向该场节点，并将该 `<节点号>` 作为上游节点号传给 `current` 与 `readout` 计算各自的节点指纹。
   - 作业执行 `field` 校验时，`_field(kwargs, device)` 先经 `_of(kwargs, device)` 切换到对应器件视图，再调用 `ready(kwargs, kwargs["_files"])`；返回 `None` 时抛出 `FileNotFoundError(f"no field of {kwargs['det_name']} ready for this run: solve it with `raser field {kwargs['det_name']}`")`。

## 软件实现

### 源文件分工

- `src/raser/stages/field/__init__.py`：实现 `raser field`（`fld`）命令注册与入口路由（`register`、`run`）、场求解调度（`solve`、`settings`、`job_command`）、求解辅助与单点电容写出（`_solver`、`_bias`、`_solved`、`_ramp_or_weighting`、`_capacitance`、`_import`、`_empty_devsim`），以及面向仿真链的共享场就绪检查与补算接口（`_flux_of_run`、`ready`、`start`）。
- `src/raser/stages/chain.py`：组装仿真链中 `field` 与下游 `current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 的衔接，提供单/多器件视图切换 `_of` 及场就绪校验函数 `_field`。
- `src/raser/lifecycle/`（`workflow.py`、`slices.py`）：管理分段 `config.json` 读取、`points.json` 参数表与 `points/<点名>/<环节>/<作业号>` 视图更新、节点指纹计算与 `node.json` 读写、单节点加锁与 `.part` 原子落盘、共享场预检与去重补算（`make_shared`、`_make_shared`），以及本地进程封装与集群唤醒等待命令（`_start`、`_run_job`、`_start_again`）。
- `src/raser/core/field/`（`solved.py`、`reading.py`、`solver_section.py`、`saved_point.py`、`tcad.py`、`save_milestone.py`、`circuit_parameters.py`、`device_circuit.py`）：被本环节直接调用的底层模块，分别提供共享场定位（`solved_field`）、器件读取追踪比对（`Reading`、`changed`）、默认求解器配置与 DEVSIM 入口（`SOLVER`、`main`）、单点电容求解（`capacitance`）、Sentaurus TDR 导入（`import_field`）、求解状态更新（`save_solved`）与器件参数等效电路构造。

### 核心数据结构

| 数据结构 | 字段 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `settings` 字典 | `umf` | `bool` | 无 | 是否打开 UMFPACK 线性求解器开关 |
| `settings` 字典 | `imported` | `str \| None` | 无 | TCAD 导入的 TDR 文件的完整 64 位 SHA-256 哈希，未导入为 `None` |
| `point` 电容字典 | `voltage_V` | `float` | $\text{V}$ | 单点小信号电容求解偏置电压 |
| `point` 电容字典 | `specific_capacitance_pF` | `float` | 1D $\text{pF/cm}^2$，2D $\text{pF/cm}$，3D $\text{pF}$ | 网格比电容（3D 为器件电容） |
| `point` 电容字典 | `per` | `str` | 无 | 比电容归一化基准：`"cm^2"`、`"cm"` 或 `"device"` |
| `point` 电容字典 | `area_factor` | `float` | 1D $\text{cm}^2$，2D $\text{cm}$，3D 无量纲 | 器件面积或长度换算因子（缺省 `1.0`） |
| `point` 电容字典 | `frequency_Hz` | `float` | $\text{Hz}$ | 小信号 AC 求解频率 |

## 接口

### 选项与配置键

命令是 `raser field [路径]`：不给路径就是当前文件夹，给了就是相对或绝对路径，可为器件名、器件 project 路径或含 `config.json` 的实验文件夹路径；传入场文件夹本身会中止。`--draw <对象>` 只绘制网格和网格节点上的掺杂。公共运行、扫描与集群选项 `-b`/`--batch`、`-t`、`-mem`、`--dry-run`、`--scan`、`--set` 见[命令行接口（`raser`）](../cli.md)与[实验、扫描点与种子](../lifecycle/experiments.md)。

`field` 段的设置取自实验 `config.json`，用 `--set field.<键>=<值>`、`--scan field.<键>=<值1>,<值2>` 改。代码不留默认值：表里“示例里的值”是 `examples/HPK-Si-PiN/signal/config.json` 写的值；`config.json` 缺了要用的键时报错，指出缺的“段.键”。

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage` | `200.0`（写 `null` 时取器件文件里的偏压 `bias.voltage`） | $\text{V}$ | 目标偏置电压（`float`）；缺场时链命令以 `--set field.voltage=<值>` 调用 `raser field`；TCAD 导入时核对 TDR 电极电压，或在 TDR 无电极电压时指定偏压 |
| `field.irradiation_flux` | `null`（取器件文件里的辐照注量，器件文件没有辐照块时为 `0`） | $\text{cm}^{-2}$ | 辐照注量（`float`，$1\ \text{MeV}$ 中子等效注量） |
| `field.mode` | `"full"` | 无 | 场获取模式，可选 `"full"`、`"semi_fast"`、`"fast"`；当前只实现 `"full"` |

`field` 段还有这几类设置，各自做的事如下：

- **网格**：同一个器件可以有几套网格，用哪一套由 `field` 段的设置指定。
- **子任务**：IV 扫描从 `0 V` 扫到目标偏压求解电势与电场并输出 IV 曲线；单点电容从已有 `<V>V.devsim` 重载该偏压做小信号电容求解，写出 `<V>V.cv.json`；权重场读取同偏压 `Conductive_<V>V.pkl` 求解各读出电极权重场（单晶胞周期性条形电极另算条间互容）。三个都不打开时做整套求解：含沿途 CV 的偏压扫描，再求权重场。
- **噪声**：偏压扫描各曲线采样点额外求解并绘制器件噪声电流（HEMT `drift_diffusion_v1` 分支下丢弃）。
- **UMFPACK**：求解前加载 `devsim.umfpack.umfshim`，切至 UMFPACK 线性求解器。
- **TCAD 导入**：给出 Sentaurus TDR 文件，跳过 DEVSIM 偏压扫描，导入体区场并在其网格上求权重场；坐标翻转只配合 TCAD 导入，反转节点坐标列序，2D 绘图同步交换 `x` 与 `y` 轴。

单场节点单作业执行、固定子任务顺序 `iv → cv → wf`、整套求解时沿途算 CV、只实现 `field.mode` 为 `"full"`、DEVSIM 重置保留参数列表、集群唤醒重试次数与递归深度上限都写死在代码里。

器件文件里 `field` 读的键：

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.solver` | `SOLVER`（见[场求解与加载（`core/field`）](../core/field.md)） | 依子键而定 | 深度合并覆盖求解器配置 `SOLVER` |
| `hemt_physics.transport_model` | 无（未设时走常规路径） | 无 | 设为 `"drift_diffusion_v1"` 时分派到二维 HEMT 直流输运分支，丢弃单点电容、权重场与噪声开关 |
| `area_factor` | `1.0` | 1D $\text{cm}^2$，2D $\text{cm}$，3D 无量纲 | `_capacitance` 写入 `<V>V.cv.json` 的器件面积/长度换算因子 |

### 读写的文件

以下共享场节点文件位于 `<场节点目录>`（即 `work/<器件>/field/<节点号>/`，示例就地运行时为 `examples/<器件>/field/<节点号>/`；写入期间目录带 `.part` 后缀并单独加锁）内，实验侧通过 `<实验文件夹>/points.json` 和 `<实验文件夹>/points/<点名>/field` 引用。

#### 本环节直接读写的文件

- **读入的输入文件**：
  - 器件 JSON（project 内的 `device.json` 或内置组件 `<器件名>.json`）：由本环节读取，其中被 `field` 用到的部分纳入场节点输入指纹并记入 `node.json`。
  - `<实验文件夹>/config.json`：按八个环节分段的完整配置文件；在 `raser field <实验文件夹>` 或链命令补算共享场时读取其中的 `field` 段及实验设置。
  - TCAD 导入的 TDR 文件（Sentaurus TDR，HDF5）：由 `settings` 读取全文计算 64 位 SHA-256 哈希，由 `tcad.import_field` 读取网格、电极电压与体区场。
  - `<场节点目录>/<voltage>V.devsim` 与 `<场节点目录>/Conductive_<V>V.pkl`：分别由单点电容（`saved_point.capacitance`）与权重场（`solver_section.main`）子任务读取。
- **`<场节点目录>/node.json`**（写者：生命周期节点管理与场求解作业）：JSON 对象，原样记录该场节点的输入（`field` 环节用到的设置值与器件组件文件里用到的那一部分，指纹由它们算出），同时另记代码版本、运行环境和运行状态。
- **`<场节点目录>/<voltage>V.cv.json`**（文件名保留浮点格式，如 `200.0V.cv.json`；写者：单点电容子任务 `_capacitance`）：JSON 对象，包含 `voltage_V`（`float`，$\text{V}$）、`specific_capacitance_pF`（`float`，1D $\text{pF/cm}^2$、2D $\text{pF/cm}$、3D $\text{pF}$）、`per`（`str`，`"cm^2"`/`"cm"`/`"device"`，无）、`area_factor`（`float`，1D $\text{cm}^2$、2D $\text{cm}$、3D 无量纲）、`frequency_Hz`（`float`，$\text{Hz}$）。
- **器件参数电路图资产**（写者：`field` 环节，位于 `work/<器件>/field/` 下）：标上结电容、耦合电容与未耗尽层数值的器件参数电路图，作为器件资产供 `readout` 环节接进器件电路。
- **`<实验文件夹>/points.json` 与 `<实验文件夹>/points/<点名>/field`**（写者：生命周期实验调度）：`points.json` 为实验参数表，一行一个扫描点，记录各扫描轴取值与包括 `field` 在内的每个环节节点号（由 `raser status` 打印）；`points/<点名>/field` 为指向 `work/<器件>/field/<节点号>/` 的软链接视图。

#### `core/field` 写出的场数据、归档与图

在 `<场节点目录>` 内，`.pkl` 与 `Capacitance_<V>V.json` 对整数偏压省略小数点（如 `Potential_200V.pkl`），非零偏压的 `.devsim`、`.dd` 与全部 `.undepleted.json`、`.cv.json` 保留浮点格式（如 `200.0V.undepleted.json`），零偏归档写作 `0V.devsim` 与 `0V.dd`。DEVSIM 偏压扫描（在 `0 V`、每个 `saved_voltage_interval` 存盘点与目标偏压）或 TCAD 导入写出的体区场 `.pkl`（`Potential`、`Electrons`、`Holes`、`TrappingRate_n`、`TrappingRate_p`、`Conductive`、`NetDoping_0V.pkl` 或 TCAD 下的 `NetDoping_<V>V.pkl`）、未耗尽层文件 `<V>V.undepleted.json`、DEVSIM 与 Tecplot 归档（`0V`/`<V>V.devsim`、`0V`/`<V>V.dd`、`last_solvable.dd`、`<det_name>.dat`、`converted.devsim`），权重场子任务（含整套求解）或 TCAD 导入写出的权重场 `weightingfield/<电极>/Potential_<V>V.pkl`、`weightingfield/weightingfield.dat` 与单晶胞条形互容 `weightingfield/<电极>/Capacitance_<V>V.json`，IV/CV/噪声曲线数据（`simIV*`、`simCV*`、`simnoise*`）与各维度场分布图（一维的存进 `plots/`：`iv`、`cv`、`noise`、`doping`、`potential_<V>V`、`electric_field_<V>V`、`trapping_rate_<V>V`、`weighting_potential_<电极>_<V>V`、`weighting_field_<电极>_<V>V`，各有 `.png` 与 `.pdf`），以及 HEMT `drift_diffusion_v1` 分支写出的 `HEMT_TRANSPORT_*`（`IdVg.csv`、`final_profile.csv`、`final.devsim`、`IdVg.png`/`.pdf`、`summary.json`），其内部格式、键、形状、类型与单位以及物理求解与插值细节见[场求解与加载（`core/field`）](../core/field.md)。
