"""v1.0.0.2: solid hair + clean clothes for every character built on the Ana / Daniel meshes.

* hair: the strand meshes are kept exactly as in FIREOUT SHINE (opaque, two-sided, depth write, same shader), and a
  hair-coloured scalp shell is added underneath (a copy of the head skin under the strands, pushed 2 mm out), so the
  gaps between strands show hair, never the scalp / background -> hair reads solid at every distance.
* clothes: body skin that lies under a shirt / sleeve is pulled 4 mm inwards, so it can never poke through the cloth.
* far crowd: simple opaque hair shapes (no strands)."""
import numpy as np
from panda3d.core import (GeomVertexReader, GeomVertexRewriter, GeomVertexFormat, GeomVertexData, GeomVertexWriter,
                          GeomTriangles, Geom, GeomNode, Material)


def _geomnodes(m, name):
    out = []
    for g in m.find_all_matches("**/" + name):
        if g.node().is_geom_node(): out.append(g)
        out += [c for c in g.find_all_matches("**/+GeomNode") if c != g]
    return out


def _read(gn, i, col):
    vd = gn.node().get_geom(i).get_vertex_data()
    if not vd.has_column(col): return None
    r = GeomVertexReader(vd, col); out = []
    while not r.is_at_end(): out.append(tuple(r.get_data4() if col == "color" else r.get_data3()))
    return np.array(out, np.float32)


def _tris(geom):
    t = []
    for pi in range(geom.get_num_primitives()):
        p = geom.get_primitive(pi).decompose()
        for k in range(p.get_num_primitives()):
            s = p.get_primitive_start(k); t.append((p.get_vertex(s), p.get_vertex(s + 1), p.get_vertex(s + 2)))
    return np.array(t, np.int64).reshape(-1, 3)


def inflate_cloth(m, names=("tank", "sleeve*", "tank.*", "straps"), d=0.004):
    done = set()
    for nm in names:
        for g in _geomnodes(m, nm):
            if g in done: continue
            done.add(g); gn = g.node()
            for i in range(gn.get_num_geoms()):
                vd = gn.modify_geom(i).modify_vertex_data()
                if not vd.has_column("normal"): continue
                rv = GeomVertexRewriter(vd, "vertex"); rn = GeomVertexReader(vd, "normal")
                while not rv.is_at_end():
                    v = rv.get_data3(); n = rn.get_data3(); rv.set_data3(v + n * d)


def hair_shell(m, out=0.002, reach=0.016):
    """hair-coloured scalp under the strands (same transforms / shader inputs as the hair: it is the hair node's child)"""
    hr = m.find("**/hair")
    sk = _geomnodes(m, "skin")
    hg = _geomnodes(m, "hair")
    if hr.is_empty() or not sk or not hg: return None
    sk = sk[0]; H = []; HC = []
    for g in hg:
        for i in range(g.node().get_num_geoms()):
            v = _read(g, i, "vertex"); c = _read(g, i, "color")
            if v is None: continue
            mat = g.get_mat(m); v = np.array([tuple(mat.xform_point(tuple(map(float, p)))) for p in v[::3]], np.float32)
            H.append(v)
            if c is not None: HC.append(c)
    H = np.concatenate(H); col = np.concatenate(HC).mean(0) if HC else np.array([0.05, 0.035, 0.03, 1], np.float32)
    col[3] = 1.0
    geom = sk.node().get_geom(0); V = _read(sk, 0, "vertex"); N = _read(sk, 0, "normal"); T = _tris(geom)
    mat = sk.get_mat(m)
    V = np.array([tuple(mat.xform_point(tuple(map(float, p)))) for p in V], np.float32)
    N = np.array([tuple(mat.xform_vec(tuple(map(float, p)))) for p in N], np.float32)
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    head = np.where(V[:, 2] > H[:, 2].min() - 0.01)[0]
    cov = np.zeros(len(V), bool)
    for s in range(0, len(head), 512):
        idx = head[s:s + 512]; P = V[idx]
        dd = P[:, None, :] - H[None, :, :]                               # skin -> hair
        dist = np.sqrt((dd * dd).sum(2))
        outside = (-(dd * N[idx][:, None, :]).sum(2)) > -0.002            # the strand is on the outer side of the skin
        cov[idx] = (np.where(outside, dist, 9.0).min(1) < reach)
    face = (N[:, 1] < -0.35) & (V[:, 2] < 1.665)          # front of the head below the hairline (brows, lashes, eyes)
    cov &= ~face
    sel = T[cov[T].all(1)]
    if len(sel) == 0: return None
    used = np.unique(sel); remap = -np.ones(len(V), np.int64); remap[used] = np.arange(len(used))
    fmt = GeomVertexFormat.get_v3n3c4(); vd = GeomVertexData("hairshell", fmt, Geom.UH_static); vd.set_num_rows(len(used))
    wv, wn, wc = GeomVertexWriter(vd, "vertex"), GeomVertexWriter(vd, "normal"), GeomVertexWriter(vd, "color")
    hinv = hr.get_mat(m); hinv.invert_in_place()
    for k in used:
        p = V[k] + N[k] * out
        wv.add_data3(hinv.xform_point(tuple(map(float, p)))); wn.add_data3(hinv.xform_vec(tuple(map(float, N[k]))))
        wc.add_data4(*map(float, col))
    tr = GeomTriangles(Geom.UH_static)
    for a, b, c in remap[sel]: tr.add_vertices(int(a), int(b), int(c))
    g = Geom(vd); g.add_primitive(tr); gn = GeomNode("hair_shell"); gn.add_geom(g)
    sh = hr.attach_new_node(gn)
    mt = Material("hair_shell"); mt.set_base_color((1, 1, 1, 1)); mt.set_roughness(0.35); mt.set_metallic(0.0); sh.set_material(mt, 1)
    return sh


def _world(g, m, col):
    out = []
    for i in range(g.node().get_num_geoms()):
        v = _read(g, i, col)
        if v is None: continue
        mat = g.get_mat(m)
        f = mat.xform_point if col == "vertex" else mat.xform_vec
        out.append(np.array([tuple(f(tuple(map(float, p)))) for p in v], np.float32))
    return np.concatenate(out) if out else np.zeros((0, 3), np.float32)


def tuck_under_cloth(m, names=("tank", "sleeve*", "tank.*"), reach=0.008, d=0.004):
    C = [_world(g, m, "vertex") for nm in names for g in _geomnodes(m, nm)]
    C = np.concatenate(C) if C else np.zeros((0, 3), np.float32)
    if len(C) == 0: return
    C = C[::2]
    for g in _geomnodes(m, "skin"):
        gn = g.node(); mat = g.get_mat(m); inv = g.get_mat(m); inv.invert_in_place()
        V = _world(g, m, "vertex"); N = _world(g, m, "normal"); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
        lo, hi = C.min(0) - reach, C.max(0) + reach
        idx = np.where(((V >= lo) & (V <= hi)).all(1))[0]; mv = np.zeros(len(V), bool)
        for s in range(0, len(idx), 512):
            k = idx[s:s + 512]; dd = C[None, :, :] - V[k][:, None, :]
            dist = np.sqrt((dd * dd).sum(2)); outside = (dd * N[k][:, None, :]).sum(2) > -0.003
            mv[k] = np.where(outside, dist, 9.0).min(1) < reach
        if not mv.any(): continue
        V2 = V - N * d * mv[:, None]
        for i in range(gn.get_num_geoms()):
            vd = gn.modify_geom(i).modify_vertex_data(); rw = GeomVertexRewriter(vd, "vertex"); j = 0
            while not rw.is_at_end():
                rw.get_data3(); rw.set_data3(inv.xform_point(tuple(map(float, V2[j])))); j += 1
            break


def prepare(m):
    """called once per cached model (fs_people.load)"""
    try:
        tuck_under_cloth(m)
        hair_shell(m)
    except Exception as e:
        print("an_hair.prepare:", e)


# mean vertex colour of the strand meshes (daniel.bam / heroine.bam): hair colours are given as real target colours and
# turned into the shader tint, so grey is grey and blonde is blonde on both models (no >1 tints washing out the strands)
HAIR_MEAN = {"daniel": (0.043, 0.029, 0.022), "ana": (0.072, 0.029, 0.037)}
NATURAL_HAIR = [(0.030, 0.024, 0.021), (0.055, 0.036, 0.026), (0.10, 0.065, 0.042), (0.17, 0.10, 0.06),
                (0.20, 0.085, 0.045), (0.40, 0.29, 0.16), (0.36, 0.345, 0.33), (0.55, 0.535, 0.515)]


def hair_tint(who, target):
    b = HAIR_MEAN["daniel" if who == "daniel" else "ana"]
    return (target[0] / b[0], target[1] / b[1], target[2] / b[2], 1.0)

# everyday mix for crowds / protesters / police: mostly dark and brown, some auburn / blonde, few grey
EVERYDAY_HAIR = [NATURAL_HAIR[i] for i in (0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 5, 6, 7)]
