# 运行四个示范

当前源码展示 PLDT／Delta 纳秒开发候选版。公开 `0.2.0b2` 是冻结对照，
不包含本轮新增接口，不能用公开 b2 wheel 运行这些新示范。当前
`demo/runtime.json` 明确选择本轮本地环境与实际候选 wheel 的校验清单；
这不代表新版本已经发行或通过最终性能验收。

示范不属于运行库依赖。Delta、Parser、Pydt 比较冻结的 cyTimes3.1.0，使用与它兼容的 pandas2 环境；Pddt 比较 pandas3，使用另一环境。不能把 cyTimes 的 pandas<3 依赖强装进 pandas3。

本轮已准备 `.local/pldt-72h-20261030/demo-oracle` 和
`.local/pldt-72h-20261030/dev`。前三个示范使用前者，Pddt／Pldt 示范使用
后者。两者安装同一候选 wheel；只有官方比较环境包含 cyTimes 和 Babel。

需要在另一机器重建环境时，从项目根目录准备下列环境。这里使用
CPython3.13，以取得冻结官方版本的现成 wheel。将 `CANDIDATE_WHEEL`
替换成当前已验证候选 wheel 的实际路径，不能改为公开 b2：

```sh
python3.13 -m venv .local/pldt-72h-20261030/demo-oracle
.local/pldt-72h-20261030/demo-oracle/bin/python -m pip install -r requirements-oracle.txt polars==2.0.0 CANDIDATE_WHEEL
python3.13 -m venv .local/pldt-72h-20261030/dev
.local/pldt-72h-20261030/dev/bin/python -m pip install -r requirements-test.txt polars==2.0.0 CANDIDATE_WHEEL
```

Windows 的解释器位于环境的 `Scripts/python.exe`，相应替换上面的
`bin/python`。也可以自行选择目录，再修改 `demo/runtime.json` 的默认
`environment` 与 `environments.pddt`。`release_manifest` 是已安装候选
wheel 的实际校验清单；当前指向 W25 的分发包验证结果，不能使用旧发行
清单冒充新候选。最终采用后再同步到实际采用清单。

随后执行：

```sh
python demo/delta.py
python demo/parser.py
python demo/pydt.py
python demo/pddt.py
```

从其他目录调用时使用脚本的绝对路径。直接执行会选择明确指定的环境并检查版本、真实 native 路径与发行清单的 SHA256；不会临时编译、静默退回旧包或修改调用方安装。导入示范模块时只做检查，不替换调用方进程。Pddt 示范不会导入 Delta 示范或 cyTimes。

显示的短批次耗时仅用于交互观察，不属于正式性能验收。正常安装和使用 rsTimes 不需要这些示范环境、cyTimes 或 Babel。
