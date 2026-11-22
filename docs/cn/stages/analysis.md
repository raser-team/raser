# 统计分析环节（`stages/analysis`）

`src/raser/stages/analysis/` 是仿真链的第八个环节，命令是 `raser analysis`（短别名 `raser ana`），由[命令行接口（`raser`）](../cli.md)分发。它读取同一扫描点上[能量沉积环节（`stages/deposit`）](deposit.md)、[载流子输运与感应电流环节（`stages/current`）](current.md)与[事件重建环节（`stages/reconstruction`）](reconstruction.md)的节点，调用[统计分析（`core/analysis`）](../core/analysis.md)计算电荷收集效率与脉冲时间分辨。每个扫描点的结果是一个 `analysis` 节点，从视图 `points/<点名>/analysis` 查看；跨扫描点的汇总表和趋势图写在 `<实验文件夹>/analysis/` 下。结果的存放方式见[架构总纲](../architecture.md#结果)。

## 行为

### 运行

`raser analysis [路径]` 在当前文件夹或给定路径的实验上跑到 `analysis`，缺的上游自动补上。`raser signal` 等测试命令跑完整条链，`analysis` 是最后一步。

下面的例子先在 `HPK-Si-PiN` 上扫两个偏压，每点 `2` 个作业、每作业 `200` 个事例（作业事例数写在 `config.json` 的 `deposit` 段）；再单独重跑一次统计分析：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --seed 1
raser analysis examples/HPK-Si-PiN/signal
```

`work/` 下没有 `HPK-Si-PiN` 时，第一条命令在 `examples/HPK-Si-PiN/` 下就地运行，实验文件夹是 `examples/HPK-Si-PiN/signal`。链上的 `digitizer` 把每个作业的波形采样、量化，写出 `digitizer.h5`；`trigger` 按幅度阈值把越过阈值的事例号写进 `trigger.h5`，只有这些事例进入 `reconstruction`。第二条命令的上游节点指纹和原来相同，全部复用；`analysis` 节点指纹也相同时同样复用。每个点写完后打印它的 `result.json` 路径；样本不足时，先打印缺了哪项结果及原因。

### 单点统计与分布图

每个扫描点汇总它用到的全部作业。程序先算全部事例的电荷收集效率（事例数不少于 `2` 时画出 `efficiency.png`、`efficiency.pdf`）。再对单电极重建结果取出选中事例的各定时量与最早沉积时刻 `truth`，写入 `events.h5`，画出 `amplitude.png`、`amplitude.pdf`。最后对 `ToA`、`CoG` 与各 `CFD*` 通道计算 `time - truth` 的核心宽度，画出 `time_difference` 与 `resolution_of_fraction`，各有 `.png`、`.pdf`。

样本不足时作业照常完成：效率不足 `2` 个事例、全点 `0` 事例，或任一时间通道有效样本不足 `20` 个，原因写进 `result.json` 对应的 `error` 字段，相应的图跳过。某个作业在 `deposit` 里录得 `0` 个事例时，它的下游环节随之跳过，统计时也跳过它。

在上面的例子中（每点 `2` 个作业、共 `400` 个事例），两个点的 `result.json` 关键结果如下：

- `200 V`（`examples/HPK-Si-PiN/signal/points/voltage_200/analysis/result.json`）：全部 `400` 个事例的电荷收集效率 `mean = 0.9348`（`0.9347645480767679`）、`mean_error = 0.007225`、`spread = 0.1445`；被 `trigger` 记录、且找到不低于 `10 mV` 幅度阈值的团簇种子的选中事例 `276` 个（`polarity = -1.0`），`ToA` 经 `5` 轮迭代在窗口内保留 `241` 个事例得 `sigma = 123.99 ps`（`1.2399e-10 s`）、`sigma68 = 123.69 ps`，`CFD30` 得 `sigma = 33.35 ps`、`sigma68 = 31.66 ps`。
- `100 V`（`examples/HPK-Si-PiN/signal/points/voltage_100/analysis/result.json`）：`400` 个事例的收集效率 `mean = 0.9195`（`0.9194852059626839`）、`mean_error = 0.008746`、`spread = 0.1749`；选中事例 `257` 个，`CFD30` 得 `sigma = 43.58 ps`、`sigma68 = 38.87 ps`。

`200 V` 点的三张分布图如下：

![HPK-Si-PiN 电荷收集效率分布](../images/analysis-efficiency-HPK-Si-PiN.png)

`200 V` 下 `400` 个事例的电荷收集效率分布直方图，虚线标出平均收集效率 `0.9348`。

![HPK-Si-PiN 脉冲幅度分布](../images/analysis-amplitude-HPK-Si-PiN.png)

`200 V` 下 `276` 个选中事例（被 `trigger` 记录且团簇种子幅度不低于 `10 mV`）的脉冲幅度分布直方图，虚线标出幅度阈值。

![HPK-Si-PiN 时间差分布与截断高斯拟合](../images/analysis-time-difference-HPK-Si-PiN.png)

`200 V` 下 `ToA`、`CoG` 与 `CFD10`–`CFD90` 相对 `truth` 的时间差分布、拟合窗口阴影与截断高斯拟合曲线。

### 跨扫描点汇总与趋势图

有结果的扫描点多于 `1` 个时，程序在 `<实验文件夹>/analysis/` 下写出 `points.json`。它只保留各点之间取值不同的扫描选项，并汇集每点的效率与时间分辨。取值不同的扫描选项恰好只有 `1` 个、且取值都是非布尔数值时，再按该变量升序画出左右双图 `trend.png`、`trend.pdf`。

上面的例子写出的 `examples/HPK-Si-PiN/signal/analysis/points.json` 节选如下（`CoG` 与 `CFD10`–`CFD90` 通道结构与 `ToA` 相同，此处略去）：

```json
[
  {
    "point": "voltage_100",
    "field.voltage": 100,
    "events": 400,
    "efficiency": 0.9194852059626839,
    "efficiency_error": 0.00874583566620318,
    "selected": 257,
    "ToA": {
      "sigma68": 1.4373747887851763e-10,
      "sigma": 1.4600067149809272e-10,
      "sigma_error": 1.0200597423600211e-11
    }
  },
  {
    "point": "voltage_200",
    "field.voltage": 200,
    "events": 400,
    "efficiency": 0.9347645480767679,
    "efficiency_error": 0.007224687825783201,
    "selected": 276,
    "ToA": {
      "sigma68": 1.2368887903341034e-10,
      "sigma": 1.2399174526244709e-10,
      "sigma_error": 9.047206914503263e-12
    }
  }
]
```

对应的 `examples/HPK-Si-PiN/signal/analysis/trend.png` 如下：

![HPK-Si-PiN 电荷收集效率与时间分辨随偏压变化](../images/analysis-points-HPK-Si-PiN.png)

`100 V` 与 `200 V` 两个偏压点的电荷收集效率（左）与各 `CFD` 通道时间分辨（右）对比图。

## 规则

### 节点

`analysis` 节点的输入只有 `config.json` 中 `analysis` 段用到的设置值，以及这个点上 `deposit`、`current`、`reconstruction` 的节点号。指纹相同就复用。上游任一节点变了，节点号跟着变，`analysis` 重算成新节点。节点单独加锁，写到一半带 `.part` 后缀。代码版本和 `node.json` 记录的不一致时只给一条提示，结果照常复用。

### 内置常数

下表列出 `src/raser/stages/analysis/` 中使用的全部内置常数与写死参数：

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `PICOSECOND` | `1.0e-12` | $\text{s}$ | `plots.py`、`across_points.py`；将时间差、拟合窗口与时间分辨由 $\text{s}$ 换算为 $\text{ps}$ |
| `MILLIVOLT` | `1.0e-3` | $\text{V}$ | `plots.py`；将脉冲幅度与幅度阈值由 $\text{V}$ 换算为 $\text{mV}$（`timing.py` 的 `table_setting` 同按 `1.0e-3` 换算为 $\text{mV}$ 并 `round(..., 9)`） |
| `EDGE_SIGN` | `{"rising": 1.0, "falling": -1.0}` | 无 | 导入自 `raser.core.reconstruction.event_table`，在 `timing.py` 的 `event_times` 中将首电极脉冲边沿映射为极性符号 `polarity` |
| 效率最少事例数（字面量） | `2` | 个 | `collection.py` 的 `efficiency_spread`；计算收集效率均值、均值标准误与样本标准差（`ddof=1`）所需的最少事例数 |
| `MINIMUM_EVENTS` | `20` | 个 | 定义于 `raser.core.analysis.resolution`，在 `timing.py` 的 `time_widths` 调用 `core_width` 时生效；单通道非 `NaN` 样本数及首轮窗口内样本数下限 |
| 分布图分箱与曲线采样数（字面量） | 效率与幅度直方图 `60` 箱；时间差在 `mean ± 8 * sigma` 内 `64` 箱、`200` 个拟合曲线点、最多 `3 × 4` 子图 | 箱 / 点 / 格 | `plots.py`；写死在 `draw_efficiencies`、`draw_amplitudes`、`draw_differences` 中 |
| 图像画幅与分辨率（字面量） | 单图 `(6, 4)`、`150 dpi`；时间差 `(16, 10)`、`130 dpi`；跨点图 `(11, 4)`、`150 dpi` | $\text{in}$ / $\text{dpi}$ | `plots.py`、`across_points.py`；导出 PNG 的固定画幅与分辨率 |

### 0 事例作业与缺失文件

`files.py` 的 `job_file(folder, index, name)` 经视图 `points/<点名>/<name>/<作业号>` 找一个作业 `<name>` 节点里的 `<name>.h5`。文件存在时直接返回。不存在时读取同一作业 `deposit` 节点里的 `deposit.h5`（经 `read_deposits`），统计 `recorded = len(deposits.events)`：

- `recorded == 0` 时返回 `None`，静默跳过该 0 事例作业；
- `recorded > 0` 时抛出：

  ```text
  FileNotFoundError: <path>: job <index> recorded <recorded> events but left no <name> file
  ```

  原因是该作业本应生成下游文件却缺失（例如文件被误删）；补齐缺失文件。

局限：多位置链只写出带 `.<position>` 后缀的文件，`analysis` 现在不读它们，遇到这样的作业也抛出上面的报错；多位置的统计还没做。

### 单点统计与绘图

对每个扫描点，`collect` 调用 `write_point(jobs, <点的输出文件夹>)`，按以下步骤执行：

1. **读取并校验重建表（`point_tables`）**：以 `enumerate(jobs)` 迭代 `(place, (folder, index))`，调用 `job_file(folder, index, "reconstruction")`；返回 `None` 时跳过，否则调用 `read_event_table` 并将 `(place, folder, index, table)` 存入 `tables`（因此 `place` 保留了 0 事例作业在 `jobs` 中的占位下标）。随后对所有表计算 `table_setting(table)`：
   ```python
   (round(table.threshold / 1.0e-3, 9), round(table.amplitude_threshold / 1.0e-3, 9), table.fractions, tuple(table.edges))
   ```
   若不同作业得到的设置集合大小大于 `1`，抛出：
   ```text
   ValueError: the jobs of the point were reconstructed with different settings: <settings>
   ```
   原因是同一扫描点内不同作业使用了不同的重建参数；用统一参数重跑重建后再分析。
2. **核对电流文件并计算逐事例收集效率（`event_efficiencies`）**：收集效率按作业 `current` 节点里的全部事例算，不经过触发；重建表里只有被 `trigger` 记录的事例，是电流文件事例的一个子集。对 `tables` 中的每条 `(place, folder, index, table)`，调用 `job_file(folder, index, "current")` 与 `read_currents(path).events`，记 `numbers = {event.event for event in events}`、`rows = {int(number) for number in table.columns["event"]}`：
   - 若 `rows - numbers` 非空，抛出：

     ```text
     ValueError: <path>: events <list> are in the reconstruction of the job, not in its currents
     ```

     其中 `<list>` 为 `sorted(rows - numbers)`；原因是该作业的重建表不是由这份电流文件算出来的，重跑该作业的 `current` 及下游即可。电流文件里有、重建表里没有的事例是没被触发记录的事例，属于正常情形。
   - 否则调用 `collection_efficiency([event.charge for event in events], [event.pairs for event in events])` 计算电流文件里每个事例的无量纲收集效率，全部作业拼接为一维数组 `efficiencies`（`tables` 为空时返回空数组）。
3. **记录重建参数并统计效率展宽（`efficiency_spread`）**：若 `tables` 非空，将 `table_setting(tables[0][3])` 写入 `result["reconstruction"]`（两阈值单位 `mV`）。对 `efficiencies` 统计样本数 `count = len(efficiencies)`：
   - 若 `count < 2`，`efficiency_spread` 抛出 `TooFewValues`，消息为 `<count> events in the point, a mean and a spread need at least 2`。`write_point` 捕获后写入 `result["collection"] = {"events": count, "error": str(too_few)}`，向 `missing` 追加 `no efficiency: <too_few>`，并跳过 `efficiency.png`。
   - 若 `count >= 2`，计算样本标准差 `spread = float(np.std(efficiencies, ddof=1))`、均值 `mean = float(np.mean(efficiencies))` 与均值标准误 `mean_error = spread / np.sqrt(count)`，写入 `result["collection"]`，并调用 `plots.draw_efficiencies` 画出 `efficiency.png`（`60` 箱直方图，均值处画虚线，`150 dpi`）。
4. **全点 0 事例提前结束**：若 `len(efficiencies) == 0`，写入 `result["timing"] = {"events": 0, "selected": 0, "error": "the jobs recorded no event"}`，向 `missing` 追加 `"no time resolution: the jobs recorded no event"`，写出 `result.json` 并返回 `"; ".join(missing)`。
5. **提取单电极选中事例时间与真值（`event_times`）**：
   - 局限：`analysis` 现在只统计单电极的结果，多电极的统计还没做。先检查 `tables` 中每个表；若任一表满足 `len(table.electrodes) > 1`，抛出：

     ```text
     NotImplementedError: <len> electrodes; the time of an event with several electrodes is not settled
     ```

     原因是 `analysis` 现在只为单电极器件定义了事例时间。
   - 对每条 `(place, folder, index, table)`，经 `slice_file(folder, index, "deposit")` 找到该作业的沉积文件 `deposits`，构造映射 `earliest = {event.event: min(event.t) for event in read_deposits(str(deposits)).events}`（单位 `s`）。逐条检查 `table.columns["event"]` 中的全部事例号 `number`（含未选中事例）；若 `number not in earliest`，抛出：

     ```text
     ValueError: <deposits>: event <number> is not among the deposits of the job
     ```

     原因是同一作业的沉积文件与重建表不匹配；清理并重跑该作业。
   - 取布尔掩码 `chosen = table.columns["selected"]`，按选中事例抽取：`job`（填充 `float(place)`）、`event`、第 `0` 号电极的 `ToA`、`ToT`、`amplitude`、`baseline`、`noise`、`CoG`、`truth`（`earliest[number]`），以及每个恒比比例 `(k, part)` 对应的 `CFD<round(100 * part)>`（取 `rows["CFD"][chosen, 0, k]`；若两个比例四舍五入后百分数相同，数据依次拼接到同名数组）。全部作业按列拼接，统计总事例数 `count = sum(len(table) for *_, table in tables)` 与极性符号 `polarity = EDGE_SIGN[tables[0][3].edges[0]]`。
6. **写出 `events.h5` 与幅度直方图**：创建 `events.h5`，将 `job` 与 `event` 转为 `int64`、其余列保持 `float64` 写入同名一维数据集。初始化 `result["timing"] = {"events": count, "selected": len(times["truth"]), "polarity": polarity}`，并调用 `plots.draw_amplitudes` 画出 `amplitude.png`、`amplitude.pdf`（幅度与 `tables[0][3].amplitude_threshold` 均除以 `figures.UNIT["mV"]` 换算为 `mV`，`60` 箱直方图，图例写 `<n> of <N> events`，阈值处画黑色虚线，图例写 `threshold <阈值> mV`）。
7. **计算各通道时间分辨与绘制时间图（`time_widths`）**：按 `["ToA", "CoG"]` 及 `times` 中全部 `CFD*` 键顺序遍历通道 `name`：
   - 计算时间差 `difference = times[name] - times["truth"]`（`s`），令 `found = ~np.isnan(difference)`，调用 `core_width(difference[found])`（算法见 `core/analysis`）并附带 `"missing": int(np.sum(~found))`。
   - 若任一通道抛出 `TooFewValues`（`<len> values, fewer than 20` 或 `<inside> of <len> values are inside [<low>, <high>], fewer than 20`），`write_point` 捕获后写入 `result["timing"]["error"] = str(too_few)`，向 `missing` 追加 `no time resolution: <too_few>`，跳过 `time_difference` 与 `resolution_of_fraction` 两张图。
   - 若样本数不少于 `20` 但拟合层抛出其他异常（如窗口内样本全相等抛出 `ValueError: all values in the window are equal`、首轮窗口为空抛出 `ValueError: the window [<low>, <high>] is empty` 或截断高斯拟合未收敛抛出 `ArithmeticError: the fit in [<low>, <high>] did not converge: <message>`），异常直接上抛，作业中止；需检查该点波形与重建阈值设置或增大统计量后重跑。
   - 若全部通道拟合成功，写入 `result["timing"]["times"] = widths` 并绘制两张图：
     - `plots.draw_differences` 写出 `time_difference.png`、`time_difference.pdf`：用 `figures.new(3, 4)` 在 `3 × 4` 网格上绘制前 `12` 个通道（`ToA`、`CoG` 与前 `10` 个 `CFD*`，其余空子图隐藏）。每个通道将非 `NaN` 的 `difference` 除以 `figures.UNIT["ps"]` 换算为 `ps`，在 `[mean - 8 * sigma, mean + 8 * sigma]` 内均分为 `64` 箱（`65` 个边界，填充 `figures.HISTOGRAM`），用浅灰阴影标出末轮窗口 `[low, high]`，在 `[low, high]` 上取 `200` 个等距点绘出黑色实线的归一化截断高斯曲线：横轴 `<通道名> - truth [ps]`，纵轴 `Events`，小标题只写通道名，每幅左上角（`fontsize` 为 `9`）写 `sigma68`、`sigma ± sigma_error` 与窗内事例数 `<window_events> of <events> events in the window`：
       $$y(x) = N_{\text{win}}\,\Delta x_{\text{bin}}\,\frac{\exp\!\left(-\frac{(x - \mu)^2}{2\sigma^2}\right)}{\sqrt{2\pi}\,\sigma \cdot \frac{1}{2}\left[\operatorname{erf}\!\left(\frac{\text{high} - \mu}{\sqrt{2}\,\sigma}\right) - \operatorname{erf}\!\left(\frac{\text{low} - \mu}{\sqrt{2}\,\sigma}\right)\right]}$$
       其中 $x$ 为时间差（$\text{ps}$），$\mu$、$\sigma$ 为该通道末轮拟合的 `mean`、`sigma`（$\text{ps}$），$N_{\text{win}}$ 为末轮窗口内的事例数 `window_events`（个），$\Delta x_{\text{bin}}$ 为直方图箱宽（$\text{ps}$），$y(x)$ 为每箱的期望事例数（个）。
     - `plots.draw_fractions` 写出 `resolution_of_fraction.png`、`resolution_of_fraction.pdf`：筛选所有 `CFD*` 通道，按 `int(name[3:]) / 100` 还原恒比比例，以黑色实心圆和误差棒绘出 `sigma ± sigma_error`（`ps`，图例 `sigma of the Gaussian`）、黑色空心方点绘出 `sigma68`（`ps`，图例 `sigma68`），横轴 `CFD fraction`，纵轴 `Time resolution [ps]`，纵轴下限设为 `0`。
8. **落盘单点结果并打印摘要**：以 2 空格缩进写出 `result.json` 并返回 `"; ".join(missing) or None`。回到 `collect`，若返回值非 `None`，先打印 `<点的输出文件夹>: <error>`，随后打印 `result.json` 的路径，再把这个点的选项与解析后的 `result.json` 留给跨点汇总。

### 跨扫描点汇总

全部扫描点处理完后，有结果的点多于 `1` 个时，`collect` 调用 `write_points(done, results, folder)`：

- 调用 `scanned_options(done)`：取所有点 `options` 键的排序并集，保留满足 `len({json.dumps(options.get(key)) for _, options in done}) > 1` 的键列表 `scanned`。
- 为每个点构造一行记录，包含 `"point"`、每个变化扫描选项的当前值、`"events"`、`"efficiency"`（无 `mean` 时为 `None`）、`"efficiency_error"`（无 `mean_error` 时为 `None`）、`"selected"`，以及 `timing.times` 中每个通道的 `{"sigma68", "sigma", "sigma_error"}`（单位 `s`；有 `times` 时才写时间键），以 2 空格缩进写出 `points.json`。
- 判定是否作图：`len(scanned) == 1` 且对所有行均满足 `isinstance(row[scanned[0]], (int, float)) and not isinstance(row[scanned[0]], bool)`。不满足时直接返回。
- 满足时按 `key = scanned[0]` 升序排列各行，用 `figures.new(1, 2)` 建立 `1 × 2` 画幅：左图筛选 `row["efficiency"] is not None` 的行，以黑色圆点连线和误差棒绘制效率，纵轴 `Charge collection efficiency`；右图筛选 `"ToA" in row` 的行记为 `timed`，若 `timed` 非空则取 `timed[0]` 中所有 `CFD*` 通道名，逐通道绘制 `sigma / figures.UNIT["ps"]` 及误差棒 `sigma_error / figures.UNIT["ps"]`（`ps`），颜色取 `figures.series(通道数, True)`，纵轴 `Time resolution [ps]`，下限设为 `0`；两幅的横轴都写扫描键名本身。存为 `trend.png`、`trend.pdf`。

## 软件实现

### 模块与文件分工

- `src/raser/stages/analysis/__init__.py`：注册子命令 `analysis`（短别名 `ana`），实现作业函数 `collect`（编排单点分析与跨点汇总）。
- `src/raser/stages/analysis/files.py`：提供 `slice_file` 与 `job_file`，找到一个作业的上游文件，并在文件缺失时核查该作业 `deposit` 节点里的 `deposit.h5`，区分正常 0 事例作业与缺失报错。
- `src/raser/stages/analysis/collection.py`：提供 `event_efficiencies` 与 `efficiency_spread`，核对电流与重建事例号一致，调用 `collection_efficiency` 计算逐事例收集效率并汇总均值、均值标准误与样本标准差。
- `src/raser/stages/analysis/timing.py`：提供 `table_setting`、`point_tables`、`event_times`、`time_widths` 与独立汇总接口 `point_resolution`，负责同点重建参数校验、单电极检查、最早沉积时刻 `truth` 提取以及各时间通道核心宽度拟合。
- `src/raser/stages/analysis/point.py`：提供 `write_point`，串联单个扫描点的表加载、效率计算、时间提取、`events.h5` 与 `result.json` 落盘以及四张单点图绘制，并捕获 `TooFewValues` 转为结果中的 `error` 字段。
- `src/raser/stages/analysis/plots.py`：封装四张单点分布图的 `matplotlib` 绘制函数：`draw_efficiencies`、`draw_amplitudes`、`draw_differences` 与 `draw_fractions`。
- `src/raser/stages/analysis/across_points.py`：提供 `scanned_options` 与 `write_points`，提取各点间变化的选项，写出 `points.json` 并在单一数值扫描变量下绘制 `trend`。
- 作业调度、节点复用与加锁由 `src/raser/lifecycle/` 承担。

### 核心数据结构

| 数据结构 | 字段或元素 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| 单作业重建条目（`point_tables` 返回元素） | `(place, folder, index, table)` | `(int, Path, int, EventTable)` | 无（`table` 内阈值为 $\text{V}$） | 作业在 `jobs` 中的 0 基下标、作业所在文件夹、作业号与读出的 `EventTable` |
| 重建参数键（`table_setting` 返回值） | `(threshold, amplitude_threshold, fractions, edge)` | `(float, float, tuple[float, ...], tuple[str, ...])` | $\text{mV}$、$\text{mV}$、无、无 | 用于校验同点一致性的可哈希参数四元组（两阈值已四舍五入至 `9` 位小数） |
| 选中事例时间字典 `times`（`event_times` 返回） | `job`, `event` | `ndarray`（`float64`，写 `events.h5` 时转 `int64`） | 无 | 选中事例所属作业下标与 Geant4 事例号 |
| 选中事例时间字典 `times`（`event_times` 返回） | `ToA`, `ToT`, `truth`, `CoG`, `CFD<percent>` | `ndarray`（`float64`） | $\text{s}$ | 选中事例的各重建时刻、过阈持续时间与最早沉积真值时刻 |
| 选中事例时间字典 `times`（`event_times` 返回） | `amplitude`, `baseline`, `noise` | `ndarray`（`float64`） | $\text{V}$ | 选中事例基线以上脉冲幅度、基线均值与基线总体标准差 |
| 单点结果字典 `result`（`point.py`） | `reconstruction`, `collection`, `timing` | `dict` | `reconstruction` 阈值 $\text{mV}$；`collection` 无量纲；`timing.times` 时间量 $\text{s}$ | 与单点 `result.json` 一一对应的内存汇总结构 |
| 跨点汇总行 `row`（`across_points.py`） | `point`, `<变化扫描选项>`, `events`, `efficiency`, `efficiency_error`, `selected`, `<通道>` | `dict` | 选项按原单位；效率无量纲；通道 `sigma68`/`sigma`/`sigma_error` 为 $\text{s}$ | 与 `points.json` 中每个扫描点元素一一对应的字典 |

## 接口

### 命令行与运行选项

`raser analysis [路径]`：不给路径就是当前文件夹，给了就是相对或绝对路径，例如 `examples/HPK-Si-PiN/signal`。全局选项和共用运行参数见[命令行接口](../cli.md)：

| 选项 | 默认值 | 含义 |
| --- | --- | --- |
| `-b` | 关闭 | 把作业提交到集群队列（集群机制见[作业、日志、锁、断点续跑与集群提交](../lifecycle/jobs.md)） |
| `-t` | 关闭 | 与 `-b` 联用，只检查并预览提交信息 |
| `-mem` | `1` | 集群提交的内存档位 |
| `-s`、`--seed`、`--same-seeds` | 见[命令行接口](../cli.md) | 作用于要补跑的上游测量环节 |
| `--set` | 无 | 用“段.键”作地址修改设置，例如 `--set field.voltage=100` |
| `--scan` | 无 | 用“段.键”作地址扫描设置，例如 `--scan field.voltage=100,200` |
| `--dry-run` | 关闭 | 只打印将要运行的扫描点、环节和作业状态 |

收集效率最少事例数 `2`、截断高斯拟合最少事例数 `20` 与最大轮数 `6`、直方图箱数与拟合曲线点数、`3 × 4` 子图上限以及 PNG 分辨率都写死在代码里。定时阈值、团簇种子的幅度阈值、恒比比例与脉冲沿方向是 `reconstruction` 段的设置，`analysis` 直接读取 `reconstruction` 节点里 `reconstruction.h5` 记录的值；改了它们，`reconstruction` 节点号变，`analysis` 跟着重算。

### 读入的文件

- **`<实验文件夹>/points.json`**：参数表，给出每个扫描点各环节的节点号。
- **`deposit` 节点里的 `deposit.h5`**：文件格式见[能量沉积与电离（`core/deposit`）](../core/deposit.md)。本环节只读取事例数 `len(events)` 与每个事例最早沉积步时刻 `min(event.t)`（$\text{s}$）。
- **`current` 节点里的 `current.h5`**：文件格式见[载流子漂移与感应电流（`core/current`）](../core/current.md)。本环节只读取每个事例的 `event`、`charge`（$\text{C}$）与 `pairs`（对）。
- **`reconstruction` 节点里的 `reconstruction.h5`**：文件格式见[事件重建（`core/reconstruction`）](../core/reconstruction.md)。本环节读取属性 `electrodes`、`threshold`（$\text{V}$）、`amplitude_threshold`（$\text{V}$）、`fractions`、`edge` 及数据集 `event`、`selected`、`ToA`、`ToT`、`amplitude`、`baseline`、`noise`、`CoG`、`CFD`。

### 写出的文件

单点结果写在这个点的 `analysis` 节点里，从 `points/<点名>/analysis/` 查看；节点里另有一份 `node.json`。跨点结果写在 `<实验文件夹>/analysis/` 下。

#### `points/<点名>/analysis/result.json`

每个扫描点一份（2 空格缩进 JSON）：

| 顶层键 | 子键 | 类型 | 单位 | 写入条件与含义 |
| --- | --- | --- | --- | --- |
| `reconstruction` | `threshold`, `amplitude_threshold`, `fractions`, `edge` | `float`, `float`, `list[float]`, `list[str]` | $\text{mV}$、$\text{mV}$、无、无 | 至少有 `1` 个含事例作业时写入；两阈值按 `round(val / 1e-3, 9)` 舍入 |
| `collection` | `events` | `int` | 个 | 总写入；该点总事例数 |
| `collection` | `mean`, `mean_error`, `spread` | `float` | 无 | `events >= 2` 时写入；电荷收集效率均值、均值标准误与样本标准差（`ddof=1`） |
| `collection` | `error` | `str` | 无 | `events < 2` 时替代 `mean`/`mean_error`/`spread` 写入，原文为 `<count> events in the point, a mean and a spread need at least 2` |
| `timing` | `events`, `selected` | `int` | 个 | 总写入；总事例数与选中事例数 |
| `timing` | `polarity` | `float` | 无 | 至少有 `1` 个事例时写入；`+1.0` 对应 `"rising"`，`-1.0` 对应 `"falling"` |
| `timing` | `times.<通道>` | `dict` | 见含义 | 全部通道拟合成功时写入；`<通道>` 为 `"ToA"`、`"CoG"` 与各 `"CFD<percent>"`，含 `events`（`int`，个）、`window`（`[low, high]`，$\text{s}$）、`window_events`（`int`，个）、`rounds`（`int`，轮）、`mean`、`mean_error`、`sigma`、`sigma_error`、`sigma68`（均为 `float`，$\text{s}$）与 `missing`（`int`，个，为 `NaN` 的选中事例数） |
| `timing` | `error` | `str` | 无 | 全点 `0` 事例时写入 `"the jobs recorded no event"`；有事例但任一通道触发 `TooFewValues` 时替代 `times` 写入 `<len> values, fewer than 20` 或 `<inside> of <len> values are inside [<low>, <high>], fewer than 20` |

#### `points/<点名>/analysis/events.h5`

扫描点至少有 `1` 个事例时写出。文件只含该点全部 `selected` 个选中事例的一维数据集：

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `job` | `(selected,)`, `int64` | 无 | 事例所在作业在该点作业列表中的 0 基下标 |
| `event` | `(selected,)`, `int64` | 无 | 事例在所属作业中的 Geant4 编号 |
| `ToA` | `(selected,)`, `float64` | $\text{s}$ | 过阈到达时间 |
| `ToT` | `(selected,)`, `float64` | $\text{s}$ | 过阈持续时间 |
| `amplitude` | `(selected,)`, `float64` | $\text{V}$ | 基线以上最大脉冲幅度 |
| `baseline` | `(selected,)`, `float64` | $\text{V}$ | 基线均值 |
| `noise` | `(selected,)`, `float64` | $\text{V}$ | 基线总体标准差 |
| `truth` | `(selected,)`, `float64` | $\text{s}$ | 事例在 `deposit` 中最早能量沉积步的时刻 |
| `CoG` | `(selected,)`, `float64` | $\text{s}$ | 过阈区间的时间重心 |
| `CFD<percent>` | `(selected,)`, `float64`（同名比例拼接时按倍数拉长） | $\text{s}$ | 恒比定时时刻，`<percent>` 为 `round(100 * part)` |

#### `<实验文件夹>/analysis/points.json`

有结果的扫描点多于 `1` 个时写出（2 空格缩进 JSON 数组，每个点占一个对象）：

| 键名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `point` | `str` | 无 | 点名 |
| `<变化扫描选项>` | 原选项类型 | 原选项单位 | 仅列出各点之间取值有差异的选项键（按字典序） |
| `events` | `int` | 个 | 该点总事例数 |
| `efficiency`, `efficiency_error` | `float \| null` | 无 | 收集效率均值及均值标准误；无效率结果时为 `null` |
| `selected` | `int` | 个 | 选中事例数 |
| `<通道>`（`ToA`、`CoG`、`CFD<percent>`） | `{"sigma68", "sigma", "sigma_error"}`（各为 `float`） | $\text{s}$ | 该点存在 `timing.times` 时写入 |

#### 绘图输出

| 文件路径 | 生成条件 | 内容 | 坐标单位 |
| --- | --- | --- | --- |
| `points/<点名>/analysis/efficiency.png`、`.pdf` | 事例数 $\ge 2$ | 全部事例电荷收集效率的 `60` 箱直方图、均值黑色虚线；图例写事例数 `<N> events` 与均值 `mean <均值>` | 横轴 `Charge collection efficiency`（无量纲），纵轴 `Events` |
| `points/<点名>/analysis/amplitude.png`、`.pdf` | 事例数 $\ge 1$ | 选中事例基线以上脉冲幅度的 `60` 箱直方图、`amplitude_threshold` 黑色虚线；图例写选中数与总事例数 `<n> of <N> events` 和阈值 `threshold <阈值> mV` | 横轴 `Amplitude [mV]`，纵轴 `Events` |
| `points/<点名>/analysis/time_difference.png`、`.pdf` | `timing.times` 全部算出 | 最多 `3 × 4` 子图展示 `ToA`、`CoG` 与前 `10` 个 `CFD*` 通道相对 `truth` 的时间差分布（`mean ± 8 * sigma` 分 `64` 箱）、末轮拟合窗口阴影与黑色截断高斯拟合曲线；每幅小标题写通道名，左上角写 `sigma68`、`sigma` 与窗内事例数 | 横轴 `<通道名> - truth [ps]`，纵轴 `Events` |
| `points/<点名>/analysis/resolution_of_fraction.png`、`.pdf` | `timing.times` 全部算出 | 各 `CFD*` 通道的截断高斯拟合 `sigma`（黑色实心圆，带误差棒）与 `sigma68`（黑色空心方块）随恒比比例变化 | 横轴 `CFD fraction`（无量纲），纵轴 `Time resolution [ps]` |
| `<实验文件夹>/analysis/trend.png`、`.pdf` | 有结果的扫描点多于 `1` 个、变化选项恰有 `1` 个且取值均为非布尔数值 | 按扫描变量升序绘制左右双图：左图为收集效率及误差棒，右图为各 `CFD*` 通道的 `sigma` 及误差棒，每个通道一条线 | 横轴为扫描选项名；左图纵轴 `Charge collection efficiency`，右图纵轴 `Time resolution [ps]` |
