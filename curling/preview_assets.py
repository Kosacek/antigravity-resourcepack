# -*- coding: utf-8 -*-
"""Software preview of the curling models, read straight from the generated JSON and PNG files.

Usage:  python preview_assets.py <output folder of build_assets.py> <out.png>

Renders every item from three angles into <out.png>, and a close-up of the stones into
<out>_stone.png. Same geometry and UVs as the JSON: elements, multi-axis rotation, per-face UV
rectangles, nearest-neighbour texture lookup, back-face culling, a z-buffer. Faces with the
unlit tint (-66052, #FEFDFC) are drawn flat like the patched item shader does; others get a
simple vanilla-style direction shading. Needs Pillow and numpy.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

NS = "curling"
UNLIT_TINT = -66052
BG = (150, 168, 188)
DIRECTION_SHADE = {"up": 1.0, "down": 0.5, "north": 0.8, "south": 0.8, "east": 0.6, "west": 0.6}

# corner (x, y, z) selectors, 0 = min, 1 = max, in Minecraft's vertex order for each face;
# corner k gets uv (u0,v0), (u0,v1), (u1,v1), (u1,v0)
FACE_CORNERS = {
    "down": ((0, 0, 1), (0, 0, 0), (1, 0, 0), (1, 0, 1)),
    "up": ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),
    "north": ((1, 1, 0), (1, 0, 0), (0, 0, 0), (0, 1, 0)),
    "south": ((0, 1, 1), (0, 0, 1), (1, 0, 1), (1, 1, 1)),
    "west": ((0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)),
    "east": ((1, 1, 1), (1, 0, 1), (1, 0, 0), (1, 1, 0)),
}
NORMALS = {"down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1), "south": (0, 0, 1),
           "west": (-1, 0, 0), "east": (1, 0, 0)}


def rot_matrix(ax, ay, az):
    a, b, c = math.radians(ax), math.radians(ay), math.radians(az)
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return rz @ ry @ rx


def axis_matrix(axis, angle):
    return {"x": rot_matrix(angle, 0, 0), "y": rot_matrix(0, angle, 0), "z": rot_matrix(0, 0, angle)}[axis]


class Pack(object):
    def __init__(self, folder):
        self.root = os.path.join(folder, "assets", NS)
        self.textures = {}

    def texture(self, ref):
        if ref not in self.textures:
            ns, _, path = ref.partition(":")
            file = os.path.join(os.path.dirname(self.root), ns, "textures", path + ".png")
            self.textures[ref] = np.array(Image.open(file).convert("RGBA"))
        return self.textures[ref]

    def load_item(self, name):
        with open(os.path.join(self.root, "items", name + ".json")) as fh:
            item = json.load(fh)["model"]
        unlit = any(t.get("value") == UNLIT_TINT for t in item.get("tints", []))
        with open(os.path.join(self.root, "models", "item", item["model"].split("/")[-1] + ".json")) as fh:
            model = json.load(fh)
        return model, unlit

    def faces(self, model, unlit):
        """All faces of a model as dicts: verts (4,3), uv rectangle, texture array, normal, shade."""
        out = []
        for el in model["elements"]:
            lo, hi = np.array(el["from"], float), np.array(el["to"], float)
            rot = el.get("rotation")
            if rot is None:
                m, origin = np.eye(3), np.zeros(3)
            else:
                origin = np.array(rot["origin"], float)
                if "axis" in rot:
                    m = axis_matrix(rot["axis"], rot["angle"])
                else:
                    m = rot_matrix(rot.get("x", 0), rot.get("y", 0), rot.get("z", 0))
            for name, face in el["faces"].items():
                pick = np.array(FACE_CORNERS[name], float)
                verts = lo + pick * (hi - lo)
                verts = (verts - origin) @ m.T + origin
                normal = m @ np.array(NORMALS[name], float)
                ref = model["textures"][face["texture"].lstrip("#")]
                tinted = "tintindex" in face
                flat = unlit and tinted
                if flat:
                    shade = 1.0
                else:                                  # nearest axis direction, like the item shader
                    axis = max(NORMALS, key=lambda d: float(np.dot(normal, NORMALS[d])))
                    shade = DIRECTION_SHADE[axis]
                out.append({"verts": verts, "uv": face["uv"], "tex": self.texture(ref),
                            "normal": normal, "shade": shade})
        return out


def view_basis(yaw, pitch):
    """Camera looking at the model from yaw/pitch (degrees). yaw 0 = from the south (+z), where +x
    is on the right; returns (right, up, towards_camera)."""
    y, p = math.radians(yaw), math.radians(pitch)
    d = np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])
    right = np.array([math.cos(y), 0.0, -math.sin(y)])
    up = np.cross(d, right)
    return right, up, d


def project(faces, views, centre):
    """Per view: min/max screen extents of every vertex."""
    ext = []
    for yaw, pitch in views:
        right, up, _ = view_basis(yaw, pitch)
        pts = np.concatenate([f["verts"] for f in faces]) - centre
        xs, ys = pts @ right, pts @ up
        ext.append((xs.min(), xs.max(), ys.min(), ys.max()))
    return ext


def render(faces, yaw, pitch, size, scale, centre, shift=(0.0, 0.0), ss=2):
    w, h = size[0] * ss, size[1] * ss
    img = np.zeros((h, w, 3), np.float32)
    img[:] = BG
    zbuf = np.full((h, w), -1e9, np.float32)
    right, up, toward = view_basis(yaw, pitch)
    s = scale * ss
    cx, cy = w / 2.0 + shift[0] * ss, h / 2.0 - shift[1] * ss
    for f in faces:
        if float(np.dot(f["normal"], toward)) <= 1e-4:      # back-face culling
            continue
        pts = f["verts"] - centre
        sx = cx + (pts @ right) * s
        sy = cy - (pts @ up) * s
        sz = pts @ toward
        u0, v0, u1, v1 = f["uv"]
        uvs = [(u0, v0), (u0, v1), (u1, v1), (u1, v0)]
        tex = f["tex"]
        th, tw = tex.shape[0], tex.shape[1]
        for tri in ((0, 1, 2), (0, 2, 3)):
            _raster(img, zbuf, [(sx[i], sy[i], sz[i]) for i in tri], [uvs[i] for i in tri], tex, tw, th, f["shade"])
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    return out.resize(size, Image.LANCZOS) if ss > 1 else out


def _raster(img, zbuf, p, uv, tex, tw, th, shade):
    h, w = zbuf.shape
    x0 = max(int(math.floor(min(q[0] for q in p))), 0)
    x1 = min(int(math.ceil(max(q[0] for q in p))), w - 1)
    y0 = max(int(math.floor(min(q[1] for q in p))), 0)
    y1 = min(int(math.ceil(max(q[1] for q in p))), h - 1)
    if x1 < x0 or y1 < y0:
        return
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = p
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(den) < 1e-12:
        return
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
    l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
    l3 = 1.0 - l1 - l2
    eps = -1e-3
    inside = (l1 >= eps) & (l2 >= eps) & (l3 >= eps)
    if not inside.any():
        return
    z = l1 * az + l2 * bz + l3 * cz
    u = l1 * uv[0][0] + l2 * uv[1][0] + l3 * uv[2][0]
    v = l1 * uv[0][1] + l2 * uv[1][1] + l3 * uv[2][1]
    tx = np.clip((u / 16.0 * tw).astype(int), 0, tw - 1)
    ty = np.clip((v / 16.0 * th).astype(int), 0, th - 1)
    texel = tex[ty, tx]
    sub_z = zbuf[y0:y1 + 1, x0:x1 + 1]
    ok = inside & (texel[..., 3] >= 128) & (z > sub_z)
    if not ok.any():
        return
    sub = img[y0:y1 + 1, x0:x1 + 1]
    sub[ok] = texel[..., :3][ok].astype(np.float32) * shade
    sub_z[ok] = z[ok]


# --- sheet -------------------------------------------------------------------------------------

def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def bbox_centre(faces):
    pts = np.concatenate([f["verts"] for f in faces])
    return (pts.min(axis=0) + pts.max(axis=0)) / 2.0, pts.max(axis=0) - pts.min(axis=0)


def fit(faces, views, tile, margin=0.10):
    """Common scale for all views of a model, and the per-view shift that centres it."""
    centre, _ = bbox_centre(faces)
    ext = project(faces, views, centre)
    scale = min(min(tile[0] * (1 - 2 * margin) / max(e[1] - e[0], 1e-6),
                    tile[1] * (1 - 2 * margin) / max(e[3] - e[2], 1e-6)) for e in ext)
    shifts = [(-(e[0] + e[1]) / 2.0 * scale, -(e[2] + e[3]) / 2.0 * scale) for e in ext]
    return centre, scale, shifts


ROWS = [  # item, tile size, views as (label, yaw, pitch)
    ("stone_red", (330, 300), [("side", 20, 14), ("handle side (+x)", 90, 22), ("from above", 20, 70)]),
    ("stone_yellow", (330, 300), [("side", 20, 14), ("handle side (+x)", 90, 22), ("from above", 20, 70)]),
    ("broom_red", (330, 430), [("front", 20, 12), ("side", 110, 8), ("pad from below", 30, -50)]),
    ("broom_yellow", (330, 430), [("front", 20, 12), ("side", 110, 8), ("pad from below", 30, -50)]),
    ("delivery_stick", (330, 430), [("front", 20, 12), ("side", 110, 8), ("head from below", 20, -45)]),
    ("house", (330, 330), [("from above", 0, 90), ("oblique", 20, 35), ("low", 20, 8)]),
    ("aim_marker", (330, 330), [("from above", 0, 90), ("oblique", 20, 35), ("low", 20, 8)]),
]


def make_sheet(pack, out_path):
    lab = font(15)
    small = font(12)
    label_w = 190
    width = label_w + 3 * 330
    height = sum(r[1][1] for r in ROWS)
    sheet = Image.new("RGB", (width, height), (30, 32, 38))
    d = ImageDraw.Draw(sheet)
    y = 0
    for name, tile, views in ROWS:
        model, unlit = pack.load_item(name)
        faces = pack.faces(model, unlit)
        centre, size = bbox_centre(faces)
        centre, scale, shifts = fit(faces, [(v[1], v[2]) for v in views], tile)
        d.text((10, y + 10), name, fill=(240, 240, 240), font=lab)
        d.text((10, y + 32), "%d elements" % len(model["elements"]), fill=(170, 175, 185), font=small)
        d.text((10, y + 50), "%.2f x %.2f x %.2f blocks" % tuple(size / 16.0), fill=(170, 175, 185), font=small)
        d.text((10, y + 68), "unlit" if unlit else "lit", fill=(170, 175, 185), font=small)
        for i, (label, yaw, pitch) in enumerate(views):
            tile_img = render(faces, yaw, pitch, tile, scale, centre, shifts[i])
            sheet.paste(tile_img, (label_w + i * 330, y))
            d.text((label_w + i * 330 + 6, y + tile[1] - 18), label, fill=(30, 36, 44), font=small)
        y += tile[1]
    sheet.save(out_path)
    print("wrote", out_path)


def make_stone_closeup(pack, out_path):
    big = (640, 560)
    sheet = Image.new("RGB", (big[0] * 2, big[1] * 2), (30, 32, 38))
    d = ImageDraw.Draw(sheet)
    lab = font(15)
    jobs = [("stone_red", 25, 14, "red, side"), ("stone_red", 100, 30, "red, handle side (+x)"),
            ("stone_yellow", 200, 55, "yellow, from above"), ("stone_red", 0, 90, "red, straight down")]
    for i, (name, yaw, pitch, label) in enumerate(jobs):
        model, unlit = pack.load_item(name)
        faces = pack.faces(model, unlit)
        centre, _ = bbox_centre(faces)
        ext = project(faces, [(yaw, pitch)], centre)[0]
        scale = min(big[0] * 0.8 / (ext[1] - ext[0]), big[1] * 0.8 / (ext[3] - ext[2]))
        shift = (-(ext[0] + ext[1]) / 2.0 * scale, -(ext[2] + ext[3]) / 2.0 * scale)
        img = render(faces, yaw, pitch, big, scale, centre, shift, ss=3)
        ox, oy = (i % 2) * big[0], (i // 2) * big[1]
        sheet.paste(img, (ox, oy))
        d.text((ox + 8, oy + 8), label, fill=(20, 24, 30), font=lab)
    sheet.save(out_path)
    print("wrote", out_path)


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    pack = Pack(argv[1])
    out = argv[2]
    make_sheet(pack, out)
    make_stone_closeup(pack, os.path.splitext(out)[0] + "_stone.png")


if __name__ == "__main__":
    main(sys.argv)
