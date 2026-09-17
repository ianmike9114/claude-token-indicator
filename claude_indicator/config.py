"""User-tweakable configuration, persisted to config.json next to the app."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass

DEFAULT_POLL_SECONDS = 180
MIN_POLL_SECONDS = 60  # the usage endpoint is rate-limited; don't poll faster


def _config_path() -> str:
    # When frozen (PyInstaller onefile) __file__ lives in a temp extract dir
    # that is wiped each run, so anchor config to the exe's own folder instead.
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config.json")


@dataclass
class Config:
    poll_seconds: int = DEFAULT_POLL_SECONDS
    # top/bottom + left/center/right, e.g. "bottom-right", "top-center"
    position: str = "bottom-right"
    offset_x: int | None = None   # manual position (set by dragging)
    offset_y: int | None = None
    show_weekly: bool = True
    warn_threshold: float = 60.0
    crit_threshold: float = 85.0

    @classmethod
    def load(cls) -> "Config":
        path = _config_path()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return cls()
        known = {k: data[k] for k in cls().__dict__ if k in data}
        cfg = cls(**known)
        cfg.poll_seconds = max(MIN_POLL_SECONDS, int(cfg.poll_seconds))
        return cfg

    def save(self) -> None:
        path = _config_path()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2)
        except OSError:
            pass  # a failed settings write must never crash the indicator
