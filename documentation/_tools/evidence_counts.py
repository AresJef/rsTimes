"""Count successful worker records and registered successful case/profile pairs."""

import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def count_successes(reports, registry, producers):
    successes = {}
    by_profile = {}
    exceptions = []
    for producer in producers:
        profile = producer["profile"]
        if profile in by_profile:
            raise ValueError("Duplicate producer: " + profile)
        inventory = producer["inventory_only"]
        result = {"inventory_only": inventory, "worker_successes": 0, "registered_successes": 0}
        by_profile[profile] = result
        files = sorted((reports / profile).rglob("*.json"))
        if bool(files) == inventory:
            raise ValueError("Examples and inventory-only artifacts differ from the producer list: " + profile)
        for file in files:
            report = read(file)
            if report["profile"] != profile:
                raise ValueError("Incorrect profile in " + file.name)
            if report["status"] != "pass":
                continue
            for group in report["groups"]:
                if group["status"] != "pass":
                    continue
                case = group["id"]
                pair = (case, profile)
                if pair in successes:
                    raise ValueError("Repeated successful case/profile: " + repr(pair))
                registration = registry.get(case, {})
                if registration and registration["page"] != report["page"]:
                    raise ValueError("A case receipt belongs to another page: " + case)
                applicable = profile in registration.get("profiles", ())
                successes[pair] = applicable
                result["worker_successes"] += 1
                result["registered_successes"] += applicable
                if not applicable:
                    exceptions.append({"case": case, "profile": profile, "page": report["page"],
                                       "registered_profiles": registration.get("profiles", []),
                                       "report": "verification/reports/" + file.relative_to(reports).as_posix()})
    return {
        "producer_count": len(by_profile),
        "example_profiles": sum(not item["inventory_only"] for item in by_profile.values()),
        "inventory_only_profiles": sum(item["inventory_only"] for item in by_profile.values()),
        "worker_successes": len(successes), "registered_successes": sum(successes.values()),
        "by_profile": by_profile, "unregistered_successes": exceptions,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--producers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = {case["id"]: case for case in read(args.registry)["examples"]}
    result = count_successes(args.reports, registry, read(args.producers))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
