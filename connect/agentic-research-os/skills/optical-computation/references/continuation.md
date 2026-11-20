# Continue inside a program / 在程序内部接续计算

`resume_run` keeps successful workflow steps and starts a new attempt for unfinished
ones. A Python program can also continue inside a step by saving its own position:

```python
import json

state = CHECKPOINT.load({'next': 0, 'values': []})
files = dict(CHECKPOINT.files)
for i in range(state['next'], INPUTS['points']):
    value = solve(i)
    file = OUTPUT_DIR / f'point-{i}.json'
    file.write_text(json.dumps(value))
    files[str(i)] = file
    state['values'].append(value['summary'])
    state['next'] = i + 1
    CHECKPOINT.save(state, files=files)
RESULT = {'values': state['values']}
```

`CHECKPOINT` is provided by the worker. `load(default)` returns JSON state from the
latest attempt that saved it. `files` maps saved names to `Path` objects; files may
still live in an earlier attempt, so a large model is not copied just to resume.
`restored_from` names the snapshot read by `load`, or is `None`. `save` writes an
atomic JSON snapshot after checking that every named file or directory exists
inside this calculation's current or prior attempts. Relative paths start at
`OUTPUT_DIR`. It returns a compact path, save time, file count and kind.

Write and close artifacts before saving. Treat referenced files as immutable;
write a new file for a changed model. Save only the JSON position and state needed
by the algorithm; arrays and native model files belong in `files`. A new run has
its own progress. Within a resumed step, changed source, inputs or environment
cannot silently consume old state: loading it reports the difference. An invalid
or missing saved artifact also reports an error instead of replaying older work.
Content changes to files named by inputs and changes inside external software are
the research program's responsibility; keep those inputs fixed or start a new run.

The same Python code can wrap native software through its session, `APP` or `RUN`.
Open the session, load its saved model if the solver supports that, and continue
from the saved iteration. Live SDK objects and device state are not serialized.
Programs that do not call `CHECKPOINT` retain their existing behavior.

`run_status` includes an optional `progress` list on a step. It gives the run-relative
snapshot path and a small summary, never the whole state. Existing result-file
read/download tools retrieve it and the artifacts. Prior attempt outputs remain
available. The [diffraction example](../../../examples/continuation/) runs a complete
interruption and continuation using the standard library.

## Optimization

Built-in differential evolution and Nelder–Mead save each completed evaluation,
including failures, and the best result and model files. After `resume_run`, they
reconstruct the seeded search from these recorded outcomes and continue only the
unevaluated points. The original evaluation budget, random sequence, integer and
logarithmic bounds, failure scores and final polish are preserved. The result's
`reused_evaluations` states how many completed evaluations were reused.

The solver session opens afresh. An evaluation interrupted before its outcome
was saved runs again; a Python objective can use `CHECKPOINT`
inside that evaluation to save its own progress. Keep objective inputs and external
data fixed while continuing. Finished evaluations are not measured again, including
noisy measurements; submit a new calculation when fresh observations are intended.

## Grouped sweeps

A sweep may compute several points in one worker. When that worker is interrupted,
`resume_run` reuses its finished successful points and computes failed or unfinished
points again. The points journal retains the old outcomes across repeated
interruptions. Large result files stay in the attempt that produced them.
`sweep_results` includes an `output` path on each successful row; append the result's
relative filename and use the ordinary file tools. The group result reports
`reused_points`. A completed group with some failed points retains the existing
behavior: inspect those rows and submit the selected failed points again.

## 中文

`resume_run` 保留工作流中已成功的步骤，为未完成的步骤开始新的尝试。Python 程序还可以保存自己的
计算位置，从步骤内部接续：

接口与上方 Python 示例相同。

运行器提供 `CHECKPOINT`。`load(default)` 返回最近一次保存的 JSON 状态。`files` 将保存的名称映射为
`Path` 对象；文件可以仍在之前的尝试中，大模型不必仅为接续而复制。`restored_from` 是 `load` 读到的
快照路径，没有读取过则为 `None`。`save` 确认每个文件或目录都存在于本次计算的当前或先前尝试后，
原子写入 JSON 快照。相对路径从 `OUTPUT_DIR` 开始。返回值只包含路径、保存时间、文件数量和类别。

先写完并关闭产物，再保存进度。被引用的文件保持不变，模型发生变化时另写文件。状态只保存算法
需要的 JSON 位置与信息，数组和求解器模型通过 `files` 引用。新运行拥有独立进度；接续同一步骤时，
源码、输入或环境变化会在加载时明确报错。快照损坏或产物缺失也会报错，不会悄悄回到更早的位置。
输入引用的文件内容、外部软件内部发生的变化由研究程序处理；接续时保持它们不变，或提交新运行。

Python 代码可以通过会话、`APP` 或 `RUN` 操作原生软件。重新打开会话，按求解器的能力载入已保存模型，
从保存的迭代位置接续。不会序列化活动 SDK 对象或仪器物理状态。不使用 `CHECKPOINT` 的程序保留原有行为。

`run_status` 的步骤可以带有 `progress` 列表，给出相对运行目录的快照路径与简短概况，不返回全部状态。
已有的结果文件读取和下载工具可读取快照与产物。先前尝试的输出仍然保留。
[衍射示例](../../../examples/continuation/README.zh-CN.md) 使用标准库运行了一次完整的中断与接续。

## 优化计算

内置差分进化和 Nelder–Mead 每完成一次计算就保存结果，包括失败情况，以及当前最优结果与模型文件。
调用 `resume_run` 后，算法用已记录的结果重建相同种子的搜索过程，只计算尚未完成的点。原来的计算
次数预算、随机序列、整数与对数边界、失败评分和最后的局部优化保持一致。结果中的 `reused_evaluations`
给出复用了多少次已完成计算。

接续的是搜索过程，求解器会话会重新打开。结果保存前中断的那一次计算会重新运行；Python 目标程序
可以在该次计算内部使用 `CHECKPOINT` 保存进度。接续期间保持目标程序的输入和外部数据不变。已经完成的
计算不会重新测量，含噪声的测量也一样；需要新观测时提交新计算。

## 分组扫描

一次扫描可在同一进程内计算多个点。进程中断后，`resume_run` 复用已成功的点，只重新计算失败或未完成的点。
多次中断仍保留先前的结果。大型结果文件留在生成它的那次尝试中，不会为了接续而复制。
`sweep_results` 的成功行带有 `output` 路径，拼接结果中的相对文件名后，可用已有文件工具读取。
分组结果中的 `reused_points` 表示复用了多少点。已经完成但含有部分失败点的分组保留现有行为：
读取失败行，再提交选中的失败点。
