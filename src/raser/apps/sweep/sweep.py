# raser/apps/xray/sweep.py
import json
import os
import time
from functools import partial
from concurrent.futures import ProcessPoolExecutor, as_completed
import re
from pathlib import Path
from raser.supports.output import output
from raser.apps.signal import gen_signal_scan  # 假设有这个模块

def run_sweep(args_tuple, kwargs, sweep_parameter):
    parameter_value, i = args_tuple
    kwargs['job'] = i
    # 可在此更新 g4_json 或其它配置文件
    # 调用信号生成（需确保 gen_signal_sweep.main 接受 kwargs）
    gen_signal_scan.main(kwargs)

def run_simulation(g4_json, kwargs):
    folder_path = kwargs['folder_path']
    scan_number = kwargs['scan_number']
    sweep_parameter = kwargs['sweep_parameter']
    sweep_range = kwargs['sweep_range']
    sweep_step = kwargs['sweep_step']
    sweep_number = kwargs['sweep_number']
    max_processes = min(scan_number, os.cpu_count() or 4)

    for number in range(sweep_number):
        parameter_value = sweep_range[0] + number * sweep_step
        subfolder_name = f"{sweep_parameter}_{parameter_value}"
        subfolder_path = os.path.join(folder_path, subfolder_name)
        os.makedirs(subfolder_path, exist_ok=True)
        kwargs['subfolder_path'] = subfolder_path

        # 更新 g4_json（或其他配置）
        with open(g4_json, 'r') as f:
            dict_data = json.load(f)
        dict_data[sweep_parameter] = parameter_value
        with open(g4_json, 'w') as f:
            json.dump(dict_data, f, indent=4)

        args = [(parameter_value, i) for i in range(scan_number)]
        func = partial(run_sweep, kwargs=kwargs, sweep_parameter=sweep_parameter)
        with ProcessPoolExecutor(max_workers=max_processes) as executor:
            futures = [executor.submit(func, arg) for arg in args]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"任务失败: {e}")

def extract_number(path):
    name = Path(path).name
    match = re.search(r'\d+\.?\d*', name)
    return float(match.group()) if match else 0

def energy_resolution_calculation(kwargs):
    """遍历所有子文件夹，计算每个参数点下的能量分辨率"""
    from .core import compute_energy_resolution, read_events
    from raser.device import build_device as bdv

    folder_path = kwargs['folder_path']
    sweep_parameter = kwargs['sweep_parameter']
    sweep_list = []
    energy_resolution_list = []

    subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
    subfolders = sorted(subfolders, key=extract_number)
    for subfolder in subfolders:
        subfolder_path = os.path.join(folder_path, subfolder)
        # 读取波形
        waveforms = read_events(subfolder_path)
        # 构建探测器对象（可能需要从 kwargs 取参数）
        det_name = kwargs['det_name']
        my_d = bdv.Detector(det_name)
        # 应用参数
        if kwargs.get('voltage') is not None:
            my_d.voltage = kwargs['voltage']
        # ... 其他参数
        # 计算能量分辨率（不绘图，因为后续会汇总）
        eres = compute_energy_resolution(waveforms, my_d, fit_output_path=None)
        energy_resolution_list.append(eres)
        sweep_value = float(subfolder.split("_")[-1])
        sweep_list.append(sweep_value)
        # 保存单个结果
        with open(os.path.join(folder_path, f"energy_resolution_{subfolder}.txt"), 'w') as f:
            f.write(str(eres))
    return sweep_list, energy_resolution_list