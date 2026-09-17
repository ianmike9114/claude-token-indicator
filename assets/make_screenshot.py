"""Render assets/screenshot.png — a faithful still of the indicator strip.

Mirrors the colors/layout in claude_indicator/ui.py so the README image
matches the real overlay. Rendered at 3x for crisp text.
"""

import os

from PIL import Image, ImageDraw, ImageFont

S = 3  # scale
BG = (27, 27, 29)
TRACK = (58, 58, 61)
TEXT = (230, 230, 230)
MUTED = (154, 154, 159)
OK = (78, 161, 255)
CRIT = (239, 91, 91)

WIN = "C:\\Windows\\Fonts"


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(WIN, name), size * S)
    except OSError:
        return ImageFont.load_default()


F = font("segoeui.ttf", 9)
FB = font("segoeuib.ttf", 9)


def draw_segment(d, x, cy, label, pct, reset):
    d.text((x, cy), label, font=F, fill=TEXT, anchor="lm")
    bx = x + 46 * S
    bw, bh = 54 * S, 5 * S
    d.rounded_rectangle([bx, cy - bh // 2, bx + bw, cy + bh // 2], radius=bh // 2, fill=TRACK)
    fw = int(bw * pct / 100)
    if fw > 0:
        d.rounded_rectangle([bx, cy - bh // 2, bx + max(fw, bh), cy + bh // 2],
                            radius=bh // 2, fill=OK)
    d.text((bx + bw + 6 * S, cy), f"{pct:.0f}%", font=FB, fill=TEXT, anchor="lm")
    d.text((bx + bw + 6 * S + 32 * S, cy), reset, font=F, fill=MUTED, anchor="lm")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    pad, seg, quit_w = 7 * S, 182 * S, 16 * S
    w = pad + seg + pad + seg + pad + quit_w
    h = 16 * S
    margin = 22 * S

    img = Image.new("RGBA", (w + margin * 2, h + margin * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0 = margin, margin
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=5 * S, fill=BG)

    cy = y0 + h // 2
    draw_segment(d, x0 + pad, cy, "Session", 34, "in 1h22m")
    draw_segment(d, x0 + pad + seg + pad, cy, "Weekly", 48, "in 6h")
    d.text((x0 + w - quit_w // 2, cy), "\u2715", font=FB, fill=CRIT, anchor="mm")

    out = os.path.join(here, "screenshot.png")
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    main()
