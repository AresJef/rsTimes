# Parser 与 Configs 行为修订验收

日期：2026-10-15。范围：macOS arm64、普通 CPython 3.13.3。

**结论：本轮已完成，采用 `rstimes==0.1.0+parser.4`／rc02 作为当前本地版本。功能、独立构建、67项必要性能保护和3个固定组合全部通过，两个 demo 已同步实际运行。没有发布。**

## 1. 目标与实际修改

在保护正常解析功能和性能的前提下，让明确写出的日期、时间和配置值有可预期的处理规则。批准决定完整保存在[行为修订决定](Parser与Configs行为修订决定-20261015.md)，执行和时间只记[计划](../tasks/plan.md)与[唯一台账](../tasks/todo.md)。

| 项目 | 本轮行为 |
| --- | --- |
| ISO 不带秒的时区 | `2024-05-07T15:30+08:00` 正确读为 15:30:00；保留时区时为 UTC+08:00，偏移不再被当作秒 |
| 新参数 | `strict=False`，只能以关键字传入；原有八个位置参数顺序不变 |
| 明确非法字段 | 默认限制到最近合法边界，不进位、不丢弃已识别字段；严格模式报错并说明字段、数值和范围 |
| 重复字段 | 换算后相同值接受；冲突时默认后值覆盖，严格模式报错 |
| 星期与完整日期冲突 | 默认保留按星期调整日期；严格模式报错，不能改写明确日期 |
| 缺失日期与 default | date/datetime 的年月日可补缺；默认日超过月底时两模式都截到月底；不继承时分秒、微秒、时区或 fold |
| 两位年份 | 严格模式始终要求完整年份；默认模式必须有 default，用其年份的前50年至后49年选择世纪；不再读取系统年份 |
| 默认词表 | haziran、HAZIRAN、Haziran 修正为六月，不扩大语言范围 |
| 配置数值 | add、replace、恢复统一接受整数；1.0、1.9 等浮点数拒绝；时区总偏移必须在正负24小时之间，不能等于端点 |
| 配置复制 | copy.copy、deepcopy、pickle 生成独立配置；两边修改互不影响；失败设置／恢复不部分修改原对象 |
| 明确保留的行为 | lower／upper／title 识别方式、默认 ignoretz=True、未知文字／未知时区的宽松处理、Configs 不可继承及查询仅供 Rust 内部使用 |

严格模式只检查上述字段规则，**不表示必须识别每一个词，也不表示只接受 ISO**。

```python
from datetime import date
from rstimes import Configs, parse

parse("2024-01-02 12:99")                    # 2024-01-02 12:59:00
parse("2024-01-02 12:99", strict=True)       # ParserFailedError: minute
parse("Mon 2024-01-02")                     # 2024-01-01
parse("Mon 2024-01-02", strict=True)         # ParserFailedError: weekday
parse("February 2024", default=date(2024, 1, 31), strict=True)
# 2024-02-29；补入的默认日允许截到月底

parse("01/01/75", default=date(2026, 1, 1), yearfirst=False)  # 2075-01-01
parse("01/01/75", default=date(2000, 1, 1), yearfirst=False)  # 1975-01-01
# 缺少 default 或 strict=True 时，短年份报错并提示可行写法。
```

普通路径使用不拥有历史容器的 Rust 状态；严格路径才记录需要检查的重复赋值。语法和日历计算共享，避免维护两份解析器。没有引入新依赖补丁、Python 解析回退或新工具框架。

## 2. 最终采用产物身份

| 项目 | 值 |
| --- | --- |
| 当前本地版本 | `rstimes==0.1.0+parser.4`／rc02 |
| 行为／性能对照 | 已采用的 `0.1.0+parser.3`／rc03；官方行为参考仍为冻结 cyTimes 3.1.0 |
| 最终环境 | `.local/parser-behavior-20261015/rc02-final-env` |
| wheel | `dist/parser-behavior-0.1.0+parser.4-rc02/rstimes-0.1.0+parser.4-cp313-cp313-macosx_11_0_arm64.whl` |
| wheel SHA-256 | `ee3175bc787cf68081195b8b6c5d3378b6498c95e9d404b98fc71fe7b61b94b2` |
| sdist SHA-256 | `8a7a7688b83de3dce57758ed85078fe20091f56c514c92dea304b9adbe076ab8` |
| 实际 native SHA-256 | `4275aa83f3048641f2993ca6124b96d485512ac967139256410a25f45faa6007` |
| 实际 native | `.local/parser-behavior-20261015/rc02-final-env/lib/python3.13/site-packages/rstimes/_native.cpython-313-darwin.so` |

新进程加载的扩展与 wheel 内成员一致，`.pyi` 也与源码一致。最终 wheel 由独立解包的 sdist 构建，31个包内源码文件经过核对；Maturin 只为 Cargo.toml 添加 readme 元数据。参考资料、测试、证据和环境未被打包。用户 README SHA-256 保持 `4566f2f6f5082c4ac1dd77e28dc63db5ddaa6e12d2a668ff622df4360adf4a91`。

完整交付身份及依赖版本见[delivery-identity.json](../tasks/evidence/parser-behavior-revision-20261015/delivery-identity.json)，源码对应关系见[源码包审计](../tasks/evidence/parser-behavior-revision-20261015/rc02-sdist-audit.json)。当前工作树还包含用户原有修改，本轮没有以 Git HEAD 代替实际交付源码指纹。

## 3. 功能、构建与维护检查

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| Python 检查 | 4862通过，0失败／错误／跳过 | 实际最终环境运行，含 Parser 与既有 Unix 功能 |
| 保留行为逐项核对 | 5297／5297通过，0未知差异 | 每项保留原版结果、新版独立预期和实际结果；509条观察按批准规则改变 |
| Delta 保护 | 1529／1529与已采用包一致 | 相同输入指纹；本轮没有修改 Delta 实现 |
| Rust 检查 | 11通过 | 包含普通状态不拥有历史释放容器的结构检查 |
| 静态检查与格式 | 通过 | Clippy 将警告视为错误；格式检查通过 |
| 公开接口与文档例子 | 通过 | strict 默认值／关键字限制、3个文档例子、时区／默认日／短年份例子 |
| 独立源码包构建和安装 | 通过 | 实际 wheel、native 和声明文件身份一致 |
| 源码审查 | 已完成 | 实施者作有界审查，未宣称独立 Agent 审查 |

509是多种参数组合下的**观察条数**，不是509个不同问题。新版预期由独立政策脚本生成，不把候选的输出当作正确答案。原有完整测试输入未因批准差异而删除。

证据：[Python](../tasks/evidence/parser-behavior-revision-20261015/rc02-python.xml)、[保留行为](../tasks/evidence/parser-behavior-revision-20261015/rc02-behavior.json)、[Delta](../tasks/evidence/parser-behavior-revision-20261015/rc02-delta-comparison.json)、[Rust](../tasks/evidence/parser-behavior-revision-20261015/rc02-rust-tests.log)、[静态检查](../tasks/evidence/parser-behavior-revision-20261015/rc02-clippy.log)、[接口与例子](../tasks/evidence/parser-behavior-revision-20261015/rc02-api-doc-smoke.json)、[源码审查](../tasks/evidence/parser-behavior-revision-20261015/rc02-review.md)。

## 4. 性能口径与当前状态

性能对照是本轮起点 parser.3，目标是正常共同调用逐项及固定等权组合在两轮中的中位和保守结果，**耗时增加最多5%**。Configs 独立设置只报告；新 strict 和短年份的调用成本单列，不充当共同功能提速。

67项必要场景：36项代表 parse、4项兼容、12项补充正常调用、6项实际日期字符串语料、3项 Delta、3项恢复配置的旧新比较、3项新版恢复配置与未保存配置的比较。完整映射见[最终性能映射](../tasks/evidence/parser-behavior-revision-20261015/final-performance-map.json)。

语料性能使用703条新旧含义一致的字符串；另外25条短年份输入按**速度采集前**确定的行为差异排除出共同性能比较，但原728条输入全部保留在功能检查中。10个短年份性能输入换为明确世纪的正常同义输入，旧新双方调用和结果一致。组合名称与指纹按新输入重新记录，没有沿用历史提速成绩。

每项先作12短／6长批次控制，倍率差不超过3%。正式两轮各9个新进程周期，每场景每周期24个完整配对，AB／BA各12；每场景双轮432对，合计28944对。每批重复完整的公开 Python 调用，记录原始总耗时和次数，结果分配／释放计入。固定预热在目标计时外、整组跨度内。保留所有合格快慢数据；调度干扰使任一成员无效时，整组原顺序回队。

质量沿用既有规则：单批至少5ms、读取边界不超过0.1%、经过校准误差界的线程 CPU 差不超过2%。正式固定分组、顺序及跨轮波动最多5%；覆盖、质量、稳定性和性能分别判断。

rc01准备阶段用了原计划两次限定调整，精度控制全部通过；代表预试84／88组有效，耗时约12.54秒。预试不是正式稳定性证据，原配置及原始值完整保留。

rc02沿用选定批长重新控制后，B07／B15／U08精度未过。依据用户此前明确允许未来合理、预算内有限追加调整的授权，增加一次限定校准，已用两次不重置：只将这3项目标窗口增至20／40／20ms，最高40ms，保留全部旧数据，精度／质量／样本／性能门槛不变。三项均有精度改善并通过，67项控制全过。新代表预试84／85对有效，约11.94秒；仍有小样本波动，不当作正式稳定通过。完整采集预计30–33分钟，已留出交付时间。当前冻结配置见[rc02最终配置](../tasks/evidence/parser-behavior-revision-20261015/rc02-perf/frozen-config.json)。

rc01主轮已收齐：63项主轮通过、3项稳定性能未过、1项波动未明确。3个未过项是长小数时间加default、缺日月底补全和星期跨月调整。由于独立轮不能补救主轮不合格，已停止剩余采集，保存完整主轮及部分独立轮；不称rc01双轮完成。随后在15分钟有界单元内修复了无用日历工作；无可靠收益的入口内联原型撤回。原候选全部负面证据保留。

**最终结果：67项全部PASS，0项稳定性能失败，0项未明确；三个固定组合全部PASS。**

| 相对上一采用版 parser.3 | 主轮速度比 | 独立轮速度比 | 耗时变化 | 结论 |
| --- | ---: | ---: | --- | --- |
| 36项正常 parse 组合 | 1.03783 | 1.03642 | 减少约3.64%／3.51% | 通过 |
| 14项 ISO 组合 | 1.02028 | 1.01893 | 减少约1.99%／1.86% | 通过 |
| 703条共同字符串的6种调用组合 | 0.99179 | 0.99345 | 增加约0.83%／0.66% | 通过，低于5%上限 |

速度比为旧版耗时÷新版耗时，大于1表示新版较快。组合采用固定等权汇总，不能抵消任何单项退步。这是与 parser.3 的同含义比较，不把历史对官方的提速倍率改署为本次成绩。

| 最终必要验收 | 实际结果 | 门槛 |
| --- | --- | --- |
| 覆盖与顺序 | 每项双轮432完整对，AB／BA配额完整 | 全部67项完整 |
| 单组质量 | 最终采用组全部通过既定检查 | 最低5ms、边界0.1%、线程CPU误差界2% |
| 最大短长精度差 | 2.80% | 不超过3% |
| 最大分组／顺序／跨轮波动 | 4.23% | 不超过5% |
| 最差保守耗时增加 | 4.38% | 不超过5% |
| 解析、兼容、Delta、恢复调用 | 67 PASS／0 FAIL／0 INCONCLUSIVE | 全部通过 |

rc02第一份完整双轮收齐28944对，30898次尝试中1954对未通过质量或整组跨度检查，完整组接收率约93.68%。当时65项通过，D02／N03仅因波动5.63%／5.17%未明确，没有稳定性能失败。

按预定一次、最多10分钟局部处理，只对D02／N03验证固定预热／批长。首次N03精度4.27%未过，没有进入正式替换；同一单元内依据D02已实测有效的固定预热方法，最后一次N03验证精度1.68%、波动3.39%通过。随后两项完整重采双轮，约4分9秒，全部局部处理连审计约7分钟。最终D02／N03波动为2.06%／2.98%，均通过。

最终复用65项的28080对，新完整替换2项的864对，采用总数仍为28944对。原864对完整保留，累计保留29808个有效对；原36和替代36共72个真实工作进程。替代采集893次尝试、29次拒收。逐项来源、配置、旧结果和新结果都在最终文件中，没有跨配置拼接单个组或统计批次，也没有择优回退。

完整结果：[逐项JSON](../tasks/evidence/parser-behavior-revision-20261015/rc02-perf/final-performance.json)、[逐项CSV](../tasks/evidence/parser-behavior-revision-20261015/rc02-perf/final-performance.csv)、[原完整双轮](../tasks/evidence/parser-behavior-revision-20261015/rc02-perf/formal/performance.json)、[局部范围与原截止](../tasks/evidence/parser-behavior-revision-20261015/rc02-perf/remedy-scope.json)、[替代配置](../tasks/evidence/parser-behavior-revision-20261015/rc02-perf/remedy-frozen-config.json)。

### 设置和新规则的有限成本观察

15项既有Configs独立设置，以及4项新版strict=False／True比较，完成3个新进程周期、每项每周期12对，仅作成本观察，不是正式验收。四项strict=True的额外耗时约5.2%～13.6%，这反映新增字段检查的调用成本；正常默认调用仍按上述5%保护通过。

15项设置观察中K01／K03／K14／K15波动超过5%，只保留观察值，不给稳定提速结论；其余有限观察亦不宣称完成正式双轮。完整明细见[19项观察](../tasks/evidence/parser-behavior-revision-20261015/rc02-observations-resumed/observations.json)。没有为每个独立copy／pickle入口新增性能矩阵，其正确性仍由功能测试保护。

Y01两位年份的旧新成本对照未收齐：当前旧包单次调用约40微秒，按新包快方选择的共同批量数使旧方单批达到约3秒，120秒控制预算仍未完成。已停止该可选项，保存[原始控制与部分观察](../tasks/evidence/parser-behavior-revision-20261015/rc02-observations/config.json)，不报告可信倍率，不为了漂亮数字追加测试。它不属于必要5%性能否决项。

## 5. 使用与交付入口

对外说明：[Parser使用说明](Parser使用说明.md)。编辑器声明：`src/rstimes/parser.pyi`；运行时英文docstring与声明同步，面向API调用者。

从项目根目录直接运行：

```sh
python demo/parser.py
python demo/delta.py
```

两个脚本共享 `demo/runtime.json`，当前选中 `.local/parser-behavior-20261015/rc02-final-env`。启动器切换解释器并检查版本、native路径和SHA-256，源码、安装产物和demo已同步。

- Parser demo在根目录、其他目录直接执行均通过，展示原版／新版默认／新版严格行为及配置复制和恢复。
- Delta demo实际完成20个功能分组、145个对比场景，未知差异0。其交互计时不当作正式性能验收。
- 实际记录：[Parser根目录](../tasks/evidence/parser-behavior-revision-20261015/demo-parser-root.log)、[Parser其他目录](../tasks/evidence/parser-behavior-revision-20261015/demo-parser-other-cwd.log)、[Delta根目录](../tasks/evidence/parser-behavior-revision-20261015/demo-delta-root.log)、[交付审计](../tasks/evidence/parser-behavior-revision-20261015/completion-audit.json)。

## 6. 时间、限制与最终决定

本轮有效用时约 **247.1分钟（约4小时7分钟）**，少于360分钟预算约 **112.9分钟**。含最后核对与回复的约1.5分钟尾段估算，整体边界误差约±1分钟；未把记录和交付当作免费时间。明确等待用户启动的约33.20分钟不计入，普通构建、采样、失败处理和观察均已计入。

| 阶段 | 原分钟 | 实际约分钟 | 差额 |
| --- | ---: | ---: | ---: |
| P0 规划 | 20 | 17.03 | -2.97 |
| P1及R1–R6（含必要修复） | 195 | 137.33 | -57.67 |
| V1 两次最终功能／独立构建 | 30 | 15.40 | -14.60 |
| V2 必要性能准备／采集／有限处理 | 65 | 64.27 | -0.73 |
| D1 观察、采用、demo、报告及交付 | 20 | 13.04 | -6.96 |
| 原修复余量 | 30 | 0.00 | -30.00 |
| 合计 | **360** | **247.07** | **-112.93** |

阶段时间依据台账里程碑归并，未能准确区分的交错实现不伪造逐子步骤秒表。R6单项超出原30分钟，T85／T95等检查已公开自查和调配；原小步预算及失败尝试均保留。必要修复约12.7分钟、两次独立构建及已失败rc01的采集都只计一次。修复从前段实际节省调配，原30分钟余量未另行单独动用，不能再加到总工时。

工具维护估计约19.3分钟／20分钟上限；复用现有测量和合并代码，未建立新框架。rc01主轮证明稳定失败后及时停止剩余独立采集；短年份可选观察成本失控时及时停止，保留真实未完成项。依据：[时间结算](../tasks/evidence/parser-behavior-revision-20261015/budget-final.json)。

本轮采用rc02并结束，未发布、未推送或创建Release。用户README、冻结官方资料、旧产物、全部失败／未明确记录均保留。没有继续利用余额做额外优化。

适用范围为macOS arm64／普通CPython 3.13.3，没有新验收其他平台或自由线程Python。必要验收全部通过；非否决的Y01成本观察未完成，4个Configs观察波动未明确。当前三项Delta代表保护通过，不代表历史全部Delta性能缺项均已解决。
