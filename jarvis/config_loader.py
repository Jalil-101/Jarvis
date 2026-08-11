"""Load YAML defaults and environment secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    model: str
    max_tokens: int
    max_history_turns: int
    db_path: Path
    audit_log_path: Path
    data_dir: Path
    sandbox_root: Path


def _repo_root() -> Path:
    return _REPO_ROOT


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(_repo_root() / ".env")
    cfg = _load_yaml(_repo_root() / "config" / "default.yaml")

    data_dir = Path(
        os.getenv("JARVIS_DATA_DIR", cfg.get("data_dir", "data"))
    )
    if not data_dir.is_absolute():
        data_dir = _repo_root() / data_dir

    db_path = Path(os.getenv("JARVIS_DB_PATH", cfg.get("db_path", str(data_dir / "jarvis.db"))))
    if not db_path.is_absolute():
        db_path = _repo_root() / db_path

    audit_log_path = Path(
        os.getenv("JARVIS_AUDIT_LOG", cfg.get("audit_log_path", str(data_dir / "audit.jsonl")))
    )
    if not audit_log_path.is_absolute():
        audit_log_path = _repo_root() / audit_log_path

    sandbox = Path(cfg.get("sandbox_root", str(data_dir / "sandbox")))
    if not sandbox.is_absolute():
        sandbox = _repo_root() / sandbox

    llm = cfg.get("llm", {}) if isinstance(cfg.get("llm"), dict) else {}

    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        model=os.getenv("JARVIS_MODEL", llm.get("model", "claude-sonnet-4-20250514")),
        max_tokens=int(os.getenv("JARVIS_MAX_TOKENS", llm.get("max_tokens", 1024))),
        max_history_turns=int(cfg.get("max_history_turns", 20)),
        db_path=db_path,
        audit_log_path=audit_log_path,
        data_dir=data_dir,
        sandbox_root=sandbox,
    )
