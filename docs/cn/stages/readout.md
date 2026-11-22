# 电子学读出环节（`stages/readout`）

`src/raser/stages/readout.py` 是八环节仿真链的第 4 个环节 `readout`，由 `raser readout`（短命令 `raser rdo`）或测试、应用的实验命令调度。它承接[载流子输运与感应电流环节（`stages/current`）](current.md)节点里的电极感应电流，以及[场求解环节（`stages/field`）](field.md)在 `<器件 project>/field/<节点号>/` 下的场节点给出的器件电路参数。本环节调用[场求解与加载（`core/field`）](../core/field.md)组装器件等效电路，调用[电子学读出（`core/readout`）](../core/readout.md)加载前端放大器链、判定各输出通道的脉冲方向、求解每个事例的瞬态输出电压波形并叠加电路热噪声，把波形写进自己的节点 `nodes/readout/<节点号>/`。写出的波形交给下游[数字化环节（`stages/digitizer`）](digitizer.md)按示波器或数字化板的采样和量化变成数字波形。

## 行为

### 器件等效电路与前端波形

本环节把各电极的感应电流送进器件等效电路和 `amplifier` 指定的前端放大器链，算出每个事例各输出通道的电压波形、器件电路参数记录及脉冲方向（`"rising"` 或 `"falling"`），写进波形文件。`readout` 有自己的种子，由作业的种子派生（见[实验、扫描点与种子](../lifecycle/experiments.md#种子)），管 NGspice 的噪声抽样，和 `deposit`、`current` 的种子一样进本环节节点的指纹；只有带种子的运行为每个被存储的通道独立抽样叠加时域热噪声。每个事例只存最大绝对电压摆幅不小于该事例最大通道摆幅 `1e-3` 倍的输出通道；没有非零感应电流的事例存 `0` 个通道。

例如在 `HPK-Si-PiN` 示例上扫两档偏压：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --set deposit.events_per_job=200 --seed 1
```

`work/` 下没有 `HPK-Si-PiN` 时，命令在 `examples/HPK-Si-PiN/` 下就地运行，实验文件夹是 `examples/HPK-Si-PiN/signal`。`HPK-Si-PiN` 是常规单电极平面器件，器件文件直接给出 `capacitance_pF = 3.44162280284`（`3.44162280284e-12 F`），器件文件里的偏压为 `200 V`。`voltage_200` 点用示例里的放大器链 `SantaCruz+Gali52+Termination50`，`points/voltage_200/readout/0` 指向的节点里，作业 `0` 的 `readout.h5` 属性（`attrs`）为：

- `dt = 5e-12`（单位 `s`）
- `electrodes = ['top']`
- `pulse_edge = ['falling']`
- `device_circuit = '{"junction_capacitance": {"farad": 3.44162280284e-12, "from": "device file"}, "between_electrodes": null, "bias_resistance": null, "coupling_capacitance": null, "undepleted_layer": null}'`

数据集（`datasets`）如下：

| 数据集名 | 示例形状 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `event` | `(200,)` | `int64` | 无 | 记录事例的 Geant4 编号 |
| `t0` | `(200,)` | `float64` | `s` | 首个时间箱左边界时刻 |
| `count` | `(200,)` | `int64` | 箱 | 每个事例的波形采样点数 |
| `stored` | `(200,)` | `int64` | 个 | 每个事例中存储波形的电极数 |
| `index` | `(196,)` | `int64` | 无 | 被存储电极在 `electrodes` 中的下标 |
| `voltage` | `(245196,)` | `float64` | `V` | 按事例与存储电极依次拼接的时间箱中心输出电压 |

`device_circuit` 显示结电容直接取自器件文件（`"from": "device file"`）；`undepleted_layer` 为 `null`，说明 `200 V` 下器件已全耗尽。`pulse_edge` 为 `['falling']`，因为 `top` 电极加 `+200 V` 收集电子，两级放大器串联后净极性同相，输出脉冲向下走。`200` 个记录事例中 `index` 长度为 `196`，说明有 `4` 个事例在 `top` 电极上的感应电流全为零，它们的 `stored` 为 `0`，其余 `196` 个事例的波形依次拼接在 `voltage` 中。

### 跑到读出环节，上游节点在各点之间共用

`raser readout`（或 `raser rdo`）在当前文件夹或给定路径的实验上跑到 `readout` 为止，缺的 `field`、`deposit`、`current` 节点先补上：

```bash
raser readout [路径]
raser rdo [路径]
```

放大器链只有 `readout` 读。在上面的实验上再扫两条放大器链：

```bash
raser rdo examples/HPK-Si-PiN/signal --scan field.voltage=100,200 --scan readout.amplifier=SantaCruz+Gali52+Termination50,BroadBandCividec+Termination50 -s 2 --seed 1
```

扫描只影响下游的设置时，上游节点在各点之间共用。`deposit`、`current` 仍是两档偏压各 $2$ 个作业、共 $4$ 个节点，指纹没变，直接复用；`readout` 是两档偏压乘两条链、每点 $2$ 个作业，共 $8$ 个节点，其中 `SantaCruz+Gali52+Termination50` 的 $4$ 个已经算过，只为 `BroadBandCividec+Termination50` 新算 $4$ 个。下游的 `digitizer`、`trigger`、`reconstruction` 读 `readout` 的节点号，同样各有 $8$ 个节点；`analysis` 每个扫描点一个节点，共 $4$ 个。节点只增不减，把链改回去时视图指回原来的节点。代码版本和节点记录的不一致时只给一条提示，结果照常复用。每个节点单独加锁，写到一半的节点带 `.part` 后缀。节点与复用规则见[片与重跑](../lifecycle/slices.md)。

### 上游零事例与多位置空电流

上游 `deposit` 在本作业录得 `0` 个有效事例时，`readout` 随之跳过本作业。多位置实验里某个位置本作业没有沉积步、也就没有电流文件时，这个位置直接记 `0` 个事例；同一作业的其他位置照常计算。

### 画原理图和冲击响应

`raser readout --draw <对象>` 画本环节的对象：前端电路的原理图和冲击响应。前端电路图和冲击响应只取决于电路和它的参数，是资产，放在 `work/<电路名>/` 下，被各实验的 `readout` 引用。

阻性层器件（器件文件有 `resistive_layer`）另有一个对象 `network`：`raser readout --draw network [路径]` 只解器件电路与 `readout.amplifier` 的放大器链，不读 `deposit` 和 `current` 的结果。冲击的位置是器件上的一个点，用几何坐标 $(x, y)$ 给出，单位 $\mu\text{m}$，坐标系与 `current` 相同（$0 \le x \le l_x$，$0 \le y \le l_y$）；条形器件只用 $x$。$1\ \text{fC}$ 的电荷在第一个时间箱里以矩形电流脉冲注入这一点，按它到相邻晶胞中心的距离线性分给这些晶胞的节点；时间箱宽 $10\ \text{ps}$、共 $2000$ 箱；方阻取 `readout.sheet_resistance`，没有时取器件文件。给出 `--at <x>,<y>` 时冲击这一点，`network_waveforms.png` 画每个读出电极（条或焊盘）的输出波形；不给时沿 $x$ 以晶胞宽度为步长扫过器件中线（$y = l_y/2$），`network_waveforms.png` 画扫描中点那一个冲击点的波形，另画 `network_sharing.png`：各读出电极的波形幅度和波形积分随冲击点 $x$ 的曲线。两种情形都画 `network_schematic.png`：器件网络的电路图，标上各元件的数值。

## 规则

### 内置常数

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `STAGES["readout"]` | `("rdo", "the waveforms of the electronics, after all before them", ...)` | 无 | `src/raser/stages/stage_commands.py`：`raser readout` 的短命令、帮助说明与参数挂载函数 |
| `PART_EDGE` | `1e-3` | 无量纲 | `src/raser/core/readout/job.py`：`write_waveforms` 保存输出通道、以及条形行局部电路扩展收敛判定用的相对最大电压摆幅阈值 |

### 环节命令的解析与启动（`stage_commands.run`）

1. **挂载参数（`register`）**：注册 `readout`（别名 `rdo`），挂上共用运行参数及本环节命令选项（上游各环节的设置写在各自的段里，见[场求解环节（`stages/field`）](field.md)、[能量沉积环节（`stages/deposit`）](deposit.md)和[载流子输运与感应电流环节（`stages/current`）](current.md)），执行入口设为 `partial(run, "readout")`。
2. **解析实验**：读实验文件夹的 `config.json`，找到它的实验类。
3. **核对环节**：实验类不含 `readout` 环节时退出：

   ```text
   <folder>: the experiment <workflow> has no readout slice; its slices: <names>
   ```

4. **启动**：截止环节设为 `readout`，进入实验所在 project 的上下文、切到实验文件夹后执行，结束后切回原目录。实验文件夹带 `config.json` 时，命令行里的目标被改写成绝对路径，集群上的作业从实验文件夹重新运行原命令时用它。

作业开始时器件的场还没就绪，作业报错：

```text
FileNotFoundError: no field of <det_name> ready for this run: solve it with `raser field <det_name>`
```

按提示先运行 `raser field <det_name>` 补齐场，再重跑。

### 读出计算（`readout.waveforms`）

1. **多位置预检**：给了位置且该位置本作业没有电流文件时，直接返回 `{"events": 0}`。
2. **构造器件与电极名**：
   - `my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])`（器件文件键见[探测器组件（`components/device`）](../components/device.md)）。
   - `electrodes = electrode_names(my_d.read_out_contact, my_d.read_ele_num)`，命名规则见[载流子漂移与感应电流（`core/current`）](../core/current.md)。
   - `part_of = None`，`sheet_ohm = kwargs.get("sheet_resistance")`。
3. **组装器件等效电路**：
   - **器件文件有 `resistive_layer`（阻性层器件）**：
     1. `my_d.is_pixel` 为真时取 `build = device_grid`（二维阻性网格），否则取 `build = device_row`（一维阻性行）。
     2. `circuit, values = build(my_d, electrodes, sheet_ohm=sheet_ohm)`：方阻依次按 `sheet_ohm` 非 `None`（来源记 `"chosen"`）→ `resistive_layer["sheet_resistance"]`（`"device file"`）→ 铝注入层参数推算（`"implanted layer"`）选取；单元电容依次按 `capacitance_pF`（`"device file"`）→ 器件平板电容估算（`"parallel plate"`）选取。
   - **没有阻性层却给了 `sheet_ohm`**：抛出

     ```text
     ValueError: <det_name> has no resistive layer to give a sheet resistance of <sheet_ohm> Ohm
     ```

     去掉 `readout.sheet_resistance` 的设置或扫描后再运行。
   - **常规器件**：
     1. **辐照注量**：取 `my_d.irradiation_flux`（$\text{cm}^{-2}$）；`field.irradiation_flux` 不为 `null` 时改用 `float(irradiation_flux)`。
     2. **找场（`solved_field(my_d, my_d.voltage, flux, mode)`）**：在器件已解过的场里筛选辐照注量等于 `float(flux)`、求解模式等于 `field.mode` 的，再用 `changed` 比对器件参数，并检查该偏压下解过电势与权重场。找不到时分别抛出：

        ```text
        FileNotFoundError: no <mode> field of <det_name> at the irradiation flux <flux> in <root> (flux and mode of those solved: <have>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode> --set field.irradiation_flux=<flux>`
        ValueError: the field in <folder> was solved for another device (<differing>); solve it again with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
        FileNotFoundError: the field in <folder> is not solved at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>`
        FileNotFoundError: the field in <folder> has no weighting field at <voltage> V (solved at: <solved>); solve it with `raser field <det_name> --set field.voltage=<voltage> --set field.mode=<mode>` with the weighting field switched on in the field settings
        ```

        四条依次表示：缺这个注量与模式的场；场是按改动前的器件参数解的；缺该偏压的电势；缺该偏压的权重场。按报错末尾的命令补算；缺权重场时，在 `field` 段打开权重场求解（用 `--set field.<键>=<值>` 改场的设置）。
     3. **读场里的电路参数（`row, solved_f, undepleted = field_circuit(folder, my_d)`）**：
        - `my_d.is_strip and len(my_d.read_out_contact) == 1 and my_d.read_ele_num > 1`（单读出接触重复排布的条形行）：读 `weightingfield/<electrode>/Capacitance_<bias>V.json` 为 `row`，`solved_f = None`。文件不存在时抛出

          ```text
          FileNotFoundError: the field in <folder> has no capacitances between the strips of <det_name> at <voltage> V: <path> is missing, and the readout of a row of strips needs it. A field solved by raser stores it with its weighting field: switch the weighting field on in the field settings. A field imported from TCAD does not store it yet, so the strips of an imported field cannot be read out
          ```

          这个文件随 DEVSIM 解的权重场写出；在 `field` 段打开权重场求解（用 `--set field.<键>=<值>` 改场的设置），由 DEVSIM 解权重场。
        - `row is None` 时：该偏压解过电容，就从 `<float(voltage)>V.cv.json` 取 `specific_capacitance_pF * area_factor * 1e-12`（$\text{F}$）作 `solved_f`；否则 `solved_f = None`。
        - `solved_undepleted(Path(folder), my_d.voltage, undepleted_area_cm2(my_d))` 读 `<float(voltage)>V.undepleted.json`。该偏压没存未耗尽层时抛出

          ```text
          FileNotFoundError: the field in <folder> has no undepleted bulk at <voltage> V (solved at: <solved>): solve it with `raser field <det_name> --set field.voltage=<voltage>`
          ```

     4. **组装电路（`circuit, values = device_circuit(my_d, electrodes, solved_f, row=row, solved_undepleted=undepleted)`）**：
        - 读器件文件的 `bias_resistance_ohm`（$\Omega$）与 `coupling_capacitance_pF * 1e-12`（$\text{F}$）。给了耦合电容没给偏置电阻时抛出

          ```text
          ValueError: A coupling capacitance needs a bias resistance: without it the electrode has no DC potential
          ```

          在器件文件里补上 `bias_resistance_ohm`。
        - 未耗尽层参数 `undepleted_layer_of(my_d, undepleted)`：器件文件里 `undepleted_resistance_ohm` 与 `undepleted_capacitance_pF` 只给了一项时抛出

          ```text
          ValueError: <det_name> gives <key> alone: the undepleted layer has both undepleted_resistance_ohm and undepleted_capacitance_pF
          ```

          两项都给时取器件文件值（来源记 `"device file"`），否则取场里的 `undepleted`（`"field"`）。
        - 结电容 `junction_capacitance` 依次按器件文件 `capacitance_pF * 1e-12`（`"device file"`）→ 场电容（`row is None` 时为 `solved_f`，否则为 `float(row["total"]) * float(my_d.l_y) * 1e-4`，记 `"field"`）→ 器件平板估算 `my_d.capacitance * 1e-12`（`"parallel plate"`）选取。三者都没有时抛出

          ```text
          ValueError: <det_name> has no capacitance: its device file gives none, its field was not asked for one, and the device has no estimate
          ```

          在器件文件里补 `capacitance_pF`，或在 `field` 段打开 CV 求解（用 `--set field.<键>=<值>` 改场的设置）解电容。
        - `row` 非 `None` 时要求 `row["unit"] == "F/cm"`，否则抛出 `ValueError: The capacitances of the row are in <unit>`。通过后按条长 `l_y * 1e-4`（$\text{cm}$）换算近邻条间互容、组装 `row_of_electrodes`，并定义 `part_of(hit, margin) = part_of_row(my_d, electrodes, hit, margin, solved_f, row)`。
4. **放大器链与脉冲方向**：
   - `chain = named_chain(str(kwargs["amplifier"]))` 按 `"+"` 拆开 `amplifier`，从组件目录依次加载 `readout/<part>.cir`（子电路语法与内置组件见[前端读出电路组件（`components/readout`）](../components/readout.md)）。找不到时抛出 `FileNotFoundError: Cannot find RASER component readout/<part>.cir:`，检查子电路名的拼写，或确认文件放进了 `readout/`。
   - `pulse_edges(my_d, chain, list(circuit.outputs))` 给出与 `circuit.outputs` 一一对应的脉冲方向。
5. **求解并写出（`write_waveforms`）**：先删掉同路径的旧波形文件，再逐事例求瞬态电压、按种子叠加时域热噪声、筛掉最大绝对摆幅 `< 1e-3 * largest` 的通道后写出。

## 软件实现

### 源文件分工

- `src/raser/stages/readout.py`：`waveforms(kwargs, position=None)` 做多位置预检，构造 `Detector` 与电极名，按有无 `resistive_layer` 组装器件等效电路，加载前端子电路链，判定脉冲方向并调用 `write_waveforms`。
- `src/raser/stages/chain.py`：定义按需导入 `readout` 模块的入口 `_waveforms`。
- `src/raser/stages/stage_commands.py`：注册各环节命令；解析目标实验，核对实验含目标环节，设截止环节并切入实验文件夹执行。
- `src/raser/stages/files.py`：给出各环节在当前作业下的输入输出文件路径。

### 核心数据结构

`readout.waveforms(kwargs, position)` 从 `kwargs` 读取：

| 键名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `"det_name"` | `str` | 无 | 当前器件名称 |
| `"_files"` | `dict` | 随器件键 | 组件文件内容，`_files["device"]` 是已写入本次偏压的器件配置字典 |
| `"amplifier"` | `str` | 无 | 以 `"+"` 连接的前端放大器与末级负载子电路链 |
| `"sheet_resistance"` | `float \| None` | $\Omega$ | 阻性层器件的方阻覆盖值 |
| `"irradiation_flux"` | `float \| None` | $\text{cm}^{-2}$ | 本次运行的辐照注量（`field.irradiation_flux`，$1\ \text{MeV}$ 中子等效注量）；为 `None` 时取 `my_d.irradiation_flux` |
| `"seed"` | `int \| None` | 无 | 热噪声的随机种子；无种子的工作流（如 `tct`）为 `None`，不叠加噪声 |

组装器件等效电路返回的 `values`（序列化写进波形文件的 `device_circuit` 属性）：

| 键名 | 适用器件与结构 | 单位 | 含义 |
| --- | --- | --- | --- |
| `"junction_capacitance"` | 常规器件：`{"farad": float, "from": str}` | $\text{F}$ | 单电极耗尽层结电容及来源（`"device file"`、`"field"` 或 `"parallel plate"`） |
| `"between_electrodes"` | 常规器件：`{"farad": list[float], "from": "field"} \| None` | $\text{F}$ | 条形行与第 $1, \dots, N$ 近邻单侧条间的耦合电容（非条形行为 `null`） |
| `"bias_resistance"` | 常规器件：`{"ohm": float} \| None` | $\Omega$ | 单电极偏置电阻（未配置为 `null`） |
| `"coupling_capacitance"` | 常规器件：`{"farad": float} \| None` | $\text{F}$ | 单电极交流耦合电容（未配置为 `null`） |
| `"undepleted_layer"` | 常规器件：`{"ohm": float, "farad": float, "from": str} \| None` | $\Omega$, $\text{F}$ | 未耗尽层并联电阻、电容及来源（已全耗尽为 `null`） |
| `"cell_capacitance"` | 阻性层器件：`{"farad": float, "from": str}` | $\text{F}$ | 阻性层单个网格单元对背面的电容及来源 |
| `"sheet_resistance"` | 阻性层器件：`{"ohm": float, "from": str}` | $\Omega$ | 阻性层方阻及来源（`"chosen"`、`"device file"` 或 `"implanted layer"`） |
| `"coupling_per_area_f_m2"` | 阻性层器件：`float \| None` | $\text{F/m}^2$ | 读出条或焊盘下方介质层的单位面积耦合电容（直连时为 `null`） |

## 接口

### 选项与配置键

本环节能设的只有下表这些；保存通道的相对摆幅阈值 `PART_EDGE = 1e-3`、频域噪声分析的频段与温度都写死在代码里。`--set`、`--scan` 用“段.键”作地址，如 `--set readout.amplifier=BroadBandCividec+Termination50`。共用运行参数（`-s`、`--seed`、`--same-seeds`、`--set`、`--scan`、`-b`、`-t`、`-mem`、`--dry-run`）见[命令行接口（`raser`）](../cli.md)和[实验、扫描点与种子](../lifecycle/experiments.md)；上游各环节的设置写在各自的段里，见[能量沉积环节（`stages/deposit`）](deposit.md)和[载流子输运与感应电流环节（`stages/current`）](current.md)。配置键的“示例里的值”是 `examples/HPK-Si-PiN/signal/config.json` 写的值；`config.json` 缺了要用的键时报错，指出缺的“段.键”。器件文件键一行写的是器件文件里的写法。

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `[路径]` | 当前文件夹 | 无 | 实验文件夹 |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `"+"` 连接的 `readout/<名称>.cir` 子电路链，前几项是双端口放大级，末项是单端口负载 |
| `readout.sheet_resistance` | `null`（取器件文件里阻性层的方块电阻） | $\Omega$ | 覆盖阻性层器件的方阻；对常规器件给出会抛出 `ValueError` |
| `field.voltage` | `200.0`（写 `null` 时取器件文件里的偏压） | $\text{V}$ | 属于 `field` 段：偏压，用来找场并判定收集电荷的极性 |
| `field.irradiation_flux` | `null`（取器件文件里的辐照注量，器件文件没有辐照块时为 `0`） | $\text{cm}^{-2}$ | 属于 `field` 段：找场时用的辐照注量 |
| 器件文件键 `read_out_contact`、`read_ele_num`、`electrodes`、`l_y`、`p_x`、`p_y`、`x_ele_num`、`y_ele_num` | 见 `components/device` 页 | $\mu\text{m}$ / 个 | 决定读出电极名称、布局（`"pad"`、`"strip"`、`"pixel"`）、条长与网格单元尺寸 |
| 器件文件键 `capacitance_pF` | 无（可选） | $\text{pF}$ | 直接给出的单电极耗尽层结电容（或阻性层单元电容），优先于场电容与平板估算 |
| 器件文件键 `bias_resistance_ohm` | 不写（可选） | $\Omega$ | 常规器件单电极偏置电阻；给了 `coupling_capacitance_pF` 时必须给 |
| 器件文件键 `coupling_capacitance_pF` | 不写（可选） | $\text{pF}$ | 常规器件单电极交流耦合电容 |
| 器件文件键 `undepleted_resistance_ohm`、`undepleted_capacitance_pF` | 不写（可选） | $\Omega$, $\text{pF}$ | 常规器件未耗尽层并联电阻与电容，必须成对给出；不给时从场里读 |
| 器件文件键 `resistive_layer` | 无（可选） | $\Omega$, $\text{cm}^{-2}$, $\mu\text{m}$, $^\circ\text{C}$ | 阻性层配置块，含方阻 `sheet_resistance`（或铝注入参数 `implanted`、`thickness`、`anneal`）、读出条 `strips` 或焊盘 `pads`、接地接触 `grounded` 及可选介质层 `coupling`（`thickness`、`permittivity`） |

### 读写的文件

- **读：`<器件 project>/field/<节点号>/` 场节点里的电路文件**（`<V>V.cv.json`、`<V>V.undepleted.json`、`weightingfield/<electrode>/Capacitance_<bias>V.json`）。常规器件从中取结电容、未耗尽层的 RC 参数和条形行的条间互容；格式见[场求解与加载（`core/field`）](../core/field.md)。
- **读：`current` 节点里的 `current.h5`**（多位置实验里每个位置一个 `current.<位置>.h5`）。取 `electrodes`、`dt`（$\text{s}$）和逐事例感应电流；格式见[载流子漂移与感应电流（`core/current`）](../core/current.md)。
- **写：`nodes/readout/<节点号>/readout.h5`**（多位置实验里同节点下每个位置一个文件 `readout.<位置>.h5`）。上游有记录事例、且（多位置下）该位置有电流文件时写出，先删旧文件再逐事例追加。底层读写函数见[电子学读出（`core/readout`）](../core/readout.md)，HDF5 属性与数据集如下：

  | 类别 | 名称 | 形状与类型 | 单位 | 含义 |
  | --- | --- | --- | --- | --- |
  | 属性（`attrs`） | `dt` | 标量，`float64` | $\text{s}$ | 采样时间箱宽度 |
  | 属性（`attrs`） | `electrodes` | `(outputs,)`，变长字符串数组 | 无 | 电路全部可能输出的读出通道名 |
  | 属性（`attrs`） | `pulse_edge` | `(outputs,)`，变长字符串数组 | 无 | 与 `electrodes` 一一对应的脉冲方向，`"rising"` 或 `"falling"` |
  | 属性（`attrs`） | `device_circuit` | 标量，JSON 字符串 | $\text{F}$, $\Omega$, $\text{F/m}^2$ | 器件等效电路各参数值及来源（结构见上文 `values` 表） |
  | 数据集（`datasets`） | `event` | `(events,)`，`int64` | 无 | 记录事例的 Geant4 编号 |
  | 数据集（`datasets`） | `t0` | `(events,)`，`float64` | $\text{s}$ | 每个事例首个时间箱的左边界时刻 |
  | 数据集（`datasets`） | `count` | `(events,)`，`int64` | 箱 | 每个事例的波形采样点数 |
  | 数据集（`datasets`） | `stored` | `(events,)`，`int64` | 个 | 该事例存储波形的通道数（无电流事例为 `0`） |
  | 数据集（`datasets`） | `index` | `(sum(stored),)`，`int64` | 无 | 被存储通道在 `electrodes` 中从 `0` 起的下标，按 `stored` 切分到各事例 |
  | 数据集（`datasets`） | `voltage` | `(sum(stored * count),)`，`float64`（`gzip` 压缩） | $\text{V}$ | 按事例和存储通道依次展开的时间箱中心输出电压，每通道占所属事例的 `count` 个点 |

- **写：`nodes/readout/<节点号>/node.json`**。记下本节点的输入，以及代码版本、运行环境和运行状态。
- **写：`points.json` 与 `points/<点名>/readout/<作业号>`**。参数表记各点 `readout` 用的节点号；视图软链接指向该节点。
- **写：`<器件 project>/network/<节点号>/`**（只在 `--draw network` 时）。`network.h5`、`node.json`，以及 `plots/` 下的 `network_schematic.png`、`network_waveforms.png` 和扫描时的 `network_sharing.png`；`network.h5` 的属性 `dt`（$\text{s}$）、`charge`（$\text{C}$）、`electrodes` 与 `device_circuit`，数据集 `point` 形状为 `(points, 2)`，单位 $\mu\text{m}$，是各冲击点的 $(x, y)$，数据集 `voltage` 形状为 `(points, outputs, bins)`，单位 $\text{V}$，是冲击各点时各读出电极在时间箱中心的输出电压。
