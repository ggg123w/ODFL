#!/bin/bash

# 按版本排序（数字顺序）
files=$(find benchmark1/gccbugs -type f -name "fail.c" | sort -V)

# 使用cloc但后处理排序
cloc $files --by-file --quiet --csv > temp_cloc.csv

# 按照原始文件顺序重新排列
> count_failLine.txt
for file in $files; do
    grep "$file" temp_cloc.csv >> count_failLine.txt
done
rm temp_cloc.csv

echo "完成！只包含代码行数的结果保存在 count_failLine.txt"
