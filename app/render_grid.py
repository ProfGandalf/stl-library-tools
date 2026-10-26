"""
==========================================================================
 RENDER GRID - preview a collection of 3D models on one contact sheet
==========================================================================
 Imports every model in a folder, lays them out in a tidy grid, gives
 them a uniform matte (clay) material, sets up soft lighting and a
 camera, then renders one large high-resolution image. Handy for
 showing a large number of miniature parts at a glance.

 APP VERSION (app/stl_tools.py). The app runs this file as:
   blender --background --python render_grid.py -- --folder X [--only name]...
   and reads console lines starting with "@@" (progress). It can also be
   run by hand exactly like version 1 - without arguments it behaves the same.

 HOW TO USE (by hand, from Blender):
   1. Open Blender (4.x or newer). No need to clear the default scene -
      the script does that itself.
   2. "Scripting" tab -> New -> paste this file (or Open and pick it).
   3. Set FOLDER below to the path of your models folder.
   4. Press "Run Script" (Alt+P). The finished image is saved to OUTPUT.

 Supported: STL, OBJ, PLY, FBX, GLB/GLTF.
 NOTE ON 3MF: Blender does not import 3MF natively. The easiest fix is to
 export those files to STL from your slicer (Bambu/Prusa/Chitubox). The
 script skips 3MF files and lists them in the console.
==========================================================================
"""

import bpy
import os
import sys
import math
from mathutils import Vector, Matrix

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

# ============================ SETTINGS ==================================

# Leave FOLDER = "" -> the script uses the folder it lives in.
# (so it is enough to drop the script + .bat into the models folder)
FOLDER        = ""
OUTPUT        = ""          # empty -> ___png.png in the same folder

BATCH         = True        # True: BATCH MODE. Instead of reading models
                            # directly from FOLDER, it goes into every
                            # SUBFOLDER and makes a separate render named
                            # after the folder:
                            #   Models\xyz\*.stl    ->  Models\xyz.png
                            #   Models\abc\*.stl    ->  Models\abc.png
                            # Folders without 3D files are skipped.

RECURSIVE     = True        # True: models are ALSO collected from subfolders.
                            # Example - a folder with parts in subdirectories:
                            #   Dreadnought\Arms\*.stl
                            #   Dreadnought\Body\*.stl
                            #   Dreadnought\Head\*.stl
                            # -> everything lands on one sheet Dreadnought.png
                            # False: only files directly in the folder.


def _script_dir():
    """Folder this script lives in (also works with blender --background)."""
    p = None
    try:
        p = os.path.abspath(__file__)
    except NameError:
        pass
    if not p or not os.path.isfile(p):
        # run from Blender's text editor
        txt = bpy.context.space_data.text if hasattr(bpy.context, 'space_data') else None
        if txt and txt.filepath:
            p = bpy.path.abspath(txt.filepath)
    if not p:
        # last resort: the --python argument on the command line
        for i, a in enumerate(sys.argv):
            if a == '--python' and i + 1 < len(sys.argv):
                p = os.path.abspath(sys.argv[i + 1])
                break
    return os.path.dirname(p) if p else os.getcwd()


ONLY = None    # list of subfolder names to process (None = all)


def _parse_args():
    """Arguments after '--' on Blender's command line (passed by the app):
         --folder PATH      parent folder with model subfolders
         --only NAME        process only this subfolder (can be repeated)
         --res PX           resolution (square)
         --samples N        render quality
         --one-side         only sheet A (without the flipped B)
    """
    global FOLDER, ONLY, RES_X, RES_Y, SAMPLES, RENDER_BOTH_SIDES
    if '--' not in sys.argv:
        return
    args = sys.argv[sys.argv.index('--') + 1:]
    i = 0
    while i < len(args):
        a = args[i]
        val = args[i + 1] if i + 1 < len(args) else None
        if a == '--folder' and val is not None:
            FOLDER = val
            i += 1
        elif a == '--only' and val is not None:
            ONLY = (ONLY or []) + [val]
            i += 1
        elif a == '--res' and val is not None:
            RES_X = RES_Y = int(val)
            i += 1
        elif a == '--samples' and val is not None:
            SAMPLES = int(val)
            i += 1
        elif a == '--one-side':
            RENDER_BOTH_SIDES = False
        i += 1


def progress(*parts):
    """Progress line for the app - starts with '@@' and is flushed at once,
    because with redirected output Python buffers whole blocks."""
    print("@@ " + " ".join(str(p) for p in parts), flush=True)


if not FOLDER:
    FOLDER = _script_dir()
if not OUTPUT:
    OUTPUT = os.path.join(FOLDER, "___png.png")

RES_X         = 4000        # horizontal resolution (px)
RES_Y         = 4000        # vertical resolution (px)

RENDER_BOTH_SIDES = True    # True: every folder produces TWO files:
                            #   name_A.png - models as the script placed them
                            #   name_B.png - the same models flipped over
                            #                (you see them from below)
                            # The layout is identical on both, so it is easy to
                            # compare and pick the better side. False = one file.
SAMPLES       = 128         # render quality (more = nicer + slower)

# Aspect ratio of the model layout (width:height). 1.0 = square.
# None -> match the image aspect automatically (RES_X / RES_Y).
TARGET_ASPECT = 1.0

NORMALIZE     = False       # False: keep the real proportions/scale of models
                            #        (fine when files use the same units)
                            # True: rescale each to the same height (below)
TARGET_HEIGHT = 2.0         # target model height (used only when True)
SPACING       = 0.15        # gap between parts (multiplier, 0.15 = 15%)

ALLOW_ROTATE  = True        # when packing, rotate a part by 90 deg so its
                            # longer side is horizontal -> lower shelves, tighter.
                            # False = keep the original in-plane orientation.

AO_STRENGTH   = 0.8         # ambient occlusion strength (0 = off, 1 = strong)
                            # darkens crevices and grounds parts on the floor
                            # less = tighter, less empty floor between models

ONE_PER_FILE  = True        # True: one file = one cell (parts joined)
                            # False: every separate object gets its own cell

VIEW_MODE     = "top"       # "top" = top-down view (models flat, tight grid)
                            # "iso" = corner view (models standing, isometric)

AUTO_UPRIGHT  = True        # automatic model orientation:
                            #  - in "iso" mode: stands them up (longest axis up)
                            #  - in "top" mode: lays them flat (shortest axis up,
                            #    i.e. the largest silhouette seen from above)

AUTO_FLIP     = True        # True: automatically pick the side shown facing up
                            # (works in "top" mode). Override exceptions in ROTATIONS.

FLIP_METHOD   = "density"   # "density" - judges by mesh density (fast,
                            #             gave better results on your parts)
                            # "depth"   - depth-map test: detail + convexity
                            #             (slower, theoretically more accurate)

# Manual orientation fix for specific files. Key = file name,
# value = rotation (X, Y, Z) in degrees. Overrides AUTO_UPRIGHT for that file.
# Example:
#   ROTATIONS = {
#       "captain.stl":  (90, 0, 0),
#       "tank.obj":     (0, 0, 180),
#   }
ROTATIONS = {
}

SHOW_LABELS   = False       # True: label every model with its file name (to find
                            # what to rotate in ROTATIONS). Turn off for the final render.

TRANSPARENT_BG = False      # True: transparent background (PNG with alpha), no floor,
                            # but soft shadows under the models are kept

USE_GPU       = True        # try to render on the graphics card

# Camera angles - used ONLY in "iso" mode
CAM_AZIMUTH   = 45          # rotation around the vertical (degrees)
CAM_ELEVATION = 32          # camera height above the horizon (degrees)

# ========================================================================


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras):
        for b in list(block):
            block.remove(b)


def import_file(path):
    """Imports a file and returns the list of new MESH objects (or None)."""
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    try:
        if ext == '.stl':
            try:    bpy.ops.wm.stl_import(filepath=path)
            except AttributeError: bpy.ops.import_mesh.stl(filepath=path)
        elif ext == '.obj':
            try:    bpy.ops.wm.obj_import(filepath=path)
            except AttributeError: bpy.ops.import_scene.obj(filepath=path)
        elif ext == '.ply':
            try:    bpy.ops.wm.ply_import(filepath=path)
            except AttributeError: bpy.ops.import_mesh.ply(filepath=path)
        elif ext == '.fbx':
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext in ('.glb', '.gltf'):
            bpy.ops.import_scene.gltf(filepath=path)
        else:
            return None
    except Exception as e:
        print(f"  ERROR importing {os.path.basename(path)}: {e}")
        return []
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    return new


def join_objects(objs):
    """Joins a list of objects into one and returns it."""
    if not objs:
        return None
    if len(objs) == 1:
        return objs[0]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    return objs[0]


def world_bbox(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    return (Vector((min(xs), min(ys), min(zs))),
            Vector((max(xs), max(ys), max(zs))))


def robust_bounds(obj, lo=1.0, hi=99.0):
    """Returns world (min, max) computed from vertex percentiles -
    ignores stray vertices. Falls back to world_bbox without numpy."""
    me = getattr(obj, "data", None)
    if not HAS_NUMPY or me is None or len(me.vertices) == 0:
        return world_bbox(obj)
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    m = np.array(obj.matrix_world, dtype=np.float64)
    world = co @ m[:3, :3].T + m[:3, 3]
    lo_p = np.percentile(world, lo, axis=0)
    hi_p = np.percentile(world, hi, axis=0)
    return (Vector((lo_p[0], lo_p[1], lo_p[2])),
            Vector((hi_p[0], hi_p[1], hi_p[2])))


MODEL_EXTS = ('.stl', '.obj', '.ply', '.fbx', '.glb', '.gltf')


def collect_models(folder, recursive=True):
    """Returns a sorted list of (display_name, full_path).

    recursive=True -> also walks into subfolders, e.g.
        Dreadnought/Arms/a.stl
        Dreadnought/Body/b.stl
      everything lands on ONE sheet "Dreadnought".
    The display name includes the subfolder (Arms/a.stl), so it is clear
    where a part comes from and identical file names do not get mixed up.
    """
    out = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            for f in sorted(files):
                if f.lower().endswith(MODEL_EXTS + ('.3mf',)):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, folder).replace('\\', '/')
                    out.append((rel, full))
    else:
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith(MODEL_EXTS + ('.3mf',)):
                out.append((f, os.path.join(folder, f)))
    return sorted(out, key=lambda t: t[0].lower())


def rotate_world(obj, axis, deg):
    """Rotates the object by the given angle around a WORLD axis.

    NOTE - this is not the same as obj.rotation_euler[i] += angle!
    Blender composes Euler angles in XYZ order (R = Rz @ Ry @ Rx), so the
    X component acts FIRST. If the model was previously laid down by a
    rotation around Y, adding 180 to the X component will NOT flip it to
    the other side - it rotates it in-plane, because the Y rotation remaps
    the X axis. Composing the world matrix (R @ matrix_world) is order-proof.
    """
    R = Matrix.Rotation(math.radians(deg), 4, axis)
    obj.matrix_world = R @ obj.matrix_world
    bpy.context.view_layer.update()


def apply_manual_rotation(obj, name):
    """Manual fix from ROTATIONS. Returns True if anything was applied."""
    rot = ROTATIONS.get(name)
    if not rot:
        return False
    for axis, ang in (('X', rot[0]), ('Y', rot[1]), ('Z', rot[2])):
        if ang:
            rotate_world(obj, axis, ang)
    return True


def orient_upright(obj):
    """Rotates the object so its longest axis is vertical (Z)."""
    mn, mx = robust_bounds(obj)
    dx, dy, dz = (mx.x - mn.x), (mx.y - mn.y), (mx.z - mn.z)
    longest = max(dx, dy, dz)
    if longest <= dz:
        return                                    # already standing
    if longest == dx:
        rotate_world(obj, 'Y', 90)   # X -> Z
    else:
        rotate_world(obj, 'X', 90)   # Y -> Z


def orient_flat(obj):
    """Lays the object flat - shortest axis vertical (largest silhouette from above)."""
    mn, mx = robust_bounds(obj)
    dx, dy, dz = (mx.x - mn.x), (mx.y - mn.y), (mx.z - mn.z)
    shortest = min(dx, dy, dz)
    if shortest >= dz:
        return                                    # already lying flat
    if shortest == dx:
        rotate_world(obj, 'Y', 90)   # X -> Z
    else:
        rotate_world(obj, 'X', 90)   # Y -> Z


def _visible_relief(obj, grid=40):
    """Scores how good this side of the part looks when seen from above.
    Same criterion as a test render, but computed from a depth map (raycast):
    faster and without rendering. Made of two measures:

    1. DETAIL = local gradient of the depth map (not the global spread!).
       A hollow back is one big smooth bowl - huge spread, but gentle change.
       A sculpted front is a thicket of small steps. What counts is how
       often the surface changes, not by how much.

    2. CONVEXITY = how high the material sits within the part's bounds.
       A shell lying cavity-up has only its rim high. Without this measure
       shells with ribs inside win on detail density alone.
    """
    me = getattr(obj, "data", None)
    if not HAS_NUMPY or me is None or len(me.vertices) == 0:
        return 0.0
    try:
        from mathutils.bvhtree import BVHTree
        me.calc_loop_triangles()
    except Exception:
        return 0.0
    ntri = len(me.loop_triangles)
    if ntri == 0:
        return 0.0

    # vertices -> world space
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(nv, 3)
    m = np.array(obj.matrix_world, dtype=np.float64)
    world = co @ m[:3, :3].T + m[:3, 3]

    tri = np.empty(ntri * 3, dtype=np.int32)
    me.loop_triangles.foreach_get('vertices', tri)
    tri = tri.reshape(ntri, 3)

    try:
        bvh = BVHTree.FromPolygons([tuple(v) for v in world],
                                   [tuple(t) for t in tri],
                                   all_triangles=True)
    except Exception:
        return 0.0

    mn = world.min(axis=0)
    mx = world.max(axis=0)
    if mx[0] - mn[0] <= 0 or mx[1] - mn[1] <= 0:
        return 0.0
    zext = float(mx[2] - mn[2])
    if zext <= 0:
        return 0.0
    z_start = float(mx[2]) + zext * 0.5
    down = Vector((0.0, 0.0, -1.0))

    # depth map: NaN = ray went into the air (outside the silhouette)
    dm = np.full((grid, grid), np.nan, dtype=np.float64)
    hits = 0
    for gx in range(grid):
        x = mn[0] + (mx[0] - mn[0]) * (gx + 0.5) / grid
        for gy in range(grid):
            y = mn[1] + (mx[1] - mn[1]) * (gy + 0.5) / grid
            hit = bvh.ray_cast(Vector((x, y, z_start)), down)
            if hit and hit[0] is not None:
                dm[gx, gy] = hit[0].z
                hits += 1
    if hits < 16:
        return 0.0

    # local gradient: mean |difference| between neighbouring samples.
    # Only pairs where both rays hit the model are counted.
    diffs = []
    for a, b in ((dm[1:, :], dm[:-1, :]), (dm[:, 1:], dm[:, :-1])):
        d = np.abs(a - b)
        d = d[~np.isnan(d)]
        if d.size:
            diffs.append(d)
    if not diffs:
        return 0.0
    grad = np.concatenate(diffs)
    # clip the top 2% - single cliffs at the silhouette edge
    # must not outweigh the overall detail density
    hi = np.percentile(grad, 98.0)
    grad = np.clip(grad, 0.0, hi)
    detail = float(grad.mean()) / zext

    # CONVEXITY: how high the material sits relative to the part's bounds.
    # A shell lying cavity-up has only its rim high and the rest of the
    # surface deep below it -> low meanh. A convex side has material
    # right under the top -> high meanh. Without this, shells with
    # ribs inside win on detail density alone.
    vals = dm[~np.isnan(dm)]
    meanh = float(((vals - float(mn[2])) / zext).mean())

    coverage = hits / float(grid * grid)
    return detail * (0.5 + 0.5 * coverage) * (0.25 + 1.2 * meanh)


def _flip_by_density(obj):
    """'density' method - judges a side by mesh density.
    Assumes the sculpted front has many small triangles and the smooth/flat
    back has few. Fast, casts no rays. Returns True if the part was flipped.
    """
    me = getattr(obj, "data", None)
    if not HAS_NUMPY or me is None or len(me.vertices) == 0:
        return False
    try:
        me.calc_loop_triangles()
    except Exception:
        return False
    ntri = len(me.loop_triangles)
    if ntri == 0:
        return False

    nor = np.empty(ntri * 3, dtype=np.float64)
    me.loop_triangles.foreach_get('normal', nor)
    nor = nor.reshape(ntri, 3)
    m = np.array(obj.matrix_world, dtype=np.float64)
    nor_w = nor @ m[:3, :3].T

    area = np.empty(ntri, dtype=np.float64)
    me.loop_triangles.foreach_get('area', area)

    up = nor_w[:, 2] > 0.2
    dn = nor_w[:, 2] < -0.2
    n_up, n_dn = int(np.count_nonzero(up)), int(np.count_nonzero(dn))
    if n_up == 0 or n_dn == 0:
        return False

    a_up, a_dn = float(area[up].sum()), float(area[dn].sum())
    if a_up <= 0 or a_dn <= 0:
        return False
    dens_up, dens_dn = n_up / a_up, n_dn / a_dn

    if dens_dn > dens_up * 1.15:       # detail clearly underneath -> flip
        rotate_world(obj, 'X', 180)
        return True
    return False


def auto_flip_detail(obj):
    """Picks the side shown facing up. Method set by FLIP_METHOD."""
    if FLIP_METHOD == "density":
        return _flip_by_density(obj)
    # "depth": tests both sides with a depth map and keeps the better one
    a = _visible_relief(obj)
    rotate_world(obj, 'X', 180)
    b = _visible_relief(obj)
    if b > a * 1.05:                 # flipped side clearly more interesting
        return True
    rotate_world(obj, 'X', -180)   # back to the original
    return False


def make_clay_material():
    mat = bpy.data.materials.new("Clay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.72, 0.70, 0.66, 1.0)   # light bone
        bsdf.inputs["Roughness"].default_value = 0.6
        for name in ("Specular IOR Level", "Specular"):
            if name in bsdf.inputs:
                bsdf.inputs[name].default_value = 0.2

    # (5) Ambient occlusion - darkens crevices and contact points,
    # which makes the sculpt easier to read and parts "sit" on the floor.
    if AO_STRENGTH > 0 and bsdf:
        nt = mat.node_tree
        ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
        ao.samples = 16
        ao.inputs['Distance'].default_value = 1.0   # set later according to scale
        ao.name = "ClayAO"
        base = nt.nodes.new('ShaderNodeRGB')
        base.outputs[0].default_value = (0.72, 0.70, 0.66, 1.0)   # must == Base Color above
        mix = nt.nodes.new('ShaderNodeMixRGB')
        mix.blend_type = 'MULTIPLY'
        mix.inputs['Fac'].default_value = min(1.0, max(0.0, AO_STRENGTH))
        nt.links.new(base.outputs[0], mix.inputs['Color1'])
        nt.links.new(ao.outputs['Color'], mix.inputs['Color2'])
        nt.links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
    return mat


def setup_lighting():
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.80, 0.83, 0.88, 1.0)   # cool ambient
        bg.inputs[1].default_value = 0.4                        # fill strength

    # SUN lights do not depend on scene scale - they light evenly
    # no matter how big the models are (crucial with NORMALIZE=False).
    def sun(name, rot_deg, energy):
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.angle = math.radians(4)        # disc size = shadow softness
        o = bpy.data.objects.new(name, ld)
        o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        bpy.context.collection.objects.link(o)
        return o

    # (X rotation = tilt, Z rotation = direction/azimuth)
    # high tilt -> short shadows that do not spill onto neighbours
    sun("Key",  (70, 0, 35),   1.6)    # main, almost from above
    sun("Fill", (72, 0, -110), 0.6)    # fill from the other side
    sun("Rim",  (75, 0, 180),  0.9)    # back light, separates from background


def main(FOLDER, OUTPUT):
    if not os.path.isdir(FOLDER):
        print(f"!!! Folder does not exist: {FOLDER}")
        return

    clear_scene()

    files = collect_models(FOLDER, RECURSIVE)

    clay = make_clay_material()
    cells = []          # finished objects to lay out
    cell_names = []     # file name for each cell (for labels)
    skipped = []
    flipped = []        # files flipped by AUTO_FLIP (console report)

    for k, (f, path) in enumerate(files, 1):
        progress("IMPORT", k, len(files))
        if f.lower().endswith('.3mf'):
            skipped.append(f)
            continue
        objs = import_file(path)
        if not objs:
            continue
        group = [join_objects(objs)] if ONE_PER_FILE else objs
        for obj in group:
            if obj is None:
                continue
            # material
            obj.data.materials.clear()
            obj.data.materials.append(clay)
            # orientation: a manual fix takes precedence over auto
            if not apply_manual_rotation(obj, f) and AUTO_UPRIGHT:
                if VIEW_MODE == "top":
                    orient_flat(obj)
                    if AUTO_FLIP and auto_flip_detail(obj):
                        flipped.append(f)
                else:
                    orient_upright(obj)
            # height normalisation
            if NORMALIZE:
                mn, mx = robust_bounds(obj)
                h = mx.z - mn.z
                if h > 1e-6:
                    s = TARGET_HEIGHT / h
                    obj.scale = (obj.scale[0]*s, obj.scale[1]*s, obj.scale[2]*s)
                    bpy.context.view_layer.update()
            cells.append(obj)
            cell_names.append(f)

    if not cells:
        print("!!! No models were imported.")
        return

    # cell size: MEDIAN of footprints - robust even when half the models
    # are outliers. Normal models fill the frame, odd ones stick out of their
    # cell (but stay visible) instead of blowing the whole grid up to nothing.
    foots = []
    heights = []
    for obj in cells:
        mn, mx = robust_bounds(obj)
        foots.append(max(mx.x - mn.x, mx.y - mn.y))
        heights.append(mx.z - mn.z)
    foots_sorted = sorted(foots)
    heights_sorted = sorted(heights)
    med = foots_sorted[len(foots_sorted) // 2]
    cell = med * (1.0 + SPACING)
    if cell <= 0:
        cell = 1.0
    rep_height = heights_sorted[len(heights_sorted) // 2]
    if rep_height <= 0:
        rep_height = cell

    # DIAGNOSTICS - spread of model sizes (check the console!)
    print("  --- model sizes (footprint) ---")
    print("      min: %.3f   median: %.3f   max: %.3f"
          % (foots_sorted[0], med, foots_sorted[-1]))
    if med > 0 and foots_sorted[-1] > med * 4:
        outliers = sorted(set(cell_names[i] for i, fp in enumerate(foots)
                              if fp > med * 4))
        print("  WARNING - these files are >4x larger than the median (wrong scale"
              " or a stray vertex): " + ", ".join(outliers))
        print("      -> fix: repair those files or set NORMALIZE = True")

    # AO distance must match the model scale (otherwise the effect vanishes
    # or blackens everything) - set only now, once the median is known
    if AO_STRENGTH > 0:
        ao_node = clay.node_tree.nodes.get("ClayAO")
        if ao_node:
            ao_node.inputs['Distance'].default_value = max(1e-4, med * 0.15)

    n = len(cells)

    label_mat = None
    if SHOW_LABELS:
        label_mat = bpy.data.materials.new("Label")
        label_mat.use_nodes = True
        lb = label_mat.node_tree.nodes.get("Principled BSDF")
        if lb:
            lb.inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1.0)
            lb.inputs["Roughness"].default_value = 0.9

    # --- SHELF PACKING --------------------------------------------------
    # Every model gets a slot of its real size (footprint), models are
    # placed shelf by shelf. No overlap despite different sizes -
    # and WITHOUT touching the model scale.
    #  * ALLOW_ROTATE: longer side horizontal -> lower shelves, tighter
    #  * sort by height descending -> similar heights on one shelf
    #  * centre vertically on the shelf -> neater, fewer holes
    gap = med * SPACING                       # absolute gap between models

    # PACKING DIMENSIONS: use the REAL bounding box, not percentiles.
    # Reason: robust_bounds trims the outermost 1% of vertices. With large
    # flat plates (walls, panels) geometry is dense in the middle and sparse
    # at the edges - so REAL edges get trimmed, the slot comes out too
    # small and neighbouring parts overlap.
    # Percentiles stay only as a safety net: if the real bbox is
    # absurdly larger (a stray vertex), the trimmed version is used.
    dims = []
    huge = []
    for i, obj in enumerate(cells):
        tmn, tmx = world_bbox(obj)                 # real dimensions
        rmn, rmx = robust_bounds(obj)              # trimmed by percentiles
        tw, th = tmx.x - tmn.x, tmx.y - tmn.y
        rw, rh = rmx.x - rmn.x, rmx.y - rmn.y
        if rw > 0 and rh > 0 and (tw > rw * 3.0 or th > rh * 3.0):
            dims.append([rw, rh])                  # pathological - take trimmed
            huge.append(cell_names[i])
        else:
            dims.append([tw, th])
    if huge:
        print("  [i] Stray geometry in: " + ", ".join(sorted(set(huge))))

    # (3) 90 deg in-plane rotation: put the longer side horizontally
    rotated = []
    if ALLOW_ROTATE:
        for i, obj in enumerate(cells):
            w, h = dims[i]
            if h > w:
                rotate_world(obj, 'Z', 90)
                dims[i] = [h, w]
                rotated.append(cell_names[i])

    # (1) sort by height descending - the classic shelf packing improvement
    order = sorted(range(n), key=lambda i: -dims[i][1])

    def pack(row_width):
        """Lays models out on shelves for the given row width.
        Returns (positions by index, width, height, bounds)."""
        shelves = []                          # [[indices], ...]
        cur, x_cur = [], 0.0
        for i in order:
            w = dims[i][0]
            if cur and x_cur + w > row_width:
                shelves.append(cur)
                cur, x_cur = [], 0.0
            cur.append(i)
            x_cur += w + gap
        if cur:
            shelves.append(cur)

        # width of every shelf (for horizontal centring)
        shelf_w = []
        for items in shelves:
            shelf_w.append(sum(dims[i][0] for i in items) + gap * (len(items) - 1))
        max_w = max(shelf_w) if shelf_w else 0.0

        pos = [None] * n
        y_top = 0.0
        for si, items in enumerate(shelves):
            sh = max(dims[i][1] for i in items)    # shelf height
            # centre the shelf horizontally - a partial row does not drift left
            x_cur = (max_w - shelf_w[si]) * 0.5
            for i in items:
                w, h = dims[i]
                # (2) centre vertically on the shelf
                pos[i] = (x_cur + w * 0.5, y_top - sh * 0.5)
                x_cur += w + gap
            y_top -= (sh + gap)

        xs_min = min(pos[i][0] - dims[i][0] * 0.5 for i in range(n))
        xs_max = max(pos[i][0] + dims[i][0] * 0.5 for i in range(n))
        ys_min = min(pos[i][1] - dims[i][1] * 0.5 for i in range(n))
        ys_max = max(pos[i][1] + dims[i][1] * 0.5 for i in range(n))
        return pos, (xs_max - xs_min), (ys_max - ys_min), (xs_min, xs_max, ys_min, ys_max)

    # Look for the row width that gives a layout with TARGET_ASPECT ratio.
    # A simple formula (sqrt of total area) is not enough, because shelves
    # have different heights and leave gaps - so many variants are tested.
    widest = max(d[0] for d in dims)
    total_area = sum((d[0] + gap) * (d[1] + gap) for d in dims)
    base = math.sqrt(total_area) if total_area > 0 else 1.0
    aspect_goal = TARGET_ASPECT if TARGET_ASPECT else (RES_X / float(RES_Y))
    best = None
    for k in range(1, 241):
        rw = max(widest, base * (0.35 + k * 0.02))
        pos, lw, lh, bounds = pack(rw)
        if lh <= 0 or lw <= 0:
            continue
        err = abs(math.log((lw / lh) / aspect_goal))   # log -> symmetric
        if best is None or err < best[0]:
            best = (err, pos, lw, lh, bounds)
    positions = best[1]
    lay_min_x, lay_max_x, lay_min_y, lay_max_y = best[4]
    print("  Layout aspect: %.2f:1 (target %.2f:1)" % (best[2] / best[3], aspect_goal))
    if rotated:
        print("  Rotated 90 deg while packing: %d parts" % len(rotated))

    # place models in their slots: base at z=0, footprint centred in the slot
    # IMPORTANT: the centre is computed with the same measure as the slot
    # size (real bbox) - otherwise the part shifts relative to its slot and
    # runs into its neighbour.
    for i, obj in enumerate(cells):
        cx, cy = positions[i]
        mn, mx = world_bbox(obj)
        center = (mn + mx) * 0.5
        obj.location.x += cx - center.x
        obj.location.y += cy - center.y
        obj.location.z += -mn.z            # stand it on the "floor"
        bpy.context.view_layer.update()

        if SHOW_LABELS:
            if VIEW_MODE == "top":
                offset = Vector((0, -dims[i][1] * 0.5 - gap * 0.5, 0))
                lbl_rot = (0, 0, 0)
            else:
                az = math.radians(CAM_AZIMUTH)
                offset = Vector((math.cos(az), math.sin(az), 0)) * cell * 0.42
                lbl_rot = (0, 0, az + math.radians(90))
            cur = bpy.data.curves.new("lbl", type='FONT')
            cur.body = cell_names[i]
            cur.align_x = 'CENTER'
            cur.align_y = 'CENTER'
            lbl = bpy.data.objects.new("lbl_" + cell_names[i], cur)
            lbl.location = Vector((cx, cy, 0.02)) + offset
            lbl.rotation_euler = lbl_rot
            s = cell * 0.10
            lbl.scale = (s, s, s)
            lbl.data.materials.append(label_mat)
            bpy.context.collection.objects.link(lbl)

    grid_diag = math.hypot(lay_max_x - lay_min_x, lay_max_y - lay_min_y)

    setup_lighting()

    # isometric camera (ortho)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = 'ORTHO'
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)

    # centre and framing computed from the LAYOUT bounds (shelf packing) -
    # robust to outliers: every model occupies a slot of its own size
    gx_min, gx_max = lay_min_x, lay_max_x
    gy_min, gy_max = lay_min_y, lay_max_y
    gz_min, gz_max = 0.0, rep_height
    target = Vector(((gx_min + gx_max) * 0.5,
                     (gy_min + gy_max) * 0.5,
                     (gz_min + gz_max) * 0.5))

    if VIEW_MODE == "top":
        # straight from above, looking down, top of frame = +Y
        cam.location = target + Vector((0, 0, 1)) * grid_diag * 3
    else:
        az = math.radians(CAM_AZIMUTH)
        el = math.radians(CAM_ELEVATION)
        direction = Vector((math.cos(el) * math.cos(az),
                            math.cos(el) * math.sin(az),
                            math.sin(el)))
        cam.location = target + direction * grid_diag * 3
    look = target - cam.location
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    # CAMERA CLIPPING RANGE. By default Blender clips everything further than
    # 100 units. Models can be large (footprints of 100+ units), and the
    # camera is placed grid_diag*3 away - with bigger sets that is
    # hundreds/thousands of units. Without this the render comes out EMPTY
    # (only the world background, no models, no floor). Scale range to scene.
    cam_dist = (target - cam.location).length
    cam_data.clip_start = max(1e-4, grid_diag * 0.001)
    cam_data.clip_end = (cam_dist + grid_diag * 4.0) * 2.0 + 1000.0
    print("  Camera: distance %.1f, range %.1f - %.1f"
          % (cam_dist, cam_data.clip_start, cam_data.clip_end))

    # fit ortho_scale to the 8 corners of the GRID volume in camera space
    bpy.context.view_layer.update()
    minv = cam.matrix_world.inverted()
    ext_x = ext_y = 0.0
    for cx in (gx_min, gx_max):
        for cy in (gy_min, gy_max):
            for cz in (gz_min, gz_max):
                p = minv @ Vector((cx, cy, cz))
                ext_x = max(ext_x, abs(p.x))
                ext_y = max(ext_y, abs(p.y))
    cam_data.ortho_scale = 2.0 * max(ext_x, ext_y) * 1.06   # 6% margin

    # floor: created AFTER fitting the camera, sized relative to the frame
    # (not 4x the grid), centred on the models. In iso it has to be larger,
    # because the ground "runs away" into the depth of the frame.
    floor_span = cam_data.ortho_scale * (4.0 if VIEW_MODE == "iso" else 1.6)
    bpy.ops.mesh.primitive_plane_add(
        size=floor_span, location=(target.x, target.y, 0))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("Floor")
    fmat.use_nodes = True
    fb = fmat.node_tree.nodes.get("Principled BSDF")
    if fb:
        fb.inputs["Base Color"].default_value = (0.10, 0.11, 0.13, 1.0)   # dark background
        fb.inputs["Roughness"].default_value = 0.9
    floor.data.materials.append(fmat)
    if TRANSPARENT_BG:
        floor.is_shadow_catcher = True   # only shadows visible, the rest transparent

    # render
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.filepath = OUTPUT
    scene.render.image_settings.file_format = 'PNG'
    if TRANSPARENT_BG:
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = 'RGBA'
    else:
        scene.render.film_transparent = False
        scene.render.image_settings.color_mode = 'RGB'
    # AgX rolls off bright areas gently (does not blow out to white)
    try:
        scene.view_settings.view_transform = 'AgX'
    except Exception:
        pass

    if USE_GPU:
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.get_devices()
            for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
                try:
                    prefs.compute_device_type = backend
                    if any(d.type == backend for d in prefs.devices):
                        for d in prefs.devices:
                            d.use = True
                        scene.cycles.device = 'GPU'
                        print(f"  Rendering on GPU ({backend})")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"  GPU unavailable, rendering on CPU: {e}")

    print(f"\n  Models in layout: {n}")
    if flipped:
        print(f"  AUTO_FLIP flipped {len(flipped)} parts (detail was facing down):")
        print("      " + ", ".join(sorted(set(flipped))))
    if skipped:
        print(f"  Skipped 3MF (export them to STL): {', '.join(skipped)}")

    def _render_to(path):
        progress("RENDER", os.path.basename(path))
        scene.render.filepath = path
        print(f"  Rendering -> {path}")
        bpy.ops.render.render(write_still=True)

    if not RENDER_BOTH_SIDES:
        _render_to(OUTPUT)
        print("  DONE.")
        return

    # A and B from ONE scene - import, orientation and packing computed once.
    _render_to(_with_suffix(OUTPUT, "_A"))

    # flip every model over and put it back into its slot.
    # A 180 deg rotation around X does not change the footprint size (X the
    # same, Y mirrored, Z the same), so slot positions stay the same -
    # parts end up exactly where they were on A.
    for i, obj in enumerate(cells):
        rotate_world(obj, 'X', 180)
        cx, cy = positions[i]
        mn, mx = world_bbox(obj)
        center = (mn + mx) * 0.5
        obj.location.x += cx - center.x
        obj.location.y += cy - center.y
        obj.location.z += -mn.z
    bpy.context.view_layer.update()

    _render_to(_with_suffix(OUTPUT, "_B"))
    print("  DONE.")


def _with_suffix(path, suffix):
    """inserts a suffix before the extension: sheet.png -> sheet_A.png"""
    root, ext = os.path.splitext(path)
    return root + suffix + ext


def run_all():
    """Single or batch mode - depending on BATCH."""
    if not BATCH:
        main(FOLDER, OUTPUT)
        return

    subs = []
    skipped_dirs = []
    for name in sorted(os.listdir(FOLDER)):
        d = os.path.join(FOLDER, name)
        if not os.path.isdir(d):
            continue
        # folders starting with _ are skipped (same as when zipping)
        if ONLY is not None and name not in ONLY:
            continue
        if name.startswith('_'):
            skipped_dirs.append(name)
            continue
        # only folders that contain models - also in subfolders
        # (e.g. Dreadnought\\Arms\\*.stl), if RECURSIVE = True
        try:
            if collect_models(d, RECURSIVE):
                subs.append((name, d))
        except Exception:
            continue

    if skipped_dirs:
        print("  Skipped folders starting with _ : " + ", ".join(skipped_dirs))

    if not subs:
        print(f"!!! No subfolders with models in: {FOLDER}")
        print("    (BATCH = True expects folders, each with 3D files)")
        return

    print("\n" + "=" * 60)
    print(f"  BATCH MODE - folders to process: {len(subs)}")
    print("=" * 60)

    progress("TOTAL", len(subs))
    done, failed = [], []
    for i, (name, d) in enumerate(subs, 1):
        progress("FOLDER", i, name)
        out = os.path.join(FOLDER, name + ".png")
        sides = " (_A + _B)" if RENDER_BOTH_SIDES else ""
        print("\n" + "-" * 60)
        print(f"  [{i}/{len(subs)}] {name}  ->  {name}{sides}.png")
        print("-" * 60)
        try:
            main(d, out)
            done.append(name)
            progress("DONE", "ok", name)
        except Exception as e:
            print(f"  !!! ERROR in '{name}': {e}")
            failed.append(name)
            progress("DONE", "fail", name)

    print("\n" + "=" * 60)
    print(f"  FINISHED: done {len(done)} / {len(subs)}")
    if failed:
        print("  Failed: " + ", ".join(failed))
    print("=" * 60 + "\n")


_parse_args()
run_all()
