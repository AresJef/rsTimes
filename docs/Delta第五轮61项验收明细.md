# Delta 第五轮：61项指定目标逐项验收

基线：Rust rc04（delta.4）；新候选：delta.5 final01；Cython：0.2.0 R2FinalE。

旧／新Rust耗时来自彼此的紧邻配对；Cython／新Rust耗时来自另一套紧邻配对。两列新Rust耗时属于不同测量时段，分别列出，不择优合并。单位μs，批量场景表示整个列表调用。
速度比=Cython耗时÷新Rust耗时。主轮和独立轮都≥1.00，且覆盖、质量、精度及稳定性全部合格，才算目标通过。保护项要求旧Rust÷新Rust两轮都≥1/1.05。

| ID | 方向／场景 | 旧Rust μs | 新Rust μs（与旧版） | Cython μs | 新Rust μs（与Cython） | C／新：主轮 | C／新：独立 | 目标 | 旧版保护 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| I01 | 整数构造 / C:construct-empty | 0.0340 | 0.0320 | 0.0245 | 0.0316 | 0.7784 | 0.7776 | 未通过 | 通过 |
| I02 | 整数构造 / C:construct-normal | 0.1969 | 0.1845 | 0.1859 | 0.1898 | 0.9831 | 0.9806 | 未通过 | 未明确 |
| I03 | 整数构造 / C:construct-positive | 0.1819 | 0.1748 | 0.1727 | 0.1748 | 0.9795 | 0.9867 | 未通过 | 通过 |
| I04 | 整数构造 / C:construct-negative | 0.1806 | 0.1704 | 0.1679 | 0.1727 | 0.9904 | 0.9708 | 未通过 | 未明确 |
| I05 | 整数构造 / C:construct-mixed | 0.1518 | 0.1470 | 0.1439 | 0.1477 | 0.9711 | 0.9732 | 未通过 | 通过 |
| I06 | 整数构造 / C:construct-absolute | 0.2246 | 0.2153 | 0.2049 | 0.2135 | 0.9541 | 0.9553 | 未通过 | 未明确 |
| I07 | 整数构造 / C:construct-positional | 0.0949 | 0.0782 | 0.0576 | 0.0776 | 0.7440 | 0.7326 | 未通过 | 通过 |
| I08 | 属性读取 / C:value-attributes | 0.1920 | 0.1857 | 0.1776 | 0.1751 | 1.0079 | 1.0239 | 通过 | 未明确 |
| I09 | 表示文本 / C:value-repr | 0.0947 | 0.0183 | 0.0191 | 0.0184 | 1.0405 | 1.0421 | 通过 | 通过 |
| I10 | 首次哈希 / C:value-hash-first | 0.1381 | 0.1247 | 0.1220 | 0.1271 | 0.9438 | 0.9641 | 未通过 | 通过 |
| I11 | Delta加减 / C:arithmetic-delta-add | 0.0349 | 0.0306 | 0.0243 | 0.0297 | 0.8199 | 0.8073 | 未通过 | 通过 |
| I12 | Delta加减 / C:arithmetic-delta-subtract | 0.0351 | 0.0305 | 0.0235 | 0.0304 | 0.7763 | 0.7673 | 未通过 | 通过 |
| I13 | timedelta运算 / C:arithmetic-timedelta-add | 0.0334 | 0.0325 | 0.0248 | 0.0319 | 0.7811 | 0.7699 | 未通过 | 通过 |
| I14 | timedelta运算 / C:arithmetic-timedelta-radd | 0.0355 | 0.0346 | 0.0277 | 0.0340 | 0.8177 | 0.8067 | 未通过 | 通过 |
| I15 | timedelta运算 / C:arithmetic-timedelta-rsubtract | 0.0362 | 0.0342 | 0.0273 | 0.0343 | 0.8041 | 0.7865 | 未通过 | 未明确 |
| I16 | NumPy日期 / C:interop-numpy-datetime-ns | 0.0729 | 0.0475 | 0.0597 | 0.0477 | 1.2566 | 1.2552 | 通过 | 通过 |
| I17 | NumPy日期 / C:interop-numpy-datetime-us-add | 0.0728 | 0.0470 | 0.0590 | 0.0471 | 1.2590 | 1.2523 | 通过 | 未明确 |
| I18 | NumPy时长 / C:interop-numpy-duration-us-subtract | 0.0640 | 0.0438 | 0.0480 | 0.0405 | 1.1964 | 1.1653 | 通过 | 未明确 |
| I19 | NumPy时长 / C:interop-numpy-duration-year | 0.0750 | 0.0417 | 0.0532 | 0.0412 | 1.2890 | 1.2953 | 通过 | 未明确 |
| I20 | pandas时长 / C:interop-pandas-timedelta-subtract | 0.0802 | 0.0612 | 0.0546 | 0.0598 | 0.9089 | 0.9151 | 未通过 | 通过 |
| I21 | 16元素timedelta批量 / C:batch-timedelta-16 | 0.3635 | 0.3175 | 0.2126 | 0.3172 | 0.6692 | 0.6726 | 未通过 | 通过 |
| I22 | 16元素Delta批量 / C:batch-delta-16 | 0.3587 | 0.3126 | 0.2337 | 0.3096 | 0.7565 | 0.7541 | 未通过 | 通过 |
| I23 | 整数构造 / R:relative:mixed | 0.1283 | 0.1197 | 0.1122 | 0.1190 | 0.9428 | 0.9482 | 未通过 | 通过 |
| I24 | Delta加减 / R:delta-arithmetic:positive:sub | 0.0513 | 0.0483 | 0.0430 | 0.0478 | 0.8985 | 0.8933 | 未通过 | 通过 |
| I25 | Delta加减 / R:delta-arithmetic:negative:add | 0.0470 | 0.0443 | 0.0393 | 0.0441 | 0.8988 | 0.8881 | 未通过 | 通过 |
| I26 | Delta加减 / R:delta-arithmetic:cancel:add | 0.0465 | 0.0443 | 0.0394 | 0.0441 | 0.8956 | 0.8874 | 未通过 | 通过 |
| I27 | Delta加减 / R:delta-arithmetic:cancel:sub | 0.0510 | 0.0479 | 0.0429 | 0.0476 | 0.9069 | 0.8974 | 未通过 | 通过 |
| I28 | Delta加减 / R:delta-arithmetic:year:both:add | 0.0524 | 0.0465 | 0.0392 | 0.0470 | 0.8357 | 0.8333 | 未通过 | 通过 |
| I29 | Delta加减 / R:delta-arithmetic:year:both:sub | 0.0577 | 0.0494 | 0.0433 | 0.0490 | 0.8890 | 0.8822 | 未通过 | 通过 |
| I30 | 取负与绝对值 / R:unary:negative-month:neg | 0.0470 | 0.0460 | 0.0326 | 0.0457 | 0.7163 | 0.7102 | 未通过 | 通过 |
| I31 | 取负与绝对值 / R:unary:negative-us:abs | 0.0545 | 0.0516 | 0.0384 | 0.0511 | 0.7557 | 0.7409 | 未通过 | 通过 |
| I32 | 取负与绝对值 / R:unary:opposite-signs:abs | 0.0537 | 0.0511 | 0.0385 | 0.0504 | 0.7672 | 0.7585 | 未通过 | 通过 |
| I33 | timedelta运算 / R:timedelta:positive:relative:sub | 0.0765 | 0.0742 | 0.0653 | 0.0743 | 0.8765 | 0.8807 | 未通过 | 通过 |
| I34 | timedelta运算 / R:timedelta:positive:relative:rsub | 0.0800 | 0.0766 | 0.0721 | 0.0756 | 0.9437 | 0.9626 | 未通过 | 通过 |
| I35 | timedelta运算 / R:timedelta:positive:absolute:add | 0.0617 | 0.0601 | 0.0512 | 0.0610 | 0.8469 | 0.8410 | 未通过 | 通过 |
| I36 | timedelta运算 / R:timedelta:positive:absolute:sub | 0.0769 | 0.0741 | 0.0654 | 0.0745 | 0.8750 | 0.8854 | 未通过 | 通过 |
| I37 | timedelta运算 / R:timedelta:positive:absolute:rsub | 0.0798 | 0.0771 | 0.0713 | 0.0755 | 0.9361 | 0.9518 | 未通过 | 通过 |
| I38 | timedelta运算 / R:timedelta:negative-us:relative:add | 0.0622 | 0.0603 | 0.0512 | 0.0609 | 0.8377 | 0.8426 | 未通过 | 通过 |
| I39 | timedelta运算 / R:timedelta:negative-us:relative:sub | 0.0765 | 0.0739 | 0.0651 | 0.0744 | 0.8726 | 0.8770 | 未通过 | 通过 |
| I40 | timedelta运算 / R:timedelta:negative-us:relative:rsub | 0.0795 | 0.0760 | 0.0717 | 0.0753 | 0.9419 | 0.9622 | 未通过 | 通过 |
| I41 | timedelta运算 / R:timedelta:negative-us:absolute:add | 0.0618 | 0.0604 | 0.0512 | 0.0607 | 0.8517 | 0.8402 | 未通过 | 通过 |
| I42 | timedelta运算 / R:timedelta:negative-us:absolute:radd | 0.0656 | 0.0641 | 0.0574 | 0.0638 | 0.9009 | 0.8967 | 未通过 | 通过 |
| I43 | timedelta运算 / R:timedelta:negative-us:absolute:sub | 0.0772 | 0.0739 | 0.0657 | 0.0745 | 0.8789 | 0.8875 | 未通过 | 通过 |
| I44 | timedelta运算 / R:timedelta:negative-us:absolute:rsub | 0.0798 | 0.0762 | 0.0714 | 0.0754 | 0.9348 | 0.9497 | 未通过 | 通过 |
| I45 | 首次哈希 / R:protocol:hash-first | 0.1691 | 0.1540 | 0.1443 | 0.1587 | 0.9165 | 0.9074 | 未通过 | 通过 |
| I46 | 表示文本 / R:protocol:repr | 0.0997 | 0.0265 | 0.0274 | 0.0266 | 1.0287 | 1.0274 | 通过 | 通过 |
| I47 | 表示文本 / R:protocol:str | 0.0994 | 0.0262 | 0.0267 | 0.0260 | 1.0291 | 1.0280 | 通过 | 通过 |
| I48 | NumPy日期 / R:numpy-datetime:D:negative:add | 0.0986 | 0.0743 | 0.0920 | 0.0748 | 1.2262 | 1.2328 | 通过 | 通过 |
| I49 | NumPy日期 / R:numpy-datetime:Y:negative:add | 0.1036 | 0.0823 | 0.0961 | 0.0832 | 1.1506 | 1.1595 | 通过 | 通过 |
| I50 | NumPy时长 / R:numpy-timedelta:ns:negative:add | 0.1070 | 0.0713 | 0.0817 | 0.0724 | 1.1159 | 1.1493 | 通过 | 未明确 |
| I51 | NumPy时长 / R:numpy-timedelta:ns:negative:sub | 0.1067 | 0.0847 | 0.0896 | 0.0852 | 1.0505 | 1.0552 | 通过 | 通过 |
| I52 | NumPy时长 / R:numpy-timedelta:us:negative:add | 0.1062 | 0.0713 | 0.0822 | 0.0717 | 1.1461 | 1.1430 | 通过 | 通过 |
| I53 | NumPy时长 / R:numpy-timedelta:us:negative:sub | 0.1076 | 0.0837 | 0.0889 | 0.0837 | 1.0667 | 1.0606 | 通过 | 通过 |
| I54 | NumPy时长 / R:numpy-timedelta:D:negative:add | 0.1070 | 0.0716 | 0.0877 | 0.0722 | 1.2107 | 1.2090 | 通过 | 通过 |
| I55 | NumPy时长 / R:numpy-timedelta:D:negative:sub | 0.1067 | 0.0844 | 0.0950 | 0.0838 | 1.1295 | 1.1328 | 通过 | 通过 |
| I56 | NumPy时长 / R:numpy-timedelta:M:negative:add | 0.1071 | 0.0718 | 0.0870 | 0.0722 | 1.2045 | 1.2052 | 通过 | 通过 |
| I57 | NumPy时长 / R:numpy-timedelta:M:negative:sub | 0.1075 | 0.0838 | 0.0942 | 0.0840 | 1.1164 | 1.1339 | 通过 | 通过 |
| I58 | NumPy时长 / R:numpy-timedelta:Y:negative:add | 0.1068 | 0.0722 | 0.0865 | 0.0720 | 1.1949 | 1.2084 | 通过 | 通过 |
| I59 | NumPy时长 / R:numpy-timedelta:Y:negative:sub | 0.1069 | 0.0839 | 0.0939 | 0.0838 | 1.1183 | 1.1275 | 通过 | 通过 |
| I60 | 10000元素负timedelta批量 / R:bulk:timedelta-negative:10000 | 185.9569 | 166.1044 | 175.8198 | 167.8896 | 1.0491 | 1.0540 | 通过 | 通过 |
| I61 | 表示文本 / direct:repr-alternating | 0.0836 | 0.0521 | 0.0755 | 0.0519 | 1.4586 | 1.4451 | 通过 | 通过 |

[266项完整CSV（含输入、稳定性和逐项证据目录）](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第五轮完整性能明细.csv)
