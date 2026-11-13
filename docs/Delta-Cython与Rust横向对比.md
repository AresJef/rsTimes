# Delta：Cython R2FinalE与Rust候选97直接对比

日期：2026-10-13。固定对象为Cython `cytimes-rewrite 0.2.0 / R2FinalE`和Rust `rsTimes 0.1.0+delta.3 / 候选97`。

本报告比较两个已交付版本，没有优化或修改它们。先核对功能结果，再对相同工作做直接计时；原项目分别与旧版比较的成绩没有搬来充当横向结果。

## 一眼看懂的功能结论

**两边都有完整的常用Delta接口及两个新方法。Rust的主要扩展是保留固定时长小数和扩大部分整数范围；Cython在非空slots子类状态、重写比较方法的子类，以及标准timedelta返回约束方面有不同实现。不能把两者概括成“所有功能完全一样”。**

| 功能 | Rust候选97 | Cython R2FinalE | 对比结论 |
| --- | --- | --- | --- |
| 19个构造参数、关键词与位置调用 | 支持 | 支持 | 普通整数输入一致；范围和小数差异见下表 |
| 15个只读属性 | 支持 | 支持 | 普通值、未设置字段及归一化一致 |
| 相对进位、负数归一化 | 支持 | 支持 | 常规输入一致 |
| 绝对上限截取、负值未设置、毫秒/微秒优先级 | 支持 | 支持 | 可共同接收的常规输入一致 |
| Delta加减、取负、绝对值 | 支持 | 支持 | 常规输入一致；大年份范围不同 |
| timedelta四个加减方向 | 支持 | 支持 | 已覆盖场景一致 |
| date/datetime、时区、fold和月底 | 支持 | 支持 | 已覆盖常规场景一致；月底往返均不保证还原 |
| Pydt、pandas日期/时长 | 支持已有交互 | 支持已有交互 | 单项代表场景一致；to_timedelta的返回约束不同 |
| relativedelta转换及加减 | 支持，检查normalized后的weekday/leapdays | 支持，检查原始及normalized后字段 | 普通对象一致；自定义normalized子类不同 |
| NumPy日期/时长标量 | 支持 | 支持 | 常规标量一致；NaT[D/M]异常类别不同 |
| 同类比较、哈希、真假判断 | 支持 | 支持 | 普通值一致；重写eq/hash的子类不同 |
| 构造后值不可变、重复init不改值 | 支持 | 支持 | 一致；子类附加元数据仍可变 |
| repr/str | 支持 | 支持 | 文字一致；Cython有单对象表示缓存，热/冷路径分开测 |
| 本包pickle、copy/deepcopy | 支持 | 支持 | 基础值可往返；状态格式、缓存处理及slots元数据不同 |
| apply_many：列表、混合类型、生成器 | 支持 | 支持 | 普通list与逐项value+delta语义一致 |
| to_timedelta：无起点/有起点 | 支持 | 支持 | 普通微秒时长一致；子类和纳秒差异见下表 |
| 固定时长参数保留float小数 | 支持7个单位 | float可传入，但先向零取整 | Rust提供额外时长含义 |
| 旧cyTimes pickle与旧内部Cython ABI兼容 | 不承诺 | 不承诺 | 不把项目内部实现文件当作旧ABI兼容保证 |
| 乘除、replace、原生数组输出 | 未提供 | 未提供 | 本次不作为缺失的共同功能扩展 |

相对参数：`years, quarters, months, weeks, days, hours, minutes, seconds, milliseconds, microseconds`。

绝对参数：`year, month, day, weekday, hour, minute, second, millisecond, microsecond`。

15属性：`years, months, days, hours, minutes, seconds, microseconds, year, month, day, weekday, hour, minute, second, microsecond`。

## 功能差异：逐类说明

| 差异 | Rust实际行为 | Cython实际行为 | 使用影响 |
| --- | --- | --- | --- |
| 固定时长小数 | `Delta(hours=1.5)`为1小时30分钟；微秒统一半偶舍入 | 同输入为1小时；构造时去掉小数部分 | 两边接收同一float，不一定表示同一时长；不能拿这种输入直接排名性能 |
| 年/季度/月/周及绝对参数入口 | 有符号64位范围 | 有符号32位范围 | `year=2**40`在Rust截到9999，在Cython报OverflowError |
| 最终相对年份 | 可保存64位年份 | 限于32位 | `years=2**53+1`仅Rust可保存；日期最终仍须满足Python范围 |
| 极大相对时长的中间计算 | 部分换算按受检查的64位中间量，溢出立即拒绝 | 必要中间量使用更宽计算，最终字段检查后可接受 | `milliseconds=2**63-1`在Rust报错，Cython可规范化；Rust并非所有整数情形都更宽 |
| 重写eq且无hash的Delta子类 | 基类方法仍按字段比较；普通表达式中已观察到`==`和`!=`同时False | 基类方法返回NotImplemented，普通表达式为`== False`、`!= True` | 自定义子类比较的实际行为不同，Rust这里需要注意 |
| to_timedelta返回时长子类 | 保留等价Python表达式返回的子类 | 无损转换为标准datetime.timedelta | 自定义日期减法返回Span时，两边返回类型不同 |
| to_timedelta纳秒尾数 | Timestamp例子返回带877ns的pandas Timedelta | 报ValueError，拒绝不是整微秒的差值 | Rust保留表达式结果；Cython强调无损标准微秒时长 |
| 非空slots子类的保存与复制 | copy/deepcopy/pickle后丢失已设置的slots附加字段 | 保留slots附加字段 | Rust当前的实际功能缺口；后续访问字段会报AttributeError |
| 恢复时的错误哈希缓存 | 明确验证并拒绝伪造缓存 | 合法字段恢复时忽略旧缓存并重新计算 | 两者均不信任错误缓存，但接收规则不同 |
| relativedelta子类的normalized回调 | 先调用回调，再检查返回字段 | 原始字段不支持时先拒绝，不执行回调；否则也检查返回字段 | 子类清除原weekday/leapdays时Rust接受、Cython拒绝；回调异常顺序也不同 |
| 状态接口与格式 | 暴露__setstate__、__copy__、__deepcopy__及本包状态 | 通过受控重建协议；没有相同直接方法，基础__getstate__为None | 标准pickle/copy都有实现，不能互换原始状态入口 |
| NumPy NaT[D/M] | 所覆盖加法/反向方法报OverflowError | 报ValueError，最终日期年份越界 | 都拒绝这些输入，但依赖异常类别捕获的代码需要区分 |
| 异常文字 | 有PyO3/本包转换提示 | 有Cython/__cinit__转换提示 | 已单列所有观察到的文字差异，不把异常类别相同视作文字完全兼容 |

补充说明：Cython构造不保留小数，不代表它不能处理已由`timedelta`或合法`relativedelta.normalized()`拆成整数单位的时长；这类共同语义调用仍可比较。

此次非空slots结果补充了旧验收边界：Rust此前通过普通子类字典和空slots子类，并不能证明带实际slots字段的子类状态也被保留。

完整逐项记录见[功能差异明细](/Users/jef/ResilioSync/code/rsTimes/docs/Delta-Cython与Rust功能差异明细.md)；全部输入和双方结果见[功能观察CSV](/Users/jef/ResilioSync/code/rsTimes/docs/Delta-Cython与Rust功能观察.csv)。本次共3651项功能观察：3547项值/类型/异常类别一致，104项不同；一致项中另有594项异常文字不同。重复场景不算独立功能数量。

## 共同功能的直接性能比较

完整采集202项、两轮各3个新进程，共29088个有效完整四批组。

按冻结的质量与稳定性规则：**Rust更快34项，Cython更快26项，接近54项，不明确88项。** 这是固定场景计数，不是业务时间占比。

| 方向 | 明确/总场景 | Cython耗时÷Rust耗时 | Rust更快项 | Cython更快项 | 接近项 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 整数构造与归一化 | 6/11 | 0.896× | 0 | 3 | 3 |
| 属性读取 | 2/3 | 0.983× | 1 | 1 | 0 |
| 真假判断 | 0/3 | 不明确 | 0 | 0 | 0 |
| 表示：重复读取同一对象 | 1/3 | 0.270× | 0 | 1 | 0 |
| 哈希 | 2/4 | 0.919× | 0 | 1 | 1 |
| 相等比较 | 0/4 | 不明确 | 0 | 0 | 0 |
| 取负与绝对值 | 2/5 | 0.707× | 0 | 2 | 0 |
| Delta加减 | 0/10 | 不明确 | 0 | 0 | 0 |
| timedelta运算 | 3/20 | 0.904× | 0 | 3 | 0 |
| date/datetime与时区 | 9/24 | 1.013× | 2 | 1 | 6 |
| relativedelta | 10/10 | 1.019× | 0 | 0 | 10 |
| NumPy标量 | 19/34 | 0.928× | 1 | 10 | 8 |
| pandas | 2/4 | 1.011× | 0 | 0 | 2 |
| Pydt | 8/8 | 1.040× | 1 | 0 | 7 |
| 批量 date/datetime | 14/14 | 1.127× | 10 | 1 | 3 |
| 批量 timedelta | 7/7 | 0.925× | 0 | 2 | 5 |
| 批量 Delta | 7/7 | 1.049× | 6 | 1 | 0 |
| pickle与复制 | 6/8 | 2.466× | 6 | 0 | 0 |
| 批量 Pydt | 4/4 | 1.046× | 0 | 0 | 4 |
| 批量 relativedelta | 4/4 | 1.040× | 0 | 0 | 4 |
| 批量 NumPy | 4/4 | 17.696× | 4 | 0 | 0 |
| 批量混合 | 2/2 | 1.421× | 2 | 0 | 0 |
| to_timedelta | 1/6 | 1.372× | 1 | 0 | 0 |
| 表示：新对象/交替/子类 | 1/3 | 1.034× | 0 | 0 | 1 |

分组倍率为明确项的等权几何平均；“明确/总场景”保留未明确项的数量，不用局部平均掩盖它们。

### 代表调用的实际耗时

| 调用 | Cython μs | Rust μs | 速度比 | 结论 |
| --- | ---: | ---: | ---: | --- |
| Delta() | 0.026 | 0.036 | 0.717× | Cython更快 |
| 多字段整数构造 | 0.194 | 0.201 | 0.969× | 接近 |
| 负值进位构造 | 0.178 | 0.184 | 0.964× | 不明确 |
| 毫秒/微秒构造 | 0.134 | 0.136 | 0.988× | 不明确 |
| 读取全部15属性 | 0.178 | 0.197 | 0.909× | Cython更快 |
| Delta + Delta | 0.025 | 0.033 | 0.773× | 不明确 |
| Delta + timedelta | 0.026 | 0.034 | 0.762× | 不明确 |
| datetime + Delta | 0.042 | 0.038 | 1.108× | Rust更快 |
| from_relativedelta | 1.748 | 1.727 | 1.016× | 接近 |
| Pydt + Delta | 0.606 | 0.583 | 1.034× | 接近 |
| repr同一对象（热） | 0.020 | 0.101 | 0.202× | 不明确 |
| 新建对象后首次repr | 0.113 | 0.132 | 0.854× | 不明确 |
| 两个对象交替repr | 0.076 | 0.087 | 0.870× | 不明确 |
| 子类repr | 0.097 | 0.094 | 1.034× | 接近 |
| 重复hash | 0.031 | 0.031 | 0.994× | 接近 |
| pickle保存基础Delta | 2.006 | 0.910 | 2.199× | Rust更快 |
| pickle读取基础Delta | 1.112 | 0.588 | 1.891× | Rust更快 |
| to_timedelta无起点 | 0.045 | 0.052 | 0.868× | 不明确 |
| to_timedelta月底起点 | 0.080 | 0.062 | 1.285× | 不明确 |

### apply_many同一规模直接对比

| 输入 | 元素数 | Cython μs/整次 | Rust μs/整次 | 速度比 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| date月底 | 1024 | 20.721 | 19.398 | 1.066× | Rust更快 |
| date月底 | 10000 | 190.622 | 189.922 | 1.001× | 接近 |
| datetime时长 | 1024 | 21.916 | 17.476 | 1.251× | Rust更快 |
| datetime时长 | 10000 | 197.939 | 169.492 | 1.166× | Rust更快 |
| Delta | 1024 | 20.895 | 17.549 | 1.189× | Rust更快 |
| Delta | 10000 | 187.405 | 169.288 | 1.109× | Rust更快 |
| timedelta | 1024 | 19.755 | 19.033 | 1.039× | 接近 |
| timedelta | 10000 | 177.997 | 183.545 | 0.971× | 接近 |
| Pydt月底 | 1024 | 610.084 | 580.739 | 1.047× | 接近 |
| Pydt月底 | 10000 | 6137.031 | 5876.234 | 1.044× | 接近 |
| relativedelta | 1024 | 1887.182 | 1813.370 | 1.040× | 接近 |
| relativedelta | 10000 | 18444.802 | 17697.375 | 1.042× | 接近 |
| NumPy datetime64 | 1024 | 424.253 | 27.735 | 15.410× | Rust更快 |
| NumPy datetime64 | 10000 | 4103.098 | 266.877 | 15.453× | Rust更快 |
| NumPy timedelta64 | 1024 | 429.349 | 21.095 | 20.319× | Rust更快 |
| NumPy timedelta64 | 10000 | 4181.280 | 206.362 | 20.266× | Rust更快 |
| 混合类型 | 1024 | 474.427 | 333.330 | 1.424× | Rust更快 |
| 混合类型 | 10000 | 4627.476 | 3259.236 | 1.418× | Rust更快 |

速度比定义为**Cython耗时÷Rust耗时**：大于1表示Rust更快，小于1表示Cython更快。逐项耗时为完整公共调用成本；批量耗时包含整份list及全部结果的创建、持有和释放，不能和单元素调用混读。

完整202项数值见[性能逐项明细](/Users/jef/ResilioSync/code/rsTimes/docs/Delta-Cython与Rust性能逐项明细.md)及[性能CSV](/Users/jef/ResilioSync/code/rsTimes/docs/Delta-Cython与Rust性能明细.csv)。分组为所选场景的等权描述，不代表实际业务调用频率，也不据此宣布整个类在任意场景都更快。

## 环境与测量方式

- 同一普通CPython3.13.3解释器、同一测量线程加载两个准确安装路径的扩展；双方源码和二进制不变。
- 共同依赖采用Rust交付环境：NumPy2.5.3、pandas2.3.3、dateutil2.9.0.post0、cytimes3.1.0、tzdata2026.5。Cython原环境是NumPy2.3.3/pandas2.3.2，历史成绩不混用；本报告明确描述统一环境下的表现。
- Pydt和第三方输入来自同一份共同依赖，避免输入实现不同造成假差距。
- 优先复用两边现有输入和公共调用，先逐项核对值与返回类型；仅拒绝规则的两个调用单列，不用更快报错证明收益。
- 短函数采用共同n的循环批量平均，最快方至少5ms；保留真实调用、分配与释放，GC正常启用，不扣除循环开销。
- 每个完整组使用C-R-R-C或R-C-C-R，平衡顺序；任一成员受明显干扰时整组回队。墙钟/线程CPU差≤10%、读取边界≤1%、读取成本≤0.5%，正式四批组跨度≤500ms。
- 全202项进行短/2倍长控制，倍率差≤3%；原始失败控制保留。两个NumPy批量长控制按2倍工作量使用1000ms跨度，并只重做这两项验证；正式短组质量和跨度未放宽。
- 主周期与独立周期各3个新进程，每进程每场景24个合格四批组、两种顺序各12组。完整时每项144组、576个计时批次；内部循环次数不冒充独立样本。
- 逐完整组按C总耗时/R总耗时计算倍率，全部合格组中位作为逐项估计。进程、顺序与主独倍率跨度均≤5%才给明确方向；±5%范围记为接近。这里是固定操作性检查，不是置信区间。
- 原始快慢样本均保留，不按胜负选择；稳定性不足标为不明确，不追加采集寻找更好的结果。

计时和筛查无法消除所有频率、温度或缓存竞争影响，结论限于此机器、依赖和这些真实调用。

## 身份、证据和原项目验收边界

| 项目 | Rust | Cython |
| --- | --- | --- |
| 固定版本 | 0.1.0+delta.3 / 97 | 0.2.0 / R2FinalE |
| 原生源码提交 | 5119a7f3aa4de8c4e6d33b9f0c0caf60733d5ac8 | 96045d63d7371fd0593ef1644de0dd9cb006731e |
| native SHA-256 | bdadd54566d4ad41ceed5591d57a6fa789cee9d09eaff4d2e5a84345d326bb73 | 3ef0ec227fe995ebb0c289f28d59ff69faa8847dcfd13b0755eaaf71fb289aba |
| 原项目最终验收 | 用户采用成果；完整双轮性能验收未全部通过 | 原交付记录的全部约定验收通过 |

这次直接比较不会把Rust旧验收的两项噪声、未执行独立周期改成通过，也不把Cython原锁环境的完整验收改署为当前共同依赖验收。

- [本次实际加载身份](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-comparison-20261013/identity.json)
- [两边wheel和源码提交核对](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-comparison-20261013/artifact-manifest.json)
- [全部功能观察](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-comparison-20261013/functional.json)
- [冻结采集配置及控制](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-comparison-20261013/config.json)
- [采集起止与预算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-comparison-20261013/campaign.json)
- [最终逐项汇总](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/delta-cross-comparison-20261013/performance-summary.json)
- [本次唯一计划与实际状态](/Users/jef/ResilioSync/code/rsTimes/tasks/delta-cython-rust-comparison-20261013.md)

## 交付范围

这是一份固定版本的功能与速度对比。完整接口清单及已观察差异已给出，不宣称穷尽所有Python输入、任意自定义子类或所有第三方版本。发现的缺口只记录，不自动进入修复或优化。

本次按120分钟预算完成对比交付，实际约45.1分钟，正式直接采集约18.7分钟。两边选定wheel及native指纹保持不变，未重建、安装、优化或发布。202项覆盖、质量和精度控制齐全；88项未达到冻结稳定性标准，仅报告观察值。完成对比交付不表示所有性能项稳定通过。
