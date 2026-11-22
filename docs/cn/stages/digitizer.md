# 数字化环节（`stages/digitizer`）

`digitizer` 是仿真链的第 5 个环节，排在[电子学读出环节（`stages/readout`）](readout.md)之后、[触发环节（`stages/trigger`）](trigger.md)之前，命令是 `raser digitizer`（短命令 `raser digi`）。它读 `readout` 节点里放大后的波形、`config.json` 的 `digitizer` 段，以及 `digitizer` 段选用的[数字化器组件（`components/digitizer`）](../components/digitizer.md)，即一台示波器或数字化板的设置。它让每个电极的波形依次经过设备的模拟带宽、采样和量化，得到每个事例整段的数字波形，计算交给[数字化器（`core/digitizer`）](../core/digitizer.md)。数字波形写进本环节的节点 `nodes/digitizer/<节点号>/`，由视图 `points/<点名>/digitizer/<作业号>` 指向，交给 `trigger`。真实设备里属于模拟带宽、采样、量化的事都归这里。

## 行为

### 跑到数字化

`raser digitizer` 在当前文件夹或给定路径的实验上跑到 `digitizer`，缺的上游自动补上：

```bash
raser digitizer [路径]
raser digi [路径]
```

不给路径就是当前文件夹，给了就是相对或绝对路径。上游的 `field`、`deposit`、`current`、`readout` 节点指纹相同就复用，不管它们是在哪个点、哪次运行里算出来的；缺的按链的顺序先算。`digitizer` 节点同样按指纹复用。代码版本和节点记录的不一致时，只给一条提示，结果照常复用。节点、参数表与复用见[片与重跑](../lifecycle/slices.md)。

### 换设备与改面板设置

`digitizer` 段的 `device` 选用一台设备，设备的各项设置在它的组件文件里。改面板上调的量，例如把 `MXR608A` 的满量程从 `0.04 V` 放大到 `0.08 V`：

```bash
raser digi --set digitizer.device.full_scale_V=0.08
```

改的是 `digitizer` 用到的设置，所以得到新的 `digitizer` 节点；`readout` 及更早的节点指纹不变，照常复用。`digitizer` 段是分析参数，不扫描：对它给 `--scan` 会报错；换一个值就用 `--set` 改掉再跑，已经测到的事例复用，只重做 `digitizer` 及之后的环节（见[实验、扫描点与种子](../lifecycle/experiments.md)）。

### 一个事例整段数字化

`digitizer` 对每个事例的整段波形采样、量化，`readout` 节点里的事例全部写进数字波形文件。记录窗就是上游波形的长度，示波器只定采样率。超出满量程的点截在最大或最小码，每个电极被截的点数记在文件里。

### 纯噪声道

两类道不走 `current`、`readout`，由 `digitizer` 按该道电子学的噪声谱直接在采样点上抽出噪声并量化，得到它的数字波形：一类是不在触发条件里、沉积能量低于使用者给的能量 cut 的道；另一类是多位置实验里在该事例未命中的槽位（没有沉积步，或沉积能量低于该槽位的能量下限 `deposit.<槽位>.edep_min`，没设时取 `deposit.edep_min`），无论该槽位在不在触发条件里（触发条件里的槽位照样拿这条纯噪声波形去过阈值，噪声造成的假触发自然出现）。两类的区别在于：前一类是不参与触发的道，后一类是槽位整个未命中，使用者用能量下限选择不算它的信号。前一类由上游在 `current` 之前判断，后一类由本环节按 `deposit.h5` 的 `detector`、`e` 两列和能量下限判断，`current`、`readout` 按同一判断跳过这个槽位的这个事例，`digitizer` 按给定的列表处理；噪声谱是实验通用的资产，一种器件、偏压和放大器链只算一次。式子和判断函数见[数字化器（`core/digitizer`）](../core/digitizer.md#纯噪声道)。

## 规则

### 执行流程

1. **读入**：读 `readout` 节点的波形文件、`digitizer` 段，以及 `digitizer.device` 指定的数字化器组件。组件按名字查找：project 文件夹里自己的组件优先，找不到再到组件库找。
2. **分组与相位**：一台设备的所有通道共用一个采样时钟。`readout.h5` 属性 `electrodes` 里的通道数多于组件的 `channels` 时，按 `electrodes` 的顺序每 `channels` 个分为一组，每组一台同型号设备，各台的时钟相位各自抽取。
3. **带宽与采样**：按组件的 `response`（`"brickwall"` 或 `"none"`）限带宽，在采样时刻 $t_k = t_0 + \varphi + k\,T_s + \delta_k$ 按带限插值取电压（$\text{V}$）：$t_0$ 为 `readout.h5` 里该事例的 `t0`（$\text{s}$），$T_s = 10^{-9}/$`sampling_rate_GSps`（$\text{s}$），$\varphi$ 在 $[0, T_s)$ 上均匀分布，$\delta_k$ 是均方根为 `aperture_jitter_ps`（$\text{ps}$）的高斯孔径抖动。每个电极取 $\lfloor n_{\text{bin}}\,\Delta t / T_s \rfloor$ 个点（$n_{\text{bin}}$、$\Delta t$ 为该事例 `readout` 波形的箱数和箱宽）。式子见[数字化器（`core/digitizer`）](../core/digitizer.md)。
4. **量化**：$\text{LSB} = $`full_scale_V`$/2^N$（$\text{V}$），$N$ 为组件的 `bits`；码 $= \lfloor(V - $`offset_V`$)/\text{LSB}\rfloor + 2^{N-1}$，截到 $[0,\ 2^N - 1]$。每个电极被截的点数逐个记下。
5. **纯噪声道**：该事例列为纯噪声的道按其噪声谱资产抽出采样点上的噪声，再量化；点数和时钟相位与同一事例的其他道相同。多位置实验里，某槽位在 `deposit` 记录的某个事例未命中时，该槽位的全部电极均列为纯噪声道，点数、时钟相位与同一事例其他槽位相同。
6. **写出**：把数字波形文件 `digitizer.h5` 和本环节的图写进 `digitizer` 节点（多位置实验里每个位置的 `digitizer.<位置>.h5` 含 `deposit` 记录的全部事例，未命中的事例其电极标 `noise_only`）。图有两种：前 `digitizer.plots` 个存了波形的事例各一张 `samples_<事例号>`（带宽滤波后的模拟波形叠上数字化后的样点），以及每个节点一张 `codes`（码的直方图）；`digitizer.plots` 为 `0` 时都不画。

### 种子

采样的随机量（时钟相位 $\varphi$、孔径抖动）和纯噪声道的噪声由 `digitizer` 自己的种子抽取，由作业的种子派生（见[实验、扫描点与种子](../lifecycle/experiments.md#种子)）。这个种子进本环节节点的指纹，和 `readout` 管 NGspice 噪声的种子各自独立取。

### 节点指纹

本环节节点的指纹由 `digitizer` 段里的设置值、所选数字化器组件里触发条件以外的键、`digitizer` 自己的种子、上游 `readout` 节点的节点号，以及纯噪声道所用噪声谱资产的指纹组成。

## 软件实现

- `src/raser/stages/digitizer.py`：本环节的模块，读入 `readout` 节点的波形、`digitizer` 段和组件，按上面的流程调用 `core/digitizer` 的采样与量化，写出数字波形文件和图。函数 `digitized(kwargs, position=None)`：设备名取 `device`，画图的事例数取 `plots`，种子取 `seed`，组件内容由 lifecycle 交来（已并入 `--set digitizer.device.<键>=…` 的覆盖）；缺其中任何一样时报错并写明缺的是哪个。多位置实验里一个位置一片；上游在这个位置没留下 `readout.<位置>.h5` 时，本片不写文件，记 0 个事例。纯噪声道的列表暂不接：现在每个事例都没有纯噪声道。
- `src/raser/core/digitizer/`：带宽、采样与量化的计算，见[数字化器（`core/digitizer`）](../core/digitizer.md)。

## 接口

### 设置

`config.json` 的 `digitizer` 段有两个键：槽位 `device` 和 `plots`。“示例里的值”是 `examples/HPK-Si-PiN/signal/config.json` 写的值；`config.json` 缺了其中一个键时报错，指出缺的“段.键”。

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `digitizer.device` | `"MXR608A"` | 无 | 选用的数字化器组件名，对应 `components/digitizer/<组件名>.json`；也可写成带 `name` 的对象，其余键覆盖组件文件里的同名键 |
| `digitizer.plots` | `100`（`timeres`、`bmos`、`cflm` 示例为 `0`） | 事例（个） | 每个作业画 `samples_<事例号>` 的事例数上限 |

设备的设置都写在组件文件里，按“段.槽位.键”寻址：用 `--set digitizer.device.<键>=<值>` 改，例如 `--set digitizer.device.sampling_rate_GSps=8`。设备本身定死的键（如 `bits`、`response`）也能这样改，等于换了一台假想的设备。`name` 不能用 `--set` 改：换设备写 `--set digitizer.device=<组件名>`，这时槽位整个换成那个组件文件，原来覆盖的键一并去掉。各键的名字、单位和含义见[数字化器组件](../components/digitizer.md#键的含义)。一台设备同时管采样和触发时（例如示波器），它的触发条件写在同一个组件文件里，由 `trigger` 读，触发的键也在 `digitizer.device` 里，例如 `digitizer.device.trigger.level_V`。公共运行参数见[命令行接口（`raser`）](../cli.md)，配置分段与扫描见[实验、扫描点与种子](../lifecycle/experiments.md)。

### 读写的文件

- **读：`readout` 节点的 `readout.h5`**（多位置实验里为同节点下的 `readout.<位置>.h5`）：放大后的波形，由[电子学读出环节（`stages/readout`）](readout.md)写出，本环节只读。
- **读：`deposit` 节点的 `deposit.h5`（多位置实验）、纯噪声道列表与噪声谱资产**：多位置实验按 `deposit.h5` 的 `detector`、`e` 两列和能量下限判断各事例哪些槽位未命中；其余纯噪声道列表由上游给出；各输出的噪声谱由 `readout` 算出、作为资产存放，本环节只读。
- **写：`nodes/digitizer/<节点号>/digitizer.h5`**（多位置实验里为同节点下的 `digitizer.<位置>.h5`）：数字波形文件，沿用 `readout.h5` 的稀疏存法，存 `readout.h5` 里存了波形的电极和纯噪声道；多位置实验里每个位置的 `digitizer.<位置>.h5` 含 `deposit` 记录的全部事例，未命中的事例其电极标 `noise_only`。

  | 类别 | 名称 | 形状与类型 | 单位 | 含义 |
  | --- | --- | --- | --- | --- |
  | 属性（`attrs`） | `electrodes` | `(outputs,)`，变长字符串数组 | 无 | 读出通道名，照抄 `readout.h5` |
  | 属性（`attrs`） | `sampling_period` | 标量，`float64` | $\text{s}$ | 采样间隔 $T_s$ |
  | 属性（`attrs`） | `lsb_V` | 标量，`float64` | $\text{V}$ | 每档电压 LSB |
  | 属性（`attrs`） | `offset_V` | 标量，`float64` | $\text{V}$ | 量程中心 |
  | 属性（`attrs`） | `bits` | 标量，整数 | 位 | ADC 位数 $N$ |
  | 属性（`attrs`） | `channels` | 标量，整数 | 个 | 一台设备的通道数 |
  | 属性（`attrs`） | `pulse_edge` | `(outputs,)`，变长字符串数组 | 无 | 与 `electrodes` 一一对应的脉冲方向，照抄 `readout.h5` |
  | 属性（`attrs`） | `pre_window` | 标量，`float64` | $\text{s}$ | 前段长度，照抄 `readout.h5` |
  | 属性（`attrs`） | `device` | 标量，字符串 | 无 | 所用的数字化器组件名 |
  | 数据集（`datasets`） | `event` | `(events,)`，`int64` | 无 | 事例编号 |
  | 数据集（`datasets`） | `count` | `(events,)`，`int64` | 点 | 该事例每个电极的采样点数 |
  | 数据集（`datasets`） | `stored` | `(events,)`，`int64` | 个 | 该事例存了数字波形的电极数 |
  | 数据集（`datasets`） | `index` | `(sum(stored),)`，`int64` | 无 | 存了的电极在 `electrodes` 中从 `0` 起的下标，按 `stored` 切分到各事例 |
  | 数据集（`datasets`） | `t0` | `(sum(stored),)`，`float64` | $\text{s}$ | 该电极第一个采样点的时刻（$t_0 + \varphi$），已含所属设备的时钟相位，按 `stored` 切分到各事例；同一台设备上的电极取值相同 |
  | 数据集（`datasets`） | `noise_only` | `(sum(stored),)`，`bool` | 无 | 该电极是纯噪声道 |
  | 数据集（`datasets`） | `clipped` | `(sum(stored),)`，`int64` | 点 | 该电极被截在最大或最小码的点数 |
  | 数据集（`datasets`） | `code` | `(sum(stored * count),)`，`int16` | 无 | 按事例和存了的电极依次展开的码，每个电极占所属事例的 `count` 个点 |

  码换回电压：$V = (\texttt{code} - 2^{N-1} + 0.5)\cdot\texttt{lsb\_V} + \texttt{offset\_V}$（单位 $\text{V}$），其中 $N$ 为属性 `bits`；每个存了波形的电极第 $k$ 个点（从 `0` 起）的标称时刻为该电极对应的 `t0` $+ k\cdot$`sampling_period`（单位 $\text{s}$）。第 $i$ 个事例（从 `0` 起）的码从 `code` 里前 $i$ 个事例 `stored * count` 之和处起，依次是该事例 `index` 所列各电极的 `count` 个点。
- **写：本环节的图**：`samples_<事例号>` 和 `codes`，放在本环节节点的 `plots/` 里，样式见[出图](../supports/figures.md)。
- **写：`nodes/digitizer/<节点号>/node.json`**：记下本环节的输入、代码版本、运行环境和运行状态。写到一半的节点带 `.part` 后缀，写完才改成正式的名字。
- **写：`points.json` 与 `points/<点名>/digitizer/<作业号>`**：参数表记各点 `digitizer` 用的节点号；视图软链接指向 `../../../nodes/digitizer/<节点号>`。
