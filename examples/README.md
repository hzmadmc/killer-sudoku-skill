# 示例题说明

这道题是真实使用中跑过的题目（无 given 数字，纯笼子题）。

## 文件

- `killer4.json`：题目。格式为 `{"givens": [[9x9]], "cages": [{"sum": n, "cells": [[r,c],...]}]}`，0 基坐标。27 个笼子覆盖全部 81 格，总和 405。
- `killer4_steps.txt`：`human_solve.py` 跑出的完整编号步骤单，共 139 步。已用 `replay_check.py` 验真：逐步回放与唯一解一致，**0 错误**。末尾附完整解盘。

## 复现

```bash
python scripts/human_solve.py examples/killer4.json
python scripts/replay_check.py examples/killer4.json examples/killer4_steps.txt
# 预期输出：重放完毕：139 步全部与唯一解一致，0 错误。
```

需要 45 法则扫描报告和盘面高亮图的话：

```bash
python scripts/killer45_scan.py examples/killer4.json
# 生成 killer4_45map.html，浏览器打开可交互
```

## 解盘（验真通过）

```
3 4 2 9 7 8 1 5 6
1 7 6 3 2 5 4 9 8
9 8 5 6 4 1 3 2 7
2 3 8 7 6 9 5 1 4
5 1 7 4 8 3 9 6 2
6 9 4 5 1 2 8 7 3
8 5 1 2 3 6 7 4 9
7 6 9 8 5 4 2 3 1
4 2 3 1 9 7 6 8 5
```
