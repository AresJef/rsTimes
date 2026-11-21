"""Check the complete set of copyable rsTimes installation commands on the upgrade page."""

import argparse
from pathlib import Path
import re

from bs4 import BeautifulSoup


def upgrade_commands(html):
    page = BeautifulSoup(html, "html.parser")
    commands = []
    for block in page.select("main pre, main code"):
        if block.name == "code" and block.find_parent("pre") is not None:
            continue
        text = re.sub(r"\\\n[ \t]*", " ", block.get_text())
        for line in text.splitlines():
            if re.search(r"\bpip(?:3(?:\.\d+)?)?\s+install\b", line) and re.search(r"rs[-_.]?times\b", line, re.I):
                commands.append(line.strip())
    return commands


def check_upgrade(html, version):
    expected = f'python -m pip install --upgrade "rsTimes[pandas,polars]=={version}"'
    commands = upgrade_commands(html)
    if commands != [expected]:
        raise ValueError(f"Expected one current upgrade command for {version}, found {commands!r}")
    return commands


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page", type=Path)
    parser.add_argument("version")
    args = parser.parse_args()
    print(*check_upgrade(args.page.read_text(encoding="utf-8"), args.version), sep="\n")
