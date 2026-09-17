"""The always-on-top strip: a slim, frameless tkinter window.

Renders two mini progress bars (Session / Weekly) with percentages and reset
countdowns. Runs the tkinter main loop; the polling thread pushes new data via
``schedule_update`` (thread-safe through ``root.after``).
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from datetime import datetime, timezone

from .config import Config
from .usage import UsageSnapshot, Window

# Palette (dark, matches the desktop app's usage panel vibe).
BG = "#1b1b1d"
TRACK = "#3a3a3d"
TEXT = "#e6e6e6"
MUTED = "#9a9a9f"
OK = "#4ea1ff"      # blue, like the app's session bar
WARN = "#e6b34d"    # amber
CRIT = "#ef5b5b"    # red
STALE = "#6d6d72"

BAR_W = 54
BAR_H = 5
PAD = 7
LABEL_W = 46
PCT_W = 32
RESET_W = 50
SEG_W = LABEL_W + BAR_W + PCT_W + RESET_W  # width of one Session/Weekly segment
QUIT_W = 16   # hover ✕ button area on the right
HEIGHT = 16
FONT = ("Segoe UI", 8)
FONT_BOLD = ("Segoe UI", 8, "bold")


def _icon_path() -> str | None:
    """Locate icon.ico whether running from source or a PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidate = os.path.join(base, "icon.ico")
    else:
        candidate = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets", "icon.ico",
        )
    return candidate if os.path.exists(candidate) else None


def _fmt_countdown(resets_at: datetime | None) -> str:
    if resets_at is None:
        return "—"
    now = datetime.now(timezone.utc)
    delta = (resets_at - now).total_seconds()
    if delta <= 0:
        return "now"
    d, rem = divmod(int(delta), 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d}d{h}h"
    if h:
        return f"{h}h{m}m"
    if m:
        return f"{m}m"
    return "<1m"


class Indicator:
    def __init__(self, cfg: Config, on_refresh=None, on_quit=None):
        self.cfg = cfg
        self.on_refresh = on_refresh
        self.on_quit = on_quit
        self._state = ("loading", None)
        self._drag = None
        self._hover = False

        self.root = tk.Tk()
        self.root.title("Claude Token Indicator")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.94)
        except tk.TclError:
            pass

        icon = _icon_path()
        if icon:
            try:
                self.root.iconbitmap(default=icon)
            except tk.TclError:
                pass

        width = PAD + SEG_W + (PAD + SEG_W if cfg.show_weekly else 0) + PAD + QUIT_W
        self.width = width
        self.canvas = tk.Canvas(
            self.root, width=width, height=HEIGHT, bg=BG, highlightthickness=0
        )
        self.canvas.pack()

        self._build_menu()
        self._bind_events()
        self._place_window()
        self._tick()  # starts the 1s redraw loop (keeps countdowns live)

    # ---- window placement -------------------------------------------------
    def _work_area(self) -> tuple[int, int, int, int]:
        """Screen work area (left, top, right, bottom), excluding the taskbar."""
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            if rect.right > rect.left and rect.bottom > rect.top:
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _place_window(self) -> None:
        self.root.update_idletasks()
        if self.cfg.offset_x is not None and self.cfg.offset_y is not None:
            x, y = self.cfg.offset_x, self.cfg.offset_y
            self.root.geometry(f"{self.width}x{HEIGHT}+{x}+{y}")
            return

        left, top, right, bottom = self._work_area()
        margin = 0  # flush into the corner (tray corner for bottom-right)
        pos = (self.cfg.position or "bottom-right").lower()

        if pos.endswith("right"):
            x = right - self.width - margin
        elif pos.endswith("left"):
            x = left + margin
        else:  # center
            x = (left + right - self.width) // 2

        if pos.startswith("bottom"):
            y = bottom - HEIGHT - margin
        else:  # top
            y = top

        self.root.geometry(f"{self.width}x{HEIGHT}+{x}+{y}")

    # ---- events -----------------------------------------------------------
    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Double-Button-1>", lambda _e: self._refresh())
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Button-2>", self._show_menu)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

    def _in_quit(self, x: int) -> bool:
        return x >= self.width - QUIT_W

    def _on_enter(self, _e):
        self._hover = True
        self._draw()

    def _on_leave(self, _e):
        self._hover = False
        self._draw()

    def _drag_start(self, e):
        if self._in_quit(e.x):
            self._quit()
            return
        self._drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())

    def _drag_move(self, e):
        if not self._drag:
            return
        sx, sy, ox, oy = self._drag
        self.root.geometry(f"+{ox + e.x_root - sx}+{oy + e.y_root - sy}")

    def _drag_end(self, _e):
        self._drag = None
        self.cfg.offset_x = self.root.winfo_x()
        self.cfg.offset_y = self.root.winfo_y()
        self.cfg.save()

    def _build_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Refresh now", command=self._refresh)
        self.menu.add_command(label="Reset position", command=self._reset_pos)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self._quit)

    def _show_menu(self, e):
        try:
            self.root.focus_force()
        except tk.TclError:
            pass
        try:
            # Offset up-left so the menu isn't clipped off the bottom-right corner.
            self.menu.tk_popup(e.x_root - 4, e.y_root - 4)
        finally:
            self.menu.grab_release()

    def _refresh(self):
        if self.on_refresh:
            self.on_refresh()

    def _reset_pos(self):
        self.cfg.offset_x = self.cfg.offset_y = None
        self.cfg.save()
        self._place_window()

    def _quit(self):
        if self.on_quit:
            self.on_quit()
        self.root.destroy()

    # ---- state updates ----------------------------------------------------
    def schedule_update(self, kind: str, payload=None) -> None:
        """Thread-safe entry point for the polling thread."""
        self.root.after(0, lambda: self._set_state(kind, payload))

    def _set_state(self, kind: str, payload) -> None:
        self._state = (kind, payload)
        self._draw()

    def _color_for(self, pct: float | None) -> str:
        if pct is None:
            return STALE
        if pct >= self.cfg.crit_threshold:
            return CRIT
        if pct >= self.cfg.warn_threshold:
            return WARN
        return OK

    # ---- drawing ----------------------------------------------------------
    def _tick(self):
        self._draw()
        self.root.after(1000, self._tick)

    def _draw(self):
        c = self.canvas
        c.delete("all")
        kind, payload = self._state
        self._draw_quit()

        if kind == "loading":
            c.create_text(PAD, HEIGHT // 2, anchor="w", text="Claude usage — loading…",
                          fill=MUTED, font=FONT)
            return
        if kind == "auth":
            c.create_text(PAD, HEIGHT // 2, anchor="w",
                          text="⚠ Claude auth expired — open Claude Code",
                          fill=CRIT, font=FONT)
            return
        if kind == "error":
            msg = payload or "error"
            c.create_text(PAD, HEIGHT // 2, anchor="w", text=f"Claude usage — {msg}",
                          fill=MUTED, font=FONT)
            return

        snap: UsageSnapshot = payload if kind in ("ok", "stale") else None
        if snap is None:
            return
        stale = kind == "stale"
        x = PAD
        self._draw_segment(x, "Session", snap.session, stale)
        if self.cfg.show_weekly:
            x += SEG_W + PAD
            self._draw_segment(x, "Weekly", snap.weekly, stale)

    def _draw_quit(self):
        if not self._hover:
            return
        cx = self.width - QUIT_W // 2
        self.canvas.create_text(cx, HEIGHT // 2, text="✕", fill=CRIT, font=FONT_BOLD)

    def _draw_segment(self, x: int, label: str, w: Window, stale: bool):
        c = self.canvas
        cy = HEIGHT // 2
        c.create_text(x, cy, anchor="w", text=label, fill=MUTED if stale else TEXT,
                      font=FONT)
        bx = x + LABEL_W
        by = cy - BAR_H // 2
        c.create_rectangle(bx, by, bx + BAR_W, by + BAR_H, fill=TRACK, outline="")
        pct = w.pct
        if pct is not None:
            fill = STALE if stale else self._color_for(pct)
            fw = max(2, int(BAR_W * pct / 100)) if pct > 0 else 0
            if fw:
                c.create_rectangle(bx, by, bx + fw, by + BAR_H, fill=fill, outline="")
        pct_txt = "—" if pct is None else f"{pct:.0f}%"
        c.create_text(bx + BAR_W + 6, cy, anchor="w", text=pct_txt,
                      fill=MUTED if stale else TEXT, font=FONT_BOLD)
        c.create_text(bx + BAR_W + 6 + PCT_W, cy, anchor="w",
                      text="⟳" + _fmt_countdown(w.resets_at), fill=MUTED, font=FONT)

    def run(self):
        self.root.mainloop()
