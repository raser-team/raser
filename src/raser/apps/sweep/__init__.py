# raser/apps/sweep/__init__.py
import os
from raser.supports import runs, jobs
from raser.supports.output import output
from raser.core.device import build_device as bdv
from .energy_resolution import read_events, compute_energy_resolution, draw_fit_curve
from .sweep import run_simulation, energy_resolution_calculation
import json
import time

def _prepare(kwargs):
    """设置默认参数和路径"""
    # 确保 det_name 存在
    det_name = kwargs.get('det_name')
    if not det_name:
        raise ValueError("det_name is required")
    my_d = bdv.Detector(det_name)
    # 应用可选参数
    if kwargs.get('voltage') is not None:
        my_d.voltage = kwargs['voltage']
    if kwargs.get('irradiation') is not None:
        my_d.irradiation_flux = float(kwargs['irradiation'])
    if kwargs.get('g4experiment') is not None:
        my_d.g4experiment = kwargs['g4experiment']
    if kwargs.get('amplifier') is not None:
        my_d.amplifier = kwargs['amplifier']
    if kwargs.get('subfolder_path') is not None:
        my_d.subfolder_path = kwargs['subfolder_path']
    # 扫描模式标记
    if kwargs.get('sweep'):
        my_d.sweep = kwargs['sweep']  # 例如 "Xbeam_energy_resolution"
    kwargs['_detector'] = my_d
    return my_d

def run(kwargs):
    """主入口"""
    my_d = _prepare(kwargs)

    # 如果是扫描模式
    if kwargs.get('sweep'):
        # 读取扫描配置（从环境变量或设置路径）
        sweep_mode = my_d.sweep
        sweep_json = os.getenv("RASER_SETTING_PATH") + "/sweep/" + sweep_mode + ".json"
        with open(sweep_json) as f:
            sweep_dict = json.load(f)
        kwargs['sweep_parameter'] = sweep_dict['sweep_parameter']
        kwargs['sweep_range'] = sweep_dict['sweep_range']
        kwargs['sweep_step'] = sweep_dict['step']
        kwargs['scan_number'] = sweep_dict['scan_number']
        range_len = sweep_dict['sweep_range'][1] - sweep_dict['sweep_range'][0]
        kwargs['sweep_number'] = int(range_len // sweep_dict['step'] + 1)

        # 输出文件夹
        local_time = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        folder_path = output(__file__, kwargs['det_name'], 'sweep',
                             f"{kwargs['sweep_parameter']}_{local_time}")
        kwargs['folder_path'] = folder_path
        kwargs['g4_json'] = os.getenv("RASER_SETTING_PATH") + "/g4experiment/" + my_d.g4experiment + ".json"

        # 如果使用已有数据，跳过仿真
        if not kwargs.get('usedata', False):
            run_simulation(kwargs['g4_json'], kwargs)
        else:
            print("Using existing data, skip simulation.")

        # 后处理
        sweep_list, eres_list = energy_resolution_calculation(kwargs)
        # 绘图
        import matplotlib.pyplot as plt
        plt.plot(sweep_list, eres_list)
        plt.xlabel(kwargs['sweep_parameter'])
        plt.ylabel("Energy Resolution")
        plt.title(f"Energy Resolution vs {kwargs['sweep_parameter']}")
        plt.savefig(os.path.join(folder_path, f"energy_resolution_vs_{kwargs['sweep_parameter']}.pdf"))
        plt.close()
        return

    # 否则为单次计算模式
    event_folder_path = my_d.subfolder_path
    if not event_folder_path:
        # 可以从 kwargs 获取，或使用默认路径
        raise ValueError("subfolder_path (event folder) must be provided")
    waveforms = read_events(event_folder_path)
    eres = compute_energy_resolution(waveforms, my_d)
    print(f"Energy resolution: {eres:.2%}")
    
    return eres