# Device 组件

Device 组件将一个 [Device 项目](../core/device.md)绑定到应用项目。它记录 Device 引用，以及该应用选择的工作状态。

## 定义

```text
<application-project>/components/device/<name>.json
```

条目包含：

- 在应用项目中的名称
- 标识 Device 项目的符号名称或路径
- 所选偏压、温度和辐照状态
- 所选 Field 配置值

解析从 `device.json` 的默认值开始，随后应用 Device 组件中的值，再通过[运行记录](../supports/runs.md)应用命名运行值与调用值。解析后的状态指向 Device 项目保存的一项 Field 配置。

应用在 `run.json` 中记录 Device 引用、定义版本、解析后的状态、Field 配置及 Field 配置哈希。
