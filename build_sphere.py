"""Real 3D pool balls: a smooth sphere mesh with the ball's markings painted on.

Minecraft 26.x model elements can be rotated on all three axes ("rotation": {"x","y","z"},
applied as Rz*Ry*Rx), so each ball is LON x LAT thin quads, each one tangent to the sphere
and showing its own patch of an equirectangular texture. The pack rotates its ball displays
as they roll, so the numbers and stripes roll with the ball, and nothing on the server has
to follow the balls.

The mesh is unlit ("shade": false): Minecraft shades a face by its nearest axis direction,
which would light a sphere in six flat patches. Instead one see-through lighting overlay
(soft shadow towards the edge and a gloss highlight) faces the viewer in front of each ball;
the server stacks it on the ball once.

Usage:  python build_sphere.py <original pack folder> <output folder>
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from build_sprites import NS, POOL, SNOOKER, WHITE, DOT

R = 4.0                  # radius in model units (the pack's balls span 4..12)
C = 8.0
LON, LAT = 32, 16        # quads around and from pole to pole
TEX_W, TEX_H = 512, 256  # equirectangular texture
STRIPE_HALF = math.asin(0.52)        # stripe covers latitudes within +-31 degrees
NUMBER_RADIUS = 0.42                 # number circle, as a fraction of the ball radius (chord)
DOT_RADIUS = 0.13
LIGHT_SIZE = 1.6                   # the overlay square, as a fraction of the radius: covers the
                                   # ball's outline even near the edge of the screen
DISPLAY_SCALE = 0.5                # the pool pack shows its balls at this scale
SPHERE_RADIUS = R / 16.0 * DISPLAY_SCALE * 1.012   # in blocks, a hair over the mesh
# Tint colours no vanilla item uses, which the patched item shader looks for
BALL_TINT = 0xFEFDFC               # balls: skip the per-face lighting
OVERLAY_TINT = 0xFEFDFB            # lighting overlays: ray-traced shading
ITEM_VSH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "item.vsh")   # from the 26.3 client jar
ITEM_FSH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "item.fsh")
INK = (18, 18, 18)


# --- sphere maths ---------------------------------------------------------------------

def direction(lat, lon):
    """lat/lon in radians -> unit vector; lon is measured from +Z towards +X."""
    return (math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon))


def frame(lat, lon):
    """(east, north, normal) at a point, a right-handed basis."""
    e = (math.cos(lon), 0.0, -math.sin(lon))
    u = (-math.sin(lat) * math.sin(lon), math.cos(lat), -math.sin(lat) * math.cos(lon))
    return e, u, direction(lat, lon)


def euler_zyx(m):
    """Angles (x, y, z) in degrees with m = Rz(z) * Ry(y) * Rx(x) (Minecraft's element rotation)."""
    b = -math.asin(max(-1.0, min(1.0, m[2][0])))
    a = math.atan2(m[2][1], m[2][2])
    c = math.atan2(m[1][0], m[0][0])
    return math.degrees(a), math.degrees(b), math.degrees(c)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# --- textures -------------------------------------------------------------------------

class Decal(object):
    """A flat picture (number circle, dot) stuck onto the sphere around a centre direction."""

    def __init__(self, lat, lon, radius, image):
        self.e, self.u, self.n = frame(lat, lon)
        self.radius = radius
        self.image = image.convert("RGBA")

    def sample(self, p):
        if dot(p, self.n) <= 0.0:
            return None
        x, y = dot(p, self.e) / self.radius, dot(p, self.u) / self.radius   # -1..1 inside the decal
        if x * x + y * y > 1.0:
            return None
        w, h = self.image.size
        px = self.image.getpixel((min(w - 1, int((x + 1) / 2 * w)), min(h - 1, int((1 - y) / 2 * h))))
        return px if px[3] >= 128 else None


def number_image(n, font):
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=WHITE + (255,))
    text = str(n)
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text((size / 2.0 - w / 2.0 - box[0], size / 2.0 - h / 2.0 - box[1]), text, fill=INK + (255,), font=font)
    if n in (6, 9):                       # real balls underline 6 and 9
        uy = size / 2.0 + h / 2.0 + size * 0.04
        d.rectangle((size / 2.0 - w / 2.0, uy, size / 2.0 + w / 2.0, uy + size * 0.035), fill=INK + (255,))
    return img


def dot_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, 63, 63), fill=DOT + (255,))
    return img


def ball_texture(base, stripe=None, decals=()):
    """Equirectangular texture: column = longitude, row = latitude (north pole at the top)."""
    ss = 2
    w, h = TEX_W * ss, TEX_H * ss
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        lat = math.pi / 2 - (y + 0.5) / h * math.pi
        for x in range(w):
            lon = (x + 0.5) / w * 2 * math.pi
            p = direction(lat, lon)
            colour = stripe if stripe is not None and abs(lat) < STRIPE_HALF else base
            for decal in decals:
                hit = decal.sample(p)
                if hit is not None:
                    colour = hit[:3]
            px[x, y] = colour
    return img.resize((TEX_W, TEX_H), Image.LANCZOS)


def light_overlay():
    """Soft shadow towards the edge and a gloss highlight, see-through elsewhere."""
    size, ss = 128, 4
    big = size * ss
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    px = img.load()
    light = (-0.45, 0.55, 0.70)
    ln = math.sqrt(dot(light, light))
    light = tuple(c / ln for c in light)
    half = (light[0], light[1], light[2] + 1.0)
    hn = math.sqrt(dot(half, half))
    half = tuple(c / hn for c in half)
    r = big / 2.0
    for y in range(big):
        for x in range(big):
            nx, ny = (x + 0.5 - r) / r, -(y + 0.5 - r) / r
            d2 = nx * nx + ny * ny
            if d2 >= 0.99 * 0.99:
                continue
            nz = math.sqrt(1.0 - d2)
            n = (nx, ny, nz)
            diffuse = max(0.0, dot(n, light))
            shadow = (1.0 - (0.38 + 0.62 * diffuse)) * 0.62
            edge = max(0.0, min(1.0, (0.99 - math.sqrt(d2)) / 0.05))   # fade out at the rim
            spec = max(0.0, dot(n, half)) ** 70
            if spec > 0.04:
                a = min(1.0, spec * 0.9) * edge
                px[x, y] = (255, 255, 255, int(255 * a))
            else:
                px[x, y] = (0, 0, 0, int(255 * shadow * edge))
    return img.resize((size, size), Image.LANCZOS)


# --- shader ---------------------------------------------------------------------------

def _argb(rgb):
    return (0xFF000000 | rgb) - (1 << 32)     # an opaque signed ARGB int, as vanilla writes tints


def _glsl_rgb(rgb):
    return "vec3(%d.0, %d.0, %d.0) / 255.0" % ((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)


def patch_item_vsh(vsh):
    """Patch Minecraft's item vertex shader for the pool balls.

    Balls and overlays skip the per-face lighting. For an overlay vertex it also works out the
    ball's centre and passes it to the fragment shader, which ray-traces the sphere. The overlay
    is a square facing the camera at the ball's centre (the server puts it there), so its centre
    is the vertex minus that corner's offset along the camera's right and up axes. The corner is
    the vertex's index within its quad, in Minecraft's order for a north face (MAX_X MAX_Y,
    MAX_X MIN_Y, MIN_X MIN_Y, MIN_X MAX_Y; an item display turns the model 180 degrees, so
    +x ends up on the viewer's left). Position is relative to the camera here."""
    main = "void main() {\n"
    light = "    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, Color);\n"
    for part in (main, light):
        assert vsh.count(part) == 1, "item.vsh changed: update the patch"
    helper = ("// Antigravity Server: pool balls (see the resource pack's README)\n"
              "bool antigravity_tint(vec4 color, vec3 tint) {\n"
              "    return all(lessThan(abs(color.rgb - tint), vec3(0.002)));\n"
              "}\n"
              "layout(location = 8) out vec3 antigravityPos;\n"
              "layout(location = 9) flat out vec3 antigravityCentre;\n"
              "layout(location = 10) flat out float antigravityBall;\n\n")
    unlit = (light +
             "    antigravityPos = Position;\n"
             "    antigravityCentre = vec3(0.0);\n"
             "    antigravityBall = 0.0;\n"
             "    if (antigravity_tint(Color, %(ball)s)) {\n"
             "        vertexColor = vec4(1.0, 1.0, 1.0, Color.a);\n"
             "    }\n"
             "    if (antigravity_tint(Color, %(overlay)s)) {\n"
             "        vertexColor = vec4(1.0, 1.0, 1.0, Color.a);\n"
             "        int corner = gl_VertexID %% 4;\n"
             "        vec2 side = vec2(corner < 2 ? -1.0 : 1.0, (corner == 0 || corner == 3) ? 1.0 : -1.0);\n"
             "        vec3 right = vec3(ModelViewMat[0][0], ModelViewMat[1][0], ModelViewMat[2][0]);\n"
             "        vec3 up = vec3(ModelViewMat[0][1], ModelViewMat[1][1], ModelViewMat[2][1]);\n"
             "        antigravityCentre = Position - %(half)s * (side.x * right + side.y * up);\n"
             "        antigravityBall = 1.0;\n"
             "    }\n") % {"ball": _glsl_rgb(BALL_TINT), "overlay": _glsl_rgb(OVERLAY_TINT),
                         "half": "%.5f" % (R * LIGHT_SIZE / 16.0 * DISPLAY_SCALE)}
    return vsh.replace(main, helper + main).replace(light, unlit)


def patch_item_fsh(fsh):
    """Ray-trace the ball under each overlay pixel: lighting from a fixed light above the
    table (diffuse, a darker rim, and a gloss highlight that follows the viewer), written as
    a see-through layer over the unlit ball, with the depth of the sphere's surface so other
    balls and the cue hide it properly."""
    head = "#include <minecraft:oit.glsl>\n"
    main = "void main() {\n    vec4 color = texture(Sampler0, texCoord0);\n"
    tint = "    color *= vertexColor * ColorModulator;\n"
    tail = "    #ifdef OIT_ALPHA_ONLY\n    executeAlphaOnlyPhase(gl_FragCoord.z, color.a);\n"
    for part in (head, main, tint, tail):
        assert fsh.count(part) == 1, "item.fsh changed: update the patch"
    decl = (head +
            "#include <minecraft:projection.glsl>\n\n"
            "// Antigravity Server: pool balls (see the resource pack's README)\n"
            "layout(location = 8) in vec3 antigravityPos;\n"
            "layout(location = 9) flat in vec3 antigravityCentre;\n"
            "layout(location = 10) flat in float antigravityBall;\n")
    shade = ("void main() {\n"
             "    vec4 color;\n"
             "    float depth = gl_FragCoord.z;\n"
             "    if (antigravityBall > 0.5) {\n"
             "        vec3 dir = normalize(antigravityPos);           // the eye is at the origin\n"
             "        vec3 oc = -antigravityCentre;\n"
             "        float b = dot(oc, dir);\n"
             "        float h = b * b - (dot(oc, oc) - %(r2)s);\n"
             "        if (h < 0.0) {\n"
             "            discard;\n"
             "        }\n"
             "        vec3 hit = dir * (-b - sqrt(h));\n"
             "        vec3 n = normalize(hit - antigravityCentre);\n"
             "        vec3 light = normalize(vec3(0.35, 1.0, 0.25));\n"
             "        vec3 view = -dir;\n"
             "        float diffuse = max(dot(n, light), 0.0);\n"
             "        float rim = pow(1.0 - max(dot(n, view), 0.0), 3.0);\n"
             "        float keep = (0.42 + 0.58 * diffuse) * (1.0 - 0.3 * rim);   // how much of the ball shows\n"
             "        float gloss = pow(max(dot(n, normalize(light + view)), 0.0), 90.0) * 0.85;\n"
             "        float alpha = 1.0 - keep * (1.0 - gloss);\n"
             "        color = vec4(vec3(alpha > 0.0 ? gloss / alpha : 0.0), alpha) * ColorModulator;\n"
             "        vec4 atHit = ProjMat * ModelViewMat * vec4(hit - dir * 0.01, 1.0);  // just in front\n"
             "        vec4 atQuad = ProjMat * ModelViewMat * vec4(antigravityPos, 1.0);\n"
             "        depth = gl_FragCoord.z + (atHit.z / atHit.w - atQuad.z / atQuad.w);\n"
             "    } else {\n"
             "    color = texture(Sampler0, texCoord0);\n") % {"r2": "%.6f" % (SPHERE_RADIUS ** 2)}
    fsh = fsh.replace(head, decl).replace(main, shade)
    fsh = fsh.replace(tint, tint + "    }\n    gl_FragDepth = depth;\n")
    return fsh.replace(tail, "    #ifdef OIT_ALPHA_ONLY\n    executeAlphaOnlyPhase(depth, color.a);\n")


# --- models ---------------------------------------------------------------------------

def sphere_elements(tex):
    els = []
    dlat, dlon = math.pi / LAT, 2 * math.pi / LON
    for j in range(LAT):
        lat0 = -math.pi / 2 + j * dlat
        lat1 = lat0 + dlat
        lat = (lat0 + lat1) / 2
        near = min(abs(lat0), abs(lat1))            # the edge closer to the equator is the wider one
        if lat0 < 0 < lat1:
            near = 0.0
        width = 2 * R * math.cos(near) * math.sin(dlon / 2) * 1.04
        height = 2 * R * math.sin(dlat / 2) * 1.04
        depth = R * math.cos(dlat / 2) * math.cos(dlon / 2 * math.cos(lat))
        v0 = (math.pi / 2 - lat1) / math.pi * 16
        v1 = (math.pi / 2 - lat0) / math.pi * 16
        for i in range(LON):
            lon0 = i * dlon
            lon = lon0 + dlon / 2
            e, u, n = frame(lat, lon)
            m = [[e[k], u[k], n[k]] for k in range(3)]   # columns: local x, y, z
            ax, ay, az = euler_zyx(m)
            els.append({
                "from": [round(C - width / 2, 4), round(C - height / 2, 4), round(C + depth, 4)],
                "to": [round(C + width / 2, 4), round(C + height / 2, 4), round(C + depth, 4)],
                "rotation": {"origin": [C, C, C], "x": round(ax, 4), "y": round(ay, 4), "z": round(az, 4)},
                "shade": False,
                "faces": {"south": {"uv": [round(lon0 / (2 * math.pi) * 16, 4), round(v0, 4),
                                           round((lon0 + dlon) / (2 * math.pi) * 16, 4), round(v1, 4)],
                                    "texture": tex, "tintindex": 0}},
            })
    return els


def build(src, out):
    root = os.path.join(out, "assets", NS)
    models = os.path.join(root, "models", "item")
    tex_dir = os.path.join(root, "textures", "item", "hg")
    items = os.path.join(root, "items")
    for p in (os.path.join(models, "hg"), tex_dir, items):
        os.makedirs(p, exist_ok=True)
    try:
        font = ImageFont.truetype("arialbd.ttf", 128)
    except OSError:
        font = ImageFont.load_default()
    with open(os.path.join(src, "assets", NS, "models", "item", "ball_08.json")) as fh:
        display = json.load(fh).get("display", {})
    elements = sphere_elements("#0")

    def write(name, image):
        image.save(os.path.join(tex_dir, "sphere_" + name + ".png"))
        t = "%s:item/hg/sphere_%s" % (NS, name)
        model = {"credit": "Round pool ball for Pool and Billiards (Squid Workshop), generated by build_sphere.py",
                 "textures": {"0": t, "particle": t}, "elements": elements, "display": display}
        with open(os.path.join(models, name + ".json"), "w") as fh:     # replaces the pack's own ball model
            json.dump(model, fh, separators=(",", ":"))

    number_lons = (math.pi / 2, 3 * math.pi / 2)            # two number circles on opposite sides
    for n in range(1, 16):
        img = number_image(n, font)
        decals = [Decal(0.0, lon, NUMBER_RADIUS, img) for lon in number_lons]
        if n >= 9:
            write("ball_%02d" % n, ball_texture(WHITE, POOL[n], decals))
        else:
            write("ball_%02d" % n, ball_texture(POOL[n], None, decals))
    dots = [Decal(lat, lon, DOT_RADIUS, dot_image()) for lat, lon in
            ((0, 0), (0, math.pi / 2), (0, math.pi), (0, 3 * math.pi / 2), (math.pi / 2, 0), (-math.pi / 2, 0))]
    write("cueball", ball_texture(WHITE, None, dots))
    write("cueball_clean", ball_texture(WHITE))
    for name, rgb in SNOOKER.items():
        write(name, ball_texture(rgb))

    light_overlay().save(os.path.join(tex_dir, "ball_light.png"))
    t = "%s:item/hg/ball_light" % NS
    e = 0.001
    q = R * LIGHT_SIZE
    with open(os.path.join(models, "hg", "ball_light.json"), "w") as fh:
        # north: item displays turn their item 180 degrees, so this is the side facing the viewer
        json.dump({"textures": {"0": t, "particle": t},
                   "elements": [{"from": [C - q, C - q, C - e], "to": [C + q, C + q, C + e], "shade": False,
                                 "faces": {"north": {"uv": [0, 0, 16, 16], "texture": "#0", "tintindex": 0}}}]},
                  fh, indent=1)
    with open(os.path.join(items, "hg_ball_light.json"), "w") as fh:
        json.dump({"model": {"type": "minecraft:model", "model": "%s:item/hg/ball_light" % NS,
                             "tints": [{"type": "minecraft:constant", "value": _argb(OVERLAY_TINT)}]}}, fh, indent=1)
    # Mark the balls with a tint colour no vanilla item uses, so the item shader can skip its
    # six-direction lighting for them (the overlay does their shading instead).
    for name in ["ball_%02d" % n for n in range(1, 16)] + ["cueball", "cueball_clean"] + list(SNOOKER):
        with open(os.path.join(items, "render_%s.json" % name), "w") as fh:
            json.dump({"model": {"type": "minecraft:model", "model": "%s:item/%s" % (NS, name),
                                 "tints": [{"type": "minecraft:constant", "value": _argb(BALL_TINT)}]}}, fh, indent=1)
    shaders = os.path.join(out, "assets", "minecraft", "shaders", "core")
    os.makedirs(shaders, exist_ok=True)
    with open(ITEM_VSH, encoding="utf-8") as fh:
        vsh = fh.read()
    with open(os.path.join(shaders, "item.vsh"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(patch_item_vsh(vsh))
    with open(ITEM_FSH, encoding="utf-8") as fh:
        fsh = fh.read()
    with open(os.path.join(shaders, "item.fsh"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(patch_item_fsh(fsh))
    print("wrote %d-quad sphere balls to %s" % (len(elements), os.path.abspath(out)))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
