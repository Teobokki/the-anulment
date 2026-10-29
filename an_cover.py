"""v1.0.0.3: no body skin under clothes or hair - the covered skin faces are REMOVED, not shrunk.

The Ana / Daniel body skin is a full body under the garments. With the 1.0.0.1/1.0.0.2 'pull in / shrink' tweaks the two
layers were still only millimetres apart, so on real GPUs the skin z-fought / poked through the T-shirts, sleeves and hair
(worst on the decimated far-crowd copies, where the layers cross each other by centimetres).

Now every skin triangle that has a top (T-shirt / tank / sleeve) right above or below it along its normal is taken OUT of
the skin and becomes a 'tank.under' layer in the garment's colour (so even a crack in the garment shows cloth, never skin),
skin fully inside the trousers is deleted, and the garments get a depth offset so they always win over the layer below.
Results are cached per model in assets/models/cover_<model>.npz (built by tools/build_cover.py; computed at runtime
if the cache is missing)."""
import os, numpy as np
from panda3d.core import GeomVertexReader, GeomTriangles, Geom

CLOTH = ("tank", "sleeve", "straps", "trousers", "belt", "buckle")


def _is_cloth(name):
    return any(name.startswith(c) for c in CLOTH)


def _gnodes(m):
    return list(m.find_all_matches("**/+GeomNode"))


def _tris(geom):
    out = []
    for pi in range(geom.get_num_primitives()):
        p = geom.get_primitive(pi).decompose()
        for k in range(p.get_num_primitives()):
            s = p.get_primitive_start(k); out.append((p.get_vertex(s), p.get_vertex(s + 1), p.get_vertex(s + 2)))
    return np.array(out, np.int64).reshape(-1, 3)


def _verts(g, m, i, col="vertex"):
    vd = g.node().get_geom(i).get_vertex_data()
    if not vd.has_column(col): return None
    r = GeomVertexReader(vd, col); V = []
    while not r.is_at_end(): V.append(tuple(r.get_data3()))
    mat = g.get_mat(m)
    if col == "normal":
        W = np.array([tuple(mat.xform_vec(p)) for p in V], np.float64)
        return W / (np.linalg.norm(W, axis=1, keepdims=True) + 1e-12)
    return np.array([tuple(mat.xform_point(p)) for p in V], np.float64)


def _poking(P, C, CN, reach):
    """skin points lying OUTSIDE a garment (through it) - directly along the nearest garment vertex's normal"""
    out = np.zeros(len(P), bool)
    for s in range(0, len(P), 512):
        d = P[s:s + 512, None, :] - C[None]; dist = np.sqrt((d * d).sum(2)); k = dist.argmin(1)
        dd = d[np.arange(len(k)), k]; nn = CN[k]; along = (dd * nn).sum(1); L = dist[np.arange(len(k)), k]
        out[s:s + 512] = (L < reach) & (along > 0.0) & (along > 0.7 * L)
    return out


def _hits(O, D, A, E1, E2, tmax):
    """for each ray (O, D): any triangle hit with |t| < tmax (Moller-Trumbore, both directions)"""
    res = np.zeros(len(O), bool)
    for s in range(0, len(O), 256):
        o = O[s:s + 256, None, :]; d = D[s:s + 256, None, :]
        p = np.cross(d, E2[None]); det = (E1[None] * p).sum(2)
        ok = np.abs(det) > 1e-12; inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        tv = o - A[None]; u = (tv * p).sum(2) * inv
        q = np.cross(tv, E1[None]); v = (d * q).sum(2) * inv; t = (E2[None] * q).sum(2) * inv
        hit = ok & (u >= -1e-4) & (v >= -1e-4) & (u + v <= 1 + 1e-4) & (np.abs(t) < tmax)
        res[s:s + 256] = hit.any(1)
    return res


LIMBS = ("armR", "armL", "foreR", "foreL", "handR", "handL")


def _group(g, m):
    """which rigid part a geom moves with: an arm / forearm node, or the body"""
    n = g
    while not n.is_empty() and n != m:
        if n.get_name() in LIMBS: return n.get_name()
        n = n.get_parent()
    return "body"


TOP = ("tank", "sleeve", "straps")


def compute(m, tmax=0.03, rigid=True, col_r=0.0, under=True):
    """-> {"<skin geom>|under": tris under a top (any sample hits it), "<skin geom>|del": tris fully under trousers/belt}.
    Only garments of the SAME rigid part count (body, or that arm) unless rigid=False (static far figures)."""
    gs = _gnodes(m); cl = {}; pv = {}
    for g in gs:
        nm = g.get_name()
        if not _is_cloth(nm): continue
        cat = "top" if any(nm.startswith(c) for c in TOP) else "bot"
        for i in range(g.node().get_num_geoms()):
            V = _verts(g, m, i); T = _tris(g.node().get_geom(i))
            if len(T): cl.setdefault(((_group(g, m) if rigid else "all"), cat), []).append((V[T[:, 0]], V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]))
            CN = _verts(g, m, i, "normal")
            if CN is not None: pv.setdefault(((_group(g, m) if rigid else "all"), cat), []).append((V, CN))
    out = {}
    for g in gs:
        if not g.get_name().startswith("skin"): continue
        V = _verts(g, m, 0); T = _tris(g.node().get_geom(0))
        if not len(T): continue
        a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        N = np.cross(b - a, c - a); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
        samples = ((a + b + c) / 3, a * 0.8 + (b + c) * 0.1, b * 0.8 + (a + c) * 0.1, c * 0.8 + (a + b) * 0.1,
                   (a + b) * 0.45 + c * 0.1, (b + c) * 0.45 + a * 0.1, (a + c) * 0.45 + b * 0.1)
        for cat in ("top", "bot"):
            L = cl.get(((_group(g, m) if rigid else "all"), cat))
            if not L: continue
            A = np.concatenate([x[0] for x in L]); E1 = np.concatenate([x[1] for x in L]); E2 = np.concatenate([x[2] for x in L])
            lo = np.minimum(A, np.minimum(A + E1, A + E2)); hi = np.maximum(A, np.maximum(A + E1, A + E2))
            H = []
            for P in samples:
                pl = P.min(0) - tmax; ph = P.max(0) + tmax; sel = ((hi >= pl) & (lo <= ph)).all(1)
                H.append(_hits(P, N, A[sel], E1[sel], E2[sel], tmax))
            H = np.array(H)
            if not under:       # full-detail characters: only delete skin that is completely under a garment
                r = np.where(H.all(0))[0]
                if len(r): out[g.get_name() + "|del" + cat] = r
                continue
            hit = H.any(0) if cat == "top" else H.all(0)
            if cat == "top" and ((_group(g, m) if rigid else "all"), cat) in pv:
                C = np.concatenate([x[0] for x in pv[((_group(g, m) if rigid else "all"), cat)]])
                CN = np.concatenate([x[1] for x in pv[((_group(g, m) if rigid else "all"), cat)]])
                pk = _poking(V, C, CN, tmax * 1.5)
                hit |= pk[T].any(1)          # any corner sticking out through the garment
            if cat == "top" and _group(g, m) == "body" and col_r:
                # shirts are tubes round the body: a skin point that a horizontal ray from the body axis meets the
                # shirt within col_r of is under (or through) the shirt
                tk = [t for t in gs if t.get_name() == "tank" and _group(t, m) == "body"]
                if tk:
                    TV = np.concatenate([_verts(t, m, 0) for t in tk]); ax = TV[:, :2].mean(0)
                    TT = [(_verts(t, m, 0), _tris(t.node().get_geom(0))) for t in tk]
                    A2 = np.concatenate([v[t[:, 0]] for v, t in TT]); B2 = np.concatenate([v[t[:, 1]] - v[t[:, 0]] for v, t in TT])
                    C2 = np.concatenate([v[t[:, 2]] - v[t[:, 0]] for v, t in TT])
                    for P in samples:
                        R = P.copy(); R[:, 0] -= ax[0]; R[:, 1] -= ax[1]; R[:, 2] = 0
                        R /= np.linalg.norm(R, axis=1, keepdims=True) + 1e-9
                        pl = P.min(0) - col_r; ph = P.max(0) + col_r
                        lo2 = np.minimum(A2, np.minimum(A2 + B2, A2 + C2)); hi2 = np.maximum(A2, np.maximum(A2 + B2, A2 + C2))
                        sel = ((hi2 >= pl) & (lo2 <= ph)).all(1)
                        hit |= _hits(P, R, A2[sel], B2[sel], C2[sel], col_r)
            r = np.where(hit)[0]
            if len(r): out[g.get_name() + ("|under" if cat == "top" else "|del")] = r
    return out


def apply(m, dels):
    """skin under a top becomes a 'tank.under' layer in the top's colour (far figures: fills any crack in the garment;
    drawn behind the garment, which has a depth offset); skin completely under a garment is deleted.
    All lists of one geom index its ORIGINAL triangle order, so they are applied together."""
    gs = _gnodes(m); byname = {g.get_name(): g for g in gs}
    tops = [g for g in gs if any(g.get_name().startswith(c) for c in TOP)]
    per = {}
    for key in dels:
        nm, kind = key.split("|"); per.setdefault(nm, {})[kind] = dels[key]
    for nm, kinds in per.items():
        g = byname.get(nm)
        if g is None: continue
        geom = g.node().modify_geom(0); T = _tris(geom)
        drop = np.zeros(len(T), bool); und = np.zeros(len(T), bool)
        for kind, idx in kinds.items():
            idx = idx[idx < len(T)]
            (und if kind == "under" else drop)[idx] = True
        und &= ~drop
        if und.any():
            ug = Geom(geom.get_vertex_data()); tr = GeomTriangles(Geom.UH_static)
            for x, y, z in T[und]: tr.add_vertices(int(x), int(y), int(z))
            ug.add_primitive(tr)
            grp = _group(g, m); src = [t for t in tops if _group(t, m) == grp] or tops
            from panda3d.core import GeomNode
            st = src[0].node().get_geom_state(0) if src else g.node().get_geom_state(0)
            un = GeomNode("tank.under"); un.add_geom(ug, st)
            u = g.get_parent().attach_new_node(un); u.set_transform(g.get_transform())
            u.set_texture_off(1); u.set_shader_input("use_tex", 0.0)
        tr = GeomTriangles(Geom.UH_static)
        for x, y, z in T[~(drop | und)]: tr.add_vertices(int(x), int(y), int(z))
        geom.clear_primitives(); geom.add_primitive(tr)
    for g in gs:
        if _is_cloth(g.get_name()): g.set_depth_offset(1)


def cover(m, key, base, tmax=0.03, rigid=True, col_r=0.0, under=True):
    """delete the covered skin of model m (cached by key)"""
    p = os.path.join(base, "assets", "models", "cover_%s.npz" % key)
    dels = None
    if os.path.exists(p):
        try:
            z = np.load(p); dels = {k: z[k] for k in z.files}
        except Exception as e: print("an_cover: bad cache", p, e)
    if dels is None:
        dels = compute(m, tmax, rigid, col_r, under)
        try: np.savez(p, **dels)
        except Exception: pass
    apply(m, dels)
    return dels


def smooth_normals(m):
    """far-crowd meshes: area-weighted smooth vertex normals (welded by position) - the decimation left them faceted"""
    from panda3d.core import GeomVertexRewriter
    for g in _gnodes(m):
        gn = g.node()
        for i in range(gn.get_num_geoms()):
            geom = gn.modify_geom(i); vd = geom.modify_vertex_data()
            if not vd.has_column("normal"): continue
            r = GeomVertexReader(vd, "vertex"); V = []
            while not r.is_at_end(): V.append(tuple(r.get_data3()))
            V = np.array(V, np.float64); T = _tris(geom)
            if not len(T): continue
            key = np.round(V / 0.002).astype(np.int64); _, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel()
            fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
            acc = np.zeros((inv.max() + 1, 3))
            for k in range(3): np.add.at(acc, inv[T[:, k]], fn)
            Nn = acc[inv]; Nn /= np.linalg.norm(Nn, axis=1, keepdims=True) + 1e-12
            w = GeomVertexRewriter(vd, "normal"); j = 0
            while not w.is_at_end():
                old = w.get_data3(); n = Nn[j]
                if not np.isfinite(n).all() or np.linalg.norm(n) < 0.5: n = (old[0], old[1], old[2])
                w.set_data3(float(n[0]), float(n[1]), float(n[2])); j += 1
