# 接续一次光学计算

[English](README.md)

`diffraction.py` 在 61 个探测位置对均匀狭缝的复振幅作积分，将强度与夫琅禾费衍射解析结果对照。
只需要 Python 标准库。这里采用标量、近轴、远场模型，展示如何接续具有独立已完成点的长循环。

安装本仓库后运行：

```sh
python examples/continuation/run.py --home /path/to/example-environment
```

程序保存七个位置后主动停止。运行脚本接续同一次运行；程序读取第一次尝试的文件，只计算剩余
54 个位置。各次尝试分别保留自己的输出。第二次尝试写出 `pattern.csv`，并报告与解析结果的最大差值。

用于实际求解器时，保存已经完成的位置，以及接续所需的模型或数组文件。先关闭这些文件，再保存进度。
求解器会话重新打开。详见[程序接续](../../skills/optical-computation/references/continuation.md)。
