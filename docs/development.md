# 开发与本机核验

当前正式基线为 rsTimes 1.1.0。[1.1.0 实物清单](releases/1.1.0/records/release-manifest.json) · [性能回执](releases/1.1.0/records/performance-receipt.json)。使用当前源码开发。复核正式发行时，在独立目录检出对应 tag，并从源码目录外检查实际安装的 wheel。[发行流程](RELEASING.md) · [发行说明](releases/v1.1.0.md)

## 本机构建

使用仓库指定的 Rust 工具链和匹配目标 ABI 的 Python。在隔离环境安装开发依赖，从项目根构建。

```sh
python -m pip install -r requirements-dev.txt
python -m maturin build --release --locked --out dist
```

将对应 wheel 安装到验证环境，再用该环境执行 `python -I -B /path/to/rsTimes/tools/run_release_tests.py --junitxml product-tests.xml`。启用自由线程时使用匹配的上游运行时，并在实际运算后核对 GIL 状态。[自由线程说明](free-threaded-python.md) · [类型指南](type-checking.md)

## 可选依赖版本提示

首次请求 `Pddt` 或 `Pldt` 时，如果对应的 pandas 或 Polars 版本低于当前环境的下限，rsTimes 会发出 `rstimes.errors.DependencyWarning`，默认继续加载。安装对应的 `rsTimes[pandas]` 或 `rsTimes[polars]` 可让安装器选择合适的依赖。应用可通过 Python 的 `warnings.filterwarnings` 按此类别过滤。

## 性能证据

发行测量使用 CI 封存的实际发行 wheel 和正式 1.0.0 的对应 macOS ARM64 wheel。六个 ABI 的对照指纹、105 项比较及必要门槛在[冻结合同](../.github/release-performance-contract.json)中登记。保留各次完整调用的原始配对记录、安装身份、校准、严格判定和独立复算回执。

## Demo 与还原

按 [demo 安装说明](../demo/README.md) 建立普通 CP313 环境并从项目内外运行示例。对照环境中的 CyTimes 和 Babel 用于示例对比。重现旧版本时，使用 `v1.0.0` 的选择器和相应公开 wheel。
