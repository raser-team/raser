# 数字化器组件（`components/digitizer`）

`components/digitizer/` 放示波器或数字化板的设置，一个文件描述一台真实设备怎样把 [`readout`](../stages/readout.md) 输出的模拟电压波形变成数字波形：模拟带宽、采样和量化。[`digitizer`](../stages/digitizer.md) 环节按 `digitizer` 段的 `device` 读这里的组件，得到数字波形，交给 [`trigger`](../stages/trigger.md)。一台设备同时管采样和触发时（例如示波器），它的设置只在这里放一份，`digitizer` 和 `trigger` 两个环节都读这一份（见 [架构总纲](../architecture.md#组件)）。

查找组件时，project 文件夹里自己的组件优先，找不到再到组件库按名字找。

## 组件文件

一个组件文件 `components/digitizer/<设备>.json` 描述一台设备，文件名就是组件名，在实验 `config.json` 的 `digitizer` 段里用 `device` 按名字选用。库里的 `MXR608A.json` 设计如下：

```json
{
    "channels": 8,
    "bits": 10,
    "max_sampling_rate_GSps": 16,
    "bandwidth_GHz": 6,
    "sampling_rate_GSps": 16,
    "full_scale_V": 0.04,
    "offset_V": -0.01
}
```

前四个键是设备本身定死的，取说明书的值；后三个是使用者在面板上调的，取组里实测时的设置（量程 $-30\ \text{mV}$ 至 $+10\ \text{mV}$）。孔径抖动 `aperture_jitter_ps` 取值待按数据手册核定，核定后加进这份文件。示波器兼管触发，它的触发条件写在同一个文件里，由 `trigger` 读。

## 键的含义

| 类别 | 键 | 单位 | 含义 | `MXR608A` 的值 |
| --- | --- | --- | --- | --- |
| 设备定死 | `channels` | 个 | 一台的通道数 | `8` |
| 设备定死 | `bits` | 位 | ADC 位数 $N$ | `10` |
| 设备定死 | `max_sampling_rate_GSps` | $\text{GS/s}$ | 最高采样率 | `16` |
| 设备定死 | `bandwidth_GHz` | $\text{GHz}$ | 模拟带宽（$-3\ \text{dB}$ 点），高斯响应 | `6` |
| 设备定死 | `aperture_jitter_ps` | $\text{ps}$ | 孔径抖动的均方根 | 取值待按数据手册核定 |
| 面板上调 | `sampling_rate_GSps` | $\text{GS/s}$ | 采样率，不超过 `max_sampling_rate_GSps` | `16` |
| 面板上调 | `full_scale_V` | $\text{V}$ | 满量程 | `0.04` |
| 面板上调 | `offset_V` | $\text{V}$ | 量程中心 | `-0.01` |

满量程覆盖 [`offset_V` $-$ `full_scale_V`$/2$, `offset_V` $+$ `full_scale_V`$/2$]，分成 $2^N$ 档，每档 $\text{LSB} = $`full_scale_V`$/2^N$。

组件里的量按“段.组件.键”寻址，写成 `digitizer.<组件>.<键>`：用 `--set digitizer.<组件>.<键>=<值>` 改一个，用 `--scan digitizer.<组件>.<键>=<值1>,<值2>` 扫描，例如 `--set digitizer.MXR608A.full_scale_V=0.08`。面板上调的键这样改，等于在示波器面板上换一档；设备定死的键也能这样改，等于换了一台假想的设备，库里的组件保持说明书的值。兼管触发的设备，它的触发条件同样按这个地址改。环节本身的设置见[数字化环节](../stages/digitizer.md#设置)。

## 读进程序以后怎么用

1. **`digitizer` 环节**：按 `digitizer.device` 找到组件，各键的用处如下（式子见[数字化器（`core/digitizer`）](../core/digitizer.md#物理)）：
   - `bandwidth_GHz`：高斯低通的 $-3\ \text{dB}$ 点 $B$。
   - `sampling_rate_GSps`：采样间隔 $T_s = 1/$`sampling_rate_GSps`。
   - `aperture_jitter_ps`：每个采样时刻高斯孔径抖动的均方根 $\sigma_a$。
   - `bits`、`full_scale_V`、`offset_V`：量化的位数、每档电压和偏置。
   - `channels`：`readout` 文件里的读出通道数多于它时，按 `electrodes` 的顺序每 `channels` 个一组，每组一台同型号设备，各台时钟相位各自抽取。

   组件里 `digitizer` 用到的键进 `digitizer` 节点的指纹，改了其中任何一个得到新的 `digitizer` 节点。数字波形写进 `nodes/digitizer/<节点号>/`。
2. **`trigger` 环节**：设备兼管触发时，读同一个组件文件里的触发条件。这部分进 `trigger` 节点的指纹，改了它得到新的 `trigger` 节点。

节点、指纹与复用见[片与重跑](../lifecycle/slices.md)。

## 库里有哪些组件

| 组件名称 | 设备 | 出处 | 适用 |
| --- | --- | --- | --- |
| `MXR608A` | Keysight MXR608A 示波器（$6\ \text{GHz}$、8 通道），兼管采样和触发 | 设备定死的键：[Infiniium MXR B 系列数据手册](https://www.keysight.com/us/en/assets/3123-1557/data-sheets/Infiniium-MXR-B-Series.pdf)（A 系列手册待核）；面板上调的键：组里实测文件 `~/Documents/e-test/trials/1021/R43-2nd-stage-only_234901/500V/burst_0002.h5`（采样率 $16\ \text{GSa/s}$、量程 $-30$ 至 $+10\ \text{mV}$），型号见 `~/Documents/e-test/trials/1105/DCRSD-run.log` 里示波器的自报 | `HPK-Si-PiN` 一类实验的缺省设备 |
