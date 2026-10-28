# rsTimes

**rsTimes 0.2.0b1** 是使用 Rust 内核的 Python 日期时间库，提供日历增量、可配置解析、标准 `datetime` 子类和 pandas 日期索引子类。

- **`Delta`**：相对日历增量、绝对字段设置、日期运算和批量应用。
- **`parse_str` / `parse` / `parse_to_epoch`**：共享 Rust 解析内核，分别输出日期对象或指定单位的纪元整数。
- **`Configs`**：配置解析词表、顺序规则、固定偏移和地区时区。
- **`Pydt`**：真正继承 `datetime.datetime`，提供日历、边界、时区和格式操作。
- **`Pddt`**：真正继承 `pandas.DatetimeIndex`，支持纳秒、明确单位、整列运算和 pandas 索引协议。

PyPI 分发名为 `rsTimes`，Python 导入名为 `rstimes`。PLDT 尚未实现；Polars 可选依赖用于读取受支持的 Series 输入。

## 安装

这是 beta 发行，请明确选择版本：

```sh
python -m pip install "rsTimes==0.2.0b1"
# 需要 Pddt 时安装 pandas；需要 Polars Series 输入时增加 polars：
python -m pip install "rsTimes[pandas,polars]==0.2.0b1"
```

基础依赖为 NumPy、python-dateutil；Windows 另外安装 tzdata，以提供标准 ZoneInfo 的 IANA 时区数据。pandas 和 Polars 为可选依赖。运行库不依赖 Babel、cytimes 或 Cython。

## 使用

```python
from datetime import datetime
from rstimes import Configs, Delta, Pydt, parse, parse_str, parse_to_epoch

assert datetime(2024, 1, 31) + Delta(months=1) == datetime(2024, 2, 29)
assert Pydt(2024, 1, 31).add(months=1) == datetime(2024, 2, 29)
assert parse(datetime(2024, 5, 7)) == datetime(2024, 5, 7)
assert parse_str("2024-01-02T12:34+08:00", ignoretz=False).isoformat() == "2024-01-02T12:34:00+08:00"
assert parse_to_epoch(1e-9, unit="ns") == 1

cfg = Configs()
cfg.add_month("custommonth", 2)
assert parse_str("29 custommonth 2024", cfg=cfg) == datetime(2024, 2, 29)
```

Pddt 使用集合输入，构造时通过 `unit` 选择单位，已有对象通过 `as_unit()` 显式转换：

```python
from rstimes import Delta, Pddt, parse_to_epoch

x = Pddt(["2024-01-31T12:30:00.123456789", None], unit="ns", name="events")
y = x + Delta(months=1)
assert y[0].isoformat() == "2024-02-29T12:30:00.123456789"
assert y.isna().tolist() == [False, True]

# Pddt 的裸数字表示所选单位的刻度；parse_to_epoch 的数字输入表示秒。
assert Pddt([1], unit="ms").asi8.tolist() == [1]
assert parse_to_epoch(1, unit="ms") == 1000
```

默认解析顺序为 `yearfirst=True, dayfirst=False`，可由 Configs 或显式参数调整。`strict=False`；`isoformat=True` 表示优先尝试 ISO，仍可回退通用解析。默认 `ignoretz=True`，需要保留文本时区时明确传 `False`。Parser 负责解释字段，目标日期类决定可表示范围和地区时间存在性。

Pydt 保持微秒精度及年份1—9999；Pddt 支持 `s/ms/us/ns` 和相应容量内的零年、负年及宽年份。已有 Pddt 日期运算保持当前单位，精度或容量不足时明确报错，需用户调用 `as_unit()`；不会自动换单位或把失败变成 NaT。可选数字修改参数的 `None` 表示保留，零为真实数值。

原有 `to_unix_ms` / `from_unix_ms` 继续提供带时区日期与 Unix 毫秒的转换。前者将不足一毫秒部分向负无穷取整；后者返回 UTC-aware datetime。类型错误为 TypeError、naive 输入为 ValueError、容量超限为 OverflowError。

## 发行矩阵与测试

同一套源码构建普通带GIL的 CPython 3.12—3.15：

| 平台 | CPU | 构建/测试 runner | wheel |
|---|---|---|---|
| macOS | arm64 | macos-15 | 每个 Python 版本1个 |
| macOS | x86_64 | macos-15-intel | 每个 Python 版本1个 |
| Windows | x86_64 | windows-2025 | 每个 Python 版本1个 |
| Linux | x86_64 | ubuntu-24.04，固定 manylinux_2_28 构建容器 | 每个 Python 版本1个 |

总计16个wheel和1个sdist。macOS wheel 的部署目标为11.0；Linux wheel 为 manylinux_2_28。表中列的是实际验收 runner，不代表已在每个历史操作系统版本物理测试。此次不包含 PyPy、free-threaded CPython、musl 或 Windows/Linux ARM。

产品测试固定 pandas3.0.6、NumPy2.5.3、Polars2.0.0。冻结官方 cyTimes3.1.0 声明 pandas<3，放在独立 pandas2.3.3 环境运行原对照测试；它不进入用户运行依赖。完整保留的字符串样本另有4,588项独立冻结预期，可在所有四个Python版本检查。普通云runner不用于发布正式性能倍率。

## 本地开发

需要 Rust；仓库的 `rust-toolchain.toml` 固定本次验证工具链。以下命令在已激活的虚拟环境执行：

```sh
python -m pip install --upgrade pip==26.2.2
python -m pip install -r requirements-dev.txt
maturin build --release --locked --interpreter python --out dist
python -m pip install --no-deps dist/*.whl
python -I -B tools/wheel_smoke.py --expect-version 0.2.0b1 --with-pandas --with-polars
python -I -B tools/run_release_tests.py --junitxml evidence/tests.xml
python -I -B tools/check_public_docs.py
python -I -B tools/check_typing.py
```

Windows PowerShell 可用 `Get-ChildItem dist\*.whl | ForEach-Object { python -m pip install --no-deps $_.FullName }` 安装生成的wheel。源码目录导入不能替代真实wheel安装验证。切换源码后请使用独立输出目录，避免混入旧版发行文件。

## 对照 demo

四个 `demo/*.py` 用独立环境比较冻结官方版本，不是运行库依赖或正式性能验收。先创建 `demo/runtime.json` 指定的环境，在其中安装 `requirements-oracle.txt` 和已发布的 `rsTimes==0.2.0b1`，并从本次 GitHub Release 下载 `release-manifest.json` 到该文件指定的位置。启动器核对版本、加载位置和清单中的 native SHA256，不会静默使用旧包或临时编译。随后可从任意目录执行四个 demo；不要把官方 cyTimes 强装进 pandas3 环境。

## 自动发行

- `ci.yml` 在普通分支提交、PR和手动运行时构建并测试，均无发布权限。
- `publish.yml` **只由 `v*` tag push触发**，检查 Python版本、Rust同义版本、源码提交和 `docs/releases/<tag>.md`。
- 全部构建和测试通过后，创建 GitHub Release，再以 PyPI Trusted Publishing/OIDC 上传同一批已测文件。发布job不重新编译。
- 发布完成后，16个组合从PyPI下载指定版本，比对原SHA256，在干净环境安装并验证核心功能。
- GitHub owner/repository为 `AresJef/rsTimes`，PyPI Publisher绑定 `publish.yml` 和 `pypi` environment，不使用长期PyPI token。

发行部分失败时保留tag及原产物。PyPI步骤失败可在核对既有文件后重跑失败job，使用原成功构建的bundle；GitHub文件仅补齐缺项，不覆盖已有资产。构建矩阵失败时修复原因后运行完整验证，避免把不同尝试的残缺矩阵混为一次通过。不要移动已发布tag或覆盖已发行文件。

## 文档与许可

- [Delta API](https://github.com/AresJef/rsTimes/blob/main/docs/DeltaAPI.md)、[Delta使用说明](https://github.com/AresJef/rsTimes/blob/main/docs/Delta使用说明.md)
- [Parser使用说明](https://github.com/AresJef/rsTimes/blob/main/docs/Parser使用说明.md)、[对象解析](https://github.com/AresJef/rsTimes/blob/main/docs/Parser对象解析使用说明.md)
- [Pydt使用说明](https://github.com/AresJef/rsTimes/blob/main/docs/Pydt使用说明.md)、[Pddt与纪元解析](https://github.com/AresJef/rsTimes/blob/main/docs/Pddt与parse_epoch使用说明.md)
- [错误处理](https://github.com/AresJef/rsTimes/blob/main/docs/错误处理使用说明.md)、[本次发行说明](https://github.com/AresJef/rsTimes/blob/main/docs/releases/v0.2.0b1.md)

公开类型声明和 `py.typed` 随wheel分发，编辑器可显示参数、返回类型、docstring和示例。本项目采用 [MIT](LICENSE)；第三方许可说明包含在源码包和wheel中。
