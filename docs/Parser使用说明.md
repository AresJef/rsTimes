# Parser、Configs 与三个解析入口

```python
from datetime import date, datetime, timezone
import numpy as np
from rstimes import Configs, Pydt, Pddt, parse_str, parse, parse_to_epoch

assert parse_str("2024-05-07 12:30") == datetime(2024, 5, 7, 12, 30)
assert parse(date(2024, 5, 7)) == datetime(2024, 5, 7)
assert parse_to_epoch("1970-01-01T00:00:00.000000123", unit="ns") == 123
```

- `parse_str` 读一个字符串，默认返回标准 datetime。
- `parse` 还接受支持的 date／datetime 及真实子类、pandas Timestamp、NumPy datetime64、数值纪元秒，以及已有支持的单值 Polars Date／Datetime Series。
- `parse_to_epoch` 接受对应的支持来源，返回一个指定单位的Python整数，不返回列表或数组。多行日期使用 Pddt。

标准对象出口使用微秒；Pddt和整数出口可保留来源纳秒。输入本来只有微秒时，不伪造更细信息。缺失无法表示单一日期／整数，None、NaT及单值Polars null会明确报错；普通坏输入不自动变为NaT。

## 参数与默认值

三个入口共享适用的 `default`、`yearfirst`、`dayfirst`、`ignoretz`、`isoformat`、`strict` 和 `cfg`。对象出口另外可选 `dtclass`，整数出口另外选择 `unit` 和数字输入的 `input_unit`。

|参数|含义|
|---|---|
|default=None|完整、独立的日期兜底，仅补缺失年月日|
|yearfirst=None／dayfirst=None|明确非None优先，再用Configs；无配置为True／False|
|ignoretz|parse／parse_str默认True，保钟表而丢时区；parse_to_epoch默认False，保真实时刻|
|isoformat=True|优先尝试ISO，仍可进入通用文本规则|
|strict=False|默认宽松；True检查非法显式字段及重复冲突，不等于严格ISO|
|cfg=None|默认词表；明确Configs时使用其当前规则|
|dtclass|由所选构造器生成对象并决定最终类型容量|

普通布尔开关只收 Python bool／numpy.bool_；None只在文档列明的顺序选择中可用。日期／纪元数字及实际使用的数值default不接受两种bool。

```python
assert parse_str("2024-02-30").day == 29
try:
    parse_str("2024-02-30", strict=True)
except ValueError:
    pass
else:
    raise AssertionError("invalid explicit date must fail")

aware = parse_str("2024-01-01 08:00+08:00", ignoretz=False)
assert aware.utcoffset().total_seconds() == 28800
assert parse_str("2024-01-01 08:00+08:00").tzinfo is None
```

strict=True拒绝明确字段的非法范围、不同值重复和完整日期／星期矛盾；同值重复可接受。strict=False对已识别的越界日历／时钟分量限制到合法边界，不进位，冲突保后值。两种模式中，缺失日期从default补入后超过月底，均可合理取月底。宽松的未知普通内容继续沿已确定语法处理，不把strict扩大成“必须消费所有词”的新规则。

完整两位年份在严格模式报错；宽松模式需要default提供参考年份，无default会提示用法。default只作为明确参考，不依赖每年变化的本机世纪窗口。完整四位0000不作为“两位00”，也不会被default覆盖。

## 完整default与目标类型

```python
assert parse_str("May 7", default="2024-01-01") == datetime(2024, 5, 7)
assert parse_str("02-29", default=date(2024, 1, 1)) == datetime(2024, 2, 29)
assert parse_to_epoch("0000-01-01", unit="us") == -62167219200000000
assert Pddt(["0000-01-01"], unit="us").year.tolist() == [0]
```

default可用完整date／datetime及真实子类、完整日期字符串、既有Python int／float纪元秒或NumPy datetime64。它必须能独立得到年月日；只给月份、时钟或NaT不能作完整兜底。不从datetime default继承时分秒或时区；原datetime的fold可供对象解析选择重复当地时间。未用到default的原生输入不会触发其解析。

解析器识别实际年份，不先把最终年份截到1或9999。标准datetime／Pydt不支持零年，会由最终构造报错；整数／Pddt可在自身容量内保存。普通文本目前不因此扩大为任意负年语法；专用strptime另有明确宽年格式规则。

Parser解释字段、时区和fold，不判断地区当地时间是否存在。选择标准datetime会遵循其构造行为；选择Pydt会触发Pydt严格创建规则；Pddt从共享字段结果执行自己的数组ambiguous／nonexistent策略。

## Configs的设置和保存

Configs不支持继承。设置按 `add_*`、`del_*`、`set_*` 命名；不保留旧设置别名，内部词条查询不是公开API。读取词表得到独立快照，不能通过修改显示字典偷偷改内部解析规则。

```python
cfg = Configs()
cfg.add_month("mymonth", 2)
assert parse_str("29 mymonth 2024", cfg=cfg).month == 2
cfg.set_month({"mymonth": 3})
assert parse_str("29 mymonth 2024", cfg=cfg).month == 3
```

普通名称沿保存的小写／首字母大写／大写生成规则，只识别保存的形式，不临时接纳任意混合大小写。词条不能跨类别产生冲突；会被解析器拆开的非法词条在设置阶段拒绝。数值编码和偏移字段按各自整数范围校验，不把布尔编码成月份或偏移。

`Configs.from_parserinfo(info)` 导入八张既定表及两顺序标志，不执行parserinfo子类任意重写解析逻辑。None表表示不导入、不回填默认，错误非None外层容器报TypeError；结果与来源独立。copy／pickle保存基本规则的独立快照，恢复后重新建立查询规则；不把外部可变状态当运行缓存。

导入的 `info.yearfirst` 和 `info.dayfirst` 必须是Python bool或NumPy布尔标量；0、1、文本、None及其他真假对象会报TypeError，不会执行任意对象的真假转换。

## 地区名、数字偏移和可选依赖

```python
cfg = Configs()
cfg.add_tzone("Asia/Shanghai")
text = "2024-01-02 12:00:00.123456789 Asia/Shanghai"
assert parse_to_epoch(text, unit="ns", cfg=cfg) == 1704168000123456789
x = Pddt([text], unit="ns", cfg=cfg)
assert x.unit == "ns"
```

地区文本需要在Configs中登记完整IANA名；未知明确地区名会提示add_tzone并传cfg。显式tz参数和已经有区的对象不需要先登记。地区在配置时验证并加载，解析时复用；同一文本同时成功读到地区和数字偏移时，地区优先。

数字偏移保完整已支持秒和微秒分量；严格模式检查各分量范围，宽松模式逐分量限制而不进位。地区有冬夏变化，固定偏移不冒充地区规则。tzoffset提供明确固定别名；例如CST只在用户明确配置后才代表其选择，不自动猜本机缩写。

pandas、Polars均为可选依赖；未安装时不影响Delta／Parser／Pydt的普通使用。Polars系列的单个Python值通常已经是标准date／datetime，整列入口则读取真实列类型和单位。单值Parser不接收多行作为单一日期。

## 数字秒与精度

```python
assert parse_to_epoch(1, unit="ms") == 1000
assert parse_to_epoch(1, unit="ns", input_unit="us") == 1000
assert parse_to_epoch(1e-9, unit="ns") == 1
assert parse_to_epoch(-0.5e-9, unit="ns") == -1
assert parse_to_epoch(np.datetime64(123, "ns"), unit="ns") == 123
```

整数出口直接按来源精度换算最终刻度，较粗单位取更早边界，不先丢成微秒。Python整数出口不套日期缓冲int64容量，但真实计算仍有安全范围。

普通parse及Pydt的浮点秒保留既有微秒换算规则；数值default也保自己的既定角色。这和直接纳秒整数出口不同，不承诺浮点数能准确表示任意纳秒。

错误会说明公开入口、失败字段或可靠行位置，类型不符用TypeError，非法值用ValueError或已有明确领域错误，真实溢出用OverflowError。用户构造器、字段和时区回调的原异常不被通用包装吞掉。

## Optional dateutil integration in 0.2.0b2

Normal Configs creation and Rust parsing do not require python-dateutil.
`Configs.from_parserinfo()` requires the optional `rsTimes[dateutil]` extra;
without it the call raises `ImportError` identifying the public entry and
installation command. Install it before starting Python, or restart after
installation. The existing table, `None`, subclass and source-error contracts
remain unchanged. This does not introduce a dateutil parsing fallback.
