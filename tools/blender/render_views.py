"""Render orthographic anatomical views (transparent PNG) from an anatomy model in Blender.

Usage (headless):
  blender -b Z-Anatomy.blend --python tools/blender/render_views.py -- \
      --out build/body-views --collections "Regions of human body" --size 2000

Optional: --regions head,right_hand   --list-collections   --style color|flat

Writes <out>/<region>_<view>.png and <out>/manifest.json. The manifest records, for every image,
the world-space box and axes, so acupoint positions can later be stored as normalized (x, y)
image coordinates and re-projected if the images are re-rendered.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="build/body-views")
    p.add_argument("--views", default=os.path.join(HERE, "views.json"))
    p.add_argument("--collections", default="", help="comma-separated collection names to render (default: everything visible)")
    p.add_argument("--regions", default="", help="comma-separated region names (default: all)")
    p.add_argument("--size", type=int, default=2000, help="pixels on the longest side")
    p.add_argument("--margin", type=float, default=1.06, help="padding factor around the region")
    p.add_argument("--style", choices=["flat", "color"], default="flat")
    p.add_argument("--engine", choices=["workbench", "cpu"], default="workbench",
                   help="workbench = fast, uses the GPU; cpu = Cycles on the CPU, slower but never touches the GPU")
    p.add_argument("--exclude", default="", help="comma-separated, case-insensitive substrings; objects whose name contains one are dropped (labels, helpers)")
    p.add_argument("--light", type=float, default=1.0, help="lighting multiplier for the cpu engine (lower if the render looks washed out)")
    p.add_argument("--glow", type=float, default=0.0, help="brightness of the flat skin tone used for surfaces seen from inside the mesh (cpu engine, flat style); 0 disables")
    p.add_argument("--shadows", action="store_true", help="keep object shadows (cpu engine). Off by default: the body mesh is open, and shadows turn the inside seen through gaps (groin, eye sockets) black")
    p.add_argument("--sheet", action="store_true", help="also write <out>/sheet.png, all rendered views tiled on one grey page for quick review")
    p.add_argument("--samples", type=int, default=24, help="Cycles samples (cpu engine only)")
    p.add_argument("--outline", action="store_true", help="Freestyle line art (cpu engine only; slow and memory hungry)")
    p.add_argument("--list-collections", action="store_true")
    p.add_argument("--find", default="", help="comma-separated substrings; print matching object names in the chosen collections and exit")
    return p.parse_args(argv)


def all_children(coll):
    yield coll
    for c in coll.children:
        yield from all_children(c)


def select_visible_objects(names, exclude=()):
    """Hide from render everything outside the named collections. Returns renderable mesh objects."""
    if not names:
        keep = {o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render}
    else:
        wanted = set(names)
        keep = set()
        for coll in all_children(bpy.context.scene.collection):
            if coll.name in wanted:
                keep.update(o for o in coll.all_objects if o.type == "MESH")
        missing = wanted - {c.name for c in all_children(bpy.context.scene.collection)}
        if missing:
            sys.exit("Collections not found: %s (use --list-collections)" % ", ".join(sorted(missing)))
    keep = {o for o in keep if not any(x in o.name.lower() for x in exclude)}
    for o in bpy.context.scene.objects:
        o.hide_render = o not in keep
    for o in keep:
        o.hide_viewport = False
        o.visible_camera = True
        o.is_holdout = False
    if not keep:
        sys.exit("No mesh objects selected.")
    if names:
        enable_layer_collections(bpy.context.view_layer.layer_collection, set(names))
    return keep


def enable_layer_collections(lc, wanted, inside=False):
    """Un-exclude / un-hide the wanted collections and their parents so they actually render."""
    inside = inside or lc.name in wanted
    has_wanted = inside
    for child in lc.children:
        has_wanted = enable_layer_collections(child, wanted, inside) or has_wanted
    if has_wanted:
        lc.exclude = False
        lc.hide_viewport = False
        lc.holdout = False
        lc.indirect_only = False
        lc.collection.hide_render = False
    return has_wanted


def world_bbox(objs):
    deps = bpy.context.evaluated_depsgraph_get()
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in objs:
        ev = o.evaluated_get(deps)
        for corner in ev.bound_box:
            w = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def print_extremes(objs, n=4):
    """Print the objects that stretch the bounding box, to spot stray helpers/labels."""
    deps = bpy.context.evaluated_depsgraph_get()
    rows = []
    for o in objs:
        ev = o.evaluated_get(deps)
        pts = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        rows.append((o.name, min(p.x for p in pts), max(p.x for p in pts), min(p.z for p in pts), max(p.z for p in pts)))
    for label, idx, rev in (("lowest x (subject's right)", 1, False), ("highest x (subject's left)", 2, True),
                            ("lowest z", 3, False), ("highest z", 4, True)):
        print("Extremes -", label)
        for r in sorted(rows, key=lambda r: r[idx], reverse=rev)[:n]:
            print("   %-40s x[%.3f, %.3f] z[%.3f, %.3f]" % r)


def region_box(body_lo, body_hi, frac):
    size = body_hi - body_lo
    lo = Vector((body_lo[i] + frac[2 * i] * size[i] for i in range(3)))
    hi = Vector((body_lo[i] + frac[2 * i + 1] * size[i] for i in range(3)))
    return lo, hi


def setup_workbench(sc, style):
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.render_aa = "8"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.show_object_outline = True
    sh.object_outline_color = (0.05, 0.05, 0.05)
    if style == "flat":
        sh.color_type = "SINGLE"
        sh.single_color = (0.86, 0.80, 0.74)
    else:
        sh.color_type = "OBJECT"


def setup_cycles_cpu(sc, style, samples, outline, light, glow):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False

    world = bpy.data.worlds.new("ViewWorld")
    sc.world = world
    try:
        world.use_nodes = True  # deprecated (always on) in newer Blender
    except Exception:
        pass
    bg = world.node_tree.nodes.get("Background") if world.node_tree else None
    if bg:
        bg.inputs["Color"].default_value = (1, 1, 1, 1)
        bg.inputs["Strength"].default_value = 0.5 * light

    if style == "flat":
        mat = bpy.data.materials.new("FlatSkin")
        try:
            mat.use_nodes = True
        except Exception:
            pass
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.86, 0.80, 0.74, 1)
            bsdf.inputs["Roughness"].default_value = 0.8
            if glow > 0:
                # Surfaces seen from inside (through gaps in the open body mesh) get a flat skin tone
                # instead of rendering black. Front faces keep normal shading.
                nt = mat.node_tree
                out = nt.nodes.get("Material Output")
                geo = nt.nodes.new("ShaderNodeNewGeometry")
                emit = nt.nodes.new("ShaderNodeEmission")
                emit.inputs["Color"].default_value = (0.86, 0.80, 0.74, 1)
                emit.inputs["Strength"].default_value = glow
                mix = nt.nodes.new("ShaderNodeMixShader")
                nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
                nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
                nt.links.new(emit.outputs["Emission"], mix.inputs[2])
                if out:
                    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
        bpy.context.view_layer.material_override = mat

    if outline:
        sc.render.use_freestyle = True
        bpy.context.view_layer.use_freestyle = True
        bpy.context.view_layer.freestyle_settings.linesets[0].linestyle.thickness = 1.5


def setup_scene(style, engine, samples, outline, light=1.0, glow=0.0):
    sc = bpy.context.scene
    # The Z-Anatomy scene ships with a compositor (white background + Freestyle lines) and a second
    # view layer for its "Take a picture" feature. Both would overwrite our output.
    sc.render.use_compositing = False
    sc.render.use_sequencer = False
    active = bpy.context.view_layer
    for vl in sc.view_layers:
        vl.use = vl == active
    print("View layers:", [(vl.name, vl.use) for vl in sc.view_layers], "-> rendering", active.name)
    sc.render.film_transparent = True
    sc.render.use_freestyle = bool(outline and engine == "cpu")  # the Z-Anatomy scene ships with it enabled
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    if engine == "cpu":
        setup_cycles_cpu(sc, style, samples, outline, light, glow)
    else:
        setup_workbench(sc, style)

    cam_data = bpy.data.cameras.new("ViewCam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("ViewCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam

    sun = None
    if engine == "cpu":
        sun = bpy.data.objects.new("ViewSun", bpy.data.lights.new("ViewSun", "SUN"))
        sun.data.energy = 1.5 * light
        sc.collection.objects.link(sun)
    return sc, cam, sun


def aim_camera(cam, box_lo, box_hi, d, up, margin, size):
    f = Vector(d).normalized()
    u0 = Vector(up).normalized()
    r = f.cross(u0).normalized()
    u = r.cross(f).normalized()

    corners = [Vector((x, y, z)) for x in (box_lo.x, box_hi.x) for y in (box_lo.y, box_hi.y) for z in (box_lo.z, box_hi.z)]
    center = (box_lo + box_hi) / 2
    rel = [c - center for c in corners]
    pr = [v.dot(r) for v in rel]
    pu = [v.dot(u) for v in rel]
    pf = [v.dot(f) for v in rel]
    w, h = max(pr) - min(pr), max(pu) - min(pu)
    depth = max(pf) - min(pf)

    # Camera sits on the near face of the box, so geometry before it is clipped away.
    eps = 1e-4
    cam.location = center + f * (min(pf) - eps)
    cam.matrix_world = Matrix.Translation(cam.location) @ Matrix(
        ((r.x, u.x, -f.x, 0), (r.y, u.y, -f.y, 0), (r.z, u.z, -f.z, 0), (0, 0, 0, 1))
    )
    cam.data.clip_start = eps
    cam.data.clip_end = depth + 2 * eps + 0.001

    if w >= h:
        res_x, res_y = size, max(1, round(size * h / w))
        cam.data.ortho_scale = w * margin
    else:
        res_x, res_y = max(1, round(size * w / h)), size
        cam.data.ortho_scale = h * margin
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = res_x, res_y, 100
    return {
        "width_px": res_x,
        "height_px": res_y,
        "ortho_scale": cam.data.ortho_scale,
        "right_axis": list(r),
        "up_axis": list(u),
        "forward_axis": list(f),
        "center": list(center),
    }


def image_stats(path):
    """Return (% opaque pixels, mean RGB of opaque pixels) so a blank render is obvious."""
    import numpy as np
    img = bpy.data.images.load(path)
    arr = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(arr)
    arr = arr.reshape(-1, 4)
    opaque = arr[arr[:, 3] > 0.5]
    bpy.data.images.remove(img)
    if not len(opaque):
        return 0.0, (0, 0, 0)
    return 100.0 * len(opaque) / len(arr), tuple(float(v) for v in opaque[:, :3].mean(axis=0))


def write_sheet(out_dir, names, cell, cols=7):
    """Tile the rendered PNGs on a grey page (in the order of `names`) and save <out_dir>/sheet.png."""
    import numpy as np
    rows = -(-len(names) // cols)
    sheet = np.full((rows * cell, cols * cell, 4), 0.55, dtype=np.float32)
    sheet[..., 3] = 1.0
    for i, name in enumerate(names):
        img = bpy.data.images.load(os.path.join(out_dir, name))
        w, h = img.size
        arr = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(arr)
        arr = arr.reshape(h, w, 4)
        bpy.data.images.remove(img)
        h, w = min(h, cell), min(w, cell)
        arr = arr[:h, :w]
        y0 = (rows - 1 - i // cols) * cell + (cell - h) // 2
        x0 = (i % cols) * cell + (cell - w) // 2
        a = arr[..., 3:4]
        sheet[y0:y0 + h, x0:x0 + w, :3] = arr[..., :3] * a + sheet[y0:y0 + h, x0:x0 + w, :3] * (1 - a)
    out = bpy.data.images.new("sheet", cols * cell, rows * cell, alpha=False)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = os.path.join(out_dir, "sheet.png")
    out.file_format = "PNG"
    out.save()
    print("Sheet order (left to right, top to bottom, %d per row):" % cols)
    for i, n in enumerate(names):
        print("  %2d  %s" % (i + 1, n))


def main():
    args = parse_args()
    if args.list_collections:
        for c in all_children(bpy.context.scene.collection):
            print(c.name, len(c.objects))
        return

    cfg = json.load(open(args.views, encoding="utf-8"))
    names = [n.strip() for n in args.collections.split(",") if n.strip()]
    exclude = [x.strip().lower() for x in args.exclude.split(",") if x.strip()]
    objs = select_visible_objects(names, exclude)
    if args.engine == "cpu" and not args.shadows:
        for o in objs:
            o.visible_shadow = False
    if args.find:
        needles = [x.strip().lower() for x in args.find.split(",") if x.strip()]
        for o in sorted(objs, key=lambda o: o.name):
            if any(n in o.name.lower() for n in needles):
                print("FOUND:", o.name)
        return
    body_lo, body_hi = world_bbox(objs)
    print("Body bbox:", tuple(body_lo), tuple(body_hi))
    print_extremes(objs)

    sc, cam, sun = setup_scene(args.style, args.engine, args.samples, args.outline, args.light, args.glow)
    os.makedirs(args.out, exist_ok=True)
    wanted = {r.strip() for r in args.regions.split(",") if r.strip()}
    manifest = {"body_bbox": [list(body_lo), list(body_hi)], "images": {}}

    for region, spec in cfg["regions"].items():
        if wanted and region not in wanted:
            continue
        lo, hi = region_box(body_lo, body_hi, spec["box"])
        for view in spec["views"]:
            dv = cfg["directions"][view]
            info = aim_camera(cam, lo, hi, dv["dir"], dv["up"], args.margin, args.size)
            if sun is not None:  # key light: from the camera, slightly above and to the side
                sun.matrix_world = cam.matrix_world @ Matrix.Rotation(math.radians(25), 4, "X") @ Matrix.Rotation(math.radians(20), 4, "Y")
            label = spec.get("aliases", {}).get(view, view)
            fname = "%s_%s.png" % (region, label)
            sc.render.filepath = os.path.abspath(os.path.join(args.out, fname))
            bpy.ops.render.render(write_still=True)
            info.update({"region": region, "view": view, "label": label, "box": [list(lo), list(hi)]})
            manifest["images"][fname] = info
            pct, rgb = image_stats(sc.render.filepath)
            print("rendered %s  stats: %.1f%% opaque, mean RGB (%.2f, %.2f, %.2f)" % ((fname, pct) + rgb))

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    if args.sheet:
        write_sheet(args.out, list(manifest["images"]), args.size)


main()
