# -*- coding: utf-8 -*-
"""Build the curling resource pack assets (namespace "curling").

Usage:  python build_assets.py <output folder>

Writes <output>/assets/curling/{items,models/item,textures/item}. Sizes come from the game's
config.py (curling/config.py: STONE_RADIUS, STONE_HEIGHT, RING_RADII). Needs Pillow only.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_decals          # noqa: E402
import build_gear            # noqa: E402
import build_stone           # noqa: E402
import mc_model as mm        # noqa: E402

CONFIG = os.path.normpath(os.path.join(
    HERE, "..", "..", "..", "MinecraftServer", "plugins", "PySpigot", "projects", "curling", "curling", "config.py"))
DEFAULTS = {"STONE_RADIUS": 0.3, "STONE_HEIGHT": 0.24, "RING_RADII": (3.0, 2.0, 1.0, 0.35)}

ITEMS = ("stone_red", "stone_yellow", "broom_red", "broom_yellow", "delivery_stick", "house", "aim_marker")
UNLIT = ("stone_red", "stone_yellow", "house", "aim_marker")


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.isfile(CONFIG):
        spec = importlib.util.spec_from_file_location("curling_config", CONFIG)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for key in DEFAULTS:
            if hasattr(mod, key):
                cfg[key] = getattr(mod, key)
    else:
        print("config.py not found, using default sizes: %s" % CONFIG)
    return cfg


def build(out):
    cfg = load_config()
    writer = mm.PackWriter(out)
    counts = {}
    profile = build_stone.Profile(cfg["STONE_RADIUS"] * 16.0, cfg["STONE_HEIGHT"] * 16.0)
    writer.texture("stone_granite", build_stone.granite_texture(profile))
    for team in ("red", "yellow"):
        textures, elements, palette = build_stone.stone_model(team, profile)
        writer.texture("stone_handle_%s" % team, palette.image())
        writer.model("stone_%s" % team, textures, elements)
        writer.item("stone_%s" % team, unlit=True)
        counts["stone_%s" % team] = len(elements)
    counts.update(build_gear.build(writer))
    counts.update(build_decals.build(writer, cfg["RING_RADII"]))
    problems = validate(out)
    for name in ITEMS:
        print("%-16s %4d elements" % (name, counts[name]))
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("wrote %d files to %s (all JSON parses, all textures exist)" % (len(writer.written), os.path.abspath(out)))


def validate(out):
    """Every JSON parses, every item points at a model, every model texture exists."""
    root = os.path.join(out, "assets", mm.NS)
    problems = []

    def load(path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except (IOError, ValueError) as exc:
            problems.append("%s: %s" % (path, exc))
            return None

    for name in ITEMS:
        item = load(os.path.join(root, "items", name + ".json"))
        if item is None:
            continue
        model_id = item["model"]["model"]
        tinted = bool(item["model"].get("tints"))
        if tinted != (name in UNLIT):
            problems.append("%s: tint mismatch" % name)
        model = load(os.path.join(root, "models", "item", model_id.split("/")[-1] + ".json"))
        if model is None:
            continue
        for key, ref in model["textures"].items():
            ns, _, path = ref.partition(":")
            if not os.path.isfile(os.path.join(out, "assets", ns, "textures", path + ".png")):
                problems.append("%s: texture %s missing" % (name, ref))
        for el in model["elements"]:
            for face in el["faces"].values():
                key = face["texture"].lstrip("#")
                if key not in model["textures"]:
                    problems.append("%s: face uses unknown texture %s" % (name, face["texture"]))
                if tinted and "tintindex" not in face:
                    problems.append("%s: unlit model has a face without tintindex" % name)
                if el.get("shade", True) and tinted:
                    problems.append("%s: unlit model has a face with shade true" % name)
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    build(sys.argv[1])
