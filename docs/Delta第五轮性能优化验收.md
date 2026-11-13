# Delta 第五轮性能优化验收

**当前候选可以运行，功能与安全检查通过，全部约定场景已经执行；性能目标未全部达到。** 本轮保留 `0.1.0+delta.5`（final01）的有效优化，61项指定目标22通过、39稳定未通过；旧版保护213通过、53未明确。未发布，也未把候选保留当成完整验收通过。

主报告记录截至2026-10-14 07:34:02 北京时间；最后交付审计与实际工时见唯一状态 [todo.md](/Users/jef/ResilioSync/code/rsTimes/tasks/todo.md)。

后续追加90分钟预算的试验与最新采用决定见[续接优化记录](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第五轮续接优化记录.md)。当前仍选择final01；final02/03及SDK配置原型均未采用，旧表格继续对应final01，不改署后续候选。

## 先看验收结果

| 验收项 | 结果 | 判断 |
| --- | --- | --- |
| 与rc04的结构化功能观察 | 1381项一致、未知差异0 | 通过 |
| 独立行为契约 | 54项通过 | 通过 |
| Rust单元／格式／严格Clippy | 9项单元测试，格式与Clippy通过 | 通过 |
| 对象释放、缓存、子类与普通线程检查 | 本轮最终64字节对象上的必要检查通过 | 通过；不代表自由线程或其他平台验收 |
| 独立sdist→wheel→安装 | 固定产物及真实native指纹一致 | 通过 |
| 61项追平Cython目标 | 22通过、39稳定未通过、0未明确 | 未全通过 |
| 相对rc04最多慢5%的保护 | 213通过、53未明确、0稳定超标 | 未全通过 |
| 小数相对等价整数最多慢20% | 7项全部通过 | 通过 |
| 可直接执行demo | 20函数、145场景、未知差异0 | 通过；演示计时不作正式性能成绩 |

按固定100分权重，当前有效通过约 **54.41%**。61项目标阶段 **36.07%**，旧版保护阶段 **80.08%**。测量可信5分因未全满足稳定性而不计；没有用预算消耗比例当完成率。

## 各方向一眼对比

| 方向 | 指定项数 | 通过 | 稳定未通过 | 未明确 |
| --- | ---: | ---: | ---: | ---: |
| 整数构造 | 8 | 0 | 8 | 0 |
| Delta加减 | 8 | 0 | 8 | 0 |
| timedelta运算 | 15 | 0 | 15 | 0 |
| 取负与绝对值 | 3 | 0 | 3 | 0 |
| NumPy日期 | 4 | 4 | 0 | 0 |
| NumPy时长 | 12 | 12 | 0 | 0 |
| pandas时长 | 1 | 0 | 1 | 0 |
| 表示文本 | 4 | 4 | 0 | 0 |
| 首次哈希 | 2 | 0 | 2 | 0 |
| 属性读取 | 1 | 1 | 0 | 0 |
| 16元素Delta批量 | 1 | 0 | 1 | 0 |
| 16元素timedelta批量 | 1 | 0 | 1 | 0 |
| 10000元素负timedelta批量 | 1 | 1 | 0 | 0 |
| **合计** | **61** | **22** | **39** | **0** |

200个共同场景：**Rust更快69项、Cython更快55项、接近71项、未明确5项**。这是按5%差距归类的全面对照；61项采用更严格的两轮都不慢于Cython要求。因此部分“接近”场景仍是指定目标的未通过项。

[61项逐条：旧Rust、新Rust、Cython实际耗时和状态](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第五轮61项验收明细.md)；[200项共同功能全面对比](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第五轮200项性能对比.md)；[266项CSV（包括额外保护输入）](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第五轮完整性能明细.csv)。

## 哪些改进已经进入候选

保留单次位置参数读取、较小的基础对象存储、原生NumPy热路径、表示文本缓存、有界对象分配缓存、批量准备结果复用、仅公开已初始化的输出前缀，以及空构造、属性和首次哈希的直接处理。调用方式和已批准的行为没有新增变化。

下面列出部分实际耗时。旧／新Rust是同轮紧邻比较；Cython／新Rust是另一轮紧邻比较，分别展示。未明确场景不据此承诺收益。

| 代表场景 | 旧Rust μs | 新Rust μs（与旧版） | 旧版保护 | Cython μs | 新Rust μs（与Cython） | Cython对比 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| C:construct-positional | 0.0949 | 0.0782 | 通过 | 0.0576 | 0.0776 | Cython更快 |
| C:arithmetic-delta-add | 0.0349 | 0.0306 | 通过 | 0.0243 | 0.0297 | Cython更快 |
| C:arithmetic-timedelta-add | 0.0334 | 0.0325 | 通过 | 0.0248 | 0.0319 | Cython更快 |
| C:value-repr | 0.0947 | 0.0183 | 通过 | 0.0191 | 0.0184 | 接近 |
| C:interop-numpy-duration-us-add | 0.0740 | 0.0409 | 通过 | 0.0531 | 0.0408 | Rust更快 |
| R:bulk:timedelta-negative:10000 | 185.9569 | 166.1044 | 通过 | 175.8198 | 167.8896 | Rust更快 |

整数构造、Delta加减、timedelta运算、取负和部分小批量虽然有保留的改进，仍未追平固定Cython。原型38/40的入口拆分、43的解析块拆分、44的取负公式、45的额外C转换、46的时钟加减方案都未采用。46功能与数学检查通过，但与final01的直接配对没有一致收益，已撤回；没有把不同候选的漂亮成绩拼成最终结果。

## 测量如何完成，以及仍有什么限制

短函数使用循环批量计时，再除以调用次数；保留真实公共调用、对象生成和释放。两方按ABBA／BAAB紧邻完整配对；质量不合格整组重试，合格的慢样本照常保留。每场景主轮和独立轮各3个新进程，每进程24个有效四批组，合计144组／576次计时批次。小数保护另按既有协议每项288个配对组，真实worker PID均记录。

窗口通常7ms、最低5ms；仅原定失败控制项或纯波动项允许一次10ms控制。墙钟与线程CPU差≤10%、读时边界≤1%、读取开销≤0.5%、正式完整组跨度≤500ms。短／双长倍率差≤3%，进程、顺序和主／独立倍率差分别≤5%。全部最终精度控制通过；53项保护及5项Cython对比仍因稳定性不足未明确。无法据此宣称它们没有退化。

最初200项共同对比收集28800个有效四批组（拒绝97）；266项保护38304个有效组（拒绝106）。只对原来波动未明确的场景做预定有限调整：保护96项控制中79项证明改善，79项完整重收、187项原完整证据复用；Cython15项控制中10项证明改善，10项完整重收、190项原完整证据复用。正式替换分别收集11376／1440有效组，拒绝21／8。所有旧原始数据和未改善控制均保存；没有局部槽位、不同调用次数或不同产物的拼接。没有重测39项稳定速度失败。

首次fold同包控制的进程波动为5.418%，明确保留未通过；实际最终fold保护在限定10ms复核后通过，并不追溯改判同包控制。固定测量可信整项未全过。系统负载、缓存竞争及频率变化仍可能影响结果；短窗质量核验不能证明消除了全部噪声。

有限调整证据：[保护控制](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/guard-finite-control/control.json)、[三项先验控制](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/stability-proof/proof.json)、[Cython控制](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/cross-finite-control/control.json)。最终归并：[266保护](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/guard266-final.json)、[200对比](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/cross200-final.json)、[61目标](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/targets61-final.json)、[7小数保护](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/float/plan-performance-summary.json)。

## 交付版本与运行

产物目录：[本地wheel和sdist](/Users/jef/ResilioSync/code/rsTimes/dist/delta-optimized-0.1.0+delta.5)；完整身份：[delivery-identity.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/delivery-identity.json)。

| 产物 | SHA-256 |
| --- | --- |
| wheel | `663a805158cffdb9e6d59d7b0089ca2c4e7917fc61414c9b955990219ad04c95` |
| sdist | `6cb5a3eda8e3b9ded71bd9fe5c58988dfbfdca9171069aee61183350f3ef8028` |
| 实际native | `dff8bbd57640065fbb899ce4b8cbf0c40ec58adc3dacb63568cce942efde7c2b` |

验收为macOS arm64、普通CPython3.13.3；实际系统macOS27.0.1，共享NumPy2.5.3、pandas2.3.3、dateutil2.9.0.post0。固定Cython为0.2.0 R2FinalE，native SHA `3ef0ec227fe995ebb0c289f28d59ff69faa8847dcfd13b0755eaaf71fb289aba`。这些是本轮真实加载身份，旧交付依赖锁仅属于历史。

直接执行：

```sh
cd /Users/jef/ResilioSync/code/rsTimes
python demo/delta.py
```

Demo由runtime.json选定环境，不在启动时编译。当前指向final-env01，并核对项目版本、安装版本、native路径和SHA。运行记录：[demo-direct-run.log](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/demo-direct-run.log)。明确标示“功能通过，完整性能未通过”。

功能证据：[1381项与rc04一致](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/functional.json)、[54契约](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/candidate-contracts.json)、[最终对象与生命周期](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/cache-safety.json)、[46项已有测试](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/timestamp-tests.json)。独立构建与源码证据：[sdist审计](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/sdist-audit.json)、[当前实现指纹](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final01/source-sha256.json)。质量日志：[Rust tests](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final/rust-tests.log)、[Clippy](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final/clippy-repaired.log)、[fmt](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-fast12h-20261013/final/fmt-repaired.log)；质量检查后两处等价样式修正已经包含在final01，不借旧实现证明新实现。

用户行为继续以[Delta行为说明](/Users/jef/ResilioSync/code/rsTimes/docs/Delta行为说明.md)和[rc04批准边界](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第四轮行为修正验收.md)为准，本轮不改变接口、溢出、子类、纳秒、状态恢复或NaT约定。原Git HEAD包含已有工作，不能用HEAD代替本轮未提交实现的源码指纹。

## 时间、偏离与结束边界

本轮720分钟从正式实施时刻开始计算；启动前规划按用户决定不扣预算。原T0为2026-10-13 22:57:23北京时间，硬预算边界2026-10-14 10:57:23。没有暂停区间，普通构建、采样等待和分析都计入，并行区间只计一次。

最终交付累计 **516.66分钟**，比720分钟总额度少 **203.34分钟**；没有暂停。S11报告、demo与交付实际 **7.42分钟**，在原20分钟内。下表按连续不重叠区间分布，阶段诊断的共享时间不再次相加。

| 时间区间／工作 | 有效分钟 |
| --- | ---: |
| 起点、最小工具和前置可测性 | 14.37 |
| 优化、开发构建和定向确认 | 375.40 |
| 最终打包、功能、安全和校准 | 21.09 |
| 初轮完整Cython／保护／小数验收 | 44.04 |
| 最后试验46的剩余分析与止损（前段与采集重叠） | 19.28 |
| 有限控制和一次场景正式替换 | 35.05 |
| 报告、demo及交付 | 7.42 |

工具开发／维护累计14.83分钟，未突破15分钟硬上限；后续只是调用既有接口和执行固定控制，没有扩大工具。O方向共享估算工时、工具诊断工时和X15与正式采集的重叠均在execution.json注明，不能加总作为总项目耗时。

本轮仍出现分析止损不及时：X13原10分钟实际共享16.68分钟，X15原35分钟实际共享44.46分钟。超额6.68分别由X11未用4.48与X06未用2.20补；X15超额9.46由S08未用7.952与X14未用1.506补。没有增加720总额，但晚自查本身是执行偏差；不能因有预算就称按时。下一轮应在结果返回时立即采用／撤回，减少继续分析的等待。

遵守T480停止新优化、T510冻结的边界；最终保留的源码与final01完全相同。有限调整用完，不因尚有预算重复采集或重开已否定方案。报告与demo交付完成后，当前候选和真实缺口保存，**目标仍未完成**；若继续攻克39项，需要新的明确实施安排，不能把本轮的剩余额度当作无限追加试验。

## 维护边界

PyO3固定为0.29.3。`tp_new_impl`虽然公开导出，位于带`doc(hidden)`的`impl_`边界，不属于常规稳定应用API；SDK升级须重新检查完整初始化和产物行为。未手工仿造Python私有对象头或payload偏移。分配缓存仅在已验证的普通GIL环境启用，容量有界；其它平台或自由线程没有在本轮验收。此维护说明不进入对外API docstring。

2026-10-14追加SDK原型验证：固定计数补丁有局部收益，61目标19通过/35未过/7未明确，保护与整包验收尚未齐，不替换final01。详见[依赖补丁原型验证](Delta第五轮依赖补丁原型验证.md)。
