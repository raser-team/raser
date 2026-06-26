import psutil

'''
Description:  memory_decorator.py
@Date       : 2025
@Author     : Chenxi Fu
@version    : 1.0
'''

def memory_decorator(func):
    def wrapper(*args, **kwargs):
        # 获取当前进程
        process = psutil.Process()
        
        # 获取初始内存使用情况
        mem_info_before = process.memory_info()
        rss_before = mem_info_before.rss / (1024 ** 2)  # 常驻集大小（MB）
        vms_before = mem_info_before.vms / (1024 ** 2)  # 虚拟内存大小（MB）
        
        print(f"Memory usage before calling {func.__name__}: RSS = {rss_before:.2f} MB, VMS = {vms_before:.2f} MB")

        # 调用被装饰的函数
        result = func(*args, **kwargs)

        # 获取结束时的内存使用情况
        mem_info_after = process.memory_info()
        rss_after = mem_info_after.rss / (1024 ** 2)  # 常驻集大小（MB）
        vms_after = mem_info_after.vms / (1024 ** 2)  # 虚拟内存大小（MB）

        print(f"Memory usage after calling {func.__name__}: RSS = {rss_after:.2f} MB, VMS = {vms_after:.2f} MB")
        print(f"Memory increase: RSS = {rss_after - rss_before:.2f} MB, VMS = {vms_after - vms_before:.2f} MB")

        return result

    return wrapper
