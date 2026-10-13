# Delta performance comparison

`optimization.py` compares the frozen cyTimes implementation, the documented Rust
baseline, and the candidate Rust wheel in separate actual processes. It reuses
`bench.py` workloads and `paired.py` timing/quality checks. Public Python calls are
measured; initialization, allocation and result release remain part of each call.

The canonical inputs are in `tests/delta/cases.py`. `cases.json` selects the fixed
99 scenes and ten groups. Preserve input IDs and weights when comparing versions.
The formal contract and budget are in `tasks/plan.md`; current progress belongs
only in `tasks/todo.md`.

## Quick development comparison

Run from the project root after installing the intended release wheel in the
candidate environment. The baseline environment must remain unchanged.

```sh
.local/delta/documentation-env/bin/python benchmarks/delta/optimization.py \
  --group B3 --output tasks/evidence/new-development-comparison
```

Quick defaults to six blocks of twenty complete groups. It cannot pass formal
acceptance. Use it to select or reject a concrete implementation change, not to
repeat the same candidate until a favorable result appears.

## Precision control and formal comparison

The final second-round configuration is stored in
`tasks/evidence/delta-optimization-20261011/targets-v6-final.json` and
`extra-final-v6.json`. These are this project's declared parameters, not
universal defaults for another project or environment.

```sh
.local/delta/documentation-env/bin/python benchmarks/delta/optimization.py \
  --control --control-seconds 1200 \
  --targets tasks/evidence/delta-optimization-20261011/targets-v6-final.json \
  --extra-controls tasks/evidence/delta-optimization-20261011/extra-final-v6.json \
  --output tasks/evidence/new-precision-control
```

Use the emitted `precision.json` path in `--precision` for a full comparison:

```sh
.local/delta/documentation-env/bin/python benchmarks/delta/optimization.py \
  --mode formal --precision PATH_TO_PRECISION_JSON \
  --targets tasks/evidence/delta-optimization-20261011/targets-v6-final.json \
  --extra-controls tasks/evidence/delta-optimization-20261011/extra-final-v6.json \
  --output tasks/evidence/new-formal-cycle
```

A formal cycle requires 99 scenes, twelve blocks per scene, and 120 complete
three-role groups per block. Each role order occurs twenty times per block.
Run the independent cycle with new processes and another output directory.
Both complete cycles must independently meet the contract.

## Timing, eligibility and interpretation

For each scene, pilots choose one common invocation count. The fastest role must
reach the declared duration, and every role must also satisfy the frozen clock
resolution/read-cost limit with a fixed 25% count margin. Pilots and short/long
controls never become formal performance scores.

A short/long control requires twelve blocks of forty complete units. The short
and long invocation counts differ by five; implementation orders are balanced,
length order alternates, and the whole unit must pass the joint time boundary.
The frozen ratio-difference and noise limits remain 3% and 5%.

Every accepted group includes all three adjacent batches, actual PIDs, counts,
monotonic boundaries, wall/thread CPU times and required host checks. A failed
member rejects the complete group; its original order slot returns to the queue.
Valid slow measurements remain in the data. System counters with insufficient
resolution are handled by the declared rules, not assumed to show an idle host.

Within each fixed statistical block, per-call time is `sum(time) / sum(count)`.
The report keeps median ratios, the worst paired block ratio and maximum ratio
deviation separate. Blocks are logical averages, not independent processes.
`COMPLETE`, `VALID` and a favorable median do not imply `PASS`: stability,
precision, coverage, protection and independent-process requirements also apply.

## Recovery and bounded adjustments

Raw receipts and append-only journals preserve every complete accepted group,
failed attempt and consumed time. An incomplete last journal fragment is allowed;
a corrupt complete record is an error. Resume never resets consumed limits.

Scoped controls require the complete predeclared failed set and the original
receipt/source archive. Earlier passing controls can be reused only after their
artifact, environment, workload, timing, quality and statistical dependencies match.
Each replacement scene must complete all required groups in its own actual cohort.

`--formal-case` requires an original formal receipt, its source archive and matching
new precision evidence. It replaces only declared unstable scenes, inherits their
attempt counts and original collection runtime, and leaves the remaining scenes
untouched. `tools/compose_optimization_performance.py` audits complete scene sources
and recomputes all gates. Never splice groups or blocks from different cohorts.

Keep the original project budget and collection-runtime caps. Control, diagnostics,
compilation, analysis and reporting still count toward project time even when
reported separately from formal collection runtime. At a limit, preserve missing
work and report `INCOMPLETE` or `INCONCLUSIVE`; do not loosen the contract.
