# Delta 性能复测

工具入口为 `benchmarks/delta/bench.py`，短配对执行细节在 `paired.py`。输入只定义在 `tests/delta/cases.py`，固定九组93项及等权规则在 `benchmarks/delta/cases.json`；参考固定 cyTimes 3.1.0。先核对实际输出和冻结参考，再从真实 Python 调用计时。

## 当前快速复测

修改 Rust 后先构建明确的 release wheel，用 `tools/delta_check.py --group installed --wheel <wheel> --report <新报告>` 安装到候选环境，并检查受影响功能。旧二进制不能证明新代码。

```sh
.local/delta/build/bin/python benchmarks/delta/bench.py --protocol short --mode quick --group B5 --candidate-env .local/delta/candidate --short-ms 1 --pairs-per-block 20 --measurement-qos interactive
.local/delta/build/bin/python benchmarks/delta/bench.py --protocol short --mode quick --group all --candidate-env .local/delta/candidate --short-ms 1 --pairs-per-block 20 --measurement-qos interactive
```

quick 每项固定6个统计批次，每批次20个完整有效短配对。每个短配对的两方使用相同调用次数，较快方目标约1ms，整批耗时除以次数；统计批次使用全部完整配对耗时之和除以全部调用次数。调用、循环和结果释放成本保留，不扣除估计开销，不删除合格慢样本。quick只用于开发判断。

两方在同一隔离测量线程内紧邻执行。工具确认同进程内cyTimes二进制、解释器、依赖及输出与冻结oracle一致；子类pickle模块绑定在计时之外切换。调度等级仅调整本项目测量线程，两方一致，不暂停外部应用。

## 自动核验与有界补测

每个短配对在工作进程内测量并核验，减少进程通信成本。每批至少0.2ms，wall与thread CPU时间相差不超过10%；实际时钟读取边界不超过批次1%，时钟精度及实测读取开销不超过0.5%；整短配对跨度不超过250ms。主机前后快照必须包围测量，load/逻辑CPU≤0.8，free+inactive页估计内存比例≥3%。该内存估计不是全部可回收内存，speculative已包含在free中，不能重复相加。

主机CPU累计计数变化至少10tick才使用忙碌≤75%判断，计数不足只作诊断；线程CPU计时等必要证据仍需合格。上下文切换只作诊断。检查不消除频率、温度或缓存影响，因此还要检查配对结果波动。

任何一方无效，则完整短配对回队；已有有效短配对保留。无效项1秒退避，其他项继续。每项最多 `max(120,所需短配对数×3)` 次尝试，每会话累计最多600秒。上限不足或结果不稳定，记录“不明确”，不无限重试。持续仅候选一方无效需检查自身成本，不能统称外部干扰。

原始尝试逐条追加到 attempts.jsonl，初始状态与最终全量报告保存；测量期间不重复编码大报告；保存失败、原始异常或环境不匹配不能视作通过。断点续接保留有效配对、尝试次数和累计预算，不重置上限：

```sh
.local/delta/build/bin/python benchmarks/delta/bench.py --protocol short --mode formal --group all --candidate-env .local/delta/final-env --short-ms 1 --pairs-per-block 120 --session-seconds 600 --measurement-qos interactive --precision-evidence tasks/evidence/short-protocol-precision-05.json --resume <同配置raw.json>
```

代码、输入、native、runner、解释器、依赖、硬件及采样配置必须相同。优化代码后新测；原始数据可用于对照，但不能混入新版本的正式样本。工具仍保留 `--protocol legacy --previous <同输入/runner/环境的raw.json>` 开发候选比较入口；旧协议不能代替当前正式验收。

## 当前正式验收

```sh
.local/delta/build/bin/python benchmarks/delta/bench.py --protocol short --mode formal --group all --candidate-env .local/delta/final-env --short-ms 1 --pairs-per-block 120 --session-seconds 600 --measurement-qos interactive --precision-evidence tasks/evidence/short-protocol-precision-05.json
```

formal每项固定12个统计批次，各含120个有效短配对，共1440个有效配对、两方各约1440ms或更多测量时间。短配对轮流切换先后，每个统计批次内部也平衡；12批次分别6个从原版开始、6个从候选开始。统计批次是短配对之和，不能冒称连续240ms测量，也不能把大量调用次数当作大量独立样本。

1ms用7个既有代表输入，与5ms控制在同线程紧邻交替采集、四次测量同组核验：速度比差≤3%、计时边界≤1%、短方案波动≤5%。receipt绑定实际工具、输入、环境、配置及最终native。源码/配置变化后旧receipt拒绝，需针对受影响测量重新验证。

通过条件：

- P1 核心B1–B6等权组合速度比≥1.25。
- P2 每项两方中位每调用耗时比较，候选最多退步10%。
- P3 dateutil/NumPy两组等权组合≥1.00；保存复制仍遵守P2。
- P4 输出已核对、完整功能证据有效、最终release native一致。
- P5 全93项各12个完整统计批次、每批120有效短配对、次数及顺序匹配，精度证据有效。
- P6 任一统计批次的配对速度比偏离该项中位≤5%；各项最差完整统计批次速度比按原权重合成，核心≥1.25、第三方≥1.00；每项最差配对候选耗时最多退步10%。

这次P5/P6由用户授权调整：旧规则为7对≥100ms、两方各自波动及跨时点极值比较；当前用逐个核验的短配对、固定汇总量及完整配对保守比较。两者并不等价；1.25/10%/第三方不变慢目标保持。旧三轮P6失败结果完整保留，不追溯改判。

## 输出与边界

每会话独立输出raw.json、attempts.jsonl、summary.md、summary.csv。包含环境、输入、runner/helper、native指纹，全部有效/拒绝尝试、原因、各方拒绝次数、wall/CPU时间、校准、预热和调用量。部分场景或预算耗尽不可能取得全项目正式通过。

结论适用于本次macOS arm64、普通CPython3.13和锁定依赖、固定成功调用、通过环境检查的计算性能。不能据此宣称繁忙机器端到端延迟或全部业务使用量覆盖率。错误和极端输入由功能/安全检查保护，不为扩大性能数字反复计时。

优化后需要重新绑定精度证据时，可复用：

```sh
.local/delta/build/bin/python tools/validate_delta_timing.py --capture --candidate-env .local/delta/candidate --pairs-per-block 40 --output <全新精度receipt.json>
```

此有限验证固定七代表项、180秒预算；未通过则不启动正式验收。它不增加Delta输入或功能测试。

最终精度控制固定40微配对/批次，正式统计量120微配对/批次；两者目的不同：前者证明1ms计时可靠，后者补足正式采样量并由P5/P6核验。精度绑定实际计时源码/规则/native/输入/硬件及短批次长度，正式数据续接仍严格绑定统计量和全部配置。120是在第三次正式前由既有数据仅诊断确认的固定选择，不把旧失败改判通过。
