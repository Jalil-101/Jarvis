"""Developer tools: inspect, search, patch, test, git (Phase 6)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from jarvis.config_loader import Settings
from jarvis.security.paths import assert_allowed, is_forbidden_command
from jarvis.security.permissions import PermissionLevel
from jarvis.tools.registry import Tool, ToolRegistry

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".tox"}


def register_dev_tools(registry: ToolRegistry, settings: Settings) -> None:
    roots = _project_roots(settings)

    def repo_tree(project: str = "jarvis", max_entries: int = 80) -> str:
        root = _project_root(project, settings)
        entries: list[str] = []
        for path in root.rglob("*"):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            rel = str(path.relative_to(root))
            entries.append(rel + ("/" if path.is_dir() else ""))
            if len(entries) >= max_entries:
                break
        return json.dumps({"root": str(root), "entries": entries})

    def repo_search(pattern: str, project: str = "jarvis", max_hits: int = 30) -> str:
        root = _project_root(project, settings)
        hits: list[dict[str, str | int]] = []
        needle = pattern.lower()
        for path in root.rglob("*"):
            if path.is_dir() or any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".yml", ".yaml", ".toml", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if needle in line.lower():
                    hits.append({"file": str(path.relative_to(root)), "line": i, "text": line.strip()[:240]})
                    if len(hits) >= max_hits:
                        return json.dumps({"root": str(root), "hits": hits})
        return json.dumps({"root": str(root), "hits": hits})

    def repo_read(relative_path: str, project: str = "jarvis") -> str:
        root = _project_root(project, settings)
        path = assert_allowed(root / relative_path, roots)
        text = path.read_text(encoding="utf-8", errors="replace")[:20000]
        return json.dumps({"path": str(path), "content": text})

    def repo_write(relative_path: str, content: str, project: str = "jarvis") -> str:
        root = _project_root(project, settings)
        path = assert_allowed(root / relative_path, roots)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return json.dumps({"wrote": str(path)})

    def run_tests(project: str = "jarvis", extra_args: str = "") -> str:
        root = _project_root(project, settings)
        argv = ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
        if extra_args.strip():
            if is_forbidden_command(extra_args):
                raise PermissionError("Rejected extra_args.")
            argv = extra_args.split()
        completed = subprocess.run(  # noqa: S603
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=settings.shell_timeout * 4,
            check=False,
        )
        return json.dumps(
            {
                "returncode": completed.returncode,
                "stdout": (completed.stdout or "")[-6000:],
                "stderr": (completed.stderr or "")[-3000:],
            }
        )

    def git_status(project: str = "jarvis") -> str:
        root = _project_root(project, settings)
        completed = subprocess.run(
            ["git", "status", "-sb"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return json.dumps({"cwd": str(root), "status": completed.stdout, "stderr": completed.stderr})

    def git_commit(message: str, project: str = "jarvis") -> str:
        root = _project_root(project, settings)
        add = subprocess.run(["git", "add", "-A"], cwd=str(root), capture_output=True, text=True, timeout=20, check=False)
        commit = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return json.dumps(
            {
                "add": add.stdout + add.stderr,
                "commit": commit.stdout + commit.stderr,
                "returncode": commit.returncode,
            }
        )

    registry.register(
        Tool(
            "repo_tree",
            "List files in a registered project (skips .git, node_modules, .venv).",
            {
                "type": "object",
                "properties": {"project": {"type": "string"}, "max_entries": {"type": "integer"}},
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            repo_tree,
        )
    )
    registry.register(
        Tool(
            "repo_search",
            "Search text files in a registered project for a string.",
            {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "project": {"type": "string"},
                    "max_hits": {"type": "integer"},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            repo_search,
        )
    )
    registry.register(
        Tool(
            "repo_read",
            "Read a file relative to a registered project root.",
            {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}, "project": {"type": "string"}},
                "required": ["relative_path"],
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            repo_read,
        )
    )
    registry.register(
        Tool(
            "repo_write",
            "Write a file relative to a registered project root only.",
            {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "content": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["relative_path", "content"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            repo_write,
        )
    )
    registry.register(
        Tool(
            "run_tests",
            "Run the project's test suite (unittest by default).",
            {
                "type": "object",
                "properties": {"project": {"type": "string"}, "extra_args": {"type": "string"}},
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            run_tests,
        )
    )
    registry.register(
        Tool(
            "git_status",
            "Show git status -sb for a registered project.",
            {
                "type": "object",
                "properties": {"project": {"type": "string"}},
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            git_status,
        )
    )
    registry.register(
        Tool(
            "git_commit",
            "Stage all and commit in a registered project. Requires confirmation.",
            {
                "type": "object",
                "properties": {"message": {"type": "string"}, "project": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
            PermissionLevel.SENSITIVE,
            git_commit,
        )
    )


def _project_roots(settings: Settings) -> tuple[Path, ...]:
    roots = [alias.path for alias in settings.projects.values()]
    roots.append(settings.sandbox_root)
    return tuple(roots)


def _project_root(name: str, settings: Settings) -> Path:
    alias = settings.projects.get(name.lower())
    if alias:
        return alias.path
    raise ValueError(f"Unknown project '{name}'. Known: {list(settings.projects)}")
