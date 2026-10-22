# 入门

> RASER 5.0 · Python 3.11 · 安装与使用分为两个步骤

环境安装一次即可。每个新 shell 在运行 RASER 前激活一条完整环境路径。该路径提供彼此匹配的 Python、ROOT、Geant4 与 ngspice 运行环境。

---

## 📦 安装环境

根据主机平台选择一条路径。本节命令用于创建环境或镜像。工作流命令见[运行 RASER](#运行-raser)。

安装不是一键操作：首次安装时按所选平台依次执行下列命令。安装完成后，每个新 shell 只需一条激活命令。

### 原生 Linux x86-64

conda 环境提供 Python 3.11、ROOT、ngspice 和 MKL。项目 venv 继承这些系统包，并加入 `env/uv.txt` 中固定版本的 Python 包。

```bash
conda env create -p .conda/envs/raser -f env/conda-linux-x86.yml
conda activate "$PWD/.conda/envs/raser"
uv venv --system-site-packages --python "$(command -v python3.11)" .venv
uv pip sync --python .venv/bin/python env/uv.txt
```

需要精确的 conda 产物时，可使用显式 conda 规格：

```bash
conda create -p .conda/envs/raser -c conda-forge --file env/conda-linux-64.lock
```

Geant4 由主机或外部安装提供。其余原生运行时由 conda 环境提供。

### Ubuntu 22.04 集群 SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_ubuntu.sif bootstrap/ubuntu/raser-ubuntu-sif.def
```

该镜像提供项目 Python 环境、ngspice 与 Ubuntu 运行库。ROOT 和 Geant4 来自匹配的 `ubuntu2204` LCG view。

### EL9 集群 SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_el9.sif bootstrap/el9/raser-el9-sif.def
```

该镜像提供 ROOT、ngspice、项目 Python 环境，以及与外部 EL9 Geant4 安装匹配的运行库。可选源码归档可缓存在 `bootstrap/ingredients/` 下。

单进程 squashfs 选项用于受限集群节点。镜像细节见[容器路径说明](../../bootstrap/README.md)。

### 原生 Apple Silicon

固定版本的 Python 包要求 arm64 上的 macOS 14 或更新版本。ROOT 由 conda 提供；ngspice 构建至当前 conda 环境中。

```bash
conda env create -p .conda/envs/raser -f env/conda-macos-arm64.yml
conda activate "$PWD/.conda/envs/raser"
env/install-ngspice-macos-arm64.sh
uv venv --system-site-packages --python "$(command -v python3.11)" .venv
uv pip sync --python .venv/bin/python env/uv.txt
```

对应的显式 conda 规格如下：

```bash
conda create -p .conda/envs/raser -c conda-forge --file env/conda-macos-arm64.lock
```

基于 Lima 的 macOS 路径先构建 Ubuntu SIF，再使用 `make run-raser-sif-macos`。

## 🔌 激活环境路径

激活其中一条路径：

| 路径 | 命令 |
| --- | --- |
| 原生 conda | `source env/setup_cvmfs.sh conda` |
| Ubuntu 22.04 SIF | `source env/setup_cvmfs.sh ubuntu` |
| EL9 SIF | `source env/setup_cvmfs.sh el9` |
| 本地自动选择 | `source env/setup_cvmfs.sh` |

自动选择依次查找本地 Ubuntu SIF、本地 EL9 SIF 和 conda 路径。conda 路径优先加载已配置的 CVMFS profile；若该文件不存在，则从 `PATH` 加载 conda，并自动激活 `.conda/envs/raser`。

在已配置 CVMFS 站点之外，使 `geant4-config` 位于 `PATH` 中或设置外部安装前缀，然后使用相同的一条激活命令：

```bash
export RASER_GEANT4_INSTALL=/path/to/geant4-install
source env/setup_cvmfs.sh conda
```

设置脚本向当前 shell 加入项目 CLI、组件搜索路径与 `work/` 位置。依赖安装在前述环境准备步骤中完成。

## 🚀 运行 RASER

首先使用元数据命令检查当前环境路径：

```bash
raser --version
raser --help
```

随后通过公共 CLI 运行工作流：

```bash
raser field -cv HPK-Si-PiN
raser signal HPK-Si-PiN
raser cce NJU-PiN
```

使用 `raser <command> --help` 查看选项。公共命令为 `raser`；源码树中的模块路径属于实现细节。

## 验证完整传感器链

下列命令求解 Device 场数据，并以固定工作参数和随机种子运行三个主要传感器响应应用：

```bash
source env/setup_cvmfs.sh conda
raser field HPK-Si-PiN -bias 200
raser field -wf HPK-Si-PiN -bias 200
raser signal HPK-Si-PiN decay/Sr90 -vol 200 --events-per-job 1 --seed 7
raser tct signal HPK-Si-PiN SPA_top_Si_IR -vol 200 --seed 7
raser timeres HPK-Si-PiN decay/Sr90 -vol 200 --events-per-job 100 --seed 7
```

Signal 处理一个 Geant4 事件。TCT 计算激光产生的载流子组。Timeres 处理 100 个 Geant4 事件并写入时间分析。

## 🌳 在工作树间共享环境

本地 SIF 镜像及 conda/venv 目录是被忽略的运行时资产。将工作树链接至主检出中的共享资产：

```bash
cd .worktrees/<name>
ln -s ../../img img
ln -s ../../.conda .conda
ln -s ../../.venv .venv
```

从工作树根目录运行激活命令，使路径指向相应源码树，同时共享大型运行时资产。

## 📌 依赖策略

RASER 按策略省略 `uv.lock`。直接 Python 依赖保留在 `pyproject.toml` 中；精简且固定版本的 `env/uv.txt` 定义部署的 Python 包，供原生与 SIF 路径使用。Conda YAML 与显式规格文件定义编译依赖。生成 `uv.lock` 需要明确调整相应策略。
