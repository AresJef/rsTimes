# PLDT与Delta纳秒升级最终验收与本地采用

日期：2026-11-02。最终采用对象：**source31／本地最终版**；实际Python发行元数据仍为0.2.0b2，公开PyPI／GitHub的b2并未替换。报告生成：2026-11-02T12:46:48.395053+00:00。

**结论：功能、安全、安装、32位置、类型／文档和交付核查通过；按本轮最终授权取舍采用source31。性能原始判定为624严格PASS、3稳定性INCONCLUSIVE、1稳定速度FAIL。3项稳定性例外由根Agent依用户本Goal明确委托作出；L209速度例外由用户逐项批准。不是628项全部严格PASS，也不是原始无例外门槛全部通过。**

## 1. 依据、范围与唯一最终对象

- 唯一新增行为正文：[最终讨论决定](/Users/jef/ResilioSync/code/rsTimes/docs/PLDT与Delta纳秒升级最终讨论决定-20261030.md)：14板块、60主项、GN01—GN13、D01.O1—O4、U1—U3，范围和例外一同执行。
- [当前执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/PLDT与Delta纳秒升级七十二小时执行计划-20261030.md)组织执行；启动逐字原件为[W00启动计划](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W00/plan-at-start.md)，不能用后来的预算修订替代原约定。
- 原有Pddt／Parser／Pydt未被本轮修改的行为仍按[Pddt唯一最终决定](/Users/jef/ResilioSync/code/rsTimes/docs/Pddt重写最终讨论决定-20261026.md)；Delta此次使用完整ns模型，不保留旧us值核或旧状态自动迁移。
- 交付核心类为Delta、Pydt、Pddt、Pldt。不开子Agent；未启动nogil、Pages、PyPI新版本或GitHub Release。隔离Draft PR 1及32位置CI属于本轮授权；未推用户主干、未合并、未建tag。

| 身份 | 本轮实际值 |
|---|---|
| 本机CP313 macOS ARM64实际native | `e15fb9e5ff96fc8af93573772d9dcf99edbc3e3f5b5bb2dd4155dcc3bc348f6f` |
| 本机实际wheel | `3298fddd5689bb0e04f47983a591e00f1f98a475a91e43ab016183d39aa2b9f4` |
| 完整sdist | `93f5e40b6ce3ebb40af94fdee4a2cf26c8fa55fa613b5d0c6f8bc9f551be385b` |
| 隔离CI源码提交 | `62fb0625fc137e8a803378d51b05f160d7b47fe1` |
| 隔离源码树 | `89f82a4e93b5ac3055fb4201e92d6fc99f064edb` |
| Actions实际checkout | `305291a37d52844fb1de0f1efe563610ea863993`；与133项必要生产输入一致 |
| 用户根工作区保留 | HEAD `985f836219203bfc10010b93c11076a04d7a9d0c`，分支`codex/delta-native`，原index SHA保持 |

分发manifest中的source_commit是保留的根HEAD，不应把它说成当前新实现的已提交源码；当前实现由133文件SHA清单、同字节CI树、安装wheel／native及完整sdist共同确定。跨ABI／平台native各有独立SHA，不能把本机e15复制成所有32平台的二进制身份。公开b2同名元数据也不能替代此核验。

证据：[分发清单](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W38/final-source-08/distribution-manifest.json)、[当前身份最终读回](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W39/SOURCE31-final-identity-readback-02/complete.json)。

## 2. 实现了什么

1. **Polars原生日期能力。**Pldt是真Series子类；普通Series和Expr提供`.pldt`，日期表达式直接返回原生Expr，正常DataFrame／LazyFrame执行，不逐行调用Python UDF或隐式collect。共同日期含义尽量与Pddt／Pydt一致，保留Polars自然返回、dtype和容器边界。
2. **完整输入到输出。**原生／文本／混合构造、parse／strptime、所有批准命名工厂／ISO／date_range、严格replace和便利移动、日历add/sub／Delta、时区、边界／snap／round／fsp、查询／diff、输出／格式、copy／pickle／业务子类均按逐项契约实现。普通调用在原生字段／缓冲内计算，尽量仅最后一次构造结果。
3. **Delta唯一精确ns内核。**相对nanoseconds和绝对nanosecond完整加入构造、字段合并、normalize、四方向、date／datetime／Timestamp／Pydt／Pddt／Pldt、NumPy ns标量左侧运算、批量、getter／比较／hash／repr、copy／pickle等。整数精确，合法二进制浮点贡献合并后在Delta值出口最后一次ns取偶；目标datetime／Pydt／timedelta按其us能力最终投影。没有旧us核兜底。
4. **共享修改。**纯Rust词法／字段完成／格式资料和原生错误由旧类与插件共用；保护Parser→Pydt既有行为。同步Pddt空／全缺失combine时钟列的来源时区、有效int64最小值来源、ISO／strptime／range目标时区和策略、字段replace namespace，以及三日期类strftime小数规则。
5. **能力差异明确。**Pldt为ms／us／ns和独立有效位，合法int64最小值不等于null；Pddt为s／ms／us／ns和NaT哨兵。已有对象运算固定unit，精度或容量不足报错，用户显式as_unit。Pydt保持us及datetime最终容量，宽年小核不提前受Pydt构造挡住。
6. **真正原生执行。**插件worker不触碰Python对象或重新attach；必要真实子类回调只在明确eager边界按真实协议执行。Configs／default／格式资料在规定时点快照，原生输入不强迫走公开Python parser。naive／UTC／固定偏移走捷径，地区时区保候选／infer／gap的完整规则。

共同入口示意，以下调用已通过当前安装示例／功能集：

```python
import polars as pl
from rstimes import Delta, Pldt

x = Pldt(["2024-01-31 12:00:00.123456789", None], unit="ns", name="time")
result = x.to_next_month()  # Pldt；2月29日，保留ns和null
result = x.pldt.add(nanoseconds=1)  # Pldt；使用同一ns日期内核
expr = pl.col("time").pldt.to_next_month()  # 原生pl.Expr
result = pl.DataFrame({"time": x}).lazy().select(expr).collect()  # DataFrame
delta = Delta(nanoseconds=1)  # 完整纳秒Delta
```

例子不意味着所有输出都包装为Pldt：布尔、整数、String、Duration、Struct／DataFrame按职责返回；单元素Polars提取遵循Python标量精度边界。格式化／默认／单位／字段／元数据的具体限制仍以唯一正文为准。

## 3. 功能、类型和历史正确样本保护

| 门槛 | 当前有效证据及结果 |
|---|---|
| 条款映射 | 60主项＋13 GN；D01.O1—O4／U1—U3另7行映射到当前来源和真实独立预期测试 |
| 入口与参数角色 | 126参考入口无缺失，729个自有运行入口／参数记录；明确区分实际阅读、运行验证、旧有效来源复核和只作存在盘点 |
| 本机当前安装主线 | 22962 PASS／1原条件SKIP；pandas2为22949 PASS／14原条件SKIP |
| 邻接旧行为 | 上一产物22865个case ID／结果／完整skip原因不变，新增98独立宽整数边界case全部PASS；更早S0保护和批准差异按此前各薄片清单保留 |
| 原生安全／质量 | Rust debug／release各84，fmt和严格Clippy通过；所有权、有效位、空列、宽整数、真实业务协议及释放边界有对应功能测试 |
| 当前安装文档与类型 | 7份pyi共752定义，缺失docstring／参数注解／返回注解0；158可执行示例0失败；6组mypy正负例按固定错误位置通过 |
| 当前四demo | 根目录／另一目录共8次通过；每次Delta150案例，未知差异0；实际绑定source31 native与正确oracle／main环境 |

数量本身不是行为正确性的证明。
完整对应关系保存在[条款／源码／测试映射](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W39/SOURCE31-entry-audit/final-clause-evidence-map.json)、[派生及优化映射](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W39/SOURCE31-entry-audit/optimization-and-derived-decisions.json)、[入口／参数盘点](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W39/SOURCE31-entry-audit/own-entry-parameters.json)。当前完整安装结果、原独立预期、各薄片负向证明与32位置XML分别提供行为证据；入口存在不冒充729项重新独立深审。
文档／类型的本机当前产物补核为[current docs/types](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W39/SOURCE31-current-docs-types/complete.json)；四demo为[八次实际结果](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W39/SOURCE31-demo-candidate/complete.json)。无关指南和历史记录未扩展重写。

## 4. 当前32位置跨平台与分发验收

[当前完整CI41379257407 attempt1](https://github.com/AresJef/rsTimes/actions/runs/41379257407)的39任务成功。32个实际wheel及38份原始ZIP均核对提供者SHA／大小，不只读绿灯。

普通64位GIL CPython3.12、3.13、3.14、3.15分别覆盖下表8平台，共32位置。

| 平台 | CPU／wheel环境 | 4个Python版本的成功任务用时范围 |
|---|---|---:|
| Linux glibc | ARM64／manylinux2.28 | 8.93—10.43分钟 |
| Linux musl | ARM64／musllinux1.2 | 14.27—15.33分钟 |
| Linux musl | x86_64／musllinux1.2 | 13.47—17.83分钟 |
| Linux glibc | x86_64／manylinux2.28 | 8.60—11.47分钟 |
| macOS | ARM64 | 10.98—12.78分钟 |
| macOS | Intel x86_64 | 20.18—27.35分钟 |
| Windows | ARM64 | 13.25—15.47分钟 |
| Windows | x86_64 | 14.20—18.62分钟 |

**整次正常工作流墙钟为50分55秒**，含队列和依赖关系；各并行任务用时不能相加冒充总时长。此表是当前成功attempt，调试／失败／旧CI和旧产物成本另留原记录。

| 已真实运行的安装lane | 数量／结果 |
|---|---|
| pandas3主线、固定Polars2.0.0 | 32 × 22962 PASS／1原SKIP |
| 适用pandas2.3.3兼容 | 21 × 22949 PASS／14原SKIP |
| core无dateutil／pandas／Polars | 32 × 4717 PASS／1原SKIP |
| core＋Polars2.0.0 | 32 × 6087 PASS／81原条件SKIP |
| 固定Polars2.1.0补充lane | 8 × 22962 PASS／1原SKIP |

合计125次实际安装smoke；再加两独立sdist重建和两oracle，共129条真实XML lane的case ID／结果／完整skip原因核对零差异。NumPy下限2.5.3；pandas3.0.6主线，Python3.15／Windows ARM64不承诺pandas2。dateutil／pandas／Polars保持可选，Pldt需要Polars，Pddt需要pandas。Babel仅oracle对照环境存在。

两代表sdist在空target真实独立重建并安装：Linux musl ARM64／Python3.15与macOS ARM64／Python3.13，各22962 PASS／1原SKIP；二进制SHA按各自真实构建记录。当前本机sdist与CI的实际SHA一致。

范围边界：这些是32位置的功能／构建／安装证明，不是32平台严格5%性能证明；不宣称32位、PyPy、free-threaded、所有系统小版本或所有任意依赖组合。Arrow功能有本机独立验证／2必要性能场景，部分CI条件skip按原意保留，不把它说成全部32位置Arrow均已执行。

原始来源：[32实际wheel核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W38/FINAL08-ci-artifacts/artifact-audit-final.json)、[129 XML保留核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W38/FINAL08-ci-artifacts/case-preservation-audit.json)、[sdist独立重建](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W38/FINAL08-ci-artifacts/independent-sdist-audit.json)、[分平台正常用时](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-normal-CI-platform-timings.json)。

## 5. 性能协议、完整原始读回和例外

冻结24物理比较轴、628必要比较＋8独立观察；同一API在S0／B0／相邻最佳版／不同已定依赖有分别保护，因此628不是628个不同公开函数。主机为macOS ARM64、同一CPython3.13.3、NumPy2.5.3；每配对依赖版本相同。S0是启动前公开b2；B0是本项目首个全功能可用基准；相邻主线保护按冻结图保留。

- 每必要项main／independent两轮，每轮9周期，每周期12完整紧邻配对、AB／BA各6；每项216对／36真实worker。必要135648选定对，含8观察共137376选定对。
- 12短／6长控制，双边归一耗时和倍率精度≤3%；每轮连续三组各3周期、顺序和跨轮稳定性≤5%；倍率R=对照／新版，两轮中位及保守倍率均须≥1/1.05。原始估计量未替换成置信区间。
- 完整公开调用含必要结果物化／释放，Expr计实际select／collect，计划建立另观察。真实并行调用按原端到端墙钟，thread／process CPU只诊断，不扣除或用单线程off-CPU公式拒收其必要等待。
- 全部控制／预试／正式样本、负面、机械拒收及整项来源保留；完成的新整项无论好坏替换，不按胜负择旧，不混不同配置配对。旧native时间未转记source31。
- 当前61份实际选定报告从只读原始样本重算，完整字典逐项相同，真实身份／数量／顺序／配置／源码hash检查通过；这不是另一个统计估计器或追加性能采集。
- 实际被引用的61份完整source报告原始合计attempts=149388、accepted=148176、rejected=1212；这是含已被其它文件替代行的完整source报告分母，不是137376个最终选定对的拒收分母。逐报告分母及机械拒收见[原始分母](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W37/SOURCE31-selected-source-rejection-denominators.json)，避免把未选取行重复混入最终得分。

原始选取：[全部636项来源和结果](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-final-selected-performance.json)。原始复算：[61报告exact replay](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W37/SOURCE31-selected-raw-replay/complete.json)。

### 5.1 严格结果与最终采用判定分开

| 类别 | 数量 | 解释 |
|---|---:|---|
| 严格PASS | 624 | 原精度、稳定性、双轮速度保护全部通过 |
| 稳定性INC | 3 | 原始判定保留；依据本Goal合理取舍明确委托，根Agent接受仅source31这3项稳定性例外 |
| 稳定速度FAIL | 1 | L209；用户逐项批准的source31专属例外，原FAIL不改写 |

624严格PASS的最大控制精度为2.959893%，最大稳定性波动4.997688%，最差中位耗时增加4.496314%，最差保守耗时增加4.951373%。这些最大值只描述严格PASS集合，不把3个INC的19.319%波动藏起来。

### 5.2 三项稳定性例外的实际依据

| 轴／项目 | 入口 | 精度 | 未过指标 | 原保守倍率下限 | 全216配对最小倍率 |
|---|---|---:|---|---:|---:|
| pddt-S0／X027 | `Pddt(polars_data.head(n))` | 2.829% | 跨轮19.319% | 2.640851 | 2.004048 |
| pddt-S0／N101 | `Pddt(date_column)` | 0.760% | 组间13.161% | 2.073270 | 1.564668 |
| pandas2-S0／X007 | `Pddt(polars_data.head(n))` | 0.897% | 组间14.247% | 3.070013 | 2.787389 |

每项完整216对／36worker均保留，648个选定配对中没有一对显示5%退化，最弱一对R=1.564668；最低原分组保守倍率R=2.073270。这是明确的观测保护余量，**不是证明其提速幅度已稳定，也不把INC改成PASS**。因此这些项不宣称可靠精确倍率；不能把它们当全局普遍性能保证。 这项取舍不是因为预算即将结束：作出决定时仍有约3小时余额；依据是完整配对的宽裕观测保护、有限尝试已穷尽以及继续盲试缺少信息增益，严格负面仍公开。

例外是在两个普通质量批次、真实双native模型、当前公开Pddt模块／原输出证明以及最后固定40ms／6n资格失败后作出的有限取舍。改变Polars线程数、扣减必要等待、继续同参数采到偶然PASS都未采用。新6n控制未合格不进入正式，保留上一份完整INC，不退回某个较好PASS。

授权区别必须明确：用户原先只逐项批准L209且带“无其他FAIL／INC”的条件；随后用户明确授权“在本次目标，后续的推进和收尾，合理的请求以及取舍统一approve，保证项目完成交付”。根Agent在此委托下另行明确批准3项稳定性例外，并明文修订该source31采用前提为“624严格PASS＋这3稳定性例外＋原L209速度例外，无其他未批准缺口”。**不是声称原来的无INC条件已满足，也不是用户亲自逐项回答了这3项。**

完整决定及原始依据：[委托下3项产物专属稳定性决定](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-three-stability-specific-exceptions-delegated-decision.json)、[648配对描述性核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-residual-three-quality-raw-audit.json)。不延用到其它产物、项目或条目。

### 5.3 L209原速度FAIL

L209是Pldt.strptime解析1000行带9位小数的格式文本。精度1.2499%、稳定性合格；主轮121.363→126.529us／完整调用，独立轮124.842→129.056us，中位耗时分别增加4.35%／3.45%，最差保守增加6.239467%超过原5%。原始216对／36worker及FAIL保留，没有为同一实现反复重采寻更好速度。此项不证明格式解析主体改动是根因：对应Python入口及Rust读取主体与B0未变，未做未经实测的因果归属。

用户批准来源：[L209逐项批准原件](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-L209-specific-exception-approval.json)；后续条件修订在上一节新决定明示，原件不改写。

## 6. PLDT相对B0的优化成果

合同主分数只用101个Pldt必要场景：八个不重叠成本族，族内调用等权几何平均，再对八族等权。没有因行数或采样n不同改变权重；SDK2.1、Arrow、新Delta等不掺入主分数。

| 成本族 | 场景数 | 主轮倍率 | 独立轮倍率 |
|---|---:|---:|---:|
| B01 构造／工厂 | 27 | 1.322933 | 1.320223 |
| B02 文本／格式解析 | 13 | 1.033972 | 1.037068 |
| B03 字段／日历变换 | 12 | 1.222520 | 1.220423 |
| B04 Delta算术 | 11 | 1.061987 | 1.058319 |
| B05 时区／DST | 10 | 1.013404 | 1.012776 |
| B06 查询／diff | 11 | 1.137934 | 1.134867 |
| B07 单位／导出／格式 | 10 | 1.087100 | 1.087143 |
| B08 完整Lazy管线 | 7 | 1.005373 | 1.005890 |

主轮八族组合：**1.105961倍**；保守1.104834倍；中位耗时减少9.581%。

独立轮八族组合：**1.104993倍**；保守1.103110倍；中位耗时减少9.502%。

**两轮均达到可选1.10倍争取目标**，没有达到1.20倍。这里的组合提升不能抵消L209原单项FAIL，原FAIL仍靠明确批准的例外处理。不是每个函数都更快。

### 6.1 旧类／共享模块与补充对照

以下为每组内部调用等权描述性倍率，帮助理解不同范围；不是把所有628异质比较再混成一个分数。

| 范围／对照 | 必要项数 | 主轮 | 独立轮 | 状态 |
|---|---:|---:|---:|---|
| Delta／shared-S0 | 50 | 1.040193 | 1.038648 | 严格PASS |
| Parser/Configs／shared-S0 | 45 | 1.043287 | 1.039812 | 严格PASS |
| Pydt／shared-S0 | 42 | 1.007539 | 1.007329 | 严格PASS |
| Delta／shared-B0 | 50 | 1.147937 | 1.147259 | 严格PASS |
| Parser/Configs／shared-B0 | 45 | 1.059254 | 1.058982 | 严格PASS |
| Pydt／shared-B0 | 42 | 1.016511 | 1.017368 | 严格PASS |
| pddt-B0 | 45 | 1.156016 | 1.157868 | 严格PASS |
| pandas2-B0 | 35 | 1.122191 | 1.122709 | 严格PASS |
| SDK21-B0 | 15 | 1.280804 | 1.282125 | 严格PASS |
| new-NS-B0 | 35 | 1.263060 | 1.264204 | 严格PASS |
| pddt-S0 | 45 | 1.215106 | 1.216819 | 包含稳定性INC，只列观测 |
| pandas2-S0 | 35 | 1.172545 | 1.172566 | 包含稳定性INC，只列观测 |

所有24物理轴／21语义对照组、fraction、格式、准备、Arrow、grid和相邻主线保护均在完整附表中。上表不以总提速掩盖某个较慢调用；3个INC所在组的描述性几何倍率不作为稳定精确提升承诺。

### 6.2 全部慢项

**225个必要比较至少一轮中位耗时高于各自对照**，已按最差中位增幅降序完整列出。细微的0.x%并不被包装为独立统计显著性；两轮绝对耗时、原倍率／保守倍率、配置和来源全部保存。
- [全部225慢项CSV](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-final-all-slower.csv)。
- [完整分类及225项可读附表](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-final-performance-appendix.md)。
- [全部636比较含双轮绝对ns](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-final-all-comparisons.csv)。

最慢中位增幅的前10项如下；us为一次完整调用，包含该场景规定的整列工作量，并非每行耗时。中位倍率按配对统计，A／B绝对耗时各自汇总，因此不强求二者的商与配对中位完全相同。

| 轴／项目 | 调用 | 最差中位增幅 | 对应轮A→B（us／调用） | 原状态 |
|---|---|---:|---:|---|
| SDK21-B0／L304 | `x.to_next_month()` | 4.496% | 3101.937→3239.396 | PASS |
| pldt-B0／L209 | `Pldt.strptime(text,"%Y-%m-%d %H:%M:%S.%f",unit="ns")` | 4.347% | 121.363→126.529 | FAIL |
| pldt-B0／L304 | `x.to_next_month()` | 4.249% | 3100.203→3246.771 | PASS |
| shared-S0／S003 | `Delta(year=2025,month=2,day=28,hour=9)` | 3.675% | 0.131→0.135 | PASS |
| shared-B0／EW02 | `parse_epoch(2**80,unit='s')` | 3.586% | 0.143→0.147 | PASS |
| shared-S0／D114 | `delta.microseconds` | 3.416% | 0.017→0.017 | PASS |
| pldt-B0／L303 | `x.to_next_month()` | 3.250% | 42.537→43.913 | PASS |
| SDK21-B0／L702 | `x.as_unit("us")` | 3.120% | 11.025→11.351 | PASS |
| shared-S0／N008 | `delta+np.datetime64('2024-05-07T15:30:01','us')` | 3.032% | 0.125→0.128 | PASS |
| pldt-B0／L208 | `Pldt.strptime(text,"%Y-%m-%d %H:%M:%S",unit="us")` | 3.017% | 108.828→112.017 | PASS |

采集器表达式里的parse_epoch只是对公开parse_to_epoch的局部绑定；没有恢复旧公开名称。

## 7. 保留与未采用的优化

最终只有一份累积主线source31。保留的有依据方向包括：每批一次prepared civil日期移动、精确float首次二进制拆解后合并、少数已实测小日期helper内联、小列安全快照与合法年份证明、公开整数出口保留SDK路径并调整宽度判断顺序、已知NumPy单位的native常数除法及原i128宽倍率回退。D01.O1—O4分别有评估／独立测试和处理记录，不把必要功能自动算成提速。

未采用／已撤回的路线包括：通用EpochOutput枚举／Bound输出／exact-int identity分流、全量projected-reader外提、没有可靠收益的宽整数通用常数除法替换、宽整数字节裁剪、未经证明的零字段日历分支或compiler hint。没有为适配旧产物加入兼容层，也未将部分候选各自通过的部分拼成“最终”。

完整历史索引[source31累计选择及全部负面链](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-optimization-history.json)指向所有实际原型和开发／正式结果。source29两个稳定速度失败、source30负面和更早失败均保留；这些不是source31正式成绩，不转记其时间。

## 8. 独立资源与启动观察

本机9个新进程／角色，S0、B0、source31按固定顺序轮转，总27次。未清文件系统缓存，因此不称磁盘冷启动；无新发明5%资源门槛，不混进热性能组合。

| 角色 | import中位 | 首次插件select中位 | 导入后峰值RSS中位 | 插件后峰值RSS中位 |
|---|---:|---:|---:|---:|
| S0 | 194.361ms | 原包无Pldt | 93.48MiB | — |
| B0 | 200.354ms | 0.995ms | 94.94MiB | 106.44MiB |
| SOURCE31 | 200.404ms | 0.986ms | 94.84MiB | 106.30MiB |

source31本机native展开21,681,760B，wheel 6,484,632B（native压缩5,970,550B），sdist 911,387B；B0 native21,435,344B，旧S0 native2,951,136B。新增Polars原生实现后包明显大于旧S0，不能声称零体积代价；相对完整新功能B0增幅约1.15%。启动／RSS观测不能当稳定内存优化证明，owner／释放安全仍由专门测试承担。

当前本机构建日志实际Cargo release阶段为1分08秒，属于共享target的增量构建，不是干净完整Maturin墙钟；干净跨平台构建／安装／全测用时见第4节实际任务记录。

来源：[当前启动和RSS全部27进程](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-startup-observation.json)、[当前文件尺寸及真实构建日志来源](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W39/SOURCE31-final-identity-readback-02/resource-observations.json)。

## 9. 过程、预算与实质偏差

原预算72小时／4320分钟，后续明确追加180、120、60、60、120分钟，当前81小时／4860分钟。沿原T0 2026-10-30T05:31:11Z，带入本项目规划46.9044251分钟，必要纯等待合计115.86889963333333分钟单列；普通CI、工具、采集、分析和此报告均计时，不以并行相加或重启候选刷新时间。

当前有效已用公式为：46.9044251＋(当前UTC−原T0)/60−115.86889963333333。最终实际有效用时和各等待区间以budget-final.json／唯一ledger结算，不用本报告生成时间冒充最终完成时间。当前延续口径下硬边界为2026-11-02T15:40:08.868472Z；不自动加时。

实际偏差及纠偏：

- 首次完整可用B0和若干阶段软目标偏差按ledger实际区间保留；原72小时未能完成，追加9小时均有用户明确记录。没有把事后计划修订说成原来的安排。
- source31初采原预测270分钟，按当前72份控制实跨度重估约311分钟，最终实际314.278620分钟。原过于乐观预测及新增预热／窗口成本导致的偏差保留，未删样本来赶点。
- 普通预热／窗口质量调整2／2批已用完；随后按本Goal明确委托作有界实际双native／公共模块模型验证，原始身份、完整输出、端到端计时、样本／统计不变。所有扩展和最后6n固定集合均事前记录，不把它们冒称原计划两批仍有余额。
- 当前源不变的累计initial／quality数据最终选取600→624严格PASS；不按快慢择配对。多次预热无益的条目停止，不继续盲试到偶然通过；剩3个具体质量取舍明示为例外。
- 模型2首次检查了旧S0没有的新helper，计时前失败，约2分钟内按真实共有helper校正并保留原脚本／日志；无真实产品错误或已测结果被改写。
- 为避免最终读回和最后采集重叠，核对PID后仅停止尚未开始的本Goal等待控制器；没有停止目标采集、原样本或其它应用。默认sandbox拒绝进程操作后，经针对该已核验自有等待进程的工具批准完成。
- 最后安装身份检查误把24个py／pyi／pytyped和“25载荷”比较；第25项是资源JSON。修正为确切25项SHA清单后新进程一秒内全部通过；第一次脚本exit1保留，不把原pipeline改成全绿，也未重做成功的统计／raw replay。
- T4380／4410曾实际迟延44.001／14.001分钟；其它自查的实际迟延、原因及动作逐条保留。没有补造准时检查或将没有进展的宿主间隔扣作等待。流程偏差与产品采用分开评价。

最后剩余交付从原85分钟调整为50分钟是在当前入口／八demo／启动观察实际完成后作出的有据再估，不删除必要工作。最终全部有效门槛与授权例外确认后即结束，不为用完81小时新增优化。

唯一台账：[ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/ledger.json)；5次追加分别见W40显式75／77／78／79／81小时批准；最终结算：[budget-final](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/budget-final.json)。每30分钟自问／纠偏的实际记录列在ledger.checks，不因本报告的总结代替原记录。

## 10. 使用、保存和最终核查

本机采用环境：

```bash
/Users/jef/ResilioSync/code/rsTimes/.local/pldt-72h-20261030/repair-31-main/bin/python -c "from rstimes import Delta, Pydt, Pddt, Pldt; print(Delta(nanoseconds=1)); print(Pldt(['2024-01-31'], unit='ns').to_next_month())"
```

wheel：
`/Users/jef/ResilioSync/code/rsTimes/.local/pldt-72h-20261030/candidates/formal-repair-31/rstimes-0.2.0b2-cp313-cp313-macosx_11_0_arm64.whl`

sdist：
`/Users/jef/ResilioSync/code/rsTimes/.local/pldt-72h-20261030/candidates/final-source-08/rstimes-0.2.0b2.tar.gz`

这两个是本轮已验证本地分发件；不能用pip安装公开0.2.0b2来替代它们，也没有覆盖已发布b2。四demo/runtime已实际绑定source31及SHA，前三个官方对照保留隔离oracle，Pddt用main；root源码与133manifest一致，AGENTS另外更新本轮采用事实及断言，历史公开b2／失败产物不删除。

最终交付核查：[adoption-completion-audit](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/adoption-completion-audit.json)；准确结束状态／后续入口：[CURRENT-RESUME](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/CURRENT-RESUME.json)。原始证据、负面、31代累计选择索引和全部旧冻结产物保留。

## 11. 最终结论

- 功能／安全／类型文档／32位置构建安装：本轮必要范围通过。
- 性能原始严格口径：624 PASS／3 INC／1 FAIL，未达无例外全PASS；Pldt核心八族组合两轮达到可选1.10目标。
- 本轮最终采用条件：用户直接批准L209及根Agent依后续明确委托批准3个产物专属稳定性例外后通过；未批准缺口0。例外不继承到下一版本。
- 执行过程：有软目标偏差、明确追加预算和真实自查迟延；保留事实，不以产品交付反过来抹掉流程问题。
- 发布：仅本地采用／隔离Draft PR和CI；公开b2、主干、tag、Release、PyPI未替换。

因此：**当前source31有充分本轮证据按最终授权的例外条件采用；没有充分依据称它符合原始完全无例外的628项严格全绿标准。**

## 最终结算

最终保存／读回结算时刻：2026-11-02T13:05:46.684240+00:00；本轮有效已用 **4705.630分钟／78.427小时**，批准总额4860分钟／81小时，未用 **154.370分钟**。原72小时预算差额+385.630分钟，在用户明确追加总额内；纯等待115.868900分钟单列，普通工具／CI／采集等待及最后119链接／哈希读回均计入。余额随本Goal完成停止，不转新任务。最终采用source31，含4项明示例外；不是原始严格628项全PASS。
