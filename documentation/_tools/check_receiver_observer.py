"""Check that receiver traces distinguish real expression work from reading materialized data."""

import json
from pathlib import Path
import runpy
import sys


def main():
    observer = runpy.run_path(str(Path(__file__).with_name("observe_receivers.py")))
    entry = "polars.Expr.pldt.as_unit"
    setup = """import polars as pl
import rstimes.pldt
frame = pl.DataFrame({"event": pl.Series([-1500, None], dtype=pl.Datetime("ns", "UTC"))})
batches = []
def batch(column):
    batches.append(column.len())
    return column
expr = pl.col("event").pldt.as_unit("us").map_batches(batch, return_dtype=pl.Datetime("us", "UTC"))
table = frame.select(expr)
assert batches == [2]
assert table["event"].to_physical().to_list() == [-2, None]
"""
    cases = {
        "read-materialized": ("""result = table.lazy().select("event").collect()
assert batches == [2]
""", {"select"}),
        "compute-again": ("""result = frame.lazy().select(expr).collect()
assert batches == [2, 2]
""", {"select", "collect"}),
    }
    result = {}
    for case, (code, expected) in cases.items():
        text = setup + code + 'print(result["event"].to_physical().to_list())\n'
        trace = observer["visible"](text, observer["Observer"]([entry]), case, None)
        assert trace["exception"] is None and trace["output"] == "[-2, None]", trace
        effects = {use["effect"] for use in trace["uses"] if use["effect"] in {"select", "collect"}}
        assert effects == expected, (case, effects)
        result[case] = {"expected": sorted(expected), "observed": sorted(effects), "value": trace["output"]}
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
