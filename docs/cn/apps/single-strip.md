# 单层条形探测器测角

`raser telescope joint-strip` 从读出波形估计带符号的横向斜率。
角度为 `atan(dx/dz)`，单位为度。岭回归、小网络和模板同时输出入口位置，
其单位为 µm，参考面与原点由数据清单显式给出。

## 器件与输入

上游已有 `strip_ayyouby` 器件，厚 50 µm，节距 20 µm，条长 5 mm，
三道分别对应左邻条、中央条、右邻条。默认背电极 −200 V，
两埋层峰值浓度各为 3×10¹⁶ cm⁻³，高斯指数含 1/2。
掺杂系数描述注入剖面。实际增益由具体器件和偏压决定。
更换器件或工作点时需另存响应标识并重新标定。

每个 NPZ 按道保存原始时间与有符号电压。
例如第一道为 `frontend_time_s_1` 与 `frontend_mV_1`，
单位分别为秒和 mV。清单声明要读的通道，读取和哈希覆盖这些通道。
回归支持 C、L+C、C+R 和 L+C+R 四种视图，每种分别训练。
具体清单与标签格式见[英文使用说明](../../en/apps/single-strip.md)。

入射角、入口位置和真实跨条数另存标签文件。预测命令只需要波形清单与模型。
同一粒子的通道、噪声和输运变体使用共同的 `particle_id`，始终归入一个数据划分。
程序检查训练、区间校准与预测之间的事例、粒子和波形重复。

## 先跑小例子

在已安装 RASER 的 Python 3.11 环境中，从仓库根目录执行。

~~~bash
python examples/single_strip_angle/run.py --output work/single-strip-example
~~~

示例在本地生成 36 条训练波形和另外 12 条评估波形，
逐个运行差分峰值、差分时序、岭回归和 24 隐单元小网络。
岭回归与网络同时比较四种读出视图。
生成器用相对延迟编码斜率、相对幅度编码位置，叠加独立高斯噪声。
这些合成波形用于验收软件流程；其 RMSE 描述解析生成器的参数恢复。
真实探测器性能需使用经过物理验证的器件信号。
种子与生成器哈希保存在输出的 `data/generation.json`。

生成的 `comparison.json` 对同一组可给候选角的事例比较各方法，
并按几何单命中、双命中、三命中分别列请求数、候选数和候选角 RMSE。
无事例的组保留零分母。三路读出仍可对应几何单命中。

## 方法与输出

| 估计器 | 输入与结果 |
|---|---|
| `difference-peak` | 左右邻条差分的带符号极值，经线性标定给出斜率 |
| `difference-waveform` | 差分波形的 32 点，经岭回归给出斜率 |
| `ridge` | 摘要或完整波形特征，给出斜率与入口位置 |
| `mlp` | 与岭回归相同的输入，用一层 24 单元网络回归 |
| `template` | 联合响应模板，给出角度／位置候选、校准区间与严格判定 |

差分方法用三道共同确定时间对齐和幅度归一。
完整回归输入共 120 个数，包括每道 32 个波形点、20 个摘要量和 4 个组合波形矩。
摘要输入为 20 个数。时间窗、极性、噪声门槛、归一化、输入顺序与训练设置
均保存在模型中。模型保存后可直接重载预测。

~~~bash
raser telescope joint-strip calibrate --estimator mlp \
  --dataset train.json --labels train-labels.json --output mlp.npz
raser telescope joint-strip predict \
  --dataset test.json --model mlp.npz --output prediction.json
raser telescope joint-strip evaluate \
  --dataset test.json --labels test-labels.json --model mlp.npz --output evaluation.json
~~~

模板使用独立区间校准集，命令需增加 `--interval-dataset` 和
`--interval-labels`。严格通过要求响应在标定支持范围内，
95% 联合区连通且位于校准边界内。失败时保留候选值和原因。
回归输出的严格通过率为 `null`，其接受条件需要独立校准。

角 RMSE 在明示的候选事例集合上计算，等于角残差平方平均值的平方根。
偏置、残差标准差、绝对误差尾部与位置误差分别输出。
每个输入事例都进入请求分母。数值收敛、前端条件和独立物理性能验证的范围，
随对应研究数据记录。
