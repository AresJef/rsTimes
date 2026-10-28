# Delta 使用说明

`Delta`保存相对增量和可选的绝对字段。本发行版本为`0.2.0b1`，范围见[发行说明](releases/v0.2.0b1.md)。安装及四个对照demo的环境准备见README；demo/runtime.json选择并验证已发行的wheel。

```python
from datetime import date, datetime, timedelta
from rstimes import Delta
from rstimes.delta import Delta as SameDelta
assert Delta is SameDelta

assert date(2024, 1, 31) + Delta(months=1) == date(2024, 2, 29)
assert datetime(2024, 1, 31, 12) + Delta(months=1, hour=9) == datetime(2024, 2, 29, 9)
```

## 构造、None与整数

相对参数为years、quarters、months、weeks、days、hours、minutes、seconds、milliseconds、microseconds；有符号数表示真实增减量，0表示零增量，不接受None。位置顺序中weeks在days之前，建议用关键字。

绝对参数用于设置字段，默认None。省略或None表示未设置，数字代表明确设置；不能再用0或负数表示跳过。

| 绝对字段 | 合法输入 |
|---|---|
| year、month、day | 正整数；高于9999、12、31仍取该上界，应用日期时保留月底处理 |
| weekday | 整数0—6，周一到周日 |
| hour | 整数0—23 |
| minute、second | 整数0—59 |
| millisecond | 整数0—999 |
| microsecond | 整数0—999999 |

绝对字段接受标准整数协议，包括NumPy整数；float即使为9.0也报TypeError。星期和时钟字段超过范围报ValueError，不再静默截取。极端整数及真实计算溢出报OverflowError。

```python
assert Delta(hour=None).hour is None
assert Delta(hour=0).hour == 0
# Delta(hour=-1)   # ValueError；请改为hour=None
# Delta(hour=9.8)  # TypeError；请传明确的整数
# Delta(hour=25)   # ValueError；小时只能0—23
```

weeks至microseconds这七个固定时长单位保留小数能力，合并后最后一次舍入到微秒，中点取偶。相对years、quarters、months要求整数协议，拒绝float（含1.0）和布尔；一年半请用months=18。相对增量会进位，绝对字段设置不会把超出范围的时钟变成下一天。

```python
assert Delta(hours=1.5) == Delta(hours=1, minutes=30)
negative=Delta(microseconds=-1)
assert (negative.days,negative.hours,negative.minutes,negative.seconds,negative.microseconds)==(-1,23,59,59,999999)
```

同时指定millisecond和microsecond时，毫秒部分由millisecond决定，microsecond只保留末三位。month/day调整仍有日历含义；1月31日加一个月再减一个月可能得到1月29日。

## 运算与比较

支持已约定方向上的Delta、timedelta、date/datetime、dateutil.relativedelta及NumPy日期/时长标量运算。返回类型、反向调用和用户子类构造沿各操作规则处理；不能把所有运算都理解成秒数加减。绝对字段按运算的左右优先级保留，因此Delta(hour=9)减去自身仍可包含hour=9。

只有同值域Delta参与值相等比较；跨类型比较返回NotImplemented，由Python决定最终结果。Delta(days=1)不再与timedelta(days=1)或relativedelta(days=1)相等。字段不变，对象哈希稳定，适合作为同类型字典/集合键；不支持排序。

from_relativedelta按来源实际日期含义转换，不机械套直接构造规则：来源year/month/day为0表示未设置，时钟0仍表示设置为0，过大的day保留其月底意义。不能准确表示的字段、非空weekday和非零leapdays明确拒绝，不能悄悄丢掉含义。

导入直接读取来源字段，不调用`normalized()`，包括子类自定义实现。支持的小数时长由Rust按与Delta构造相同的规则处理，避免分段舍入或直接截掉小数。真实子类的字段读取和数值转换错误正常传播。补偿年月先完成必要的进退位，再判断是否可表示，例如绝对10000年1月减一个月可以得到9999年12月。

来源子类的数值转换若改变了 weekday／leapdays，完成相关读取后仍会检查这两项；不能借转换回调将不支持的规则悄悄带入 Delta。这项检查不改变 Delta 自身的归一化规则，也不重放数值转换。

转换后得到的是Delta，遵循Delta自身的规则：date不会因为小时增量自动变成datetime，日期运算保留既定fold规则，绝对字段的减法也不承诺与原relativedelta的反向应用完全等价。需要来源完整行为时，直接使用来源对象。

```python
from dateutil.relativedelta import relativedelta
assert Delta.from_relativedelta(relativedelta(hours=1.5)) == Delta(hours=1, minutes=30)
assert Delta.from_relativedelta(relativedelta(year=10000, month=1, months=-1)) == Delta(year=9999, month=12)
start = datetime(2024, 1, 1)
assert start + Delta(hours=1.1, microseconds=-1.5) == datetime(2024, 1, 1, 1, 5, 59, 999999)
```

## 批量应用与固定时长

```python
assert Delta(days=1).apply_many([date(2024,1,1),date(2024,1,2)]) == [date(2024,1,2),date(2024,1,3)]
assert Delta(hours=25).to_timedelta() == timedelta(days=1,hours=1)
assert Delta(months=1).to_timedelta(date(2024,1,31)) == timedelta(days=29)
```

apply_many返回按原顺序排列的list，每项含义与value + delta一致；出错不返回部分结果。to_timedelta无起点时只转换可精确表达的固定时长；含日历年月、星期或绝对字段时需要起点，按(start + delta) - start计算。最终返回标准timedelta；有纳秒时先保留纳秒计算，再最后一次舍入到微秒。

NumPy的datetime64/timedelta64两类NaT均报ValueError。已支持的单位、方向和NumPy标量边界继续按现行契约处理，不扩成任意数组广播。

## 不可变值、复制和保存

字段只读，重复调用__init__不改变既有值。copy/deepcopy和pickle保留本包值及正常子类字典/可写slots；恢复错误哈希缓存会丢弃后按真实字段重新计算。只保证本包格式，不读取旧cyTimes pickle或Cython内部状态。pickle仅用于可信数据。

直接数值参数拒绝Python／NumPy布尔。公开None仅表达参数含义；Delta内部仍使用紧凑整数表示，不把Python对象带进普通运算内核。本轮已核对其对象大小与起点相同，整数构造、既有主要运算与相关批量路径仍受逐项5%性能保护。

## NumPy 和状态恢复的本轮修正

NumPy dtype 的倍数会计入日期或时长，例如 `datetime64(1, "10D")` 是纪元后的第10天。转换到微秒时，负数小于微秒的余数仍向下取整；两类 NaT 均报 ValueError。

`apply_many(values)` 的每项结果与普通 `value + delta` 保持一致，包括返回类型与错误。NumPy 某些日期单位会返回 `date`，另一些单位可能不支持普通相加；批量入口同样遵守这些结果。

带槽位的子类恢复属性时，按恢复开始时的条目处理。用户 setter 后来改动输入字典，不会使正在执行的恢复崩溃，也不会改变 Delta 的不可变字段和哈希。详见[本次发行说明](releases/v0.2.0b1.md)。


## Pandas values and subclass operations

With pandas installed, Delta uses the actual Timestamp date and Timedelta duration. Calendar arithmetic keeps a representable Timestamp result, including years beyond the standard datetime range. A duration does not become zero merely because it exceeds the standard timedelta range. A requested output that cannot hold the result raises an overflow or range error.

```python
import numpy as np
import pandas as pd
from rstimes import Delta

start = pd.Timestamp(np.datetime64("10000-01-02", "s"))
result = Delta(days=1) + start
assert (result.year, result.month, result.day) == (10000, 1, 3)

span = pd.Timedelta(np.timedelta64(1_000_000_000 * 86400, "s"))
assert (Delta() + span).days == 1_000_000_000
```

`to_timedelta(start)` always returns a standard `datetime.timedelta`. A pandas nanosecond remainder is kept until the final rounding to microseconds; exact half-microseconds round to even. The first call and later calls follow the same rule. Results outside the standard timedelta range raise `OverflowError`.

If a Delta subclass defines `__eq__` and inherits `__ne__`, inequality follows the opposite of that equality result. An explicit subclass `__ne__` remains authoritative. Direct calls preserve `NotImplemented`, and user comparison exceptions propagate. Copies preserve instance attributes, slots and reference cycles. Exceptions raised by your copy hooks or setters are propagated.


For the beta's public scope and distributions, see [the release notes](releases/v0.2.0b1.md).


## Current reconstruction rules

See [the release notes](releases/v0.2.0b1.md) for scope. Standard pandas Timestamp anchors in `to_timedelta(start)` use elapsed instants and retain nanoseconds until one final nearest-microsecond rounding (ties to even); ordinary datetime anchors retain Python wall-clock subtraction for the same timezone object. Long spans may exceed pandas Timedelta storage if standard timedelta can hold them. Custom arithmetic remains in control.

NumPy may convert a scalar before a reflected expression dispatches. Consequently, `value + delta` can pass a different Python type from `delta.__radd__(value)`; direct method probes and expression results should not be confused.

`apply_many` keeps the item already taken before any preparation callback. Subsequent items follow the live input iterator positions. Default dictionary/slot saving remains supported; subclass state and whole-reduce hooks are respected without allowing extra state to overwrite the immutable Delta fields.


## Errors

See [Handling errors](错误处理使用说明.md) for the three domain error classes, standard Python exceptions, callback propagation, and batch positions.
