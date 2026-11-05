# Verify, publish and maintain these docs

The website tests **publicly released wheels**. It does not rebuild rsTimes,
create a product version/tag, update a GitHub Release or publish to PyPI.
Its source branch is `docs-pages`; documentation changes are reviewed through
pull requests to that branch.

## The source of each claim

The files in `documentation/_data` record the public release's file SHA256s,
the independent runtime/stub API inventory, entry-to-example mappings and
fixed execution profiles. `public-api.json` is independent of the coverage
table: removing a row from coverage must fail the inventory comparison.
The release binder checks pinned wheel ZIP bytes against the installed
package, including its native module, all stubs and complete package payload.

The page runner executes the actual MyST doctest blocks in fresh isolated
interpreters, with strict expected output and no skipped/ellipsis examples.
Reports bind the page/code and runner hashes, actual package identity,
Python/GIL state and tracked dependency presence/versions. No profile is
validated merely because its report has a matching label.

## Local review of one profile

Use ordinary Python 3.13 for this baseline slice. The following POSIX-shell
commands keep the example and HTML-build environments separate. On Windows,
use each virtual environment's `Scripts\python.exe` in place of `bin/python`.
Start with a wheel directory containing only the intended product download.

```shell
python -m venv .venv-doc-examples
python -m venv .venv-doc-build
.venv-doc-examples/bin/python -m pip install -r documentation/requirements/full.txt
.venv-doc-build/bin/python -m pip install -r requirements-docs.txt
.venv-doc-examples/bin/python -m pip download --only-binary=:all: --no-deps --dest .local/docs-wheels "rsTimes==0.2.0b3"
.venv-doc-examples/bin/python -I documentation/_tools/bind_release.py --wheel-dir .local/docs-wheels --check-wheel-only
.venv-doc-examples/bin/python -m pip install --no-deps .local/docs-wheels/*.whl
.venv-doc-examples/bin/python -I documentation/_tools/bind_release.py --wheel-dir .local/docs-wheels --output .local/docs-evidence/identity.json
.venv-doc-examples/bin/python -I documentation/_tools/extract_stubs.py --output documentation/_stubs
.venv-doc-examples/bin/python -I documentation/_tools/run_profile.py --profile full --evidence-dir .local/docs-evidence/full
.venv-doc-build/bin/sphinx-build -d documentation/_build/doctrees -b html -E -W --keep-going documentation documentation/_build/html
```

This is one review slice. The complete gate also requires the other declared
profiles, relevant ABI/platform runs, current API anchors and the complete
page/source-to-HTML integrity manifest. A successful HTML build or one profile
alone does not authorize publication.

## Complete CI and deployment

The English documentation workflow installs fixed profile requirements and a
SHA-checked public product wheel. It runs page examples, matches all public
entries and declared environments, builds HTML strictly and checks internal
links and artifact contents. Free-threaded jobs reuse the repository's fixed,
unmodified official Polars qualification dependency for internal tests; they
do not distribute that runtime with the website.

PR verification has read permissions. Deployment occurs only after the merged
`docs-pages` commit has passed its own verification. The deployment job grants
only the required Pages/OIDC permissions and publishes the already checked
artifact; it does not rebuild the product or website at the deployment step.
The existing product pipeline targets `main`; this separate documentation
branch and PR target keep those triggers unchanged. Non-documentation changes
are rejected by the docs gate.

After changing a page, run **all** its examples immediately and inspect values,
types, units, timezone, missingness, shape and necessary errors. Expr examples
must execute; constructing an Expr is insufficient. Then update its entry,
scenario and profile mapping. Finish with a full current-page rerun and the
complete CI gate. Re-run all jobs of an existing documentation run to repeat
verification of that commit.

## Release updates and rollback

For a newer **already published** rsTimes release, first bind its actual source,
public file checksums, installed native/payload/stubs and dependency profiles.
Regenerate the independent public inventory and review every changed behavior.
Update target/version metadata, API prose, guides and mappings together; rerun
the entire site on that actual release. Historical success from another
native module or version string is not a new result.

Keep exact-version URLs when adding a version, and move the root/latest entry
only to an actually verified published package. Retain prior validated version
directories when preparing a multi-version artifact. Check the new public
root, exact version, API anchors, assets, search, theme, keyboard/mobile use,
404 and public build metadata after deployment.

For a docs regression, revert the documentation change on its branch, run the
complete workflow and deploy the resulting checked artifact. A product tag,
Release or PyPI file is not part of that rollback. Preserve the failing run
and its evidence, and confirm the restored public site before calling the
rollback complete.

## Findings stay within rsTimes responsibility

Record meaningful rsTimes implementation, wrapper, validation, design or
documentation-tool problems when discovered. Include artifact identity,
minimal reproduction, expected/actual behavior, impact, status and evidence.
Keep a defect reproduction separate from a functional pass. Attribute the
actual provider and the rsTimes promise; do not turn pure provider problems
into a separate project or a catalog in these docs.
