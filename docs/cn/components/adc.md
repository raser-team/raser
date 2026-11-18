# 数字化仪与示波器组件（`components/adc`）

`src/raser/components/adc/` 存放示波器阈值配置的 JSON 文件，当前目录内仅保存 `scope.json` 一份定义文件。仿真链路上波形过阈与幅度筛选的阈值参数实际通过 [`reconstruction`](../stages/reconstruction.md) 环节的 `-threshold` 与 `-amplitude_threshold` 命令行选项设置（完整信号仿真流程见 [快速入门](../getting-started.md)）。

## 文件格式

`src/raser/components/adc/scope.json` 原文如下：

```json
{
    "threshold" : 50,
    "amplitude_threshold" : 100
}
```

| 键名 | `scope.json` 中的值 | 说明 |
| --- | --- | --- |
| `threshold` | `50` | 示波器过阈阈值配置项 |
| `amplitude_threshold` | `100` | 示波器幅度筛选阈值配置项 |

## 库中组件

`src/raser/components/adc/` 包含以下 1 个 JSON 文件：

| 组件名称 | 文件路径 |
| --- | --- |
| `scope` | `src/raser/components/adc/scope.json` |

## 相关页面

- [快速入门](../getting-started.md)
- [`../stages/reconstruction.md`](../stages/reconstruction.md)
- [`../core/digitizer.md`](../core/digitizer.md)
- [`../supports/README.md`](../supports/README.md)
