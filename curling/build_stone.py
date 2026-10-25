# -*- coding: utf-8 -*-
"""The curling stones: a smooth granite body of revolution plus a gooseneck handle.

The body is a surface of revolution (PROFILE turned round the vertical axis). Every ring of the
profile is SEGMENTS thin quads, each one tangent to the surface, using Minecraft's multi-axis
element rotation. Faces are unlit (tint #FEFDFC, "shade": false), so the shading is painted into
the textures and depends only on the height on the stone, never on the angle around it: stones
spin about their vertical axis.

Textures:  stone_granite.png (shared body, u = angle round the stone, v = along the profile)
           stone_handle_<team>.png (palette of shaded colour cells for handle and bolt)
"""
import math
import random

from PIL import Image, ImageDraw

import mc_model as mm

SEGMENTS = 32
REF_R, REF_H = 4.8, 3.84          # the profile below is drawn for this radius and body height

# (radius, height) from the running edge on the ice up to the centre of the cup, in model units
PROFILE = [
    (3.75, 0.00),
    (3.92, 0.20),
    (4.20, 0.50),
    (4.52, 0.90),
    (4.74, 1.30),
    (4.80, 1.70),
    (4.74, 2.10),
    (4.58, 2.55),
    (4.28, 3.00),
    (3.85, 3.38),
    (3.30, 3.66),
    (2.70, 3.80),
    (2.35, 3.84),                 # rim of the cup, the highest point
    (1.80, 3.76),
    (1.20, 3.62),
    (0.70, 3.52),
]
BAND = (1.20, 2.20)               # the dark running band (heights on the reference stone)

TEAM_RGB = {"red": (206, 34, 40), "yellow": (250, 198, 24)}
TUBE_R = 0.58                     # handle bar half thickness (apothem of the octagon)


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / float(b - a)))
    return t * t * (3 - 2 * t)


class Profile(object):
    """The scaled profile with arc lengths and smooth normals."""

    def __init__(self, radius, height):
        self.kr, self.kh = radius / REF_R, height / REF_H
        self.pts = [(r * self.kr, y * self.kh) for r, y in PROFILE]
        self.s = [0.0]
        for i in range(1, len(self.pts)):
            self.s.append(self.s[-1] + math.hypot(self.pts[i][0] - self.pts[i - 1][0],
                                                  self.pts[i][1] - self.pts[i - 1][1]))
        self.length = self.s[-1]
        seg = []
        for i in range(len(self.pts) - 1):
            dr, dy = self.pts[i + 1][0] - self.pts[i][0], self.pts[i + 1][1] - self.pts[i][1]
            ln = math.hypot(dr, dy)
            seg.append((dy / ln, -dr / ln))               # outward normal (radial, vertical)
        self.seg_normal = seg
        self.vert_normal = []
        for i in range(len(self.pts)):
            ns = [seg[k] for k in (i - 1, i) if 0 <= k < len(seg)]
            nr, ny = sum(n[0] for n in ns), sum(n[1] for n in ns)
            ln = math.hypot(nr, ny)
            self.vert_normal.append((nr / ln, ny / ln))

    def at(self, s):
        """(radius, height, normal_r, normal_y) at arc length s."""
        s = max(0.0, min(self.length, s))
        i = 0
        while i < len(self.pts) - 2 and s > self.s[i + 1]:
            i += 1
        t = (s - self.s[i]) / (self.s[i + 1] - self.s[i])
        r = self.pts[i][0] + t * (self.pts[i + 1][0] - self.pts[i][0])
        y = self.pts[i][1] + t * (self.pts[i + 1][1] - self.pts[i][1])
        n0, n1 = self.vert_normal[i], self.vert_normal[i + 1]
        nr, ny = n0[0] + t * (n1[0] - n0[0]), n0[1] + t * (n1[1] - n0[1])
        ln = math.hypot(nr, ny)
        return r, y, nr / ln, ny / ln


# --- body geometry --------------------------------------------------------------------------

def body_elements(profile, tex="#0"):
    els = []
    dphi = 2 * math.pi / SEGMENTS
    pts, arc, total = profile.pts, profile.s, profile.length
    for i in range(len(pts) - 1):
        (r0, y0), (r1, y1) = pts[i], pts[i + 1]
        dr, dy = r1 - r0, y1 - y0
        seg = math.hypot(dr, dy)
        v_top = (1 - arc[i + 1] / total) * 16.0
        v_bot = (1 - arc[i] / total) * 16.0
        rc = (r0 + r1) / 2.0 * math.cos(dphi / 2)
        hw = max(r0, r1) * math.sin(dphi / 2) * 1.025
        for j in range(SEGMENTS):
            phi = (j + 0.5) * dphi
            radial = (math.sin(phi), 0.0, math.cos(phi))
            e = (math.cos(phi), 0.0, -math.sin(phi))
            u = mm.unit((dr * radial[0], dy, dr * radial[2]))
            n = mm.cross(e, u)
            centre = (8 + rc * radial[0], 8 + (y0 + y1) / 2.0, 8 + rc * radial[2])
            uv = [j * 16.0 / SEGMENTS, v_top, (j + 1) * 16.0 / SEGMENTS, v_bot]
            els.append(mm.quad_element(centre, e, u, n, hw, seg / 2.0 * 1.01, tex, uv))
    return els


# --- body texture -----------------------------------------------------------------------------

def _row_light(profile, y_px, height_px):
    """Painted lighting for one texture row: depends on the height on the stone only."""
    s = (1.0 - (y_px + 0.5) / height_px) * profile.length
    r, y, nr, ny = profile.at(s)
    yy = y / profile.kh                                  # height as on the reference stone
    up = max(ny, 0.0)
    shade = 0.60 + 0.36 * up ** 0.85 - 0.20 * max(-ny, 0.0)
    shade *= 0.80 + 0.20 * smooth(0.0, 1.6, yy)          # darker down at the ice
    if yy > 3.4 and r < 2.3:
        shade *= 0.93 + 0.07 * smooth(0.7, 2.3, r)       # the cup is a touch darker inside
    gloss = 0.0
    if yy > 2.4:                                         # a soft highlight band on the top bevel
        gloss = 0.62 * math.exp(-((ny - 0.70) / 0.085) ** 2)
        gloss += 0.25 * math.exp(-((ny - 0.30) / 0.10) ** 2)
    band = smooth(BAND[0], BAND[0] + 0.07, yy) * (1.0 - smooth(BAND[1] - 0.07, BAND[1], yy))
    band = max(band, 0.55 * (1.0 - smooth(0.28, 0.38, yy)))   # the running edge is dark too
    line = math.exp(-((yy - BAND[0]) / 0.045) ** 2) + math.exp(-((yy - BAND[1]) / 0.045) ** 2)
    return shade, gloss, band, line


def _wrapped_dot(draw, x, y, size, colour, width):
    """A small speck of 1-2 px (size 0..3 picks 1x1, 2x1, 1x2, 2x2), wrapped round the stone."""
    w, h = ((1, 1), (2, 1), (1, 2), (2, 2))[size]
    for dx in (-width, 0, width):
        draw.rectangle((x + dx, y, x + dx + w - 1, y + h - 1), fill=colour)


def granite_texture(profile, width=512, seed=7):
    px_per_unit = width / (2 * math.pi * profile.pts[5][0])
    height = max(128, int(round(profile.length * px_per_unit / 16.0)) * 16)
    rnd = random.Random(seed)

    # soft mottling, tiled round the stone
    gw, gh = width // 8, height // 8
    small = Image.new("L", (gw, gh))
    sp = small.load()
    for y in range(gh):
        for x in range(gw):
            sp[x, y] = rnd.randint(0, 255)
    wide = Image.new("L", (gw * 3, gh))
    for k in range(3):
        wide.paste(small, (k * gw, 0))
    mottle = wide.resize((width * 3, height), Image.BICUBIC).crop((width, 0, 2 * width, height))
    mp = mottle.load()

    albedo = Image.new("RGB", (width, height))
    ap = albedo.load()
    for y in range(height):
        for x in range(width):
            m = (mp[x, y] - 128) / 128.0
            g = rnd.randint(-9, 9)
            ap[x, y] = (int(176 + 13 * m + g), int(179 + 13 * m + g), int(187 + 12 * m + g))
    d = ImageDraw.Draw(albedo)
    area = width * height
    for _ in range(int(area * 0.022)):                   # dark grains
        v = rnd.randint(28, 70)
        _wrapped_dot(d, rnd.randrange(width), rnd.randrange(height), rnd.choice((0, 0, 0, 1, 2, 3)), (v, v, v + 6), width)
    for _ in range(int(area * 0.014)):                   # pale quartz
        v = rnd.randint(220, 250)
        _wrapped_dot(d, rnd.randrange(width), rnd.randrange(height), rnd.choice((0, 0, 1, 2)), (v, v, v + 4), width)
    for _ in range(int(area * 0.004)):                   # pinkish feldspar
        _wrapped_dot(d, rnd.randrange(width), rnd.randrange(height), rnd.choice((1, 2, 3)),
                     (rnd.randint(176, 206), rnd.randint(132, 156), rnd.randint(128, 150)), width)

    out = Image.new("RGB", (width, height))
    op = out.load()
    for y in range(height):
        shade, gloss, band, line = _row_light(profile, y, height)
        k = shade * (1.0 - 0.52 * band)
        for x in range(width):
            r, g, b = ap[x, y]
            r, g, b = r * k * (1 - 0.04 * band), g * k, b * k * (1 + 0.07 * band)
            lift = 46 * line
            r, g, b = r + lift, g + lift, b + lift
            r, g, b = r + (255 - r) * gloss, g + (255 - g) * gloss, b + (255 - b) * gloss
            op[x, y] = (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))
    return out.convert("RGBA")


# --- handle -------------------------------------------------------------------------------------

RAMP_LEVELS = 8
BOLT_LEVELS = 4


def handle_palette(team):
    pal = mm.Palette()
    base = TEAM_RGB[team]
    for i in range(RAMP_LEVELS):
        f = 0.36 + 0.78 * i / (RAMP_LEVELS - 1)
        c = mm.scale_rgb(base, f)
        if i == RAMP_LEVELS - 1:
            c = tuple(int(v + (255 - v) * 0.28) for v in c)
        pal.add("h%d" % i, c)
    for i in range(BOLT_LEVELS):
        f = 0.35 + 0.65 * i / (BOLT_LEVELS - 1)
        pal.add("b%d" % i, mm.scale_rgb((78, 80, 88), f))
    return pal


def _level(ny, levels):
    s = max(0.0, min(1.0, 0.55 + 0.45 * ny))
    return int(round(s * (levels - 1)))


def handle_path():
    """Centre line of the gooseneck in (x, y) relative to the middle of the cup (model units)."""
    r1, r2, top = 0.95, 0.70, 1.0
    pts = [(0.0, 0.2), (0.0, top)]
    for k in range(1, 6):
        a = math.pi - k * (math.pi / 2) / 5
        pts.append((r1 + r1 * math.cos(a), top + r1 * math.sin(a)))
    yc = top + r1
    pts.append((3.5, yc))
    for k in range(1, 5):
        a = math.pi / 2 - k * (math.pi / 2) / 4
        pts.append((3.5 + r2 * math.cos(a), yc - r2 + r2 * math.sin(a)))
    return pts


def handle_elements(cup_y, palette, tex="#1"):
    els = []
    path = [(8 + x, cup_y + y, 8.0) for x, y in handle_path()]
    side = (0.0, 0.0, 1.0)
    apothem = TUBE_R
    hw = apothem * math.tan(math.pi / 8) * 1.06
    tans = [mm.unit(mm.sub(path[i + 1], path[i])) for i in range(len(path) - 1)]

    def bend(i):
        """Turn between segment i-1 and i: (half angle tangent, turn direction), or None at the ends."""
        if i <= 0 or i >= len(tans):
            return None
        c = mm.sub(tans[i], tans[i - 1])
        if mm.length(c) < 1e-9:
            return None
        cosang = max(-1.0, min(1.0, mm.dot(tans[i], tans[i - 1])))
        return math.tan(math.acos(cosang) / 2.0), mm.unit(c)

    for i in range(len(path) - 1):
        p0, p1 = path[i], path[i + 1]
        t = tans[i]
        w = (-t[1], t[0], 0.0)
        seg = mm.length(mm.sub(p1, p0))
        for k in range(8):
            th = k * math.pi / 4
            o = (math.cos(th) * w[0] + math.sin(th) * side[0], math.cos(th) * w[1] + math.sin(th) * side[1],
                 math.cos(th) * w[2] + math.sin(th) * side[2])
            ext = []
            for j in (i, i + 1):                        # lengthen on the outside of each bend, no gaps
                b_ = bend(j)
                ext.append(0.03 + (apothem * b_[0] * max(0.0, -mm.dot(o, b_[1])) if b_ else 0.0))
            mid = mm.add(mm.mul(mm.add(p0, p1), 0.5), mm.mul(t, (ext[1] - ext[0]) / 2.0))
            e = mm.cross(t, o)
            centre = mm.add(mid, mm.mul(o, apothem))
            uv = palette.uv("h%d" % _level(o[1], RAMP_LEVELS))
            els.append(mm.quad_element(centre, e, t, o, hw, seg / 2.0 + (ext[0] + ext[1]) / 2.0, tex, uv))
    # closed tip
    p_end, t_end = path[-1], mm.unit(mm.sub(path[-1], path[-2]))
    e = side
    els.append(mm.quad_element(mm.add(p_end, mm.mul(t_end, 0.04)), e, mm.cross(t_end, e), t_end,
                               apothem * 0.9, apothem * 0.9, tex,
                               palette.uv("h%d" % _level(t_end[1], RAMP_LEVELS))))
    # the dark bolt and washer where the handle is fixed
    side_uv = palette.uv("b1")
    top_uv = palette.uv("b%d" % (BOLT_LEVELS - 1))
    els.extend(mm.prism_y(8.0, 8.0, 0.95, cup_y - 0.12, cup_y + 0.55, 8, side_uv, tex, caps=(True, False),
                          shade=False, tint=True, cap_uv=top_uv))
    return els


def stone_model(team, profile):
    """(textures, elements) of one stone."""
    pal = handle_palette(team)
    cup_y = 8 + profile.pts[-1][1]
    els = body_elements(profile, "#0") + handle_elements(cup_y, pal, "#1")
    return {"0": "stone_granite", "1": "stone_handle_%s" % team}, els, pal
