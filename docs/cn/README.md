# RASER 文档

RASER 围绕可复用的传感器定义，以及将传感器置于测量或仿真场景中的应用组织。

## 设计

| 文档 | 主题 |
| --- | --- |
| [架构](architecture.md) | 代码分层、项目类型与科学数据流 |
| [入门](getting-started.md) | 环境配置与首批命令 |
| [CLI](cli/README.md) | 命令路由与项目选择 |

## 科学核心

| 文档 | 主题 |
| --- | --- |
| [Device](core/device.md) | 传感器定义、默认值、几何及 Device 项目数据 |
| [Field](core/field.md) | 半导体物理、网格、求解、转换及 Field 数据 |
| [Interaction](core/interaction.md) | 粒子、激光及指定的载流子生成 |
| [Current](core/current.md) | 载流子输运、增益及电极感应电流 |
| [Frontend](core/frontend.md) | 传感器电学模型与前端电路计算 |
| [Metrics](core/metrics.md) | 波形与读出观测量 |

PCB、ASIC 和 ADC 设计维护在 [`core/draft/`](core/draft/) 下。

## 应用

| 文档 | 场景 |
| --- | --- |
| [Signal](apps/signal.md) | Device 对粒子源的响应 |
| [TCT](apps/tct.md) | 激光瞬态电流与位置扫描 |
| [时间分辨](apps/timeres.md) | 使用专属装置的时间测量 |
| [电荷收集](apps/cce.md) | 使用专属装置的电荷测量 |
| [BMOS](apps/bmos.md) | 束流监测器响应 |
| [Lumi](apps/lumi.md) | 亮度监测器仿真 |
| [Telescope](apps/telescope.md) | 多层径迹与重建 |

[应用概览](apps/README.md)列出了各场景绑定的组件。

## 组件

| 文档 | 所选对象 |
| --- | --- |
| [Device 组件](components/device.md) | Device 项目及应用所选传感器状态 |
| [PCB 组件](components/pcb.md) | PCB 项目及应用所选电路板定义 |
| [ASIC 组件](components/asic.md) | ASIC 项目及应用所选芯片定义 |
| [G4Setup 组件](components/g4setup.md) | 应用的 Geant4 场景与对象放置 |
| [AFE 组件](components/afe.md) | 模拟前端电路选择 |
| [ADC 组件](components/adc.md) | 波形数字化选择 |
| [Source 组件](components/source/README.md) | 束流源与衰变源 |
| [Laser 组件](components/laser.md) | 光注入 |

## 支撑模块

| 文档 | 主题 |
| --- | --- |
| [Supports](supports/README.md) | 共享运行时服务 |
| [Paths](supports/paths.md) | 项目上下文与定义查找 |
| [Runs](supports/runs.md) | 已解析的运行配置与记录 |
| [Jobs](supports/jobs.md) | 本地与集群执行 |
| [Output](supports/output.md) | 产物路径与写入器 |
