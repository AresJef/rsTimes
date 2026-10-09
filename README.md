# rsTimes

`rsTimes` 0.1.0 是一个纯 Python 日期时间小工具，提供带时区 `datetime`
与 Unix 毫秒时间戳的双向转换。没有运行时依赖，要求 Python 3.10 或更新版本。
当前版本没有 Rust 内核，不承诺性能优势或与其他日期时间库兼容。

PyPI 分发名是 `rsTimes`，Python 导入名是 `rstimes`。

## 使用

首次成功发布到 PyPI 后可安装：

```sh
python -m pip install rsTimes
```

```python
from datetime import datetime, timedelta, timezone
from rstimes import from_unix_ms, to_unix_ms

local_epoch = datetime(1970, 1, 1, 8, tzinfo=timezone(timedelta(hours=8)))
assert to_unix_ms(local_epoch) == 0
assert from_unix_ms(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)

before_epoch = datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
assert to_unix_ms(before_epoch) == -1
assert from_unix_ms(-1).isoformat() == "1969-12-31T23:59:59.999000+00:00"
```

## 转换规则

- `to_unix_ms(value: datetime) -> int`：输入必须带有效 UTC 偏移，
  转换到 UTC 后用整数计算。微秒余数**向负无穷方向取整**：
  纪元后 999 微秒得到 `0`，纪元前 1 微秒得到 `-1`。
- `from_unix_ms(value: int) -> datetime`：只接受整数，拒绝 `bool`、
  浮点数、字符串等类型；返回 `timezone.utc` 的带时区时间。
- 毫秒范围为 `-62135596800000` 到 `253402300799999`，含两端，
  对应 UTC 年份 1–9999。超出范围或时区转换越界抛出 `ValueError`；
  naive datetime 也抛出 `ValueError`，非法输入类型抛出 `TypeError`。
- 不使用本机时区、不经过浮点时间戳。毫秒整数可以精确往返；
  datetime 的不足 1 毫秒部分在转换时会丢失。

## 本地开发与构建

以下命令适用于 macOS/Linux；Windows 可用 `.venv\Scripts\python`。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple -e ".[test]" build twine
.venv/bin/python -m pytest
.venv/bin/python -m build
.venv/bin/python -m twine check --strict dist/*

.venv/bin/python -m venv .wheel-test
.wheel-test/bin/python -m pip install --no-deps dist/*.whl
.wheel-test/bin/python -I -c 'from rstimes import from_unix_ms, to_unix_ms; assert to_unix_ms(from_unix_ms(-1)) == -1'
```

重新构建前清理旧的 `dist/` 内容，避免混入以前的发布文件。
CI 配置会在 GitHub 的 Ubuntu runner 上使用 Python 3.10 和 3.13 测试、构建、
检查元数据，并从 wheel 安装验证导入；这些配置不代表已在所有平台完成测试。

## 发布前需要填写的信息

维护者需要自行填写真实信息：

| 项目 | 当前状态 |
| --- | --- |
| GitHub owner | 待填写本人账号或组织名 |
| GitHub repository | 待填写实际仓库名 |
| 许可证 | [MIT](LICENSE)，Copyright (c) 2026 Jiefu Chen |
| 作者与项目 URL | 尚未填写；按实际情况补充，不使用虚构身份或链接 |

本项目采用 [MIT 许可证](LICENSE)，许可证文本随源码与分发包一同提供。

PyPI 将没有功能或空包的占名项目视为无效项目。本版本提供实际的时间转换功能，
README 和包描述应保持与实际功能一致。

## GitHub → PyPI Trusted Publisher

本地配置已经准备好，以下持久授权和发布操作由维护者完成：

1. 补齐需要的真实元数据；自行把这些文件提交并推送到自己的 GitHub
   仓库。CI 成功后再准备正式 release。
2. 在该 GitHub 仓库的 Settings → Environments 中创建名为 `pypi` 的 environment。
   如有需要，为它配置审批人和允许发布的 tag 规则。
3. 若 PyPI 尚无该项目，在自己的 PyPI 账号 Publishing 页面添加 **Pending Publisher**，
   选择 GitHub，准确填写下表。已有项目则在该项目的 Publishing 页面添加 publisher。

   | PyPI 字段 | 必须填写的值 |
   | --- | --- |
   | PyPI Project Name（pending 时） | `rsTimes` |
   | Owner | 实际 GitHub owner，须与仓库所属账号或组织一致 |
   | Repository name | 实际 GitHub 仓库名 |
   | Workflow name | `publish.yml`（文件名，不是 workflow 显示名称） |
   | Environment name | `pypi` |

   Pending Publisher 在首次成功上传前不会创建项目或预留包名；名称也可能已被占用
   或被 PyPI 保留。首次成功发布后 pending publisher 转为正式 publisher。
4. 当前 `pyproject.toml` 的版本为 `0.1.0`。在包含上述文件的 commit 上创建 tag
   `v0.1.0`，再发布对应的 GitHub Release。仅推送 tag 或保存 release 草稿不会触发上传。
5. `.github/workflows/publish.yml` 只响应 `release: published`，检查 tag 与包版本
   精确匹配（必须是 `v` 加版本号），随后测试、构建、检查 sdist/wheel 并验证 wheel。
   只有这些步骤全部成功才会进入发布 job。
6. 发布 job 使用 `environment: pypi`，仅该 job 有 `id-token: write`。
   它只下载本次运行的构建产物，使用 PyPA 官方 action 的 OIDC 身份发布，
   不需要设置 `PYPI_TOKEN` 或用户名/密码 secret。

PyPI 发布是公开且持久的；首次发布前检查 wheel/sdist 内容与真实元数据。
新版本请先修改 `pyproject.toml`，重新验证，再创建匹配的新 tag/release。
已经用过的版本和分发文件不能直接覆盖。

官方说明：

- [Python 项目打包](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [创建 Pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [通过 Trusted Publisher 发布](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [PyPI 名称政策](https://docs.pypi.org/project-management/name-retention/#invalid-projects)
