# 运行四个示范

示范不属于运行库依赖。Delta、Parser、Pydt 比较冻结的 cyTimes3.1.0，使用与它兼容的 pandas2 环境；Pddt 比较 pandas3，使用另一环境。不能把 cyTimes 的 pandas<3 依赖强装进 pandas3。

从项目根目录准备下列环境。这里使用 CPython3.13，以取得冻结官方版本的现成 wheel；不限制 rsTimes 本身已经验证的 CPython3.12—3.15 支持。

```sh
python3.13 -m venv .local/rstimes-beta-release-20261028/oracle-env
.local/rstimes-beta-release-20261028/oracle-env/bin/python -m pip install -r requirements-oracle.txt "rsTimes==0.2.0b1"
python3.13 -m venv .local/rstimes-beta-release-20261028/published-pd3
.local/rstimes-beta-release-20261028/published-pd3/bin/python -m pip install -r requirements-test.txt "rsTimes==0.2.0b1"
gh release download v0.2.0b1 --repo AresJef/rsTimes --pattern release-manifest.json --dir .local/rstimes-beta-release-20261028/public-release
```

Windows 的解释器位于环境的 `Scripts/python.exe`，相应替换上面的 `bin/python`。也可以自行选择目录，再修改 `demo/runtime.json` 的默认 `environment` 与 `environments.pddt`；它们必须分别指向这两套环境。`release_manifest` 指向本次实际 GitHub Release 的清单。

随后执行：

```sh
python demo/delta.py
python demo/parser.py
python demo/pydt.py
python demo/pddt.py
```

从其他目录调用时使用脚本的绝对路径。直接执行会选择明确指定的环境并检查版本、真实 native 路径与发行清单的 SHA256；不会临时编译、静默退回旧包或修改调用方安装。导入示范模块时只做检查，不替换调用方进程。Pddt 示范不会导入 Delta 示范或 cyTimes。

显示的短批次耗时仅用于交互观察，不属于正式性能验收。正常安装和使用 rsTimes 不需要这些示范环境、cyTimes 或 Babel。
