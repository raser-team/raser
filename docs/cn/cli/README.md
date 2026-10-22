# 命令行接口

_位于 `src/raser/cli/` 的 RASER 5.0 安装入口_

受支持的入口为 `raser`。用户说明采用该安装命令；源码树中的模块调用属于实现细节。

---

## ⌨️ 命令表面

```bash
raser --help
raser <command> --help
```

| 公共命令 | 所属模块 |
| --- | --- |
| `bmos` | [`apps/bmos`](../apps/bmos.md) |
| `cce` | [`apps/cce`](../apps/cce.md) |
| `field` | [Core Field](../core/field.md) |
| `frontend` | [Frontend](../core/frontend.md) |
| `current` | [Current](../core/current.md) |
| `metrics` | [Metrics](../core/metrics.md) |
| `lumi` | [`apps/lumi`](../apps/lumi.md) |
| `signal` | [`apps/signal`](../apps/signal.md) |
| `tct` | [`apps/tct`](../apps/tct.md) |
| `telescope` | [`apps/telescope`](../apps/telescope.md) |
| `timeres` | [`apps/timeres`](../apps/timeres.md) |

CLI help 是命令语法与选项的依据。未注册的顶层形式会明确失败。

## 🔀 路由

[`raser.py`](raser.md) 负责解析、路由描述、延迟导入、临时项目与组件上下文、进程退出状态、全局批处理分发和运行时清理。应用从路由器接收解析后的顶层参数值。

每条路由最多声明一个项目选择器。项目推断与组件查找遵循 [Supports 路径](../supports/paths.md)。

## ⚙️ 批处理边界

全局 `raser -t -b <command>` 提交一条完整命令。应用的索引模式将一次已记录运行展开为多个 worker。相应边界见 [Jobs](../supports/jobs.md) 与 [Runs](../supports/runs.md)。
