# 触发组件（`components/trigger`）

`components/trigger/` 放独立触发设备的触发条件，描述一台真实触发设备按什么条件决定记录哪些事例。[`trigger`](../stages/trigger.md) 环节读这里的组件，从 [`digitizer`](../stages/digitizer.md) 输出的数字波形里挑出满足条件的事例，交给 [`reconstruction`](../stages/reconstruction.md)；一个事例记不记录，由触发条件决定。一台设备同时管采样和触发时（例如示波器），触发条件和采样设置放在一起，写在 [`components/digitizer/`](digitizer.md) 的那一份文件里，`trigger` 环节读那一份（见 [架构总纲](../architecture.md#组件)）。

查找组件时，project 文件夹里自己的组件优先，找不到再到组件库按名字找。

## 组件文件

一个组件文件描述一台触发设备，文件名就是组件名，在实验 `config.json` 的 `trigger` 段里用 `device` 按名字选用。需要几块器件同时过阈的符合触发（例如 [`timeres`](../bench/timeres.md)），符合条件也写在触发组件里。

## 键的含义

一个触发组件设置这几类量：

- **幅度阈值**：波形越过阈值的事例被记录，没越过的丢掉（例如 `HPK-Si-PiN` 示例，见[触发环节](../stages/trigger.md#按幅度阈值触发)）。
- **符合条件**：哪几块器件要在同一事例里都过幅度阈值，这个事例才被记录（例如 `timeres` 的双器件符合）。

一个事例记不记录，由这里的触发条件决定；要调触发阈值，改触发条件。[`reconstruction`](../stages/reconstruction.md) 段里的 `reconstruction.threshold` 和 `reconstruction.amplitude_threshold` 是重建用的阈值，作用在已被记录的事例上：`reconstruction.threshold` 用于过阈定时；`reconstruction.amplitude_threshold` 是团簇种子通道的幅度阈值，被记录的事例里找到种子的记为 `selected`。

`trigger.device` 是槽位，组件里的量按“段.槽位.键”寻址：独立触发设备的量写成 `trigger.device.<键>`，用 `--set trigger.device.<键>=<值>` 改一个，用 `--scan trigger.device.<键>=<值1>,<值2>` 扫描。兼管触发的示波器，触发条件在 `digitizer.device` 槽位里，写成 `digitizer.device.<键>`，例如 `digitizer.device.trigger_level_V`（见[数字化器组件](digitizer.md#键的含义)）。`name` 不能用 `--set`、`--scan` 改；换设备写 `--set trigger.device=<组件名>`，扫设备写 `--scan trigger.device=<组件名1>,<组件名2>`，这时槽位整个换成那个组件文件，原来覆盖的键一并去掉。环节本身的设置见[触发环节](../stages/trigger.md#设置)。

## 读进程序以后怎么用

`trigger` 环节读 `trigger` 段和触发条件，逐个事例判断，把被记录的事例写进 `nodes/trigger/<节点号>/`。组件里它用到的部分进 `trigger` 节点的指纹，改了触发条件得到新的 `trigger` 节点，下游的 `reconstruction`、`analysis` 跟着得到新节点，上游的 `digitizer` 节点照常复用。节点、指纹与复用见[片与重跑](../lifecycle/slices.md)。

## 库里有哪些组件

库里的触发条件都随兼管触发的示波器放在 [`components/digitizer/`](digitizer.md#库里有哪些组件) 下。
