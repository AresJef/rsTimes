# Delta 首版验收报告

更新时间：2026-10-10T14:53:29.562817+00:00。完成率100%，33步骤全部验收通过。实施T0为2026-10-10T05:08:45Z；用户追加60分钟，总额度780分钟。暂停2026-10-10T13:00:33Z至13:18:33Z共18分钟单列。

## 交付结果

Rust/PyO3实现Delta的19参数、15只读属性、27自有Python接口及必要协议：归一化、日期/时区/fold/子类、增量与时长正反运算、dateutil/NumPy标量、比较/哈希/真假/文本、本包保存复制和模块导出。冻结cyTimes3.1.0为参考。

实际数值溢出抛OverflowError；不做旧pickle/Cython兼容。跨类型相等/hash旧缺陷及既定日历规则保留，差异和限制见[行为说明](Delta行为说明.md)与[安全说明](Delta安全说明.md)。

## 验收结果

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 功能 | 1381共同输入验收通过，141已批准差异，未知差异0 | tasks/evidence/final-02/green.json |
| 本包契约 | 54状态/保存复制/模块/生命周期检查通过 | 同一green.json的candidate_contracts |
| 原有功能 | 46原测试通过 | final-02/existing.json |
| Rust检查 | debug/release各9通过，fmt与Clippy通过 | safety-03-review.json |
| 依赖核对 | 固定Rust15与Python55依赖，0已知漏洞；源码及版本未变化 | cargo-audit-01.json、python-audit-01.json |
| wheel/sdist | 已安装release、独立源码重建、严格元数据及pip check通过；22源文件再次逐字核对 | final-acceptance-03.json、final-source-02.json |
| 指定环境 | AppleM4、macOS27.0.1 arm64、普通CPython3.13.3，NumPy2.5.3/dateutil2.9.0.post0 | 最终性能environment及final-02/installed.json |
| CI与发布保护 | 本地执行相同构建/安装检查；标签/版本/local版本拒绝/TrustedPublishing保护核对 | ci-local-prepared.json、S8.3.json |

GitHub当前官方表将macos-15列为arm64；配置与本次平台一致。[官方runner说明](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。远程GitHub job未运行，未创建Release或上传PyPI。

## 性能：P1–P6全部通过

固定九组93项，组内及核心六组等权；结果不是实际用户使用频率。

| 标准 | 要求 | 实测 |
| --- | --- | --- |
| 核心组合 | ≥1.25 | 中位1.338646，完整配对保守1.315658 |
| 单项中位耗时退步 | ≤10% | 最大6.58% |
| 单项保守耗时退步 | ≤10% | 最大8.21% |
| dateutil/NumPy组合 | ≥1.00 | 中位1.145955，保守1.133168 |
| 统计波动 | 各项任一批次偏离中位≤5% | 最大4.28%，不稳定0 |
| 完整样本 | 全93项固定12统计批次 | 每批120有效短配对，共133920完整配对；每方1475720640次调用 |

91项短批次目标1ms，2项目标5ms。全部使用相同冻结代码、输入、解释器、依赖、硬件、QoS及计时规则，每个短配对两方调用量相同。环境核验不合格整组回队，所有合格慢值保留；实际全量424.84秒，两项有依据地加长后49.57秒。仅整项替换两项不稳定结果，不挑最好成绩。

[最终摘要](../benchmarks/delta/results/20261010T143458883509Z/summary.md)、[原始记录](../benchmarks/delta/results/20261010T143458883509Z/raw.json)。原始记录包含源数据位置/hash、完整配置矩阵及两份精度证据。全量与替换原始尝试均保留；最终采纳133920有效/168无效，双方各90次自身检查拒绝（部分整组两方同时拒绝）。

本次P5/P6由用户授权从旧7对≥100ms/跨时点极值，调整为短配对逐批核验、固定统计量及完整配对保守比较，数值目标保持。旧3轮长采样和新方案失败均保留，未追溯改判。结果只说明本环境、固定成功调用、通过环境检查的计算性能；不保证繁忙机器下所有延迟。

## 最终文件与来源

- [wheel](/Users/jef/ResilioSync/code/rsTimes/dist/delta-accepted-0.1.0+delta.1/rstimes-0.1.0+delta.1-cp313-cp313-macosx_11_0_arm64.whl)：SHA256 `013ae06917621daf7f55a3072da5982295492c05ea9bba9458629099750163c3`，401179字节。
- [sdist](/Users/jef/ResilioSync/code/rsTimes/dist/delta-accepted-0.1.0+delta.1/rstimes-0.1.0+delta.1.tar.gz)：SHA256 `d23d97cb091230dfcc2dd82a89b5ebb8706f221fc609935a9038c92de99db0f7`，153765字节。
- native SHA256 `468e1c142f64fbed1c829a3bc5449a59623bf2d34420737da59d54558d97648e`，与实际安装及正式测量一致。
- 冻结参考、开发环境和生成C未进入包；notice包含cyTimes/dateutil、Cargo依赖与工具链原版标准库目录及MIT/Unicode许可。原样许可中的空白保留，未为格式检查改变已验收包。

本地版本0.1.0+delta.1已验收，尚未公开发布。公开0.1.0仍为原最小包。

## 时间、进度和使用

交付记录有效用时566.74分钟（约9小时26分钟），总780分钟剩213.26分钟；相对原720分钟仍余153.26分钟。暂停18分钟不计，修复余量120未动用；阶段实际用时已包含全部工具、采样、分析、记录及交付准备，不重复计余量或并行耗时。末尾记录/提交计时以tasks/todo.md的最终完成快照为准。

全项目100%，S1–S8分别100%。[使用说明](Delta使用说明.md)、[快速复测](Delta性能复测.md)、[执行台账](../tasks/todo.md)。本轮无待决定开发事项；公开发布、其他平台和更高性能目标属于后续任务。
