# 运行记录

_位于 `src/raser/supports/runs.py` 的 RASER 5.0 运行配置与标识_

---

## 📋 职责

Runs 将应用提供的规范化规格转为不可变执行记录，并解析明确指定的运行或最新兼容运行。应用持有工作流默认值与结果模式；科学对象校验自身数值；Jobs 执行 worker。

## ⚙️ 配置优先级

工作流数值按以下顺序解析：

1. 明确的命令值
2. 命名运行配置或明确的运行配置
3. 项目组件保存的值
4. 被引用 Device 或其他可复用对象持有的默认值
5. 应用持有的通用默认值

命名配置解析至 `<project>/config/<name>.json`；明确文件从给定路径读取。配置填充未指定值，同时保留路由所选的项目上下文。

## 📥 规范化规格

| 字段 | 契约 |
| --- | --- |
| 工作流 | 所属工作流与输出命名空间 |
| 组件引用 | 项目组件及引用的 Device、source 或电子学标识 |
| Device 状态 | 解析后的偏压、温度与辐照状态 |
| Field 配置 | 解析后的偏压、温度、辐照、维度、source 及 source 特定设置 |
| Field 数据 | 完整 Field 配置的哈希，用于寻址 Device 持有的资产 |
| 工作分配 | 每个 worker 的事件数与计划 worker 数 |
| 电子学 | 适用时选择的 PCB、ASIC、AFE 与 ADC 标识 |
| 运行标识 | 明确 ID，或带创建时间的新分配 ID |
| 来源信息 | 可用时记录已解析来源、代码版本与工作树状态 |

规格包含规范化基础值。`run.json` 在任务展开前写入一次，并在整个执行期间保持不变。

## 📦 包络与选择

```text
<project>/<workflow>/<run_id>/
├── run.json
├── batch/
└── analysis/
```

每个 worker 将其索引化产物写入 `batch/`。所属应用在校验记录及所有必需 worker 输出后创建 `analysis/`。

`latest` 是临时读取选择器。持久记录携带已分配运行 ID。选择器按请求的元数据筛选兼容记录，并返回唯一的最新匹配项。明确路径精确选择相应运行目录。

## 🔄 生命周期

```mermaid
flowchart LR
    accTitle: RASER 运行记录生命周期
    accDescr: 应用规范化输入、预留一次运行、写入不可变记录、执行索引任务，并在分析前单独校验产物。

    inputs([接收工作流输入]) --> normalize[规范化规格]
    normalize --> reserve[预留唯一运行]
    reserve --> record[写入不可变 run.json]
    record --> jobs[执行或提交索引任务]
    jobs --> batch[(批处理产物)]
    batch --> collect[应用校验并收集]
    collect --> analysis([分析产物])
```

任务执行见 [Jobs](jobs.md)；产物位置遵循 [Output](output.md)。

## ⚠️ 失败契约

无效配置在预留运行前失败。规格缺失时给出缺少的字段。标识冲突在写入前失败。缺失或有歧义的选择触发明确错误。预留后的失败保留运行目录与记录。
