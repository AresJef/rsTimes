"""Protect validity and acceptance decisions; does not add Delta workloads."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("paired", ROOT/"benchmarks/delta/paired.py")
paired = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paired)


def fixture(cpu=1_000_000, candidate=1_000_000):
    batch = {"count": 100, "elapsed_ns": 1_000_000, "cpu_elapsed_ns": cpu,
             "ns_per_call": 10_000, "boundary_ns": 500}
    second = {**batch, "elapsed_ns": candidate, "cpu_elapsed_ns": candidate,
              "ns_per_call": candidate/100}
    snap = {"start_ns": 0, "end_ns": 10, "load_per_cpu": .2,
            "memory_fraction": .1, "ticks": [100,100,100,100]}
    return {"count": 100, "start_ns": 10, "end_ns": 3_000_000,
            "before": snap, "after": {**snap, "start_ns": 3_000_000, "end_ns": 3_000_010},
            "batches": {"reference": batch, "candidate": second}, "order": ["reference", "candidate"]}


INFO = {"wall_clock": {"resolution": 1e-9}, "thread_clock": {"resolution": 1e-9}, "clock_read_p99_ns": 200}


class Validity(unittest.TestCase):
    def test_coarse_ticks_missing_do_not_veto(self):
        p = fixture()
        self.assertEqual(paired.reasons(p, INFO), [])
        self.assertFalse(p["host_cpu"]["used_as_gate"])

    def test_cpu_wait_rejects_whole_pair(self):
        self.assertIn("reference:cpu-gap", paired.reasons(fixture(cpu=600_000), INFO))

    def test_clock_and_short_reject(self):
        p = fixture(); p["batches"]["candidate"]["elapsed_ns"] = 100_000
        self.assertIn("candidate:short", paired.reasons(p, INFO))
        info = copy.deepcopy(INFO); info["clock_read_p99_ns"] = 20_000
        self.assertIn("reference:clock-precision", paired.reasons(fixture(), info))

    def test_eligible_slow_samples_are_retained(self):
        self.assertEqual(paired.reasons(fixture(candidate=2_000_000), INFO), [])

    def test_mismatched_count_rejects(self):
        p = fixture(); p["batches"]["candidate"]["count"] = 101
        self.assertIn("candidate:count", paired.reasons(p, INFO))

    def test_enough_busy_ticks_veto(self):
        p = fixture(); p["after"]["ticks"] = [110,110,101,100]
        self.assertIn("host-busy", paired.reasons(p, INFO))

    def test_partial_and_unvalidated_cannot_pass(self):
        state = {"count":100, "accepted":[], "attempts":[], "required":12}
        for i in range(12):
            p = fixture(candidate=700_000); p["valid"] = True
            p["order"] = ["reference","candidate"] if i%2==0 else ["candidate","reference"]
            state["accepted"].append(p)
        r = paired.row({"id":"one","group":"B1"}, state)
        summary = {"core":{"median_ratio":1.4,"conservative_ratio":1.4},
                   "thirdparty":{"median_ratio":1.1,"conservative_ratio":1.1}}
        self.assertFalse(paired.evaluate([r], summary, ["one"], "formal", True)["formal_acceptance"])
        self.assertFalse(paired.evaluate([r], summary, ["one"], "formal", False)["gates"]["P5"])

    def test_noise_and_slow_valid_pair_fail_gate(self):
        state = {"count":100, "accepted":[], "attempts":[], "required":12}
        for i in range(12):
            p=fixture(candidate=2_000_000 if i==11 else 700_000); p["valid"]=True
            p["order"]=["reference","candidate"] if i%2==0 else ["candidate","reference"]
            state["accepted"].append(p)
        r=paired.row({"id":"one","group":"B1"},state)
        self.assertGreater(r["max_noise"], .05)
        self.assertEqual(r["conservative_candidate_ratio"], 2)

    def test_statistical_block_keeps_every_valid_micro_pair(self):
        state = {"count":100, "accepted":[], "attempts":[], "required":1, "pairs_per_block":20}
        for i in range(20):
            p=fixture(candidate=2_000_000 if i==19 else 700_000); p["valid"]=True
            state["accepted"].append(p)
        groups = paired.blocks(state)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["micro_pairs"]), 20)
        self.assertEqual(groups[0]["batches"]["candidate"]["elapsed_ns"], 19*700_000+2_000_000)
        self.assertEqual(groups[0]["batches"]["candidate"]["count"], 2000)


if __name__ == "__main__":
    unittest.main()
