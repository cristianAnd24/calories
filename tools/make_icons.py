"""Draws the app icons: a white progress ring on a green gradient.

    python tools/make_icons.py

iOS masks the apple-touch-icon itself, so every icon is a full, opaque square
with no rounded corners. The maskable icon keeps the ring inside the central
safe zone (80% circle) that Android crops to.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent
TOP, BOTTOM = (76, 217, 100), (31, 166, 74)
SCALE = 4  # draw large, then downsample, for smooth edges


def gradient(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        c = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        for x in range(size):
            px[x, y] = c
    return img


def icon(size, ring_frac):
    big = size * SCALE
    r = big * ring_frac / 2
    w = round(big * ring_frac * 0.17)
    box = [big / 2 - r, big / 2 - r, big / 2 + r, big / 2 + r]
    # faint track: white at low opacity over the gradient
    track = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(track).arc(box, 0, 360, fill=(255, 255, 255, 80), width=w)
    img = Image.alpha_composite(gradient(big).convert("RGBA"), track)
    d = ImageDraw.Draw(img)
    # the filled part: most of the way round from 12 o'clock, round caps
    start, end = -90, 200
    d.arc(box, start, end, fill=(255, 255, 255, 255), width=w)
    for ang in (start, end):
        a = math.radians(ang)
        cx = big / 2 + (r - w / 2) * math.cos(a)
        cy = big / 2 + (r - w / 2) * math.sin(a)
        d.ellipse([cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2], fill=(255, 255, 255, 255))
    return img.convert("RGB").resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    icon(180, 0.56).save(OUT / "apple-touch-icon.png")
    icon(192, 0.56).save(OUT / "icon-192.png")
    icon(512, 0.56).save(OUT / "icon-512.png")
    icon(512, 0.46).save(OUT / "icon-512-maskable.png")
    print("icons written to", OUT)
