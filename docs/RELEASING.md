# rsTimes release procedure

This is the maintainer procedure validated while publishing rsTimes 0.2.0b3.
Its observed records are evidence for that release, not reusable authorization
or acceptance for another artifact.

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

An explicitly approved execution-order adjustment may overlap local work on
individually qualified, immutable CI files with the tail of the same full run.
Keep that partial qualification separate. Final certification still requires
all full-CI jobs and the original complete bundle, then byte equality of every
early-used file, native and Python payload. A partial six-wheel manifest must
remain incapable of passing the full release gate. If any relevant input or
artifact changes, invalidate its local qualification and measurements. Do not
run heavy archive capture/extraction alongside timed batches. This run's DE03
used that bounded overlap; it is not authorization for an unrelated future run.

Count actual installation roles from receipts rather than multiplying platform
counts by an assumed fixed number of profiles. Full CI has three to five
profiles depending on ABI/platform, whereas the pilot is deliberately smaller.
This run has 181 native-job install receipts plus three sdist receipts, 184 in
total, and 13 separate local installation roles. Preserve any previous counting
error and its correction rather than rewriting original evidence.

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
Post-publication procedure, runtime selection and adoption records use a
separately identified normal follow-up PR and merge. A necessary test-control
repair is identified as verification maintenance and receives its own checks;
it is not called docs-only. Neither kind changes the immutable release tag or
public wheels. Do not push directly to the default branch as a shortcut.
If a change affects product/package payload, do not call it docs-only.

Report actual clean successful timings by platform and ABI, cache state and
major step, plus platform parallel wall times, summed job minutes, full CI wall
time, publishing/public-verification wall time and total effective release
time. These are different measures. Separate failed/debug/recovery runs, and
do not repeat an entire valid matrix just to manufacture an attractive timing.

Completion is reported separately as configuration, actual Actions success,
GitHub publication, PyPI publication and public-package installation success.
Save the final report, completion audit, raw identities and budget settlement.

## This run's verified release records

| Stage | Actual evidence | State |
|---|---|---|
| Account, publisher, absent version | S01 readbacks | Verified |
| Adopted baseline integration | dd1c1b4; 135 input hashes | Verified |
| Release wiring and metadata | 00042d4 | Verified locally |
| Local installed examples, functionality and gates | S04 | Passed; not remote final evidence |
| PR representative CI | 41969566935 and current-head41978594378, attempt1 | Passed, eight positions each; original artifacts and full case inventories read back |
| Normal merge / main source | PR1, dc878ef53f531f09c3bfe22348850bf9f163c7ee | Merged and remotely read back; root HEAD/index preserved |
| Main/full CI and sealed artifacts | CI41982305161 attempt1, S06/S07 | All56 jobs passed; 104 original archives,48 wheels/1sdist,184 install receipts/186 XML lanes independently read back; three fresh-target rebuilds passed |
| Exact final artifact measurements | S08/S09 | All94 strictPASS;20304 complete pairs/648 distinct actual workerPIDs; all41540 raw formal members and1692 selected controls independently replayed; no exceptions |
| Tag / GitHub / PyPI | S10 | Annotatedv0.2.0b3 object57c9590fe163065bdfc93f7981400a67806fd80f; GitHub52 assets actualdownload/SHAequal; PyPI49 files/SHAequal, OIDC upload succeeded |
| Public 48-position install checks | S11 | Original47 positions plus one unchanged macIntel315t recovery passed;144 smoke/144 XML independently checked; original failure retained |
| Procedure, demos and timing | S12 | This runbook and original timing receipts; root/other-directory8 demos passed, Delta150 scenarios/0unknown differences; follow-up PR/CI recorded in the release ledger |

## Command reference for the next approved release

Run these from the isolated integration checkout. Use the authenticated `gh`
executable already verified for the task; a non-PATH installation should use
its recorded absolute path. Values below are explicit task variables, not
instructions to reuse b3's source, budget, evidence or authorization.

Read-only account and source checks:

```bash
git status --short
git remote -v
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
gh auth status
gh api repos/AresJef/rsTimes
gh pr view "$release_pr" --repo AresJef/rsTimes \
  --json number,state,isDraft,headRefOid,baseRefOid,mergeable,statusCheckRollup
gh api repos/AresJef/rsTimes/environments/pypi
python tools/distribution_manifest.py --print-matrix full
```

The PyPI project/Trusted Publisher and any required owner login are separate
from GitHub CLI authentication. The exact version must also be absent from
PyPI and the proposed tag absent remotely before any new tag is created.
Do not save output containing credential material.

Useful existing local gates, with the task's qualified Python/Node environment:

```bash
python -I -B -m pytest tests/test_release_candidate.py tests/test_release_b3_gate.py
python -I -B tools/check_typing.py --full --python-version 3.12 \
  --evidence-dir "$typing_evidence"
python -I -B tools/check_public_docs.py --evidence-dir "$docs_evidence"
```

The b3-specific test remains a historical regression. A future contract needs
its own current positive/negative inputs rather than editing it to accept an
old receipt. The existing CI also checks the approved 3.14 and 3.15 language
views. Use the pinned Actionlint binary for all changed workflow files.

After applicable PR checks and review, use normal merge with an exact expected
head. For example, `gh pr ready` and `gh pr merge --merge --match-head-commit`
provide the CLI equivalents of the connector actions. Do not use `--admin`.
Read back main and follow its automatically triggered CI instead of dispatching
a duplicate full build:

```bash
gh run list --repo AresJef/rsTimes --workflow ci.yml \
  --commit "$release_source" --json databaseId,event,headSha,headBranch,status,conclusion
gh run view "$release_ci" --repo AresJef/rsTimes \
  --json jobs,createdAt,startedTime,updatedAt,conclusion,headSha
gh run download "$release_ci" --repo AresJef/rsTimes \
  --name "release-distributions-${release_ci}-${release_attempt}" \
  --dir "$sealed_directory"
```

Retain the original artifact ZIPs and complete paginated run/job metadata too;
the extracted files alone omit their original container provenance. Keep
different attempts and partial captures separate. The task's existing capture
helper uses the artifact API to retain original ZIP bytes and original logs.

Use `distribution_manifest.py` to recheck the actual downloaded bundle against
the frozen source. Pass the approved matrix count from `release_matrix()` to
`--wheels`, plus `--sdists 1 --complete`. Do not place checksum/receipt files in
the `dist/` directory: that directory must contain distributions only. Keep the
CI's original manifest and checksums; write the independent recheck elsewhere.

`verify_wheel.py` accepts `--directory`, `--platform-id`, `--python-minor`,
`--mode` and `--evidence`. Its t role additionally needs `--free-threaded` and
the qualified `--internal-polars` directory. `wheel_smoke.py` can independently
check a real installed environment with `--expect-version`, `--with-pandas`,
`--with-polars`, and one of `--with-dateutil`/`--without-dateutil`, according to
the actual profile. Run with `-I -B` outside the checkout. Neither tool makes
an ABI-incompatible wheel compatible; use the actual target interpreter.

Create a certificate only from the completed current raw audit and final CI
metadata. Use `release_candidate.digest_json`, `validate_ci`, `verify_bundle`
and `validate_performance` from the frozen source as the local preflight. The
certificate must contain the complete current performance receipt, not an
inherited result or just a digest. Save the JSON file with real newlines.

The final authorized write is then a single immutable annotated tag:

```bash
git tag --annotate "$release_tag" "$release_source" --file "$certificate_file"
git cat-file -p "$release_tag"
git push origin "refs/tags/${release_tag}"
gh api "repos/AresJef/rsTimes/git/ref/tags/${release_tag}"
```

Follow the tag-triggered `publish.yml`. Its jobs perform GitHub publication,
OIDC PyPI upload and actual public installation in that order. The only manual
workflow used for public recovery is the read-only `verify-published.yml` with
its explicit `tag` input. It has no upload or compilation permission for
rsTimes. Before any recovery, verify what already exists and compare bytes.

Starting prompt for a future release:

> Read AGENTS.md, docs/RELEASING.md and the current adoption report. Propose a
> bounded plan for the requested next version, using the current repository and
> actual support matrix. Verify GitHub/PyPI authorization first. Preserve my
> dirty root checkout and immutable past releases. Reuse existing CI, package
> verifier and benchmark tools; validate the actual release artifacts and do
> not transfer older binary timings. State the version, baseline, full required
> scope, budget, account handoffs, and whether commit/push/merge/tag/publication
> are authorized. Keep 30-minute self-questioning corrections and reports.
> Do not begin publishing until the agreed authorization and current gates hold.

## Successful full-CI timing observed for b3

Run41982305161 attempt1 at dc878ef was successful without a failed job. All16
internal upstream-runtime qualifications were actual cache misses on main.
Do not substitute the warmer eight-position pilot for this full48-position time.

| Platform | ABI positions | Native parallel span | Sum of native job time | Sum of observed job queue time |
|---|---:|---:|---:|---:|
| linux-arm64 | 6 | 1h 20m 42s | 2h 16m 02s | 2h 18m 41s |
| linux-musl-arm64 | 6 | 2h 10m 33s | 4h 11m 33s | 2h 10m 28s |
| linux-musl-x86_64 | 6 | 1h 42m 37s | 4h 03m 40s | 0h 36m 09s |
| linux-x86_64 | 6 | 0h 57m 07s | 1h 54m 28s | 1h 28m 19s |
| macos-arm64 | 6 | 1h 39m 00s | 2h 46m 18s | 1h 45m 25s |
| macos-x86_64 | 6 | 2h 47m 43s | 5h 58m 51s | 2h 44m 23s |
| windows-arm64 | 6 | 1h 22m 00s | 3h 35m 36s | 0h 11m 14s |
| windows-x86_64 | 6 | 1h 30m 09s | 3h 30m 37s | 2h 44m 12s |

Whole full-CI wall time, including the independent rebuilds/oracles/final bundle: **3h 06m 37s**.
Native spans run concurrently and may contain scheduling gaps. Neither those
spans nor sums of job/queue times should be added to claim workflow wall time.
Per-ABI rows, actual interpreter patches, step times and cache-source log lines
are retained in the release evidence `S12/full-41982305161-timing.json`.
The initial publication attempt failed one owned watchdog diagnostic control.
Only macOS Intel/3.15t was rerun unchanged and passed in5m24s. Other50
successful jobs retained their original step/timing records. GitHub assigned
new API job IDs/run_attempt fields to those reused records: that does not mean
50 extra executions or repeated uploads. Keep both attempts and the explicit
47+1 public-position selection. Never describe the first attempt as all-green.

The fragile control injected0.6s bootstrap delay into a1.5s diagnostic window;
its parent deadline/reaping worked but a slow t interpreter could leave no
time to flush a traceback. Verification maintenance gives that synthetic test
a5s window with2s bootstrap delay, retaining its diagnostic/phase/reaping
assertions and default60/30/5 watchdog limits. Six ABI suites passed and
ordinary/314t/315t isolated relative-deadline mutations remained rejected.
It changes no production source or released distribution.
