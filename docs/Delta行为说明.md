# Delta 行为差异与使用说明

冻结参考为 cyTimes 3.1.0。本文件随实现补齐；不代表整体已验收。

## D1：极端整数计算

普通输入转换和错误保持原规则；原整数位宽中的实际计算溢出明确抛 OverflowError。失败初始化不提交新字段；本次输入原版会回绕，属于已决定差异。

| 固定输入编号 | 原版结果 | 新包结果 | 决定与证据 |
| --- | --- | --- | --- |
| relative:overflow:years | {"years": -2147483648, "months": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:quarters | {"years": 178956970, "months": 5, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:weeks | {"years": 0, "months": 0, "days": 2147483641, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:days | {"years": 0, "months": 0, "days": -9223372036854775808, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:milliseconds | {"years": 0, "months": 0, "days": -1, "hours": 23, "minutes": 59, "seconds": 59, "microseconds": 999000, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:us-addition | {"years": 0, "months": 0, "days": -106751992, "hours": 19, "minutes": 59, "seconds": 5, "microseconds": 225191, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:negative-years | {"years": 2147483647, "months": 11, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:negative-quarters | {"years": -178956971, "months": 4, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:negative-weeks | {"years": 0, "months": 0, "days": -2147483648, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |
| relative:overflow:negative-milliseconds | {"years": 0, "months": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null} | builtins.OverflowError: integer overflow in Delta normalization | D1；construct-03/green.json |

Python 模块从 cytimes.delta 改为 rstimes.delta；四个已验证的属性/不可改写类型错误消息只相应替换类名，其他文字和异常类别保持。证据：properties-04/green.json。

## D1：运算溢出补充

| 输入编号 | 原版结果 | 新包结果 |
| --- | --- | --- |
| delta-arithmetic:overflow:add-years | {"type": "rstimes.delta.Delta", "fields": {"years": -2147483648, "months": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta normalization |
| delta-arithmetic:overflow:sub-years | {"type": "rstimes.delta.Delta", "fields": {"years": 2147483647, "months": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta normalization |
| delta-arithmetic:overflow:add-days | {"type": "rstimes.delta.Delta", "fields": {"years": 0, "months": 0, "days": -9223372036854775808, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta arithmetic |
| delta-arithmetic:overflow:sub-days | {"type": "rstimes.delta.Delta", "fields": {"years": 0, "months": 0, "days": 9223372036854775807, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta arithmetic |
| unary:overflow:years:neg | {"type": "rstimes.delta.Delta", "fields": {"years": -2147483648, "months": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta normalization |
| unary:overflow:years:abs | {"type": "rstimes.delta.Delta", "fields": {"years": -2147483648, "months": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta normalization |
| unary:overflow:days:neg | {"type": "rstimes.delta.Delta", "fields": {"years": 0, "months": 0, "days": -9223372036854775808, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta negation |
| unary:overflow:days:abs | {"type": "rstimes.delta.Delta", "fields": {"years": 0, "months": 0, "days": -9223372036854775808, "hours": 0, "minutes": 0, "seconds": 0, "microseconds": 0, "year": null, "month": null, "day": null, "weekday": null, "hour": null, "minute": null, "second": null, "microsecond": null}} | builtins.OverflowError: integer overflow in Delta absolute value |

证据：arithmetic-04/green.json；普通输入结果保持，八个极端加减或取负输入明确报错。

## NumPy 规则

不支持的 ps/fs/as 和 generic 单位保留原版实际 TypeError("Expected str, got type")，不是凭工具文档改成 ValueError。多倍单位仍按原版只使用基础单位。NaT[ns]/NaT[us] 保留原结果或错误；NaT[D]/NaT[M] 经本 Delta 自己转换时发生的实际整数溢出改抛 OverflowError。NumPy 自己先转换的反向表达式仍保留原结果。逐项原/新值与20个D1输入在 numpy-05/green.json 的 approved_differences 中；模块类名只在已固定的86个错误位置替换引号内路径，其他字段严格比较。

pandas Timestamp 改变日期时按原版舍弃微秒以下余数；无变化返回原对象保留余数。真实第三方类60例见 numpy-04/green.json，不表示这些包的其他功能已经迁移。

## 新包状态与保存复制

状态为 ("rstimes.delta", 1, 15字段tuple, 内部hash缓存, 子类字典或None)。字段顺序就是15属性顺序，绝对未设置保存为-1；普通字段必须满足范围和归一化关系，整数为exact int。读取前完整检查版本、长度、整数、范围、hash对应关系和字典，再一次提交字段，不擅自重新归一化。原始 __new__ 对象的全零字段/hash=0单独保存。

新包pickle使用标准copyreg.__newobj__和实际类；协议2–5使用NEWOBJ，恢复绕过__init__，支持必填构造参数子类。本包协议0–5及copy/deepcopy均已验证（newobj-01/green.json）；不读取旧pickle或提供旧Cython别名。pickle只用于可信数据，这个格式不使不可信pickle变安全。

跨类型相等与hash不一致的旧缺陷保留，例如Delta(days=1)==timedelta(days=1)，两者hash仍不同；不能据此混用字典/集合键。原始raw对象hash仍为0，普通对象使用15整数tuple的hash，重新初始化后清空缓存。证据：exports-02/green.json。
