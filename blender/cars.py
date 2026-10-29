"""THE ANULMENT (EX Inc.) - original Valdoran vehicle designs, modelled procedurally in Blender (bpy).
Run: blender -b -P blender/cars.py   -> assets/models/car_<type>.glb (+ docs/cars_render.png)
Each car is built from a lofted cross-section cage + subdivision surface. All designs are original (no real makes, no logos).
Objects per car: paint (white, tinted in game), glass, trim, lamp_f, lamp_r, wheel_FL/FR/RL/RR (pivot at hub)."""
import bpy, bmesh, math, os, sys
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "models")
os.makedirs(OUT, exist_ok=True)

# L length, W width, wb wheelbase, wr wheel radius, ride: sill height, belt: shoulder height, roof height,
# A/C: cabin start/end as fraction of length from front (0..1), nose/tail heights, extras
TYPES = {
    "sedan":  dict(L=4.75, W=1.82, wb=2.80, wr=0.33, ride=0.26, belt=0.92, roof=1.45, A=0.33, C=0.76, nose=0.74, tail=0.95, rw=0.76),
    "estate": dict(L=4.80, W=1.82, wb=2.82, wr=0.33, ride=0.26, belt=0.92, roof=1.48, A=0.33, C=0.95, nose=0.74, tail=1.30, rw=0.80),
    "taxi":   dict(L=4.60, W=1.78, wb=2.70, wr=0.32, ride=0.26, belt=0.95, roof=1.50, A=0.32, C=0.78, nose=0.78, tail=0.98, rw=0.80, taxi=True),
    "police": dict(L=4.85, W=1.85, wb=2.85, wr=0.34, ride=0.26, belt=0.93, roof=1.47, A=0.33, C=0.77, nose=0.75, tail=0.96, rw=0.77, lightbar=True),
    "hatch":  dict(L=3.90, W=1.74, wb=2.45, wr=0.31, ride=0.25, belt=0.92, roof=1.50, A=0.30, C=0.93, nose=0.72, tail=1.05, rw=0.85),
    "van":    dict(L=5.40, W=1.95, wb=3.20, wr=0.36, ride=0.32, belt=1.15, roof=2.35, A=0.10, C=0.30, nose=1.10, tail=2.30, rw=0.95, boxy=True, cargo=True),
    "policevan": dict(L=5.60, W=2.00, wb=3.30, wr=0.37, ride=0.34, belt=1.15, roof=2.45, A=0.10, C=0.32, nose=1.12, tail=2.40, rw=0.95, boxy=True, cargo=True, lightbar=True),
    "bus":    dict(L=11.0, W=2.50, wb=5.80, wr=0.50, ride=0.38, belt=1.20, roof=3.05, A=0.03, C=0.97, nose=1.30, tail=2.90, rw=0.97, boxy=True),
}

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def mat(name, col, emit=0.0, metal=0.0, rough=0.4, alpha=1.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Metallic"].default_value = metal; b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*col, 1); b.inputs["Emission Strength"].default_value = emit
    return m

def section(p, f, x):
    """half cross-section (list of (y_side, z)) at fraction f (0 front .. 1 rear)."""
    L, W = p["L"], p["W"] / 2
    # plan-view width taper at nose/tail
    taper = 1.0 - 0.10 * max(0, (0.12 - f) / 0.12) ** 1.6 - 0.08 * max(0, (f - 0.90) / 0.10) ** 1.6
    if p.get("boxy"): taper = 1.0 - 0.04 * max(0, (0.06 - f) / 0.06) - 0.03 * max(0, (f - 0.95) / 0.05)
    w = W * taper
    # fender bulges over the wheels
    fw = p.get("fender", 0.02)
    for wf in (0.5 - p["wb"] / L / 2, 0.5 + p["wb"] / L / 2):
        w += fw * math.exp(-((f - wf) / 0.07) ** 2)
    # top profile: nose -> hood -> windscreen -> roof -> rear screen -> deck -> tail
    A, C, nose, tail, roof, belt = p["A"], p["C"], p["nose"], p["tail"], p["roof"], p["belt"]
    if p.get("boxy"):
        if f < A: deck = nose + (belt - nose) * (f / max(A, 1e-3)) ** 0.5
        else: deck = belt
    else:
        if f < A: deck = nose + (belt - nose) * (f / A) ** 0.7
        elif f > C: deck = belt + (tail - belt) * ((f - C) / (1 - C)) ** 1.5
        else: deck = belt
    # greenhouse
    rw = p["rw"]
    if p.get("cargo"):
        gh = roof if f > A * 0.6 else None; deck = deck if f < A else belt
    elif p.get("boxy"):
        gh = roof if A * 0.5 < f < C + 0.03 else None
    else:
        ws = A + (C - A) * 0.28; rs = A + (C - A) * 0.78
        if A <= f <= C:
            if f < ws: gh = belt + (roof - belt) * math.sin((f - A) / (ws - A) * math.pi / 2)
            elif f > rs: gh = belt + (roof - belt) * math.cos((f - rs) / (C - rs) * math.pi / 2)
            else: gh = roof
        else: gh = None
    ride = p["ride"]
    pts = [(0.0, ride - 0.02), (w * 0.86, ride), (w, ride + 0.18), (w, deck - 0.12), (w * 0.97, deck)]
    if gh is not None and gh > deck + 0.03:
        pts += [(w * rw + (w * 0.97 - w * rw) * 0.15, deck + 0.04), (w * rw, gh - 0.03), (w * rw * 0.6, gh)]
        top = gh
    else:
        pts += [(w * 0.80, deck + 0.03), (w * 0.45, deck + 0.05)]
        top = deck + 0.05
    pts += [(0.0, top + (0.005 if gh is None else 0.0))]
    return pts, deck, gh

def build_body(p, name):
    L = p["L"]; N = 34
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    rows = []
    for i in range(N + 1):
        f = i / N
        f = 0.5 - 0.5 * math.cos(f * math.pi)        # denser at ends
        y = L / 2 - f * L                             # car faces +Y in Blender (front at +y)
        pts, deck, gh = section(p, f, 0)
        half = [bm.verts.new((sx, y, z)) for sx, z in pts]
        mirr = [bm.verts.new((-sx, y, z)) for sx, z in reversed(pts[1:-1])]
        rows.append(half + mirr)
    n = len(rows[0])
    for i in range(N):
        a, b = rows[i], rows[i + 1]
        for j in range(n):
            k = (j + 1) % n
            bm.faces.new((a[j], a[k], b[k], b[j]))
    # caps
    bm.faces.new(list(reversed(rows[0]))); bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    sub = ob.modifiers.new("sub", "SUBSURF"); sub.levels = 2; sub.render_levels = 2
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier="sub")
    bpy.ops.object.shade_smooth()
    return ob

def split_glass(ob, p):
    """faces above the beltline inside the cabin become glass (separate object)."""
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me)
    L = p["L"]; belt = p["belt"]
    glass = []
    for fc in bm.faces:
        c = fc.calc_center_median(); f = (L / 2 - c.y) / L
        nz = fc.normal.z
        if c.z > belt + 0.06 and c.z < p["roof"] - 0.05 and (abs(fc.normal.x) > 0.25 or abs(fc.normal.y) > 0.35):
            if p.get("cargo") and f > p["A"] + 0.02 and abs(fc.normal.y) < 0.5: continue   # no side glass on the cargo box
            if p.get("cargo") and f > 0.9: continue
            glass.append(fc)
    gm = bpy.data.meshes.new(ob.name + "_glass"); gb = bmesh.new()
    vm = {}
    for fc in glass:
        vs = []
        for v in fc.verts:
            if v.index not in vm: vm[v.index] = gb.verts.new(v.co.copy())
            vs.append(vm[v.index])
        gb.faces.new(vs)
    bmesh.ops.delete(bm, geom=glass, context="FACES")
    bm.to_mesh(me); bm.free()
    for v in gb.verts: v.co += Vector((0, 0, 0))
    gb.to_mesh(gm); gb.free()
    go = bpy.data.objects.new(ob.name + "_glass", gm); bpy.context.collection.objects.link(go)
    # solidify-ish: offset glass slightly inward is not needed; mark smooth
    for pl in gm.polygons: pl.use_smooth = True
    return go

def box(name, c, s, m, rot=(0, 0, 0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=c, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = s
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        bv = o.modifiers.new("bv", "BEVEL"); bv.width = bevel; bv.segments = 2
        bpy.ops.object.modifier_apply(modifier="bv")
    o.data.materials.append(m); return o

def wheel(name, c, r, w, mt, mr, side):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=r, depth=w, location=(0, 0, 0), rotation=(0, math.pi / 2, 0))
    t = bpy.context.object; t.data.materials.append(mt)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bv = t.modifiers.new("bv", "BEVEL"); bv.width = r * 0.18; bv.segments = 3; bpy.ops.object.modifier_apply(modifier="bv")
    bpy.ops.object.shade_smooth()
    # rim: 5-spoke original design = disc + spokes
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=r * 0.66, depth=w * 0.2, location=(side * w * 0.42, 0, 0), rotation=(0, math.pi / 2, 0))
    rim = bpy.context.object; rim.data.materials.append(mr); bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    parts = [t, rim]
    for k in range(5):
        a = k * 2 * math.pi / 5
        bpy.ops.mesh.primitive_cube_add(size=1, location=(side * w * 0.47, math.cos(a) * r * 0.36, math.sin(a) * r * 0.36), rotation=(a, 0, 0))
        sp = bpy.context.object; sp.scale = (w * 0.08, r * 0.14, r * 0.62); bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        sp.data.materials.append(mr); parts.append(sp)
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts: o.select_set(True)
    bpy.context.view_layer.objects.active = t; bpy.ops.object.join()
    t.name = name; t.location = c
    return t

def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join(); objs[0].name = name
    return objs[0]

def make(tname, p):
    clear()
    M_paint = mat("paint", (0.9, 0.9, 0.9), metal=0.3, rough=0.25)
    M_glass = mat("glass", (0.02, 0.025, 0.04), rough=0.05)
    M_trim = mat("trim", (0.03, 0.03, 0.035), rough=0.5)
    M_chrome = mat("chrome", (0.75, 0.75, 0.78), metal=1.0, rough=0.15)
    M_tire = mat("tire", (0.02, 0.02, 0.02), rough=0.9)
    M_hl = mat("lamp_f", (1.0, 0.97, 0.9), emit=6)
    M_tl = mat("lamp_r", (1.0, 0.05, 0.08), emit=6)
    M_red = mat("bar_red", (0.1, 0.3, 1.0), emit=8); M_blue = mat("bar_blue", (0.1, 0.3, 1.0), emit=8)   # Valdoran police: blue + blue; M_blue = mat("bar_blue", (0.1, 0.3, 1.0), emit=8)
    M_white = mat("whitepanel", (0.95, 0.95, 0.95), rough=0.3); M_taxi = mat("taxilamp", (1.0, 0.85, 0.2), emit=4)
    L, W = p["L"], p["W"]
    body = build_body(p, "paint"); body.data.materials.append(M_paint)
    glass = split_glass(body, p); glass.name = "glass"; glass.data.materials.append(M_glass)
    trim = []
    yf, yr = L / 2, -L / 2
    nz, tz = p["nose"], p["tail"]
    # headlights: slim LED strips (signature), tail-lights: full-width light bar
    hlw = W * 0.30 if not p.get("boxy") else W * 0.22
    lf = [box("hl%d" % s, (s * W * 0.30, yf - 0.02, nz - 0.12), (hlw, 0.12, 0.07 if not p.get("boxy") else 0.14), M_hl) for s in (-1, 1)]
    lr = [box("tl", (0, yr + 0.01, max(p["ride"] + 0.35, tz - 0.16)), (W * 0.88, 0.08, 0.07), M_tl)]
    # grille / diffuser / side skirts
    trim.append(box("grille", (0, yf - 0.06, p["ride"] + 0.16), (W * 0.62, 0.14, 0.16), M_trim, bevel=0.02))
    trim.append(box("diff", (0, yr + 0.04, p["ride"] + 0.10), (W * 0.80, 0.12, 0.14), M_trim))
    for s in (-1, 1):
        trim.append(box("skirt", (s * (W / 2 + 0.005), 0, p["ride"] + 0.07), (0.04, p["wb"] * 0.78, 0.1), M_trim))
        trim.append(box("mirror", (s * (W / 2 * p["rw"] + 0.22), L / 2 - L * p["A"] - 0.05, p["belt"] + 0.10), (0.16, 0.08, 0.08), M_trim, bevel=0.02))
    if p.get("spoiler"):
        trim.append(box("wing", (0, yr + 0.30, tz + 0.22), (W * 0.84, 0.30, 0.03), M_trim, bevel=0.01))
        for s in (-1, 1): trim.append(box("strut", (s * W * 0.28, yr + 0.32, tz + 0.10), (0.04, 0.12, 0.22), M_trim))
    if p.get("lightbar"):
        rz = p["roof"]
        trim.append(box("barbase", (0, -0.15, rz + 0.04), (1.2, 0.26, 0.06), M_trim))
        lf.append(box("bar_r", (-0.32, -0.15, rz + 0.11), (0.52, 0.22, 0.10), M_red, bevel=0.02))
        lr.append(box("bar_b", (0.32, -0.15, rz + 0.11), (0.52, 0.22, 0.10), M_blue, bevel=0.02))
    if p.get("taxi"):
        trim.append(box("taxisign", (0, -0.25, p["roof"] + 0.10), (0.42, 0.18, 0.16), M_taxi, bevel=0.03))
    # bake objects
    objs = {"paint": body, "glass": glass, "trim": join(trim, "trim") if trim else None}
    if p.get("lightbar"):
        br = [o for o in lf if o.name.startswith("bar_r")][0]; bb = [o for o in lr if o.name.startswith("bar_b")][0]
        lf.remove(br); lr.remove(bb); br.name = "bar_red"; bb.name = "bar_blue"
    objs["lamp_f"] = join(lf, "lamp_f")
    objs["lamp_r"] = join(lr, "lamp_r")
    tw = 0.24 if p["wr"] > 0.3 else 0.19
    ax = p["wb"] / 2
    for nm, (sx, sy) in {"wheel_FL": (-1, 1), "wheel_FR": (1, 1), "wheel_RL": (-1, -1), "wheel_RR": (1, -1)}.items():
        wheel(nm, (sx * (W / 2 - tw / 2 + 0.02), sy * ax, p["wr"]), p["wr"], tw, M_tire, M_chrome, sx)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "car_%s.glb" % tname), export_format="GLB", use_selection=False,
                              export_apply=True, export_yup=True)
    print("CAR", tname, flush=True)

for k, p in TYPES.items():
    if len(sys.argv) > 1 and "--only" in sys.argv and k not in sys.argv: continue
    make(k, p)

# --- contact sheet render of all designs (Eevee)
if "--render" in sys.argv:
    clear()
    for i, k in enumerate(TYPES):
        bpy.ops.import_scene.gltf(filepath=os.path.join(OUT, "car_%s.glb" % k))
        for o in bpy.context.selected_objects:
            if o.parent is None: o.location.x += (i % 3) * 6.5 - 6.5; o.location.y += (i // 3) * 7 - 7
    sc = bpy.context.scene; sc.render.engine = "BLENDER_EEVEE_NEXT"; sc.render.resolution_x = 1600; sc.render.resolution_y = 1000
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (14, -22, 14); cam.rotation_euler = (math.radians(58), 0, math.radians(32))
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun); sun.rotation_euler = (0.7, 0.2, 0.5); sun.data.energy = 3
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.04, 0.1, 1)
    sc.render.filepath = os.path.join(ROOT, "docs", "cars_render.png"); bpy.ops.render.render(write_still=True)
