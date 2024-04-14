#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import matplotlib.pyplot as plt
import numpy as np

csv_files = []

def read_csv_file(folder_path):
    for csv_file in os.listdir(folder_path):
        if csv_file.endswith('.csv'):
            csv_files.append(os.path.join(folder_path, csv_file))
    return csv_files

folder_path = 'C:\\Users\\86188\\Desktop\\20230808\\noise_diya_ucsc'
csv_files = read_csv_file(folder_path)

def read_csv(csv_file):
    time, voltage = [], []
    with open(csv_file, 'r') as file:
        lines = file.readlines()
        for line in lines[6:]:
            time.append(float(line.split(',')[3]) * 1e9)
            voltage.append(float(line.split(',')[4]) * 1e3)
    return time, voltage

voltage_list = []

for csv_file in csv_files:
    time, voltage = read_csv(csv_file)
    voltage_list.extend(voltage)  # 将每个csv文件的电压值添加到列表中

# 计算直方图
hist, bins = np.histogram(voltage_list, bins=70)

# 计算均值和标准差
mean = np.mean(voltage_list)
stddev = np.std(voltage_list)

# 绘制直方图
plt.figure(figsize=(10, 6))
plt.hist(voltage_list, bins=50, alpha=1, density=True, label='Voltage Distribution')

# 显示均值和标准差
plt.text(0.7, 0.9, f'Mean: {mean:.2f} mV', transform=plt.gca().transAxes)
plt.text(0.7, 0.85, f'Standard Deviation: {stddev:.2f} mV', transform=plt.gca().transAxes)

plt.xlabel('Voltage/mV')
plt.ylabel('Frequency')
plt.title(' noise voltage distribution')

save_dir = 'C:\\Users\\86188\\Desktop\\20230808\\noise_diya_ucsc'
file_name = 'noise.pdf'
save_file = os.path.join(save_dir,file_name)
plt.savefig(save_file)
plt.show()
