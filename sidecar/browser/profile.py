"""Browser profile management — fingerprint persistence and user data dirs."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from loguru import logger


@dataclass
class BrowserProfile:
    """A persistent browser profile with fingerprint and user data."""
    id: str
    name: str
    fingerprint: dict[str, Any] = field(default_factory=dict)
    user_data_dir: str = ""
    proxy: dict | None = None
    os_target: str = "windows"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BrowserProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def get_profiles_dir() -> Path:
    """Get the base directory for storing browser profiles."""
    base = Path(os.environ.get("MIMICRY_DATA_DIR", Path.home() / ".mimicry"))
    profiles_dir = base / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir


def get_profile_data_dir(profile_id: str) -> str:
    """Get the user_data_dir path for a given profile."""
    p = get_profiles_dir() / profile_id
    p.mkdir(parents=True, exist_ok=True)
    return str(p)
