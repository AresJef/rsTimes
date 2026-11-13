# rsTimes Delta 迁移规划

状态：**本轮基准冻结和规划已完成；Delta 实现未启动。** 调查日期2026-10-09 UTC。rsTimes是用户本人cyTimes的Rust重写项目；第一条迁移路径只覆盖Delta及使其Python契约成立的必要内核。后续每阶段须另行进入实现任务，本规划完成不会自动执行Rust开发、配置变更或发布。

## 1. 已冻结的正式起点

通过 [PyPI项目JSON](https://pypi.org/pypi/cytimes/json) 对所有releases进行PEP 440比较，排除pre/dev版本和没有非yanked文件的版本，再与 [官方Simple索引](https://pypi.org/simple/cytimes/) 的文件hash/yanked状态核对。**本次实际最新稳定版是cyTimes 3.1.0**；这个结论来自2026-10-09查询，不是沿用历史3.1.0假设。版本后续变化不会移动这次冻结基线；升级基准需要重新冻结并审阅契约差异。

| 冻结档 | 大小 | PyPI SHA256（已逐字节验证） |
| --- | --- | --- |
| `cytimes-3.1.0.tar.gz` | 2,777,509 bytes | `f6b17e019293202fb2dbfe4eab74b7db45e35434c207b157973b7ff541d64ca9` |
| `cytimes-3.1.0-cp313-cp313-macosx_10_13_universal2.whl` | 5,272,194 bytes | `5ba8d9556271cebd8d52fcab592866ce26c84e68cc4794cd01b2e637f0894a19` |

仅下载一个本机CPython3.13/macOS arm64兼容wheel。完整URL、上传时间、冻结UTC、许可证、运行/构建依赖、JSON/索引、解包文件清单和工具版本证据都在 [manifest.json](../reference/baseline/cytimes-3.1.0/manifest.json) 与metadata目录。

```text
reference/baseline/cytimes-3.1.0/
  artifacts/                       # 原始官方sdist + 一个wheel
  metadata/                        # PyPI JSON/Simple、wheel METADATA/WHEEL、源码hash清单
  source/cytimes-3.1.0/             # 38个安全解包原文件，未执行其setup.py
  supplement/github-67941e0/        # 同版本官方测试补充，明确不属于PyPI源码档
  analysis/probe.py                 # 有界行为调查脚本，无性能负载
  analysis/probe-results.json       # 环境与每一项观察结果/异常
  manifest.json
```

先验证全部tar成员，再仅复制目录/普通文件；拒绝绝对路径、`..`、硬/软链接、设备等，单一顶层目录。原始档和解包源分别保留，wheel只读取元数据，没有把其模块展开进项目。目录位于`src`之外；现`pyproject.toml`只在src中发现rstimes且`include-package-data=false`，本轮不修改配置。已于2026-10-09 14:18:38 UTC在包含baseline/docs的临时工作树副本中，使用现有setuptools重新构建wheel和sdist并验证产物不含reference，证据见 [packaging-check.json](../reference/baseline/cytimes-3.1.0/analysis/packaging-check.json)。此检查仅验证当前setuptools产物的基准排除情况，不代表未来Rust wheel已完成验收。

Delta源码规模：delta.py 1,048行、delta.pxd 41行、delta.pyi 114行、生成delta.c 105,309行。实际算法大量位于utils.pxd 11,017行，不能只读utils.py就认为完成依赖调查。完整、自有/继承不重复的清单、实际签名、默认值、每个分支、源码路径行号、迁移方向和验收示例见 [Delta功能对照.md](Delta功能对照.md)。

sdist未附测试目录；官方GitHub标签3.1.0解析到commit `67941e0f3eefde3b5926390f21730b6ac5e60461`，它的delta.py与sdist字节相同。test_delta.py 388行与test_utils.py 4行仅作补充来源，原入口100,000随机轮次和utils大循环未运行。本轮轻量探针在 `/tmp/rstimes-baseline-venv` 中从校验wheel安装，记录CPython3.13.3、NumPy2.5.3、pandas2.3.3、dateutil2.9.0.post0等版本；未改变系统或rsTimes依赖。

原cyTimes元数据许可为 `MIT license, Apache License 2.0, BSD 3-Clause`，LICENSE含dateutil来源notice，不能只根据作者本人和rsTimes现MIT删去其归属文本。现rsTimes MIT原样保留；未来移植时在新分发中带入适用来源notice，范围依实际移植内容审查，不迁移Parser也不消除Delta/dateutil衍生部分的归属。

发现一个待实际多版本验证的发行矛盾：冻结sdist/本机wheel的根包第3行导入datetime.UTC，但 [官方Python文档](https://docs.python.org/3/library/datetime.html#datetime.UTC) 说明该别名3.11才新增，和cyTimes元数据>=3.10不吻合。这是源码推断，未运行3.10官方wheel。未来rsTimes必须保留现3.10支持；oracle优先在可原样运行的解释器执行，单独记录3.10安装/行为证据及无法同版本直接差分的限界，不修改冻结源来伪装官方基准。

## 2. 本轮保护的项目事实和范围

本轮开始HEAD为main上的`141c447`，工作树已有README.md用户修改（发布失败须Re-run all jobs段落）。未发现repo或祖先目录的AGENTS.md。README初始SHA256为 `4566f2f6f5082c4ac1dd77e28dc63db5ddaa6e12d2a668ff622df4360adf4a91`；检查其保持不变。

现项目0.1.0，Python>=3.10，setuptools>=77.0.3，纯Python、无运行依赖；`src/rstimes/__init__.py`的 `to_unix_ms`/`from_unix_ms` 必须保留原功能、结果类型、异常与边界。当前CI测试3.10/3.13，发布是Release published触发→tag/version检查→测试→构建→元数据和wheel安装检查→本次run/attempt产物→environment pypi / OIDC Trusted Publishing。本轮不改任何上述源码、CI、发布配置、版本或许可证，不stage/commit/push/发布。

第一迁移交付必须提供同一Python类：`rstimes.Delta is rstimes.delta.Delta`；Rust模块文件名为 **delta.rs**，类名 **Delta**，类型模块名为rstimes.delta。Python调用层是必需品，单独Rust库不能算交付。只迁移功能对照A/B/M/G和K中的必要内核；Pydt/Pddt/Parser、全utils公开函数、矢量引擎、时区Parser没有实施任务。

| 必要依赖 / 范围 | 处理方式 |
| --- | --- |
| Gregorian、负数归一化、日期/时间字段应用 | Rust整数内核；只取Delta可达函数和常量 |
| datetime/date/timedelta及其子类 | Python类型判定、字段提取、原类关键字构造；保留tzinfo/fold、identity和异常cause |
| dateutil.relativedelta | 初期仍调用Python `normalized()`并提取字段；记录丢弃weekday.n/leapdays的旧行为；运行依赖python-dateutil版本矩阵 |
| NumPy标量dt64/td64 | 必要适配，保留raw tick/unit/multiplier/NaT语义；不加array API；初期建议NumPy为明确依赖，不能在未批准时把现有支持降为“缺库就忽略” |
| pandas/Pydt/Pendulum | 互操作输入与返回类；不实现这些类。pandas/Pendulum为测试依赖，cyTimes仅冻结oracle环境安装 |
| errors | 最小兼容异常链，保留类名MRO；不拖入pandas/pytz的全errors导入链 |
| typing | 准确rstimes.delta.pyi与py.typed；以实际weeks/days顺序修正旧stub，不重复计overload |
| pickle/copy | 显式协议和state兼容，新包路径独立；旧路径读取另作决策 |

直接使用chrono/dateutil快捷加法会改变墙钟时区、月底、weekday、date小于一天的负偏移等行为。优先照冻结整数算法写必要calendar核；除非每个分支被差分验证，否则不靠通用日期crate宣称兼容。

## 3. 官方工具版本与拟议布局

本次 [PyO3官方最新release](https://github.com/PyO3/pyo3/releases/tag/v0.29.3) 是非预发布 **0.29.3**（2026-09-30），[该版本API](https://docs.rs/pyo3/0.29.3/pyo3/) 要求Rust>=1.83。[maturin官方PyPI](https://pypi.org/project/maturin/1.15.0/) 当前稳定版为 **1.15.0**。原crates.io API本次HTTP403，改以官方GitHub latest记录和docs.rs核实，不把403隐去也不把旧0.28.2当最新。详细查询证据保存在metadata/toolchain-verification.json。

建议将未来第一实现环境固定PyO3 `=0.29.3`、maturin `==1.15.0`，Cargo.lock入项目；Cargo使用官方稳定Rust满足最低版本，并在实施开始把实际工具链完整版本写入rust-toolchain.toml/环境清单。未查询Rust最新稳定号，故不捏造一个已验证版本。实施跨度变长后重新检查官方修订版，但升级必须有独立验证，不使用浮动latest构建对比。支持matrix至少保住项目现有CPython3.10/3.13；增加3.11/3.12及更新普通CPython由实际wheel安装证据确认，free-threaded/PyPy不默认宣称已支持。

拟议文件布局如下，仅为设计，**本轮不创建Cargo或Rust代码**：

```text
Cargo.toml / Cargo.lock / rust-toolchain.toml
rust/
  lib.rs              # 原生扩展入口，导出Delta
  delta.rs            # Delta结构、normalize、字段合并、Python协议绑定
  calendar.rs         # 仅Gregorian/ordinal必要内核
  interop.rs          # Python/NumPy/dateutil适配；若短则并入delta.rs
src/rstimes/
  __init__.py         # 保留现两转换函数；新增Delta re-export
  delta.py            # 必要子模块转出同一原生Delta及序列化入口
  delta.pyi / py.typed
  errors.py           # 必要异常层级
  _native.<so|pyd>     # maturin构建产物，不手工存源码
tests/delta/          # 有契约ID的差分用例
benchmarks/delta/     # 最后阶段的Python完整调用基准
```

原生扩展拟定为rstimes._native，pyclass module显式为rstimes.delta；用Python外壳保证子模块import、异常、pickle全局入口和类型提示。依据 [maturin混合项目布局](https://www.maturin.rs/project_layout.html) 设置未来 `python-source='src'` 与 `module-name='rstimes._native'`；保留原有Python文件。Cargo `[lib]`指向rust/lib.rs并生成cdylib。配置细节在正式实施任务中验证，不在现setuptools配置中预填。

[PyO3 0.29.3类文档](https://pyo3.rs/v0.29.3/class.html) 支持pyclass、pymethods、getter、classmethod、显式module、subclass与initializer。这里需要自定义数值转换与协议，不用derive(eq/hash)自动覆盖跨类型行为；不把只读getter等同frozen。须验证其new/init支持能重现Cythonraw分配与可重初始化；实现接口不应被框架默认值悄悄改变。按 [该版比较/数值协议](https://pyo3.rs/v0.29.3/class/protocols.html) 处理NotImplemented和反射槽。初期全CPython API、每解释器wheel，待datetime/NumPy和原型验证后再考虑abi3；[官方构建说明](https://pyo3.rs/v0.29.3/building-and-distribution.html) 中abi3是稳定Python ABI选择，**不是旧Cython ABI兼容方案**。

## 4. 执行队列与阶段验收

队列只在rsTimes项目内管理。本文件和功能对照就是当前任务清单；实施记录按ID勾选、附产物，不另建跨项目共享锁。依赖顺序如下，尚未通过的阶段不能以测试数量跳过：

```mermaid
flowchart LR
  F[0 基准冻结] --> C[1 行为契约与差分输入]
  C --> R[2 Rust核心及PyO3绑定]
  R --> D[3 逐项差分与边界]
  D --> W[4 构建安装与版本兼容]
  W --> P[5 完整Python调用性能及最终验收]
```

### 阶段0：基准冻结——本轮已完成

**输入：** 官方PyPI项目JSON/Simple和本机Python标签；项目当前文件/用户修改。

**动作：** 按稳定非yanked规则选择版本→只取sdist和一个兼容wheel→核对两处SHA256/大小→安全解包→存原档/元数据/许可证/逐文件hash→用同tag commit补测试并确认主源码同字节→隔离venv轻量探针→保留工作树事实。

**输出：** manifest、source-inventory、原始档、冻结源、明确补充测试、probe脚本/results、本轮两份中文文档。

**完成标准：** manifest可解析；每个原档SHA256同时匹配PyPI两来源；wheel标签与host相容；解包没有路径逃逸或特殊成员；baseline在现构建wheel和sdist中未出现；源码/CI配置和README用户修改保持；git index未改变。当前完成记录见manifest和packaging-check，网络最初sandbox DNS失败、Simple TLS重试及crates API403均已记录，不是未报告的读取拒绝。

### 阶段1：行为契约与差分用例——调查已完成，正式契约待实施

**输入：** 功能对照A01–19/B01–15/M01–12/G01–10/H01–04/K01–09、冻结wheel、补充T测试、P观察及Q决策。

| 任务ID | 具体动作 | 产物 | 完成标准 / 状态 |
| --- | --- | --- | --- |
| C1 | 将每个构造参数的默认值、位置顺序、i32/i64范围、19×类型矩阵、浮点向零、负数归一化、absolute截断/合并分支写成命名case | tests/delta/cases_constructor.py、冻结oracle输出 | 每个A/B ID至少覆盖正常/负/边界/异常；整组15字段与类型全部验证；待实施 |
| C2 | 将加/减/反加/反减的每种operand建立独立case；每个absolute字段测试左右冲突/未设置补齐；自定义反射对象检查NI交接 | cases_arithmetic.py、operand结果类型矩阵 | M03–08每个分派分支有结果类型+错误或NI；直接dunder和表达式均覆盖；待实施 |
| C3 | 用确定日期覆盖月底、1900/2000闰年、年1/9999、负小单位date、weekday向前、tz/fold/DST、identity、子类构造cause | cases_calendar.py、具体expected/exception记录 | K01–03可达分支逐个证据；不得用datetime普通加法覆盖月份行为；待实施 |
| C4 | 独立覆盖eq/hash三外部类型、可变状态/缓存、repr/str、子类、raw new、copy/pickle全部协议与state异常 | cases_protocol.py、新旧pickle可信fixture | M09–12/G/H逐项；Q1/Q4已明确；不得只修hash；待实施 |
| C5 | 固定NumPy/dateutil/pandas组合：13units正负、NaT、multiplier、dateutil fractional/weekday.n/leapdays、pandas残余、Pendulum子类 | cases_interop.py、依赖lock/平台metadata | 每个可观察错误/结果类型都进入契约；不把次级来源T当oracle；待实施 |
| C6 | 将T中的100k随机循环改为小型固定seed输入集合，扩充缺失契约；与冻结wheel运行器连接 | oracle_runner.py、case JSON、coverage-contract.md | 同一输入可反复运行；每条输出标来源和case ID；未运行的边界明确列出；待实施 |

运行方式：初期两个隔离venv分别装冻结cyTimes与候选rsTimes；父驱动传输相同结构化输入，固定tz数据库、环境、依赖、seed。候选导入用已安装wheel并使用`-I`，防止源码目录遮盖。能共存时可同解释器复核hash关系，不能通过修改sys.modules让两类型混为一体。输出比较15字段、准确Python类型、iso/tzinfo/fold/identity、NI、异常class/MRO/message/cause与文本；仅对必要包名与批准的版本差异进行具体白名单映射。

golden不能直接把P中function内存地址或pickle字节当跨进程规范；需结构化函数模块/名称、type、state/hash算法关系。保存原始观察便于追溯；缺少oracle输出的输入标记待调查，不自动把rsTimes结果当期望。dateutil不是Delta的普遍oracle，因为weekday和leapdays确有区别。

**阶段门槛：** 每个契约ID有输入、oracle证据和验收字段；差分器先针对同一冻结版本重复跑得一致；Q1–Q4中会影响契约的范围已落实或明确保持现状。不以“用例数量足够”替代覆盖。

### 阶段2：Rust核心 / PyO3绑定——未启动

**输入：** 已定契约、固定工具链与Q决策。**输出：** 可安装开发wheel和最小必要Rust/Python源。按以下顺序逐片开发，每片先通过其契约再接下一片。

| 任务ID / 预计文件 | 实施动作 | 本片完成标准 |
| --- | --- | --- |
| R1 rust/delta.rs | 建15字段+独立hash缓存；区分constructor规范状态/raw new/state恢复；兼容Python数值转换；Euclidean normalize与absolute ms/us | A/B/C1全字段、转换异常、i32/i64输入边界一致；中间溢出按Q2；不得先无条件用Rust checked或frozen |
| R2 rust/calendar.rs | 实现闰年、月天数、年之前天数、ordinal双向、day clamp、weekday同周调整；宽位中间计算和最终Python日期范围 | C3日历子集完整；月底/clamp顺序、year0过渡产生原错误；无chrono时间线替换 |
| R3 delta.rs + interop.rs | 接date/datetime字段、no-op identity、原类关键字构造、tzinfo/fold与cause；实现相对正负应用 | M03/M04/M06 date/datetime所有类型分支；精确类型/子类返回/失败异常 |
| R4 delta.rs | 7relative加减、8absolute优先；td日秒us；neg/abs独立组逻辑；直接/反射NI | M03–08非日期分支C2全过；子类Delta结果基类；不添加乘除/排序 |
| R5 interop.rs + errors.py | dateutil normalized及字段提取，最小异常链，分数/weekday.n/leapdays旧规则 | M02、rd运算/eq、错误MRO/message一致；运行依赖确定 |
| R6 interop.rs | NumPyraw值/unit获取、microsecond转换、Y/M平均td、NaT/multiplier旧分支；表达式反向调度 | C5全部units/方向/错误类型及NaT；无需迁移array/Pddt |
| R7 delta.rs + delta.py | eq、tuple hash缓存、bool/repr；生成比较槽、mutable init/state、subclass、reduce aliases/new恢复函数 | C4全面过，包括已记录eq/hash异常和旧状态行为；G01结构与框架能否匹配必须有实际验证 |
| R8 lib.rs + Python外壳/stub | 注册rstimes._native与rstimes.delta导出、根re-export、errors/py.typed；保留现有转换函数；如Q3要求则补2个意外parse函数的小兼容实现 | import身份/module、必要函数参数完全一致；to_unix_ms/from_unix_ms既有测试仍过；不迁移Parser |

Rust层单元测试只覆盖纯整数核的关键不变量和已批准溢出，不用镜像实现的无意义测试替代差分。初始保持Python调用所需GIL，不为了“Rust性能”提前释放GIL或新增共享锁。可纯Rust运行的计算片以后按测量决定是否detach，不能在触碰Python/日期类/dateutil时无约束离开解释器。

### 阶段3：逐项差分与边界——未启动

**输入：** R1–R8候选wheel、阶段1输入与oracle。**具体动作：** 按A/B/M/G/H/K ID逐项运行；失败输出最小复现（输入、预期、实际、环境、原source行）；修复后只复测相关分支及其依赖，再执行完整契约；有限固定seed组合交叉覆盖normalize/clamp/carry/absolute冲突；解释器发生native crash也算失败；核对引用计数、子类生命周期、并发普通调用对状态/hash不额外改变。

**输出：** 差分报告（每个ID已过/未过/批准偏差/不可直接1:1）、最小复现与偏差登记表。偏差表必须写原行为、新行为、为何不能一致、影响调用方、批准人/日期、case ID；未批准的行一直失败。

**完成标准：** 每个功能的行为、结果类型、异常类别/消息/cause、边界、NI路径一致；必要包名白名单之外无未批准变化；旧pickle/C ABI边界不能藏在“全兼容”标题里；保留rsTimes现有两函数全部契约。测试数只是信息，不是门槛。

### 阶段4：构建安装 / 多版本兼容——未启动

**输入：** 正确性已过的实现、固定PyO3/maturin、锁定依赖。**输出：** 可本地审核的sdist及平台wheel、安装矩阵、依赖/许可证/类型信息/产物内容报告；本阶段不自动发布。

| 任务ID | 具体过渡与检查 | 完成标准 |
| --- | --- | --- |
| W1 | 在单独实施变更中由setuptools纯Pythonbackend切为maturin混合backend；固定build requirement、Cargo路径与module-name；准确描述原生Delta而保留Python工具 | python -m build/maturin build --release产出真实native wheel及可重建sdist；无需改包名占位功能；版本更改后决定 |
| W2 | 检查wheel内rstimes文件、native扩展、stub、py.typed、license/归属；sdist包含Cargo/Rust/必要Python源、排除reference基准/分析venv/巨型上游C | 明确zip/tar清单审核；没有cytimes基准或额外顶级包；从sdist干净构建成功 |
| W3 | 至少在现CPython3.10/3.13干净venv安装rsTimes wheel，运行完整契约和既有转换；补普通CPython3.11/3.12和新增版本经验证后扩展；实际核实官方cyTimes 3.10根包导入限制 | 每个正式声明的Python/OS/架构都有wheel安装、native导入和行为结果；pip check通过；3.10无法同解释器原样运行oracle的差分限界明确列出，不冒称全平台已对比 |
| W4 | Windows x64、macOS arm64/x64、Linux x86_64（架构扩展有明确目标再加）的实际runner构建/安装；检验NumPy版本ABI、i32/64与异常文本、原类行为 | 无“开发机过了等于所有平台过”的结论；未支持的平台不虚报wheel可用 |
| W5 | NumPy最低可安装组合及当前组合、dateutil支持下限/当前、pandas测试组合；确定是否abi3；free-threaded/PyPy若未验收明确不作为本次已完成承诺 | lock/environment可复建；不因依赖未测就删除原功能；abi3不能降低契约 |
| W6 | 未来更新CI的构建工具与平台产物策略，保留Release published→验证→测试→构建/安装→TrustedPublishing结构 | 发布job仍只取当前run/attempt审核产物；build失败绝不上传；tag/version、pypi环境、OIDC和最小权限仍在；本轮不改workflow |

现纯Python的universal wheel不能承载假Rust声明。切backend后要明确平台wheel标签/来源；sdist用户需要Rust工具链。若为不存在wheel的环境设计纯Pythonfallback，须另行决定，不在未授权情况下增加两套Delta实现。可用maturin或以后cibuildwheel等方案协调矩阵，真正命令/版本于实施阶段验证。

Release链的测试必须先校验将要发布的wheel，不能只测工作目录。多平台产物应统一审阅、按同run/attempt收集，保持“先测试再发布”；可信发布不替代wheel安装正确性。当前0.1.0及已有发布功能本轮原样保存。

### 阶段5：完整Python调用性能 / 最终验收——未启动

**输入：** 阶段4能安装且契约已过的release wheel、冻结cyTimes oracle及固定环境。**动作：** 在rsTimes内部排队分块测量，先固定hardware/OS/Python/Rust flags/依赖/tzdata、电源和后台负载；记录wheel hash、commit、CPU/架构、warm-up、输入、轮次、原始计时和方法，保证下次可复测。本轮没有运行性能负载。

测量块：构造（零值/混合/负单位/absolute）；属性读取；Delta±Delta/timedelta；date/datetime月底与普通路径、tz/fold、子类构造；dateutil转换与运算；NumPy各常见标量转换；eq/hash（首次与缓存分别）；repr/str；copy/pickle。计时从Python调用发起到Python结果完成，包含对象分配、参数/类型转换、PyO3边界和Python回调，不以Rust内部循环吞吐替代用户调用速度。每块先核对结果，warm-up后多批重复，报告中位数/分布/置信范围和原始样本；避免测量期间共享跨项目锁或不同任务互扰。

Rust没有必然速度优势，dateutil/subclass回调可能主导时间，简单调用也可能被绑定开销抵消。若比cyTimes慢，报告具体块和原因，先定位、再有证据地优化；重跑受影响正确性/性能块。没有事先批准的量化性能指标就不能造一个“2倍”门槛，也不能以性能掩盖行为偏差。

**最终输出：** 安装矩阵、逐ID行为结果、已批准偏差表、可重测性能包、使用示例和必要升级说明。**最终完成标准：** 全功能/类型/异常/边界与基准一致或明确批准偏差；支持矩阵的wheel可安装，sdist可构建；旧pickle/C ABI等边界被维护者接受并文档化；现转换功能无回归；性能测量可复测且不虚称更快。完成实现验收仍不代表公开发布授权。

## 5. 少量需要明确的兼容决策

本轮只提出决策，不阻碍冻结/文档完成；也不替维护者批准行为变更。保持基准行为是后续实施的默认值。

| ID | 已验证的问题 | 建议默认 / 需要批准之处 |
| --- | --- | --- |
| Q1 eq/hash与可变对象 | Delta同时等于td/rd而hash不同，set/dict失败；__setstate__可保留旧缓存；仅改hash无法匹配两种外部hash | 首版严格保存；若修复则明确选择跨类型eq限制、不可hash或其它契约改动，作为独立兼容变更，不在迁移暗改 |
| Q2 极端数值/C溢出 | 输入范围有检查，中间C加乘/total_us/neg没有统一检查，本机出现回绕；跨编译器有符号溢出不构成可移植契约 | 先固定位宽，普通范围逐项一致；若把观察到的wrap纳为目标，要显式wrapping且跨目标probe。若改为OverflowError，必须具体列批准输入域/偏差 |
| Q3 Cython及附带导出范围 | pxd公开布局/vtable/11方法；Python delta模块意外有parse_to_int/float；完整utils也作为import残留可见 | Python Delta及其参数/方法完整一致；两小parse函数建议保留兼容。C ABI不承诺自动兼容；若有cimport消费者需单独适配/重编译，不扩大到全库 |
| Q4 旧pickle与包名边界 | pickle引用cytimes.delta恢复函数/类且带Cythonchecksum/state/hash；错误消息包含旧全限定类型名 | 新rstimes路径完整往返；批准必要包名文字映射。旧pickle默认提供显式迁移方案，不注入cytimes模块；如要求pickle.loads透明读取须另设计共存方案并验收 |

工具版本和第一平台矩阵可按本规划先验证，不是需要本轮停下来询问的审批；实现启动、配置改变、行为偏差与公开发布不包含在本轮授权中。

## 6. 本轮交付及剩余工作

- [Delta功能对照.md](Delta功能对照.md)：逐参数、属性、方法、槽、依赖、边界与来源行号。
- [manifest.json](../reference/baseline/cytimes-3.1.0/manifest.json)：官方来源、文件SHA256、许可证/依赖、源码规模、补充测试来源、隔离探针环境。
- [probe-results.json](../reference/baseline/cytimes-3.1.0/analysis/probe-results.json)：每条调查的原始结果与异常；未宣称完整跨平台验收。
- [packaging-check.json](../reference/baseline/cytimes-3.1.0/analysis/packaging-check.json)：本轮隔离构建与reference排除证据。

当前无未解决的基准下载或源码读取权限阻塞；网络限制/官方HTTP403和成功替代来源已明确记录。尚未完成的是阶段1正式差分契约、阶段2–5全部实现与验收，以及Q决策的最终选择。本轮到规划交付结束。
