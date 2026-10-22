# raser/apps/sweep/energy_resolution.py
import os
import time
import numpy as np
import ROOT
ROOT.gROOT.SetBatch(True)
import matplotlib.pyplot as plt
from scipy import stats
from raser.supports.output import output  # 统一输出路径
from raser.core.device import build_device as bdv  # 设备构建


import numpy as np
import ROOT


def _read_root_file(file_path, electrode_index):
    """读取单个 ROOT 文件，返回 (事件数, bins) 的 numpy 数组。
       如果文件、tree、目标波形分支不存在或无效，则返回 None。
    """
    f = ROOT.TFile(file_path)
    if not f or f.IsZombie():
        print(f"Warning: could not open {file_path}")
        return None

    try:
        tree = f.Get("tree")
        if not tree:
            print(f"Warning: tree not found in {file_path}")
            return None

        n_events = tree.GetEntries()
        if n_events == 0:
            print(f"Warning: no events in tree of {file_path}")
            return None

        branch_name = f"amplified_waveform_{electrode_index}"
        if not tree.GetBranch(branch_name):
            print(f"Warning: branch {branch_name} not found in {file_path}")
            return None

        # 1. 读取第一个事件，获取 nbins
        tree.GetEntry(0)
        hist = getattr(tree, branch_name)
        if not hist:
            print(f"Warning: histogram {branch_name} is invalid in {file_path}")
            return None
        
        nbins = hist.GetNbinsX()
        if nbins <= 0:
            print(f"Warning: histogram {branch_name} has no bins in {file_path}")
            return None

        # 2. 预分配内存，一次性读取所有事件
        print(f"Reading {n_events} events from {file_path}")
        data = np.zeros((n_events, nbins))
        
        for i in range(n_events):
            tree.GetEntry(i)
            hist = getattr(tree, branch_name)
            if not hist:
                continue
            # 使用 numpy 直接从 histogram 批量获取数组
            # 注意：GetArray() 返回的是长度为 nbins + 2 的数组（包含溢出流和未流入）
            # 我们需要的是第 1 到 nbins 的元素
            for j in range(nbins):
                data[i, j] = hist.GetBinContent(j + 1)
        return data

    finally:
        # 无论发生什么（包括 return None），文件必定会被关闭
        f.Close()
def _read_csv_file(file_path):
    """
    读取单个 CSV 文件。
    假定每行是一个事件，各列为波形采样点（无行头或自动检测跳过表头）。
    返回 (事件数, bins) 的 numpy 数组。
    """
    # 先检查第一行是否为表头（尝试将第一行第一列转为 float）
    with open(file_path, 'r') as f:
        first_line = f.readline().strip()
        parts = first_line.split(',')
        has_header = False
        if parts:
            try:
                float(parts[0])
            except ValueError:
                has_header = True   # 第一列非数字，判定有表头

    try:
        if has_header:
            data = np.genfromtxt(file_path, delimiter=',', skip_header=1)
        else:
            data = np.genfromtxt(file_path, delimiter=',')
        # print(f"read_csv_file: {file_path}, shape: {data.shape}")
    except Exception as e:
        print(f"Warning: failed to read {file_path}: {e}")
        return None

    # 若数据是一维，转为二维（单事件）
    if data.ndim == 1:
        data = data.reshape(1, -1)
    # 若数据为空或无效，返回 None
    if data.size == 0:
        print(f"Warning: no valid data in {file_path}")
        return None
    return data


import os
import numpy as np


def read_events(event_folder_path, electrode_index=0):
    """
    读取文件夹中的波形数据，支持 ROOT (.root) 和 CSV (.csv) 文件。
    会扫描顶层文件以及一级子目录中的文件。

    返回 numpy 数组，形状 (事件总数, 波形点数)。
    """
    print(f"Reading events from {event_folder_path} for electrode {electrode_index}...")
    waveforms_list = []
    waveforms_show = 0
    def _process_file(file_path, label, waveforms_show):
        """读取单个文件，返回 (n_events, nbins) 的二维数组，失败返回 None。"""
        lower = file_path.lower()
        if lower.endswith('.root'):
            data = _read_root_file(file_path, electrode_index)
        elif lower.endswith('.csv'):
            data = _read_csv_file(file_path)
        else:
            return None

        if data is None:
            return None
        if data.ndim != 2 or data.shape[1] == 0:
            print(f"Warning: unexpected shape {data.shape} in {label}")
            return None

        print(f"Read {data.shape[0]} events from {label}, waveform length: {data.shape[1]}")
        if waveforms_show < 1:
            print(f"Sample waveform: {data[0]}")
        waveforms_show += 1
        return data  # ← 直接使用，不要 data[:, 1]

    # 遍历顶层文件 + 一级子目录文件，顺序稳定
    for entry in sorted(os.listdir(event_folder_path)):
        full_path = os.path.join(event_folder_path, entry)

        if os.path.isdir(full_path):
            for sub_entry in sorted(os.listdir(full_path)):
                sub_file_path = os.path.join(full_path, sub_entry)
                if not os.path.isfile(sub_file_path):
                    continue
                data = _process_file(sub_file_path, f"{entry}/{sub_entry}", waveforms_show)
                if data is not None:
                    waveforms_list.append(data)
        elif os.path.isfile(full_path):
            data = _process_file(full_path, entry, waveforms_show)
            if data is not None:
                waveforms_list.append(data)
        # 其他类型（符号链接、socket 等）忽略

    if not waveforms_list:
        raise ValueError(f"No valid waveform files found in {event_folder_path}")

    # 显式检查各文件 nbins 是否一致，报错时列出具体值
    nbins_set = {arr.shape[1] for arr in waveforms_list}
    if len(nbins_set) > 1:
        raise ValueError(
            f"Inconsistent number of bins among files: {sorted(nbins_set)}"
        )

    waveforms = np.vstack(waveforms_list)
    print(f"Total events read: {waveforms.shape[0]}, waveform length: {waveforms.shape[1]}")
    return waveforms



def compute_energy_resolution(waveforms, my_d, fit_output_path=None):
    """
    计算能量分辨率，并可选绘制拟合曲线。
    返回 energy_resolution (float)
    """
    print("Computing energy resolution...")
    print(waveforms.shape)
    peaks = []
    for i in range(waveforms.shape[0]):
        peak_i = max(waveforms[i,:])
        peaks.append(peak_i)
        peaks.sort()
    # print(peaks)
    sep = 50
    mu, sigma = stats.norm.fit(peaks)
    fwhm = 2 * np.sqrt(2 * np.log(2)) * sigma
    energy_resolution = fwhm / mu

    # 如果是单能量测试（非扫描），保存拟合图
    if not hasattr(my_d, 'sweep') or my_d.sweep is None:
        if fit_output_path is None:
            now = time.strftime("%Y_%m%d_%H%M%S")
            # fit_output_path = output("/afs/ihep.ac.cn/users/s/shaochangpu/raser1/raser-main/work", my_d.det_name, now)
            fit_output_path = os.path.join(os.getenv("RASER_WORK_PATH"), my_d.det_name, now)
        draw_fit_curve(peaks, mu, sigma, fit_output_path, sep, my_d.det_name)
        with open(os.path.join(fit_output_path, f"{my_d.det_name}_energy_resolution.txt"), 'w') as f:
            f.write(f"Energy resolution: {energy_resolution:.2%}\n")
    return energy_resolution

def draw_fit_curve(peaks, mu, sigma, path, bins, det_model):
    """绘制高斯拟合曲线"""
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.hist(peaks, bins=bins, density=False, alpha=0.6, color='steelblue',
             edgecolor='black', linewidth=0.5, label='peaks')
    ax1.set_xlabel('voltage')
    ax1.set_ylabel('counts', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')
    ax1.grid(alpha=0.3)

    ax2 = ax1.twinx()
    HIST_XMIN = 200.0
    HIST_XMAX = 330.0

    x = np.linspace(HIST_XMIN, HIST_XMAX, 200)
    ax1.set_xlim(HIST_XMIN, HIST_XMAX)
    ax2.set_xlim(HIST_XMIN, HIST_XMAX)
    #x = np.linspace(min(peaks), max(peaks), 200)
    pdf = stats.norm.pdf(x, mu, sigma)
    ax2.plot(x, pdf, 'r-', lw=2.5, label=f'fit_curve $N({mu:.2f}, {sigma:.2f}^2)$')
    ax2.set_ylabel('Probability density', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')
    ax1.set_title('fit curve')
    os.makedirs(path, exist_ok=True)
    fig.savefig(os.path.join(path, f"{det_model}_fit_curve.pdf"))
    plt.close(fig)