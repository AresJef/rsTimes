"""Test regional error copy and the real ISO result of installed examples."""

import ast
import inspect
import os
from pathlib import Path
import runpy
import unittest

from rstimes import Pldt


HERE = Path(__file__).resolve().parent
CHECKER = Path(os.environ.get("RSTIMES_REGIONAL_CHECKER", HERE / "check_regional_raises.py"))
GATE = runpy.run_path(str(CHECKER))
OBSERVER = runpy.run_path(str(CHECKER.with_name("observe_receivers.py")))
STUB = Path(inspect.getfile(Pldt)).with_suffix(".pyi")
EXPR_ERROR = "polars.exceptions.ComputeError"
COLLECT = 'frame.lazy().select(expr).collect()["event"]'


def expr_doc():
    owner = next(node for node in ast.parse(STUB.read_bytes()).body
                 if isinstance(node, ast.ClassDef) and node.name == "_ExprNamespace")
    return ast.get_docstring(next(node for node in owner.body
                                  if isinstance(node, ast.FunctionDef) and node.name == "isocalendar"))


class RegionalRaisesTest(unittest.TestCase):
    def test_regional_error_belongs_to_execution(self):
        raises = GATE["doc_raises"](inspect.getdoc(Pldt.isoyear))
        current = raises[EXPR_ERROR]
        accepted = (
            current,
            current.replace("raises this error", "raises ComputeError"),
            "When select() or collect() evaluates a date outside the supported range of a named time zone, "
            "Polars raises ComputeError. An invalid input type can still fail during planning.",
        )
        rejected = (
            "A named time zone date outside the supported range raises OverflowError during expression creation.",
            "If a date is outside the supported range of a named time zone, creating the expression "
            "raises OverflowError before select or collect can evaluate that row.",
            current.replace("raises this error", "raises OverflowError"),
            "A date outside the supported range of a named time zone raises ComputeError during expression "
            "creation, before select or collect raises anything.",
            "A date outside the supported range of a named time zone raises ComputeError. "
            "A different failure can occur during select or collect.",
        )
        for text in accepted:
            with self.subTest(accepted=text):
                self.assertEqual(GATE["runtime_problems"]("isoyear", raises | {EXPR_ERROR: text}), [])
        for text in rejected:
            with self.subTest(rejected=text):
                self.assertTrue(GATE["runtime_problems"]("isoyear", raises | {EXPR_ERROR: text}))

    def test_row_count_does_not_materialize_iso_fields(self):
        leaving_only_length = (
            '_ = frame.lazy().select(expr).select(pl.col("event").len()).collect()\n'
            '>>> print(source.pldt.isocalendar().to_list())'
        )
        doc = expr_doc()
        original = f">>> print({COLLECT}.to_list())"
        self.assertIn(original, doc)
        altered = doc.replace(original, ">>> " + leaving_only_length)
        checked, problems = GATE["installed_iso_example"]("Expr.pldt", altered, STUB, OBSERVER)
        self.assertEqual(checked["failures"], 0)
        self.assertTrue(problems)

    def test_direct_select_and_renamed_result_are_real_iso(self):
        doc = expr_doc()
        for expression in (
            COLLECT,
            'frame.select(expr)["event"]',
            'frame.select(expr.alias("iso"))["iso"]',
            'frame.lazy().select(expr).select(pl.col("event").alias("iso")).collect()["iso"]',
        ):
            with self.subTest(expression=expression):
                self.assertIn(COLLECT, doc)
                checked, problems = GATE["installed_iso_example"](
                    "Expr.pldt", doc.replace(COLLECT, expression), STUB, OBSERVER,
                )
                self.assertEqual(checked["failures"], 0)
                self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
