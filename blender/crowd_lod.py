"""THE ANULMENT: low-poly crowd LOD copies of the EX Inc. character meshes (same proportions, decimated)."""
import bpy, sys, os
src, dst, ratio = sys.argv[-3], sys.argv[-2], float(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
for o in list(bpy.data.objects):
    if o.type != "MESH": continue
    n = o.name.lower()
    if any(k in n for k in ("finger", "fist", "eye", "sphere", "buckle", "choker", "straps")) and "fingers" not in n:
        bpy.data.objects.remove(o); continue
    if "fist" in n: bpy.data.objects.remove(o); continue
    r = ratio * (0.15 if "hair" in n else 1.0)
    m = o.modifiers.new("dec", "DECIMATE"); m.ratio = max(0.004, min(1.0, r))
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_apply=True, export_materials="EXPORT", export_image_format="NONE")
