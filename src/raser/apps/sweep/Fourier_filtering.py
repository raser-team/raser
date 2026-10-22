import os
import numpy as np
import csv
import matplotlib.pyplot as plt
from scipy.signal import find_peaks


def filter_sine(spectrum):
    time_length = len(spectrum)
    for spectrum_index in range(len(spectrum)):
        if abs(spectrum[spectrum_index]/time_length) > 0.005:1
            spectrum[spectrum_index] = 0
            spectrum[spectrum_index-1] = 0
            try:
                spectrum[spectrum_index+1] = 0
            except IndexError:
                pass
    return spectrum

def filter_DC(spectrum):
    spectrum[0] = 0
    return spectrum

# def select_file(spectrum, freqs):
#     print("Selecting file based on frequency spectrum...")
#     spectrum[0] = 0
#     freq_data = np.column_stack((freqs, spectrum))
#     peak_value = np.max(np.abs(spectrum))
#     peak_index = np.argmax(np.abs(spectrum))
#     peak_frequency = freqs[np.argmax(np.abs(spectrum))]
#     start = max(0, peak_index - 5)
#     end = min(len(spectrum), peak_index + 6)
#     mean_val = (np.sum(np.abs(spectrum[start:end])) - np.abs(spectrum[peak_index])) / (end - start - 1)
#     print(f'Peak frequency: {peak_frequency} Hz, Peak value: {peak_value}, Mean value: {mean_val}')
#     if peak_value > 5 * mean_val:
#         print(f"error data")
#         return True
#     else:
#         print(f"normal data")
#         return False


import numpy as np
from scipy.signal import find_peaks


def find_peaks_in_spectrum(spectrum, freqs, sharpness_threshold=4, peak_prominence=0.1):
    spectrum = np.abs(spectrum.copy())
    spectrum[0] = 0
    
    # 2. 寻找所有局部峰值
    max_val = np.max(spectrum)
    if max_val == 0:
        return 'pure_noise', []
    prominence = max_val * peak_prominence
    peaks, props = find_peaks(spectrum, prominence=prominence, height=0)
    
    if len(peaks) == 0:
        return 'pure_noise', []  # 无显著峰，按噪声处理
    
    # 3. 对每个峰值计算尖锐度
    sharp_peaks = []   # 尖锐峰（纯噪声）
    broad_peaks = []   # 宽峰（可能信号）
    noise_freqs = []
    noise_idx = []
    for idx in peaks:
        print(f"Analyzing peak at frequency {freqs[idx]} Hz with magnitude {spectrum[idx]}")
        start = max(0, idx - 5)
        end = min(len(spectrum), idx + 6)
        # 邻域均值（排除自身）
        neighbor_sum = np.sum(spectrum[start:end]) - spectrum[idx]
        neighbor_cnt = end - start - 1
        if neighbor_cnt == 0:
            continue
        mean_neighbor = neighbor_sum / neighbor_cnt
        if mean_neighbor == 0:
            sharpness = float('inf')
        else:
            sharpness = spectrum[idx] / mean_neighbor
        
        # 判断尖锐度
        if sharpness > sharpness_threshold:
            sharp_peaks.append(idx)
            noise_freqs.append(freqs[idx])
            noise_idx.append(idx)
        elif spectrum[idx] < 0.4 * max_val:
            pass
        else:
            broad_peaks.append(idx)
    return sharp_peaks, broad_peaks, noise_freqs,  peaks, noise_idx

def analyze_spectrum(spectrum, freqs):
    """
    分析频谱，返回文件类型和可能需要滤波的标记
    :param spectrum: 频谱幅值（1D数组）
    :param freqs: 频率轴
    :param sharpness_threshold: 判定为尖锐峰的阈值（峰高/邻域均值）
    :param peak_prominence: 峰值检测的突出度阈值（相对最大幅值比例）
    :return: (status, freq_list) 
             status: 'pure_noise' | 'contains_signal' | 'signal_with_noise'
             freq_list: 尖锐噪声的频率列表（用于后续滤波）
    """
    sharp_peaks, broad_peaks, noise_freqs, peaks, noise_idx = find_peaks_in_spectrum(spectrum, freqs)
    if len(sharp_peaks) > 0 and len(broad_peaks) == 0:
        # 只有尖锐峰，无宽峰  纯噪声文件
        return 'pure_noise', noise_freqs
    elif len(sharp_peaks) == 0 and len(broad_peaks) > 0:
        # 只有宽峰，无尖锐噪声  正常信号文件
        return 'contains_signal', [], []
    else:
        # 两者都有  信号和噪声共存，需要滤波
        return 'signal_with_noise', noise_freqs, noise_idx


# 你的原函数可以改为调用这个分析器，并做相应处理
def select_file(spectrum, freqs):
    status, noise_freqs,*_ = analyze_spectrum(spectrum, freqs)
    if status == 'pure_noise':
        print("纯噪声文件，丢弃")
        return 1   # 丢弃
    elif status == 'contains_signal':
        print("正常信号文件，保留")
        return 2
    else:  # signal_with_noise
        print(f"信号含噪声（频率 {noise_freqs} Hz），建议滤波后保留")
        # 这里你可以返回 False 并标记需要滤波，或者直接执行滤波再返回
        # 假设我们仍保留，但记录噪声频率以便后续处理
        return 3  # 保留，但需后续滤波


def filter_spectrum(spectrum, freqs):
    status, noise_freqs, noise_idx = analyze_spectrum(spectrum, freqs)
    if status == 'pure_noise':
        return np.zeros_like(spectrum)  # 全部置零
    elif status == 'contains_signal':
        return spectrum  # 保留原始信号
    else:  # signal_with_noise
        # 对于每个噪声频率，找到对应的索引并置零
        for idx in noise_idx:
            spectrum[idx] = 0
            # 可选：也可以考虑邻近频率一起置零，具体取决于噪声宽度
            if idx > 0:
                spectrum[idx - 1] = 0
            if idx < len(spectrum) - 1:
                spectrum[idx + 1] = 0
        return spectrum

def sample_smoothing(signal, window_size=5):
    """
    平滑信号
    :param signal: 信号（1D数组）
    :param window_size: 平滑窗口大小
    :return: 平滑后的信号
    """
    if window_size < 1:
        raise ValueError("window_size must be at least 1")
    if window_size % 2 == 0:
        window_size += 1  # 确保窗口大小为奇数
    half_window = window_size // 2
    smoothed_signal = np.copy(signal)
    for i in range(len(signal)):
        start = max(0, i - half_window)
        end = min(len(signal), i + half_window + 1)
        smoothed_signal[i] = np.mean(signal[start:end])
    return smoothed_signal

def draw_spectrum(spectrum,filtered_spectrum, freqs):
    time_length = len(freqs)
    plt.figure(figsize=(12, 6))
    plt.subplot(2, 1, 1)

    plt.plot(freqs, np.abs(spectrum/time_length))
    plt.title('Frequency Spectrum')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.grid()

    
    plt.subplot(2, 1, 2)
    plt.plot(freqs, abs(filtered_spectrum/time_length))
    plt.title('filtered Frequency Spectrum')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.grid()


    plt.show()

def draw_filtered_signal(time, signal, signal2):
    

    plt.figure(figsize=(12, 8))
    plt.subplot(2, 1, 1)
    plt.plot(time, signal)
    plt.title('Original Signal in Time Domain')
    plt.xlabel('Time')
    plt.ylabel('Amplitude')
    plt.grid()

    plt.subplot(2, 1, 2)
    plt.plot(time, signal2)
    plt.title('Filtered Signal in Time Domain')
    plt.xlabel('Time')
    plt.ylabel('Amplitude')
    plt.grid()


    plt.show()
    
import os
import numpy as np
import shutil
import glob

def is_valid_format(data):
    """
    验证数据格式是否符合要求：
    - 至少有2列（时间、信号）
    - 不存在 NaN 或 Inf
    - 时间列严格递增（可选，加强验证）
    """
    if data.ndim != 2:
        return False
    if data.shape[1] < 2:
        return False
    # 检查是否有缺失值或无穷值
    if not np.isfinite(data).all():
        return False
    # 检查时间列是否严格递增（如果是时间序列，通常要求）
    time_col = data[:, 0]
    if np.any(np.diff(time_col) <= 0):
        # 若允许等间隔或非严格递增，可改为 < 0，这里使用 <= 0 要求严格递增
        return False
    return True


def fourier_filtering(data, use_smoothing=False, smoothing_window=5):
    """
    对输入数据进行傅里叶变换、滤波和逆变换
    :param data: 输入数据，二维数组，第一列为时间，第二列为信号
    :param use_smoothing: 是否对滤波后的信号进行平滑处理
    :param smoothing_window: 平滑窗口大小
    :return: 滤波后的信号（时间域）
    """
    time = data[:, 0]
    signal = data[:, 1]
    time_length = len(time)

    # 傅里叶变换
    freqs = np.fft.fftfreq(time_length, d=(time[1] - time[0]))
    spectrum = np.fft.fft(signal)

    # 滤波处理
    filtered_spectrum = filter_spectrum(spectrum, freqs)

    # 逆傅里叶变换
    filtered_signal = np.fft.ifft(filtered_spectrum).real

    # 可选平滑处理
    if use_smoothing:
        filtered_signal = sample_smoothing(filtered_signal, window_size=smoothing_window)

    return filtered_signal


def sweep_file(folder_path):
    # 创建三个目标文件夹（若不存在则创建）
    subdirs = {
        1: 'noise',
        2: 'signal',
        3: 'mix'
    }
    for sub in subdirs.values():
        target_path = os.path.join(folder_path, sub)
        os.makedirs(target_path, exist_ok=True)

    # 获取文件夹下所有 .csv 文件（非递归）
    csv_files = glob.glob(os.path.join(folder_path, '*.csv'))
    if not csv_files:
        print(f"在 {folder_path} 中未找到任何 .csv 文件")
        return

    # 分类结果列表（仅记录文件名）
    noise_list = []
    signal_list = []
    mix_list = []
    error_files = []

    for file_path in csv_files:
        # 仅提取文件名用于记录
        filename = os.path.basename(file_path)
        try:
            data = np.loadtxt(file_path, delimiter=',')
        except Exception as e:
            print(f"读取文件 {filename} 失败: {e}")
            continue

        if not is_valid_format(data):
            print(f"⚠️ 文件 {filename} 不符合格式要求（需至少两列，无缺失/无穷，时间递增），已跳过")
            error_files.append(filename)
            continue

        time = data[:, 0]
        signal = data[:, 1]
        time_length = len(time)

        freqs = np.fft.fftfreq(time_length, d=(time[1] - time[0]))
        spectrum = np.fft.fft(signal)

        # 取正频率部分
        positive_freqs = freqs[:time_length // 2]
        positive_spectrum = np.abs(spectrum[:time_length // 2] / time_length)

        # 调用外部分类函数，返回类别标识（1:噪声, 2:信号, 3:混合）
        category = select_file(positive_spectrum, positive_freqs)

        # 根据类别移动文件到对应子文件夹
        if category == 1:
            noise_list.append(filename)
            dest_dir = os.path.join(folder_path, 'noise')
        elif category == 2:
            signal_list.append(filename)
            dest_dir = os.path.join(folder_path, 'signal')
        else:
            mix_list.append(filename)
            dest_dir = os.path.join(folder_path, 'mix')

        shutil.copy(file_path, os.path.join(dest_dir, filename))
    

    # 打印分类结果
    print(f"Noise files: {noise_list}")
    print(f"Signal files: {signal_list}")
    print(f"Mix files: {mix_list}")
    print(f"noise length: {len(noise_list)}")
    print(f"signal length: {len(signal_list)}")
    print(f"mix length: {len(mix_list)}")



def check_file(file_path):
    file_name = file_path
    data = np.loadtxt(file_name, delimiter=',')
    time = data[:, 0]
    signal = data[:, 1]
        # print(time)
        # print(signal)
    time_length = len(time)
    freq_length = time_length
    
    freqs = np.fft.fftfreq(freq_length, d=(time[1] - time[0]))
    spectrum = np.fft.fft(signal) 

    spectrum1 = spectrum.copy()

    positive_freqs = freqs[:len(freqs)//2]
    positive_spectrum = np.abs(spectrum[:len(spectrum)//2]/time_length)
    select_file(positive_spectrum, positive_freqs)
    filtered_spectrum = filter_spectrum(spectrum, freqs)
    filtered_signal = np.fft.ifft(filtered_spectrum).real
    smoothed_signal = sample_smoothing(filtered_signal, window_size=31)
    smoothed_spectrum = np.fft.fft(smoothed_signal)
    draw_filtered_signal(time, filtered_signal, smoothed_signal)
    draw_spectrum(filtered_spectrum, smoothed_spectrum, freqs)


def mix_process(folder_path):
    mix_folder = os.path.join(folder_path, 'mix')
    signal_folder = os.path.join(folder_path, 'signal')
    for file_name in os.listdir(mix_folder):
        file_path = os.path.join(mix_folder, file_name)
        if os.path.isfile(file_path) and file_name.endswith('.csv'):
            data = np.loadtxt(file_path, delimiter=',')
            processed_signal = fourier_filtering(data)
            file_path_signal = os.path.join(signal_folder, file_name)
            np.savetxt(file_path_signal, np.column_stack((data[:, 0], processed_signal)), delimiter=',')
            

# sweep_file(r"E:\科创\data\meas\7.18sic-pin-13.5mm\7.18sic-pin-13.5mm\10V")
# check_file(r"E:\科创\data\meas\7.18sic-pin-18.5mm\7.18sic-pin-18.5mm\400V\wf00004.csv")

            

mix_process(/afs/ihep.ac.cn/users/s/shaochangpu/raser1/raser-main/src/raser/components/data/meas/8.5/10v)