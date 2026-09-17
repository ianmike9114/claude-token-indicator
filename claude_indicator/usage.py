"""Fetch and normalize Claude subscription usage.

Calls the undocumented endpoint behind Claude Code's ``/usage`` command:

    GET https://api.anthropic.com/api/oauth/usage

Response shape (fields are undocumented and may drift, so parsing is
defensive)::

    {
      "five_hour":  {"utilization": 8.0, "resets_at": "2026-01-03T09:00:00Z"},
      "seven_day":  {"utilization": 7.0, "resets_at": "2026-01-08T08:00:00Z"},
      "seven_day_opus":   {...},
      "seven_day_sonnet": {...}
    }

``utilization`` is a percentage (0-100); ``resets_at`` is ISO-8601 UTC or null
when the window is inactive.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from . import auth

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


class UsageAuthError(Exception):
    """The access token was rejected (HTTP 401); a refresh is needed."""


class UsageFetchError(Exception):
    """A transient failure (network, 429, 5xx). Keep showing last-good data."""


@dataclass
class Window:
    pct: float | None
    resets_at: datetime | None


@dataclass
class UsageSnapshot:
    session: Window
    weekly: Window
    fetched_at: datetime


def _parse_dt(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        # Python's fromisoformat handles the trailing 'Z' from 3.11+; be safe.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _pct(block) -> float | None:
    """Extract a 0-100 percentage from a window block, tolerating variants."""
    if not isinstance(block, dict):
        return None
    for key in ("utilization", "percent", "percentage", "used_pct"):
        if key in block and block[key] is not None:
            try:
                return max(0.0, min(100.0, float(block[key])))
            except (TypeError, ValueError):
                continue
    return None


def _window(block) -> Window:
    if not isinstance(block, dict):
        return Window(pct=None, resets_at=None)
    return Window(pct=_pct(block), resets_at=_parse_dt(block.get("resets_at")))


def parse_usage(data: dict) -> UsageSnapshot:
    return UsageSnapshot(
        session=_window(data.get("five_hour")),
        weekly=_window(data.get("seven_day")),
        fetched_at=datetime.now(timezone.utc),
    )


def fetch_usage(token: str, timeout: float = 20.0) -> UsageSnapshot:
    """Fetch a fresh usage snapshot.

    Raises ``UsageAuthError`` on 401 (caller should refresh the token) and
    ``UsageFetchError`` on transient failures.
    """
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "Accept": "application/json",
            "User-Agent": auth.USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return parse_usage(json.load(resp))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise UsageAuthError("access token rejected") from exc
        raise UsageFetchError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UsageFetchError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise UsageFetchError(f"bad response: {exc}") from exc
