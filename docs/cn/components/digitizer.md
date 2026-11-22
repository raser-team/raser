# 数字化器组件（`components/digitizer`）

`components/digitizer/` 放示波器或数字化板的设置，一个文件描述一台真实设备怎样把 [`readout`](../stages/readout.md) 输出的模拟电压波形变成数字波形：模拟带宽、采样和量化。[`digitizer`](../stages/digitizer.md) 环节按 `digitizer` 段的 `device` 读这里的组件，得到数字波形，交给 [`trigger`](../stages/trigger.md)。一台设备同时管采样和触发时（例如示波器），它的设置只在这里放一份，`digitizer` 和 `trigger` 两个环节都读这一份（见 [架构总纲](../architecture.md#组件)）。

查找组件时，project 文件夹里自己的组件优先，找不到再到组件库按名字找。

## 组件文件

一个组件文件 `components/digitizer/<设备>.json` 描述一台设备，文件名就是组件名，在实验 `config.json` 的 `digitizer` 段里用 `device` 按名字选用。库里的 `MXR608A.json` 如下：

```json
{
    "channels": 8,
    "bits": 10,
    "max_sampling_rate_GSps": 16,
    "response": "brickwall",
    "bandwidth_GHz": 6,
    "aperture_jitter_ps": 0.15,
    "sampling_rate_GSps": 16,
    "full_scale_V": 0.04,
    "offset_V": -0.01,
    "trigger": {
        "mode": "edge",
        "source": "CH1",
        "level_V": -0.002,
        "slope": "falling"
    }
}
```

`toy.json` 是 toy 设备：不限带宽、没有孔径抖动，其余各键取好算的值，`trigger` 与 `MXR608A` 相同：

```json
{
    "channels": 64,
    "bits": 14,
    "max_sampling_rate_GSps": 20,
    "response": "none",
    "aperture_jitter_ps": 0,
    "sampling_rate_GSps": 20,
    "full_scale_V": 1.0,
    "offset_V": 0.0,
    "trigger": {
        "mode": "edge",
        "source": "CH1",
        "level_V": -0.002,
        "slope": "falling"
    }
}
```

`MXR608A` 的前六个键是设备本身定死的，取数据手册 [1] 的值；后三个是使用者在面板上调的，取组里实测时的设置（量程 $-30\ \text{mV}$ 至 $+10\ \text{mV}$）；`trigger` 是示波器兼管的触发条件，也在面板上调，取组里实测时的设置（`CH1` 下降沿、电平 $-2\ \text{mV}$）。孔径抖动 `aperture_jitter_ps` 取 `0.15`：数据手册给 8 通道机型的通道内固有抖动为 $150$–$181\ \text{fs}$ rms [1]。示波器兼管触发，它的触发条件写在同一个文件的 `trigger` 里，由 `trigger` 环节读（见[触发条件](#触发条件)）。

## 键的含义

| 类别 | 键 | 单位 | 含义 | `MXR608A` 的值 |
| --- | --- | --- | --- | --- |
| 设备定死 | `channels` | 个 | 一台的通道数 | `8` |
| 设备定死 | `bits` | 位 | ADC 位数 $N$，`1` 至 `15`（码存成 `int16`） | `10` |
| 设备定死 | `max_sampling_rate_GSps` | $\text{GS/s}$ | 最高采样率 | `16` |
| 设备定死 | `response` | 无 | 带宽的响应，`"brickwall"`（理想砖墙）或 `"none"`（不限带宽） | `"brickwall"` |
| 设备定死 | `bandwidth_GHz` | $\text{GHz}$ | 模拟带宽；只在 `response` 为 `"brickwall"` 时写 | `6` |
| 设备定死 | `aperture_jitter_ps` | $\text{ps}$ | 孔径抖动的均方根 | `0.15` |
| 面板上调 | `sampling_rate_GSps` | $\text{GS/s}$ | 采样率，不超过 `max_sampling_rate_GSps` | `16` |
| 面板上调 | `full_scale_V` | $\text{V}$ | 满量程 | `0.04` |
| 面板上调 | `offset_V` | $\text{V}$ | 量程中心 | `-0.01` |
| 触发 | `trigger` | 无 | 触发条件，见[触发条件](#触发条件) | `CH1` 下降沿，$-2\ \text{mV}$ |

满量程覆盖 [`offset_V` $-$ `full_scale_V`$/2$, `offset_V` $+$ `full_scale_V`$/2$]，分成 $2^N$ 档，每档 $\text{LSB} = $`full_scale_V`$/2^N$。

`digitizer.device` 是槽位，组件里的量按“段.槽位.键”寻址，写成 `digitizer.device.<键>`：用 `--set digitizer.device.<键>=<值>` 改，例如 `--set digitizer.device.full_scale_V=0.08`。面板上调的键这样改，等于在示波器面板上换一档；设备定死的键也能这样改，等于换了一台假想的设备，库里的组件保持数据手册的值。兼管触发的设备，它的触发条件也在 `digitizer.device` 里，例如 `digitizer.device.trigger.level_V`。`digitizer` 段是分析参数，不能用 `--scan`。`name` 不能用 `--set` 改；换设备写 `--set digitizer.device=<组件名>`，这时槽位整个换成那个组件文件，原来覆盖的键一并去掉。环节本身的设置见[数字化环节](../stages/digitizer.md#设置)。

## 触发条件

`trigger` 的 `mode` 选触发方式，对应示波器面板上的两种：

- **`"edge"`**（边沿触发）：一个信源通道 `source` 按 `slope`（`"falling"` 或 `"rising"`）越过电平 `level_V`（$\text{V}$）时触发。
- **`"pattern"`**（码型触发）：`channels` 里列几个通道，每个给电平 `level_V`（$\text{V}$）和状态 `state`（`"low"`：低于电平，`"high"`：高于电平）；所有通道同时处在各自状态的那一刻触发。例如：

  ```json
  "trigger": {
      "mode": "pattern",
      "channels": {
          "CH1": {"level_V": -0.002, "state": "low"},
          "CH2": {"level_V": -0.003, "state": "low"}
      }
  }
  ```

通道写成 `CH1`、`CH2`……，第 $n$ 通道是 `readout.h5` 属性 `electrodes` 里下标为 $n-1$ 的电极；电极多于一台设备的 `channels` 时，编号接着排到下一台。判断的式子见[触发（`core/trigger`）](../core/trigger.md)。几块器件之间的符合由独立触发设备管，见[触发组件](trigger.md)。

## 读进程序以后怎么用

1. **`digitizer` 环节**：按 `digitizer.device` 找到组件，各键的用处如下（式子见[数字化器（`core/digitizer`）](../core/digitizer.md#物理)）：
   - `response`、`bandwidth_GHz`：带宽的响应和带宽 $B$。
   - `sampling_rate_GSps`：采样间隔 $T_s = 10^{-9}/$`sampling_rate_GSps`（$\text{s}$）。
   - `aperture_jitter_ps`：每个采样时刻高斯孔径抖动的均方根 $\sigma_a$。
   - `bits`、`full_scale_V`、`offset_V`：量化的位数、每档电压和偏置。
   - `channels`：`readout` 文件里的读出通道数多于它时，按 `electrodes` 的顺序每 `channels` 个一组，每组一台同型号设备，各台时钟相位各自抽取。

   组件里 `trigger` 以外的键进 `digitizer` 节点的指纹，改了其中任何一个得到新的 `digitizer` 节点。数字波形写进 `nodes/digitizer/<节点号>/`。
2. **`trigger` 环节**：设备兼管触发时，读同一个组件文件里的 `trigger`。只有 `trigger` 进 `trigger` 节点的指纹，改了它只得到新的 `trigger` 节点，`digitizer` 节点照常复用。

节点、指纹与复用见[片与重跑](../lifecycle/slices.md)。

## 库里有哪些组件

| 组件名称 | 设备 | 出处 | 适用 |
| --- | --- | --- | --- |
| `MXR608A` | Keysight MXR608A 示波器（$6\ \text{GHz}$、8 通道、$16\ \text{GSa/s}$、10 位 ADC），兼管采样和触发 | 设备定死的键：数据手册 [1]；面板上调的键与触发条件：组里用这台示波器实测时面板上的设置（采样率 $16\ \text{GSa/s}$、量程 $-30$ 至 $+10\ \text{mV}$、`CH1` 下降沿触发、电平 $-2\ \text{mV}$） | `HPK-Si-PiN` 一类示例里选用的设备 |
| `toy` | toy 设备，不限带宽、没有孔径抖动 | 无 | 不关心示波器细节时用 |

局限：`MXR608A` 用砖墙滤波，数据手册给 10–90% 上升时间 $71.7\ \text{ps}$（$0.43/B$）[1]；本模块的理想砖墙给 $0.446/B = 74\ \text{ps}$，过渡带的形状待按数据手册核定。

## 参考文献

- [1] Keysight Technologies, “Infiniium MXR-Series Oscilloscopes (A-Series)”, Data Sheet 7120-1115.EN, https://www.keysight.com/us/en/assets/7120-1115/data-sheets/Infiniium-MXR-Series.pdf
