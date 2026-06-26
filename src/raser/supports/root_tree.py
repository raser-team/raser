'''
Description:  root_tree.py
@Date       : 2023
@Author     : Ye He
@version    : 1.0
'''

import csv
from array import array

import ROOT

def root_tree_to_csv(csv_file_name, root_file_name, tree_name):
    # 打开 ROOT 文件
    root_file = ROOT.TFile(root_file_name, "READ")
    # 获取 ROOT 文件中的 TTree
    tree = root_file.Get(tree_name)
    if tree:
        print(tree)
        print(tree.GetListOfBranches())
    # 打开 CSV 文件，使用 'w' 模式表示写入
    with open(csv_file_name, mode='w', newline='') as file:
        writer = csv.writer(file)  # 创建 CSV writer 对象
        # 写入 CSV 文件的表头（字段名）
        header = [branch.GetName() for branch in tree.GetListOfBranches()]
        writer.writerow(header)
        # 遍历 TTree 中的数据，将数据写入 CSV 文件
        for event in tree:
            data = [event.GetLeaf(branch.GetName()).GetValue() for branch in tree.GetListOfBranches()]
            writer.writerow(data)