"""Preview the rolling balls: body picture + markings turned by a ball rotation,
seen from a camera looking down at the table. Markings behind the centre plane are
dropped, as the body picture hides them in the game.

Usage:  python preview_rolling.py <built pack folder> <out.png>
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw

from render import FACES, _corners

TILE = 160
SCALE = 15.0     # pixels per model unit


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _rx(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _apply(m, p):
    return tuple(sum(m[i][k] * p[k] for k in range(3)) for i in range(3))


def render(pack, name, roll, pitch=-50):
    root = os.path.join(pack, "assets", "swpool")
    model = json.load(open(os.path.join(root, "models", "item", "hg", "marks_%s.json" % name)))
    body = Image.open(os.path.join(root, "textures", "item", "hg", "body_%s.png" % name)).convert("RGBA")
    img = Image.new("RGBA", (TILE, TILE), (34, 110, 62, 255))
    size = int(8 * SCALE)
    img.alpha_composite(body.resize((size, size), Image.LANCZOS), ((TILE - size) // 2, (TILE - size) // 2))
    view = _rx(-pitch)                      # camera tilted to look down at the table
    full = _matmul(view, roll)
    draw = ImageDraw.Draw(img)
    polys = []
    cache = {}
    for el in model["elements"]:
        pts = [(p[0] - 8, p[1] - 8, p[2] - 8) for p in _corners(el)]
        pts = [_apply(full, p) for p in pts]
        for face, spec in el["faces"].items():
            idx, _ = FACES[face]
            q = [pts[i] for i in idx]
            ax, ay, az = [q[1][k] - q[0][k] for k in range(3)]
            bx, by, bz = [q[3][k] - q[0][k] for k in range(3)]
            nz = ax * by - ay * bx
            if nz < 0:                     # facing away from the camera (+z)
                continue
            if face not in ("up", "down"):
                q = [q[3], q[2], q[1], q[0]]   # Minecraft maps the texture top to the face top
            tname = model["textures"][spec["texture"].lstrip("#")]
            if tname not in cache:
                cache[tname] = Image.open(os.path.join(root, "textures", "item", "hg",
                                                       tname.split("/")[-1] + ".png")).convert("RGBA")
            tex = cache[tname]
            g = 20
            for i in range(g):
                for j in range(g):
                    u, v = (i + 0.5) / g, (j + 0.5) / g
                    px = tex.getpixel((min(tex.width - 1, int(u * tex.width)), min(tex.height - 1, int(v * tex.height))))
                    if px[3] < 128:
                        continue

                    def at(uu, vv):
                        top = [q[0][k] + (q[1][k] - q[0][k]) * uu for k in range(3)]
                        bot = [q[3][k] + (q[2][k] - q[3][k]) * uu for k in range(3)]
                        return [top[k] + (bot[k] - top[k]) * vv for k in range(3)]
                    cell = [at(i / g, j / g), at((i + 1) / g, j / g), at((i + 1) / g, (j + 1) / g), at(i / g, (j + 1) / g)]
                    depth = sum(c[2] for c in cell) / 4
                    if depth < 0:          # behind the body picture
                        continue
                    polys.append((depth, [(TILE / 2 + c[0] * SCALE, TILE / 2 - c[1] * SCALE) for c in cell], px))
    for _, poly, col in sorted(polys, key=lambda p: p[0]):
        draw.polygon(poly, fill=col)
    return img


def main(pack, out):
    names = ["ball_01", "ball_06", "ball_08", "ball_09", "ball_11", "ball_14", "cueball"]
    steps = 6
    sheet = Image.new("RGBA", (TILE * steps, TILE * len(names)), (20, 20, 20, 255))
    for r, name in enumerate(names):
        for s in range(steps):
            # roll forward around the x axis, with a little side spin, like a struck ball
            roll = _matmul(_rx(s * 33.0), _ry(20.0 + s * 11.0))
            sheet.paste(render(pack, name, roll), (s * TILE, r * TILE))
    sheet.save(out)
    print("preview:", os.path.abspath(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
