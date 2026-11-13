# Delta 第四轮行为修正与验收

当前本地候选为 rc04，版本 `0.1.0+delta.4`。约定的行为修正、最终包功能、保存恢复、构建和文档示例检查通过；**完整性能保护未通过，因此不能宣布本轮全部验收完成。** 用户已决定保留未全验收候选并结束本轮；新包与demo已保存，旧97环境与产物保留，未发布。

本轮对照是 Rust `0.1.0+delta.3`（候选97）。Cython R2FinalE只作为已决定行为的参考。本轮不修改Cython，不发布到PyPI，也不补写旧轮尚未通过的性能成绩。

## 使用者可见的变化

| 项目 | 现在的行为 | 保留的边界 |
| --- | --- | --- |
| 4. 极端时长 | `Delta(milliseconds=2**63-1)`能够归一化。跨单位抵消、负向进位和单项/批量运算在最终字段可保存时成功 | 输入仍受有符号64位范围限制；最终年份或天数真正越界仍抛出`OverflowError` |
| 5. 子类比较 | 子类自定义相等、不等或哈希规则时，基类返回`NotImplemented`，由Python继续处理。已复现的Child得到`== False`、`!= True` | 没有改变这些规则的子类仍按Delta字段比较；普通Delta与外部类型不作跨类型相等比较 |
| 6. 时长返回类型 | `to_timedelta(start)`成功时始终返回标准`datetime.timedelta`。起点的自定义加减运算仍受尊重 | 不接受非日期起点；自定义减法没有返回时长时明确报错 |
| 7. 纳秒计算 | pandas Timestamp的纳秒尾数在相对增量和日历调整中保留；最终时长只舍入一次 | Delta自身仍保存到微秒，不新增纳秒构造参数或NumPy数组入口 |
| 8. 子类属性 | copy、deepcopy和pickle保存继承的slots、私有slots和普通属性字典 | 浅复制仍共享属性值；深复制正确处理共享引用与循环；未赋值slot仍未赋值 |
| 9. 恢复哈希 | 外部状态的错误哈希缓存被丢弃，实际哈希由有效字段计算 | 错误字段、长度、版本仍拒绝；不能用状态恢复改变已有对象的Delta值 |
| 10. dateutil检查 | 先检查原始`weekday`/`leapdays`，再调用`normalized()`，随后检查返回对象 | 非空weekday和非零leapdays仍明确拒绝；合法回调的异常正常传播 |
| 11. 保存格式 | 保留Rust本包的状态接口与保存格式，候选97的有效pickle可读取 | 不提供cyTimes或Cython旧pickle兼容；pickle只用于可信数据 |
| 12. NumPy NaT | datetime64与timedelta64两类NaT在相应标量运算入口均抛出`ValueError` | 正常标量维持原有值与返回类型；None不是NaT；正常值真正溢出仍为`OverflowError` |

## 纳秒的明确规则

```python
from rstimes import Delta
import pandas as pd

start = pd.Timestamp("2024-01-01 00:00:00.000000123")
start + Delta(microseconds=1)
# Timestamp('2024-01-01 00:00:00.000001123')

Delta(microseconds=1).to_timedelta(start)
# datetime.timedelta(microseconds=1)

start + Delta(microsecond=0)
# Timestamp('2024-01-01 00:00:00')
```

相对增量和仅调整年份、小时等其他字段时，保留尾数。有效的绝对`microsecond`或`millisecond`设置替换完整的小数秒并清零额外纳秒，即使设置的微秒与起点相同。最终表示“未设置”的负数参数不会清零尾数。毫秒覆盖微秒的既有规则保留。

`to_timedelta()`先求真实差值，然后舍入到最近的微秒；正好半微秒时取偶数。877ns→1µs，1500ns→2µs，2500ns→2µs；负数按同样规则处理，误差绝对值不超过500ns。整微秒差值精确。普通datetime继续遵守原有时区、fold和墙钟规则，pandas起点遵守pandas本身的减法规则。

## 功能与构建验收

| 验收 | 结果 |
| --- | --- |
| 已有行为观察 | 1381条；1314条不变，67条批准变化，未知差异0 |
| 新维护契约 | 123/123通过 |
| 既有修订契约 | 26/26通过 |
| 接口与状态契约 | 54/54通过 |
| 对外文档示例 | 11/11通过 |
| Rust单元测试 | 9/9通过 |
| 格式与Clippy | 已改Rust文件格式通过；全部目标/特性按`-D warnings`通过 |
| 源码包重建 | 从sdist解包到独立目录，用独立编译目录构建release wheel并安装到新环境 |
| 发布内容隔离 | sdist共24条目，未打入冻结参考、任务证据或本地环境 |

67条批准变化分别为3条极端时长、58条NaT处理、6条pandas纳秒日期处理。每条按独立整数计算、明确错误类别或明确日期预期核对，未用候选输出自己充当预期。

## 性能保护

固定66个输入，另有7条小数与同字段整数的配对，共73条关系。短函数以共同调用次数批量计时，每个有效计时批次至少5ms。主轮和独立轮各使用3个新进程周期，每关系每周期48个完整配对；每关系共288配对。全部合格慢样本保留。

正式成绩必须同时满足质量、稳定性、中位及保守保护：既有调用最多慢5%；七类小数相对同字段整数最多慢20%。短长差不超过3%，正式波动不超过5%。组结果使用固定等权几何平均，不能抵消超标单项。

rc04完整10ms准备耗时107.11秒，72/73关系通过精度要求。`duration:datetime`的短长差为6.21%，超过3%，保留为未明确，不继续调参。其余72条使用各自有效控制冻结后做一次正式采集；最终报告范围仍为73条，不能因只采集可测部分而宣称完整通过。

一次获批的20ms同包确认没有证明整体稳定性改善：构造、getter与10000元素Delta批量分别出现11.86%、7.05%、7.94%的最大波动，三项全部未明确。20ms未采用，所有原始数据与旧候选成绩保留。

一次rc04正式采集已结束，用时863.06秒（14分23秒）。完整73条范围中：**28通过、8稳定超标、37未明确**。72条形成正式成绩，每条288配对，共20736配对；要求21024，剩余288属于精度不足的`duration:datetime`，没有凑数。

8条稳定超标的中位耗时增加均在5%以内，但至少一轮的保守结果超限，仍判FAIL。1条波动未明确项`arithmetic:add`的中位保护也没有满足，不能把71条中位达标概括为全体性能通过。合格慢样本、全部旧控制和失败结果保留，不再重开采集寻找通过结果。

| 结果 | 意义 | 数量 |
| --- | --- | ---: |
| PASS | 该关系同时满足质量、稳定性和性能保护 | 28 |
| FAIL | 统计稳定，但约定性能保护未满足 | 8 |
| INCONCLUSIVE | 波动或精度不够，结论未明确 | 37 |

稳定超标项为混合构造、等价整数小时/秒构造、绝对小时日期运算、Timestamp日期运算、普通相等比较、10000元素Delta批量和1024元素混合批量。完整固定输入ID、两轮中位值、保守结果及全部未明确项见[性能明细](../tasks/evidence/delta-correction-20261013/final04/performance-results.md)。这张清单不是只选择慢项重新采样的队列。

## Demo与本地使用

直接执行`python demo/delta.py`会选择rc04的隔离环境并核对版本和native指纹，无须手动指定解释器。Demo明确打印“本地候选：功能验收通过，完整性能验收尚未通过”，旧97环境和产物保留。

普通启动已完成20个分组、145个代表场景，未知差异0。补充了极大毫秒、两类NaT、纳秒保留与绝对替换、标准timedelta返回示例。演示计时只帮助理解调用，不属于正式性能成绩。

## 文件与复现

- [唯一计划与时间台账](../tasks/delta-correction-plan-20261013.md)
- [最终功能结果](../tasks/evidence/delta-correction-20261013/final04/final-functional.json)
- [产物与运行身份](../tasks/evidence/delta-correction-20261013/final04/identity.json)
- [独立批准预期](../tasks/evidence/delta-correction-20261013/final04/approved-expectations.json)
- [完整性能准备与未明确项](../tasks/evidence/delta-correction-20261013/final04/performance/config.json)
- [可测部分的冻结配置](../tasks/evidence/delta-correction-20261013/final04/performance-measurable/config.json)
- [完整范围性能判定](../tasks/evidence/delta-correction-20261013/final04/performance-acceptance.json)
- [性能明细](../tasks/evidence/delta-correction-20261013/final04/performance-results.md)
- [Demo运行记录](../tasks/evidence/delta-correction-20261013/final04/demo.log)
- [交付与保护检查](../tasks/evidence/delta-correction-20261013/final04/delivery-identity.json)
- [性能采集入口](../tools/delta_correction_benchmark.py)
- [本地wheel与sdist](../dist/delta-corrected-0.1.0+delta.4/rc04/)

当前最终包运行环境为`.local/delta/correction-20261013/final-env4d`，普通CPython3.13.3、macOS arm64。依赖复用经身份核对的97环境，包本身从新环境加载；旧包未替换。实际native SHA-256为`e4d919cb654d1c554b6ee20b22bc4429537b93dd4049bc45a3a504f36c56273d`。其他平台没有在本轮验收。

## 本轮收尾

用户已明确选择“保留未全验收候选，结束本轮”。本轮以rc04本地候选收尾，不再优化、采样或发布。最终有效验收仍为93/100，完整性能未通过；该决定不将FAIL/INCONCLUSIVE改为PASS。最终工作快照北京时间2026-10-13 21:23:53：累计205.42有效分钟，240分钟余额34.58，相对总预算差额-34.58分钟；明确暂停171秒单列，未知秒级等待未臆扣，末尾答复秒数误差约1分钟以内。自动续接核查及收尾计入已有时间，未重置T0。
