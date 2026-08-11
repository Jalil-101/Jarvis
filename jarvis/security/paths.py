"""Path allowlists and dangerous-command denylist."""

from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_COMMAND = re.compile(
    r"""
    (
        \brm\s+-rf\s+[/\\]
        | \bsudo\b
        | \bmkfs\b
        | \bformat\s+[a-z]:
        | :\(\)\s*\{
        | \bdd\s+if=
        | >\s*/dev/sd
        | \bshutdown\b
        | \breboot\b
        | \bpasswd\b
        | \bchmod\s+-R\s+777\s+/
        | \bdel\s+/[sf]
        | \brd\s+/s
        | \bRemove-Item\s+-Recurse\s+C:\\
        | \bcygstart\b
        | \bcurl\s+[^\n]*\|\s*sh
        | \bwget\s+[^\n]*\|\s*sh
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

WRITEISH = re.compile(
    r"\b(rm|del|rmdir|rd|mv|move|chmod|chown|kill|taskkill|Set-Content|Remove-Item|ren|rename)\b",
    re.IGNORECASE,
)


def is_forbidden_command(command: str) -> bool:
    return bool(FORBIDDEN_COMMAND.search(command))


def looks_writeish(command: str) -> bool:
    return bool(WRITEISH.search(command))


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def assert_allowed(path: Path, allowed_roots: tuple[Path, ...] | list[Path]) -> Path:
    resolved = path.expanduser().resolve()
    for root in allowed_roots:
        try:
            root_res = root.expanduser().resolve()
        except OSError:
            continue
        if is_under(resolved, root_res) or resolved == root_res:
            return resolved
    raise PermissionError(f"Path not in allowlist: {resolved}")
