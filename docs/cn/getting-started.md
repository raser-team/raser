# 快速入门

本页从安装开始，用一条命令跑通 `HPK-Si-PiN` 示例，按链的顺序看每一步的结果，再建自己的 project、改参数。

## 1. 安装

```bash
env/install_conda.sh
```

## 2. 激活

在本地终端激活环境，集群上改用 CVMFS 激活脚本，然后检查版本：

```bash
source env/setup.sh
# 集群上使用：
source env/setup_cvmfs.sh

raser --version
```

## 3. 第一次运行

```bash
raser signal HPK-Si-PiN
```

它模拟 Sr90 放射源发出的电子穿过 `HPK-Si-PiN`：电子在器件里留下电荷，电荷漂移产生电流，经放大、采样、触发后被记录，最后统计出电荷收集效率和相对真实时刻的时间分辨。所有设置都写在 `examples/HPK-Si-PiN/signal/config.json` 里，结果也存在 `examples/HPK-Si-PiN/` 下。

## 4. 链上每一步的结果

这条命令按顺序走完链上的八个环节。下面按同样的顺序看每一步算出了什么。

### 4.1 field

第一次用到这块器件时，先算它的电场、IV 和 CV，存在 `examples/HPK-Si-PiN/field/`，这块器件的其他实验也用这一份。

![HPK-Si-PiN IV 曲线](../images/field/iv-HPK-Si-PiN.png)

反向偏压下的暗电流。

![HPK-Si-PiN CV 曲线](../images/field/cv-HPK-Si-PiN.png)

电容随偏压下降，器件全耗尽后趋于平缓。

![HPK-Si-PiN 200 V 一维电场分布](../images/field/efield-HPK-Si-PiN-200V.png)

`200 V` 下沿器件深度的电场。

### 4.2 deposit 和 current

deposit 用 Geant4 算出电子在器件里留下多少能量、留在哪里；current 让这些电荷在电场中漂移，算出电极上的感应电流。

![HPK-Si-PiN 单事例载流子漂移路径](../images/current/drift-path-HPK-Si-PiN.png)

一个事例里电子和空穴的漂移轨迹。

![HPK-Si-PiN 单事例感应电流](../images/current/event-HPK-Si-PiN.png)

同一个事例在读出电极上的感应电流：电子分量、空穴分量和总电流。

### 4.3 readout

readout 把感应电流送进器件的等效电路，再经过前端放大器，算出放大器输出端的电压波形。这个示例用的放大器是 SantaCruz 板加 Gali52，末端接 50 Ω：

![SantaCruz 放大器原理图](../images/readout/schematic-SantaCruz.png)

放大器的噪声也在这一步算出来，叠在输出波形上。

### 4.4 digitizer

digitizer 像示波器或数字化板那样，按固定的采样率取点，把每个点的电压量化成有限的几档，得到数字波形。采样率和位数写在配置的 `digitizer` 段里。

### 4.5 trigger

trigger 像真实的触发设备那样，决定哪些事例被记录。这个示例按幅度阈值触发：波形越过阈值的事例被记录，没越过的就丢掉。

### 4.6 reconstruction

reconstruction 在每个被记录的事例里，从波形上取出这些量：基线、幅度、过阈时刻（ToA）、恒比定时时刻（CFD），以及脉冲面积和过阈时长。

### 4.7 analysis

analysis 汇总所有事例。

![HPK-Si-PiN 电荷收集效率分布](../images/analysis/efficiency-HPK-Si-PiN.png)

电荷收集效率的分布，虚线是平均值。

![HPK-Si-PiN 脉冲幅度分布](../images/analysis/amplitude-HPK-Si-PiN.png)

被记录事例的脉冲幅度，虚线是幅度阈值。

![HPK-Si-PiN 时间差分布与截断高斯拟合](../images/analysis/time-difference-HPK-Si-PiN.png)

各种定时方法给出的时刻相对真实沉积时刻的差。仿真知道每个事例真实的沉积时刻，所以能这样算出时间分辨；实验里拿不到真实时刻，要测时间分辨得用参考器件，见 timeres。

每一步的结果按扫描点放在 `examples/HPK-Si-PiN/signal/points/<点名>/<环节>/` 下，统计和趋势图放在 `examples/HPK-Si-PiN/signal/analysis/` 下，存放方式见 [architecture.md](architecture.md#结果)。

## 5. 建自己的 project

把示例 project 复制到 `work/my-PiN`，配置是完整的，之后和示例互不影响，再在自己的 project 上跑 `signal`：

```bash
raser new --from HPK-Si-PiN work/my-PiN
raser signal my-PiN
```

结果存在 `work/my-PiN/signal/` 里（下有 `points.json`、`nodes/`、`points/<点名>/` 和 `analysis/`），器件场存在 `work/my-PiN/field/` 里。

## 6. 改点东西再跑

改单个偏压设置再跑，新节点写入 `work/my-PiN/signal/nodes/` 并更新 `work/my-PiN/signal/points.json` 和 `work/my-PiN/signal/points/<点名>/` 视图：

```bash
raser signal my-PiN --set field.voltage=100
```

扫描多个偏压，在 `work/my-PiN/signal/points/voltage_100/` 和 `work/my-PiN/signal/points/voltage_200/` 下按点看各环节结果，并在 `work/my-PiN/signal/analysis/` 下看趋势图：

```bash
raser signal my-PiN --scan field.voltage=100,200
```

![HPK-Si-PiN 电荷收集效率与时间分辨随偏压变化](../images/analysis/trend-HPK-Si-PiN.png)

打印 `work/my-PiN` 的参数表（各实验、各扫描点、各环节的状态和节点号）：

```bash
raser status work/my-PiN
```

不跑仿真，只画器件本身的几何、电极和掺杂：

```bash
raser device --draw HPK-Si-PiN
```

加 `--seed <整数>` 结果可重复（更多参数与扫描用法见 [cli.md](cli.md) 和 [lifecycle/experiments.md](lifecycle/experiments.md)）。
