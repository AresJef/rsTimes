# Delta 使用说明

当前本地版本为 `0.1.0+delta.1`，由 Rust 计算，PyO3 提供 Python 接口。此版本尚未公开发布；整体验收状态以 `tasks/todo.md` 和最终验收报告为准。首次验收环境限定为 macOS arm64、普通 CPython 3.13。

## 安装与导入

创建新 Python 3.13 环境，将最终验收报告列明的 `.whl` 文件交给 `python -m pip install <wheel文件>`，然后执行 `python -m pip check`。pip 会安装 NumPy、python-dateutil；实际验收使用的锁定版本在 `tests/delta/requirements.txt`。旧的 PyPI 0.1.0 不含本次 Rust Delta。

```python
from rstimes import Delta
from rstimes.delta import Delta as SameDelta

assert Delta is SameDelta
```

原有 `to_unix_ms` 和 `from_unix_ms` 仍可从根包导入。

## 构造与字段

相对参数表示增减量：years、quarters、months、weeks、days、hours、minutes、seconds、milliseconds、microseconds。绝对参数表示替换字段：year、month、day、weekday、hour、minute、second、millisecond、microsecond。

19个参数的实际位置顺序先weeks、后days；建议使用关键词，避免把旧类型存根中的不同顺序当作运行行为。15个公开属性只读；未设置的绝对字段返回None。

```python
from datetime import date, datetime, timezone

assert date(2024, 1, 31) + Delta(months=1) == date(2024, 2, 29)
assert date(2024, 1, 31) + Delta(month=2, days=1) == date(2024, 3, 1)

negative = Delta(microseconds=-1)
assert (negative.days, negative.hours, negative.minutes,
        negative.seconds, negative.microseconds) == (-1, 23, 59, 59, 999999)

original = datetime(2024, 1, 31, 12, tzinfo=timezone.utc)
result = original + Delta(months=1, hour=9)
assert result == datetime(2024, 2, 29, 9, tzinfo=timezone.utc)
```

按原规则先应用绝对字段、再加相对增量，最后调整weekday；月底夹取、负数进位和时区/fold规则沿用冻结参考。空增量或没有实际变化时，可返回原日期对象。日期子类、第三方日期子类和自定义构造异常也按原行为处理，不擅自统一成基础类。

## 运算和第三方对象

支持 Delta 加减、取负、绝对值、标准 timedelta、dateutil.relativedelta 和 NumPy 日期/时长标量的既定正反运算；不支持的方向仍返回NotImplemented，表达式由Python决定是否抛TypeError。这里只迁移Delta，不提供数组批量接口。

```python
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import numpy as np

assert Delta(days=1) + timedelta(days=2) == Delta(days=3)
assert Delta.from_relativedelta(relativedelta(months=1)) == Delta(months=1)
assert np.datetime64(-1, "us") + Delta(microseconds=1) == datetime(1970, 1, 1)
```

NumPy多倍单位、NaT、微秒以下单位及其异常次序保持已核对的原规则；详见 `docs/Delta行为说明.md`，不要按通常直觉替换这些行为。

## 保存、复制及已决定的差异

```python
import copy
import pickle

saved = pickle.dumps(negative, protocol=5)
assert pickle.loads(saved) == negative
assert copy.copy(negative) == negative
assert copy.deepcopy(negative) == negative
```

本包自己的pickle协议0–5、copy/deepcopy和子类状态受支持。pickle只读取可信数据。本版不读取cyTimes旧pickle，不提供旧Cython内部接口、旧路径别名或转换工具。

实际整数计算溢出会抛OverflowError，取代原实现的回绕结果；普通转换、日期无效值和异常顺序保留。失败的外层初始化不提交新字段；若用户数字转换回调已经再次初始化对象，那次完成的内层初始化仍保留。

跨类型相等与哈希不一致的旧缺陷保留，例如 `Delta(days=1) == timedelta(days=1)`，两者hash可能不同。使用字典或集合键时保持同一种类型。排序比较仍不支持。

完整行为差异见 `docs/Delta行为说明.md`；安全检查范围见 `docs/Delta安全说明.md`；后续优化的快速/正式复测命令见 `docs/Delta性能复测.md`。需要公开发布、其他平台或更高性能目标时另定范围。
