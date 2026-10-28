# parse_str 与 parse 使用说明

本发行版本为`0.2.0b2`，范围见[发行说明](releases/v0.2.0b2.md)。四个demo共用demo/runtime.json；按README准备独立环境和发行清单后，运行python demo/parser.py会校验版本及native身份。


`parse_str()` 专门处理字符串，`parse()` 同时处理字符串、datetime、date、int/float秒数和NumPy datetime64。

```python
from datetime import date, datetime, timezone
from rstimes import parse_str, parse

parse_str("2024-05-07T15:30+08:00", ignoretz=False)
parse(date(2024, 5, 7))  # 2024-05-07 00:00:00
parse(1.1)              # 1970-01-01 00:00:01.100000
```

## 参数顺序

两个入口都采用 `input, default, yearfirst, dayfirst, ignoretz, isoformat, strict, cfg, dtclass`，strict默认False并位于isoformat之后。原parse(dtstr=...)改为parse_str(dtstr=...)或parse(dtobj=...)。

旧版按位置传入cfg、dtclass的调用必须调整：原来的第7个位置现在是strict，第8个位置现在是cfg。将这两项改写为`cfg=...`和`dtclass=...`，可避免参数错位。

## 字符串

保留已采用版本的strict、非法字段限制、星期、配置词表、默认日期和两位年份规则。default只补年月日；两位年份需要strict=False和明确default。ignoretz默认True；需要保留已识别偏移时传False。

parse_str只接受Python内置str的实例，不接受str子类。str子类请使用parse；该入口先调用str(value)，再解析转换后的字符串。

## 其他对象

- 标准datetime默认直接返回原对象，时区和fold保留。ignoretz不会删除输入datetime已有的时区。
- datetime子类默认转成标准datetime。若希望保留目标类型，显式传dtclass；输入实际类型就是该目标类型时返回原对象。
- date变成同一天零点，不从default继承时分秒。
- 数字是从1970-01-01起算的秒数，返回无时区datetime，不读取电脑的本地时区。Python bool和NumPy bool均抛TypeError，不作为0或1秒。浮点秒数保留官方规则：先舍入到七位小数，再取前六位作为微秒。
- np.datetime64支持Y/M/W/D/h/m/s/ms/us/ns；纳秒尾数减到微秒，负数向下取整。不接受数组和timedelta64。dtype倍数参与转换，例如np.datetime64(1, '10D')表示纪元后10天，得到1970-01-11。
- default、yearfirst、dayfirst、ignoretz、isoformat、strict和cfg的解析含义只作用于字符串；dtclass对所有支持类型生效。

非字符串输入也会校验ignoretz、isoformat、strict：它们只接受Python bool或NumPy bool，不接受整数或任意真假转换对象，也不调用其__bool__。cfg必须为有效的Configs或None；这些参数本身不合法时仍会报错。

## 错误

不支持的输入类型抛TypeError；NaT和数字NaN抛ValueError；无穷大或真实计算越界抛OverflowError。文本无法解析、strict字段不合法或互相冲突时，抛rstimes.errors.ParseError。Configs中无法使用的词条、值或规则抛rstimes.errors.ConfigError。

目标构造函数、字符串转换、时区等用户回调失败时，保留其原异常对象、原参数和原因链，只在需要时增加说明公开调用入口的标准备注。内存、中断、退出和取消信号原样传播。不会为了说明错误再次执行转换或用户展示方法。

## 地区时区与配置名称

编辑词表统一使用 `add_*`、`del_*`、`set_*`；固定偏移组为 `tzoffset`，地区组为 `tzone`。旧 `remove_*`、`replace_*`、`tz` 名称不保留别名。

```python
from rstimes import Configs, parse_str, parse_to_epoch
cfg = Configs()
cfg.add_tzone("Asia/Shanghai")
value = parse_str("2024-01-02 12:00 Asia/Shanghai", cfg=cfg, ignoretz=False)
ticks = parse_to_epoch("2024-01-02 12:00:00.123456789 Asia/Shanghai", "ns", cfg=cfg)
```

`default`只补年月日；原始datetime default还提供fold，没有时使用0。Parser不检查或修正地区当地时间是否存在；选择dtclass=Pydt时，由严格Pydt构造拒绝不存在的时间。标准datetime目标直接接收字段。strict只管理文本字段是否合法。地区与固定偏移同时识别时采用地区。


## Errors

See [Handling errors](错误处理使用说明.md) for the three domain error classes, standard Python exceptions, callback propagation, and batch positions.
