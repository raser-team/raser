# 共享支撑模块

_位于 `src/raser/supports/` 的 RASER 5.0 工程基础设施_

Supports 提供 CLI、Applications 与 Core 共用的机制。科学模型、物理过程、工作流默认值与分析策略归属各自模块。

---

## 📦 模块

| 模块 | 职责 | 详细契约 |
| --- | --- | --- |
| `paths.py` | 工作根目录、项目根目录、组件查找与应用资产 | [Paths](paths.md) |
| `runs.py` | 运行配置、标识、记录与选择 | [Runs](runs.md) |
| `jobs.py` | 索引化本地执行 | [Jobs](jobs.md) |
| `batchjob.py` | IHEP 提交与 Apptainer worker 命令 | [Jobs](jobs.md) |
| `output.py` | 所属目录与小型文件系统操作 | [Output](output.md) |

`io_decorator.py`、`memory_decorator.py` 与 `root_tree.py` 提供范围明确的诊断或格式工具。调用者决定测量、转换或序列化在工作流中的位置。

科学插值、卷积、拟合及其他数值行为属于相关 Core 能力契约。

## 📋 边界

调用者提供科学意图与规范化数据。Supports 可解析路径、保存基础运行规格、执行结构化命令、创建指定目标，或转换一种声明的格式。每次调用以规范化值传入明确的策略输入。

应用持有收集器与产物模式。Supports 提供运行查找与执行机制。应用收集器对缺失事件文件进行分类，并选择 Core metrics。

## 🔗 依赖方向

```text
CLI ───────────────┐
Applications ──────┼──> Supports ──> 文件系统 / 进程 / 调度器
Core ──────────────┘
```

CLI、Applications 与 Core 指向 Supports 的依赖边终止于 Supports。跨模块工具接收明确的类型化数值，并保留可见错误。
