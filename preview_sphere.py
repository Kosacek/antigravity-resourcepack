"""Check and preview the sphere balls.

1. Geometry: rebuilds every quad's corners with Minecraft's element rotation (Rz*Ry*Rx about
   the origin) and checks each quad sits tangent to the sphere where its texture patch says.
2. Look: ray-traces the textured ball at several roll angles, with the lighting overlay on
   top, as seen from a player looking down at the table.

Usage:  python preview_sphere.py <built folder> <out.png>
"""
import json
import math
import os
import sys

from PIL import Image

from build_sphere import C, R, direction

TILE = 150


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def apply(m, p):
    return tuple(sum(m[i][k] * p[k] for k in range(3)) for i in range(3))


def check_geometry(model):
    worst = 0.0
    for el in model["elements"]:
        r = el["rotation"]
        m = mul(mul(rot_z(math.radians(r["z"])), rot_y(math.radians(r["y"]))), rot_x(math.radians(r["x"])))
        f, t = el["from"], el["to"]
        centre = apply(m, ((f[0] + t[0]) / 2 - C, (f[1] + t[1]) / 2 - C, f[2] - C))
        normal = apply(m, (0, 0, 1))
        u0, v0, u1, v1 = el["faces"]["south"]["uv"]
        lon = (u0 + u1) / 2 / 16 * 2 * math.pi
        lat = math.pi / 2 - (v0 + v1) / 2 / 16 * math.pi
        want = direction(lat, lon)
        cn = math.sqrt(sum(c * c for c in centre))
        err = max(abs(centre[k] / cn - want[k]) for k in range(3)) + max(abs(normal[k] - want[k]) for k in range(3))
        worst = max(worst, err)
        # the face's right edge must point east (increasing longitude) so the texture isn't mirrored
        right = apply(m, (1, 0, 0))
        east = (math.cos(lon), 0, -math.sin(lon))
        assert sum(right[k] * east[k] for k in range(3)) > 0.99, el
    return worst


def render(tex, light, roll, pitch_deg=50):
    img = Image.new("RGBA", (TILE, TILE), (34, 110, 62, 255))
    px = img.load()
    view = rot_x(math.radians(pitch_deg))        # tilt the ball towards a camera looking down
    m = mul(view, roll)
    inv = [[m[j][i] for j in range(3)] for i in range(3)]
    tw, th = tex.size
    rr = TILE * 0.42
    for y in range(TILE):
        for x in range(TILE):
            nx, ny = (x + 0.5 - TILE / 2) / rr, -(y + 0.5 - TILE / 2) / rr
            d2 = nx * nx + ny * ny
            if d2 > 1:
                continue
            p = apply(inv, (nx, ny, math.sqrt(1 - d2)))      # back into the ball's own frame
            lat = math.asin(max(-1, min(1, p[1])))
            lon = math.atan2(p[0], p[2]) % (2 * math.pi)
            px[x, y] = tex.getpixel((min(tw - 1, int(lon / (2 * math.pi) * tw)),
                                     min(th - 1, int((math.pi / 2 - lat) / math.pi * th)))) + (255,)
    size = int(rr * 2 * 1.0)
    img.alpha_composite(light.resize((size, size), Image.LANCZOS), (int(TILE / 2 - rr), int(TILE / 2 - rr)))
    return img


def main(out_dir, out):
    root = os.path.join(out_dir, "assets", "swpool")
    model = json.load(open(os.path.join(root, "models", "item", "ball_09.json")))
    print("quads: %d, worst placement error: %.5f" % (len(model["elements"]), check_geometry(model)))
    light = Image.open(os.path.join(root, "textures", "item", "hg", "ball_light.png")).convert("RGBA")
    names = ["ball_01", "ball_06", "ball_08", "ball_09", "ball_11", "ball_14", "cueball", "red"]
    steps = 6
    sheet = Image.new("RGBA", (TILE * steps, TILE * len(names)), (20, 20, 20, 255))
    for r, name in enumerate(names):
        tex = Image.open(os.path.join(root, "textures", "item", "hg", "sphere_%s.png" % name)).convert("RGB")
        for s in range(steps):
            roll = mul(rot_x(math.radians(s * 33.0)), rot_y(math.radians(80 + s * 15.0)))
            sheet.paste(render(tex, light, roll), (s * TILE, r * TILE))
    sheet.save(out)
    print("preview:", os.path.abspath(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
