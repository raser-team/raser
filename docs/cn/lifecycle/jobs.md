# 作业、日志、锁、断点续跑与集群提交

`src/raser/lifecycle/jobs.py`、`src/raser/lifecycle/scheduler.py` 与 `src/raser/lifecycle/workflow.py` 的作业调度部分承接 [命令行接口（`raser`）](../cli.md) 分发的实验命令和 [仿真链与环节入口（`stages`）](../stages/README.md) 的环节命令。[实验、扫描点与种子](experiments.md) 展开扫描点、[片与重跑](slices.md) 定下哪些节点要新算之后，这三个模块接手执行：先求解还没有的器件场，再按本地进程或 `hep_sub`/HTCondor 集群调度器拆分并启动编号作业，写作业日志和提交记录，并在中断、失败或前置作业完成后续跑。单个作业按依赖顺序运行各环节；写好的节点供下游环节读取，供 `raser status` 查看进度，供后续运行复用。

## 行为

### 本地运行与作业拆分

不传 `-b` 时，主命令按扫描点数目和是否给了 `-s`（`--jobs`），分三种方式在本地执行待跑作业：

- **单个扫描点且省略 `-s`**：在当前进程内直接运行作业 `0`。作业出错时直接抛出原异常。
- **多个扫描点且省略 `-s`**：逐个为每个扫描点启动独立子进程，运行作业 `0`。某个扫描点失败时，主命令打印异常回溯，继续跑完其余扫描点，全部结束后汇总报错退出：

  ```text
  1 of 2 points failed:
    <扫描点>: RuntimeError('the job failed: <异常行> (<作业日志>)')
  ```

  原因是对应作业的子进程返回了非零退出码。打开括号里的作业日志看完整回溯，排除故障后原样重跑原命令（带同一个 `--seed`），已算完的节点按指纹复用。

- **传入 `-s <数量>`**：无论扫描点是一个还是多个，每个扫描点都用本地进程池（`ProcessPoolExecutor`）并行运行待跑作业（作业号 `0` 到 `<数量> - 1`）。最大并发进程数为 $\min(\text{待运行作业数},\, \text{CPU 核数或 } 4)$。池中某个作业退出码非零时，其余作业照常跑完，全部结束后主命令报错退出，附上失败作业的异常摘要与日志路径：

  ```text
  RuntimeError: Local jobs failed for indices [1]
    job 1: <异常行> (<作业日志>)
  ```

  原因是进程池内对应作业的子进程返回了非零退出码。打开括号里的作业日志排查，修复后原样重跑原命令，只补算没算完的节点。

启动各扫描点的作业前，若这块器件的场还没有，主命令先在本地求解；同样输入的场只求解一次。本地刚求解完、却仍判定不可用时，主命令直接中止：

```text
RuntimeError: <环节> was made in this process and is still not ready for a point of <实验文件夹>: waiting would not help
```

原因是刚求解出的场缺少当前扫描点需要的结果，或校验没有通过。查看这个场节点的 `node.json` 和作业日志后再重跑。

加上 `--dry-run` 时，只打印将要运行的扫描点、环节和作业状态，打印完即返回。对 `raser field <实验文件夹>`，打印各扫描点的器件场是 `ready` 还是 `to be made`。

以双偏压扫描为例，下面这条命令在两个偏压点各并行启动作业 `0` 和 `1`：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --seed 1
```

### 作业日志与失败摘要

本地运行的每个作业都写一份作业日志。

- 独立子进程模式与进程池模式（多扫描点或传了 `-s`）把子进程的标准输出与标准错误合并，同时写到终端和作业日志。
- 单扫描点省略 `-s` 的当前进程模式，把 Python 的标准输出、标准错误和异常回溯同时写到终端和作业日志；Geant4 与 ROOT 从 C++ 层直接打印的内容只出在终端。
- 作业跑完本次请求的全部环节后，在日志末尾打印正常结束行 `raser: the job ran its slices: <逗号分隔的环节名>`。
- 本地作业失败时，主命令从作业日志末尾反向查找最后一行 Python 异常（异常名以 `Error`、`Exception`、`Exit`、`Interrupt` 结尾），跳过进程退出时 Geant4 和 ROOT 刷出的 C++ 尾行，拼进终端的报错摘要；没有匹配行时取最后一行非空文本。

### 节点锁

每个节点单独加锁。写到一半的节点带 `.part` 后缀，写完才改成正式的名字，正式名字的节点都是完整结果。

锁是非阻塞排他文件锁（`fcntl.flock`）。锁已被另一进程持有时，命令只打印下面这一行就直接退出：

```text
<对象> is run by another process now; run the command again when it is done
```

原因是另一个 `raser` 进程正在写同一份结果。等对方结束后再重跑，可用 `raser status` 查看进度。

底层文件系统不支持 `flock`（系统调用返回 `ENOLCK`、`ENOTSUP`、`EOPNOTSUPP` 或 `EINVAL`）时，程序打印一行警告后继续运行：

```text
warning: <锁文件> cannot be locked here (No locks available): nothing keeps another command off it
```

原因是实验目录所在的网络文件系统不支持文件锁，并发写入失去保护。此时需人工避免同时向同一实验发起写命令；查进度改用只读的 `raser status` 或 `--dry-run`。

### 集群提交与宿主机提交队列

传入 `-b`（`--batch`）时，主命令把每个待运行作业写成可执行脚本 `<command_name>.job`（权限 `0o755`），交给 `RASER_SCHEDULER` 指定的集群调度器提交；省略 `-s` 时提交作业 `0`。`-b` 写在子命令前作全局选项时可连写为 `-b`、`-bb`、`-bbb` 等，内存档位取 $\max(\text{-mem},\, \text{全局 } \texttt{b} \text{ 的个数})$，实际向调度器申请 $8000 \times \text{档位}\ \text{MB}$ 内存。顶层 `-t`（`--test`）只在与顶层 `-b` 同时给出时生效，只检查并预览提交信息。

作业脚本与提交文件放在 `<project_root>/<命令首词>/jobs/`，路径解析见 [公共基础设施（`supports`）](../supports/README.md)。脚本开头先清除登录节点的 X11 环境变量、导出 `RASER_CLUSTER_JOB=1`，再从容器绑定变量中滤掉 X11 挂载项。从源码树运行时，脚本先 `cd` 到仓库根目录，再激活 `env/setup_cvmfs.sh <路线名>`（未设 `RASER_ENV_ROUTE` 时执行 `env/setup.sh`）；以 Python 包安装运行时，脚本 `cd` 到提交时的当前工作目录，沿用调度器环境。

以申请两档内存（`16000 MB`）提交两个作业为例：

```bash
raser -bb signal HPK-Si-PiN -s 2 --seed 1
```

默认调度器 `hep_sub` 下，每个作业执行 `hep_sub -o <jobs目录> -e <jobs目录> <job文件> -mem 16000 -g <当前目录用户组>`。`RASER_SCHEDULER=condor` 下，额外生成 `<command_name>.sub` 并执行 `condor_submit <sub文件>`，`.sub` 内容形如：

```text
executable = /.../work/HPK-Si-PiN/signal/jobs/<command_name>.job
output = /.../work/HPK-Si-PiN/signal/jobs/<command_name>.out
error = /.../work/HPK-Si-PiN/signal/jobs/<command_name>.err
log = /.../work/HPK-Si-PiN/signal/jobs/<command_name>.log
request_memory = 16000
getenv = True
+JobFlavour = "workday"
queue
```

配置校验失败或批量提交部分出错时，程序按触发点报错：

- **`-mem` 为 `0` 或负数**：抛出 `ValueError: Indexed job memory level must be positive`（直接调用 `scheduler.plan_job` 时为 `ValueError: Batch memory level must be positive`）。把 `-mem` 改为正整数即可。
- **`RASER_SCHEDULER` 不是 `"hep_sub"` 或 `"condor"`**：写出脚本与提交前抛出 `ValueError: Unknown scheduler: <值>`。改回 `"hep_sub"` 或 `"condor"` 后重跑。
- **`RASER_CONDOR_JOB_FLAVOUR` 不在允许的 `7` 个取值内**：`condor` 模式下抛出 `ValueError: Unknown HTCondor job flavour: <值>`。改为 `"espresso"`、`"microcentury"`、`"longlunch"`、`"workday"`、`"tomorrow"`、`"testmatch"`、`"nextweek"` 之一即可。
- **批量提交时部分作业失败**：主命令仍逐个尝试提交同批其余作业，全部尝试完后抛出：

  ```text
  RuntimeError: Cluster accepted indices [0, 2]; failed indices [1]
  ```

  启用 `RASER_SUBMIT_QUEUE` 时报错中的 `accepted` 为 `queued`：

  ```text
  RuntimeError: Cluster queued indices [0, 2]; failed indices [1]
  ```

  原因是部分作业调用 `hep_sub`/`condor_submit` 返回非零，或写队列文件失败；其余作业已正常提交。看紧随其后的原始异常（如调度器临时拒绝、作业数超配额、组权限或队列文件路径不可写），排除故障后重跑原 `-b` 命令。直接提交模式下，已接受的作业留有提交记录，会自动跳过。

在不含调度器客户端的 SIF 容器内运行时，宿主机封装函数设置 `RASER_SUBMIT_QUEUE` 指向临时队列文件。该变量非空时，程序把每条提交命令追加写入队列文件，等容器内命令退出后由宿主机逐行提交。写队列时拿不到集群作业号，所以程序跳过原命令的记录，并在提交前打印：

```text
the jobs go to the queue the host submits: a job that waits for others is not started again by itself; run the command again when those are done
```

跳过原命令的记录，是为了防止作业跑完后重复提交整批作业。用集群命令或 `raser status` 确认前置的器件场或上游节点全部跑完后，在宿主机重新运行原命令即可。这种模式跳过提交记录的写入，已入队的作业算完之前再跑同一条 `-b` 命令，会重复入队。

### 提交记录与集群自动续跑

直接向调度器提交、并从调度器标准输出中匹配到 `submitted to cluster (\d+)` 后，主命令为这个作业原子写出一份提交记录，内容是集群作业号与提交时间：

```json
{"job": "123456", "time": "2026-11-22 04:30:00"}
```

作业在集群上跑完对应环节后，自动删除这份提交记录。

集群作业脚本导出了 `RASER_CLUSTER_JOB=1`。集群作业在本次执行中新算完了至少一个所请求的环节时，退出前按顺序自动重新拉起等待它的命令：

1. **外部等待命令**：例如实验在 `-b` 模式下触发了还没有的器件场求解（见 [场求解环节（`stages/field`）](../stages/field.md)），这个实验的命令和工作目录记为等待场作业的命令。场作业跑完后在原工作目录下重启该命令，退出码为 `0` 后把它从等待列表中移除。递归深度上限为 `8` 层。
2. **本实验命令**：`-b` 直接提交时，主命令记下原命令和工作目录。用于跨扫描点共用的上游节点算完后，自动提交等待它的下游扫描点。命令在记录的工作目录下重启。递归深度上限等于链上环节的个数。

每次自动拉起前打印 `starting the command again: raser <命令>`，并把子进程环境变量 `RASER_RESUBMIT_DEPTH` 加 `1`。为应对同时结束的另一作业还占着锁，每次拉起最多尝试 `4` 次，相邻两次之间等待 `30 s`。自动拉起运行在集群节点上，`RASER_CLUSTER_JOB=1` 仍有效，因此已有提交记录的作业直接跳过，只提交此前没提交过的作业。

自动续跑失败或达到嵌套深度上限时，作业 `.out` 日志末尾出现以下三行之一：

```text
the command did not start again in 4 tries: give it again when the jobs it waits for are done
not starting the command again: <深度> starts deep, as many as the slices of the chain
not starting raser ...: 8 starts deep
```

第一行说明 `4` 次尝试（每次间隔 `30 s`）都返回非零，常见于另一作业正占锁，或工作节点缺少运行环境与调度器客户端。后两行说明自动拉起已到嵌套深度上限（本实验命令为链上环节的个数，外部等待命令为 `8` 层），程序主动停下，防止循环提交。查看 `<project_root>/<命令首词>/jobs/` 下 `.out`/`.err` 中每次 `starting the command again: raser ...` 下方的输出；等前置作业完成后，在登录节点手动重跑原命令即可继续。

### 中断续跑

中断或失败后，原样重跑同一条命令（带同一个 `--seed`）即可续跑：已算完的节点按指纹复用，写到一半的节点带 `.part`，只有正式名字的节点算作结果。代码版本和节点记录的不一致时，只给一条提示，结果照常复用。

再次运行时，已提交到集群、还没算完的作业按调度器的回答分别处置。在登录节点重跑 `-b` 时，`hep_sub` 调用 `hep_q -u <当前用户>` 查询，`condor` 调用 `condor_q <集群作业号> -af ClusterId` 查询，单次查询超时 `120 s`：

| 作业的情况 | 本地再运行 | 登录节点 `-b` 再运行 | 集群节点自动续跑 |
| --- | --- | --- | --- |
| 所请求的环节都已算完 | 跳过 | 跳过 | 跳过 |
| 没算完，没有提交记录 | 补算缺的节点 | 提交 | 提交 |
| 没算完，有提交记录，调度器确认仍在集群中 | 直接运行 | 跳过，打印 `are submitted already` | 跳过 |
| 没算完，有提交记录，调度器确认已不在集群中 | 直接运行 | 删除提交记录并重新提交 | 跳过 |
| 没算完，有提交记录，调度器报错或 `120 s` 超时 | 直接运行 | 保持原状 | 跳过 |
| 要读的器件场或上游节点还没算完 | 跳过并打印等待原因 | 跳过并打印等待原因 | 跳过并打印等待原因 |

各种情况的终端提示如下。行首的 `<位置>` 是作业所在的扫描点。

- **仍在集群中**：

  ```text
  <位置>: jobs [0, 1] are submitted already
  ```

  对应作业已在集群排队或运行，命令跳过它们以免重复提交；等它们完成即可。

- **集群上已消失**：

  ```text
  <位置>: job 0 (123456) is no more on the cluster: it failed and is submitted again
  ```

  调度器确认集群上已无该作业，而它没有算完。程序已删掉旧提交记录并重新提交，重提后仍复用已算完的上游节点。到 `<project_root>/<命令首词>/jobs/` 查看上次作业的 `.out`/`.err` 排查原因，例如被内存限制杀掉时调高 `-mem`。

- **调度器无法查询**：

  ```text
  <位置>: job 0 (123456): the scheduler cannot be asked; left as it is
  ```

  调用 `hep_q` 或 `condor_q` 报错、找不到命令或超过 `120 s`，程序保留提交记录，保持原状。切到有调度器客户端的登录节点、核对 `RASER_SCHEDULER`，待调度器恢复后再跑；已人工确认该作业结束时，删掉它的提交记录后重跑。

- **等待器件场或上游节点**：

  ```text
  <位置>: jobs <作业号列表> wait for <依赖说明>; run the command again when it is done
  ```

  要读的器件场还没求解完，或另一个扫描点要算的上游节点还没写好。命令把这个扫描点记入失败列表并跳过这些作业。直接提交到集群时，前置作业完成后通常会自动重拉；用宿主机提交队列、达到递归上限或本地另一进程占锁时，等前置作业完成后再运行原命令即可。

## 规则

### 内置常数

下表是 `jobs.py`、`scheduler.py` 与 `workflow.py` 作业调度部分的内置常数。它们写死在代码中：

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| 默认进程池回退并发数 | `4` | 个 | `jobs.py` `run_indexed_jobs` 中 `os.cpu_count() or 4`，取不到 CPU 核数时的最大并发进程数 |
| `_RAISED` | `^[A-Za-z_][\w.]*(Error\|Exception\|Exit\|Interrupt)\b` | 无 | `jobs.py`，从日志末尾反向匹配 Python 异常行的正则表达式 |
| 单档内存基准 | `8000` | $\text{MB/档}$ | `scheduler.py` `plan_job` 中 `memory_mb = 8000 * batch_level`，每档内存对应的兆字节数 |
| `_NAME_BYTES` | `200` | $\text{B}$ | `scheduler.py`，集群作业脚本基名 `command_name` 的 UTF-8 最大字节数；超长时截断前缀至 `183` $\text{B}$，拼 `_` 与 `16` 位十六进制 SHA-256 摘要 |
| 脚本文件权限 | `0o755` | 无 | `scheduler.py` `gen_job`，写出的 `<command_name>.job` 的权限 |
| `allowed_flavours` | `{"espresso", "microcentury", "longlunch", "workday", "tomorrow", "testmatch", "nextweek"}` | 无 | `scheduler.py` `plan_job`，`condor` 后端允许的 `+JobFlavour` 取值 |
| 集群作业号正则 | `submitted to cluster (\d+)` | 无 | `scheduler.py` `submit_job`，从调度器标准输出提取集群作业号 |
| 调度器查询超时 | `120` | $\text{s}$ | `scheduler.py` `job_alive` 中 `timeout=120`，单次调用 `hep_q` 或 `condor_q` 的超时 |
| `_WORKER_UNSET` | `("DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "APPTAINERENV_DISPLAY", "APPTAINERENV_XAUTHORITY", "SINGULARITYENV_DISPLAY", "SINGULARITYENV_XAUTHORITY")` | 无 | `scheduler.py`，作业脚本开头用 `unset` 清除的 `7` 个显示环境变量 |
| `_WORKER_BIND_VARIABLES` | `("APPTAINER_BIND", "APPTAINER_BINDPATH", "SINGULARITY_BIND", "SINGULARITY_BINDPATH", "BINDPATH", "RASER_SIF_BIND", "RASER_SIF_EXTRA_BINDS")` | 无 | `scheduler.py`，作业脚本中滤掉 X11 挂载项的 `7` 个容器绑定环境变量 |
| `JOB_ENDED` | `"raser: the job ran its slices"` | 无 | `workflow.py`，作业跑完请求的环节后打印的正常结束行前缀 |
| `_STARTS` | `4` | 次 | `workflow.py` `_run_again`，集群作业结束后自动重拉命令的最大尝试次数 |
| `_PAUSE` | `30` | $\text{s}$ | `workflow.py` `_run_again`，自动重拉相邻两次尝试之间的等待 |
| `_WAITING_DEPTH` | `8` | 层 | `workflow.py` `_start_again`，自动拉起外部等待命令的最大递归深度 |
| 本实验续跑深度上限 | 链上环节的个数 | 层 | `workflow.py` `_start_again`，自动拉起本实验命令的最大递归深度 |
| 忽略的加锁 `errno` 集合 | `{ENOLCK, ENOTSUP, EOPNOTSUPP, EINVAL}` | 无 | `workflow.py` `_lock`，文件系统不支持 `flock` 时只打印警告并继续运行的错误号 |

### 加锁与器件场准备

1. **分流单作业入口**：主命令派发出的单个作业进程直接转入 `_run_job` 运行这个作业。
2. **加锁（`_lock`）**：打开锁文件后执行 `fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)`：
   - 捕获 `BlockingIOError` 时关闭句柄，抛出 `Running(f"{what} is run by another process now; run the command again when it is done")`。`Running` 继承 `SystemExit`，只输出这一行就退出。
   - 捕获 `OSError` 且 `error.errno` 在 `{ENOLCK, ENOTSUP, EOPNOTSUPP, EINVAL}` 中时，打印 `warning: <path> cannot be locked here (<error.strerror>): nothing keeps another command off it` 并返回 `None`；其他 `OSError` 原样抛出。
3. **预览返回**：`kwargs["dry_run"]` 为真时，打印规划后直接返回。
4. **准备器件场（`_make_shared`）**：
   - 遍历各扫描点要读的器件场，同样输入的只处理一次；
   - 对还没有的器件场调用其求解入口（`-b` 时连同等待它的本实验命令和工作目录一起传入）；若捕获 `Running`，打印 `f"{名字}: {running}"` 并继续，下游扫描点随后进入等待；
   - 若不是 `-b`、也不是 `--dry-run`，求解结束后器件场仍不可用，抛出 `RuntimeError(f"{名字} was made in this process and is still not ready for a point of {root}: waiting would not help")`。
5. **执行各扫描点并汇总**：逐个扫描点启动作业。若有扫描点失败，全部结束后抛出 `SystemExit("\n".join([f"{len(failed)} of {len(todo)} points failed:", *failed]))`。

单独运行 `raser field <实验文件夹>` 时，入口调用 `workflow.make_shared`：以只读方式读取 `config.json`，按当前配置与命令行的 `--set`/`--scan` 展开扫描点；`dry_run` 为真时逐点打印 `<root>: <名字> ready|to be made for <options>`，否则直接调用 `_make_shared`。

### 扫描点调度与作业启动

对每个扫描点，按以下顺序执行：

1. **筛出等待前置的作业**：要读的器件场不可用，或另一个扫描点要算的上游还没写好时，把这些作业从待跑列表中移出，打印等待提示并记入 `failed`。
2. **记下续跑信息**：`-b` 且 `RASER_SUBMIT_QUEUE` 非空时，跳过这一步；`-b` 且 `RASER_SUBMIT_QUEUE` 未设或为空时，记下去掉内部续跑参数的原命令词与 `os.getcwd()`，再调用 `_not_submitted` 过滤待跑作业：
   - 作业没有任何提交记录时保留；
   - 有提交记录且环境变量 `RASER_CLUSTER_JOB` 非空时直接跳过；
   - 有提交记录且未设 `RASER_CLUSTER_JOB` 时，读出首个记录的 `"job"`，按作业号去重缓存调用 `scheduler.job_alive(job)`：返回 `False` 时打印 `is no more on the cluster`、删除该作业全部提交记录并保留；返回 `None` 时打印 `the scheduler cannot be asked; left as it is` 并跳过；返回 `True` 时静默跳过；
   - 循环结束后若有作业被跳过，打印 `<位置>: jobs <已跳过作业号升序列表> are submitted already`；
   - 过滤后没有作业可跑时，进入下一个扫描点。
3. **分三路启动作业（`_start`）**：记 `single = kwargs.get("jobs") is None and not kwargs["batch"]`，`alone = len(todo) == 1`：
   - **当前进程模式（`single and alone`）**：在 `with _logged(<作业日志>):` 上下文中直接调用 `_run_job`。`_logged` 用 `_Both` 把 `sys.stdout` 和 `sys.stderr` 同时写向终端与日志文件；捕获 `BaseException` 时把 `traceback.format_exc()` 写入日志后原样重抛，并在 `finally` 恢复标准流。
   - **独立子进程模式（`single and not alone`）**：拼出作业的子命令词，调用 `_own_process` 转调 `jobs._run_local_job(words, <作业日志>)`。`_run_local_job` 用当前 Python 解释器以 `subprocess.Popen(..., stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)` 行缓冲转发输出到终端与日志。退出码非零时调用 `jobs.last_line(log)`（先取非空行，无文件为 `"no log"`、全空为 `"an empty log"`，逆序找首个匹配 `_RAISED` 的行，未命中取末行），抛出 `RuntimeError(f"the job failed: {jobs.last_line(log)} ({log})")`。
   - **本地进程池或集群模式（`not single`）**：`-b` 且 `RASER_SUBMIT_QUEUE` 非空时，先打印宿主机队列提示行。随后调用 `jobs.run_indexed_jobs(..., count=len(left), use_cluster=kwargs["batch"], mem=kwargs["mem"], destination=<命令首词>, indices=left, ...)`：
     - `use_cluster=False` 时，启动 `ProcessPoolExecutor(max_workers=min(len(plan.commands), os.cpu_count() or 4))` 并行执行 `_run_local_job`。全部任务结束后若有异常，为每个带日志的失败作业拼出 `\n  job <index>: <last_line(log)> (<log>)`，抛出 `RuntimeError`（链接首个底层异常）。
     - `use_cluster=True` 时，逐个作业调用 `scheduler.main(destination, command, mem, is_test=False)`；成功时记入 `accepted` 并触发 `submitted(index, getattr(plan, "job_id", None))` 回调写提交记录，失败时记入 `failed` 并继续提交其余作业。循环结束后若 `failed` 非空，按 `RASER_SUBMIT_QUEUE` 是否非空选 `"queued"` 或 `"accepted"` 抛出 `RuntimeError`（链接首个底层异常）。
4. **多点错误汇总**：`_start` 抛出 `Exception` 时，若只有一个扫描点，立即重抛；若有多个，打印异常回溯，把 `f"  {folder}: {error!r}"` 追加到 `failed`，继续处理其余扫描点。

### 集群脚本生成、提交与状态查询

1. **校验与生成作业计划（`jobs.plan_indexed_jobs`）**：检查 `count > 0`（否则抛 `ValueError("Indexed job count must be positive")`）与 `mem > 0`（否则抛 `ValueError("Indexed job memory level must be positive")`）。按 `range(count)`（`indices is None` 时）或 `indices` 为每个编号拼接 `(*command_prefix, *tail, "--job-index", str(index))`，返回 `IndexedJobPlan`；`jobs.run_indexed_jobs` 带 `dry_run=True` 时直接返回这份计划。辅助函数 `jobs.command_tail(argv, command_prefix, remove_options)` 去掉匹配的前缀、`remove_options`（含 `--opt val` 与 `--opt=val` 两种写法）以及 `-b`、`--batch`、`--dry-run`。
2. **规划单作业脚本与提交命令（`scheduler.plan_job`）**：
   - 检查 `batch_level > 0`（否则抛 `ValueError("Batch memory level must be positive")`）及 `_tokens(command)` 非空（否则抛 `ValueError("Batch worker command must contain tokens")`）；
   - 计算申请内存 `memory_mb = 8000 * batch_level`（$\text{MB}$），输出目录 `directory = project_path(destination_subfolder, "jobs")`；
   - 构造 `command_name = "_".join(command_tokens).replace("/", "_")`。若 `len(command_name.encode()) > 200`，取其 UTF-8 字节的 SHA-256 十六进制前 `16` 位为 `digest`，把前缀截断至前 `183` 字节（`decode(errors="ignore")`），拼成 `<前缀>_<digest>`；
   - 令 `job_file = directory / f"{command_name}.job"`、`worker = ("raser", *command_tokens)`，读 `RASER_SCHEDULER`（默认 `"hep_sub"`）：
     - 为 `"hep_sub"` 时，取 `group_name = group or grp.getgrgid(os.stat(".").st_gid)[0]`，拼出 `("hep_sub", "-o", str(directory), "-e", str(directory), str(job_file), "-mem", str(memory_mb), "-g", group_name)`，返回 `ClusterJobPlan`；
     - 为 `"condor"` 时，读 `RASER_CONDOR_JOB_FLAVOUR`（默认 `"workday"`），不在 `allowed_flavours` 中时抛 `ValueError(f"Unknown HTCondor job flavour: {flavour}")`；用 `directory.resolve()` 与 `job_file.resolve()` 构造绝对路径的 `submit_description`（含 `executable`、`output`、`error`、`log`、`request_memory`、`getenv = True`、`+JobFlavour`、`queue`），令 `submit_file = directory / f"{command_name}.sub"`、`submit = ("condor_submit", str(submit_file))`，返回 `ClusterJobPlan`；
     - 为其他值时抛 `ValueError(f"Unknown scheduler: {scheduler}")`。
3. **生成工作节点脚本（`scheduler.worker_script`）**：
   - 写出 `#!/bin/bash` 后先记录 `raser_x11_sources`（`/tmp/.X11-unix`、`/tmp/.X11-unix/`、`$HOME/.Xauthority`、`${XDG_RUNTIME_DIR:-}`、`${XAUTHORITY:-}`、`${APPTAINERENV_XAUTHORITY:-}`、`${SINGULARITYENV_XAUTHORITY:-}`）；
   - 执行 `unset` 清除 `_WORKER_UNSET` 中的 `7` 个变量，再执行 `export RASER_CLUSTER_JOB=1`；
   - 遍历 `_WORKER_BIND_VARIABLES` 中的 `7` 个变量，对非空变量按 `,` 拆分，滤掉源路径 `${raser_bind%%:*}` 命中 `raser_x11_sources` 的项后重新导出；
   - `REPO_ROOT is not None`（源码树）时，先 `cd <REPO_ROOT> || exit 1`，再按 `RASER_ENV_ROUTE` 非空与否执行 `. env/setup_cvmfs.sh <route> || exit $?` 或 `. env/setup.sh || exit $?`；`REPO_ROOT is None`（包安装）时，执行 `cd <os.getcwd()> || exit 1`；
   - 末尾执行 `shlex.join(worker_command)`。
4. **落盘与提交（`scheduler.main`、`gen_job`、`submit_job`）**：
   - `is_test=True` 时只把脚本、可选 `.sub` 正文与提交命令打印到标准输出并返回 `plan`；
   - `is_test=False` 时由 `gen_job` 创建父目录、以 UTF-8 写出 `<command_name>.job`（末尾附换行）并设权限 `0o755`；有 `submit_file` 时以 UTF-8 写出 `.sub`；
   - `submit_job` 检查 `RASER_SUBMIT_QUEUE`：非空时以追加模式写入 `shlex.join(plan.submit_command) + "\n"` 并返回 `None`；未设时调用 `subprocess.run(plan.submit_command, shell=False, check=True, capture_output=True, text=True)`，原样打印 `result.stdout`，用 `submitted to cluster (\d+)` 提取作业号（未匹配时为 `None`），经 `replace(plan, job_id=...)` 返回。
5. **原子写提交记录（`workflow._note_submitted`）**：`job is None` 时直接返回。否则拼出 JSON 行 `{"job": <job>, "time": "<YYYY-MM-DD HH:MM:SS>"}\n`，先写同目录临时文件 `<记录名>.<pid>.part`，再经 `os.link(part, path)` 原子落盘（同名记录已存在时捕获 `FileExistsError`，保留旧记录），最后在 `finally` 中删掉 `.part`。
6. **查询集群作业存活（`scheduler.job_alive`）**：按 `RASER_SCHEDULER`（默认 `"hep_sub"`）选 `["hep_q", "-u", getpass.getuser()]` 或 `["condor_q", str(job_id), "-af", "ClusterId"]`，以 `timeout=120` 执行子进程。抛出 `OSError`、`subprocess.TimeoutExpired` 或返回码非 `0` 时返回 `None`；否则收集所有首词以数字开头的输出行中 `words[0].split(".")[0]` 构成集合 `held`，返回 `str(job_id) in held`。

### 单作业执行与集群自动续跑

1. **执行各环节**：单个作业进程进入 `workflow._run_job` 后，按依赖顺序运行本次请求的环节，跳过已算完的。
2. **收尾**：删除已算完环节的提交记录；打印 `f"{JOB_ENDED}: {','.join(wanted)}"`；调用 `_start_again(..., progress=<本次是否新算完了所请求的环节>)`。
3. **集群自动续跑（`_start_again` 与 `_run_again`）**：
   - 未设 `RASER_CLUSTER_JOB` 或 `progress` 为假时直接返回；
   - 读当前递归深度 `depth = int(os.environ.get("RASER_RESUBMIT_DEPTH", "0"))`；
   - **外部等待命令**：逐条读出等待列表的命令词：`depth >= 8` 时打印 `not starting raser <words>: <depth> starts deep`；否则调用 `_run_again(words, entry["cwd"], depth)`，返回 `True` 后把该条目从等待列表移除；
   - **本实验命令**：记有原命令时，先检查 `depth >= <链上环节的个数>`，满足时打印 `not starting the command again: <depth> starts deep, as many as the slices of the chain` 并返回；否则调用 `_run_again(<原命令词>, <原工作目录>, depth)`；
   - `_run_again(words, cwd, depth)` 打印 `starting the command again: raser <words>`，在子进程环境中把 `RASER_RESUBMIT_DEPTH` 置为 `str(depth + 1)`，循环 `attempt` $\in \{0, 1, 2, 3\}$：非首次尝试前 `time.sleep(30)`，以 `cwd` 启动 `raser` 子进程（`check=False`），返回码为 `0` 立即返回 `True`；`4` 次全非零则打印 `the command did not start again in 4 tries: give it again when the jobs it waits for are done` 并返回 `False`。

## 软件实现

### 模块与函数分工

- `src/raser/lifecycle/jobs.py`：编号作业的计划构建、命令行尾参数清理与本地/集群批量派发。`command_tail` 剥离命令前缀、`--batch`/`--dry-run` 及指定选项；`plan_indexed_jobs` 校验作业数与内存档位，生成 `IndexedJobPlan`；`_run_local_job` 与 `last_line` 负责子进程执行、终端与日志双写，以及跳过 C++ 尾行提取 Python 异常摘要；`run_indexed_jobs` 按 `use_cluster` 经 `scheduler.main` 串行提交集群，或经 `ProcessPoolExecutor` 本地并行执行，并汇总失败作业。
- `src/raser/lifecycle/scheduler.py`：集群作业目录定位、脚本生成、调度器提交与在轨状态查询。`job_dir` 定位 `<project_root>/<destination_subfolder>/jobs/`；`plan_job` 组装 `hep_sub` 或 HTCondor 的 `ClusterJobPlan`（含 `200` 字节脚本名截断与内存换算）；`worker_script` 与 `gen_job` 生成清理 X11 变量与容器绑定、导出 `RASER_CLUSTER_JOB=1`、权限 `0o755` 的 bash 脚本；`submit_job` 写宿主机队列 `RASER_SUBMIT_QUEUE` 或调用调度器并解析集群作业号；`main` 统筹规划、预览、写盘与提交；`job_alive` 经 `hep_q` 或 `condor_q` 查询作业是否还在；`run_cmd` 提供通用外部命令的预览与执行。
- `src/raser/lifecycle/workflow.py`（作业调度、锁、日志与续跑部分）：`Running` 与 `_lock` 实现非阻塞文件锁；`_make_shared` 与 `make_shared` 去重触发还没有的器件场求解；`_start`、`_logged`（`_Both`）、`_own_process` 实现三路启动；`_run_job` 运行单个作业并打印 `JOB_ENDED`；`_note_submitted` 与 `_not_submitted` 管理提交记录的原子写入与登录节点重提判定；`_start_again`、`_run_again` 与 `waited_for_by` 实现集群自动重拉与外部等待列表。

### 核心数据结构

| 数据结构 | 定义文件 | 字段 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `IndexedJobPlan` | `jobs.py` | `commands` | `tuple[tuple[str, ...], ...]` | 无 | 每个编号作业的完整命令词元组（末尾含 `--job-index <index>`） |
| `IndexedJobPlan` | `jobs.py` | `backend` | `str` | 无 | 执行后端，`"cluster"` 或 `"local"` |
| `IndexedJobPlan` | `jobs.py` | `destination` | `str` | 无 | 作业脚本目录归属的子目录名（命令首词） |
| `IndexedJobPlan` | `jobs.py` | `memory_level` | `int` | 档（`8000 MB`） | 集群作业申请的内存档位（`as_dict()` 导出以上四个字段） |
| `ClusterJobPlan` | `scheduler.py` | `job_file` | `Path` | 无 | 生成的可执行集群脚本 `<command_name>.job` 路径 |
| `ClusterJobPlan` | `scheduler.py` | `worker_command` | `tuple[str, ...]` | 无 | 工作节点执行的 `("raser", *command_tokens)` 命令词 |
| `ClusterJobPlan` | `scheduler.py` | `submit_command` | `tuple[str, ...]` | 无 | 调度器提交命令词（`hep_sub ...` 或 `condor_submit ...`） |
| `ClusterJobPlan` | `scheduler.py` | `submit_file` | `Path \| None` | 无 | HTCondor 的 `<command_name>.sub` 路径（`hep_sub` 为 `None`） |
| `ClusterJobPlan` | `scheduler.py` | `submit_description` | `str \| None` | 无 | `.sub` 文件正文（`hep_sub` 为 `None`） |
| `ClusterJobPlan` | `scheduler.py` | `job_id` | `str \| None` | 无 | 调度器返回的集群作业号（未提交、入队或未匹配时为 `None`；`as_dict()` 略去此字段） |
| `Running` | `workflow.py` | 继承 `SystemExit` | 异常类 | 无 | 锁被其他进程持有时抛出，只输出一行占用提示就退出 |
| `_Both` | `workflow.py` | `stream`, `log` | 文本流 | 无 | 当前进程模式下同时写终端流与作业日志的双写代理 |

## 接口

### 选项与环境变量

使用者能设的作业与集群参数只有下表这些命令行选项和环境变量。其余参数（单档内存基准 `8000 MB`、进程池回退并发数 `4`、脚本基名 `200 B` 截断上限与 `16` 位摘要、调度器查询超时 `120 s`、自动续跑重试 `4` 次与间隔 `30 s`、外部等待递归上限 `8` 层、本实验续跑递归上限等于链上环节的个数，以及清空的 X11 变量与过滤的挂载路径清单）都写死在代码里。

| 选项或键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `-s`, `--jobs` | 无（按 `1` 处理） | 个 | 每个扫描点并行运行的作业数，作业号为 `0` 到 `<数量> - 1` |
| `--dry-run` | 关 | 无 | 只打印将要运行的扫描点、环节和作业状态，打印完即返回；对 `raser field <实验文件夹>` 打印器件场是 `ready` 还是 `to be made` |
| `-b`, `--batch`（子命令选项） | 关 | 无 | 把待运行作业提交到集群；省略 `-s` 时提交作业 `0` |
| `-b`, `--batch`（顶层全局选项） | `0`（计数） | 档（`8000 MB`） | 写在子命令前，可连写为 `-b`、`-bb`、`-bbb` 等；开启集群提交，内存档位取 $\max(\text{-mem},\, \text{计数})$ |
| `-mem` | `1` | 档（`8000 MB`） | 每个集群作业申请的内存档位，须为正整数；实际申请 $8000 \times \text{档位}\ \text{MB}$ |
| `-t`, `--test`（顶层全局选项） | 关 | 无 | 只能写在子命令前，只在与顶层 `-b`/`--batch` 同时给出时生效：只检查并预览提交信息 |
| `RASER_SCHEDULER` | `"hep_sub"` | 无 | 集群调度器后端：`"hep_sub"`（调用 `hep_sub`/`hep_q`）或 `"condor"`（调用 `condor_submit`/`condor_q`） |
| `RASER_CONDOR_JOB_FLAVOUR` | `"workday"` | 无 | 只在 `RASER_SCHEDULER=condor` 时生效，写入 `.sub` 的 `+JobFlavour`；允许值为 `"espresso"`、`"microcentury"`、`"longlunch"`、`"workday"`、`"tomorrow"`、`"testmatch"`、`"nextweek"` |
| `RASER_ENV_ROUTE` | 未设置 | 无 | 只在从源码树提交集群作业时读取：非空（如 `conda`、`ubuntu`、`el9`）则脚本执行 `. env/setup_cvmfs.sh <路线名>`，未设或为空则执行 `. env/setup.sh` |
| `RASER_SUBMIT_QUEUE` | 未设置 | 无 | 宿主机提交队列文件路径（SIF 路线由 `env/setup.sh` 的 `raser` 封装自动设置）；非空时把提交命令追加写入该文件，由宿主机提交，并跳过原命令的记录 |
| `RASER_CLUSTER_JOB` | 未设置 | 无 | 集群作业脚本自动导出为 `"1"`，表示当前进程在集群工作节点上；开启作业完成后的自动续跑，并跳过已有提交记录的作业；通常由程序自动设置 |
| `RASER_RESUBMIT_DEPTH` | `"0"` | 层 | 集群自动重新拉起命令的当前递归深度，每拉起一层加 `1`；通常由程序自动设置 |

主命令派发作业时还自动传一个隐藏的内部选项 `--job-index <作业号>`。

### 读写的文件

- **节点**：作业把各环节的结果写进 `<实验>/nodes/<环节>/<节点号>/`；写到一半的节点带 `.part` 后缀，写完才改成正式的名字。每个节点单独加锁。节点与 `node.json` 见 [片与重跑](slices.md)。
- **作业日志**：每个作业一份纯文本日志，记录标准输出与标准错误（当前进程模式只含 Python 层的输出与回溯）。作业跑完请求的环节后，末尾打印 `raser: the job ran its slices: <逗号分隔的环节名>`；本地作业失败时由 `jobs.last_line` 读出摘要。
- **提交记录**：集群直接提交并取得作业号后写出的 JSON，含两个字符串字段：`"job"`（集群作业号）和 `"time"`（本地时间，格式 `YYYY-MM-DD HH:MM:SS`）。写入时先写同目录 `<记录名>.<pid>.part`，再经 `os.link` 原子落盘并删掉 `.part`。对应环节算完，或登录节点确认该作业已离开集群后删除。
- **`<project_root>/<命令首词>/jobs/<command_name>.job`**：`scheduler.gen_job` 写出的 UTF-8 可执行 bash 脚本（权限 `0o755`）。它清理 X11 环境变量与容器绑定、导出 `RASER_CLUSTER_JOB=1`、按源码树或包安装模式切换目录并激活环境，再执行 `raser <作业命令>`。
- **`<project_root>/<命令首词>/jobs/<command_name>.sub`**：只在 `RASER_SCHEDULER=condor` 时由 `scheduler.main` 写出的 UTF-8 HTCondor 提交描述，记录绝对路径的 `executable`、`output`、`error`、`log`，内存请求 `request_memory`（单位 $\text{MB}$）、`getenv = True`、`+JobFlavour` 与 `queue`。
- **`<project_root>/<命令首词>/jobs/<command_name>.out`、`.err`（及 `.log`）**：集群作业的标准输出、标准错误及调度器事件日志（纯文本）。`hep_sub` 按 `-o`/`-e` 在 `<jobs目录>` 下写出带集群作业号的 `.out`/`.err`；`condor` 按 `.sub` 写出 `<command_name>.out`、`<command_name>.err` 与调度器日志 `<command_name>.log`。
- **`RASER_SUBMIT_QUEUE` 指向的队列文件**：`scheduler.submit_job` 追加写入的 UTF-8 文本，每行一条经 `shlex.join` 转义的调度器提交命令，供宿主机 `raser` 封装函数在容器退出后逐行提交。

`config.json` 与 `points.json` 见 [实验、扫描点与种子](experiments.md) 和 [片与重跑](slices.md)。
