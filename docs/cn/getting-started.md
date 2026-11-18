# 快速入门：环境激活与第一次运行

本页说明在安装好 RASER 运行环境后，如何激活环境并用内置硅平面探测器 `HPK-Si-PiN` 跑通**信号扫描仿真 → 查看状态 → 统计分析**完整流程，以及在各个输出目录中查看哪些文件与图。

## 激活运行环境

若尚未安装环境，可在仓库根目录运行 `env/install_conda.sh` 完成本地 Conda 与 Python 依赖配置。环境装好后，每次打开新终端时激活环境：

```bash
# 本地 Conda 环境
source env/setup.sh

# 或在挂载了 /cvmfs / 配置了 SIF 容器镜像的集群节点上
source env/setup_cvmfs.sh
```

激活后可通过以下命令确认 `raser` 可用并查看子命令列表：

```bash
raser --version
raser --help
```

## 第一步：运行信号扫描仿真（`raser signal`）

对 `HPK-Si-PiN` 扫描偏置电压 `100 V` 与 `200 V`，每个偏压跑 `2` 个并行作业（`-s 2`）、每个作业记录 `200` 个有效事例（`-evt 200`），并固定随机种子 `--seed 1`。正式运行前可加 `--dry-run` 预览各扫描点和作业清单，确认无误后直接启动仿真：

```bash
raser signal HPK-Si-PiN --scan voltage=100,200 -s 2 -evt 200 --seed 1
```

默认使用 `decay/Sr90` 放射源、`device_alone` 几何和 `SantaCruz+Gali52+Termination50` 放大器链。执行过程中终端会先打印各扫描点的切片与作业规划，检测到场尚未求解时自动调用 `raser field` 补算所需偏压的场，随后完成各作业的五个切片（以下省略 `work/` 之前的绝对路径）：

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
work/HPK-Si-PiN/signal/seed_1: jobs [0, 1]
  deposit        jobs [0, 1]
  field          jobs [0, 1]
  current        jobs [0, 1]
  readout        jobs [0, 1]
  reconstruction jobs [0, 1]
the field is not ready: raser field HPK-Si-PiN -bias 100.0
work/HPK-Si-PiN/field: jobs [0]
...
the field is not ready: raser field HPK-Si-PiN -bias 200.0
work/HPK-Si-PiN/field: jobs [0]
...
raser: the job ran its slices: deposit,field,current,readout,reconstruction
```

这次运行中有几点直接可见的事实：

- **共享场自动求解**：`100 V` 与 `200 V` 的场未事先算好时，`raser signal` 先打印 `the field is not ready: raser field HPK-Si-PiN -bias 100.0`（及 `200.0`）并自己调用 `raser field` 求解，写入 `work/HPK-Si-PiN/field/`，再接着运行信号仿真链。
- **默认偏压点的位置**：`200 V` 是 `HPK-Si-PiN` 器件文件里的默认偏压，所以 `200 V` 这个点的结果落在实验根目录 `work/HPK-Si-PiN/signal/seed_1/`，而 `100 V` 落在 `work/HPK-Si-PiN/signal/voltage_100/seed_1/`。
- **生成与记录事例数**：在该几何与放射源下，四个作业各记下 `200` 个有效沉积事例（其中 `200 V` 的作业 `0` 生成 `7359` 个事例；`generated_fraction` 约 `0.017` 是源发射方向中被模拟的比例）。

运行结束后可在以下目录查看输出与图表：

- **共享场目录 `work/HPK-Si-PiN/field/`**：存放 `run.json`、各偏压（`0 V`、`100 V`、`200 V`）下的电势与载流子数据 `.pkl`、`weightingfield/top/` 权重场、`100.0V.undepleted.json`、`200.0V.undepleted.json`，以及 IV、CV 和一维电场分布图。

![HPK-Si-PiN IV 曲线](images/field-iv-HPK-Si-PiN.png)

反向偏压扫描得到的暗电流（IV）曲线，可用于检查器件击穿与泄漏电流随电压的变化。

![HPK-Si-PiN CV 曲线](images/field-cv-HPK-Si-PiN.png)

电容随偏压变化（CV）曲线，反映器件随反偏电压增大逐步耗尽直至电容趋于平缓的过程。

![HPK-Si-PiN 200 V 一维电场分布](images/field-efield-HPK-Si-PiN-200V.png)

`200 V` 偏压下 `HPK-Si-PiN` 沿深度方向的一维电场分布。

- **实验目录 `work/HPK-Si-PiN/signal/`**：顶层写入 `config.json`，每个扫描点种子目录下包含运行记录 `run.json`、`batch/`（`deposit_<job>.h5`、`current_<job>.h5`、`readout_<job>.h5`、`reconstruction_<job>.h5`、`.done` 标记与 `job_<job>.log`）以及 `plots/job_<job>/event_<事例号>/`（默认绘制前 `100` 个记录事例的载流子漂移路径图 `planar_drift_path.pdf`/`.root` 与电极感应电流图 `No_1electrode_basic_infor.pdf`/`.root`）。

![HPK-Si-PiN 单事例载流子漂移路径](images/current-drift-path-HPK-Si-PiN.png)

`HPK-Si-PiN` 单个事例的载流子漂移路径图（含器件三维体区与局部平面投影中的沉积点、电子和空穴轨迹）。

![HPK-Si-PiN 单事例感应电流](images/current-event-HPK-Si-PiN.png)

`HPK-Si-PiN` 单个事例的感应电流图，分别绘出电子、空穴分量及总感应电流随时间的变化。

## 第二步：查看运行状态（`raser status`）

随时检查实验目录下各扫描点与切片的作业完成进度：

```bash
raser status work/HPK-Si-PiN/signal
```

输出如下（以下省略 `work/` 之前的绝对路径）：

```text
work/HPK-Si-PiN/signal/voltage_100/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
work/HPK-Si-PiN/signal/seed_1:
  deposit     2/2 done
  field       2/2 done
  current     2/2 done
  readout     2/2 done
  reconstruction2/2 done
```

两个偏压点的 `2` 个作业在全部 5 个切片上均显示 `2/2 done`。

## 第三步：统计分析（`raser analysis`）

作业完成后，对实验文件夹运行分析命令（短命令 `raser ana`）：

```bash
raser analysis work/HPK-Si-PiN/signal
```

终端输出（以下省略 `work/` 之前的绝对路径）：

```text
work/HPK-Si-PiN/signal/analysis: jobs [0]
work/HPK-Si-PiN/signal/analysis/voltage_100/result.json
work/HPK-Si-PiN/signal/analysis/result.json
```

与仿真目录相同，默认偏压 `200 V` 的分析结果直接写在 `work/HPK-Si-PiN/signal/analysis/` 根下，`100 V` 的结果写在 `work/HPK-Si-PiN/signal/analysis/voltage_100/`：

- **`result.json`**：汇总电荷收集效率与时间分辨（单位为 `s`）。在 `200 V` 下，全部 `400` 个记录事例的平均收集效率为 `0.9348`（展宽 `0.1445`），有 `276` 个事例幅度达到或超过 `10 mV` 阈值，其中 `CFD30` 时间分辨 `sigma` 为 `33.35 ps`、`sigma68` 为 `31.66 ps`；在 `100 V` 下平均收集效率为 `0.9195`，选中 `257` 个事例。
- **`events.h5`**：所有选中事例的幅度、基线、噪声与各定时量明细表。
- **`points.json` 与 `points.png`**：写在 `analysis/` 根目录下的多偏压点汇总数据与趋势图。
- **单点统计图表**：`efficiency.png`、`amplitude.png`、`time_difference.png` 与 `resolution_of_fraction.png`。

![HPK-Si-PiN 电荷收集效率分布](images/analysis-efficiency-HPK-Si-PiN.png)

`200 V` 下 `400` 个记录事例的电荷收集效率分布直方图，虚线标出平均收集效率 `0.9348`。

![HPK-Si-PiN 脉冲幅度分布](images/analysis-amplitude-HPK-Si-PiN.png)

`200 V` 下幅度达到或超过 `10 mV` 阈值的 `276` 个选中事例的脉冲幅度分布直方图，虚线标出重建时设定的幅度阈值。

![HPK-Si-PiN 时间差分布与截断高斯拟合](images/analysis-time-difference-HPK-Si-PiN.png)

`200 V` 下 `ToA`、`CoG` 与 `CFD10`–`CFD90` 相对真实沉积时刻（`truth`）的时间差分布与截断高斯拟合结果，用于读出时间分辨 `sigma` 与 `sigma68`。

![HPK-Si-PiN 电荷收集效率与时间分辨随偏压变化](images/analysis-points-HPK-Si-PiN.png)

`100 V` 与 `200 V` 两个扫描点的电荷收集效率（左）与各 `CFD` 通道时间分辨（右）对比图。

## 实用小技巧

- **只跑到某一环节**：若只想运行链上前面几步，可运行 `raser deposit|current|readout|reconstruction <target>`（短命令 `dep|cur|rdo|reco`），程序会自动补齐缺少的上游步骤。
- **单独解场**：也可以提前运行 `raser field HPK-Si-PiN` 求解默认偏压下的场，供同一器件后续所有实验共享。
- **正式跑之前先预览**：在任何运行命令后加上 `--dry-run`，可在不实际启动仿真的情况下预览各扫描点将要运行的作业与切片状态。
- **在实验目录内简写命令**：`cd work/HPK-Si-PiN/signal` 后可直接运行 `raser -evt 200 -s 2`，程序会自动从当前目录的 `config.json` 识别工作流与器件。

## 下一步

- 全部命令与模块对应关系：[命令行接口（`raser`）](cli.md)
- 参数设置、扫描（`--set` / `--scan`）与多种子管理：[实验、扫描点与种子](lifecycle/experiments.md)
- `signal` 工作流的完整参数说明：[单探测器信号测试台](bench/signal.md)
- 链上切片复用与文件结构：[架构总纲](architecture.md)、[片、过期判断与状态查看](lifecycle/slices.md)
- 批量作业与集群提交：[作业与集群提交](lifecycle/jobs.md)
