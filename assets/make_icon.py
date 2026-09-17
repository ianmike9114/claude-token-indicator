"""Generate assets/icon.ico — a gauge meter that reads at any size.

Dark rounded square with a partial ring (grey track + blue fill), echoing the
indicator's progress bars. Rendered at 4x then downsampled for smooth edges,
and saved as a multi-resolution .ico.
"""

import os

from PIL import Image, ImageDraw

BG = (27, 27, 29, 255)      # #1b1b1d
TRACK = (58, 58, 61, 255)   # #3a3a3d
FILL = (78, 161, 255, 255)  # #4ea1ff (session blue)

SS = 1024                   # supersample canvas
START = 135                 # gauge sweep: 135deg .. 405deg (270deg total)
SWEEP = 270
FILL_FRAC = 0.66            # how much of the ring is filled


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # rounded-square background
    pad = int(size * 0.06)
    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=int(size * 0.22),
        fill=BG,
    )

    # gauge ring
    ring_pad = int(size * 0.24)
    box = [ring_pad, ring_pad, size - ring_pad, size - ring_pad]
    width = int(size * 0.12)
    d.arc(box, START, START + SWEEP, fill=TRACK, width=width)
    d.arc(box, START, START + int(SWEEP * FILL_FRAC), fill=FILL, width=width)

    # center dot
    r = int(size * 0.055)
    c = size // 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=FILL)
    return img


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    master = render(SS)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [master.resize((s, s), Image.LANCZOS) for s in sizes]
    out = os.path.join(here, "icon.ico")
    frames[-1].save(out, format="ICO", sizes=[(s, s) for s in sizes])
    # also a PNG for docs / non-Windows use
    master.resize((256, 256), Image.LANCZOS).save(os.path.join(here, "icon.png"))
    print("wrote", out)


if __name__ == "__main__":
    main()
