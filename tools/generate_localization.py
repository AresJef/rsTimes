"""Generate Gregorian names from frozen Unicode CLDR 46.0.0, using stdlib only.

Run with the reference directory and source root as positional arguments.
Archives are read in place; no archive paths are extracted onto the filesystem.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile


def load_json(archive: tarfile.TarFile, member: str) -> dict:
    """Read one named JSON member without unpacking archive paths."""
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"missing CLDR member: {member}")
    with stream:
        return json.load(stream)


def rust_string(value: str) -> str:
    """Quote UTF-8 text while using Rust's syntax for control code points."""
    text = json.dumps(value, ensure_ascii=False)
    for number in range(32):
        text = text.replace(f"\\u{number:04x}", f"\\u{{{number:x}}}")
    return text


def main(reference: Path, source: Path) -> None:
    """Verify frozen sources and emit deterministic native lookup tables."""
    manifest = json.loads((reference / "download-manifest.json").read_text())
    for item in manifest:
        blob = (reference / item["file"]).read_bytes()
        if hashlib.sha256(blob).hexdigest() != item["sha256"]:
            raise ValueError(f"changed frozen source: {item['file']}")
        if item.get("npm_integrity"):
            actual = "sha512-" + base64.b64encode(hashlib.sha512(blob).digest()).decode()
            if actual != item["npm_integrity"]:
                raise ValueError(f"npm integrity mismatch: {item['file']}")

    with tarfile.open(reference / "cldr-core-46.0.0.tgz") as core:
        defaults = set(load_json(core, "package/defaultContent.json")["defaultContent"])
        parents = load_json(core, "package/supplemental/parentLocales.json")["supplemental"]["parentLocales"]["parentLocale"]
        likely = load_json(core, "package/supplemental/likelySubtags.json")["supplemental"]["likelySubtags"]
        aliases = load_json(core, "package/supplemental/aliases.json")["supplemental"]["metadata"]["alias"]
        license_stream = core.extractfile("package/LICENSE")
        if license_stream is None:
            raise ValueError("CLDR license is absent")
        (source / "NOTICE-UNICODE.txt").write_bytes(license_stream.read())

    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    names: dict[str, tuple[str, ...]] = {}
    with tarfile.open(reference / "cldr-dates-full-46.0.0.tgz") as dates:
        for member in dates.getnames():
            if not member.startswith("package/main/") or not member.endswith("/ca-gregorian.json"):
                continue
            locale = member.split("/")[2]
            calendar = load_json(dates, member)["main"][locale]["dates"]["calendars"]["gregorian"]
            months = calendar["months"]["format"]["wide"]
            days = calendar["days"]["format"]["wide"]
            names[locale] = tuple(months[str(i)] for i in range(1, 13)) + tuple(days[d] for d in weekdays)
    root = ET.parse(reference / "root.xml").getroot()
    calendar = root.find("./dates/calendars/calendar[@type='gregorian']")
    if calendar is None:
        raise ValueError("CLDR root Gregorian calendar is absent")
    months = calendar.findall("./months/monthContext[@type='format']/monthWidth[@type='wide']/month")
    days = calendar.findall("./days/dayContext[@type='format']/dayWidth[@type='wide']/day")
    root_months = {m.attrib["type"]: m.text for m in months}
    root_days = {d.attrib["type"]: d.text for d in days}
    names["root"] = tuple(root_months[str(i)] for i in range(1, 13)) + tuple(root_days[d] for d in weekdays)
    if any(not isinstance(word, str) for group in names.values() for word in group):
        raise ValueError("unresolved CLDR name")

    # The JSON release omits unconfirmed draft names that the existing library
    # already supplies. Retain those from the same official XML release rather
    # than replacing minor languages with root month codes.
    explicit: dict[str, dict[int, str]] = {}
    with zipfile.ZipFile(reference / "core.zip") as core:
        for member in core.namelist():
            if not member.startswith("common/main/") or not member.endswith(".xml"):
                continue
            identifier = Path(member).stem.replace("_", "-")
            explicit[identifier.lower()] = {}
            tree = ET.fromstring(core.read(member))
            calendar = tree.find("./dates/calendars/calendar[@type='gregorian']")
            if calendar is None:
                continue
            selected = {}
            for leaf in calendar.findall("./months/monthContext[@type='format']/monthWidth[@type='wide']/month"):
                if "alt" not in leaf.attrib and leaf.text not in (None, "↑↑↑"):
                    selected[int(leaf.attrib["type"]) - 1] = leaf.text
            for leaf in calendar.findall("./days/dayContext[@type='format']/dayWidth[@type='wide']/day"):
                if "alt" not in leaf.attrib and leaf.text not in (None, "↑↑↑"):
                    selected[12 + weekdays.index(leaf.attrib["type"])] = leaf.text
            explicit[identifier.lower()] = selected

    def overlay(identifier: str, group: tuple[str, ...]) -> tuple[str, ...]:
        lineage = []
        current = identifier
        while current not in ("root", ""):
            if current in lineage:
                raise ValueError(f"cyclic CLDR parent locale: {identifier}")
            lineage.append(current)
            fallback = current.rsplit("-", 1)[0] if "-" in current else "root"
            parts = current.split("-")
            # CLDR's nonlikelyScript parent rule prevents e.g. zh-Latn from
            # inheriting Chinese-script names simply by dropping its script.
            if len(parts) == 2 and len(parts[1]) == 4 and parts[1].isalpha():
                maximized = likely.get(parts[0], "").split("-")
                if len(maximized) >= 2 and parts[1] != maximized[1]:
                    fallback = "root"
            current = parents.get(current, fallback)
        result = list(group)
        for ancestor in reversed(lineage):
            for index, text in explicit.get(ancestor.lower(), {}).items():
                result[index] = text
        return tuple(result)

    names = {identifier: overlay(identifier, group) for identifier, group in names.items()}

    def resolve(identifier: str, seen: frozenset[str] = frozenset()) -> tuple[str, ...] | None:
        if identifier in names:
            return names[identifier]
        if identifier in seen:
            return None
        if identifier in defaults:
            parent = parents.get(identifier, identifier.rsplit("-", 1)[0])
            inherited = resolve(parent, seen | {identifier})
            return overlay(identifier, inherited) if inherited is not None else None
        return None

    all_names = dict(names)
    for identifier in sorted(defaults):
        group = resolve(identifier)
        if group is None:
            raise ValueError(f"unresolved CLDR default-content locale: {identifier}")
        all_names[identifier] = group
    # XML also carries valid variant locales without a separate JSON calendar
    # file, e.g. en_US_POSIX. Resolve their existing parent before adding them.
    by_lower = {identifier.lower(): group for identifier, group in all_names.items()}
    for identifier in sorted(explicit):
        if identifier in by_lower:
            continue
        parent = identifier
        while "-" in parent:
            parent = parent.rsplit("-", 1)[0]
            if parent in by_lower:
                all_names[identifier] = overlay(identifier, by_lower[parent])
                break

    # Only finite identifiers supplied by CLDR may gain aliases. Unknown
    # regions are not silently discarded to fall back to a language's names.
    for identifier, maximized in sorted(likely.items()):
        parts = maximized.split("-")
        candidates = [maximized]
        if len(parts) >= 3:
            candidates += [parts[0] + "-" + parts[-1], "-".join(parts[:2]), parts[0]]
        group = next((all_names[c] for c in candidates if c in all_names), None)
        if group is None:
            continue
        all_names.setdefault(identifier, group)
        if len(parts) >= 3:
            all_names.setdefault(parts[0] + "-" + parts[-1], group)

    canonical = tuple(all_names.items())
    for old, record in sorted(aliases["languageAlias"].items()):
        replacement = record["_replacement"].split()[0]
        if replacement in all_names:
            all_names.setdefault(old, all_names[replacement])
        for identifier, group in canonical:
            if identifier.startswith(replacement + "-"):
                all_names.setdefault(old + identifier[len(replacement):], group)
    for old, record in sorted(aliases["territoryAlias"].items()):
        replacement = record["_replacement"].split()[0]
        for identifier, group in canonical:
            if identifier.endswith("-" + replacement):
                all_names.setdefault(identifier[:-len(replacement)] + old, group)

    groups = sorted(set(all_names.values()))
    group_index = {group: i for i, group in enumerate(groups)}
    normalized = {identifier.lower(): group_index[group] for identifier, group in all_names.items()}
    lines = ["//! Generated from Unicode CLDR 46.0.0 Gregorian format/wide names.",
             "//! Source hashes and regeneration: tools/generate_localization.py.",
             "//! Copyright Unicode, Inc.; see NOTICE-UNICODE.txt.", "",
             f"pub(super) const ENGLISH: usize = {group_index[names['en']]};",
             "#[rustfmt::skip]", "pub(super) static GROUPS: &[[&str; 19]] = &["]
    for group in groups:
        lines.append("    [" + ", ".join(rust_string(word) for word in group) + "],")
    lines += ["];", "", "#[rustfmt::skip]", "pub(super) static LOCALES: &[(&str, usize)] = &["]
    for identifier, group in sorted(normalized.items()):
        lines.append(f"    ({rust_string(identifier)}, {group}),")
    lines += ["];", ""]
    output = source / "rust/localization_data.rs"
    output.write_text("\n".join(lines))
    metadata = {"cldr_version": "46.0.0", "weekday_order": weekdays,
                "full_locales": len(names) - 1, "default_content_locales": len(defaults),
                "lookup_identifiers": len(normalized), "distinct_name_groups": len(groups),
                "source_manifest": manifest, "generated_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    (source / "src/rstimes/_localization_sources.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({k: v for k, v in metadata.items() if k != "source_manifest"}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_localization.py REFERENCE_DIR SOURCE_ROOT")
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
