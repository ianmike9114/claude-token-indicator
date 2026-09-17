"""Render assets/demo.gif — hover ✕ and refresh, driven through the real UI.

Uses the actual claude_indicator.ui.Indicator so the frames match the app,
toggling hover and pushing snapshots in-process (synthetic mouse moves don't
fire tkinter's <Enter>), and grabbing the window region with PIL.ImageGrab.
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageGrab

from claude_indicator.config import Config
from claude_indicator.ui import HEIGHT, Indicator
from claude_indicator.usage import UsageSnapshot, Window

X, Y = 965, 712  # flush bottom-right on this screen


def snap(sess, wk, sess_min, wk_h):
    now = datetime.now(timezone.utc)
    return UsageSnapshot(
        session=Window(sess, now + timedelta(minutes=sess_min)),
        weekly=Window(wk, now + timedelta(hours=wk_h)),
        fetched_at=now,
    )


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = Config()
    cfg.offset_x, cfg.offset_y = X, Y  # force fixed on-screen position
    ind = Indicator(cfg)
    ind._set_state("ok", snap(12, 49, 227, 10))
    ind.root.update()
    time.sleep(0.3)

    bbox = (X, Y, X + ind.width, Y + HEIGHT)
    frames, durs = [], []

    def grab(hold):
        ind.root.update()
        time.sleep(0.05)
        frames.append(ImageGrab.grab(bbox).convert("RGB"))
        durs.append(hold)

    # idle
    ind._hover = False; ind._draw(); grab(900)
    # hover -> X appears
    ind._hover = True; ind._draw(); grab(1100)
    # "refresh": numbers/countdown update while hovered
    ind._set_state("ok", snap(13, 49, 224, 10)); grab(700)
    ind._set_state("ok", snap(2, 49, 300, 10)); grab(1100)
    # leave -> X gone
    ind._hover = False; ind._draw(); grab(900)

    ind.root.destroy()

    scale, m = 2, 10
    big = [f.resize((f.width * scale, f.height * scale), Image.NEAREST) for f in frames]
    canv = []
    for b in big:
        c = Image.new("RGB", (b.width + m * 2, b.height + m * 2), (14, 14, 16))
        c.paste(b, (m, m))
        canv.append(c)
    out = os.path.join(here, "demo.gif")
    canv[0].save(out, save_all=True, append_images=canv[1:], duration=durs,
                 loop=0, optimize=True)
    print("wrote", out, canv[0].size, "frames", len(canv))


if __name__ == "__main__":
    main()
