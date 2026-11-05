# 运行四个示范

这份源码的本地采用版本是 R18 检查器优化 final01（保留完整日期导出检查）；采用记录见根
`AGENTS.md` 和本轮完成审计。公开 PyPI `0.2.0b2` 是较早的独立产物，不能仅凭相同
版本号，把它当成本地的 Pldt／Delta 纳秒／NoGIL 实现。

`demo/runtime.json` 明确选择实际安装环境及 wheel／native 校验清单。
前三个示范对照冻结的 cyTimes 3.1.0，使用兼容的 pandas 2 环境；Pddt
示范对照 pandas 3，使用独立主环境。只有官方比较环境需要 cyTimes 和
Babel；正常使用 rsTimes 不需要它们。

本轮环境为：

- Delta、Parser、Pydt：`.local/r18-numpy-check-optimization-20261105/final01-oracle-demo`。
- Pddt：`.local/r18-numpy-check-optimization-20261105/final01-main`。
- 实际文件清单：`tasks/evidence/r18-numpy-check-optimization-20261105/S04/demo-delivery-manifest.json`。

从项目根目录执行：

```sh
python demo/delta.py
python demo/parser.py
python demo/pydt.py
python demo/pddt.py
```

从其他目录执行时使用脚本的绝对路径。直接执行会进入明确配置的解释器，
检查项目／安装版本、实际 native 位置和 SHA256。它不会临时编译、静默退回
旧包或修改调用者安装。导入示范模块时只检查，不替换调用方进程。Pddt
示范不会导入 Delta 示范或 cyTimes。

若在另一台机器准备环境，使用该 Python ABI／平台上已经验证的当前 wheel；
不要改用公开旧 b2，也不要复用另一个 ABI 的 native SHA。下面的 wheel 路径
需要替换为实际已验证文件：

```sh
python3.13 -m venv .local/r18-numpy-check-optimization-20261105/final01-oracle-demo
.local/r18-numpy-check-optimization-20261105/final01-oracle-demo/bin/python -m pip install -r requirements-oracle.txt /absolute/path/to/verified-current-wheel.whl
python3.13 -m venv .local/r18-numpy-check-optimization-20261105/final01-main
.local/r18-numpy-check-optimization-20261105/final01-main/bin/python -m pip install -r requirements-test.txt /absolute/path/to/verified-current-wheel.whl
```

Windows 的解释器位于环境的 `Scripts/python.exe`，相应替换 `bin/python`。
自选环境目录时同步修改 `runtime.json` 的 `environment`、`environments.pddt`
和经实际文件核验的 `release_manifest`；旧环境和历史清单可以保留，但不能
把旧成绩或旧 native 身份转记给新安装。

示范中的短批次耗时只供交互观察，不属于正式性能验收。行为有已批准差异的
场景分别展示结果和独立预期，不计算不等价调用之间的提速倍率。
