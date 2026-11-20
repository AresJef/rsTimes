"""Link API signatures to their registered reader examples and guides."""
from collections import defaultdict
import json
from pathlib import Path

from docutils import nodes
from sphinx import addnodes


def load_links(app):
    root = Path(app.srcdir)
    entries = json.loads((root / "_data/coverage.json").read_text())["entries"]
    examples = json.loads((root / "_data/examples.json").read_text())["examples"]
    cases = {case["id"]: case for case in examples}
    titles = {}
    by_page = defaultdict(dict)
    for entry in entries:
        linked = [cases[name] for name in entry["examples"]]
        choices = [case for case in linked if case.get("format") == "python"]
        case = (choices or linked)[0]
        page = case["page"]
        if page not in titles:
            title = (root / page).read_text(encoding="utf-8").splitlines()[0]
            titles[page] = title.lstrip("# ").strip()
        if choices:
            target = ("ref", case["id"], titles[page])
        else:
            target = ("doc", "/" + Path(page).with_suffix("").as_posix(), titles[page])
        by_page[entry["page"]][entry["anchor"]] = target
    app.env.rstimes_example_links = dict(by_page)


def link_examples(app, doctree):
    docname = app.env.docname
    targets = app.env.rstimes_example_links.get(docname, {})
    for description in doctree.findall(addnodes.desc):
        signatures = [node for node in description if isinstance(node, addnodes.desc_signature)]
        match = next((targets[id_] for node in signatures for id_ in node["ids"] if id_ in targets), None)
        if not match:
            continue
        role, target, title = match
        if role == "doc" and target == "/" + docname:
            continue
        link = addnodes.pending_xref("", refdomain="std", reftype=role, reftarget=target,
                                    refdoc=docname, refexplicit=True, refwarn=True)
        link += nodes.inline("", title)
        paragraph = nodes.paragraph("", "Example in " if role == "ref" else "Usage in ")
        paragraph += link
        description[-1] += paragraph
