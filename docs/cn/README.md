# RASER 中文文档

RASER（Radiation Semiconductor，版本 `5.0`，Python `3.11`）是半导体探测器仿真软件，通过命令行入口 `raser` 连接器件场求解、能量沉积、感应电流计算、读出电子学仿真、波形重建、结果分析与实验工作流。

## 目录

### 总览与入门

- [README.md](README.md)：中文文档总目录与一句话介绍。
- [getting-started.md](getting-started.md)：安装与激活环境后第一次运行一个器件（`HPK-Si-PiN`）。
- [architecture.md](architecture.md)：源码目录分层、`pyproject.toml` 的 `importlinter` 依赖契约、链上环节与顺序、各环节交接的切片文件、实验与环节的关系。
- [cli.md](cli.md)：`raser` 的全部命令、短命令别名、模块注册表与公共选项。

### 生命周期（`lifecycle`）

- [lifecycle/experiments.md](lifecycle/experiments.md)：实验文件夹、`config.json`、`run.json`、扫描点、`--set`/`--scan`、种子与 `--same-seeds`。
- [lifecycle/slices.md](lifecycle/slices.md)：切片（`Slice`）、`needs` 依赖、过期判断、`.done` 标记、重跑与 `raser status`。
- [lifecycle/jobs.md](lifecycle/jobs.md)：作业拆分、日志文件、文件锁、断点续跑与集群提交。

### 仿真链环节（`stages`）

- [stages/README.md](stages/README.md)：`src/raser/stages/chain.py`、`files.py`、`stage_commands.py`，作业切片链顺序、切片数据文件路径与环节命令入口。
- [stages/field.md](stages/field.md)：`stages/field`，求解器件电势、电场、权重场、IV/CV 曲线（或使用 `-ext` 导入单个偏压 TCAD 场解并据此求解权重势）的命令、选项与共享切片输出。
- [stages/deposit.md](stages/deposit.md)：`stages/deposit`，计算放射源或束流在器件中的能量沉积与电离电子-空穴对的命令与切片。
- [stages/current.md](stages/current.md)：`stages/current`，在已求解场中漂移载流子并计算各读出电极感应电流的命令与切片。
- [stages/readout.md](stages/readout.md)：`stages/readout`，求解器件等效电路与放大器链输出电压波形的命令与切片。
- [stages/reconstruction.md](stages/reconstruction.md)：`stages/reconstruction`，从读出波形提取基线、幅度、定时量、脉冲面积与团簇特征的命令与切片。
- [stages/analysis.md](stages/analysis.md)：`stages/analysis`，汇总实验各扫描点的电荷收集效率与时间分辨并输出统计文件与图表。

### 核心（`core`）

- [core/model.md](core/model.md)：`core/model`，半导体材料参数、能带结构、掺杂、迁移率、复合、不完全电离与碰撞电离公式。
- [core/device.md](core/device.md)：`core/device`，从器件 JSON 定义构建 `Detector` 对象、电极排布、电容计算与几何边界。
- [core/field.md](core/field.md)：`core/field`，DEVSIM 电势/电场/权重场/IV/CV 求解、TCAD 导入、插值场查询 `DevsimField` 与器件等效 SPICE 电路构造。
- [core/deposit.md](core/deposit.md)：`core/deposit`，Geant4 粒子输运、简化 MIP 径迹、激光吸收、电离对数计算与 `deposit_<job>.h5` 读写。
- [core/current.md](core/current.md)：`core/current`，载流子漂移、扩散、俘获、雪崩倍增、Shockley-Ramo 感应电流计算与 `current_<job>.h5` 读写。
- [core/readout.md](core/readout.md)：`core/readout`，SPICE 放大器链瞬态求解、热噪声频谱抽样、脉冲边沿判定与 `readout_<job>.h5` 读写。
- [core/digitizer.md](core/digitizer.md)：`core/digitizer`，基于 `pymtl3` 的寄存器递增器数字电路模型与仿真。
- [core/reconstruction.md](core/reconstruction.md)：`core/reconstruction`，波形脉冲极性转换、基线扣除、定时量（`ToA`、`ToT`、`CoG`、`CFD`）、脉冲面积、团簇算法与 `reconstruction_<job>.h5` 读写。
- [core/analysis.md](core/analysis.md)：`core/analysis`，电荷收集效率计算、截断高斯迭代拟合核心宽度 `core_width` 与 `WaveformStatistics`。

### 组件定义（`components`）

- [components/device.md](components/device.md)：`components/device`，平面型、条型、像素型、3D、LGAD 与 HEMT 等器件 JSON 定义及网格脚本。
- [components/source.md](components/source.md)：`components/source`，束流（`beam`）、放射源衰变（`decay`）与简化最小电离粒子（`toy`）源 JSON 定义。
- [components/laser.md](components/laser.md)：`components/laser`，TCT 激光注入参数 JSON 定义与硅材料吸收系数表。
- [components/g4setup.md](components/g4setup.md)：`components/g4setup` 与 `components/g4macro`，Geant4 几何环境 Python 脚本（`G4SETUP`）与可视化宏。
- [components/afe.md](components/afe.md)：`components/afe`，前端放大器与端接电路 SPICE 子电路文件（`.cir`）。
- [components/adc.md](components/adc.md)：`components/adc`，含 `threshold`、`amplitude_threshold` 两个键的 `scope.json`。

### 基准实验（`bench`）

- [bench/cce.md](bench/cce.md)：`raser cce`，电荷收集实验工作流。
- [bench/signal.md](bench/signal.md)：`raser signal`，单器件信号仿真工作流。
- [bench/tct.md](bench/tct.md)：`raser tct`，瞬态电流技术（TCT）激光脉冲仿真工作流。
- [bench/telescope.md](bench/telescope.md)：`raser telescope`，束流望远镜（`taichu_v1`、`taichu_v2`）空间分辨仿真工作流。
- [bench/timeres.md](bench/timeres.md)：`raser timeres`，时间分辨实验工作流。

### 专用应用（`apps`）

- [apps/bmos.md](apps/bmos.md)：`raser bmos`，束流监测在线系统（BMOS）束团脉冲仿真工作流。
- [apps/cflm.md](apps/cflm.md)：`raser cflm`，CEPC 快速亮度监测器（CFLM）24 垫片束团丢失电子仿真工作流。

### 工程支撑（`supports`）

- [supports/README.md](supports/README.md)：`supports`，运行时路径解析、输出目录边界检查、缺失依赖异常、进程清理回调与内存统计装饰器。
