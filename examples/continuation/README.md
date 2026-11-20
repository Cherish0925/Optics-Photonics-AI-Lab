# Continue an optical calculation

[中文](README.zh-CN.md)

`diffraction.py` integrates the complex amplitude of a uniform slit at 61 detector
positions and compares its intensity with the analytic Fraunhofer pattern. It
uses only Python's standard library. This scalar, paraxial far-field model is an
example of a long loop with independent completed points.

From an installed checkout:

```sh
python examples/continuation/run.py --home /path/to/example-environment
```

The program deliberately stops after saving seven positions. The runner resumes
the same run; the program reads those files from the first attempt and computes
the remaining 54 positions. Each attempt keeps its own output. The second attempt
writes `pattern.csv` and reports the largest difference from the analytic result.

For a real solver, save the completed position and the model or array files needed
to continue. The checkpoint commits after those files are closed. The solver
session itself is opened afresh. See [program continuation](../../skills/optical-computation/references/continuation.md).
