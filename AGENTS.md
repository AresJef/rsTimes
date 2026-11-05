# rsTimes 现行核心指令

2026-11-05。现行核心断言共26条／77子条款；适用范围和例外是断言的一部分。已采用实现范围见下；未批准的扩展不因断言文字而自动启动。

## 当前公开采用：rsTimes 0.2.0b3

- **公开采用Python0.2.0b3／Cargo0.2.0-beta.3／v0.2.0b3。**源码dc878ef53f531f09c3bfe22348850bf9f163c7ee，树49c399cc688f3c0185558fbd319368e068638bff，注释tag对象57c9590fe163065bdfc93f7981400a67806fd80f。核心类仍Delta、Pydt、Pddt、Pldt；发行算法与R18 final01一致，135生产输入中只有4项版本／交付元数据变化。RV03—RV05与P3仍未处理，不把历史成绩或旧例外转记本包。
- 同源main CI41982305161 attempt1的56必要job成功，32普通＋16t共48 wheel／1sdist；104原ZIP、184真实安装检查／186XML、3个fresh-target独立sdist重建及2oracle均已独立读回。代表普通23843PASS／5条件SKIP、t23846PASS／2、两oracle各29947PASS／18；各位置以实际XML为准，旧案例无未解释变化。干净完整CI墙钟3小时6分37秒；16项上游SDK资格实际cache miss，不能用暖pilot代替此完整时间。
- **本包94必要性能全部严格PASS，0FAIL／0INC，无产物例外。**每项216完整配对／36真实worker，20304选定对、648不同worker；41540原始正式成员与1692选定控制对独立复算。最大精度2.932926%、稳定性3.721199%、最差保守耗时增加3.031401%；原3/5/5与覆盖／样本保持。仅六macARM ABI差分保护，不宣称全平台严格5%计时或新增统一提速。
- GitHub Release435062763的52公开资产全部实际下载核对；PyPI49文件与原封存清单一致。发布42011736440首轮47公开位置成功、1个合成watchdog诊断测试失败；只重跑macIntel315t后通过，144公开安装／XML与同文件fullCI核对。原FAIL、恢复及API克隆历史成功job的新ID均保留，不称首轮全绿；50既有成功job的真实时间和步骤未重跑，产品未重建／重传，tag未移动。
- CP313／macARM公开native SHA256为3d7eec63be232574d419952eb0932961d7e87a1a8ffdd0ca31f53735e110ed5b；wheel59b7d661d7d0a5aceaa1e1c15587a8061df74d7c2ec90520a4b811d4053346a5；sdist94d1a08d2c65817e075906e12ca3cbefe55841397d775e7d251bbeb1f46bf3b4。各ABI独立身份；所有wheel各27非native载荷＋1native。Pyright1.1.414／Node26.7.0、三语言41活动文件、993声明／162例子通过；43既定demo诊断和51具体语句例外保持，意外诊断0；Rust89debug／89release、fmt／严格Clippy通过。
- 普通CPython3.12—3.15及3.14t／3.15t同源，八个64位平台与既定依赖范围保持。**D01不变：**内部使用固定未改官方Polars2.1.0源码SDK验证；不维护fork、不分发自建runtime，不承诺所有平台均有官方现成t wheel。用户自行取得兼容上游依赖；t实际导入／真实工作GIL保持关闭，不用强制关闭参数。性能计时器不冒称逐计时批额外探测GIL。
- 主环境`.local/beta-b3-release-20h-20261105/public-main`，前三官方对照demo用独立`public-oracle-demo`（Babel／cytimes仅对照）；core无可选集成环境亦已验证。四demo根／另一目录8次运行、Delta150场景未知差异0；源码／pyi身份、指南／runtime与公开包同步。后续验证维护通过正常PR／CI；不改变已发布产物，也不把新构建转为采用对象。根原HEAD／分支／index及全部既存修改保留。
- [统一发布流程](docs/RELEASING.md)、[本轮报告](/Users/jef/ResilioSync/code/rsTimes/docs/rsTimes-0.2.0b3合并发布与验收-20261105.md)、[唯一ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/beta-b3-release-20h-20261105/ledger.json)、[完成核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/beta-b3-release-20h-20261105/adoption-completion-audit.json)。48小时原T0／已用沿用，软调配、自查迟延、工具疏漏与原负面如实保留。主Agent独立，未启动／咨询子Agent；收尾结束后本轮合理approve授权失效，不为余额扩新项目。

## 历史本地采用：R18完整NumPy检查器优化 final01

- **本轮本地采用R18 final01，完整检查、真实子类与原异常职责不变。** 主Agent独立完成，未启动或咨询子Agent。仅优化P1原生typed迭代与P2单位一次准备；P3直接NumPy缓冲重写未做，RV03—RV05仍开放、暂不处理。包元数据仍0.2.0b2，公开PyPI b2仍是旧发行，本轮未提交、推送、远端CI、tag、Release或PyPI。
- 135生产输入仅`rust/pldt/output.rs`改变，SHA256为`e29317c555e39908220ed6df7ce7ad62204961acfed3a423671aa4f803efb238`；其余134项、Python／pyi／依赖不变。源日期和实际目标日期每行完整比较，独立validity、有效MIN、ns、乘数、Y/M、sub-ns、精度／容量及首个错误位置保持。复用既有单位解码，i64先扩大到i128再乘，宽因子保留checked计算和原错误冷路；无新unsafe、全局锁或裸缓冲借用。
- Python exporter绑定、一次实际回调、捕获的同一owner、copy和真实业务覆写保持。新增68独立答案Python案例、5个Rust案例；1204当前final05／final01实际返回和完整错误对照一致。12本机功能lane全部通过，旧案例ID／结果／完整skip原因无未解释变化。普通313／314／315各23818PASS／5条件SKIP，314t／315t各23821PASS／2，Arrow313及312各23987PASS／3，pd2／Polars2.1定向各2118PASS；Rust89debug／89release、fmt／严格Clippy通过。
- 六本机ABI真实release wheel、完整sdist及从sdist重建安装通过；重用编译缓存，不称空target。14实际安装视图逐项28载荷及native、真实工作、可选依赖读回；t不强制关闭参数，工作前后GIL实际保持关闭。本轮为macOS ARM64本机差分验收，**不是新48位置CI，不转记旧CI或旧时间。** CP313实际native为`7c963fe3881300f0f2352bad51842afbf97d1ddf1bc3ccee7bcfe8a6708cc601`，wheel为`cdc64cc3d3b7cc9353ebbc2bbc3981d633c6ba629125fd9fa816b94e3c9653a9`，sdist为`160128277e49b5662b06a2062dfdeb5498070da75670003d06b0f8326941433d`；其他ABI分别登记。
- **94项必要性能全部严格PASS，0稳定速度FAIL／0INC；另1历史观察质量合格。** 每项216完整配对／36真实worker，选定20520对、必要20304对，684不同真实worker；42164来源文件成员质量和1710选定控制对从raw独立复算。最大精度2.977294%、稳定性3.412443%、最差保守耗时增加2.556831%；原3%／5%／5%与覆盖／样本不变，没有继承或新增产物专属性能例外。
- 主R18同公开调用对当前final05双轮1.368377／1.371468倍，约27.76／28.01µs→20.31／20.39µs；普通R15约1.42倍，16384行日期导出约2.29—2.33倍。其余R18兼容／ABI代表均有可靠收益；不是全库统一提速。对旧未承担完整保护的doc02路径仍有约48.5%—48.9%中位耗时增加，仅作本轮新采历史观察，不把旧错误路径设为5%否决条件。
- 初采搬用了四项旧观察的不同reference表达式，原3FAIL／1PASS不构成本轮同公开调用退化结论。DQ02保存疏漏与全部raw，四项包括原PASS整体用同一真实公开调用重新216／36验证，全部PASS；原冻结文件未覆盖。另CP312两项原稳定INC，在一次限定40ms、固定9周期预试实测质量改善后，完整双轮整项替换，不择优回退；旧负面全留。
- Pyright1.1.414仍唯一检查器，三语言／40活动实现通过，意外诊断0；43既定demo诊断和51具体语句例外保持。993定义／162可执行示例通过。指南、runtime及四demo同步，根／另一目录8次运行通过，Delta150案例未知差异0。主安装`.local/r18-numpy-check-optimization-20261105/final01-main`，前三demo用独立`final01-oracle-demo`，Babel／cytimes仅供官方对照。
- [本轮报告](/Users/jef/ResilioSync/code/rsTimes/docs/R18检查器优化与验收-20261105.md)、[完成核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/r18-numpy-check-optimization-20261105/adoption-completion-audit.json)、[唯一ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/r18-numpy-check-optimization-20261105/ledger.json)、[预算结算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/r18-numpy-check-optimization-20261105/budget-final.json)。480分钟、原T0沿用，重启不重置；检查迟延、工具准备错误、比较配置疏漏及所有未采用原型如实保留。根HEAD／分支／index及历史证据保持。本Goal结束后统一approve失效，不为剩余预算继续扩展优化。

## 历史本地采用：RV01／RV02 final05（Arrow日期输入与NumPy导出修复）

- **本轮本地采用final05，只关闭RV01、RV02；RV03—RV05仍开放、暂不处理。** 主Agent独立完成，未启动或咨询子Agent。包元数据仍0.2.0b2，公开PyPI b2是旧发行；本轮未提交、推送、远端CI、tag、Release或PyPI。
- 135生产输入中仅`src/rstimes/pldt.py`改变，其SHA256为`2d25bd18a22d929ea2bcef1601802f6443e5661fe7046edd61da4c4780eb34b0`；其余134项、Rust／pyi／依赖保持原doc02。CP313／macOS ARM64实际native仍`d839ba9291b072decf082a1750ed021006cd13a7cd6200dd79cf088a4f5f8f79`，但新wheel为`f62b5dccfea3519532f5fd3697b95dc93b460d9171223885f3661573df8d99bc`，完整sdist为`09aaaa8341d0ce0dcc9caf43f31649c725f945b43c2cf3469413f42c3394d33c`。不能据相同native或版本号转记旧包成绩。
- RV01以真实pandas Arrow timestamp类型和公开Arrow／Polars交换统一构造、日期工厂、combine、正向相减、eager／Expr diff；保ns、单位、时区、独立validity和有效MIN，导出一次。普通非Arrow路径不增加PyArrow依赖。fromdate／fromdatetime／combine各自已确认的日期／时钟／目标时区职责保持；不增加继承Polars反向相减的支持承诺。
- RV02根据一次实际exporter绑定识别库原出口；共享一个已捕获owner完成SDK导出和目标保值检查。普通属性包装不取消精度／缺失／容量保护；真实业务覆写、descriptor和动态替换仍保其返回及原异常，实际外部callback只执行一次。copy遵循成熟NumPy／Polars协议。
- 新191独立case全部通过：163Arrow输入、26实际导出、2个有进程deadline的2／4线程共享读取。189串行case在旧doc02为127FAIL／62正常控制；最终旧案例ID／结果／完整skip原因无未解释变化。普通313／314／315各23750PASS／5条件SKIP，314t／315t各23753PASS／2条件SKIP；Arrow313及312各23919PASS／3条件SKIP，pd2／Polars2.1定向各2050PASS；按真实XML testcase计数。
- 六本机ABI wheel、完整sdist及代表真实release重建安装已核；重用编译缓存，不称空target。14实际安装视图新进程完整载荷／native／依赖及真实工作通过；t不强制关闭参数，工作前后GIL保持关闭。无pandas／Arrow的Polars-only环境和core分支均验证。**本轮是批准的本机差分验收，没有重新跑48位置CI；旧CI不转记新Python包。**
- **本轮必要性能严格44PASS／1稳定速度FAIL／1精度INC，共46项；另4观察质量合格。** 每项216完整配对／36真实worker，共10800选定对（必要9936），396不同真实worker；21600成员质量、900控制汇总及全部分组／身份独立复算。44严格PASS最大精度2.513271%、稳定性4.880500%、最差保守耗时增加2.532496%。
- 依本Goal用户对合理请求和严谨合理代价取舍的明确委托，主Agent修订**仅本final05**两项采用条件：main/R18保留FAIL，1024行转发属性子类ns→us导出补回必要检查，约13.54µs→27.51／27.82µs，最差保守+106.7202%；main-R12-diagnostic/R12保留INC，短长精度4.8466%＞3%，完整216／36诊断稳定性4.9245%、保守耗时增加2.5633%。不是用户逐项亲批，不降低全局3%／5%／5%、覆盖／样本，不设功能安全例外，不继承旧例外或延用新产物。**原全部必要严格通过未达成；明确修订的本轮采用条件已完成。**
- Arrow四个同义1024行场景约60—208倍加速，不是全库统一提速；普通路径按逐项实际报告。所有失败控制、INC、已拒绝候选和原始数据保留，没有以旧错误作为同义速度基准。
- Pyright1.1.414仍唯一检查器，三语言配置、40活动实现通过，意外诊断0；43既定demo诊断保留。删除失效TY034，TY031只随同一SDK边界移动，51具体例外；993定义／162可执行示例通过。指南、runtime及四demo交付选择同步；根／另一目录8次demo通过，Delta150案例未知差异0。
- 主安装`.local/doc02-rv01-rv02-fix-20261104/final05-main`；前三demo用`final05-oracle-demo`，其Babel／cytimes只供官方对照。旧环境、根HEAD／分支／index、四延期实现及338份旧审查文件保持。D01上游runtime供应边界与全部现行断言不变。
- [本轮报告](/Users/jef/ResilioSync/code/rsTimes/docs/RV01-RV02修复与验收-20261104.md)、[原计划](/Users/jef/ResilioSync/code/rsTimes/tasks/RV01-RV02轻量修复与验收计划-20261104.md)、[两项采用条件](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc02-rv01-rv02-fix-20261104/S04/final-adoption-conditions.json)、[完成核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc02-rv01-rv02-fix-20261104/adoption-completion-audit.json)、[唯一ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc02-rv01-rv02-fix-20261104/ledger.json)、[预算结算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc02-rv01-rv02-fix-20261104/budget-final.json)。原360分钟及已用规划不重置；阶段超软目标、自查迟延及工具准备负面如实保留，产品与过程分别评价。本轮结束后统一approve失效，不为余额续开工作。

## 历史本地采用：doc02／fix02（七项审查修复与性能补证）

- **采用本轮doc02／fix02，核心类仍为Delta、Pydt、Pddt、Pldt，普通CPython3.12—3.15及3.14t／3.15t同源。** 隔离CI源码`63fc3be0d1e85c2e41a70b871a722e84481bf545`，树`eb4d6796c85a6c00b17c3b0656bef2de5a4d5615`。包元数据仍0.2.0b2，公开PyPI b2仍为旧发行；不以版本字符串认定产物相同，不转记历史时间成绩。
- 七项修复分别为：整列业务回调返回日期列拥有自己的validity；浅／深copy hook遵循标准库的真实查找及绑定；实际类定义不受元类展示MRO／字典替换；错误冷路安全预览不覆盖原异常；线程高风险case有独立可回收进程／启动执行清理deadline；九日历工厂非可空单位注解与运行一致；carrier的s/ms/us/ns与Polars最终ms/us/ns职责分开。普通源null、逐行回调、固定单位、纳秒、时区及真实子类协议继续保护。
- 本机CP313／macOS ARM64采用native SHA256 `d839ba9291b072decf082a1750ed021006cd13a7cd6200dd79cf088a4f5f8f79`；本机wheel `e31e93259adb693434a100b6995c3848300080f0d5a7bed4f144cb9f35c2d91d`；完整sdist `ee6288229f8eb66c0860b1bfa112dad129aae2a74eb2510665211771301ff5ea`。135生产输入与sdist／CI源码相同；21个实际本机安装视图各28包文件=27非native（含JSON资源）＋1native逐项读回。CI不同平台／ABI的native各自登记，不据同源声称二进制相同。
- CI41780361380 attempt1，56／56SUCCESS：8平台×6ABI，共32普通＋16t、48wheel＋1sdist、3空target独立重建、2oracle；104原始ZIP、184安装smoke、181验证XML另加5重建／oracleXML全部读回。代表普通23722PASS／4原条件SKIP、t23725PASS／1、pd2兼容23709PASS／17；两oracle各29826PASS／17，实际按各XML。旧case ID／结果／重复次数／完整skip原因无未解释变化；13原线程函数主体保留。600个新增产品回归在旧doc01为277FAIL／323正常控制，当前全过；9个watchdog故障／正常控制亦通过。完整最终成功CI3小时12分02秒，不包括此前三次调试失败／取消运行。
- **本轮必要性能严格151PASS／1稳定性INC／0稳定速度FAIL，共152比较、32832选定配对；每项216对／36真实worker。** 全部2736短长控制对与71136成员批次公式独立复算。151严格PASS最大精度2.981279%、稳定性4.922282%、最差保守耗时增加3.988514%。EVD01普通3.14／3.15的S0→R／R→F／S0→F三轴36项及3.14t／3.15t同ABI R→F十二项全部严格PASS。其余历史675／631项只属原doc01，不冒称本轮同native成绩。
- 依**本Goal**用户对合理请求和合理代价取舍的明确委托，主Agent接受仅当前CP313 native的`shared-R-F/NT01`稳定性采用条件：精度2.462973%、稳定性5.027386%（比5%高0.027386个百分点）、最差保守耗时增加1.955821%。原严格结果仍INC，原完整数据／失败控制保留；13份实际原sdist责任源码与当前字节相同不代替新native实测。不是用户逐项亲批，不继承doc01／source31例外；不变全局3%／5%／5%、必要覆盖或样本，不设功能安全例外，不延用后续产物／Goal。原全部严格通过条件未完全达成；明确修订后的本轮采用条件已完成。原严格阶段评分95／100，按本次修订的采用条件100／100，分别报告。
- Pyright1.1.414仍为唯一检查器，三语言配置及40活动实现通过；52旧拒绝位置＋10新拒绝位置、993定义／162可执行示例通过；43既定demo诊断与52具体语句例外保持，意外诊断0。Rust fmt／严格Clippy及84debug／84release通过。没有将可选旧internal docstring观察升级为新否决条件。
- NoGIL实际导入和真实工作前后保持关闭，不强制关闭参数。D01继续严格适用：Polars官方维护，固定未改官方runtime只作内部开发CI，不维护fork、不供应自建runtime，不宣称所有位置都有官方现成t wheel。依赖和平台范围未扩大，主环境无Babel／cytimes；官方比较demo独立环境例外。
- 主安装`.local/doc01-review-seven-fix-20261104/fix02-main`；前三demo使用独立`fix02-oracle-demo`，Pddt demo使用主环境。根目录／另一目录四demo共8次成功，Delta150案例未知差异0；源码／pyi／相关指南／runtime／四demo同步。失败和未采用原型全留；编译提示未证明收益已撤回，SmallVec在编辑前取消，没有追加无关产品优化。
- [本轮最终报告](/Users/jef/ResilioSync/code/rsTimes/docs/doc01七项修复与性能补证验收-20261104.md)、[执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/doc01七项修复与性能补证十六小时执行计划-20261104.md)、[原始冻结计划](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc01-review-seven-fix-20261104/S01/plan-at-start.md)、[完成审计](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc01-review-seven-fix-20261104/adoption-completion-audit.json)、[NT01有限决定](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc01-review-seven-fix-20261104/S14/DE03-NT01-delegated-artifact-condition.json)、[唯一ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc01-review-seven-fix-20261104/ledger.json)、[预算结算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/doc01-review-seven-fix-20261104/budget-final.json)。软预算调配、自查真实迟延、CI原失败和测量元数据更正均保留；产品和过程分别评价。
- 本轮完成后合理approve失效；不为剩余预算续开工作。未启子Agent；根HEAD／分支／index及既有工作保留，仅专用隔离分支作CI必要提交／推送；未新建PR、合并、tag、Release或PyPI发行。

## 历史本地采用：原生Polars／Pyright／NoGIL doc01

- **本轮本地采用doc01，核心类Delta、Pydt、Pddt、Pldt及Parser／Configs同一源码支持普通CPython3.12—3.15及3.14t／3.15t。**冻结源码`aedc2ac9b05b939da4e227fb0a7724369101984e`，树`688332bd24bd80ac50f5d1ce34e1fe18558df6d2`。包元数据仍0.2.0b2；下面公开PyPI b2是旧发行，不据同名版本转记成果。source31只作历史基准。
- CP313／macOS ARM64实际native SHA256 `08e7bac640563398f52a70b8f17c7f228628d850cb16d7fc11aa5b49ad949434`；wheel `923236a8ad0f4cb61dcd4c0c268b7f27a2d427f350049c3ab098750746363074`；sdist `00f815f5ac187e5393d2d23c6dc56fb344910e90e35a97cb81907b49475d4b94`。135生产输入、361活动输入与冻结产物核对；实际每安装28包文件=27非native（含JSON资源）＋1native，各ABI独立SHA。
- 同源CI41629627028 attempt1为56／56SUCCESS；48wheel＋1sdist、3空target独立重建、2oracle／104ZIP全部读回。8平台×6ABI=32普通＋16t；181测试lane未解决旧结果变化0。代表普通23113PASS／4条件SKIP、t23116PASS／1条件SKIP、pd2兼容23100PASS／17条件SKIP；各位置按各自XML。完整正常CI77分49秒，不包括此前调试。
- t实际导入及真实工作前后GIL保持关闭，不用强制关闭参数。24个2／4线程探针覆盖六成本族，结果正确且计算实际重叠；普通快路与t安全路线分别保护。Configs不可变规则、短锁缓存发布及每实例业务编辑控制，不以全调用全局锁代替适配。
- Pyright1.1.414为唯一Python静态检查器，Node26.7.0；3语言配置、40活动实现、48旧＋4新拒绝位置、8正负fixture、993定义／159示例核查通过。43既定demo诊断和52具体语句例外保留，意外诊断0，不声称所有诊断0或弱化公开类型刷绿。
- **普通必要性能严格为624PASS／6稳定性INC／1稳定速度FAIL，共631项；全部675比较／145800选定对，每项216对／36真实worker。**42t观察29质量合格／13未明确，2静态构建观察合格但较慢。624严格PASS最大精度2.991912%、稳定性4.947211%、最差保守耗时增加4.984671%。原所有必要严格PASS未达成，不改写统计。
- 依本Goal用户对合理请求及严谨判断后合理代价取舍的明确委托，主Agent接受仅当前产物的7项采用条件修订：pldt-B0/L801、shared-S0/S081、shared-S0/NT01、shared-mainline33b-guard/NT01、pandas2-S0/V102、shared-mainline35-guard/S010六INC及shared-B0/S082一FAIL。S082最差保守耗时+5.5913604%；V102是strftime输出。不是用户逐项亲批，不继承source31例外，不降全局3%／5%／5%、不减覆盖／样本；功能安全不设例外。原负面和未采用原型全留。
- 普通共享模块基本持平；Polars2.1代表15项全PASS，双轮约1.161337／1.163252倍；本项目真实B0的3个N19目标约1.159231／1.156021倍。不是全库统一提速。全部4线程扩展性观察质量未明确，不宣称可靠线性加速；RSS仅整进程诊断。
- D01严格适用：Polars／runtime由官方维护；内部仅编译固定未改官方2.1.0源码7f902bd3ffd27ff82d14278a09a295ff2f7aed92供开发CI，不维护fork、不供应自建runtime、不代装或切换用户环境。四类t集成验证通过不证明各平台有官方现成t wheel；用户自行取得兼容上游依赖。普通最低Polars2.0.0职责保持；最低OS须结合依赖，见free-threaded指南。
- 主安装`.local/native-pyright-nogil-48h-20261103/doc01-ordinary-dependencies-main`无Babel／cytimes；官方比较demo用独立doc01-final-oracle-demo。四demo根／另一目录8次成功，Delta150案例未知差异0；runtime／指南／pyi同步，旧参考和计时环境保留。
- [本轮报告](/Users/jef/ResilioSync/code/rsTimes/docs/rsTimes原生内核-Pyright-NoGIL最终验收-20261103.md)、[本轮最终决定Q01—Q07／D01](/Users/jef/ResilioSync/code/rsTimes/docs/rsTimes原生内核-Pyright-NoGIL统一项目最终讨论决定-20261102.md)、[执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/rsTimes原生内核-Pyright-NoGIL四十八小时执行计划-20261103.md)、[完成核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/adoption-completion-audit.json)、[七项有限决定](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/N27/final-artifact-seven-case-decision.md)、[唯一ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/ledger.json)、[最终预算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/native-pyright-nogil-48h-20261103/budget-final.json)。原2880有效分钟／T0沿用；自查迟延、90分钟测量维护软目标超限与所有恢复负面如实保留，产品和过程分别评价。
- 本Goal已完成，合理approve随结束失效，不为余额续开优化。根HEAD／分支／index及既有脏工作保持；仅专用隔离分支作CI必需提交／推送，未合并主干、tag、Release、PyPI或新建PR。后续工作另列范围和预算。

## 历史本地采用：Pldt与Delta完整纳秒source31（本轮前基准）

- **本轮本地采用source31，核心类为Delta、Pydt、Pddt、Pldt。**Pldt是真正polars.Series子类，Series／Expr提供.pldt，表达式直接返回原生pl.Expr；Delta唯一精确ns值核、17字段／v2状态及各日期类完整投影已接通。公开发行仍为下面的0.2.0b2旧发行；当前本地包元数据也显示0.2.0b2，须按路径／SHA识别，不能据同名版本转记成绩或声称新实现已在PyPI。
- 本机CP313／macOS ARM64实际native SHA256 `e15fb9e5ff96fc8af93573772d9dcf99edbc3e3f5b5bb2dd4155dcc3bc348f6f`；wheel `3298fddd5689bb0e04f47983a591e00f1f98a475a91e43ab016183d39aa2b9f4`；sdist `93f5e40b6ce3ebb40af94fdee4a2cf26c8fa55fa613b5d0c6f8bc9f551be385b`。133生产输入、25安装Python／pyi／资源载荷和实际native新进程读回一致；各ABI有独立二进制身份。
- 主环境`/Users/jef/ResilioSync/code/rsTimes/.local/pldt-72h-20261030/repair-31-main`，oracle单独`repair-31-oracle`。完整主线22962PASS／1原SKIP；pd2为22949PASS／14原SKIP；22865原case ID／结果／完整skip原因保持，新98独立宽整数边界PASS。Rust84debug／84release、fmt／严格Clippy通过。当前安装7份pyi752定义／158可执行示例／6组mypy正负例通过；四demo根／另一目录8次通过，Delta150案例未知差异0，runtime实际绑定source31。
- 同源隔离源码提交`62fb0625fc137e8a803378d51b05f160d7b47fe1`／树`89f82a4e93b5ac3055fb4201e92d6fc99f064edb`，CI41379257407 attempt1的39任务成功。32实际wheel／38原始ZIP核验、125安装smoke／129XML lane核对及两代表sdist空target独立重建通过。普通64位GIL CP312—315×8平台（macARM／Intel、Winx64／ARM、Linux x64／ARM各glibc2.28／musl1.2），不宣称全平台严格5%性能或32位／nogil／任意Arrow组合。
- **必要性能原始严格结果为624PASS、3稳定性INC、1稳定速度FAIL。**每必要项216对／36真实worker，628必要共135648选定配对，含8观察共137376；61实际选定报告从raw完整重算一致。624严格PASS最大精度2.959893%、稳定性4.997688%、最差保守耗时增加4.951373%。不把下面例外写成严格PASS。
- 用户逐项批准L209源31专属速度例外：1000行ns格式strptime，两轮中位+4.35%／+3.45%，最差保守+6.239467%，原FAIL保留。根Agent另依本Goal后续合理请求／取舍统一approve的明确委托，接受仅pddt-S0 X027／N101、pandas2-S0 X007这3项稳定性例外；各216对／36worker，648对全部未显示退步，最弱配对仍R1.564668，最低原保守组R2.073270，但原稳定性INC不改成PASS／不宣称可靠精确倍率。新决定明文修订原L209“无其它INC”采用条件，不假称原条件严格达成或用户逐项亲批3项；没有其它未批准缺口。
- Pldt核心101必要比较按八成本族等权：双轮1.105961／1.104993倍，保守1.104834／1.103110倍，达到可选1.10目标，未达1.20；不是逐项都更快。225个至少一轮中位较慢的必要比较、双轮绝对耗时和未采用优化完整保存。原3%／5%／5%严格标准不变，4项采用例外仅限本source31，不继承下一native／项目。
- 原两个普通质量批次均已耗尽；后续真实双native／公共模块同线程模型和最后固定6n资格均有当前Goal有界决定、实际身份／完整输出／预试证据。主／独立轮交错保持原分组和216／36，不事后按胜负重排；新完整整项好坏均替换，旧负面保留，不转记source29等旧native时间。最后3项资格失败不继续盲试，按明确委托取舍收口；例外与原严格统计分开。
- [最终报告](/Users/jef/ResilioSync/code/rsTimes/docs/PLDT与Delta纳秒升级最终验收-20261102.md)、[执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/PLDT与Delta纳秒升级七十二小时执行计划-20261030.md)、[唯一ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/ledger.json)、[采用核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/adoption-completion-audit.json)、[最终预算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/budget-final.json)、[3项委托例外决定](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pldt-72h-20261030/W40/SOURCE31-three-stability-specific-exceptions-delegated-decision.json)。原72h经用户5次追加至81h，原T0／已用／等待不重置；阶段偏差、自查延迟和工具错误全部如实保留。
- 本轮为本地采用与隔离Draft PR1／CI；根HEAD／分支／index和既有脏工作保留，未推用户主干／merge／tag／Release／PyPI。四demo与类型／指南／源码已同步。Goal完成后合理approve授权失效，不为剩余预算继续新优化；后续发行或新工作另列授权和预算。

## 历史公开发行：0.2.0b2（保留独立产物事实）

- **历史公开采用 `rsTimes==0.2.0b2`，依赖／平台扩展已完成必要验收。** Python0.2.0b2、Cargo0.2.0-beta.2、tag `v0.2.0b2`，已发行源码`ae74aa973a7d7af23026ef41dd13806ca9cf1d32`，注释tag对象`96a10864a985a2c645dac476fc94b9e7720359fe`。普通64位GIL CPython3.12—3.15 × macOS ARM64／Intel、Windows x86_64／ARM64、Linux x86_64／ARM64各glibc2.28及musl1.2，共32wheel＋1sdist。
- 默认NumPy>=2.5.3，Windows tzdata>=2026.5；dateutil>=2.9、pandas、Polars>=2.0.0可选。pandas2最低2.3.3，在21适用位置验收；全部32位置以pandas3.0.6主线验收。Py315／WindowsARM64须pandas>=3.0.6。旧NumPy1／Py311／pandas2.0仅历史证据，不是b2支持。日期语义仍按唯一Pddt最终决定，新的依赖／平台事实按[本轮最终决定](/Users/jef/ResilioSync/code/rsTimes/docs/依赖与跨平台发行最终讨论决定-20261028.md)。
- 完整同源CI40742598980 attempt1的39任务全部通过：32主线各19485PASS、21pandas2各19472PASS／13原条件SKIP、8最新各19485PASS；两个oracle各25589PASS／13原条件SKIP。19432旧正确案例ID和817旧oracle ID均保留，新53不同ID。两代表sdist空target独立重建，Rust fmt／严格Clippy／debug16／release16、357pyi定义／96示例及静态类型正负例通过。
- CP313macOS ARM64实际公开native SHA256 `818a9a6ebd4ae6736802d23c0b1e1be95b8d59797bd4eb1c126c795b692a4506`；wheel `599ba1ef7e2b9b379b51b583716420b53821ce75bf1351fc05e5c9c240fe79b7`；sdist `985326d453f769c8c8adeb1b52db5ca2e6582a2500bce9114a267ad7ee26baf9`。不同ABI／平台有各自SHA；75生产／构建／许可输入与原sdist和实际发行文件一致。
- 最终实际待发wheel对b1的145必要项全部严格PASS，0FAIL／0INC；每项216对／36worker，必要31320对，含3设置观察31968选定对／252不同worker。最大精度2.774829%、稳定性4.907472%、最差保守耗时增加3.733281%。整体基本持平，不宣称逐项更快。N001 Configs独立创建仅观察且精度仍未明确，原数据保留；其非否决角色在计时前固定，必要项无门槛／样本豁免。
- GitHub36资产／PyPI33文件和原CI清单匹配。最初tag运行40755368314真实完成GitHub→OIDC PyPI，但16个Linux后置检查因Git拒绝容器可信/project目录而在下载前失败，最后3个重复未完成检查取消。全部16原日志已核实并保留。仅两份CI YAML修正，维护提交`c07d18401e4a1ecf0dbacd6211570c8a846627ed`，不移动tag／重建／重传；原75生产输入不变。
- 随后只读公开验证40757419293 attempt1为33／33SUCCESS：32真实PyPI wheel、96实际native导入、各19Python载荷和原始测试XML核对通过。完整正常构建／全测CI19分26秒；独立无错误公开验证15分26秒，不能合称首次tag全流程全绿。GitHub标准运行器队列计入相应墙钟，调试与正常运行分开。
- 本机公开主环境 `/Users/jef/ResilioSync/code/rsTimes/.local/dateutil-optional-platforms-16h-20261028/published-pd3` 无Babel／cytimes；public-core无dateutil／pandas／Polars，Babel只在oracle-env供官方比较。3组公开安装smoke和四demo根／另一目录8次通过；Delta150场景未知差异0。源码／pyi／相关指南／四demo runtime均已同步，旧b1环境与发行保留。
- [本轮报告](/Users/jef/ResilioSync/code/rsTimes/docs/rsTimes-0.2.0b2依赖与跨平台发行验收-20261028.md)、[执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/dateutil可选化与跨平台支持十六小时执行计划-20261028.md)、[唯一ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/dateutil-optional-platforms-16h-20261028/ledger.json)、[采用核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/dateutil-optional-platforms-16h-20261028/adoption-completion-audit.json)、[预算结算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/dateutil-optional-platforms-16h-20261028/budget-final.json)。960分钟总额沿用原T0／规划，仅68秒等待启动排除；实际迟延、软目标调配、测量接线估计15—17／目标15分钟和负面全部保留。不开子Agent；根HEAD／分支／index保护，明确提交／推送／发行在隔离checkout完成。本轮结束后合理approve授权失效，不沿用剩余预算扩新工作。

### 历史参考：已完成公开beta b1（不是b2同产物成绩）


- **当前采用公开beta `rsTimes==0.2.0b1`，已发布且通过安装验收。** Python版本0.2.0b1、Rust0.2.0-beta.1、tag `v0.2.0b1`，冻结源码提交 `819af50758265aed6988f9e49d13fabab8df7447`。GitHub Release426594977及PyPI同16wheel＋1sdist的SHA已全部公开下载读回。矩阵为CPython3.12—3.15 × macOSarm64／x86_64、Windowsx86_64、Linuxx86_64；不宣称beta的Py311、free-threaded、PyPy、musl或Windows/LinuxARM已验收。
- CP313macOSarm64实际native SHA256 `070f22daa08d4fde892ef0c556de3b09aafbad55409d3150b15e6e1054394665`；wheel `2c915ef1cf895e308b281baa766a22417fef855dae27a3f53ab5a13b4b2338b9`；sdist `961901565802543902f51bcabb3fb89d1319a5de86692b9cb5045090b7b8a203`。其余平台／Python有各自二进制身份，见发行manifest。
- 单一源码经Actions16环境实际构建安装，各19480PASS／817原条件SKIP／0FAIL；两个独立官方对照环境（pd2.3.3／NumPy2.3.3及1.26.4）各25584PASS／13SKIP。代表sdist空target独立重建安装、Rust16debug/16release、fmt／严格Clippy、357pyi定义／96示例及静态类型正负例通过。WindowsTZif测试真实执行，不额外skip。
- beta必要适配仅涉及pandas2真实非零ns尾数、Windows公开Unicode构建资料和公开地区格式资料；pandas3保留原快路。冻结原版cytimes的pandas<3依赖不强装进产品pd3环境，Babel仅供官方对照。原final04历史成绩不转记新包；本轮同实际mac313native15项保护全PASS，每项216对／36worker，3%精度／5%稳定性／5%耗时保护保持，最大精度2.2403%、稳定性3.9295%、最差保守耗时增加1.9436%。
- 实际PyPI16wheel下载SHA／native／19项Python载荷及每环境578PASS已通过，本机全新环境也578PASS。首次仅macarm315公共索引未见beta，保留原失败并只恢复此项；37项旧成功任务原执行时间不变，不能把API的76条记录当76次重测。已发布tag和文件未移动／覆盖／重建。
- 旧占位PyPI0.1.0、GitHub旧Release及远／本地v0.1.0tag已按明确授权删除；先备份并校验，删除后规范化及先前缓存的大小写旧JSON均404，simple索引无旧文件、实际pip不可下载。保留PyPI项目身份、旧文件及历史本地证据，不宣称可抹除外部历史拷贝。
- 当前主环境 `/Users/jef/ResilioSync/code/rsTimes/.local/rstimes-beta-release-20261028/published-pd3` 无Babel／cytimes。前三个官方比较demo在同轮oracle-env，Pddtdemo在pd3；4demo根／另一目录8次通过，Delta150场景未知差异0。独立小demo启动器校验版本／路径／真实native；不静默旧包、不在导入时替换进程、不让Pddtdemo导入cytimes。原final04环境保留。
- 发布后维护提交 `0e2a0eb9bed2c33762c5f1914945cf348bfae19a` 仅调整README／demo及CI有限重试／四demo发布前门槛，最终CI40684056336全部实际成功；生产Python／Rust／pyi未变。当前README的demo准备说明与冻结发行README有明确的后续文档差异，其余74项生产输入、19已安装Python载荷和mac313native一致；不混用main构建产物与已发布文件。正常CI完整成功11分37秒；tag全程20分05秒含一次索引恢复，不冒称无调试耗时。
- 本轮[验收报告](/Users/jef/ResilioSync/code/rsTimes/docs/rsTimes-0.2.0b1发行验收-20261028.md)、[计划](/Users/jef/ResilioSync/code/rsTimes/tasks/rsTimes-beta发行计划-20261028.md)、[唯一台账](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/rstimes-beta-release-20261028/ledger.json)、[完成核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/rstimes-beta-release-20261028/adoption-completion-audit.json)、[最终预算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/rstimes-beta-release-20261028/budget-final.json)。总预算原480加600为1080分钟，T0与暂停不重置；自查延迟、工具软目标超限、负面和恢复均保留。根原HEAD／分支／index保留，公开源码在独立release-checkout显式提交；未启子Agent、未改SQLAero。本Goal已完成并结束，其统一approve不延用新Goal。

### 历史参考：CR01—CR07采用final04（不是beta同产物成绩）

- **当前本地采用 `0.2.0+pddt.4/final04`。** CR01—CR07七组修复、功能、构建、三环境、类型／文档、178项必要性能和四demo核查全部通过。CPython3.13 native SHA-256为 `6262d8ccbc8bd8d572988bb665ba6da2a5fa31335187b5936f19fec9c10c169e`；wheel为 `b88302f84c169765ae3a0e92954dc2736823c12d20c76d4eb6c87407f580dd22`；sdist为 `43d4ed38d1a508447aa69fc7bf9c7b57883ac658dcfab5ca8eba0ab5bcc884b6`。CP311同源独立native为 `4a198a0c00d910f7143761352138899769859b2ca151b327fc64e10521ca75ef`，其wheel另见身份记录。
- 真实Delta／timedelta／Pandas Timedelta子类列运算遵守实际方法和描述符，普通值／无覆写子类保留原生快路；不以第三方通用槽地址等价冒充方法继承。空工厂来源时区独立于长度保存，date_range当地载体与最终UTC单位分开，原F01／F02保持；relativedelta数值回调后复核活状态，字段顺序不变、不调用normalized；Pddt自有类型边界按真实类型，冷错误保留已知位置和原异常。CR05仅修正文档／typing，不放宽数值和bool，Pydt可执行AST不变。PLDT仍未启动。
- 同包完整 **20124PASS／817原条件SKIP／0FAIL**；20701旧案例ID／结果／原因保持，新增240；三个代表环境各1777PASS。新240项在旧包为151FAIL／89正常控制，当前全部通过。Rust16、fmt、严格Clippy、六pyi357定义／96示例、静态正负例通过。75项生产／构建／许可输入与独立sdist一致，四环境各20载荷和新进程native读回一致；四demo根目录／另一目录8次通过，Delta150场景未知差异0。
- 最终必要性能 **178／178PASS，0FAIL／0INC**：113对本轮前采用final03，65原S0／B0／B7对应保护；每项216对／36真实worker，共38448必要配对，含1设置观察38664选定对／252不同worker。最大精度2.833%、稳定性4.928%、最差保守耗时增加4.089%。首轮15项质量缺口按计划一批40ms控制／固定预试有改善后完整替换，旧负面全留；无门槛／样本豁免，不转记旧228／46项。仅X007／X027沿本计划的Polars端到端模型，其余单线程规则保持。
- 113项必要调用等权双轮倍率1.000239／0.998594，整体基本持平；Pddt86项1.002811／0.998880，不宣称每项更快。主环境 `/Users/jef/ResilioSync/code/rsTimes/.local/astra-seven-fix-20261028/final04-pd3` 和两个兼容环境无Babel；demo环境的Babel仅供冻结官方对照。源码／pyi、相关指南、四demo／runtime已同步，README和未涉内容保持；旧final03环境和wheel／sdist保留。
- 本轮[验收报告](/Users/jef/ResilioSync/code/rsTimes/docs/CR01-CR07修复与验收-20261028.md)、[执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/CR01-CR07八小时修复与验收计划-20261028.md)、[唯一执行／预算台账](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/astra-seven-fix-20261028/ledger.json)、[完成核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/astra-seven-fix-20261028/adoption-completion-audit.json)、[最终预算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/astra-seven-fix-20261028/budget-final.json)。原启动计划逐字保存S01/plan-at-start.md，原48小时计划／最终讨论决定／Astra报告未改；历史过程评价不删除。
- 本轮480分钟预算的实际结算见budget-final.json，规划已用及唯一无工作等待保留；自查实际延迟、S10软目标调配和工具接线估算18／目标15分钟均如实记录。本Goal完成，不为余额续开优化；未启子Agent、提交、推送或发布。统一合理approve随Goal结束失效，不延用新Goal。

以下为旧版历史证据，不能作新版的同产物成绩。唯一行为决定及26条/77子条款继续适用。

### 历史参考：已完成F01—F03修复（仅适用pddt.3/final03）

- **当前本地采用 `0.2.0+pddt.3/final03`。** F01—F03修复的功能、构建、三环境、类型/文档、46项必要性能及四demo核查均通过。CPython3.13 native SHA-256为 `df7ad772ba40f7d8e66f50002a25631dbd02768b25b416fb5e9b5079ff601acc`；wheel为 `c405ed24f2ddfb33b50350868b61c3818c87a7fc2801f239026439d1371f83f8`；sdist为 `875f207ba6a79df0f3345157b3a15bad45a07b6d1d2ad80bde3aa320c9700878`。CP311同源独立二进制另见本轮身份文件。
- F01共享strptime正确处理年份后的数字字面量，尾宽只在格式准备时计算；F02所有提供的date_range端点在normalize/时区准备后须符合显式unit，原生和明确委托分支共用；F03只修正文档中的真布尔和整数字段说明，不放宽实现。未启动新功能或整库再审计，PLDT仍未启动。
- 同包完整 **19884PASS／817原条件SKIP／0FAIL**；20619旧案例ID/结果/原因保持，新增82；两个兼容环境各1537PASS。Rust16、fmt、严格Clippy、六pyi357定义/96示例及静态类型正负例通过。75项生产/构建/许可输入与独立sdist重建一致，四个最终环境各19载荷一致，根及另一目录8次demo通过。
- 本轮新包必要性能 **46/46PASS、0FAIL、0INC**：41项对当前旧采用final02，另5项对原S0/B0；每项216对/36真实worker，共9936必要配对，含1设置观察10152选定对/180不同worker。最大精度2.6727%、稳定性4.4952%、最差保守耗时增加4.0441%。S035按本Goal有界授权采用两份真实native同线程模型，有控制和预试改善后才正式采；未豁免门槛/样本。原负面全留，旧228项不转记新包。
- 修复组合总体与final02基本持平：41项等权双轮倍率1.002412/0.998361；不宣称每项更快。主采用环境 `/Users/jef/ResilioSync/code/rsTimes/.local/pddt-audit-F01-F03-fix-20261027/final-pd3` 无Babel；demo环境 `final-demo-env` 的Babel仅供冻结官方对照。源码/pyi、相关指南、四demo/runtime已同步，原README及未涉修改保持。
- 本轮[验收报告](/Users/jef/ResilioSync/code/rsTimes/docs/F01-F03修复与验收-20261027.md)、[执行计划](/Users/jef/ResilioSync/code/rsTimes/tasks/F01-F03轻量修复与验收计划-20261027.md)、[唯一执行/预算台账](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pddt-audit-F01-F03-fix-20261027/ledger.json)、[完成核查](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pddt-audit-F01-F03-fix-20261027/adoption-completion-audit.json)、[最终预算](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pddt-audit-F01-F03-fix-20261027/budget-final.json)。启动计划逐字原件另存S06/plan-at-start.md；原48小时计划及独立审计未改，F04/F05历史过程评价保留。
- 本轮300分钟总预算沿用原已用，完成结算以budget-final.json为准；T90自查延迟及准备阶段超限已明确记录。本Goal已完成；不为剩余额度继续优化。不启子Agent、不提交/推送/发布；本Goal结束后，其统一合理approve授权失效，不延用新Goal。

### 历史参考：已完成48小时项目（仅适用pddt.2/final02）

- **48小时项目已完成并采用 `0.2.0+pddt.2/final02`。** CPython3.13 native SHA-256为 `eb37f1ea2eb5fbd06d05e8b5b1949eda53162555b3d1e35748559302148e6596`；wheel为 `b61b3d7de583d11a5417278a3c407f7ebbe7f5dc10a131b322e6c0bab854acee`，sdist为 `fc5acf9be35cee7ef3370ddf6bf3168b3f3c0f8abfc5f99b202b3fc31c0e8d73`。Pddt已按最终决定重写；R0仅参考，不恢复旧兼容层。Delta／Parser／Configs／Pydt的批准修改已同步，PLDT未启动。
- 唯一行为依据仍为[Pddt重写最终讨论决定](/Users/jef/ResilioSync/code/rsTimes/docs/Pddt重写最终讨论决定-20261026.md)，18板块／26条断言／77子条款及其例外继续适用。下方逐板块必读指令保持。不要按历史文稿中的“当前／下一步”重启旧任务。
- 同包完整19802PASS／817原条件SKIP／0FAIL，20453个B0旧案例ID／结果／原因保持，新增166PASS；两个兼容环境各1455PASS，无Babel1597PASS，独立sdist空target真实release重建1129契约／Rust16、fmt／严格Clippy及六pyi357定义／88示例／静态正负例通过。Python3.11为同源独立wheel／native，不能冒称其二进制与3.13相同。
- 全部228项必要性能检查严格PASS，无速度失败／INC或阈值、样本豁免：共享86对S0、Pddt核心75和受影响37对B0、邻接30对B7。每项216对／36真实worker；必要49248对，含2设置观察49680选定对／684不同worker。最大精度2.9444%、稳定性4.9401%、最差保守耗时增加4.8514%。原INC／失败／不完整及机械排除全部保留，整项新完整数据替换，不转记其它native时间。
- Pddt核心等权双轮1.09249／1.09533倍，未达可选1.10争取目标；共享模块等权1.04215／1.04208倍。全部慢项与未采用原型如实列出，不宣称每个调用更快。5项pandas3参考为探索性观察，边界分辨率拒收率高；6项未测，不作为采用或组合成绩。
- 根74项生产／构建／数据／许可输入与固定sdist一致，toolchain另行核对，5环境各20载荷一致；六pyi、七指南、四demo/runtime同步。根目录及另一目录8次demo通过，Delta150场景未知差异0；采用后13项定向检查通过。主环境 `.local/pddt-rewrite-48h-20261026/formal-pd3` 无Babel；demo环境另有Babel仅供冻结官方对照。README、原有工作及S0／B0／B7固定参考保留。
- 最终报告[完整验收](/Users/jef/ResilioSync/code/rsTimes/docs/Pddt重写与共享模块修改最终验收-20261026.md)，计划[plan](/Users/jef/ResilioSync/code/rsTimes/tasks/plan.md)，唯一执行／预算[ledger](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pddt-rewrite-48h-20261026/ledger.json)，完成审计[adoption-completion-audit](/Users/jef/ResilioSync/code/rsTimes/tasks/evidence/pddt-rewrite-48h-20261026/adoption-completion-audit.json)。原T0及已用保留，最终结算以budget-final.json为准；普通分析与工具等待计时，三段必要纯等待单列。
- **本Goal已结束，统一合理approve随之失效，不延用新Goal。** 不为余额继续开发／测试／优化；本轮未启子Agent，未提交／推送／发布。后续新任务先确认自己的范围和预算，继续保护已有成果并执行必要的30分钟自问纠偏机制。

## 开始对应板块前必须阅读

**本轮新增／变更的唯一正文为[PLDT与Delta纳秒升级最终讨论决定](/Users/jef/ResilioSync/code/rsTimes/docs/PLDT与Delta纳秒升级最终讨论决定-20261030.md)，含PL01／PL02、14板块60主项、GN01—GN13、D01.O1—O4、U1—U3及范围／例外。**Pddt／Parser／Pydt未被本轮改变的行为继续按[Pddt重写最终讨论决定](/Users/jef/ResilioSync/code/rsTimes/docs/Pddt重写最终讨论决定-20261026.md)的18板块执行。旧主稿及分批稿只作历史／导航，不恢复已删除表述；不只读下表或断言概括替代参数、例子和例外。


|本轮工作板块|必须阅读PLDT／Delta最终决定|
|---|---|
|Pldt对象／Series／Expr／输入|PL01、PL02、A01—A04、B01—B05、M01—M04|
|单位／validity／宽年份／导出|C01—C06、K01—K04；Pldt仅ms/us/ns，独立validity保有效MIN；Pddt仍s/ms/us/ns与NaT哨兵|
|Parser／Configs／default及既有类优化|D01—D04、D01.O1—O4、N01；Expr创建时快照与eager活回调分开|
|工厂／格式输入／date_range|E01—E05、D04、C、H；完整委托与本库自有规则按正文分工|
|字段／日历移动／边界|F01—F04、H06；Pddt字段replace为.pddt.replace，Pldt为.pldt.replace，原宿主replace保其原义|
|Delta ns值／数值准备／状态|G01.N的GN01—GN13，尤其GN03—GN05、GN10；U1逐字段合并、U2 NumPy左侧、U3真实回调|
|日期算符／时长／DST／取整|G01—G03、H01—H06、I01—I03；原生快路、日历与经过时长、标量／严格等长列分别执行|
|查询／diff／语言／格式输出|J01—J04、K01—K04；%f与%.[1-9]f／%.0f按K03，Pydt/Pddt同步批准范围|
|业务状态／元数据／真实子类／生态|L01—L04、M01—M04、G03；Pldt非elementwise伴随列、聚合标量和惰性schema按正文|
|测试／性能／交付／预算|N01—N04及现行计划；必要数值门槛和产物专属例外分开保存，不转记历史native成绩|

PLDT的宿主差异按各条直接适用：B01拒Mapping/set/frozenset；B02长度1集合不广播、原生可空字段；C04完整int64与allow_nat_collision=False；H01规范化Polars时区字符串，不强保Pydt/Pddt的Python tz对象身份；L／M的结果容器、元数据、快照与子类边界。下列旧Pddt专有规则不被机械扩展到PLDT，公共整数／布尔／安全／错误原则仍适用。

|工作板块|必须阅读最终决定|
|---|---|
|全局／环境／生态|P01、P02、P18|
|类型、依赖、批量容器和参数准备|P02—P04|
|单位、纳秒、宽年份和输出容量|P05|
|Parser／Configs／default|P04—P06、P08、P10、P17|
|新Pddt构造和命名工厂|P03—P07、P10、P16|
|strptime和date_range|P08、P09、P10|
|Pydt／Pddt时区与Snap|P10、P13、P17|
|字段／周期／批量／add-sub|P03—P05、P11|
|日期算符／Delta整列交互|P12、P17|
|查询／diff／日历表|P14、P05|
|访问形式／导出／语言／格式|P15|
|返回／子类／copy／pickle／索引|P16|
|Delta／Parser／Pydt批准共享变化|P17及其指向板块|
|错误／文档／测试／性能与预算|P18，错误沿已采用E01—E32|

历史已完成Pddt重写项目的U12预算为48小时，其原计划／采样口径仅按相应历史产物引用，不作为当前PLDT项目起点、预算或成绩。当前项目按上方唯一PLDT决定、现行计划及明确批准调整执行；计划不重写行为，C编号26条／77子条款和适用范围／例外保持。

## 核心断言

### C01 依据、目标版本与修改边界

- **C01.1** 最新明确决定及现行主讨论决定目标；Delta、Parser/Configs、Pydt、新Pddt一律核查全部已批准修改实施后的版本。当前事实、已批待实施、修改后剩余缺口分开，不把设计批准写成已采用。
- **C01.2** 旧Pddt只参考，不保留旧参数、别名、转译和pickle自动迁移。旧测试仅在预期仍符合时复用，不为通过旧样本恢复废弃行为。
- **C01.3** 共同日期含义与Pydt一致，保留已明确的标量/整列、us/ns、NaT、单位和年份差异，不为统一而缩掉Pddt能力。
- **C01.4** 共享修改限最终决定P17及后续明确批准；调查、讨论批准、实现、验收/采用分开记录。实质未决不能自行当批准；符合断言的入口直接过，不重复重开。

### C02 真实容器与返回职责

- **C02.1** Pydt真正继承datetime，Pddt真正继承pandas.DatetimeIndex，Pldt真正继承polars.Series。Pddt正常DataFrame索引／日期选择可用；Pldt按PL01／PL02提供Series／Expr的.pldt入口，Expr方法直接返回原生Expr，正常DataFrame／LazyFrame接入与真实外部协商保持。
- **C02.2** 自有日期结果按契约返回日期类；整数/布尔/字符串/时长/数组/DataFrame按职责返回，不能都包装为Pddt。Pddt单元素仍为Timestamp，显式datetime导出按约定为Pydt。
- **C02.3** 原日期NaT的自有布尔查询为False，整数查询用已定可空整数；不把日期NaT哨兵套到所有整数。目标缺失仍按C08拒绝。

### C03 pandas默认与完整成熟接口复用

- **C03.1** 新Pddt默认以固定pandas3.0.6所代表的3.x为准，pandas2也用同一本库规则，本库明确差异优先。当前b2发行是CPython3.12—3.15／NumPy>=2.5.3；pandas3.0.6主线32位置、pandas2.3.3兼容21位置，限制见本轮最终决定D2—D5。本机严格性能代表为Py3.13.3／NumPy2.5.3配同版本pandas2.3.3或3.0.6；旧三代表环境及NumPy1／Py311证据仅历史。最新pandas3.1补充验证不自动改变日期默认，不宣称所有未来版本／系统小版本已验收。
- **C03.2** 明确完整复用成熟公开入口时，参数、转换、广播、返回及原异常一起保留；不同契约由本库完整实现。共享小Rust算法/最终容器复用不等于完整复用某公开方法。
- **C03.3** take/repeat完整沿用pandas，不额外加本库整数/bool/float/文本/协议限制、预处理或错误包装；标准广播、索引和填充保持。该例外不扩大到自有size/periods/字段/add/sub。

### C04 最小共享Rust内核与完整路径效率

- **C04.1** 语义相同的日历/解析/单位/边界共用最小明确Rust函数，标量/批量输入和目标容量/输出分开；不把Pydt强塞一行数组，不让Pddt／Pldt逐行调用公开Pydt/Parser。Pldt插件worker只处理Rust字段／typed buffers，不接触Python对象或重新attach；必要真实外部协议限明确eager适配边界。
- **C04.2** 普通计算在紧凑原生字段/整数/缓冲中完成，尽量只构造最终对象；查询/整数导出不先造临时Pddt。不重复解析、包装或分配，不以塞满开关的大函数替代共享。
- **C04.3** 安全、可维护性及同语义完整公开调用性能优先；必要协议载体或有整体效率证据的datetime适配可保留并独立携带ns。不强制零Python对象，不为少对象损坏真实子类行为。

### C05 真实类型、元数据与依赖准备

- **C05.1** 类型分流用真实类身份、继承和原生dtype/单位/时区元数据；不按类型名、模块前缀、字符串化或首元素猜整列，不以名称门禁拦合法子类。
- **C05.2** 必需导入／类型／能力在适合模块入口准备复用，不在热路径反复import/getattr。当前NumPy必需，dateutil／pandas／Polars可选；Pddt须pandas、Pldt须Polars，不强迫Delta／Parser／Pydt安装这些可选依赖。dateutil按D6复用真实顶层能力／类型准备，缺失后安装须重启；损坏／嵌套导入错误不缓存为缺失，原relativedelta首次有限重入协议保持。pytz按既定可选适配职责处理，不把不同依赖一概改永久缺失缓存。

### C06 一维集合与按用途配对

- **C06.1** 新版Pddt自有批量入口共用list/tuple、一维ndarray、pandas Series/适用Index/ExtensionArray、可选Polars Series、生成器/iterator/range及合法一维Iterable；合法非连续切片也支持。外层可读不表示每种元素合法。
- **C06.2** Mapping只迭代键，set/frozenset按实际顺序，不取values/猜字段表/排序。str为文本标量，bytes/bytearray不拆字节；DataFrame/Polars DataFrame/LazyFrame、零维/二维、嵌套行不自动取列/收集/展平。
- **C06.3** 普通构造须集合、不隐式重复标量；命名工厂标量须合法size、列不同时给size；多分量标量广播到共同列长、全标量须size。freq/周期/unit/tz/cfg/default/普通开关/格式/locale/inclusive/size/periods/fsp精度等仍按单值职责。
- **C06.4** 已批准逐行目标为标量广播或严格等长列；长度1集合不当标量、Series按位置不按标签、多列等长。空列也校验所传选项。ambiguous布尔列按原完整行策略，nonexistent不扩成逐行列；继承索引/集合操作保留C03及自身用途。

### C07 一次准备与原生值

- **C07.1** 实参按实际用途读取一次：整数/合法浮点协议、真实来源字段、一次性迭代器不重复求值，不先int判零再转换一次；标量整列外准备，不展开N份。
- **C07.2** 合法原生列尽量直接读取并持有owner/必要快照；普通内核使用紧凑原生整数、布尔和必要缺失/存在标记，不让公开None/Python数字进入计算循环。
- **C07.3** 外部真实协议按既定调用、返回、原异常保护，不把一次读取泛化成所有方向只许一次回调。relativedelta原字段转换既有weekday/leapdays在数值回调后的必要活状态复核保持，不为“一次”删掉安全规则。既有Timestamp子类反向NotImplemented边界保持：Pydt在左一次；Timestamp子类在左可全局两次并有状态差异。

### C08 None、零、负数、缺失与原子失败

- **C08.1** 可选数字修改参数None保留，零为真实数值，相对负数反向；Pddt零年/负年为真实年份。删除旧占位的入口不恢复-1/0；必填增量/offset不额外增加None。
- **C08.2** tzinfo省略保留/显式None去时区，其它tz入口各按用途。明确日期缺失可为NaT、普通解析失败不能变NaT。日期字段条件查询的新目标None/pd.NA/NaN/NaT等TypeError，即使原日期NaT也检查；from_parserinfo表None不导入、不回填默认；工厂默认各按职责。
- **C08.3** 日期计算/解析/批量调用不修改来源数据、不交付部分成功结果；不把非法类型/值/缺失伪装“不修改”。Configs设置和明确恢复业务状态等本来修改目标的入口按自身契约，不由本条取消其作用或承诺事务回滚；外部回调副作用按真实协议。

### C09 数值、布尔按角色读取

- **C09.1** 已批准统一整数协议的参数接受Python/NumPy整数及合法__index__；float含1.0、数字文本、仅__int__对象TypeError。覆盖已批Pydt/Pddt frommicroseconds、序数/ISO/年内日、offset、命名add/sub、fsp、目标年份、绝对字段/选择/查询；范围依用途，合法查询非匹配False。Delta years/quarters/months同用整数协议，正负/零和checked范围保持。
- **C09.2** Delta weeks至nanoseconds支持整数/index及Python float/真实NumPy float16/32/64完整换算；独立longdouble/扩展浮点、Decimal/Fraction/complex/文本、仅int/float转换对象拒绝。真实别名按身份，不依平台位数猜。NaN ValueError，无穷/超范围OverflowError。构造、原字段导入、四方向/批量统一，不额外截掉来源小数。整数贡献保持精确；合法二进制浮点贡献在唯一ns准备核中精确合并，最后在Delta值出口取偶一次，不保亚ns残量，不回退旧us算法。absolute microsecond／nanosecond各自保存存在状态，字段合并按GN04／U1。
- **C09.3** 自有数字/数量/日期/纪元和实际使用的数值default先拒绝Python/NumPy bool；普通开关只收这两种真布尔，空/原生输入也检查，不调用任意真假协议。fold仅按已批整数0/1和两bool例外；DST策略/合法mask/外部来源字段按专门语义。
- **C09.4** 明确例外保持：裸刻度可收整值float但不截非整数；秒数/实际数值default保留专用小数协议，不扩大为任意float()。relativedelta来源bool按含义处理，如month=False未设/True一月、hour=False零时、相对True为1；不调用normalized，不扩大weekday/leapdays。take/repeat仅C03。

### C10 构造选单位、已有对象固定单位

- **C10.1** 新Pddt构造统一unit，转换为as_unit(unit=...)，支持s/ms/us/ns，删除旧构造关键字/别名。显式单位在解析/构造前确定，未指定按来源，原生日期保留受支持单位，混合按共同精度要求。
- **C10.2** 不简写为所有输入us；普通文本/裸数字/原生列、空集合/有dtype的空数组按最终决定P05.1分别解释。
- **C10.3** 已有Pddt普通日期运算保持unit；精度不足ValueError、容量不足OverflowError并提示显式as_unit，不自动升降/截尾/回绕/变NaT。
- **C10.4** 检查合并后的真实结果，允许microseconds=1,nanoseconds=-1000等合法抵消；必要原生安全仍检查，不让较窄中间表示制造假溢出。

### C11 来源精度与出口精度规则

- **C11.1** 共享解析／Pddt／Pldt的来源ns/大整数保留到出口，不先缩us、不转float、不一律转int64 ns；没有真实细精度不伪造。Delta/Pydt已定精度出口分别执行，不由本条新增其未批准的转换能力。
- **C11.2** Pydt仍us及自身容量，Pddt／Pldt真ns；必要datetime适配独立携带尾数。Parser/Pddt小数秒到ns按已批直接换算，parse_to_epoch(1e-9,unit="ns")目标1，不先按us舍入。
- **C11.3** 精度减少只按明确功能：普通构造/数值工厂指定unit无损；as_unit round_ok=True向更早刻度、False无损；now/today/utcnow按所选分辨率取得当前值；strptime %f及主动us导出最后截取；round/floor/ceil/fsp各自取整；Delta在其值出口仅最后一次ns取偶；最终投影到datetime／Pydt／timedelta时另按目标us取偶，date按午夜精确运算后选所在日；Pddt／Pldt保持完整ns并检查固定unit，不先丢尾数。不统一成一种截断/舍入/拒绝。

### C12 日历和目标容量决定年份

- **C12.1** 共同日历内核支持Pddt当前unit容纳的零年/负年/宽年；Pydt/datetime最终1—9999。便利上限选择/月末与严格replace分别按既定契约，不把目标容量偷偷改成字段截取。
- **C12.2** Parser ISO优先/通用路径同义识别完整四位零年，明确零年不被default覆盖；最终dtclass决定构造，整数出口不套datetime/64位容器容量。保持原生checked安全，不因此扩普通Parser负年份语法；strptime宽年按专用明确格式。

### C13 元数据、所有权与低成本复用

- **C13.1** Pddt日期变换保留unit、真实ns、tz、name和原NaT位置；freq仅仍有效且验证时保留，不伪造日期/dtype/freq。
- **C13.2** 持有owner，处理lifetime/stride/字节序/外部可变数据及必要快照；copy=True隔离、copy=False安全时可借，不承诺所有输入零复制或共享数据绝对不可变。
- **C13.3** 低成本已知不变可返回原对象，不全列扫描只为证明is；明确复制/业务状态/元数据改变不能被no-op省略。状态/复制按C22。

### C14 共享Parser与选项优先级

- **C14.1** 普通文本统一Rust Parser语法/词表/strict，不新造Pddt方言或先采用pandas成功结果；原生日期/数字直接读，不转文本，不强迫每类都过同一公开Python函数。Parser解释字段/tz/fold，目标类承担构造和地区存在性。
- **C14.2** 每个顺序参数取显式非None > Configs > 无配置yearfirst=True/dayfirst=False，显式False生效。strict=False、isoformat=True保持共享含义，后者ISO优先可通用回退；strict不是错误转NaT/DST策略；专用fromisoformat按严格ISO合同。

### C15 独立default与有效Configs

- **C15.1** default须独立完整，实际需要时准备一次，不借今天补普通解析；补YMD及既定两位年参考，纯原生路径不处理无关default。
- **C15.2** Pddt不继承default时钟/tz/ns/fold以决定整列歧义；Parser/Pydt维持各自已定fold用途，明确零年不被覆盖，已识别字段优先。
- **C15.3** 词条、地区文本和strptime %Z用有效Configs明确规则，保留删除/自定义；成功识别保留tz，不猜本机CST/EST，不绕cfg。Configs独立状态快照、恢复重建Rust词表，内部查询/公开设置分工。
- **C15.4** 识别词表与CLDR月份/星期名称输出分工，复用现有服务及成熟iana-time-zone，不恢复Babel或另写平台探测备选。

### C16 原生实现与外部委托分界

- **C16.1** 安全可维护的共享Rust能力优先，可借成熟Rust组件或一次准备的静态资料；只在明确的复杂pandas规则/特殊DateOffset/业务日历/真实自定义执行协议边界委托。
- **C16.2** strptime/date_range按最终决定P08/P09逐格式/规则分工，不因未写完、解析失败、宽年或tz换引擎求成功；普通解析始终C14。

### C17 日历、经过时长与边界计数

- **C17.1** 新Pddt命名日历/Delta按日历顺序/月末/绝对字段语义；固定timedelta运算符按实际经过时间、日期相减返回真实时长、diff按已定单位边界计数，不能全部加整数秒。
- **C17.2** 保留Pydt标准datetime减法/运算和Delta自身语义；不因新Pddt改变标量。Delta共享算法与薄容器适配分工，不给relativedelta另建原生整列实现；继承的合法外部协商保持。

### C18 时区服务及附加/转换/去除

- **C18.1** 标准UTC/timezone/ZoneInfo/IANA字符串及受支持自定义tzinfo按既定规则；真实pytz只取有效地区名到ZoneInfo，无效名报错，不强依赖pytz、不猜固定偏移。自定义tzinfo无法形成pandas列时明确错误。
- **C18.2** local首次实际需要时发现并缓存成功ZoneInfo，失败不回退UTC；不导入即探测系统。
- **C18.3** aware有效时间点按真实时刻转换，naive按明确来源/目标本地化；混合来源需要tz就明确给，不猜第一行/退object；带区数组UTC刻度不能当本地YMD。
- **C18.4** tz_localize(None)去区保钟表；tz_convert(None)先UTC去区且须aware；astimezone(None)为local；tz_switch(None)按既定保钟表去区，naive来源转非空目标须base_tz，naive=True在完成转换后保目标钟表。None逐入口解释。

### C19 集中DST及普通时区快路

- **C19.1** 新Pddt构造/parse/严格replace/tz_localize及解释naive来源的必要入口保留ambiguous/nonexistent默认raise，不加fold；aware转换不重新本地化。Parser不检查存在性，Pydt严格创建/replace缺失时间错误、fold只选重复。
- **C19.2** ambiguous支持raise/NaT/infer、真Python/NumPy bool标量/一维布尔列，按原完整位置；bool为pandas DST/非DST而非普适早晚/fold。infer由Rust按原序推断、证据不足报错，不排序/猜测/调pandas infer。
- **C19.3** nonexistent支持raise/NaT/shift_forward/shift_backward/合法统一timedelta或Timedelta，不扩逐行列；shift为最近有效边界，不是恒按缺口长度移。数字0/1、None/任意真假对象不作策略；显式NaT只处理对应DST问题，不吞普通解析失败。
- **C19.4** naive、标准UTC/固定偏移不做地区候选、双fold和往返验证；必要类型/范围检查保持。统一策略外层准备一次，布尔列/推断仅相应分支，必要动态适配独立保ns。

### C20 自动操作守原数学和周期含义

- **C20.1** round中点取偶，ceil不早于/floor不晚于真实输入；first/last保时钟，start/end在目标周期取有效边界，normalize留本日；不越周期冒充成功。
- **C20.2** 便利操作按既定自动规则，不给所有入口加公开DST参数；先方向/周期/有效性再参考原偏移，不机械复制fold/假设1小时缺口/生新NaT。整个周期不存在或不能可靠满足时错误。
- **C20.3** Snap最近有效周期起点、真实时刻等距取晚，重复起点按不同真实时刻；完全缺失周期按已定搜索。边界查询直接共用定义，合法不匹配False、未知/空名ValueError、非字符串TypeError。round/ceil/floor用freq，Snap用unit；fsp单标量precision按各类上限截位，不扩逐行精度。

### C21 子类自有新日期结果

- **C21.1** 精确Pddt直接出口，子类自有运算/工厂的新日期结果由库对整列发起一次正常构造，不逐行、不先父类再子类；标准data/关键字应可接收，额外必填业务参数不猜。
- **C21.2** 保留正常new/init的实际行为、合法结果和原异常，不降父类/重试/回调后强改值；用户自己再构造不算库一次保证。当前Pydt可观察协议和C07外部比较边界保持。
- **C21.3** 不包装全部pandas继承操作；查询/时长/导出不强制子类。无变化复用无新回调；copy/状态按C22，不把旧业务字典覆盖新日期构造结果。

### C22 复制/恢复独立于新日期构造

- **C22.1** 默认保存合法业务dict/已设slots，核心日期/unit/tz/name/有效freq与业务分开；不重复导出缓存/引用管理，不删所有下划线业务字段。浅复制新外壳按规则共享日期及业务引用，Pddt.copy默认deep=False。
- **C22.2** 深复制同一memo保别名/循环，日期缓冲按规则独立；pickle版本化验证核心后按协议恢复业务。默认不重跑业务初始化，不自动迁移旧Pddt。Delta新v2四元组和17字段LE载荷按GN10验证，不保留旧版本自动迁移或旧us值核；自定义真实状态协议仍按C22.3。
- **C22.3** 尊重真实copy/deepcopy/reduce/getstate/setstate及原异常，自定义状态不套默认格式，不丢字段/额外补用户没选的字段；用户协议自己选择构造则保留。忽略memo/业务字段的旧日期拷贝不证明本合同。

### C23 E01—E32错误架构

- **C23.1** 合理标准/领域错误写实际公开入口、字段、可靠位置/范围、简短安全预览，失败才建上下文，不泄露整列/用内部Rust名替公开入口。
- **C23.2** 外部原异常、严重错误和必要原因链/二次失败保持，不吞错求成功；完整复用pandas保持原异常、不加包装。

### C24 用户文档、类型及demo同步

- **C24.1** 全部公开pyi类/方法/独立函数有准确注解、英文用户docstring、参数/返回及必要例子，明确unit/tz/缺失/错误；不以内部源码说明代替用户用法。
- **C24.2** 采用时同步源码/pyi/指南/调用方及四demo/runtime。demo选择明确环境/版本/native指纹，直接运行不静默旧包/临时编译，导入模块不替换调用方进程。

### C25 独立预期与同产物证据

- **C25.1** 最终决定加独立正确预期作答案；Pddt参考仅查漏/比较，Pydt共同范围成对验证，数组用固定pandas/独立整数预期。构建/加载/功能/性能分层并绑定同产物。
- **C25.2** 旧调查/PASS/例外不转记新包；保留负面、未明确及已接受取舍，未测与设计推演明确标识。量化性能目标/样本/采用门槛留U12，不补造硬指标。

### C26 预算约束、快速迭代与真实推进

- **C26.1** 严格遵守计划时间、减少防御性行为、快速优化和快速迭代；后续实施先可用基准，再按预算累计可靠收益且守功能/安全/性能保护；局部方向不合适记录后转下一项，不停止整项目。优先直接清晰实现，局部问题先考虑更直接方案，不把原则硬化成无必要的大改。
- **C26.2** 新增调查/测试/工具对应真实缺口/证据/停止条件，复用不造框架，维护不压过目标；预算内调配不改总额，超步目标即时自查。每30有效分钟核对计划/进度/偏离/余额/下一动作并简报。
- **C26.3** 工具正常等待计时，必要纯等待/用户暂停单列；续接保留T0/已用/证据，完成不为余额扩新优化，不自动加时/降标。本次范围和预算以顶部当前任务为准；历史调查余额和授权不自动延用，不由本条授权修改运行代码或发布。
