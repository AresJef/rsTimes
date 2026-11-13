# Delta 第二轮性能优化验收

记录时间：2026-10-11T21:42:45.112596+08:00。本轮目标：保持既定行为、安全和英文文档，核心组合相对文档版 Rust 的中位及保守速度比均达到1.10。

**验收结论：同一最终包的主测与新进程独立复测均通过G1–G7。交付版本为0.1.0+delta.2，未发布。**

## 性能结果

速度比＝旧版耗时÷新版耗时；数值越大越快。组合采用计划冻结的等权规则。每个场景在固定统计批次内用全部合格值计算Σ耗时÷Σ调用数，再计算中位及最差配对批次速度比。

| 比较 | 主测中位 | 主测保守 | 独立复测中位 | 独立复测保守 | 门槛 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 当前Rust/优化Rust核心 | 1.123840 | 1.101847 | 1.135151 | 1.111948 | 1.10 |
| cyTimes/优化Rust核心 | 1.512159 | 1.482584 | 1.528959 | 1.497124 | 1.25 |
| dateutil当前Rust/优化Rust | 1.013871 | 1.006938 | 1.008448 | 1.000540 | 1.00 |
| NumPy当前Rust/优化Rust | 1.079554 | 1.056058 | 1.072961 | 1.054426 | 1.00 |
| Pydt当前Rust/优化Rust | 1.516275 | 1.493295 | 1.477091 | 1.455175 | 1.00 |

核心组合的实际提速约为12.38%和13.52%；对应组合耗时减少约11.02%和11.91%。

并非每个单项都提速。两轮中相对当前Rust最差单项中位耗时退步分别为5.93%和4.26%，最差完整批次分别为7.80%和7.45%，均小于约定10%。日期/Pydt的1.15为可选目标，不增加完成门槛。

## 每项验收

| 项目 | 结果与证据 |
| --- | --- |
| G1核心新收益 | 两轮中位与保守均≥1.10 |
| G2当前版保护 | 全部99项中位与最差配对批次耗时均不退步超过10% |
| G3第三方保护 | dateutil、NumPy、Pydt三组各自两种速度比均≥1.00；dateutil复测保守1.000540，余地较小，保留实际值 |
| G4首版保护 | 原93项核心≥1.25、单项退步≤10%、原第三方组合≥1.00全部通过 |
| G5正确性 | 1381共同输入、54本包契约、46原有pytest、9Rust测试通过；未知差异0；新增Factory边界13种调用/异常/递归与基线一致 |
| G6测量可信 | 每轮99项×12批×120完整三方组＝142560合格组；17项短长控制通过；两轮原始来源核验、进程全集不相交 |
| G7交付质量 | release wheel与sdist、隔离sdist重建、实际安装native指纹、pip check、内容/许可、格式/Clippy/rustdoc/英文文档通过 |

## 保留的实现改进

- 原生Delta相对字段采用有界归一化，保留溢出检查顺序与绝对字段优先级。
- timedelta和NumPy增量减少中间对象；dateutil运算直接组合已检查字段，保留normalized及属性/数值回调顺序。
- 实际原生类型的日期、增量和relativedelta减少重复类型判断；子类及其他对象保留原路径。
- 原生整数构造借用现有参数对象，完整检查参数形状与位宽；空参数和纯绝对字段跳过无效工作。
- 原生repr使用有界ASCII缓冲；子类保留动态名称读取。
- 已验证64位CPython3.13采用等值的整数元组哈希，其他版本保留Python元组路径；未改变原有跨类型相等与哈希限制。算法依据[CPython v3.13.3 tupleobject.c](https://github.com/python/cpython/blob/v3.13.3/Objects/tupleobject.c)和[longobject.c](https://github.com/python/cpython/blob/v3.13.3/Objects/longobject.c)，等值另有本项目272组实际tuple检查；归属和许可证随包保存。
- 日期子类构造缓存固定关键词，保持构造回调、时区、fold和无变化身份。

没有可靠收益的尝试保留记录后撤回。生产代码不识别测试名称、样本计数或性能门槛；未拟合、修正或筛选耗时。

## CPU波动、有限调整与真实重复

计时包含完整Python调用、分配与结果释放。各方紧邻测量，六种顺序平衡；wall/线程CPU差、时钟与读取边界、负载/内存、适用主机计数和组跨度按原规则程序核验。无效成员使全组回队，合格慢值全部保留。共同调用数同时满足最快方目标时长及每方已测时钟成本/分辨率的0.5%要求，固定25%计数裕度；没有从耗时中扣除观察成本或拟合时间。

旧候选和失败证据未改判。最终getter短控制6.23%波动，经5→10ms限定控制降到2.20%；主测缓存hash/子类copy以及独立复测负微秒timedelta反向加按预先固定失败集合做1→5ms控制。各项仍12×40短长组，倍率差≤3%、波动≤5%，通过后完整12×120场景替换。最后负微秒场景在主测中也重测，使两轮采用相同最终配置。

保留场景只在产物、输入、环境、质量、计时、统计及源码保护签名匹配时复用。每个场景来自完整实际进程群，不跨进程拼半场景；变差也采用新完整结果。两轮分别重算全部门槛。

主测实际PID集合：`[59932, 59935, 59938, 67464, 67467, 67473, 76988, 76991, 76994]`。独立复测集合：`[69513, 69516, 69519, 77380, 77383, 77386]`。全集互不重叠。

两周期正式采集运行分别17.00和17.18分钟，累计34.18分钟，满足每周期20/累计40分钟。校准、分析、构建及交付仍计入项目有效时间，没有用采集运行时间替代项目工时。两轮最大噪声分别4.84%和4.64%。逻辑批次不是独立实验，正式结果按真实新进程周期分别验收。

## 最终产物与基线

- wheel：[rstimes-0.1.0+delta.2-cp313-cp313-macosx_11_0_arm64.whl](/Users/jef/ResilioSync/code/rsTimes/dist/delta-optimized-0.1.0+delta.2/rstimes-0.1.0+delta.2-cp313-cp313-macosx_11_0_arm64.whl)
- sdist：[rstimes-0.1.0+delta.2.tar.gz](/Users/jef/ResilioSync/code/rsTimes/dist/delta-optimized-0.1.0+delta.2/rstimes-0.1.0+delta.2.tar.gz)
- wheel SHA-256：`7b7c75ff66963181ae4770dc8b3703996fc91f323849bddea062d4fd8cdfa9fb`
- sdist SHA-256：`a4795d3abe63e59f0e28f1aedf7d01f6cff78915d3729519665dcbdc1e2657a4`
- 实际native SHA-256：`70942435f7c2cf95f4f17f35b4ba32da050107b69557999168fa6ff5cd29524d`
- R0仍是原文档版wheel，SHA-256 `cdeae5f6e0c99d781be69b14234e1eb8ac95dc3768a4d2b9e94066f40a7548fb`；原安装native `eee6dca499165338401dad52475b3be7cb60368b863ce333c8f74d0101f85e50`，未覆盖。
- C为冻结cyTimes3.1.0，未升级。

重建native与开发wheel字节不同，因此最终功能/文档/性能均绑定重建产物，没有改署开发成绩。README、demo及冻结资料保留；wheel/sdist不含参考资料、测试证据和本地环境。

## 时间与边界

原总预算480分钟；最终交付有效用时338.13分钟（约5.64小时），比原预算少141.87分钟，100/100。最终用时和分值以[todo.md](../tasks/todo.md)的交付检查为准。原T0保持2026-10-11T07:36:37.921Z；单列暂停/必要等待合计31.29分钟，区间见台账。普通工具、安装、编译、采样等待、记录和交付均计时；并行不重复加。

修复余量实际使用16.82分钟（原O3超支11.02及计时校准修复5.80），已含项目有效工时。O6额外54.98分钟来自O4/O5释放额度；最终精度控制27.67分钟来自O8释放；O10超支来自O7释放。原预算、实际差额和原目标线保留，不减少分母。

仅验收macOS arm64/普通CPython3.13，本机3.13.3；实际依赖环境与平台细节保存于原始身份记录。D1实际溢出OverflowError、无旧pickle/Cython兼容、已记录跨类型哈希限制和包名差异沿用。没有发布到GitHub/PyPI，也没有验收其他平台或新的Python版本。

## 安装和快速复测

```sh
python -m pip install --force-reinstall dist/delta-optimized-0.1.0+delta.2/rstimes-0.1.0+delta.2-cp313-cp313-macosx_11_0_arm64.whl
```

在已验证的候选环境直接使用：

```sh
.local/delta/optimization-20261011/candidate-env/bin/python -c "from rstimes import Delta; from datetime import datetime; print(datetime(2024, 1, 31) + Delta(months=1))"
```

复测参数、原始来源和调用说明见[benchmark使用说明](../benchmarks/delta/README.md)。正式复测必须重新核对预算、产物和精度身份；不能把旧控制直接套在新wheel上。

关键证据：

- [最终源/产物/进程/性能审计](../tasks/evidence/delta-optimization-20261011/final-audit-01.json)
- [主测最终全矩阵](../tasks/evidence/delta-optimization-20261011/formal-main-final.json)
- [独立复测最终全矩阵](../tasks/evidence/delta-optimization-20261011/formal-independent-final.json)
- [最终功能](../tasks/evidence/delta-optimization-20261011/final-functional-01.json)
- [最终文档](../tasks/evidence/delta-optimization-20261011/final-documentation-01.json)
- [分发重建与内容](../tasks/evidence/delta-optimization-20261011/distribution-01.json)

当前没有需要用户决定的未决事项。
