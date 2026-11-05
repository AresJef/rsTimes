# rsTimes maintainer release procedure — release candidate

This is the current operating procedure. Its b3 experience record is still
provisional: publication and remaining gates have not yet succeeded. The
maintainer will replace pending facts with actual receipts after completion.

## Authority and immutable inputs

Begin with the current `AGENTS.md`, the approved release plan and its single
ledger. Establish the version, support matrix, performance baseline, scope,
budget and authorization for commit, push, merge, tag and publication. A
previous release's authorization, exceptions or remaining budget do not carry
forward. The current release is an example, not a permanent version policy.

Keep the root checkout's existing branch, index and dirty work intact. Integrate
in an isolated checkout starting from the actual remote PR branch. Use explicit
file lists and source hashes; do not stage an entire historical working tree.
Preserve old environments, failed measurements and previous published files.

## 1. Verify accounts and version availability first

Use the authenticated GitHub connector or existing `gh` installation. Read back
the current account, repository permission, PR head/base, main, tag rules and
the `pypi` environment. Check the real PyPI project and its Trusted Publisher:
repository `AresJef/rsTimes`, workflow `publish.yml`, environment `pypi`.

Use the ChatGPT in-app browser for any account handoff. The owner performs
login, password confirmation and 2FA; never request or record credentials.
Verify the requested version is absent on PyPI and the tag is absent on GitHub.
An existing version with any conflicting file is a stop for that write, not a
reason to overwrite files or try a different version without authorization.

For this run the account checks and absent b3 version were completed in S01.
The user completed PyPI login; no publisher or account settings were changed.

## 2. Integrate the adopted source and prepare the beta metadata

Read the adoption manifests and compare every production input, relevant test,
type/tool file, resource and license. A matching version string is insufficient.
Separate a mechanical adopted-source commit from release-specific changes when
this makes the actual diff easier to review.

Update the Python and Cargo versions to equivalent ecosystem spellings, and
commit `docs/releases/<tag>.md`. Keep `Cargo.lock`; do not update transitive
dependencies merely to change the local crate version. Release notes describe
actual upgrade behavior, dependency conditions and explicitly deferred issues.
Run examples against an installed wheel. The release's README is package
metadata, so complete it before freezing the release source.

Freeze the README's stable maintainer-procedure link before the release tag.
The procedure itself can be explicitly provisional until this release's actual
experience is finalized. Its file is excluded from wheel/sdist payload; the
README is package metadata and must not be changed as a supposedly payload-free
post-publication follow-up.

This run uses Python `0.2.0b3`, Cargo `0.2.0-beta.3` and tag `v0.2.0b3`.
Mechanical synchronization preserved all 135 adopted production inputs; release
wiring did not change product algorithms. RV03–RV05 remain deferred.

## 3. PR validation and normal merge

`ci.yml` separates verification from publication:

- PRs to main run the approved eight-position `pilot` and Rust quality checks.
- Main product/build changes run `full`.
- Manual `pilot` or `full` verification never publishes.
- A tag push is the only publication trigger; there is no `release published`
  trigger and no manual publication bypass.

Run focused release-gate positive/negative tests, the pinned sole Pyright
checker, Actionlint, installed-package functional checks and a review of the
actual incremental changes. Preserve previous case IDs, outcomes and complete
skip reasons. An explicit source-root prefix normalization may remove only
checkout-location differences; it must not discard meaningful skip messages.

Update the PR's title/body to the final implementation and evidence, rather
than retaining provisional history. A same-repository PR must not set
`maintainer_can_modify=true`: GitHub reserves that option for cross-repository
fork collaboration. Wait for the actual pilot result, mark Ready, and normally
merge the expected exact head. Do not force-push main or use an admin bypass.

Batch small unrelated release-wiring edits when a valid cold pilot is already
running. This run kept the initial pilot alive while a publisher-only commit
was prepared locally, so dependency qualification/cache completion was not
cancelled unnecessarily. The final PR head still receives its own applicable
validation. A demonstrated correctness blocker takes priority; this is a cost
judgment, not a requirement to keep a useless failing run alive.

## 4. Freeze main and run the full matrix once

Record the merge source commit and tree. The complete matrix is defined by
`.github/native-matrix.json` and `release_matrix()`, not by a hand-copied table.
The current approved matrix is eight 64-bit platforms × six ordinary/t ABI
roles: 32 ordinary plus 16 t wheels, and one canonical sdist.

Full CI installs the actual produced wheel in isolated environments. It checks
the selected NumPy/pandas/Polars profiles, core-only and Polars-only roles,
typing, stubs, examples, runtime behavior, three independent representative
sdist rebuilds and two isolated frozen-oracle environments. Source-tree test
success is not an installation test. The exact final run/attempt must satisfy
`release_candidate.validate_ci`; pilot or branch-only CI cannot qualify.

Record bootstrap and target interpreters separately. Desktop jobs use their
explicit setup-python patch version; Linux wheel building/testing uses the
interpreter inside the frozen container digest. For example, this run's first
Linux ARM64 pilot used host bootstrap 3.13.17 and actual container target
3.13.18. The ABI role is cp313 in both cases. Use `verification.json` for the
actual tested target; do not copy the host patch into the target evidence or
claim tests on every patch release.

On t interpreters, verify the real ABI and GIL state before and after real work.
Do not force the GIL off to conceal a dependency import that re-enables it.
The fixed unmodified official Polars runtime is an internal test dependency,
not a distributable rsTimes asset or a promise that upstream publishes a t
wheel for every platform. Its cache key binds actual upstream build inputs.
The shared internal-runtime action may build that dependency on a cold cache;
publication and public revalidation never rebuild rsTimes distribution files.

Do not assume a PR's cold runtime cache will accelerate the first main build:
GitHub scopes PR-created caches to the PR merge ref. Main's subsequently created
cache can be available to tag verification under GitHub's normal branch access
rules. Record actual hits/misses rather than inferring them from identical keys.
See [GitHub's cache access restrictions](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#restrictions-for-accessing-a-cache).

Save run/job metadata, failure logs, installation receipts and XML while
artifacts are available. A new source/native requires its own applicable
evidence. Re-run a failed job only when its fixed source and retained artifacts
are still valid; never assemble an apparently complete bundle from unrelated
commits or CI attempts.

## 5. Seal and measure the actual CI bundle

Download the full run's `release-distributions-<run>-<attempt>` bundle. Keep
the original archive, manifest, SHA256SUMS and all 49 distribution files in a
sealed directory. Independently verify every file and native hash, source
identity, supported tag, package resource, stub, `py.typed` and license.
Install the six actual macOS ARM64 wheels in fresh local views and read back
their native paths and loaded identities from outside the source checkout.

If local validation reuses relocated official macOS Python frameworks, first
check the real framework, OpenSSL library and trusted-CA paths. This run's
controlled t verifier needed the unmodified installer's OpenSSL libraries via
a task-local `DYLD_LIBRARY_PATH`, plus the working host's existing trusted
`SSL_CERT_FILE`; merely locating PythonT.framework did not make SSL available.
Do not guess a pip module exists in a pip-less analysis environment. Retain the
diagnostic and environment receipt. Do not patch interpreter binaries, disable
TLS verification or force GIL state; normal hosted setup-python installations
are a separate environment. These are developer-validation settings, not new
rsTimes runtime requirements.

The versioned `.github/release-performance-contract.json` fixes the necessary
case/ABI set and baseline identities. For b3 that is 94 comparisons against
the adopted R18 final01, each with 216 complete pairs and 36 real workers,
two rounds, 3% measurement precision, 5% stability and per-item 5% protection.
This contract protects the current adopted implementation; it does not require
a release-only metadata change to produce new speedups.

Reuse existing collectors and the same complete public expressions. Prepare
controls and a fixed readiness pilot on the new actual artifacts, forecast
remaining cost, and freeze settings before formal samples. Keep every negative
result and use whole-item replacement, not favorable sample selection. Bound
quality-adjustment attempts and record any currently authorized tradeoff; do
not inherit an earlier artifact's exception or write INC/FAIL as strict PASS.

Recompute selected raw controls, group/order statistics, clock/quality checks,
worker identities, provenance and quotas independently. A receipt's digest
does not itself prove its contents. Retain a raw-file hash list and the actual
raw-audit output, then generate the complete v2 performance receipt.

## 6. Certify and push the annotated tag once

Only after all current necessary gates pass, create the annotated tag at the
frozen main source. Its JSON envelope uses `rstimes-verified-release-v1` and
binds the exact source/version, successful full CI run and attempt, original
manifest SHA256, and complete `rstimes-performance-completion-v2` receipt and
canonical digest. Validate locally using the same source-frozen gate functions
before pushing the tag. Save the actual annotated tag object and read it back
remotely. Use an authenticated maintainer channel that really emits the tag
push event; the workflow's ordinary GITHUB_TOKEN does not generally recurse
into a second push-triggered workflow.

Do not move a published tag, recreate binaries or overwrite an existing
release. Retain b1/b2 and historical evidence unless a separate explicit
cleanup instruction applies to those exact versions.

## 7. GitHub Release, then the same files to PyPI

`publish.yml` resolves the tag and the original qualified CI bundle without
compilation. It validates source, full CI, matrix, artifacts and performance
receipt, then uploads the unchanged bundle to workflow storage. The next job
creates/verifies GitHub Release with `docs/releases/<tag>.md` as its body and
uploads the original 49 files plus the three provenance assets. Only after
GitHub succeeds does the `pypi` environment job obtain GitHub OIDC identity
and publish those same files to PyPI. No long-lived PyPI token is used.

The PyPI identity is configured for this repository/workflow/environment.
Account login and environment configuration do not prove OIDC upload success;
save the actual publishing job and platform readbacks. In an already authorized
release there is no second artificial approval inserted after the tag.

## 8. Public installation is a distinct completion gate

Every approved matrix position downloads the exact public PyPI version and
verifies its filename/SHA/native against the original manifest. Ordinary and t
roles have distinct job labels, artifacts, interpreter ABI paths and flags.
Linux runs in its matching libc container, with metadata dependencies installed
inside that container's actual target interpreter. A host installation does
not install tooling into a container.

The existing verifier installs the downloaded wheel in isolated environments,
reads actual package/native locations and runs the approved public functional
subset, dependency-role and NoGIL checks. Public checks are not described as a
second full functional suite; full installed-wheel CI is the earlier evidence
for those same exact files. Independently download/check the public sdist too.

## 9. Recovery after partial publication

Classify what actually completed: CI, GitHub assets, PyPI files, or public
installation. First read remote state and hashes; a failed local readback does
not prove a failed remote write. Save the original error before recovery.

- If a CI/build/required test fails, do not tag. Fix the actual issue and obtain
  the evidence required for the resulting source/artifacts.
- If GitHub succeeds but PyPI fails, retain the tag and original bundle. The
  existing publisher checks every present file's exact SHA before `skip-existing`
  may fill missing files. Do not republish changed files under the same version.
- If upload succeeds but installation verification fails, repair only the
  validation wiring when that is the demonstrated cause. Use read-only
  `verify-published.yml` with the original tag; it downloads original release
  metadata/files and does not upload or rebuild rsTimes.
- If a real published product defect is found, withhold a completion claim and
  report its affected scope. Yank/delete/new-version actions require their
  appropriate explicit decision; a validation repair cannot mask a product bug.

Record the main run and any retries/recovery independently. Do not claim one
clean full workflow if completion required a recovery run. An alternative
recovery route that has not actually been executed remains unverified.

## 10. Final local synchronization, procedure and timing report

Use the public verified install identity for the four demo runtime selections.
Keep the oracle-only environment separate; Babel/cytimes are not product
dependencies. Run all four demos from the repository and another directory.
Synchronize approved source/docs locally without overwriting unrelated dirty
work, changing the root branch or staging its existing index.

Finalize this document only after replacing pending facts with actual records.
Add the concise reference to AGENTS; the README link was frozen before the tag.
Post-publication procedure,
runtime selection and adoption records are a separately identified docs-only
follow-up commit; they do not alter the immutable release tag or public wheels.
If a change affects product/package payload, do not call it docs-only.

Report actual clean successful timings by platform and ABI, cache state and
major step, plus platform parallel wall times, summed job minutes, full CI wall
time, publishing/public-verification wall time and total effective release
time. These are different measures. Separate failed/debug/recovery runs, and
do not repeat an entire valid matrix just to manufacture an attractive timing.

Completion is reported separately as configuration, actual Actions success,
GitHub publication, PyPI publication and public-package installation success.
Save the final report, completion audit, raw identities and budget settlement.

## This run's observed records — incomplete until finalization

| Stage | Actual evidence | State |
|---|---|---|
| Account, publisher, absent version | S01 readbacks | Verified |
| Adopted baseline integration | dd1c1b4; 135 input hashes | Verified |
| Release wiring and metadata | 00042d4 | Verified locally |
| Local installed examples, functionality and gates | S04 | Passed; not remote final evidence |
| PR representative CI | 41969566935, attempt1 | Passed, eight positions; publisher follow-up awaits current-head validation |
| Main/full CI and sealed artifacts | S06/S07 | Pending |
| Exact final artifact measurements | S08/S09 | Pending |
| Tag / GitHub / PyPI | S10 | Pending |
| Public 48-position install checks | S11 | Pending |
| Final procedure/demos/timing settlement | S12 | Pending |
