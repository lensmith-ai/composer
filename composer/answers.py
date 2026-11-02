"""Answers files for a setup with no questions: `composer setup --answers answers.toml` (or .json).

The TOML read here is a small, strict subset that works the same on every Python Composer supports
(tomllib only exists from 3.11): [section] headers, `key = value` with a "string", true/false, a whole number,
or a one-line list of strings, and # comments. Anything else is an error that names the line.

A key is never written in an answers file. Name the environment variable that holds it instead:

    [provider]
    kind = "anthropic"
    key_from_env = "ANTHROPIC_API_KEY"   # read once at setup and stored in the 0600 key file
    # or: key = "env"                    # keep using the variable at run time; nothing is stored
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SECTIONS = {
    "install": {"home": str, "python_download": bool},
    "provider": {"kind": str, "model": str, "base_url": str, "key": str, "key_from_env": str},
    "sources": {"hacker_news": bool, "add": list},
    "narration": {"enabled": bool, "use": str, "accept_licences": bool, "url": str},
    "schedule": {"enabled": bool, "time": str, "timezone": str, "sources": list, "lens": str, "insights": int},
    "server": {"port": int},
    "backup": {"weekly": bool, "keep": int},
}
_LINE_HEADER = re.compile(r"^\[([a-z_]+)\]$")
_LINE_PAIR = re.compile(r"^([a-z_]+)\s*=\s*(.+)$")
_STRING = re.compile(r'^"((?:[^"\\]|\\["\\nt])*)"$')


class AnswersError(ValueError):
    pass


def _value(raw: str, where: str):
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?[0-9]+", raw):
        return int(raw)
    m = _STRING.match(raw)
    if m:
        return m.group(1).replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        items, rest = [], inner
        while rest:
            m = re.match(r'^"((?:[^"\\]|\\["\\])*)"\s*(,\s*|$)', rest)
            if not m:
                raise AnswersError(f"{where}: a list may only hold \"strings\"")
            items.append(m.group(1).replace('\\"', '"').replace("\\\\", "\\"))
            rest = rest[m.end():]
        return items
    raise AnswersError(f"{where}: cannot read the value {raw[:40]!r}")


def _strip_comment(line: str) -> str:
    out, quoted, escaped = [], False, False
    for ch in line:
        if escaped:
            escaped = False
        elif ch == "\\" and quoted:
            escaped = True
        elif ch == '"':
            quoted = not quoted
        elif ch == "#" and not quoted:
            break
        out.append(ch)
    return "".join(out).strip()


def parse_toml(text: str, name: str = "answers") -> dict:
    doc: dict = {}
    section = None
    for number, line in enumerate(text.splitlines(), 1):
        line = _strip_comment(line)
        if not line:
            continue
        where = f"{name} line {number}"
        m = _LINE_HEADER.match(line)
        if m:
            section = m.group(1)
            if section in doc:
                raise AnswersError(f"{where}: [{section}] appears twice")
            doc[section] = {}
            continue
        m = _LINE_PAIR.match(line)
        if not m or section is None:
            raise AnswersError(f"{where}: expected [section] or key = value inside a section")
        key = m.group(1)
        if key in doc[section]:
            raise AnswersError(f"{where}: {key} appears twice")
        doc[section][key] = _value(m.group(2), where)
    return doc


def load(path: str | Path) -> dict:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise AnswersError(f"cannot read {p}: {exc}") from None
    if p.suffix.lower() == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AnswersError(f"{p}: not valid JSON ({exc.msg}, line {exc.lineno})") from None
    else:
        doc = parse_toml(text, p.name)
    return check(doc)


def check(doc: dict) -> dict:
    if not isinstance(doc, dict):
        raise AnswersError("an answers file is a set of sections")
    for section, values in doc.items():
        if section not in SECTIONS:
            raise AnswersError(f"unknown section [{section}]; known: {', '.join(SECTIONS)}")
        if not isinstance(values, dict):
            raise AnswersError(f"[{section}] must hold key = value lines")
        for key, value in values.items():
            want = SECTIONS[section].get(key)
            if want is None:
                raise AnswersError(f"[{section}] has an unknown key {key!r}; known: {', '.join(SECTIONS[section])}")
            if not isinstance(value, want) or (want is int and isinstance(value, bool)):
                raise AnswersError(f"[{section}] {key} must be a {want.__name__}")
    provider = doc.get("provider", {})
    if "key" in provider and provider["key"] not in ("env", "none"):
        raise AnswersError("[provider] key may only be \"env\" or \"none\"; never put a key in a file. "
                           "Use key_from_env = \"ANTHROPIC_API_KEY\" to store it from a variable.")
    return doc
