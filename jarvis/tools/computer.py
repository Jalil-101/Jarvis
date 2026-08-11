"""Computer control: sandbox (Phase 1) and allowlisted hands (Phase 3)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from jarvis.config_loader import Settings
from jarvis.security.paths import assert_allowed, is_forbidden_command, looks_writeish
from jarvis.security.permissions import PermissionLevel
from jarvis.tools.registry import Tool, ToolRegistry


def register_computer_tools(registry: ToolRegistry, settings: Settings) -> None:
    sandbox = settings.sandbox_root

    def list_sandbox(path: str = ".") -> str:
        target = assert_allowed(sandbox / path, (sandbox,))
        if not target.exists():
            return json.dumps({"error": "not found", "path": str(target)})
        if target.is_file():
            return json.dumps({"path": str(target), "type": "file", "size": target.stat().st_size})
        entries = []
        for child in sorted(target.iterdir()):
            entries.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
        return json.dumps({"path": str(target), "entries": entries})

    def create_folder(path: str) -> str:
        target = assert_allowed(sandbox / path, (sandbox,))
        target.mkdir(parents=True, exist_ok=True)
        return json.dumps({"created": str(target)})

    def open_path(path: str) -> str:
        target = assert_allowed(_resolve_user_path(path, settings), settings.allow_read_paths)
        if not target.exists():
            raise FileNotFoundError(str(target))
        _open_with_os(target)
        return json.dumps({"opened": str(target)})

    def run_allowlisted_command(name: str) -> str:
        argv = settings.allowlisted_commands.get(name)
        if not argv:
            return json.dumps(
                {
                    "error": "unknown command",
                    "allowed": list(settings.allowlisted_commands),
                }
            )
        return _run(argv, cwd=sandbox, timeout=settings.shell_timeout)

    def get_system_info() -> str:
        info = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "hostname": platform.node(),
            "cwd": os.getcwd(),
            "sandbox": str(sandbox),
            "data_dir": str(settings.data_dir),
        }
        try:
            usage = shutil.disk_usage(settings.data_dir)
            info["disk_free_gb"] = round(usage.free / 1024**3, 2)
        except OSError:
            pass
        return json.dumps(info)

    def list_dir(path: str) -> str:
        target = assert_allowed(_resolve_user_path(path, settings), settings.allow_read_paths)
        if not target.is_dir():
            return json.dumps({"error": "not a directory", "path": str(target)})
        entries = sorted(p.name for p in target.iterdir())[:200]
        return json.dumps({"path": str(target), "entries": entries})

    def read_file(path: str, max_bytes: int = 20000) -> str:
        target = assert_allowed(_resolve_user_path(path, settings), settings.allow_read_paths)
        if not target.is_file():
            raise FileNotFoundError(str(target))
        data = target.read_bytes()[: max(1, min(max_bytes, 200_000))]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return json.dumps({"path": str(target), "content": text})

    def write_file(path: str, content: str) -> str:
        target = assert_allowed(_resolve_user_path(path, settings), settings.allow_write_paths)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return json.dumps({"wrote": str(target), "bytes": len(content.encode("utf-8"))})

    def delete_path(path: str) -> str:
        target = assert_allowed(_resolve_user_path(path, settings), settings.allow_write_paths)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        else:
            raise FileNotFoundError(str(target))
        return json.dumps({"deleted": str(target)})

    def launch_app(name_or_path: str) -> str:
        alias = settings.projects.get(name_or_path.lower())
        if alias:
            _open_with_os(alias.path)
            return json.dumps({"launched": str(alias.path), "project": alias.name})
        known = {
            "vscode": "code",
            "code": "code",
            "cursor": "cursor",
            "notepad": "notepad",
            "explorer": "explorer",
            "browser": _default_browser(),
        }
        target = known.get(name_or_path.lower(), name_or_path)
        path = Path(target)
        if path.exists():
            assert_allowed(path, settings.allow_read_paths)
            _open_with_os(path)
            return json.dumps({"launched": str(path)})
        subprocess.Popen([target], shell=False)  # noqa: S603
        return json.dumps({"launched": target})

    def run_terminal(command: str, cwd: str = "") -> str:
        if is_forbidden_command(command):
            raise PermissionError("Command matches the dangerous denylist.")
        work = sandbox if not cwd else _resolve_user_path(cwd, settings)
        work = assert_allowed(work, settings.allow_read_paths)
        if looks_writeish(command):
            decision = registry.gate.authorize(
                "run_terminal.writeish",
                PermissionLevel.SENSITIVE,
                detail={"command": command},
            )
            if not decision.allowed:
                return json.dumps({"error": "permission_denied", "reason": decision.reason})
        return _run(command, cwd=work, timeout=settings.shell_timeout, shell=True)

    def get_clipboard() -> str:
        text = _clipboard_get()
        return json.dumps({"clipboard": text})

    def set_clipboard(text: str) -> str:
        _clipboard_set(text)
        return json.dumps({"ok": True, "n": len(text)})

    def take_screenshot() -> str:
        out = settings.data_dir / "screenshots"
        out.mkdir(parents=True, exist_ok=True)
        dest = out / "latest.png"
        _screenshot(dest)
        return json.dumps({"path": str(dest)})

    def read_document(path: str) -> str:
        target = assert_allowed(_resolve_user_path(path, settings), settings.allow_read_paths)
        suffix = target.suffix.lower()
        if suffix == ".pdf":
            return json.dumps({"path": str(target), "content": _read_pdf(target)})
        return read_file(str(target))

    def resolve_project(name: str) -> str:
        alias = settings.projects.get(name.lower())
        if not alias:
            return json.dumps({"error": "unknown project", "known": list(settings.projects)})
        return json.dumps(
            {
                "name": alias.name,
                "path": str(alias.path),
                "stack": alias.stack,
                "notes": alias.notes,
            }
        )

    registry.register(
        Tool(
            "list_sandbox",
            "List files in the Jarvis sandbox workspace (safe).",
            _object_schema({"path": "Relative path inside the sandbox."}),
            PermissionLevel.READ,
            list_sandbox,
        )
    )
    registry.register(
        Tool(
            "create_folder",
            "Create a folder inside the Jarvis sandbox.",
            _object_schema({"path": "Relative folder path inside the sandbox.", "type": "string"}, required=["path"]),
            PermissionLevel.LOW_RISK,
            create_folder,
        )
    )
    registry.register(
        Tool(
            "open_path",
            "Open a file or folder with the OS default application.",
            _object_schema({"path": "Path or sandbox-relative path.", "type": "string"}, required=["path"]),
            PermissionLevel.LOW_RISK,
            open_path,
        )
    )
    registry.register(
        Tool(
            "run_allowlisted_command",
            "Run a named allowlisted command (whoami, hostname, date, python_version, git_version, disk).",
            _object_schema({"name": "Allowlisted command name.", "type": "string"}, required=["name"]),
            PermissionLevel.LOW_RISK,
            run_allowlisted_command,
        )
    )
    registry.register(
        Tool(
            "get_system_info",
            "Read host OS, hostname, Python version, and disk free space.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            get_system_info,
        )
    )
    registry.register(
        Tool(
            "list_dir",
            "List a directory if it is under an allowlisted read path.",
            _object_schema({"path": "Directory path or project alias.", "type": "string"}, required=["path"]),
            PermissionLevel.READ,
            list_dir,
        )
    )
    registry.register(
        Tool(
            "read_file",
            "Read a UTF-8 text file from an allowlisted path.",
            _object_schema(
                {"path": {"type": "string"}, "max_bytes": {"type": "integer"}},
                required=["path"],
            ),
            PermissionLevel.READ,
            read_file,
        )
    )
    registry.register(
        Tool(
            "write_file",
            "Write a text file under an allowlisted write path (sandbox or registered projects).",
            _object_schema(
                {"path": {"type": "string"}, "content": {"type": "string"}},
                required=["path", "content"],
            ),
            PermissionLevel.LOW_RISK,
            write_file,
        )
    )
    registry.register(
        Tool(
            "delete_path",
            "Delete a file or folder under an allowlisted write path. Requires confirmation.",
            _object_schema({"path": {"type": "string"}}, required=["path"]),
            PermissionLevel.SENSITIVE,
            delete_path,
        )
    )
    registry.register(
        Tool(
            "launch_app",
            "Launch an application, editor, or named project (e.g. jarvis, cursor, vscode).",
            _object_schema({"name_or_path": {"type": "string"}}, required=["name_or_path"]),
            PermissionLevel.LOW_RISK,
            launch_app,
        )
    )
    registry.register(
        Tool(
            "run_terminal",
            "Run a shell command in an allowlisted directory with timeout. Dangerous patterns are denied.",
            _object_schema(
                {"command": {"type": "string"}, "cwd": {"type": "string"}},
                required=["command"],
            ),
            PermissionLevel.LOW_RISK,
            run_terminal,
        )
    )
    registry.register(
        Tool(
            "get_clipboard",
            "Read the current clipboard text.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            get_clipboard,
        )
    )
    registry.register(
        Tool(
            "set_clipboard",
            "Set the clipboard text.",
            _object_schema({"text": {"type": "string"}}, required=["text"]),
            PermissionLevel.LOW_RISK,
            set_clipboard,
        )
    )
    registry.register(
        Tool(
            "take_screenshot",
            "Capture the screen to the Jarvis data directory (read-only snapshot).",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            take_screenshot,
        )
    )
    registry.register(
        Tool(
            "read_document",
            "Read a text or PDF document from an allowlisted path.",
            _object_schema({"path": {"type": "string"}}, required=["path"]),
            PermissionLevel.READ,
            read_document,
        )
    )
    registry.register(
        Tool(
            "resolve_project",
            "Resolve a project alias (e.g. jarvis, shiplink) to its path and notes.",
            _object_schema({"name": {"type": "string"}}, required=["name"]),
            PermissionLevel.READ,
            resolve_project,
        )
    )


def _object_schema(properties: dict, required: list[str] | None = None) -> dict:
    props = {}
    for key, spec in properties.items():
        props[key] = spec if isinstance(spec, dict) else {"type": "string", "description": str(spec)}
    schema: dict = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


def _resolve_user_path(path: str, settings: Settings) -> Path:
    alias = settings.projects.get(path.lower())
    if alias:
        return alias.path
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw
    return settings.sandbox_root / path


def _open_with_os(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])  # noqa: S603
    else:
        subprocess.Popen(["xdg-open", str(path)])  # noqa: S603


def _default_browser() -> str:
    if sys.platform.startswith("win"):
        return "msedge"
    return "xdg-open"


def _run(argv: list[str] | str, *, cwd: Path, timeout: int, shell: bool = False) -> str:
    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "timeout", "seconds": timeout})
    out = (completed.stdout or "")[-8000:]
    err = (completed.stderr or "")[-2000:]
    return json.dumps({"returncode": completed.returncode, "stdout": out, "stderr": err})


def _clipboard_get() -> str:
    try:
        import pyperclip  # type: ignore

        return pyperclip.paste() or ""
    except Exception:
        pass
    if sys.platform.startswith("win"):
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return completed.stdout
    if shutil.which("xclip"):
        completed = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return completed.stdout
    raise RuntimeError("Clipboard not available (install pyperclip or xclip).")


def _clipboard_set(text: str) -> None:
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return
    except Exception:
        pass
    if sys.platform.startswith("win"):
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard", "-Value", text],
            check=False,
            timeout=10,
        )
        return
    if shutil.which("xclip"):
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
            check=False,
            timeout=10,
        )
        return
    raise RuntimeError("Clipboard not available.")


def _screenshot(dest: Path) -> None:
    try:
        import mss  # type: ignore

        with mss.mss() as sct:
            sct.shot(output=str(dest))
        return
    except Exception:
        pass
    try:
        from PIL import ImageGrab  # type: ignore

        image = ImageGrab.grab()
        image.save(dest)
        return
    except Exception:
        pass
    raise RuntimeError("Screenshot support not installed. pip install mss Pillow")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages[:20]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)[:20000]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"PDF read failed (pip install pypdf): {exc}") from exc
