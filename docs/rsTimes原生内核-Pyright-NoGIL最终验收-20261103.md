# rsTimes 原生内核、Pyright 与 NoGIL：最终验收记录

**状态：已完成并本地采用doc01；32项任务／100分交付权重。采用包含七项明确的产物专属性能取舍，原始性能标准没有全部严格通过。最终预算及采用核查分别保存。**

本轮执行依据为[最终讨论决定](/Users/jef/ResilioSync/code/rsTimes/docs/rsTimes原生内核-Pyright-NoGIL统一项目最终讨论决定-20261102.md)的 Q01—Q07、D01，以及[48 小时执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/rsTimes原生内核-Pyright-NoGIL四十八小时执行计划-20261103.md)。原日期语义及明确例外继续适用。本轮不开子 Agent，不合并主干或公开发行。

## 1. 对象和发行边界

本轮最终冻结源码为 `aedc2ac9b05b939da4e227fb0a7724369101984e`，树为 `688332bd24bd80ac50f5d1ce34e1fe18558df6d2`。相对产品父提交 `0660613910badaafeb53fdeb39d41e07c4c5dcb0`，最后只修正 README 的类型检查准备说明及发行矩阵表述。135 项生产输入已与原 sdist 核对；每个实际安装包含27项非 native 载荷（16个.py、9个.pyi、py.typed及1个JSON资源）和1个native，共28个包文件。

CPython 3.13／macOS ARM64 实际最终 CI wheel：

| 对象 | SHA-256 |
|---|---|
| 实际 native | `08e7bac640563398f52a70b8f17c7f228628d850cb16d7fc11aa5b49ad949434` |
| wheel | `923236a8ad0f4cb61dcd4c0c268b7f27a2d427f350049c3ab098750746363074` |
| 原 sdist | `00f815f5ac187e5393d2d23c6dc56fb344910e90e35a97cb81907b49475d4b94` |

不同 Python ABI／平台有各自的实际 native 和 wheel 身份，不能用上面的 macOS 3.13 SHA 代替。独立 sdist 重建也保留自己的二进制身份，不假定可重建为逐字节相同的 native。

包元数据仍为 `0.2.0b2`；公开 PyPI `0.2.0b2` 是旧发行。本轮的新源码、Pldt 与 NoGIL 支持不因版本字符串相同而成为公开发行事实。采用与验证须核对源码、安装路径、载荷和 native SHA。

## 2. 已完成的构建和功能证据

[最终 CI 41629627028，attempt 1](https://github.com/AresJef/rsTimes/actions/runs/41629627028)的 56 项任务全部成功，源码身份与最终冻结输入一致。104 份原始 ZIP 已下载并核验；以下读回报告共同确认完整覆盖：

- [48 位置 native 与安装读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N29/doc01/CI-41629627028/native-readback-complete.json)：32 个普通 GIL 位置、16 个 t 位置，135 项生产输入及实际安装 smoke。
- [旧案例保留读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N29/doc01/CI-41629627028/case-preservation-complete.json)：181 个测试 lane，未解决的旧结果变化为 0；新支持的 ABI 标签对应旧拒绝样本按明确范围替代。
- [发行包与独立重建读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N29/doc01/CI-41629627028/bundle-readback-complete.json)：48 个 wheel、1 个原 sdist、3 个空 target 独立重建、2 个官方对照环境。

实际完整主线代表结果：普通 GIL 为 23113 PASS／4 条件 SKIP；t 为 23116 PASS／1 条件 SKIP；普通 pandas 2 兼容代表为 23100 PASS／17 条件 SKIP。各位置和各 lane 的原始结果分别保留，不能用同一个代表数量替代所有环境。

支持矩阵为同一源码，8 类平台分别构建普通 CPython 3.12、3.13、3.14、3.15，以及 3.14t、3.15t：

| 平台 | 普通 GIL 位置 | NoGIL 位置 |
|---|---:|---:|
| macOS ARM64 | 4 | 2 |
| macOS Intel x86_64 | 4 | 2 |
| Windows x86_64 | 4 | 2 |
| Windows ARM64 | 4 | 2 |
| Linux x86_64／glibc 2.28 | 4 | 2 |
| Linux ARM64／glibc 2.28 | 4 | 2 |
| Linux x86_64／musl 1.2 | 4 | 2 |
| Linux ARM64／musl 1.2 | 4 | 2 |
| 合计 | 32 | 16 |

依赖最低操作系统条件与本库 wheel tag 分开：Intel macOS 的 t 组合需要 macOS 14.0；NumPy 2.5.3 下 macOS ARM64 的 3.14／3.15 普通和 t 组合也需要 macOS 14.0。不能把较低的本库部署 tag 当成整套依赖最低条件，也不宣称物理测试了所有旧系统小版本。

## 3. NoGIL 与原生接线

核心类继续为 `Delta`、`Pydt`、`Pddt`、`Pldt`。日期合同、真实子类和外部回调职责不为 NoGIL 或类型检查改写。

- 模块声明、实际编译 ABI、导入前后和真实工作后的 GIL 状态分别核对。t 验证不通过 `PYTHON_GIL=0` 或 `-X gil=0` 强制隐藏不兼容依赖。
- 普通 GIL 快路与 t 安全路径按编译条件分开；t 不使用普通构建专属的裸读取、无保护缓存或 freelist 路线。
- Configs 的词表使用不可变 Arc 规则；t 显示缓存短锁发布，退出锁后释放旧 Python 引用。业务编辑使用每实例的非阻塞身份控制，同线程回调重入保持；正常共享只读及首次缓存竞争不能被伪装成业务冲突。
- Pldt 保留正式 namespace、15 个表达式插件、SDK 整列交换和共享小 Rust 内核。必要宿主桥接按固定 SDK／Polars 版本验证，不能笼统宣称整个实现没有底层宿主接口。

[实际并发读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N31/doc01-real-parallel-proof-readback.json)包含最终 doc01 的 24 组计算探针：两种 t 版本、2／4 个真实线程、Delta／Parser／Pydt／Pddt／Pldt eager／Expr。各组完整答案正确，计算区间存在重叠，实际线程 CPU 总量支持真实并行执行。该证据用于排除仅屏障同时启动或全调用串行化的伪并发；它不是正式吞吐倍率。

### Polars 责任和用户安装条件

Polars 本体及 runtime 由官方维护。本轮内部固定官方 Polars 2.1.0，提交 `7f902bd3ffd27ff82d14278a09a295ff2f7aed92`，源码与完整构建特性有独立核查。普通版最低 Polars 2.0.0 兼容职责保留。

内部源码构建及缓存仅供开发／CI；不维护 Polars fork，不向用户供应自建 runtime，不提供代下载、安装或切换用户环境的产品层。最终 48 个 rsTimes wheel 和 sdist 不含内部 Polars runtime。

用户需要匹配的 t 解释器、rsTimes wheel，以及自己从上游取得的兼容依赖。当前内部构建通过，不能推导所有平台已经存在可直接下载的官方 t wheel，也不承诺任意未来 Polars 版本。说明见[Free-threaded Python](/Users/jef/ResilioSync/code/rsTimes/docs/free-threaded-python.md)。

## 4. Pyright、类型和文档

Pyright 1.1.414 是唯一 Python 静态检查器，固定分析环境的 Node 为 26.7.0。3.12／3.14／3.15 三种语言配置均对实际安装包运行；与解释器实际 GIL 状态的验证分开。

[最终类型／文档读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N30/doc01-typing-docs-readback.json)确认：

- 原 48 个预期拒绝位置保留，新增 4 个原生边界拒绝位置；正负样本共 8 份。
- 完整活动源码范围为 40 个文件，意外诊断为 0。
- demo 中 43 个既定诊断和 52 个具体语句例外明确保留及校验，不通过修改公开 API、宽泛忽略或抹去真实外部行为刷绿。
- 文档核查覆盖 993 个定义、159 个可执行示例，缺失和示例失败均为 0。
- 安装包载荷、原生边界 stub、公开类型完整性及准确的安装路径一并核查。

源码检查器底层在存在预期诊断时可返回非零；通过的是检查工具对全部预期和意外诊断的完整判定，不能把结果表述为“源码没有任何诊断”。使用方法见[Python type checks](/Users/jef/ResilioSync/code/rsTimes/docs/type-checking.md)。

## 5. 原生优化及未采用路线

本轮沿一条主线实施。最终 Pldt elementwise 资格只对具有真实资格的静态基本列来源生效；选择器、别名、聚合及其它组合来源保留一般路径。新增 24 个真实 eager／lazy 选择器与 Delta 用例保护这些边界。

另有 80 个纪元整数值／符号／单位边界案例。必要直接修正还包括 UTC 去时区时避免无用目标分类，以及 Pddt 状态捕获避免每次创建仅供类型检查的 GenericAlias。

未采用候选如实保留：

1. 全局 PolarsAllocator 候选在真实导入前路径发生 SIGSEGV；同 SDK、工具链和环境的 System 分配器对照正常，最终仍使用 System。见[不采用决定及原始故障索引](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N20/non-adoption-decision.json)。该证据只否决本候选，不推断上游 SDK 在所有用法中都存在相同故障。
2. CPython 正数整数额外字节宽度路径未取得可靠净收益，资格数据不稳定，未采用；成熟整数 SDK 路线保留。
3. 静态来源的早期 scalar-query 草案破坏选择器语义，真实用例出现 12 个失败；直接替换为稳定的公开基本列判定，未保留错误草案作为兼容层。
4. N19 的 scalar query／diff elementwise 扩展未取得可靠净收益：diff 预试没有可见收益，query 预试存在顺序波动。两类可选标志撤回，保留基准实现；不把预试写成已经确认的稳定性能退化。见[主线选择和未采用范围](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N19/selection-decision.json)；其中开发轮数字不转记为最终 doc01 的性能成绩。
5. 为核查 `Pydt.is_future()` 的正式性能缺口，先查真实机器码，确认编译器已实现逐字段提前结束，未再做无效的源码改写。随后独立原型用两个私有入口共享同一比较内核，省去固定布尔参数传递；当前版与原型各 744 项功能验证通过，但控制阶段的表观改善没有在固定九周期预试中可靠复现：组间波动 9.81%，中位倍率 0.984838。按停止条件拒绝原型，正式源码、stub 和选定产物未改变。见[原型不采用决定](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N27/S082-prototype/non-adoption-decision.json)。这些是开发验证，不能作为正式缺口已关闭或最终产物的新性能成绩。

这些开发筛选不是最终性能成绩。最终净收益和逐项保护须以下面的新产物正式结果为准。

## 6. 最终性能与明确的采用限制

本次目标 **631项普通必要比较＋42项t观察＋2项静态Expr构建观察，共675项**，全部完成。每项216个完整配对／36个新真实worker，最终选定145800对，其中普通必要项136296对。不同轴可共用worker，不将675×36写成全局不同进程数。

普通必要项的实际对照：628项对冻结source31，N19的3项优化对本项目真实B0（提交`bbbccab0c4d66ec4250ded79456ca78bc85d5280ef5640deabe39496282e6388`）。历史`shared-B0`等轴名不是本项目B0身份。42项t中的6项`topt`另按各自同ABI基准比较。见[最终实际A/B产物来源核对](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/final-selected-artifact-lineage-audit.json)。

### 6.1 严格统计与采用取舍分别记录

|类别|数量|最终原始状态|
|---|---:|---|
|普通必要比较|631|624严格PASS、6稳定性未明确INC、1稳定速度FAIL|
|t单线程／同ABI优化／扩展性观察|42|29质量合格观察、13未明确观察|
|静态Expr构建观察|2|2质量合格；构建成本有所增加，按预设非否决角色报告|

普通标准仍为精度≤3%、稳定性≤5%、逐项最差保守耗时增加≤5%。624项严格PASS的最大精度为2.991912367%，最大稳定性差4.947211135%，最差保守耗时增加4.984671102%。**原先“所有必要比较严格PASS”的采用条件没有原样达成。**

当前Goal中，用户明确委托主Agent对合理请求和严谨判断后的合理代价取舍作决定。根据完整数据、限定质量尝试、独立功能证据和失败优化原型，主Agent作出[七项产物专属取舍决定](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N27/final-artifact-seven-case-decision.md)，明确修订且仅修订这七项的采用条件。不是用户逐项亲批，不继承旧source31的例外，不改变原3%／5%／5%数值或624／6／1原始标签，不减覆盖和样本，功能与安全不设例外。

|比较键|实际调用|原始状态与具体缺口|
|---|---|---|
|pldt-B0/L801|Polars2.0，1000行Lazy日历变换|INC；稳定性差5.421996%，不能宣称可靠精确倍率|
|shared-S0/S081|缓存后的Pydt标准hash|INC；跨组差5.092772%|
|shared-S0/NT01|单元素numpy us列的Delta.apply_many|INC；最大稳定性差13.657644%，保护结论未明确|
|shared-mainline33b-guard/NT01|同实际调用的独立原保护比较|INC；稳定性差5.688848%，不事后合并或转记其它比较|
|pandas2-S0/V102|1024行Pddt.strftime输出|INC；稳定性差8.993481%，原保守慢9.153574%是未明确描述值，不能称保护已过|
|shared-mainline35-guard/S010|标准datetime＋Delta|INC；稳定性差5.847210%|
|shared-B0/S082|UTC Pydt.is_future()|FAIL；精度2.503029%、稳定性4.855587%合格，最差保守耗时增加5.5913604%超5%|

S082的两轮中位倍率为1.008941／0.962219，第二轮约增加8ns。真实机器码已提前结束比较；一次私有入口原型未能可靠复现净收益，按停止条件拒绝。未通过反复重测同一失败产物寻找较有利数据。原型、本次质量失败和所有旧负面保留。其它同源调用的通过成绩只作风险旁证，不替换原INC或FAIL。

### 6.2 普通版收益与慢项

倍率R为对照耗时／本版耗时，R>1表示本版较快。以下是同一成本族的等权几何均值，不是所有API或业务工作量的整体加权收益。

|代表成本族|项目数|双轮倍率|可作出的结论|
|---|---:|---|---|
|source31对照的Delta共享主轴|29|0.999997／0.999376|全部严格PASS，基本持平|
|source31对照的Parser共享主轴|36|0.998660／0.997320|全部严格PASS，约0.13%—0.27%的小幅耗时增加|
|source31对照的Pydt共享主轴|36|0.999732／0.996108|含1INC，全部项组合只作描述，整体接近持平|
|Polars2.0 Pldt主轴|101|1.025039／1.026898|含L801的1INC；100项合格子集组合约1.01424，不能把全101描述值称可靠整体倍率|
|Polars2.1 Pldt代表族|15|1.161337／1.163252|15项全部严格PASS，该族约1.16倍|
|本项目B0对照的N19优化目标|3|1.159231／1.156021|全部严格PASS，该3项组合约1.16倍；100000行流式代表约1.57倍|

Pddt及其它保护族大多接近持平；所有族和具体行见[完整性能判定与分族表](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/final-performance-verdict.md)。不能把source31、真实B0、普通／t或不同输入规模混成一个总提速。

[全部观察慢项排序CSV](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/final-selected-summary/all-observed-slower-necessary.csv)保留588条“至少一轮或保守估计较慢”的必要比较，按最差耗时变化排序。这不等于588项稳定性能失败。中位中心估计较慢为356项，其中354项质量合格。正式稳定速度FAIL仍仅为S082。

### 6.3 t成本、吞吐和内存

42项分为12项同小版本普通／t单线程成本、6项同ABI优化观察和24项1／2／4线程扩展性观察。前12项及6项均质量合格；扩展性11项合格、13项未明确。所有真实worker导入和工作后的GIL状态与实际ABI一致，没有强制关闭参数掩盖不兼容依赖。

计算探针与正式吞吐不同：探针证明真实重叠计算；正式吞吐仍按完整公开调用、原始墙钟、相同工作量与样本判定。多项容器的2线程代表约1.82—1.89倍；3.15t标量Delta的2线程代表约0.89倍，并非所有调用多线程更快。全部4线程扩展性项质量尚未明确，不能报告可靠4倍或线性提速。

计时工作单元包含循环和校验：每次execute实际2048个Delta/Pydt或1024个Parser操作；Pddt/eager为32次、Expr为16次1024行调用。线程池创建在计时外，提交／等待／消费结果在计时内。Polars全局线程池与Python线程可能过度并行，不能简单把10×4当40个不同工作线程。

RSS为实际进程在准备后和工作后的峰值，包含解释器、依赖、输入、线程池等，不是每对象或函数独占内存；原始墙钟不以CPU/RSS修正。[完整42项吞吐与内存读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/final-selected-summary/t-throughput-and-memory-readback.json)保留合格／未明确、工作量、CPU与RSS全部细项。两项静态Expr构建分别约慢2%—3%和7%，保留其非否决观察角色，不混入执行净收益。

### 6.4 数据选择与可复核性

初采675项完整后，24个唯一比较键采用新的完整整项216对／36worker结果，全部PASS；替换规则在采前固定为新结果无论好坏采用，未挑选单轮或部分有利样本。一个较早R004 INC在同源原始文件中保留，仅作审计，不重复取得成绩。

- [最终唯一选源表](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N27/doc01-selected-replacements-07.json)。
- [675项初采43份报告的raw完整重算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/doc01-raw-recompute-01.json)。
- [21份补证来源raw完整重算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/selected-replacement-raw-recompute-02.json)：物理文件含25行，实际只选24行；不是额外扩大统计。
- [最终选源统计JSON](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/final-selected-summary/selected-source-and-statistics.json)及[数值判定](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N28/final-performance-verdict.json)。

双native／共同官方runtime模型均有当前Goal范围明确的决定、真实产物、完整输出和准备证据；保留原采集失败及限定控制失败。不把相同源码当作相同机器码性能，不把不同ABI或其它native旧成绩转给本产物。严格性能代表是本机CPython3.13.3／macOS ARM64及其冻结依赖；48位置CI功能通过不等于48位置逐项测了5%性能保护。

## 7. CI 正常完成耗时

本次最终同源、无错误的完整 attempt 从工作流创建到最后任务结束为 **77 分 49 秒**。含源码构建、48 位置、依赖前提、测试、独立重建和最终 bundle；不把此前失败、调试或其它 attempt 拼接进这次耗时。

[详细时长](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N29/doc01-ci-timings.json)及[逐 job CSV](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N29/doc01-ci-job-timings.csv)保留队列和执行时间。下表为同平台 6 个 ABI 任务的最早启动至最后结束跨度，平台间并行，不能相加为整轮耗时。

| 平台 | 6 个 ABI 的启动至最后结束跨度 |
|---|---:|
| Linux ARM64／glibc | 41:00 |
| Linux ARM64／musl | 48:40 |
| Linux x86_64／glibc | 42:16 |
| Linux x86_64／musl | 37:37 |
| macOS ARM64 | 64:20 |
| macOS Intel | 60:21 |
| Windows ARM64 | 31:03 |
| Windows x86_64 | 38:55 |

本次依赖与缓存条件由原始记录界定；这些时间不保证未来冷缓存、上游依赖或队列条件下完全相同。

## 8. 最终同步、过程与完成结论

最终源码135项生产输入与CI原sdist一致，361项活动输入与冻结doc01一致。根HEAD、分支与index保持启动时身份。整Git树中另两份PLDT历史计划的本地变体在本Goal前已经存在，不属本轮361活动输入；与后续有意更新的runtime／AGENTS／本轮状态页分别说明，不以覆盖既有工作强求整树相同。见[源码与保护读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N31/root-source-artifact-Git-readback.json)及[比较范围纠正](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N31/full-tree-comparison-scope-correction.json)。

主安装环境为`.local/native-pyright-nogil-48h-20261103/doc01-ordinary-dependencies-main`，不含Babel／cytimes；官方比较用独立`doc01-final-oracle-demo`。两者从最终实际wheel核对全部28个包文件和新进程native。旧oracle及计时环境未覆盖。

四个demo在项目根及另一工作目录共8次实际运行全部成功，Delta每次150个场景未知差异为0。runtime已绑定最终环境和实际SHA，不静默选择旧同名版本；未宣称这8次普通3.13demo替代16t验证。见[8次demo完整输出读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N30/eight-demo-output-readback.json)及[实际安装身份](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N30/doc01-oracle-environment-prepared.json)。

### 8.1 预算与流程评价

原2880有效分钟（48小时）总额、原T0、6分钟规划预收费及唯一5.716分钟无工作等待排除保持。所有分析、工具、CI与采集等待计入；阶段并行按时间并集计费，不把各阶段跨度相加或重复收费。最终实际用时与余额以[最终预算结算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/budget-final.json)为准。没有追加总预算。

每30分钟检查的实际时间和七个自问答案保留在唯一ledger。至T1680，56个到期位置均有记录，另8条额外检查；19次迟延超过1分钟，最大9.434279分钟。后续最终统计以[过程读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N31/process-grid-readback.json)为准。“1分钟”只是展示分组，未把准时要求放宽。也发生过超过期望的简报间隔，不能称沟通节奏全部达标。

测量维护原90分钟软目标未达到；[最终成本记录](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N27/measurement-maintenance-cost-final.json)给出约429.22分钟的保守整段上界，含准备／控制／采集／等待／分析，不冒充精确纯编码时间。CI恢复、步骤调配和全部负面有原始记录。总体预算内完成与这些历史软目标偏差分别评价，产品完成不能抹除流程偏差。

本轮自身的报告参数元数据、hash槽跨进程身份比较、S008独立预期表达、安装文件数量及整Git比较范围错误均已纠正，原失败保留。没有把它们伪装成产品缺陷，也没有删除不利记录。

### 8.2 条款、采用与边界

[最终逐条要求—源码—证据对应表](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N31/requirements-evidence-matrix-final.json)覆盖Q01—Q07及D01；[完成与本地采用核查（独立保存）](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/adoption-completion-audit.json)记录全部32个任务、100分权重、实际产物和有限取舍。

功能、并发安全、支持矩阵、类型、文档、安装与demo均具有同源实际证据。原必要性能条件部分符合：624严格PASS、6INC、1FAIL；本轮授权下明确接受的7项产物专属条件修订已保存。流程评价为总体预算守约、部分节奏及软目标存在如实记录的偏差。

**最终采用以完成核查的实际记录为准：本地采用doc01，带上述七项明确限制；不能表述为原先全部数值门槛严格通过。**不把13项未明确t观察写成可靠倍率，不继承例外给下一版。不合并主干、不建tag／Release、不上传PyPI、不创建PR。公开b2仍是旧发行，用户依赖供应按D01由上游负责。

完成后本Goal的统一合理approve授权结束；不因预算有余额继续新开发、优化或采集。全部旧参考、原始样本和失败证据保留。
