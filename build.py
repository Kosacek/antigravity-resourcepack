"""Rounder, properly textured balls for the Pool and Billiards resource pack.

Minecraft item models are made of boxes, and a box may rotate around one axis in
22.5 degree steps. Each ball is a stack of horizontal layers; every layer is four
square boxes turned 0 / 22.5 / 45 / 67.5 degrees around Y, which together make a
16-sided disc. The layer radii follow a sphere, so the outline is round from above
and finely stepped from the side.

Textures: real pool colours, white caps on the stripe balls (9-15), a white number
circle on two sides, a cue ball with red dots, and plain snooker balls.

Usage:  python build.py <original pack folder> <output folder>
Writes the override models and textures, then preview.png (a software render).
"""
import json
import math
import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

R = 4.0                 # ball radius in model pixels (the original balls span 4..12)
C = (8.0, 8.0, 8.0)     # ball centre
LAYERS = 11
ANGLES = (0.0, 22.5, 45.0, -22.5)
SQUARE = 1.0 / 1.33     # half-side of each square relative to the layer radius
STRIPE = 0.56           # stripe band half-height as a fraction of R
DECAL = 0.42            # number circle radius as a fraction of R

POOL = {  # number -> colour (RGB)
    1: (245, 197, 24), 2: (24, 64, 168), 3: (204, 28, 38), 4: (84, 44, 132), 5: (242, 110, 30),
    6: (14, 120, 64), 7: (128, 30, 34), 8: (16, 16, 18),
}
for n in range(9, 16):
    POOL[n] = POOL[n - 8]
SNOOKER = {"red": (186, 18, 28), "yellow": (245, 200, 30), "green": (16, 112, 56), "brown": (110, 62, 30),
           "blue": (28, 66, 160), "pink": (236, 128, 168), "black": (16, 16, 18)}
WHITE = (246, 244, 236)
DOT = (196, 22, 30)
NS = "swpool"


# ---------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------

def solid(rgb, path):
    Image.new("RGBA", (16, 16), rgb + (255,)).save(path)


def number_decal(n, path, font):
    """White circle with a black number, transparent outside (32x32)."""
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((1, 1, 30, 30), fill=WHITE + (255,))
    text = str(n)
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((32 - w) / 2 - box[0], (32 - h) / 2 - box[1]), text, fill=(12, 12, 12, 255), font=font)
    im.save(path)


def dot_decal(path):
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((1, 1, 14, 14), fill=DOT + (255,))
    im.save(path)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def layer_bounds():
    step = 2 * R / LAYERS
    for k in range(LAYERS):
        y0 = -R + k * step
        yield y0, y0 + step


def box(x0, y0, z0, x1, y1, z1, tex, angle=0.0, axis="y", faces="nsewud"):
    names = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    el = {"from": [round(C[0] + x0, 4), round(C[1] + y0, 4), round(C[2] + z0, 4)],
          "to": [round(C[0] + x1, 4), round(C[1] + y1, 4), round(C[2] + z1, 4)],
          "faces": dict((names[f], {"uv": [0, 0, 16, 16], "texture": tex}) for f in faces)}
    if angle:
        el["rotation"] = {"angle": angle, "axis": axis, "origin": list(C)}
    return el


SPOKE_W = math.sin(math.radians(11.25)) * 1.04   # half-width per unit radius: spokes 22.5 deg apart overlap


def sphere(color_for_layer):
    """Layered sphere. Each layer is 8 spokes (long thin boxes) 22.5 degrees apart: together they
    cover the whole disc, and their ends form a 16-sided rim. color_for_layer(ymid) -> texture."""
    els = []
    for y0, y1 in layer_bounds():
        ymid = (y0 + y1) / 2.0
        r = math.sqrt(max(R * R - ymid * ymid, 0.0))
        w = r * SPOKE_W
        tex = color_for_layer(ymid)
        for a in ANGLES:
            els.append(box(-r, y0, -w, r, y1, w, tex, angle=a))   # along x, turned by a
            els.append(box(-w, y0, -r, w, y1, r, tex, angle=a))   # along z, turned by a
    return els


def surface_z():
    """How far the equator layer reaches along +z (where decals sit)."""
    return R


def decal(direction, size, tex):
    """A thin flat box just outside the surface, facing `direction` (n/s/e/w/u/d)."""
    s = size
    out = surface_z() + 0.02
    t = 0.01
    if direction == "s":
        return box(-s, -s, out, s, s, out + t, tex, faces="s")
    if direction == "n":
        return box(-s, -s, -out - t, s, s, -out, tex, faces="n")
    if direction == "e":
        return box(out, -s, -s, out + t, s, s, tex, faces="e")
    if direction == "w":
        return box(-out - t, -s, -s, -out, s, s, tex, faces="w")
    top = R + 0.02
    if direction == "u":
        return box(-s, top, -s, s, top + t, s, tex, faces="u")
    return box(-s, -top - t, -s, s, -top, s, tex, faces="d")


def model(textures, elements, original):
    m = {"credit": "Rounder balls for Pool and Billiards (Squid Workshop) - generated by build.py",
         "textures": textures, "elements": elements}
    if "display" in original:
        m["display"] = original["display"]
    if "gui_light" in original:
        m["gui_light"] = original["gui_light"]
    return m


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def main(src, out):
    item_models = os.path.join(out, "assets", NS, "models", "item")
    tex_dir = os.path.join(out, "assets", NS, "textures", "item", "pool_round")
    for d in (item_models, tex_dir):
        os.makedirs(d, exist_ok=True)
    try:
        font = ImageFont.truetype("arialbd.ttf", 19)
    except OSError:
        font = ImageFont.load_default()

    def t(name):
        return "%s:item/pool_round/%s" % (NS, name)

    solid(WHITE, os.path.join(tex_dir, "white.png"))
    dot_decal(os.path.join(tex_dir, "dot.png"))
    src_models = os.path.join(src, "assets", NS, "models", "item")
    built = {}

    def original(name):
        with open(os.path.join(src_models, name + ".json")) as fh:
            return json.load(fh)

    # Pool balls 1-15
    for n in range(1, 16):
        cname = "c%02d" % n
        solid(POOL[n], os.path.join(tex_dir, cname + ".png"))
        number_decal(n, os.path.join(tex_dir, "n%02d.png" % n), font)
        stripe = n >= 9

        def colour(ymid, stripe=stripe):
            return "#w" if stripe and abs(ymid) > STRIPE * R else "#c"

        els = sphere(colour) + [decal("s", DECAL * R, "#n"), decal("n", DECAL * R, "#n")]
        name = "ball_%02d" % n
        built[name] = model({"c": t(cname), "w": t("white"), "n": t("n%02d" % n), "particle": t(cname)},
                            els, original(name))

    # Snooker balls (no numbers)
    for cname, rgb in SNOOKER.items():
        solid(rgb, os.path.join(tex_dir, "s_" + cname + ".png"))
        built[cname] = model({"c": t("s_" + cname), "particle": t("s_" + cname)},
                             sphere(lambda ymid: "#c"), original("ball_md"))

    # Cue balls: dotted (shows spin) and clean
    dots = [decal(d, 0.16 * R, "#d") for d in "nsewud"]
    built["cueball"] = model({"c": t("white"), "d": t("dot"), "particle": t("white")},
                             sphere(lambda ymid: "#c") + dots, original("ball_md"))
    built["cueball_clean"] = model({"c": t("white"), "particle": t("white")},
                                   sphere(lambda ymid: "#c"), original("ball_md"))

    for name, m in built.items():
        with open(os.path.join(item_models, name + ".json"), "w") as fh:
            json.dump(m, fh, indent=1)
    print("wrote %d models, %d elements each (pool balls)" % (len(built), len(built["ball_09"]["elements"])))
    return built, tex_dir


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    built, tex_dir = main(src, out)
    import render
    render.preview(built, tex_dir, os.path.join(out, "..", "preview.png"))
