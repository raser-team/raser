import json
import os
import time
from functools import partial
from concurrent.futures import ProcessPoolExecutor,as_completed

from ..device import build_device as bdv
from ..util.output import output
from . import gen_signal_sweep

def run_sweep(args_tuple, kwargs, sweep_parameter):
    
    parameter_value, i = args_tuple
    kwargs['job'] = i
    #监测点
    print(f"Running sweep for {sweep_parameter} = {parameter_value}, scan number: {i}")
    #
    folder_path = kwargs['folder_path']
    subfolder_name = f"{sweep_parameter}_{parameter_value}"
    subfolder_path = os.path.join(folder_path, subfolder_name)
    #监测点
    #print(f"Creating subfolder: {subfolder_path}")
    #
    kwargs['subfolder_path'] = subfolder_path
    # g4_json = kwargs['g4_json']
    
    # with open(g4_json, 'r') as f:
    #     #print(f"Reading {g4_json} for updating {sweep_parameter} to {parameter_value}")
    #     dict_data = json.load(f)
    #     print(dict_data.get(sweep_parameter))
    # if dict_data.get(sweep_parameter) == parameter_value:
    #     print(f"{sweep_parameter} already set to {parameter_value} in {g4_json}, skipping update.")
    #     pass
    # else:
    #     dict_data[sweep_parameter] = parameter_value
    #     with open(g4_json, 'w') as f:
    #         json.dump(dict_data, f, indent=4)
        #监测点
        # print(f"Updated {sweep_parameter} to {parameter_value} in {g4_json}")
        #

    gen_signal_sweep.main(kwargs)


def check_signal(kwargs):
    kwargs['job'] = 1
    subfile_name = f"check_signal"
    subfile_path = os.path.join(kwargs['folder_path'], subfile_name)
    kwargs['subfile_path'] = subfile_path
    gen_signal_sweep.main(kwargs)




def run_simulation(g4_json, kwargs):
    folder_path = kwargs['folder_path']
    scan_number = kwargs['scan_number']
    #暂时不知道这个scan_number是干什么的，先放在这里,让它是1，后续再完善
    sweep_parameter = kwargs['sweep_parameter']
    sweep_range = kwargs['sweep_range']
    sweep_step = kwargs['sweep_step']
    sweep_number = kwargs['sweep_number']
    max_processes = min(scan_number, os.cpu_count() or 4)
    for number in range(sweep_number):
        args = []
        parameter_value = sweep_range[0] + number * sweep_step

        subfile_name = f"{sweep_parameter}_{parameter_value}"
        subfile_path = os.path.join(folder_path, subfile_name)
        kwargs['subfile_path'] = subfile_path
        #运行检测点
        print (f"Preparing sweep for {sweep_parameter} = {parameter_value}")
        #
        #暂时只能改g4_json里面的参数
        with open(g4_json, 'r') as f:
            #print(f"Reading {g4_json} for updating {sweep_parameter} to {parameter_value}")
            dict_data = json.load(f)
            print(dict_data.get(sweep_parameter))
        
        dict_data[sweep_parameter] = parameter_value
        with open(g4_json, 'w') as f:
            json.dump(dict_data, f, indent=4)
        #监测点
        print(f"Updated {sweep_parameter} to {parameter_value} in {g4_json}")
        #

        for i in range(scan_number):
            args.append((parameter_value,i))
        func = partial(run_sweep, kwargs=kwargs, sweep_parameter=sweep_parameter)
        with ProcessPoolExecutor(max_workers=max_processes) as executor:
            #运行监测点
            print(f"Running sweep with {max_processes} parallel processes...")
            #
            futures = [executor.submit(func, arg) for arg in args]

            for future in as_completed(futures):
                try:
                    result = future.result()   # 获取结果，如果有异常会在这里抛出
                    print(f"任务成功: {result}")
                except Exception as e:
                    print(f"任务失败: {e}")    # 打印异常信息，不中断其他任务



def energy_resolution_calculation(kwargs):
    sweep_parameter = kwargs['sweep_parameter']
    sweep_range = kwargs['sweep_range']
    sweep_step = kwargs['sweep_step']
    sweep_number = kwargs['sweep_number']
    folder_path = kwargs['folder_path']
    energy_resolution_list = []
    from . import energy_resolution
    for subfile in os.listdir(folder_path):
        kwargs['subfile_path'] = os.path.join(folder_path, subfile)
        energy_resolution = energy_resolution.main(kwargs)
        energy_resolution_list.append(energy_resolution)
    sweep_list = [sweep_range[0] + i * sweep_step for i in range(sweep_number)]
    return sweep_list, energy_resolution_list



def main(kwargs):
    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    #检索扫描变量
    
   
      
    kwargs['sweep'] = True
    if kwargs['Xray'] != None:
        my_d.sweep = "Xbeam_energy_resolution"

    sweep_mode = my_d.sweep
    sweep_json = os.getenv("RASER_SETTING_PATH")+"/sweep/" + sweep_mode + ".json"
    dict_json = os.getenv("RASER_SETTING_PATH") + "/detector/" + det_name + ".json"
    g4_json = os.getenv("RASER_SETTING_PATH")+"/g4experiment/" + my_d.g4experiment + ".json"
    with open(sweep_json) as f:
        sweep_dict = json.load(f)
    sweep_parameter = sweep_dict['sweep_parameter']
    kwargs['sweep_parameter'] = sweep_parameter
    sweep_range = sweep_dict['sweep_range']
    kwargs['sweep_range'] = sweep_range
    sweep_step = sweep_dict['step']
    kwargs['sweep_step'] = sweep_step
    scan_number = sweep_dict['scan_number']
    kwargs['scan_number'] = scan_number
    range_lenth = sweep_range[1] - sweep_range[0]
    sweep_number = int(range_lenth // sweep_step + 1)
    kwargs['sweep_number'] = sweep_number

    local_time = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    folder_path = output(__file__, det_name, str(sweep_parameter) + "_" + local_time)
    
    kwargs['folder_path'] = folder_path
    kwargs['g4_json'] = g4_json

    #run simulation
    run_simulation(g4_json, kwargs)

    #check_signal(kwargs)

    #data processing
    sweep_list, energy_resolution_list = energy_resolution_calculation(kwargs)
    

    #画图
    import matplotlib.pyplot as plt
    plt.plot(sweep_list, energy_resolution_list)
    plt.xlabel(sweep_parameter)
    plt.ylabel("energy_resolution")
    plt.title(f"Energy Resolution vs {sweep_parameter}")
    plt.savefig(os.path.join(folder_path, f"energy_resolution_vs_{sweep_parameter}.pdf"))
    plt.close()




