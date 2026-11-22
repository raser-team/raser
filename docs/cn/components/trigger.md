# 触发组件（`components/trigger`）

`components/trigger/` 放独立触发设备的触发条件，描述一台真实触发设备按什么条件决定记录哪些事例。[`trigger`](../stages/trigger.md) 环节读这里的组件，从 [`digitizer`](../stages/digitizer.md) 输出的数字波形里挑出满足条件的事例，交给 [`reconstruction`](../stages/reconstruction.md)；一个事例记不记录，由触发条件决定。一台设备同时管采样和触发时（例如示波器），触发条件和采样设置放在一起，写在 [`components/digitizer/`](digitizer.md) 的那一份文件里，`trigger` 环节读那一份（见 [架构总纲](../architecture.md#组件)）。

查找组件时，project 文件夹里自己的组件优先，找不到再到组件库按名字找。

## 组件文件

一个组件文件描述一台触发设备，文件名就是组件名，在实验 `config.json` 的 `trigger` 段里用 `device` 按名字选用。需要几块器件同时过阈的符合触发（例如 [`timeres`](../bench/timeres.md)），符合条件也写在触发组件里。库里的 `coincidence.json` 是一台甄别加符合的逻辑单元：

```json
{
    "level_V": -0.002,
    "slope": "falling",
    "require": "all",
    "coincidence_window_ns": null
}
```

## 键的含义

| 键 | 单位 | 含义 | `coincidence` 的值 |
| --- | --- | --- | --- |
| `level_V` | $\text{V}$ | 幅度阈值。一个数时各槽位共用；写成按槽位名的对象时各槽位分别设，如 `{"dut": -0.002, "ref": -0.005}` | `-0.002` |
| `slope` | 无 | 越过阈值的方向，`"falling"` 或 `"rising"` | `"falling"` |
| `require` | 无 | 符合条件的逻辑式 | `"all"` |
| `coincidence_window_ns` | $\text{ns}$ | 符合时间窗；`null` 为不卡时间 | `null` |

### 符合条件

- **槽位与命中**：逻辑式的操作数是实验器件表里的槽位名（由字母、数字、`_`、`-` 组成）。一个槽位命中，指它的任一电极的波形按 `slope` 越过 `level_V`；命中时刻取其中最早的越过时刻。越过的判断和时刻见[触发（`core/trigger`）](../core/trigger.md#越过电平)。
- **逻辑式**：槽位名用 `AND`、`OR` 和括号连接，例如 `"dut AND (ref1 OR ref2)"`。`"all"` 是全部槽位用 `AND` 连接的简写，`"any"` 是全部槽位用 `OR` 连接的简写。式里出现器件表里没有的槽位名，或器件表里有槽位没出现在式里，报错。
- **时间窗**：`coincidence_window_ns` 为 $W$ 时，只有命中时刻落在同一个宽 $W$ 的时间段里的槽位才一起算：存在一个时刻 $t$，命中时刻在 $[t - W,\ t]$ 里的那些槽位使逻辑式成立，这个事例才被记录，触发时刻取最早的这样的 $t$。`null` 时所有命中的槽位一起算，触发时刻取使逻辑式成立的最早时刻。

- **$N$ 个里至少 $k$ 个**：`AT_LEAST(k: a, b, c)`，槽位 `a`、`b`、`c` 里至少 $k$ 个命中时为真，可以和 `AND`、`OR` 混用，例如 `"AT_LEAST(6: l1, l2, l3, l4, l5, l6, l7, l8) AND dut"`。

一个事例记不记录，由这里的触发条件决定；要调触发阈值，改触发条件。[`reconstruction`](../stages/reconstruction.md) 段里的 `reconstruction.threshold` 和 `reconstruction.amplitude_threshold` 是重建用的阈值，作用在已被记录的事例上：`reconstruction.threshold` 用于过阈定时；`reconstruction.amplitude_threshold` 是团簇种子通道的幅度阈值，被记录的事例里找到种子的记为 `selected`。

`trigger.device` 是槽位，组件里的量按“段.槽位.键”寻址：独立触发设备的量写成 `trigger.device.<键>`，用 `--set trigger.device.<键>=<值>` 改一个，用 `--scan trigger.device.<键>=<值1>,<值2>` 扫描。兼管触发的示波器，触发条件在 `digitizer.device` 槽位里，写成 `digitizer.device.trigger.<键>`，例如 `digitizer.device.trigger.level_V`（见[数字化器组件](digitizer.md#触发条件)）。`name` 不能用 `--set`、`--scan` 改；换设备写 `--set trigger.device=<组件名>`，扫设备写 `--scan trigger.device=<组件名1>,<组件名2>`，这时槽位整个换成那个组件文件，原来覆盖的键一并去掉。环节本身的设置见[触发环节](../stages/trigger.md#设置)。

## 读进程序以后怎么用

`trigger` 环节读 `trigger` 段和触发条件，逐个事例判断，把被记录的事例写进 `nodes/trigger/<节点号>/`。`trigger.device` 选了独立触发设备时，由它按符合条件对整个事例判断一次，各位置记录同一批事例；`trigger.device` 为 `null` 时，各位置由各自示波器的触发条件判断。组件里它用到的部分进 `trigger` 节点的指纹，改了触发条件得到新的 `trigger` 节点，下游的 `reconstruction`、`analysis` 跟着得到新节点，上游的 `digitizer` 节点照常复用。节点、指纹与复用见[片与重跑](../lifecycle/slices.md)。

## 库里有哪些组件

| 组件名称 | 设备 | 出处 | 适用 |
| --- | --- | --- | --- |
| `coincidence` | 甄别加符合的逻辑单元 | 无（通用逻辑，阈值取 `MXR608A` 实测时的触发电平 $-2\ \text{mV}$） | 几块器件之间的符合，例如 `timeres` |

兼管触发的示波器的触发条件放在 [`components/digitizer/`](digitizer.md#触发条件) 下。
