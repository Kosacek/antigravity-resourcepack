# -*- coding: utf-8 -*-
"""Brooms and the delivery stick: boxes and thin prisms with a palette of solid colours.

Both are normally lit (thin sticks look fine under vanilla lighting). Model y runs up the shaft
and the bottom of the head is at y = 0, so the pad sits on the ground when held with the hand
transforms below.
"""
import mc_model as mm

TEAM_PAD = {"red": ((206, 36, 44), (236, 84, 84), (140, 20, 30)),
            "yellow": ((246, 198, 28), (255, 230, 96), (186, 138, 10))}

# Right-hand display transforms (translation in 1/16 block, rotation in degrees). In the hand space
# of a hanging arm item +z is up and +y is forward, so rotating 90 degrees about x stands the shaft
# upright with the pad down; the -4 lowers it so the pad is at the feet when the hand is ~0.75 up.
HAND = {
    "thirdperson_righthand": {"rotation": [90, 0, 0], "translation": [0, 0, -4], "scale": [1, 1, 1]},
    "firstperson_righthand": {"rotation": [0, 35, 14], "translation": [-1, 0, 0], "scale": [0.75, 0.75, 0.75]},
}


def broom_palette(team):
    pad, pad_hi, pad_lo = TEAM_PAD[team]
    pal = mm.Palette()
    pal.add("pad", pad)
    pal.add("pad_hi", pad_hi)
    pal.add("pad_lo", pad_lo)
    pal.add("bristle", (30, 30, 34))
    pal.add("bristle2", (52, 52, 58))
    pal.add("shaft", (176, 180, 188))
    pal.add("shaft_lo", (96, 100, 108))
    pal.add("grip", (34, 34, 38))
    pal.add("grip_cap", (70, 72, 80))
    pal.add("bracket", (64, 66, 74))
    pal.add("stripe", (240, 242, 246))
    return pal


def broom_elements(pal):
    B = lambda a, b, name, **kw: mm.box_element(a, b, pal.uv(name), **kw)
    els = []
    # dark bristles under the pad: eight slats of slightly different length
    for i in range(8):
        x0 = 4.2 + i * 0.95
        els.append(B([x0, 0.0, 6.9], [x0 + 0.95, 1.3 + 0.1 * (i % 2), 9.1],
                     "bristle" if i % 2 == 0 else "bristle2"))
    # the team coloured pad: body, a lighter top plate, rounded end caps and a white stripe
    els.append(B([4.0, 1.3, 6.6], [12.0, 2.7, 9.4], "pad"))
    els.append(B([4.4, 2.7, 6.9], [11.6, 3.05, 9.1], "pad_hi"))
    els.append(B([3.7, 1.5, 6.9], [4.0, 2.6, 9.1], "pad_lo"))
    els.append(B([12.0, 1.5, 6.9], [12.3, 2.6, 9.1], "pad_lo"))
    els.append(B([4.3, 1.85, 9.4], [11.7, 2.25, 9.46], "stripe"))
    els.append(B([4.3, 1.85, 6.54], [11.7, 2.25, 6.6], "stripe"))
    # hinge bracket
    els.append(B([7.0, 3.05, 7.3], [9.0, 4.3, 8.7], "bracket"))
    els.append(B([6.65, 3.3, 7.7], [7.0, 4.0, 8.3], "shaft_lo"))
    els.append(B([9.0, 3.3, 7.7], [9.35, 4.0, 8.3], "shaft_lo"))
    # shaft (about 1.5 blocks), foam grip and end cap
    els.extend(mm.prism_y(8, 8, 0.62, 4.3, 29.0, 8, pal.uv("shaft"), caps=(False, False)))
    els.append(B([7.15, 17.0, 7.15], [8.85, 17.3, 8.85], "shaft_lo"))
    els.extend(mm.prism_y(8, 8, 0.86, 17.3, 28.4, 8, pal.uv("grip"), caps=(False, False)))
    els.extend(mm.prism_y(8, 8, 0.8, 28.4, 29.1, 8, pal.uv("grip_cap"), caps=(True, False)))
    return els


def stick_palette():
    pal = mm.Palette()
    pal.add("black", (24, 24, 27))
    pal.add("dark", (54, 56, 62))
    pal.add("steel", (122, 126, 134))
    pal.add("tape", (238, 114, 28))
    pal.add("tape2", (196, 84, 16))
    pal.add("cap", (82, 84, 92))
    return pal


def stick_elements(pal):
    B = lambda a, b, name, **kw: mm.box_element(a, b, pal.uv(name), **kw)
    els = []
    # forked head: a neck block and two prongs splayed out, that cup a stone's handle between them
    els.append(B([7.15, 3.4, 7.0], [8.85, 5.0, 9.0], "dark"))
    for sign in (1, -1):
        els.append(B([7.4, 0.5, 7.0], [8.6, 3.9, 9.0], "dark",
                     rotation={"origin": [8, 3.9, 8], "x": 0, "y": 0, "z": 30 * sign}))
        els.append(B([7.4, 0.2, 7.0], [8.6, 1.0, 9.0], "steel",
                     rotation={"origin": [8, 3.9, 8], "x": 0, "y": 0, "z": 30 * sign}))
    # the stick: black shaft, coloured grip tape wound in bands near the top, end cap
    els.extend(mm.prism_y(8, 8, 0.6, 4.6, 24.0, 8, pal.uv("black"), caps=(False, False)))
    for i in range(4):
        y0 = 13.2 + i * 2.0
        els.extend(mm.prism_y(8, 8, 0.82, y0, y0 + 2.0, 8, pal.uv("tape" if i % 2 == 0 else "tape2"),
                              caps=(False, False)))
    els.extend(mm.prism_y(8, 8, 0.84, 21.2, 24.0, 8, pal.uv("black"), caps=(False, False)))
    els.extend(mm.prism_y(8, 8, 0.8, 24.0, 24.5, 8, pal.uv("cap"), caps=(True, False)))
    return els


def build(writer):
    counts = {}
    for team in ("red", "yellow"):
        pal = broom_palette(team)
        els = broom_elements(pal)
        writer.texture("broom_%s" % team, pal.image())
        writer.model("broom_%s" % team, {"0": "broom_%s" % team}, els, display=HAND)
        writer.item("broom_%s" % team, unlit=False)
        counts["broom_%s" % team] = len(els)
    pal = stick_palette()
    els = stick_elements(pal)
    writer.texture("delivery_stick", pal.image())
    writer.model("delivery_stick", {"0": "delivery_stick"}, els, display=HAND)
    writer.item("delivery_stick", unlit=False)
    counts["delivery_stick"] = len(els)
    return counts
