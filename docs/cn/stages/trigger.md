# 触发环节（`stages/trigger`）

`trigger` 是仿真链的第 6 个环节，排在[数字化环节（`stages/digitizer`）](digitizer.md)之后、[事件重建环节（`stages/reconstruction`）](reconstruction.md)之前，命令是 `raser trigger`（短命令 `raser trig`）。它读 `digitizer` 节点里的 `digitizer.h5`、`config.json` 的 `trigger` 段，以及[触发组件（`components/trigger`）](../components/trigger.md)里的触发条件，像真实触发设备（例如示波器的触发）那样决定哪些事例被记录。被记录事例的事例号写进本环节节点的 `trigger.h5`（位于 `nodes/trigger/<节点号>/`），由视图 `points/<点名>/trigger/<作业号>` 指向，交给 `reconstruction`（`reconstruction` 据此从 `digitizer.h5` 读出这些事例的数字波形）。真实设备里属于触发的事都归这里。

## 行为

### 跑到触发

`raser trigger` 在当前文件夹或给定路径的实验上跑到 `trigger`，缺的上游自动补上：

```bash
raser trigger [路径]
raser trig [路径]
```

不给路径就是当前文件夹，给了就是相对或绝对路径。上游的 `field`、`deposit`、`current`、`readout`、`digitizer` 节点指纹相同就复用，不管它们是在哪个点、哪次运行里算出来的；缺的按链的顺序先算。`trigger` 节点同样按指纹复用。代码版本和节点记录的不一致时，只给一条提示，结果照常复用。节点、参数表与复用见[片与重跑](../lifecycle/slices.md)。

### 按幅度阈值触发

`HPK-Si-PiN` 示例照组里实测的设置，在 `MXR608A` 的 `CH1` 上边沿触发：下降沿、电平 $-2\ \text{mV}$。`CH1` 的数字波形向下越过电平的事例记入 `trigger.h5`，没越过的就丢掉。改电平：

```bash
raser trig --set digitizer.device.trigger.level_V=-0.005
```

改的是触发条件，所以只得到新的 `trigger` 节点，`digitizer` 及更早的节点照常复用。

### 几块器件之间的符合

`timeres` 的两块、三块器件用独立触发设备 `coincidence`：各槽位分别设阈值，按逻辑式和符合时间窗判断整个事例记不记录，各位置记录同一批事例。写法见[触发组件](../components/trigger.md#符合条件)。

## 规则

### 执行流程

1. 读 `digitizer` 节点的 `digitizer.h5`（按 `lsb_V`、`offset_V` 把量化码换回电压，单位 $\text{V}$），以及 `trigger` 段和触发组件里的触发条件。
2. 按触发条件逐个事例判断，决定哪些事例被记录：`trigger.device` 为 `null` 时用各位置示波器的边沿或码型触发，否则用独立触发设备的符合条件。式子见[触发（`core/trigger`）](../core/trigger.md)。
3. 把被记录事例的事例号数据集 `event`（`int64`）和触发时刻 `trigger_time`（$\text{s}$）写进 `nodes/trigger/<节点号>/trigger.h5`（多位置实验里同节点下每个位置一个文件 `trigger.<位置>.h5`），并写出本环节的图 `trigger_amplitude`。

本环节节点的指纹由 `trigger` 段里用到的设置值、触发组件里用到的部分，以及上游 `digitizer` 节点的节点号组成。

## 软件实现

- `src/raser/stages/trigger.py`：本环节的模块。`triggered(kwargs, position=None)` 用示波器自己的触发，多位置实验里一个位置一片：读本位置的 `digitizer.h5`，触发条件取 `digitizer.device` 组件内容里的 `trigger`，组件里没有 `trigger` 时报错；上游在这个位置没留下数字波形文件时，本片不写文件，记 0 个事例。`coincident(kwargs, positions)` 用独立触发设备，一片读各位置的 `digitizer.<位置>.h5`、写各位置的 `trigger.<位置>.h5`，设置取 `trigger.device` 的组件内容，没有这个组件时报错；没留下数字波形文件的位置，它的槽位在所有事例里都不命中。两个函数都返回被记录的事例数。
- `src/raser/core/trigger/`：越过电平、边沿、码型、槽位之间的符合与写出，见[触发（`core/trigger`）](../core/trigger.md)。

## 接口

### 设置

`config.json` 的 `trigger` 段只有一个键，就是槽位 `device`：`null` 表示用 `digitizer.device` 里示波器的触发条件，否则是独立触发设备的组件名或带 `name` 的对象；缺了这个键时报错。本环节自身的设置写在 `config.json` 的 `trigger` 段里，用 `--set trigger.<键>=<值>` 改。`trigger` 段是分析参数，不扫描：对它给 `--scan` 会报错；换一个值就用 `--set` 改掉再跑，已经测到的事例复用，只重做 `trigger` 及之后的环节。独立触发设备的组件放在 `components/trigger/` 下，由槽位 `trigger.device` 选用，其内部量按“段.槽位.键”寻址（`--set trigger.device.<键>=<值>`）；`name` 不能用 `--set` 改，换设备写 `--set trigger.device=<组件名>`，这时槽位整个换成那个组件文件，原来覆盖的键一并去掉。一台设备同时管采样和触发时（例如示波器 `MXR608A`），设置在[`components/digitizer/`](../components/digitizer.md)下只放一份，`digitizer` 和 `trigger` 都读它，其触发条件在槽位 `digitizer.device` 里，按 `digitizer.device.trigger.<键>` 寻址（例如 `digitizer.device.trigger.level_V`），见[触发组件（`components/trigger`）](../components/trigger.md)。公共运行参数见[命令行接口（`raser`）](../cli.md)，配置分段与扫描见[实验、扫描点与种子](../lifecycle/experiments.md)。

### 读写的文件

- **读：`digitizer` 节点的 `digitizer.h5`**（多位置实验为 `digitizer.<位置>.h5`）：数字波形（量化码 `code` 与 `sampling_period`、`lsb_V`、`offset_V`、`bits` 等），由[数字化环节（`stages/digitizer`）](digitizer.md)写出，本环节只读。
- **写：`nodes/trigger/<节点号>/trigger.h5`**（多位置实验为同节点下的 `trigger.<位置>.h5`）：被记录事例清单，含形状为 `(recorded,)`、类型 `int64`、无单位的数据集 `event`，存通过触发条件的事例编号；形状相同、类型 `float64` 的数据集 `trigger_time`（$\text{s}$），存触发时刻；属性 `events_seen` 为 `digitizer.h5` 里的事例总数；下游[事件重建环节（`stages/reconstruction`）](reconstruction.md)据此从 `digitizer.h5` 读取这些事例的数字波形。
- **写：本环节的图与 `nodes/trigger/<节点号>/node.json`**：节点里另含本环节的图与 `node.json`，记下本环节的输入、代码版本、运行环境和运行状态。写到一半的节点带 `.part` 后缀，写完才改成正式的名字。
- **写：`points.json` 与 `points/<点名>/trigger/<作业号>`**：参数表记各点 `trigger` 用的节点号；视图软链接指向 `../../../nodes/trigger/<节点号>`。
