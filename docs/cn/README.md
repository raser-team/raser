# RASER 中文文档

RASER 是半导体辐射探测器全链路仿真软件，用一套命令行连接器件场求解、粒子能量沉积、载流子漂移、前端读出、数字化、触发、重建和统计分析。

## 总览

- [README.md](README.md)：中文文档总目录。
- [getting-started.md](getting-started.md)：安装与激活环境、跑通 `HPK-Si-PiN` 示例、按视图查看结果并建立自己的 project。
- [architecture.md](architecture.md)：布局、实验类、project、结果、链、组件、资产。
- [cli.md](cli.md)：`raser` 命令分发、全部命令清单、全局选项与共用运行参数。

## lifecycle

- [lifecycle/experiments.md](lifecycle/experiments.md)：project 与实验文件夹、`config.json`、`run.json`、`--set` 与 `--scan` 参数扫描、随机种子。
- [lifecycle/slices.md](lifecycle/slices.md)：环节切片依赖、代码版本提示、完成标记与 `raser status` 状态查看。
- [lifecycle/jobs.md](lifecycle/jobs.md)：并行作业拆分、日志、文件锁、断点续跑与集群提交。

## 环节（stages）

八个环节按仿真链顺序排列，地位相同，总览见 [stages/README.md](stages/README.md)（链式组装、切片数据文件路径与环节命令入口）：

1. [stages/field.md](stages/field.md)：`field` 环节，算器件里的电场、权重场、IV/CV 与器件等效电路参数。
2. [stages/deposit.md](stages/deposit.md)：`deposit` 环节，用 Geant4 算粒子沉积的能量与电离电子-空穴对。
3. [stages/current.md](stages/current.md)：`current` 环节，让载流子在场中漂移，算电极上的感应电流。
4. [stages/readout.md](stages/readout.md)：`readout` 环节，把电流送进器件等效电路和前端放大器，得到波形。
5. [stages/digitizer.md](stages/digitizer.md)：`digitizer` 环节，按示波器或数字化板的采样和量化把波形变成数字波形。
6. [stages/trigger.md](stages/trigger.md)：`trigger` 环节，按真实触发设备的条件决定记录哪些事例。
7. [stages/reconstruction.md](stages/reconstruction.md)：`reconstruction` 环节，从波形里取击中时间和幅度，束流测试里做径迹拟合。
8. [stages/analysis.md](stages/analysis.md)：`analysis` 环节，统计各扫描点的效率与时间分辨，并在 `<实验>/analysis/` 下出趋势图。

## core

- [core/model.md](core/model.md)：半导体物理模型注册表，含能带、掺杂、迁移率、复合与碰撞电离模型。
- [core/device.md](core/device.md)：器件几何、电极排布与掺杂定义解析。
- [core/field.md](core/field.md)：DEVSIM 电势、电场、权重场、IV/CV 求解、TCAD 导入与器件等效电路构造。
- [core/deposit.md](core/deposit.md)：Geant4 粒子输运、激光吸收与电离电子-空穴对计算。
- [core/current.md](core/current.md)：载流子漂移、扩散、俘获、雪崩倍增与 Shockley-Ramo 感应电流计算。
- [core/readout.md](core/readout.md)：SPICE 前端电路瞬态求解与噪声叠加。
- [core/digitizer.md](core/digitizer.md)：波形采样、量化与数字电路仿真。
- [core/reconstruction.md](core/reconstruction.md)：基线扣除、定时量（`ToA`、`ToT`、`CoG`、`CFD`）、脉冲面积与团簇重建算法。
- [core/analysis.md](core/analysis.md)：电荷收集效率统计与时间分辨截断高斯拟合。

## components

组件是可以复用的定义，放在 `raser/components/` 下，按读它的环节分文件夹：

- [components/device.md](components/device.md)：器件的几何、电极、掺杂，以及选用的物理模型。
- [components/deposit.md](components/deposit.md)：入射粒子的来源：Geant4 装置、放射源和束流、激光。
- [components/readout.md](components/readout.md)：前端放大器和端接电路。
- [components/digitizer.md](components/digitizer.md)：示波器、数字化板的采样和量化设置。
- [components/trigger.md](components/trigger.md)：触发条件。

## 测试（bench）

官方测试类都在 `raser_bench` 包里，每个测试是一个继承 `raser` 实验基类的 Python 类，输出放在 `work/<器件>/<测试>/`：

- [bench/signal.md](bench/signal.md)：`raser signal`，单器件全链路信号测试，给出电荷收集效率。
- [bench/timeres.md](bench/timeres.md)：`raser timeres`，时间分辨（Time Resolution）测试。
- [bench/tct.md](bench/tct.md)：`raser tct`，瞬态电流技术（Transient Current Technique）测试，扫激光相对器件的位置。
- [bench/telescope.md](bench/telescope.md)：`raser telescope`，束流望远镜空间分辨测试，默认用 TAICHU 做参考器件。

## 应用（apps）

官方应用类都在 `raser_app` 包里，每个应用是一个继承 `raser` 实验基类的 Python 类，输出放在 `work/<应用>/`：

- [apps/bmos.md](apps/bmos.md)：`raser bmos`，在线束流监测系统（Beam Monitor Online System）应用。
- [apps/cflm.md](apps/cflm.md)：`raser cflm`，CEPC 快速亮度监测器（CEPC Fast Luminosity Monitor）应用。
- [apps/hbf.md](apps/hbf.md)：`raser hbf`，氢硼聚变（Hydrogen–Boron Fusion，p–¹¹B）应用。
- [apps/pimg.md](apps/pimg.md)：`raser pimg`，质子成像（Proton Imaging）应用。

## supports

- [supports/README.md](supports/README.md)：路径解析、输出边界检查、缺失依赖提示与进程清理等工程支撑。
