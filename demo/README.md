# 运行四个示范

当前公开发行是 **rsTimes 0.2.0b3**。本机采用STR与全库审查修复版 **final04**，
包版本字段同为 `0.2.0b3`。本地和公开产物分别按安装路径和 native SHA 核对。

`demo/runtime.json`选择本轮实际安装的release wheel，并通过清单验证native。
前三个示范仍对照冻结的cyTimes 3.1.0，使用独立的兼容环境；Pddt示范使用主环境。
只有官方比较环境需要cyTimes和Babel，正常使用rsTimes不需要它们。

本机当前选择

- Delta、Parser、Pydt 使用 `.local/review-triage-fix-30h-20261111/final04/env-oracle-demo`。
- Pddt 使用 `.local/review-triage-fix-30h-20261111/final04/env-313`。
- 六个本机 ABI 的实际文件和指纹见[分发清单](../tasks/evidence/review-triage-fix-30h-20261111/Q06/final04-validation/distributions.json)。

Parser 示范覆盖 `parse_to_integer`／`parse_to_float`，包括 128 位整数、三位分组、
浮点小数优先和错误分组。日期文本子类的规则与数值文本语法分别记录。
[日期解析](../docs/Parser对象解析使用说明.md) · [数值文本解析](../docs/NumericParsing.md)

从项目根目录执行以下命令。

```sh
python demo/delta.py
python demo/parser.py
python demo/pydt.py
python demo/pddt.py
```

从其他目录执行时使用脚本绝对路径。直接执行会切换到配置的解释器，再检查
项目／安装版本、实际native位置及SHA256。导入示范模块时只验证，不替换调用者
进程。Pddt示范不导入Delta示范或cyTimes。

其他机器应使用适合该 ABI 和平台的实际 wheel、安装环境及对应 native 指纹。
Windows 解释器路径为 `Scripts/python.exe`。本轮验收的实际 wheel 覆盖 macOS ARM64。

本机采用后从项目根目录和另一目录各执行了四个示范，八次均通过。示范中的短批次计时用于交互观察。
正式340项必要比较为325严格PASS、12稳定性INC、3稳定速度FAIL；后15项只按本final04的具体采用条件保留，原严格成绩不改。
完整矩阵、全部快慢项及取舍见[修复验收报告](../docs/STR与全库审查修复验收-20261111.md)和[直接运行记录](../tasks/evidence/review-triage-fix-30h-20261111/Z01/demo-runs.json)。
