# 载流子输运与感应电流环节（`stages/current`）

`src/raser/stages/current.py` 是八环节仿真链的第 3 个环节 `current`。它承接[能量沉积环节（`stages/deposit`）](deposit.md)节点里的电子-空穴对沉积，以及[场求解环节（`stages/field`）](field.md)在 `<器件 project>/field/<节点号>/` 下算好的场节点。本环节用器件文件构造器件模型和插值场，调用[载流子漂移与感应电流（`core/current`）](../core/current.md)让电子-空穴对在电场与权重场中漂移，把各读出电极的时域感应电流写进自己的节点 `nodes/current/<节点号>/`，并为每个作业的前 `plots` 个事例画漂移路径与电流图。感应电流交给下游[电子学读出环节（`stages/readout`）](readout.md)；净感应电荷 `charge` 与初始对数 `pairs` 交给[统计分析环节（`stages/analysis`）](analysis.md)算电荷收集效率。

## 行为

### 跑到感应电流环节，缺的上游自动补上

`raser current`（短命令 `raser cur`）在当前文件夹或给定路径的实验上跑到 `current` 为止，缺的 `field`、`deposit` 节点先补上：

```bash
raser current [路径]
raser cur [路径]
```

`tct` 的 `current` 环节在标准漂移的基础上再与激光时间脉冲卷积，见[瞬态电流技术测试（`bench/tct`）](../bench/tct.md)；本页讲标准仿真链的 `current`。

例如在 `HPK-Si-PiN` 示例上扫 $100\ \text{V}$ 与 $200\ \text{V}$ 两档偏压，每个扫描点跑 $2$ 个作业、每作业记录 $200$ 个事例，只跑到感应电流环节：

```bash
raser current examples/HPK-Si-PiN/signal --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

程序先确认 `examples/HPK-Si-PiN/field/` 里有两档偏压的场节点，没有就在作业开始前补算，存进 `examples/HPK-Si-PiN/field/`；再为 `voltage_100`、`voltage_200` 两个点各算 `deposit` 与 `current` 节点，`points/voltage_100/current/<作业号>`、`points/voltage_200/current/<作业号>` 指向各作业的 `current` 节点。换偏压是重新测，两档偏压各测各的，每点 $2$ 个作业，所以 `deposit`、`current` 各有 $4$ 个节点（每点 $2$ 个）。之后再跑完整的 `raser signal`，这些节点指纹不变，直接复用，只接着算 `readout` 及以后的环节。

### 找到场节点，构造插值场

所需的场在作业开始前补算，存进器件 project 的 `field/`。作业开始时若场还没就绪，作业报错：

```text
FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>`
```

这通常发生在跳过了主命令的自动补算，或场节点被中途改动之后。按提示运行 `raser field` 补齐对应偏压与辐照注量的场，再重跑本命令。

随后本环节取本次运行的辐照注量（`field.irradiation_flux` 不为 `null` 时用它，为 `null` 时取器件文件的 `irradiation_flux`，器件文件没有辐照块时为 $0\ \text{cm}^{-2}$）和偏压（单位 $\text{V}$），调用 `solved_field` 在器件的场里找辐照注量、求解模式和器件参数都对得上、并在该偏压下解过电势和权重场的那一份，构造[场求解与加载（`core/field`）](../core/field.md)的 `DevsimField`，向漂移计算提供插值电场、导电区标志、俘获率、权重电势与一维平面增益接口。找不到时按缺的那一项报错：

```text
FileNotFoundError: no <mode> field of <det_name> at the irradiation flux <flux> in <root> (flux and mode of those solved: <have>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode> --set field.irradiation_flux=<flux>`
ValueError: the field in <folder> was solved for another device (<differing>); solve it again with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
FileNotFoundError: the field in <folder> is not solved at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
FileNotFoundError: the field in <folder> has no weighting field at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>` with the weighting field switched on in the field settings
```

四条依次表示：缺这个辐照注量与模式的场；场是按改动前的器件参数解的；缺目标偏压下的电势；缺目标偏压下的权重场。按报错末尾的 `raser field` 命令补算后重跑；缺权重场时，在 `field` 段打开权重场求解（用 `--set field.<键>=<值>` 改场的设置）。

### 零沉积事例与多位置按探测器过滤

上游 `deposit` 在本作业录得 $0$ 个有效事例时，`current` 随之跳过本作业。

多位置实验（如 `cflm` 的 24 个 pad）按位置分别算感应电流。某个位置在本作业里没有 `detector` 等于该位置的沉积步时，这个位置直接记 $0$ 个事例；同一作业的其他位置照常计算。

沉积文件没有标记提前结束却不含任何记录事例（例如被手动改过），或按 `detector` 过滤后没有沉积步，计算入口报错：

```text
ValueError: <deposits_path> holds no event: there is no current to write
ValueError: <deposits_path> holds no deposit in the detector <detector>: there is no current to write
```

这说明输入的沉积文件为空或已损坏。删掉这个 `deposit` 节点后重跑。

### 逐事例漂移、写出感应电流与单事例绘图

有沉积事例时，本环节用器件文件构造[器件模型（`core/device`）](../core/device.md)的 `Detector`，先删掉同名的旧电流文件（若存在），再逐事例筛选器件边界与电极阵列投影范围内的沉积步（多位置只保留 `detector` 等于该位置的沉积步，只为该位置有沉积的事例写行）。它在 `DevsimField` 中推进载流子漂移、热扩散、辐照俘获衰减及可选的雪崩倍增，按 Shockley-Ramo 定理累计各读出电极的时域感应电流与净感应电荷，逐事例追加写入电流文件。对前 `plots` 个事例，程序清空并重建该事例的绘图子文件夹，画漂移路径图、非零电流电极的波形图，以及（条形或像素器件时）电极收集电荷图。图放在本环节自己的输出里。

全部事例写完后，作业日志汇总各类停止原因的团簇数和载流子数；有团簇停在无场区（`"no_field"`）时打印警告：

```text
<clusters> clusters (<carriers> carriers) stopped where the field has no value, the first in event <event> at x, y, z = <x>, <y>, <z> um: what they would have induced further on is missing
```

这说明漂移路径落到了场网格没覆盖的坐标，后面的感应电流缺了。检查器件尺寸与场网格范围是否一致。

以上例 $200\ \text{V}$ 点作业 `0` 的 `current.h5` 为例：`current` 读入 `deposit` 节点的 `deposit.h5`（$200$ 个事例）和场节点里 $200\ \text{V}$ 的电场与 `top` 电极权重场，写出 `current.h5`，并在节点内 `plots/` 下为前 $100$ 个记录事例各画 `drift_path_<事例号>` 与 `current_<事例号>`（各有 `.png`、`.pdf`、`.root`；`HPK-Si-PiN` 是单电极 `pad` 器件，`charge_per_electrode_<事例号>` 只为条形或像素器件画）。文件属性（`attrs`）为 `dt = 5e-12`（1D 器件默认时间箱宽度，单位 $\text{s}$）和 `electrodes = ['top']`（读出电极名列表），数据集（`datasets`）如下：

| 数据集名 | 示例形状 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | 无 | 记录事例的 Geant4 编号 |
| `t0` | `(200,)` | `float64` | $\text{s}$ | 首个时间箱左边界时刻 |
| `count` | `(200,)` | `int64` | 箱 | 每个事例的时间箱数 |
| `pairs` | `(200,)` | `float64` | 对 | 倍增前的输入电子-空穴对总数 |
| `sensitive_pairs` | `(200,)` | `float64` | 对 | 器件内且电极阵列上方非导电区产生、实际参与漂移的对数 |
| `carriers_without_field` | `(200,)` | `float64` | 个 | 因遇到无场区（`"no_field"`）停止的未俘获载流子总数 |
| `charge` | `(200, 1)` | `float64` | $\text{C}$ | 各电极带符号净感应电荷 |
| `stored` | `(200,)` | `int64` | 个 | 每个事例中存储的非零电流电极数 |
| `index` | `(196,)` | `int64` | 无 | 被存储电极在 `electrodes` 中的下标（$200$ 个事例中有 $196$ 个产生非零电流） |
| `current` | `(245196,)` | `float64` | $\text{A}$ | 所有存储电极按时间箱展开拼接的一维平均感应电流 |

`index` 长度为 `196`，表示 $200$ 个记录事例中有 $196$ 个的感应电流写进了 `current`，其余 $4$ 个在全部时间箱上都为零。下游读取时按 `stored` 与 `count` 切分 `index` 和 `current`，把未存储的电极还原为零。

![HPK-Si-PiN 单事例载流子漂移路径](../../images/current/drift-path-HPK-Si-PiN.png)

`HPK-Si-PiN` 单个事例的载流子漂移路径图，上方为器件三维体区内的轨迹，下方为 $x$-$z$ 平面内的沉积点、电子与空穴轨迹（坐标单位 $\mu\text{m}$）。

![HPK-Si-PiN 单事例感应电流](../../images/current/event-HPK-Si-PiN.png)

`HPK-Si-PiN` 单个事例在 `top` 电极上的感应电流图，分别画出电子分量、空穴分量与总感应电流随时间的变化（横轴单位 $\text{s}$，纵轴单位 $\text{A}$）。

### 复用与重算

`current` 是测量环节，它的指纹包括本环节用到的设置值、器件文件里它用到的部分、上游 `deposit` 与场的节点号，以及种子（由作业种子派生，见[实验、扫描点与种子](../lifecycle/experiments.md#种子)）。指纹相同就复用，不论是在哪个点、哪次运行里算的；改了偏压、注量或 `current.plots`，算成新节点，旧节点留着，改回去时视图指回旧节点。代码版本和节点记录的不一致时只给一条提示，结果照常复用。每个节点单独加锁，写到一半的节点带 `.part` 后缀，写完才改成正式的名字。节点与复用规则见[片与重跑](../lifecycle/slices.md)。

## 规则

### 内置常数

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `STAGES["current"]` | `("cur", "the induced currents, after the deposits and the field", ...)` | 无 | `src/raser/stages/stage_commands.py`：`raser current` 的短命令与帮助说明 |

### 环节命令的解析与启动（`stage_commands.run`）

1. **挂载参数（`register`）**：注册 `current`（别名 `cur`），挂上共用运行参数及本环节命令选项（上游各环节的设置写在各自的段里，见[场求解环节（`stages/field`）](field.md)和[能量沉积环节（`stages/deposit`）](deposit.md)），执行入口绑定为 `partial(run, "current")`。
2. **解析实验**：读实验文件夹的 `config.json`，找到它的实验类。
3. **核对环节**：实验类不含 `current` 环节时退出：

   ```text
   <folder>: the experiment <workflow> has no current slice; its slices: <names>
   ```

4. **启动**：截止环节设为 `current`，进入实验所在 project 的上下文、切到实验文件夹后执行，结束后切回原目录。实验文件夹带 `config.json` 时，命令行里的目标被改写成绝对路径，集群上的作业从实验文件夹重新运行原命令时用它。

### 场定位与插值场构造（`current.solved` 与 `solved_field`）

1. **辐照注量**：取 `my_d.irradiation_flux`（单位 $\text{cm}^{-2}$）；`field.irradiation_flux` 不为 `null` 时改用 `float(irradiation_flux)`。
2. **查找并校验场（`solved_field(my_d, my_d.voltage, flux, mode)`，`mode` 取 `field.mode`）**：
   - 在器件已解过的场里筛选辐照注量等于 `flux`、求解模式等于 `mode` 的；一个都没有时抛出缺注量与模式的 `FileNotFoundError`。
   - 对筛出的场用 `changed` 比对当时读到的器件参数与当前 `my_d`，优先取无差异的；全部有差异时取第一个并抛出 `ValueError: the field in <folder> was solved for another device ...`。
   - `float(my_d.voltage)`（单位 $\text{V}$）不在已解电势的偏压里时，抛出缺电势的 `FileNotFoundError`；不在已解权重场的偏压里时，抛出缺权重场的 `FileNotFoundError`。都通过后返回该场的文件夹。
3. **构造插值场**：返回 `devfield.DevsimField(my_d.device, my_d.voltage, my_d.read_out_contact, irradiation_flux=flux, bounds=my_d.bound, field_directory=folder, interpolation_bins=my_d.device_dict.get("field_interpolation_bins"))`。

### 感应电流计算（`current.currents`）

1. **多位置预检**：给了位置时，读入本作业的沉积；没有任何沉积步的 `detector` 含该位置，直接返回 `{"events": 0}`。
2. **构造器件**：`my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])`。
3. **写出感应电流（`write_induced_currents`）**：
   - 读入沉积；没有事例时抛出 `ValueError(f"{deposits_path} holds no event: there is no current to write")`。
   - 给了 `detector=position` 时，用 `deposits_in(record, detector)` 只留 `record.detector` 等于该位置的沉积步，并滤掉没有沉积步的事例；过滤后为空时抛出 `ValueError(f"{deposits_path} holds no deposit in the detector {detector}: there is no current to write")`。
   - 电流文件已存在时先删掉，再逐事例构造 `CalCurrent(my_d, my_f, record.pairs, positions, keep_drift_paths=(count < plots))`，用 `append_currents` 追加写入；`plots > 0` 时开画前先删掉 `plot_path` 里上次留下的 `current_`、`drift_path_`、`charge_per_electrode_` 开头的图；`count < plots` 时画轨迹图、波形图，以及（`my_d.is_strip` 或 `my_d.is_pixel` 为真时的）各电极电荷图。
   - 全部事例结束后调用 `log_ends(ends, without_field)` 汇总停止原因。

## 软件实现

### 源文件分工

- `src/raser/stages/current.py`：`solved(my_d, kwargs)` 解析运行辐照注量并调用 `solved_field` 构造 `DevsimField`；`currents(kwargs, position=None)` 做多位置预检、构造 `Detector`、拼出输出与绘图路径并调用 `write_induced_currents`。
- `src/raser/stages/chain.py`：定义按需导入 `current` 模块的入口 `_currents` 和作业开始时核对场是否就绪的 `_field`。
- `src/raser/stages/stage_commands.py`：注册各环节命令；解析目标实验，核对实验含目标环节，设截止环节并切入实验文件夹执行。
- `src/raser/stages/files.py`：给出本环节在当前作业下的输出文件路径。

### 核心数据结构

`currents(kwargs, position=None)` 与 `solved(my_d, kwargs)` 从运行字典 `kwargs` 读取：

| `kwargs` 键名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `"det_name"` | `str` | 无 | 当前器件名称 |
| `"_files"` | `dict` | 无 | 组件文件内容，`kwargs["_files"]["device"]` 是已写入本次偏压（单位 $\text{V}$）的器件 JSON 字典 |
| `"irradiation_flux"` | `float \| None` | $\text{cm}^{-2}$ | 本次运行的辐照注量（$1\ \text{MeV}$ 中子等效注量）；为 `None` 时 `solved` 取 `my_d.irradiation_flux` |
| `"plots"` | `int` | 事例（个） | 每个作业画单事例漂移路径与电流图的事例数上限 |

## 接口

### 选项与配置键

本环节能设的只有下表这些；截止环节、传给 `CalCurrent` 的热扩散开关 `diffusion=True` 和绘图文件名都写死在代码里。`--set`、`--scan` 用“段.键”作地址，如 `--set field.voltage=100`。共用运行参数（`-s`、`--seed`、`--same-seeds`、`--set`、`--scan`、`-b`、`-t`、`-mem`、`--dry-run`）见[命令行接口（`raser`）](../cli.md)和[实验、扫描点与种子](../lifecycle/experiments.md)；上游各环节的设置写在各自的段里，见[场求解环节（`stages/field`）](field.md)和[能量沉积环节（`stages/deposit`）](deposit.md)；器件几何、电极、温度、材料、掺杂、辐照模型与雪崩倍增键见[载流子漂移与感应电流（`core/current`）](../core/current.md)。配置键的“示例里的值”是 `examples/HPK-Si-PiN/signal/config.json` 写的值，括号里是别的示例写的不同值；`config.json` 缺了要用的键时报错，指出缺的“段.键”。

| 段.键或命令行选项 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `[路径]` | 当前文件夹 | 无 | 实验文件夹 |
| `current.plots` | `100`（`timeres`、`bmos`、`cflm` 示例为 `0`） | 事例（个） | 每个作业画 `current` 自己的图：漂移路径、电极电流和（条形/像素器件）收集电荷图的事例数上限，$\le 0$ 时不画；漂移路径用 `deposit` 交来的沉积列表画。多位置实验中每个位置各自从该位置有沉积的事例数起；改它让 `current` 及下游重算 |
| `field.voltage` | `200.0`（写 `null` 时取器件文件里的偏压） | $\text{V}$ | 器件偏压，属于 `field` 段；决定取哪一档偏压的场，改它会让场、`current` 及下游重算 |
| `field.irradiation_flux` | `null`（取器件文件里的辐照注量，器件文件没有辐照块时为 `0`） | $\text{cm}^{-2}$ | 器件辐照注量（$1\ \text{MeV}$ 中子等效注量），属于 `field` 段；决定取哪一个注量的场，改它会让场、`current` 及下游重算 |
| 器件文件键 `field_interpolation_bins` | 不写（`DevsimField` 取 `{"x": 30, "y": 30, "z": 30}`） | 箱（个） | 构造 `DevsimField` 时三维非结构化场反距离加权插值网格各轴的箱数 |

### 读写的文件

- **读：`deposit` 节点里的 `deposit.h5`**。`current` 从中读记录事例的 Geant4 编号 `event`、沉积步所属逻辑体名 `detector`、局部坐标 `x`/`y`/`z`（$\mu\text{m}$）、全局时间 `t`（$\text{s}$）及电子-空穴对数 `pairs`（对）；格式见[能量沉积环节（`stages/deposit`）](deposit.md)。
- **读：`<器件 project>/field/<节点号>/` 里的场节点**。由 `raser field` 写出。`DevsimField` 读 `Potential_<V>V.pkl`、`Conductive_<V>V.pkl`、`NetDoping_0V.pkl`（TCAD 导入为 `NetDoping_<V>V.pkl`）、`TrappingRate_n_<V>V.pkl`、`TrappingRate_p_<V>V.pkl` 及 `weightingfield/<电极>/Potential_<V>V.pkl`；各文件的数据结构与单位见[场求解与加载（`core/field`）](../core/field.md)。
- **写：`nodes/current/<节点号>/current.h5`**（多位置实验里同节点下每个位置一个文件 `current.<位置>.h5`）。上游 `deposit` 有记录事例、且（多位置实验中）该位置本作业有沉积步时写出，重算前先删旧文件再逐事例追加。它交给 `readout` 求输出波形，`charge`（$\text{C}$）与 `pairs`（对）也交给 `analysis` 算电荷收集效率；HDF5 属性（`electrodes`、`dt`［$\text{s}$］）与全部数据集的形状、类型与单位见[载流子漂移与感应电流（`core/current`）](../core/current.md)。
- **写：`nodes/current/<节点号>/plots/` 里的单事例图**。`plots > 0` 时为前 `plots` 个事例写出（写前先删掉这个文件夹里上次留下的同类图），每张图有 `.png`、`.pdf`、`.root` 三份：三维与 $x$-$z$ 平面漂移路径图 `drift_path_<事例号>`（坐标单位 $\mu\text{m}$）、电流分量波形图 `current_<事例号>`（多个读出电极时各非零电流电极一张 `current_<事例号>_electrode_<k>`，`<k>` 从 `1` 起；横轴 `Time [ns]`、纵轴 `Current [μA]`），以及条形（`strip`）或像素（`pixel`）器件的各电极电荷图 `charge_per_electrode_<事例号>`（数值为各电极的净电荷，单位 $\text{fC}$）；内容与坐标单位见[载流子漂移与感应电流（`core/current`）](../core/current.md)。
- **写：`nodes/current/<节点号>/node.json`**。记下本节点的输入，以及代码版本、运行环境和运行状态。
- **写：`points.json` 与 `points/<点名>/current/<作业号>`**。参数表记各点 `current` 用的节点号；视图软链接指向 `../../../nodes/current/<节点号>`。
