# Pydt 使用说明

Pydt 是 `datetime.datetime` 的真正子类，保留标准日期类型的使用方式，增加日历调整、周期边界、查询和时区便利方法。它保存微秒，年份范围仍是1—9999；不会因为 Pddt 支持纳秒和宽年份，就改变这个范围。

```python
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from rstimes import Configs, Delta, Pydt

p = Pydt(2024, 1, 31, 12, tzinfo="Asia/Shanghai")
assert isinstance(p, datetime)
assert p.to_month(1).day == 29
assert p.tz_convert("UTC").hour == 4
assert p.weekday() == 2
assert p.day_of_year == 31
assert p.days_in_month == 31
assert p.is_leap_year is True
```

`weekday()` 保留标准 datetime 方法；day_of_year、days_in_month、is_leap_year 是只读属性。日期值不可变；低成本已知不变的操作可能返回原对象，不保证每个同值结果都有相同身份。

## 数值、None 与布尔

日期字段、日历数量、frommicroseconds、ordinal／ISO／年内日工厂、相对 offset、命名 add/sub、fsp 及整数条件查询使用整数协议。Python／NumPy 整数及合法 `__index__` 可用；float 即使是1.0、数字文本、仅 `__int__` 和布尔均不作为这些整数。

秒数工厂按其文档接受数值，仍拒绝 bool、字符串、bytes 和 bytearray。普通开关只接受 Python bool 或 numpy.bool_；不会把1、字符串或普通对象当真值。fold 是明确例外：整数协议0／1以及两种布尔可用。

可选字段省略／None 表示保留，数字表示明确修改；不再用0或负数表示“不改”。相对数量中的0和负数仍分别表示零移动和反向移动。

```python
p = Pydt(2024, 1, 31, 12, 30)
assert p.to_time(hour=0).hour == 0
assert p.to_date(day=None).day == 31
assert p.to_date(month=2, day=31).day == 29
# p.to_time(hour=25)        # ValueError
# p.add(months=1.5)        # TypeError
# Pydt.frommicroseconds(1.0)  # TypeError
assert (p + Delta(hours=1.5)).hour == 14
```

严格 replace 必须形成完整合法日期；便利 to_date／to_datetime 会把合法 day=31 适配到目的月份月底。weekday 选择用0—6，月份／星期未知或空名称报 ValueError。合法但不匹配的条件查询为 False。

`to_date(month=...)` 和 `to_datetime(month=...)` 的 month 是1—12的整数，None保留原值；不接受月份名称、浮点数或布尔值。例如 `p.to_date(month=2)` 选择二月，`month="February"` 报TypeError。`to_curr_year("February")` 等名称选择接口继续按各自文档使用。

## 创建与解析

|工厂|含义|
|---|---|
|now(tz=None)、today()|完整当地当前日期和时钟；today 不归零|
|utcnow()、utcfromtimestamp(ts)|带标准 UTC 的结果|
|fromtimestamp(ts, tz=None)|真实 UTC 纪元秒；目标为空时返回当地无区钟表|
|fromseconds(seconds, tz=None)|无区纪元钟表秒；目标时区只附加，不移动数字|
|frommicroseconds(us, tz=None)|同一钟表坐标的整数微秒|
|fromordinal(n)|1为0001-01-01，最终仍受Pydt年份范围限制|
|fromisocalendar(year, week, weekday)|周／星期低于1报错，过高取该ISO年实际末周／周日|
|fromdayofyear(year, doy)|doy低于1报错，过高取当年年末|
|fromdate(value, tz=None)|取年月日，时钟归零|
|fromdatetime(value, tz=None)|保真实日期时钟和输入fold；显式tz替换时区但保钟表|
|fromdatetime64(value, tz=None)|读取真实来源单位，最终取更早微秒，NaT报错|
|combine(date=None, time=None, tz=None)|各取日期和时钟；标量None提供今天／午夜|
|fromisoformat(text)|专用ISO语法|
|parse(value, ...)|共享普通Parser规则，返回本Pydt类型|
|strptime(text, fmt, cfg=None)|完整按共享格式规则读取文本|

```python
assert Pydt.fromseconds(0, "Asia/Shanghai").hour == 0
assert Pydt.fromtimestamp(0, "Asia/Shanghai").hour == 8
assert Pydt.frommicroseconds(-1).isoformat() == "1969-12-31T23:59:59.999999"
assert Pydt.fromisocalendar(2024, 53, 7).year == 2024

cfg = Configs()
cfg.add_month("harvest", 10)
assert Pydt.parse("14 harvest 2026", cfg=cfg).month == 10
assert Pydt.strptime("14 harvest 2026", "%d %b %Y", cfg=cfg).month == 10
```

fromseconds 和普通对象 parse 的浮点秒保留已确定的微秒换算：先按七位小数规则处理，再丢第七位。`parse_to_epoch` 的直接纳秒换算是不同出口，不把它的细精度规则套回 Pydt。

strptime 的数字、周历、月份／星期／AMPM、数字偏移和已配置时区采用同一套格式规则；%f可读更细小数，但最终Pydt只有微秒。%Z只接受Configs中明确的UTC词、固定偏移别名或登记地区，并附加对应时区；不自动采用本机缩写。普通数字格式不依赖本地语言。%c／%x／%X使用当前LC_TIME模板；宿主无法提供所需资料的格式会明确报错，不静默换另一种解释。

combine 的两侧可用已支持的完整来源，分别只贡献日期和时钟。time一侧的datetime可提供时区和fold；date一侧不替代它。合法子类和自定义构造／时区协议继续生效，原回调异常保留。

## 时区、fold 和有效当地时间

可传标准 tzinfo／timezone／ZoneInfo、已支持的地区名，或合法自定义tzinfo。真实pytz对象只按有效地区名转成ZoneInfo；无有效地区名报错。pytz不是必装依赖。本机地区只在实际需要时发现，成功后缓存；失败不会悄悄改成UTC。

Pydt严格创建、replace及相关工厂遇地区不存在时间会报错；fold只选重复时间的前后，不让缺失时间变合法。标准UTC、固定偏移和无区值没有地区缺口检查。

```python
ny = ZoneInfo("America/New_York")
first = Pydt(2024, 11, 3, 1, 30, tzinfo=ny, fold=0)
second = Pydt(2024, 11, 3, 1, 30, tzinfo=ny, fold=1)
assert first.utcoffset() != second.utcoffset()
# Pydt(2024, 3, 10, 2, 30, tzinfo=ny)  # ValueError: 不存在的当地时间
assert first.to_start_of("us") is first
```

便利日历移动先满足目标日期、方向和周期，重复时优先保原UTC偏移，没有匹配候选时按既定自动规则选有效结果。to_first_of／to_last_of保时钟，to_start_of／to_end_of取目标周期可表示边界；normalize留在本日。整个目标周期不存在时，要求构造的变换会报错；合法但不匹配的边界查询可以直接返回False。

`tz_convert(tz)` 保真实时刻；`tz_convert(None)` 转UTC后去区。`tz_switch(None)` 保当地钟表去区；无区转非空目标时需base_tz。`astimezone(None)` 使用本机地区；与其他各入口的None含义分开。

Pydt保留已有日历timedelta加法，直接交给外部 `ZoneInfo.fromutc(pydt)` 或显式标准 `datetime.astimezone` 描述符，可能与这个日历算术产生冲突。需要时区转换时使用Pydt自身的tz_convert／astimezone；不能把外部协议当成完全透明的等价入口。

## 日历、取整和查询

月份移动按目的月份取合法日，因此1月31日加一月再减一月可能是1月29日。绝对字段是设置指令，Delta含hour=9即使与自身相减也仍可保留这个设置。

`round(freq)` 中点取偶，ceil 向上、floor 向下，频率参数统一为freq。Snap是 `snap(unit="s")`：取最近有效周期起点，等距取较晚，独立于round的取偶规则。支持单倍Y／Q／M／W／D／h／m／min／s／ms／us、已保存月份／星期名称，ns是us别名；不支持任意多倍频率。`fsp(precision)` 截去多余小数秒，0清小数，6及更细的已有别名可保原值。

`days_in_*`、`days_bf_*`、`day_of_*` 查询日历位置；上面列出的三个日期访问使用属性，其他自有查询保持各自方法。isocalendar是标准ISO周历三元结果，isoyear／isoweek／isoweekday取单项。未知／空月份和星期名称报错；合法不匹配返回False。

`diff(value, unit, absolute=False, inclusive="one")` 统计跨过的边界，支持Pydt精度范围中的单位，不支持真正纳秒。整数日历桶可以计算合法UTC换算跨出的0／10000年，不先构建范围外Pydt。

## 相减、秒／微秒输出、状态

普通datetime比较、哈希和相减沿Python标准规则。同一tzinfo对象的相减按钟表差，忽略fold；需要真实经过时长可先都转UTC。pandas Timestamp保真实字段和纳秒到最后，日期差返回标准timedelta，最后一次舍入到最近微秒、恰好一半取偶数；比较不先舍入。

```python
wall = Pydt(1970, 1, 1, 8, tzinfo="Asia/Shanghai")
assert wall.toseconds() == 28800.0
assert wall.toseconds(utc=True) == 0.0
assert wall.tomicroseconds() == 28800000000
assert wall.tomicroseconds(utc=True) == 0
```

这两个输出默认是当地钟表坐标；utc=True才使用真实UTC纪元。timestamp()是另一种真实时间点出口，不要与默认钟表坐标混淆。

复制和pickle保日期及合法dict／slots附加状态，遵循真实业务钩子和memo／别名规则，不通过重新init修改原对象。公共错误给出真实入口和失败字段；自定义构造、字段和时区回调的原异常继续保留。
