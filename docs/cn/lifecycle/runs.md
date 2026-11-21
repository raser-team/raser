# 运行记录

_位于 `src/raser/lifecycle/` 的实验、扫描与运行记录_

---

## 输入

一次运行由器件、默认和实验配置决定。

**器件**放在默认注册的位置 `work/<器件>/`，偏压默认值在[器件定义](../components/device.md)里。

**默认**来自三处：

| 来源 | 内容 |
| --- | --- |
| 器件定义 | 偏压、辐照等器件状态 |
| 工作流 | 用哪个源、前端、ADC、G4Setup，以及每个任务的事例数；写在应用目录下，例如 `src/raser/apps/cce/charge_collection.json` |
| [组件](../components/README.md)定义 | 被选中的源、G4Setup 等文件本身的值 |

**实验**是一个文件夹，带一份 `config.json`，只写相对默认改了什么、扫什么：

```json
{
  "workflow": "cce",
  "device": "HPK-Si-PiN",
  "set": {"events_per_job": 20},
  "scan": {"voltage": [200, 300]}
}
```

| 键 | 含义 |
| --- | --- |
| `set` | 这个实验里固定改掉的值，每个点都用。上例把每个任务的事例数改成 20 |
| `scan` | 要逐个试的值，每个值是一个点。上例是 200 V 和 300 V 两个点；写了几个参数就跑它们的全部组合 |

`set` 和 `scan` 里的参数名是命令选项（如 `voltage`），或器件、源、G4Setup 定义里的地址（如 `source.par_energy`）。实验文件夹放在哪里、在哪里运行由用户决定，`work/` 是推荐位置。

## 运行

当前目录没有 `config.json` 时，命令落到器件下以工作流命名的文件夹并生成 `config.json`：

```bash
raser cce HPK-Si-PiN -s 4        # work/HPK-Si-PiN/cce/
```

在实验文件夹里，`raser -s 4` 与上面带子命令的写法等价。

没有扫描就跑一个点，有扫描就扫。扫描也可以在命令行直接给出：

```bash
raser cce HPK-Si-PiN -s 4 --scan voltage=200,300
```

| 选项 | 含义 |
| --- | --- |
| `-s <n>` | 每个种子文件夹分成的[任务](jobs.md)数 |
| `-b` | 把任务提交到[集群](jobs.md#运行) |
| `--seed <n>` | 固定种子 |
| `--dry-run` | 只显示将要运行的内容 |

一条命令为每个点建一个种子文件夹，再把它分成任务运行；任务怎样生成、在本机或集群怎样执行见[任务](jobs.md)。

改实验的参数时，器件的场保持已有求解结果。

## 输出

扫描时自动开子文件夹，名字只写变了的参数，平铺，例如 `voltage_300_al_0.05/`。没变的那个点放在实验文件夹根部。`config.json` 中的 `"name"` 一行给出名字模板。

每个点下面有一层种子文件夹。默认种子取时间戳，文件夹以时间戳命名；固定种子的文件夹为 `seed_42/`。

种子文件夹里的 `run.json` 记这次的配置和 commit。固定种子再次运行时，配置或 commit 与记录不同就重跑，旧结果保留。工作区有未提交改动时给出警告。

```text
work/HPK-Si-PiN/cce/
├── config.json
├── 2026_1112_133122/
│   ├── run.json
│   └── batch/
├── seed_42/
│   ├── run.json
│   └── batch/
├── voltage_300/
│   └── 2026_1112_133210/
│       ├── run.json
│       └── batch/
└── analysis/
```

各任务向所属种子文件夹的 `batch/` 写入产物，内容见[任务](jobs.md#输出)。汇总结果写在 `analysis/` 下。
