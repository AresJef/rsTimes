# Verify, publish and maintain these docs

Use an independent checkout on a documentation branch based on
`docs-pages`. Document the installed public wheel whose package
bytes, native module, declarations and released source are pinned
in `documentation/_data`.

## The source of each claim

Use the published declarations for signatures and an independently
calculated expectation for example results. Add a plain Python snippet
that imports what it uses, followed by its expected output.
Register it in `_data/examples.json` with its applicable public
entries, scenarios and runtime profiles. Put extra behavior checks
in the associated `_checks` file or the case's typed assertions.
Check value, return type, unit, timezone and missing positions.
For Expr, actually execute eager `select` and lazy `collect`.
Check generated reference prose for the actual receiver and its
options. Website-specific wording corrections belong in the
documentation generator, with the published signatures and
wheel bytes as the release reference.

The page runner compares the standalone code and output with
execution in a fresh interpreter. A build checks the rendered code
and output against the same source. Evidence captures the page,
code and verifier hashes, installed native bytes and dependencies.
Run every applicable example when you finish editing the page.

## Run a page against an installed wheel

Prepare an example environment that matches a declared profile
and a build environment with `requirements-docs.txt`. The
following commands use Python 3.13 and the full profile in a
POSIX shell. Run them at the documentation checkout root.

```shell
python -m venv .local/doc-examples
python -m venv .local/doc-build
.local/doc-examples/bin/python -m pip install -r documentation/requirements/full.txt
.local/doc-build/bin/python -m pip install -r requirements-docs.txt
.local/doc-examples/bin/python -m pip download --only-binary=:all: --no-deps --dest .local/doc-wheels rsTimes==1.0.0
.local/doc-examples/bin/python -I documentation/_tools/bind_release.py --wheel-dir .local/doc-wheels --check-wheel-only
.local/doc-examples/bin/python -m pip install --no-deps .local/doc-wheels/*.whl
.local/doc-examples/bin/python -I documentation/_tools/bind_release.py --wheel-dir .local/doc-wheels --output .local/doc-proof/identity.json
.local/doc-examples/bin/python -I documentation/_tools/extract_stubs.py --output documentation/_stubs
.local/doc-examples/bin/python -I documentation/_tools/verify_examples.py guides/parsing.md --profile full --evidence-dir .local/doc-proof/full
.local/doc-build/bin/sphinx-build -d .local/doc-doctrees -b html -E -W --keep-going documentation .local/doc-html
```

Keep one product wheel in the download directory. On Windows, use
the virtual environment's `Scripts\python.exe` and the appropriate
Windows profile. Replace `guides/parsing.md` with your changed
page. Run `_tools/run_profile.py --profile full` for a complete
single-profile pass, supplying the evidence directory.

## Complete CI and deployment

Open the pull request against `docs-pages`. The English
documentation workflow installs the pinned public wheel, verifies
its identity, runs the profiles and checks the generated API
reference and example HTML. The merged branch runs the complete
gate again for its own commit, then publishes the checked GitHub
Pages artifact.

Inspect the workflow and deployed commit in the
[verification receipts](verification.md). Verify the public root,
exact version, representative examples, reference anchors,
search, keyboard navigation and unknown-page 404.

## Update the release or restore an earlier site

For a newer published rsTimes release, verify its source commit,
wheel hashes, payload, stubs and runtime projections. Review
every changed public entry and result. Keep the release lock,
coverage, verified code and navigation in sync. Re-run all
applicable profiles on the new wheel before changing root/latest.

Preserve the outgoing version artifact when first publishing its
successor. If old prose is retired, map known page paths, API
fragments and search URLs to supported destinations. Retain the
historical machine receipts with their original product identity.

For a site regression, revert the documentation change on
`docs-pages` and deploy its checked artifact. Verify the restored
public root, deep links and metadata. Preserve the failed and
restored workflow evidence for investigation.

## Record actionable rsTimes findings

Record meaningful issues with the rsTimes API, implementation,
error, wrapper or documentation tools as you find them. Include the
installed artifact identity, minimal reproduction, expected and
observed behavior, user impact, and evidence. Confirm which code
supplied the behavior before attributing it to rsTimes.
