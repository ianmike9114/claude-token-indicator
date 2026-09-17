"""Orchestration: background polling thread wired to the UI strip.

The endpoint is rate-limited, so we poll on a fixed interval (default 180s) and
apply exponential backoff on failure. The tkinter UI runs on the main thread;
the worker communicates only via ``Indicator.schedule_update``.
"""

from __future__ import annotations

import threading

from . import auth, usage
from .config import Config
from .ui import Indicator

BACKOFF_START = 30.0
BACKOFF_MAX = 600.0


class App:
    def __init__(self) -> None:
        self.cfg = Config.load()
        self.ui = Indicator(self.cfg, on_refresh=self._wake, on_quit=self._stop)
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._last: usage.UsageSnapshot | None = None
        self._worker = threading.Thread(target=self._loop, daemon=True)

    # ---- control ----------------------------------------------------------
    def _wake(self) -> None:
        self._wake_event.set()

    def _stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    # ---- polling loop -----------------------------------------------------
    def _poll_once(self) -> None:
        """Fetch usage, refreshing the token on a 401. Updates the UI state."""
        try:
            token = auth.get_valid_token()
        except auth.AuthError as exc:
            self.ui.schedule_update("auth", str(exc))
            raise usage.UsageFetchError("auth") from exc

        try:
            snap = usage.fetch_usage(token)
        except usage.UsageAuthError:
            # Local token looked valid but server rejected it: force a refresh.
            try:
                token = auth.force_refresh()
                snap = usage.fetch_usage(token)
            except (auth.AuthError, usage.UsageAuthError) as exc:
                self.ui.schedule_update("auth", "re-authenticate in Claude Code")
                raise usage.UsageFetchError("auth") from exc

        self._last = snap
        self.ui.schedule_update("ok", snap)

    def _loop(self) -> None:
        backoff = BACKOFF_START
        while not self._stop_event.is_set():
            try:
                self._poll_once()
                backoff = BACKOFF_START
                wait = self.cfg.poll_seconds
            except usage.UsageFetchError:
                # Show last-good data as stale (unless we never had any).
                if self._last is not None:
                    self.ui.schedule_update("stale", self._last)
                wait = backoff
                backoff = min(backoff * 2, BACKOFF_MAX)
            except Exception as exc:  # never let the worker die silently
                self.ui.schedule_update("error", type(exc).__name__)
                wait = backoff
                backoff = min(backoff * 2, BACKOFF_MAX)

            # Sleep until the next poll, a manual refresh, or quit.
            self._wake_event.wait(timeout=wait)
            self._wake_event.clear()

    # ---- entry ------------------------------------------------------------
    def run(self) -> None:
        self._worker.start()
        self.ui.run()
        self._stop()
