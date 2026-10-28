# Delta 当前行为与使用说明

完整参数与示例见 [Delta API guide](DeltaAPI.md)，错误规则见[错误处理使用说明](错误处理使用说明.md)。当前产物及本轮实测以[本轮验收报告](Delta-Parser-Pydt十项与错误处理重构验收-20261023.md)为准。

## 使用规则

| 场景 | 当前行为 |
| --- | --- |
| 相对增量 | years/quarters/months 使用整数协议，拒绝float与布尔；weeks 至 microseconds 支持整数和有限小数，进位归一化。 |
| 小数时长 | 保留大整数部分与小数尾数，所有固定时长合并后只舍入一次，半值取偶，结果精度为微秒。 |
| 绝对字段 | None 表示不设置；有值时使用整数协议，float（包括9.0）不接受。 |
| 绝对年月日 | 只接受正数，保留9999/12/31上限限制；合法日期选择可截取到目的月月底。 |
| 绝对星期和时钟 | weekday 只接受0至6；hour/minute/second/millisecond/microsecond须在各自范围内，0是实际设置，越界报ValueError。 |
| 不可变与比较 | 字段不能原地改写，重复__init__不改变值。Delta自身只按字段与Delta比较；不内建与timedelta/relativedelta的相等关系。 |
| 日历运算 | 先绝对字段，再相对增量，最后星期。月末调整不保证加减可逆；绝对设置也不会因减去自身而消失。 |
| relativedelta导入 | 读取真实原字段，不调用normalized()。只接受可表达的来源含义，转换后遵循Delta自己的规则；非空weekday及非零leapdays拒绝。 |
| NumPy | dtype倍数参与换算；支持Y/M/W/D/h/m/s/ms/us/ns。进入Delta的datetime64/timedelta64 NaT均报ValueError，不因空Delta或无变化返回而绕过。 |
| Timestamp | 日期操作保留真实日期和纳秒尾数；显式设置绝对microsecond或millisecond会清零旧纳秒尾数。 |
| apply_many | 与[value + delta for value in values]同序、同结果和类型。首个实际失败即停止，不返回前缀；读取失败与元素处理失败分别指出索引。 |
| to_timedelta | 不近似月份。需要日历含义时必须提供start；返回标准timedelta，保留纳秒差到最后一次微秒半值取偶舍入。 |
| 复制与pickle | 保留真实子类及正常字典/slots和自定义协议。状态格式严格检查，错误哈希缓存不被信任，不能用状态覆盖既有不可变值。 |
| 错误 | 错误类型、值域错误和真实溢出分别说明；外部回调保留原异常对象，只在需要时补公开入口备注。 |

## 示例

```python
from datetime import date
import numpy as np
from rstimes import Delta, parse

assert Delta(hour=None).hour is None
assert Delta(hour=0).hour == 0
assert (Delta(hours=1.5).hours, Delta(hours=1.5).minutes) == (1, 30)
assert date(2024, 1, 31) + Delta(months=1) == date(2024, 2, 29)
assert parse(np.datetime64(1, "10D")).date() == date(1970, 1, 11)
```

旧版逐项对比表属于当时的固定版本，已[原样归档](../tasks/archive/v-and-errors-refactor-20261022/legacy-guides/Delta行为说明.md)，不将其中的旧输出和测试数量当成当前版本结果。冻结官方cyTimes 3.1.0参考不变。
