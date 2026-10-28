# Pddt 与 parse_to_epoch

Pddt 是真正的 pandas `DatetimeIndex` 子类，提供与 Pydt 对应的日历操作，并保留一列数据、缺失值和纳秒精度。使用 Pddt 需要安装 pandas；传入 Polars 列时才需要 Polars。Delta、Parser 和 Pydt 可单独使用，不要求这两个可选依赖。

本轮重新设计了 Pddt，旧参数名、旧多位置构造写法和旧 Pddt pickle 格式不继续适配。构造和自有日期操作采用固定 pandas 3.0.6 所代表的默认规则，在已验证的 pandas 2.x 环境也保持这些规则。排序、切片、集合、比较、`take` 和 `repeat` 等完整继承的操作，继续使用实际安装的 pandas 行为。

## 输入与单位

```python
from datetime import date, datetime, time, timedelta, timezone
import copy
import pickle
import numpy as np
import pandas as pd
from rstimes import Configs, Delta, Pddt, Pydt, parse_to_epoch

x = Pddt(["2024-01-31 12:30", "2024-02-29 09:15", None], unit="us")
assert x.unit == "us"
assert x.isna().tolist() == [False, False, True]
```

普通构造只接受一维集合。list、tuple、一次性迭代器、一维 NumPy 数组、pandas Index／Series／相应扩展数组，以及已支持的 Polars 列均可使用；顺序保持，二维输入报错，不自动展平。集合中可混合合法日期文本、date／datetime／Pydt／Timestamp、NumPy datetime64 和数值。标量请写成 `[value]`，或使用对应命名工厂。

|来源|未显式指定 unit 时|
|---|---|
|普通日期时间文本、Python datetime|通常 us；文本声明更细小数秒时保留 ns|
|Python date、空输入、普通仅缺失列表|s|
|原生 datetime64 数组、DatetimeIndex、Polars Datetime|保留支持的 s／ms／us／ns 单位|
|带单位的 NumPy NaT|保留其可支持的来源单位|
|普通整数／整值浮点刻度、数值数组|ns；日期缓冲中的 -2**63 表示 NaT|

`unit` 支持 `"s"`、`"ms"`、`"us"` 和 `"ns"`。构造时显式指定单位必须准确保存来源精度；原数据有非零细尾数而目标单位不能保存时，报 ValueError。目标容量不足报 OverflowError。普通日期操作始终保留当前单位，不自动升细或退到微秒。

```python
nano = Pddt(["2024-01-01 00:00:00.123456789"], unit="ns")
coarse = nano.as_unit("us", round_ok=True)
assert coarse.unit == "us"
# nano.as_unit("us", round_ok=False)  # ValueError: 非零纳秒尾数不能无损保存
assert Pddt(np.array([-1500], dtype="datetime64[ns]")).as_unit("us").asi8.tolist() == [-2]

seconds = Pddt(["2024-05-07 09:30:00"], unit="s")
# seconds.add(milliseconds=250)  # ValueError: 请先显式选择更细单位
assert seconds.as_unit("ms").add(milliseconds=250).millisecond.tolist() == [250]
```

`as_unit()` 默认 `round_ok=True`，明确允许本次转换舍去细尾数，取更早刻度，因此 -1500ns 变成 -2us；False 要求无损。这个参数不放宽容量和整数安全限制。

裸数字是所选单位的刻度。秒数工厂和整数解析出口则有各自明确的输入单位：

```python
assert Pddt([1], unit="ms").asi8.tolist() == [1]
assert Pddt.fromseconds([1], unit="ms").asi8.tolist() == [1000]
assert Pddt.frommicroseconds([1], unit="ns").asi8.tolist() == [1000]
assert parse_to_epoch(1, unit="ms") == 1000
assert parse_to_epoch(1e-9, unit="ns") == 1
```

布尔不是日期或数值。普通整数刻度允许已支持的整值浮点数，如 1.0；1.5 不是整数刻度。微秒、序号、日历字段、数量和命名 add／sub 等整数参数接受整数及合法 `__index__`，拒绝 float，即使它是 1.0。

## 解析、Configs 和 default

`Pddt(data, ...)` 与 `Pddt.parse(data, ...)` 使用相同的文本规则。关键字为 `default`、`yearfirst`、`dayfirst`、`isoformat`、`strict`、`cfg`，另有 `unit`、`tz`、`name`、`copy`、`freq` 和数组本地化策略。Pddt 不提供 `ignoretz` 或 `dtclass`：已识别的时区会保留，`tz` 表示目标时区。

`yearfirst/dayfirst` 的明确非 None 值优先于 Configs，无配置时分别为 True／False。`isoformat=True` 表示优先尝试 ISO，仍可使用通用语法；严格 ISO 输入可用 `fromisoformat()`。`strict=True` 检查明确字段的非法值和冲突，False 沿用已确定的宽松解析规则。它不是把所有错误变成缺失的开关，也不决定 DST 策略。

```python
cfg = Configs()
cfg.add_month("mymonth", 2)
assert Pddt(["29 mymonth 2024"], cfg=cfg).month.tolist() == [2]
cfg.add_tzone("Asia/Shanghai")
regional = Pddt(["2024-01-02 12:00:00.123456789 Asia/Shanghai"], cfg=cfg)
assert regional.unit == "ns"
```

地区文本只接受在 Configs 中登记的完整名称；未登记的明确地区格式会提示 `add_tzone()`。显式 `tz="Asia/Shanghai"` 或已有日期对象的时区不需要登记。普通词条保持现有保存的大小写形式，不为每次调用自动增加任意拼写。

`default` 必须能独立解析成完整年月日，可用完整 date／datetime 及真实子类、完整日期文本、既有数值纪元秒或 NumPy datetime64。它只补缺失的年月日，不继承时分秒或时区；完整零年不被 default 覆盖。未使用的 default 不会被无关原生输入触发。Pddt 的数组 DST 策略优先，`default.fold` 不替代它。

## 时区与 DST

|调用|含义|
|---|---|
|无区字段加目标 tz|保钟表数字，在目标地区解释|
|已有时刻加目标 tz／tz_convert(tz)|保真实时刻，换目标地区显示|
|fromdatetime(..., tz=...)／replace(tzinfo=...)|保钟表数字，重新解释目标地区|
|tz_localize(None)|去掉时区，保当地钟表|
|tz_convert(None)|先转 UTC，再去时区；来源须有区|
|tz_switch(None)|去区，保当地钟表|
|astimezone(None)|转到本机地区；无区来源按本机解释|

没有目标 tz 时，混合不同地区、不等固定偏移，或混合有区／无区的有效输入会报错，提示指定目标。不会猜第一行时区或退成 object 列。

构造、parse、严格 replace、tz_localize 及需要解释当地字段的命名工厂接受：

- `ambiguous="raise"`（默认）、`"NaT"`、`"infer"`，或 Python／NumPy 真布尔标量及一维等长真布尔列。True／False 按 pandas 的真实候选规则选择，不可简单等同“总是较早／较晚”或“是否夏令时”。布尔列对应全部输入位置，包含原 NaT。
- `nonexistent="raise"`（默认）、`"NaT"`、`"shift_forward"`、`"shift_backward"`，或统一 timedelta／pandas Timedelta。前后移动选缺口最近有效边界；纽约 02:30 的 shift_forward 是 03:00，显式 timedelta(hours=1) 才是 03:30。

`infer` 使用输入原顺序推断；证据不足会报错，不排序、不猜。策略 NaT 只处理对应 DST 问题，普通坏文本仍报错。不增加 Pddt.fold，也不让 time.fold／default.fold 覆盖数组策略。

```python
local = Pddt(["2024-03-10 02:30"], tz="America/New_York", nonexistent="shift_forward")
assert local.hour.tolist() == [3]
assert local.minute.tolist() == [0]
```

`to_*`、normalize、周期边界、round／ceil／floor 和 snap 使用自动有效时间规则，不接受两种显式策略。它们先保持操作方向和目标周期，再参考原偏移选重复时间；整个目标周期不存在时会报错，不跳到别的周期。无时区、标准 UTC 和标准固定偏移不需要地区重复／缺口检查。

## 字段、逐行目标和日历算术

```python
x = Pddt(["2024-01-31 12:30", "2024-03-31 09:15"], unit="us")
assert x.to_date(month=2, day=31).day.tolist() == [29, 29]
assert x.to_date(day=[1, None]).day.tolist() == [1, 31]
assert x.add(months=[1, 2]).month.tolist() == [2, 5]
assert x.replace(day=28).day.tolist() == [28, 28]
# x.replace(month=2)  # ValueError: 严格替换不生成2月31日
```

省略／None 表示保留可选修改字段；0 或负数不再表示“不改”。时钟零有效，Pddt 的零年和负年也是真实年份。`replace` 要求完整合法日期；便利 `to_date/to_datetime` 仍把合法 day=31 适配到目的月份月底。普通月份／星期选择保各自名称和范围规则。

支持逐行目标的方法使用统一一维容器和等长位置配对，不按 pandas 标签对齐，不接受只有一个元素的列作为广播。标量可广播；所有字段列长度都要与日期列匹配。字段列中的 None 表示保留，查询目标中的缺失则报 TypeError，即使该行来源为 NaT。`fsp` 和 round／ceil／floor 的精度／频率仍为统一标量，不逐行变化。

命名 `add/sub` 和相对 offset 只收整数；小数时长使用 Delta 或实际时长对象。日历移动与实际经过时长分开：

```python
x = Pddt(["2024-03-09 12:00"], tz="America/New_York")
calendar_next = x + Delta(days=1)
elapsed_next = x + timedelta(days=1)
assert calendar_next.hour.tolist() == [12]
assert elapsed_next.hour.tolist() == [13]
```

Delta 按共同日历规则，timedelta／Timedelta／numpy.timedelta64 按真实经过时长。匹配的时长列、真实 Delta 列按位置处理；日期相减返回 pandas TimedeltaIndex，保较细来源单位。已有 pandas DateOffset 的成熟用途完整委托，不为它套本库的额外整数限制。普通 relativedelta 不新增支持，可明确先转换成 Delta。

Delta／timedelta 的真实子类如果覆盖相应算术协议，整列调用也会执行其规则，而不是只读取父类中保存的时长。需要回调时，单行日期以保留原精度的 pandas Timestamp 提供；普通值和未覆盖运算的子类仍使用原生计算。回调应返回合法日期；原回调异常保持原对象，不交付部分成功的日期列。

## 周期、取整、查询与 diff

`to_first_of/to_last_of` 选周期首末日并保时钟；`to_start_of/to_end_of` 选可表示首末时刻。四个 is_* 查询使用相同边界定义，合法但不匹配为 False；未知／空名称报 ValueError。

`round(freq)` 中点取偶，ceil 不更早，floor 不更晚，支持 `"15min"`、`"500ns"` 等正固定频率。Snap 使用 `snap(unit="s")`，取最近有效周期起点、等距取较晚；支持单倍年／季度／月／周／日、原生时钟精度及已保存月份／星期名，不支持任意多倍频率或业务日历。`fsp(precision)` 明确截去更细小数秒。

日历整数查询和 isoyear／isoweek／isoweekday 返回可空整数 Index；NaT 变为 pd.NA。自有布尔查询在来源 NaT 处为 False。标准 pandas 日期属性保标准结果形式；year 对宽年份避免32位回绕。`isocalendar()` 保 year／week／day 三列 UInt32，真实 ISO 年超出此表容量会报 OverflowError，可改用 signed `isoyear()`。

```python
x = Pddt([np.datetime64(2, "s")])
assert x.diff(1, "s").tolist() == [1]
assert x.diff([1], "s").tolist() == [1]
```

`diff(dtobj, unit, absolute=False, inclusive="one")` 统计跨过的日历／刻度边界，不是把时长相减再除。数字目标统一表示秒；支持标量或等长目标。无区使用无区坐标，有区使用 UTC 边界，两类混用报错。`one` 保原差；`both` 增大一个单位的幅度，`neither` 减少一个；零差的 neither 为 -1，absolute 先于 inclusive。完整 int64 包含 -2**63 可作为真实整数差，不与日期 NaT 混淆。

批量输入失败时，错误说明会保留已知的字段和位置，例如 `dtobj[1]` 或 `days[2]`。迭代器自身读取失败时会说明正在读取的位置；用户回调的异常类别、对象和原因链不因此被改写。

## 工厂、格式与范围

标量命名工厂须给 size；集合省略 size。多字段工厂允许标量广播和等长列。now／today 保完整当前时钟，utcnow 带 UTC；非空整次取一次系统时钟，重复同一数值。指定 ns 保系统真实可得尾数，单位不代表系统有1ns准确度；指定较粗单位可直接取当前刻度。

标量来源的时区不会因 `size=0` 丢失。例如 `Pddt.fromdatetime(datetime(2024, 1, 1, tzinfo=timezone.utc), size=0)` 返回带 UTC 的空列；fromisoformat、strptime 和 combine 同样保留可确定的来源时区。支持显式目标时区的工厂仍以目标为准。

`fromseconds/frommicroseconds` 是纪元钟表坐标并可附区，`fromtimestamp/utcfromtimestamp` 是真实时刻。fromdate 只取年月日，fromdatetime 保日期时钟，fromdatetime64 读取真实来源精度。ordinal 允许零／负连续日坐标；ISO周、ISO星期和年内日低于1报错，过高取该年实际上界。Pddt 年份不套 datetime 的1—9999范围。

`strptime(data, fmt, cfg=None, ...)` 使用共享格式规则，完整匹配；`%f` 支持九位，并按格式规则在最终选定单位截去更细位，不为它另加 `%N`。月份／星期／AMPM 用默认或显式 Configs；`%Z` 只认明确 UTC词、固定别名和登记地区，成功附加时区，不自动猜本机 CST。

格式中的数字也按字面量匹配。例如 `Pddt.strptime(["2024001"], "%Y0%m")` 表示2024年一月，格式中的0不会被读入年份。有明确非数字分隔时，仍可按目标单位解析零年、负年和宽年份。

`date_range` 自身支持已确认的固定／日历频率与 start/end/periods 组合，包括 freq=None 的等分。特殊业务规则或自定义 DateOffset 使用 pandas 的完整成熟协议。它们的结果也必须遵守本次明确单位和容量；不能用宽松回退掩盖非法参数。

显式 `unit` 必须能无损保存所提供的两个端点，即使某个端点不在最终结果中或结果为空。比如 `end="1970-01-01 00:00:01.5"` 配合 `unit="s"` 报ValueError，可改用 `unit="ms"`。`normalize=True` 明确先将端点时钟归零，再检查单位精度。

这里检查的是时区解释后的实际存储刻度。当地字段可能需要更细的中间精度，但只要与时区偏移抵消后的 UTC 端点能由显式 unit 准确保存，就可构建；最终输出单位不会自动改变。原生频率和明确委托的成熟频率使用相同规则。

## 输出、复制与保存

`toseconds(utc=False)`／`tomicroseconds(utc=False)` 导出当地钟表坐标，utc=True 则先按真实时刻换 UTC。`timestamp()` 是真实纪元秒；无区日期需要按本机解释，遇重复／缺口时提示先显式本地化。

`datetime()` 最后生成 Pydt 对象数组；微秒之后取更早边界，合法时区／fold 保留。超 Pydt 年份范围会在此出口报错。`date/time/timetz` 保各自标准含义；`isoformat(sep="T", timespec="auto")` 保纳秒和完整偏移，支持 hours／minutes／seconds／milliseconds／microseconds／nanoseconds 及 h／m／min／s／ms／us／ns 缩写。`timedf/utctimedf` 返回固定九字段的可空整数表。

```python
wall = Pddt(["1970-01-01 08:00"], tz="Asia/Shanghai")
assert wall.toseconds().tolist() == [28800.0]
assert wall.toseconds(utc=True).tolist() == [0.0]
assert wall.tomicroseconds(utc=True).tolist() == [0]
y = pickle.loads(pickle.dumps(wall))
assert y.asi8.tolist() == wall.asi8.tolist()
```

copy.copy／copy(deep=False) 新外壳按安全规则共享日期缓冲，业务 dict／slots 保原引用；deepcopy／copy(deep=True) 独立日期缓冲并保共享别名和自身循环。pickle 使用新版本化核心格式，保合法业务状态、时区、单位、name 和有效 freq。真实自定义复制／保存钩子及其原错误保持，不重复业务 init，不迁移旧 Pddt pickle。
