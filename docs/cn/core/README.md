# 科学核心

_RASER 5.0 的可复用科学计算_

Core 包含 RASER 应用组装的传感器定义与计算。软件包级数据流见[架构](../architecture.md)。

## 模块

| 模块 | 科学内容 |
| --- | --- |
| [Device](device.md) | 传感器定义、默认状态、几何、接触、读出布局、电学量与模型选择 |
| [Field](field.md) | 半导体方程、网格生成、数值求解、TCAD 转换与场数据 I/O |
| [Interaction](interaction.md) | Geant4 能量沉积、激光激励与指定的 MIP 载流子生成 |
| [Current](current.md) | 载流子输运、俘获、增益与电极感应电流 |
| [Frontend](frontend.md) | 传感器电学建模、AFE 电路组装与波形计算 |
| [Metrics](metrics.md) | 波形测量、电极组合与事件统计 |

## 草稿

- [PCB](draft/pcb.md)
- [ASIC](draft/asic.md)
- [ADC](draft/adc.md)
