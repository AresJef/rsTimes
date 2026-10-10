# Delta 安全检查说明

本次S7.4检查通过，证据为tasks/evidence/S7.4.json，首次对应safety-01安装的候选；后续受影响部分复核见tasks/evidence/safety-02-review.json及safety-03-review.json。后续相关源码改动必须复核受影响部分；这不是所有输入、所有解释器或所有依赖版本的绝对安全保证。

Rust 核心对可能溢出的数值和日历计算使用有检查的整数运算；已经由归一化证明有界的日期时间单位使用32位加减和进位，微秒相加最多1999998；date的组合微秒用64位运算，最大组合低于1728亿。days保留64位检查、year保留原32位结果检查；Python 字段转换和回调成功后再提交初始化结果。普通 CPython 3.13 以 GIL 串行执行，提交期间不调用 Python。字段使用原子整数，避免持有可变 Rust 借用时重入 Python。

## Python 直接运算方法适配

必要性：PyO3 0.29.3 将正反运算合为同一 CPython 数值入口，直接 __radd__/__rsub__ 因而额外接受 Delta。原版的直接反向方法要求返回 NotImplemented，关键字错误消息也需保留。rust/protocol.rs 集中安装四个方法描述符；表达式的加减入口也使用集中回调，计算共用原有Rust方法。arithmetic-02/green.json 是修复前六处差异，newobj-01/green.json 包含最新入口的完整检查。

这里的 unsafe 只用于 CPython 接口：

- 回调由 CPython 的 METH_O 描述符调用，接收两个非空、仍然存活的 Python 对象，并已持有解释器线程状态。使用限于回调的 Borrowed，CPython保证两个参数在回调内存活；重新核对 Delta 实际类型后才读取 Rust 字段。
- 回调捕获 Rust panic，转换为 Python RuntimeError；Python 异常恢复到解释器并返回空指针，不跨 C 边界展开 Rust 栈。
- 方法定义、字符串和函数地址具有静态生命周期；CPython 不修改这些定义。Sync 声明仅用于这些不变地址。
- 模块初始化持有 ready 的 Delta 类型；tp_dict 与数值表属于此类型。仅修改本类型的描述符和已记录的入口，再调用 PyType_Modified 使缓存失效。当前构建使用普通 CPython 完整接口，不启用 abi3。

月份增量已归一化为0–11，因此日期运算最多跨一年，使用有检查的年份加减。没有weekday的小量天数增减（±27天）最多跨一个月，先按原规则夹取月底，再移动；Rust检查同时验证其公历结果及32位年份溢出。纯date仅在已提交的时钟标志证明所有钟点不贡献天数时省去读取；datetime保留全部时钟字段。

没有自写Rust对象内存偏移，也没有在核心算法中使用unsafe。依赖内部的unsafe不计作本项目已全部审阅。

## NumPy 标量边界

rust/numpy_scalar.rs 读取 NumPy 公共 arrayscalars.h 中的两个标量前缀。读取前核对对象真实类型与 NumPy datetime64/timedelta64 的继承关系；不用可伪造的 __class__ 作为内存访问依据。Bound 持有对象，GIL 阻止当前解释器并发写入；只读 value/unit，不保留对象内部指针。有效年份的NumPy日期直接由Rust部件计算创建最终datetime，省去临时对象；无效初始年份仍先调用原Python构造器报错，保持异常次序。元数据倍率按冻结实现忽略。当前验收版本 NumPy 2.5.3；C 头编译所得大小32、值偏移16、元数据偏移24，与 Rust repr(C) 单元检查一致（numpy-layout-c.json）。不宣称已验证其他 NumPy ABI。

## 已测小调用入口

属性读取的集中回调由 CPython getset 描述符调用；描述符在调用前核对真实接收对象是本 Delta 的实例/子类，15个属性对错误对象的拒绝检查已通过。通过 PyO3 Borrowed/get 读取已核对的 Rust 类型，不自写 Rust 对象偏移。借用和 Python token 限于回调，不逃逸；属性索引为0–14的静态值，回调先核对上界，索引指针只作为数字编码，从不解引用。对象保持存活，字段读取为原子整数。返回的是新拥有引用的 Python整数或None，分配错误沿用Python异常。所有Rust panic均被捕获，不能越过C调用边界。

bool入口由已就绪类型的数值表调用，只读取该类型保证的有效接收对象并返回0/1；异常返回-1并设置Python异常。真假值由每次合法字段提交计算，保存在原有空余槽中，不增加对象大小；重新初始化、空状态恢复和raw状态恢复已单独验证。模块初始化只修改自己创建的ready类型，并使类型缓存失效。

加减入口对两侧真实Python类型分别检查；比较入口由CPython保证接收对象是本类型/子类，另一侧先核对真实类型。同类型快速路径比较Py_TYPE指针，其他子类沿用完整检查；伪造__class__不会触发Rust字段读取。hash使用既有缓存算法，排序仍返回NotImplemented。初始化入口由CPython提供存活的本类型对象、参数tuple及dict或NULL，调用原有完整转换逻辑；所有转换/回调结束后才提交字段。

精确基础类分配通过安全的Bound::new，PyO3内部调用tp_alloc而不再次调用tp_new；Python子类交回保存的PyO3原分配函数。函数地址为静态代码，由OnceLock保存，不持有Python对象或实例内存；不自行创建对象布局或释放内存。最新字段存储将两个已验证的32位字段放入一个64位原子数，days另用64位原子数；每次提交同时更新真假和日期时钟标志。只有已归一化、已完整验证状态或可信快照能进入提交；其他字段的32位范围由原规则保证，不能以压缩存储代替溢出检查。

## 本次验收结果与边界

| 检查 | 结果 | 证据与范围 |
| --- | --- | --- |
| 转换、异常、溢出、非法状态及类型分派 | 完整共同输入1381项、本包契约54项通过；141处已决定差异 | safety-01/green.json；不跳过失败或将错误状态提交到对象 |
| 数字回调再次初始化 | 成功返回后外层字段正确；失败保留已完成的内层初始化 | lifecycle:integer-reentry及integer-reentry-error；与原版一致 |
| dateutil回调再次初始化 | 结果days=5，接收对象days=3；未发生借用冲突 | lifecycle:dateutil-reentry；与原版一致 |
| 有限创建/释放 | 2000次普通运算后Delta类型、日期、时区、NumPy标量的引用数恢复；100个有自引用的子类可回收 | lifecycle:bounded-release；不宣称证明所有路径无泄漏 |
| 缓存真假值 | 初始化和合法状态恢复后与字段一致 | state:derived-truth |
| 编译模式 | debug/release各9项通过，包含负数进位、中间溢出和C布局 | safety-01/rust-release.json及S7.4记录 |
| Rust代码检查 | cargo clippy --all-targets --all-features --locked -- -D warnings通过 | 自有生产代码无unwrap/expect；仅测试中保留断言 |
| Rust依赖 | 15项，0已知漏洞、0警告 | cargo-audit-01.json；数据库提交7eebec69c352c7191b1f13eb95dd510eeca5d1de |
| Python依赖 | 锁定运行、测试与构建环境55项，0已知漏洞 | python-audit-01.json；依赖未改变，复用有效结果 |

所有C回调在本次普通CPython/GIL环境执行，返回对象持有正确Python引用；异常使用空指针或-1并恢复Python异常，Rust panic不跨C边界。模块安装所访问的ready类型/字典/数值表具有类型生命周期，方法和属性定义为静态只读表，改变后使类型缓存失效。NumPy仅有一处按公共头读取的边界，已完成真实类型和C布局核对。核心日历、归一化、状态验证没有unsafe。

pickle仍只用于可信数据。跨类型相等/hash不一致的旧缺陷仍保留。当前检查只覆盖本次明确候选、macOS arm64、普通CPython3.13及固定依赖，未验收无GIL、多解释器或其他NumPy ABI组合。
