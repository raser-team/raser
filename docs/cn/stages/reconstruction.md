# 事件重建环节（`stages/reconstruction`）

`src/raser/stages/reconstruction.py` 是八环节仿真链的第 7 个环节 `reconstruction`，由 `raser reconstruction`（短命令 `raser reco`）或测试、应用的实验命令调度。它排在[触发环节（`stages/trigger`）](trigger.md)之后，读 `trigger` 的输出：被记录的事例和它们经[数字化环节（`stages/digitizer`）](digitizer.md)得到的数字波形。本环节把阈值从 $\text{mV}$ 换算为 $\text{V}$，确定各电极的脉冲方向，调用[事件重建（`core/reconstruction`）](../core/reconstruction.md)扣除基线、估计噪声、提取脉冲幅度、定时量、主瓣面积与跨电极团簇，把每个事例写成事件表的一行，存进自己的节点 `nodes/reconstruction/<节点号>/`。事件表交给下游[统计分析环节（`stages/analysis`）](analysis.md)统计时间分辨。

## 行为

### 跑到重建环节

`raser reconstruction`（或 `raser reco`）在当前文件夹或给定路径的实验上跑到 `reconstruction` 为止，缺的上游节点先补上：

```bash
raser reconstruction [路径] [<source>] [选项...]
raser reco [路径] [<source>] [选项...]
```

多位置实验（如 `cflm` 的 `24` 个位置）按位置分别重建，各位置用同一组重建设置。

例如在 `HPK-Si-PiN` 示例上扫两档偏压：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 -evt 200 --seed 1
```

`voltage_100`、`voltage_200` 两个点都按默认参数 `threshold = 10.0` $\text{mV}$、`amplitude_threshold = 10.0` $\text{mV}$、9 个恒比比例 `[0.1, ..., 0.9]` 重建，沿用 `readout` 给出的 `pulse_edge = ['falling']`。`points/voltage_200/reconstruction` 指向的节点里，作业 `0` 的事件表属性为 `threshold = 0.01`（单位 $\text{V}$）、`amplitude_threshold = 0.01`（单位 $\text{V}$）、`edge = ['falling']`、`electrodes = ['top']`、`fractions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]`，14 个数据集如下（`200` 个事例中有 `196` 个存了 `top` 电极波形，其余 `4` 个在波形数值列填 `NaN`、`above` 为 `False`）：

| 数据集名 | 示例形状 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | 无 | 记录事例的 Geant4 编号 |
| `selected` | `(200,)` | `bool` | 无 | 事例是否找到 seed：至少一个电极的幅度不低于 `amplitude_threshold` |
| `cluster_size` | `(200,)` | `int64` | 个 | 团簇包含的电极数 |
| `cluster_center` | `(200,)` | `float64` | 电极下标（从 `0` 起） | 团簇的幅度加权中心位置（无团簇时为 `NaN`） |
| `traced` | `(200, 1)` | `bool` | 无 | 该事例是否存有该电极的波形（`196` 个事例为 `True`） |
| `above` | `(200, 1)` | `bool` | 无 | 波形峰值是否达到 `threshold` |
| `baseline` | `(200, 1)` | `float64` | $\text{V}$ | 波形前 `200` 点基线均值 |
| `noise` | `(200, 1)` | `float64` | $\text{V}$ | 波形前 `200` 点基线总体标准差 |
| `amplitude` | `(200, 1)` | `float64` | $\text{V}$ | 基线以上最大脉冲幅度 |
| `ToA` | `(200, 1)` | `float64` | $\text{s}$ | 过阈到达时间 |
| `ToT` | `(200, 1)` | `float64` | $\text{s}$ | 过阈持续时间 |
| `CoG` | `(200, 1)` | `float64` | $\text{s}$ | 过阈区间的时间重心 |
| `area` | `(200, 1)` | `float64` | $\text{V}\cdot\text{s}$ | 正向脉冲主瓣积分面积 |
| `CFD` | `(200, 1, 9)` | `float64` | $\text{s}$ | 各恒比比例 `fractions` 对应的定时结果 |

### 改重建设置，上游节点全部复用

重建设置只有 `reconstruction` 读。只改这一段时，`deposit`、`current`、`readout`、`digitizer`、`trigger` 的指纹都和原来相同，节点全部复用，只算新的 `reconstruction` 节点：

```bash
raser reco work/HPK-Si-PiN/signal --set reconstruction.threshold=15 --set reconstruction.amplitude_threshold=20
```

`--set` 把新阈值 `15` $\text{mV}$ 与 `20` $\text{mV}$ 写进 `config.json` 的 `reconstruction` 段，之后的 `raser analysis` 按新阈值统计。节点只增不减：把阈值改回 `10`，视图指回原来的节点。代码版本和节点记录的不一致时只给一条提示，结果照常复用。每个节点单独加锁，写到一半的节点带 `.part` 后缀。正式运行前可加 `--dry-run`，只打印将要运行的扫描点、环节和作业状态。节点与复用规则见[片与重跑](../lifecycle/slices.md)。

### 上游零事例与多位置空输入

上游 `deposit` 在本作业录得 `0` 个有效事例时，`reconstruction` 随之跳过本作业。多位置实验里某个位置本作业没有能量沉积、也就没有波形时，这个位置直接记 `0` 个事例；同一作业的其他位置照常计算。

### 沿用脉冲方向与反向提示

没有设 `edge`（默认 `None`）时，每个电极沿用 `readout` 给出的 `pulse_edge`（如负脉冲取 `"falling"`，重建时先把扣除基线后的净波形乘以 `-1.0` 翻正，再提取特征）。用 `--edge` 或 `reconstruction.edge` 指定 `"rising"` 或 `"falling"` 时，这个方向统一用于所有电极；某电极的 `pulse_edge` 与它相反时，计算照常继续，终端为该电极打印一行提示：

```text
<readout_path>: edge <edge> given for <electrode>, whose pulse is <pulse_edge>: its pulses are not seen as the readout makes them
```

这说明所选方向与读出链实际给出的脉冲极性相反。不是有意反向检查时，去掉 `--edge`（或删掉配置里的 `edge`），或改成与 `pulse_edge` 一致的方向。

## 规则

### 内置常数

下表的常数写死在模块代码里：

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `MILLIVOLT` | `1.0e-3` | $\text{V/mV}$（代码注释标为 `V`） | `src/raser/stages/reconstruction.py`：把 `threshold` 与 `amplitude_threshold` 从 $\text{mV}$ 换算为 $\text{V}$ 的乘子 |
| `BASELINE_POINTS` | `200` | 采样点 | `src/raser/core/reconstruction/event.py`：每条波形开头用于求基线均值与噪声标准差的采样点数 |
| `EDGE_SIGN` | `{"rising": 1.0, "falling": -1.0}` | 无 | `src/raser/core/reconstruction/event_table.py`：把净波形按所选方向翻成正向脉冲的极性乘子 |

### 环节命令的解析与启动（`stage_commands.run`）

1. **挂载参数（`register`）**：注册 `reconstruction`（别名 `reco`），依次挂上上游各环节和本环节的选项以及共用运行参数，执行入口绑定为 `partial(run, "reconstruction")`。
2. **解析实验**：读实验文件夹的 `config.json`，找到它的实验类。
3. **核对环节**：实验类不含 `reconstruction` 环节时退出：

   ```text
   <folder>: the experiment <workflow> has no reconstruction slice; its slices: <names>
   ```

   改用该实验具备的环节命令，或换用含重建环节的实验。
4. **启动**：截止环节设为 `reconstruction`，进入实验所在 project 的上下文、切到实验文件夹后执行，结束后切回原目录。实验文件夹带 `config.json` 时，命令行里的目标被改写成绝对路径，集群上的作业从实验文件夹重新运行原命令时用它。

### 单作业重建（`reconstruction.run` 与 `reconstruct`）

1. **多位置预检**：给了位置且该位置本作业没有输入波形时，直接返回 `{"events": 0}`。
2. **调用重建**：`reconstruct(输入波形, 输出事件表, float(threshold), float(amplitude_threshold), tuple(float(part) for part in fractions), edge)`。
3. **读入并校验波形（`read_waveforms`）**：
   - `_check_layout` 检查数据集 `("event", "t0", "count", "stored", "index", "voltage")` 都在且 `voltage` 是一维；不满足时抛出

     ```text
     ValueError: <path> is a readout file of an older layout (no <missing>): run the readout again
     ```

   - 文件属性里没有 `pulse_edge` 时抛出

     ```text
     ValueError: <path> has no pulse_edge: the readout of this version did not write it; run the readout again
     ```

     两条都说明输入由旧版本写出，重跑 `readout` 即可。校验通过后还原各事例已存电极的电压波形 `voltage`（单位 $\text{V}$），返回 `Waveforms(electrodes, dt, events, pulse_edge)`。
4. **选定脉冲方向（`chosen_edges(edge, waveforms.pulse_edge, waveforms.electrodes)`）**：
   - `edge is None` 时，返回 `list(waveforms.pulse_edge)` 和空提示列表。
   - `edge` 不在 `EDGE_SIGN` 里时抛出

     ```text
     ValueError: edge <值>: the thresholds are set on a rising (positive pulses) or a falling (negative pulses) edge
     ```

     改成 `"rising"`、`"falling"`，或删掉这个键让它沿用 `pulse_edge`。
   - `edge` 为 `"rising"` 或 `"falling"` 时，所有电极都用它；对 `pulse_edge` 与它不同的每个电极生成一条提示，`reconstruct` 逐条打印 `f"{readout_path}: {note}"`。
5. **换算阈值、提取特征（`event_table`）**：
   - 传入 `threshold * MILLIVOLT` 与 `amplitude_threshold * MILLIVOLT`（单位 $\text{V}$）。
   - `fractions` 里有不在 $(0, 1)$ 开区间内的元素时抛出 `ValueError: fractions <非法列表>: a constant fraction lies between 0 and 1`。
   - 输入没有事例时抛出 `ValueError: the readout holds no event`；检查对应作业的 `current` 和 `readout` 输出，必要时重算上游。
   - 对每个事例每个存了波形的电极调用 `net_pulse(samples)`。采样点数 `<= 200`（`BASELINE_POINTS`）时抛出 `ValueError: <点数> samples, not more than the 200 of the baseline`，检查模拟时间窗长度与采样步宽 `dt` 是否太短。点数大于 `200` 时扣除前 `200` 点均值 `baseline`（$\text{V}$）、求前 `200` 点总体标准差 `noise`（$\text{V}$），乘以 `EDGE_SIGN[edge]` 翻正后由 `electrode_row` 与 `cluster` 算出单电极特征和跨电极团簇，组成 `EventTable`。
6. **写出（`write_event_table(path, table)`）**：把 `EventTable` 一次写进事件表文件。

## 软件实现

### 源文件分工

- `src/raser/stages/reconstruction.py`：定义 `MILLIVOLT`、单作业重建函数 `reconstruct` 和环节入口 `run`，负责单位换算、反向提示打印和调用核心重建函数。
- `src/raser/stages/chain.py`：定义默认参数 `RECONSTRUCTION_DEFAULTS`、参数注册函数 `reconstruction_arguments`（`-threshold`、`-amplitude_threshold`、`--edge`）和按需导入 `reconstruction` 模块的入口 `_reconstruction`。
- `src/raser/stages/stage_commands.py`：注册各环节命令；解析目标实验，核对实验含目标环节，设截止环节并切入实验文件夹执行。
- `src/raser/stages/files.py`：给出各环节在当前作业下的输入输出文件路径。

### 核心数据结构

`EventTable`（`src/raser/core/reconstruction/event_table.py`）：

| 字段 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `electrodes` | `list[str]` | 无 | 读出电极名称，与二维、三维数组第 2 维顺序一致 |
| `threshold` | `float` | $\text{V}$ | 换算为 $\text{V}$ 后的过阈阈值 |
| `amplitude_threshold` | `float` | $\text{V}$ | 换算为 $\text{V}$ 后找团簇 seed 的幅度阈值 |
| `fractions` | `tuple[float, ...]` | 无 | 恒比定时比例，各元素位于 $(0, 1)$ |
| `edges` | `list[str]` | 无 | 各电极实际用的脉冲方向（`"rising"` 或 `"falling"`） |
| `columns` | `dict[str, np.ndarray]` | `baseline`、`noise`、`amplitude` 为 $\text{V}$；`ToA`、`ToT`、`CoG`、`CFD` 为 $\text{s}$；`area` 为 $\text{V}\cdot\text{s}$；`cluster_size` 为个；`cluster_center` 为电极下标；其余无单位 | 14 个输出数据集的名字到 NumPy 数组的映射 |

## 接口

### 选项与配置键

本环节能设的只有下表这些；基线采样点数 `200`、毫伏到伏的换算因子 `1.0e-3` $\text{V/mV}$、方向极性乘子都写死在代码里。设置写在 `config.json` 的 `reconstruction` 段，`--set`、`--scan` 用“段.键”作地址，如 `--set reconstruction.threshold=15`。

| 选项或键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `[路径]` | 当前文件夹 | 无 | 实验文件夹 |
| `-threshold`（`reconstruction.threshold`） | `10.0` | $\text{mV}$ | 脉冲过阈阈值（环节内乘以 `1e-3` 换算为 $\text{V}$）；用来判定单电极 `above`、计算 `ToA`、`ToT`、`CoG`、`area`，以及种子左右紧邻电极的入簇条件 |
| `-amplitude_threshold`（`reconstruction.amplitude_threshold`） | `10.0` | $\text{mV}$ | 找团簇 seed 的幅度阈值（环节内乘以 `1e-3` 换算为 $\text{V}$）；幅度不低于它的电极作 seed，事例找到 seed 时记 `selected = True` |
| `--edge`（`reconstruction.edge`） | `None` | 无 | 阈值作用的脉冲方向：`"rising"`（正脉冲）、`"falling"`（负脉冲）或 `None`（各电极沿用 `readout` 给出的 `pulse_edge`） |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | 无 | 恒比定时（`CFD`）的幅度比例，每个元素严格位于 $(0, 1)$；写在 `config.json` 的 `reconstruction` 段里 |

`fractions` 的列表值带方括号和逗号，用命令行 `--set` 或 `--scan` 传入时报错：

```text
ValueError: fractions = <值>: the folder of this value would be named <名>, which holds more than letters, digits and ._+-; scan or set a number or a short name, and give an expression such as a doping profile a parameter with a name in its file
```

把 `fractions` 改写进 `config.json` 的 `reconstruction` 段即可。

`raser reconstruction` 同时挂载上游环节的选项，供新建实验或补算上游时用：`deposit` 选项（`source`、`--g4setup`、`-evt`、`-gen`、`--generated-limit`、`--edep-min`、`--edep-max`、`deposit.plots`、`current.plots`、`-g4_vis`、`--g4-vis-driver`）见[能量沉积环节（`stages/deposit`）](deposit.md)，`-vol`/`--voltage`、`-irr`/`--irradiation` 见[场求解环节（`stages/field`）](field.md)和[载流子输运与感应电流环节（`stages/current`）](current.md)，`-amp`/`--amplifier`、`--sheet-resistance` 见[电子学读出环节（`stages/readout`）](readout.md)。共用运行参数（`-s`、`--seed`、`--same-seeds`、`--set`、`--scan`、`-b`、`-t`、`--dry-run`）见[命令行接口（`raser`）](../cli.md)和[实验、扫描点与种子](../lifecycle/experiments.md)。

### 读写的文件

- **读：`trigger` 的输出**。被记录事例的数字波形，带文件属性 `electrodes`（`string[]`，无单位）、`dt`（`float64`，单位 $\text{s}$）、`pulse_edge`（`string[]`，`"rising"` 或 `"falling"`），以及数据集 `event`（`(events,)`，`int64`）、`t0`（`(events,)`，`float64`，单位 $\text{s}$）、`count`（`(events,)`，`int64`，单位箱）、`stored`（`(events,)`，`int64`，单位个）、`index`（`(sum(stored),)`，`int64`）与 `voltage`（`(sum(stored * count),)`，`float64`，单位 $\text{V}$）。波形格式见[电子学读出（`core/readout`）](../core/readout.md)。
- **写：`nodes/reconstruction/<节点号>/` 里的事件表**。上游有记录事例、且（多位置实验中）该位置有输入波形时写出。HDF5 文件有 5 个属性（`electrodes`［`string[]`，无单位］、`threshold`［`float64`，单位 $\text{V}$］、`amplitude_threshold`［`float64`，单位 $\text{V}$］、`fractions`［`float64[]`，形状 `(fractions,)`，无单位］、`edge`［`string[]`，`"rising"` 或 `"falling"`］）、4 个形状为 `(events,)` 的一维数据集（`event`［`int64`］、`selected`［`bool`］、`cluster_size`［`int64`，单位个］、`cluster_center`［`float64`，单位为从 `0` 起的电极下标］）、9 个形状为 `(events, electrodes)` 的二维数据集（`traced`［`bool`］、`baseline`［`float64`，单位 $\text{V}$］、`noise`［`float64`，单位 $\text{V}$］、`amplitude`［`float64`，单位 $\text{V}$］、`above`［`bool`］、`ToA`［`float64`，单位 $\text{s}$］、`ToT`［`float64`，单位 $\text{s}$］、`CoG`［`float64`，单位 $\text{s}$］、`area`［`float64`，单位 $\text{V}\cdot\text{s}$］），以及 1 个形状为 `(events, electrodes, fractions)` 的三维数据集 `CFD`（`float64`，单位 $\text{s}$）。各属性与数据集的定义见[事件重建（`core/reconstruction`）](../core/reconstruction.md)。
- **写：`nodes/reconstruction/<节点号>/node.json`**。记下本节点的输入，以及代码版本、运行环境和运行状态。
- **写：`points.json` 与 `points/<点名>/reconstruction`**。参数表记各点 `reconstruction` 用的节点号；视图软链接指向该节点。
