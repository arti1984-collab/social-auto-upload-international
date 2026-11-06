"""Rewrite single top-level assignments in conf.py.

Only the named settings change: comments, order and unrelated lines stay as they
are, and a missing setting is appended once at the end of the file.
"""
from __future__ import annotations

import re
from pathlib import Path

ASSIGNMENT = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>.*)$")


def conf_path() -> Path:
    """The conf.py this process imported."""
    import conf

    return Path(conf.__file__).resolve()


def set_conf_values(values: dict[str, str], *, path: str | Path | None = None) -> Path:
    """Set each top-level assignment to the given Python literal and return the file."""
    target = Path(path) if path else conf_path()
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    pending = dict(values)
    lines: list[str] = []
    for line in text.splitlines():
        match = ASSIGNMENT.match(line)
        if match and match.group("name") in pending:
            name = match.group("name")
            lines.append(f"{name} = {pending.pop(name)}")
        else:
            lines.append(line)
    if pending:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Default profile set by `sau profile use`")
        lines.extend(f"{name} = {value}" for name, value in pending.items())
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
