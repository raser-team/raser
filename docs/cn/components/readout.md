# 前端读出电路组件（`components/readout`）

前端读出电路组件是 SPICE 子电路文件（`.cir`，存放在 `components/readout/` 下，见 [架构总纲](../architecture.md#组件)），承接 [`current`](../stages/current.md)（[`core/current`](../core/current.md)）输出的电极感应电流以及 [`field`](../stages/field.md)（[`core/field`](../core/field.md)）和 [探测器组件](device.md) 给出的器件等效电路 `DeviceCircuit`。[`readout`](../stages/readout.md) 环节（[`core/readout`](../core/readout.md)）按 `+` 连接的顺序读取各级 `.cir` 文件，将它们串成放大器与终端负载链，接在器件等效电路后面交给 `ngspice` 求解瞬态响应与频域热噪声，得到的输出电压波形交给 [`digitizer`](../stages/digitizer.md)（[`core/digitizer`](../core/digitizer.md)）。

```mermaid
flowchart LR
    CUR["感应电流 (current)"] --> DEV["器件电路 (来自器件文件与 field)"]
    DEV --> S1["SantaCruz (.cir)"]
    S1 --> S2["Gali52 (.cir)"]
    S2 --> LOAD["Termination50 (.cir)"]
    LOAD --> OUT["输出电压波形 (交给 digitizer)"]
```

查找组件时，project 文件夹里自己的组件优先，找不到再到组件库按名字找。

## 组件文件原文

下面是默认前端链 `SantaCruz+Gali52+Termination50` 上三级组件的 `.cir` 原文与对应原理图：

### `SantaCruz`

```spice
.subckt SantaCruz in out
VCC 8 0 dc 2.25
R13 in 0 1MEG
C1 in 3 3.3n
x1 5 3 0 BFR840L3RHESD ; npn
R1 3 4 475
R2 4 5 3k
C2 4 5 3.3n
C5 5 out 3.3n
L1 5 6 47U
R3 6 7 63.7
C7 8 0 10n
C8 7 0 10n
C3 7 0 1n
C4 7 0 1n
L2 8 7 2.2u
.ends SantaCruz
```

![SantaCruz 原理图](../images/afe-schematic-SantaCruz.png)

`SantaCruz` 放大级原理图：信号从 `in` 经 `C1`（`3.3 nF`）到 `x1` 基极，从集电极经 `C5`（`3.3 nF`）到 `out`；`R13`（`1 MOhm`）把输入端直流接地；`R1`（`475 Ohm`）与 `R2`（`3 kOhm`）$\parallel$ `C2`（`3.3 nF`）串联从集电极接回基极构成跨阻反馈；`VCC`（`2.25 V`）经 `L2`（`2.2 uH`）、`R3`（`63.7 Ohm`）、`L1`（`47 uH`）供电，`L1` 阻挡高频信号进入电源，`C3`（`1 nF`）、`C4`（`1 nF`）、`C7`（`10 nF`）、`C8`（`10 nF`）去耦；`x1` 引用同一文件里主子电路之前的 `BFR840L3RHESD` 子电路与 `.MODEL` 定义。

### `Gali52`

```spice
.subckt Gali52 in out
Rin in 0 50
* minus twice 10^(22.66/20): the 50 Ohm output and the 50 Ohm load halve it
E1 a 0 in 0 -27.17
Rp a b 1
Cp b 0 112.9p
E2 c 0 b 0 1
Rout c out 50
.ends Gali52
```

![Gali52 原理图](../images/afe-schematic-Gali52.png)

`Gali52` 放大级原理图：`E1` 是反相增益 `-27.17` 的压控电压源（经 `50 Ohm` 输出电阻 `Rout` 与 `50 Ohm` 负载分压后等效增益为 `-13.585`，即 `22.66 dB`），`Rp`（`1 Ohm`）与 `Cp`（`112.9 pF`）构成 $1/(2\pi R_p C_p) = 1.41\ \text{GHz}$ 的单极点低通滤波，`E2`（增益 `1`）隔离缓冲后经 `Rout` 输出，输入电阻 `Rin` 与输出电阻 `Rout` 各为 `50 Ohm`。

### `Termination50`

```spice
.subckt Termination50 in
R1 in 0 50
.ends Termination50
```

![Termination50 原理图](../images/afe-schematic-Termination50.png)

`Termination50` 终端负载原理图：`50 Ohm` 接地电阻 `R1`，作为读出链的最后一级，只含单输入端口 `in`。

## 键的含义

前端电路组件是 `.cir` 文本文件，使用者能定义和修改的是子电路端口、主子电路内的 SPICE 元件行、主子电路外的辅助模型（`.subckt` 与 `.MODEL`）以及行尾 `;` 后的原理图布局提示；`readout.amplifier` 是槽位，由几级串成，组件里的量按“段.槽位.级名.元件名”寻址：在实验 `config.json` 或命令行 `--set`、`--scan` 中用 `readout.amplifier.<放大级名>.<元件名>`（如 `readout.amplifier.SantaCruz.R1`）覆盖或扫描主子电路内元件的数值。换放大器链写 `--set readout.amplifier=<组件名>`，扫放大器链写 `--scan readout.amplifier=<组件名1>,<组件名2>`，这时槽位整个换成那套组件，原来覆盖的元件数值一并去掉。

### 子电路端口与元件行语法

每个 `.cir` 文件必须包含一个与文件名词干（`path.stem`）同名的 `.subckt <名称> <端口...>` 块，接地节点固定为 `"0"`。主子电路内支持以下 7 种元件行格式（`src/raser/core/readout/circuit.py`）：

| SPICE 元件行格式 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `.subckt <文件名> in out` / `.subckt <文件名> in` | 无（必填） | 无 | 主子电路头部声明：前序放大器级必须声明双端口 `in out`，链末端的终端负载必须只声明单端口 `in` |
| `R<名> <节点1> <节点2> <数值>` | 无 | `Ohm` | 含热噪声的电阻（解析为 `{"between": [n1, n2], "ohm": R}`） |
| `R<名> <节点1> <节点2> <数值> noisy=0` | 无 | `Ohm` | 无热噪声的电阻（解析为 `{"between": [n1, n2], "ohm": R, "noiseless": True}`，用于模拟有源反馈形成的无热噪声等效输入阻抗或极点辅助电阻） |
| `C<名> <节点1> <节点2> <数值>` | 无 | `F` | 电容（解析为 `{"between": [n1, n2], "farad": C}`） |
| `L<名> <节点1> <节点2> <数值>` | 无 | `H` | 电感（解析为 `{"between": [n1, n2], "henry": L}`） |
| `V<名> <正节点> <负节点> [dc] <数值>` | 无 | `V` | 直流电压源（解析为 `{"between": [n+, n-], "volt": V}`） |
| `E<名> <输出+> <输出-> <跟随+> <跟随-> <增益>` | 无 | 无量纲 | 压控电压源（解析为 `{"between": [o+, o-], "follows": [f+, f-], "gain": G}`） |
| `X<名> <节点...> <子电路模型名>` | 无 | 无 | 调用同一文件主子电路外定义的外部子电路实例（解析为 `{"model": <模型名>, "nodes": [...]}`） |

元件数值支持科学计数法与不区分大小写的 SPICE 词头：`t`（$10^{12}$）、`g`（$10^{9}$）、`meg`（$10^{6}$）、`k`（$10^{3}$）、`m`（$10^{-3}$）、`u`（$10^{-6}$）、`n`（$10^{-9}$）、`p`（$10^{-12}$）、`f`（$10^{-15}$），词头后紧跟的单位字母会被忽略。

### 原理图布局提示语法

主子电路内元件行尾 `;` 后的文本由 `schematic.py` 读取，用于控制原理图网格排布：

| 布局提示格式 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `; <方向> [步数]` | 自动排布（给定方向时默认 `2.0` 步） | 网格步 | 指定从元件第一节点到第二节点的方向（`right`、`left`、`up`、`down`）与跨越的网格步数 |
| `; <主提示>, shift <方向> [步数]` | 无偏移（给定方向时默认 `2.0` 步） | 网格步 | 将元件整体向指定方向平移并通过折线导线连回两端节点 |
| `; npn` | 无（`X` 实例绘图必填） | 无 | 将三节点（集电极、基极、发射极）的子电路实例 `X` 绘制为基极在左的 NPN 双极晶体管符号 |
| `; amp` | `E` 元件自动识别 | 网格步（固定向右 `2.0` 步） | 将正负控制端与输出负端共地的压控电压源 `E` 绘制为三角形放大器符号 |

其余与网表求解、频域噪声抽样、局部电路扩展及脉冲极性测试相关的参数均写死在 `src/raser/core/readout/` 中，`.cir` 组件文件里不能设置：

| 常数名或固定项 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `LOWEST_NOISE_HZ` | `1e3` | `Hz` | `src/raser/core/readout/job.py`，`ngspice` 频域噪声分析的起始频率下限（上限为奈奎斯特频率 $0.5 / \Delta t$） |
| `PER_DECADE` | `50` | 点/十倍频程 | `src/raser/core/readout/spice.py`，`ngspice` `noise` 分析每十倍频程的采样频率点数 |
| `ngspice` 噪声分析温度 | `27`（`300.15`） | `°C`（`K`） | `src/raser/core/readout/spice.py`，`ngspice` 频域噪声分析的固定工作温度，与器件文件的 `temperature` 无关 |
| `RECORD` | `256` | 倍 | `src/raser/core/readout/spectral_noise.py`，`noise_from_spectrum` 合成时域高斯噪声时的频域记录长度相对于波形时间箱数的倍数 |
| `PART_EDGE` | `1e-3` | 无量纲 | `src/raser/core/readout/job.py`，保存输出通道波形及停止条形行局部电路扩展的电压摆幅占当事例最大通道摆幅的比例阈值 |
| 脉冲方向探测参数 | 探针电容 `1e-12`、注入电荷 `1e-15`、`dt = 10e-12`、`2000` 箱（第 `5` 箱注入） | `F`, `C`, `s`, 箱 | `src/raser/core/readout/pulse_edge.py`，`chain_sign` 测试放大器链同相或反相的固定探针输入 |
| `NO_ANSWER_V` | `1e-9` | `V` | `src/raser/core/readout/pulse_edge.py`，`chain_sign` 判定放大器链对 `1 fC` 注入有响应的最小输出摆幅阈值 |
| `COLLECTOR`, `EMITTER`, `dpi` | `(2, 1)`, `(2, -1)`, `160` | 网格步, 网格步, `dpi` | `src/raser/core/readout/schematic.py`，NPN 晶体管集电极与发射极相对基极的网格偏移及导出原理图的分辨率 |

## 读进程序以后怎么用

### 读入与解析子电路链（`circuit.py`）

1. **按 `+` 拆分链名（`named_chain`、`read_chain`）**：`named_chain(name)` 按 `"+"` 拆开 `amplifier` 设置，对每一段调用 `component_path("readout", f"{part}.cir")` 定位文件并传给 `read_chain(paths)`。
2. **解析单级文件（`read_subcircuit`）**：逐行读取 `.cir` 文件，先按 `";"` 截去行尾原理图布局提示，忽略空行与 `"*"` 开头的注释行。在 `.subckt <文件名> ...` 与 `.ends` 之外的所有非注释行（辅助 `.subckt` 与 `.MODEL` 定义）原样保存在 `"models"` 列表中；在主子电路内，调用 `spice_number` 把元件数值换算成标准国际单位（$\Omega$、$\text{F}$、$\text{H}$、$\text{V}$）。
3. **端口校验与重名编号（`read_chain`）**：链的前 $N - 1$ 项必须含两个端口 `in` 和 `out`（否则抛出 `ValueError`），按顺序存入 `"stages"`，若同一放大级在链中重复出现则从第 2 个起自动追加 `_2`、`_3` 后缀；链的最后一项必须只含单端口 `in` 作为终端负载 `"load"`（若含 `out` 则抛出 `ValueError`；若某放大级名为 `"load"` 则在拼网表时抛出 `ValueError`）。

### 拼网表与瞬态求解（`spice.py`、`job.py`）

下面是对 `HPK-Si-PiN`（结电容 `3.4416228 pF`，全耗尽）和默认链 `SantaCruz+Gali52+Termination50` 生成的瞬态网表（顶部 `BFR840L3RHESD` 模型的内部元件行略去）：

```spice
device > SantaCruz > Gali52 > load
.subckt BFR840L3RHESD 1 2 3
* 此处省略 BFR840L3RHESD 的内部元件与 .MODEL 定义（原样保留自 SantaCruz.cir）
.ends BFR840L3RHESD
.subckt SantaCruz in out
V_VCC 8 0 2.25
R_R13 in 0 1000000
C_C1 in 3 3.3e-09
X_x1 5 3 0 BFR840L3RHESD
R_R1 3 4 475
R_R2 4 5 3000
C_C2 4 5 3.3e-09
C_C5 5 out 3.3e-09
L_L1 5 6 4.7e-05
R_R3 6 7 63.7
C_C7 8 0 1e-08
C_C8 7 0 1e-08
C_C3 7 0 1e-09
C_C4 7 0 1e-09
L_L2 8 7 2.2e-06
.ends SantaCruz
.subckt Gali52 in out
R_Rin in 0 50
E_E1 a 0 in 0 -27.17
R_Rp a b 1
C_Cp b 0 1.129e-10
E_E2 c 0 b 0 1
R_Rout c out 50
.ends Gali52
.subckt load in
R_R1 in 0 50
.ends load
X1_1 top_pad in1_2 SantaCruz
X1_2 in1_2 out1 Gali52
Xload1 out1 load
Ctop_depleted top_pad 0 3.4416228e-12
I1 0 top_pad PWL(2.5e-12 0 7.5e-12 2e-06 1.25e-11 5e-06 1.75e-11 1e-06)
.save v(out1)
.control
tran 5e-12 2e-11
wrdata out.raw v(out1)
.endc
.end
```

`write_netlist`（`spice.py`）生成的网表自上而下分五段：

1. **外部模型与各级子电路（`_chain`、`subcircuit`）**：首行是标题行 `device > SantaCruz > Gali52 > load`。随后写出各组件 `"models"` 中的外部定义（如 `BFR840L3RHESD`，相同的模型块在整张网表中去重只出现一次），再依次写出 `.subckt SantaCruz`、`.subckt Gali52` 和末级负载 `.subckt load`（末级不论文件名叫什么，在网表里固定命名为 `load`；主子电路内每个元件名前自动加上 SPICE 类型字母前缀 `R_`、`C_`、`L_`、`V_`、`E_`、`X_`，数值格式化为 `.9g` 的标准国际单位）。
2. **串联实例（`_chain`）**：对 `circuit.outputs` 的第 $k$ 个输出通道（从 `1` 起），`X<k>_1` 的输入端接器件输出节点（这里是 `top_pad`，由读出电极名 `top` 加 `_pad` 构成），级间节点命名为 `in<k>_<j>`（$j = 2, \dots, N_{\text{stages}}$），末级放大器输出与负载 `Xload<k>` 接在 `out<k>` 上（若链中无放大级而只有负载，负载直接接在器件输出节点上）。
3. **器件等效电路（`circuit.lines`）**：写出 [`core/field/circuit_parameters.py`](../core/field.md) 构造的 `DeviceCircuit.lines`。全耗尽平板器件为接在 `top_pad` 与地 `0` 之间的结电容 `Ctop_depleted top_pad 0 3.4416228e-12`（单位 `F`）。
4. **分段线性感应电流源（`_current_sources`）**：写出 `I<k> <from> <to> PWL(...)`，正电流从 `<from>` 流向 `<to>`（全耗尽时从 `0` 流向 `top_pad`）。为避免 `ngspice` 将首个点当作一直流过的稳态直流电流，代码在最前面补 1 个零电流箱（中心时刻 $0.5\,\Delta t = 2.5\times 10^{-12}\ \text{s}$ 处取 `0 A`），随后第 $m$ 个时间箱（$m = 0, \dots, n_{\text{bin}} - 1$）的中心时刻为 $t_m = (m + 1.5)\,\Delta t$（单位 `s`），取值为该箱的平均感应电流（单位 `A`，上例演示三箱电流 `2`、`5`、`1 uA`）。
5. **瞬态求解与插值输出（`_transient`、`_run`）**：`.save` 仅保留待导出的输出节点电压，`tran <dt> <dt * (bins + 1)>` 以感应电流箱宽 $\Delta t$（`5e-12 s`）为步长求解 $(n_{\text{bin}} + 1)\,\Delta t$ 时长并通过 `wrdata` 导出；`_run` 调用 `ngspice -b` 后将输出电压线性插值回各时间箱中心 $t_m = (m + 1.5)\,\Delta t$，得到形状 `(outputs, bins)` 的输出电压波形（单位 `V`）。

对于单接触多条形器件，`write_waveforms`（`job.py`）通过 `_solve_part` 围绕有非零感应电流的受击条，从两侧 `margin = 1` 起逐次将 `margin` 倍增扩展局部电路，直至摆幅 $\ge \text{PART\_EDGE} \times V_{\max}$（`PART_EDGE = 1e-3`）的所有通道在相邻两次扩展间的最大电压变化 $< 10^{-3} V_{\max}$ 或覆盖整行；每个事例仅将最大绝对电压摆幅 $\ge 10^{-3} V_{\max}$（且 $V_{\max} > 0$）的通道写入 `readout.h5`。

### 未耗尽层在网表中的接法（`device_circuit.planar_circuit`）

当器件存在未耗尽体区（例如未耗尽层电阻 `1000 Ohm`、电容 `2 pF`）时，网表中器件电路与电流源四行变为：

```spice
Ctop_depleted top_pad undepleted 3.4416228e-12
R_undepleted undepleted 0 1000
C_undepleted undepleted 0 2e-12
I1 undepleted top_pad PWL(2.5e-12 0 7.5e-12 0 1.25e-11 0 1.75e-11 0)
```

耗尽层结电容 `Ctop_depleted` 改接在读出电极 `top_pad` 与节点 `undepleted` 之间；`undepleted` 与地 `0` 之间接入并联的未耗尽层电阻 `R_undepleted`（`Ohm`）和电容 `C_undepleted`（`F`）；感应电流源 `I1` 接在 `undepleted` 与 `top_pad` 之间，仅跨过耗尽层。器件有多个读出电极时，各电极的耗尽层电容都接到这一个 `undepleted` 节点。这相当于在耗尽层和背电极之间串联了一级并联 RC 阻抗，对信号产生分压与 RC 时间常数展宽，并由 `R_undepleted` 在频域噪声分析中引入热噪声。

### 频域噪声分析与时域合成（`spice.py`、`job.py`、`spectral_noise.py`）

1. **求解单边电压噪声谱密度（`noise_spectra`、`output_noise_spectrum`）**：仅当运行传入整数 `noise_seed` 时叠加噪声（`noise_seed` 为 `None` 时输出无噪声波形）。代码对同一套器件电路加放大器链在首个感应电流源节点对之间放一个交流源 `I1 <from> <to> dc 0 ac 1`，对每个等效电路对称组 `circuit.alike` 取中间通道 `group[len(group) // 2]`，调用 `ngspice -b` 在固定温度 `27 °C` 下执行 `noise v(<node>) I1 dec 50 1000 <0.5/dt>`，算出从 $f_{\min} = 10^3\ \text{Hz}$ 到奈奎斯特频率 $f_{\max} = 0.5 / \Delta t\ \text{Hz}$、每十倍频程 `50` 点的单边输出电压噪声幅度谱密度 $S_V(f)$（单位 $\text{V}/\sqrt{\text{Hz}}$）。
2. **频带功率积分与复高斯谱抽样（`band_power`、`noise_from_spectrum`）**：对单事例长度 $n_{\text{bin}}$ 的每条保存波形，在长度 $N_{\text{rec}} = 256\,n_{\text{bin}}$（`RECORD = 256`）、频率步长 $\Delta f = 1 / (N_{\text{rec}}\,\Delta t)$（`Hz`）的实傅里叶频率网格 $f_k = k\,\Delta f$（$k = 0, 1, \dots, \lfloor N_{\text{rec}}/2 \rfloor$）上，由梯形积分累积功率函数 $P(f) = \int_0^f S_V^2(f')\,df'$（谱范围外功率密度置 `0`，单位 $\text{V}^2$）计算第 $k$ 个频带的功率 $\Delta P_k$ 与复高斯谱标准差 $\sigma_k$：
   $$\Delta P_k = P\!\left(f_k + \tfrac{1}{2}\Delta f\right) - P\!\left(\max\!\left(f_k - \tfrac{1}{2}\Delta f,\, 0\right)\right), \qquad \sigma_k = \frac{1}{2}\,N_{\text{rec}}\sqrt{\Delta P_k} \tag{1}$$
   其中：
   - $\Delta P_k$：频率点 $f_k$ 周围宽度 $\Delta f$ 频带内的噪声电压方差，$\text{V}^2$；
   - $N_{\text{rec}} = 256\,n_{\text{bin}}$：扩展时域记录点数（无量纲）；
   - $\sigma_k$：内部频率点（$0 < k < N_{\text{rec}}/2$）复谱 $X_k$ 的实部与虚部各自独立抽取零均值高斯分布的标准差，$\text{V}$；直流分量 $X_0$（承接低于 $\Delta f / 2$ 的全部功率，使慢于波形时长的低频噪声表现为逐事例变化的基线偏移）及偶数 $N_{\text{rec}}$ 下的最高频分量 $X_{N_{\text{rec}}/2}$ 按实高斯分布 $\mathcal{N}(0,\, N_{\text{rec}}^2 \Delta P_k)$ 抽样。
3. **逆变换截取与叠加**：随机数生成器由 `np.random.default_rng([noise_seed, event.event, place[name]])` 按种子、事例号和通道全局下标独立初始化，调用 `np.fft.irfft(X, n=N_rec)[:bins]` 截取前 $n_{\text{bin}}$ 个点（单位 `V`），直接加到该通道的输出电压波形上。

### 脉冲边沿方向判定（`pulse_edge.py`）

1. **判定电极收集电荷符号（`collected_charge_sign`）**：读取器件文件的 `bias.electrode` 与 `bias.voltage`（`V`）。若读出电极即为偏置电极，其相对另一电极的电势差为 $V_{\text{above}} = V_{\text{bias}}$，否则为 $V_{\text{above}} = -V_{\text{bias}}$（$V_{\text{above}} == 0$ 时抛出 `ValueError`）。$V_{\text{above}} > 0$ 时电极处于高电势、收集电子，返回 $s_q = -1$；$V_{\text{above}} < 0$ 时收集空穴，返回 $s_q = +1$。
2. **探测放大器链极性（`chain_sign`）**：在结电容为 $1\ \text{pF}$（`1e-12 F`）的单电极平板电路上，以时间箱宽 $\Delta t = 10\ \text{ps}$（`10e-12 s`）、共 `2000` 箱在第 `5` 箱注入 $+1\ \text{fC}$ 正电荷（电流 $10^{-15} / \Delta t = 10^{-4}\ \text{A}$），求解放大器链输出电压相对首箱静态电压 `voltage[0]` 的最大绝对偏离点摆幅 $V_{\text{largest}}$：若 $|V_{\text{largest}}| < 10^{-9}\ \text{V}$（`NO_ANSWER_V`），抛出 `ValueError`；$V_{\text{largest}} > 0$ 返回 $s_{\text{chain}} = +1$，$V_{\text{largest}} < 0$ 返回 $s_{\text{chain}} = -1$。
3. **合成通道脉冲方向（`pulse_edges`）**：对每个输出通道计算乘积 $s_q \cdot s_{\text{chain}}$，大于 `0` 记为 `"rising"`，小于 `0` 记为 `"falling"`，写入 `readout.h5` 的 `pulse_edge` 属性供下游定时与触发使用。

## 库里有哪些组件

`raser/components/readout/` 包含以下 5 个 SPICE 电路组件：

| 组件名称 | 端口数 | 电路描述 | 出处 | 适用的器件或实验 |
| --- | --- | --- | --- | --- |
| `BroadBandCividec` | 2（放大器级：`in`, `out`） | CIVIDEC C2 宽带同相电流放大器，带宽 `1 MHz - 2 GHz`，增益 `40 dB`，输入 `1 nF` 耦合与 `1 MOhm` 偏置，输入输出阻抗 `50 Ohm`，等效输入电流噪声 `0.4 uA rms` | 文件头注释：CIVIDEC 数据手册 *"C2 Broadband Amplifier, 2 GHz, 40 dB"* | 宽带电流读出（如 `BroadBandCividec+Termination50`） |
| `ChargeSensitiveCremat` | 2（放大器级：`in`, `out`） | Cremat CR-110-R2.2 电荷灵敏前放，反馈电容 `Cf = 1.4 pF` 并联 `Rf = 100 MOhm`，空载增益 `1.4 V/pC`，衰减时间 `140 us`，输出阻抗 `50 Ohm` | 文件头注释：Cremat CR-110-R2.2 应用指南（2023 年 7 月）与 Cremat 官网 LTspice 模型 `CR-110-R2` | 电荷灵敏前放读出（如 `ChargeSensitiveCremat+Termination50`） |
| `Gali52` | 2（放大器级：`in`, `out`） | Mini-Circuits GALI-52+ 反相增益模块，低频增益 `22.66 dB`，极点 `1.41 GHz`，输入输出阻抗 `50 Ohm` | 文件头注释：Mini-Circuits GALI 系列数据手册（`50 mA`、`4.4 V`、`50 Ohm` 系统下 `100 MHz` 至 `2 GHz` S 参数单极点拟合） | [`readout`](../stages/readout.md)、[`signal`](../bench/signal.md)、[`timeres`](../bench/timeres.md)、[`tct`](../bench/tct.md)、[`bmos`](../apps/bmos.md)、[`cflm`](../apps/cflm.md) 默认链第二级 |
| `SantaCruz` | 2（放大器级：`in`, `out`） | UC Santa Cruz 单通道 LGAD 读出板，基于 `BFR840L3RHESD` 的 `475 Ohm` 反馈反相跨阻放大级，`2.25 V` 供电，输入输出 `3.3 nF` 交流耦合 | 文件头注释：SCIPP/UCSC 原理图 *"Prototype Beam Test Board"*（M. Wilder, 2016-02-19, `proto_beam_test_board_V1.1C.pdf`） | [`readout`](../stages/readout.md)、[`signal`](../bench/signal.md)、[`timeres`](../bench/timeres.md)、[`tct`](../bench/tct.md)、[`bmos`](../apps/bmos.md)、[`cflm`](../apps/cflm.md) 默认链第一级 |
| `Termination50` | 1（终端负载：`in`） | `50 Ohm` 接地终端负载电阻 | 文件头注释：示波器或后级仪器的 `50 Ohm` 输入端接 | [`readout`](../stages/readout.md)、[`signal`](../bench/signal.md)、[`timeres`](../bench/timeres.md)、[`tct`](../bench/tct.md)、[`bmos`](../apps/bmos.md)、[`cflm`](../apps/cflm.md) 默认链末级负载 |

![BroadBandCividec 原理图](../images/afe-schematic-BroadBandCividec.png)

`BroadBandCividec` 放大级原理图：`Rbias` 是输入端 `1 MOhm` 直流偏置电阻，`Cin` 是 `1 nF` 交流耦合电容；输入端 `50 Ohm` 阻抗拆成产生热噪声的 `Rn`（`325.4 Ohm`）和无噪声的 `Rq`（`59.08 Ohm`，`noisy=0`）两个并联电阻，使 `2 GHz` 单极点带宽内的输入电流噪声等于厂家标称的 `0.4 uA rms`；`E1` 增益为 `200`（经 `50 Ohm` 输出电阻 `Rout` 与 `50 Ohm` 负载分压后为 `100`，即 `40 dB`），`Rp`（`1 Ohm`）与 `Cp`（`79.58 pF`）给出 `2 GHz` 单极点。

![ChargeSensitiveCremat 原理图](../images/afe-schematic-ChargeSensitiveCremat.png)

`ChargeSensitiveCremat` 放大级原理图：`Cin`（`12.24 pF`）与串联等效输入电压噪声电阻 `Rs`（`43.1 Ohm`）接在反相增益 `-3000` 的第一级 `E1` 前，跨接 `Cf`（`1.4 pF`）与 `Rf`（`100 MOhm`）反馈回路以及无噪声极点 `Rp`（`1 kOhm`，`noisy=0`）、`Cp`（`401.3 pF`），再经增益 `+2` 的第二级 `E3` 和 `50 Ohm` 输出电阻 `Rout` 输出。
