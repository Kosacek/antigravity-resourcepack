# -*- coding: utf-8 -*-
"""The house (rings) and the aim marker: single flat faces looking up, unlit.

Both textures use only fully opaque or fully transparent pixels (a partly transparent pixel would
make the whole face render translucent), so the drawing is antialiased against black outlines and
the alpha is cut hard.
"""
from PIL import Image, ImageDraw

import mc_model as mm

BLUE = (30, 84, 172)
WHITE = (246, 248, 251)
RED = (204, 32, 42)
BLACK = (10, 10, 12)
LIME = (96, 255, 96)


def _finish(rgb, mask, size):
    """Downsample the supersampled drawing and cut the alpha hard."""
    rgb = rgb.resize((size, size), Image.LANCZOS)
    alpha = mask.resize((size, size), Image.BOX).point(lambda v: 255 if v >= 128 else 0)
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def _disc(draws, centre, r, colour):
    for d, c in draws:
        d.ellipse((centre - r, centre - r, centre + r, centre + r), fill=c(colour))


def house_texture(radii, size=512, ss=4, outline_px=3.0):
    """Rings from the config: radii[0] (12-ft) touches the texture edges."""
    big = size * ss
    rgb = Image.new("RGB", (big, big), BLACK)
    mask = Image.new("L", (big, big), 0)
    draws = [(ImageDraw.Draw(rgb), lambda c: c), (ImageDraw.Draw(mask), lambda c: 255)]
    centre = big / 2.0
    scale = (big / 2.0 - 1.0) / radii[0]                # supersampled pixels per block
    colours = (BLUE, WHITE, RED, WHITE)                 # 12-ft, 8-ft, 4-ft, button
    half = outline_px * ss / 2.0
    for i, (r, colour) in enumerate(zip(radii, colours)):
        pr = r * scale
        if i == 0:                                      # the outline stays inside the texture
            _disc(draws, centre, pr, BLACK)
            _disc(draws, centre, pr - 2 * half, colour)
        else:                                           # outline centred on the ring edge
            _disc(draws, centre, pr + half, BLACK)
            _disc(draws, centre, pr - half, colour)
    return _finish(rgb, mask, size)


def marker_texture(size=256, ss=4):
    big = size * ss
    rgb = Image.new("RGB", (big, big), BLACK)
    mask = Image.new("L", (big, big), 0)
    c = big / 2.0
    R = c - 2

    def paint(shape_mask, colour):
        rgb.paste(colour, mask=shape_mask)
        mask.paste(255, mask=shape_mask)

    def ring(r0, r1, colour):
        m = Image.new("L", (big, big), 0)
        d = ImageDraw.Draw(m)
        d.ellipse((c - R * r1, c - R * r1, c + R * r1, c + R * r1), fill=255)
        d.ellipse((c - R * r0, c - R * r0, c + R * r0, c + R * r0), fill=0)
        paint(m, colour)

    def disc(r, colour):
        m = Image.new("L", (big, big), 0)
        ImageDraw.Draw(m).ellipse((c - R * r, c - R * r, c + R * r, c + R * r), fill=255)
        paint(m, colour)

    def bars(r0, r1, w, colour):
        m = Image.new("L", (big, big), 0)
        d = ImageDraw.Draw(m)
        d.rectangle((c - R * r1, c - R * w, c + R * r1, c + R * w), fill=255)
        d.rectangle((c - R * w, c - R * r1, c + R * w, c + R * r1), fill=255)
        d.ellipse((c - R * r0, c - R * r0, c + R * r0, c + R * r0), fill=0)
        paint(m, colour)

    # outer ring: a lime band between two black outlines; the middle of the disc stays see-through
    ring(0.80, 0.99, BLACK)
    ring(0.845, 0.945, LIME)
    ring(0.36, 0.50, BLACK)                             # inner white ring
    ring(0.395, 0.465, WHITE)
    bars(0.12, 0.90, 0.062, BLACK)                      # crosshair: black bars with lime centres
    bars(0.15, 0.87, 0.030, LIME)
    disc(0.15, BLACK)
    disc(0.095, (255, 48, 48))
    return _finish(rgb, mask, size)


def build(writer, ring_radii):
    counts = {}
    writer.texture("house", house_texture(ring_radii))
    writer.model("house", {"0": "house"},
                 [mm.flat_element([0, 8, 0], [16, 8, 16], "up", "#0", [0, 0, 16, 16])])
    writer.item("house", unlit=True)
    counts["house"] = 1
    writer.texture("aim_marker", marker_texture())
    writer.model("aim_marker", {"0": "aim_marker"},
                 [mm.flat_element([4, 8, 4], [12, 8, 12], "up", "#0", [0, 0, 16, 16])])
    writer.item("aim_marker", unlit=True)
    counts["aim_marker"] = 1
    return counts
