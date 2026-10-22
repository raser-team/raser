# PCB 构思草稿

_非规范性设计说明_

`PCB` 类描述一块电路板。其项目目录保存可在不同应用场景间复用的电路板产物。

## 🧩 拟定职责

`PCB` 定义覆盖电路板标识、材料、层、元件放置、连接关系，以及保持几何与电学表示一致所需的映射。它持有由该定义产生的可复用产物：

- 电路板 GDML
- 电路板元件的 Geant4 表示与放置
- 板级模拟仿真定义与结果
- 板级数字仿真定义与结果

应用可将这些产物组装为探测器测试、辐照或读出场景。场景输入、运行记录，以及测量或仿真响应归属相应应用。

## 🗂️ 候选产物分组

```text
<pcb>/
├── pcb.json
├── geometry/
│   └── <gdml-and-placement-products>
├── geant4/
│   └── <component-representations>
├── analog/
│   └── <simulation-definitions-and-results>
└── digital/
    └── <simulation-definitions-and-results>
```

这些名称是暂定的归属分组。后续契约将确定文件格式，并定义贯穿 PCB 网络、物理放置、Geant4 体、模拟节点与数字信号的稳定组件标识和映射。

## ❓ 待确定的设计点

- 电路板及其已安装元件的标识与版本规则
- 网表、几何、Geant4、模拟和数字表示之间的共享映射
- PCB 引用可复用 ASIC 产物、ASIC 保留其定义的方式
- 属于稳定电路板资产的仿真产物，以及属于具体应用场景的仿真产物
