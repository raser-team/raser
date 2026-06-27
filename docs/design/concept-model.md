# RASER 概念模型

RASER 面向传感器仿真、测试工作流和系统应用。
代码按 Core、对象、Apps 和 Support 四层组织。
Core 提供可复用计算能力。
对象层保存可被多个工作流引用的物理对象。
Apps 定义用户可运行的物理工作流。
Support 提供路径、批处理、运行记录和通用 IO。

## Core

Core 放在 `src/raser/core`。
Core 面向跨工作流复用的计算能力。
Core 的输入来自对象、运行参数和已有资产。
Core 的输出由调用它的 App 或 Support 写入工作区。
Core 可被多个 Apps 调用。

Core 包括器件建模、电场计算、粒子相互作用、电流计算、模拟电子学、数字电子学、控制逻辑和事例统计。
器件建模定义传感器在计算中的几何、掺杂和接触表示。
电场计算提供电势、电场、陷阱率和权重场的读取、求解和转换能力。
粒子相互作用计算提供能量沉积和载流子产生。
电流计算把载流子运动转换为感应电流。
模拟电子学计算提供信号放大、整形和模拟读出。
数字电子学计算提供数字处理和寄存器级逻辑。
控制逻辑计算提供控制器和读出调度逻辑。
事例统计把多个事例的信号和波形转换为统计结果。

## 对象

对象集中在对象层管理。
对象层放跨工作流复用的物理对象。
对象描述物理实体、装置部件和可复用配置。
一次 run 的结果归入 work 目录。
Apps 通过名字或路径引用对象。

对象层包括传感器、激发源、电子学、材料和可复用实验 setup。
传感器定义探测器本体的几何、材料、掺杂、接触和稳定网格描述。
激发源定义作用于传感器或 setup 的外部输入。
电子学定义信号读出、数字处理和控制逻辑对象。
材料定义仿真计算中使用的物质属性。
可复用 setup 定义可被多个 App 引用的布置对象。

激发源对象目录使用 `beam`、`decay`、`laser` 和 `synch`。
电子学对象目录使用 `analog`、`digital` 和 `control`。
传感器 JSON 中的稳定结构包括 `read_out_contact` 和 `mesh`。
传感器 JSON 中的电压和场选择属于默认工作点或运行选择来源。

## Apps

Apps 放在 `src/raser/apps`。
Apps 用物理目标组织对象、Core 计算和结果压缩。
公共 CLI 以 Apps 和用户级资产命令作为主要入口。
Core 调试入口放在 `raser dev` 下。
Apps 下面管理本 App 自己的 Geant4 几何 JSON。
App 的 Geant4 几何 JSON 直接放在对应 App 目录下。

`signal`、`cce` 和 `timeres` 是传感器表征工作流。
对这些工作流，传感器就是 work project。
输出路径以 `work/<sensor>/<workflow>/...` 为根。
`field` 是传感器资产工作流。
Field 资产输出路径以 `work/<sensor>/field/...` 为根。
`bmos`、`lumi` 和 `telescope` 是系统或应用工作流。
对这些工作流，传感器或传感器配置是 App 的输入对象。
输出路径以 `work/<app>/<config-or-sensor>/...` 为根。

### Signal

Signal 工作流保存一次完整信号链。
Signal 的 scan/job 编排是多个工作流共享的执行机制。
Signal 提供 CCE 和 Timeres 可复用的信号产生机制。

### CCE

CCE 工作流定义电荷收集效率测量。
`raser cce run <sensor> [source]` 产生事件或 batch 数据。
`raser cce analyze <sensor> --run <run>` 消费已有 run 并产生统计或图。

### Timeres

Timeres 工作流定义时间分辨测量。
`raser timeres run <sensor> [source]` 产生事件或 batch 数据。
`raser timeres analyze <sensor> --run <run>` 消费已有 run 并产生统计或图。

### TCT

TCT 工作流用可控激光注入扫描传感器位置或深度响应。
TCT 使用激光对象作为激发源。

### BMOS

BMOS 工作流从束流粒子在监测传感器中的能量沉积和读出响应估计束流强度。

### Lumi

Lumi 工作流从碰撞产物在监测几何中的命中、电流或计数估计束流亮度。

### Telescope

Telescope 工作流用多层传感器命中重建径迹并评估空间分辨。

## Field 资产

Field 是传感器级可复用资产。
Field 归属 work 中的传感器项目。
Field 由用户求解、导入或派生。
一个 field 资产可以被多个 workflow 和多个 App run 复用。
Field set 是同一传感器下的一组场产物。
默认 field set 命名为 `default`。

Field App 提供用户级资产命令。
`raser field solve <sensor>` 复用现有电场求解能力。
`raser field import <tdr-file>` 复用现有 TCAD 导入能力。
`raser field weight <voltage> <electrode> <sensor>` 复用现有权重场派生能力。
运行前轻量文件检查属于 `run` 入口。
用户级 field 命令聚焦资产生成、导入和派生。

Field 产物保持现有计算契约。
Field 产物包括 `Potential_<V>V.pkl`、`NetDoping_<V>V.pkl`、`TrappingRate_p_<V>V.pkl`、`TrappingRate_n_<V>V.pkl` 和 `weightingfield/<contact>/Potential_1V.pkl`。
工作流通过 field set 和 field source 引用这些产物。

## Run

Run config 是运行前输入。
Run record 是运行后或提交后的记录。
二者分别承担控制输入和执行记录。

Run config 定义这次工作流打算怎么跑。
Run config 可以来自 App 默认、project 默认或 CLI 覆盖。
库内 App 默认由 App 入口或 App 配置常量表达。
用户可编辑 run config 应放在 work/project 中。

Run record 记录一次实际执行的解析结果和产物位置。
Run record 可保存为 run 目录下的 `run.json`。
Run record 包括 workflow、sensor、source、field set、field source、voltage、events、jobs、electronics、daq、git 和 run id。

新 run 的默认 run id 使用创建时刻的 `YYYY_MMDD_HHMMSS` 时间戳。
显式 `--run` 提供外部调度、测试和复现需要的固定 run id。
Run 输出使用 `work/<sensor>/<workflow>/<run>/`。
Run 的物理条件和软件状态记录在 `run.json`。
`analyze` 消费已有 run 并产生统计结果。
`latest` 在已有 run record 中选择最近一次 run。

## Support

Support 放在 `src/raser/supports`。
Support 提供路径、组件查找、批处理、indexed job、运行记录、IO、装饰器和通用工具。
Signal scan/job 的命令展开属于 Support。
Support 服务 Core、对象和 Apps。
Support 的职责是工程基础设施。
