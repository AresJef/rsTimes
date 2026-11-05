# 运行四个示范

当前公开采用版本是 **rsTimes 0.2.0b3**，包含Pldt、Delta完整纳秒和普通／free-threaded支持。源码与公开产物以版本、路径和SHA共同识别；旧b1／b2和历史本地环境不冒称本次产物。

`demo/runtime.json`明确选择实际安装环境与发行清单。前三个示范对照冻结的cyTimes 3.1.0，使用兼容的pandas2环境；Pddt示范使用独立pandas3主环境。只有官方比较环境需要cyTimes和Babel，正常使用rsTimes不需要它们。

本机当前选择：

- Delta、Parser、Pydt：`.local/beta-b3-release-20h-20261105/public-oracle-demo`。
- Pddt：`.local/beta-b3-release-20h-20261105/public-main`。
- 清单：`tasks/evidence/beta-b3-release-20h-20261105/sealed-release/release-manifest.json`。

这些环境安装了实际从PyPI下载、与原CI文件逐字节核对的b3 wheel。目录名中的20h是本轮早期证据标识；实际批准总预算是48小时，并未通过改名重置时间。

从项目根目录执行：

```sh
python demo/delta.py
python demo/parser.py
python demo/pydt.py
python demo/pddt.py
```

从其他目录执行时使用脚本绝对路径。直接执行会选择配置的解释器，校验项目／安装版本、实际native位置及SHA256。导入示范模块时只检查，不替换调用者进程。Pddt示范不导入Delta示范或cyTimes。

在另一台机器上，使用目标Python ABI／平台已经验证的同一公开b3文件，并准备对应发行清单。普通CPython3.13示例：

```sh
python3.13 -m venv .local/demo-b3-oracle
.local/demo-b3-oracle/bin/python -m pip install -r requirements-oracle.txt rsTimes==0.2.0b3
python3.13 -m venv .local/demo-b3-main
.local/demo-b3-main/bin/python -m pip install -r requirements-test.txt rsTimes==0.2.0b3
```

Windows解释器位于`Scripts/python.exe`。同步更新runtime.json的environment、environments.pddt及已核验的release_manifest；不要复用其他ABI的native哈希。旧环境和历史清单保留各自身份。

四个示范已经从项目根目录和另一目录各运行一次，共8次；Delta150个对比场景未知差异0。短批次耗时仅供交互观察，不能代替正式216配对／36worker的性能验收。公开Beta使用及升级范围见[发行说明](../docs/releases/v0.2.0b3.md)，未来发布步骤见[统一发布流程](../docs/RELEASING.md)。
