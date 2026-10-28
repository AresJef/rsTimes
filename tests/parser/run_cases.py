"""Run the fixed public-call behavior contract and retain every difference."""
from datetime import date
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
from approved_behavior import expected_parse, ExpectedConfigs, outcomes_equal, error_category

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("_parser_contract_cases", HERE / "cases.py")
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    from cytimes.parser import Configs as OriginalConfigs, parse as original_parse
    from rstimes.parser import Configs, parse_str as parse
    from rstimes import _native
    import importlib.metadata
    upstream = json.loads((HERE / "data" / "upstream_datetimes.json").read_text(encoding='utf-8'))
    rows = []
    def record(ident, legacy, expected, actual, **extra):
        changed = expected != legacy
        equal = outcomes_equal(actual, expected)
        # Approved numeric errors define their public type and message. The
        # oracle adapter's own Python exception context is not target behavior.
        if changed and ident.startswith('config:'):
            def public(value):
                if not isinstance(value, dict): return value
                if 'error' in value:
                    return {'error': {k:value['error'][k] for k in ('type','message')}}
                return {k:public(v) for k,v in value.items()}
            equal = outcomes_equal(actual, expected)
        error_contract = extra.pop('error_contract', None)
        if error_contract:
            error = actual.get('error', {})
            equal = error_category(error) == error_contract
            expected = {'error_contract': {'standard_category':error_contract}}
            changed = True
        rows.append(dict(id=ident, legacy_expected=legacy, expected=expected,
                         actual=actual, approved_difference=changed,
                         reason=((('C05/C06: corrected default month and uniform integer/range validation' if ident.startswith('config:') else 'C07: century selected from the explicit default year' if ident.startswith('original:') else 'C01/C02/C07: minute-offset fix, field bounds or explicit century policy') if changed else None)),
                         equal=equal, **extra))
    matrix = upstream["matrix"]
    configured = cases.configured(Configs)
    original_cfg = cases.configured(OriginalConfigs)
    for index, row in enumerate(upstream["rows"]):
        for position, (iso, ignore, use_cfg) in enumerate(matrix):
            kwargs = dict(default=date(1,1,1), yearfirst=False, isoformat=iso, ignoretz=ignore)
            legacy = cases.outcome(lambda: original_parse(row[0], cfg=original_cfg if use_cfg else None, **kwargs))
            expected = cases.outcome(lambda: expected_parse(row[0], cfg=original_cfg if use_cfg else None, **kwargs))
            actual = cases.outcome(lambda: parse(row[0], cfg=configured if use_cfg else None, **kwargs))
            record(f"original:{index}:{position}",legacy,expected,actual,input=row[0],kwargs=kwargs)
    for index, case in enumerate(cases.parse_cases()):
        legacy = cases.parse_outcome(original_parse, OriginalConfigs, case)
        expected = cases.parse_outcome(expected_parse, OriginalConfigs, case)
        actual = cases.parse_outcome(parse, Configs, case)
        error_contract = 'OverflowError' if case['text']=='12345678901234567890' else (
            'ValueError' if case['text']=='2024-06-15T12:00+24:00' and not case['kwargs'].get('ignoretz',True) else None)
        record(f"extra:{index}",legacy,expected,actual,input=case,error_contract=error_contract)
    legacy = cases.config_transcript(OriginalConfigs)
    original_indices = {row['id']:i for i,row in enumerate(legacy)}
    legacy_rows = cases.config_transcript(OriginalConfigs, include_queries=False)
    expected = cases.config_transcript(ExpectedConfigs, include_queries=False)
    actual = cases.config_transcript(Configs, include_queries=False)
    for index,(old,new) in enumerate(zip(expected,actual)):
        record(f"config:{original_indices[old['id']]}",legacy_rows[index],old,new)
    if len(expected)!=len(actual):
        raise RuntimeError("Configuration transcript coverage changed")
    failures=[row for row in rows if not row["equal"]]
    native=Path(_native.__file__)
    result = dict(version=importlib.metadata.version("rstimes"), python=sys.version,
                  executable=sys.executable, native=str(native),
                  native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),
                  inputs_sha256=hashlib.sha256((HERE/"cases.py").read_bytes()).hexdigest(),
                  expected_policy_sha256=hashlib.sha256((HERE/"approved_behavior.py").read_bytes()).hexdigest(),
                  upstream_inputs_sha256=hashlib.sha256((HERE/"data/upstream_datetimes.json").read_bytes()).hexdigest(),
                  program_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  retired_config_query_ids=[f"config:{i}" for i,row in enumerate(legacy) if row['id'] not in {v['id'] for v in expected}],
                  retired_reason="13 public query APIs explicitly removed; recognition protected through parse and Rust internal tests",
                  calls=len(rows), equal=len(rows)-len(failures), differences=len(failures),
                  approved_differences=sum(row['approved_difference'] for row in rows),
                  rows=rows,
                  by_group={group:{"count":sum(r["id"].startswith(group+":") for r in rows),
                                   "different":sum(r["id"].startswith(group+":") for r in failures)}
                            for group in ("original","extra","config")},
                  failures=failures)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2,
                                     default=lambda value: value.isoformat() if isinstance(value, date) else repr(value))+"\n")
    print(json.dumps({k:result[k] for k in ("calls","equal","differences","by_group")}))
    for row in failures[:8]:
        print(json.dumps({k: row[k] for k in ("id", "input") if k in row},ensure_ascii=True))
    return bool(failures)

if __name__ == "__main__":
    raise SystemExit(main())
