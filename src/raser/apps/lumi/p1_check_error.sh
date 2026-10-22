#!/bin/bash

repo_root=$(git rev-parse --show-toplevel)
target_dir="$repo_root/work/lumi/jobs" 

# 遍历目标目录及子目录中的所有 .err 文件
find "$target_dir" -type f -name "*.err.*" | while read -r file; do
    # 检查文件中是否包含 "Error" 或 "error"（忽略大小写）
    if grep -iqE 'Error|error' "$file"; then
        echo "发现错误文件: $file"
    fi
done
