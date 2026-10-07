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
    p.add_argument("--list-collections", action="store_true")
    return p.parse_args(argv)


def all_children(coll):
    yield coll
    for c in coll.children:
        yield from all_children(c)


def select_visible_objects(names):
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
    for o in bpy.context.scene.objects:
        o.hide_render = o not in keep
    if not keep:
        sys.exit("No mesh objects selected.")
    return keep


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


def region_box(body_lo, body_hi, frac):
    size = body_hi - body_lo
    lo = Vector((body_lo[i] + frac[2 * i] * size[i] for i in range(3)))
    hi = Vector((body_lo[i] + frac[2 * i + 1] * size[i] for i in range(3)))
    return lo, hi


def setup_scene(style):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
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
    sc.view_settings.view_transform = "Standard"

    cam_data = bpy.data.cameras.new("ViewCam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("ViewCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


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


def main():
    args = parse_args()
    if args.list_collections:
        for c in all_children(bpy.context.scene.collection):
            print(c.name, len(c.objects))
        return

    cfg = json.load(open(args.views, encoding="utf-8"))
    names = [n.strip() for n in args.collections.split(",") if n.strip()]
    objs = select_visible_objects(names)
    body_lo, body_hi = world_bbox(objs)
    print("Body bbox:", tuple(body_lo), tuple(body_hi))

    sc, cam = setup_scene(args.style)
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
            label = spec.get("aliases", {}).get(view, view)
            fname = "%s_%s.png" % (region, label)
            sc.render.filepath = os.path.abspath(os.path.join(args.out, fname))
            bpy.ops.render.render(write_still=True)
            info.update({"region": region, "view": view, "label": label, "box": [list(lo), list(hi)]})
            manifest["images"][fname] = info
            print("rendered", fname)

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


main()
