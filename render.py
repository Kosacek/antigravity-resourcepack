"""Tiny software renderer for Minecraft item models (boxes + single-axis rotation).

Good enough to check silhouettes and colours without starting the game.
"""
import math
import os

from PIL import Image, ImageDraw

FACES = {  # face -> (corner indices, normal)
    "north": ((1, 0, 2, 3), (0, 0, -1)), "south": ((4, 5, 7, 6), (0, 0, 1)),
    "west": ((0, 4, 6, 2), (-1, 0, 0)), "east": ((5, 1, 3, 7), (1, 0, 0)),
    "down": ((0, 1, 5, 4), (0, -1, 0)), "up": ((6, 7, 3, 2), (0, 1, 0)),
}


def _rot(p, axis, deg, o):
    a = math.radians(deg)
    x, y, z = p[0] - o[0], p[1] - o[1], p[2] - o[2]
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        y, z = y * c - z * s, y * s + z * c
    elif axis == "y":
        x, z = x * c + z * s, -x * s + z * c
    else:
        x, y = x * c - y * s, x * s + y * c
    return (x + o[0], y + o[1], z + o[2])


def _corners(el):
    (x0, y0, z0), (x1, y1, z1) = el["from"], el["to"]
    pts = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    # order: index = xbit + 2*ybit + 4*zbit
    pts = [(x0 if i & 1 == 0 else x1, y0 if i & 2 == 0 else y1, z0 if i & 4 == 0 else z1) for i in range(8)]
    r = el.get("rotation")
    if r and r.get("angle"):
        pts = [_rot(p, r["axis"], r["angle"], r["origin"]) for p in pts]
    return pts


def _view(p, yaw, pitch):
    x, y, z = p[0] - 8, p[1] - 8, p[2] - 8
    a = math.radians(yaw)
    x, z = x * math.cos(a) - z * math.sin(a), x * math.sin(a) + z * math.cos(a)
    b = math.radians(pitch)
    y, z = y * math.cos(b) - z * math.sin(b), y * math.sin(b) + z * math.cos(b)
    return x, y, z


def _shade(n):
    lx, ly, lz = -0.3, 0.85, 0.45
    d = max(0.0, n[0] * lx + n[1] * ly + n[2] * lz)
    return 0.45 + 0.55 * d


def render_model(model, textures, size=150, yaw=30, pitch=-15, scale=13):
    img = Image.new("RGBA", (size, size), (40, 110, 60, 255))
    draw = ImageDraw.Draw(img)
    polys = []
    tex_cache = {}
    for el in model["elements"]:
        pts = _corners(el)
        for face, spec in el["faces"].items():
            idx, _ = FACES[face]
            quad = [pts[i] for i in idx]
            # normal from geometry (rotation-aware)
            ax, ay, az = [quad[1][k] - quad[0][k] for k in range(3)]
            bx, by, bz = [quad[3][k] - quad[0][k] for k in range(3)]
            n = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
            ln = math.sqrt(sum(c * c for c in n)) or 1
            n = tuple(c / ln for c in n)
            vq = [_view(p, yaw, pitch) for p in quad]
            vn = _view((n[0] + 8, n[1] + 8, n[2] + 8), yaw, pitch)
            if vn[2] > 1e-6:          # facing away (camera looks toward -z)
                continue
            tex_name = model["textures"][spec["texture"].lstrip("#")]
            if tex_name not in tex_cache:
                tex_cache[tex_name] = Image.open(textures(tex_name)).convert("RGBA")
            tex = tex_cache[tex_name]
            sh = _shade(n)
            g = 6
            for i in range(g):
                for j in range(g):
                    u0, u1, v0, v1 = i / g, (i + 1) / g, j / g, (j + 1) / g
                    px = tex.getpixel((min(tex.width - 1, int((u0 + u1) / 2 * tex.width)),
                                       min(tex.height - 1, int((v0 + v1) / 2 * tex.height))))
                    if px[3] < 128:
                        continue

                    def lerp(u, v):
                        top = [vq[0][k] + (vq[1][k] - vq[0][k]) * u for k in range(3)]
                        bot = [vq[3][k] + (vq[2][k] - vq[3][k]) * u for k in range(3)]
                        return [top[k] + (bot[k] - top[k]) * v for k in range(3)]
                    cell = [lerp(u0, v0), lerp(u1, v0), lerp(u1, v1), lerp(u0, v1)]
                    depth = sum(c[2] for c in cell) / 4
                    col = tuple(int(px[k] * sh) for k in range(3)) + (255,)
                    polys.append((depth, [(size / 2 + c[0] * scale, size / 2 - c[1] * scale) for c in cell], col))
    for depth, poly, col in sorted(polys, key=lambda p: -p[0]):
        draw.polygon(poly, fill=col)
    return img


def preview(models, tex_dir, path):
    def textures(name):
        return os.path.join(tex_dir, name.split("/")[-1] + ".png")
    names = ["ball_%02d" % n for n in range(1, 16)] + ["cueball", "cueball_clean", "red", "yellow", "green",
                                                        "brown", "blue", "pink", "black"]
    cols = 8
    tile = 150
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * tile, rows * tile * 2), (30, 30, 30, 255))
    for i, name in enumerate(names):
        m = models[name]
        x, y = (i % cols) * tile, (i // cols) * tile * 2
        sheet.paste(render_model(m, textures, yaw=25, pitch=-12), (x, y))
        sheet.paste(render_model(m, textures, yaw=-40, pitch=-55), (x, y + tile))
    sheet.save(path)
    print("preview:", os.path.abspath(path))
