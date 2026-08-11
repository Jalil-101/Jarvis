"""Load YAML defaults and environment secrets."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ProjectAlias:
    name: str
    path: Path
    stack: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    model: str
    max_tokens: int
    max_tool_rounds: int
    max_history_turns: int
    db_path: Path
    audit_log_path: Path
    data_dir: Path
    sandbox_root: Path
    tts_provider: str
    tts_voice: str
    wake_word: str
    stt_model: str
    session_silence_seconds: float
    acknowledgment: str
    max_autonomous_level: int
    confirm_timeout_seconds: int
    location_name: str
    latitude: float
    longitude: float
    allow_read_paths: tuple[Path, ...]
    allow_write_paths: tuple[Path, ...]
    projects: dict[str, ProjectAlias]
    shell_timeout: int
    allowlisted_commands: dict[str, list[str]]
    quiet_hours_start: int
    quiet_hours_end: int
    max_proactive_per_hour: int
    importance_threshold: float
    server_host: str
    server_port: int
    api_token: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def repo_root() -> Path:
    return _REPO_ROOT


def default_data_dir() -> Path:
    """Linux body uses XDG so git pulls never wipe memory. Windows workshop uses ./data."""
    env = os.getenv("JARVIS_DATA_DIR")
    if env:
        p = Path(env).expanduser()
        return p if p.is_absolute() else _REPO_ROOT / p
    if sys.platform.startswith("linux"):
        xdg = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
        return xdg / "jarvis"
    return _REPO_ROOT / "data"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def _expand_path(raw: str, *, sandbox: Path, data_dir: Path) -> Path:
    mapping = {
        "{repo}": str(_REPO_ROOT),
        "{home}": str(Path.home()),
        "{sandbox}": str(sandbox),
        "{data}": str(data_dir),
        "{python}": sys.executable,
    }
    text = raw
    for key, value in mapping.items():
        text = text.replace(key, value)
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.resolve()


def reset_settings_cache() -> None:
    get_settings.cache_clear()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(
        _REPO_ROOT / ".env",
        encoding="utf-8-sig",
        override=True,
        interpolate=False,
    )
    cfg = _load_yaml(_REPO_ROOT / "config" / "default.yaml")

    data_dir = default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    db_name = os.getenv("JARVIS_DB_PATH", cfg.get("db_path", "jarvis.db"))
    db_path = Path(db_name)
    if not db_path.is_absolute():
        db_path = data_dir / db_path

    audit_name = os.getenv("JARVIS_AUDIT_LOG", cfg.get("audit_log_path", "audit.jsonl"))
    audit_log_path = Path(audit_name)
    if not audit_log_path.is_absolute():
        audit_log_path = data_dir / audit_log_path

    sandbox = _expand_path(
        str(cfg.get("sandbox_root", "{data}/sandbox")),
        sandbox=data_dir / "sandbox",
        data_dir=data_dir,
    )
    sandbox.mkdir(parents=True, exist_ok=True)

    llm = cfg.get("llm", {}) if isinstance(cfg.get("llm"), dict) else {}
    voice = cfg.get("voice", {}) if isinstance(cfg.get("voice"), dict) else {}
    perms = cfg.get("permissions", {}) if isinstance(cfg.get("permissions"), dict) else {}
    loc = cfg.get("location", {}) if isinstance(cfg.get("location"), dict) else {}
    shell = cfg.get("shell", {}) if isinstance(cfg.get("shell"), dict) else {}
    autonomy = cfg.get("autonomy", {}) if isinstance(cfg.get("autonomy"), dict) else {}
    server = cfg.get("server", {}) if isinstance(cfg.get("server"), dict) else {}

    allow_read = tuple(
        _expand_path(p, sandbox=sandbox, data_dir=data_dir)
        for p in cfg.get("allow_read_paths", ["{sandbox}"])
    )
    allow_write = tuple(
        _expand_path(p, sandbox=sandbox, data_dir=data_dir)
        for p in cfg.get("allow_write_paths", ["{sandbox}"])
    )

    projects: dict[str, ProjectAlias] = {}
    raw_projects = cfg.get("projects", {}) if isinstance(cfg.get("projects"), dict) else {}
    for name, spec in raw_projects.items():
        if isinstance(spec, str):
            spec = {"path": spec}
        path = _expand_path(str(spec.get("path", ".")), sandbox=sandbox, data_dir=data_dir)
        projects[name.lower()] = ProjectAlias(
            name=name,
            path=path,
            stack=str(spec.get("stack", "")),
            notes=str(spec.get("notes", "")),
        )

    allowlisted: dict[str, list[str]] = {}
    raw_cmds = shell.get("allowlisted_commands", {}) if isinstance(shell, dict) else {}
    for name, argv in raw_cmds.items():
        if isinstance(argv, list):
            allowlisted[str(name)] = [
                str(_expand_path(a, sandbox=sandbox, data_dir=data_dir))
                if "{python}" in str(a) or str(a).startswith("{")
                else str(a).replace("{python}", sys.executable)
                for a in argv
            ]

    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        model=os.getenv("JARVIS_MODEL", llm.get("model", "claude-sonnet-5")),
        max_tokens=int(os.getenv("JARVIS_MAX_TOKENS", llm.get("max_tokens", 2048))),
        max_tool_rounds=int(llm.get("max_tool_rounds", 8)),
        max_history_turns=int(cfg.get("max_history_turns", 20)),
        db_path=db_path,
        audit_log_path=audit_log_path,
        data_dir=data_dir,
        sandbox_root=sandbox,
        tts_provider=str(voice.get("tts_provider", "edge-tts")),
        tts_voice=os.getenv("JARVIS_TTS_VOICE", voice.get("tts_voice", "en-GB-RyanNeural")),
        wake_word=str(voice.get("wake_word", "jarvis")),
        stt_model=str(voice.get("stt_model", "base")),
        session_silence_seconds=float(voice.get("session_silence_seconds", 8)),
        acknowledgment=str(voice.get("acknowledgment", "Yes, sir?")),
        max_autonomous_level=int(perms.get("max_autonomous_level", 2)),
        confirm_timeout_seconds=int(perms.get("confirm_timeout_seconds", 30)),
        location_name=str(loc.get("name", "Columbus, Ohio")),
        latitude=float(loc.get("latitude", 39.9612)),
        longitude=float(loc.get("longitude", -82.9988)),
        allow_read_paths=allow_read,
        allow_write_paths=allow_write,
        projects=projects,
        shell_timeout=int(shell.get("timeout_seconds", 30)),
        allowlisted_commands=allowlisted,
        quiet_hours_start=int(autonomy.get("quiet_hours_start", 22)),
        quiet_hours_end=int(autonomy.get("quiet_hours_end", 7)),
        max_proactive_per_hour=int(autonomy.get("max_proactive_per_hour", 4)),
        importance_threshold=float(autonomy.get("importance_threshold", 0.6)),
        server_host=str(server.get("host", "127.0.0.1")),
        server_port=int(os.getenv("JARVIS_PORT", server.get("port", 8787))),
        api_token=os.getenv("JARVIS_API_TOKEN", "").strip(),
    )
