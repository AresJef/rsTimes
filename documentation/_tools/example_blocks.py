"""Read standalone, named Python blocks and their adjacent expected output."""
from __future__ import annotations

import re
import textwrap
from typing import NamedTuple


class Block(NamedTuple):
    start: int
    end: int
    language: str
    content: str
    name: str | None


class Example(NamedTuple):
    name: str
    code: str
    output: str


ID = r"[a-z][a-z0-9-]*"
PYTHON = {"python", "python3", "py"}
MARKDOWN_FENCE = re.compile(
    r"^ {0,3}(?P<fence>\x60{3,}|~{3,})(?P<language>[^\n]*)\n"
    r"(?P<body>.*?)^ {0,3}(?P=fence)[ \t]*(?:\n|\Z)", re.M | re.S,
)
RST_DIRECTIVE = re.compile(
    r"^\.\. (?:code|code-block|sourcecode)::[ \t]*(?P<language>[^\n]+)\n"
    r"(?P<body>(?:(?:[ \t]+[^\n]*|[ \t]*)(?:\n|\Z))+)", re.M,
)
OPTIONS = re.compile(r"^(?::[\w-]+:[^\n]*\n)+[ \t]*\n")


def directive_content(body):
    options = OPTIONS.match(body)
    if options is None:
        return body.lstrip("\n"), None
    name = re.search(r"^:name:[ \t]+(" + ID + r")[ \t]*$", options[0], re.M)
    return body[options.end():], name[1] if name else None


def markdown_blocks(text):
    for match in MARKDOWN_FENCE.finditer(text):
        language = match["language"].strip()
        body, name = match["body"], None
        directive = re.fullmatch(r"\{(?:code|code-block|sourcecode)\}\s+(\S+)", language)
        if directive:
            language = directive[1]
            body, name = directive_content(body)
        if language in PYTHON and name is None:
            label = re.search(r"^\((" + ID + r")\)=[ \t]*\n[ \t\n]*\Z", text[:match.start()], re.M)
            name = label[1] if label else None
        yield Block(match.start(), match.end(), language, body, name)


def rst_blocks(text):
    for match in RST_DIRECTIVE.finditer(text):
        body, name = directive_content(textwrap.dedent(match["body"]).lstrip("\n"))
        if match["language"].strip() in PYTHON and name is None:
            label = re.search(r"^\.\. _(" + ID + r"):[ \t]*\n[ \t\n]*\Z", text[:match.start()], re.M)
            name = label[1] if label else None
        yield Block(match.start(), match.end(), match["language"].strip(), body, name)


def scan_examples(text, suffix):
    """Every ordinary Python example has an ID and its own output block."""
    blocks = iter(rst_blocks(text) if suffix == ".rst" else markdown_blocks(text))
    examples = []
    for block in blocks:
        if block.language not in PYTHON:
            continue
        if block.name is None:
            raise ValueError(f"Python block at line {text[:block.start].count(chr(10)) + 1} needs an example ID")
        output = next(blocks, None)
        between = text[block.end:output.start].strip() if output else ""
        if output is None or output.language not in {"text", "none"} or between not in {"Output", "**Output**"}:
            raise ValueError(f"{block.name}: put an Output text block immediately after the code")
        code = block.content.rstrip("\n")
        if not code.strip():
            raise ValueError(f"{block.name}: empty Python block")
        examples.append(Example(block.name, code, output.content.rstrip("\n")))
    names = [example.name for example in examples]
    if len(names) != len(set(names)):
        raise ValueError("Example IDs must be unique within a page")
    return examples
