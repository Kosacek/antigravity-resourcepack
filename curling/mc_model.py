# -*- coding: utf-8 -*-
"""Shared helpers for the curling model generator.

Minecraft 26.x model elements can be rotated on all three axes
(`"rotation": {"origin", "x", "y", "z"}`, applied as Rz * Ry * Rx), so any thin quad can be
placed at any position and orientation: `quad_element` does that, using the quad's own centre as
the rotation origin. The ideas come from tools/pool_balls/build_sphere.py (copied, not imported).
"""
import json
import math
import os

from PIL import Image

NS = "curling"
UNLIT_TINT = 0xFEFDFC          # the pack's patched item shader draws faces with this tint unlit
LIMIT_MIN, LIMIT_MAX = -16.0, 32.0


def signed_argb(rgb):
    """An opaque signed ARGB int, as vanilla writes tints (#FEFDFC -> -66052)."""
    return (0xFF000000 | rgb) - (1 << 32)


# --- small vector maths ------------------------------------------------------------------

def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def rot_matrix(ax, ay, az):
    """Rz(az) * Ry(ay) * Rx(ax), angles in degrees (Minecraft's element rotation)."""
    a, b, c = math.radians(ax), math.radians(ay), math.radians(az)
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [[cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa],
            [sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa],
            [-sb, cb * sa, cb * ca]]


def euler_zyx(m):
    """Angles (x, y, z) in degrees with m = Rz(z) * Ry(y) * Rx(x), including the gimbal-lock case."""
    s = -m[2][0]                                   # sin(y)
    if abs(s) > 0.999999:
        b = math.copysign(math.pi / 2, s)
        c = 0.0
        a = math.atan2(m[0][1], m[1][1]) if s > 0 else math.atan2(-m[0][1], m[1][1])
    else:
        b = math.asin(s)
        a = math.atan2(m[2][1], m[2][2])
        c = math.atan2(m[1][0], m[0][0])
    return math.degrees(a), math.degrees(b), math.degrees(c)


def _check_euler(m, ax, ay, az):
    r = rot_matrix(ax, ay, az)
    err = max(abs(r[i][j] - m[i][j]) for i in range(3) for j in range(3))
    assert err < 2e-3, "euler decomposition error %.5f" % err


def _r(v, n=4):
    return round(v + 0.0, n)


def _check_bounds(frm, to):
    for v in list(frm) + list(to):
        assert LIMIT_MIN <= v <= LIMIT_MAX, "element coordinate %s outside -16..32" % v


# --- elements -------------------------------------------------------------------------------

def quad_element(centre, e, u, n, hw, hh, texture, uv, tint=True, shade=False):
    """One flat rectangle (a 'south' face) centred on `centre`.

    e: direction the texture's u runs along, u: direction of -v (up the texture), n: outward
    normal, with e x u = n. hw/hh are the half sizes along e and u."""
    m = [[e[k], u[k], n[k]] for k in range(3)]       # columns: local x, y, z
    ax, ay, az = euler_zyx(m)
    _check_euler(m, ax, ay, az)
    frm = [_r(centre[0] - hw), _r(centre[1] - hh), _r(centre[2])]
    to = [_r(centre[0] + hw), _r(centre[1] + hh), _r(centre[2])]
    _check_bounds(frm, to)
    face = {"uv": [_r(x) for x in uv], "texture": texture}
    if tint:
        face["tintindex"] = 0
    return {"from": frm, "to": to,
            "rotation": {"origin": [_r(c) for c in centre], "x": _r(ax), "y": _r(ay), "z": _r(az)},
            "shade": shade, "faces": {"south": face}}


def flat_element(frm, to, direction, texture, uv, tint=True):
    """An axis-aligned flat face, e.g. the up face of a decal at a fixed height."""
    _check_bounds(frm, to)
    face = {"uv": [_r(x) for x in uv], "texture": texture}
    if tint:
        face["tintindex"] = 0
    return {"from": [_r(x) for x in frm], "to": [_r(x) for x in to], "shade": False,
            "faces": {direction: face}}


def box_element(frm, to, uv_by_face, texture="#0", rotation=None, shade=True):
    """An axis-aligned box (optionally rotated); uv_by_face maps each face name to its uv rectangle
    (or is one rectangle for all six faces)."""
    _check_bounds(frm, to)
    faces = {}
    for name in ("north", "south", "east", "west", "up", "down"):
        uv = uv_by_face[name] if isinstance(uv_by_face, dict) else uv_by_face
        faces[name] = {"uv": [_r(x) for x in uv], "texture": texture}
    el = {"from": [_r(x) for x in frm], "to": [_r(x) for x in to], "faces": faces}
    if not shade:
        el["shade"] = False
    if rotation is not None:
        el["rotation"] = rotation
    return el


def prism_y(cx, cz, radius, y0, y1, sides, uv, texture="#0", caps=(True, True), shade=True,
            tint=False, cap_uv=None):
    """A vertical prism (radius = circumradius) built from thin quads."""
    els = []
    apothem = radius * math.cos(math.pi / sides)
    hw = radius * math.sin(math.pi / sides) * 1.02
    for k in range(sides):
        phi = 2 * math.pi * (k + 0.5) / sides
        n = (math.sin(phi), 0.0, math.cos(phi))
        e = (math.cos(phi), 0.0, -math.sin(phi))
        centre = (cx + apothem * n[0], (y0 + y1) / 2.0, cz + apothem * n[2])
        els.append(quad_element(centre, e, (0.0, 1.0, 0.0), n, hw, (y1 - y0) / 2.0, texture, uv,
                                tint=tint, shade=shade))
    assert sides == 8, "caps are built for octagons"
    for top, want in ((True, caps[0]), (False, caps[1])):
        if not want:
            continue
        # an octagon from four rectangles whose corners lie exactly on its vertices
        for k in range(4):
            turn = k * math.pi / 4
            e = (math.cos(turn), 0.0, -math.sin(turn))
            n = (0.0, 1.0 if top else -1.0, 0.0)
            u = cross(n, e)
            els.append(quad_element((cx, y1 if top else y0, cz), e, u, n, apothem, apothem * math.tan(math.pi / 8),
                                    texture, cap_uv or uv, tint=tint, shade=shade))
    return els


# --- palette textures: solid colour cells, so a face just points at its cell ------------------

class Palette(object):
    """A small texture of solid colour cells (4 x 4 cells of 16 px); a face points at one cell."""

    def __init__(self, size=64, grid=4):
        self.size, self.grid = size, grid
        self.names = []
        self.colours = []

    def add(self, name, rgb):
        assert len(self.names) < self.grid * self.grid, "palette full"
        self.names.append(name)
        self.colours.append(tuple(rgb[:3]))
        return name

    def uv(self, name):
        i = self.names.index(name)
        cell = 16.0 / self.grid
        cx, cy = i % self.grid, i // self.grid
        inset = cell * 0.12
        return [cx * cell + inset, cy * cell + inset, (cx + 1) * cell - inset, (cy + 1) * cell - inset]

    def image(self):
        img = Image.new("RGBA", (self.size, self.size), (90, 90, 90, 255))
        cell = self.size // self.grid
        px = img.load()
        for i, rgb in enumerate(self.colours):
            cx, cy = i % self.grid, i // self.grid
            for y in range(cy * cell, (cy + 1) * cell):
                for x in range(cx * cell, (cx + 1) * cell):
                    px[x, y] = rgb + (255,)
        return img


def scale_rgb(rgb, k):
    return tuple(max(0, min(255, int(round(c * k)))) for c in rgb)


# --- writers --------------------------------------------------------------------------------

class PackWriter(object):
    """Writes assets/curling/{items,models/item,textures/item} under an output folder."""

    def __init__(self, out):
        root = os.path.join(out, "assets", NS)
        self.items = os.path.join(root, "items")
        self.models = os.path.join(root, "models", "item")
        self.textures = os.path.join(root, "textures", "item")
        for p in (self.items, self.models, self.textures):
            if not os.path.isdir(p):
                os.makedirs(p)
        self.written = []

    def texture(self, name, image):
        path = os.path.join(self.textures, name + ".png")
        image.save(path)
        self.written.append(path)

    def model(self, name, textures, elements, display=None):
        tex = dict((k, "%s:item/%s" % (NS, v)) for k, v in textures.items())
        tex["particle"] = tex[sorted(textures)[0]]
        data = {"credit": "Curling set model generated by tools/curling/assets/build_assets.py",
                "textures": tex, "elements": elements}
        if display:
            data["display"] = display
        path = os.path.join(self.models, name + ".json")
        with open(path, "w") as fh:
            json.dump(data, fh, separators=(",", ":"))
        self.written.append(path)

    def item(self, name, unlit):
        model = {"type": "minecraft:model", "model": "%s:item/%s" % (NS, name)}
        if unlit:
            model["tints"] = [{"type": "minecraft:constant", "value": signed_argb(UNLIT_TINT)}]
        path = os.path.join(self.items, name + ".json")
        with open(path, "w") as fh:
            json.dump({"model": model}, fh, indent=1)
        self.written.append(path)
