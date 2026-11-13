# 当前Rust rc04与Cython Delta性能对比

日期：2026-10-13。固定对象为 **Rust `rsTimes 0.1.0+delta.4 / rc04`** 与 **Cython `cytimes-rewrite 0.2.0 / R2FinalE`**。本轮只测性能，没有修改、优化、重建或发布任一实现。

完整测量双方结果与返回类型一致的 **200个既有场景**：主轮与独立轮各3个真实新进程，每项144个完整四批组，总28,800组、115,200个计时批次。覆盖、成员质量与准备精度200/200通过。正式采集 **19.12分钟**。

稳定结论：**Rust更快41项，Cython更快61项，接近53项，不明确45项。** 场景数量不等于实际业务耗时占比。

## 读表方式

速度比=Cython耗时÷Rust耗时：大于1表示Rust更快，小于1表示Cython更快。例如2倍表示Rust用时约为Cython的一半；0.5倍表示Cython用时约为Rust的一半。数值在1/1.05至1.05之间且统计稳定时记为接近。

不明确项仍保留实际观察值，但不据此认定快慢。分组倍率只汇总明确项的等权几何平均，同时显示明确/全部场景数；不把这类局部平均写成整个类的总提速。

## 方向摘要

- Cython在普通整数构造、单项Delta加减、timedelta运算、取负/绝对值，以及重复读取同一对象的repr/str中占优。
- Rust在复制/pickle、带起点的to_timedelta、较大Delta批量、date/datetime批量和混合批量中占优。
- relativedelta与Pydt的明确项大多接近；普通date/datetime有13项尚不明确，不能用少数明确项概括全部日期运算。
- NumPy必须按标量/批量和日期/时长分别看。两项NumPy时长批量Rust约快20倍；两项NumPy日期批量观察值约16倍，但稳定性不足，不能给明确提速结论。
- 批量Delta不是所有规模都更快：16元素Cython更快，256至10000元素的已测场景Rust更快。

## 全部分方向结果

| 方向 | 明确/全部 | 明确项Cython÷Rust倍率 | Rust更快 | Cython更快 | 接近 | 不明确 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 整数构造与归一化 | 9/11 | 0.863× | 0 | 8 | 1 | 2 |
| 属性读取 | 2/3 | 0.946× | 0 | 1 | 1 | 1 |
| 真假判断 | 2/3 | 0.995× | 0 | 0 | 2 | 1 |
| 表示：重复读取同一对象 | 3/3 | 0.245× | 0 | 3 | 0 | 0 |
| 哈希 | 4/4 | 0.928× | 0 | 2 | 2 | 0 |
| 相等比较 | 3/4 | 0.997× | 0 | 0 | 3 | 1 |
| 取负与绝对值 | 3/5 | 0.699× | 0 | 3 | 0 | 2 |
| Delta加减 | 8/10 | 0.784× | 0 | 8 | 0 | 2 |
| timedelta运算 | 15/20 | 0.854× | 0 | 15 | 0 | 5 |
| date/datetime与时区 | 11/24 | 1.029× | 3 | 0 | 8 | 13 |
| relativedelta | 10/10 | 1.008× | 0 | 0 | 10 | 0 |
| NumPy标量 | 26/34 | 0.942× | 6 | 16 | 4 | 8 |
| pandas | 1/2 | 0.689× | 0 | 1 | 0 | 1 |
| Pydt | 7/8 | 1.013× | 0 | 0 | 7 | 1 |
| 批量 date/datetime | 14/14 | 1.117× | 11 | 0 | 3 | 0 |
| 批量 timedelta | 6/7 | 0.908× | 0 | 2 | 4 | 1 |
| 批量 Delta | 7/7 | 1.047× | 6 | 1 | 0 | 0 |
| pickle与复制 | 7/8 | 2.622× | 7 | 0 | 0 | 1 |
| 批量 Pydt | 4/4 | 1.031× | 0 | 0 | 4 | 0 |
| 批量 relativedelta | 4/4 | 1.014× | 0 | 0 | 4 | 0 |
| 批量 NumPy | 2/4 | 20.182× | 2 | 0 | 0 | 2 |
| 批量混合 | 2/2 | 1.417× | 2 | 0 | 0 | 0 |
| to_timedelta | 4/6 | 1.309× | 4 | 0 | 0 | 2 |
| 表示：新对象/交替/子类 | 1/3 | 0.870× | 0 | 1 | 0 | 2 |

## 代表调用的实际耗时

单位为微秒/次，包含完整公共调用、分配和结果释放；批量项是一次处理整个列表的用时。短调用使用共同次数的批量循环计时后取单次平均，打印与结果核对在计时之外。

| 代表操作 | Cython µs | Rust µs | Cython÷Rust | 结论 |
| --- | ---: | ---: | ---: | --- |
| 空Delta构造 | 0.0249 | 0.0349 | 0.713× | Cython更快 |
| 年/月/日/时/分/秒混合构造 | 0.1925 | 0.2038 | 0.942× | Cython更快 |
| 读取全部15个属性 | 0.1776 | 0.1979 | 0.897× | Cython更快 |
| 同值Delta比较 | 0.0152 | 0.0156 | 0.973× | 接近 |
| Delta + Delta | 0.0246 | 0.0356 | 0.691× | Cython更快 |
| Delta + timedelta | 0.0252 | 0.0338 | 0.749× | Cython更快 |
| date + Delta | 0.0386 | 0.0410 | 0.950× | 不明确 |
| datetime + Delta | 0.0413 | 0.0385 | 1.077× | Rust更快 |
| 普通Delta pickle保存 | 2.0590 | 0.9456 | 2.173× | Rust更快 |
| 普通Delta pickle读取 | 1.1407 | 0.5949 | 1.933× | Rust更快 |
| 普通Delta deepcopy | 3.7491 | 0.3865 | 9.735× | Rust更快 |
| 以闰年月末为起点转换时长 | 0.0830 | 0.0653 | 1.268× | Rust更快 |
| 16元素Delta批量 | 0.2390 | 0.3669 | 0.653× | Cython更快 |
| 10000元素相对Delta批量 | 197.1907 | 174.7217 | 1.128× | Rust更快 |
| 10000元素NumPy时长批量 | 4426.6847 | 217.8311 | 20.083× | Rust更快 |
| 10000元素NumPy日期批量 | 4305.4221 | 266.6084 | 16.022× | 不明确 |
| 10000元素混合批量 | 4891.8021 | 3441.7430 | 1.416× | Rust更快 |
| 新建Delta再repr | 0.1154 | 0.1307 | 0.876× | 不明确 |
| 交替读取两个对象的repr | 0.0778 | 0.0896 | 0.870× | Cython更快 |

这些是代表行，完整200项均在逐项表与CSV中，没有因慢或不明确而删减。

## 语义不同或拒绝输入的处理

旧对比中的两项Timestamp日期运算不再属于同一结果：Rust保留789ns尾数，Cython将尾数清零。这是当前版本的功能差异，因此不把它们放入公平性能排名。原输入与两边结果全部保留在workloads.json。仍有两个pandas Timedelta场景可比，已计入200项；不是整个pandas方向未测。

| 原场景 | Rust结果 | Cython结果 | 本轮处理 |
| --- | --- | --- | --- |
| `C:interop-pandas-timestamp-add` | 2024-03-03T03:03:05.000004789+08:00 | 2024-03-03T03:03:05.000004+08:00 | 单列，不参加成功调用排名 |
| `C:interop-pandas-timestamp-subtract` | 2024-02-27T20:54:54.999992789+08:00 | 2024-02-27T20:54:54.999992+08:00 | 单列，不参加成功调用排名 |
| `R:dateutil:from:weekday-n:Delta` | ValueError: relativedelta weekday rules cannot be represented by Delta | ValueError: relativedelta weekday cannot be represented by Delta | 单列，不参加成功调用排名 |
| `R:dateutil:arithmetic:weekday-n:radd` | ValueError: relativedelta weekday rules cannot be represented by Delta | ValueError: relativedelta weekday cannot be represented by Delta | 单列，不参加成功调用排名 |

小数保留与截断的不同语义沿用旧输入规则，不混作同工作量比较；本轮没有追加小数扩展实验。

## 方法与结论范围

- 复用原直接对比sampler和报告统计；仅使用小适配器选择rc04及新证据目录，旧97数据未混入新成绩。
- 同一普通CPython3.13.3、同一测量线程加载固定扩展；共同依赖为NumPy2.5.3、pandas2.3.3、dateutil2.9.0.post0、cytimes3.1.0及tzdata2026.5。Cython原交付环境的依赖版本不同，历史成绩不混用。
- 最快方计时批次至少5ms，读取边界≤1%，计时读取成本≤0.5%，墙钟与线程CPU差≤10%；完整四批组跨度≤500ms。
- 短/双倍长控制倍率差≤3%，至少各4有效组。初轮5项证据不足，按原参数固定数量仅复核一次，初轮数据保留；没有为了性能胜负追加正式采集。
- 每个新进程每场景24个有效CRRC/RCCR组，两种顺序各12；任何成员不合格整组回原槽。全部合格快慢样本保留。
- 每项检查进程中位差、顺序中位差和主轮/独立轮中位差，均≤5%才作明确方向判断。这是原对比的固定检查，不能保证消除所有温度、频率或缓存影响。
- 原始共29419次完整组尝试，619次不合格，28800次有效，接收率97.90%。不使用拟合、耗时修正或择优选值。
- 本轮完整的是共同输入的对比交付，不要求Rust每项获胜，也不改变rc04相对Rust97的上一轮5%保护未全通过结论。

## 文件与复现身份

- [200项逐项表](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/Delta-Cython与Rust性能逐项明细.md)
- [全部性能CSV](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/Delta-Cython与Rust性能明细.csv)
- [完整逐项结果JSON](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/performance-summary.json)
- [固定包、平台及依赖身份](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/identity.json)
- [wheel与源码来源](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/artifact-manifest.json)
- [共同输入及差异输入](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/workloads.json)
- [冻结配置与所有控制](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/config.json)
- [采集时间与预算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-rc04-20261013/campaign.json)
- [唯一计划与时间台账](/Users/jef/ResilioSync/code/rsTimes/tasks/delta-cython-rust-rc04-comparison-20261013.md)

Rust实际native SHA-256：`e4d919cb654d1c554b6ee20b22bc4429537b93dd4049bc45a3a504f36c56273d`。Cython实际native SHA-256：`3ef0ec227fe995ebb0c289f28d59ff69faa8847dcfd13b0755eaaf71fb289aba`。两边实际路径见identity.json；Cython原生源码提交`96045d63d7371fd0593ef1644de0dd9cb006731e`。Rust rc04源码以独立sdist构建记录为准，不将旧HEAD当成本轮未提交修改的源码身份。

本轮60分钟预算，最终工作快照北京时间2026-10-13 22:05:29：有效用时36.50分钟，未使用23.50分钟，暂停0；末尾答复秒数误差约1分钟。全部200项共同场景对比交付完成，不追加优化或重测。
