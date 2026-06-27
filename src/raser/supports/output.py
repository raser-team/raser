'''
Description:  output.py
@Date       : 2023
@Author     : Chenxi Fu
@version    : 1.0
'''

import os

from raser.supports.paths import module_work_path

def output(current_file_path, *label):
    """
    Usage: output_file_path(__file__, *label)

    Send generated files into the current project directory, grouped by module.

    Notice: Do not iterate this function. One call per use.
    """
    output_file_path = os.path.abspath(module_work_path(current_file_path, *label))
    create_path(output_file_path)
    # 星号将列表转化为递归，头一个os.sep使其输出绝对路径；外圈abspath考虑潜在的windows用户
    return output_file_path

def create_path(path):
    """If the path does not exit, create the path"""
    if not os.access(path, os.F_OK):
        os.makedirs(path, exist_ok=True) 

def delete_file(path):
    """If the file exists, delete the file"""
    if os.access(path, os.F_OK):
        os.remove(path)