"""Build the server's resource pack: the Pool and Billiards pack (Squid Workshop), the 3D pool
balls and the curling set, in one zip.

Usage:  python tools/build_pack.py <version number>

Writes tools/pack_build/Antigravity-Resourcepack-v<N>.zip and prints its SHA-1. Before zipping
it compiles the patched item shaders the way the 26.3 client does (tools/pool_balls/
McShaderCheck.java): a shader that fails there makes the client drop the whole pack.
Publishing (GitHub release, server.properties, hg/pool.py PACK_URL/PACK_SHA1) is a separate step.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ORIGINAL = os.path.join(TOOLS, "dl-pool", "rp")                 # the Pool and Billiards pack, unpacked
OUT = os.path.join(TOOLS, "pack_build")
APPDATA_MC = os.path.join(os.environ.get("APPDATA", ""), ".minecraft")
JDK = os.path.join(TOOLS, "jdk-25", "bin")


def run(args, cwd=None):
    print("+", os.path.basename(args[0]), os.path.basename(args[-1]))
    subprocess.check_call(args, cwd=cwd)


def overlay(src, dst):
    for root, _, files in os.walk(src):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), src)
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(os.path.join(root, f), target)


def client_classpath():
    d = json.load(open(os.path.join(APPDATA_MC, "versions", "26.3", "26.3.json")))
    paths = []
    for lib in d["libraries"]:
        art = lib.get("downloads", {}).get("artifact")
        if not art:
            continue
        p = os.path.join(APPDATA_MC, "libraries", art["path"])
        if os.path.exists(p) and "arm64" not in p and not p.endswith("x86.jar"):
            paths.append(p)
    return ";".join(paths)


def check_shaders(pack_dir):
    """Compile the pack's patched item shaders with the client's compiler settings."""
    core = os.path.join(pack_dir, "assets", "minecraft", "shaders", "core")
    includes = os.path.join(OUT, "mc_includes")
    if not os.path.isdir(includes):
        with zipfile.ZipFile(os.path.join(APPDATA_MC, "versions", "26.3", "26.3.jar")) as jar:
            for name in jar.namelist():
                if name.startswith("assets/minecraft/shaders/include/") and name.endswith(".glsl"):
                    os.makedirs(includes, exist_ok=True)
                    with open(os.path.join(includes, os.path.basename(name)), "wb") as fh:
                        fh.write(jar.read(name))
    classes = os.path.join(OUT, "mcshadercheck")
    cp = client_classpath()
    run([os.path.join(JDK, "javac.exe"), "-cp", cp, "-d", classes,
         os.path.join(TOOLS, "pool_balls", "McShaderCheck.java")])
    run([os.path.join(JDK, "java.exe"), "-cp", cp + ";" + classes, "McShaderCheck", includes,
         os.path.join(core, "item.vsh"), os.path.join(core, "item.fsh")])


def main(version):
    if os.path.isdir(OUT):
        for name in ("sphere", "curling", "full"):
            shutil.rmtree(os.path.join(OUT, name), ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    sphere, curling, full = (os.path.join(OUT, n) for n in ("sphere", "curling", "full"))
    run([sys.executable, os.path.join(TOOLS, "pool_balls", "build_sphere.py"), ORIGINAL, sphere],
        cwd=os.path.join(TOOLS, "pool_balls"))
    curling_builder = os.path.join(TOOLS, "curling", "assets", "build_assets.py")
    if os.path.exists(curling_builder):
        run([sys.executable, curling_builder, curling], cwd=os.path.dirname(curling_builder))
    shutil.copytree(ORIGINAL, full)
    overlay(sphere, full)
    if os.path.isdir(curling):
        overlay(curling, full)
    meta_path = os.path.join(full, "pack.mcmeta")
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta["pack"]["description"] = ("Antigravity Server v%s: Pool and Billiards (YMS2001 - Squid Workshop) "
                                   "with 3D balls, and curling" % version)
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    check_shaders(full)
    zp = os.path.join(OUT, "Antigravity-Resourcepack-v%s.zip" % version)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(full):
            for f in sorted(files):
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, full).replace(os.sep, "/"))
    sha = hashlib.sha1(open(zp, "rb").read()).hexdigest()
    print("pack:", zp, os.path.getsize(zp), "bytes")
    print("sha1:", sha)


if __name__ == "__main__":
    main(sys.argv[1])
