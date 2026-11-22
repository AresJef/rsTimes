"""Check the complete set of copyable rsTimes installation commands on the upgrade page."""

import argparse
from pathlib import Path, PureWindowsPath
import re
import shlex

from bs4 import BeautifulSoup


PIP = re.compile(r"pip(?:3(?:\.\d+)?)?(?:\.exe)?")
PYTHON = re.compile(r"(?:python(?:3(?:\.\d+)?)?|py)(?:\.exe)?")
RSTIMES = re.compile(r"rs[-_.]?times(?=\s*(?:$|[\[<>=!~@;]))", re.I)
RSTIMES_ARCHIVE = re.compile(r"rs[-_.]?times-\d.*\.(?:whl|tar\.gz|zip)(?:[?#].*)?", re.I)

# Only options taking a separate value need special handling. Flags and
# --option=value occupy a single word.
GLOBAL_VALUES = frozenset("""
    --python --log --keyring-provider --proxy --retries --resume-retries
    --timeout --exists-action --trusted-host --cert --client-cert --cache-dir
    --use-feature --use-deprecated
""".split())
INSTALL_VALUES = GLOBAL_VALUES | frozenset("""
    -r --requirement -c --constraint --build-constraint --group
    -t --target --platform --python-version --implementation --abi
    --root --prefix --src --upgrade-strategy -C --config-settings --global-option
    --no-binary --only-binary --progress-bar --root-user-action --report
    -i --index-url --extra-index-url -f --find-links
""".split())


def pip_arguments(words):
    command = next(words, "")
    if command == "$":
        command = next(words, "")
    launcher = PureWindowsPath(command).name
    if PIP.fullmatch(launcher):
        return words
    if PYTHON.fullmatch(launcher):
        for option in words:
            if option == "-m":
                return words if next(words, "") == "pip" else None
            if option in {"-W", "-X", "--check-hash-based-pycs"}:
                next(words, None)
            elif not option.startswith("-") or option in {"-", "--"} or option.startswith("-c"):
                break
    return None


def positional_words(words, value_options):
    for word in words:
        if word == "--":
            yield from words
            return
        if word in value_options:
            next(words, None)
        elif not word.startswith("-"):
            yield word


def installs_rstimes(line):
    try:
        words = shlex.split(line, comments=True)
    except ValueError:
        return False
    args = pip_arguments(iter(words))
    if args is None or next(positional_words(args, GLOBAL_VALUES), None) != "install":
        return False
    return any(RSTIMES.match(word) or RSTIMES_ARCHIVE.fullmatch(PureWindowsPath(word).name)
               for word in positional_words(args, INSTALL_VALUES))


def upgrade_commands(html):
    page = BeautifulSoup(html, "html.parser")
    commands = []
    for block in page.select("main pre, main code"):
        if block.name == "code" and block.find_parent("pre") is not None:
            continue
        text = re.sub(r"\\\n[ \t]*", " ", block.get_text())
        for line in text.splitlines():
            if installs_rstimes(line):
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
