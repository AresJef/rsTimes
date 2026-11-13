# Delta 第五轮：200个共同场景性能对比

单位μs；批量表示整个列表调用。速度比=Cython÷新Rust；更快／接近按5%界限分类。“接近”不代表通过本轮严格追平门槛；未明确项不排名。

| 场景 | 类型 | 调用 | Cython μs | 新Rust μs | 速度比 | 主轮 | 独立轮 | 结论 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| C:construct-empty | 整数构造与归一化 | Delta() | 0.0245 | 0.0316 | 0.7776 | 0.7784 | 0.7776 | Cython更快 |
| C:construct-normal | 整数构造与归一化 | Delta(years=2,months=3,days=4,hours=5,minutes=6,seconds=7,microseconds=8) | 0.1859 | 0.1898 | 0.9818 | 0.9831 | 0.9806 | 接近 |
| C:construct-positive | 整数构造与归一化 | Delta(months=27,weeks=3,hours=55,minutes=130,seconds=125,milliseconds=2500) | 0.1727 | 0.1748 | 0.9835 | 0.9795 | 0.9867 | 接近 |
| C:construct-negative | 整数构造与归一化 | Delta(months=-27,weeks=-3,hours=-55,minutes=-130,seconds=-125,milliseconds=-2500) | 0.1679 | 0.1727 | 0.9791 | 0.9904 | 0.9708 | 接近 |
| C:construct-mixed | 整数构造与归一化 | Delta(years=3,quarters=-5,days=-21,hours=49,microseconds=-1234567) | 0.1439 | 0.1477 | 0.9713 | 0.9711 | 0.9732 | 接近 |
| C:construct-absolute | 整数构造与归一化 | Delta(year=2024,month=12,day=31,weekday=4,hour=23,minute=59,second=59,microsecond=123456) | 0.2049 | 0.2135 | 0.9543 | 0.9541 | 0.9553 | 接近 |
| C:construct-ms-us | 整数构造与归一化 | Delta(milliseconds=1234,microseconds=5678,millisecond=12,microsecond=3456) | 0.1289 | 0.1302 | 0.9851 | 0.9877 | 0.9836 | 接近 |
| C:construct-positional | 整数构造与归一化 | Delta(2,1,3,4,5,6,7,8,9,10) | 0.0576 | 0.0776 | 0.7410 | 0.7440 | 0.7326 | Cython更快 |
| C:value-attributes | 属性读取 | (d.years,d.months,d.days,d.hours,d.minutes,d.seconds,d.microseconds,d.year,d.month,d.day,d.weekday,d.hour,d.minute,d.second,d.microsecond) | 0.1776 | 0.1751 | 1.0146 | 1.0079 | 1.0239 | 接近 |
| C:value-bool-zero | 真假判断 | bool(zero) | 0.0152 | 0.0152 | 1.0000 | 1.0009 | 0.9996 | 接近 |
| C:value-bool-mixed | 真假判断 | bool(d) | 0.0149 | 0.0150 | 0.9983 | 0.9993 | 0.9978 | 接近 |
| C:value-repr | 表示：重复读取同一对象 | repr(d) | 0.0191 | 0.0184 | 1.0414 | 1.0405 | 1.0421 | 接近 |
| C:value-hash-first | 哈希 | hash(Delta(months=3,days=4,hours=5)) | 0.1220 | 0.1271 | 0.9519 | 0.9438 | 0.9641 | Cython更快 |
| C:value-hash-cached | 哈希 | hash(cached) | 0.0217 | 0.0219 | 0.9884 | 0.9887 | 0.9875 | 接近 |
| C:value-equal-delta | 相等比较 | d==equal | 0.0150 | 0.0151 | 0.9996 | 0.9994 | 1.0000 | 接近 |
| C:value-unequal-delta | 相等比较 | d!=different | 0.0148 | 0.0149 | 0.9975 | 0.9975 | 0.9976 | 接近 |
| C:value-negate | 取负与绝对值 | -d | 0.0162 | 0.0253 | 0.6407 | 0.6420 | 0.6391 | Cython更快 |
| C:value-absolute | 取负与绝对值 | abs(negative) | 0.0183 | 0.0274 | 0.6705 | 0.6727 | 0.6643 | Cython更快 |
| C:arithmetic-delta-add | Delta加减 | d+other | 0.0243 | 0.0297 | 0.8168 | 0.8199 | 0.8073 | Cython更快 |
| C:arithmetic-delta-subtract | Delta加减 | d-other | 0.0235 | 0.0304 | 0.7727 | 0.7763 | 0.7673 | Cython更快 |
| C:arithmetic-timedelta-add | timedelta运算 | d+td | 0.0248 | 0.0319 | 0.7747 | 0.7811 | 0.7699 | Cython更快 |
| C:arithmetic-timedelta-radd | timedelta运算 | td+d | 0.0277 | 0.0340 | 0.8108 | 0.8177 | 0.8067 | Cython更快 |
| C:arithmetic-timedelta-subtract | timedelta运算 | d-td | 0.0240 | 0.0312 | 0.7680 | 0.7716 | 0.7583 | Cython更快 |
| C:arithmetic-timedelta-rsubtract | timedelta运算 | td-d | 0.0273 | 0.0343 | 0.7975 | 0.8041 | 0.7865 | Cython更快 |
| C:calendar-date-add | date/datetime与时区 | calendar+date | 0.0330 | 0.0350 | 0.9414 | 0.9452 | 0.9364 | Cython更快 |
| C:calendar-date-radd | date/datetime与时区 | date+calendar | 0.0373 | 0.0390 | 0.9563 | 0.9549 | 0.9602 | 接近 |
| C:calendar-date-rsubtract | date/datetime与时区 | date-calendar | 0.0393 | 0.0382 | 1.0294 | 1.0316 | 1.0213 | 接近 |
| C:calendar-datetime-add | date/datetime与时区 | clock+datetime | 0.0384 | 0.0349 | 1.1019 | 1.1049 | 1.0981 | Rust更快 |
| C:calendar-datetime-radd | date/datetime与时区 | datetime+clock | 0.0405 | 0.0367 | 1.1136 | 1.1104 | 1.1170 | Rust更快 |
| C:calendar-datetime-rsubtract | date/datetime与时区 | datetime-clock | 0.0405 | 0.0387 | 1.0484 | 1.0483 | 1.0484 | 接近 |
| C:calendar-aware-weekday | date/datetime与时区 | aware+weekday | 0.0416 | 0.0398 | 1.0460 | 1.0448 | 1.0484 | 接近 |
| C:calendar-date-subclass | date/datetime与时区 | datechild+calendar | 0.2508 | 0.2495 | 1.0042 | 1.0056 | 1.0018 | 接近 |
| C:calendar-datetime-subclass | date/datetime与时区 | datetimechild+clock | 0.5660 | 0.5642 | 1.0018 | 1.0017 | 1.0020 | 接近 |
| C:calendar-no-change | date/datetime与时区 | datetime+zero | 0.0215 | 0.0182 | 1.1780 | 1.1782 | 1.1773 | Rust更快 |
| C:interop-from-relativedelta | relativedelta | Delta.from_relativedelta(rd) | 1.7137 | 1.7110 | 1.0050 | 1.0072 | 1.0023 | 接近 |
| C:interop-relativedelta-add | relativedelta | d+rd | 1.7077 | 1.6909 | 1.0125 | 1.0132 | 1.0119 | 接近 |
| C:interop-relativedelta-radd | relativedelta | rd+d | 1.8149 | 1.7906 | 1.0121 | 1.0149 | 1.0101 | 接近 |
| C:interop-relativedelta-subtract | relativedelta | d-rd | 1.7063 | 1.6823 | 1.0135 | 1.0128 | 1.0138 | 接近 |
| C:interop-relativedelta-rsubtract | relativedelta | rd-d | 1.7599 | 1.7408 | 1.0113 | 1.0130 | 1.0077 | 接近 |
| C:interop-numpy-datetime-ns | NumPy标量 | clock+ndt_ns | 0.0597 | 0.0477 | 1.2558 | 1.2566 | 1.2552 | Rust更快 |
| C:interop-numpy-datetime-us-add | NumPy标量 | clock+ndt_us | 0.0590 | 0.0471 | 1.2563 | 1.2590 | 1.2523 | Rust更快 |
| C:interop-numpy-datetime-us-subtract | NumPy标量 | ndt_us-clock | 0.4206 | 0.2845 | 1.4753 | 1.4734 | 1.4816 | Rust更快 |
| C:interop-numpy-datetime-year | NumPy标量 | ndt_year+calendar | 0.4102 | 0.2770 | 1.4686 | 1.4806 | 1.4650 | 不明确 |
| C:interop-numpy-duration-ns | NumPy标量 | d+ntd | 0.0540 | 0.0409 | 1.3097 | 1.3058 | 1.3129 | Rust更快 |
| C:interop-numpy-duration-us-add | NumPy标量 | d+ntd_us | 0.0531 | 0.0408 | 1.3042 | 1.3056 | 1.2969 | Rust更快 |
| C:interop-numpy-duration-us-subtract | NumPy标量 | d-ntd_us | 0.0480 | 0.0405 | 1.1842 | 1.1964 | 1.1653 | Rust更快 |
| C:interop-numpy-duration-us-rsubtract | NumPy标量 | ntd_us-d | 0.4123 | 0.2857 | 1.4386 | 1.4427 | 1.4357 | Rust更快 |
| C:interop-numpy-duration-year | NumPy标量 | d+ntd_year | 0.0532 | 0.0412 | 1.2915 | 1.2890 | 1.2953 | Rust更快 |
| C:interop-pandas-timedelta-add | pandas | ptd+d | 0.0549 | 0.0596 | 0.9237 | 0.9255 | 0.9224 | Cython更快 |
| C:interop-pandas-timedelta-subtract | pandas | ptd-d | 0.0546 | 0.0598 | 0.9106 | 0.9089 | 0.9151 | Cython更快 |
| C:interop-pydt-add | Pydt | pydt+clock | 0.5988 | 0.5922 | 1.0101 | 1.0107 | 1.0085 | 接近 |
| C:interop-pydt-subtract | Pydt | pydt-clock | 0.6138 | 0.6096 | 1.0084 | 1.0078 | 1.0089 | 接近 |
| C:batch-date-16 | 批量 date/datetime | batch-date-16 | 0.3698 | 0.3916 | 0.9468 | 0.9424 | 0.9487 | Cython更快 |
| C:batch-date-256 | 批量 date/datetime | batch-date-256 | 5.7706 | 5.3104 | 1.0878 | 1.0827 | 1.0913 | Rust更快 |
| C:batch-date-4096 | 批量 date/datetime | batch-date-4096 | 87.4816 | 83.8641 | 1.0429 | 1.0420 | 1.0439 | 接近 |
| C:batch-datetime-16 | 批量 date/datetime | batch-datetime-16 | 0.3734 | 0.3616 | 1.0295 | 1.0352 | 1.0261 | 接近 |
| C:batch-datetime-256 | 批量 date/datetime | batch-datetime-256 | 5.7960 | 4.8868 | 1.1951 | 1.1946 | 1.1966 | Rust更快 |
| C:batch-datetime-4096 | 批量 date/datetime | batch-datetime-4096 | 89.1942 | 78.8111 | 1.1346 | 1.1421 | 1.1323 | Rust更快 |
| C:batch-timedelta-16 | 批量 timedelta | batch-timedelta-16 | 0.2126 | 0.3172 | 0.6720 | 0.6692 | 0.6726 | Cython更快 |
| C:batch-timedelta-256 | 批量 timedelta | batch-timedelta-256 | 4.9340 | 4.2630 | 1.1603 | 1.1600 | 1.1616 | Rust更快 |
| C:batch-timedelta-4096 | 批量 timedelta | batch-timedelta-4096 | 74.7963 | 68.1561 | 1.1009 | 1.0893 | 1.1199 | Rust更快 |
| C:batch-delta-16 | 批量 Delta | batch-delta-16 | 0.2337 | 0.3096 | 0.7553 | 0.7565 | 0.7541 | Cython更快 |
| C:batch-delta-256 | 批量 Delta | batch-delta-256 | 5.1958 | 4.1567 | 1.2526 | 1.2518 | 1.2547 | Rust更快 |
| C:batch-delta-4096 | 批量 Delta | batch-delta-4096 | 81.0257 | 65.9353 | 1.2251 | 1.2205 | 1.2251 | Rust更快 |
| R:relative:zero | 整数构造与归一化 | relative:zero | 0.0515 | 0.0586 | 0.8820 | 0.8814 | 0.8835 | Cython更快 |
| R:relative:mixed | 整数构造与归一化 | relative:mixed | 0.1122 | 0.1190 | 0.9438 | 0.9428 | 0.9482 | Cython更快 |
| R:absolute:clamps | 整数构造与归一化 | absolute:clamps | 0.1267 | 0.1402 | 0.9018 | 0.9065 | 0.8986 | Cython更快 |
| R:delta-arithmetic:positive:add | Delta加减 | delta-arithmetic:positive:add | 0.0395 | 0.0444 | 0.8906 | 0.8929 | 0.8819 | Cython更快 |
| R:delta-arithmetic:positive:sub | Delta加减 | delta-arithmetic:positive:sub | 0.0430 | 0.0478 | 0.8979 | 0.8985 | 0.8933 | Cython更快 |
| R:delta-arithmetic:negative:add | Delta加减 | delta-arithmetic:negative:add | 0.0393 | 0.0441 | 0.8909 | 0.8988 | 0.8881 | Cython更快 |
| R:delta-arithmetic:negative:sub | Delta加减 | delta-arithmetic:negative:sub | 0.0427 | 0.0472 | 0.9038 | 0.9114 | 0.8956 | Cython更快 |
| R:delta-arithmetic:cancel:add | Delta加减 | delta-arithmetic:cancel:add | 0.0394 | 0.0441 | 0.8928 | 0.8956 | 0.8874 | Cython更快 |
| R:delta-arithmetic:cancel:sub | Delta加减 | delta-arithmetic:cancel:sub | 0.0429 | 0.0476 | 0.9023 | 0.9069 | 0.8974 | Cython更快 |
| R:delta-arithmetic:year:both:add | Delta加减 | delta-arithmetic:year:both:add | 0.0392 | 0.0470 | 0.8347 | 0.8357 | 0.8333 | Cython更快 |
| R:delta-arithmetic:year:both:sub | Delta加减 | delta-arithmetic:year:both:sub | 0.0433 | 0.0490 | 0.8870 | 0.8890 | 0.8822 | Cython更快 |
| R:unary:negative-month:neg | 取负与绝对值 | unary:negative-month:neg | 0.0326 | 0.0457 | 0.7128 | 0.7163 | 0.7102 | Cython更快 |
| R:unary:negative-us:abs | 取负与绝对值 | unary:negative-us:abs | 0.0384 | 0.0511 | 0.7481 | 0.7557 | 0.7409 | Cython更快 |
| R:unary:opposite-signs:abs | 取负与绝对值 | unary:opposite-signs:abs | 0.0385 | 0.0504 | 0.7619 | 0.7672 | 0.7585 | Cython更快 |
| R:timedelta:positive:relative:add | timedelta运算 | timedelta:positive:relative:add | 0.0512 | 0.0608 | 0.8404 | 0.8465 | 0.8361 | Cython更快 |
| R:timedelta:positive:relative:radd | timedelta运算 | timedelta:positive:relative:radd | 0.0572 | 0.0639 | 0.8951 | 0.8966 | 0.8933 | Cython更快 |
| R:timedelta:positive:relative:sub | timedelta运算 | timedelta:positive:relative:sub | 0.0653 | 0.0743 | 0.8787 | 0.8765 | 0.8807 | Cython更快 |
| R:timedelta:positive:relative:rsub | timedelta运算 | timedelta:positive:relative:rsub | 0.0721 | 0.0756 | 0.9521 | 0.9437 | 0.9626 | Cython更快 |
| R:timedelta:positive:absolute:add | timedelta运算 | timedelta:positive:absolute:add | 0.0512 | 0.0610 | 0.8430 | 0.8469 | 0.8410 | Cython更快 |
| R:timedelta:positive:absolute:radd | timedelta运算 | timedelta:positive:absolute:radd | 0.0573 | 0.0639 | 0.8961 | 0.8970 | 0.8943 | Cython更快 |
| R:timedelta:positive:absolute:sub | timedelta运算 | timedelta:positive:absolute:sub | 0.0654 | 0.0745 | 0.8779 | 0.8750 | 0.8854 | Cython更快 |
| R:timedelta:positive:absolute:rsub | timedelta运算 | timedelta:positive:absolute:rsub | 0.0713 | 0.0755 | 0.9443 | 0.9361 | 0.9518 | Cython更快 |
| R:timedelta:negative-us:relative:add | timedelta运算 | timedelta:negative-us:relative:add | 0.0512 | 0.0609 | 0.8401 | 0.8377 | 0.8426 | Cython更快 |
| R:timedelta:negative-us:relative:radd | timedelta运算 | timedelta:negative-us:relative:radd | 0.0572 | 0.0643 | 0.8915 | 0.8937 | 0.8883 | Cython更快 |
| R:timedelta:negative-us:relative:sub | timedelta运算 | timedelta:negative-us:relative:sub | 0.0651 | 0.0744 | 0.8742 | 0.8726 | 0.8770 | Cython更快 |
| R:timedelta:negative-us:relative:rsub | timedelta运算 | timedelta:negative-us:relative:rsub | 0.0717 | 0.0753 | 0.9511 | 0.9419 | 0.9622 | Cython更快 |
| R:timedelta:negative-us:absolute:add | timedelta运算 | timedelta:negative-us:absolute:add | 0.0512 | 0.0607 | 0.8464 | 0.8517 | 0.8402 | Cython更快 |
| R:timedelta:negative-us:absolute:radd | timedelta运算 | timedelta:negative-us:absolute:radd | 0.0574 | 0.0638 | 0.8991 | 0.9009 | 0.8967 | Cython更快 |
| R:timedelta:negative-us:absolute:sub | timedelta运算 | timedelta:negative-us:absolute:sub | 0.0657 | 0.0745 | 0.8821 | 0.8789 | 0.8875 | Cython更快 |
| R:timedelta:negative-us:absolute:rsub | timedelta运算 | timedelta:negative-us:absolute:rsub | 0.0714 | 0.0754 | 0.9440 | 0.9348 | 0.9497 | Cython更快 |
| R:getters:single | 属性读取 | getters:single | 0.0262 | 0.0259 | 1.0094 | 1.0098 | 1.0088 | 接近 |
| R:getters:all | 属性读取 | getters:all | 0.6023 | 0.6152 | 0.9908 | 0.9917 | 0.9903 | 不明确 |
| R:bool:mixed | 真假判断 | bool:mixed | 0.0235 | 0.0235 | 0.9993 | 0.9990 | 1.0000 | 接近 |
| R:date-call:cross-year:reuse | date/datetime与时区 | date-call:cross-year:reuse | 0.0493 | 0.0492 | 1.0032 | 1.0013 | 1.0057 | 接近 |
| R:date-call:cross-year:construct | date/datetime与时区 | date-call:cross-year:construct | 0.1156 | 0.1201 | 0.9638 | 0.9635 | 0.9660 | 接近 |
| R:date-call:month-end:reuse | date/datetime与时区 | date-call:month-end:reuse | 0.0510 | 0.0482 | 1.0615 | 1.0631 | 1.0606 | Rust更快 |
| R:date-call:month-end:construct | date/datetime与时区 | date-call:month-end:construct | 0.1239 | 0.1275 | 0.9722 | 0.9717 | 0.9722 | 接近 |
| R:date-call:us-before:reuse | date/datetime与时区 | date-call:us-before:reuse | 0.0521 | 0.0487 | 1.0647 | 1.0644 | 1.0647 | Rust更快 |
| R:date-call:us-before:construct | date/datetime与时区 | date-call:us-before:construct | 0.1219 | 0.1238 | 0.9889 | 0.9885 | 0.9896 | 接近 |
| R:date-call:utc:reuse | date/datetime与时区 | date-call:utc:reuse | 0.0520 | 0.0500 | 1.0379 | 1.0350 | 1.0434 | 接近 |
| R:date-call:utc:construct | date/datetime与时区 | date-call:utc:construct | 0.1244 | 0.1288 | 0.9701 | 0.9713 | 0.9667 | 接近 |
| R:date-call:ny-fold:reuse | date/datetime与时区 | date-call:ny-fold:reuse | 0.0502 | 0.0472 | 1.0688 | 1.0690 | 1.0688 | Rust更快 |
| R:date-call:ny-fold:construct | date/datetime与时区 | date-call:ny-fold:construct | 0.1175 | 0.1215 | 0.9699 | 0.9684 | 0.9718 | 接近 |
| R:date-call:ny-unchanged:reuse | date/datetime与时区 | date-call:ny-unchanged:reuse | 0.0331 | 0.0298 | 1.1110 | 1.1118 | 1.1109 | Rust更快 |
| R:date-call:ny-unchanged:construct | date/datetime与时区 | date-call:ny-unchanged:construct | 0.0659 | 0.0672 | 0.9819 | 0.9856 | 0.9775 | 接近 |
| R:date-combination:reuse | date/datetime与时区 | date-combination:reuse | 0.6319 | 0.6162 | 1.0210 | 1.0175 | 1.0271 | 接近 |
| R:date-combination:construct | date/datetime与时区 | date-combination:construct | 1.0635 | 1.0655 | 0.9970 | 0.9977 | 0.9956 | 接近 |
| R:protocol:eq-equal | 相等比较 | protocol:eq-equal | 0.0241 | 0.0241 | 1.0007 | 1.0000 | 1.0010 | 接近 |
| R:protocol:eq-different | 相等比较 | protocol:eq-different | 0.0235 | 0.0239 | 0.9884 | 0.9865 | 0.9909 | 接近 |
| R:protocol:hash-first | 哈希 | protocol:hash-first | 0.1443 | 0.1587 | 0.9121 | 0.9165 | 0.9074 | Cython更快 |
| R:protocol:hash-cached | 哈希 | protocol:hash-cached | 0.0295 | 0.0297 | 0.9936 | 0.9917 | 0.9959 | 接近 |
| R:protocol:repr | 表示：重复读取同一对象 | protocol:repr | 0.0274 | 0.0266 | 1.0282 | 1.0287 | 1.0274 | 接近 |
| R:protocol:str | 表示：重复读取同一对象 | protocol:str | 0.0267 | 0.0260 | 1.0284 | 1.0291 | 1.0280 | 接近 |
| R:dateutil:from:integer:Delta | relativedelta | dateutil:from:integer:Delta | 1.7069 | 1.7111 | 0.9981 | 0.9956 | 0.9999 | 接近 |
| R:dateutil:from:fraction:Delta | relativedelta | dateutil:from:fraction:Delta | 2.1837 | 2.1684 | 1.0061 | 1.0066 | 1.0046 | 接近 |
| R:dateutil:from:absolute:Delta | relativedelta | dateutil:from:absolute:Delta | 1.8657 | 1.8444 | 1.0080 | 1.0114 | 1.0046 | 接近 |
| R:dateutil:arithmetic:absolute:add | relativedelta | dateutil:arithmetic:absolute:add | 1.8816 | 1.8526 | 1.0162 | 1.0162 | 1.0162 | 接近 |
| R:dateutil:arithmetic:fraction:rsub | relativedelta | dateutil:arithmetic:fraction:rsub | 2.2631 | 2.2445 | 1.0097 | 1.0090 | 1.0114 | 接近 |
| R:numpy-datetime:ns:negative:add | NumPy标量 | numpy-datetime:ns:negative:add | 0.1032 | 0.0778 | 1.3282 | 1.3298 | 1.3265 | Rust更快 |
| R:numpy-datetime:ns:negative:method-rsub | NumPy标量 | numpy-datetime:ns:negative:method-rsub | 0.2245 | 0.2282 | 0.9862 | 0.9840 | 0.9915 | 接近 |
| R:numpy-datetime:us:negative:add | NumPy标量 | numpy-datetime:us:negative:add | 0.1024 | 0.0735 | 1.3944 | 1.3940 | 1.3946 | Rust更快 |
| R:numpy-datetime:us:negative:method-rsub | NumPy标量 | numpy-datetime:us:negative:method-rsub | 0.2235 | 0.2272 | 0.9824 | 0.9765 | 0.9987 | 接近 |
| R:numpy-datetime:D:negative:add | NumPy标量 | numpy-datetime:D:negative:add | 0.0920 | 0.0748 | 1.2284 | 1.2262 | 1.2328 | Rust更快 |
| R:numpy-datetime:D:negative:method-rsub | NumPy标量 | numpy-datetime:D:negative:method-rsub | 0.2344 | 0.2270 | 1.0326 | 1.0301 | 1.0407 | 接近 |
| R:numpy-datetime:M:negative:add | NumPy标量 | numpy-datetime:M:negative:add | 0.0991 | 0.0840 | 1.1834 | 1.1834 | 1.1835 | Rust更快 |
| R:numpy-datetime:M:negative:method-rsub | NumPy标量 | numpy-datetime:M:negative:method-rsub | 0.2444 | 0.2367 | 1.0331 | 1.0300 | 1.0374 | 接近 |
| R:numpy-datetime:Y:negative:add | NumPy标量 | numpy-datetime:Y:negative:add | 0.0961 | 0.0832 | 1.1535 | 1.1506 | 1.1595 | Rust更快 |
| R:numpy-datetime:Y:negative:method-rsub | NumPy标量 | numpy-datetime:Y:negative:method-rsub | 0.2366 | 0.2340 | 1.0154 | 1.0156 | 1.0153 | 接近 |
| R:numpy-timedelta:ns:negative:add | NumPy标量 | numpy-timedelta:ns:negative:add | 0.0817 | 0.0724 | 1.1327 | 1.1159 | 1.1493 | Rust更快 |
| R:numpy-timedelta:ns:negative:sub | NumPy标量 | numpy-timedelta:ns:negative:sub | 0.0896 | 0.0852 | 1.0524 | 1.0505 | 1.0552 | Rust更快 |
| R:numpy-timedelta:ns:negative:method-rsub | NumPy标量 | numpy-timedelta:ns:negative:method-rsub | 0.2125 | 0.2275 | 0.9362 | 0.9324 | 0.9403 | Cython更快 |
| R:numpy-timedelta:us:negative:add | NumPy标量 | numpy-timedelta:us:negative:add | 0.0822 | 0.0717 | 1.1438 | 1.1461 | 1.1430 | Rust更快 |
| R:numpy-timedelta:us:negative:sub | NumPy标量 | numpy-timedelta:us:negative:sub | 0.0889 | 0.0837 | 1.0651 | 1.0667 | 1.0606 | Rust更快 |
| R:numpy-timedelta:us:negative:method-rsub | NumPy标量 | numpy-timedelta:us:negative:method-rsub | 0.2124 | 0.2238 | 0.9437 | 0.9400 | 0.9446 | Cython更快 |
| R:numpy-timedelta:D:negative:add | NumPy标量 | numpy-timedelta:D:negative:add | 0.0877 | 0.0722 | 1.2104 | 1.2107 | 1.2090 | Rust更快 |
| R:numpy-timedelta:D:negative:sub | NumPy标量 | numpy-timedelta:D:negative:sub | 0.0950 | 0.0838 | 1.1313 | 1.1295 | 1.1328 | Rust更快 |
| R:numpy-timedelta:D:negative:method-rsub | NumPy标量 | numpy-timedelta:D:negative:method-rsub | 0.2107 | 0.2247 | 0.9404 | 0.9305 | 0.9458 | Cython更快 |
| R:numpy-timedelta:M:negative:add | NumPy标量 | numpy-timedelta:M:negative:add | 0.0870 | 0.0722 | 1.2051 | 1.2045 | 1.2052 | Rust更快 |
| R:numpy-timedelta:M:negative:sub | NumPy标量 | numpy-timedelta:M:negative:sub | 0.0942 | 0.0840 | 1.1227 | 1.1164 | 1.1339 | Rust更快 |
| R:numpy-timedelta:M:negative:method-rsub | NumPy标量 | numpy-timedelta:M:negative:method-rsub | 0.2145 | 0.2252 | 0.9549 | 0.9567 | 0.9520 | 接近 |
| R:numpy-timedelta:Y:negative:add | NumPy标量 | numpy-timedelta:Y:negative:add | 0.0865 | 0.0720 | 1.2050 | 1.1949 | 1.2084 | Rust更快 |
| R:numpy-timedelta:Y:negative:sub | NumPy标量 | numpy-timedelta:Y:negative:sub | 0.0939 | 0.0838 | 1.1223 | 1.1183 | 1.1275 | Rust更快 |
| R:numpy-timedelta:Y:negative:method-rsub | NumPy标量 | numpy-timedelta:Y:negative:method-rsub | 0.2114 | 0.2219 | 0.9481 | 0.9483 | 0.9471 | Cython更快 |
| R:save:base:write | pickle与复制 | save:base:write | 1.9667 | 0.9068 | 2.1626 | 2.1559 | 2.1735 | Rust更快 |
| R:save:base:read | pickle与复制 | save:base:read | 1.1121 | 0.5663 | 1.9705 | 1.9577 | 1.9759 | Rust更快 |
| R:save:base:copy | pickle与复制 | save:base:copy | 0.9533 | 0.1036 | 9.2256 | 9.2021 | 9.2501 | 不明确 |
| R:save:base:deepcopy | pickle与复制 | save:base:deepcopy | 3.6269 | 0.3823 | 9.5366 | 9.5366 | 9.5375 | Rust更快 |
| R:save:child:write | pickle与复制 | save:child:write | 1.5121 | 1.0165 | 1.4891 | 1.4851 | 1.4921 | Rust更快 |
| R:save:child:read | pickle与复制 | save:child:read | 1.3800 | 0.8619 | 1.5992 | 1.6086 | 1.5928 | Rust更快 |
| R:save:child:copy | pickle与复制 | save:child:copy | 0.7418 | 0.2050 | 3.6109 | 3.5952 | 3.6237 | Rust更快 |
| R:save:child:deepcopy | pickle与复制 | save:child:deepcopy | 4.8803 | 2.0916 | 2.3341 | 2.3324 | 2.3357 | Rust更快 |
| R:pydt:month:add | Pydt | pydt:month:add | 0.6055 | 0.6000 | 1.0056 | 1.0077 | 1.0037 | 接近 |
| R:pydt:month:sub | Pydt | pydt:month:sub | 0.6069 | 0.6005 | 1.0117 | 1.0113 | 1.0120 | 接近 |
| R:pydt:month:radd | Pydt | pydt:month:radd | 0.5852 | 0.5789 | 1.0119 | 1.0129 | 1.0085 | 接近 |
| R:pydt:absolute:add | Pydt | pydt:absolute:add | 0.5335 | 0.5247 | 1.0183 | 1.0198 | 1.0172 | 接近 |
| R:pydt:fold:add | Pydt | pydt:fold:add | 0.7187 | 0.7129 | 1.0071 | 1.0092 | 1.0039 | 接近 |
| R:pydt:empty:add | Pydt | pydt:empty:add | 0.0429 | 0.0395 | 1.0836 | 1.0812 | 1.0859 | Rust更快 |
| R:bulk:date-month-end:1024 | 批量 date/datetime | bulk:date-month-end:1024 | 20.3701 | 19.2441 | 1.0581 | 1.0579 | 1.0593 | Rust更快 |
| R:bulk:date-month-end:10000 | 批量 date/datetime | bulk:date-month-end:10000 | 189.1852 | 188.4006 | 0.9997 | 0.9993 | 1.0005 | 接近 |
| R:bulk:datetime-relative:1024 | 批量 date/datetime | bulk:datetime-relative:1024 | 21.8336 | 17.5102 | 1.2423 | 1.2362 | 1.2445 | Rust更快 |
| R:bulk:datetime-relative:10000 | 批量 date/datetime | bulk:datetime-relative:10000 | 200.5918 | 173.6505 | 1.1535 | 1.1483 | 1.1618 | Rust更快 |
| R:bulk:datetime-absolute:1024 | 批量 date/datetime | bulk:datetime-absolute:1024 | 20.2188 | 16.1878 | 1.2442 | 1.2417 | 1.2509 | Rust更快 |
| R:bulk:datetime-absolute:10000 | 批量 date/datetime | bulk:datetime-absolute:10000 | 188.8440 | 161.1070 | 1.1750 | 1.1743 | 1.1761 | Rust更快 |
| R:bulk:datetime-aware:1024 | 批量 date/datetime | bulk:datetime-aware:1024 | 21.8217 | 17.8892 | 1.2209 | 1.2195 | 1.2221 | Rust更快 |
| R:bulk:datetime-aware:10000 | 批量 date/datetime | bulk:datetime-aware:10000 | 201.5968 | 177.4016 | 1.1316 | 1.1270 | 1.1372 | Rust更快 |
| R:bulk:delta-relative:1024 | 批量 Delta | bulk:delta-relative:1024 | 20.2323 | 15.2872 | 1.3194 | 1.3194 | 1.3209 | Rust更快 |
| R:bulk:delta-relative:10000 | 批量 Delta | bulk:delta-relative:10000 | 186.0366 | 146.0885 | 1.2666 | 1.2633 | 1.2701 | Rust更快 |
| R:bulk:delta-absolute:1024 | 批量 Delta | bulk:delta-absolute:1024 | 19.9501 | 14.8229 | 1.3493 | 1.3291 | 1.3575 | Rust更快 |
| R:bulk:delta-absolute:10000 | 批量 Delta | bulk:delta-absolute:10000 | 184.7840 | 144.0039 | 1.2850 | 1.2961 | 1.2781 | Rust更快 |
| R:bulk:timedelta-positive:1024 | 批量 timedelta | bulk:timedelta-positive:1024 | 19.1673 | 16.4168 | 1.1739 | 1.1490 | 1.1853 | Rust更快 |
| R:bulk:timedelta-positive:10000 | 批量 timedelta | bulk:timedelta-positive:10000 | 175.9809 | 157.3914 | 1.1210 | 1.1250 | 1.1196 | Rust更快 |
| R:bulk:timedelta-negative:1024 | 批量 timedelta | bulk:timedelta-negative:1024 | 19.1366 | 17.4137 | 1.1001 | 1.0876 | 1.1169 | Rust更快 |
| R:bulk:timedelta-negative:10000 | 批量 timedelta | bulk:timedelta-negative:10000 | 175.8198 | 167.8896 | 1.0528 | 1.0491 | 1.0540 | Rust更快 |
| R:bulk:pydt-month:1024 | 批量 Pydt | bulk:pydt-month:1024 | 590.8021 | 571.6406 | 1.0321 | 1.0307 | 1.0345 | 接近 |
| R:bulk:pydt-month:10000 | 批量 Pydt | bulk:pydt-month:10000 | 5942.4166 | 5769.2866 | 1.0303 | 1.0287 | 1.0315 | 接近 |
| R:bulk:pydt-absolute:1024 | 批量 Pydt | bulk:pydt-absolute:1024 | 590.9575 | 572.7259 | 1.0329 | 1.0327 | 1.0333 | 接近 |
| R:bulk:pydt-absolute:10000 | 批量 Pydt | bulk:pydt-absolute:10000 | 5919.9271 | 5737.8072 | 1.0328 | 1.0322 | 1.0333 | 接近 |
| R:bulk:dateutil-relative:1024 | 批量 relativedelta | bulk:dateutil-relative:1024 | 1840.1979 | 1820.8202 | 1.0108 | 1.0124 | 1.0090 | 接近 |
| R:bulk:dateutil-relative:10000 | 批量 relativedelta | bulk:dateutil-relative:10000 | 17994.5105 | 17712.0625 | 1.0146 | 1.0176 | 1.0108 | 接近 |
| R:bulk:dateutil-absolute:1024 | 批量 relativedelta | bulk:dateutil-absolute:1024 | 1933.5234 | 1904.9713 | 1.0132 | 1.0147 | 1.0122 | 接近 |
| R:bulk:dateutil-absolute:10000 | 批量 relativedelta | bulk:dateutil-absolute:10000 | 18846.3955 | 18585.1355 | 1.0147 | 1.0152 | 1.0136 | 接近 |
| R:bulk:numpy-datetime:1024 | 批量 NumPy | bulk:numpy-datetime:1024 | 411.9729 | 26.5623 | 15.5162 | 15.5252 | 15.4641 | Rust更快 |
| R:bulk:numpy-datetime:10000 | 批量 NumPy | bulk:numpy-datetime:10000 | 4015.7870 | 258.9336 | 15.5240 | 15.5803 | 15.4234 | Rust更快 |
| R:bulk:numpy-timedelta:1024 | 批量 NumPy | bulk:numpy-timedelta:1024 | 412.7714 | 21.4899 | 19.2790 | 19.2709 | 19.2816 | Rust更快 |
| R:bulk:numpy-timedelta:10000 | 批量 NumPy | bulk:numpy-timedelta:10000 | 4043.8236 | 206.5244 | 19.5830 | 19.4939 | 19.7045 | Rust更快 |
| R:bulk:mixed:1024 | 批量混合 | bulk:mixed:1024 | 465.1245 | 331.7411 | 1.4019 | 1.4111 | 1.3951 | Rust更快 |
| R:bulk:mixed:10000 | 批量混合 | bulk:mixed:10000 | 4494.9375 | 3224.8751 | 1.3951 | 1.3995 | 1.3885 | Rust更快 |
| R:to-timedelta:positive | to_timedelta | to-timedelta:positive | 0.0429 | 0.0506 | 0.8460 | 0.8480 | 0.8452 | Cython更快 |
| R:to-timedelta:negative | to_timedelta | to-timedelta:negative | 0.0430 | 0.0507 | 0.8472 | 0.8477 | 0.8468 | Cython更快 |
| R:to-timedelta:month-leap | to_timedelta | to-timedelta:month-leap | 0.0784 | 0.0628 | 1.2411 | 1.2601 | 1.2389 | Rust更快 |
| R:to-timedelta:month-normal | to_timedelta | to-timedelta:month-normal | 0.0780 | 0.0615 | 1.2685 | 1.2792 | 1.2653 | Rust更快 |
| R:to-timedelta:absolute | to_timedelta | to-timedelta:absolute | 0.0817 | 0.0625 | 1.3210 | 1.3079 | 1.3410 | 不明确 |
| R:to-timedelta:aware | to_timedelta | to-timedelta:aware | 0.0812 | 0.0606 | 1.3409 | 1.3438 | 1.3376 | 不明确 |
| direct:repr-first-fresh | 表示：新对象/交替/子类 | repr-first-fresh | 0.1090 | 0.1239 | 0.8810 | 0.8683 | 0.8986 | Cython更快 |
| direct:repr-alternating | 表示：新对象/交替/子类 | repr-alternating | 0.0755 | 0.0519 | 1.4541 | 1.4586 | 1.4451 | Rust更快 |
| direct:repr-subclass | 表示：新对象/交替/子类 | repr-subclass | 0.0920 | 0.0912 | 1.0075 | 1.0062 | 1.0097 | 接近 |

[完整CSV和逐项证据位置](/Users/jef/ResilioSync/code/rsTimes/docs/Delta第五轮完整性能明细.csv)
