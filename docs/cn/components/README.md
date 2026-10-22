# 组件

组件记录应用项目选用的对象。每个条目具有明确类型，并包含在该场景中使用相应对象所需的引用和项目级取值。

## 组件类型

| 类型 | 在应用项目中的含义 |
| --- | --- |
| [Device](device.md) | 一个传感器项目及该场景所选的传感器状态 |
| [PCB](pcb.md) | 一个电路板项目及该场景所选的电路板定义 |
| [ASIC](asic.md) | 一个芯片项目及该场景所选的芯片定义 |
| [G4Setup](g4setup.md) | 场景的 Geant4 场景、放置和灵敏体映射 |
| [AFE](afe.md) | 连接至传感器电学模型的模拟前端 |
| [ADC](adc.md) | 施加于前端波形的数字化定义 |
| [Source](source/README.md) | Interaction 使用的粒子源或衰变源 |
| [Laser](laser.md) | TCT Interaction 使用的光注入 |

## 项目布局

```text
<application-project>/
└── components/
    ├── device/
    ├── pcb/
    ├── asic/
    ├── g4setup/
    ├── afe/
    ├── adc/
    ├── source/
    └── laser/
```

应用绑定其装置所需的组件类型。命名运行配置与调用值通过[运行记录](../supports/runs.md)细化该选择。

Device、PCB 或 ASIC 条目引用持有对象定义和可复用产物的项目。组件记录应用项目采用的状态。G4Setup、Source、Laser、AFE 和 ADC 条目描述应用装置的对应部分，或引用其持有者提供的可复用定义。
