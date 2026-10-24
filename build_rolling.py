"""Round pool balls whose numbers and stripes roll.

Each ball is drawn by two displays that the server stacks on the pack's (hidden) ball:

* body:  a flat picture of a shaded sphere in the ball's base colour that always faces
         the viewer, so the outline is a perfect circle from every angle.
* marks: the number circles, the stripe band and the cue ball's dots as thin 3D pieces
         on the sphere's surface. The server gives this display the ball's own rotation,
         so the markings roll with the ball; pieces that roll round the back sit behind
         the body picture and are hidden by it.

The pack's own ball models are left alone (they are what you see without the server's help).

Usage:  python build_rolling.py <output folder>
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from build_sprites import NS, POOL, SNOOKER, WHITE, DOT, ball_image

R = 4.0          # ball radius in model units (the pack's balls span 4..12)
C = 8.0          # ball centre
MARK_LIGHT = 0.9  # markings are unshaded; match the body's brightness facing the light

STRIPE_HALF = 0.52                              # band covers |y| < 0.52 R
STRIPE_ROWS = [(0.0, 0.18), (0.18, 0.36), (0.36, STRIPE_HALF)]
SIDES = 16


def _lit(rgb, k=MARK_LIGHT):
    return tuple(int(c * k) for c in rgb)


# --- textures -------------------------------------------------------------------------

def number_texture(n, font):
    size = 64
    img = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    big = size * 4
    d.ellipse((2, 2, big - 3, big - 3), fill=_lit(WHITE) + (255,))
    text = str(n)
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x, y = big / 2.0 - w / 2.0 - box[0], big / 2.0 - h / 2.0 - box[1]
    d.text((x, y), text, fill=(18, 18, 18, 255), font=font)
    if n in (6, 9):                       # real balls underline 6 and 9
        uy = big / 2.0 + h / 2.0 + big * 0.04
        d.rectangle((big / 2.0 - w / 2.0, uy, big / 2.0 + w / 2.0, uy + big * 0.035), fill=(18, 18, 18, 255))
    small = img.resize((size, size), Image.LANCZOS)
    small.putalpha(small.split()[3].point(lambda v: 255 if v >= 128 else 0))
    return small


def solid_texture(rgb):
    return Image.new("RGBA", (16, 16), _lit(rgb) + (255,))


def dot_texture():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((1, 1, 62, 62), fill=_lit(DOT) + (255,))
    small = img.resize((16, 16), Image.LANCZOS)
    small.putalpha(small.split()[3].point(lambda v: 255 if v >= 128 else 0))
    return small


# --- geometry -------------------------------------------------------------------------

def _square(axis, sign, depth, half, tex, y_range=None, rot=0.0, width_half=None):
    """A flat square (or strip) facing outward along +-axis at distance depth*R from the centre."""
    d = depth * R
    hw = (width_half if width_half is not None else half) * R
    y0, y1 = (C - half * R, C + half * R) if y_range is None else (C + y_range[0] * R, C + y_range[1] * R)
    t = 0.01
    if axis == "x":
        x0, x1 = (C + d - t, C + d) if sign > 0 else (C - d, C - d + t)
        frm, to, face = [x0, y0, C - hw], [x1, y1, C + hw], "east" if sign > 0 else "west"
    elif axis == "z":
        z0, z1 = (C + d - t, C + d) if sign > 0 else (C - d, C - d + t)
        frm, to, face = [C - hw, y0, z0], [C + hw, y1, z1], "south" if sign > 0 else "north"
    else:   # y: only for dots, a square in the xz plane
        y0, y1 = (C + d - t, C + d) if sign > 0 else (C - d, C - d + t)
        frm, to, face = [C - hw, y0, C - hw], [C + hw, y1, C + hw], "up" if sign > 0 else "down"
    el = {"from": [round(v, 4) for v in frm], "to": [round(v, 4) for v in to], "shade": False,
          "faces": {face: {"uv": [0, 0, 16, 16], "texture": tex}}}
    if rot:
        el["rotation"] = {"angle": rot, "axis": "y", "origin": [C, C, C]}
    return el


def stripe_band():
    """A 16-sided band around the vertical axis, in rows that follow the sphere's curve."""
    half_angle = math.radians(180.0 / SIDES)
    els = []
    sides = [("x", 1), ("z", 1), ("x", -1), ("z", -1)]
    rows = []
    for lo, hi in STRIPE_ROWS:
        mid = (lo + hi) / 2.0
        vertex = math.sqrt(1.0 - mid * mid)              # polygon corners on the sphere at mid-row
        rows.append((lo, hi, vertex * math.cos(half_angle)))
    for i, (lo, hi, apothem) in enumerate(rows):
        strip_half = apothem * math.tan(half_angle) * 1.02   # a hair wider so strips meet
        inner = rows[i + 1][2] if i + 1 < len(rows) else None
        for flip in (1, -1):
            y_range = (lo, hi) if flip > 0 else (-hi, -lo)
            for axis, sign in sides:
                for rot in (-22.5, 0.0, 22.5, 45.0):
                    els.append(_square(axis, sign, apothem, 0, "#band", y_range, rot, strip_half))
                    if inner is not None:
                        els.append(_ledge(axis, sign, inner, apothem, hi * flip, flip, strip_half, rot))
    return els


def _ledge(axis, sign, inner, outer, y, flip, half_width, rot):
    """The flat ring between two band rows, so the step doesn't show the body through it."""
    t = 0.01
    y0, y1 = (C + y * R - t, C + y * R) if flip > 0 else (C + y * R, C + y * R + t)
    a, b = inner * R - 0.05, outer * R
    hw = half_width * R
    if axis == "x":
        x0, x1 = (C + a, C + b) if sign > 0 else (C - b, C - a)
        frm, to = [x0, y0, C - hw], [x1, y1, C + hw]
    else:
        z0, z1 = (C + a, C + b) if sign > 0 else (C - b, C - a)
        frm, to = [C - hw, y0, z0], [C + hw, y1, z1]
    el = {"from": [round(v, 4) for v in frm], "to": [round(v, 4) for v in to], "shade": False,
          "faces": {"up" if flip > 0 else "down": {"uv": [0, 0, 16, 16], "texture": "#band"}}}
    if rot:
        el["rotation"] = {"angle": rot, "axis": "y", "origin": [C, C, C]}
    return el


def number_discs(stripe):
    radius = 0.38 if stripe else 0.42
    depth = 0.99 if stripe else math.sqrt(1.0 - radius * radius) + 0.005
    return [_square("x", 1, depth, radius, "#num"), _square("x", -1, depth, radius, "#num")]


def cue_dots():
    radius, depth = 0.13, 0.985
    return [_square(axis, sign, depth, radius, "#dot") for axis in ("x", "y", "z") for sign in (1, -1)]


# --- output ---------------------------------------------------------------------------

def build(out):
    root = os.path.join(out, "assets", NS)
    models = os.path.join(root, "models", "item", "hg")
    tex = os.path.join(root, "textures", "item", "hg")
    items = os.path.join(root, "items")
    for p in (models, tex, items):
        os.makedirs(p, exist_ok=True)
    try:
        font = ImageFont.truetype("arialbd.ttf", int(64 * 4 * 0.5))
    except OSError:
        font = ImageFont.load_default()

    def tex_ref(name):
        return "%s:item/hg/%s" % (NS, name)

    def save_tex(name, image):
        image.save(os.path.join(tex, name + ".png"))
        return tex_ref(name)

    def write_model(name, textures, elements):
        model = {"credit": "Rolling pool balls for Pool and Billiards (Squid Workshop), generated by build_rolling.py",
                 "textures": dict(textures, particle=list(textures.values())[0] if textures else tex_ref("dot")),
                 "elements": elements}
        with open(os.path.join(models, name + ".json"), "w") as fh:
            json.dump(model, fh, indent=1)
        with open(os.path.join(items, "hg_" + name + ".json"), "w") as fh:
            json.dump({"model": {"type": "minecraft:model", "model": "%s:item/hg/%s" % (NS, name)}}, fh, indent=1)

    def body(name, rgb):
        t = save_tex("body_" + name, ball_image(lambda nx, ny, nz: rgb))
        e = 0.005
        write_model("body_" + name, {"0": t}, [{
            "from": [C - R, C - R, C - e], "to": [C + R, C + R, C + e], "shade": False,
            "faces": {"south": {"uv": [0, 0, 16, 16], "texture": "#0"},
                      "north": {"uv": [0, 0, 16, 16], "texture": "#0"}}}])

    dot = save_tex("dot", dot_texture())
    for n in range(1, 16):
        name = "ball_%02d" % n
        stripe = n >= 9
        body(name, WHITE if stripe else POOL[n])
        num = save_tex("num_%02d" % n, number_texture(n, font))
        textures = {"num": num}
        elements = number_discs(stripe)
        if stripe:
            textures["band"] = save_tex("band_%02d" % n, solid_texture(POOL[n]))
            elements = stripe_band() + elements
        write_model("marks_" + name, textures, elements)
    body("cueball", WHITE)
    write_model("marks_cueball", {"dot": dot}, cue_dots())
    body("cueball_clean", WHITE)
    write_model("marks_cueball_clean", {}, [])
    for name, rgb in SNOOKER.items():
        body(name, rgb)
        write_model("marks_" + name, {}, [])
    print("wrote rolling balls to", os.path.abspath(out))


if __name__ == "__main__":
    build(sys.argv[1])
