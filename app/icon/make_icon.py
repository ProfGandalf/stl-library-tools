"""
Generates the app icon: a contact sheet of bone tiles next to an amber zipper.

    python3 app/icon/make_icon.py      (needs Pillow; only for regenerating)

Writes into app/icon/:
    icon.png   256 px, used for the window / taskbar icon and on Linux
    icon.ico   16-256 px, built into STL-Tools.exe on Windows

Small sizes (<= 48 px) use a simpler drawing - 2x2 tiles and a few big
zipper teeth - because the full 3x3 grid turns to mush at 16-32 px.
"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
BG, EDGE = (26, 28, 33), (52, 56, 66)
BONE = (214, 207, 192)
AMBER, AMBER_D = (224, 161, 74), (176, 120, 46)
TRACK = (44, 47, 56)


def draw(size):
    """Draws the icon at 4x the size and scales down (smooth edges)."""
    n = size * 4
    s = n / 1024.0                         # the design is drawn on a 1024 grid
    simple = size <= 48
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def box(x0, y0, x1, y1, r, fill):
        d.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s), radius=r * s, fill=fill)

    # background tile
    edge = 0 if simple else 14
    box(24, 24, 1000, 1000, 210, EDGE)
    box(24 + edge, 24 + edge, 1000 - edge, 1000 - edge, 200 - edge, BG)

    # contact sheet
    if simple:
        cols, rows, x0, y0, w, h, gap, r = 2, 2, 120, 140, 215, 350, 44, 50
    else:
        cols, rows, x0, y0, w, h, gap, r = 3, 3, 140, 160, 158, 208, 34, 32
    for row in range(rows):
        for col in range(cols):
            x, y = x0 + col * (w + gap), y0 + row * (h + gap)
            box(x, y, x + w, y + h, r, BONE)

    # zipper: dark track, interlocking teeth, pull tab at the bottom
    if simple:
        zx, zw, top, bot, teeth, tw, th = 640, 270, 120, 760, 4, 120, 105
    else:
        zx, zw, top, bot, teeth, tw, th = 700, 170, 130, 770, 9, 62, 40
    box(zx, top, zx + zw, bot + 30, 50, TRACK)
    step = (bot - top - th) / float(teeth - 1)
    for i in range(teeth):
        y = top + 20 + i * step * ((bot - top - 40 - th) / float(bot - top - th))
        left = i % 2 == 0
        tx = zx + (22 if left else zw - 22 - tw)
        box(tx, y, tx + tw, y + th, 12, AMBER)
    # pull tab: slider + ring
    cx = zx + zw / 2.0
    box(cx - 60, bot - 10, cx + 60, bot + 70, 22, AMBER)
    if not simple:
        box(cx - 42, bot + 50, cx + 42, bot + 190, 40, AMBER_D)
        box(cx - 18, bot + 90, cx + 18, bot + 150, 18, BG)
    else:
        box(cx - 90, bot - 10, cx + 90, bot + 110, 30, AMBER)

    return im.resize((size, size), Image.LANCZOS)


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = {sz: draw(sz) for sz in sizes}
    imgs[256].save(os.path.join(HERE, "icon.png"))
    # every size drawn separately, so the small ones get the simple design
    imgs[256].save(os.path.join(HERE, "icon.ico"), format="ICO",
                   sizes=[(sz, sz) for sz in sizes],
                   append_images=[imgs[sz] for sz in sizes if sz != 256])
    print("written icon.png and icon.ico")


if __name__ == "__main__":
    main()
