# PLDT与Delta纳秒升级最终讨论决定

定稿日期：2026-10-30。**全部14板块／60主项已确认；PL-Q01—PL-Q06均已收口。Delta完整纳秒方案、U1／U2／U3及D01.O1—O4全部纳入本文件。总项目预算72有效小时。当前只完成讨论定稿，未启动实施、构建、性能采集或发行；公开采用版本仍为0.2.0b2。**

## 0. 唯一正文、适用范围与使用指令

1. 本文件是本次PLDT开发、Delta纳秒升级和相关现有类修改的唯一最终讨论决定。后续执行计划必须逐任务引用本文件的具体编号、目标和验收；不能只引用摘要或通过数量。原A01—N04的60编号保留，G01.N的GN01—GN13为内部子项，不另增加主项。两个核心断言PL01／PL02及所有范围、例外与参数职责一并适用。
2. 本次包含：新Pldt真实Series类及Series／Expr命名空间；Delta完整ns重构和所有相关适配；D01四项已批准优化；N01列出的Parser／Configs／Pydt／Pddt共享修改。未批准的新公共接口、任意数组算术、特殊平台、Pages文档站或全库额外审计不自动加入。
3. 已采用Pddt最终决定及根AGENTS的现行C01—C26，继续保护未被本次明确改变的行为。本文件明确批准的新Delta精度／状态、Pddt字段replace命名空间、列工厂目标tz、三类strftime小数及其它N01改动，作为后续目标执行；不能用当前实现的旧规则否决已批新合同，也不能把设计批准写成当前已采用事实。本轮不修改根AGENTS。
4. 原PLDT讨论稿、独立Delta两原稿、旧合并方案、既有证据全部保留追溯。旧讨论入口改为本文件导航，历史备选／研究观察不作为另一套现行合同。附录提供60项、6组收口决定、Delta15来源板块及U1／U2／U3的完整去向。
5. 本文代码均为已批准目标或明确标注的参考版对照，不是新PLDT已运行的证明。所有“当前／实测／参考”只指原记录冻结的b2／Polars／pandas环境；来源版本、脚本和原始结果见保存区，不据此转记新产品PASS、倍率或平台通过。
6. 72小时包含规划、实施、优化、校准／预试／正式验收、文档与交付。本次文档整理记录为规划准备；实施和发布仍需后续明确启动。旧Goal的授权、豁免和余额不继承；不启动子Agent、不提交、推送或发布。正常工程接线在已定合同内自行选择，有实质范围／质量／行为变化才重新提出。
7. 共同合同在其唯一功能条目展开，具体入口通过引用复用；不能以“以后面为准”的补丁方式让相反现行规则并存。未验证的构建／ABI／性能是实施验收工作，不是未决的产品语义。

## PLDT核心断言

### PL01 日期能力平行、使用方式贴合Polars

在实现与Pddt平行的日期能力之外，PLDT的使用方式尽最大合理可能贴合Polars。真实Series／Expr分工、DataFrame／LazyFrame接入、返回容器及原生生态按Polars模型；不机械照搬Index或额外包装流程。成熟原生功能语义相同时尽量完整复用；新增规则使用官方扩展接口和最小共享Rust核。单位、null、时区和容量等真实差异按对应条目，不伪造宿主不具备的能力，不以贴合Polars静默修改共同日期含义。

### PL02 共同日期功能尽可能与Pddt一致

在不冲突于Polars常规使用、执行模型和真实能力的前提下，共同功能尽可能沿Pddt的方法命名、参数职责、默认、运算含义、标量／逐行配对、精度／舍入及错误规则。相同算法复用小Rust函数，输出按各目标能力完成。完整继承／完整委托保原参数、广播、返回和异常，不套半套自有规则；共享小算法不等于完整委托某个公开方法。

已确认的物理／协议差异完整保留：B01拒Mapping／set／frozenset；B02严格集合长度及PLDT原生可空字段；C01仅ms/us/ns；C04独立validity／有效MIN与窄安全导出；C05宽年和目标容量；D/E/M的静态schema／创建时快照；G03动态Series载体；H01规范化时区；J/K/L的返回、元数据和子类边界。具体例外以各条正文，不由原则扩新功能。

## 板块目录与阅读指令

| 板块 | 主项数 | 开发／审查时必读范围 |
|---|---:|---|
| A 对象与执行入口 | 4 | A01—A04；原生返回与命名冲突同时读K/L |
| B 输入、参数与所有权 | 5 | B01—B05；逐行角色结合F/G/H |
| C 单位、有效位与容量 | 6 | C01—C06；所有构造／运算／导出均适用 |
| D Parser、Configs与格式输入 | 4 | D01—D04，必须含D01.O1—O4；快照与schema同时读M |
| E 全部命名工厂与范围 | 5 | E01—E05；单位读C，时区读H |
| F 字段、移动与周期 | 4 | F01—F04；日历／经过时长读G，自动地区读H06 |
| G Delta、时长与算符 | 3 | G01含GN01—GN13；G02／G03；不得漏U1／U2／U3 |
| H 时区与DST | 6 | H01—H06；来源／目标分工同时读D03/E |
| I 取整、Snap、fsp | 3 | I01—I03；自动候选读H06，字段边界读F04 |
| J 查询、diff与表格 | 4 | J01—J04；只算所需量，按真实返回容量 |
| K 数值／对象／格式／语言导出 | 4 | K01—K04；安全导出读C04，格式输出不等于D04格式输入 |
| L 元数据、状态与生态 | 4 | L01—L04；所有权读B05，动态算术读G03 |
| M Expr与原生插件 | 4 | M01—M04；所有Expr入口均核schema／逻辑域／无GIL |
| N 共享范围与整体验收 | 4 | N01—N04；所有任务必读N03/N04及本文件第0节 |
| 合计 | 60 | 关联Delta子项不重复计数 |

## A 公开对象、执行入口与返回边界

<a id="pldt-a01"></a>

### A01 Pldt真实Series子类与原生执行

**具体例子：**

```python
s = pl.Series("t", [datetime(2024, 1, 31)])
# 已确认对象形式，接口尚未实现：
x = Pldt(s)
y = x.to_next_month()
isinstance(x, pl.Series)  # True
frame.with_columns(y)    # 可直接作为Series传入
```

**确定架构：**Pldt真正继承`pl.Series`，与当前Pydt继承datetime、Pddt继承DatetimeIndex的对象关系平行。自有日期操作按各项最终合同返回Pldt，整数／布尔／字符串／时长等按职责返回相应原生类型。Pldt可以直接传入接受Series的Polars入口；不以强制`to_series()`作为接入前提。

**继承边界：**不为了保Pldt而包装全部Polars成熟方法；某些原生方法或DataFrame取列返回普通Series是需明确说明的边界，不自动当作丢失日期数据。用户再次继承Pldt的业务构造、复制状态及原生可变操作按已收口L03/L02/B05/L04。使用官方扩展机制，不覆盖Polars已有方法、不伪造原生类型；Expr支持和接入形式独立于Series继承，按已确认A02／A04，统一.pldt命名空间。

**已确认的原生执行原则：**自有批量计算优先在入口一次读取参数、准备规则及取得原生Series/Arrow数据与owner；Rust内核直接处理刻度、chunk、有效位、单位和时区元数据，出口才构造最终Python Pldt或相应查询结果。不要逐行取Series元素变Python datetime，再调公开Pydt/Parser/Delta后写回；不要通过list/逐行Python整数中转原生列。优先官方Polars Rust适配／插件或成熟Arrow协议，不借“Polars也用Rust”假定两份Rust私有类型可直接互转。具体接线按M02已定执行边界实现并验证；尚未实际构建插件。

**必要边界：**已经传入的Python datetime/自定义数值等在入口按真实协议读取；真实Python回调、业务构造、主动Python日期导出及其它确有必要的适配仍按后续明确合同保留。减少对象以完整路径效率和行为正确为准，不设全路径绝对零Python对象硬要求。naive／UTC／可表达固定偏移走整数捷径，不做地区候选／双fold或往返验证；必要地区处理优先成熟原生时区能力，旧类动态协议不能顺带删掉。

**性能影响：**真实Series子类身份不要求逐行Python计算。安全时复用底层所有权与缓冲，避免无意义全列复制及中间父Series/Pldt；新的结果缓冲和最终容器仍可按计算需要分配。只在单次操作内追求最终一次输出，不承诺把多个用户eager调用自动融合。实际零复制范围、GIL释放、插件接线和完整调用速度均待实施验证，不能仅从语言或继承方式推定更快。

<a id="pldt-a02"></a>

### A02 立即Series与原生Expr／LazyFrame的统一日期接口

**范围与事实：**Pldt沿A01是真实Series子类，Series存已有数据；Expr描述计算，不能把两者当同一对象。首版同时支持实际列与表达式，共同日期方法保持相同名称、参数职责、计算顺序及日历含义，容器／schema／标量或列参数按对应板块确定。Pddt提供共同日期语义，Polars提供Series／Expr／Frame执行模型。

**表达式入口：**使用Polars官方`register_expr_namespace`机制，命名空间按已确认A04固定为`.pldt`。每个日期变换／查询方法直接返回原生`pl.Expr`，不公开第二种日期表达式包装类型，不要求用户显式包装或导出Expr。加载PLDT功能时一次注册，不因Delta／Parser／Pydt导入而强制安装Polars；不覆盖原生`.dt`或其它已有功能。各方法／参数按本文件对应条目执行。

**平行例子（Pldt及.pldt均未实现）：**

```python
s = pl.Series("time", [datetime(2024, 1, 31), datetime(2024, 2, 29)])
df = pl.DataFrame({"time": s, "days": [1, 2]})

# 实际列：同一个日历移动，分别给出原生与本库结果。
result = s.dt.offset_by("1mo")       # pl.Series
result = Pldt(s).to_next_month()     # Pldt，亦为pl.Series
# 两边日期为2024-02-29、2024-03-29。

# 表达式：两边直接得到原生pl.Expr，尚未计算日期数据。
expr = pl.col("time").dt.offset_by("1mo")
expr = pl.col("time").pldt.to_next_month()

# 日期方法每次返回Expr；再次调用本库方法时再次进入.pldt。
expr = pl.col("time").pldt.to_next_month().pldt.to_next_month()
# 与两次原生offset_by("1mo")一样按顺序执行；结果为3月29日、4月29日，
# 不可为优化擅自改成一次加两个月。

# 使用单次移动表达式，DataFrame和LazyFrame执行方式与Polars一致。
expr = pl.col("time").pldt.to_next_month()
result = df.with_columns(expr.alias("next_month"))      # pl.DataFrame
query = df.lazy().with_columns(expr.alias("next_month"))  # pl.LazyFrame
result = query.collect()                               # pl.DataFrame
# next_month为2024-02-29、2024-03-29；取列返回普通pl.Series，
# 不承诺DataFrame会自动恢复Pldt子类。

# 布尔／整数／字符串等查询也直接返回相应原生Expr。
result = Pldt(s).is_month(1)           # pl.Series[Boolean]，值[True, False]
expr = pl.col("time").pldt.is_month(1) # pl.Expr，执行后为Boolean列
result = df.filter(expr)              # pl.DataFrame，仅保留1月31日

# 拟支持逐行输入的功能在Expr侧引用列，具体角色仍按B02/F板块确认。
expr = pl.col("time").pldt.add(days=pl.col("days"))  # pl.Expr
result = df.with_columns(expr.alias("shifted_time"))
# shifted_time为2024-02-01、2024-03-02。
```

**Rust执行与性能：**Series和Expr复用最小Rust日期内核，不分别维护两套日期算法。命名空间只是参数准备／表达式构建入口，普通数据计算在Rust列／chunk／有效位中完成；不要求逐行Python对象或整列复制。Expr交Polars按合法语义规划、批量和并行，不暗中collect，不用逐行Python UDF代替原生实现。小列Series可能更直接，Expr不保证每次更快，也不保证多插件融合；实际接线、wheel和完整调用速度仍需验证。性能采集分别计Series公开调用、DataFrame操作和Lazy执行全过程，不拿Expr创建时间当运算成绩。

**能力边界：**相同日期语义不代表所有Series能力都能延迟表达。实际长度、取单元素、Python日期导出、业务状态copy/pickle等需要已有数据的能力按eager职责保留；工厂／取钟按E板块确定。infer等顺序相关操作不随意拆batch，分组／流式按H04/M03确定。已能判断的参数错误尽早报，依赖实际数据的坏日期／溢出等在执行时报；不制造假数据或静默改dtype求成功。必要真实Python协议继续按A01保护。

<a id="pldt-a03"></a>

### A03 日期、查询、表格与单元素返回

**已确认范围：**按PL01尽量使用Polars自己的结果容器，同时保证共同日期能力和真实来源精度。A02已确认Expr方法直接返回原生Expr；本项进一步讨论实际列结果、逐行复合结果、标量与长度一切片。所有Pldt代码表示已批准目标。

**1. 单列日期变换与查询：**

```python
s = pl.Series("time", [datetime(2024, 1, 31), datetime(2024, 2, 29)])
x = Pldt(s)
result = x.to_next_month()  # Pldt：2024-02-29、2024-03-29
result = x.is_month(1)      # pl.Series，Boolean：[True, False]
result = x.toordinal()      # 原生整数Series，不返回pandas Index或Pldt
result = x.isoformat()      # 原生String Series，不返回Python字符串列表
# x-x等合法日期差按已确认G02提供原生Duration Series；规则见G02。

expr = pl.col("time").pldt.to_next_month()  # pl.Expr，日期输出
expr = pl.col("time").pldt.is_month(1)      # pl.Expr，Boolean输出
expr = pl.col("time").pldt.toordinal()      # pl.Expr，整数输出
expr = pl.col("time").pldt.isoformat()      # pl.Expr，String输出
```

日期结果才使用Pldt。实际用户子类协议、整数位宽、布尔／整数缺失及对象出口分别按已收口L03、J01/J02及K01/K02；预算和性能统一按N04执行。

**2. 逐行多个字段优先Struct，以isocalendar为例：**

```python
x = Pldt(["2021-01-01", "2024-01-02"])
result = x.isocalendar()         # pl.Series，dtype Struct
# 两行字段为(year=2020, week=53, day=5)、(year=2024, week=1, day=2)。
# 这是原生列式复合结果，不在内核逐行创建Python dict／tuple。
weeks = result.struct.field("week")  # 原生整数pl.Series：[53, 1]
table = result.struct.unnest()       # pl.DataFrame，year/week/day三列

expr = pl.col("time").pldt.isocalendar()  # pl.Expr，Struct输出
result = df.select(expr.alias("iso"))    # pl.DataFrame，一列iso Struct
result = df.select(expr.struct.unnest()) # pl.DataFrame，展开year/week/day
```

逐行复合结果在Series侧采用Struct Series、Expr侧采用Struct表达式，需要表格时由原生unnest展开，使两模式的结果结构一致。明确以整表输出为职责的timedf／utctimedf按J04已定表格合同，不把所有多字段入口一刀切；ISO字段位宽、ISO容量及空值细节按已收口J04；tm_isdst规范化表示按已确认H01／J04规则。

**3. 单元素按原生Polars返回；保ns的单行结果使用切片：**

```python
s = pl.Series("time", [1704067200123456789, None], dtype=pl.Datetime("ns"))
x = Pldt(s)
result = x[0]        # 标准datetime.datetime：2024-01-01 00:00:00.123456
result = x[1]        # None
result = x[0:1]      # Pldt，Datetime(ns)，保完整.123456789
ticks = result.cast(pl.Int64)  # 原生整数Series：[1704067200123456789]
```

直接索引／item沿原生标量协议，不改成Pydt、Timestamp或长度一容器，不新增纳秒标量类。Python datetime只有us精度及自身年份容量，原生出口的限制须写清楚；不修改源列、不为标量导出偷偷调单位。内部普通计算不经过此标量出口，因而不会为计算先丢ns。显式Python日期批量导出另见K02。

**4. 成熟原生容器功能按自己的返回职责：**原生min/max等返回Python标量或None，不能因为结果是日期就全部包装Pldt。DataFrame取列仍是普通Series；按A04可直接使用series.pldt，也可显式Pldt(series)，或在Frame中继续.pldt表达式。完整继承／业务子类／切片所有权／元数据详细合同分别在L/B确认，不为保类型包装全部Polars。

**性能影响：**普通日期／查询直接写对应原生列及有效位，只构造必要的最终结果，不先生成日期Pldt再查询。Struct以原生子列组织多字段，可共用一次日历解码，避免逐行Python字典及重复计算；unnest使用Polars能力，不承诺所有情况绝对零复制。长度一切片不需要Python datetime中转，实际共享缓冲须保owner。用户主动索引、min/max、to_list等才支付相应原生标量／对象导出成本；本项没有正式性能倍率。

<a id="pldt-a04"></a>

### A04 类名、导入、命名空间及一次加载注册

**范围与真实起点：**A01已确认真实Series子类，A02已确认原生Expr入口，A03已确认返回职责。本项只确定清晰的公开名字和接入方式，不重开日期算法。当前库使用Pydt／Pddt，Pddt从根包和子模块导出的是同一个类，根包按实际访问加载Pddt；pyproject已有polars可选依赖组。Polars官方同时提供register_expr_namespace和register_series_namespace。本机Polars2.0.0尚无Expr.pldt或Series.pldt；这不能保证用户安装的其他扩展也未占名。所有Pldt／.pldt示例均为已批准目标，未实现。

**1. 类与模块只用一套名字：**

```python
from rstimes import Pldt
from rstimes.pldt import Pldt as ModulePldt
Pldt is ModulePldt  # 目标True，两条导入路径导出同一个类

x = Pldt(s, unit="ns")
result = x.as_unit(unit="us", round_ok=False)
# x／result为Pldt；本例须是能无损转us的数据。
```

公开类名Pldt，模块rstimes.pldt，保持本库Pydt／Pddt风格；构造用unit，转换用as_unit(unit=...)。不新增PLDT／PolarsDatetime等同义类，不恢复旧构造关键字或已取消占位。具体单位／精度合同仍按C板块，不借命名决定替它放宽范围。

**2. 普通Series和Expr使用同名.pldt入口，Pldt保无原生冲突的直接方法：**

```python
from datetime import datetime
import polars as pl
from rstimes import Pldt  # 目标：加载PLDT并注册这两个官方命名空间

s = pl.Series("time", [datetime(2024, 1, 31), datetime(2024, 2, 29)])
df = pl.DataFrame({"time": s})

# 原生Series／Expr的平行写法。
result = s.dt.offset_by("1mo")                  # pl.Series
expr = pl.col("time").dt.offset_by("1mo")       # pl.Expr

# 本库同名命名空间：两边写法平行，日期规则复用同一Rust功能。
result = s.pldt.to_next_month()                 # Pldt，亦为pl.Series
expr = pl.col("time").pldt.to_next_month()       # 原生pl.Expr
# 两边日期为2024-02-29、2024-03-29。

# 已创建的Pldt对无原生同名冲突的自有功能保平行直接调用。
result = Pldt(s).to_next_month()                 # Pldt
result = s.pldt.is_month(1)                      # Boolean pl.Series：[True, False]
expr = pl.col("time").pldt.is_month(1)           # pl.Expr，Boolean输出

result = df.with_columns(pl.col("time").pldt.to_next_month().alias("next_month"))
# pl.DataFrame；取出的普通Series仍可直接继续本库命名空间，不强制先包装Pldt。
result = result.get_column("next_month").pldt.to_next_month()  # Pldt
```

Series命名空间只增加一次薄入口，不先构造临时Pldt再调用公开方法，而是与Pldt直接方法共用参数准备／Rust入口，日期输出只构建最终Pldt；查询直接输出原生Series。Expr命名空间按A02直接返回原生Expr，每次日期链再次使用.pldt；不强迫Series先转Expr或重新创建DataFrame来完成普通eager计算。命名空间提供适合实例日期运算的能力，构造／命名工厂／业务状态协议仍按类及各项职责，不承诺给Series／Expr各复制一套全部类接口。

**入口边界：**Series和Expr均注册.pldt，与Pldt直接方法复用同一套参数准备和Rust功能；不增加.rs／.rstimes等等价命名空间别名，不覆盖原生.dt或原生方法。

**3. 显式使用PLDT时一次加载注册：**`from rstimes import Pldt`、`from rstimes.pldt import Pldt`或`import rstimes.pldt`均加载同一模块并使选定命名空间可用。仅需要Expr时可用`import rstimes.pldt`激活，无需手动register调用。普通重复import复用Python模块及真实类／函数缓存，不每个公开方法／每行重新导入或注册。不因新增Pldt根导出而强制基础用户安装Polars；当前共享可选适配的已存在探测行为与“新增PLDT主动加载”分开，不在本项暗中重写所有依赖机制。

```python
import polars as pl
import rstimes.pldt

expr = pl.col("time").pldt.to_next_month()  # pl.Expr
```

没有Polars时，已有基础功能仍能使用；显式加载PLDT时明确ImportError并提示安装可选组`pip install "rstimes[polars]"`。PLDT不因此要求pandas／dateutil／PyArrow。若.pldt已被其他扩展占用，注册时明确报错，不静默覆盖；同库正常重复导入不算冲突。依赖检查、名称冲突检查都在模块准备阶段，不放进每行循环。

**性能影响：**增加的Series命名空间是常数级入口适配，不要求复制列或新建中间Pldt；直接Pldt方法和命名空间共用内核。导入／注册有一次性冷启动成本，必须如实区分首次加载与热调用；不声称零开销或已实测更快。普通计算仍按A01原生执行，Expr按A02引擎执行，返回按A03；实际wheel、类型声明、能力和完整公开调用性能待实施验收。

## B 输入、批量参数与所有权

<a id="pldt-b01"></a>

### B01 一维来源与Date/Datetime/Time准入

**本项范围：**确定普通Pldt构造／对应批量解析接收什么日期集合，按PL01接近Polars，同时保持本库明确日期含义。具体整数／bool、单位默认／转换、全null／缺失、时区及Arrow对象支持分别见B02—B04、C、D、H。所有Pldt代码表示已批准目标。

**真实依据与已确认差异：**当前Pddt的_outer按真实类型读取Polars Date／Datetime，拒绝Time／List／Array／Struct和表；Rust准备器可共用解析字段。Polars2.0.0定点核对支持日期list、datetime tuple、生成器和range；Date能转换为午夜Datetime，Time是纯钟表类型。原生Series拒绝dict／set，却可以将0维NumPy日期包装为一行、将嵌套日期list建为List(Date)。这些是原生行为，不等于PLDT应接收全部Series类型。Pddt允许Mapping键／set实际顺序；本项已确认PLDT跟随Polars拒绝这些外层，明确区别于Pddt，不修改Pddt。

**1. 支持的一维来源及合法元素：**普通list／tuple、一维NumPy数组、原生Polars Series、可选pandas一维日期／对象列、生成器／迭代器／range及合法的一维可迭代来源。每个元素须属于本库支持的日期文本、datetime／Pydt／适用Timestamp、date、NumPy datetime64、合法数字刻度或明确缺失；容器可遍历不表示任何元素都合法。按真实类型／dtype读取，不看类型名／模块字符串或第一行猜全列。生成器仅消费一次，保输入次序和缺失位置。合法混合输入允许，不先转成统一文本再解析。

```python
result = Pldt(["2024-01-01", datetime(2024, 1, 2), None], unit="us")
# Pldt，Datetime(us)：2024-01-01 00:00、2024-01-02 00:00、null。
result = Pldt((date(2024, 1, day) for day in (1, 2)), unit="us")
# Pldt，Datetime(us)，两行午夜；生成器只读取一次。
result = Pldt([0, 1000], unit="ms")
# Pldt，Datetime(ms)：纪元零时、纪元后1秒；裸刻度与秒数工厂仍分工。
result = Pldt([], unit="us")
# 空Pldt，仍为Datetime列；未显式单位的具体选择在C02讨论，缺失规则按已确认B04。
```

pandas来源包括Series、DatetimeIndex等适用Index和ExtensionArray，按位置读取；Pddt真实继承DatetimeIndex，因此也属于该已支持输入类别，不另按名称筛选。MultiIndex／未支持的扩展dtype不猜成日期。pandas支持只在依赖已存在时适配，不因接收pandas来源而使PLDT默认依赖pandas。Arrow互操作通道及对用户公开接收哪些Arrow对象由B03确定，不在这里承诺任意Arrow对象都可用。

**DatetimeIndex／Pddt接入说明：**2026-10-29已从源码和采用产物确认`issubclass(Pddt, pd.DatetimeIndex)`为True，纳秒和Asia/Shanghai来源都能读取真实unit／tz／刻度及缺失位置。拟议Pldt(index)和Pldt(pddt)均返回Pldt，通过同一日期数组适配读取来源，不逐元素转Python datetime／Timestamp、不转字符串、不为识别Pddt额外导入其模块。不能把所有asi8都当ns；带区刻度是实际UTC时刻，保原地区元数据，NaT变Polars有效位中的null。只有来源单位／时区在目标可表示时才能按合同保留；s存储等单位适配与目标容量留C，不能表达的自定义时区留H，不承诺任意Pddt都无条件无损接收。不复制Pddt的索引／freq／业务状态语义到Polars列；name按L01确定的可表达列名规则处理。pandas仍可选，不将PyArrow设为必需，具体薄适配在B03确认；本项尚未实现PLDT。

**2. Date与Datetime均能进入日期角色，输出固定为Pldt日期时间列：**

```python
s = pl.Series("time", [date(2024, 1, 1), None], dtype=pl.Date)
result = Pldt(s, unit="us")
# Pldt，Datetime(us)：2024-01-01 00:00:00、null。
# 日期提升为午夜，不读取本机当前时钟，也不逐行创建Python datetime。

s = pl.Series("time", [1704067200123456789, None], dtype=pl.Datetime("ns"))
result = Pldt(s)
# Pldt，Datetime(ns)，保原始.123456789及null，不能先缩为us。
result = s.pldt.to_next_month()  # Pldt；Date来源的提升单位规则仍按C02。
expr = pl.col("time").pldt.to_next_month()  # 原生pl.Expr，作用于日期列。
```

普通构造可解析String列；日期变换不在每次调用时隐式重新解析任意String／Object列。原生Date先按日期角色提升，Datetime保已知语义；输出单位／tz根据C/H的最终合同，不由第一行猜。带区源数据不能当naive钟表读取。真实Object元素只在eager入口按受支持协议准备；Expr worker不执行任意Python对象回调。

**3. Time／Duration不是完整日期：**

```python
s = pl.Series("clock", [time(12, 30)], dtype=pl.Time)
Pldt(s)  # TypeError：只有钟表，没有日期；提示使用明确组合入口。
result = Pldt.combine([date(2024, 1, 1)], s, unit="us")
# Pldt，Datetime(us)：2024-01-01 12:30:00；combine完整合同留E04。
```

Time用于combine等明确的time角色，不在普通构造中自动补今天；Duration／timedelta是时长，不被当作纪元日期。List／Array／Struct列即使外层Series为一维，其元素也不是标量日期，不自动展开字段或嵌套行。

**4. 普通构造只收一维集合，不猜表／表达式／单标量：**

```python
Pldt("2024-01-01")                # TypeError；改用["2024-01-01"]。
Pldt(datetime(2024, 1, 1))        # TypeError；改用[datetime(...)]。
Pldt(np.array("2024-01-01", dtype="datetime64[D]"))  # ValueError：0维。
Pldt(np.array([[0, 1]], dtype="datetime64[ms]"))      # ValueError：2维。
Pldt([["2024-01-01"]])            # TypeError：data[0]不是单个受支持日期值，不展平。
Pldt(df)                         # TypeError；用户显式取df.get_column("time")。
Pldt(lf)                         # TypeError；使用LazyFrame表达式入口，不暗中collect。
Pldt(pl.col("time"))             # TypeError；使用已确认的Expr.pldt入口。
```

data位置字符串不兼作Series名称；命名可显式name=，不以字符串内容猜用户意图。单值工厂是否／如何广播按E/B02合同，不能将普通构造的拒绝扩大为禁止全部标量工厂。空集合仍合法，所传选项需要正常校验。

**与当前Pddt的定点对照：**2026-10-29用公开采用环境核对14个代表输入：合法混合值／Date午夜／Datetime纳秒／生成器均可用，Time／单标量／表／Expr拒绝，0维／2维NumPy为ValueError，嵌套list的元素类型为TypeError。嵌套list统一为TypeError，不新增错误分类差异；本项主要有意区别为Mapping／set／frozenset直接拒绝，另有本来就按容器区分的Pddt／Pldt、NaT／null输出。此对照不是PLDT实现验收，也不代表单位／时区等后续项目已相同。

**5. 直接拒绝Mapping及set／frozenset，要求显式选择列内容：**

```python
mapping = {"2024-01-01": 10, "2024-01-02": 20}
Pldt(mapping)                    # TypeError，与原生Polars构造一致。
result = Pldt(list(mapping), unit="us")  # Pldt；用户明确选择键作为日期。
Pldt({"2024-01-01", "2024-01-02"})       # TypeError。
```

Pldt直接拒绝Mapping／set／frozenset；用户需要显式选择键、值或实际迭代内容后构成合法一维输入。不替用户选择values、不排序、不改变Pddt现有合同。

**性能影响：**已是原生Datetime的来源优先直接取得typed列／chunk／validity及owner，避免to_list／逐行Python日期中转；Date用原生整数提升，只有必要结果缓冲分配。Python混合值／Object仅在入口读取一次，纯Rust解析／计算后生成最终Pldt；文本不调用pandas／Polars解析来改变共同语法。维度、dtype与容器拒绝尽量在入口或schema阶段完成，避免扫整列猜类型；安全复制／保owner按B05，不能宣传所有来源零复制。本项无PLDT正式性能数据。

<a id="pldt-b02"></a>

### B02 标量广播、逐行参数、真布尔与整数规则

**范围与事实：**确定自有逐元素日期操作的数值／字段／查询参数如何准备和配对，不为所有参数自动增加逐行能力。Pddt当前是标量广播、明确集合严格等长；Polars不同原生操作的长度边界存在差异，不能由其中一个操作推出统一的日期广播合同。已确认自有共同日期方法沿用Pddt的行配对规则，容器及表达式接入遵循Polars；源文件arguments.rs的Scalar／Values结构可借鉴。所有Pldt代码表示已批准目标。

**容器与广播答疑：**当前Pddt已实际支持其已开放逐行参数接收list、一维NumPy列、Polars Series和pandas Series；本次对replace(day=...)四种两元素输入得到相同结果，pandas标签不参与配对。接受同一种容器不表示接受同一种广播：这些一元素集合在两行Pddt上均报ValueError，只有真正标量能广播。此说明不扩大Pddt每个参数的职责。

**原生事实与设计取舍：**Polars2.0.0的两行日期replace(day=一元素Series)会广播；一行日期加两行Duration也会扩展为两行。但一行日期replace(day=两元素Series)本次实测仅得到首项目标的一行。这些实际观察保留为参考，不能当作统一广播的依据。为自有日期方法新增一元素集合广播及日期源反向扩展，会增加与Pddt的行为差异和结果行数变化；目前没有其为必要能力或带来性能收益的证据。因此本项已确认严格行配对，未开始实施。

**1. 自有逐行日期方法与Pddt一致：标量广播、集合严格等长、保持日期源行数。**真正标量可应用于全部日期行；list／NumPy列／Series等明确集合必须与日期源严格等长，一元素集合仍是集合。多列按位置逐行配对，不按pandas标签对齐；日期源一行不隐式扩展为多行。空日期源可接受合法标量或等长空参数列，非空集合不因日期源为空而忽略；必要参数及选项仍须校验。不循环补齐、不截掉目标、不作笛卡尔积。

```python
x = Pldt(["2024-01-01 12:00", "2024-01-02 13:00"], unit="us")
result = x.pldt.replace(day=10)        # Pldt：1月10日12:00、1月10日13:00
result = x.pldt.replace(day=[10, 20])  # Pldt：1月10日12:00、1月20日13:00
result = x.pldt.replace(day=[10])      # ValueError：集合长度1与日期长度2不符
result = x.pldt.replace(day=pl.Series([10]))  # 同样ValueError；需要全列10时传标量10
x.pldt.replace(day=[10, 20, 25])       # 不兼容长度，报错；不截取／循环补齐

x = Pldt(["2024-01-01 12:00"], unit="us")
x.pldt.replace(day=[10, 20])           # ValueError：日期长度1与目标长度2不符
result = x.pldt.replace(day=[10])      # Pldt，一行：2024-01-10 12:00
```

本规则限已确认可逐行的自有日期方法，Series／Expr相同功能保持相同行配对含义。Expr里的普通标量参数及pl.lit(10)仍承担标量职责，明确列不单凭运行长度为1就改判标量；聚合／分组等逻辑标量Expr已按M03逻辑标量规则确认：公开原生角色识别、标量自然广播、具体列严格等长，不预先collect；真实插件接线仍须实施验收。已明确完整继承／委托的原生功能保持原有广播与返回规则，不套本库限制。命名工厂的全标量size、列与size关系留E；DST布尔策略／推断的完整位置合同留H，不自动将这些控制参数改作普通数值列。

**取舍理由：**PL01要求合理贴合Polars的Series／Expr及原生生态，同时保留本库共同日期规则；它不要求把Polars某条路径的广播推广为一套新的本库通用规则。已确认规则使Pddt／Pldt共同日期方法保持一致。用户若确实需要一行日期生成多行结果，应显式构造所需日期列；是否另增专门展开能力不在本项默认批准。

**2. Series与Expr参数承担相同日期职责：**

```python
result = s.pldt.replace(day=10)                    # Pldt
result = s.pldt.replace(day=pl.Series([10, 20]))    # Pldt
expr = pl.col("time").pldt.replace(day=10)         # 原生pl.Expr
expr = pl.col("time").pldt.replace(day=pl.col("new_day"))  # 原生pl.Expr
result = df.with_columns(expr.alias("changed"))    # pl.DataFrame
```

显式列用pl.col，普通字符串保留该方法本来的文字／名称职责，不猜列名。例如replace(day="new_day")不代替pl.col("new_day")；to_month("April")等已定义名称用法按F保留。Expr运行时遵守同一标量／列职责及类型规则，最终Frame上下文也需满足原生长度要求；不预先collect查长度，不偷偷截掉行。可判断的Python参数错误尽早报，依赖实际列的形状／数据错误到执行时报告，执行异常边界见N03。

**3. 数值按职责，整数字段不隐式接受bool／float：**年月日／时分秒等整数角色、命名add/sub整数增量、size／periods等数量接受Python整数、NumPy整数和合法__index__。拒绝Python／NumPy bool、1.0等float、数字文本及只有__int__的对象；合法__index__在准备阶段读一次，不在每行重复调用。原生整数列直接读，不统一转Python int。

```python
result = x.pldt.replace(day=np.int64(10)) # Pldt
x.pldt.replace(day=10.0)                 # eager TypeError
x.pldt.replace(day=True)                 # eager TypeError
x.add(days=1.0)                     # eager TypeError
result = x.add(days=-1)             # Pldt，真正向前一天，不是“不改”占位
```

这些是整数角色规则，不扩大为“所有数字都拒绝float”：秒数工厂、原始整值浮点刻度和Delta操作数仍按各自已定职责，在E/C/G确认。带月份／星期名称的参数按其专门职责读取，不因整数规则删除合法词条能力；具体范围／便利上限／精度留F/C。

**4. None、零、负数和null不混成同一占位：**可选绝对字段None保留原字段，零是实际值；有意义的相对负数向反方向调整。绝对字段的显式None逐行位置、原生可空整数字段列的null也表示该行不替换，保持Polars replace式字段职责；Python对象pd.NA／NaN等不自动伪装None。必填增量／查询目标不能因缺失而忽略，日期源null如何返回查询结果留J。

```python
result = x.pldt.replace(hour=None)       # Pldt，保原小时
result = x.pldt.replace(hour=0)          # Pldt，真实改为零时
result = x.pldt.replace(day=[None, 20])  # Pldt，第一行保day，第二行改20
x.add(days=None)                   # eager TypeError
x.is_month(None)                   # eager TypeError
```

tzinfo省略／None、default及工厂None按各自合同处理，不由数值None规则一刀切；来源日期null与参数里的保留标记区分。

**5. 开关和全局选项保持单值角色：**strict／isoformat／copy／absolute等普通开关只收Python bool／NumPy bool，不用0／1或任意__bool__对象代替；yearfirst／dayfirst等已有None优先级另按D。unit／freq／tz／cfg／default／locale／fsp精度等不因逐行广播而扩成参数列。DST策略中bool的专门含义留H，不当整数使用。空／全null／原生输入也检查其实际承担的必要参数职责，但不因此解析本来不相关的default。

**性能影响：**一次识别标量／完整列并检查形状；标量只保存一个原生值，不生成N份Python对象。集合等长检查不要求复制整列，日期内核仍直接读取原生值／有效位。整数／bool与控制参数在入口或schema准备阶段按真实类型判断，循环内使用紧凑原生字段、存在标记及有效位；日期算法继续最小Rust共享。严格配对保留标量快路，减少特殊长度分支；没有PLDT正式性能测量，不声称一定更快。

<a id="pldt-b03"></a>

### B03 NumPy/pandas/Polars/Arrow之间的真实类型与可选依赖

**具体例子：**

```python
# 拟议Pldt入口；NumPy + Polars已安装、pandas／dateutil／PyArrow未安装时也应可用。
import numpy as np
import polars as pl
from rstimes import Pldt

s = pl.Series("time", [1704067200123456789, None], dtype=pl.Datetime("ns"))
result = Pldt(s)
# 类型：Pldt，dtype为Datetime("ns")。
# 值：2024-01-01 00:00:00.123456789、null；不经逐行Python datetime缩成us。

s = np.array(["2024-01-01T00:00:00.123456789", "NaT"], dtype="datetime64[ns]")
result = Pldt(s)
# 类型：Pldt；真实ns保留，NumPy的NaT转换为Polars有效位中的null。
```

**1. 依赖独立并只准备一次：**在rsTimes默认NumPy及适用平台tzdata之外，PLDT额外要求Polars；pandas／dateutil／PyArrow不成为PLDT必须依赖。pandas已安装时，按B01接收适用pandas列、DatetimeIndex及其真实Pddt子类；pandas未安装时，普通Pldt及.pldt功能仍可加载使用。显式加载PLDT而Polars缺失时沿已确认A04的ImportError及安装提示；不影响其它基础类。不为借用私有函数导入pddt.py，复用适合的独立准备／最小Rust内核。真实类及能力在模块准备阶段保存，热调用不重复import／探测；损坏或嵌套依赖错误不伪装成未安装。

**2. 按真实类型和元数据适配：**NumPy读取实际dtype／单位／维度及NaT；Polars读取真实Date／Datetime、unit／tz／chunk／validity；pandas读取实际DatetimeArray单位／tz及NaT，真实Pddt使用同一日期数组适配，不另按名字判定或先造Python日期列表。传入列的name等输出职责仍按L01，容量／秒单位／时区能力仍按C/H逐项决定，不能以“支持该来源”承诺所有值无条件可转换。

**3. 原生互操作有明确安全边界：**优先官方表达式插件及支持的Rust适配，必要跨库传递使用公开Arrow C Data／Stream／PyCapsule协议；Arrow是原生交换协议，不等于必须安装Python包PyArrow。按协议持有数据／释放职责，不以私有_s指针作为跨版本ABI。B03不隐含新增任意Arrow生产者或表对象为公开日期输入，公开输入仍按B01及后续明确批准范围。

**替代及边界：**不通过先转换Pddt、pandas解析或逐行to_list来完成正常Polars列适配。具体Rust Polars／PyO3／插件组合须在M02实际构建证明并冻结版本，不将公开Arrow协议的稳定性推广为所有插件ABI都跨版本稳定。可借数据必须保owner，必要快照／非连续／端序和copy的详细职责留B05；不因追求少复制牺牲安全。

**性能影响：**依赖与类型一次准备，按dtype选择原生批量路径，避免逐行Python datetime／Pydt／int中转；真实转换只分配必要缓冲和最终结果。来源单位转换或缺失表示转换可能需要复制，不能把所有路径宣传成零复制；没有PLDT正式倍率。共享日期算法与Pddt一致，容器适配按Polars执行模型。

<a id="pldt-b04"></a>

### B04 空列、全null、缺失文本和独立default

**具体例子：**

```python
# 以下均为拟议Pldt接口。
s = pl.Series("t", [], dtype=pl.Datetime("ns", "Asia/Shanghai"))
result = Pldt(s)
# Pldt，零行；Datetime(ns, Asia/Shanghai)保留。

s = pl.Series("t", [None, None], dtype=pl.Datetime("ns", "Asia/Shanghai"))
result = Pldt(s)
# Pldt，两行null；显式Datetime单位／时区不因缺失丢掉。

result = Pldt([None, "2024-01-01"], unit="us")
# Pldt：[null, 2024-01-01 00:00:00]，不丢行／填充缺失。
result = Pldt([""], unit="us")
# Pldt：一行null；与当前Pddt([""])的一行NaT含义一致。
result = Pldt([None, "12:30"], unit="us", default="2024-05-07")
# Pldt：[null, 2024-05-07 12:30:00]；default不替代明确缺失。

Pldt(["broken"], unit="us")   # 解析失败，报错；不生成null。
Pldt([" NaT "], unit="us")   # 非批准的缺失文本，按普通解析规则报错。
```

**1. 日期缺失清单与Pddt一致，出口改为Polars null：**日期数据中的None、可选pandas存在时的pd.NaT／pd.NA、合法单位的NumPy datetime64 NaT、已支持浮点类型的NaN及原生日期列有效位中的缺失均保为null；保原位置、长度和顺序，不删除／前后填充。整个文本元素恰为空字符串、NaT／NAT／nat／NaN／NAN／nan也按日期缺失处理，strict两模式一致。不自动strip／lower扩展清单；空格、文本None／null、nAt／nAn或带空格的NaT按普通解析规则处理，不能因失败自动coerce。np.timedelta64 NaT、bool、bytes及其它不支持类型仍拒绝；无穷不是NaN，不能转null。

**2. 空列／全null仍是日期列，并校验实际选项：**保留已明确的Datetime单位、可表达时区及明确列名，不因没有有效日期丢声明元数据；来源name的继承及可接受类型仍由L01确定。空列不产生占位行，null不参与源时区冲突。没有dtype／未指定unit的初次选择统一留C02；不得据第一行猜整列或让原生Null推断替代日期合同。unit／cfg／strict／isoformat／copy及实际DST策略等仍按职责校验；没有实际需要的default除外。

**3. default独立、完整，只补YMD；立即路径按需准备一次：**支持当前Pddt已批准的完整标量date／datetime及真实子类、完整日期文本、Python int／float纪元秒及真实子类、NumPy datetime64；None表示不提供，不扩大为任意数值协议或数组／Series。立即入口首次实际进入普通文本解析时，传入default必须自己完整，按有效cfg／顺序／isoformat／strict准备一次原生YMD；不能借今天或主输入补自己。立即纯原生、空列及全是明确缺失标记的路径不解析无关default，不预扫生成器找文本。已确认D02的文本Expr采用创建时准备／校验的明确例外：即使未来为空／全null，所传不完整default也在创建Expr时失败；只携带原生YMD进入执行，不在worker重放Python来源协议。

```python
result = Pldt(["12:30", "18:45"], unit="us", default="2024-05-07")
# Pldt：2024-05-07 12:30:00、2024-05-07 18:45:00。

Pldt(["12:30"], unit="us")
# ValueError系错误：缺少完整日期；提示提供完整default。
Pldt(["2024-05-07"], unit="us", default="May 7")
# ValueError系错误：已经进入文本解析，所传default自身缺少年份。

result = Pldt(np.array(["2024-05-07"], dtype="datetime64[us]"), default="May 7")
# Pldt：原生日期路径不使用default，不为无关default失败。
result = Pldt([], unit="us", default="May 7")
# 空Pldt：不解析无关default。
Pldt([], unit="us", strict=1)
# TypeError：空列仍须校验普通开关。
```

default只填没有识别的年月日，明确字段和明确缺失优先；不继承default时钟／时区／纳秒或fold来决定整列DST。数值default仍为纪元秒及当前已定us角色，不随Pldt.unit暗改；宽年份／时区能力及两位年份沿后续C/D/H的共同合同。不完整／缺失default为ValueError系错误，不支持类型为TypeError，报错给出default上下文。

**替代及边界：**不增加errors='coerce'、自动丢坏行、失败转null或部分成功输出。日期源缺失与目标字段／增量／查询缺失按B02/J分别处理；地区策略明确选择null的专门职责留H，不扩大为吞普通解析失败。Parser／Pydt标量不因本项新增缺失日期返回能力。

**性能影响：**立即空／全null路径省去日期计算及无关default准备，但不省必要选项校验；原生有效位尽量直接传播，不为每个null创建Python对象。立即default首次需要时转成原生YMD并复用，文本Expr按D02在创建时准备；两者都不逐行解析default，也不先造Pydt／Pddt中转。缺失文本只做精确短标记检查，不对全部文本先分配strip／lower副本；没有PLDT实测倍率，不承诺零成本或必然提速。

<a id="pldt-b05"></a>

### B05 输入借用、copy和对外Series是否暴露可变外壳

**范围：**讨论立即构造Pldt时的输入借用、构造copy参数、Series对象／列状态句柄与底层日期数据的区别，以及普通Series出口的所有权。本项构造借用与业务copy协议／继承方法分工明确；后者已按L02—L04收口。不修改产品实现。

**具体例子：**

```python
# 拟议Pldt构造：创建独立列对象，允许安全共享底层日期数据。
s = pl.Series("t", [1, 2], dtype=pl.Datetime("ns"))
x = Pldt(s, copy=False)
s.append(pl.Series("t", [3], dtype=s.dtype))
# s：pl.Series，长度3。
# x：Pldt，长度仍为2，刻度仍为[1, 2]。

result = pl.Series(x)
# result：普通pl.Series，独立列对象，可安全时共享底层数据。
result.append(pl.Series("t", [4], dtype=result.dtype))
# result长度3；x长度仍为2。不要求用户使用新造的to_series方法。
```

**1. 始终分开构造入口的列对象，安全共享数据：**Pldt(s, copy=False)应持有独立的真实Series对象／列状态句柄，即使来源本来就是Pldt，也不以返回输入对象实现普通构造。源Series的append或原生列状态替换不能改变新Pldt的长度／列状态。利用Polars支持的独立句柄／共享缓冲机制，直接构造最终Pldt，不先做一个临时Pldt再包装；不拿私有_s指针当跨版本ABI。底层数据共享与两个Python变量指向同一对象分别处理：y=x仍是同一个对象，不能承诺对其原生原地修改彼此独立。

**2. 构造copy=False允许安全借用，copy=True保证日期数据隔离：**沿Pddt同一职责，copy=False是允许而非强制零复制；单位／布局／缺失表示转换或安全条件需要时可以复制。copy=True须使输入后续写入不能改变构造结果的日期数据，不以clone或原生Python deepcopy名称代替实际缓冲隔离证据；有效位、ns、unit及可表达时区一并保持。共享不可变元数据不等于未隔离日期数据。若本次解析／转换已经生成独立拥有的原生结果缓冲，不因copy=True再复制一次，也不由该参数额外深复制cfg／default／任意业务状态。

```python
# 原生Polars真实参考：clone不等于外部可写缓冲快照。
a = np.array([1, 2], dtype=np.int64)
s = pl.Series("t", a, dtype=pl.Datetime("ns"))
result = s.clone()
a[0] = 9
# 在已核对2.0.0／2.1.0中，result为pl.Series，刻度变为[9, 2]。

# 拟议Pldt的显式隔离合同。
a = np.array([1, 2], dtype=np.int64)
x = Pldt(a, unit="ns", copy=True)
a[0] = 9
result = x.cast(pl.Int64)
# result：pl.Series[Int64]，值仍为[1, 2]。
```

**3. owner／只读标记与并发稳定性分别保证：**保有Python owner或Rust共享所有权，使删除来源变量后缓冲仍有效；正确处理切片offset、多个chunk、null、合法非连续输入及字节序。持有owner只解决存活，不阻止其它别名写入；只读NumPy视图也不证明其base／其它别名不可写。copy=False不承诺构造后是独立数据快照，需要这种隔离时使用copy=True。释放GIL／原生并行计算时，不能借owner或GIL假定数据稳定；按适配器实际可保证的借用条件运行，必要时取得安全快照，不能把已知可写不稳定缓冲当作不可变Rust引用。对不受控外部写入不提供并发快照保证，也不承诺任意指针别名可被自动探测。

**4. 保持Polars的Series使用模型，普通导出不暴露同一可变句柄：**Pldt本身就可供Polars使用，不要求先to_series；显式需要普通Series时可用pl.Series(x)，其外壳独立、允许安全共享日期数据，不额外新增to_series方法。它的append等正常外壳修改不替换x的列状态，底层外部写入风险仍遵守copy合同。本项不增加全局冻结层或把Pldt宣称为不可变Index；具体继承可变方法／返回与算术协议在L04完整确认，业务copy／deepcopy／pickle在L02确认。自有日期计算仍遵守不修改来源；无变化运算的对象身份及返回细节按相应结果合同，不由本构造规则泛化。

**性能影响：**普通原生Series通过廉价句柄共享避免全列数据复制；准确成本与chunk／适配有关，不将所有来源一概承诺为O(1)。copy=True或必要快照在已有缓冲上通常需要O(N)复制，百万行int64日期数据约8MB，若有有效位另计；不经过Python列表／逐行datetime。能直接使用多个chunk就不为方便强制rechunk，只有算法或布局需要才整理；新拥有的解析结果直接转交最终出口。持有owner／元数据成本与必要复制分开，实施须通过共享／修改／释放来源及完整公开调用测量证明，无PLDT速度倍率。

**验收要求：**正常源append／scatter后检查新Pldt的长度和值；copy=False以适用原生来源验证真实共享，不把所有路径必须共享作为门槛；copy=True用原始可写数组后续修改及共享检查证明隔离。覆盖删除来源后继续使用、合法stride／端序、slice／多chunk／null／ns／tz，不仅比较构造当下的值相等。业务状态／继承方法完整性按L02—L04另验，不由本项冒称已完成。

## C 单位、有效位、精度与容量

<a id="pldt-c01"></a>

### C01 原生ms/us/ns与不支持秒单位的边界

**具体例子：**

```python
# 以下Pldt为拟议接口。
x = Pldt([1], unit="ms")
# Pldt，Datetime(ms)，日期为1970-01-01 00:00:00.001；原始刻度1。
x = Pldt([1], unit="us")
# Pldt，Datetime(us)，日期为1970-01-01 00:00:00.000001；原始刻度1。
x = Pldt([1], unit="ns")
# Pldt，Datetime(ns)，日期为1970-01-01 00:00:00.000000001；原始刻度1。

Pddt([1], unit="s")          # 当前Pddt：datetime64[s]，纪元后1秒。
Pldt([1], unit="s")          # ValueError：不支持秒存储，列出ms/us/ns。
x.as_unit("s")              # ValueError：目标日期dtype也不支持s。
```

**1. 日期存储只支持ms／us／ns：**公开构造unit及as_unit的目标日期单位与真实Polars dtype一致。显式unit="s"为ValueError，说明合法单位及来源秒数据的使用方式；非字符串／未知单位按既有参数职责处理，不能静默将显式s改成ms或只维护一个假的逻辑s标签。无unit时如何按所有来源选择默认值留C02，不把本项简写为所有输入默认ms或us。

**2. 接收原生存储单位为s的合法来源，默认精确提升到ms：**对已批准接收的NumPy datetime64[s]、pandas日期数组／DatetimeIndex及Pddt的s来源，无显式目标且该来源没有更细精度要求时，以1000倍整数刻度构成Datetime(ms)。若明确指定合法us／ns，直接向该目标换算，不先创建ms对象再转换。混合来源的共同单位按C02；普通fromseconds数值工厂不因其输入含义为秒就套本规则，其默认单位及坐标按E板块。保真实时刻和原NaT位置，后者按B04转null，不对NaT哨兵作普通数值乘法。

```python
s = np.array([1, 2], dtype="datetime64[s]")
p = Pddt(s)
# 当前输出Pddt，unit=s，刻度[1, 2]。

x = Pldt(s)
# 目标输出Pldt，dtype=Datetime(ms)，刻度[1000, 2000]。
# 两个实际日期仍为1970-01-01 00:00:01、00:00:02。
result = x.cast(pl.Int64)
# pl.Series[Int64]：[1000, 2000]。

s = Pddt([1, 2], unit="s")
x = Pldt(s)
# 相同的目标输出Pldt／Datetime(ms)，不先逐行生成Python日期。
```

**3. 目标容量不足时报OverflowError：**s可存不代表ms可存，按最终目标单位进行checked整数换算，不回绕、不截尾、不变null或退成Int64／Object。ms已经是Polars最粗Datetime单位，ms仍放不下的秒来源不能靠us／ns解决，也不能继续建议在Pldt内部as_unit("s")。报错应说明来源单位与目标ms的容量限制，提示保留在支持s的Pddt／NumPy来源或自行选择可表示数据范围。全列有一项失败则整次失败，不交付部分Pldt。已有Pldt的固定单位运算及主动降精度在C03确认，不由本项为后续运算增加自动改单位。

```python
limit = (2**63 - 1) // 1000
s = Pddt([limit + 1], unit="s")
# 当前Pddt可保存该s刻度。
Pldt(s)
# OverflowError：该值乘1000后的ms刻度超出目标int64容量。
# 不自动截取、回绕、变null或伪装成可存s的Pldt。
```

**4. 秒仍可作为输入含义、取整周期或整数导出单位：**日期存储能力与输入／周期／整数输出职责分开；不因无Datetime(s)而取消秒数工厂或秒级操作。原生整数导出可用x.dt.epoch("s")，返回普通Int64 Series；Expr同义导出返回原生Expr，执行后的列为Int64，原日期列dtype不改变。周期操作的具体freq／舍入含义留I，数值工厂坐标留E，进一步自有导出语义留K，本项不隐含新增其余能力。

```python
x = Pldt(np.array([1, 2], dtype="datetime64[s]"))
# 建议Pldt，Datetime(ms)，刻度[1000, 2000]。
result = x.dt.epoch("s")
# 原生pl.Series[Int64]：[1, 2]；这是整数秒输出，不是Datetime(s)。
expr = pl.col("time").dt.epoch("s")
# 原生pl.Expr；在相同日期列上执行得到Int64列，值[1, 2]。
```

**与Pddt的明确差异：**Pddt可真正保存s单位，PLDT最粗仅ms；s来源可无损转ms时日期含义相同但原始刻度／dtype不同。极宽s来源可能只有Pddt／NumPy可存而Pldt不可存。这是宿主真实类型能力的差异，不改变Pddt、Parser或Pydt的现有支持，不增加逻辑单位兼容层。

**性能影响：**合法同单位原生列沿B05安全借用；s到ms在Rust中单遍checked乘1000并生成必要结果缓冲，O(N)，不经过float、统一int64 ns、Python datetime或中间Pddt／Pldt。源到显式目标直接换算，避免较窄中间单位制造假溢出；来源单位只准备一次，循环中处理原生刻度及缺失位。非法unit在入口／规划时拒绝，不为确认s不支持扫描日期。单位转换确实可能需要新缓冲，不能称零复制；未测PLDT正式倍率。

**验收要求：**核对三种存储dtype及显式s拒绝；NumPy／DatetimeIndex／Pddt的s来源正负刻度、NaT、空来源声明单位、时区元数据及直接显式目标换算；验证s→ms的两端安全边界和一格越界均按目标检查。原生s导出的整数结果及dtype独立核对，禁止以dtype标签或与另一同源错误结果相等代替真实整数预期。

<a id="pldt-c02"></a>

### C02 初次单位选择与Expr在读数据前必须确定dtype

**范围与当前事实：**本项区分立即构造／Series立即解析的初次单位选择，与Expr在规划时确定输出dtype；后续日期运算固定单位见C03。Pddt是立即的DatetimeIndex构造，可随一次输入准备积累来源精度；Polars Expr必须在执行前通过参数／输入schema／明确方法合同确定输出字段，不能按某行／某批内容升级单位。原生字符串解析默认us的T11观察不能作为PLDT丢掉ns的理由；本库文本仍使用共享Rust Parser。

**真实核查：**C02/unit-and-schema-reference.py在现有两环境各记录34个Pddt单位观察及6个原生Polars schema观察，含7／8／9位小数、九位零尾数、原生单位、空／缺失来源、单遍生成器、显式单位和宽年／ns冲突。Pddt在普通文本／datetime使用us，7—9位文本及原生ns来源保ns；无单位信息的空／缺失集合为s，PLDT按已确认C01映射到ms。原生schema观察验证已知Datetime单位可传播、指定文本单位可在坏文本真正解析前确定；不是已实现的PLDT插件证明。pandas3.0.6／3.1.0用相同Timestamp构造参数生成的实际单位可能不同，补充记录已确认Pddt读取真实来源unit，而非根据构造参数猜单位。

**具体例子：**

```python
# 以下Pldt／.pldt为拟议接口，Expr解析入口暂以parse表示，具体命名留D。
x = Pldt(["2024-01-01"])
# Pldt，Datetime(us)。
x = Pldt(["2024-01-01 00:00:00.123456789"])
# Pldt，Datetime(ns)，保真实纳秒。
x = Pldt(["2024-01-01 00:00:00.123456000"])
# Pldt，Datetime(ns)；来源声明九位，不因末三位为0自动降us。
x = Pldt([1])
# Pldt，Datetime(ns)，刻度1；裸数字默认是纳秒刻度。
x = Pldt([1], unit="ms")
# Pldt，Datetime(ms)，刻度1；显式单位从输入解释开始生效。
```

**1. 立即路径尽量沿用Pddt来源规则，s按C01映射到ms：**显式合法unit优先成为目标，不先构造另一单位对象。未指定时，对已批准的合法来源采用下表；不按最先一行推整列，不将default的时钟／ns作为日期数据精度。目标仍须满足C03的无损／容量规则。

|未显式unit的来源|当前Pddt|PLDT规则|
|---|---|---|
|有效普通日期／整数秒文本，至多6位小数秒文本|us|us|
|合法7—9位小数秒文本，含额外小数位为0|ns|ns；不按实际整除性降单位|
|datetime／Pydt|us|us|
|适用Timestamp、原生日期列已有ms／us／ns|真实来源单位|真实来源单位|
|原生日期来源为s|s|ms；沿C01直接精确换算|
|date／Polars Date／合法粗于秒的NumPy日期|s|ms；按真实日期换算|
|合法裸数字／原生数值列|ns|ns|
|无日期／数值单位信息的空集合或全部明确缺失，如None／pd.NaT／pd.NA／数值NaN／缺失文本标记|s|ms|
|声明单位的空／全缺失日期来源，或带单位的NumPy NaT标量|保其来源单位|保来源ms／us／ns，s／更粗按C01及本表映射|
|合法的空原生数值列／全NaN原生浮点列|ns|ns；不同于无单位的全缺失列表|

无有效日期且没有日期／数值分辨率的String／Null／Object来源，不仅凭字符串dtype猜us；按无单位缺失集合的ms默认。原生Datetime(ns)空列与一个普通空列表并非同一来源；已声明ns的NaT也不当无单位None。所有dtype及元素准入仍按B01—B04，不由本表放行非法bool、扩展浮点或不支持的NumPy单位。

```python
x = Pldt([])
# Pldt，Datetime(ms)：与Pddt空集合默认s经C01映射的方向一致。
x = Pldt(np.array([], dtype="datetime64[ns]"))
# Pldt，Datetime(ns)：来源本来声明了ns。
x = Pldt([None, np.datetime64("NaT", "ns")])
# Pldt，两行null，Datetime(ns)：NaT标量仍携带来源单位。
x = Pldt(np.array([], dtype=np.float64))
# Pldt，Datetime(ns)：原生数值列沿裸刻度职责。
```

**2. 混合来源选共同精度，只有初次构造允许这次自动选择：**未指定unit时，在单次输入准备中累计各有效来源及已声明单位的精度要求，采用能保留全部来源要求的较细单位，次序不影响选择。生成器仅消费一次；不为推断unit再遍历一遍或重新解析文本。共同单位容量不足则OverflowError，不偷偷退粗、丢尾数或把坏行变null；指定较粗目标是否无损仍按真实结果检查，具体规则在C03确认。构造完成后的对象unit固定，不因后续运算再自动升降。

```python
x = Pldt(["2024-01-01", "2024-01-01 00:00:00.123456789"])
# Pldt，整列Datetime(ns)，不是一行us、一行ns。
x = Pldt(["2500-01-01"])
# Pldt，Datetime(us)，不因统一默认ns而人为缩窄普通日期范围。
Pldt(["2500-01-01", "2024-01-01 00:00:00.123456789"])
# OverflowError：共同要求为ns，2500年不能用ns存储。
```

**3. Expr输出dtype在规划时确定：**相同表达式在DataFrame和LazyFrame中使用同一规则，不因DataFrame立即执行就偷偷读取日期样本推断unit。已有Datetime Expr可从输入schema保留unit／时区；Date Expr可固定映射ms；合法普通数值构造Expr在未指定时固定按ns刻度解释。明确unit直接成为目标。未知或不支持原生dtype依B/M拒绝，不读第一值或执行Python对象回调来猜日期类型。

```python
expr = pl.col("time").pldt.to_next_month()
# 原生pl.Expr；若time输入schema是Datetime(ns, UTC)，日期输出仍为该dtype。
# 不要求每个已有日期操作重新指定unit。
```

**4. 普通共享文本Expr必须显式指定unit：**Polars的技术要求是规划器能提前确定输出dtype；这本身不等于要求用户必须亲自填写unit。本库选择显式目标，是因为Pddt那套完整自动选择规则需要实际文本内容：同为String，普通日期默认us、九位小数默认ns、2500年普通日期默认us；仅有输入字段String无法知道应选哪个。官方插件output_type_func接收输入Field信息，并不接收待解析的整列内容。规则完整不代表执行这些规则所需的数据在规划阶段已知。

普通共享文本Expr明确指定ms／us／ns，缺少unit在schema／规划阶段报错，即使本次为空／全null也不因行数改变合同。不必承诺在尚未知输入dtype的Python表达式构建一刻就报错。可在Python入口判断的非法显式选项尽早报，依赖schema的错误在规划时判断。输出单位固定不等于任意值都合法，精度不足／容量／解析错误在执行时失败，Polars异常边界见N03。

```python
lf = pl.LazyFrame({"text": ["2024-01-01 00:00:00.123456789"]})
expr = pl.col("text").pldt.parse(unit="ns")
# 原生pl.Expr；示例文本无时区。
query = lf.select(expr.alias("time"))
# 原生pl.LazyFrame，计划输出time为Datetime(ns)。
result = query.collect()
# 原生pl.DataFrame，time列保123456789纳秒；取result["time"]为普通pl.Series。

expr = pl.col("text").pldt.parse()
# 对String来源在规划阶段报缺少unit错误。
expr = pl.col("text").pldt.parse(unit="us")
# 输出dtype仍固定us；上述有真实非零ns尾数的文本在执行时按无损构造失败，不能静默截尾。
```

这里明确收窄原草案的约束：**不要求所有产生日期的Expr工厂一律额外传unit。**凡来源schema或明确的方法／格式默认已能决定输出单位，直接推导；只有原默认确实依赖尚未读取的行值、又无固定规则可推导时，才要求显式unit。各工厂及专用格式细节在E／D04确认，不能为减少参数擅自改其原职责。所有Expr输出字段均通过官方schema／插件output_type_func等适用机制声明，不在collect中把已声明us改为ns；全null／空batch也遵守固定字段。

**选择依据：**不新增固定us默认，以免将Pddt本可自动保留的真实ns变为默认失败；也不新增固定ns默认，以免普通宽日期被默认容量缩窄。Polars原生str.to_datetime允许省略time_unit，并可从明确格式推导单位或使用us默认；它不是承诺Pddt式无损逐值自动us／ns选择。本库普通文本Expr采用明确目标，是已批准的使用差异。若先完整准备日期并物化为Series，再按已知dtype加入后续计划，则可以自动选单位，但这是显式立即／延迟边界。不能提前抽样、隐式扫描或collect来伪装完全延迟。

**时区及其它边界：**本项只确定dtype里的时间单位，时区同样是schema的一部分，按D03／H01另定；以上文本示例均为naive，已有带区Datetime Expr保原schema。不由本项批准任意混合地区文本推断、提前解析无关default或临时改变tz。立即Series命名空间与Pldt构造同属立即路径；普通Expr解析入口最终名称仍留D，不因示例写法自动定名。

**性能影响：**已知原生来源只读元数据即可决定候选单位，普通同单位可沿B05借用；自动文本／混合输入随单次读取积累最少原生精度信息，随后写出最终缓冲，不重复消费源、不重解析、不中转Python日期或统一int64 ns。显式目标可提前准备并融合检查／写出。Expr不额外扫描文本选dtype，schema选择成本不随行数增长；全列解析本身仍O(N)，预先声明dtype不等于免除数据检查或必然提速。无PLDT正式倍率。

**验收方式：**按表逐类覆盖默认及显式单位、7／8／9位与全零尾数、原生单位空／全缺失及单个带单位NaT、普通缺失与数值dtype差别、混合次序及单遍生成器；精度／容量不足不能自动改单位。普通String Expr在有值／空／全null时均要求明确unit；已知schema或明确方法规则可决定单位时不额外强制。DataFrame／LazyFrame保持同一规则，跨batch不变字段。实际插件证明在M02完成，不以本次原生schema探针代替。

<a id="pldt-c03"></a>

### C03 固定单位、无损构造与主动as_unit降精度

**范围与当前事实：**本项只讨论自有日期构造／变换／as_unit的单位与精度合同，不替代round／ceil／floor／fsp、strptime小数处理、取当前时间和整数导出的独立职责。已确认C01只提供真实ms／us／ns，C02只在初次构造选择单位；本项明确构造完成后如何保持和主动转换。以下接口是已批准的新版本目标。

**1. 显式构造单位无损，但不按小数位数机械拒绝：**如果真实值可以精确表达，来源声明ns仍可显式构造us；真实非零ns尾数不能容纳才失败。构造本身不新增round_ok开关。

```python
source = pl.Series("time", [1000, -1000], dtype=pl.Datetime("ns"))
x = Pldt(source, unit="us")
# Pldt，Datetime(us)，真实整数刻度[1,-1]，两行都无损。

source = pl.Series("time", [1500, -1500], dtype=pl.Datetime("ns"))
Pldt(source, unit="us")
# ValueError：真实值不能用整数us准确表示；不是自动取[1,-2]。

x = Pldt(["2024-01-01 00:00:00.123456000"], unit="us")
# Pldt，Datetime(us)，时间保留为.123456；来源额外三位全零，允许。
Pldt(["2024-01-01 00:00:00.123456789"], unit="us")
# ValueError：非零纳秒尾数不能在us中保留。
```

**2. 已有对象的普通日期运算保持单位，用户主动升精度后再操作：**add／sub及对应自有日期变换不能自动升细／退粗、截掉精度、警告后继续或把失败行变null；具体字段合法性及地区策略仍按对应项讨论。判断的是完整真实结果，而不是单凭出现nanoseconds或microseconds参数就拒绝。

```python
x = Pldt([1], unit="ms")
# Pldt，Datetime(ms)，时间为纪元后1毫秒。
x.add(nanoseconds=1)
# ValueError：结果1.000001毫秒，当前ms不能准确表达。

y = x.as_unit("ns").add(nanoseconds=1)
# Pldt，Datetime(ns)，整数刻度[1000001]。
y = x.add(microseconds=1000)
# Pldt，Datetime(ms)，整数刻度[2]：增量恰好为1毫秒，允许。
y = x.add(microseconds=1, nanoseconds=-1000)
# Pldt，Datetime(ms)，整数刻度仍[1]：先合并实际增量，两者相抵。
```

**3. 主动as_unit统一接口与Pddt相同：**`as_unit(unit, round_ok=True)`；unit单值只收ms／us／ns，round_ok沿B02只收Python／NumPy真布尔。True明确允许此次单位转换减少精度，取更早的目标刻度；False要求精确。两者都不允许真实容量溢出。不会将原整数直接改dtype标签来冒充转换，也不经过浮点秒。

```python
x = Pldt([1500, -1500], unit="ns")
y = x.as_unit("us")
# Pldt，Datetime(us)，整数刻度[1,-2]，默认round_ok=True。
y = x.as_unit("us", round_ok=True)
# 同上；1500ns→1us，-1500ns→-2us，不向零或取最近。
x.as_unit("us", round_ok=False)
# ValueError；来源x及其单位／值不变。

x = Pldt([1000, -1000], unit="ns")
y = x.as_unit("us", round_ok=False)
# Pldt，Datetime(us)，整数刻度[1,-1]，无损通过。
```

|来源刻度／ns|主动换成us，round_ok=True|round_ok=False|
|---|---|---|
|1500|1|ValueError|
|-1500|-2|ValueError|
|1000|1|1|
|-1000|-1|-1|

负数语义表示纪元之前的真实时间，不能用Rust默认整数除法向零截取。更早取整也只约束此次as_unit等已明确的出口，不能套到全部日期函数。

**4. 容量检查和精度检查分开：**不能准确表达真实精度为ValueError；转换或运算结果超出目标物理刻度范围为OverflowError，并提示显式选择适合的as_unit。即使round_ok=True也不能把2500年的us时间转成ns。日期函数不因容量不足自动退到us；需要用户先调整单位。

```python
x = Pldt(["2500-01-01"], unit="us")
x.as_unit("ns")
# OverflowError：目标ns容量不足，允许减精度也不能放宽容量。
y = x.as_unit("ms", round_ok=False)
# Pldt，Datetime(ms)；本例整日值可无损表达。
```

**5. Series与Expr共用同一数学规则：**Pldt直接调用与普通Series的.pldt入口输出Pldt；Expr的.pldt入口直接输出原生pl.Expr，目标Datetime单位在规划时固定。值依赖的精度／容量错误在执行时出现，不先扫描整列来改schema。Expr异常边界见N03，不能先承诺插件错误全部保留同一Python异常类。

```python
s = pl.Series("time", [1500, -1500, None], dtype=pl.Datetime("ns"))
y = s.pldt.as_unit("us")
# Pldt，Datetime(us)，整数刻度／缺失为[1,-2,null]。

expr = pl.col("time").pldt.as_unit("us", round_ok=True)
# 原生pl.Expr；输入time为Datetime(ns)时输出字段为Datetime(us)。
result = pl.DataFrame({"time": s}).lazy().select(expr).collect()
# 原生pl.DataFrame；time是普通pl.Series，Datetime(us)，[1,-2,null]。
```

保列名／时区／原null位置和合法chunks等必要元数据；as_unit只改变存储分辨率，不重新解释当地墙钟，不做地区DST存在性检查。任一有效行失败则本次自有调用失败，不交付部分成功列或修改来源；null不参与数值换算，具体全i64及跨NaT生态边界留C04。空／全null照样校验明确unit和round_ok，不能因数据空就接受unit="s"或round_ok=1。

**与Pddt的差异：**数学和精度规则完全一致，包括默认round_ok=True、负数向更早刻度、结果合并及整次失败。Pddt日期存储支持s／ms／us／ns，Pldt沿C01仅ms／us／ns；Pddt结果为Pddt／NaT，Pldt日期结果为Pldt／null，并额外提供原生Expr。Polars自身cast_time_unit允许减少精度，原生ms日期加1ns Duration的本次样例仍为原ms刻度；这不能代替本库无损构造／固定单位合同。完整继承／明确委托的原生操作仍保原合同，不重写全部.dt或Polars算符。

**推荐：**采用上述完整Pddt数学规则及Polars容器出口。若允许普通运算自动升级，或者构造时默认截取，虽然部分调用会成功，却破坏已确认的固定schema／无损方向，也与Pddt分叉，不推荐。不是禁止使用已证明安全且符合合同的成熟原生算子，而是不使用未经必要检查的cast来冒充这些保证。

**性能影响：**单位及倍率在循环外准备；同单位走元数据快路，不为证明不变额外全列扫描。变单位时检查和写出尽量融合成一次原生遍历，沿chunks读取ticks／validity、复用有效位，不逐行创建Python日期或数字。精确转换余数、目标范围检查是必要成本；允许减精度路径可省去无损余数拒绝，但仍做范围检查。可共享Pddt的最小换算数学，PLDT的validity／全i64／所有权出口独立；必要时用checked i128中间值，不先把整列塞进可能溢出的int64 ns。尤其不因地区tz给单位缩放增加本地化往返。尚无PLDT测速，不承诺这些检查的具体百分比成本或必然快于Polars cast。

**验收要求：**用独立整数预期覆盖正负精确／不精确值、零尾数文本、细化容量两端及越界、普通运算的相抵与真实余数；覆盖标量／等长列参数、空／全null／混合null、chunks／slice、name／tz、来源不变及整次失败。Series和Expr按同一预期核对，Expr同时检查schema与执行结果，不用两个同源入口相等代替正确答案。检查缩放不重新调用Parser或地区本地化；性能按受影响范围保护既有Pddt／Parser／Pydt，正式方案后定，不在讨论轮采集。

<a id="pldt-c04"></a>

### C04 Polars独立有效位与完整int64值域，以及跨NaT生态的无损转换

**1. 推荐保留Polars真实值域，缺失只由有效位判断：**日期原始刻度支持`-2**63`至`2**63-1`，null在独立validity中表示；不能把某个整数保留成PLDT自己的缺失哨兵。有效位为0时该槽的数值载荷没有日期意义，不能要求它一定是0或最小值。无null时可沿原生省略全有效位图表示，不能要求每列都新建一张位图。

```python
MIN = -(2**63)
s = pl.Series("time", [MIN, None, 0], dtype=pl.Datetime("ns"))
s.is_null().to_list()
# 当前原生Polars实测：[False, True, False]。
s.to_physical().to_list()
# 原生pl.Series(Int64)转list：[MIN, None, 0]。

x = Pldt(s)
# 建议：Pldt，Datetime(ns)，有效／缺失位置原样保留。
x.is_null().to_list()
# 建议：[False, True, False]。
```

在ns下，MIN是有效日期`1677-09-21 00:12:43.145224192`，不是缺失。ms／us同样可保存其完整物理int64，只是对应日期更宽；不能用先转Python datetime的方式验证其有效性。本次三个单位的两端刻度及独立null均已核对。

**2. 相同整数位模式按来源职责解释，不能全局猜NaT：**PLDT裸数字和原生整数列的MIN是真实刻度；已有NumPy datetime64／传统pandas日期／Pddt的NaT是来源已经声明的缺失。读取真实dtype与有效位，不根据单个整数脱离来源判定。

```python
x = Pldt([MIN], unit="ns")
# 建议：Pldt，Datetime(ns)，一条有效日期。
x = Pldt(np.array([MIN], dtype=np.int64), unit="ns")
# 同上，整数来源的MIN是数值。
x = Pldt(np.array([MIN], dtype="datetime64[ns]"))
# 建议：Pldt，Datetime(ns)，一条null；此来源已经把MIN定义成NaT。
x = Pldt(Pddt([None], unit="ns"))
# 建议：Pldt，Datetime(ns)，一条null；不把既有NaT复活成有效日期。
```

Pddt现有裸MIN仍保NaT，这是已采用的pandas值域合同，不为PLDT反过来更改。PLDT内部计算的最终值恰好为MIN也应保有效；低于MIN／高于MAX才按物理容量OverflowError，不回绕或把失败变null。不能直接复用Pddt把MIN过滤／填成NaT的pack；只共享单位及checked日期数学，最终日期缓冲按各目标输出。

**3. 普通datetime64目标撞NaT保留值时默认明确失败：**NumPy普通datetime64及传统pandas DatetimeArray／DatetimeIndex／Pddt无法在同单位同坐标下区分“有效MIN”与NaT。当前Polars原生to_numpy把上述s转换后，np.isnat结果为`[True,True,False]`，有效第一行丢失。不能把两个来源都变成NaT称为无损；新增选择参数只讨论用户是否可明确请求这一次有损表示，不改默认安全规则。

```python
x = Pldt(s)
x.to_numpy()
# 建议：OverflowError，不能把第0行有效MIN变成NaT。
# 不改单位、不加1ns、不改成object数组，也不返回部分结果。

y = Pldt([0, None, 1], unit="ns")
array = y.to_numpy()
# 建议：numpy.ndarray，dtype=datetime64[ns]。
# np.isnat(array).tolist() == [False, True, False]，原null可正常变NaT。
```

本库自有的传统pandas日期／Pddt转换也遵守同一边界。错误注明入口、行位置、目标格式的NaT保留值冲突及可保值的Arrow／整数有效位路径。NumPy的隐式数组协议应沿相同受保护的日期出口，不让np.asarray绕开检查；当前Polars Series.__array__会调用self.to_numpy，可复用该公开分派而非默认另写一套协议，未来实际继承及dtype／copy参数在K／L验收。用户显式先转普通pl.Series后采用原生出口，仍是Polars合同，不承诺替整个第三方生态追加保护。

**导出布尔选择（已确认）：**关键字固定为`allow_nat_collision=False`。False维持上述安全失败；显式True只允许此次导出中“有效目标MIN撞目标NaT保留值”的行按目标缺失表示输出，不影响源数据或其它有效行。该选择不可逆，不称为无损；用户已明确选择时不另逐次警告。它不禁止原来就有的null／NaT正常导出。参数不是Polars现有参数，是本库新增设计的窄职责选项；只提供该布尔形式，不另设字符串模式或别名，不吞解析错误、其它溢出或精度失败。普通布尔按B02只收Python／NumPy真布尔；在入口准备一次，Rust内部为bool，不因改为布尔就宣称明显提速。

```python
array = x.to_numpy(allow_nat_collision=True)
# 设计输出：numpy.ndarray，datetime64[ns]。
# np.isnat(array).tolist() == [True,True,False]。
# 仅有效MIN与原null合并为NaT，来源x仍保持[有效MIN,null,0]。

result = x.to_pandas(allow_nat_collision=True)
# 设计输出：传统日期表示的pandas.Series，前两行NaT，第三行纪元0。
# to_pandas完整签名及其它可选依赖按K01确认。
```

保留Polars原writable／allow_copy等参数职责。可保值的Arrow表示没有该冲突，不因为allow_nat_collision=True就强行破坏其有效MIN；若采用to_pandas的现有use_pyarrow_extension_array=True，该格式选择与冲突策略分别履职，实际支持在K01验证。np.asarray(x)不额外接受此参数，沿默认False及安全报错；要允许损失必须显式调用导出。Pddt构造／普通运算不新增此开关，直接Pddt(有效MIN的Polars来源)仍按最终目标检查；用户可先明确导出成NaT再传给Pddt。普通解析、真正超范围、自动换单位及小数截取规则不被此选项放宽。

**4. 能保留独立有效位的出口正常无损，不一概拒绝所有pandas格式：**原生Polars／Arrow timestamp能同时保存有效MIN及null；原生可空Int64配合明确unit／tz也能表达刻度。直接日期Arrow协议保留unit／tz／validity更完整；整数或裸缓冲若单独导出，必须保留或随附缺失信息，不能只给一个i64数组而丢mask。

```python
ticks = x.to_physical()
# 原生pl.Series，Int64：[MIN, null, 0]，仍有独立有效位。
result = pl.from_arrow(x)
# 按Polars公开Arrow协议，原生pl.Series，Datetime(ns)。
# 原有效MIN／null／0区分保留；不强迫安装Python pyarrow包。
expr = pl.col("time").to_physical()
# 原生pl.Expr，输出Int64且保null；不是普通NumPy日期数组。
```

当前无PyArrow环境的普通Series往返及带slice／多chunk往返已实测保值；Pldt协议继承仍需实施验证。显式Arrow对象导出或Arrow-backed pandas若采用成熟公开接口，按该接口需要相应可选包；不因此给PLDT增加强制PyArrow依赖。Arrow-backed pandas是不同目标表示，不可用“pandas都不能保存MIN”概括；本次未装PyArrow，未将其实际运行判为已通过，具体接口及参数按本轮已收口K01，实际Arrow-backed运行仍待实施验证。to_pandas返回pandas.Series，按K01执行，不变成DatetimeIndex，也不另增重复to_pddt出口；Pddt构造使用本项已批的来源适配。

**5. 本次确认的Pddt直接Polars导入问题，建议限域同步修正：**当前`Pddt(s)`实际返回Pddt但isna为`[True,True,False]`；src/rstimes/pddt.py:_outer在Datetime分支先fill_null(MIN)，再view成NumPy datetime64，合并了有效MIN与缺失。本次实施范围包含真实Polars Datetime来源适配：保留有效位和原整数到目标处理，在最终明确单位／时区结果检查目标NaT冲突，不能提前把有效来源吞掉。不以type-name筛选Pldt，也不对所有输入硬加MIN黑名单；构造／parse／实际复用该适配的工厂一同保护。

```python
Pddt(s).isna().tolist()
# 当前两环境实测：[True, True, False]，有效第一行已丢失。
# 建议修正后的默认同单位同坐标导入：OverflowError。
Pddt([MIN], unit="ns").isna().tolist()
# 当前及建议保持：[True]；Pddt自身裸刻度NaT合同不变。
```

若用户明确的目标处理能产生可表示的最终值，则按真实最终结果判断，不是遇到来源MIN就不论上下文全拒绝。本项主体已批准的共享修正限Polars日期来源适配及PLDT相关出口；不借机扩大Pddt值域、重写Delta／Parser或改变现有数值／缺失合同。当前未实施，新增导出选择不自动扩到Pddt构造。

**与Pddt的明确差异：**Pddt每单位的MIN保NaT，有效刻度从MIN+1起；PLDT采用Polars原生独立validity，有效MIN可保留。真实缺失语义相同，表示不同。日期结果分别Pddt／Pldt；对应缺失分别NaT／null；普通NumPy日期出口为ndarray，Arrow协议往返为普通Series，Expr为原生Expr，按职责输出，不把所有返回包装成Pldt。

**排除范围：**把PLDT所有来源的MIN也强行当null，可以表面靠近pandas，但会丢掉真实Polars数据；默认导出仅警告后变NaT，也不能满足安全默认。推荐主体保持原生数据与默认明确失败，保值沿现有有效位通道；用户明确选择的导出损失另以第3节已定窄职责选择，不把它描述为自动修复或无损转换。

**性能影响：**原生数据沿chunk复用values／validity，位图约每行一bit，全部有效时可不额外分配；无须先填NaT再重建mask。无null与有null分路，普通计算跳过无效槽；新结果仅最终checked写出，不每行构造Python对象。转换到哨兵生态时，只在该边界检查有效目标MIN，尽量融合已有转换／写出；同单位零复制导出可能仍需原生扫描，零复制不代表无检查。不能在B05允许外壳变化或外部可变缓冲时永久缓存“没有MIN”而不验证有效性。Pddt限定导入修正尽量复用原有效位／一次批量准备，不把额外扫描放到无关Parser／Pydt热路。没有PLDT正式测速，不承诺零成本或固定倍率。

**验收要求：**三个真实单位的MIN／MIN+1／0／MAX及独立null，整数／NumPy日期／Pddt来源职责对照，运算最终到MIN及越界、slice／bitmap偏移／多chunk／空／全null／全有效，名字／时区／单位保留；普通NumPy日期／隐式数组／传统pandas／Pddt不能碰撞吞值。Arrow及可空整数往返用独立原整数和mask断言，缺可选依赖明确记录，不能记作该出口已验证。新增Pddt回归须在当前包能暴露上述吞值，同时保留真实NaT正常导入。具体外部协议签名及标量容量按K／L确认，不把物理完整int64理解为所有外部库函数无边界。

<a id="pldt-c05"></a>

### C05 零年/负年/宽年与Polars日历操作容量

**范围与核查：**本项区分存储容量、日历算法容量、最终标量／格式／地区时区能力。拟议PLDT沿现行Pddt P05.5与AGENTS C12的延伸公历，在当前真实ms／us／ns容纳范围内支持0、负年和超过9999年；C04已确认的全int64／有效位及C03固定单位保持。实际物理可存不等于每个第三方函数都能处理。这里不扩普通Parser负年份语法，不提前决定D的格式合同、H的地区时区后端或J的全部返回dtype。

**1. 日期含义与Pddt相同，0／负年不是占位：**采用天文年份编号，0年对应公元前1年，-1对应公元前2年，公历闰年规则继续适用，因此0年2月29日合法。绝对year=None才表示保留，year=0／-1是真实年份；显式修改仍按字段契约校验，其它字段的非法范围不能因支持宽年而放宽。

```python
source = np.array(
    ["0000-01-01", "-0001-12-31", "12000-01-01"],
    dtype="datetime64[ms]",
)
x = Pldt(source)
# 拟议输出：Pldt，Datetime(ms)，保原生来源单位。
years = x.year
# 原生整数pl.Series，值[0,-1,12000]；具体整数位宽在J01统一确认。
y = x.add(years=1)
# Pldt，Datetime(ms)，日期为0001-01-01、0000-12-31、12001-01-01。
```

这些Pddt对应结果和两版Polars普通年份读取已核对。示例使用原生日期来源，不能据此宣称普通字符串Parser已接受负年／任意位数年。现有Pddt的专用strptime可按明确格式处理负年，PLDT格式路径复用范围仍在D确认。

**2. 自有日历查询／移动不受较窄第三方日历载体提前限制：**在目标单位容纳且共享算法可安全计算时，year／日历字段／周期边界／月份长度及已有自有日期移动等，复用最小共享Rust公历算法。不能仅存下宽年，随后把正常有效值查成null；也不先转换为Python datetime或受较窄日期范围限制的库对象。具体输出表若有明确标准类型限制，仍在其真实输出边界检查，不由本项取消格式合同。

```python
source = np.array(["1000000-01-01", "-1000000-01-01"], dtype="datetime64[ms]")
x = Pldt(source)
# 拟议：Pldt，Datetime(ms)，两条有效日期。
years = x.year
# 拟议：原生整数pl.Series，[1000000,-1000000]。
y = x.add(years=1)
# 拟议：Pldt，Datetime(ms)，年份[1000001,-999999]。

s = pl.Series("time", source)
s.dt.year().to_list()
# 本次两版原生Polars实测：[None,None]。
Pddt(source).year.tolist()
# 本次两环境实测：[1000000,-1000000]。
```

Polars Datetime底层是带单位的有符号64位整数；其原生日历实现使用的日期类型还有自身范围，不能把两种能力画等号。若用户明确走pl.Series(x).dt.year()或其它完整原生入口，其行为归Polars，不能修改整个.dt来消除差异。自有.pldt／Pldt入口及原生Expr输出应共用本库数学规则，具体属性／方法形式及位宽在J01确定，不为Expr另建窄年算法。

**3. 单位是实际容量边界，不能为宽年自动更换：**支持0／负／宽年并不表示所有单位都能保存同一日期。原生合法输入可以被ms保存，但目标us或ns不一定能保存；构造和已有运算仍按C03检查。

```python
x = Pldt(np.array(["1000000-01-01"], dtype="datetime64[ms]"))
# Pldt，Datetime(ms)。
x.as_unit("us", round_ok=False)
# OverflowError：真实us容量不足，来源x保持ms。

Pldt(np.array(["12000-01-01"], dtype="datetime64[ms]"), unit="ns")
# OverflowError：目标ns无法容纳，不自动退到us／ms。
```

所选单位不能表达最终值时明确失败；不能变NaT／null、回绕或把年份截成1／9999。allow_nat_collision只处理C04的导出哨兵冲突，不放宽这些容量错误。0年在ms／us可表达，但不在ns的实际区间，不因它语义合法就绕过物理检查。

**4. 最终Python日期出口保真实协议，单元素与切片区别清楚：**标准Python datetime／Pydt最终年份仍为1—9999。本次Polars取0年或12000年的单元素均抛ValueError；当前Pddt.datetime()导出0年也在最终Pydt构造处ValueError。错误应明确目标范围；不能为了成功创建标量而修改年份。完整继承的Polars取元素仍保原异常，不统一包装成另一种错误。

```python
source = np.array(["0000-01-01"], dtype="datetime64[ms]")
s = pl.Series("time", source)
s[0]
# 当前原生Polars：ValueError，year 0 is out of range。

x = Pldt(source)
x[0]
# 依已确认A03：沿Polars Python标量出口，目标年份错误。
one = x[:1]
# Pldt，Datetime(ms)，仍是一行日期列，不需要构造Python datetime。
```

与Pddt有实质差异：当前Pddt单元素为pandas.Timestamp，本次1000000年的ms标量仍能读取year=1000000；Pldt按Polars返回Python datetime时无法覆盖该年份。保列形式／整数／适用原生协议可继续计算；主动Python对象出口的容器细节留K02，不增自定义宽年份Python标量。NumPy日期数组能按自身单位保宽年，不能把它也误限为1—9999。

**5. 地区时区的可靠范围独立，不让无区路径负担动态处理：**naive、UTC以及H最终明确支持的固定偏移直接用整数日期／偏移数学，不做DST查找；偏移后仍检查真实目标容量。动态地区要按选定成熟Rust后端能够可靠处理的年份范围执行，实际不能处理时明确报范围错误，不用今年偏移替代、不忽略地区或改成UTC。H规定后端／可靠能力边界，本项不预先承诺百万年地区规则。

当前Pddt的正负百万年ms在naive／UTC／固定+08:00下均能构造并正确查年；Asia/Shanghai地区路径因现有Python tzinfo载体1—9999限制而OverflowError，源码rust/pddt/zones.rs:candidates/fromutc已明确分流。这个载体限制不能作为PLDT所有日期或所有Rust地区后端的统一年份上限；也不因PLDT设计而自动扩大当前Pddt地区能力。两者共同目标为日期含义一致，可靠能力范围差异如实说明。

**与Pddt的差异及采用原则：**共同公历、0／负年含义、固定单位、容量失败及Python目标容量均沿Pddt；Pddt查询输出pandas.Index，Pldt查询输出原生整数Series，原日期缺失沿Polars保持null。Pddt支持s，因此有比Pldt最粗ms更宽的物理范围；C04的NaT保留值差异保持。Pddt取元素为Timestamp，Pldt取元素为Python datetime，这是已确认的容器协议差异，不为一致而自造新标量。保留共享内核的宽公历能力，不将整个Pldt人为缩到Python或Polars某个日历库的范围；同时明确成熟原生入口及地区／对象出口的实际边界。

**性能影响：**复用现有整数算法，从tick按所需量直接计算年份／月份／星期／边界，不逐行建Pydt、不借strftime再解析字段，不为一次查询先造整张日历表。普通年份和宽年份尽量使用同一已验证算法，单位计划在循环外准备；必要中间值checked，最终写合法类型及有效位。元数据已知的naive／UTC／固定偏移保快路，动态后端边界检查只在对应路径发生。保留B05允许的安全原生借用，普通计算不因Python标量容量而预扫描拒绝。复用共享函数时保护已采用Pddt／Pydt／Parser，不新增Pddt逐行公开调用或默认把所有结果先缩ns。没有PLDT正式测速，不承诺比原生Polars某单项更快。

**验收要求：**以独立NumPy原始整数／明确日期预期覆盖0／-1／负闰年／0年闰日／9999↔10000／12000／正负百万年；核对跨0年加减、字段查询及合法日期变换、null／空／切片／chunk、保单位及名字。各单位边界和一格越界按真实最终结果检查；源无效与目标不可容纳分开。单元素Python出口和保列切片分别验证，Pddt Timestamp与Pldt datetime协议各自对照。naive／UTC／适用固定偏移与地区后端范围分组，不用两边都失败冒充同义正确；具体ISO表／格式／对象出口仍按自身合同。Expr以相同独立整数预期及固定dtype验证，原生返回null不能充当本库有效日期查询的正确答案。

<a id="pldt-c06"></a>

### C06 纳秒尾数与小数字段替换的共同含义

**1. 推荐自有分量含义与Pddt一致：**对于同一日期的小数秒`.123456789`：

|自有查询|职责／范围|建议结果|
|---|---|---|
|millisecond|本秒内毫秒分量，0—999|123|
|microsecond|本秒内微秒分量，0—999999|123456|
|nanosecond|微秒之后的额外纳秒尾数，0—999|789|

microsecond不是只取456；millisecond不是独立于微秒之外再叠加的一段。分量关系为完整本秒纳秒=`microsecond*1000+nanosecond`，毫秒=`microsecond//1000`。查询日期分量与自有命名保持Pddt语义，Pydt的微秒含义也相同；不因本项给Pydt增加不存在的真实纳秒精度。

```python
x = Pldt(["2024-01-02 12:34:56.123456789"])
# 拟议：Pldt，Datetime(ns)。
ms = x.millisecond   # 原生整数pl.Series，[123]。
us = x.microsecond   # 原生整数pl.Series，[123456]。
ns = x.nanosecond    # 原生整数pl.Series，[789]。
# 查询整数位宽在J01统一确认；原日期null在这些整数结果中仍为null。

full = x.dt.nanosecond()
# 沿Polars原生命名空间：普通pl.Series，Int32，[123456789]。
```

当前两版Polars原生dt.millisecond／dt.microsecond分别也为123／123456，dt.nanosecond是完整本秒纳秒而非789尾数。保留原生.dt可直接获取完整量，不要求先包装普通Series，也不另增fraction_nanoseconds等重复公共名称；自有属性与原生限定路径的含义在docstring明确区别，不能把原生结果直接当自有纳秒属性返回。

**2. 绝对替换一次合并，微秒替换覆盖整段微秒小数：**只改nanosecond保原microsecond；显式改microsecond会替换全部六位小数，并清未指定的旧纳秒尾数；两者同时提供则微秒值及明确尾数一起组成新小数。未涉及小数的其它字段修改保小数不变。

|调用，来源小数秒为.123456789|结果小数秒|拟议输出|
|---|---|---|
|replace(nanosecond=2)|.123456002|Pldt，Datetime(ns)|
|replace(microsecond=1)|.000001000|Pldt，Datetime(ns)|
|replace(microsecond=1,nanosecond=2)|.000001002|Pldt，Datetime(ns)|
|replace(nanosecond=0)|.123456000|Pldt，Datetime(ns)|
|replace(microsecond=0)|.000000000|Pldt，Datetime(ns)|
|replace(microsecond=None,nanosecond=2)|.123456002|Pldt，Datetime(ns)|
|replace(microsecond=1,nanosecond=None)|.000001000|Pldt，Datetime(ns)|
|replace(microsecond=None,nanosecond=None)|.123456789|Pldt，Datetime(ns)|

以上Pddt对应结果均实测确认。None表示该参数未设置，不是要求恢复被另一项明确替换覆盖的旧子精度；显式microsecond时整个微秒分辨率的小数被重设，因此其内未指定的纳秒尾数清零，不与普通独立字段None保留规则混为一谈。零是真实替换，不能当成未设置。该包含关系也适用于实际提供这两个字段的to_datetime／to_time等对应入口；日期合法性及地区策略仍按F／H各合同，不由本项重新统一成另一种校验／收口。

**3. 逐行参数遵守B02，不重复构造日期对象：**真正标量广播，明确集合严格等长，集合中的None按该行未设置处理；不能因一个字段提供列而改变另一字段职责。源日期null保持null，选项／非缺失目标照样校验。

```python
x = Pldt([
    "2024-01-02 12:34:56.123456789",
    "2024-01-02 12:34:56.123456789",
])
y = x.pldt.replace(microsecond=[1, None], nanosecond=[None, 2])
# Pldt，Datetime(ns)，两行小数秒分别.000001000和.123456002。

expr = pl.col("time").pldt.replace(microsecond=1, nanosecond=2)
# 原生pl.Expr；time是Datetime(ns)时，输出仍Datetime(ns)，小数秒.000001002。
# 该输出在collect后为原生DataFrame中的普通Series，不在Python逐行造Pldt。
```

Series自有日期结果Pldt、整数查询普通Series、Expr原生Expr的分工不变；最终属性／方法样式及完整dtype清单在J01确认，不以本项示例偷偷定完所有命名。

**4. 绝对字段与相对增量分清：**replace的microsecond范围0—999999，nanosecond尾数0—999，整数协议沿B02，拒绝bool和float，包括1.0。负值不再作保留占位。非法绝对分量不能靠组合抵消放行，也不能进位成另一字段。相对add／sub的复数单位为增量，允许合法负数和超过单字段范围的值，并按C03合并真实结果检查。

```python
x.pldt.replace(nanosecond=1000)
# ValueError，明确说明0—999尾数范围；不自动进位。
x.pldt.replace(nanosecond=-1)
# ValueError；不代表保留。
x.pldt.replace(nanosecond=1.0)
# TypeError；只收整数协议，bool也拒绝。

y = x.add(nanoseconds=1000)
# Pldt，Datetime(ns)，来源.123456789变为.123457789。
y = x.add(microseconds=1)
# 相同日期结果，保原纳秒尾数789。
```

不额外新增replace(millisecond=...)，保持对应Pddt的绝对字段接口；millisecond是查询分量，相对milliseconds仍是既有增量角色。是否扩展其它接口必须另有明确决定，不能把本项误读为新增参数。

**5. 低分辨率不伪造尾数，修改仍检查实际单位：**ms日期的microsecond会体现毫秒换算，如.123对应123000；us／ms中没有纳秒尾数时自有nanosecond为0，但null仍为null。查询到0不自动缩小存储单位，也不把声明ns且尾数为0的来源降成us。

```python
x = Pldt(["2024-01-02 12:34:56.123456"], unit="us")
x.nanosecond       # 整数pl.Series，[0]。
x.pldt.replace(nanosecond=1)
# ValueError：当前us不能无损保存，不自动升级。
y = x.pldt.replace(nanosecond=0)
# Pldt，Datetime(us)，合法。

x = Pldt(["2024-01-02 12:34:56.123"], unit="ms")
x.microsecond      # 整数pl.Series，[123000]。
x.pldt.replace(microsecond=1)
# ValueError：当前ms不能保存1us。
y = x.pldt.replace(microsecond=1000)
# Pldt，Datetime(ms)，小数秒.001000000，合法。
```

负纪元也按真实秒内非负分量处理，不能用Rust向零除余：-1ns是1969-12-31 23:59:59.999999999，自有microsecond=999999、nanosecond=999；不是负分量。C04完整int64／validity与C05宽年原则保持，不能为查询小数先缩成Python微秒、将有效MIN当缺失或先经过较窄日历对象。

**与Pddt的差异及采用原则：**数值含义、None／零、微秒覆盖尾数、相对增量及固定单位规则沿Pddt。Pddt字段查询是pandas.Index，PLDT是原生整数Series，整数null沿Polars有效位；日期操作返回各自日期类。与原生Polars的明确差异主要是自有nanosecond取额外三位，而dt.nanosecond仍保持完整本秒量；本次两版原生dt.replace没有nanosecond参数，自有入口增加与Pddt平行的尾数替换。采用这套共同规则，完整保留原生.dt职责，不把两种量混用。

**性能影响：**直接以原生整数除余读取分量，按所需量计算；不格式化字符串、不转float、不逐行创建datetime或先构造临时Pldt。微秒及尾数在同一次原生替换中合并，持有源缓冲／有效位，最终检查单位并写一次结果；不调用公开replace两次。可复用现有字段拆分／重组中的最小明确算法，不能因共享而把所有查询强迫解码完整日历／地区回调。已知适用单位／时区坐标走正确快捷路径，普通分量查询不加入多余DST往返。Pddt／Pydt原行为及热路需受保护；尚无PLDT正式测速，不承诺固定比例收益。

**验收要求：**独立整数预期覆盖完整微秒／额外尾数、0／999／999999、None／零／显式微秒清尾数、同时替换、无关字段保小数、真正标量及等长逐行None、空／原null／slice／chunk、负纪元及C04有效MIN。原生.dt完整纳秒与自有尾数分别核对，不能只验证两入口相等；ms／us／ns精度失败及合法整除结果、非法绝对值／bool／float、相对大值／负值及抵消分组。Series与Expr同预期、固定输出字段；一次调用整次失败，来源不变。具体命名／位宽／地区／对象出口细节沿J／H／K，不在本项开始实现或性能采集。

## D 共享Parser、Configs与格式解析

<a id="pldt-d01"></a>

### D01 共享Rust Parser需要抽出的真正边界

**目标与范围：**为Polars字符串列和表达式复用已完成的语法／词表／字段推导，保现有Parser／Pydt／Pddt公开合同。只抽出必要的内部Rust边界，不新增公开parse_fields或另造PLDT文本方言；原生日期／数值继续按B01/B03直接适配，不强迫全部类型走文本扫描。本项确定结构与兼容边界，D02决定Configs／default快照时点，D03决定文本Expr时区等完整入口合同，D04处理专用格式，H处理地区本地化，M02验证插件与实际构建。

**当前源码事实：**

|实际位置|已经具备|仍须隔离的边界|
|parser/fields.rs|Rust Fields、RuleLookup、ParseResult，Lenient／Strict及Nano精度策略|不能把旧公开微秒出口一律改成纳秒策略|
|parser/scan.rs、resolve.rs|ISO优先、通用token、年月日推导主要使用Rust字段|目前函数签名直接绑定TextView；需要输入视图抽象而非复制语法|
|parser/text.rs:17|借用CPython Unicode及其1／2／4字节字符存储，含孤立surrogate|不是Polars UTF-8视图，不能把Bound／裸Python字符指针带进worker|
|parser/text.rs:196、build.rs|非Windows使用CPython原生字母分类；Windows按构建解释器生成等价isalpha表|这是额外CPython依赖，不等于仅凭函数名判定原生分类调用不安全；新原生适配须明确Unicode语义、符号和线程边界|
|parser/config.rs:65/69|Rust不可变词表与Arc/COW；格式路径已有低成本快照|现有NativeView依赖Python Configs借用；地区表仍含Python对象|
|parser.rs:708/735及complete|Pddt可复用已准备default后的扫描／补字段|仍接Python、Bound、PyResult并在错误冷路重新attach Python|
|pddt/prepare.rs:19|文本先完成字段再转原生日期整数，不创建普通文本datetime中转|入口仍是PyString／Python配置，且批量缺失注册依赖pandas对象|

因此“代码用Rust写”不等于现有绑定函数可直接作为无Python干预的Polars工作线程函数。当前Pddt先解析字段再构建日期数组的正确思路保留，移出的主要是来源、准备和出口依赖。

**1. 推荐共享的内部接口只承载Rust数据：**输入字符访问视图、已准备的不可变识别规则、普通选项／独立YMD参考 → 原生日期字段、真实小数精度、已识别数字偏移／有效登记地区标识或原生错误。已有普通／严格／纳秒策略尽量保静态专门化；不为了统一增加每字符动态分派或全局开关大函数。字段扫描、顺序推导、default补足、strict检查、零年及小数语法保持同义。完成字段的纯逻辑也要从PyResult边界分开，不能只抽扫描却保留worker里调用Python的错误完成器。

内部保留真正的未匹配与字段非法／溢出错误区别，不能把后者变成NoMatch／null，避免破坏现有算符等真实协商。Python异常只在原Python出口构造或传播，Polars执行错误在其边界转换，具体类别／行位置规则留N；外部准备回调失败保原异常，不塞进纯核心伪装语法错误。不把Python对象放入worker，即使其Rust句柄形式上可Send也不等于允许访问。

**2. 两种文本适配，共用一份扫描与推导：**原Python str仍借用现有CPython字符视图，普通ASCII及已有Unicode快路不统一转UTF-8／String。Polars String通过公开Rust字符串数组访问有效UTF-8，保chunk／slice／owner，不先to_list或每行造PyString。ASCII可借原字节；非ASCII按需一次解码成可复用的原生代码点暂存，或采用经验证的等价视图，不对每个随机索引反复chars().nth而退成平方扫描。代码点及字节偏移不能混用；不能假设所有Polars字符串都采用同一种原始offset缓冲布局。

共享的是语法源代码与词表规则，允许针对输入载体编译专门路径。非ASCII分类按既定Unicode合同准备等价原生数据，可复用build.rs已有生成能力，不在worker调用_PyUnicode_IsAlpha，也不直接用Rust char.is_alphabetic悄悄替换Python字母语义／Unicode版本。原有Python孤立surrogate路径保留；Polars UTF-8无法表达的输入不通过替换字符伪装成功。本项不扩大大小写规则，仍识别词表已经保存的形式。

**3. Configs/default在边界准备，识别地区与实际本地化分开：**工作线程接收不可变Rust词表、普通选项、可用地区键／状态及已准备YMD等需要的数据；不每行借用Python Configs、查Python字典、创建ZoneInfo或重建全词表。登记地区识别仍以有效Configs为准，不因Rust时区数据库有该键就绕过登记／已恢复不可用状态。识别结果只携带地区标识，PLDT构造层按H完成本地化／转换和最终单位检查，不把地区DST职责塞回通用扫描。

本项不修改既有Parser读取配置及真实准备回调的先后。立即路径遵守已确认B04：无关原生／空／明确缺失不提前处理default，文本路径按原合同准备一次。Expr按已确认D02在创建时捕获Configs／实际格式资料并准备所传default；因未来输入未知，明确允许此时执行一次必要default来源协议并提前报告非法default，即使未来为空／全null。该例外只作用于文本Expr，不改变立即路径或在worker重放Python回调。

**具体例子：同一个Configs必须产生相同日期含义。**

```python
cfg = Configs()
cfg.set_month({"jan": 2})
parse_str("14 Jan 2024", cfg=cfg)
# 当前实测：datetime.datetime，2024-02-14。
Pydt.parse("14 Jan 2024", cfg=cfg)
# 当前实测：Pydt，2024-02-14。
Pddt(["14 Jan 2024"], cfg=cfg)
# 当前实测：Pddt，us，一行2024-02-14。
x = Pldt(["14 Jan 2024"], cfg=cfg)
# 拟议：Pldt，Datetime(us)，一行2024-02-14。

expr = pl.col("text").pldt.parse(unit="us", cfg=cfg)
# 拟议：原生pl.Expr；共享文本入口的完整合同继续在D03确认。
result = pl.LazyFrame({"text": ["14 Jan 2024"]}).select(expr.alias("time")).collect()
# 拟议：pl.DataFrame，time为普通Datetime(us) Series，日期2024-02-14。
```

这个刻意修改jan含义的例子证明不能先用Polars自己的解析成功结果，再对失败行才使用本库词表。中文自定义词“收获月”对应10月的现有三个入口也已核对；UTF-8新适配需与CPython视图产生同义字段。所有默认顺序保持显式非None > Configs > yearfirst=True/dayfirst=False，显式False有效；strict=False、isoformat=True的ISO优先且可通用回退不变。普通Strict不是错误转null，也不新增全字符消费要求。Pldt不新增dtclass／ignoretz，已识别时区按既定保留方向；公开Parser已有dtclass／ignoretz及其默认职责不变。

**4. 纳秒保留与各出口分开：**当前Nano<P>已服务Pddt／epoch，不需另造PLDT九位小数语法。列／epoch路径保真实ns到最终单位；datetime／Pydt原微秒出口及其既定精度处理保持，不能因为共享纳秒能力而让旧普通路径附加无用状态。原生日期／数值直接适配到紧凑日期表示，不转字符串、不逐行调用公开parse、Pydt或Pddt；必要真实协议载体按C04性能原则保留，普通文本列不为中转创建Python datetime。

```python
text = "2024-01-02 12:34:56.123456789"
parse_str(text).microsecond  # 当前：123456，datetime出口为us。
Pydt.parse(text).microsecond # 当前：123456，Pydt出口为us。
Pddt([text]).nanosecond.tolist() # 当前：[789]，日期列实际保完整ns。
x = Pldt([text])
# 拟议：Pldt，Datetime(ns)，保完整.123456789。
parse_to_epoch(text, unit="ns")
# 当前：Python int，1704198896123456789。
```

**5. 批量缺失与最终容器由适配层负责，不能修改通用语法：**Polars null／B04明确缺失标记在列适配中处理，保validity；不让工作线程需要pandas.NA／NaT注册。普通文本非法仍失败，不能errors=coerce。当前parse_str("")／Pydt.parse("")是ParseError，Pddt([""])是一行NaT；拟议Pldt([""])沿B04是一行null、默认ms。这个公开职责差异保留，不能为了“共享”让标量Parser也把空文本变缺失。

共同字段准备后只在出口生成目标datetime／Pydt、Pddt日期数组、Pldt的Polars日期列或epoch整数；Pldt无需先构造Pddt或导入pandas。初始化／数据缓冲／错误均按原接口及各目标范围处理，接线使用官方Rust表达式插件及已确认公开数据协议，具体ABI／版本／真实运行在M02验收；源码是Rust不能代替插件工作线程已运行的证据。

**采用结构与替代边界：**采用输入适配、纯Rust规则／扫描／补字段、目标出口三部分，小共享模块优先，不预设另建通用框架或第二套公开API。立即原型可暂借现有GIL入口探索，但不是最终Expr交付；把全部文本交给Polars、先Polars成功再本库兜底、列循环调用公开Python parse都不能满足已确认语义／原生执行方向。成熟原生容器和适配继续复用，不因此重写Polars调度器或普通Parser的非字符串协议。

**与Pddt的差异：**共同语法／Configs／strict／default日期含义保持；Pddt当前通过CPython文本及pandas外壳接入，Pldt新增Polars UTF-8／validity／Expr调度适配，最终输出Pldt或原生Expr。Pddt的原生日期／数字快路和现有标量Parser出口不需要改成Polars通路；已批准C04的Pddt跨有效位修正按其独立范围执行。

**性能影响：**改动涉及共享热路，不能宣称无代价。保原CPython借用、ASCII读数快路、既有Lenient／Strict及精度专门化；新UTF-8路径直接借字符串、按需一次原生解码、规则按批准备复用，不每行import／造日期／复制词表。减少Python逐元素桥有合理收益方向，但Unicode暂存、词表序列化／准备、插件调度成本需计完整公开调用。不能用新增Pldt吞吐提高掩盖parse_str／parse／parse_to_epoch、Pydt或Pddt稳定退步；未来按既定功能与逐项性能保护验收，当前不采正式倍率。

**验收要求：**复用全部仍有效旧正确文本及历次修复样本，外加两种字符视图的独立字段／日期／拒绝预期；覆盖ASCII、多语言／组合字符／大小写已有形式、UTF-8边界／chunk／slice、适用孤立surrogate边界、ISO优先／通用回退、strict两模式、Configs修改／显式False、default、零年与ns。区分未匹配、字段非法、外部回调错误和批量明确缺失；原类型／字段读取及异常链按旧合同。验证插件普通批循环没有Python对象访问／回调或临时datetime，不能只用源码grep作为运行证明；有效位／单位／目标容量和最终构造一起验证。具体配置时点D02、时区schema D03、动态区H、错误N、插件跨平台M02逐项完成，不提前当成已解决。

<a id="d01-existing-library-optimizations"></a>

**补充决定：现有库优化D01.O1—O4（已同意，待后续实施）。**用户在确认D01后询问现有实现的优化空间，随后明确“这一部分也记入讨论，确定同意进行优化，后续回顾的时候，D01需要明确引用，因为是相关的”。以下四项纳入后续项目的优化范围，沿同一D01编号保存，不新增主目录细项；源码上的可减少工作与已证明提速分开，当前尚未实施或采正式性能。

|优先级／已批优化方向|当前真实开销与位置|优化方向|主要受益／限制|
|D01.O1，优先|Pddt._outer的Polars String等来源仍进入_pddt_prepare.try_iter，Reader逐项取得PyString；prepare.rs:276/315及pddt.py:_outer|复用D01的新UTF-8适配，使确有公开原生字符串视图的来源直接批量进入共享核，按已知长度准备原生缓冲，最后生成Pddt|大批Polars String／适用原生字符串后端优先；普通Python list已有PyString，不为统一再编码；pandas object／混合／回调输入不冒充原生列，不强制新增PyArrow|
|D01.O2，随后|_pddt_prepare已检查cfg，但每个文本scan_prepared仍做Configs类型识别、借用和部分配置选项准备；parser.rs:740及prepare.rs:295|把已证明稳定的类型／选项准备移到批次边界，内部传明确的原生上下文；无回调路径可复用适当规则视图|自定义cfg的长文本列较有价值；这些多为Rust侧检查，不是每token调用Python字典；必须保护外部回调后读取最新规则的既有合同，编译器已消去的重复不算新收益|
|D01.O3，中等|非ISO回退tokenize每次创建代码点arena与ranges两个Vec，text.rs:248/253/254|批量中复用每调用／worker的词法暂存；标量短文本若分配确为热点再评估小容量内联存储，长输入安全扩展|Pddt通用／多语言文本，以及Parser／Pydt.parse的非ISO路径；完整ISO本来可不分词，收益不能推广到该路径；不用全局无限缓存，不截断文本|
|D01.O4，关联优化，范围较大|Pddt查询／字段修改／单位转换等先对asi8.tobytes生成输入快照；pddt.py:404/522/587/888|借新原生适配能力评估对所有权／稳定性确有保证的来源直接借buffer，减少一次O(N)输入复制；输出np.frombuffer已是低拷贝，不能重复算作新收益|大列轻量查询／日期运算可受益；外部可变NumPy、真实时区／数值回调及重入场景保必要快照，read-only标记本身不证明无可写别名。该项超出纯解析拆层，后续计划单列实施任务和验收，不因独立列项遗漏|

**真实协议保护证据：**existing-library-opportunities-01/callback-config-reference.py在两环境分别验证字符串子类__str__和生成器回调修改cfg。两行相同文本“14 Jan 2024”，第一行按默认一月得到2024-01-14，回调将jan改成2，第二行得到2024-02-14；__str__只调用一次，生成器保原执行顺序。故不能对所有现有Pddt输入提前固定整批词表，更不能跳过真实子类／迭代器协议；类型准备可优化，有效规则在这些路径仍须按原时点读取。D02的未来Expr快照合同与现有Pddt协议分开决定。

**已经完成的优化，不重复列为待做：**Configs词表已是Rust HashMap查询；Arc/COW复制已可低成本共享；Reader.prepared_default已在实际文本首次需要时准备一次并记住None；完整ISO前缀成功可跳过通用tokenize；Pddt文本普通路径已不创建datetime中转；Python str视图已借原字符存储。这些都是优化起点，不能把重新实现同一件事包装成新成果。

**模块收益边界：**最直接潜力在Pddt的批量文本／原生数据路径。Parser和Pydt文本解析主要可能受益于共同词法算法及短文本分配改善，单次调用已精简，不能拿批量潜力推算其倍率；Configs准备优化服务解析，不以独立设置速度为主要目标。Parser分层不推导Delta收益；Delta自身升级按G01.N的独立批准范围实施。错误移出纯核主要是原生执行和维护边界，当前错误已经偏冷路径，不能单独许诺显著提速。

**实施与采用原则：**四项均已同意后续进行优化；优先D01.O1原生字符串路径，再看D01.O2批次准备与D01.O3词法暂存，D01.O4单列任务评估。复用现有采集和保护证据，先确认热点及一项最小原型，再测完整公开调用；逐项守行为／协议／单位／缺失／安全与性能保护。有可靠收益才合入，无收益或未达保护的具体改法回退并记录，不为表面共享而拖慢已有Python str快路，也不将单项失败作为其它方向停止的理由。后续回顾必须明确引用本D01正文和四个子项，记录各项覆盖入口、实施／验证／采用或未采用原因。当前只有源码依据和四项现有协议观察，没有任何新优化倍率或实现。

<a id="pldt-d02"></a>

### D02 Configs/default和格式资料在Expr中的快照时点

**已确认职责：**对于尚未执行的Expr，在创建时读取并固定有效Configs／实际需要的格式资料，准备所传default；创建后修改原Configs／LC_TIME不改变同一表达式。立即执行入口保按当次调用读取。所有下列PLDT接口均为未实现示例，本项已完整确认。

**采用：创建表达式时捕获参数，执行时只读准备好的原生资料。**

|资料|建议时点与内容|创建后修改的作用|
|Configs与顺序|Expr创建时冻结有效词表、顺序、地区登记key／可用状态；显式顺序非None仍优先于Configs，cfg=None使用库默认规则|不改变旧Expr；新Expr读新值|
|default|文本Expr创建时按同一快照规则准备一次独立完整YMD；None不提供，不继承时钟／tz／ns／fold|执行不再访问原Python对象或解析default|
|格式结构|格式入口创建Expr时准备格式步骤；非法静态格式当场失败|不依赖执行时再调用Python编译器|
|实际需要的格式词义／系统模板|按该格式的现行职责捕获Configs词义及必要LC_TIME模板／词条；纯数字格式不探测locale|旧Expr保旧资料；新Expr使用新的有效资料|

先捕获Configs／显式选项，default按这个稳定规则集解析；准备default可能执行的真实来源协议只在Python入口依当前支持范围执行一次，其对原cfg的副作用不反向修改已捕获的规则。worker只持受检原生数据，不保存可执行Python cfg／default／pickle回调；不得在每行、每个chunk或每次collect重新读取原对象。地区快照保登记有效性，不能因Rust数据库存在同名key而激活一个恢复时已标为不可用的地区；不把Python ZoneInfo对象直接塞进无GIL参数。

**例1：编辑Configs后，同一个Expr仍使用旧规则。**

```python
# 拟议PLDT接口，尚未实现。
cfg = Configs()
cfg.add_month("mymonth", 2)
lf = pl.DataFrame({"text": ["14 mymonth 2024"]}).lazy()

expr_old = pl.col("text").pldt.parse(unit="us", cfg=cfg)
cfg.set_month({"mymonth": 3})
expr_new = pl.col("text").pldt.parse(unit="us", cfg=cfg)

result_old = lf.select(expr_old.alias("time")).collect()
result_new = lf.select(expr_new.alias("time")).collect()
# expr_old／expr_new：pl.Expr；select后：pl.LazyFrame。
# result_old／result_new：pl.DataFrame，time列均为Datetime(us)。
# 旧表达式：2024-02-14 00:00:00；新表达式：2024-03-14 00:00:00。
# 取result_old["time"]：普通pl.Series，不自动包装Pldt。
```

同一Expr在相同输入及兼容执行环境下重复collect，不因原cfg继续编辑而改变。现有Pddt是立即执行，修改后下一次调用自然使用新词表；已构造出的旧Pddt也不会随cfg编辑而改变。这是执行时点差异，不为统一而修改Parser／Pydt／Pddt已采用合同，尤其保D01真实回调后读取次序。

**例2：default只准备YMD，不成为运行期Python依赖。**

```python
from datetime import date

expr = pl.col("text").pldt.parse(
    unit="us", default=date(2024, 5, 7)
)
lf = pl.DataFrame({"text": ["12:30", None]}).lazy()
result = lf.select(expr.alias("time")).collect()
# expr：pl.Expr；result：pl.DataFrame；time：pl.Series[Datetime(us)]。
# 值：2024-05-07 12:30:00、null；不把default填到null行。
```

default是自定义月份文本时，也按创建时Configs快照准备。例如default="14 mymonth 2024"在创建Expr时映射二月，之后把mymonth改成三月，不改变这个Expr的默认日期。完整性、真实类型、数值秒角色及default独立可解析的要求沿B04，不能借主输入或今天补齐。

**已确认的B04边界：文本Expr准备default采用提前校验例外。**

Expr创建时通常不知道未来数据是否空／全null。对任意支持的Python default，同时保证“此时就冻结完整解析值／真实来源协议”和“未来无文本时完全不触碰default”不能无条件兼得。已确定选择前者，保持入口直接、worker纯原生；所传default不合法或真实协议失败，就在创建文本Expr时报告原有对应类别／原协议异常，标明default，不保存异常等到后来挑行触发。

```python
# 当前Pddt实测，也是拟议立即Pldt继续保留的行为：
x = Pddt([None], unit="us", default="May 7")
# Pddt，一行NaT；没有普通文本，不解析这个不完整default。

# 拟议文本Expr：
expr = pl.col("text").pldt.parse(unit="us", default="May 7")
# 建议在这一步报ValueError系错误：default缺少年份，须独立完整。
# 即使以后输入恰好全null，也不把静态参数校验延后或吞掉。
```

此处是**用户已确认的明确例外**。B04按需准备继续适用于立即构造和现有库；文本Expr采用D02的创建时准备规则。普通数据文本非法仍在实际执行时失败；非法cfg／unit／开关／静态格式继续按其参数职责在准备阶段拒绝。原生日期变换不新增无关default参数或准备成本。

**例3：格式资料在创建格式Expr时准备，纯数字格式不读取locale。**

```python
# strptime完整格式合同见D04；本例只说明资料时点。
expr = pl.col("text").pldt.strptime("%x %X", unit="us")
# 假设创建时LC_TIME为C，对应文本：05/07/24 12:30:00。
# 建议创建时捕获相应模板；之后修改LC_TIME不改变旧Expr模板。
lf = pl.DataFrame({"text": ["05/07/24 12:30:00"]}).lazy()
result = lf.select(expr.alias("time")).collect()
# expr：pl.Expr；result：pl.DataFrame。
# time：pl.Series[Datetime(us)]；值2024-05-07 12:30:00。
```

格式里的配置名称沿Configs规则；只有格式本来需要系统资料时才读取对应locale，不自动使用本机缩写作为%Z规则。准备时若发现LC_TIME在读取期间变化，明确失败，不得到混合快照。D04将决定完整格式能力；本项不预先批准所有指令。快照锁定配置值及准备好的格式资料，不承诺不同机器／tzdata／插件版本的执行环境完全相同；跨机计划边界仍在M04。

**与Pddt的差异：**普通Pddt解析每次立即读取有效配置，default在实际普通文本首次出现时准备一次；Pddt.strptime已按一次调用准备格式和规则。Expr则把对应静态准备移到创建时，稍后collect只处理数据。立即Pldt继续贴近Pddt现行语义，不为了Expr改写旧类回调或全null路径。

**不采用的路线及原因：**每次collect再读活cfg／default会使同一个表达式依赖外部可变Python状态，需要额外桥接／同步；为兼顾未来全null而建立复杂延迟默认值／回调层也不采用。采用前述创建时快照与提前校验，写入文档和测试；原提案及替代讨论保存在历史快照，不作为第二套现行合同。

**性能影响：**同进程Arc/COW捕获词表句柄可低成本复用，default只准备一次、纯数字格式不读locale、旧Expr重用不重复执行Python准备。插件参数编码有与资料量相关的成本，不能把Arc句柄的低成本推广为跨库传输零成本；数据解码可能按原生调用／分区发生，需要M02实测，禁止每行复制或重建词表。大列及重复执行较可能受益，小列／大量一次性Expr可能主要体现固定准备成本，目前无速度倍率。直接关联已批准D01.O2批次准备，D01.O1/O3/O4及其保护边界保持，后续回顾必须明确引用。

**验收要求：**旧／新Expr分别解析二月／三月，原cfg删除后旧Expr仍可执行；同一输入重复collect不受后续编辑影响；default按冻结配置得到同一YMD且真实来源协议不在worker重放；立即空／全null跳过无关default而文本Expr不完整default创建时失败；格式词义／locale按创建时捕获，数字格式不读系统locale；地区不可用状态不被绕过。查询无输入时不伪造成功结果，执行线程只读原生资料；当前Pddt回调和全部旧正确文本保护。测试计划和精确插件参数／构建证明留N/M，不把本建议当已完成。

<a id="pldt-d03"></a>

### D03 带时区文本、混合来源与Expr输出时区必须预知

**已确认职责：**区分文本／原生来源的时区与最终整列的输出时区。来源时区用于解释当地钟表；目标tz用于给naive字段附区或将已知真实时刻转换到目标。整列只有一个Datetime时区元数据，不能每行另设dtype，也不能在Expr首批执行后改schema。本项完整确认，接口仍待实施。

**采用方案：共同日期含义沿Pddt，Expr额外要求可事先确定的输出时区。**

|入口／来源|未指定目标tz|明确指定目标tz|
|立即Pldt／Series解析：全部有效来源naive|输出naive日期列|按目标当地钟表解释|
|立即解析：全部有效来源同一可表达地区／等值标准固定偏移|保共同来源区；同地区冬夏不同offset仍是同一区|保每个真实时刻，转换到目标|
|立即解析：不同地区／不同固定偏移，或naive与aware混合|明确报错，提示传tz；不选第一行／local／UTC，不退object|按每项来源角色统一到目标|
|普通String Expr共享解析|规划输出naive；执行仅接受非缺失naive结果，遇已识别来源区／offset报错，提示显式tz|规划输出Datetime(unit, tz)，执行按真实来源解释后统一|
|已有Datetime Expr且schema带区|保已有schema区，不能把它当作未知String结果|明确需要转换的入口按已知源区／目标区处理|

所有地区／固定偏移是否可作为Polars输出dtype按H01确定，本项不承诺任意Python tzinfo或任意固定偏移都能存入Polars；无法表达时明确失败并提示可选目标，不暗改UTC或去区。tz仍是单值参数，不扩成逐行时区列。空／全null按B04/C02保已声明元数据；缺失行不参与来源区冲突，也不免除静态选项校验。

**例1：登记地区名后，先按来源区解释，再转换目标。**

```python
# 以下PLDT接口均为拟议行为，尚未实现。
cfg = Configs()
cfg.add_tzone("America/New_York")

x = Pldt(
    ["2024-01-01 12:00 America/New_York"],
    unit="us", cfg=cfg, tz="UTC",
)
# x：Pldt，dtype=Datetime(us, UTC)。
# 值：2024-01-01 17:00:00+00:00。
```

同一来源转到Asia/Shanghai则是2024-01-02 01:00:00+08:00，不能把文本12:00直接替换为UTC／上海12:00。来源地区文本只按有效Configs登记，不因目标tz合法就自动识别全部IANA名称：没有登记America/New_York时，即使tz="UTC"也应报来源区未登记的错误并提示cfg.add_tzone。已经传入的真实aware datetime／日期列按其原生元数据处理，不要求再在cfg登记其来源区；目标tz的解析与文本词表登记是不同职责。地区与数字offset同时识别时保既定地区优先，不增加额外一致性判断。当前公开Parser的ignoretz默认值不因PLDT修改，Pddt／Pldt保留来源区的内部路径继续独立按自身合同执行。

**例2：立即解析可保共同来源区，不能只看当日offset。**

```python
x = Pldt([
    "2024-01-01 12:00 America/New_York",
    "2024-07-01 12:00 America/New_York",
], unit="us", cfg=cfg)
# Pldt，Datetime(us, America/New_York)。
# 2024-01-01 12:00:00-05:00
# 2024-07-01 12:00:00-04:00
```

纽约冬夏offset不同仍保同一地区。相反，纽约与多伦多在某日offset相同，也不能在未指定目标时当成同一个地区；不同地区的历史规则可能不同。naive／aware混合无目标也拒绝，沿现有Pddt：

```python
values = [
    "2024-01-01 12:00",
    "2024-01-01 12:00 America/New_York",
]
x = Pldt(values, unit="us", cfg=cfg, tz="UTC")
# Pldt，Datetime(us, UTC)。
# 第一行naive在目标UTC解释：2024-01-01 12:00:00+00:00。
# 第二行来源纽约保真实时刻：2024-01-01 17:00:00+00:00。
# 不传tz则拒绝这组混合有效来源。
```

数字刻度沿其纪元instant职责，不与naive文本混淆：Pddt当前实测Pddt([0], unit="us", tz="Asia/Shanghai")为1970-01-01 08:00+08，文本"1970-01-01 00:00"配同目标为00:00+08。PLDT按B/C同义保留，原生日期／数字不转文本重解析。

**例3：String Expr显式选择输出区，不能在执行中改变dtype。**

```python
lf = pl.DataFrame({"text": [
    "2024-01-01 12:00 America/New_York",
    "2024-07-01 12:00 America/New_York",
]}).lazy()

expr = pl.col("text").pldt.parse(unit="us", tz="UTC", cfg=cfg)
result = lf.select(expr.alias("time")).collect()
# expr：pl.Expr；select后：pl.LazyFrame；result：pl.DataFrame。
# time：普通pl.Series[Datetime(us, UTC)]。
# 值：2024-01-01 17:00:00+00:00、2024-07-01 16:00:00+00:00。
```

```python
expr = pl.col("text").pldt.parse(unit="us", cfg=cfg)
# expr仍是pl.Expr，输出schema为Datetime(us)，无时区。
result = lf.select(expr.alias("time")).collect()
# 执行时报错：文本包含来源时区，请明确传tz="UTC"等输出目标。
# 不静默丢区，不默认转UTC，不按第一行／首chunk改变schema。
```

即使全部文本来自同一已登记地区，cfg中存在该地区也不等于调用者选择它作输出区；通用String Expr仍须明确tz。全部naive文本则可省略tz。对已有Datetime列，时间区已在schema中，例如pl.col("time").pldt.as_unit("us")可按C03保原区，不因此强迫所有日期表达式再次传tz。strptime／fromisoformat等专用格式入口的可推导能力继续在D04／E05确定，不把普通文本规则扩大为“所有Expr必须显式tz”。

**与Pddt的差异：**立即路径继承其来源／目标含义和冲突规则；返回Pldt而非Pddt，日期缺失用独立null而非NaT哨兵。Expr是新增执行形式，未知String来源额外显式选择输出区；已知Datetime schema可以保区。一个Datetime列只有一个时区、Lazy执行前要知道schema，均贴合Polars执行模型；实际同版本原生通用Expr的拒绝结果也支持这一方向，不把共享语法偷偷替换为Polars strptime语言。

**错误与性能边界：**无效静态目标按准备入口检查；未登记来源区、混合来源无目标、String Expr遇未请求时区等数据相关错误在读取对应数据时失败，指出来源／目标职责和可行用法；Polars插件异常边界见N03。strict不充当丢区、强制UTC或DST策略开关。来源本地化与已有真实时刻转换分开，只有需要地区当地解释时才做DST候选／不存在性处理；naive／UTC／标准固定偏移走直接整数路。输出schema一次确定，不预扫数据、不全列试解析后重来、不逐行构造datetime或Pldt；可按来源地区复用实际所需准备。纯区转换的时区元数据复用须保源instant，底层ticks是否可借按B05。当前无PLDT正式倍率，未来须保护现有Parser／Pydt／Pddt并明确引用D01及D02。

**不采用的路线：**所有String Expr默认输出UTC会给普通naive输入增加未请求的含义变化；按首个值猜输出区或预扫描全列则破坏确定schema和延迟执行。采用前述显式输出目标，保立即与原生已知schema的便利；专用格式的可推导能力见D04／E05。

**验收要求：**已登记／未登记地区配显式目标；冬夏同地区及同offset不同地区；naive／aware混合与显式目标；数字刻度／文本角色；region优先于offset；空／全null元数据；String Expr无目标遇aware拒绝且不随chunk顺序改变schema；已知Datetime Expr保区；地区策略默认及细项按H另定。以独立UTC整数答案验证真实时刻、ns／unit／null／来源未修改，不仅对比两入口相等。

<a id="pldt-d04"></a>

### D04 strptime的格式语言、Configs和系统locale

**本项要决定的职责：**Pldt类工厂、Series命名空间和Expr的strptime使用本库已完成的共享格式语言／Rust规则；保持Pydt／Pddt共同含义，按Polars输出类型及schema准备差异。本项同D01—D03均已完整确认；保留cfg及地区策略，给Pddt／Pldt的strptime同步增加目标tz，接口尚未实现。

**采用一：原生执行形式贴合Polars，格式语言沿本库共享内核。**

```python
# 平行调用，均尚无PLDT实现。
s = pl.Series("text", ["1970-01-01 00:00:00.123"])

# Polars原生：Chrono格式，日期输出普通pl.Series。
result_native = s.str.strptime(
    pl.Datetime("ns"), format="%Y-%m-%d %H:%M:%S%.f"
)

# 本库：共享Pydt/Pddt格式，日期输出Pldt。
result_pldt = s.pldt.strptime(
    fmt="%Y-%m-%d %H:%M:%S.%f", unit="ns"
)
# 两者原生ns刻度均应为[123000000]。
```

本库格式必须明确提供，不猜格式，不自动把Python式格式翻译为Chrono再尝试，也不在失败后转去Polars／pandas／datetime重新求成功。用户主动使用s.str.strptime保其原生完整合同；本库.pldt.strptime按自身合同实现。保本库已支持数字／日历／名称／组合／时区／字面量，未知指令明确拒绝，不因借Rust生态就宣称支持全部Chrono或所有平台私有strftime修饰。

|格式职责|建议复用规则|
|%Y/%y/%m/%d及已有字段别名|沿共享数字规则；有边界的%Y支持零／负／宽年，最终容量各类负责；%y保格式标准世纪规则，不套普通Parser的default参考年|
|%H/%I/%M/%S/%f|按格式匹配，不套普通parse的宽松小时／日期收口；%f规则见下|
|%b/%B、%a/%A、%p|查有效Configs的month／weekday／ampm；cfg=None用已完成默认Rust表，不补回显式cfg已删除词条|
|%j、%G/%V/%u、%U/%W等已支持组合|沿共享checked日历和格式组合含义，不套便利工厂上限收口|
|%z／%:z|沿既有数字偏移语法／精度；先保来源真实含义|
|%Z|仅有效cfg.utc／tzoffset／tzone规则，保UTC／固定偏移／地区含义，不猜本机缩写|
|%c/%x/%X/%r等已支持系统复合格式|按实际需要准备当前LC_TIME模板／内部词条，再由Rust解析；系统内部词义不全量灌入Configs|
|%%、空白、字面量及可确定展开的已有组合|正常文本按格式完整消费，尾随垃圾报错，不忽略或切换引擎|

省略字段沿标准1900-01-01／零时钟，不使用今天，不增加通用Parser default／yearfirst／dayfirst／isoformat或strict开关；strptime不因此新增errors='coerce'、exact=False、格式列表和%N。明确日期缺失沿B04保null，不把普通格式不匹配变null。Pydt最终us及1—9999，Pddt／Pldt的宽年／ns按自身单位容量；不为统一改现有类已批准精度／容量。

**采用二：%f完整读取，最后按出口精度截取；单位准备与C02一致。**

```python
text = "1970-01-01 00:00:00.1234567899"
fmt = "%Y-%m-%d %H:%M:%S.%f"

x_ns = Pldt.strptime(text, fmt, size=1, unit="ns")
x_us = Pldt.strptime(text, fmt, size=1, unit="us")
x_ms = Pldt.strptime(text, fmt, size=1, unit="ms")
# 都是Pldt；对应刻度分别123456789、123456、123。
# 第十位完整消费但不进位，不经float或长尾大整数。
```

strptime主动按unit截取是已有明确功能，不放宽普通构造的无损规则。时区／日期解释完成后才降精度；负纪元取更早目标刻度，真实容量仍检查。立即入口未给unit沿Pddt：至少us，前九位有实际非零ns尾数才选ns，第十位以后不增加精度；例如.123456000自动us，.123456789自动ns。

Expr格式在创建时已知：准备后的完整格式不含%f时默认us；含%f而未给unit时，原默认取决于尚未读的行值，因此创建Expr时报错，提示明确ms／us／ns。不要将全部格式Expr无条件要求unit，也不以统一默认ns改变范围／容量；含系统复合格式时按D02准备后的实际步骤判断。显式%f配us／ms允许上述主动截取，区别于通用parse显式unit的无损构造。

```python
expr = pl.col("text").pldt.strptime("%Y-%m-%d")
# pl.Expr，输出Datetime(us)；不含%f，可静态确定默认。

expr = pl.col("text").pldt.strptime(
    "%Y-%m-%d %H:%M:%S.%f", unit="ns"
)
# pl.Expr，输出Datetime(ns)；省略unit则创建时失败。
```

**采用三：Configs／locale按D02准备；%Z保明确名称准入。**

```python
cfg = Configs()
cfg.add_month("mymonth", 2)
cfg.add_tzone("America/New_York")

x = Pldt.strptime(
    "14 mymonth 2024", "%d %B %Y", size=1, cfg=cfg
)
# Pldt，Datetime(us)，2024-02-14 00:00:00。
```

直接名称指令查已有Configs表，不新建多语言表／依赖Babel。系统复合模板只在需要时读现有公开适配资料：立即入口按当次有效locale，Expr按D02创建时捕获；纯数字格式不探测locale，不改全局locale，检测到资料准备期间的locale变化则明确失败。格式结构缓存与实际词义／locale状态分离；不按cfg对象身份缓存过期词义。不可用地区不能因原生后端有同名key而激活。

**采用四：Pddt与PLDT格式入口同步增加目标tz；含时区的格式Expr明确指定输出区。**

Pddt.strptime与Pldt.strptime同步提供仅关键字tz=None，保dtstr／fmt、size、unit、name、cfg及既定DST策略职责。PLDT的Series／Expr命名空间使用已有列作文本来源，fmt／unit／cfg／tz等是单值准备参数，不额外传size。日期结果分别为Pddt／Pldt／原生pl.Expr；DataFrame.select得到DataFrame，取列为普通pl.Series。Pydt单值格式入口不在本项追加目标参数；策略完整范围仍按H，不由D04单独提前批准。

立即Pddt.strptime／Pldt.strptime无目标时保原有共同可表达来源区，混合来源按D03拒绝；给目标则先按%z/%Z来源解释，再统一输出。对Expr：不含时区步骤且未给tz时输出naive；准备后的格式含%z/%Z时必须给tz，因为源offset／地区仍可能随行不同，不能保任意原区而又事先固定dtype。格式已知，所以这项遗漏在创建Expr时报告，不等执行到必然失败的非null文本。若格式无区但给目标，按目标当地钟表解释。tz=None不表示去时区，不自动输出UTC；原有省略目标的调用含义保持，各目标容器仍守可表达时区及容量。

**两边同步增加的实际价值与实现依据：**Pddt／Pldt同步增加目标tz，保既有cfg和地区策略。当前b2实测对+0800／+0900的混合格式文本，Pddt.strptime先报不同来源区无法合列，无法随后再tz_convert；错误虽建议传目标tz，该公开入口目前却会对tz关键字报TypeError。两边不加会保留这一能力限制，并迫使PLDT带区Expr另选隐式UTC或拒绝。同步增加既统一列类参数职责，也能解析这类真实输入：

```python
# 已确认接口，尚未实现；两个列类输出各自日期类型。
values = ["2024-01-01 12:00+0800", "2024-01-01 12:00+0900"]
fmt = "%Y-%m-%d %H:%M%z"
x_pd = Pddt.strptime(values, fmt, unit="us", tz="UTC")
x_pl = Pldt.strptime(values, fmt, unit="us", tz="UTC")
# x_pd：Pddt；x_pl：Pldt，Datetime(us, UTC)。
# 两者日期均为2024-01-01 04:00:00+00:00、03:00:00+00:00。
```

当前rust/pddt/formatted.rs最终调用finish_truncated时把已有target位置固定传None，common.rs的同一最终收尾已支持目标区／来源本地化／合并后截取。建议复用该能力并在入口统一准备目标，不先构造Pddt再tz_convert／tz_localize，也不新增解析引擎。源码基础不等于已完成：须验证显式tz=None／省略保持、naive附区、aware保时刻、混合来源、ns最后截取、DST策略、空／全null、错误上下文和逐项性能保护。tz=None普通路径只保轻量可选分支，显式目标按一次准备和最终构建融合；当前没有新性能倍率或零开销承诺。证据见D04/paired-target-proposal-02/current-mixed-offsets.json。

```python
expr = pl.col("text").pldt.strptime(
    "%Y-%m-%d %H:%M %Z", unit="us", tz="UTC", cfg=cfg
)
lf = pl.DataFrame({"text": [
    "2024-01-01 12:00 America/New_York"
]}).lazy()
result = lf.select(expr.alias("time")).collect()
# expr：pl.Expr；result：pl.DataFrame。
# time：普通pl.Series[Datetime(us, UTC)]；值2024-01-01 17:00:00+00:00。
# 此格式省略tz则创建Expr时报缺少明确输出区的错误。
```

**不采用的路线：**含时区格式Expr省略目标后自动转UTC、仅PLDT增加目标、以及三个类去cfg／去地区策略均不采用。Expr明确输出tz，立即路径省略目标保来源含义；仍须按H核实各容器时区能力。不因本项扩大到Pydt目标参数或E05工厂。

**具体拒绝例子：**"2024-02-30"配%Y-%m-%d明确日期非法；"2024-01-02 banana"有未消费内容；.%N或Chrono的%.f属于不支持的本库格式；%Z的未登记地区／未知CST给出登记用法，数字偏移用%z。缺失字段的标准默认、合法%j跨年等仍按格式合同，不能把严格匹配误写成所有字段都套相同收口／范围规则。

**与当前Pddt的关系及跨类边界：**共享语法、名称、完整匹配、日历、小数及立即来源含义保持；最终规则给Pddt／Pldt的strptime同步增加可选目标tz，原省略调用不改为自动UTC。Pldt仍用Polars原生ms/us/ns／null和容量，Expr按已知格式决定schema与静态错误时点；Pydt不在本项扩大参数。现有Pddt真实格式调用／回调／词义快照保护，不用PLDT新增测试代替旧样本。

**性能影响与共享边界：**结构／数字尾宽编译和规则准备在批次／Expr入口执行，复用现有有界结构缓存与D02原生快照；数据逐行走Rust格式步骤，原生String接D01 UTF-8适配，普通路径不经Python datetime／pandas解析、逐行Pydt或中间Pldt。当前格式类型和地区对象有Python边界，只抽必要原生步骤／错误／资料供worker，不把PyRef直接传无GIL线程。小数只累积必要位并完整跳过余数，不构建长尾数；底层分区解码、词义准备和端到端收益需实测，不能仅因Rust执行宣称提速。关联D01及其已批准O1—O4，保护旧类原调用性能；不新增通用格式转换／fallback框架。

**验收要求：**不同小数宽度尤其3／6／9／10位独立整数预期；负纪元截取、尾随字面量／垃圾、相邻数字及年份后数字字面量旧修复、零／负／宽年与目标容量；Configs自定义／删除／修改后旧新Expr；%Z登记／未登记／地区优先，格式含区Expr遗漏tz；无%f Expr默认us、有%f遗漏unit及显式截取；系统格式准备及数字格式无locale调用；Series／Expr相同日期／dtype／null／来源未变。正式跨平台及插件／性能样本留M/N计划，当前50项观察不冒充实现已通过。

## E 全部命名工厂与日期范围

<a id="pldt-e01"></a>

### E01 now/today/utcnow的取钟和Expr时点

**已确认职责：**三工厂保持Pydt／Pddt已有当前时间含义，明确取钟次数、单位、空结果和进入Lazy计划后的时点。首版均为立即工厂，调用时取一次当前时刻并生成Pldt；需要Expr时用Polars原生pl.lit保存该日期列，不另造now Expr包装或运行期时钟框架。本项已完整确认，尚未实现。

**已确认接口与输出：**

```text
拟议Pldt接口，尚未实现：
Pldt.now(size, *, tz=None, unit=None, name=None)
Pldt.today(size, *, unit=None, name=None)
Pldt.utcnow(size, *, unit=None, name=None)
```

上面的签名用于说明参数；调用例子见下，非执行代码。三者均返回Pldt／Datetime列；unit=None默认us，原生存储仅ms／us／ns，显式s沿C01拒绝，不照抄Pddt的s存储。size用B02整数协议且非负，拒绝bool／float，0合法，name职责后续沿L01；空列也检查实际所传参数。

|调用|时区／时钟含义|返回类型及默认dtype|
|Pldt.now(n)|当前当地完整钟表，无时区|Pldt，Datetime(us)|
|Pldt.now(n, tz="Asia/Shanghai")|当前真实时刻在上海显示|Pldt，Datetime(us, Asia/Shanghai)|
|Pldt.today(n)|当前当地完整钟表，保时分秒，不归午夜|Pldt，Datetime(us)|
|Pldt.utcnow(n)|当前真实时刻，带UTC|Pldt，Datetime(us, UTC)|

显式unit改dtype，不改变这些时区职责。now／utcnow来源已经是确定的真实时刻，目标地区只是显示转换，不新增fold／ambiguous／nonexistent去重新选时间；可接受目标及后端范围仍按H。naive输出按当地钟表得到，不把UTC整数直接伪装成当地字段。

**例1：一次调用的所有行重复同一时刻。**

```python
x = Pldt.utcnow(3, unit="ns", name="stamp")
# Pldt，Datetime(ns, UTC)，3行原始tick完全相同。
# 假设本次取到2024-05-07 04:30:00.123456789+00:00：
# 2024-05-07 04:30:00.123456789+00:00
# 2024-05-07 04:30:00.123456789+00:00
# 2024-05-07 04:30:00.123456789+00:00
```

同一假设时刻，now(3, tz="Asia/Shanghai", unit="ns")显示12:30:00.123456789+08，now(3)／today(3)是本地完整naive时钟；真实连续的不同工厂调用各自重新取一次时刻，不能要求它们彼此完全相等。以上是假设例子，不是当前真实时钟数据或系统保证。

**例2：单位是请求分辨率，不是强制无损地转换更细当前值。**

```python
x = Pldt.now(2, tz="UTC", unit="ms")
# Pldt，Datetime(ms, UTC)；按照ms取更早边界。
x = Pldt.today(0, unit="ns")
# 空Pldt，Datetime(ns)，不取时钟。
x = Pldt.utcnow(0, unit="ns")
# 空Pldt，Datetime(ns, UTC)，UTC元数据仍保留。
```

now/today/utcnow本来就按所选精度取得当前值，ms不会因系统有us/ns尾数而报无损精度错误；真实容量／checked范围仍保护。ns直接保系统整数实时时钟提供的信息，不先经datetime或float缩成us再放大，也不为让尾数非零而补造精度。若系统实际只提供us，ns尾三位为0完全合法；ns dtype不承诺1ns准确度或每次调用都不同。已采用Pydt的us出口和其它普通构造／单位转换的无损合同不变。

**例3：进入Expr用原生literal，重复collect不重新取当前时间。**

```python
stamp = Pldt.utcnow(2, unit="ns", name="stamp")
expr = pl.lit(stamp).alias("stamp")
lf = pl.DataFrame({"id": [1, 2]}).lazy().select(pl.col("id"), expr)

first = lf.collect()
second = lf.collect()
# stamp：Pldt；expr：pl.Expr；lf：pl.LazyFrame。
# first／second：pl.DataFrame；日期列为普通pl.Series[Datetime(ns, UTC)]。
# 时间流逝不触发重新取钟，两次使用同一份此前取得的日期数据。
```

pl.lit是用户主动将已存在的Series作为字面数据接入计划，不表示在worker执行Pldt.utcnow。保原生ns缓冲，不写stamp[0]后再把Python datetime塞回计划，以免纳秒尾数提前损失；不新增to_expr／to_series包装。示例列长为2，与DataFrame行数一致；原生literal的其它广播／长度行为沿Polars，不扩大B02的自有逐行参数广播。所有权及可变外部缓冲仍按B05，快照时点不等于对任意外部别名承诺绝对不变。

**与Pddt／Pydt的关系：**now／today／utcnow含义、数量及一次取钟与当前Pddt一致；Pldt限定原生三单位、使用Polars日期列及Expr，Pydt为单个datetime真子类且us。Pddt现在已直接用整数时钟填充一次，不把它当作待做新优化；新Pldt复用适合共享的最小取钟／单位函数，不为了调用Pddt私有工厂强制导入pandas，不逐行调用Pydt.now，不创建中间日期容器。

**性能影响：**非空取钟及时间区准备通常是一次固定成本，填充N行仍需O(N)数据／有效位／元数据工作，不能宣称整个工厂O(1)。空结果省去取钟及无关本地地区加载，仍保选项校验。按目标unit直接算tick，尽量转交最终原生缓冲并一次构造Pldt；naive／UTC／可表达固定偏移保持已有快捷路径，必要地区处理按实际instant转换，不走当地候选搜索。pl.lit无需新建本库包装框架，实际复制及生命周期以适配器证明为准，当前没有PLDT正式性能倍率。

**验收要求：**以可控内部时钟或隔离验证证明非空一次、空零次取钟；独立预期检查当地／UTC／显式地区含义、完整today、ms/us/ns、真实尾数和较粗边界、checked容量；bool／float／负数量拒绝；空dtype／显式区保留；直接native缓冲／最终一次容器。实际Series literal要保非零ns与两次执行的固定值，不能只比较Python datetime；反向核对现有Pydt／Pddt未被新工厂拖慢或改变。正式构建／跨平台和性能留M/N，已有22观察不转记新类PASS。

<a id="pldt-e02"></a>

### E02 四数值工厂的秒坐标、真实时间戳和微秒整数

**已确认职责：**fromseconds、frommicroseconds、fromtimestamp、utcfromtimestamp在Pldt立即路径及Series／Expr命名空间保现有数值含义，明确输入单位与输出unit、数量／缺失、默认schema和本地区准备时点。推荐复用Pydt／Pddt已确定语义与最小Rust数值内核，PLDT出口保ns／有效位／原生单位；本项已完整确认，尚未实现。

**一、四个名称保不同职责，不合并为同一种时间戳。**

|工厂|输入含义|传零和上海时区的日期|拟议输出|
|fromseconds|以无区1970-01-01 00:00为起点的秒钟表坐标，再附目标区|1970-01-01 00:00:00+08:00|Pldt，默认Datetime(us, Asia/Shanghai)|
|frommicroseconds|同一无区坐标的整数微秒，再附目标区|1970-01-01 00:00:00+08:00|Pldt，默认Datetime(us, Asia/Shanghai)|
|fromtimestamp|真实UTC纪元秒，转换到目标显示区|1970-01-01 08:00:00+08:00|Pldt，默认Datetime(us, Asia/Shanghai)|
|utcfromtimestamp|真实UTC纪元秒，固定输出UTC|不接目标tz；1970-01-01 00:00:00+00:00|Pldt，默认Datetime(us, UTC)|

```python
# 拟议Pldt接口，尚未实现。
x = Pldt.fromseconds(0, size=1, tz="Asia/Shanghai")
# Pldt：1970-01-01 00:00:00+08:00。
x = Pldt.fromtimestamp(0, size=1, tz="Asia/Shanghai")
# Pldt：1970-01-01 08:00:00+08:00。
```

无tz时fromseconds／frommicroseconds保无区纪元钟表，不读取local改变坐标；fromtimestamp按当前Pydt／Pddt转换到本地区后返回naive钟表，本机上海0秒为08:00；utcfromtimestamp始终UTC aware。fromseconds／frommicroseconds附地区会解释新的当地时间，所需ambiguous／nonexistent职责保留，完整策略见H；timestamp两个入口已有真实时刻，不新增这些策略或fold重选。time zone仍单值，单位／输出能力按C/H，不让四方法因共享代码失去含义。

**二、输入单位固定，unit只决定输出存储分辨率。**

```python
x = Pldt.fromseconds(1.5, size=1, unit="ms")
# Pldt，Datetime(ms)，刻度1500，即纪元后1.5秒。
x = Pldt.frommicroseconds([1000, 2000], unit="ms")
# Pldt，Datetime(ms)，刻度[1, 2]。
x = Pldt.fromseconds(1e-9, size=1, unit="ns")
# Pldt，Datetime(ns)，刻度1。
```

fromseconds和timestamp两入口的数字始终表示秒，frommicroseconds始终表示整数微秒；不得按unit把1.5解作1.5毫秒。保负数真实含义，大整数／index不先float；例如9007199254740993微秒当前能精确保留，不能因通用float读取丢1。秒数按现有合法数值协议读一次，小数到ns沿已批准换算；Pydt最终us不因此强制新增ns输出。

普通数值工厂显式unit必须无损，不套E01当前时间或D04的主动截取例外：1ns选us、1us选ms均ValueError并提示选择更细单位；真实容量不足OverflowError，不能自动升降单位、回绕或变null。PLDT仅ms／us／ns，s目标沿C01拒绝；默认至少us，确有非零ns尾数初次选ns，空／全缺失默认us，不为宽范围自动退ms。精度／容量检查实际结果而不是不必要的较窄中间值；C04完整int64及有效位职责保持，不能将合法数字误套Pddt NaT哨兵。

**三、输入、缺失和数量沿已确认角色。**

frommicroseconds只收整数协议，finite float含1.0／1.5均TypeError，不能截成整数；数字角色先拒Python／NumPy bool，普通数字文本／bytes拒绝，不因float(text)额外接收。秒数保已有专用数值协议，不把Delta的较窄数值合同强套上来；不强制接普通date／datetime／非缺失datetime64，使用对应日期入口。明确日期缺失沿B04为null，合法NaN是缺失而非有限float例外，不能把无穷或数值溢出吞成null；源有效位／顺序／长度保留。

```python
x = Pldt.fromseconds(1.5, size=3, unit="ms")
# Pldt，3行同一1500毫秒刻度，标量协议只准备一次。
x = Pldt.fromseconds([0, 1.5, None], unit="ms")
# Pldt：[1970-01-01 00:00:00, 00:00:01.500, null]。

Pldt.frommicroseconds(1.0, size=1)  # TypeError，整数微秒不接float。
Pldt.fromseconds(True, size=1)     # TypeError，bool不是数值日期。
Pldt.fromseconds("1.5", size=1)    # TypeError，不解析数字文本。
Pldt.fromseconds(1.5)              # 缺size，ValueError。
Pldt.fromseconds([1.5], size=1)    # 集合不同时给size，ValueError。
```

一维来源统一沿B01/B02/B03，不再另造四种容器规则；长度1集合仍是集合，标量size非负整数、bool／float拒绝。合法原生列直接读dtype、数值缓冲和有效位；普通Python来源按真实协议在入口一次准备。size=0仍验证所传标量／选项，但不做无用日期填充；立即空／全缺失fromtimestamp不加载不需要的local服务，沿现有Pddt读取时点。

**四、原生数值Series／Expr直接提供平行入口；能推导的默认不强制填写。**

```python
s = pl.Series("seconds", [0.0, 1.5, None])
x = s.pldt.fromseconds(unit="ms", tz="UTC")
# Pldt，Datetime(ms, UTC)，刻度0／1500／null。

expr = pl.col("seconds").pldt.fromtimestamp(unit="ns", tz="UTC")
result = pl.DataFrame({"seconds": [0.0, 1e-9, None]}).lazy().select(
    expr.alias("time")
).collect()
# expr：pl.Expr；result：pl.DataFrame。
# time：普通pl.Series[Datetime(ns, UTC)]，有效刻度0／1，第三行null。
```

Expr默认单位由输入schema及方法职责决定，修正旧目录里“所有数值Expr都必须明确unit”的过度约束：

|方法／输入schema|省略unit的规则|
|frommicroseconds|固定us；有限float按数据规则拒绝、明确缺失保持，不把Float NaN列一概误拒为普通float|
|fromseconds／fromtimestamp／utcfromtimestamp的合法整数列|默认us，不能因个别大值而改单位；容量不足按实际结果报错|
|上述三入口的浮点秒列或无法静态证明默认的合法数值来源|规划时要求显式ms／us／ns，因为实际非零ns尾数依赖数据|
|明确Null来源／空缺失而无细精度声明|沿默认us及已选目标区；声明型来源仍按其真实角色校验|

输入字段可能要到query规划时才可知，缺单位等错误在schema推导阶段报告，不承诺pl.col方法创建时就已有dtype。所有batch／空结果输出同一schema，不按第一行猜单位。目标tz已明确时输出区已知；fromseconds／frommicroseconds无目标为naive，utcfromtimestamp固定UTC。

**fromtimestamp省略tz的Expr准备差异（已确认）：**为了保Pydt／Pddt的“本地naive”含义而不在worker调用Python，建议创建Expr时捕获当前库有效本地区并准备原生资料，执行时真实UTC秒转成该地区钟表、去区；同一Expr不在collect／chunk重新发现本地区。这里只准备地区规则，不读取当前时钟。未知未来是否为空／全null时，可能提前发生一次本地区准备；这与立即入口按首个有效数值再加载local不同，作为明确Expr准备差异记录，不能暗称全路径按需。显式目标或utcfromtimestamp不读取local；使用已有本地区缓存／服务，不另建探测层，地区能力和后端版本仍按H/M。若原生适配已有等价安全准备，可复用，不能把Python ZoneInfo对象塞进无GIL参数。

**与Pddt／Pydt的关系：**四方法的数值坐标、附区／转换含义、微秒整数及拒绝bool均以当前Pydt／Pddt为依据。列类保缺失、ns、批量；Pydt保持自身标量／us及容量，不扩NaT。Pldt是Polars容器、仅三原生单位及独立有效位；新增命名空间Expr遵守schema和前述local快照差异。不能为了平行把fromseconds改成fromtimestamp、把无tz timestamp改UTC或统一所有数值先转float。

**性能影响：**复用现有checked整数／小数秒／单位函数，标量在循环外一次准备，原生数值列用typed循环及有效位，不经字符串解析、逐行Python scalar／datetime或中间Pydt／Pddt。目标区／单位计划外提；必要地区附区的成本保留，UTC／固定偏移及已有真实instant转换省去当地候选搜索。输出最终构建一次，输入不可变及所有权沿B05；额外schema／地区准备是固定成本，实际吞吐／小列收益待测，当前无PLDT正式倍率。共享修改复核应明确引用D01及四项已批准优化，保护已采用Parser／Pydt／Pddt。

**验收要求：**独立epoch整数答案核对两类坐标、默认本地／UTC、负值及不同目标；1e-9、非零尾数、明确unit拒损、大整数不先float；bool／有限微秒float／文本／无穷及必要协议一次；标量／列／空／全缺失、原生缓冲／有效位。Expr按Int／Float／Null规划单位并保空batch schema，local捕获和无Python worker读取，naive附区与instant转换的DST职责分开。测试既有正确样本和类差异，正式平台／插件／性能留M/N，不转记现有48观察为新类PASS。

<a id="pldt-e03"></a>

### E03 fromdate/fromdatetime/fromdatetime64来源职责

**本项职责与状态：**三个专用工厂沿Pydt／Pddt的真实来源角色，区分取日期、保完整钟表、解码NumPy日期，以及附区和转换。本项已完整确认，尚未实现；未修改产品实现。立即入口返回Pldt，适用Series命名空间返回Pldt，适用Expr返回原生pl.Expr。

**一、三个工厂各守来源与含义，不改成普通parse。**

|工厂|可接受的真实日期来源（缺失沿B04）|时钟／时区职责|
|---|---|---|
|fromdate|Python date／datetime及真实子类，适用Timestamp；匹配的pandas／Polars Date／Datetime原生列|取来源当地YMD，时钟和小数归零，源区／fold不继承；明确tz附到该日午夜|
|fromdatetime|datetime／Pydt／Timestamp及真实子类，匹配的pandas／Polars Datetime列|完整字段和真实精度；tz省略／None保源区及已知时刻，明确tz替换源区并保钟表|
|fromdatetime64|真实NumPy datetime64标量或合法一维NumPy日期来源／集合|读真实刻度、单位／倍率；NumPy没有源时区，明确tz附到解码钟表，不把它当UTC瞬间转换|

普通文本／数字不能因能parse就混入这些入口；fromdatetime拒纯date／Polars Date，fromdate及fromdatetime不借宽收接NumPy日期，fromdatetime64不接普通datetime或Polars／pandas Datetime列。精确缺失标记仍沿B04，不因专用来源而取消；合法一维外层、标量size、列禁止size、None／bool／选项角色沿B01—B04。真实子类按既定字段／协议读取，不能按类名或模块字符串筛掉；不是为了性能直接读取替代字段。原生来源按dtype／元数据直接衔接，不强制拆为Python日期。

```python
# 以下接口是已批准的新版本目标。
source = datetime(2024, 1, 2, 12, 30, 45, 123456,
                  tzinfo=ZoneInfo("Asia/Shanghai"))
x = Pldt.fromdate(source, size=1)
# Pldt，Datetime(us)：2024-01-02 00:00:00，无时区。
x = Pldt.fromdate(source, size=1, tz="UTC")
# Pldt，Datetime(us, UTC)：2024-01-02 00:00:00+00:00。
x = Pldt.fromdate([date(2024, 1, 2), None])
# Pldt，Datetime(ms)：当日午夜／null；date的s来源按C01映射ms。
```

提取YMD必须按来源当地日历：上海2024-01-02 00:30在UTC仍是1月1日，但fromdate结果为1月2日午夜，不能先按UTC刻度直接除日。取日期本来就丢弃钟表／小数；因此带ns钟表的来源先fromdate再输出ms可以成功，不是允许fromdatetime静默丢ns。

**二、fromdatetime显式tz保钟表，普通构造显式tz保真实时刻。**

```python
source = datetime(2024, 1, 2, 12, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
x = Pldt.fromdatetime(source, size=1)
# Pldt，Datetime(us, Asia/Shanghai)：2024-01-02 12:30:00+08:00。
x = Pldt.fromdatetime(source, size=1, tz=None)
# 同上，None不是去掉时区。
x = Pldt.fromdatetime(source, size=1, tz="UTC")
# Pldt，Datetime(us, UTC)：2024-01-02 12:30:00+00:00，保12:30。
x = Pldt([source], tz="UTC")
# Pldt，Datetime(us, UTC)：2024-01-02 04:30:00+00:00，保真实时刻。
```

这个区别参考当前Pydt／Pddt，不是PLDT新增另一套时间含义；也对应Polars原生replace_time_zone与convert_time_zone的职责区别，不能混用。tz=None保留来源，明确非None即请求新地区解释，即使名字等于源区也保明确替换语义，不能当作必然no-op。未给目标且源区无法合成单一日期列时报错，不按第一行猜区／退Object；需要保各来源真实时刻统一目标时用普通构造或对应转换，不把fromdatetime的替换偷偷变转换。

已有aware来源的已知时刻保留其fold决定的瞬间，不重新本地化。明确tz替换后，新的当地钟表由整列ambiguous／nonexistent决定，原fold不覆盖这些策略，不另加fold参数。例如纽约2024-11-03 01:30 fold=1无目标保-05:00；显式tz="America/New_York"默认仍报重复时间错误，明确ambiguous=False才按该列策略选候选。策略完整集合／执行与地区可表达性见H，不由此扩大为任意Python tzinfo均可存Polars。

**三、ns／单位／容量保持来源，目标出口不经Pydt限制。**

```python
source = pd.Timestamp("2024-01-02 12:30:45.123456789", tz="Asia/Shanghai")
x = Pldt.fromdatetime(source, size=1)
# Pldt，Datetime(ns, Asia/Shanghai)：完整.123456789。
Pldt.fromdatetime(source, size=1, unit="us")
# ValueError：不能无损保存非零789ns尾数。
x = Pldt.fromdate(source, size=1, unit="ms")
# Pldt，Datetime(ms)：2024-01-02午夜；fromdate本来只取日期。

source = np.datetime64("2024-01-02T12:30:45.123456789", "ns")
x = Pldt.fromdatetime64(source, size=1, tz="Asia/Shanghai")
# Pldt，Datetime(ns, Asia/Shanghai)：2024-01-02 12:30:45.123456789+08:00。
# 附到12:30，不转换成20:30。
source = np.array([1, 2], dtype="int64").view("datetime64[3ms]")
x = Pldt.fromdatetime64(source)
# Pldt，Datetime(ms)：纪元后3毫秒／6毫秒；倍率不能丢。
```

NumPy的Y／M／W／D／h／m／s／ms／us／ns按现有真实日期合同解码，含合法倍率、非连续切片及非本机端序；不接不支持的更细单位然后暗自截尾。默认单位沿C02与实际来源精度：date／Date／原s及更粗日期映射ms；Python datetime是us；已有ms／us／ns保来源，fromdate虽清时钟仍保已声明来源单位；混合取共同单位。明确unit按最终实际结果无损／容量检查，不自动升降或转null。零／负／宽年共用整数日历，在真实unit和地区后端容量内保留；不先构建Pydt／datetime卡在1—9999。

明确来源dtype即使空／全null也保单位及按方法保留／清除的区；标量aware且size=0保来源区元数据但无数据输出。fromdate空源仍清源区、用明确目标；无单位／区信息的普通空集合或全缺失沿C02映射ms及naive，不照搬E02数值工厂默认us。原NaT来源按自己的哨兵读取；Polars真实有效i64最小值及独立null按C04保留，不能将Pddt当前的哨兵缓冲原样用于PLDT或误掉合法数据。

**四、Series／Expr用真实Date／Datetime；NumPy专用工厂只在立即边界提供。**

|入口|建议模式与输出|默认schema|
|---|---|---|
|Pldt.fromdate／Pldt.fromdatetime|真实日期标量配size，或合法一维立即来源；返回Pldt|按上述来源选择单位和输出区|
|s.pldt.fromdate|Date／Datetime原生Series及其它已准入立即日期来源；返回Pldt|Date→ms，Datetime保单位；无目标输出naive|
|s.pldt.fromdatetime|Datetime原生Series及其它已准入立即datetime来源；返回Pldt|保单位，tz=None保来源区，明确tz替换|
|pl.col(...).pldt.fromdate|Date／Datetime或明确Null缺失schema；返回原生pl.Expr|Date→ms，Datetime保单位；目标区或naive，事前已知|
|pl.col(...).pldt.fromdatetime|Datetime或明确Null缺失schema；返回原生pl.Expr|保来源单位／源区，明确unit／tz优先；Null无来源单位默认ms|
|Pldt.fromdatetime64|仅接真实NumPy日期标量／合法一维来源，立即返回Pldt|读真实NumPy单位并直接映射目标|

不要求这些Date／Datetime Expr都显式unit，因为schema足以推导；明确unit仍提前成为目标，运行期检查真实精度／容量，空batch不改dtype。Expr真实Object未知元素不在worker调用Python判断日期，先通过合法立即入口准备为原生日期列；不通过String／Int64 cast冒充真实日期来源。两种fromdate／fromdatetime在立即eager阶段可以按B规则读取合法Python日期集合，与原生Expr的typed合同区分。

**已确认的接口收敛：**不为Polars Series／Expr新增.pldt.fromdatetime64()。Polars原生dtype只记录Date／Datetime和unit／zone，不记录它是否曾来自NumPy；先构造Polars列后使用fromdatetime。将其传给fromdatetime64会与Pddt真实NumPy专用边界冲突，不能为了目录平行加别名／接受伪NumPy来源。输入NumPy直接用Pldt.fromdatetime64；若要参与Lazy计划，合法日期列可用pl.lit，或先作为DataFrame日期列，均保原生ns，不经过Python单元素提取。旧导航“fromdatetime64一律Series+Expr、所有Expr必须unit”的冲突草案已直接替换，不保留相反活跃合同。

```python
s = pl.Series("time", [1_234_567_891, None], dtype=pl.Datetime("ns", "UTC"))
x = s.pldt.fromdatetime()
# Pldt，Datetime(ns, UTC)，刻度1_234_567_891／null。
expr = pl.col("time").pldt.fromdatetime()
# pl.Expr，输出仍为Datetime(ns, UTC)，无需重复unit／tz。
expr = pl.col("time").pldt.fromdatetime(tz="Asia/Shanghai")
# pl.Expr，保源UTC钟表并重新附上海区；不是转换显示区。
result = pl.DataFrame({"time": s}).lazy().select(expr).collect()
# pl.DataFrame；time是普通pl.Series[Datetime(ns, Asia/Shanghai)]。

s = pl.Series("day", [date(2024, 1, 2), None], dtype=pl.Date)
x = s.pldt.fromdate()
# Pldt，Datetime(ms)：2024-01-02午夜／null。
expr = pl.col("day").pldt.fromdate(tz="UTC")
# pl.Expr，输出Datetime(ms, UTC)。

Pldt.fromdatetime(date(2024, 1, 2), size=1)  # TypeError，使用fromdate。
Pldt.fromdatetime64(s)  # TypeError，s是Polars列，不是真实NumPy来源。
Pldt.fromdate("2024-01-02", size=1)  # TypeError，普通文本用parse。
```

**与Pddt／Pydt的区别：**取YMD、完整钟表／区替换、NumPy解码附区均参考两已采用类；Pydt是标量／us／1—9999且其NumPy出口按既定截取，Pddt和Pldt保真实ns及列容量，不能为统一仿照Pydt截us。Pddt输出Index／NaT，Pldt输出Series／null，仅ms／us／ns且提供适用原生Expr；NumPy工厂职责不因其容器是Polars就放宽，Pddt本来也拒Polars输入到fromdatetime64。PLDT还必须保护C04完整int64和有效位，不能照用NaT打包器。

**性能影响与实现建议：**无目标／无单位变化的合法Datetime列优先安全共享原生数据及元数据、保owner，最终只建一次Pldt外壳；不是所有情况都承诺零复制。fromdate需取当地日期并归午夜，重新附地区、换单位或处理真实子类时做必要计算；Naive／UTC快路不做地区候选。NumPy直接typed缓冲解码，必要端序／stride处理不绕Python datetime；Python真实来源在边界读取实际协议，worker不调用这些对象。不先造Pydt／Pddt／中间Pldt再转换，不为固定schema额外扫列。共享最小日历／单位／时区职责，输出适配独立；D01.O1—O4的既有性能／协议保护继续适用。PLDT未实现，未测倍率，不能承诺一定较Pddt或原生更快。

**验收要求：**分别对三个入口覆盖合法／拒绝来源、标量size与列形状、真实子类协议、null与i64最小值、单位默认与无损／溢出、ns／NumPy倍率／端序／切片、零／宽年、来源当地日历、保时刻与保钟表的对照、fold已知时刻及显式同区重解释、空／全null元数据；Expr验证schema／分块一致，无Object回调和隐式collect，输出类型及父子类协议按A/L。复用当前42观察作输入线索，最终答案来自本项确认及独立整数预期，不直接把现行Pddt误差当标准。

<a id="pldt-e04"></a>

### E04 fromordinal/fromisocalendar/fromdayofyear及combine

**本项职责与状态：**三个整数日历工厂复用Pydt／Pddt已采用的公历／ISO／便利上限规则；combine复用日期与时钟的独立角色及Pddt整列策略。原生标量／列准备、Polars Series／Expr与输出schema分开。本项已完整确认，尚未实现或采正式性能。

**一、整数日历工厂：保共同数学，输出各自容量的午夜日期。**

|入口／字段|规则与含义|拟议输出|
|---|---|---|
|fromordinal(ordinal)|连续公历日坐标，1为0001-01-01，0为0000-12-31，负数继续向前；不作低位／高位收口|Pldt，默认Datetime(us)，午夜|
|fromisocalendar(year,week,weekday)|ISO年／周／星期；week和weekday小于1报ValueError，高week取该ISO年的实际末周，高weekday取7／周日|Pldt，默认Datetime(us)，午夜|
|fromdayofyear(year,doy)|年与年内第几天；doy小于1报ValueError，高于365／366取该年末日|Pldt，默认Datetime(us)，午夜|

```python
# 本项所有Pldt／.pldt示例均为待实施设计。
x = Pldt.fromordinal([1, 0, -1])
# Pldt，Datetime(us)：0001-01-01、0000-12-31、0000-12-30，均午夜。
x = Pldt.fromisocalendar([2020, 2021], 53, 7)
# Pldt，Datetime(us)：2021-01-03、2022-01-02。
# 2020有53周，2021仅52周；合法ISO跨公历年不能再裁回12月31日。
x = Pldt.fromdayofyear([2023, 2024], 366)
# Pldt，Datetime(us)：2023-12-31、2024-12-31。
x = Pldt.fromdayofyear([2023, 2024], 60)
# Pldt，Datetime(us)：2023-03-01、2024-02-29。
```

ISO weekday是1—7，与自有普通weekday的0—6角色区分；本项的高位便利调整不能推广到普通weekday选择或其它严格字段。year保真实零／负／宽年，不截成1／9999；共同整数日历不经Python日期对象。Pydt最终仍受1—9999容量，Pddt／Pldt按单位和必要地区能力输出。默认us是这三个工厂的明确合同，空／全缺失仍us，不套普通Pldt([])的ms默认。

输入使用真实整数／__index__协议，拒bool、float含1.0、普通数字文本及只实现__int__的对象。合法明确日期缺失沿B04构成null行，不表示今天／保留旧值；必填参数省略仍按签名拒绝。数值0在ordinal和year有真实含义，但week／weekday／doy的0非法。缺失不吞其它已提供的非法数值，如year=[None],doy=[0]仍失败。

```python
Pldt.fromisocalendar(2024, 0, 1, size=1)  # ValueError，week至少1。
Pldt.fromisocalendar(2024, 1, 0, size=1)  # ValueError，ISO weekday至少1。
Pldt.fromdayofyear(2024, 0, size=1)       # ValueError，doy至少1。
Pldt.fromordinal(1.0, size=1)            # TypeError，不能截成1。
Pldt.fromordinal(True, size=1)           # TypeError，bool不作日数。
x = Pldt.fromdayofyear([2024, None], [60, 1])
# Pldt，Datetime(us)：2024-02-29午夜／null。
```

明确tz附到计算出的当地午夜，保所需ambiguous／nonexistent默认raise；午夜本身也可能重复或不存在，不能假设零时永远安全。无区／UTC／可表达固定偏移直接计算，地区后端和策略完整能力见H。明确unit只接ms／us／ns，并按真实结果无损／容量检查，不能因2500年选ns失败自动降us；中间计算checked，不统一先缩成int64 ns。

**二、标量／列共用B02，不新增长度1广播。**

全标量须size，存在列则省略size；标量广播到共同列长，多列严格等长并按位置配对，长度1列不作标量。合法一维来源沿B01／B03；来源协议和一次性迭代器按C07在入口读取一次，标量无需展开为N个Python对象。空列仍校验明确选项／非法标量，非法普通值不因结果可能全null而忽略。

```python
x = Pldt.fromdayofyear(2024, [1, 60, 366])
# Pldt，Datetime(us)：2024-01-01、2024-02-29、2024-12-31。
x = Pldt.fromisocalendar(2024, 1, 1, size=2)
# Pldt，两行相同的2024-01-01午夜。
Pldt.fromisocalendar([2024], [1, 2], 1)
# 长度不等，ValueError；[2024]不是标量。
```

**三、combine：date供YMD，time供钟表与来源区，最后一次组装。**

立即接口保共同职责，接口形式如下，不传Expr给立即工厂：

```text
Pldt.combine(date=None, time=None, *, size=None, tz=None, unit=None,
             name=None, ambiguous="raise", nonexistent="raise")
```

- date提供当地YMD，忽略它的钟表、小数和时区；time提供时钟、小数和来源时区，忽略其日期。
- time／datetime／Timestamp及真实子类、匹配原生Date／Datetime／Time、NumPy日期、共享Parser可接受的相应文本／数值等角色，沿当前Pydt／Pddt已有来源合同，不误套E03三个专用工厂的严格来源边界。time对象及Polars Time只放在time角色，不能作date。数值是已有Parser的秒数角色，不能因unit="ms"重新解释为毫秒。
- 普通文本沿共享默认词表／语法，time文本需要的基准日期在字段层使用既定1970-01-01；不新增combine专用cfg／default／顺序／strict参数。文本中实际出现的日期片段仍按共享规则校验，不为只取时钟删除其验证。自定义词表可先显式parse准备。
- tz=None保time来源区；明确tz替换其时区并保钟表，不按原时刻转换。date来源区始终不继承；明确传入datetime日期的tz也不因此生效。
- 新组装结果按列级ambiguous／nonexistent解释，time.fold／default.fold不覆盖；Pydt标量combine继续保自身fold职责。不新增整列fold参数。

```python
x = Pldt.combine(
    [date(2024, 1, 2), date(2024, 1, 3)],
    time(12, 30),
)
# Pldt，Datetime(us)：2024-01-02 12:30、2024-01-03 12:30。

clock = pd.Timestamp("2000-05-07 12:34:56.123456789", tz="Asia/Shanghai")
x = Pldt.combine(date(2024, 1, 2), clock, size=1)
# Pldt，Datetime(ns, Asia/Shanghai)：2024-01-02 12:34:56.123456789+08:00。
# 使用date的2024-01-02，不用clock的2000-05-07。
x = Pldt.combine(date(2024, 1, 2), clock, size=1, tz="UTC")
# Pldt，Datetime(ns, UTC)：2024-01-02 12:34:56.123456789+00:00。
# 保12:34，不变成04:34。
```

**四、combine的默认／缺失和精度明确区分。**

|输入角色|含义|
|---|---|
|标量date省略／None|取系统当地今天的YMD；不是目标tz的今天，不调用完整Pldt.today再反读|
|标量time省略／None|午夜零时钟|
|date或time列中的None／合法缺失|对应行null，不补今天／午夜|
|其它明确日期缺失标量|缺失，不伪装省略None的默认职责|

立即combine在首次需要实际结果日期时取一次当地今天，各有效行复用；空列／全缺失时钟不取钟、不加载无关local。这个“今天的日期片段”不改变E01已确认today()保完整当前时钟的含义。全标量仍须size，混合标量／列沿B02；给合法日期列配time=None生成午夜，给time=[None]则生成缺失行。

```python
x = Pldt.combine([date(2024, 1, 2), date(2024, 1, 3)], None)
# Pldt，Datetime(us)：两天各自午夜。
x = Pldt.combine([date(2024, 1, 2), date(2024, 1, 3)], [None, time(12)])
# Pldt，Datetime(us)：null、2024-01-03 12:00。
x = Pldt.combine(None, [time(12), time(13)])
# Pldt，Datetime(us)：调用时系统当地今天的12:00和13:00。
```

combine默认至少us，有实际非零ns尾数初次选ns；明确unit必须无损，不能仿照Polars原生combine默认us截掉输入尾数。日期来源自身带ns时钟会被丢弃，不单凭date dtype把结果选ns；time的ns单位但尾数全零时，当前Pddt默认us，PLDT保此角色规则。空结果的合法已准备标量时钟仍能给出真实ns／区；明确目标区始终优先。容量不足报OverflowError，无实际精度损失才允许显式较粗单位，不能自动换单位／变null。

```python
clocks = pl.Series("clock", [123_456_789, None], dtype=pl.Int64).cast(pl.Time)
x = Pldt.combine(date(1970, 1, 1), clocks)
# Pldt，Datetime(ns)，有效刻度123456789／null。
Pldt.combine(date(1970, 1, 1), clocks, unit="us")
# ValueError，非零789ns尾数不能无损保留。
```

Polars Time的完整ns／null／chunk／owner直接在Rust侧处理，不逐行导出Python time后损失后三位；来源内部值必须在一天范围内，不能将损坏值解释成日期进位。原生独立Time不因此进入普通Pldt构造或普通Parser。

**五、Series／Expr采用原生调用形式，日历Expr可直接默认us。**

|工厂|Series命名空间|Expr命名空间与输出|
|---|---|---|
|fromordinal|ordinal_series.pldt.fromordinal(...)→Pldt|pl.col("ordinal").pldt.fromordinal(...)→pl.Expr|
|fromisocalendar|year_series.pldt.fromisocalendar(week,weekday,...)→Pldt|pl.col("year").pldt.fromisocalendar(week,weekday,...)→pl.Expr|
|fromdayofyear|year_series.pldt.fromdayofyear(doy,...)→Pldt|pl.col("year").pldt.fromdayofyear(doy,...)→pl.Expr|
|combine|date_series.pldt.combine(time,...)→Pldt|date_expr.pldt.combine(time,...)→pl.Expr|

三个整数日历Expr有固定方法默认us，不一律要求unit；明确unit／目标区则提前决定schema，非法dtype／bool／浮点不能靠cast截为整数。真实值的范围／容量错误在执行时按N的异常映射处理。整列参数可用对应Expr按位置计算，不按行调用Python工厂；原生literal与明确集合依已确认B02及M的形状职责，不用长度1数据列冒充标量。

```python
expr = pl.col("year").pldt.fromdayofyear(pl.col("doy"))
# pl.Expr，输出Datetime(us)，无需重复unit。
result = pl.DataFrame({"year": [2023, 2024], "doy": [60, 60]}).lazy().select(
    expr.alias("time")
).collect()
# pl.DataFrame；time为普通pl.Series[Datetime(us)]，2023-03-01／2024-02-29。

expr = pl.col("day").pldt.combine(pl.col("clock"), unit="ns")
# day为Date，clock为Time：原生pl.Expr，输出Datetime(ns)，保实际ns和null。
```

combine Expr沿Polars“接收者提供日期，参数提供时钟”的常规用法，但自有精度／时区规则仍由本库实现，不直接转发整个.dt.combine。可由方法／输入schema／已准备的合法标量决定的默认不要求unit；真正依赖未来行值的情况要求明确unit：

|时钟来源|combine Expr省略unit|
|---|---|
|省略／Python None、合法已准备的time／日期时钟标量、纯Null缺失|可直接推导：一般us，已准备标量确有ns尾数则ns|
|可证明无亚微秒的合法原生clock来源，如Datetime(ms/us)、Date、整数秒角色|默认us|
|Polars Time／Datetime(ns)／String／浮点秒等未来数据可能有真实ns尾数|要求显式ms／us／ns；未知／不支持的dtype不靠第一行猜测|

同一Time dtype内可能全是微秒对齐值，也可能有非零ns，当前Pddt默认分别为us／ns；不能偷偷把全部Time默认ns来缩窄宽日期，也不能默认us静默截取，且不隐式扫描／collect选schema。日期来源自己的小数与时区被丢弃，不制造无关的单位／区要求。String clock没有明确目标时仅规划naive，若实际识别出来源区则执行时报错并提示目标；明确tz先按clock来源含义取字段，再按combine保钟表附目标，与D03转换真实瞬间的普通parse分开。已知Datetime clock schema可保其区，明确tz覆盖，工作线程不调用Python来源对象；默认词表和标量文本准备沿D02快照。

**已确认的Expr默认日期职责：**.pldt.combine以接收者作为date，不另设省略date并隐式取今天的Expr入口。想将今天配一列时钟时，由用户明确建立日期literal；它按建立时的值固定，不因collect／分组／chunk重新取钟。不混用Pldt.combine(date=Expr)让立即工厂有时返回Pldt、有时返回Expr，也不把Null Date Expr误解为省略date。旧草案“Expr省略date时自动捕获今天”已直接替换为上述日期接收者／用户显式literal规则。

```python
day = date.today()
expr = pl.lit(day).pldt.combine(pl.col("clock"), unit="ns")
# pl.Expr：day是用户明确捕获的日期，之后collect仍使用该日。
expr = pl.col("day").pldt.combine(time=None)
# pl.Expr：各有效day配午夜，默认Datetime(us)。
expr = pl.col("day").pldt.combine(pl.lit(None, dtype=pl.Time))
# pl.Expr：显式缺失时钟，输出null，不等同上一个None默认。
```

**六、Pddt元数据差异与已确认的同步修正范围。**

当前Pddt.combine接收Datetime(ns,UTC)原生时钟列为空／全缺失时，结果默认us但tz变None；相同UTC标量时钟配空日期列能保UTC。此差异已在两环境实际复现，不是PLDT设计推测。

```python
clocks = pl.Series("clock", [], dtype=pl.Datetime("ns", "UTC"))
x = Pddt.combine(date(2024, 1, 2), clocks)
# 当前实际：Pddt，unit="us"，tz=None，0行。
# 建议：仍unit="us"，但保已知UTC；全null原生clock同理。
```

PLDT即使空／全null，也从明确的原生clock元数据保可表达时区；明确目标优先，date源区仍忽略，无区信息的普通缺失集合不猜区。单位仍沿combine实际精度合同，保UTC不等于把默认强改ns。与已确认B04／C02一致，并避免eager与Expr仅因有没有有效行而丢schema。本次实施须**同步修正Pddt.combine这一处元数据分支**，作为E04相关共享修改单列验收；不是顺手扩全库优化。其余正常日期、数值语义、策略和默认单位保持，已批准纳入后续实施范围，尚未实施。

**与Pddt／Pydt的关系：**整数协议、ISO／年内日高位便利规则、combine角色／默认和日期含义均以现行Pydt／Pddt为依据；Pydt标量、us、1—9999和自身fold保留，Pddt／Pldt可列计算、真ns及更宽年月。Pddt是Index／NaT、支持s-ms-us-ns；PLDT为Series／null、仅ms-us-ns，另有适用Expr及schema差异；当前空／全缺失原生clock时区差异按上一节明确处理，不写成所有结果已相同。

**性能建议与影响：**共享最小整数日历与date／clock字段合并函数，标量／选项循环外一次准备，合法原生列直接typed读取及有效位处理；不先造临时Pydt／Pddt／Pldt再提字段，不逐行调用公开工厂，最终只构造一次目标Pldt或原生Expr执行结果。calendar只做所需公历数学和checked单位输出；combine融合读取／合并／最终检查，Time保ns且只处理必要地区候选，naive／UTC直接路线。今天仅真实需要时一次取值，Expr不增加时钟上下文／扫描；元数据修正只需已知资料及空／缺失分支，不额外全列扫描。D01及O1—O4现有库保护持续适用。PLDT未实现，未采正式性能，不承诺倍率或所有路径零开销；Pddt同步小修需按最终同产物保护验证。

**验收要求：**独立整数／已确认日期答案逐类核对ordinal0／负值、ISO跨年／52-53周、week／weekday／doy低错高收、闰年、零／宽年、ns容量、bool／float拒绝、一次__index__／迭代、标量／列配对和null不隐藏非法值；combine覆盖YMD／时钟／源区分工、显式目标保钟表、None默认与列null、真实ns／Time chunks／所有权、默认us/ns与显式无损、一次取今天／空零次、fold不覆盖列策略以及空／全nullclock区元数据。Expr检验三个日历默认us、combine需要unit的确切集合、固定schema／null／native literal、日期接收者、无隐式collect及无工作线程Python协议；原生错误类按N，地区策略按H。共享小修及PLDT各有最终产物测试，不用当前112+12参考观察冒称新实现验收。

<a id="pldt-e05"></a>

### E05 fromisoformat和date_range

**已确认职责与状态：**E04已完整确认，Pddt.combine原生空／全缺失时钟来源区修正已纳入后续实施；本项已完整确认，尚未修改产品。fromisoformat复用Pydt／Pddt已有专用严格ISO语法，保数组ns及宽正年／零年能力；建议Pddt／Pldt同步增加可选目标tz及必要地区策略，Pydt不增加。date_range保Pddt共同范围合同，立即输出Pldt；普通／静态规则用共享Rust生成，建议仅真正特殊规则允许可选pandas明确委托，不令普通PLDT依赖pandas。

**当前源码与真实核查：**Pddt最终决定P07.7／P09／P10；rust/parser/iso_factory.rs完整扫描ISO，无普通语法回退；src/rstimes/pddt.py:fromisoformat当前没有目标tz，但其共用_from_dates／原生最终器已有目标与策略槽。date_range生成已有Rust Frequency／整数日历／等分，src/rstimes/_range.py已拥有3.x字符串词汇及部分词法，但仍经pandas Offset资料准备，不能直接声称整条PLDT已无pandas。两代表环境各57观察，结果一致；三个环境各6个既有原生边界观察，结果也一致，共132观察，含预期拒绝。public-core确实无pandas／Polars，现有Rust月末／固定ns生成及ISO目标最终器仍可运行；它证明内核能力，不证明PLDT入口／新频率准备／插件已实现。二进制身份和原始输出见本项证据，不采正式性能。

**一、fromisoformat保专用语法和严格字段，不改成普通parse。**

真实来源仅合法ISO文本标量／一维集合及准入的明确日期缺失；普通日期对象、数字和普通非ISO文字不因可parse而接受。标量须size，集合不同时给size；真子类和一维规则沿A/B。保Pydt已有的日历／基本／ISO周日期、单字符日期时间分隔和数字时区偏移，保Pddt年内日文本扩展；零年及宽正年由共享内核／单位容量处理，不新增普通负年ISO文本语法。

|文本|建议行为|来源依据|
|---|---|---|
|2024-01-02／20240102|1月2日午夜|Pydt／Pddt共同|
|2020-W53-7|2021-01-03午夜|Pydt／Pddt共同|
|2024-002|2024-01-02午夜|Pddt年内日扩展|
|2024-01-02x12:30|2024-01-02 12:30|已有单字符分隔合同|
|2024-02-30／2021-W53-7／2023-366|报错，绝不按E04高位便利规则收口|专用文本字段必须有效|
|Jan 2 2024／合法ISO后有杂字|报错，不切到普通Parser求成功|专用完整匹配|

```python
# 所有Pldt／.pldt示例为设计，尚未实现。
x = Pldt.fromisoformat("2024-002", size=1)
# Pldt，Datetime(us)：2024-01-02 00:00:00。
x = Pldt.fromisoformat("2020-W53-7", size=1)
# Pldt，Datetime(us)：2021-01-03 00:00:00。
Pldt.fromisoformat("2021-W53-7", size=1)
# ValueError：2021没有第53周，不取末周。
Pldt.fromisoformat("2024-02-30", size=1)  # ValueError，不截到2月29日。
```

不增加strict／cfg／default／顺序／格式猜测等通用Parser参数；严格ISO不读取自定义月份词表，不因cfg登记过就接受IANA尾缀。目标tz参数属于输出解释／转换，不是扩张ISO文本语法。既有12:30.5为12:30:00.500000而非半分钟，保持专用合同；datetime当前版本细节变化不自动更改本库已采用解释。

小数完整扫描：最多6位来源默认us，超过6位默认ns，包括额外三位全零；超9位沿当前专用ISO截取至9位，不四舍五入，不能误当未消费文本。显式unit仍要求保存所得真实ns；不同于strptime主动选择输出精度。Pydt最终仍us／自身容量，不因共享增加ns返回。无有效日期／无来源精度的空／全缺失ISO集合，当前Pddt实际默认s，PLDT沿C01/C02映射ms；不是误写成所有ISO空集合默认us。明确unit优先，null不吞普通解析失败。

```python
x = Pldt.fromisoformat("2024-01-02T12:30:00.123456789", size=1)
# Pldt，Datetime(ns)，保.123456789。
Pldt.fromisoformat("2024-01-02T12:30:00.123456789", size=1, unit="us")
# ValueError，不能无损保存。
x = Pldt.fromisoformat(["2024-01-02", None, "NaT"])
# Pldt，Datetime(us)，有效日期／null／null。
x = Pldt.fromisoformat([])
# Pldt，Datetime(ms)，0行；无日期精度信息的空来源按C02。
```

**二、推荐Pddt／Pldt同步增加可选目标tz和必要地区策略（已确认的共享接口修改）。**

```text
Pddt.fromisoformat(dtstr, *, size=None, tz=None, unit=None, name=None,
                  ambiguous="raise", nonexistent="raise")
Pldt.fromisoformat(dtstr, *, size=None, tz=None, unit=None, name=None,
                  ambiguous="raise", nonexistent="raise")
```

本项独立确认此扩展，D04 strptime修改和本项分别验收。当前Pddt混合+08:00／Z会提示传目标tz，但传tz又因不支持关键字而TypeError；同步补充可以解决真实用例，并让两列类保持一致。旧省略调用保原含义，Pydt.fromisoformat继续当前标量接口，不加目标／列策略。

- 省略／None目标：保可形成一列的来源区；naive仍naive，混合区或naive／aware混合照原规则失败，不猜第一行／自动UTC。
- 明确目标：带偏移ISO先保真实时刻，再转目标显示区；naive按目标当地字段解释。不是fromdatetime保钟表替换的含义。
- 新附地区的naive需要数组策略，默认raise；已有明确偏移的时间点不重新本地化。策略类型／完整能力见H，不扩strict或丢失fold概念到此入口。
- PLDT只能输出Polars可表达的区；不能原样表示的来源偏移须明确目标区或按H01报错，不擅自丢区／换UTC／挑相似地区。当前两版Polars实测+08:00可规范为Etc/GMT-8，但+05:30拒绝；不能笼统写成所有固定偏移均支持或均拒绝。精确可接受映射在H01确认，不在本项预定实现。

```python
x = Pldt.fromisoformat(
    ["2024-01-02T12:30+08:00", "2024-01-02T04:30Z"],
    tz="UTC",
)
# Pldt，Datetime(us, UTC)：两行均2024-01-02 04:30+00:00。
# 拟新增Pddt同样调用返回Pddt，数值含义相同。
x = Pldt.fromisoformat("2024-01-02T12:30+05:30", size=1, tz="UTC")
# Pldt，Datetime(us, UTC)：2024-01-02 07:00+00:00。
```

已有原生ISO最终器已实测可完成混合偏移统一UTC、naive目标附区、缺失地区报错及显式shift策略；这里只验证内部能力，当前公开Pddt还没有上述新参数。未来应接现有最终器、一次输出，不先造无法容纳混合区的Pddt再tz_convert。

**三、fromisoformat的Series／Expr模式和schema。**

立即Pldt工厂／Series命名空间返回Pldt；Expr经.pldt.fromisoformat直接返回原生Expr。普通String schema仍不知道实际小数宽度，需明确unit，即使未来空／全null也不换合同；有明确Null缺失而无日期精度时按C02默认ms。单位／区在规划时固定，不抽样／预扫／collect来选dtype，不把非法Date／Int64列转文本冒充ISO来源。

```python
s = pl.Series("text", ["2024-01-02T12:30:00.123456789", None])
x = s.pldt.fromisoformat()
# Pldt，Datetime(ns)，立即可按来源选择精度。
expr = pl.col("text").pldt.fromisoformat(unit="ns")
# pl.Expr；无目标只规划naive，遇带区文本报错提示明确目标。
expr = pl.col("text").pldt.fromisoformat(unit="ns", tz="UTC")
# pl.Expr，输出Datetime(ns, UTC)，含偏移与naive各按前述职责。
```

没有目标的String Expr不按第一行猜区，即使所有实际输入都为Z也不静默把schema从naive改UTC；有来源区需要目标，立即入口仍可推导来源。这与D03已确认通用文本的区规划一致，专用ISO只改变语法。Expr实际错误类映射留N；地区能力按H，不宣称当前原生插件已验证。

**四、date_range保Pddt共同接口，为立即生成工厂。**

```text
Pldt.date_range(start=None, *, end=None, periods=None, freq=None, tz=None,
                normalize=False, inclusive="both", unit=None, name=None,
                default=None, yearfirst=None, dayfirst=None,
                isoformat=True, strict=False, cfg=None,
                ambiguous="raise", nonexistent="raise")
```

仅start可首位置，其余关键字；输入为标量端点，不按列逐行生成List，不把DataFrame／Expr端点隐式collect。periods为非负整数协议，拒bool／float，0合法；不是size。明确freq时start／end／periods恰有两个；freq=None且三者全给为等分，否则按D默认再检查合法组合。无端点缺失NaT／非法文本吞错，None端点表示未提供。

```python
x = Pldt.date_range("2024-01-01", periods=3)
# Pldt，Datetime(us)：1月1日、2日、3日午夜。
x = Pldt.date_range("2024-01-15", periods=3, freq="ME")
# Pldt，Datetime(us)：1月31日、2月29日、3月31日午夜。
x = Pldt.date_range("2024-01-01", end="2024-01-05", periods=3)
# Pldt，Datetime(us)：1月1日、3日、5日；Rust整数等分。
x = Pldt.date_range(0, end=5, periods=4, unit="ns")
# Pldt，Datetime(ns)，刻度[0,1,3,5]；反向为[5,3,1,0]。
```

端点字符串统一本库Parser及cfg／default／顺序／strict；非文本按真实来源读取，不调用pandas猜文本。default独立完整／实际需要时准备一次，显式False优先级保持；原生端点不解析无关default。裸数字端点按unit刻度，未指定时按ns，不同于E02秒数工厂。单位按端点来源和频率声明需要选择，s来源映射ms，500ns等须ns；不把全部范围强制ns／us。显式单位无损／容量，所有所给端点都须检查，即使periods=0、inclusive排除、频率滚动后不输出该端点。normalize=True先有意归当地午夜，再按最终值检查；strict=False不放松生成精度和容量。

inclusive保持both／left／right／neither；反向用负频率／反向等分，不交换端点／排序求成功。等分沿既定整数格点向更早刻度，不经float；periods0／1、同端点和边界删减沿Pddt基准。地区D是日历日，24h／timedelta是实际时长，不能合并语义：纽约2024-03-09 12:00起三点，D为每天12:00，24h为12:00／13:00／13:00。必要DST默认raise，布尔mask按inclusive删减前完整生成序列对应；细策略H，不能因是范围就换Polars较窄语义或逐点Python日期。

**五、普通／静态频率走Rust，准备过程也去除无必要pandas中转。**

|首版复用的原生规则|范围与例子|
|---|---|
|固定实际时长|ns/us/ms/s/min/h及合法倍数／小数／组合／反向；timedelta与适用Timedelta，例如500ns、15min、1h30min|
|日历日／周|D／W／W-MON至W-SUN及倍数／反向；W默认周日|
|月／季／年边界|MS/ME、QS/QE、YS/YE及标准月份锚点和倍数|
|普通工作日及边界|B、BMS/BME、BQS/BQE、BYS/BYE及已支持标准锚点|
|静态自定义工作日|C／CBMS／CBME等已有字符串默认规则；实际标准CustomBusinessDay／CustomBusinessMonth类完整导入weekmask／固定holidays／offset等已有参数|
|半月／位置星期|SMS/SME及已支持日锚点，WOM-2MON、LWOM-FRI等|
|整数等分|freq=None且给start／end／periods|
|等价真实标准Offset实例|只对真实受支持类型，完整读取影响参数后进入同一原生计划|

现有_range.py已维护3.x词汇，不是普通字符串全部交pandas.to_offset；但仍构建Offset中间资料并依赖pd。建议把普通字符串直接准备为共享原生Frequency计划，固定小词汇／精确十进制解析与日历生成分工，不先new pandas Offset再拆字段。可复用当前规则和Rust生成算法，不复制另一套Polars interval语法，也不为PLDT强制安装pandas。实际Offset仅在可选pandas可用且用户真提供时从真实类型／完整参数适配；仅导入静态规则不等于让pandas生成日期。真自定义子类不能降格成标准类型快路。

这一步是新共享边界准备，不写成现成整个接口只需换输出容器。现有Pddt需保真正freq元数据和外部协议，初期可保其现行准备适配并共用原生计划，不为PLDT开发硬改无关Pddt热路；有安全／可维护收益的共同准备在后续实施中复用并做保护。PLDT不伪造Polars原生没有的Index／freq元数据；可确定名称沿Polars出口，L01继续具体元数据合同。

不恢复m／M／H／T等本库已经拒绝的旧别名；分钟min、月末ME。Polars原生datetime_range使用interval／closed／time_unit且没有periods；Pldt.date_range服务Pddt平行的范围职责，保freq／inclusive／unit，不机械改名或把ME偷译为1mo。原生pl.datetime_range及其Expr行为保持，用户仍可直接使用，不包装全部Polars范围函数。

**六、特殊规则采用已确认的可选pandas委托方案A。**

**确定委托范围：**仅在原P09.3已明确的真实成熟执行边界，且可选pandas存在时委托：真实自定义DateOffset／回调、带额外语义的通用DateOffset组合、BusinessHour／CustomBusinessHour、特殊52/53周财年、不能完整冻结的动态业务日历。普通规则／静态资料不因此回退；安装pandas也不改变本来Rust规则的引擎选择。无pandas且用户明确请求这种能力，给说明所需依赖的ImportError；普通PLDT功能不需要pandas。

```python
x = Pldt.date_range("2024-01-01 09:00", periods=3, freq="bh")
# 已装pandas时走明确成熟执行器，返回Pldt，时间09:00／10:00／11:00。
# 未装pandas时明确ImportError；普通freq="D"／"ME"仍可用。
```

外部执行器只接本库已解释的端点和原规则，不重新猜文本；保真实回调、参数及原异常，不在包装外虚构额外限制。当前Pddt已有这种路径，PLDT做薄出口适配，直接接其native刻度／单位／区／缺失并checked生成Pldt，不先创建Pddt／逐行Timestamp或tolist。pandas返回的必要DatetimeIndex是成熟执行器真实输出，不能伪称整个特殊路线零外部容器；普通原生路线仍只构造最终Pldt。

**七、date_range首版只提供立即Pldt工厂，进入Lazy用原生literal。**

返回Pldt；需要放入DataFrame／LazyFrame可明确用结果Series或pl.lit(x)，不提供返回类型随参数变动的Pldt／Expr工厂，不增加.pldt.date_range逐行List范围／隐式collect。Polars原生pl.datetime_range本就能返回Expr，保留原入口；本库首版新增范围强调共同periods／频率／容量／Parser合同。

```python
x = Pldt.date_range("2024-01-01", periods=3, freq="D")
expr = pl.lit(x)
# x：Pldt；expr：原生pl.Expr，保已生成列和真实ns／null，不重新生成范围。
result = pl.LazyFrame().select(expr.alias("time")).collect()
# pl.DataFrame；time为普通pl.Series[Datetime(us)]。
```

**Pddt／Pldt使用与可观察行为的已确认对照。**比较对象是“按E05推荐修改后的Pddt”与“拟实现Pldt”，不能把当前Pddt缺少tz参数说成两类最终设计差异。此表与H／L／N完整合同一起执行。

|方面|按推荐完成的Pddt|拟实现Pldt|性质|
|---|---|---|---|
|共同日期含义|严格ISO、范围／频率／整数等分、端点解释、显式无损|共同可表达范围内保持相同预期|共同合同，不是已实现一致性证明|
|工厂参数|ISO拟增加tz及必要策略；date_range保现有参数|相同职责和关键字；合法单位等实际能力分开|拟同步，不保留仅Pldt有目标的推荐|
|输出／缺失|Pddt／DatetimeIndex，NaT|Pldt／Series，null|已定容器差异；完整int64／独立有效位按C04|
|单位|s/ms/us/ns；Date端点或无精度空ISO可默认s|ms/us/ns；对应s映射ms，显式s拒绝|C01/C02已定；日期相同不等于dtype相同|
|ISO集合外层|Mapping按键，set/frozenset按实际顺序|直接拒绝这些外层|B01已定差异，不因本项恢复|
|来源固定偏移|能保标准timezone表达的偏移，如+05:30|必须是Polars可表达的区；否则明确目标或报错|H01完整映射已定，不承诺全偏移支持；显式共同UTC后预期日期相同|
|延迟入口|两个公开工厂立即返回Pddt|ISO另有.pldt Expr，String需unit、带区需目标；范围仍立即Pldt，可literal|不能把Expr额外控制套到立即Pldt工厂|
|依赖／特殊范围|Pddt本来要求pandas，既定特殊规则可委托|普通只需Polars及默认依赖；方案A特殊规则才需可选pandas|无pandas时特殊能力明确失败，不改变普通规则引擎|
|频率和名称元数据|可有经验证的Index.freq，Index模型|不伪造pandas式freq／Index，名称按Polars模型|具体name等完整类型在L01确认，不保证任意hashable名称两边通用|

共同调用仍不是所有Python对象／类型／错误外壳完全一致：自有eager错误原则保持，Expr由Polars执行的异常类映射留N；地区策略实现／后端边界留H。不要把“共享日期算法”扩大为所有范围、时区、容器和第三方协议已经无差异，也不把暂未确认内容包装成实现完成。

**性能影响与建议：**专用ISO用借用字符串／原生UTF8小扫描器及共享最终器，不走通用词法／Pydt或先造Pddt再转区；已有Pddt旧省略调用可保持目标None快路。普通范围频率和端点各准备一次，整数／日历生成直接写原生缓冲，最终一次构造Pldt；只做必要地区处理，无区／UTC直接计算，单位验证融合，不先统一int64 ns造成假溢出。特殊委托有第三方成本和必要容器，但只在该分支；不把它计作普通原生路线的提速。D01.O1—O4保护和最小共享原则继续适用；PLDT未实现、无正式性能倍率，Pddt新增接口及共同内核改动必须回归旧正确样本和性能保护，不能宣称一定比原生Polars或Pddt快。

**验收要求：**ISO逐语法／非法字段／尾随／缺失／真来源、ns／超长小数、空单位、零／宽年、显式无损、混合偏移目标、naive目标地区／策略及旧省略调用全部覆盖，Pydt标量保持；Series输出与Expr固定schema／空／全null／带区错误明确。范围按规则家族／参数组合／periods0-1／inclusive／反向／整数等分、端点共享Parser／cfg/default、端点精度即使未输出、normalize、D与24h、单位／容量／NaT／mask完整位置、静态参数及真自定义协议逐类验证。无pandas环境验证普通字符串／timedelta全原生和特殊能力明确失败；有pandas环境验证只批准边界委托、实际回调和异常；不把内部6观察当公开PLDT已完成。最终构建／跨平台／同产物性能留M/N，不重跑旧研究当新实现。

## F 字段、日历移动与周期边界

<a id="pldt-f01"></a>

### F01 严格replace与只收合法字段意图的to_datetime/date/time

**1. 日期字段替换采用命名空间方案A，Pddt／Pldt同步。**

Polars的Series.replace(old, new)／Expr.replace(old, new)是整值替换，原生日期字段操作为.dt.replace。Pldt.replace完整继承原生整值API，日期字段统一用x.pldt.replace、s.pldt.replace及expr.pldt.replace。三个to_*没有Series直接同名冲突，Pldt保直接方法及命名空间。

Pddt同步修改：日期字段入口改为x.pddt.replace(...)，删除自有Pddt.replace的日期字段入口，不保留旧名转发或猜参数的双义分流。x.replace仅按底层pandas原生职责提供：pandas3.1起继承Index整值replace，参数／转换／返回／异常完整沿原生；pandas2.3／3.0原本无该方法，不额外补造整值replace。Pydt.replace仍为标量日期字段替换，不改名；Pddt其它方法不因本项整体迁入命名空间。本项明确Pddt实例的.pddt.replace，不额外扩成所有原生DatetimeIndex全局注册。源码／pyi／运行文档／指南／demo／有效测试及字段入口错误上下文在实施时同步；旧冻结证据及历史决定保留。

~~~python
from datetime import datetime
import polars as pl
from rstimes import Pldt

x = Pldt(["2024-01-31 12:00"], unit="us")
result = x.replace(datetime(2024, 1, 31, 12), datetime(2024, 2, 29, 12))
# 整值替换：原生pl.Series，Datetime(us)，2024-02-29 12:00。
result = x.pldt.replace(month=2, day=29)             # Pldt
result = x.to_date(month=2)                          # Pldt，同一日期值
result = x.pldt.to_date(month=2)                     # Pldt
expr = pl.col("time").pldt.replace(month=2, day=29)  # 原生pl.Expr
~~~

共同日期字段调用分别为Pddt对象x.pddt.replace(month=2)与Pldt对象x.pldt.replace(month=2)。原生整值replace不套本库字段限制、配对规则、错误包装或返回包装。两者共同日期含义及B02已确认的数值／形状规则保持；本稿早期字段replace直调示例已统一改为.pldt.replace。覆盖原生API的相反方案及待决定表述已删除，历史快照仅留证据。

~~~python
from rstimes import Pddt
x = Pddt(["2024-01-31 12:00"])
result = x.pddt.replace(month=2, day=29)  # 批准后的Pddt入口，返回Pddt
# x.replace(old, new)只在底层pandas具备该原生方法时可用；不再修改日期字段。
~~~

**2. 四个日期方法沿当前Pddt／Pydt共同含义。**

|本库日期方法|可修改内容|日历规则|Series／Expr输出|
|---|---|---|---|
|.pldt.replace|八数值字段；另有单值tzinfo、必要DST策略|全部修改合并后的真实日期必须合法|Pldt／pl.Expr，Datetime|
|to_datetime|八数值字段|合法day意图可拟合目标月末|Pldt／pl.Expr，Datetime|
|to_date|year、month、day|保时钟、微秒与ns尾数；合法day可拟合月底|Pldt／pl.Expr，Datetime|
|to_time|hour、minute、second、microsecond、nanosecond|保原日期，不能把非法小时等夹成合法值|Pldt／pl.Expr，Datetime|

to_*均非字段提取、Python对象导出或类型转换；原生.dt.date()／.dt.time()仍分别提取Date／Time。本项作用于已准备的Datetime源，不新增隐式文本解析路径；Date／文本来源用已确认fromdate／parse等入口。

~~~python
x = Pldt(["2024-01-31 12:34:56.123456789", None], unit="ns")
x.pldt.replace(month=2)           # ValueError：2月没有31日
x.pldt.replace(month=2, day=29)   # Pldt：[2024-02-29 12:34:56.123456789, null]
x.to_date(month=2)                # Pldt，同上，时钟及完整小数保留
x.to_datetime(month=2, hour=0)     # Pldt：[2024-02-29 00:34:56.123456789, null]
x.to_time(hour=0)                 # Pldt：[2024-01-31 00:34:56.123456789, null]
x.to_time(hour=None)              # 保原值，None不是午夜
x.to_time(hour=24)                # ValueError
x.to_date(day=32)                 # ValueError
~~~

先合并全部字段，再验证结果，不能先改月产生中间2月31日而拒绝同时day=29的合法请求。便利方法仅对合法1—31日意图拟合月底；不恢复通用上下收口、进位、-1不修改或strict开关。

**3. 真实整数、等长配对和缺失职责复用B02。**

|字段|准入|
|---|---|
|year|真实整数零／负／宽年，受当前unit和已定日历容量约束|
|month／day|1—12／1—31|
|hour／minute／second|0—23／0—59／0—59|
|microsecond／nanosecond|0—999999／0—999；后者是微秒之后的尾数|
|省略／None|保对应原字段，零按该字段真实含义|

接受Python／NumPy整数及合法__index__，准备阶段一次读取；拒绝bool、1.0、数字文本、绝对月份名。标量广播、列严格等长、长度1集合仍为列、源一行不扩行、按位置配对；Expr显式pl.col，不猜字符串列名。

~~~python
x = Pldt(["2024-01-02", "2024-01-03"], unit="us")
x.pldt.replace(day=[None, 20])  # Pldt：[1月2日, 1月20日]
days = pl.Series("new_day", [None, 20], dtype=pl.Int64)
x.pldt.replace(day=days)        # Pldt，同上；已确认B02
expr = pl.col("time").pldt.replace(day=pl.col("new_day"))  # pl.Expr
x.pldt.replace(day=[20])        # 长度不等，报错
x.pldt.replace(day=True)        # TypeError
~~~

**明确与当前Pddt的差异：**PLDT原生可空整数字段列的null按已批B02表示该行不替换；当前Pddt允许Python None位置，但上述可空Polars整数列报TypeError。本次不放宽Pddt的该缺失边界；日期替换改名按本项同步实施。Python对象pd.NA／NaN不伪装None；Float列不因全空成为整数字段。日期源null保null，但空／全null也须检查形状、字段类型／各字段范围和选项，不能掩盖day=32或hour=24。依赖源日期的组合合法性仅对有效日期计算，不为缺失行伪造YMD。

**4. 固定单位、ns、宽年及元数据沿C03—C06。**

源.123456789，microsecond=1得.000001000；只改nanosecond=2得.123456002；同时给1和2得.000001002。若该行nanosecond为不替换标记而microsecond被显式设置，仍按“未显式提供尾数”清旧尾数，不能因nullable列误保789。

不自动改单位或截尾：us列非零nanosecond报精度错误，ms列microsecond=1000可表示、=1报错；ns列year=2500超容量报OverflowError并提示显式as_unit，us可表示的零／负／宽年不经Pydt范围。保name、原有效位、当前unit和未改tz，不伪造Polars没有的freq。成功结果一次交付且不改源。便宜可知的无变化可在参数校验后复用已有Pldt，不全列扫描只为证明is；Series命名空间仍需输出Pldt，Expr不承诺Python身份同一。业务子类按本轮已收口L03。

**5. 时区replace与便利自动规则分开。**

日期replace的tzinfo为单值：省略保留／None去区保钟表／明确区保钟表重解释，不是tz_convert。Expr区由源schema及该参数静态确定，不逐行混区。严格replace按需要解释新当地时间，提供ambiguous="raise"、nonexistent="raise"；已知不变时刻不制造新歧义，具体策略全集和区域表示能力留H。

~~~python
x = Pldt(["2024-01-02 12:00"], tz="Asia/Shanghai", unit="us")
x.pldt.replace(tzinfo=None)   # Pldt，naive的12:00
x.pldt.replace(tzinfo="UTC")  # Pldt，12:00+00:00，真实时刻改变
# 保时刻转换tz_convert("UTC")另按H02，结果04:00+00:00。

x = Pldt(["2024-03-10 01:30"], tz="America/New_York", unit="us")
x.pldt.replace(hour=2)                             # 默认报不存在时间
x.pldt.replace(hour=2, nonexistent="shift_forward") # Pldt，03:00-04:00
x.to_time(hour=2)                                  # Pldt，03:30-04:00
~~~

to_*不增fold或两DST策略，沿Pddt／Pydt便利自动规则：重复时间优先原实际偏移，缺口按真实间距和来源侧处理且不跨出所选目标日，不一律加一小时或取边界；纽约来源03:30改hour=2得01:30-05:00，来源01:30则03:30-04:00。整日缺失如Apia的2011-12-30报错。显式replace策略按自身含义可调整到边界，不能强套便利自动规则。naive／UTC／真正固定偏移跳过地区候选／存在性往返。

**参考Pydt的部分：**严格非法日期／便利合法日拟合月底、None与零、整数角色、to_date保时钟／to_time保日期及便利自动DST均来自当前Pydt。Pydt标量／us／1—9999／自身fold与列类ns／宽年／列策略是明确能力差异；不把Pydt严格创建规则机械套到全部便利操作。

**性能建议：**最小纯Rust字段合并／日历函数共用，输出适配分开，不能把整个Python绑定_pddt_transform当插件内核。Pddt哨兵与Polars完整int64＋有效位分开；标量一次准备，列保owner／必要快照，循环仅原生整数和存在位。全部字段合并后一次最终日期／容量处理及一次最终列构建，不逐字段构建临时Pldt／Pddt／datetime，不map_elements／逐行Python回调。Pydt不强塞一行数组；Series与Expr共用小核。naive／UTC／固定偏移快路；动态地区必要适配保精度。结构方向未测倍率，不能承诺提速；共享修改须保护现有公开行为与性能。

**验收要求：**严格／便利及同时月日、None／0／负年、类型范围／长度／空／全缺失、原生nullable字段、微秒／ns覆盖、固定单位精度容量、tzinfo去除／替换、NY双向缺口／重复已知时刻／非一小时缺口／整日缺失、name／有效位／源不变、Series与Expr及eager/lazy同义；原生整值replace原合同保持，Pddt新增命名空间在pandas2.3／3.0／3.1分别验证存在性和委托边界；Pydt字段replace不变。用独立日历／刻度预期，不只以Pddt相等证明正确。

<a id="pldt-f02"></a>

### F02 年季月周日移动和全部便利别名

**1. 完整实现26个对应方法，共同含义与当前Pddt／Pydt一致。**

|基本方法|offset单位|可选选择参数|选择的含义|
|---|---|---|---|
|to_year(offset, month=None, day=None)|日历年|month、day|month为全年1—12或已有默认月份名|
|to_quarter(offset, month=None, day=None)|日历季度|month、day|month为目标季度内第1—3个月，不是全年月份号，不收月份名|
|to_month(offset, day=None)|日历月|day|day为1—31的合法日意图，最终拟合目标月末|
|to_weekday(offset, weekday=None)|日历周|weekday|周一0至周日6，或已有默认星期名；None保原星期|
|to_day(offset)|日历日|无|保当地时钟和小数，必要地区自动规则除外|

offset必填整数，可正／负／零，None不代表不移动；0仍执行显式选择。其数值是相对周期数量，to_year(1)为下一年，不是year=1；绝对字段修改按F01的.pldt.replace。可选字段None保原选择，但原日遇目标月末仍按便利日意图拟合。未知／空名称ValueError，不支持类型TypeError；month／weekday仅识别当前Pydt默认已保存词条，不增加cfg、任意大小写归一化或字符串offset表达式。

~~~python
x = Pldt(["2024-01-31 12:34:56.123456789", None], unit="ns", name="time")
x.to_year(1)                    # Pldt：[2025-01-31 12:34:56.123456789, null]
x.to_year(0, month="February")   # Pldt：[2024-02-29 12:34:56.123456789, null]
x.to_quarter(1)                 # Pldt：[2024-04-30 12:34:56.123456789, null]
x.to_quarter(1, month=2, day=31) # Pldt：[2024-05-31 12:34:56.123456789, null]
x.to_month(1)                   # Pldt：[2024-02-29 12:34:56.123456789, null]
x.to_day(1)                     # Pldt：[2024-02-01 12:34:56.123456789, null]
~~~

季度month=None保来源在季度中的月份位置，明确month=2取目标季度第二个月。先确定最终目标年／月及可选day，再一次拟合真正目标月末；不能先移动并损失日号，再做选择。day=0／32、年度month=0／13、季度month=0／4均报ValueError，不收口。合法31日遇二月可取末日，日期位不足与字段非法分开。

**2. 周以周一为起点，offset按周数，不新增week别名或改成ISO编号。**

~~~python
x = Pldt(["2024-01-31 12:00"], unit="us")  # 周三
x.to_weekday(0, weekday="Monday")  # Pldt：2024-01-29 12:00
x.to_weekday(1, weekday="Monday")  # Pldt：2024-02-05 12:00
x.to_weekday(1)                    # Pldt：2024-02-07 12:00，下一周同一星期
x.to_weekday(-1, weekday="Friday") # Pldt：2024-01-26 12:00
x.to_monday()                      # Pldt：2024-01-29 12:00，当前周，不是下一次／最近周一
x.to_sunday()                      # Pldt：2024-02-04 12:00
x.to_weekday(0, weekday=7)          # ValueError，须0—6或有效名称
~~~

本库选择参数0—6与Pydt／Pddt一致；Polars原生.dt.weekday()为ISO周一1／周日7，原生功能不改，也不能直接把这个输出不转换就当本方法weekday目标。J板块再确定查询出口的完整表达，不由本项修改查询接口。

**3. 全部21个便利别名明确落到同一内核。**

|方法组|名单|对应关系|
|---|---|---|
|年度|to_curr_year、to_prev_year、to_next_year|to_year的offset 0／-1／+1；仍收month、day|
|季度|to_curr_quarter、to_prev_quarter、to_next_quarter|to_quarter的offset 0／-1／+1；仍收季度内month、day|
|月度|to_curr_month、to_prev_month、to_next_month|to_month的offset 0／-1／+1；仍收day|
|星期|to_curr_weekday、to_prev_weekday、to_next_weekday|to_weekday的offset 0／-1／+1；仍收weekday|
|当前周七天|to_monday、to_tuesday、to_wednesday、to_thursday、to_friday、to_saturday、to_sunday|当前周固定weekday 0—6，无参|
|相邻日|to_yesterday、to_tomorrow|to_day的offset -1／+1，无参|

5基本＋12周期＋7星期＋2相邻日＝26。保已有方法名，不因Polars有offset_by只实现少数别名，也不新增to_week等同义名字。别名内部直接准备固定offset／选择并进入小核，不先调用公开基本方法产生中间日期对象；错误上下文保用户实际入口。

~~~python
x = Pldt(["2024-01-31 12:00"], unit="us")
x.to_next_month(day=31)             # Pldt：2024-02-29 12:00
x.to_prev_year(month="February", day=31) # Pldt：2023-02-28 12:00
x.to_next_quarter(month=3, day=31)   # Pldt：2024-06-30 12:00
x.to_curr_weekday(weekday="Friday") # Pldt：2024-02-02 12:00
x.to_yesterday()                    # Pldt：2024-01-30 12:00
~~~

月底拟合可能丢失原日号，不承诺反向可逆或分步等同合并。当前Pddt已实测：1月31日.to_month(2)为3月31日；.to_month(1).to_month(1)为3月29日。每次调用只根据实际输入日期运算，不隐藏“原本31日”的状态；有明确最后一天意图可传day=31或使用相应月底方法。

**4. Series／Expr与逐行职责沿A／B，无新增广播。**

全部26项在Pldt支持直接调用，普通Series和Expr用.pldt。日期立即结果Pldt；Expr返回原生pl.Expr，计算后的Frame按原生取列返回Series，不强制Pldt。两已测Polars版本未发现本组26个直接名称与Series冲突；未因此承诺全部未来版本。

~~~python
x = Pldt(["2024-01-31 12:00", "2024-04-30 13:00"], unit="us")
result = x.to_year([1, -1], month=["February", "March"], day=31)
# Pldt：[2025-02-28 12:00, 2023-03-31 13:00]
result = x.to_quarter([1, -1], month=[1, 3])
# Pldt：[2024-04-30 12:00, 2024-03-30 13:00]

s = pl.Series("time", [1706702400000000, 1714482000000000], dtype=pl.Datetime("us"))
result = s.pldt.to_next_month(day=31)  # Pldt
expr = pl.col("time").pldt.to_year(
    pl.col("year_offset"), month=pl.col("target_month"), day=31
)  # pl.Expr；按日期源原行数执行
result = df.with_columns(expr.alias("changed"))  # pl.DataFrame
~~~

offset及所有允许的选择参数支持真标量或合法一维等长列，严格按位置、不按标签；长度1集合仍为列，日期源一行不扩行。正负／零和整数协议沿B02；1.0、bool、数字文本和仅__int__不作整数。标量__index__一次准备，本次两日期广播验证只读一次；表达式不先collect读取长度。

可选month／day／weekday的Python None按行保选择，原生可空整数字段null沿已批B02保留；offset作为必填增量，None／null均报错。年度month与星期weekday的可空String名称列同样null保对应选择，其余名称正常查已保存词条；这与当前Pddt的可空String名称列实测一致，不能因名字列有null就补默认名字。Float／错误dtype不因全空合法。当前Pddt对可空原生整数字段null仍拒绝，保留已批的PLDT差异，不扩大Pddt缺失规则。原日期null保null，但参数范围／类型／长度及所传选项仍检查，不因空／全null跳过错误。

**5. 日历移动保共同自动地区规则，不直接等同原生offset_by。**

时钟／完整小数通常保留；地区缺口按已定自动规则调整时钟，以有效结果守住所选目标日；重复时间优先来源实际偏移，不简单复制fold。无区／UTC／真正固定偏移不做地区候选／存在性往返。无公开fold／ambiguous／nonexistent附加参数，H继续确定相关完整合同。

~~~python
x = Pldt(["2024-03-09 12:00"], tz="America/New_York", unit="us")
x.to_day(1)  # Pldt：2024-03-10 12:00-04:00，日历次日，实际间隔23小时
# 固定timedelta一天的算符职责留G；不能把to_day(1)改成UTC刻度+24小时。

x = Pldt(["2024-03-09 02:30"], tz="America/New_York", unit="us")
x.to_day(1)  # Pldt：2024-03-10 03:30-04:00，与当前Pddt一致
~~~

真实核查：上述缺口例在本机Polars2.0.0及2.1.0原生.dt.offset_by("1d")得到次日01:30-05:00，而当前Pddt得到03:30-04:00。因此PLDT本库方法保Pddt／Pydt共同自动规则，不完整委托offset_by；原生.dt.offset_by仍按Polars原合同可用，不做覆盖。本库不是强行包装一个同名原生函数：目标日／选择／空值／固定单位等均是自有完整合同。普通无区月移动示例可同义，不证明所有地区边界等价。

纽约从3月11日02:30向前一天得到3月10日01:30-05；秋季来源11月2日01:30向后一天保-04，来源11月4日向前一天保-05。Lord_Howe的半小时缺口从10月5日02:15移一日为10月6日02:45+11，不写死一小时；Apia整日缺失2011-12-30仍报错，不跳成另一日成功。

**与Pddt／Pydt的关系：**共同周期定义、先最终年月后月底、星期0—6、默认保存名称、全部26方法及自动地区规则直接参考当前Pydt／Pddt。Pydt为标量／us／1—9999；Pddt／Pldt保列、真实ns和受单位容量限制的宽年。PLDT为Series／Expr／有效位／ms-us-ns，无Index／freq，原生INTMIN可有效；Pddt为Index及NaT哨兵／另有s单位。已有Pddt本组不批准新的日期算法改动，F01.pddt.replace改名不扩大为本组全部命名空间迁移。

**性能建议：**优先复用已存在calendar::move_date与名称选择小核，提取必要纯Rust逻辑服务标量、pandas列及Polars插件；不把整个Python绑定或每行Pydt／Pddt当共享核。operation种类、标量offset／名称和单位／区资料在外准备；原生列及有效位按位置读取，真正计算只用紧凑原生值。一次解码来源日历，合并目标月份及选择后只拟合一次，保时钟／纳秒而不无意义转文本或统一int64 ns；checked中间与最终容量分开。别名固定参数直接入核，输出一次构建，不造26套循环或按别名重入公开方法。可便宜知无变化则合法检查后复用，不为is额外全列扫描。动态区只付必要代价，普通快路保留。未正式测量，不承诺倍率；后续共享修改保护现有公开行为／性能。

**验收要求：**26方法独立代表日期／刻度预期；年／季度／月／周／日正负零及跨年；季度内位置；默认名称／未知名／非法范围；分步月底信息损失；整数协议一次与合法逐行类型、严格长度、可选名称／整数字段null及必填offset缺失；空／全null验证；ns和固定单位／宽年容量；NY日历与实际时长区别、双向缺口／秋季重复／非一小时缺口／整日缺失；source不变及name／有效位／精度；Series与Expr及eager/lazy同义。原生.dt.offset_by完整合同继续保留，不只拿它或Pddt单一路径作正确答案。

<a id="pldt-f03"></a>

### F03 add/sub的日历顺序、逐行量和精度抵消

**1. 保持现行Pddt的两个自有日历方法及11个增量角色。**

~~~python
x.add(
    years=0, quarters=0, months=0, weeks=0, days=0,
    hours=0, minutes=0, seconds=0,
    milliseconds=0, microseconds=0, nanoseconds=0,
)
x.sub(
    years=0, quarters=0, months=0, weeks=0, days=0,
    hours=0, minutes=0, seconds=0,
    milliseconds=0, microseconds=0, nanoseconds=0,
)
~~~

全部是相对增量，不是绝对字段；省略为真实0，负数反向。None／null不代表“不移动”，需要不移动给0；相对hours=25、months=13、nanoseconds=1000均可合法进位，不套F01绝对字段范围。绝对字段仍用已确认.pldt.replace，不在add/sub混入year／month等单数参数或Delta绝对字段。所有角色接受Python／NumPy整数及合法__index__，bool、1.0、数字文本、仅__int__拒绝；每个输入仍须满足既有checked整数转换，不承诺任意Python大整数可凭最终抵消绕过输入转换安全。Delta允许的既定小数角色不因此扩大这两个命名方法。

Pldt直接调用add/sub及Series／Expr的.pldt.add/sub共用规则。实测Polars2.0／2.1的Series没有直接同名add/sub，Pldt可提供直接方法；原生Expr已有.add(other)／.sub(other)等价算符，完整保留其职责，本库Expr日期命名量必须经过.pldt。F01的Pddt字段replace改名不迁移Pddt.add/sub。

**2. 一次合并，固定执行顺序，不按用户关键字排列逐步操作。**

1. 合净月量years×12＋quarters×3＋months，合净日量weeks×7＋days，并将小时至ns合成有符号钟表增量。
2. 根据净月量一次确定目标年月，原日只拟合一次该目标月末；净月量0不先移年／月再移回。
3. 再应用净日量、钟表量及其进退位；月份不是固定30日，不能与日数按常数抵消。
4. sub反转整组相对量方向，仍按相同日历顺序计算；不通过公开add重读参数或构造中间对象。
5. 合并得到最终当地字段后按共同自动地区规则定位，再检查最终固定unit精度／容量并一次构造结果。

~~~python
x = Pldt(["2024-01-31 12:00"], unit="us")
x.add(months=1, days=-1)  # Pldt：[2024-02-28 12:00]
# 先确定2月29日，再减一天；不能先减到1月30日后移成2月29日。

x.sub(months=1, days=-1)  # Pldt：[2024-01-01 12:00]
# 减一月到2023-12-31，再加一天。
x.sub(months=-1)         # Pldt：[2024-02-29 12:00]，减负数为增加。
x.add(hours=25)          # Pldt：[2024-02-01 13:00]，相对增量正常进位。
~~~

以上共同顺序直接参考现行Pydt／Pddt。月底拟合有信息损失，不承诺add后sub总可逆或分步等同合并；固定日历顺序不随关键字书写顺序改变。

**3. 年月抵消先于月底，细时间抵消先于出口精度检查。**

~~~python
x = Pldt(["2024-02-29 12:00"], unit="us")
x.add(years=1, months=-12)   # Pldt：[2024-02-29 12:00]
x.sub(years=1, months=-12)   # Pldt：同上
x.add(years=1, quarters=-1, months=-9)  # Pldt：同上
# 不先变2025-02-28再回2024，净月量已经是0。

x.add(years=1).sub(months=12)
# Pldt：[2024-02-28 12:00]；这是两次独立调用，第一次已丢失闰日。
~~~

~~~python
x = Pldt(["2024-01-01 00:00:00"], unit="ms")
x.add(microseconds=1, nanoseconds=-1000)
# Pldt：原值，净0，ms完全可表示。

x.add(microseconds=1001, nanoseconds=-1000)
# Pldt：[2024-01-01 00:00:00.001]，净1ms，可表示。

x.add(microseconds=1)
# ValueError：最终多出1us，ms不能无损表示。
~~~

按每一行合并后的真实结果检查，不分别因microseconds／nanoseconds较细就拒绝，也不先截掉其中一个再相加。必要的原生checked中间范围仍须守住；不将Python任意精度或超出单个角色转换范围的值先收下。

**4. 固定单位及ns不被覆盖或舍入。**

相对add不是小数字段replace。例如源.123456789：
- add(microseconds=1)为.123457789，原789ns尾数保留；
- add(nanoseconds=211)为.123457000，正确进位；
- sub(nanoseconds=790)为.123455999，正确借位。

保源当前unit，不自动升降、截尾、回绕或变null；精度不足ValueError，容量不足OverflowError，提示按意图显式as_unit后再操作。粗单位合法宽年不因统一成int64 ns而假溢出；本次ms来源加500年保持ms并得到2524年，ns来源同操作超容量。零／负年按C05共同日历及真实单位容量，Pydt目标仍自身1—9999。源中有效INTMIN是Polars正常整数与有效位组合，不被Pddt NaT哨兵吞掉；C04目标转生态的明确碰撞规则保持。

**5. 标量与等长逐行量沿B02，增量缺失必须拒绝。**

~~~python
x = Pldt(["2024-01-31 12:00", "2024-04-30 13:00"], unit="us")
x.add(months=[1, -1], days=[-1, 2])
# Pldt：[2024-02-28 12:00, 2024-04-01 13:00]

x.sub(months=[1, 2])
# Pldt：[2023-12-31 12:00, 2024-02-29 13:00]

x.add(microseconds=[1, 2], nanoseconds=[-1000, -2000])
# Pldt：两行各自净零，保持原值。
x.add(days=[1])       # 长度不等，ValueError；长度1集合不是标量。
x.add(days=[1, None]) # TypeError，增量缺失不代表不修改。
~~~

支持已确认的一维合法容器及Expr列，按位置不按标签；标量不展开N份，原生整数列不转Python整数逐行计算。源日期null保null，但其位置传入非法／缺失增量仍报错，不能借源null跳过参数校验。空源／全null源也校验所有提供的数值／dtype／形状；任一有效行精度或容量失败，整次无结果，不修改来源、不返回部分成功。可选字段null保留职责不扩到这些相对增量。

~~~python
result = s.pldt.add(months=1, days=-1)          # Pldt
expr = pl.col("time").pldt.add(
    months=pl.col("months"), days=pl.col("days")
)                                             # 原生pl.Expr，Datetime
expr = pl.col("time").pldt.sub(months=pl.col("months"))  # pl.Expr
result = df.with_columns(expr.alias("changed")) # pl.DataFrame；取列按原生Series
~~~

本项输出保持日期类型，不输出Duration；Pddt对应返回Pddt，Pldt立即返回Pldt，Expr为pl.Expr。单位／tz源schema已知，不新添unit、strict、fold、ambiguous／nonexistent等参数；Expr无需collect判类型或长度，运行数据约束在执行时检查，错误包装边界留N。

**6. 当地日历／钟表运算，不等同真实经过秒数。**

~~~python
x = Pldt(["2024-03-09 12:00"], tz="America/New_York", unit="us")
x.add(days=1)    # Pldt：[2024-03-10 12:00-04:00]
x.add(hours=24)  # Pldt：同上，命名add的当地钟表进位，实际经过23小时。
~~~

现行Pddt加固定timedelta(hours=24)为次日13:00，属于真实经过时长；PLDT固定时长算符已在G02单独确认，真实动态协议按G03；本项不新增其它算符。Pydt既有算符职责也不因本项改变。

新当地结果沿F01/F02共同自动地区规则：重复时刻优先实际来源偏移，缺口按真实间距／来源侧处理且守住最终目标日；纽约3月9日02:30加一天为次日03:30，3月11日02:30减一天为3月10日01:30；Lord_Howe半小时缺口真实调整，Apia整日缺失报错。naive／UTC／真正固定偏移不做地区候选和往返。不用一条Polars offset_by字符串替代任意正负混合及本库日历合同；原生offset_by完整保留，等价子路径须有证据后才复用，不为了复用改变共同含义。

**与当前Pddt／Pydt的差异：**当前Pddt已经具备本项11角色、顺序、抵消、ns、逐行和固定单位规则，PLDT不要求新Pddt算法。共同日历含义参考Pydt，Pydt仅标量／us、现有10角色不含nanoseconds及自身容量；不因PLDT扩展Pydt公开签名或输入范围。Pddt为Index／s-ms-us-ns及NaT哨兵；Pldt为Series／ms-us-ns、独立null有效位及原生Expr，无Index或freq。保名称、区、原缺失和完整精度；用户子类实际构造协议按L03执行。

**性能建议：**沿现有最小Rust日历与原生整数换算核提取必要纯函数，避免把_pddt_transform的Python绑定整体当插件算法。单值组合尽量在外准备，逐行量按同一既定顺序合并，使用足够宽且checked的中间量；日期只需必要一次解码／月底处理／最终输出，不逐单位创建临时Pldt、Pddt、Delta或Python datetime。sub以原生方向标志复用小核，不能先在较窄整数中取负导致假溢出；参数转换／迭代一次，外部实际协议保护保持。原生owner／切片／有效位／chunk职责沿B/M；不拼N条offset字符串、不map_elements或逐行Python回调。已知净零且参数合法可低成本复用，不额外全列扫描只为证明is；naive／UTC／固定偏移快路保持。结构收益未实测，不宣称倍率；现有类共享修改需独立保护原公开行为及完整调用性能。

**验收要求：**11角色×add/sub的默认零、正负、真实整数协议和拒绝bool／float／None；相对量与绝对范围区分；关键字排列不影响顺序；年月抵消保闰日／日周抵消／钟表抵消／混合细单位逐行最终精度；相对微秒保ns尾数及进借位；固定单位容量与宽年；标量／全列／混合列／不连续列／生成器严格等长、来源null及空／全null仍校验；整体失败源不变；NY春秋／双向缺口／非一小时缺口／整日缺失／固定区；Series与Expr、eager/lazy独立刻度预期；原生Expr.add/sub不受影响。不能只用两个共用同一内核入口相等证明正确；Pydt只对共同us及容量范围比较，纳秒答案用独立整数刻度。

<a id="pldt-f04"></a>

### F04 first/last/start/end/normalize与四个查询

**1. 九个方法职责清楚区分，沿当前Pydt／Pddt共同含义。**

|方法|实际职责|立即／Expr输出|
|---|---|---|
|to_first_of(unit)|选择周期首个日历日，通常保原时钟及完整小数|Pldt／pl.Expr，Datetime|
|to_last_of(unit)|选择周期末个日历日，通常保原时钟及完整小数|Pldt／pl.Expr，Datetime|
|to_start_of(unit)|定位目标周期按当前精度的有效开始|Pldt／pl.Expr，Datetime|
|to_end_of(unit)|定位目标周期按当前精度的有效结束|Pldt／pl.Expr，Datetime|
|normalize()|取原当地日期的有效开始，不跳离本日|Pldt／pl.Expr，Datetime|
|is_first_of(unit)／is_last_of(unit)|判断是不是目标首／末日，忽略时钟|原生Boolean pl.Series／pl.Expr|
|is_start_of(unit)／is_end_of(unit)|判断是不是该周期的实际起／止边界，含当前精度及必要地区信息|原生Boolean pl.Series／pl.Expr|

不是把first／last做成start／end别名，也不是提取Python date／time。地区首末日的原时钟若处于缺口，只按既定便利规则在所选日内作必要调整；整选定日不存在则报错，不以另一日期冒充该首末日。start/end在所选周期内找真实边界，与“首末日保钟表”是不同任务。

~~~python
x = Pldt(["2024-05-07 12:34:56.123456789", None], unit="ns", name="time")
x.to_first_of("M")  # Pldt：[2024-05-01 12:34:56.123456789, null]
x.to_last_of("M")   # Pldt：[2024-05-31 12:34:56.123456789, null]
x.to_start_of("M")  # Pldt：[2024-05-01 00:00:00, null]
x.to_end_of("M")    # Pldt：[2024-05-31 23:59:59.999999999, null]
x.normalize()      # Pldt：[2024-05-07 00:00:00, null]
~~~

五个变换均保原unit、name、区和原缺失位置，不修改来源；不自动改成Date列或调unit。业务子类出口仍按L03，不能以本项先批准全部子类协议；Pddt.freq与Polars无freq的边界保持。

**2. unit为单个静态字符串，准入按方法分开，不能机械复制Snap／freq语法。**

|方法组|接受的周期／名称|
|---|---|
|first／last及对应两个查询|Y、Q、M、W，或已有默认保存月份名称|
|start／end及对应两个查询|Y、Q、M、W、D、h、m／min、s、ms、us、ns，或已有默认保存月份／星期名称|
|normalize|无unit或其它新参数，语义同本日to_start_of("D")|

周从周一到周日；Y／Q／M／W按来源当地日历所在周期。月份名称选择来源同一年该月，星期名称选择来源当前周该日；不是最近候选、不是以指定星期为起点的一整周，也不是Snap的跨相邻年／周搜索。只有保存词条形式生效，单位先识别；不增加cfg／随意大小写／strip猜测或新名称表。

~~~python
x = Pldt(["2024-05-07 12:00"], unit="us")  # 周二，第二季度
x.to_first_of("Q")       # Pldt：2024-04-01 12:00
x.to_last_of("W")        # Pldt：2024-05-12 12:00，周日
x.to_start_of("W")       # Pldt：2024-05-06 00:00，周一
x.to_start_of("February")# Pldt：2024-02-01 00:00，本年二月
x.to_end_of("February")  # Pldt：2024-02-29 23:59:59.999999
x.to_start_of("Friday")  # Pldt：2024-05-10 00:00，本周周五
x.to_end_of("h")         # Pldt：2024-05-07 12:59:59.999999
~~~

first/last的"D"、时钟单位或星期名称不在其准入内，ValueError；"15min"、任意DateOffset、多倍频率也不属本项。非字符串（None、数字、bytes、list、Expr列）TypeError，未知／空字符串ValueError并提示对应方法的合法单位／名称；空列和全null也照常校验。合法但不匹配的查询为False，不额外包装成错误。

**3. 四个查询直接输出布尔，源null为False，与Pddt一致。**

~~~python
x = Pldt(["2024-05-01 12:00", "2024-05-31 12:00", None], unit="ns")
x.is_first_of("M")  # Boolean pl.Series：[True, False, False]
x.is_last_of("M")   # Boolean pl.Series：[False, True, False]
x.is_start_of("M")  # Boolean pl.Series：[False, False, False]
x.is_end_of("M")    # Boolean pl.Series：[False, False, False]
x.to_end_of("M").is_end_of("M")  # Boolean pl.Series：[True, True, False]
~~~

日期变换保null，布尔查询返回False，两种职责不能混淆。这里是四个自有查询的已确认规则，不修改Polars原生布尔表达式通常的null规则，也不借本项提前决定J其余全部查询。空查询仍返回空Boolean列。名字／别名按Polars表达式上下文，完整元数据在L确认，不照搬pandas查询Index的命名方式。

直接查询与变换共用周期定义及候选选择，查询不能先调用公开to_*再逐行比较、生成临时Pldt或Python日期。靠近存储容量端点，某周期边界在容量外不可能等于当前值时应直接False；不能因为构造该边界会Overflow而误报查询失败。实际变换若边界超当前容量仍报OverflowError并提示显式as_unit，不把容量边缘截成假的周期边界。整段不存在的命名目标日变换报错，合法不匹配查询False。

**4. 精度由当前存储单位决定，不升降单位或补造细信息。**

同一天的to_end_of("D")：
- ms列为23:59:59.999；
- us列为23:59:59.999999；
- ns列为23:59:59.999999999。

start/end细于当前存储时，只能在原单位刻度上给出结果；原值本来就是所选细周期唯一可表示点时保原值，不为了时钟尾数生成一个不可表示的临时结果。ns原生最小周期的start/end不变，对应两个start/end查询对有效日期为True，null仍False；us列同样对本身us及更细ns周期按其已有刻度处理。不能把“细周期保原值”误读为us列允许真实非零ns。Pydt仅us，已有ns别名同us；Pddt／Pldt真ns时必须真正区分us边界和ns尾数。

边界数学先用足够宽的原生值，不把所有输入转int64 ns；完整零／负／宽年及当前单位容量按C05。容量检查不截断、不自动改unit、不变null。

**5. 地区边界先守周期含义，normalize必须留本日。**

~~~python
x = Pldt(["2018-11-04 12:00"], tz="America/Sao_Paulo", unit="us")
x.normalize()          # Pldt：2018-11-04 01:00-02:00，当天午夜不存在
x.to_start_of("D")     # Pldt：同上
# 不能跳到前一天午夜或机械生成不存在的00:00。
~~~

当前日历周期开始有缺口时取周期内首个有效边界，末端有缺口时取末个有效边界；日期变换若整个目标周期不存在则报错，不产生新null，合法查询仍按第3节返回非匹配False。不假设缺口一小时，按真实历史规则处理。实际核查：Manila的1844年末日缺失，to_last_of("Y")无法保该选定日而报错；to_end_of("Y")可取本年仍有效的12月30日最后刻度。两操作不应因“统一”被做成一样。

重复小时／分钟等时钟周期优先保来源实际偏移／所属那次出现，再取该次有效边界；日／周／月／季度／年的边界按整个对应日历周期的真实开始／结束，不机械复制来源fold。例如纽约2024-11-03第二次01:30-05，to_start_of("h")为01:00-05，to_end_of("h")为01:59:59.999999-05；to_start_of("D")则为当天00:00-04。共同含义直接参考当前Pydt／Pddt。

不新增公开fold／ambiguous／nonexistent参数。naive／UTC／真正固定偏移不做地区候选、双fold或存在性往返；必要类型／单位／容量校验保留。时区可表示能力和完整策略仍在H，不因已有Pddt能接某custom tzinfo就宣称Polars同样能表示。

**6. 使用与Pddt的差异明确，仅改变载体而不改变共同日期规则。**

~~~python
result = s.pldt.to_last_of("M")              # Pldt
result = s.pldt.is_last_of("M")              # Boolean pl.Series
expr = pl.col("time").pldt.to_end_of("D")    # 原生pl.Expr，Datetime
query = pl.col("time").pldt.is_end_of("D")   # 原生pl.Expr，Boolean
result = df.with_columns(expr.alias("day_end"), query.alias("at_day_end"))  # pl.DataFrame
~~~

Pldt直接方法与两命名空间同规则；两已测Polars版本的Series／Expr没有这九个直接同名冲突。Datetime来源unit／tz由源dtype明确，Expr规划不读数据，不要求collect；本项不加unit输出覆盖参数，不把Date／文本隐式解析混进来。

Pddt日期结果为Pddt、查询为pandas Boolean Index及NaT→False；PLDT为Pldt／Boolean Series或对应Expr及null→False。Pddt另有s单位／Index／freq，PLDT只有ms-us-ns／Series和有效位；Pydt为单值／us及自身容量，查询为bool。九方法共同周期、名称和缺口规则沿Pydt／Pddt，不批准本项重写其已采用算法。

Polars原生.dt.month_start／month_end本就保时钟，普通月首末日与本库对应；本机普通例和缺失午夜的truncate例也有同义结果。但完整的名称、查询、宽年／容量、细单位及地区合同不能由几例相等就全面委托。保原生.dt接口原合同，可证明同义且完整路径更合适时才走原生子路；不在完整委托外套半套自有规则。

**性能建议：**周期／名称在外分类一次，抽出最小纯Rust日历边界及直接谓词函数，Pydt标量、Pddt和Polars插件分别适配精度／有效位／出口，不把整个Python绑定_pddt_period当线程算法。first/last只计算需要的日历字段并保时钟；start/end做原生刻度对齐；查询直接写Boolean列，不生成日期列再比较。普通路径无地区查验，动态地区仅必要候选，必要Python协议载体独立保ns；不逐行调用公开Pydt/Pddt、map_elements或重复创建中间Pldt。owner／chunk／来源可变外壳继续按B/M保护。不为证明无变化另扫全列；合法低成本已知no-op可复用已有Pldt，但不以此绕开非法参数校验。未正式测量，无倍率承诺；后续共享修改保护现有公开路径性能。

**验收要求：**九入口和两种方法准入；Y/Q/M/W及完整现行名称表，星期／月份名称的同年／同周职责与Snap区分；first/last保时钟、start/end及normalize精度；合法非匹配／源null／空Boolean；错误unit空／全null仍拒绝；源不变、metadata和eager／Expr／lazy一致；ms/us/ns边界、最小精度no-op、Pydt ns别名、宽年和容量查询不假溢出；午夜缺口、整日缺失、重复时钟／日历边界、非一小时偏移；独立日历／整数刻度答案，不只对比共用内核的两个入口。原生Polars函数仍按其自身合同。

## G Delta纳秒、经过时长与日期算符

<a id="pldt-g01"></a>

### G01 Delta与PLDT整列算术的归属和字段保真

**一、算法归最小共享Rust核，容器协议各自负责。**

日历顺序、绝对／相对字段和末日规则复用Delta／calendar现有最小纯Rust函数；Pddt和PLDT各准备真实操作数、源整数刻度／unit／时区／有效位，完成原生运算后只构建最终日期容器。Delta类保其标量和Python算符职责，不为支持整列而在Delta中导入pandas／Polars、不把Pldt转成Pddt，也不逐行调用公开Delta/Pydt方法。普通日期来源不变，Delta也不被修改；自有原子失败规则及必要外部副作用边界继续适用。

具体Python协商中，Delta对其不处理的容器正确返回NotImplemented，由Pldt的相应日期操作数入口接管；不发明新的通用分流框架。后续共享修改必须保护现有Delta、Pydt、Pddt公开调用，不把当前已采用的正确性和速度当作可牺牲的参考。

**二、普通Delta支持三个有日期含义的方向。**

~~~python
x = Pldt([
    "2024-01-31 12:34:56.123456789",
    "2024-02-29 12:34:56.123456789",
], unit="ns")

a = x + Delta(months=1)     # Pldt：02-29／03-29，时钟和123456789保留
b = Delta(months=1) + x     # Pldt：与a相同
c = x - Delta(months=1)     # Pldt：2023-12-31／2024-01-29，保时钟／ns
# Delta(months=1) - x       # 不支持；不赋予“时长减日期”的新含义

deltas = [Delta(months=1), Delta(months=2)]
out = x + deltas            # Pldt：2024-02-29／2024-04-29，保时钟／ns
~~~

标量Delta只准备一次并广播；明确的一维Delta集合按B02严格等长、位置配对，长度1集合不当标量，日期源一行不扩成多行。可读list／tuple、Object ndarray、真实Polars Object Series、迭代器等仅表示允许读取此类外层，元素仍须真实Delta且符合其协议职责；不按名称／模块前缀猜类型，不把混合Delta／日期／timedelta列一律强转成同一类型。本项不新增公开Delta列dtype。

原日期null仍为null。明确的Delta操作数／列元素缺失报TypeError，即使对应原日期为null；不把None当Delta()，用户需要逐行不调整可明确传Delta()。空日期列仍校验传入操作数和形状。通用减法中全缺失操作数可能属于“日期差”的类型判定，留G02／G03，不把所有x-[None]无条件解释为Delta列。

**三、完整读取Delta规范值，不能只摘相对量。**

新版完整规范值见GN03；各适配器必须读取相对／绝对ns及其存在状态，不保旧15字段兼容层。

|例子（取上面x的第一行）|建议结果|含义|
|---|---|---|
|x + Delta(days=1)|2024-02-01 12:34:56.123456789|相对加一天|
|x + Delta(day=1)|2024-01-01 12:34:56.123456789|绝对指定当月1日|
|x - Delta(day=1)|2024-01-01 12:34:56.123456789|减法不反转绝对目标|
|x + Delta(hour=0)|2024-01-31 00:34:56.123456789|绝对0时有效，不能误作未设置|
|x + Delta(microseconds=1)|2024-01-31 12:34:56.123457789|相对微秒保来源789ns尾数|
|x + Delta(microsecond=1)|2024-01-31 12:34:56.000001000|绝对小数字段替换，清原ns尾数|
|x + Delta(microsecond=0)|2024-01-31 12:34:56.000000000|显式绝对0也必须执行|
|x + Delta(month=2, months=1, day=31)|2024-03-31 12:34:56.123456789|先综合月份再作最终月末适配，不能先截成二月29再加月|

共享现有顺序：准备绝对年月／合并相对年月，再处理目标日、绝对时钟及相对时钟／天数，并按Delta既定weekday规则定位；相减只反转相对增量，不反转绝对目标。数学顺序以既有独立预期保护，实现统一按G01.N的新精确日历核；当前calendar::apply仅作现状行为参考，不继续保旧微秒核或另写一份近似Polars算法。Delta(day=31)沿Delta原有月底适配，不等同于F01严格字段replace，不能拆成严格replace再add；也不能转成timedelta来丢掉年月与绝对字段。weekday沿本库0—6及当前周规则，不直接采用Polars原生ISO1—7。

**四、保来源精度，当前Delta精度事实与新增能力分开。**

PLDT原生ms／us／ns直接用整数和独立有效位计算，source ns保到出口，绝对microsecond／millisecond按原Delta及C06清尾数。新Delta精度／目标投影按下方G01.N，F03命名整数add/sub不随Delta固定量float角色扩输入。固定Duration职责见G02。

既有Pldt仍固定unit：ms日期加真实1us而无抵消时报ValueError，ns日期加500年若超当前刻度容量报OverflowError；不自动改unit／丢尾数／产生null。零年／负年／宽年份来源只按目标unit容量计算，不先造受1—9999限制的Python日期；Delta构造器自己的可选绝对字段范围仍按其现有合同，不因PLDT宽年能力偷偷放宽。Polars有效INT64_MIN仍是日期，不误当pandas NaT。

时区日期按既定日历含义与H中策略解析，不把当地日历日增量一律当UTC固定24小时；naive／UTC／可表达固定偏移继续捷径。Pddt NaT哨兵、s单位、Index/freq与PLDT独立有效位、ms/us/ns、Series/chunk是适配差异，不改变共同Delta日期数学。

**五、Series／Expr入口贴合Polars，不改原生Expr算符。**

Pldt立即执行支持上面的日期算符；为普通Series和原生Expr提供.pldt.add_delta(delta)／.pldt.sub_delta(delta)，与F03已有.add/sub(years=...,nanoseconds=...)分清。Expr原生.add(other)／+不是本库可随意重载的统一门禁，不猴子补丁Expr，不要求先包装再to_expr。

~~~python
# 以下为拟议PLDT用法
out = s.pldt.add_delta(Delta(months=1, day=1))      # Pldt
out = s.pldt.sub_delta([Delta(days=1), Delta()])  # Pldt，s须两行

expr = pl.col("time").pldt.add_delta(Delta(months=1, day=1))  # pl.Expr
result = df.with_columns(expr.alias("next_month_first"))     # pl.DataFrame
plan = lf.with_columns(expr.alias("next_month_first"))       # pl.LazyFrame，不计算

expr = pl.col("time").pldt.add_delta([Delta(months=1), Delta(months=2)])
# pl.Expr；具体列在建表达式时一次准备，执行时仍须与整个来源严格等长
~~~

普通Delta标量在表达式建立时提取原生字段快照；提前给定的普通Delta集合一次准备紧凑字段列／必要标记，source执行期核对共同长度。分批／chunk执行须保持全列行号，不能每个batch把同一目标列重新配对；不能保证此约束的插件调度方式不得作为实现。输出dtype继承源Datetime的unit／tz，不能按batch改变。Lazy计划不读取、collect日期列；普通运算在Rust中完成。

首版不新增任意Python Object列的符号执行合同：.pldt.add_delta(pl.col("deltas"))在deltas为Python Object Delta列时不能假装已有原生Delta dtype／Struct，须明确拒绝并提示传已准备的具体Delta／集合，或对纯相对整数列使用F03的命名参数Expr。后者只替代相对量表达，不能伪称覆盖Delta绝对字段。原生Object只说明存着Python对象，不自动保证Rust worker可按纯日期算法访问。首版不发明公开Struct布局或自定义Delta dtype，不用map_elements逐行回调补齐。

**六、真实子类／外部回调按已确认G03执行，不静默绕过。**

普通Delta原生读取、无相关覆写的合法子类与确有动态特殊方法的对象必须按真实类型和真实方法定义分开，不能见到子类就拒绝，也不能直接拿其基类字段忽略覆写。具体算符协商／描述符／NotImplemented／原异常及动态Expr准入按已确认G03执行，本项只确定普通原生值路径。

G03已采用的相关实证：当前Pddt标量自定义Delta.__radd__可收到整个Pddt并返回业务字符串；逐行回调使用真实pandas Timestamp承载ns，本机回调读到789ns尾数并能加2ns。Polars ns Series直接取单个值则是us精度Python datetime，1ns实测变成0us。PLDT不能照搬这个逐行取值方式后宣称字段保真，也不能在G01默默引入pandas必需依赖、删掉回调或新造日期标量。已确认G03方案A以一行原生Series承载逐行回调，保ns／宽年并明确返回／Expr边界；普通原生日期数学保持G01规则，尚未实施。

**与Pddt的差异：**普通Delta支持方向、相对／绝对含义、月底适配、纳秒／小数字段替换与严格逐行形状尽量相同；结果由Pddt变Pldt。PLDT另有.pldt表达式入口、Polars有限单位／有效位／chunk约束；不增加pandas必需依赖，不自动给现有Pddt新增add_delta／sub_delta方法。两类真实动态回调载体差异已由G03方案A确认，尚未实施，不冒称与Pddt回调入参同型。

**性能建议与取舍：**标量一次原生快照，不复制N份Delta；原生Delta集合一次读取、一次准备并缓存经核实可复用的类型能力，数值字段列紧凑存储。日历层与Pddt共享，PLDT直接读写刻度／有效位／chunk，末端只包装一次Pldt；Expr使用原生插件供Polars优化／并行，不逐行持GIL调用公开函数。由已有Delta→timedelta或Pddt中转的替代会丢规则／引入依赖和多余转换，不建议。新增准备／结果容量校验仍有成本，端到端未测量，不能承诺更快；以后按相同语义完整公开调用验收，并保护当前Delta／Pydt／Pddt性能。

**验收要求：**三个普通方向与不支持反向相减；标量和每类合法列／生成器／非连续slice，严格等长及空／null参数检查；完整原字段及新增相对／绝对纳秒和组合顺序、相对符号／绝对0／绝对weekday、月底闰年；来源ns保真与绝对小数字段清尾数、新Delta统一ns舍入及各目标出口；不从旧已舍对象恢复未知输入；ms/us/ns固定精度、抵消、容量、宽年和有效INT64_MIN；源Delta／日期不变、name/tz/缺失位；普通子类不因名称门禁被拒；Series／Expr／lazy／多chunk相同独立预期、快照时点与无隐式collect。真实动态回调按已确认G03，不把当前88次观察当新PLDT验收。

<a id="pldt-g01-nanosecond"></a>

#### G01.N Delta纳秒升级：完整统一内核与所有适配

G01.N为G01内部关联方案，不增加60个主项的数量。以下GN01—GN13已合并原Delta方案M01—M13；U1并入GN04，U2并入GN07，U3以G03为唯一动态协议正文。旧原稿与旧合并稿仅供追溯，不另拼接执行。

<a id="pldt-delta-gn01"></a>

##### GN01 已确认合同和实施边界

按新版本完整重构Delta的值、准备、规范化、日期算法、类型出口、状态和实际槽，不兼容旧Delta核心／字节格式，不在旧微秒核外贴纳秒补丁。现有仍保留参数直接属于新合同，不通过旧参数／word布局转译。

新增仅关键字nanoseconds=0与nanosecond=None及只读属性；原19个位置参数职责不移位。相对ns沿固定量数值角色，绝对ns为微秒之后0—999尾数，None未设置／0是真设置。新增字段必须贯穿所有Delta自身操作、真实外部方向、Pydt／Pddt／PLDT及apply_many，不能只让构造接受。

未批准的乘除、排序、Delta减日期、任意ndarray算术和通用ufunc不因纳秒升级自动加入；不承诺保持旧64B体积。新数学支持亚us是批准差异，旧对象已丢掉的输入不可恢复。精确整数、既有years／days范围、真实类型／回调／原异常和所有权保护不变。

<a id="pldt-delta-gn02"></a>

##### GN02 统一选择的技术路线及选择理由

采用下列同一条技术路线，具体私有模块／函数名可按工程组织调整，公开语义和验收保持：

| 方面 | 确定路线 |
|---|---|
| 原生值 | 命名DeltaValue；年月＋days＋唯一clock_ns，绝对字段有独立存在状态；属性从同一值派生 |
| 小数准备 | 精确固定量累计器，合法float的真实二进制值精确累计；仅float分支启用scratch，整数直接精确准备 |
| NumPy接线 | 现有真实算符slot在.item()之前直接读取tick／unit／multiplier；不新增__array_ufunc__ |
| Expr具体Delta列 | 内部原生伴随字段列；首版整列非elementwise入口验证严格长度和全局位置；标量另走elementwise |
| 状态 | 新v2四元组及确定17字段LE字节载荷，不导出hash／repr缓存、不dump Rust内存 |
| 迭代 | 先把同一ns内核做正确，再在该模型内特化／紧凑化；不保旧us核兜底，不追64B硬指标 |

现有binary_foreign仍持有原NumPy对象；先.item()导致的身份和尾数损失可以在已有slot边界解决，不需要另建公开数组协议。技术路线有源码依据，最终速度以N04的同义完整调用证据判定。

<a id="pldt-delta-gn03"></a>

##### GN03 新原生值与公开参数

```text
DeltaValue
  relative:
    years: i64
    months: 0..11
    days: i64
    clock_ns: 0..86_399_999_999_999
  absolute:
    year, month, day, weekday, hour, minute, second,
    microsecond, nanosecond
    + 独立存在状态
```

小时／分／秒／微秒／纳秒属性从同一clock_ns派生：nanoseconds=clock_ns%1000，microseconds=(clock_ns//1000)%1000000。规范年月组与日时组分开，不把一年按天数强行折合。显式绝对0不等于未设置；microsecond存在且nanosecond未设置，不能在值层偷偷改成“显式nanosecond=0”。

绝对millisecond与microsecond先沿Delta已定组合职责归入规范microsecond：例如millisecond=2与microsecond=123456得到2456us，再给nanosecond=7得.002456007。year/month/day原高端收口、weekday／时钟严格范围仍按既定合同，不借纳秒扩大所有字段范围。

整数／index一次读取、原输入signed64 checked边界保持；不能先接收超限参数再用另一字段抵消绕过准入。相对固定量接受现有Python float和真实NumPy float16/32/64；独立扩展浮点、任意float()对象、Decimal/Fraction/complex／文本不因升级变支持。绝对新ns仅整数协议，-1／1000 ValueError，1.0／bool TypeError；相对None不是零。

运行时为紧凑原生结构，Python None与数字不进入列循环。物理布局不预设必须64B；编码／解码／派生flags集中维护，不分散复刻旧索引／word。17字段展开仅用于状态或确有必要边界，普通循环不生成17个PyInt。

<a id="pldt-delta-gn04"></a>

##### GN04 唯一精确准备、规范化和值运算

1. 相对年／季／月合并为年月组；周／日／时／分／秒／ms／us／ns全部进入固定量准备，输入读取及原异常顺序保持。
2. 整数贡献不经float。合法float按实际二进制存储值与精确整数单位系数累计；不猜原十进制拼写。专门定长二进制累计器的范围从准入类型／单位推导，仅float路径启用，不加运行期Python Fraction／大整数依赖；测试用Fraction.from_float作独立oracle。
3. 合并后只在Delta的ns值出口取偶一次。构造后不保亚ns残量；以后日期投影到us是另一个目标类型出口，不是允许构造内部逐项舍入。
4. 欧几里得借位／进位，规范余数非负。-1ns为days=-1及23:59:59.999999999；1500ns为1us+500ns；1us-1000ns规范为零，不保存“曾用ns”的精度标签。
5. 组合／取负／abs用足够宽的checked中间量，最终规范years／days才收窄。如负days最小值加正时钟可在取负后回到合法最大days，不能先窄取负制造假溢出。反之原输入超限及真实最终超限仍拒绝。
6. __neg__只反相对组，absolute不变；abs沿现有年月组／日时组符号，不逐分量abs。Delta±Delta的相对组合及既有absolute加法右优先／减法左优先保持；新增跨层us/ns按U1已确认的独立字段规则合并，不把Delta合并当成依次应用。
7. native_eq／hash／bool／repr统一读取新值及存在状态；1ns不等于零，1000ns等于1us，相等必同hash但不等允许碰撞；非Delta默认比较保持NI协商，不因为能参与加法就隐式转Delta比较。

整数／明确零小数不启用小数scratch。后续可为常见float增加有误差界证明的同义快捷路径；其余由精确累计器完成。两者都属于同一个ns数学合同，不能以未给nanoseconds为由调用旧us算法；不可证明的f64求和捷径不采用。

**U1：绝对微秒／纳秒逐字段合并。**

Delta合并仍是字段值／调整量的合并，不定义为依次执行日期变换。各规范absolute字段独立参与：

- a+b：相对量相加；absolute取右侧已设置值，右侧未设置则保左侧。
- a-b：相对量相减；absolute保左侧已设置值，左侧未设置才取右侧；absolute不反号。
- microsecond与nanosecond分别保存存在状态；一方仅设置microsecond，不在合并阶段清除另一方明确的nanosecond。
- 对日期应用单个Delta时，若只明确microsecond、没有明确nanosecond，仍清除来源旧尾数；合并后两项均明确时，应用两项。两个场景职责不同。

```python
# 新版本目标；x为ns精度日期，小数秒.123456789。
a = Delta(nanosecond=2)
b = Delta(microsecond=1)
c = a + b
# c.microsecond == 1；c.nanosecond == 2
# x + c       -> 小数秒.000001002
# x + (b + a) -> 小数秒.000001002
# (x + a) + b -> 小数秒.000001000，依次应用是另一操作
```

同字段：Delta(nanosecond=2)+Delta(nanosecond=3)取3；相减取左侧2，不变成-1。明确nanosecond=0仍覆盖为0，None仍表示未设置。上述规则同时进入merge／值比较／hash／repr／状态／各日期出口及批量验收，不增加“微秒覆盖整段小数”的另一套合并规则。

<a id="pldt-delta-gn05"></a>

##### GN05 精确日历核、精度投影和时区分工

统一纯Rust入口形如`apply_calendar_delta(value, CivilNs, direction)`：

1. 选absolute年／月，合并净relative年月，一次确定目标月及月底拟合；不先生成中间二月。
2. 选择absolute日／时钟，按下表合成小数，再加相对日时ns并作完整进退位。
3. 按精确日期应用absolute weekday，仍Monday=0／当前周规则；减法不反绝对目标。
4. 返回完整精确字段／宽整数，不构造Python日期，不写缺失哨兵，不在这里限制到1—9999或舍us。

|来源.123456789，单个Delta设置|精确结果小数|
|---|---|
|nanosecond=2|.123456002|
|nanosecond=0|.123456000|
|microsecond=1，无ns设置|.000001000|
|microsecond=1,nanosecond=2|.000001002|
|microsecond=None,nanosecond=None|.123456789|

同义精度算法抽成小函数：`round_ns_to_us_even`、`require_exact_ticks(unit)`、`checked_capacity(target)`。取偶使用整数floor商余数，包含负数／最终坐标奇偶；日历、舍入、目标容量和地区策略不塞进一个带大量模式开关的万能函数。

Pydt先得到最终us时钟，再调用其现有日历自动地区服务／真实构造；普通datetime保其原tzinfo／fold合同，不被强加Pydt地区存在性规则。Pddt／Pldt在完整本地ns中运算，按对应地区自动策略定位回真实时刻后，才校验最终UTC刻度的固定unit；不提前用当地不可整除制造失败。naive／UTC／标准固定偏移不做双fold／往返；动态时区必要协议载体可保留并独立保ns。

内部临时年月／ordinal使用足够宽整数；规范i64年月／天数的计算范围与NumPy倍率分别证明。NumPy tick×multiplier再乘较大ns因子可能超i128，先分解宽days＋日内时钟，不无条件连乘。目标容量在应有投影后检查：datetime.min减1ns最终可舍回min；datetime.max加500ns会舍到10000年，应失败。来源准入和结果容量分开，不能借absolute year修救本来不合法的NumPy标量来源。

<a id="pldt-delta-gn06"></a>

##### GN06 所有日期类与外部操作数矩阵

以下为普通库自有路线，真实外部方法先接管时保其实际返回／原异常；d为Delta，x为来源。

|来源x|d+x／x+d|d-x|x-d|出口职责|
|---|---|---|---|---|
|Delta／无相关覆写子类|base Delta|base Delta|base Delta|完整规范值，不强保Delta子类|
|标准timedelta／合法子类|Delta|Delta|Delta|原day/sec/us精确，真实回调保留|
|pandas Timedelta|Delta|Delta|Delta|真实tick／unit保ns，不因us carrier非零就跳真刻度|
|合法relativedelta|Delta或原真实协商|同角色|同角色|直接原字段，不normalized，来源bool／weekday／leapdays及回调活规则保护|
|date及子类|原日期合同|NI|原日期合同|以午夜精确运算后选择所在日，不先舍us|
|datetime及子类|原日期合同|NI|原日期合同|最终us取偶，保实际构造／异常|
|Pydt及子类|Pydt或真实协议返回|NI|同角色|最终us及Pydt既定地区服务|
|pandas Timestamp|真实Timestamp协议返回|NI|同角色|完整来源ns／宽字段和真实replace，不套Pddt固定unit|
|np时间标量|按M07方向／单位|按M07|按M07|原始元数据与输出职责分开；U2新增方向已批，需完整实现及验收|
|Pddt／Pldt|对应列日期合同|无新增日期意义|对应列日期合同|三方向、标量或严格等长Delta列|
|数字／str／bytes／缺失／未支持数组|正常协商拒绝或真实外部接管|同角色|同角色|不变成零Delta／日期／自动广播；NaT走其既定错误|

显式`d.__radd__(another_delta)`／`__rsub__`当前NI与普通表达式成功不是矛盾；直接方法和Python优先级要分开验，不为矩阵整齐改掉实际协议。+=/-=沿不可变对象正常二元回退，不新增原地修改。正号、乘除／模／排序和任意数组广播不自动增加。

relativedelta是已有专用来源适配，不能直接套公共Delta的bool拒绝而破坏来源含义：如month=False表示未设、True表示一月，hour=False为0时，相对True为1。原字段读取／数值回调后weekday及leapdays活规则复核保持；新ns升级不调用normalized()，不新增原本没有的weekday/leapdays转换支持。工厂from_relativedelta仍按已定职责返回base Delta，而非借本次重构改变子类工厂类型。

**不同日期出口的独立预期：**

- Pydt／datetime：0us+1500ns→2us；1us+500ns→2us；1us+1500ns→2us；0us+1ns→0us。
- date(2024,1,1)-1ns→2023-12-31；datetime同样减1ns最终舍回原时钟，不能共用“先变timedelta”捷径。
- Pddt／Pldt：ns+1ns精确；us+1ns ValueError，us+1000ns合法，1us-1000ns抵消合法；超容量OverflowError，不改unit／截尾／变缺失。
- 宽Timestamp原ns尾数为0且最终无变化时，不为明确abs_ns=0无谓强制成ns单位后假溢出；Delta值自身的明确设置仍保留。

<a id="pldt-delta-gn07"></a>

##### GN07 NumPy路线：读取、原有合同和U2新增范围

从实际类／继承及公开scalar布局读取ticks、unit、multiplier、NaT，持有owner；解码不包含输出类型决定，不在这里缩us。普通标量槽在.item()前把支持的真NumPy数据交新核；不新增__array_ufunc__或新的数组协议，不运行第二套旧精度算法。

| 新版来源单位组 | d+x | x+d | d-x | x-d | apply_many单项 |
|---|---|---|---|---|---|
| datetime64 Y/M/W/D | datetime | date | TypeError | date | date |
| datetime64 h/m/s/ms/us/ns | datetime | datetime | TypeError | datetime | datetime |
| timedelta64 Y/M | Delta | TypeError | Delta | TypeError | TypeError |
| timedelta64 W/D/h/m/s/ms/us/ns | Delta | Delta | Delta | Delta | Delta |

全部成功方向从原始精度进入同一ns内核；最终date／datetime职责按表保留，datetime在最终us出口取偶。ns普通左侧x+d／x-d及对应apply_many是完整必要支持；Y/M时长左方向和粗日期返回类型不附带扩展。

datetime64的Y/M按日历起点；timedelta64在Delta自有读取中Y=31556952秒、M=2629746秒，仍是平均固定时长，不偷改成相对years/months，也不将这个例外扩到Pddt／Pldt固定时长。ps/fs/as／generic及NaT拒绝边界按原类型角色保护；冷／热类型准备、multipliers和真子类实际方法要分开验证。

显式np.add／np.subtract不是当前新增的通用ufunc承诺。本次8个b2观察中，ns标量与Delta的显式ufunc各方向均UFuncTypeError；不能因选择普通slot路线就宣称这些函数已支持。若未来需要ufunc／ndarray，应单独完整设计，不混入这次U2普通算符选择。

**U2：普通NumPy纳秒标量左侧算术。**

正式补齐真实np.timedelta64／np.datetime64纳秒标量的x+d、x-d，以及由此对应的apply_many，直接读取原始刻度、单位和倍率，不能先.item()丢身份或先缩us。原已成功的Delta在左入口也完整保来源ns。np.timedelta64结果为Delta；np.datetime64结果为既定naive datetime，最终us取偶。

```python
# 新版本目标；当前b2还未实现新的左方向支持。
d = Delta(microseconds=1)
t = np.timedelta64(1500, "ns")
# t + d -> Delta(microseconds=2, nanoseconds=500)
# t - d -> Delta(nanoseconds=500)
# d.apply_many([t]) -> [Delta(microseconds=2, nanoseconds=500)]

n = np.datetime64("2024-01-01T00:00:00.000001500", "ns")
# n + d -> datetime(2024, 1, 1, microsecond=2)，2.5us取偶
# n - d -> datetime(2024, 1, 1, microsecond=0)，0.5us取偶
```

实现采用M02/M07选定路线：现有真实算符槽在.item()前解码原scalar，接唯一新纳秒核；不新增__array_ufunc__。保所有已采用真实子类／NI／原异常职责，冷／热、multiplier、direct／普通表达式／bulk分别验收，不能只以直接__radd__成功代替普通操作符。

本次明确范围为普通标量+/-与对应apply_many；不附带增加任意ndarray／通用np.add或np.subtract协议、Y/M时长左方向，不统一改掉粗日期原有date/datetime返回职责。该范围是已确认方案的边界，不是“只修当前成功方向”的回退选项；后者已删除。

<a id="pldt-delta-gn08"></a>

##### GN08 批量、Pddt、Pldt和Expr执行

`apply_many`仍为有序[value+d for value in values]，返回list，单项类型／异常顺序与普通表达式一致，不等于原生列算法。PreparedDelta批次外准备一次；精确内建值直走新核，真实子类／外部回调保协商。generator一次消费，活list回调增删、当前项强引用、已初始化输出和异常释放按既定生命周期，无部分返回／无副作用回滚承诺。

Pddt三方向标量／列完整适配；Value::Delta、普通／DYNAMIC loop、尾数清除、回调结果校验全更新。Pddt有效刻度不得等于NaT哨兵；Pldt i64::MIN可有效，null独立，不能共用同一哨兵pack。保源unit/tz/name/原缺失及仍有效freq，合法无变化复用不额外全列扫描。

Pldt／普通Series.pldt直接读真实缓冲与validity，末端一次Pldt；Expr返回原生pl.Expr，不隐式collect／在worker逐行持GIL。标量普通Delta创建Expr时做纯Rust快照，用elementwise路径；具体Delta集合一次准备成**内部原生伴随字段列**，不对外新增Struct／Delta dtype，不捕获Object列执行。

具体集合首版使用整列非elementwise插件：在引擎广播前核验它是显式集合、长度与实际来源严格相等；源一行不扩行、长度1集合不当标量。以两边chunk游标配对，不要求chunk边界相同，不把全局集合塞kwargs后每batch从0重用。先证明完整行位置和空／slice/filter/rechunk语义，才可在同一模型内做更细并行；group/window上下文按本文件M03的逻辑组／顺序／流式边界执行。

普通Delta列准备拒绝非法缺失，即使源日期null；来源null仍保留。动态Pddt行继续真实Timestamp载体，保ns／宽年／原异常及第一失败位置。PLDT动态载体按已确认G03使用一行原生Series，不能删回调／强制pandas或造新标量；完整支持仍须实施验收。

<a id="pldt-delta-gn09"></a>

##### GN09 to_timedelta的三类精度与真实锚点

无锚点仅无年月相对量、无任何absolute设置的纯固定Delta可导出；abs_ns=0仍需start。固定完整值在标准timedelta出口最后取偶到us，1500ns→2us，500ns→0us，-1500ns→-2us，范围不足OverflowError。

有锚点严格保(start+d)-start职责：

|start|先得到什么目标|跨度如何输出|
|---|---|---|
|精确date|完整ns运算后的date投影|整日标准timedelta|
|精确datetime|精确目标最终取偶到us|原同tz钟表减法；可证明同义才省中间对象|
|Pydt／自定义日期|实际加法／构造／地区规则|实际减法／原异常，不能为了少对象跳回调|
|标准Timestamp|保存精确ns的目标日期|真实时刻差完整保留到标准timedelta最后一次us取偶；动态只做一次实际加法|

```python
# 以下均为新合同的未来期望，不是已实现结果。
d = Delta(nanoseconds=500)
assert d.to_timedelta() == timedelta(0)
start = datetime(2024, 1, 1, microsecond=1)
assert d.to_timedelta(start) == timedelta(microseconds=1)
# 同一时刻的Timestamp锚点保存精确500ns差，最终标准timedelta为0us。
```

优化builtin_span不能直接舍Delta再相减，奇偶由实际目标坐标决定。普通datetime、Pydt与Timestamp的时区／减法区别保持；自定义运算最终非timedelta则按原合同TypeError。

<a id="pldt-delta-gn10"></a>

##### GN10 状态v2、复制、接线、错误和文档

选择新默认状态`(marker, 2, core17, metadata)`，无hash／repr缓存；17字段次序：

```text
years, months, days, hours, minutes, seconds, microseconds, nanoseconds,
year, month, day, weekday, hour, minute, second, microsecond, nanosecond
```

core17只收exact builtin int，reject bool／int子类及错长度／非规范值；absolute -1仅作外部格式未设置编码，运行时用存在状态。bytes采用明确新版8B magic、17个i64小端字段，共144B；不dump Rust struct／padding，不包含hash。旧v1 tuple／15项／136B旧bytes／旧magic／旧构造载荷和未知版本全部拒绝，无试读迁移。

**端序澄清：**规格固定LE，按已知测试向量读回，不猜“哪种端序更像日期”。没有端序标签／校验时，一份误写的BE内容也可能恰为另一合法LE值，不能承诺全部识别；不为此新建复杂协议。此处修正Astra原稿“错endian拒绝”的过宽表述，保留明确格式和非法值验证目标。

全部恢复入口、_restore_delta、构造载荷与__setstate__同步；新完整核心有效后才公开，setstate不改变现有immutable值。默认浅复制新外壳、业务引用共享；深复制先入同一memo再递归，保循环／别名／dict／已设slots，不重跑业务init。真实用户自定义copy/reduce/state不强套默认格式；拒旧核心不是拒绝合法自定义业务状态。

CPython实际nb_add/nb_subtract、unary、comparison、getter／METH描述符、PyO3方法、分配器和缓存一起更新；只改pyi／#[getter]不足。unsafe必须有真实类型／owner／布局依据，构建新payload后重审所有接线，失败不公开未初始化对象。

错误沿既有E01—E32：公开入口、参数、可靠行号／范围，冷路才建上下文；不在纯核引入Python异常／全列repr。真实外部异常／NI／cause、严重错误和必要副作用边界保持，不建新错误框架。

pyi、运行signature／英文docstring、Delta四指南、Pydt/Pddt受影响typing和指南、活动调用方及demo/runtime同步。说明us最终舍入、固定unit、ns尾数、锚点差异、新方向范围和旧pickle拒绝；PLDT未实现前仍标设计示例，不写成已发行能力。

<a id="pldt-delta-gn11"></a>

##### GN11 共享模块、完整入口和邻接保护

|模块职责|本轮变更目标|不得进入的内容|
|---|---|---|
|delta/value|唯一DeltaValue、访问／规范值／merge/neg/abs／值语义|旧word模拟、PyObject、第三方类型|
|delta/prepare＋numeric|21参数角色、一次整数／float准备、FixedNsAccumulator|每行import、类型名门禁、任意转换|
|calendar／小civil函数|CivilNs、宽公历、唯一日历应用|datetime容量、NaT位模式、容器对象|
|quantize小函数|最终取偶／精确unit／checked容量|所有出口强套一种舍入|
|interop／numpy_scalar|原始真实数据、特殊协议、类型专用完成器|第二套日历、先us再贴尾数|
|protocol／lib|slots／MRO／descriptor／分配及注册|跨类型猜继承、多个精度算法|
|bulk|一次PreparedDelta、实际value+d与生命周期|首元素猜整列、删回调省GIL|
|state|新版编码、严格恢复、copy metadata|v1兼容解码、可信外部hash|
|Pydt|Delta最终us与地区服务；命名add/sub的共享接线|新增未批准ns参数、公开Delta中转|
|Pddt|native与动态操作数／unit／NaT／owner／最终包装|Pydt逐行中转、微秒核后拼ns|
|未来Pldt／插件|Polars原生列／validity／schema／owned参数与输出|pandas强依赖、Object worker、隐式collect|

既有37入口／43声明的逐名账本保持：[source-inventory.json](../tasks/evidence/pldt-discussion-decisions-20261029/G01/nano-full-scheme-main/source-inventory.json)。必须包括__new__/__init__/from_relativedelta/to_timedelta/apply_many、下列属性、__add__/__radd__/__sub__/__rsub__/__neg__/__abs__/__eq__/__ne__/__bool__/__repr__/__hash__、__getstate__/__setstate__/__reduce__/__reduce_ex__/__copy__/__deepcopy__及实际槽，不以组名代替逐入口验收。

|属性角色|完整新版只读属性|
|---|---|
|相对规范量|years、months、days、hours、minutes、seconds、microseconds、nanoseconds|
|绝对设置|year、month、day、weekday、hour、minute、second、microsecond、nanosecond|

quarters／weeks／milliseconds／millisecond仍是已有构造角色，不能因为上表未作为独立规范属性列出就删除输入支持；也不因此新增未批准的派生属性。

关键源码定位：delta.rs:165/404/1069/1690/2527/3224，calendar.rs:252，interop.rs:354/404/514/623/780/895，numpy_scalar.rs:306/360/396/512，protocol.rs:425/485/865/981/1373，bulk.rs:25/55/197/379/418/534，state.rs:103/145/225/381/506，pydt.rs:195/3492/3550，pddt/operands.rs:94/274/504/543/647。源码位置是调查时锚点，实施逐入口跟踪新位置，不把旧行号当测试证明。

Parser／Configs不新增接受Delta，不修改语法／strict/default／时区。若提取公历／NumPy原始解码影响parse_str、parse、parse_to_epoch或Pydt其他入口，沿其**原出口策略**做回归与性能保护，不能把Delta最近us规则传播给其他本应floor／截取的函数。Pddt／Pydt命名add/sub直接接typed原生相对量，不经公开Delta重新解析。

<a id="pldt-delta-gn12"></a>

##### GN12 开发次序、阶段验收及停止边界

本节确定Delta子项的依赖次序和退出条件；项目总预算72小时及性能规则统一见N04，后续执行计划须引用本节，不把本节另算一份实施预算。

|阶段|实际交付|必须满足的退出标准|
|---|---|---|
|GN阶段0 合同／起点|已确认U1/U2、来源／方向／差异矩阵、源码／采用包／旧ID冻结|旧格式拒绝已定；G03依赖明确，必要场景不看成绩后挑|
|GN阶段1 新值／准备|DeltaValue、整数与float规范化、merge／neg／abs／属性|独立整数／精确float预期通过，所有构造捷径同核|
|GN阶段2 日期／精度|CivilNs、宽年月／日时、投影与容量小函数|月底／weekday／负借位／日界、各出口预期通过，无旧us兜底|
|GN阶段3 标量／槽|所有实际方向、第三方来源、Pydt／datetime／Timestamp|表达式与direct方法分开通过；原异常、真实类协议及新NumPy范围完整|
|GN阶段4 值生命周期／bulk|v2、复制、memo、apply_many及活输入|旧格式所有入口拒绝；新值／缓存／业务／回调不失配，无部分返回|
|GN阶段5 Pddt接通|普通与DYNAMIC新PreparedDelta、metadata／unit|四单位／NaT／宽年／三方向／等长列／真实回调通过|
|GN阶段6 PLDT接通|原生Series／Expr／chunk／validity|ms/us/ns／有效MIN／严格形状／schema；G03与必要H/M决定落地后才算完整|
|GN阶段7 全量功能／交付|旧正确与新独立预期、文档／typing、wheel/sdist|同源码／真实native／实际安装一致，不仅源码目录测试|
|GN阶段8 性能／采用|固定必要集合、完整两轮及真实缺口／未用原型|门槛和模型按总计划冻结；同一产物通过才采用，不拼接候选成绩|

局部失败、30分钟自查及预算边界统一按N04执行。

<a id="pldt-delta-gn13"></a>

##### GN13 完整测试、性能和产物门槛

###### 独立预期和批准差异

整数／ns用Python大整数；真实float用Fraction.from_float和整数单位因子；日历用独立公历或已知手算。测试不能以新共享核生成expected，也不能只验证Pydt／Pddt／Pldt彼此相等。不能用approx掩盖1ns错误。月份／精度不可逆，别把(x+d)-d==x套到所有场景。

|调用|当前事实|新要求|
|---|---|---|
|Delta(microseconds=.001)／seconds=1e-9|零|保1ns，已批|
|Delta()+真实1500ns时长|亚us丢失|保1us+500ns，已批|
|datetime微秒1＋Delta(microseconds=.5)|仍1us|2us，最终目标取偶|
|datetime微秒1＋Delta(microseconds=1.5)|3us|2us，最终2.5us取偶|
|整秒us Pddt＋Delta(microseconds=.001)|不变|ValueError，单位不变|
|旧v1状态|b2可读|新版本拒绝，已批|
|NumPy ns在左与Delta运算|当前普通路径失败|U2已批准，属于必要新支持及验收|

所有仍正确旧案例保ID／预期；批准差异保原结果、改因与新预期。新错误与历史未支持边界不能混成“兼容失败”。

###### 必要覆盖族

- 全37入口及新增属性／真实slot／direct-method，19位置／新keyword-only、重复／未知／超量及一次回调。
- ±1/499/500/501/999/1000/1001/1500ns、负零／非有限值、float16/32/64、半值邻域、subnormal、整数>2**53、各单位抵消、MIN取负救回／真溢出。
- 所有absolute字段及ns None/0/999/-1/1000、bool／float／index；ms/us/ns层级、U1合并、减法绝对不反号、abs分组、值／缓存不遗漏ns。
- GN06／M07来源全部类型／方向、NumPy十单位／multiplier／NaT／未支持单位、relativedelta回调与规则、optional缺失／坏嵌套导入、普通ufunc边界。
- 日期／月份／weekday／闰日、源与目标容量、Pydt最终奇偶／min/max／跨日、Timestamp宽年与尾数、DST／非1小时／跳日、naive／UTC／固定快路。
- to_timedelta各锚点、标准范围、动态加法一次／原减法、非时长结果错误；apply_many混合／活list／generator／当前项引用／异常清理。
- Pddt/Pldt固定unit／源缺失／非法增量／严格长度／切片／多chunk、有效MIN与NaT差异、来源不变和metadata、Expr快照／空／filter／slice／批次对齐。
- 新pickle所有协议／非法core／旧bytes全拒、copy/deepcopy／dict/slots／memo循环及真实自定义state；核心不可被状态覆盖。
- 高价值回归在隔离副本做最小负向证明：去ns、提前舍us、向零借位、漏absolute0、漏一个方向必须被测试捕获；不造全库变异工程。

性能数值、线程模型、限定调整和同产物交付统一按N04；必要Delta成本族必须覆盖空／整数／浮点／index构造、四方向、neg/abs、属性／比较／hash／repr、状态／copy、跨度、apply_many和各日期类受影响路径。

<a id="pldt-g02"></a>

### G02 固定时长、日期相减和Duration结果

**具体例子：**

```python
# x的当地时间为2024-03-09 12:00，America/New_York。
x.add(days=1)           # Pldt：2024-03-10 12:00，当地下一天同钟表
x + timedelta(days=1)   # Pldt：2024-03-10 13:00，真实经过24小时
x - other_dates        # 立即路径返回原生pl.Series，dtype为Duration
# 对应Expr日期差直接返回pl.Expr，执行结果dtype为Duration。
# 以上为拟议PLDT行为，不是已实现的运行结果。
```

**已确认规则：**

1. **日历与经过时长分开。**add(days=1)／普通Delta(days=1)按当地日历移动；加减固定timedelta按真实经过时长计算，与Pddt保持共同含义。日历移动遵循已定F03／G01，地区自动处理的具体策略按H对应项确认。
2. **日期差返回原生Duration。**立即路径输出Polars原生Series，Expr路径直接返回原生pl.Expr，执行结果为Duration；不包装成Pldt。保留差值正负和缺失，按真实时刻计算。
3. **时区判定明确。**不同aware时区可以相减；naive与aware混用报TypeError，不猜测时区或按钟表字段直接相减。
4. **精度与容量分别检查。**日期加减固定时长仍遵守C03的既有日期固定unit、合并后检查和无损要求。日期相减产生新的Duration结果，选择能够保存两边精度的明确合法单位，不能静默截掉细精度；真实int64 Duration容量不足报OverflowError。差值结果选择单位不改变两个源日期列的单位。新Duration的共同单位按两边来源精度／schema在执行前确定，采用更细的共同合法单位；不根据各batch数值临时降单位来躲容量错误。

**已确认边界：**不支持日期+日期；裸数字不当日期时长。不因此新增任意DateOffset适配，真实外部算符协商和子类回调按已确认G03。

**性能方向：**固定时长可用原生整数融合计算，无需日历解码；只在输出差值需要时选更细合法Duration单位，不静默截尾。普通来源一次准备，按原生刻度及有效位计算，避免逐行构造Python日期；具体性能须后续实测，本次没有提速倍率。

<a id="pldt-g03"></a>

<a id="pldt-g03-dynamic-protocol"></a>

### G03 外部算符、子类回调和不支持的DateOffset

**现有源码与运行事实：**当前Pddt通过真实类型／特殊方法判断区分普通Delta、普通timedelta及相关真实子类；未覆写相关运算的子类走原生值路径，真正覆写者保留方法和描述符。标量动态来源由正常Python算符协商；逐行动态来源在rust/pddt/operands.rs:504构造真实Timestamp，调用实际方法并校验返回。Pddt完整继承／委托给pandas的功能继续按原合同，不因PLDT设计受限。

G01/proposal-01两环境的保存证据表明：标量自定义Delta.__radd__收到整个Pddt，可返回字符串business-result；逐行覆写收到Timestamp，读到789ns尾数并返回加2ns后的791ns，原RuntimeError对象及首个失败顺序保持。Polars直接取ns日期标量得到Python datetime，原1ns变为0us；不能把这一取值路线当作保真载体。

**一、普通值及未覆写相关方法的真实子类，仍走Rust原生路径。**

~~~python
class PlainDelta(Delta):
    pass

x + Delta(months=1)       # Pldt
x + PlainDelta(months=1)  # Pldt；不因“是子类”额外逐行回调
~~~

按实际相关特殊方法及真实类型识别，不按类型名／模块字符串，不用第三方通用槽地址相同推定没有覆写；能力缓存必须观察真实类修改，不能将一次判断永久化。普通字段读取、共享Rust核、完整ns及固定unit遵守G01／G01.N。此处也保护已经批准的普通时长来源，不扩大未支持类型。

**二、Pldt立即算符保整列Python协商；外部方法的返回和异常保持。**

~~~python
class Custom(Delta):
    def __radd__(self, other):
        return "business-result"

out = x + Custom(days=1)
# 建议：Custom.__radd__收到整个Pldt；out为str："business-result"。
~~~

Pldt自有算符不提前拿Delta基类字段吞掉真实覆写；不能把普通Python运算符的业务返回强制包装成日期。遵守真实正向／反向方法次序和NotImplemented，不额外重复已发生的回调；双方均不支持时由Python报TypeError。真实外部异常保持原对象／原因；本库自己发现的返回或形状错误按公开入口及可靠位置报告。

命名日期入口的返回职责不同：Series.pldt.add_delta／sub_delta始终承诺日期结果，若执行真实整列回调，其返回必须是与来源等长的合法日期列；不能因为普通算符允许业务str，就让命名日期入口返回str，也不能把输入标量广播推广成任意业务返回自动广播。回调返回NotImplemented而无可用协议时，明确报TypeError，不静默改读基类字段。动态返回仍须守固定unit／容量／时区职责；不改写回调的业务值冒充成功。

**三、逐行真实回调采用方案A：一行原生Series载体。**

~~~python
# 以下均为已确认、尚未实施的PLDT接口。
class PlusTwoNs(Delta):
    def __radd__(self, dates):
        return dates.pldt.add(nanoseconds=2)

x = Pldt([
    "2024-01-01 00:00:00.123456789",
    "2024-01-02 00:00:00.123456789",
], unit="ns")

out = x + [Delta(), PlusTwoNs()]
# Pldt：第一行.123456789；第二行.123456791。
# 第一行走普通Rust核；第二行回调收到长度1的原生pl.Series。
# 同一PlusTwoNs作为标量参与x + PlusTwoNs()时，收到整个Pldt。
~~~

确定规则：

1. 只对真正需要动态方法的行准备长度1的原生Datetime Series，保原unit／tz／name、完整刻度与有效位；不提取成Python datetime、不转Pddt、不要求pandas，也不新造公开日期标量。该Series是必要外部协议载体，不是逐行调用普通日期算法的替代。
2. 逐行回调的日期列返回必须恰好一行；允许已经批准可读取的日期标量或明确缺失结果。拒绝字符串、数字、时长、错误长度及其它非日期结果，不调用通用文本解析“修好”业务返回。返回结果按源固定unit、容量及aware一致性检查；aware结果按真实时刻表达于源时区，不把另一时区钟表直接当源时区。
3. 源null仍保null，不为其调用逐行动态方法；所传Delta／时长目标的类型及长度仍校验，不能因源null跳过非法目标。动态回调按来源行序执行，首错即停止，不交付部分结果；外部回调已经发生的业务副作用不承诺回滚。
4. 有Python回调的立即调用由调用线程按行序完成，不能把任意PyObject或Python方法送进Polars并行worker；调用外部方法时不持跨回调的可变Rust借用，持有必要owner／对象引用。普通行仍可调用纯Rust核；不能为混合回调任意重排具有可观察先后关系的处理。
5. 无覆写、整列覆写、逐行覆写分别验收。真实子类不仅看__radd__，对应正向／减法／反向职责按实际表达式判断；描述符、live class改变、NotImplemented及原异常不能遗漏。

**与Pddt的明确差异：**Pddt逐行收到pandas.Timestamp；PLDT逐行收到长度1的原生pl.Series。都实际执行用户方法、保来源ns，但不是同一种回调入参，读取字段和返回方式需要按各自生态编写。依赖Timestamp.nanosecond的旧回调不能直接当作PLDT回调承诺；用户可用.pldt列方法或原生.dt／整数列操作改写。不改当前Pddt回调协议。

**已选边界与原因：**采用一行原生Series载体并保留逐行真实回调；不单独引入pandas Timestamp适配或新公开日期标量，避免额外依赖、有效INT64_MIN／NaT碰撞及公共维护范围扩张。载体可行性不等于PLDT完整功能已通过，仍须实施验收。

**四、Expr只接可准备成原生值的来源，不隐式执行动态Python。**

~~~python
expr = pl.col("time").pldt.add_delta(Delta(months=1))
# pl.Expr；准备原生快照，Rust执行。

expr = pl.col("time").pldt.add_delta(PlainDelta(months=1))
# pl.Expr；无相关覆写的子类同样允许。

expr = pl.col("time").pldt.add_delta(PlusTwoNs())
# 已确认：构建表达式时TypeError，说明动态Python运算方法不支持原生Expr。

expr = pl.col("time").pldt.add(nanoseconds=2)
# 对于这条业务规则，用户可直接写等价的原生pl.Expr。
~~~

在准备标量或具体Delta集合时检查真实动态资格，动态来源即拒绝，不因未来为空／全null而改准入。拒绝后不静默提取基类字段、不插map_elements／持GIL worker，不把Expr先collect成Pldt。合法普通来源继续按G01一次准备、跨chunk共同位置及原schema执行。此限制属于本库原生表达式合同，不声称Polars整体不能使用Python UDF；用户显式选择原生Polars UDF的功能、成本与行为仍由Polars负责。

**五、不自动扩展DateOffset／relativedelta列运算。**

PLDT只实现已经批准的Delta、日期、固定时长来源；不隐式转Pddt、不复制整套pandas DateOffset／特殊业务日历。Pddt原来完整继承或委托的pandas能力保持。需要relativedelta日期规则时，用户先明确转换：

~~~python
delta = Delta.from_relativedelta(rd)
out = x + delta  # Pldt；后续遵守Delta自身已定语义
~~~

不支持的普通算符正确返回NotImplemented，让真实对方方法协商；双方不支持时TypeError。命名日期方法收到未支持来源则明确TypeError，不以“没实现”伪装缺失日期。不能承诺任何第三方对象在收到NotImplemented后绝不会自行完成运算；这里只限定本库不提供隐式DateOffset适配。dateutil／pandas仍各按可选依赖职责，不因本项变必需。

**性能影响与验收方向：**普通精确Delta及未覆写子类一次准备后走原生循环，没有逐行日期包装或Python回调；真实整列覆写按Python协议执行，实际业务耗时由其实现决定。方案A逐行有k个动态有效行，就只为这k行准备必要载体和调用Python；全列动态会有明显逐行成本，不能称为纯Rust速度。真实方法识别和有效缓存仍有成本，须实测完整调用并保护Delta／Pydt／Pddt；本次没有正式性能采集或倍率。Expr普通路径不加入动态解释器，只在规划准备时识别／拒绝动态来源。符合Rust Skill按具体来源静态快路、必要时动态派发及owner约束，不为“零Python对象”删除真实协议。

**后续必要验收：**精确基类／无覆写子类／真实相关覆写／无关方法覆写／继承描述符／类运行期修改分别验证；整列运算的真实方法次序、业务返回和同一原异常；动态列行序、返回0／1／多行、日期／缺失／错误类型、NotImplemented、首错与源null；1ns／789尾数／有效INT64_MIN／ms-us-ns／时区／宽年及所有权；普通行与动态行混合、多chunk／非连续输入、固定unit与抵消；Expr在准备时同一规则拒绝动态来源、普通子类快照可用且无隐式collect／Object解释器。必须证明普通调用未额外进入逐行Python；不将载体28次观察转记为这些PLDT功能已通过。

## H 时区、DST与快捷路径

<a id="pldt-h01"></a>

<a id="pldt-q01"></a>

### H01 时区类型、固定偏移、本机区和数据库边界

**已定规则：**

1. 时区输入沿共享真实类型服务：IANA／已有UTC别名、ZoneInfo、可编码的标准固定偏移及已支持pytz名称适配；不新增任意UTC+HH:MM字符串语法，不靠类型名猜区。输出必须能真实编码进Polars Datetime的单一时区元数据。
2. UTC及存在严格等价原生表示的整小时固定偏移可使用；+05:30、秒级偏移或任意自定义tzinfo若不能作为目标dtype表达，明确ValueError，不借相似地区、不退object、不暗改UTC。整小时也以实际可编码集合为界，不承诺所有小于24小时偏移。
3. 来源偏移与目标dtype分开：已知时刻可按D03显式转换至可表达目标；例如来源+05:30可显式tz="UTC"，并非一概拒绝该输入。已是原生Series时只认真实现有元数据，不恢复它先前已丢失的来源信息。
4. local首次实际需要时复用现有iana-time-zone／ZoneInfo成功缓存，失败不回退UTC；naive／UTC／固定偏移不做地区候选。tz_available只报告实际后端可支持的地区，Expr元数据查询须有schema上下文，不隐式collect。
5. 原生dtype不保存输入Python tzinfo类型、对象身份或自定义显示名；不额外建立会在普通Series／DataFrame／Expr出口丢失的来源侧表。Python与Rust tzdb版本分别记录，代表历史日期独立对照。

**具体例子：**

```python
Pldt(s, tz="Asia/Shanghai")
Pldt(s, tz=ZoneInfo("Asia/Shanghai"))
Pldt(s, tz=timezone(timedelta(hours=8)))
Pldt(s, tz=timezone(timedelta(hours=5,minutes=30))) # ValueError：该固定偏移不能编码为目标区
```

**规范化Python表示：**naive返回None；UTC及共享服务的UTC别名返回timezone.utc；普通IANA及可表达固定偏移的规范化名称返回对应ZoneInfo。不恢复原输入对象种类／身份，不保存隐藏来源侧表；K02显式对象导出的tzinfo同用此规则。现有Pydt／Pddt保留各自输入对象的行为不改。


**性能影响：**时区在边界一次规范化；naive/UTC/固定偏移提前分路。不要为普通路径查询本机区或为不支持偏移建大型别名表。

~~~python
# 拟定行为；尚未实现Pldt
values = ["2024-01-02 12:00:00"]
a = Pldt(values, tz=timezone.utc)
b = Pldt(values, tz=ZoneInfo("UTC"))
a.tzinfo is timezone.utc  # True
b.tzinfo is timezone.utc  # True
b.timedf()["tm_isdst"].to_list()  # [-1]
b.utctimedf()["tm_isdst"].to_list()  # [0]
~~~

**明确接受的差异：**当前Pydt／Pddt保真实Python时区对象，因此ZoneInfo("UTC")来源的当地tm_isdst为0；Pldt同一原生UTC元数据统一恢复timezone.utc，当地值为-1。标准固定+08:00若编码为Etc/GMT-8，恢复ZoneInfo、当地值为0；Pydt／Pddt若保标准timezone(+08:00)，当地值为-1。两者偏移和时刻相同，不能把对象／DST表表示差异误称时间算错。已有Pydt／Pddt不修改。

<a id="pldt-h02"></a>

### H02 附区、转换、去区以及None的逐入口含义

**已定规则：**

1. 共同附区／转换／去区语义完整沿Pddt：tz_localize(tz)解释naive当地钟表；tz_convert(tz)保真实时刻且要求aware，不能沿Polars原生naive自动当UTC。
2. tz_localize(None)去区保钟表；tz_convert(None)先转UTC再去区；astimezone(None)使用共享local，naive astimezone按local解释；tz_switch(None)按既定保钟表去区，naive转非空目标须明确base_tz，naive=True在转换后去区。
3. 已知有效aware时刻不重新本地化；原unit／ns／name／null保留，实际容量仍checked。Series与Expr同义，local／目标区准备及schema按D02/D03/E02/M01，不为查询收集数据。

**具体例子：**

```python
x.tz_localize("Asia/Shanghai") # 当地解释
x.tz_convert("UTC")           # 已知时刻转换，须aware
x.tz_localize(None)            # 去区保钟表
x.tz_convert(None)             # 先UTC再去区
x.tz_switch("UTC",base_tz="Asia/Shanghai")
```

**边界与旧稿清理：**原生.dt.convert_time_zone等完整方法保持Polars自身规则；本库.pldt接口不是其改名别名。

**性能影响：**真正tz_convert通常只改元数据，共享UTC缓冲；重新本地化才做当地候选，避免不必要的双fold验证。

<a id="pldt-h03"></a>

### H03 ambiguous／nonexistent完整词汇与职责

**已定规则：**

1. 保Pddt公开ambiguous/nonexistent两参数及默认raise，不新增PLDT fold，也不再增加earliest/latest作为另一套本库公开词汇。原生.dt接口的词汇不改。
2. ambiguous接受raise／NaT／infer及真Python／NumPy bool标量或按完整逻辑位置严格等长的一维布尔策略列（Series或对应Boolean Expr；具体列按位置，聚合角色按已确认M03逻辑标量规则）；不把数值0/1、None或任意真假对象当布尔策略。bool沿既定真实候选分类，不一概True=fold0或dst()!=0。华沙1915两候选dst均0、基辅1990两候选dst均1小时，也须按已定pandas候选规则正确选择；is_dst是独立的非零DST查询。
3. nonexistent接受raise／NaT／shift_forward／shift_backward及已支持合法统一timedelta／Timedelta，不扩逐行nonexistent列。用户明确NaT策略输出Polars null，仅处理对应DST问题，不吞普通解析失败。
4. 统一策略在外层准备；mask／infer只进相应分支，普通naive／UTC／固定偏移不因选项增多而枚举候选。实际候选、原序推断与缺口处理分别沿H04/H05。

**具体例子：**

```python
Pldt(texts,tz="America/New_York",ambiguous=[True,False])
Pldt(texts,tz="America/New_York",ambiguous="infer")
Pldt(gaps,tz="America/New_York",nonexistent="shift_forward")
```

**边界与旧稿清理：**旧的“只保Polars原生选项”备选不符合共同功能规则，按本轮授权收口为完整共同策略。

**性能影响：**统一规则在循环外准备，mask和infer仅进入对应路径。普通无DST调用不因支持更多选项而枚举更多候选。

<a id="pldt-h04"></a>

### H04 infer必须保原序、跨chunk和真实候选

**已定规则：**

1. infer由共享Rust规则按当前逻辑序列原序和真实UTC候选推断，不调用pandas infer，不排序、猜测或按物理chunk独立推断；证据不足明确错误。
2. 同一逻辑列／组的歧义区间即使跨chunk仍整体判断，infer必须声明为非elementwise的有序运算；允许Polars执行引擎为必要逻辑列／组物化，不等于Python偷偷collect整表。
3. 过滤或显式排序后的数据按该执行位置实际行序推断；分组只在本组有效输入内解释，不把不同组拼接。Expr参数的聚合标量职责按M03，不改变本项推断数学。
4. 普通无歧义、统一策略和可逐元素计算的路径不因infer而整体失去并行／流式资格；状态受操作／组生命周期约束，不建立跨任务全局可变缓存。

**具体例子：**

```python
texts = ["2024-11-03 01:00","2024-11-03 01:30",
         "2024-11-03 01:00","2024-11-03 01:30"]
# 断点若恰在两个chunk之间，也必须得到同一推断
Pldt(texts,tz="America/New_York",ambiguous="infer")
```

**边界与旧稿清理：**实现需验证非elementwise调度及跨chunk／组顺序；这属于证明已定合同的技术验收，不再投票是否可以每批猜。

**性能影响：**这是少数必须额外状态／整列信息的路径；明确缓存/内存上界，不能为infer让全部普通操作放弃流式与并行。

<a id="pldt-h05"></a>

### H05 不存在时间的最近边界与统一timedelta

**已定规则：**

1. shift_forward取最近有效前向边界；shift_backward取边界前一个当前unit可表示刻度。纽约02:30分别为03:00和01:59:59.999999(us)，不是一律按缺口长度移动。
2. ms/us/ns按各自原单位计算边界；显式timedelta按用户给定量移动，移动后仍无效须按既定规则错误，不能假设所有间隙都是1小时。
3. nonexistent仍为整次统一策略；null仅来自源缺失或用户对应的明确NaT策略，不能把普通解析、容量或精度错误改成null。

**具体例子：**

```python
Pldt(["2024-03-10 02:30"],tz="America/New_York",
     nonexistent="shift_forward") # 03:00
# us下backward为01:59:59.999999
# timedelta(hours=1)明确为03:30
```

**边界与旧稿清理：**Lord Howe半小时、Apia整日缺失及边界不能跨允许周期的例子继续作为独立正确预期。

**性能影响：**间隙才进入边界搜索，缓存可靠地区转换资料；常规日期不按行做二分搜索。候选内核可不同，最终例子必须一致。

<a id="pldt-h06"></a>

### H06 自动日期操作与普通时区快捷路径

**已定规则：**

1. 自动日期操作共享目标周期／日历方向／取整数学及候选选择小核，不机械复制fold，不给全部便利方法增加公开DST策略。严格构造／replace等仍按显式策略合同。
2. ceil不能早于输入、floor不能晚于输入；first/last保时钟，start/end守目标周期，normalize留本日。周期完全不存在或不能同时满足方向／周期／有效性时明确错误，不跨周期冒充成功。
3. naive／UTC／可表达固定偏移外层识别后走整数捷径，不做地区双fold／往返验证；地区路径才访问实际必要资料。Parser仍只解释字段，不能为新类变成DST存在性检查器。
4. 候选后端可以不同，Pydt/Pddt/PLDT各自已定规则不因物理后端自动改变；既有Pydt外部协议的批准限制保持。

**具体例子：**

```python
x.to_day(1)                  # Pldt：按当地日历目标及既定自动规则
x.pldt.ceil(freq="h")         # 日期ceil，结果真实时刻不能变早
x.normalize()                # 留在本日；没有有效本日则错误
# x.ceil()保Polars原生方法；日期取整使用.pldt，见I01。
```

**性能影响：**外层一次识别naive/UTC/固定/地区；前3类只做整数计算，地区资料按真实需要访问，普通路径不支付gap/重复验证成本。

## I round／ceil／floor、Snap与fsp

<a id="pldt-i01"></a>

### I01 round/ceil/floor保共同频率和取偶规则

**已定规则：**

1. 日期round/ceil/floor完整沿Pddt固定频率集合、freq命名、取偶、真实时刻方向和自动地区规则；不恢复unit关键字，不把日历月offset当固定取整。
2. Polars Series本来已有数值round/ceil/floor，因此Pldt保留原生同名方法，本库日期取整统一使用x.pldt.round/ceil/floor，Series／Expr都经.pldt。Pddt/Pydt原入口不因本项改名。
3. 共同checked整数网格与候选选择复用；可证明同义的原生truncate子路可完整复用，但不能将不同取整规则的round原样委托。结果保持原unit，真实精度／容量按C03，不丢尾数求成功。

**具体例子：**

```python
x = Pldt([np.datetime64(500000, "us")])
x.pldt.round(freq="s")        # Pldt：纪元0秒，中点取偶
x.pldt.round(freq="15min")
x.pldt.ceil(freq="h")
x.pldt.floor(freq="500ns")
expr = pl.col("time").pldt.round(freq="s")  # pl.Expr
# x.round(decimals=0)仍为Polars原生数值API，不是本库日期取整。
```

**边界与旧稿清理：**这是依据A04/F01纠正旧稿直接x.round(freq=...)的冲突，不是新加一层兼容别名；不保留双义参数分流。

**性能影响：**单位步长外准备，纯整数融合；避免为了ceil先round后再加一步造成第二个日期对象和重复DST处理。

<a id="pldt-i02"></a>

### I02 Snap的名称、最近起点和真实等距取晚

**已定规则：**

1. 接口snap(unit="s")。单倍周期固定为Y／Q／M／W／D／h／m／min／s／ms／us／ns，以及当前默认词表554个已保存月份／星期名称和大小写形式；不任意strip/lower扩词，不接受15min等多倍频率、DateOffset、year/month/day等文字单位全称或整数星期编号，不添加cfg／fold／DST参数。非字符串TypeError，未知／空字符串ValueError。554名称原清单见已采用Pddt最终决定附录A，使用同一不可变数据，不重建另一张表。
2. 最近有效周期起点按真实时刻比较，等距取较晚；重复起点作为不同真实候选，完全缺失周期按既定相邻搜索，不替换为round/truncate/to_weekday。
3. 单位／名称一次准备，共享候选与公历小核；原unit／ns／tz／null及周期容量检查保持，不为查询生成整列中间Pldt。

**具体例子：**

```python
Pldt(["2024-01-02 12:00"]).snap("D") # 下一天00:00
x.snap("Monday")                    # 最近周一有效起点
x.snap("April")                     # 相邻年份四月一日
x.snap("15min")                     # ValueError
```

**边界与旧稿清理：**月份名称已在Pddt最终合同支持；本轮不重开是否支持月份名称。

**性能影响：**解析unit/名称一次，候选/日历小缓存按有效数据使用；查询不产生整列中间Pldt。

<a id="pldt-i03"></a>

### I03 fsp按单个precision截位，与unit转换分清

**已定规则：**

1. fsp使用单个合法整数precision，拒绝bool、float和列；负数错误，precision>=9保已有值，不伪造更细来源精度。
2. 含义是本秒小数截位、不进位；负纪元按真实秒／小数字段计算，不以向零截整个纪元代替。输出保持unit，不能把fsp变成as_unit或普通round。
3. 当前粗unit已无变化时可按低成本已知条件复用；普通原生运算不必解码完整年月日，也不先建立更细日期。

**具体例子：**

```python
x = Pldt(["1969-12-31 23:59:59.123456789"])
x.fsp(3)   # .123000000，unit仍ns
x.fsp(9)   # 不变，不补精度
x.fsp([3]) # TypeError
```

**性能影响：**简单原生模运算，无需解码完整YMD；可直接基于tick精度决定no-op。

## J 日历查询、条件、diff与表格

<a id="pldt-j01"></a>

<a id="pldt-q02"></a>

### J01 全类日历查询、属性编号与返回dtype

**已定规则：**

1. 自有字段／日历查询沿Pddt命名、属性与方法角色：weekday周一0，isoweekday()周一1，day_of_year／days_in_month／is_leap_year为既定属性，其余按完整入口映射；nanosecond仍额外0-999尾数。
2. 自有单列整数查询统一原生可空Int64，布尔查询源null为False；多字段表按J04专门dtype，不用小整数dtype备选悄悄改变同一查询。原生.dt属性仍按Polars原dtype／编号。
3. 按所需量直接计算，不为一个weekday生成完整日历表，不用strftime拆数字或构造临时日期。is_past/is_future的eager含义沿Pddt：一次有效查询共用参考，aware比真实时刻、naive比当地钟表，相等和缺失False。

**具体例子：**

```python
x.weekday        # 周一0，isoweekday()周一1
x.day_of_year    # 属性，从1开始
x.days_in_year() # 方法
x.nanosecond     # 789尾数，见C06
x.is_past()      # eager有效调用一次参考；Expr按本项规则创建时快照
```

**最终规则：**调用is_past/is_future创建Expr时各取一次原生整数参考，同一Expr重复collect复用该参考；更新须重新建立查询Expr。eager按需取一次参考，空／全缺失不取钟；Expr即使未来为空也在建立时取参考。所有行／chunk／组共用本逻辑查询参考，不承诺不同调用共用时刻。

**性能影响：**按所需量解码，单weekday无需算整张日历表；不统一用strftime拆数字或生成临时Pydt。

#### J01.1 查询参考时刻及准备边界

~~~python
# UTC 09:00建立Expr，输入日期为09:05。
expr = pl.col("time").pldt.is_past()
# 09:10才执行：仍比较09:00，past=False。
result = lf.select(expr.alias("past")).collect()
# 09:10重新建立查询Expr，捕获09:10，past=True。
result = lf.select(pl.col("time").pldt.is_past().alias("past")).collect()
~~~

**共同含义与准备：**aware比真实时刻，naive比当地钟表，严格早晚；相等／源null均False。eager沿现有有效比较时按需取一次钟，空／全缺失不取；Expr在建立时捕获，即使未来为空／全null。UTC／aware不因此解析本机区，naive所需当地坐标按schema在准备层一次处理，不让worker逐行读钟或创建Python datetime。

<a id="pldt-j02"></a>

### J02 条件目标、缺失False和leap_bt_year逐行

**已定规则：**

1. 完整沿共同条件目标及已保存名称：目标None／NaN／NaT等非法缺失须检查，即使源行null也不能跳过；合法但不匹配为False，未知／空名称ValueError、非字符串／非法类型按已定角色。
2. 选择字段的合法范围与条件查询分开；例如is_month(13)是合法不匹配False，不能套replace(month=13)的范围规则。输入配对沿B02：真正标量广播、集合严格等长、按位置、无日期源扩行。
3. leap_bt_year支持整数标量或严格等长目标列，按既定非负闰年计数；原null输出对应缺失。布尔／整数返回不套日期NaT哨兵。
4. 只规范本库自有布尔查询的源null=False；原生比较、filter和其它完整继承方法保Polars原null语义。

**具体例子：**

```python
Pldt(["2024-01-01",None]).is_month(1) # [True,False]
x.is_month(13)                        # 合法不匹配False
x.is_month(None)                      # TypeError
x.leap_bt_year([2030,2020])            # 逐行非负闰年数
```

**性能影响：**源缺失mask和目标检查在原生融合，标量外准备；避免为了False先创建所有日期对象。

<a id="pldt-j03"></a>

### J03 diff是完整边界计数，不是Series.diff相邻差值

**已定规则：**

1. 完整边界计数放在x.pldt.diff／Series.pldt.diff／Expr.pldt.diff；Pldt.diff保Polars原生相邻差的n/null_behavior参数、返回和异常，不用要求用户改成pl.Series.diff(x)来绕开本库覆盖。Pddt现有边界diff不额外改名或新增命名空间。
2. 本库diff完整沿Pddt单位桶、负纪元、日历memo、absolute及inclusive处理顺序，标量或严格等长目标；数字目标仍是秒数角色，不是输出unit裸刻度。
3. aware按UTC边界，naive按无区坐标，混用错误；缺失传播为原生整数null，合法整数结果保完整int64，包括有效MIN，超范围才OverflowError。
4. 目标不压左侧单位，不临时构造Pldt；准备计划在循环外，固定单位直接tick、日历只按需解码，结果／绝对值／inclusive／溢出／有效位融合一次输出。

**具体例子：**

```python
x = Pldt([np.datetime64(2, "s")])
x.pldt.diff(1, "s")             # 原生Int64 Series：[1]，数字1表示1秒
x.pldt.diff(targets, "M", absolute=True, inclusive="both")
x.pldt.diff(x, "D", inclusive="neither")  # 零差为-1
x.diff(n=1)                     # Polars原生相邻差，返回原生Duration Series
expr = pl.col("time").pldt.diff(pl.col("target"), "D")  # pl.Expr
```

**边界与旧稿清理：**旧稿“覆盖diff，再用基类显式调用原生”的备选已清理；相邻时长与边界计数是两个公开职责。

**性能影响：**计划循环外，固定单位直接ticks、日历仅必要解码，结果/absolute/inclusive/溢出和有效位一次融合。

<a id="pldt-j04"></a>

### J04 isocalendar/timedf/utctimedf的表格与有符号年份

**已定规则：**

1. isocalendar按A03为Struct Series／Struct Expr，字段year/week/day顺序固定，各用UInt32及独立null；需要表格用原生unnest。ISO年0允许，真实负ISO年或超UInt32错误，不回绕；signed isoyear仍Int64，不为此删宽年日历能力。
2. timedf／utctimedf立即模式为无假索引的原生DataFrame，Expr为固定Struct；九字段顺序沿Pddt，tm_year Int64、tm_yday Int16，其余七字段Int8，源null整行缺失。不能按缺失改float或逐行造dict。
3. utctimedf的aware按真实UTC、naive不猜local且不移动字段，有效tm_isdst均0；直接计算，不先造UTC Pldt。timedf按H01的规范化时区表示给DST字段：naive及timezone.utc为-1；ZoneInfo按实际DST调整，零为0、合法非零含负DST为1；源null仍整行缺失。

**具体例子：**

```python
x.isocalendar() # A03已确认Struct Series，year/week/day三个字段；可struct.unnest成表
x.timedf()      # tm_year...tm_isdst九列
x.utctimedf()   # UTC字段，不能先构造UTC Pldt
# Expr模式返回固定Struct，再由用户unnest
```

**边界与旧稿清理：**ISO表及signed查询各按真实输出容量；当地表的规范化时区差异已由H01／J04规则确认，不为恢复来源身份增加侧表，不改变UTC表有效行tm_isdst=0。


**性能影响：**直接原生多列/Struct填充，共用一次当地解码，不先分别调用9个公共查询或造Python dict列表。

## K 数值、对象、字符串与语言输出

<a id="pldt-k01"></a>

### K01 数值导出、UTC/当地坐标和目标容量

**已定规则：**

1. toseconds／tomicroseconds／timestamp／toordinal保持Pddt坐标和数值规则：默认当地无区坐标，utc=True只对aware扣偏移；timestamp对naive按共享local解释，不能直接绑定Polars.dt.epoch。微秒主动导出按既定更早刻度，float只在完整整数后最终换算。
2. values_naive为当地无区原生Datetime Series／Expr，保unit及有效位，不包装Pldt、不自动转NumPy，不把UTC缓冲直接摘tz当当地。
3. 受保护to_numpy保原生writable=False／allow_copy=True并增加已批准allow_nat_collision=False；受保护to_pandas保use_pyarrow_extension_array=False及全部原生**kwargs，增加同一安全开关，返回pandas.Series而不是DatetimeIndex。原生参数及其异常完整沿Polars，不额外套本库数值／布尔限制；新增开关才按B02真布尔规则。
4. C04是A04一般不覆盖原生方法的明确后续窄例外：只加目标NaT冲突保护，不恢复任意兼容层。默认有效目标MIN与NaT碰撞报OverflowError；显式True只允许本次冲突丢失，其它容量／精度／缺失职责保持，Arrow独立有效位可保值时不强制破坏它。
5. 显式Arrow／Arrow-backed pandas按其原公开接口需要可选包，不把PyArrow或pandas变PLDT必需依赖；真实用户types_mapper等kwargs仍执行其原协议，按实际目标检查无损／冲突，不靠固定关键词猜所有返回表示。
6. np.asarray沿默认受保护出口，不接受allow_nat_collision隐式放宽；请求dtype／copy必须同时满足其原协议和已定有效位安全，不能以改object／换单位／丢mask求成功。不能表达的目标明确失败。普通pl.Series(x)后的原生出口由Polars负责，保值整数沿to_physical／Arrow，不新增重复to_series或to_pddt别名；Pddt(x)走C04已批来源适配。
7. NumPy普通日期数组不保存时区对象：aware来源按原生UTC刻度输出；需要当地无区坐标先用values_naive。这是明确目标表示的职责，不把数组无区误称来源本来naive。真实用户导出覆写按其协议，本库不承诺替全部第三方／自定义出口追加保护。

**明确接口：**`to_numpy(*, writable=False, allow_copy=True, allow_nat_collision=False)`；`to_pandas(*, use_pyarrow_extension_array=False, allow_nat_collision=False, **kwargs)`。原生kwargs和新增安全开关分别履职。

**具体例子：**

```python
x = Pldt(["1970-01-01 08:00"], tz="Asia/Shanghai")
x.toseconds()           # 原生Float64 Series：[28800.0]
x.toseconds(utc=True)   # 原生Float64 Series：[0.0]
x.tomicroseconds()      # 原生Int64 Series：[28800000000]
x.timestamp()           # 原生Float64 Series：[0.0]
array = x.to_numpy(allow_nat_collision=False)
# numpy.ndarray；writable／allow_copy仍沿原生职责。
# x.to_pandas(*, use_pyarrow_extension_array=False, allow_nat_collision=False, **kwargs)
# 返回pandas.Series；显式选择Arrow格式时按原接口需要相应可选包。
```

**边界与旧稿清理：**完整原生kwargs／NumPy协议的具体合法目标仍需实施验证；这是证明既定安全与成熟接口协议，不是允许执行时另挑会丢数据的行为。

**性能影响：**原生整数/浮点列直接输出，整数到f64最后一次；宽整数正确舍入算法复用，不经Python每行float。

<a id="pldt-k02"></a>

### K02 Python日期导出和ns/us明确损失

**已定规则：**

1. 显式datetime()沿Pddt目的：立即输出一维NumPy object数组中的Pydt，缺失为None而非要求pandas.NaT；最后一次截至us，保真实tz/fold，目标1-9999容量错误不得丢行或coerce。
2. date／time保持属性形式，输出原生Date／Time Series及对应Expr，Date按真实i32日容量checked，Time保原生本日ns；不为贴合Pddt对象外壳而丢Polars精度。
3. timetz为明确Python对象属性出口，立即输出一维object数组的标准time／None，保tz/fold、最终us；它及datetime()只限已有数据的eager职责，不伪造可移植的Python Object Expr。
4. 直接索引／item／to_list等完整原生操作保持A03的Polars标量合同；这些主动出口的us及年份限制不反过来缩窄普通PLDT计算，宽日期的date目标若不能容纳也须错误，而非null。

**对象类型明确：**不是所有出口都返回Pydt。只有显式datetime()的有效数组元素是Pydt；date／time保Polars原生Date／Time列，timetz的有效数组元素是标准库datetime.time。Pydt是完整日期时间类型，不代替纯日期或纯时钟类型。此处澄清既定类型，不改变A03原生取元素／to_list的返回协议。

**具体例子：**

```python
x.datetime()  # numpy.ndarray[object]，Pydt或None；主动最后截us
x.date        # pl.Series[Date]；容量不足OverflowError
x.time        # pl.Series[Time]，原生ns
x.timetz      # numpy.ndarray[object]，datetime.time或None；保tz/fold
pl.col("time").pldt.date  # pl.Expr，Date输出
pl.Series(x)[0]           # 原生datetime／None，沿Polars而非自造ns标量
```

**边界与旧稿清理：**显式Python对象出口与普通原生列出口职责不同；不把Pydt object数组当普通计算中转，也不改原生to_list。 最终Python时区对象依已确认H01／J04规则的规范化表示，不承诺恢复原生列已丢失的输入对象身份。

**性能影响：**只在主动对象出口建最终Python对象；整列计算/格式化不以这个出口中转。

<a id="pldt-k03"></a>

<a id="pldt-q04"></a>

### K03 ISO输出、strftime和Chrono语言差异

**已定规则：**

1. isoformat保Pddt既定sep="T"／timespec="auto"，完整单词及精确h、m/min、s、ms、us、ns缩写；不新增H/M。sep合法单个Unicode字符，粗timespec仅截显示不进位，保原ns和带冒号偏移。
2. ctime保标准英文、日号空格补位、不显示小数／时区；ISO和ctime可直接由准备后的当地字段、ns及真实偏移生成String Series／Expr，不造逐行Timestamp中转。

**格式输出例子：**

```python
x.isoformat(sep="T", timespec="ns")
x.isoformat(timespec="milliseconds")  # 只截显示
x.strftime("%Y-%m-%d %H:%M:%S.%f")
x.ctime()  # 标准英文，不显示小数／时区
```

#### K03.1 统一strftime格式及小数规则

**确定架构：本库strftime采用自有Rust格式核心＋必要的eager系统适配。**不承诺把当前Pydt／pandas每个版本／平台的偶然差异全变成相同字节。

1. 入口保持单个必填format字符串，空串合法；None／非字符串TypeError，无cfg／locale／旧fmt别名。普通文字原样输出，iso／iso:strict不作为特殊模式。
2. 原生Rust／Expr首批完整支持明确的无修饰符指令：日期%Y/%y/%m/%d；时钟%H/%I/%M/%S/%f；日历%j/%w/%u/%U/%W/%G/%V；时区%z/%Z；转义%%。准备时一次解析整个格式，按所需字段输出，保源null为String null，不产生临时Pldt／逐行Python datetime。
3. **三类共用的小数规则：**Pydt自身为us，%f固定六位；Pddt／Pldt按真实unit：ns为九位，us与ms均为六位（ms右补三零），Pddt独有s单位为六个零。%f只输出数字，不含小数点；位数按单位／schema确定，不按非零尾数猜。%.1f—%.9f输出小数点＋恰好对应位数，只截取不四舍五入、不进位；位数超过来源真实精度时右补零，不伪造有效数字、不改日期／unit／尾数。%.0f输出空字符串，连该指令自己的点一起省略；准备时直接消除该节点，没有其它小数指令时无需读取小数部分。普通字面量点不删除，%%f及%%.3f保持转义后的文字。

   仅支持%.0f到%.9f这十种明确写法；自有精度范围外／非法写法准备时报错，不交系统fallback吞成文字。全零小数的显式非零精度仍补满位数，不自行隐藏。没有%N扩展。

   已定示例：ns .123456789的%f=123456789、%.3f=.123、%.6f=.123456、%.9f=.123456789、%.0f为空；us .123456的%f=123456、%.9f=.123456000；ms .123的%f=123000、%.6f=.123000、%.9f=.123000000；s整秒的%f=000000、%.3f=.000。%H:%M:%S%.0f得到12:34:56，若另写普通点则该点保持。
4. 原生年份输出明确：%Y及%G对非负年最少四位，零为0000；负年为负号＋至少四位绝对值（-0001），正宽年直接完整数字（10000，不额外加正号），不先造datetime。这是新Pldt的统一原生输出定义；当前pandas3.0.6在小年可能不同，三类同步的小数扩展不自动改写Pydt／Pddt的其它年份格式行为。目标字段／整数安全仍checked。
5. 系统locale指令%a/%A/%b/%B/%p/%c/%x/%X，以及非自有小数指令的其它宽度／填充／E/O修饰符／平台扩展／未知指令，eager在准备时选系统适配；保平台结果或错误，不自建系统locale表，不用Configs／CLDR识别表替代LC_TIME。**由于新增自有小数语法，不能再把原格式不经处理直接交标准库。**必须一次编译统一格式计划，库自己的小数节点先按原unit／ns生成精确内容，再由标准库处理剩余完整系统语义；不事后替换已生成字符串，也不在数据失败后换后端试成功。混合格式如%A %H:%M:%S%.9f也必须遵守同一小数规则，不能因走系统路径退回6位或输出文字.9f。
6. 上述系统格式不进入普通原生Expr worker；在Expr准备时明确报不支持并提示eager或原生.dt.strftime，不用map_elements／每行Python回调。系统适配必须用Python日期载体时按1—9999容量，不能把宽年截回或转null求成功。自身原生数字格式不受该适配容量提前限制。
7. **同步范围：**三类strftime共同采用本条小数节点／准备规则，Pydt须新增对应自有入口及pyi说明，Pddt纳秒列%f由旧六位改九位。除此之外，Pydt／Pddt已有系统指令、格式参数、返回／缺失、原异常及真实子类／strftime覆写／__format__协议保持，不将新Pldt的Expr格式子集套给旧类，不自动扩大为改写所有旧格式或年份填充行为。Pldt其余原生格式按本方案规则。

**输出类型：**Pydt为str，Pddt为pandas.Index；Pldt eager为String Series，表达式为原生pl.Expr，执行后为String列；源null仍null。系统适配只提供eager，原生数字及自有小数格式支持Series／Expr。不返回Pldt日期类，不因格式化改变源日期／unit／ns。

**范围与成本：**三类小数规则已明确同步。提取最小共享Rust格式计划／小数节点，各类保目标容量与返回职责；不先把整列降us再补出ns，不事后字符串替换输出。单位、宽度、除数、补零和%.0f消除在准备边界确定，循环只做必要整数与字符串写出；九位比六位多输出三个字符，系统适配仍有必要Python成本。未正式测量，不宣称零开销或提速倍率，不新增pandas／Babel依赖。

**验收补充：**逐类覆盖s/ms/us/ns实际适用单位、%.0f—%.9f全部十种、全零／负纪元／不舍入／补零／非法精度／转义／重复指令和混合locale系统格式；保护Pddt Index及name／缺失、Pldt String及null／Expr、Pydt str及真实子类／__format__调用协议。新行为以本条独立预期验收，旧非小数平台格式作为回归控制；类型、docstring与例子同步。这里是后续验收要求，没有实现或运行新功能。

<a id="pldt-k04"></a>

### K04 语言名称、tzname和时区偏移输出

**已定规则：**

1. month_name／weekday_name复用已采用独立CLDR数据和locale规范化，默认英文、原locale／错误规则，返回原生String Series／Expr；Configs识别词表不用于生成语言输出，不恢复Babel或新维护一套表。
2. tzname按每行真实日期及当前原生规范化地区资料，区分冬夏；UTC／可表达固定区快路。输入已丢失的Python时区自定义显示名不能凭猜测恢复；本机CST不成为解析授权。
3. 偏移按真实时刻计算，返回类型／缺失沿自身既定职责；Python／Rust tzdb版本及代表历史差异记录，不承诺全部历史永久逐字相同。tzinfo对象类型与tm_isdst按已确认H01／J04规则，不从地区缩写推断另一种来源身份。

**具体例子：**

```python
x.month_name("zh_CN")
x.weekday_name("en_US")
x.tzname() # 每行真实日期区分EST/EDT
x.utcoffset_seconds() # 依原语义，不由缩写猜区
```

**边界与旧稿清理：**有限CLDR资料／locale一次准备，实际地区名称或偏移才访问地区数据。

**性能影响：**locale一次准备，有限编译表复用，不每行格式化再拆名称；地区tzname成本仅在实际需要时承担。

## L 元数据、复制、子类与容器生态

<a id="pldt-l01"></a>

### L01 列名、无Index/freq、排序标记与元数据

**已定规则：**

1. 列名为Polars字符串，默认继承来源；未提供／None沿已定来源或原生空名，不额外保存任意hashable name。日期变换保真实unit／tz／name／null，没有pandas Index/freq职责，不伪造它们。
2. 排序标记只在低成本可证明仍有效时保留，逐行乱序等不能继续标sorted；不能为保持标记额外全列扫描，未知时清除而非虚假承诺。
3. 普通列句柄与数据所有权沿B05；不因元数据平行给原生Frame附加索引或复制全部数据。

**具体例子：**

```python
x = Pldt(s, name="events")
y = x.to_next_month() # 保name/unit/tz/null
# 逐行乱序偏移后，不能继续标记全列sorted
# 不新增伪造freq属性/Index标签
```

**性能影响：**不验证不存在的freq，不为形式平行引入Index成本；正确sorted标志与可优化程度由真实运算决定。

<a id="pldt-l02"></a>

### L02 copy/deepcopy/pickle保存什么，Expr是否可移植

**已定规则：**

1. eager copy/deepcopy/pickle完整保日期tick与validity分离、unit／tz／name及合法业务状态；默认浅复制为独立同类外壳、安全共享数据及业务引用，深复制日期缓冲隔离并沿同一memo保别名／循环，不能用clone冒充物理deep。
2. 核心状态独立版本化，验证长度／有效位／单位／容量后恢复；业务dict／已设slots与核心分开，不导出缓存／owner或只因下划线删业务字段。默认恢复／copy不重跑业务初始化，真实用户copy／reduce／state协议及原异常保留。
3. 原生Series.clone等成熟操作仍沿其自身合同，不把它们全部改成业务deepcopy。不存在自有Expr包装类型，因此不提供PLDT特有Expr pickle／远程加载协议，也不禁止或包装原生pl.Expr的既有serialize/pickle；其安全／版本边界交Polars，见M04。
4. 不迁移旧Pddt或未发行PLDT草案；新Delta状态独立沿G01.N，不能因共用算法而混合两类codec。

**具体例子：**

```python
y = copy.copy(x)
z = copy.deepcopy(x)
r = pickle.loads(pickle.dumps(x))
# eager核心必须保ticks+validity+unit+tz+name
# Expr跨机恢复不能自动下载/执行任意插件
```

**边界与旧稿清理：**旧稿“禁止PLDT自身Expr pickle”的备选被删除：A02已确定没有该自有Expr类型。

**性能影响：**状态扫描/深复制只在对应入口；日期计算不逐行扫描业务属性。大型缓冲深复制必须真的发生，不能用clone冒称deep。

<a id="pldt-l03"></a>

### L03 业务子类与一次正常构造

**已定规则：**

1. 按PL02保有界真实Python子类eager新日期结果：精确Pldt直接出口；真实子类由库对整列发起一次正常构造，保new/init的实际合法返回和原异常，不先父类后子类、不逐行、不给业务必填参数猜值。
2. 自有直接方法及真实Pldt子类的.pldt入口共用准备与结果职责；普通pl.Series.pldt日期结果为Pldt，不凭业务字段猜来源类。已知no-op复用及copy/state按自身规则，不强行触发额外构造。
3. Expr始终原生pl.Expr，既没有业务Expr包装，也不在规划或worker中虚构Business构造／全列业务值校验。原生Frame取列或完整继承操作按其真实返回，不承诺恢复业务子类。
4. G03算术回调与此处新结果构造是不同协议，两者均不能静默略过；深复制／业务恢复独立沿L02。

**具体例子：**

```python
class Business(Pldt):
    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self.checked = True

y = Business(source).to_next_month()  # 自有日期结果：一次正常整列Business构造
expr = pl.col("time").pldt.to_next_month()  # pl.Expr；不调用Business构造
```

**边界与旧稿清理：**不采用无证据的首版封闭类来缩掉共同能力，也不保留“构建业务Expr包装”的冲突表述；仍须实施验证真实Polars构造及运行期修改协议。

**性能影响：**base类直接出口，业务回调成本仅在真实子类创建；不用为所有操作附加业务状态复制或逐行反射。

<a id="pldt-l04"></a>

### L04 容器筛选、比较、成员、重复与原生聚合的边界

**已定规则：**

1. 成熟Series容器操作完整继承Polars参数、广播、返回及原异常，不用__getattr__代理、批量包装或附加本库整数／bool清洗；某些操作返回普通Series或Python标量是A03允许的真实边界。
2. 自有日期功能与原生同名时守A04/F01：例如replace及日期round/ceil/floor/diff经.pldt，原生方法不改成双义入口。C04明确安全导出是后续窄例外，不能反过来删除其保护。
3. 原生比较／filter的null语义不套自有条件查询False；原生append/scatter等可变外壳操作保其真实职责，不声称Pldt是不可变Index。自有日期计算仍不修改来源，外部协议副作用按约定。
4. 不复制pandas整个Index生态，不为不存在的take/repeat等接口新增同义壳；已有对应Polars功能按常规用法使用。只有另有明确需求才另定覆写范围。

**具体例子：**

```python
x[0:2]                    # A03所定日期切片保Pldt／ns；其它原生操作按各自返回
x.filter(mask)
x.gather(indices)
x.diff(n=1)                # 原生相邻差
x.pldt.diff(targets, "D") # 本库完整边界计数
x.min()                    # 原生聚合标量职责，不强行包装Pldt
```

**性能影响：**避免额外参数清洗与无意义包装；原生聚合可保引擎优化，不因API统一而扫描一次再调用一次。

## M Expr规划、插件执行与延迟边界

<a id="pldt-m01"></a>

### M01 Expr输出schema、unit/tz和非法输入失败时机

**已定规则：**

1. 原生日期Expr按输入schema推导unit／tz；普通String共享解析按C02/D03明确目标，专用工厂按E02/E04/E05的已定默认与额外要求，不一律强迫unit，也不扫描第一批数据猜dtype。
2. 所有自有入口声明真实输出类型／长度职责，B02标量和等长列、G01具体Delta集合及跨chunk配对保持；空／null／容量错误不能改输出schema求成功。
3. 静态参数／格式／Configs/default错误在已定准备阶段发现，真实数据错误在执行时出现；原native错误及可靠位置按已采用错误架构E01-E32，不预造每行上下文，也不承诺未知原始文件行号。
4. D02快照时点、G03动态Expr拒绝及E01取钟工厂保持。查询参考已按J01参考时刻规则确定；聚合Expr参数角色已按M03逻辑标量规则确认。

**具体例子：**

```python
e = pl.col("text").pldt.parse(unit="ns", tz="UTC")
lf.select(e).collect_schema() # 不collect，不扫描文本
# 错dtype/参数尽早失败；数据错误到collect时报
```

**性能影响：**规则在规划时准备，避免每batch重解析格式/unit。错误冷路不预造每行上下文；准确全局位置只在实际有映射时使用。

<a id="pldt-m02"></a>

### M02 官方Rust插件、Arrow边界和无GIL数据契约

**已定规则：**

1. 使用官方Rust表达式插件及公开Polars／Arrow FFI，普通worker只接受经准备的原生字段／缓冲／资料，不携带需要GIL的Configs／PyDateTime／任意PyObject，不以map_elements或私有_s ABI代替。G03立即动态回调是独立明确路径。
2. 不另建线程池与Polars争用；借用必须保owner／release，使用成熟所有权组件；最小纯Rust算法由Pydt/Pddt/PLDT共同使用，不复制新日历引擎。
3. 发行仍为同一rstimes Python包。主native合并或同包独立plugin目标属于有界实现选择，以最小真实wheel安装、ABI和体积／导入／性能证据决定，不让用户在未验证的普通编译布局之间投票。
4. 尚未编译过PLDT插件；N02兼容性规则已确定Polars2.0.0下限及32位置目标，必须实际验证ABI及安装／执行，不能用上游依赖版本看似相容冒充本项目构建成功。

**具体例子：**

```python
# 已定执行边界，尚未实现：
# Python准备 -> Rust typed column/kwargs -> 共享最小算法
# -> 原生Series/Expr结果；不map_elements调用Python
# kwargs仅受检基本数据，不把Configs/PyDateTime指针带到worker
```

**边界与旧稿清理：**若有证据表明必须改变已定公开能力、强依赖或发行布局，再报告真正取舍；普通低层接线不能不断新增用户审批。

**性能影响：**可能避免Python回调并允许引擎并行，但增加编译/产物成本；当前没做构建和正式计时，不能声称已经可安装或必定比现有Pddt快。

<a id="pldt-m03"></a>

<a id="pldt-q03"></a>

### M03 逐元素、infer、分组、流式与可靠错误位置

**已定规则：**

1. 按真实操作声明elementwise／长度／排序／确定性；普通独立日历可由引擎分块、并行或流式，infer按完整逻辑列／组原序而不是物理batch。允许执行引擎物化必要列／组，不在Python偷偷collect整表。
2. group_by／over等以调用位置的逻辑组和顺序为域；不自动将全表具体目标向量按标签重排或按batch重置，明确集合仍须与当前逻辑来源等长。原生Expr目标列按引擎配对，不能由长度1猜出标量。
3. 错误只报告可靠入口及实际可映射的位置；本库不返回部分日期结果，但不承诺外部流式sink已写入的数据也事务回滚。GPU／分布式不是普通CPU插件自动支持范围。
4. E01工厂的取值快照保持；is_past/is_future按已确认J01参考时刻规则在创建查询Expr时取得并携带原生整数参考，各worker／组共用，不在collect重新取钟，不新增全局可变时间缓存。

**具体例子：**

```python
lf.with_columns(pl.col("t").pldt.to_next_month())
# 自有逐行日期方法按已确认B02保持日期源行数
# ambiguous="infer"必须完整逻辑序列/组；不能跨batch猜
# 报错只写可靠位置，如batch item 2，不伪造源文件第2行
```



**性能影响：**平常路径不为少数状态运算禁用并行。组/窗口验证按实际接口，跨chunk不依赖物理分块；不得自建全局可变状态补齐批次。

#### M03.1 逻辑标量Expr与严格集合

**具体例子（已定Pldt接口，未实施）：**日期源为2024-01-01、2024-01-10、2024-01-20，单位us，days为整数列[1,2,3]。

~~~python
# max是逻辑标量3，三行都加3天。
expr = pl.col("time").pldt.add(days=pl.col("days").max())
# -> Datetime(us)列：2024-01-04、2024-01-13、2024-01-23

# 普通列逐行[1,2,3]，不是全列取max。
expr = pl.col("time").pldt.add(days=pl.col("days"))
# -> Datetime(us)列：2024-01-02、2024-01-12、2024-01-23

# head(1)仍为长度1列，不能冒充标量；日期源三行时执行报长度错误。
expr = pl.col("time").pldt.add(days=pl.col("days").head(1))

# 分组原序A,A,B，各组max为2、3；over恢复到原行位置。
expr = pl.col("time").pldt.add(days=pl.col("days").max()).over("group")
# -> 2024-01-03、2024-01-12、2024-01-23
~~~

**最终规则：**像Polars常规表达式一样，真正原生逻辑标量可以广播，包括类型合法的聚合、first/get等标量操作及保标量的组合／alias／cast；明确列即使实际长度1仍必须与当前日期源严格等长。按当前逻辑域／组一次求值和复用，不提前collect，不按名称、字符串计划或首个结果猜角色，不扩大日期源。

输入形状与类型分别检查：pl.lit(3)是合法整数标量，pl.lit(Series([3]))仍是具体列；pl.lit([3])虽是List标量也不是days要求的整数，mean()得到float同样不因只有一个值就合法。只作用于已批准可标量／逐行的参数，unit/freq/tz/strict/fsp精度等全局单值职责不变。

**技术与验收边界：**公开角色识别已有依据，尚未构建Pldt插件验证角色传递、分组、chunk、过滤和流式；不得把这36次原生观察写成Pldt PASS。returns_scalar插件选项标注函数输出职责，不能充当每个输入的角色。实施须用公开元数据和原生角色标记贯穿准备／执行，证明标量只准备一次、列严格配对、日期源不扩行以及空／null／类型／owner安全；若公开接线出现真实限制，保存证据再决定，不静默放宽为长度1广播或取消已批准聚合能力。

**输出与跨类对照：**日期Expr仍为原生pl.Expr，select／with_columns执行后得到Datetime列；over按原生位置映射，group_by.agg的外层List／表格职责完整沿Polars。eager Pldt仍返回Pldt，真正标量与等长列规则不变。Pydt是单个日期，无Expr／分组；Pddt是立即整列，用户先算出合法标量再传入，不增加Polars Expr输入。共同日期数学不变，Pldt把聚合参数求值留在原生执行计划。

**性能影响：**每个Expr参数在准备层识别角色；标量在当前逻辑域一次求值、Rust循环复用一个值，不在每行执行Python或聚合，也不强制构建N个Python对象。普通列保持原生缓冲／有效位和等长循环，聚合本身的计算仍必要。不要求用户先显式展开为等长列；实际执行成本须实测，本项没有性能倍率或插件成绩。

公开Expr.meta.is_scalar()在固定Polars2.0.0／2.1.0中已有角色核查，但源码标为unstable；仅在集中准备层使用，最低及代表版本必须验证真实插件传递，不读私有计划字符串。

<a id="pldt-m04"></a>

### M04 延迟计划的序列化、安全和跨版本执行

**已定规则：**

1. 没有自有Expr包装，不另建计划DSL、跨版本迁移、远程插件下载或PLDT特有计划pickle；原生Expr的clone／serialize等完整沿Polars，不能额外禁止既有功能。
2. 本库只通过自身受控的安装路径／符号和受检kwargs构建插件调用，不新增任意用户path/symbol执行入口。恢复原生计划须已有兼容安装，其安全／版本前提按上游，不承诺跨机／跨版本永久可执行。
3. 本库自有kwargs／快照有版本和数据边界，未知版本在相应自有边界拒绝；eager数据状态沿L02独立处理，不把可信pickle当不可信通用安全格式，也不自动替用户运行网络修复。

**具体例子：**

```python
expr = pl.col("text").pldt.parse(unit="ns")
# 同环境clone可复用；跨机恢复须已安装兼容库
# 不自动下载插件，不接受任意用户path/symbol执行
```

**边界与旧稿清理：**“不自建计划协议”与“禁用Polars自己的序列化”不是同一件事；旧备选中的混淆已删除。

**性能影响：**复用固定参数和不可变共享数据，不为所有调用扫描插件路径/做网络探测。安全验证在准备边界。

## N 共享修改、发行目标与整体验收

<a id="pldt-n01"></a>

### N01 共享小内核与现有类批准修改

**已定规则：**

1. 只抽实际使用的checked公历、日期字段变换、单位／精度、周期边界／取整、diff桶及格式字段等最小函数／原生准备结构；各类保自己的容量、missing、owner、元数据及出口，不用一堆开关的大执行器替代。
2. 不复制整个rust/pddt再改名，不把Pydt变一行数组，不把Pddt的NaT pack/freq/pandas状态迁给PLDT；除本条明确纳入的已批准变化外，共享改动保持现有Delta/Parser/Pydt/Pddt公开行为、真实协议和性能。
3. 后续范围逐条引用D01.O1-O4四项已批准优化、C04 Pddt的真实Polars日期有效MIN／validity导入修正、E04 Pddt.combine空／全null时钟区元数据、D04 Pddt.strptime目标tz、E05 Pddt.fromisoformat／date_range目标tz及必要策略、F01 Pddt字段replace命名空间、G01.N完整Delta纳秒及G03 PLDT载体；不遗漏实际共用该适配的入口，不借PLDT重启已经完成的旧修改。
4. 优化按完整调用的有效收益、安全及行为验收采用；不合适的方向记录后转其它项，不因局部问题停止整个项目。尚未批准的新公开行为或显著依赖范围变化仍须提出。
5. ISO／ctime共享规则保持；K03格式规则及三类strftime小数扩展已经批准。共享原生格式准备／小数输出节点，Pydt／Pddt新增%.nf支持并按单位调整%f；其余系统格式能力、返回、缺失和真实外部协议保持，不因新Pldt的Expr子集而缩掉旧类能力。

**具体例子：**

```python
# 共享：checked Gregorian、字段变换、边界桶、取整、格式字段
# 适配：Pddt NaT + pandas出口 / PLDT bitmap + Series出口
# 保留：现有Delta/Parser/Pydt/Pddt公开行为和动态协议
```

**边界与旧稿清理：**普通函数提取位置属于实施判断，不需再逐文件投票；接口、容量和可选依赖边界不许借提取改掉。

**性能影响：**优先减少整体转码/缓冲复制/多次解码，次要微优化待端到端测量。纯算法抽取本身也要证明没退化，不先宣称必快。

<a id="pldt-n02"></a>

<a id="pldt-q05"></a>

### N02 可选依赖、插件与32位置兼容目标

**依赖基线：**维持当前b2默认／可选架构，不因PLDT新增强制pandas、dateutil、PyArrow或Babel。确切Rust插件依赖在真实最小wheel证明相容后锁定，不把调查到的上游版本直接当作已构建结论。

| 依赖 | 安装角色／版本 |
|---|---|
| Python | 普通64位GIL CPython3.12—3.15 |
| NumPy | 默认依赖，>=2.5.3 |
| tzdata | Windows默认依赖，>=2026.5；其它系统按现有地区数据职责 |
| python-dateutil | 可选，>=2.9；相关显式集成入口按现有能力准备 |
| pandas | 可选；Pddt必需，普通PLDT不必需；2.x最低2.3.3，3.x主线3.0.6；Py3.15或Windows ARM64须>=3.0.6，pandas2仅21适用位置 |
| Polars | 可选，PLDT必需；>=2.0.0下限目标，固定2.0.0／2.1.0代表验证 |
| PyArrow | 仅显式Arrow对象／Arrow-backed导出按原公开接口需要；不强依赖 |
| Babel | 不恢复此依赖 |

**依赖与兼容性规则：**

1. 保留Polars>=2.0.0作为新PLDT下限目标，至少以固定2.0.0／2.1.0验证同一实际产品wheel的插件加载、eager与Lazy执行；先做最小真实安装通路，再冻结相容的Rust依赖与全矩阵配置。不因本机构建方便自行提高下限，不把Python版本相近或导入成功当作插件ABI证明，也不承诺所有未来版本都已验证。
2. 首发兼容性目标为普通64位GIL CPython3.12／3.13／3.14／3.15 × 下列8类平台组合，共32位置；不纳入32位、PyPy或free-threaded。现行ABI对应wheel布局下为32wheel＋完整sdist，内部同包插件库不因此另发一套Python包。

| 平台／架构／运行库 | CP312 | CP313 | CP314 | CP315 |
|---|---|---|---|---|
| macOS ARM64 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |
| macOS Intel x86_64 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |
| Windows x86_64 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |
| Windows ARM64 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |
| Linux x86_64／glibc>=2.28 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |
| Linux ARM64／glibc>=2.28 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |
| Linux x86_64／musl>=1.2 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |
| Linux ARM64／musl>=1.2 | 目标待验 | 目标待验 | 目标待验 | 目标待验 |

3. 各位置安装真实wheel后验证公共能力、dtype／单位／时区、null／chunk、ownership和错误传播及真实Expr collect；代表sdist独立重建。macOS两架构、Linux两libc分别构建／运行，复用现有CI，不用改wheel标签或旧运行成绩代替。具体版本／平台遇到客观障碍时保留证据并提出影响，不静默缩矩阵。
4. 同一rstimes包提供可选Polars能力；无Polars时Delta／Parser／Pydt仍可用。有Polars无pandas时普通PLDT可用，已批准特殊pandas委托另按需安装；Pddt仍按现有pandas兼容边界，不把插件要求转给旧类。
5. 正常同包单native或独立plugin目标由实际安装、体积／导入／安全和性能证据选择，不另作用户投票；另发插件包、引入强依赖、改变公开加载方式或缩兼容范围才是新的实质选择。新tag／版本／提交／推送／发布授权由正式实施发行计划另定，本次确认不授予这些动作。

**接口示例（已定设计，尚未实现）：**Pldt(["2024-01-15"], unit="us").to_next_month()返回Pldt、日期2024-02-15／Datetime(us)；pl.col("time").pldt.to_next_month()返回原生pl.Expr，实际Lazy select／collect后得到pl.DataFrame。两版代表须执行完整链，不只创建Expr。

**性能影响：**报告新增编译时间、包体积、首次加载和热调用；类型／能力／插件路径在适当入口准备复用，热循环不反复import／探测版本／扫描动态库。没有新插件测量，不宣称零成本或具体倍率。

<a id="pldt-n03"></a>

### N03 测试、错误、文档与采用证据怎样覆盖完整平行能力

**已定规则：**

1. 每个自有入口及参数角色用最终决定和独立正确预期保护，核对eager／Expr结果与schema、unit／tz／name／null、source不变、容量、ns／宽年／有效MIN、chunk／stride／owner、DST、真实子类和外部协议；不能只比较两个共享错误的入口相等。
2. 保留旧正确Parser和其它现有类样本；D01.O1-O4逐项映射原生字符串／Unicode／长文本、真实回调修改Configs后的读取顺序、快照、可写别名及所有权，不以PLDT新增测试替代旧类保护。
3. 错误完整沿已采用E01-E32及C23：实际公开入口／参数／可靠位置／安全预览，冷路才建上下文，原外部异常／严重错误保持。成熟完整委托按其协议验收，不重审整个Polars。Python准备和eager自有错误按参数角色用既定TypeError／ValueError／OverflowError及领域错误；数据错误经Polars执行边界报告，不承诺所有Expr数据错误都与eager具有相同Python异常类。只写可可靠映射的行／batch位置，不伪造过滤前文件行号；完整原生委托保其原异常。
4. 所有公开pyi及真实docstring/type annotation、英文Args/Returns/必要Example、指南与调用demo同步并运行有效例子；wheel/sdist/实际加载native及plugin和功能／性能证据必须绑定同一交付身份。
5. 研究观察含预期错误／局限，不转记产品PASS、旧跨平台/性能成绩或例外。未测能力明确未知，量化性能口径统一按N04。
6. 实施采用时同步实际受影响的根AGENTS断言／采用事实，特别是G01.N的新Delta精度与状态；本轮只记录讨论，不提前改变当前已采用断言或用旧us描述约束新批准能力。原有四demo及实际新增调用示例按影响同步，不启动GitHub Pages等其它项目。

**具体例子：**

```python
expected_ticks = [1709164800000000] # 2024-02-29独立答案
# 同时查eager/Expr、dtype/unit/tz/name/null/source未改
# 不仅比较Pldt==Pddt，避免两端同源错误一起通过
```

**性能影响：**校验与日志仅失败才建上下文；测试重用现成数据和运行器，不开发新通用框架。文档必须验证具体例子，不只数docstring。

<a id="pldt-n04"></a>

<a id="pldt-q06"></a>

### N04 72小时预算、量化性能与迭代验收

**N04.1 总预算：72个有效小时（4320分钟）。**包含正式规划、实施、测试、构建、校准／预试／正式性能、文档及交付；并行不重复计，普通CI／工具等待计入，只有明确暂停／必要纯用户等待单列。旧Goal余额不沿用。阶段为软目标，完整计划应按真实成果拆成通常不超过2小时的执行单元：

| 阶段 | 小时 | 目标／必要证据 |
|---|---:|---|
| 正式计划、范围及本轮起点冻结 | 2 | 全部条款／入口映射、当前采用产物、必要与观察场景、权限边界 |
| 最小真实wheel及Polars插件通路 | 4 | 两个Polars代表真实安装／ABI／eager／Lazy；提前暴露平台／依赖风险 |
| Delta纳秒与现有类批准共享调整 | 12 | G01.N、D01.O1—O4及N01指向修改；独立预期／旧正确样本／协议保护 |
| PLDT完整功能，Series与Expr | 20 | 构造／工厂／日期运算／查询／时区／导出／状态及原生生态，按依赖薄片迭代 |
| 完整功能、32位置及可用基准B0 | 8 | 实际wheel／代表sdist、完整功能与已有能力保护、类型／文档；本轮B0固定 |
| 持续优化与最终正式性能 | 18 | 一条主线累计可靠收益；开发定向测量、最后冻结产物及双轮完整验收 |
| 最终同步、交付与核查 | 4 | 最终源码／产物／typing／指南／demo与证据同身份、慢项和缺口报告 |
| 未分配修复余量 | 4 | 有依据调配；不重复计算成额外优化或自动延长总额 |
| 合计 | 72 | 旧项目时间、发布或额外独立审计不隐含加入 |

首次完整可用基准目标在T+46—48小时附近，不构成可以降低门槛的硬截止；风险主要为实际插件ABI、无GIL共享边界、Delta跨类精度和32位置构建。72小时是已批准总预算，不保证必然通过。正式GitHub／PyPI发行及版本号另列授权，不由本项默许；必要跨平台CI构建与安装验收属于项目交付。

**N04.2 对照、逐项保护与必要／争取目标。**

1. 本项目S0为正式启动时核验的当前采用0.2.0b2，不与历史同名基准混用；B0为全部新合同功能／安全达标后的本项目首个可用基准；B*为最近已验证的主线最佳版。保护同语义的完整公开调用，不假造旧包没有的ns／新PLDT成绩。
2. Delta／Parser／Configs使用路径／Pydt／Pddt仍可等价比较的正常必要场景，逐项相对S0中位及保守耗时增加均<=5%。访问形式变化可明确映射，不能因新接口换名或结果变慢而删保护项；真正新增工作按事前语义分类单列，不拿旧错误／少做工作作速度对照。
3. B0之后每次优化晋级，受影响项同时相对B0与上一B*保护<=5%，最终仍保S0适用项；防止多轮累积回退。最终不要求对所有历史候选再跑全矩阵，保相邻晋级证据与最终S0／B0验证。
4. 每次性能优化采用须行为／安全和保护通过，并有双轮证据支持的可辨别单场景／成本族或预定组合收益；无收益的纯优化不为代码变化保留。必要功能调整不冒称优化收益。继续在一条主线上累计，不交一堆无法合并的候选。
5. 最终PLDT核心组合相对B0争取>=1.10倍，条件允许继续冲击1.20倍；均为可选争取目标，不是删除功能或否决可靠小收益的理由。未达真实报告；不能用组合提速抵消任何必要单项失败。1.10倍是约9.09%耗时减少，不混称耗时减少10%。

**N04.3 正式采样、精度和稳定性。**本项目明确采用现有可复用口径，而非沿用旧Goal授权：

- 每必要场景main／independent双轮；每轮9真实进程周期、每周期12完整紧邻配对，AB／BA各6；两轮合计216对／36真实worker，不是每轮216，也不把内部n次调用算独立实验。
- 12短／6长控制；两方归一耗时及倍率精度均<=3%。每轮按既有连续周期划三组，各3周期；组间、顺序及跨轮稳定性均<=5%。保守倍率沿既有本轮中位与三组倍率取最小的实现，冻结公式／代码身份，不冒称置信区间或事后换估计量。
- 两轮中位与保守耗时保护都须通过；R=T对照/T新版，5%对应R>=1/1.05，按原始数值判断。覆盖／质量／稳定性／性能分别报告；精度或稳定性不足是INCONCLUSIVE，稳定超保护是FAIL，均不算必要PASS。
- 校准／有界代表预试／最终参数冻结／正式采集按Noise执行。共同n、完整组跨度按最快及最慢实际工作量校准；10／20／40ms为候选短窗，单次完整大列调用已超过窗口时取n=1而不切小输入。准备样本不混正式成绩，所有合格快慢与负面保留。
- 单线程沿适用既有质量接口；真实Polars内部多线程／必要等待的完整调用采用端到端原始墙钟模型，线程／进程CPU只诊断，不用单线程off-CPU公式拒收自身等待、不扣减或修正耗时。按真实调用链分类，不因入参是Polars就一概免掉单线程检查。

**N04.4 必要覆盖、环境与汇总。**

功能须覆盖每个自有入口及参数职责，性能按共享调用链／成本族列冻结代表，不把每个功能样本都膨胀成正式性能项，也不先规定任意少量上限。覆盖输入构造／工厂、文本解析、字段／日历变换、Delta算术、时区／DST、查询／diff、单位／导出／格式以及完整Lazy管线；已批准D01四项与Delta状态／比较／双向／批量等全部映射。空／缺失／错误路径主要做独立功能验证，真实高频空／全null代表可以计性能。

主要列规模1／10／1000／100000，百万行为有具体信息增益时的吞吐／内存观察；按成本族选代表，不展开所有单位×时区×规模笛卡尔积。区分标量／逐行、ms/us/ns、naive／UTC／固定偏移／地区及chunk／null。Expr建立成本单列观察，必要执行成绩计完整select／collect和约定结果物化，不能只计计划建立。

本机严格性能主环境为同一CPython3.13、NumPy2.5.3及固定Polars2.0.0／pandas3.0.6所需组合；同样产物在Polars2.1.0与适用pandas2.3.3的受影响路径作分别固定依赖的保护验证。每次配对依赖版本相同，不把Polars2.0对2.1差异算本库收益。32位置以真实GitHub CI做功能／构建／安装，不将共享runner抖动包装为全部平台5%严格性能证明。

PLDT核心组合在计时前按上述八个不重叠成本族分组，族内场景等权几何平均，再对族等权；每个场景只归一族，采样量／行数不改变权重。旧四类保护分别报告，不用大量新PLDT项稀释旧回退。原生Polars及Pddt同义完整调用另作参考，不硬要求全胜、不将不同能力混进B0优化成绩。所有慢项含相对与绝对耗时都列出。

首次import／插件加载、wheel体积、构建时间和峰值内存事前列为独立观察，不混进热组合或虚构普遍5%指标；依赖隔离、泄漏／owner／释放安全仍是必须。若实测暴露明显资源问题，作为具体质量风险处理，不因观察身份忽略。

**N04.5 快速迭代、有限质量调整与停止。**

- 复用当前runner／质量／统计／恢复接口。测量接线软目标30分钟，超出立即自查信息收益和更直接路径；Polars插件产品实现不误记为计时工具维护。
- 初始校准／预试有预算和固定判据，先核可测性与正式采集完成成本。正式冻结后最多预设两批问题项质量调整，每批准备验证<=15分钟，限既有预热／候选10→20→40ms及按实际量校准跨度，不改必要覆盖、216／36、估计量或3%／5%／5%。单次工作量超过40ms不切小。固定三组统计预试验证准备质量，不另添两次小样本原始极差都<=5%的更严硬门槛。新代码确需重校准的常规准备与这两批追加分别记账，不能改名产物刷新同一问题已用调整次数。
- 只有质量证据支持改善才冻结问题集合并完整重采；新完整结果无论好坏整项替换，旧负面保留，其他项只按Noise同产物／同条件规则复用。稳定速度失败先修产品或回退，不靠重测寻胜。
- 开发优化方向先用有限定向验证筛选；约60—90分钟仍无可辨别收益／新证据时停该方向，记录后转下项。普通薄片合并前做相应功能／性能检查，正式晋级按必要双轮证据；不每改一行就全矩阵，也不把快速开发观察当最终验收。
- 每30有效分钟核对最终决定／正式计划／实际成果／偏离／余额，明确自问：当前条款和入口是什么？新证据是什么？是否重复无效工作或扩范围？是否损害语义／安全／逐项保护？余量能否容纳未完必要验收和交付？下一有限动作及纠偏是什么？步骤预计或实际超时即时自查，不等半小时；迟延如实记。
- 单方向失败回退该方向并继续其它项，不据此停止整项目。基础插件或平台阻碍保存具体证据，继续无关已授权工作；实质范围／质量／模型变更再提出，不自动删功能／平台或降门槛。剩余预算不足完成下一单元及必要收尾时不启动，预算结束保存真实缺口，不自动加时。最后4小时交付时间要保护，未用修复余量在必要验收可完成时可有据调配。

**整体验收标准：**全部最终行为／安全／类型文档／实际wheel与sdist／32位置必要项通过；最终产物的全部必要性能PASS且新旧同义保护达标；源码、加载native／plugin、测试和性能身份一致；负面、慢项、未采用优化和预算／过程偏差完整保存。1.10倍／1.20倍未达不等于功能失败，必要FAIL／INC不因总体快或预算到点自动通过。实施与发行授权分别明确。

<a id="pldt-source-map"></a>

## 附录A 完整来源与决定去向

下表证明原60主项全部有唯一功能归属；关联收口规则已直接归入正文，不需要将旧Q章节叠加阅读。原讨论的身份／运行观察／作者意见在冻结原件和原证据中保留，不作新实现验收。

| 原项 | 最终唯一正文 |
|---|---|
| A01 | [A01 Pldt真实Series子类与原生执行](#pldt-a01) |
| A02 | [A02 立即Series与原生Expr／LazyFrame的统一日期接口](#pldt-a02) |
| A03 | [A03 日期、查询、表格与单元素返回](#pldt-a03) |
| A04 | [A04 类名、导入、命名空间及一次加载注册](#pldt-a04) |
| B01 | [B01 一维来源与Date/Datetime/Time准入](#pldt-b01) |
| B02 | [B02 标量广播、逐行参数、真布尔与整数规则](#pldt-b02) |
| B03 | [B03 NumPy/pandas/Polars/Arrow之间的真实类型与可选依赖](#pldt-b03) |
| B04 | [B04 空列、全null、缺失文本和独立default](#pldt-b04) |
| B05 | [B05 输入借用、copy和对外Series是否暴露可变外壳](#pldt-b05) |
| C01 | [C01 原生ms/us/ns与不支持秒单位的边界](#pldt-c01) |
| C02 | [C02 初次单位选择与Expr在读数据前必须确定dtype](#pldt-c02) |
| C03 | [C03 固定单位、无损构造与主动as_unit降精度](#pldt-c03) |
| C04 | [C04 Polars独立有效位与完整int64值域，以及跨NaT生态的无损转换](#pldt-c04) |
| C05 | [C05 零年/负年/宽年与Polars日历操作容量](#pldt-c05) |
| C06 | [C06 纳秒尾数与小数字段替换的共同含义](#pldt-c06) |
| D01 | [D01 共享Rust Parser需要抽出的真正边界](#pldt-d01) |
| D02 | [D02 Configs/default和格式资料在Expr中的快照时点](#pldt-d02) |
| D03 | [D03 带时区文本、混合来源与Expr输出时区必须预知](#pldt-d03) |
| D04 | [D04 strptime的格式语言、Configs和系统locale](#pldt-d04) |
| E01 | [E01 now/today/utcnow的取钟和Expr时点](#pldt-e01) |
| E02 | [E02 四数值工厂的秒坐标、真实时间戳和微秒整数](#pldt-e02) |
| E03 | [E03 fromdate/fromdatetime/fromdatetime64来源职责](#pldt-e03) |
| E04 | [E04 fromordinal/fromisocalendar/fromdayofyear及combine](#pldt-e04) |
| E05 | [E05 fromisoformat和date_range](#pldt-e05) |
| F01 | [F01 严格replace与只收合法字段意图的to_datetime/date/time](#pldt-f01) |
| F02 | [F02 年季月周日移动和全部便利别名](#pldt-f02) |
| F03 | [F03 add/sub的日历顺序、逐行量和精度抵消](#pldt-f03) |
| F04 | [F04 first/last/start/end/normalize与四个查询](#pldt-f04) |
| G01 | [G01 Delta与PLDT整列算术的归属和字段保真](#pldt-g01) |
| G02 | [G02 固定时长、日期相减和Duration结果](#pldt-g02) |
| G03 | [G03 外部算符、子类回调和不支持的DateOffset](#pldt-g03) |
| H01 | [H01 时区类型、固定偏移、本机区和数据库边界](#pldt-h01) |
| H02 | [H02 附区、转换、去区以及None的逐入口含义](#pldt-h02) |
| H03 | [H03 ambiguous／nonexistent完整词汇与职责](#pldt-h03) |
| H04 | [H04 infer必须保原序、跨chunk和真实候选](#pldt-h04) |
| H05 | [H05 不存在时间的最近边界与统一timedelta](#pldt-h05) |
| H06 | [H06 自动日期操作与普通时区快捷路径](#pldt-h06) |
| I01 | [I01 round/ceil/floor保共同频率和取偶规则](#pldt-i01) |
| I02 | [I02 Snap的名称、最近起点和真实等距取晚](#pldt-i02) |
| I03 | [I03 fsp按单个precision截位，与unit转换分清](#pldt-i03) |
| J01 | [J01 全类日历查询、属性编号与返回dtype](#pldt-j01) |
| J02 | [J02 条件目标、缺失False和leap_bt_year逐行](#pldt-j02) |
| J03 | [J03 diff是完整边界计数，不是Series.diff相邻差值](#pldt-j03) |
| J04 | [J04 isocalendar/timedf/utctimedf的表格与有符号年份](#pldt-j04) |
| K01 | [K01 数值导出、UTC/当地坐标和目标容量](#pldt-k01) |
| K02 | [K02 Python日期导出和ns/us明确损失](#pldt-k02) |
| K03 | [K03 ISO输出、strftime和Chrono语言差异](#pldt-k03) |
| K04 | [K04 语言名称、tzname和时区偏移输出](#pldt-k04) |
| L01 | [L01 列名、无Index/freq、排序标记与元数据](#pldt-l01) |
| L02 | [L02 copy/deepcopy/pickle保存什么，Expr是否可移植](#pldt-l02) |
| L03 | [L03 业务子类与一次正常构造](#pldt-l03) |
| L04 | [L04 容器筛选、比较、成员、重复与原生聚合的边界](#pldt-l04) |
| M01 | [M01 Expr输出schema、unit/tz和非法输入失败时机](#pldt-m01) |
| M02 | [M02 官方Rust插件、Arrow边界和无GIL数据契约](#pldt-m02) |
| M03 | [M03 逐元素、infer、分组、流式与可靠错误位置](#pldt-m03) |
| M04 | [M04 延迟计划的序列化、安全和跨版本执行](#pldt-m04) |
| N01 | [N01 共享小内核与现有类批准修改](#pldt-n01) |
| N02 | [N02 可选依赖、插件与32位置兼容目标](#pldt-n02) |
| N03 | [N03 测试、错误、文档与采用证据怎样覆盖完整平行能力](#pldt-n03) |
| N04 | [N04 72小时预算、量化性能与迭代验收](#pldt-n04) |

| 关联决定 | 最终归属 |
|---|---|
| PL-Q01 | H01规范化时区、J04当地／UTC表，K02/K04使用同一规则 |
| PL-Q02 | J01参考时刻，M03执行域 |
| PL-Q03 | M03逻辑标量，B02严格集合规则 |
| PL-Q04 | K03完整输出格式，含Pydt／Pddt同步小数节点 |
| PL-Q05 | N02最低Polars、真实插件及32位置 |
| PL-Q06 | N04预算、性能、有限调整及自查／退出 |
| D01.O1—O4 | D01四个已批准优化方向；N01／N03／N04保护与验收 |
| G01.N | G01内部GN01—GN13及G03 |
| U1 | GN04独立字段merge，GN05应用到日期；两者不混 |
| U2 | GN07普通NumPy纳秒标量左方向 |
| U3 | G03整列／逐行真实回调，M03原生执行边界 |

| 原Delta来源板块 | 本文件归属 |
|---|---|
| M01 已确认合同和实施边界 | GN01 |
| M02 统一选择的技术路线及选择理由 | GN02 |
| M03 新原生值与公开参数 | GN03 |
| M04 唯一精确准备、规范化和值运算 | GN04 |
| M05 精确日历核、精度投影和时区分工 | GN05 |
| M06 所有日期类与外部操作数矩阵 | GN06 |
| M07 NumPy路线：读取、原有合同和U2新增范围 | GN07 |
| M08 批量、Pddt、Pldt和Expr执行 | GN08 |
| M09 to_timedelta的三类精度与真实锚点 | GN09 |
| M10 状态v2、复制、接线、错误和文档 | GN10 |
| M11 共享模块、完整入口和邻接保护 | GN11 |
| M12 开发次序、阶段验收及停止边界 | GN12 |
| M13 完整测试、性能和产物门槛 | GN13 |
| M14 已确认决定与后续G03边界 | GN04／GN07／G03 |
| M15 两稿到合并稿的完整归属与深审结论 | 本附录来源映射与归并核查 |

<a id="pldt-evidence-map"></a>

## 附录B 入口、参数与证据覆盖

- 本文件[附录C统一执行模式表](#pldt-interface-modes)完整归并原Pddt130声明／126不同入口及PLDT薄出口；[旧接口导航](PLDT接口执行模式讨论表-20261029.md)仅链接本文件，不另维护规则。原完整参数／重载盘点及源码锚点保留在[逐入口映射](../tasks/evidence/pldt-design-research-20261029/Pddt接口逐项映射.md)和同目录interface-inventory.json／pddt-interface-coverage.json；实施时按本文件批准的新参数与名字更新跟踪，不能拿历史签名覆盖最终合同。
- Delta原37不同入口／43声明及新增ns角色，以[原入口盘点](../tasks/evidence/pldt-discussion-decisions-20261029/G01/nano-full-scheme-main/source-inventory.json)核漏；GN11列全协议与属性，GN10覆盖实际native slot／descriptor。公开签名、原位置参数、合法来源／方向和所有独立快路须逐项有测试归属。
- [本次冻结与归并证据](../tasks/evidence/pldt-final-decisions-consolidation-20261030/)保存输入原件及SHA、逐段处理、60项／Q／Delta映射、冲突处理、文档核验和受保护文件读回。原PLDT研究、29项归并、逐次Q确认、两份Delta原稿及所有探针／负面原始记录不覆盖。
- 旧Pddt最终行为决定、b2依赖／发行决定及根AGENTS仍按第0节明确范围适用；不能把未改变的成熟外部协议变成这次新增限制。日期数据、状态、构造、查询、格式输入／输出和原生完整委托分别按自身角色验收。
- 最终实施计划必须给每个主项及关联GN／O／U写出任务、明确目标、独立预期、实际源码、测试、安装产物和采用证据的对应；全部60讨论通过仅代表合同完整，不代表功能已实现或验收完成。

<a id="pldt-interface-modes"></a>

## 附录C 126个参照入口的统一执行模式

本表合并原130声明的同名重载为126行，仅去重名称，不删除重载覆盖。参数角色以对应正文的新合同为准；不是把历史Pddt签名原样复制给PLDT。新增与完整继承边界见表后；具体typing须在实施时与实际入口一起验收。

| 参照入口 | 最终PLDT模式 | 必要边界 | 对应主项 |
|---|---|---|---|
| `__new__` | Series（Pldt真子类） | 已确认B01接收合法一维日期来源，含可选DatetimeIndex及真实Pddt子类；直接拒绝Mapping／set／frozenset、表／Expr／单标量，嵌套列表TypeError。只构造真实Pldt，表达式按A02／A04走.pldt。 | B01 / A01 / A02 |
| `parse` | Series；Expr解析经.pldt，D01-D03已确认 | 共同Rust语法／词表／strict/default，原生来源按真实元数据；String Expr的unit/tz及快照按C02/D02/D03。 | B01 / A02 |
| `as_unit` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | C03 |
| `tzinfo` | eager元数据；无上下文Expr不返回Python时区对象 | 可表达区与local职责已定；H01／J04已定：UTC用timezone.utc，其余规范化IANA用ZoneInfo；不恢复来源身份。 | H01 |
| `tz_available` | eager元数据 | 只报告真实后端可支持区，不冒充系统ZoneInfo全集；不隐式collect Expr。 | H01 |
| `is_utc` | eager元数据 | 按真实规范化时区含义；UTC快捷路径不以getter返回对象种类判定。 | H01 |
| `is_local` | eager元数据 | 按共享local服务及真实区元数据，不为普通调用导入即探测系统。 | H01 |
| `tz_convert` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | H02 |
| `tz_localize` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | H02 |
| `astimezone` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | H02 |
| `tz_switch` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | H02 |
| `now` | Pldt立即工厂；原生literal Expr | 非空一次系统整数取钟，同值size行；默认当地naive，显式tz转换真实时刻。literal保创建工厂时的值，不隐式collect。 | E01 |
| `today` | Pldt立即工厂；原生literal Expr | 完整当地naive时钟，不归午夜；空不取钟，单位与数量沿E01。literal不因collect重新取钟。 | E01 |
| `utcnow` | Pldt立即工厂；原生literal Expr | 带UTC、同值size行；ns保系统真实信息，原生literal保ns及固定取值。 | E01 |
| `fromseconds` | Pldt工厂／Series + Expr（已确认） | 无区秒坐标后附区，unit仅输出；整数Expr默认us、浮点秒显式unit，标量size／列互斥。 | E02 |
| `frommicroseconds` | Pldt工厂／Series + Expr（已确认） | 整数微秒，finite float含1.0拒绝、明确缺失保持；Expr默认us，显式单位无损。 | E02 |
| `fromtimestamp` | Pldt工厂／Series + Expr（已确认） | 真实UTC秒；目标转换，无目标当地naive；Expr有效本地区捕获差异已确认，单位按E02 schema。 | E02 |
| `utcfromtimestamp` | Pldt工厂／Series + Expr（已确认） | 真实UTC秒并固定UTC；整数Expr默认us，浮点秒显式unit；不加载local。 | E02 |
| `fromdate` | Pldt工厂／Series + Expr（已确认） | 当地YMD归午夜、源区清除／目标附区；Date→ms，Datetime保单位，Expr由schema推导。 | E03 |
| `fromdatetime` | Pldt工厂／Series + Expr（已确认） | 真datetime／Datetime列；None保已知源时刻，明确tz保钟表替换，schema可推导单位／区。 | E03 |
| `fromdatetime64` | Pldt立即工厂（已确认） | 仅真实NumPy日期标量／一维来源，保单位倍率／ns，目标区附钟表；不加Series／Expr伪来源别名。 | E03 |
| `fromordinal` | Pldt工厂／Series + Expr（已确认） | 连续公历日，0／负数真实；默认us，Expr同默认，整数与checked容量。 | E04 |
| `fromisocalendar` | Pldt工厂／Series + Expr（已确认） | year主字段、week／weekday标量或等长列；低于1错误、高位取实际末周／周日，默认us。 | E04 |
| `fromdayofyear` | Pldt工厂／Series + Expr（已确认） | year主字段、doy标量／等长列；doy低错高取年末，默认us，不强制所有Expr填unit。 | E04 |
| `fromisoformat` | Pldt工厂／Series + Expr（已确认） | 严格共享ISO；Pddt／Pldt同步加目标tz／必要策略；String Expr明确unit、无目标只规划naive。 | E05 |
| `combine` | Pldt工厂／Series + Expr（已确认） | 日期接收者配时钟，us／真实ns；Expr精度由schema／标量决定或显式unit，空clock来源区修正单列。 | E04 |
| `strptime` | Series + Expr | D04已确认：共享格式／cfg／所需策略；Pddt／Pldt同步加目标tz，含时区格式Expr须明确目标。无%f Expr默认us，含%f须显式unit；%f按出口截取。 | D04 |
| `date_range` | Pldt立即工厂／原生literal（已确认） | 保periods／freq／共享端点；普通静态Rust、特殊协议采用可选pandas委托方案A；不隐式collect。 | E05 |
| `replace` | 日期字段：Series + Expr；F01已确认A | 日期字段只用.pldt.replace，Pddt同步.pddt.replace；各自原生整值replace沿生态／版本，不保留旧字段直调。 | F01 |
| `to_datetime` | Pldt直接／Series + Expr；F01已确认 | 八字段便利选择，合法day拟合月底；日期输出Pldt／Expr，自动地区规则，不是类型转换。 | F01 |
| `to_date` | Pldt直接／Series + Expr；F01已确认 | 只改YMD、保时钟／ns；日期输出Pldt／Expr，不是原生Date提取。 | F01 |
| `to_time` | Pldt直接／Series + Expr；F01已确认 | 只改时钟、保日期；日期输出Pldt／Expr，不是原生Time提取。 | F01 |
| `add` | Pldt直接／Series + Expr；F03已确认 | 11整数相对量；年月合并后一次月底，日与钟表随后，逐行最终精度／容量；Expr只用.pldt.add，保原生.add(other)。 | F03 |
| `sub` | Pldt直接／Series + Expr；F03已确认 | 同11角色及顺序，原生方向反转；不重入公开add，None／null拒绝，固定单位；Expr只用.pldt.sub。 | F03 |
| `to_year` | Pldt直接／Series + Expr；F02已确认 | 日历年offset；全年month整数／默认名称与day可选，最终月底；F02共同规则。 | F02 |
| `to_quarter` | Pldt直接／Series + Expr；F02已确认 | 季度offset；month仅季度内1—3位置，最终月底；保时钟／ns。 | F02 |
| `to_month` | Pldt直接／Series + Expr；F02已确认 | 日历月offset及可选day，合并目标后一次拟合月底。 | F02 |
| `to_weekday` | Pldt直接／Series + Expr；F02已确认 | 周数offset；weekday周一0—周日6或默认名称，当前周周一为起点。 | F02 |
| `to_day` | Pldt直接／Series + Expr；F02已确认 | 日历日offset，保当地时钟／ns及必要自动地区规则，不等同UTC24小时。 | F02 |
| `to_curr_year` | Pldt直接／Series + Expr；F02已确认 | 对应to_year的固定offset 0；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_prev_year` | Pldt直接／Series + Expr；F02已确认 | 对应to_year的固定offset -1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_next_year` | Pldt直接／Series + Expr；F02已确认 | 对应to_year的固定offset 1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_curr_quarter` | Pldt直接／Series + Expr；F02已确认 | 对应to_quarter的固定offset 0；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_prev_quarter` | Pldt直接／Series + Expr；F02已确认 | 对应to_quarter的固定offset -1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_next_quarter` | Pldt直接／Series + Expr；F02已确认 | 对应to_quarter的固定offset 1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_curr_month` | Pldt直接／Series + Expr；F02已确认 | 对应to_month的固定offset 0；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_prev_month` | Pldt直接／Series + Expr；F02已确认 | 对应to_month的固定offset -1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_next_month` | Pldt直接／Series + Expr；F02已确认 | 对应to_month的固定offset 1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_curr_weekday` | Pldt直接／Series + Expr；F02已确认 | 对应to_weekday的固定offset 0；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_prev_weekday` | Pldt直接／Series + Expr；F02已确认 | 对应to_weekday的固定offset -1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_next_weekday` | Pldt直接／Series + Expr；F02已确认 | 对应to_weekday的固定offset 1；同一小核及可选选择，不重入公开日期方法。 | F02 |
| `to_monday` | Pldt直接／Series + Expr；F02已确认 | 当前周weekday=0，保时钟／ns；无参，不是下一次／最近目标星期。 | F02 |
| `to_tuesday` | Pldt直接／Series + Expr；F02已确认 | 当前周weekday=1，保时钟／ns；无参，不是下一次／最近目标星期。 | F02 |
| `to_wednesday` | Pldt直接／Series + Expr；F02已确认 | 当前周weekday=2，保时钟／ns；无参，不是下一次／最近目标星期。 | F02 |
| `to_thursday` | Pldt直接／Series + Expr；F02已确认 | 当前周weekday=3，保时钟／ns；无参，不是下一次／最近目标星期。 | F02 |
| `to_friday` | Pldt直接／Series + Expr；F02已确认 | 当前周weekday=4，保时钟／ns；无参，不是下一次／最近目标星期。 | F02 |
| `to_saturday` | Pldt直接／Series + Expr；F02已确认 | 当前周weekday=5，保时钟／ns；无参，不是下一次／最近目标星期。 | F02 |
| `to_sunday` | Pldt直接／Series + Expr；F02已确认 | 当前周weekday=6，保时钟／ns；无参，不是下一次／最近目标星期。 | F02 |
| `to_yesterday` | Pldt直接／Series + Expr；F02已确认 | 日历日offset=-1，无参。 | F02 |
| `to_tomorrow` | Pldt直接／Series + Expr；F02已确认 | 日历日offset=+1，无参。 | F02 |
| `__add__` | Pldt立即算符；G01已确认 | 普通Delta标量／等长真实列走共享原生字段；不覆盖原生Expr的+。固定时长与日期差按已确认G02，动态协议按已确认G03。；保留原入口重载映射；相对／绝对字段与ns尾数不转timedelta或Pddt。 | G01 / G02 / G03 |
| `__radd__` | Pldt立即算符；G01已确认 | Delta + Pldt与正向同一日期数学，真实外部反向协商另按G03。；保留原入口重载映射；不在Delta类导入pandas／Polars；固定时长职责按已确认G02。 | G01 / G03；G01 / G02 / G03 |
| `__sub__` | Pldt立即算符；G01已确认 | 日期减Delta只反转相对量；Delta减日期不新增含义。；日期差按已确认G02返回原生Duration并保精度／缺失；不误把全缺失操作数都认定为Delta列。；保留原入口重载映射；真实外部动态协议与一行原生Series回调载体按已确认G03。 | G01 / G03；G01 / G02；G01 / G02 / G03 |
| `to_first_of` | Pldt直接／Series + Expr；F04已确认 | 首日保时钟／ns；Y/Q/M/W或保存月份名，不改为周期起点。 | F04 |
| `is_first_of` | Pldt直接／Series + Expr；F04已确认 | 直接Boolean：首日判断忽略时钟；合法非匹配／源null为False。 | F04 |
| `to_last_of` | Pldt直接／Series + Expr；F04已确认 | 末日保时钟／ns；Y/Q/M/W或保存月份名，选定日整体缺失错误。 | F04 |
| `is_last_of` | Pldt直接／Series + Expr；F04已确认 | 直接Boolean：末日判断忽略时钟；合法非匹配／源null为False。 | F04 |
| `to_start_of` | Pldt直接／Series + Expr；F04已确认 | 当前单位有效周期开始；另支持日／时钟／保存星期名，固定单位及目标周期。 | F04 |
| `is_start_of` | Pldt直接／Series + Expr；F04已确认 | 直接Boolean：实际起边界，容量外目标不先造日期；源null为False。 | F04 |
| `to_end_of` | Pldt直接／Series + Expr；F04已确认 | 当前单位有效周期结束；ms/us/ns尾精度不同，不自动改单位或截容量。 | F04 |
| `is_end_of` | Pldt直接／Series + Expr；F04已确认 | 直接Boolean：实际末边界与当前精度，源null为False。 | F04 |
| `normalize` | Pldt直接／Series + Expr；F04已确认 | 无参，本日有效开始；午夜缺失可同日首个有效时刻，不跳日。 | F04 |
| `fsp` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | I03 |
| `round` | 日期经.pldt；原生同名方法保留 | 日期freq／取偶／固定unit按I01；Pldt.round仍为Polars数值API，不加双义分流。 | I01 |
| `ceil` | 日期经.pldt；原生同名方法保留 | 日期freq／真实不早于输入及自动地区规则按I01。 | I01 |
| `floor` | 日期经.pldt；原生同名方法保留 | 日期freq／真实不晚于输入及自动地区规则按I01。 | I01 |
| `snap` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | I02 |
| `isoyear` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `isoweek` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `isoweekday` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `days_in_year` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `days_bf_year` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `days_in_quarter` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `days_bf_quarter` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `day_of_quarter` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `days_bf_month` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `day_of_month` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `millisecond` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `is_long_year` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `is_year` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J02 |
| `is_quarter` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J02 |
| `is_month` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J02 |
| `is_weekday` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J02 |
| `is_day` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J02 |
| `leap_bt_year` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J02 |
| `year` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `isocalendar` | Struct Series + Struct Expr | year/week/day各UInt32，负ISO年OverflowError、signed isoyear独立；可原生unnest。 | A03 / J04 |
| `is_dst` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `utcoffset_seconds` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | J01 |
| `is_past` | Boolean Series + Expr | J01已定：建立查询Expr时取一次整数参考，重复collect复用；eager按需取钟。 | J01 |
| `is_future` | Boolean Series + Expr | 同J01；严格晚于参考，相等／源null=False，刷新须重建查询Expr。 | J01 |
| `diff` | 本库边界计数经.pldt；原生diff保留 | 标量／等长目标、unit／absolute／inclusive／Int64有效位按J03；Pldt.diff(n, null_behavior)仍原生相邻差。 | J03 |
| `values_naive` | Series + Expr | 当地无区Datetime Series/Expr，不自动NumPy，不是直接删UTC元数据冒充当地。 | K01 |
| `toseconds` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K01 |
| `tomicroseconds` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K01 |
| `toordinal` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K01 |
| `timestamp` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K01 |
| `timedf` | eager DataFrame；Expr固定Struct | 九字段／专用dtype已定；H01／J04已定：naive/标准UTC为-1，ZoneInfo按实际DST；原null保留。 | J04 |
| `utctimedf` | eager DataFrame；Expr固定Struct | 真实UTC／naive不移动，所有有效tm_isdst=0；不先造UTC Pldt。 | J04 |
| `isoformat` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K03 |
| `strftime` | 三类方案A与小数扩展已确认 | Pydt/Pddt/Pldt共用小数计划：s/ms/us六位、ns九位；%.0f为空，%.1f—%.9f截取或补零。Pydt/Pddt其余成熟系统格式保持；Pldt系统格式仅eager。 | K03 |
| `datetime` | eager显式Python对象出口 | 一维NumPy object数组，Pydt／None，最后一次us截取、tz/fold和目标容量；不作普通计算中转。 | K02 |
| `date` | 属性；原生Date Series/Expr | 按实际i32日目标容量checked，不可表示则错误，不以null或object补救。 | K02 |
| `time` | 属性；原生Time Series/Expr | 原生本日ns，不先造Python日期。 | K02 |
| `timetz` | 属性；eager显式Python对象出口 | NumPy object数组，标准time／None，最后us、保tz/fold；不造Object Expr。 | K02 |
| `tzname` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K04 |
| `ctime` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K03 |
| `month_name` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K04 |
| `weekday_name` | Series + Expr | 共同日期规则、typed输出、固定原生元数据；参数角色见完整签名映射。 | K04 |
| `copy` | eager自有复制 | 沿L02独立同类外壳／安全浅共享或真实deep隔离；业务memo与协议保持，原生clone另按Polars。 | L02 |
| `__copy__` | eager真实Python协议 | 独立外壳及浅业务引用，不重跑业务初始化；L02。 | L02 |
| `__deepcopy__` | eager真实Python协议 | 同memo保别名／循环且日期数据隔离，不能以clone代deep；L02。 | L02 |
| `__getstate__` | Series；Expr不承诺同一公开能力 | 元数据值/长度/索引须已有数据上下文；取钟／范围先eager、可显式转literal Expr；Python对象/业务状态仅eager。不得隐式collect。 | L02 |
| `__setstate__` | Series；Expr不承诺同一公开能力 | 元数据值/长度/索引须已有数据上下文；取钟／范围先eager、可显式转literal Expr；Python对象/业务状态仅eager。不得隐式collect。 | L02 |
| `__reduce__` | Series；Expr不承诺同一公开能力 | 元数据值/长度/索引须已有数据上下文；取钟／范围先eager、可显式转literal Expr；Python对象/业务状态仅eager。不得隐式collect。 | L02 |
| `__reduce_ex__` | Series；Expr不承诺同一公开能力 | 元数据值/长度/索引须已有数据上下文；取钟／范围先eager、可显式转literal Expr；Python对象/业务状态仅eager。不得隐式collect。 | L02 |

### PLDT薄入口与公开原生协议

| PLDT薄入口／继承协议 | 模式 | 最终归属 |
|---|---|---|
| 官方Expr命名空间`.pldt` | Expr，A02已确认 | 日期操作及查询直接返回原生pl.Expr，无需本库显式包装或导出；命名已由A04确认。已有Series作为字面快照进入计划按Polars原生方式及E01/M03，不另承诺自有导出方法。 |
| 官方Series命名空间`.pldt` | Series，A04已确认 | 普通Series可直接调用本库实例日期功能；日期返回Pldt、查询返回原生Series，不先生成临时Pldt。与Expr同名入口共享功能，加载PLDT时一次注册。 |
| `.pldt.add_delta(delta)` | Series／Expr；G01已确认 | 普通Delta标量或提前给定的严格等长Delta集合一次准备原生字段；Series返回Pldt，Expr返回pl.Expr，不覆盖原生Expr的+／add。符号Object列不是原生Delta dtype，动态协议按已确认G03。 |
| `.pldt.sub_delta(delta)` | Series／Expr；G01已确认 | 日期减Delta只反转相对增量、保绝对字段与来源ns；unit固定，列与batch按全列行号配对。与F03命名增量sub分开，不自动给Pddt新增方法。 |
| `to_numpy()` | eager受保护原生导出 | 保writable/allow_copy原职责，新增allow_nat_collision=False；实际目标安全，普通Series原生导出边界另明；C04/K01。 |
| `to_pandas()` | eager受保护原生导出 | 保use_pyarrow_extension_array与全部原生kwargs，新增allow_nat_collision=False；pandas.Series，Arrow按实际目标有效位，显式可选依赖；C04/K01。 |
| `__arrow_c_stream__()` | Series | 沿Polars公开Arrow协议完整继承，保schema／chunk／有效位／owner及release；不新增必需PyArrow或任意Arrow对象输入，B03／M02／L04 |
