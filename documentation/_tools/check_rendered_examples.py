"""Require every rendered Python block to match its source and verified output."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import runpy

DOC = Path(__file__).resolve().parents[1]
SCAN = runpy.run_path(str(DOC / "_tools/example_blocks.py"))
PYTHON = SCAN["PYTHON"] | {"pycon", "ipython", "ipython3"}


class HighlightedBlocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.divs = []
        self.capture = None
        self.blocks = []
        self.ids = set()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "div":
            languages = [c.removeprefix("highlight-") for c in attrs.get("class", "").split()
                         if c.startswith("highlight-")]
            self.divs.append(languages[0] if languages else None)
        if tag == "pre":
            language = next((name for name in reversed(self.divs) if name), "")
            self.capture = (language, [])

    def handle_data(self, text):
        if self.capture is not None:
            self.capture[1].append(text)

    def handle_endtag(self, tag):
        if tag == "pre" and self.capture is not None:
            language, parts = self.capture
            self.blocks.append((language, "".join(parts)))
            self.capture = None
        if tag == "div" and self.divs:
            self.divs.pop()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def compare(path, source, registered):
    doc = HighlightedBlocks()
    html = path.read_text(encoding="utf-8")
    doc.feed(html)
    expected = SCAN["scan_examples"](source.read_text(encoding="utf-8"), source.suffix) if source else []
    problems, observed = [], []
    if {item.name for item in expected} != registered:
        problems.append("Registered example IDs differ from the Python blocks in the source.")
    candidates = [index for index, (language, code) in enumerate(doc.blocks)
                  if language in PYTHON or code.lstrip().startswith(">>> ")]
    if len(candidates) != len(expected):
        problems.append(f"Found {len(candidates)} rendered Python blocks for {len(expected)} source examples.")
    for index, example in zip(candidates, expected):
        code = doc.blocks[index][1].rstrip("\n")
        following = doc.blocks[index + 1] if index + 1 < len(doc.blocks) else ("", "")
        output = following[1].rstrip("\n")
        if example.name not in doc.ids:
            problems.append(f"Rendered example anchor missing: {example.name}")
        if code != example.code:
            problems.append(f"Rendered code differs: {example.name}")
        if following[0] not in {"text", "none"} or output != example.output:
            problems.append(f"Rendered output differs: {example.name}")
        observed.append({"id": example.name, "sha256": sha(code), "output_sha256": sha(output)})
    return {"html_sha256": sha(html), "examples": observed, "problems": problems}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page", type=Path, action="append", default=[])
    args = parser.parse_args()
    entries = json.loads((DOC / "_data/examples.json").read_text(encoding="utf-8"))["examples"]
    registry = {}
    for entry in entries:
        registry.setdefault(entry["page"], set()).add(entry["id"])
    sources = args.page or [
        path.relative_to(DOC) for path in DOC.rglob("*")
        if path.suffix in {".md", ".rst"}
        and not any(part.startswith("_") for part in path.relative_to(DOC).parts)
    ]
    pages = {name.with_suffix(".html").as_posix(): name for name in sources}
    if not args.page:
        for path in args.html.rglob("*.html"):
            pages.setdefault(path.relative_to(args.html).as_posix(), None)
    results = {}
    for relative, source_name in sorted(pages.items()):
        path = args.html / relative
        if not path.is_file():
            results[relative] = {"problems": ["Rendered page missing."]}
            continue
        source = DOC / source_name if source_name else None
        results[relative] = compare(path, source, registry.get(source_name.as_posix(), set()) if source_name else set())
    failures = {page: record["problems"] for page, record in results.items() if record["problems"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"status": "fail" if failures else "pass", "pages": results}, indent=2) + "\n")
    print(json.dumps({"pages": len(results), "failures": failures}, ensure_ascii=False))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
