"""Refresh coverage relationships and summaries from the example registry."""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def examples_by_entry(examples):
    reverse = defaultdict(dict)
    for example in examples:
        for path in example["covers"]:
            reverse[path][example["id"]] = example
    return reverse


def derived_fields(entry, cases):
    # Retain the ordering of still-valid examples for existing reference links.
    kept = [name for name in dict.fromkeys(entry["examples"]) if name in cases]
    return {
        "examples": kept + [name for name in cases if name not in kept],
        "scenarios": sorted({scenario for case in cases.values() for scenario in case["scenarios"]}),
        "profiles": sorted({profile for case in cases.values() for profile in case["profiles"]}),
    }


def main():
    table_path = ROOT / "_data/coverage.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "_data/examples.json").read_text(encoding="utf-8"))
    reverse = examples_by_entry(registry["examples"])
    for entry in table["entries"]:
        entry.update(derived_fields(entry, reverse[entry["path"]]))
    table_path.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
