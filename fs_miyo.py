"""Mesh helpers (box / blob meshes) shared by THE ANULMENT characters and street furniture."""
import math, random, re, time
import numpy as np
from panda3d.core import (GeomVertexFormat, GeomVertexArrayFormat, GeomVertexData, GeomTriangles, Geom, GeomNode, InternalName,
                          Material, TransparencyAttrib, CardMaker, ColorBlendAttrib, TextNode, NodePath)
from direct.gui.DirectGui import DirectFrame, DirectEntry, DirectSlider, DGG
import fs_data as D
import fs_ui as U

VOX = 0.5
STEP = 0.62
ORANGE = (1.0, 0.55, 0.1, 1)
ABILITY_CHAR = "ana"
_FMT = None
_COL = {}
FACES = [((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]), ((-1, 0, 0), [(0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)]),
         ((0, 1, 0), [(1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)]), ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
         ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]), ((0, 0, -1), [(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)])]
SHADE = [0.86, 0.80, 0.90, 0.95, 1.0, 0.6]
DAN_HEAD_O = (0.0, -0.030, 1.578)
DAN_HEAD_R = ((0.955854594707489, -0.2752596139907837, -0.10283010452985764), (0.2674517035484314, 0.9599443078041077, -0.08352530002593994),
              (0.12170232087373734, 0.0523359552025795, 0.9911858439445496))

def _fmt():
    global _FMT
    if _FMT is None:
        af = GeomVertexArrayFormat()
        af.add_column(InternalName.get_vertex(), 3, Geom.NT_float32, Geom.C_point)
        af.add_column(InternalName.get_normal(), 3, Geom.NT_float32, Geom.C_normal)
        af.add_column(InternalName.get_color(), 4, Geom.NT_float32, Geom.C_color)
        af.add_column(InternalName.get_tangent(), 4, Geom.NT_float32, Geom.C_vector)
        _FMT = GeomVertexFormat.register_format(GeomVertexFormat(af))
    return _FMT

def mesh_node(name, V, N, C, T, tris):
    """numpy arrays -> GeomNode (v3 n3 c4 t4 interleaved)"""
    n = len(V)
    vd = GeomVertexData(name, _fmt(), Geom.UH_static); vd.unclean_set_num_rows(n)
    arr = np.concatenate([V, N, C, T], 1).astype(np.float32)
    memoryview(vd.modify_array(0)).cast("B")[:] = arr.tobytes()
    tr = GeomTriangles(Geom.UH_static); tr.set_index_type(Geom.NT_uint32)
    ta = tr.modify_vertices(); ta.unclean_set_num_rows(len(tris) * 3)
    memoryview(ta).cast("B")[:] = np.asarray(tris, np.uint32).ravel().tobytes()
    g = Geom(vd); g.add_primitive(tr); gn = GeomNode(name); gn.add_geom(g); return gn

def blob_mesh(name, blobs, col, seg=10, ring=7):
    """union-look mesh of ellipsoids: blobs = [(cx, cy, cz, rx, ry, rz)] -> GeomNode with vertex colours"""
    V, N, C, T, tris = [], [], [], [], []
    for (cx, cy, cz, rx, ry, rz) in blobs:
        base = len(V)
        for i in range(ring + 1):
            th = math.pi * i / ring
            for j in range(seg + 1):
                ph = 2 * math.pi * j / seg
                nx, ny, nz = math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)
                V.append((cx + rx * nx, cy + ry * ny, cz + rz * nz))
                n = (nx / rx, ny / ry, nz / rz); L = math.sqrt(sum(a * a for a in n)) or 1; N.append(tuple(a / L for a in n))
                C.append(col); T.append((1, 0, 0, 1))
        for i in range(ring):
            for j in range(seg):
                a = base + i * (seg + 1) + j; b = a + seg + 1
                tris.append((a, b, b + 1)); tris.append((a, b + 1, a + 1))
    return mesh_node(name, np.array(V, np.float32), np.array(N, np.float32), np.array(C, np.float32), np.array(T, np.float32), tris)

def box_mesh(name, boxes):
    """boxes = [(x0, y0, z0, x1, y1, z1, (r, g, b, a))] -> GeomNode"""
    V, N, C, T, tris = [], [], [], [], []
    for (x0, y0, z0, x1, y1, z1, col) in boxes:
        for nrm, cs in FACES:
            base = len(V)
            for (ox, oy, oz) in cs:
                V.append((x0 + (x1 - x0) * ox, y0 + (y1 - y0) * oy, z0 + (z1 - z0) * oz)); N.append(nrm); C.append(col); T.append((1, 0, 0, 1))
            tris.append((base, base + 1, base + 2)); tris.append((base, base + 2, base + 3))
    return mesh_node(name, np.array(V, np.float32), np.array(N, np.float32), np.array(C, np.float32), np.array(T, np.float32), tris)

def shade(np_, app, gloss=0.2, sheen=0.0):
    import fs_shaders
    fs_shaders.apply(np_, app, gloss=gloss, sheen=sheen)
    mt = Material("prop"); mt.set_base_color((1, 1, 1, 1)); mt.set_roughness(0.7); np_.set_material(mt, 1)
    return np_
