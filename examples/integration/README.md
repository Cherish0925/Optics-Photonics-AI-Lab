# An installable integration / 可独立安装的扩展

Install this example into the Python environment that runs the connector:

在运行连接器的 Python 环境中安装本示例：

```sh
python -m pip install ./examples/integration
optics-photonics integrations --refresh
```

The package adds `gaussian-example`, its `propagate` program and two short
guides. It imports no scientific package and changes no built-in entry.
Bind it to a Python interpreter and submit through the ordinary interface:

扩展增加 `gaussian-example`、`propagate` 程序和中英文指南，不修改内置条目。
将它绑定到 Python 后，使用现有接口提交计算：

```python
import sys
from optics_photonics import environments, integrations, jobs

integrations.listing(refresh=True)
environments.bind('gaussian-example', python=sys.executable)
submitted = jobs.submit([{
    'id': 'beam', 'tool': 'gaussian-example', 'action': 'propagate',
    'inputs': {'distance_mm': 100}
}])
print(jobs.outcome(submitted['run_id'], wait=25))
```

The example is a paraxial analytic model, with no aperture, aberration or
interface. Its description states the radius convention and physical limits.
See the [integration reference](../../skills/optical-computation/references/integrations.md)
to publish an integration of your own, or add a distinct program to an existing
solver. Remove it with `python -m pip uninstall optics-gaussian-example`, then
refresh or restart the connector. Existing result files and environment
bindings are retained.

本示例是近轴解析模型，不包含孔径、像差或界面；说明中写明半径约定与适用范围。
[扩展参考](../../skills/optical-computation/references/integrations.md)介绍如何发布自己的扩展，
或为现有求解器添加新程序。删除时运行
`python -m pip uninstall optics-gaussian-example`，随后刷新或重启连接器。
已有结果文件与环境绑定保留。
