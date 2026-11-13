# cyTimes 3.1.0 Delta → rsTimes 功能对照

调查日期：2026-10-09 UTC。目标是保持 Python 功能、参数、方法和行为一致，只允许必要的 `cytimes` → `rstimes` 包名变化及经维护者明确批准的偏差。本文是实现前契约清单，所有 Rust 项目均为待实现，不能把“已调查”理解为“已迁移”。总体任务与验收见 [Delta迁移规划](Delta迁移规划.md)。

## 1. 证据与统计口径

主证据为 [manifest](../reference/baseline/cytimes-3.1.0/manifest.json) 中校验过的官方 PyPI sdist 与本机 wheel，未使用用户本地 cyTimes 开发源码。以下缩写均指冻结文件，行号不会随上游变化：

| 缩写 | 完整仓库路径 | 用途 |
| --- | --- | --- |
| D | [reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.py](../reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.py) | 1,048 行，运行算法和声明 |
| X | [reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.pxd](../reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.pxd) | 41 行，Cython 类型布局、11 个 cdef 方法 |
| I | [reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.pyi](../reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.pyi) | 114 行，类型提示；有与运行时不同之处 |
| C | [reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.c](../reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/delta.c) | 105,309 行，Cython 生成槽、转换、pickle |
| U | [reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/utils.pxd](../reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/utils.pxd) | 11,017 行，实际内联 calendar/date/datetime/NumPy 内核 |
| UP | [reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/utils.py](../reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/utils.py) | 2,533 行，常量、时区工具、内嵌测试 |
| E | [reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/errors.py](../reference/baseline/cytimes-3.1.0/source/cytimes-3.1.0/src/cytimes/errors.py) | Delta 异常继承与消息拼装 |
| T | [reference/baseline/cytimes-3.1.0/supplement/github-67941e0/test_delta.py](../reference/baseline/cytimes-3.1.0/supplement/github-67941e0/test_delta.py) | 388 行，官方标签 3.1.0 的补充测试；不是 PyPI 附带测试 |
| P | [reference/baseline/cytimes-3.1.0/analysis/probe-results.json](../reference/baseline/cytimes-3.1.0/analysis/probe-results.json) | 514 个轻量观察，`case` 键定位证据；不是完整差分验收 |

T 固定 commit 为 `67941e0f3eefde3b5926390f21730b6ac5e60461`。该 commit 的 `delta.py` 与 sdist 逐字节相同。补充 `test_utils.py` 仅 4 行，调用 UP 中 `_test_utils()`；UP 的大循环未运行。源码、类型提示、说明文字冲突时，优先记录冻结 wheel 的行为，不能以注释覆盖运行事实。

统计不重复计继承：D 类内有 **38 个函数定义**，其中 **27 项自行声明的 Python 接口**（15 个属性 getter、1 个 classmethod、`__init__` 和 10 个运算/协议 dunder），另 **11 个内部 cdef 方法**。模块有 **1 个内部转换函数** `_delta_fr_relativedelta`。19 个构造参数不是 19 个方法，`.pyi` overload 也不另算。冻结 wheel 的 `Delta.__dict__` 有 39 个键：上述 27 项，加 10 个生成接口（`__new__`、5 个比较槽、4 个 pickle 方法/别名），加 `__doc__` 与 `__pyx_vtable__`。继承自 object 的 `__str__`、`__reduce_ex__`、`__getstate__`、`__format__` 等另列行为，不算 Delta 自有项。

## 2. 构造器：19 个参数逐项

实际调用契约是 D:101–122 的如下顺序，19 个参数均可位置或关键字传入；没有 `/` 或 `*` 限制。`self` 不计入 19 个调用参数。

```python
Delta(years=0, quarters=0, months=0, weeks=0, days=0,
      hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0,
      year=-1, month=-1, day=-1, weekday=-1, hour=-1, minute=-1,
      second=-1, millisecond=-1, microsecond=-1)
```

I:18–19 把 `days` 放在 `weeks` 前面，是实际存在的 stub 错误。迁移以运行顺序为准：`Delta(0,0,0,2,3).days == 17`。未来 `rstimes/delta.pyi` 应准确描述此运行顺序，并记录类型提示修正，不能照抄错误 stub。冻结 wheel 的 `inspect.signature(Delta)` 和 `inspect.signature(Delta.__init__)` 抛 ValueError；“无反射签名”与“无调用契约”是两回事。

所有参数先经 Cython 数值转换，再归一化/截断；这点在每行都适用。相对字段 C 类型分为 i32 与 i64，所有绝对输入为 i32。见 D:103–121、C:103084–103126 / 103403 起及 C:104881–104904。P 的 `coerce:<参数>:<类别>` 已逐个探测 19 参数：bool 可用；有限 float、Decimal/Fraction 经过整数转换，向零截断（`-1.9 → -1`），不把小数分配到下一级；有 `__int__` 的对象可用，只有 `__index__` 的自定义对象在本 CPython wheel 被拒绝；`None`、字符串拒绝为 TypeError `an integer is required`。NaN 为 ValueError，inf 为 OverflowError。不能直接假定 PyO3 `extract::<i32/i64>()` 与它完全相同。迁移需专用 Python→C 整数兼容转换，再检查位宽，保留异常顺序、类别和消息。

| ID / 参数 | 默认 / 输入位宽 | 实际限制与语义 | 源码 / 依赖 | Rust/PyO3 方向 | 对比验收案例 |
| --- | --- | --- | --- | --- | --- |
| A01 `years` | 0 / i32 | 最终年份相对值；接收月份归一化商，可正可负 | D:103,253–266 | i32 对外范围 + 显式中间算术策略 | 1；-1；i32 min/max；max+months=12 的溢出 |
| A02 `quarters` | 0 / i32 | `quarters*3` 加入 months，不存独立字段 | D:104,254 | 有序乘加，不能把季转天 | quarters=-1 → years=-1,months=9；与 months=3 抵消 |
| A03 `months` | 0 / i32 | months+quarters*3 按 12 向下整除，余数 0..11 | D:105,253–264 | `div_euclid`/`rem_euclid`，基数12 | months=-1 → years=-1,months=11；±12 |
| A04 `weeks` | 0 / i32 | `weeks*7` 加入 days，不存独立字段 | D:106,252 | 保留乘法先发生在原 C 类型的区别 | weeks=2,days=3 →17；大 weeks 的 C 乘法边界 |
| A05 `days` | 0 / i64 | 汇入 hours 进位、weeks*7；不归一化到月 | D:107,240–252 | 独立日期时长分组；不能30天转月 | days=1,hours=-24 →0；i64范围输入 |
| A06 `hours` | 0 / i64 | 以24向下进位 days，存值0..23 | D:108,240–250 | 有序 Euclidean 除法 | -1 → days=-1,hours=23；±24 |
| A07 `minutes` | 0 / i64 | 以60向下进位 hours，存值0..59 | D:109,229–239 | 同上 | -1 → days=-1,hours=23,minutes=59；60 |
| A08 `seconds` | 0 / i64 | 以60向下进位 minutes，存值0..59 | D:110,218–228 | 同上 | -1 的整组规范表示；±60 |
| A09 `milliseconds` | 0 / i64 | 乘1000先加入 microseconds；不存独立字段 | D:111,207 | 显式处理 i64 乘法溢出；不隐式 saturate | 1→1000us；-1；max 的发布 wheel 回绕样本 |
| A10 `microseconds` | 0 / i64 | 以1,000,000向下进位 seconds，存值0..999999 | D:112,206–217 | 完整7字段规范化入口 | -1→(-1日,23时,59分,59秒,999999us)；1,000,000 |
| A11 `year` | -1 / i32 | <=0→未设置；正值上限9999，超过截到9999 | D:113,269 | 内部 sentinel -1；getter转None | -2、0、1、9999、10000、超i32 |
| A12 `month` | -1 / i32 | <=0→未设置；正值上限12 | D:114,270 | 字段截断；不提前套某个年份 | 0→None；13→12 |
| A13 `day` | -1 / i32 | <=0→未设置；正值上限31；应用时按目标月再截断 | D:115,271；U:2377–2381,4027–4029 | 延迟月底处理 | 32→31；2023-02 + day=31 →28 |
| A14 `weekday` | -1 / i32 | <0→未设置；>=0截到6；0=Mon..6=Sun | D:116,272；U:4012–4017 | 最后调到同一周指定日，允许向前 | 7→6；星期日+weekday=0→前一个星期一 |
| A15 `hour` | -1 / i32 | <0→未设置；>=0截到23；0是真实替换 | D:117,273 | sentinel与0必须区分 | -1→None；0→0；24→23 |
| A16 `minute` | -1 / i32 | <0→未设置；>=0截到59 | D:118,274 | 同上 | -1、0、60 |
| A17 `second` | -1 / i32 | <0→未设置；>=0截到59 | D:119,275 | 同上，无闰秒接口 | -1、0、60；bool(Delta(second=0))为True |
| A18 `millisecond` | -1 / i32 | >=0时截到999并覆盖 microsecond 的千位以上；负值不覆盖 | D:120,276；U:2637–2671 | 合并为唯一 absolute microsecond字段 | ms=2,us=123456→2456；ms=0,us=123456→456 |
| A19 `microsecond` | -1 / i32 | ms有效时仅正us的 `%1000` 余数；否则us>=0截到999999；双负→未设置 | D:121,276；U:2655–2669 | 按分支合并，不能简单相加 | ms=-1,us=1000000→999999；ms=1000,us=1000001→999001 |

整数输入越界在截断之前抛 OverflowError：即使 year 会截到9999，也不能接受超过 i32 的 Python int。P `width:years:over` 消息为 `value too large to convert to int`；`width:days:over` 在本 LP64/macOS 上为 `Python int too large to convert to C long`，其它平台需重新冻结对应消息。

规范表示由两个独立组组成：年/月；日/时/分/秒/微秒。组之间不相互折算，允许年/月组与日/时间组符号相反。构造数值转换的向零截断与负单位归一化的向下整除不能混淆。`Delta(years=1,months=-13,days=1,hours=-25,microseconds=-1)` 的完整字段见 P `construct:mixed`。

中间 C 算术没有全面溢出检查。P 确认 `Delta(years=2147483647,months=12).years == -2147483648`、`Delta(days=2**63-1,hours=24).days == -2**63`、`Delta(milliseconds=2**63-1)` 表示 -1000us，而 i64 min 毫秒乘1000产生零。**这些是本 wheel 观察，不能宣称 C 有符号溢出是跨编译器规范。** Rust 不得静默改成无限精度或 checked 异常后声称全部兼容；采用显式 wrapping 复现已批准的发行矩阵行为，或登记并批准极端数值偏差。见规划决策 Q2。

## 3. 15 个自有属性

属性均为只读，`getter(self)` 没有额外参数/默认值。赋值/删除会抛 AttributeError； `_days` 等内部字段不暴露。quarters/weeks/milliseconds/millisecond 没有属性，不能因存在同名构造参数就新增它们。

| ID / 属性 | 返回类型、范围与语义 | 源码 | Rust/PyO3 方向 / 依赖 | 独立验收 |
| --- | --- | --- | --- | --- |
| B01 `years` | int；规范年/月组商，正负均可 | D:296–298；I:39 | getter导出i32；A01–03 | Delta(months=-1).years=-1；写入失败 |
| B02 `months` | int；0..11 | D:301–303；I:41 | getter；A02–03 | -1个月的months=11；13个月=1 |
| B03 `days` | int；i64，允许负值 | D:306–308；I:43 | getter导出i64；A04–10 | microseconds=-1时days=-1 |
| B04 `hours` | int；0..23 | D:311–313；I:45 | getter；A06–10 | hours=-1时hours=23 |
| B05 `minutes` | int；0..59 | D:316–318；I:47 | getter；A07–10 | minutes=-1时minutes=59 |
| B06 `seconds` | int；0..59 | D:321–323；I:49 | getter；A08–10 | seconds=-1时seconds=59 |
| B07 `microseconds` | int；0..999999 | D:326–328；I:51 | getter；A09–10 | microseconds=-1时999999 |
| B08 `year` | int或None；规范值1..9999 | D:332–334；I:54 | -1→None；A11 | 默认None；year=10000→9999 |
| B09 `month` | int或None；1..12 | D:337–339；I:56 | -1→None；A12 | 默认None；month=13→12 |
| B10 `day` | int或None；1..31，尚未与日期结合 | D:342–344；I:58 | -1→None；A13 | day=31仍返回31 |
| B11 `weekday` | int或None；0..6 | D:347–349；I:60 | -1→None；A14 | weekday=0返回int0，默认None |
| B12 `hour` | int或None；0..23 | D:352–354；I:62 | -1→None；A15 | hour=0与默认可区分 |
| B13 `minute` | int或None；0..59 | D:357–359；I:64 | -1→None；A16 | minute=60→59 |
| B14 `second` | int或None；0..59 | D:362–364；I:66 | -1→None；A17 | second=-2→None |
| B15 `microsecond` | int或None；0..999999 | D:367–369；I:68 | -1→None；A18–19 | 组合ms/us结果2456 |

原始 `__new__` 和 `__setstate__` 可生成非规范状态，故表中范围是正常构造器保证，不是对所有对象的强制不变量。B08–15 getter 只判断 `== -1`，原始0值会返回0。不得把所有非正 year 都在 getter中改为None。

## 4. 12 个自行声明的调用接口

运算方法源码参数名为 `o`，没有默认值。冻结 wheel 的直接数值 dunder 调用接受一个**位置操作数**：例如 `Delta().__add__(o=Delta())` 抛 TypeError `takes no keyword arguments`，反射展示 `__add__(self, object, /)`。PyO3 需使用相应槽，核对直接调用和表达式两种入口。

| ID / 实际调用签名 | 分支、返回类型与语义 | 源码 / 依赖 | Rust/PyO3方向 | 对比验收案例 |
| --- | --- | --- | --- | --- |
| M01 `__init__(self, 上述19参数) -> None` | 初始化15字段并重置hash缓存到-1；显式再次调用会改变现对象 | D:101–279；A01–19 | `__new__`分配与`__init__`初始化分开考虑，保留重初始化 | hash后`x.__init__(days=2)`；全部字段/新hash；参数重复、过多、未知关键字 |
| M02 `from_relativedelta(cls, rd) -> Delta` | 必须是relativedelta实例/子类；调用normalized()；拷贝相对7字段/绝对8字段；忽略weekday.n和leapdays；忽略cls并返回基类Delta | D:34–73,282–292；E:18–36,117–148 | 用Python dateutil规范化，字段提取后进同一Delta构造；定义最小异常继承链 | 子类调用仍基类；rd(days=1.5,hours=-2.5)→1d9h30m；MO(3)只存0；leapdays=1→空；非法rd异常 |
| M03 `__add__(self, o, /) -> object` | 分派顺序datetime→date→Delta→timedelta→relativedelta→np.datetime64→np.timedelta64；日期应用替换/相对/weekday；delta相对相加、右绝对优先（右未设置则左）；不支持返回NotImplemented | D:372–534；U内核K01–K05 | 有序类型分派；返回真实Python日期或基类Delta；不能duck type arbitrary对象 | 月底、子类、a+b绝对冲突、timedelta、np ns、直接不支持返回NI |
| M04 `__radd__(self, o, /) -> object` | datetime/date/td同加法；rd先转Delta再左加self，故self绝对优先；**没有Delta分支**；np在表达式中可能先被NumPy转为date/datetime/int | D:537–573 | 对称表达式与直接槽均测；不擅加Delta分支 | `d.__radd__(Delta()) is NotImplemented`；rd(year=2025)+Delta(year=2024)→2024；np us/ns差异 |
| M05 `__sub__(self, o, /) -> Delta或NI` | 支持Delta/td/rd/np.td64；不支持date/datetime/np.dt64；相对self-o；绝对左已设置则保留，否则**取右绝对字段** | D:576–657 | 逐字段left-or-right；不要按文档概述仅“左保留” | Delta()-Delta(year=2025)→year2025；Delta(year=2024)-Delta(year=2025)→2024；Delta()-date抛TypeError |
| M06 `__rsub__(self, o, /) -> object` | 支持datetime/date（仅相对取负，绝对不变）、td（o-relative）、rd（转Delta后减self）、np dt/td；**没有Delta分支**；不支持NI | D:660–792 | 独立反向路径；不复用“全部取负”而改变绝对值 | date-Delta(day=1,days=1)先替day1再减1日；td-Delta；直接Delta反向返回NI |
| M07 `__neg__(self) -> Delta` | 7相对字段取负再正常构造；8绝对字段保持；返回基类，不是子类Self | D:795–824 | 组算术+统一normalize；输入min整数单列 | -Delta(months=-1,microseconds=-1,year=2024)→1月1us且year2024；子类结果基类 |
| M08 `__abs__(self) -> Delta` | vector sign：years<0翻转years和months；days<0一起翻转days和4个时间字段；绝对不变；两组分别取绝对；重归一化 | D:827–872 | 按组而非逐字段abs | months=-1→1月；负1us→正1us；一组正一组负的完整结果 |
| M09 `__eq__(self, o, /) -> bool或NI` | Delta逐15字段；td需无年/月及无绝对值后比较i64总us；rd先转Delta（可能抛转换异常）；np.td64转td；其它NI | D:875–964 | 自定义比较槽；用宽位算术前先明确旧i64回绕；不能derive同类eq替代跨类规则 | Delta(days=1)==td/rd/np(1D)；带second=0不能等于td；rd(MO(1))与MO(3)转换等价；不支持直接NI |
| M10 `__bool__(self) -> bool` | 任一相对非0或绝对非-1则True；绝对0也有效 | D:966–984 | 字段判定；不调用总时长 | 空False；second=0 True；days1+hours-24 False |
| M11 `__repr__(self) -> str` | `<'类名' (字段)>`；相对years,months,days,hours,minutes,seconds,microseconds后绝对year,month,day,weekday,hour,minute,second,microsecond；省略相对0与绝对-1；weekday为MO..SU | D:28,987–1025 | 使用运行时类名；精确顺序/空格/括号 | 空`<'Delta' ()>`；weekday0,second0文本；子类`<'Child' (...)>` |
| M12 `__hash__(self) -> int` | Python hash(15元整数tuple)，绝对sentinel用-1；首次缓存（-1哨兵）；不含类型/类名；eq/hash不一致见§8 | D:1027–1048；X:26 | 调Python tuple hash；不使用Rust HashMap随机hasher；mutable缓存保留 | 同进程hash与15元tuple相同；子类相同字段同hash；copy/pickle后缓存；跨类型dict/set异常 |

所有正常运算返回 Delta 时都直接构造 `Delta(...)`，不保留 Delta 子类。I 的 `Self` overload 是提示，不能替代此运行事实。T:296–353 涵盖主要结果类型，但没有全面测这些冲突和边界。

## 5. 运算的类型矩阵与应用算法

这里的“td”含 timedelta 子类（如 pandas.Timedelta）；“dt”含 datetime 子类（如 cytimes.Pydt、pandas.Timestamp）。“rd”是dateutil.relativedelta；“d”是Delta。

| 表达式入口 | dt | date | d | td | rd | np.datetime64 | np.timedelta64 | 任意不支持对象 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `d + x` | 同类日期时间 | 同类date | 基类Delta | 基类Delta | 基类Delta | 内核转naive datetime；结果datetime | 内核转td→Delta | 直接槽NI；表达式由其它槽决定或TypeError |
| `x + d` | 同类日期时间 | 同类date | 由x.__add__处理 | Delta | Delta，d绝对优先 | NumPy先转换，单位决定date/datetime/错误 | NumPy先转换，us可成功，ns/Y/M等可能int→错误 | 同上 |
| `d - x` | 不支持 | 不支持 | Delta | Delta | Delta | 不支持；NumPy也可能参与反射 | 转td→Delta | 同上 |
| `x - d` | 同类日期时间 | 同类date | 由x.__sub__处理 | Delta | Delta | NumPy先转换，单位决定 | NumPy先转换，单位决定 | 同上 |
| `d == x` | NI后通常False | NI后通常False | 15字段 | 有条件总us相等 | 转Delta后比较 | NI后通常False | 内核转td比较；单位/异常影响 | 直接NI；表达式通常False |

K01/K02 的真实应用顺序：

1. 年：选择绝对year或原year，再加相对years。月：选择绝对month或原month，再加months并进位年份。日：绝对day或原day。此处最终有效day尚未创建对象。
2. datetime 各时间域选择绝对值或原值，加相对值，从us向day依次进位；date把其时间基准视为0，将绝对/相对时间和折成微秒，向下整除一天，仅取日进位，仍返回date。
3. 若有relative day或weekday，先用 `ymd_to_ord` 对日期日号进行月底clamp，再加day；最后 `new_ord += weekday - current_weekday`，从当前周内可向前/后，不是dateutil“下一个第n个weekday”。转换回年月日。
4. 若所有最终字段未变，`date_fr_date`/`dt_fr_dt` 保留对象identity（同类时返回原对象）；否则最后clamp day，调用原类构造器。datetime 原 `tzinfo`、`fold` 原样带入，不做UTC换算或DST合法化。

必须对比的具体边界：2024-01-31+months1→2024-02-29；再加days1→2024-03-01；2024-02-29+years1→2025-02-28；星期日+weekday0→同周星期一；date+1us仍当天，date-1us前一天；datetime.min-1day→ValueError `year 0 is out of range`；datetime.max+1us→ValueError `year 10000 is out of range`。DST例：NY 2024-03-10 01:30+1h保留02:30-05:00这个不存在的墙钟时间；2024-11-03 01:30 fold1+1h仍携带fold1。不能使用chrono时间线加法或自动tz.normalize替换这一语义。

子类构造失败：D 的docstring承诺可能回退，但U:2686–2690 / 3085–3099 **捕获Exception并抛带cause的ValueError**；本机 `RejectDate/RejectDatetime` 探针已验证。迁移保留真实结果。Pydt/pandas/Pendulum只作为输入类型/返回类型验证，不为迁移这些类建立实现任务；Pendulum尚未安装或运行，T提供补充用例，未来单独固定测试依赖。

## 6. 11 个 Cython 内部方法与必要内核

这些 cdef 方法没有普通Python可调用入口，不算公开Python方法；但 X 是已分发的声明文件，外部 Cython 项目可以依据它进行编译。它们不能自动映射为旧ABI。

| 内部签名（无默认参数） | 行号 | 依赖与职责 | Rust迁移方向 / 验收 |
| --- | --- | --- | --- |
| `_add_date(self, datetime.date o) -> datetime.date` | D:411–440；X:28 | U.date_add_delta；传原子类 | `delta.rs`桥接K01；date±1us、月底、identity |
| `_add_datetime(self, datetime.datetime o) -> datetime.datetime` | D:444–473；X:29 | U.dt_add_delta | 桥接K02；tzinfo/fold、子类失败cause |
| `_add_timedelta(self, datetime.timedelta o) -> Delta` | D:477–504；X:30 | Cython o.day/o.second/o.microsecond是C域读取，非Python singular属性 | 提取Python days/seconds/microseconds或C API；与pd.Timedelta比对 |
| `_add_delta(self, Delta o) -> Delta` | D:508–534；X:31 | 相对相加，右绝对优先 | 7相对+8absolute字段逐项；重normalize |
| `_sub_timedelta(self, datetime.timedelta o) -> Delta` | D:600–627；X:33 | 相对相减，self绝对保持 | 保留timedelta内部标准日秒us；负td边界 |
| `_sub_delta(self, Delta o) -> Delta` | D:631–657；X:34 | 左绝对优先，未设置补右 | 特别测试每个absolute字段填充 |
| `_rsub_date(self, datetime.date o) -> datetime.date` | D:699–728；X:36 | K01，relative符号反转absolute保留 | 非交换；date-year/month等完整组合 |
| `_rsub_datetime(self, datetime.datetime o) -> datetime.datetime` | D:732–761；X:37 | K02，relative反转absolute保留 | 不能直接用rd或timedelta简化 |
| `_rsub_timedelta(self, datetime.timedelta o) -> Delta` | D:765–792；X:38 | o-self相对量，self绝对保留 | td - Delta带absolute结果 |
| `_eq_timedelta(self, datetime.timedelta o) -> bint noexcept` | D:902–937；X:40 | 无年/月/绝对才比较i64 total_us | 大days乘86,400×1e6溢出待决；普通正负td完全一致 |
| `_eq_delta(self, Delta o) -> bint noexcept` | D:942–964；X:41 | 15字段逐个eq，不比较hash缓存 | 同字段不同缓存仍eq |

模块内部 `_delta_fr_relativedelta(rd) -> Delta` 位于 D:34–73，唯一参数无默认值；是 cfunc，未列于 X。保持为Rust内部函数，不新增同名PythonAPI。weekday名常量 D:28、X:6 也不另算方法。

| 内核 ID | 冻结具体范围 / 输入输出 | 迁移限界、依赖与验收 |
| --- | --- | --- |
| K01 date应用 | U:2952–3059 `date_add_delta(date, 19个同类相对/绝对参数, dclass=None)->date`；U:2675–2691,2890–2904创建/identity | Rust calendar整数计算 + Python类构造；仅此可达子集，不迁移所有date工具；负时间向下进日 |
| K02 datetime应用 | U:3900–4032 `dt_add_delta(dt,19参数,dtclass=None)->datetime`；U:3063–3100,3783–3800 | 原tzinfo/fold；不调用时区解析工具；月底、carry、identity、Exception→ValueError cause |
| K03 Gregorian | U:1995–2015闰年；2085–2099年之前天数；2197–2238月天数/之前天数；2362–2432 ord双向 | 4/100/400规则，允许中间year0和负年份以形成最终Python错误；Rust i128中间值但溢出策略单列；1900/2000、年1/9999边界 |
| K04 absolute ms/us | U:2637–2671 `(int ms,int us)->int` | 仅合并此逻辑；A18–19逐分支 |
| K05 类型检查 | U:2709–2729、3123–3143、4685–4705、5326–5344、5484–5502 | CPython实例/精确类型以及np标量判断；先datetime后date；不按属性duck type；基本、子类、伪对象 |
| K06 NumPy datetime | U:5347–5441；dt64_to_dt(dt64,tzinfo=None,dtclass=None)调用dt64_as_int64_us，再U:3684–3697 / dtm_fr_us | ns向下整除1000；us/ms/s/m/h/D/W比例；M/Y按1970的实际calendar；不迁移ndarray内核 |
| K07 NumPy timedelta | U:5505–5657；td64_to_td(td64,tdclass=None)→U:4799–4816 | ns向下整除；Y平均365.2425天、M平均30.436875天，不是日历月/年；Y/M整数精确比例后标准td |
| K08 Python异常 | E:18–36、117–148 | `rstimes.errors`保留cyTimesError、cyTimesTypeError、DeltaError、InvalidRelativeDelta的类名与MRO（包名必要变化）；无需搬Pydt/Parser错误全集；构造器TypeError/OverflowError等为builtins |
| K09 Python数值转换 | C:103084起、103403起、104881–104904 | 有nb_int才转，错误结果类型传播；PyO3转换需要兼容层；19参数逐一应用，顺序一致 |

## 7. NumPy 不能只测一条“支持”

冻结环境：CPython 3.13.3、NumPy 2.5.3、pandas 2.3.3、dateutil 2.9.0.post0，详细依赖版本见P.environment。以下是P具体观察，不推广到未跑过的版本。

| 项目 | 已确认事实 | 源码 / 验收要求 |
| --- | --- | --- |
| `d + np.datetime64` | 即使Y/M/D等也先走K06并得到naive datetime | D:402–403；测13种unit，正负、1970前后 |
| `np.datetime64 + d` / `- d` | Y/M/W/D可能先转date，h/m/s/ms/us转datetime；ns/ps/fs/as转int后抛TypeError；与正向结果类型不同 | D:565–571注释，T:309–319，P各unit radd/rsub；保持真实调度，不能用新ufunc覆盖 |
| `d ± np.timedelta64` | us可精确到微秒，ns=-1向下到-1us；Y/M转平均时长 | D:404–405,593–594；K07；正负1ns、±1Y/M |
| `np.timedelta64 ± d` | NumPy先转Python对象；us可成功，ns以及Y/M可能先变int而失败 | T:346–353；P各unit；测试直接dunder与表达式不同 |
| ps/fs/as正向 | K06/K07不支持，错误辅助U:5450把type赋给str，当前wheel实际TypeError `Expected str, got type` | 不能按注释擅改ValueError；P np:*:ps；登记旧错误消息 |
| NaT | 未显式识别NaT sentinel；dt64 NaT[us]抛year -290308 ValueError；NaT[ns]被当1677日期；td64 NaT被当巨大负时长 | P NaT两units；不得默认为None/NaT传播；兼容或明确批准偏差 |
| 多倍unit | 直接读取unit enum和raw tick，忽略dtype multiplier；3个`timedelta64[2D]`被当3天 | U:5358–5362,5515–5519；P np:multiplier；不要直接astype后改变为6天 |
| ndarray/Pddt | Delta没有专门ndarray向量入口；NumPy fallback可能触发ufunc错误 | P np:array；本轮不增加vector API、Pddt实现或`__array_ufunc__` |

未来选择numpy crate C API或Python标量属性提取时，要特别验证raw tick、unit multiplier、NaT及反向运算进入PyO3槽的方式；普通`astype('us')`替换会修正旧行为，从而产生未批准偏差。

## 8. 比较、hash 与可变性：已确认的缺陷不能暗改

P `hash:td` 在同一进程记录：`Delta(days=1) == timedelta(days=1)` 双向True，hash分别为3367730990640253590与7839147235533974352；set长度2，`{Delta(days=1):'x'}.get(timedelta(days=1))`失败。`hash:rd` 同样双向eq True，但dateutil对象hash不同。整数hash值不是跨Python版本硬编码规范，验收比较同进程对象/tuple算法和集合表现。

P `hash:external-pair` 还确认原生 timedelta 与 relativedelta 本身不相等且hash不同。Delta能等于两者，因此只把Delta hash改成timedelta hash不能满足与relativedelta的相等hash要求；不能仅“换hash”宣称修复。默认基线保留D:875–1048的eq与hash行为，修复必须另立方案（限制跨类型eq、取消hash、或更广契约变化）并明确批准，不能由迁移顺带实施。

“只读属性”不意味着不可变：M01可重初始化，且Cython自动`__setstate__`直接写16个内部槽。P `state:cached-hash` 把已hash对象days1改成days2，同时保留旧缓存；它等于新Delta(days2)，但hash又不同。未来不能未经批准采用 `#[pyclass(frozen)]` 并移除可观察重初始化/恢复状态行为。原`__init__`会重置缓存，`__setstate__`则恢复传入缓存。Rust安全内存实现也必须明确处理这一逻辑差异。

Delta的eq宣称“加任何日期结果一致”也只是说明文字：转换会丢掉rd.weekday.n、leapdays；NaT、超大i64 total_us另有异常。验收以已冻结字段/实际调用为准。

## 9. Cython生成接口、继承与序列化

| ID / 接口（不与源码自有项重计） | 实际调用/行为 | 证据 | Rust/PyO3迁移与对比 |
| --- | --- | --- | --- |
| G01 `__new__(cls, *args, **kwargs)` | 分配零初始化C槽，未执行M01；raw absolute全部0、hashcode0；传years=2也不在此初始化 | C的tp_new；P new:raw / raw-args | PyO3通常new同时初始化，需单独探明allocation/init实现；不能使raw对象自动得到-1 sentinel而称完全一致 |
| G02 `__ne__(self,o,/)` | 生成richcompare；Delta eq的反逻辑，不支持直接NI | P edge:ne-direct / protocol:ne；C richcompare槽 | 单独核对反射顺序；不是新增源码方法 |
| G03 `__lt__(self,o,/)` | 直接NI；表达式同Delta间TypeError | P edge:lt-direct / protocol:lt；C richcompare槽 | 保持不提供排序；错误文本包名边界 |
| G04 `__le__(self,o,/)` | 未实现排序，生成槽返回NI | C richcompare槽 | 两方向<=、自定义对手反射方法 |
| G05 `__gt__(self,o,/)` | 同上 | C richcompare槽 | 两方向> |
| G06 `__ge__(self,o,/)` | 同上 | C richcompare槽 | 两方向>= |
| G07 `__reduce__(self)` | 与`__reduce_cython__`同一恢复协议，当前正常Delta返回3元reduce | C:94517–94856；P reduce:* | PyO3显式恢复函数与state；新模块rstimes.delta；测试内容、结果类型与状态 |
| G08 `__reduce_cython__(self)` | 同上，反射可见`(self)` | C:94517起；P method-signature | 保留兼容别名的可调用行为；不强求CyFunction二进制类型 |
| G09 `__setstate__(self, __pyx_state)` | 按16元状态写所有C字段，子类可附第17项dict；返回None，不自动normalize或清hash | C:94893–95013,95279起；P state:* | 逐字段范围转换与mutation；不能把state简单当19参数重新构造 |
| G10 `__setstate_cython__(self, __pyx_state)` | 同上，反射可见`(self,__pyx_state)` | 同G09 | 保留别名；正常/短tuple/类型非法异常要继续冻结 |
| H01 `__str__(self)` | 继承object，显示M11 repr | P protocol:str | 保持str==repr，不编一个独立格式 |
| H02 `__reduce_ex__(self, protocol)` | 继承object，调用reduce；本轮0..5协议均往返成功 | P pickle:* | 新包各支持协议、copy/deepcopy、子类dict；不计自有接口 |
| H03 `copy.copy/deepcopy` | 没有自有`copy`、`__copy__`、`__deepcopy__`；通过reduce返回同类副本，子类与dict可保留 | P copy:* / reduce:child | 增补identity不同、dict深复制及hash缓存验收；不能称“copy方法已迁移” |
| H04 类型/存储 | 允许Python子类；基础对象无__dict__、无weakref；私有字段不暴露；子类可有dict | C BASETYPE/getsets；P protocol:* | `#[pyclass(subclass)]`及Python子类验证；基础不启用dict/weakref；内部runtime borrow机制差异需验收 |

Cython normal reduce state顺序为：`(_day, _days, _hashcode, _hour, _hours, _microsecond, _microseconds, _minute, _minutes, _month, _months, _second, _seconds, _weekday, _year, _years)`。和构造器顺序不同，且包含hash缓存。当前生成恢复函数为 `cytimes.delta.__pyx_unpickle_Delta(__pyx_type, __pyx_checksum, __pyx_state)`，校验值 `0x845247f`（十进制138749055），C:95033–95275还接受 `0xeaaf4e2`、`0xce9f7dc`；有dict时附到state末尾。本次普通Delta/Child实际reduce都是“恢复函数(type, checksum, None) + state”3元形态，协议0..5均成功。

旧pickle的全局引用明确写入 **`cytimes.delta` 的 Delta 和 __pyx_unpickle_Delta**。仅安装rsTimes不能让Python自动读取它。建议后续提供显式、受限class/global映射的迁移读取器，或保持cyTimes安装进行一次转换；是否要兼容`pickle.loads(old_bytes)`自动透明读取，由维护者决策。不得向sys.modules注入cytimes来劫持共存安装。新rsTimes pickle应引用rstimes.delta并独立往返；不同包pickle字节不可能完全相同，必须单列批准边界。

## 10. 模块导出与 C ABI 边界

正式导出 D:23 `__all__=['Delta']`；原根包 `cytimes.__init__.py:3` re-export。目标必须提供 `from rstimes import Delta`、`from rstimes.delta import Delta`，二者同一类，`Delta.__module__='rstimes.delta'`，Rust文件名 **delta.rs**，类名 **Delta**。根包原有to_unix_ms/from_unix_ms保留。

冻结wheel还发现由U中cpdef意外进入delta模块的两个可调用函数，未在D.__all__/I中声明。不能把它们算入Delta方法统计，也不能假装未发现：

| 模块项 | 实际签名 / 语义 | 路径行号 | 方向与验收 |
| --- | --- | --- | --- |
| `delta.parse_to_int(token)` | str参数必需；前导非数字忽略、符号须在数字前；空/无ASCII数字→0；数字后非数字→ValueError；64位累加无溢出检查 | U:1438–1523；P module:parse_to_int:* | 若要求所有可观察函数一致，保留这个小兼容函数，不迁移Parser全库；测试None、非str、a-12、12a、unicode数字、超长溢出另登记 |
| `delta.parse_to_float(token)` | str参数必需；一个点、点前符号；整/小数累加后double，空/无数字→0.0，不支持科学计数；无完整溢出检查 | U:1525–1641；P module:parse_to_float:* | 若纳入兼容，同文件或必要私有utils核；不得用Python float(token)替代；1.25、1e2、1..2、负号/点顺序、精度 |

模块中 `datetime`、`relativedelta`、`Self`、`errors`、`utils` 是import残留；不会因此迁移完整utils公开集合。`__pyx_unpickle_Delta`虽下划线开头却属于序列化可观察入口；`__pyx_vtable__`属于Cython实现对象，PyO3不可原样复制。以上残留/意外函数的兼容范围见规划Q3，不会在本轮实施或擅自删除功能。

X:9–41公开了Cython cdef class布局（15字段+hash缓存）与11个cdef方法，X:6还有tuple常量。PyO3不是Cython类型：旧 `cimport cytimes.delta.Delta`、对象布局、vtable、noexcept语义或依赖`.pxd`编译的二进制不能自动兼容。Python方法相同不代表C ABI兼容。未来若有外部cimport使用者，单独选择源码适配层、重新编译或新C API，不在Delta Python迁移验收中虚报“1:1 C ABI完成”。

包名导致的异常差异必须按位置批准：unsupported operand/read-only/no-private-attr文本中的`cytimes.delta.Delta`可对应`rstimes.delta.Delta`；InvalidRelativeDelta异常模块可变为rstimes.errors，但类名、MRO、消息`<'Delta'> ...`与cause仍需一致。自定义对手类名、参数名、异常原因不能用全局字符串替换掩盖。

## 11. 尚待契约阶段完成的精细调查

发行测试覆盖也有明确缺口：T:73–198主要随机对比dateutil，失败范围常被跳过；T:239–283检查跨类型eq但没有hash/set/dict；T:296–353覆盖子类和NumPy常见unit，但不含NaT、多倍unit、pickle或重新初始化。UP:600–614/680–722/780–811有Gregorian测试，UP:1625–1638/1663–1676用普通unit和-500..500值对比NumPy转换；UP:1167–1197测试的是dt_add，不等于完整dt_add_delta契约。它们必须补成确定、可复测的输入，不能声称“发布测试已有，所以边界都一致”。

另有解释器兼容缺口：冻结sdist及本机wheel的 `src/cytimes/__init__.py:3` 都是 `from datetime import UTC`，而 [Python官方文档](https://docs.python.org/3/library/datetime.html#datetime.UTC) 标记UTC在3.11新增。由源码可推断，未经该文件适配的Python3.10安装会在根包import失败，尽管PyPI声明>=3.10。**本轮未运行3.10基准，也未下载3.10 wheel，不能说已验证那个wheel的安装行为。** rsTimes既有3.10支持要保留，后续报告须分开“rsTimes 3.10安装通过”和“相同解释器官方cyTimes oracle可运行”；不得修改冻结档或通过未注明的shim把3.10基准失败隐藏。

已保存全部轻量观察，仍需逐行生成差分case而非依靠514的数量：G04–G06直接/反向槽；所有G09/G10错误tuple与类型/关键字；raw __new__的identity/hash/copy；19参数数值转换对象异常和错误__int__返回；所有absolute字段在加减冲突的组合；dateutil子类normalized()回调失败/恶意返回的传播；自定义对手反射运算顺序；pandas纳秒残余与特殊NaT；Pendulum子类；CPython各目标版本消息；各平台i64溢出和pickle缓存跨解释器版本。

没有源码定义的 `normalize`、`replace`、`total_seconds`、`to_timedelta`、`to_relativedelta`、乘除/幂/排序、独立copy方法不能凭通用日期库常识编入实现需求。新增功能需独立任务和用户授权。
