"""Protect the second optimization's group, identity and statistical contracts.

Synthetic records test verdicts only; they never become performance evidence.
"""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("optimization", ROOT / "benchmarks/delta/optimization.py")
optimization = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimization)


def fixture(candidate_ns=1_000_000):
    """Create one complete synthetic group with three distinct expected PIDs."""
    members = {}
    for index, role in enumerate(optimization.ROLES):
        start = index * 3_000_000 + 100
        wall = candidate_ns if role == "new" else 1_000_000
        members[role] = {"pid": index + 1, "count": 100, "valid": True, "reasons": [],
                         "before": {"start_ns": start, "end_ns": start + 10},
                         "after": {"start_ns": start + wall + 210, "end_ns": start + wall + 220},
                         "batches": {"engine": {"count": 100, "elapsed_ns": wall,
                                                 "cpu_elapsed_ns": wall, "ns_per_call": wall / 100}}}
    return {"count": 100, "order": list(optimization.ROLES), "start_ns": 0,
            "end_ns": 10_000_000, "members": members}


class Contracts(unittest.TestCase):
    """Verify group eligibility and retain adverse evidence."""
    def test_approved_bulk_tolerance_preserves_core_and_numpy_limits(self):
        """Foreign 5% tolerance must not weaken core or NumPy requirements."""
        from unittest.mock import patch

        cases = [{"id": f"{group}:{size}", "group": f"{group}:{size}"}
                 for group in ("A1", "A2", "A3", "A4", "A5", "A6", "A7")
                 for size in (1024, 10000)]
        def rows_for(changed=None):
            rows = []
            for case in cases:
                prefix = case["group"].split(":")[0]
                ratio = 1.60 if prefix in ("A1", "A2", "A3") else (1.01 if prefix == "A6" else .96)
                ratio = changed.get(prefix, ratio) if changed else ratio
                rows.append({**case, "complete": True, "current": {
                    "id": case["id"], "group": case["group"], "speed_ratio": ratio,
                    "conservative_ratio": ratio, "max_noise": .01,
                }})
            return rows
        with patch.multiple(optimization, REVISION=True, SUITE="bulk", LABELS=("current",),
                            FULL_IDS={case["id"] for case in cases}):
            self.assertEqual(optimization.evaluate(rows_for(), cases, True, True)["performance"], "PASS")
            for changed in ({"A4": .95}, {"A5": .95}, {"A7": .95}, {"A6": .99}):
                self.assertFalse(optimization.evaluate(rows_for(changed), cases, True, True)["gates"]["P04"])
            self.assertFalse(optimization.evaluate(rows_for({"A2": 1.49}), cases, True, True)["gates"]["P03"])

    def test_two_role_groups_and_stable_losses_follow_revision_gates(self):
        """Two-role transport cannot inherit the historical three-role gates."""
        from unittest.mock import patch
        settings = {"ROLES": ("old", "new"), "ORDERS": (("old", "new"), ("new", "old")),
                    "LABELS": ("current",), "REVISION": True, "SUITE": "float", "FULL_IDS": {"one"}}
        with patch.multiple(optimization, **settings):
            groups = []
            for order in optimization.ORDERS:
                group = fixture(candidate_ns=2_000_000)
                group["members"].pop("oracle", None)
                group["order"] = list(order)
                for index, role in enumerate(order):
                    member = group["members"][role]
                    wall = member["batches"]["engine"]["elapsed_ns"]
                    member["before"] = {"start_ns": index * 3_000_000, "end_ns": index * 3_000_000 + 10}
                    member["after"] = {"start_ns": index * 3_000_000 + wall + 210,
                                       "end_ns": index * 3_000_000 + wall + 220}
                pids = {role: member["pid"] for role, member in group["members"].items()}
                self.assertEqual(optimization.validate_group(group, pids), [])
                groups.append(group)
            row = optimization.summarize_case({"id": "one", "group": "F1"},
                {"accepted": groups, "attempts": 2}, 1, 2)
            self.assertNotIn("original", row)
            self.assertEqual(optimization.evaluate([row], [{"id": "one", "group": "F1"}], True, True)["performance"], "FAIL")
            bad = dict(groups[0], members={"old": groups[0]["members"]["old"]})
            with self.assertRaises(ValueError):
                optimization.validate_group(bad, pids)

    def test_unequal_preflight_outputs_stop_worker_startup(self):
        """Incorrect public results stop before any target timing is accepted."""
        from unittest.mock import patch
        class Fake:
            next_pid = 0
            def __init__(self, env, package, *args):
                Fake.next_pid += 1
                value = 1 if package == "cytimes" else 2
                self.metadata = {"cases": [], "observations": [{"result": value}],
                                 "loaded_identity": {"pid": Fake.next_pid},
                                 "environment": {key: True for key in ("python", "platform", "machine", "measurement_qos",
                                     "process_model", "gil_disabled_build", "gil_enabled", "dependencies")}}
            def short_info(self):
                return {"pid": self.metadata["loaded_identity"]["pid"]}
            def close(self):
                pass
        from types import SimpleNamespace
        args = SimpleNamespace(oracle_env="a", baseline_env="b", candidate_env="c", group="all", case=[])
        with patch.object(optimization.bench, "Process", Fake):
            with self.assertRaisesRegex(ValueError, "Unequal workload output"):
                optimization.Workers(args)
    def test_missing_member_is_an_error(self):
        """Missing member is an error."""
        group = fixture(); del group["members"]["new"]
        with self.assertRaises(ValueError):
            optimization.validate_group(group, {"oracle": 1, "old": 2, "new": 3})

    def test_pid_or_count_mismatch_is_an_error(self):
        """Pid or count mismatch is an error."""
        for key, value in (("pid", 9), ("count", 101)):
            group = fixture(); group["members"]["new"][key] = value
            with self.assertRaises(ValueError):
                optimization.validate_group(group, {"oracle": 1, "old": 2, "new": 3})

    def test_quality_failure_rejects_the_whole_group(self):
        """Quality failure rejects the whole group."""
        group = fixture(); group["members"]["old"].update(valid=False, reasons=["engine:cpu-gap"])
        self.assertIn("old:engine:cpu-gap", optimization.validate_group(group, {"oracle": 1, "old": 2, "new": 3}))

    def test_order_and_span_are_checked(self):
        """Order and span are checked."""
        group = fixture(); group["order"] = ["oracle", "old", "old"]
        with self.assertRaises(ValueError):
            optimization.validate_group(group, {"oracle": 1, "old": 2, "new": 3})
        group = fixture(); group["end_ns"] = 300_000_000
        self.assertIn("group-span", optimization.validate_group(group, {"oracle": 1, "old": 2, "new": 3}))

    def test_reported_order_must_match_actual_boundaries(self):
        """Reported order must match actual boundaries."""
        group = fixture(); group["order"] = ["new", "old", "oracle"]
        with self.assertRaises(ValueError):
            optimization.validate_group(group, {"oracle": 1, "old": 2, "new": 3})

    def test_slow_valid_groups_are_retained(self):
        """Slow valid groups are retained."""
        group = fixture(candidate_ns=2_000_000)
        self.assertEqual(optimization.validate_group(group, {"oracle": 1, "old": 2, "new": 3}), [])
        state = {"accepted": [group] * 6, "attempts": 6, "count": 100}
        row = optimization.summarize_case({"id": "one", "group": "B1"}, state, 1, 6)
        self.assertEqual(row["current"]["conservative_ratio"], .5)

    def test_incomplete_order_quota_cannot_be_complete(self):
        """Incomplete order quota cannot be complete."""
        state = {"accepted": [fixture()] * 6, "attempts": 6, "count": 100}
        row = optimization.summarize_case({"id": "one", "group": "B1"}, state, 1, 6)
        self.assertFalse(row["complete"])

    def test_wrong_resume_identity_is_rejected(self):
        """Wrong resume identity is rejected."""
        with self.assertRaises(ValueError):
            optimization.validate_resume({"identity": {"new": "old-native"}}, {"new": "new-native"})

    def test_partial_row_never_produces_pass(self):
        """Partial row never produces pass."""
        state = {"accepted": [], "attempts": 0}
        row = optimization.summarize_case({"id": "one", "group": "B1"}, state, 12, 120)
        result = optimization.evaluate([row], [{"id": "one", "group": "B1"}], True, True)
        self.assertEqual(result["performance"], "INCONCLUSIVE")

    def test_one_case_per_group_cannot_pass_the_full_contract(self):
        """One case per group cannot pass the full contract."""
        manifest = json.loads((ROOT / "benchmarks/delta/cases.json").read_text())
        cases = [{"id": identifiers[0], "group": group} for group, identifiers in manifest["groups"].items()]
        rows = []
        for case in cases:
            groups = []
            for order in optimization.ORDERS:
                group = fixture(candidate_ns=500_000); group["order"] = list(order)
                groups.append(group)
            state = {"accepted": groups, "attempts": 6, "count": 100}
            rows.append(optimization.summarize_case(case, state, 1, 6))
        result = optimization.evaluate(rows, cases, True, True)
        self.assertFalse(result["full_contract"])
        self.assertEqual(result["performance"], "INCONCLUSIVE")

    def test_interrupted_attempt_keeps_time_and_count(self):
        """Interrupted attempt keeps time and count."""
        state = {"one": {"accepted": [], "attempts": 0}}
        entry = {"kind": "begin", "id": "one", "attempt": 1, "elapsed_seconds": 1210,
                 "calibration": {"count": 100, "warmup": 0, "target_ms": 1}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.jsonl"
            path.write_text(json.dumps(entry) + "\n")
            used = optimization.replay_journal(state, path, 1100, {"oracle": 1, "old": 2, "new": 3})
        self.assertEqual(used, 1210)
        self.assertEqual(state["one"]["attempts"], 1)
        self.assertEqual(state["one"]["accepted"], [])

    def test_recovery_commits_one_complete_group_once(self):
        """Recovery commits one complete group once."""
        state = {"one": {"accepted": [], "attempts": 0}}
        group = fixture(); group.update(valid=True, reasons=[])
        begin = {"kind": "begin", "id": "one", "attempt": 1, "elapsed_seconds": 2,
                 "calibration": {"count": 100, "warmup": 0, "target_ms": 1}}
        commit = {"kind": "commit", "id": "one", "attempt": 1, "elapsed_seconds": 3, "group": group}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.jsonl"
            path.write_text(json.dumps(begin) + "\n" + json.dumps(commit) + "\n")
            pids = {"oracle": 1, "old": 2, "new": 3}
            optimization.replay_journal(state, path, 0, pids)
            optimization.replay_journal(state, path, 3, pids)
        self.assertEqual(state["one"]["attempts"], 1)
        self.assertEqual(len(state["one"]["accepted"]), 1)

    def test_truncated_tail_is_distinct_from_a_corrupt_complete_line(self):
        """Truncated tail is distinct from a corrupt complete line."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.jsonl"
            path.write_text('{"kind":')
            self.assertEqual(optimization.replay_journal({}, path, 9, {}), 9)
            path.write_text('{"kind":\n')
            with self.assertRaises(json.JSONDecodeError):
                optimization.replay_journal({}, path, 9, {})

    def test_saved_pass_flag_cannot_replace_complete_raw_precision(self):
        """Saved pass flag cannot replace complete raw precision."""
        identity = {"candidate": "same-final-artifact"}
        proof = {"identity": identity, "passed": True, "comparisons": [{"id": "one"}],
                 "blocks": 12, "width": 40, "actual_pids": {"oracle": 1, "old": 2, "new": 3},
                 "states": {"one": [{"accepted": []}, {"accepted": []}]}}
        with self.assertRaisesRegex(ValueError, "Incomplete raw precision"):
            optimization.validate_precision(proof, identity, [{"id": "one", "group": "B1"}], ("one",))

    def test_clock_cost_sets_a_measurable_common_invocation_floor(self):
        """Prevent permanent precision rejection when startup clock reads are expensive."""
        class FixedWorkers:
            host = {role: {"clock_read_p99_ns": 6000 if role == "oracle" else 800,
                           "wall_clock": {"resolution": 1e-9}, "thread_clock": {"resolution": 1e-9}}
                    for role in optimization.ROLES}
            def group(self, identifier, count, order, warmup):
                return {"members": {role: {"batches": {"engine": {"ns_per_call": 1000}}}
                                    for role in optimization.ROLES}}
        count, warmup, pilots = optimization.calibrate(FixedWorkers(), "synthetic", 1)
        self.assertEqual(count, 1500)

    def test_partial_matrix_reports_missing_original_rows_without_crashing(self):
        """Keep an interrupted full matrix inconclusive even when many groups exist."""
        manifest = json.loads((ROOT / "benchmarks/delta/cases.json").read_text())
        cases = [{"id": identifier, "group": group} for group, ids in manifest["groups"].items() for identifier in ids]
        rows = []
        for case in cases:
            groups = []
            if case["id"] != cases[0]["id"]:
                for order in optimization.ORDERS:
                    group = fixture(candidate_ns=500_000); group["order"] = list(order); groups.append(group)
            rows.append(optimization.summarize_case(case, {"accepted": groups, "attempts": len(groups)}, 1, 6))
        verdict = optimization.evaluate(rows, cases, True, True)
        self.assertFalse(verdict["gates"]["G4"])
        self.assertEqual(verdict["performance"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
