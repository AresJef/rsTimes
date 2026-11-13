# Cython–Rust Delta 横向对比交接清单：Rust 候选97

准备日期：北京时间2026-10-13。此清单只交接rsTimes一侧的固定对象，不代表已完成与另一个Cython重写项目的横向测试。准备期间未构建、安装、优化或执行功能/性能测试，选定产物保持不变。

## 1. 固定比较对象

| 项目 | 固定值 |
| --- | --- |
| 项目根目录 | `/Users/jef/ResilioSync/code/rsTimes` |
| 最新采用版本 | `rsTimes 0.1.0+delta.3`，候选97 |
| 源码采用提交 | `5119a7f3aa4de8c4e6d33b9f0c0caf60733d5ac8` |
| 当前分支 | `codex/delta-native` |
| 准备时仓库HEAD | `985f836219203bfc10010b93c11076a04d7a9d0c`，后续提交为收尾及时间审计文档 |
| 采用依据 | 用户批准保留合理优化并直接收尾；原完整双轮性能验收未全部通过 |
| 平台 | macOS arm64，普通有GIL的CPython 3.13.3 |
| 发布状态 | 本地交付，未发布、未推送；PyPI原0.1.0不能替代本对象 |

本次核对：8个Rust源码、`src/rstimes`内发布文件与上述源码提交及固定sdist一致；测试输入、测试运行器、性能输入选择及构建配置也与该提交一致。工作树已有`README.md`和`AGENTS.md`修改保留，不据此改变固定比较对象。

源码提交不是所有同版本包的唯一身份。横向对比必须同时使用下面的产物路径和SHA-256，不能自动选择其他`0.1.0+delta.3`候选。

## 2. 产物、运行环境及加载身份

### 2.1 固定产物

- [wheel](/Users/jef/ResilioSync/code/rsTimes/dist/delta-revision-0.1.0+delta.3/rebuilt-97/rstimes-0.1.0+delta.3-cp313-cp313-macosx_11_0_arm64.whl)
  - SHA-256：`8dc3a914e90db8838abb5d2e109c69cba0f703686dab780001727a17567a223e`
- [sdist](/Users/jef/ResilioSync/code/rsTimes/dist/delta-revision-0.1.0+delta.3/source-97/rstimes-0.1.0+delta.3.tar.gz)
  - SHA-256：`4b266ed74f408993dedd266deb82f0e5dcd1c655a396a771121b143d9a44e495`
- [实际加载的native](/Users/jef/ResilioSync/code/rsTimes/.local/delta/revision-20261012/final-env97/lib/python3.13/site-packages/rstimes/_native.cpython-313-darwin.so)
  - SHA-256：`bdadd54566d4ad41ceed5591d57a6fa789cee9d09eaff4d2e5a84345d326bb73`

以上三个文件本次读取计算的指纹均与原交付记录一致。原证据：[N17-97安装与重建记录](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/N17-97.json)。

### 2.2 直接使用的运行环境

- 环境目录：`/Users/jef/ResilioSync/code/rsTimes/.local/delta/revision-20261012/final-env97`
- Python：[final-env97/bin/python](/Users/jef/ResilioSync/code/rsTimes/.local/delta/revision-20261012/final-env97/bin/python)
- 完整Python版本：`3.13.3 (main, Sep 18 2025, 18:58:22) [Clang 17.0.0 (clang-1700.3.19.1)]`。
- Python基础环境：`/Users/jef/.pyenv/versions/3.13.3`。
- 本次平台字符串：`macOS-27.0.1-arm64-arm-64bit-Mach-O`。
- 当前native报告`release_build() == True`；当前解释器GIL启用。

导入方式：

```python
from rstimes.delta import Delta as DeltaR
# 根包也导出同一类：from rstimes import Delta
```

调用时明确使用该解释器；不要依赖终端的默认Python或仅把源码目录加入路径。`demo/runtime.json`也选择此环境，但完整demo未在97收尾时运行，不把配置更新当作运行验收。

本次身份核对只导入模块、读取metadata及计算指纹，没有调用Delta业务方法。可机器读取的交接记录包含全部安装依赖、源码哈希和测试输入身份：[handoff97身份记录](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/rust-cython-handoff97-identity-20261013.json)。

## 3. 最终行为契约、测试输入和明确预期

### 3.1 应按什么判断行为

1. [tasks/plan.md第3节H01–H12](/Users/jef/ResilioSync/code/rsTimes/tasks/plan.md:47)：本轮最终批准的行为决定；小数和64位条件实验已采用，采用结论见97收尾记录。
2. [当前Python接口声明与方法说明](/Users/jef/ResilioSync/code/rsTimes/src/rstimes/delta.pyi)：参数、属性、方法和对外说明；构造的完整说明在已安装类docstring及[rust/delta.rs](/Users/jef/ResilioSync/code/rsTimes/rust/delta.rs:104)。
3. [最终26项行为契约结果](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/final-contracts-97.json)：绑定候选97实际native，26项均通过。
4. [最新采用及验收结论](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第三轮优化验收.md)：最终能力、性能和未完成项。

**旧文档提醒：** `docs/Delta使用说明.md`仍标注`0.1.0+delta.1`，`docs/Delta行为说明.md`也包含首版跨类型相等、重复初始化及旧整数范围等历史行为。这两份文件不能作为候选97被改变行为的最终依据。本次只登记这个文档缺口，没有修改旧文件或交付包。源码与旧说明冲突时，按本轮契约、明确测试预期和97运行证据核对。

### 3.2 可复用的测试和预期

| 内容 | 文件与入口 | 明确预期或结果来源 |
| --- | --- | --- |
| 既有接口和第三方行为 | [tests/delta/cases.py的cases()](/Users/jef/ResilioSync/code/rsTimes/tests/delta/cases.py:129) | [final-functional-97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/final-functional-97.json)同时保留1381项冻结原版观察和对应97观察，含字段、类型、结果或异常 |
| 本包恢复、复制和导出 | [candidate_cases(..., revision=True)](/Users/jef/ResilioSync/code/rsTimes/tests/delta/cases.py:1377) | 同一functional文件中的54项candidate_contracts；各行预期True，具体不变量由输入文件内assert写明 |
| 已批准的行为变化 | [revision_expectations()](/Users/jef/ResilioSync/code/rsTimes/tests/delta/cases.py:1564) | 每个受影响case ID的明确结果或异常类型；functional文件保留281项批准差异和0项未批准差异 |
| 新行为及边界 | [revision_contract_cases()](/Users/jef/ResilioSync/code/rsTimes/tests/delta/cases.py:689) | 26项独立断言；覆盖比较、不可变构造、子类、小数、宽整数、pickle、外部转换及两个新方法 |
| 既有性能工作量 | [benchmark_cases()](/Users/jef/ResilioSync/code/rsTimes/tests/delta/cases.py:588)与[旧场景选择](/Users/jef/ResilioSync/code/rsTimes/benchmarks/delta/cases.json) | 调用定义及结果来自共享输入，候选97最终正式可比既有项97个 |
| 小数、批量和时长转换工作量 | [revision_benchmark_cases()](/Users/jef/ResilioSync/code/rsTimes/tests/delta/cases.py:1289)与[revision-cases.json](/Users/jef/ResilioSync/code/rsTimes/benchmarks/delta/revision-cases.json) | reference/candidate两种等价调用：小数10项、批量30项、转换6项；不表示另一Cython包一定实现这些入口 |
| 运行器 | [tools/delta_check.py](/Users/jef/ResilioSync/code/rsTimes/tools/delta_check.py)、[tools/revision_check.py](/Users/jef/ResilioSync/code/rsTimes/tools/revision_check.py) | 分进程加载、观察和核对，不把脚本存在当成横向对比已执行 |
| 文档示例 | [documentation-97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/documentation-97.json)及[文档检查器](/Users/jef/ResilioSync/code/rsTimes/tools/check_documentation.py) | 实际安装包19个可执行例子通过 |

固定共享输入的SHA-256为：

`7c59ba52a3a58a29dde9acfe1a7f4eaae18926a5b65912b7f2c431b04c994531`

本次已确认其与源码采用提交、1381+54项结果及26项契约记录一致。原冻结参考是cyTimes 3.1.0，不是另一个Cython重写项目；现有原版–Rust成绩不能当作Cython重写–Rust成绩。

现有运行器的入口主要针对`cytimes`和`rstimes`。后续横比若另一项目包名不同，只需在预算内作必要入口适配，并按对应类映射类型名称；不修改业务输入、隐藏差异或用Python替代缺失的Cython接口。两个项目的Delta对象不能直接依靠跨类型`==`判断结果一致，应比较字段及对应类型行为。

## 4. 关键能力和边界

### 4.1 小数时长

- 真正保留小数时长的参数为`weeks/days/hours/minutes/seconds/milliseconds/microseconds`。Python float及float子类已覆盖，整数路径保持精确，不统一转float。
- 小数余量合并后仅在微秒边界舍入一次，最近值、恰好一半取偶数；支持负数、混合单位和大整数与小数组合。例：`days=1.5`得到1天12小时，`microseconds=2.5`得到2微秒。
- `years/quarters/months`和绝对字段仍先按原整数转换规则去掉小数部分，然后归一化或截取，不增加“小数月”的近似含义。
- NaN报`ValueError`；无穷及超范围值报`OverflowError`。不承诺Decimal/Fraction等非float类型的小数含义被保留。
- 对应断言：`revision:fractional-equivalence`、`revision:fractional-rounding`、`revision:fractional-errors`。

### 4.2 整数范围、归一化与日历

- 输入转换扩大到有符号64位；相对`years`和`days`支持64位存储，月份和时钟字段归一化到正常范围。并非每组64位输入都可成功：单位相乘、字段合并或中间计算真正溢出仍报`OverflowError`，不回绕。
- 例：`years=2**53+1`的整数精度保留；`days=2**63`被拒绝。`year=2**40`可截到9999，`year=2**63`在截取前已因输入范围报错。
- 绝对字段保留上限截取、负值未设置及毫秒覆盖微秒部分规则；相对字段进位，负值按向下除法归一化。`hour=25`设置23，`hours=25`表示1天1小时。
- 最终Python日期仍须在有效日历范围内；超界报错，不一律截到日期边界。月底夹取及加减不保证往返还原；绝对字段加法优先右侧、减法优先左侧的规则保留。
- 对应断言：`revision:wide-input`、`revision:wide-input-overflow`、`revision:wide-storage`、`revision:wide-calendar`。

### 4.3 比较、不可变性和子类

- Delta值在`__new__`构造；15个值字段不可改。重复`Delta.__init__`不重新写字段，直接状态恢复不能改变已有值。
- 同类Delta及继承相同值语义的子类可以比较；外部类型的Delta比较方法返回`NotImplemented`。Python仍可能调用外部类型的方法，不保证任意外部类型的`==`与`!=`结果互为相反。
- 相等的Delta字段值有相同哈希。两个项目分别定义的Delta属于不同Python类，应采用明确字段快照进行横比。
- 支持Delta子类；改变值的子类构造应写在`__new__`，`__init__`可处理额外属性。子类附加字典可改变，不等于全部Python附加状态被冻结。
- 日期/datetime子类及Pydt按已有规则尝试保留返回类型；不能承诺任意自定义子类都成功保留类型。继承的一元运算返回基础Delta，子类重写的一元方法仍遵守Python调用规则；`from_relativedelta`工厂返回基础Delta。
- 对应断言：`revision:equal-keys`、`revision:foreign-comparison`、`revision:constructor-new`、`revision:repeat-init`、`revision:subtype-new`、`revision:unary-subclass-dispatch`。

### 4.4 第三方交互

- 支持既定的date/datetime、timedelta、Pydt及其他已覆盖日期子类的运算；方向、返回类型、时区、fold、微秒精度和异常按具体case核对，不推断所有第三方API均已迁移。
- relativedelta：`weekday`只要非None就拒绝，`leapdays`非零就拒绝，报`ValueError`；显式转换和四个加减方向一致。`leapdays=0`允许，`yearday`隐式产生的非零leapdays也拒绝。正常绝对字段继续按Delta截取规则。
- NumPy：支持已覆盖的datetime64/timedelta64标量；不提供数组原生运算接口。多倍单位、NaT、微秒以下单位和反向运算可能有单位或方向相关的结果/异常，按冻结输入逐项核对，不以普通直觉推断。ps/fs/as及generic单位保留既有不支持行为；不承诺任意NumPy版本ABI兼容。
- pandas Timestamp、pendulum等已有代表用例可复用，不据此宣称完整兼容这些包。改变Timestamp日期时可能按既有规则丢弃微秒以下余数，无变化时可保留原对象。
- 对应断言：`revision:dateutil-rules`、`revision:dateutil-errors`，以及1381项冻结行为中的dateutil、NumPy、日期和子类场景。

### 4.5 pickle、copy和deepcopy

- 支持本包pickle协议0–5、copy/deepcopy、已覆盖子类字典、共享引用和循环引用。复制产生独立对象；浅/深复制附加状态遵循各自含义。
- 只处理可信pickle。不支持旧cyTimes pickle，不承诺与另一个Cython包互读，也不承诺任意历史版本格式兼容。
- 状态标记为`rstimes.delta`、版本1、15字段及哈希缓存；当前重建还使用带版本的原生bytes载荷。错误长度、字段类型、范围和伪造哈希明确拒绝，不通过恢复修改已有值。
- 对应断言：`revision:pickle-copy`、`revision:pickle-copy-cycles`、`revision:state-guards`；54项本包契约另有协议与slots子类覆盖。

### 4.6 apply_many

- `delta.apply_many(values)`等价于`[value + delta for value in values]`，返回普通list，保留顺序；空输入返回空list。
- 接收可迭代对象、生成器与混合类型。元素必须支持这个加法方向，包含已支持的日期、Delta、timedelta、有效relativedelta及NumPy标量；尊重子类运算重写和自定义迭代。
- 迭代或运算错误直接传播，不返回半份结果，已消费的迭代器不回退；没有改变的日期对象按单项行为可被复用。不增加线程、异步或原生数组输出。
- 对应断言：`revision:bulk-matrix`、`revision:bulk-iteration`、`revision:bulk-overrides`、`revision:bulk-native-boundaries`。

### 4.7 to_timedelta

- `delta.to_timedelta()`无起点时，仅接受没有相对年/月、没有任何绝对设置的固定时长；违反时报`ValueError`，不忽略绝对字段，不用平均月长近似。
- `delta.to_timedelta(start)`接受date/datetime及已支持子类，行为等价于`(start + delta) - start`。date体现整日差，datetime保留时间影响；同一时区采用Python日期表达式的钟面差规则，不擅自改成UTC经过时长。
- 常规结果为datetime.timedelta；子类重写时返回类型和异常以等价表达式为准。timedelta范围溢出报`OverflowError`；日期加法本身的错误传播，非法起点报`TypeError`。
- 对应断言：`revision:fixed-timedelta`、`revision:anchored-timedelta`。后者包含232个日期时长组合及同区时区、自定义日期差和Delta反向加法的特别检查。

## 5. 依赖、锁定范围及构建信息

| 信息 | 已有文件或记录 | 固定内容 |
| --- | --- | --- |
| Rust完整依赖锁 | [Cargo.lock](/Users/jef/ResilioSync/code/rsTimes/Cargo.lock) | 当前文件与采用提交及sdist一致；SHA-256 `0796f521315691c7004670b13747a246aae5287d7b75ab800cb9a6435888cac2` |
| Rust版本配置 | [rust-toolchain.toml](/Users/jef/ResilioSync/code/rsTimes/rust-toolchain.toml) | `1.99.0`，minimal，含rustfmt/clippy；sdist内一致 |
| Rust构建配置 | [Cargo.toml](/Users/jef/ResilioSync/code/rsTimes/Cargo.toml) | PyO3 `=0.29.3`，edition2024，release thin LTO、codegen-units=1，扩展模块feature |
| Python构建配置 | [pyproject.toml](/Users/jef/ResilioSync/code/rsTimes/pyproject.toml) | maturin `==1.15.0`，模块`rstimes._native`，Python源码目录src；sdist内一致 |
| 验证依赖的固定版本 | [tests/delta/requirements.txt](/Users/jef/ResilioSync/code/rsTimes/tests/delta/requirements.txt) | numpy2.5.3、pandas2.3.3、python-dateutil2.9.0.post0、cytimes3.1.0、pendulum3.2.0、tzdata2026.5等明确版本 |
| 实际安装依赖全量快照 | [本次身份记录](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/rust-cython-handoff97-identity-20261013.json)的installed_dependencies | 包含上述版本及pytest9.1.1、six1.17.0、pytz2026.5等实际环境中的全部发行包 |
| 实际重建日志 | [bind-97-rebuild.log](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/bind-97-rebuild.log) | 从sdist解包目录独立release重建，CPython3.13，目标aarch64-apple-darwin，MACOSX_DEPLOYMENT_TARGET=11.0 |
| 打包、安装和源码身份 | [N17-97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/N17-97.json)及[identity.log](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/bind-97-identity.log) | fresh cache重建、实际安装路径、源码/native/wheel哈希、pip check和Rust/Clippy结论 |

Python的requirements文件为固定版本清单，并非带下载哈希的完整依赖锁；本次补充的是实际环境快照，未新增安装或锁文件。构建版本配置与历史日志分开提供，不把今天可用的工具版本当成历史编译器实测记录。

sdist的Cargo.toml比源码提交多一行`readme = "README.md"`，已检查具体差异并分别记录哈希；其他构建配置及全部Rust/Python发布源码一致。不要因正常打包元数据差异误认为另一个实现候选，也不要宣称整个源码压缩包与Git提交逐字一致。

对比建议继续使用普通CPython3.13.3/arm64，并对齐共同依赖和第三方对象来源；`requires-python >=3.10`是安装声明，不是已完成其他版本或平台验收。

## 6. 通过项、未通过项与未执行项

| 验收项 | 候选97结果 | 证据及边界 |
| --- | --- | --- |
| 冻结功能差分与本包检查 | 通过 | 1381+54项、281项批准差异、0未批准差异；[final-functional-97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/final-functional-97.json) |
| 本轮明确行为契约 | 通过 | 26项；[final-contracts-97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/final-contracts-97.json) |
| 文档示例、Rust与源码检查 | 通过 | 19例、9个Rust测试、Clippy、[源码审查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/final97-source-review.json)；不扩大成任意输入安全保证 |
| sdist独立重建与安装 | 通过 | N17-97，许可、依赖、实际native身份已核对 |
| 测量精度控制 | 通过 | 78项；[control-cycle-controls97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/control-cycle-controls97.json) |
| 主周期数值性能门槛 | 全部达到 | 143项；[formal-cycle-main97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/formal-cycle-main97.json)；原版对象是cyTimes3.1.0，不能据此推断另一个Cython重写版本的速度 |
| 主周期完整质量/稳定性结论 | 未全部通过 | `protocol:hash-cached`原版波动约5.209%；`numpy-datetime:D:negative:method-rsub`当前波动约6.631%，超5% |
| 小数、批量、转换主套件 | 通过 | 各自数据齐全、质量/稳定性/性能通过；独立周期仍未执行 |
| 额外两项校准与正式替换 | 未执行 | 用户直接收尾，阶段上限扩大请求未获采用，不继续补测 |
| 候选97完整独立周期 | 未执行 | 不转记候选81/83/92的独立成绩 |
| 完整双轮原始数据审计 | 未执行 | 原完整双轮性能验收`NOT_PASSED`，严格分值73/100保留 |
| 完整最新demo | 未执行 | runtime.json已选择97；不能把此前demo运行或本对话中的8项短运行检查当成完整demo验收 |
| 其他平台/Python、旧pickle/Cython内部兼容 | 未验收或不在范围 | 仅上述实际平台；不提供旧内部C接口或旧模块路径兼容 |

采用与停止依据：[closure97.json](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-revision-20261012/closure97.json)。用户批准采用当前成果，没有将失败或未执行项改成PASS。

## 7. 后续横向对比的使用约束

- 固定本清单的wheel、sdist和native身份；测试输出另存，不覆盖选定包、现有环境或历史证据。
- 先取得Cython侧同等交接信息，再核对共同能力和结果。不同语义单列详细差异，不用更快的拒绝、截断或缺失实现证明性能胜出。
- 每项差异保留具体输入、两边值/类型或异常、预期依据及对调用者的影响。性能只比较共同实现且工作相同的场景。
- 复用现有输入和工具，新增适配或测量必须在新任务预算内有明确目的和停止条件；不默认复制本轮143场景的大规模正式采样，不边对比边优化项目。

本清单、身份快照及所有引用组成Rust侧交接；未向另一个项目发送消息，也未对Cython侧版本作未经核查的确认。
