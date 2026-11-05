# Work on rsTimes source without confusing it with an installed wheel

Use an isolated checkout and environment. The public wrapper code and stubs
are in `src/rstimes`; native implementation lives in `rust`. An imported
package from another environment is not evidence that the current checkout
was built or tested. Record the source commit, actual wheel/native identity,
import location and dependency profile when comparing behavior.

For the b3 source, `rust-toolchain.toml` pins Rust 1.99.0 and the build backend
pins maturin 1.15.0. The repository's product-development requirements are
separate from the documentation build requirements.

## Product-development checks

The following are source-development commands used by the release workflow,
not steps performed by the documentation deployment. Run them in an activated
development environment with the pinned Rust toolchain available. Use a fresh
output directory after changing source, and install the wheel you actually
built before running installed-package checks.

```shell
python -m pip install -r requirements-dev.txt
maturin build --release --locked --interpreter python --out dist
python -m pip install --no-deps dist/*.whl
python -I -B tools/wheel_smoke.py --expect-version 0.2.0b3 --with-dateutil --with-pandas --with-polars
python -I -B tools/run_release_tests.py --junitxml evidence/tests.xml
python -I -B tools/check_public_docs.py
```

The wildcard install shown is for a POSIX shell and a directory containing
only the intended wheel. On PowerShell, the source README uses
`Get-ChildItem dist\*.whl | ForEach-Object { python -m pip install --no-deps $_.FullName }`.
These commands are backed by the b3 exact-source release qualification; a
documentation-only edit does not require rebuilding the product matrix.

The native checks are:

```shell
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked --lib
cargo test --release --locked --lib
```

## Types and independent environments

Pyright 1.1.414 is the sole Python checker. The pinned Node version is 26.7.0;
`tools/typing/package-lock.json` and `requirements-typing.txt` define its
separate analysis environment. Follow the
[b3 type-checking instructions](https://github.com/AresJef/rsTimes/blob/v0.2.0b3/docs/type-checking.md)
for the installed-stub, implementation and deliberate rejection fixtures.
Node/Pyright are development tools, not runtime dependencies. Do not weaken
public types or introduce broad Any/ignore rules to make a check appear green.

The ordinary product profile does not include Babel/cytimes. Official
comparison demos use their separate oracle environment; do not force the old
comparison package's dependency constraints into a pandas 3 product environment.
See the [source demo guide](https://github.com/AresJef/rsTimes/blob/v0.2.0b3/demo/README.md)
for verified launcher and environment selection.

## Make a behavior change reviewable

Reproduce an rsTimes issue against a specific installed artifact. Establish an
expected answer independently of the implementation. Check date values and
return types, unit/timezone/validity, shape, copy or callback responsibilities,
and the required exception. An expression must actually execute. Keep genuine
old correct cases and explain deliberate changes rather than deleting tests
that expose a regression.

Attribute the behavior to its actual provider and the rsTimes contract.
Inherited visibility alone does not make a provider issue an rsTimes defect;
rsTimes remains responsible for its own wrappers, conversions, validation and
extra promises. Preserve this boundary when reporting findings.

For changes to this website, use the separate
[documentation workflow](documentation.md). It installs already published
packages and has no product tag, GitHub Release or PyPI publication step.
