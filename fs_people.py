"""On-foot characters: ANA & DANIEL (playable crew) and pedestrians (same v2 skin texture set, varied outfits)."""
import math, os, random
from panda3d.core import NodePath, Filename, TextNode, SamplerState
import fs_shaders

_models = {}
PED_TOPS = [(0.85, 0.85, 0.88), (0.12, 0.12, 0.14), (0.75, 0.2, 0.3), (0.2, 0.45, 0.7), (0.9, 0.7, 0.2), (0.3, 0.6, 0.4), (0.6, 0.4, 0.75)]
PED_BOTTOMS = [(0.1, 0.12, 0.25), (0.15, 0.15, 0.16), (0.55, 0.5, 0.42), (0.6, 0.08, 0.08), (0.85, 0.82, 0.75), (0.25, 0.3, 0.2)]
PED_HAIR = [(1, 1, 1), (0.6, 0.6, 0.6), (2.2, 1.6, 1.1), (3.0, 2.6, 1.8), (1.6, 0.8, 0.5), (0.4, 0.4, 0.45)]


OUTFITS = [("default", "DEFAULT", "Tank top, red slacks, sneakers"), ("crop", "CROP TOP", "White fitted crop top, red slacks, sneakers"), ("bikini", "BIKINI", "Coral two-piece swimsuit, flip-flops"),
           ("police", "POLICE", "POLIȚIA VALDOREI uniform: shirt, cap, badge, boots")]
# v1.0.4: one outfit table per playable character - used by the house WARDROBE and the pause-menu CLOTHING switcher
CREW_OUTFITS = {"ana": OUTFITS,
                "daniel": [("default", "DEFAULT", "Floral shirt, navy trousers, sneakers"), ("swim", "SWIM SHORTS", "Blue swim shorts, bare feet")]}


def outfits_for(app_base, who):
    """the outfits this character really has (an outfit whose model file is missing is left out)"""
    out = []
    for oid, nm, desc in CREW_OUTFITS.get(who, CREW_OUTFITS["ana"]):
        fn = BAM.get(who, "heroine") + ("" if oid == "default" else "_" + oid) + ".bam"
        if oid == "default" or os.path.exists(os.path.join(app_base, "assets", "models", fn)): out.append((oid, nm, desc))
    return out


_faces = {}
BAM = {"daniel": "daniel"}
HAND_TINT = (1.031, 0.959, 0.893, 1)    # v1.0.4.1: ANA's hands match her warmer, more realistic skin (tools_skin_realism.py)
def load(app, who, outfit="default"):
    key = who if outfit == "default" else who + "_" + outfit
    if key not in _models:
        fn = BAM.get(who, "heroine") + ("" if outfit == "default" else "_" + outfit) + ".bam"
        p = os.path.join(app.BASE, "assets", "models", fn)
        if not os.path.exists(p): p = os.path.join(app.BASE, "assets", "models", BAM.get(who, "heroine") + ".bam"); outfit = "default"
        if who != "ana" and not os.path.exists(p):
            p = os.path.join(app.BASE, "assets", "models", "heroine.bam")
        m = app.loader.load_model(Filename.from_os_specific(p)); fix_uv(m); _models[key] = m
    return _models[key].copy_to(NodePath(who))


def fix_uv(m):
    """glTF exports the UV set as 'texcoord.0'; rename it to the default 'texcoord' so the shader's p3d_MultiTexCoord0 sees it."""
    from panda3d.core import GeomVertexFormat, GeomVertexArrayFormat, InternalName
    src = InternalName.make("texcoord.0"); dst = InternalName.get_texcoord()
    for gn in m.find_all_matches("**/+GeomNode"):
        node = gn.node()
        for i in range(node.get_num_geoms()):
            g = node.modify_geom(i); vd = g.modify_vertex_data(); fmt = vd.get_format()
            if not fmt.has_column(src): continue
            nf = GeomVertexFormat(fmt)
            for a in range(nf.get_num_arrays()):
                arr = nf.modify_array(a)
                if arr.has_column(src):
                    c = arr.get_column(src)
                    nc, nt, ct, st = c.get_num_components(), c.get_numeric_type(), c.get_contents(), c.get_start()
                    arr.remove_column(src); arr.add_column(dst, nc, nt, ct, st)
            vd.unclean_set_format(GeomVertexFormat.register_format(nf))


def tex(app, name):
    p = os.path.join(app.BASE, "assets", "tex", name)
    if not os.path.exists(p):       # v1.0.0.2: a missing skin-tone variant falls back to the base skin, never a missing texture
        import re
        alt = re.sub(r"_t[0-9]+(?=\.png$)", "", name)
        print("tex: missing", name, "-> using", alt); p = os.path.join(app.BASE, "assets", "tex", alt)
    t = app.loader.load_texture(Filename.from_os_specific(p))
    t.set_minfilter(SamplerState.FT_linear_mipmap_linear)
    return t


class Person:
    def __init__(self, game, who="ana", x=0.0, y=0.0, h=0.0, ped=False):
        self.g = game; app = game.app; self.app = app; self.who = who
        self.x, self.y, self.h = x, y, h
        self.vx = self.vy = 0.0
        self.phase = 0.0; self.knock = 0.0; self.health = 100.0; self.in_car = None; self.hidden = False
        self.np = app.render.attach_new_node("person"); self.ped = ped
        self.outfit = (getattr(game, "outfits", {}) or {}).get(who, "default") if not ped else "default"
        if self.outfit not in [o[0] for o in outfits_for(app.BASE, who)]: self.outfit = "default"
        self.build_model()
        self.np.set_pos(x, y, 0.0); self.np.set_h(h)

    def set_outfit(self, outfit):
        if outfit == self.outfit: return
        self.outfit = outfit; self.model.remove_node(); self._chew_np = None; self.build_model()

    def build_model(self):
        app = self.app; who = self.who; ped = self.ped
        base = who if who == "daniel" else "ana"
        m = load(app, base, self.outfit); m.reparent_to(self.np); m.set_h(180); self.model = m
        suf = "_" + base if base != "ana" and os.path.exists(os.path.join(app.BASE, "assets", "tex", "skin_c_%s.png" % base)) else ""
        if self.outfit != "default" and os.path.exists(os.path.join(app.BASE, "assets", "tex", "skin_c_%s.png" % self.outfit)):
            suf = "_" + self.outfit
        fs_shaders.apply(m, app, gloss=0.15, sheen=0.4)
        sk = m.find("**/skin")
        if not sk.is_empty():
            sk.set_texture(tex(app, "skin_c%s.png" % suf), 1)
            fs_shaders.apply(sk, app, gloss=0.22, tex=True, nmap=tex(app, "skin_n%s.png" % suf), sheen=0.8)
        ey = m.find("**/eyes")
        if not ey.is_empty():
            ey.set_texture(tex(app, "eye_c%s.png" % suf), 1); fs_shaders.apply(ey, app, gloss=0.9, tex=True)
        # v1.0.3: arms hang free at the sides (separate shoulder-pivot nodes that swing / hold weapons)
        self.armR = m.find("**/armR"); self.armL = m.find("**/armL")
        self.foreR = m.find("**/foreR"); self.foreL = m.find("**/foreL")
        self.handR = m.find("**/handR"); self.handL = m.find("**/handL")
        self.scrub_t = None         # shower scrub animation clock (None = off)
        for ar in (self.armR, self.armL):
            if ar.is_empty(): continue
            for gn in ar.find_all_matches("**/+GeomNode"):
                if "sleeve" in str(gn): continue        # shirt sleeves keep the cloth material
                if "fingers" in str(gn) or "fist" in str(gn):   # hands: skin-tone material (no baked UVs), same skin shading
                    fs_shaders.apply(gn, app, gloss=0.22, sheen=0.8, tint=HAND_TINT if base == "ana" else (1, 1, 1, 1)); continue
                gn.set_texture(tex(app, "skin_c%s.png" % suf), 1)
                fs_shaders.apply(gn, app, gloss=0.22, tex=True, nmap=tex(app, "skin_n%s.png" % suf), sheen=0.8)
        self.arm_pose = None        # (pitchR, pitchL) override from the weapon code; None = natural swing
        self.hand_np = {sd: (m.find("**/fingers" + sd), m.find("**/fist" + sd)) for sd in ("R", "L")}
        self.set_grip(False, False)
        sh = m.find("**/tank")
        if base == "daniel" and not sh.is_empty():
            for n in [sh] + list(m.find_all_matches("**/sleeve*")):
                n.set_texture(tex(app, "floral.png"), 1); fs_shaders.apply(n, app, gloss=0.1, tex=True, sheen=0.5)
        hr = m.find("**/hair")
        if not hr.is_empty():
            fs_shaders.apply(hr, app, gloss=0.35, sheen=0.3); hr.set_two_sided(True)
            hr.set_transparency(0); hr.set_depth_write(True); hr.set_depth_offset(2); hr.set_bin("opaque", 5)
        self.legL = m.find("**/legL"); self.legR = m.find("**/legR")
        if self.outfit in ("bikini", "swim"):   # bare legs carry the baked skin; flip-flops keep their own material
            for lg in (self.legL, self.legR):
                if lg.is_empty(): continue
                lg.set_texture(tex(app, "skin_c%s.png" % suf), 1)
                fs_shaders.apply(lg, app, gloss=0.22, tex=True, nmap=tex(app, "skin_n%s.png" % suf), sheen=0.8)
                for ff in lg.find_all_matches("**/ff*"): fs_shaders.apply(ff, app, gloss=0.2, sheen=0.3)
        if self.outfit == "police":
            bd = m.find("**/badge")
            if not bd.is_empty(): fs_shaders.apply(bd, app, gloss=0.9, sheen=0.0, emitboost=1.0)
        self.upper = [c for c in m.get_children() if c.get_name() not in ("legL", "legR")]
        if ped:
            rnd = random.Random()
            # never ANA's signature look (black tank + choker + red slacks + black bob) or DANIEL's floral shirt
            ch = m.find("**/choker")
            if not ch.is_empty(): ch.remove_node()
            for n in [m.find("**/tank")] + list(m.find_all_matches("**/sleeve*")) + list(m.find_all_matches("**/tank.*")):
                if not n.is_empty(): n.set_texture_off(2); n.set_shader_input("use_tex", 0.0)
            tops = [c for c in PED_TOPS if max(c) > 0.3] + [(0.55, 0.62, 0.7), (0.95, 0.55, 0.45), (0.4, 0.3, 0.25), (0.92, 0.9, 0.8)]
            bottoms = [c for c in PED_BOTTOMS if not (c[0] > 0.4 and c[1] < 0.2)] + [(0.22, 0.32, 0.5), (0.35, 0.35, 0.38)]
            hairs = [h for h in PED_HAIR if h != (1, 1, 1)]
            hr_ = m.find("**/hair")
            if not hr_.is_empty():
                v = rnd.random()                 # different hair silhouettes: fuller, cropped or a bun
                hc = hr_.get_bounds().get_center()
                def hscale(sx, sy, sz, h=hr_, c=hc):
                    h.set_scale(sx, sy, sz); h.set_pos(c[0] * (1 - sx), c[1] * (1 - sy), c[2] * (1 - sz))
                if base == "ana":
                    if v < 0.35: hscale(1.06, 1.12, 1.03)
                    elif v < 0.65:
                        from fs_miyo import blob_mesh
                        bun = m.attach_new_node(blob_mesh("bun", [(-0.012, 0.16, 1.64, 0.055, 0.05, 0.05), (-0.012, 0.13, 1.66, 0.045, 0.04, 0.04)], (0.06, 0.05, 0.045, 1)))
                        bun.reparent_to(hr_.get_parent()); bun.set_name("hair_bun"); fs_shaders.apply(bun, app, gloss=0.35, sheen=0.3); hscale(0.98, 0.96, 1.0)
                else:
                    if v < 0.4: hscale(1.05, 1.08, 1.08)
                    elif v < 0.7: hscale(1.0, 0.98, 0.94)
            for nm, pal in (("tank", tops), ("straps", None), ("trousers", bottoms), ("hair", hairs)):
                n = m.find("**/" + nm)
                if n.is_empty(): continue
                if nm == "straps":
                    n.set_shader_input("tint", self._top + (1,)); continue
                c = rnd.choice(pal)
                if nm == "tank":
                    self._top = c
                    for sl in [n] + list(m.find_all_matches("**/sleeve*")) + list(m.find_all_matches("**/tank.*")): recolor(sl, c)
                    continue
                if nm == "trousers":
                    from panda3d.core import MaterialAttrib
                    g0 = n if n.node().get_type().get_name() == "GeomNode" else n.find("**/+GeomNode")
                    ma = g0.node().get_geom_state(0).get_attrib(MaterialAttrib)
                    ob = ma.get_material().get_base_color() if ma is not None else (0.6, 0.07, 0.06, 1)
                    recolor(n, c)
                    for lg in (self.legL, self.legR):          # the trouser legs - shoes keep their colour
                        if not lg.is_empty(): recolor(lg, c, only=lambda b, ob=ob: abs(b[0] - ob[0]) + abs(b[1] - ob[1]) + abs(b[2] - ob[2]) < 0.06)
                    continue
                if nm == "hair": continue      # v1.0.0.4: hair keeps FIREOUT SHINE's own colour (no tint)
            sc = rnd.uniform(0.94, 1.04); m.set_scale(sc)
            # v1.0.4: NPCs share ANA's realistic skin (same skin_c / skin_n maps + skin shading); only a slight natural
            # tone variation per person so nobody looks cloned
            k = rnd.uniform(-1, 1); w = rnd.uniform(-1, 1)
            tone = (1.0 + 0.03 * k + 0.02 * w, 1.0 + 0.035 * k, 1.0 + 0.04 * k - 0.03 * w, 1)
            # v1.0.0.4: no skin tint - the skin is exactly ANA's / DANIEL's (tone kept only so the random sequence is unchanged)

    def walk_anim(self, dt, speed):
        if self.knock > 0:
            return
        k = min(1.0, speed / 5.5)
        self.phase += dt * (4.5 + speed * 1.35)
        a = math.sin(self.phase) * (22 + 14 * k) * min(1.0, speed / 1.2)
        if not self.legL.is_empty(): self.legL.set_p(a)
        if not self.legR.is_empty(): self.legR.set_p(-a)
        bob = abs(math.sin(self.phase)) * 0.035 * min(1.0, speed / 1.5)
        self.model.set_z(bob); self.model.set_p(-k * 6)
        self.model.set_r(math.sin(self.phase) * 1.5 * min(1.0, speed / 2))
        self.swing_arms(a, k, speed)

    OUT = 1.0          # roll sign that splays the RIGHT arm outward (the left arm uses the opposite sign)

    def set_arms(self, ar, al, fr=None, fl=None):
        """ar/al = (pitch, roll_out) for the upper arms, fr/fl = (pitch, roll_in) for the forearms. Negative pitch = forward/up."""
        if self.armR.is_empty(): return
        o = self.OUT
        self.armR.set_hpr(0, ar[0], o * ar[1]); self.armL.set_hpr(0, al[0], -o * al[1])
        if not self.foreR.is_empty():
            fr = fr or (0, 0); fl = fl or (0, 0)
            self.foreR.set_hpr(0, fr[0], o * fr[1]); self.foreL.set_hpr(0, fl[0], -o * fl[1])

    def set_grip(self, r, l=False):
        """closed (gripping / fist) or relaxed open hands"""
        for sd, on in (("R", r), ("L", l)):
            op, cl = self.hand_np.get(sd, (NodePath(), NodePath()))
            if op.is_empty() or cl.is_empty(): continue
            if on: op.hide(); cl.show()
            else: op.show(); cl.hide()
        self.grip = (bool(r), bool(l))

    def swing_arms(self, a, k, speed):
        """arms hang relaxed at the sides and swing opposite to the legs (negative pitch = forward)."""
        if self.armR.is_empty(): return
        if self.scrub_t is not None or getattr(self, "anim_lock", False): return
        if getattr(self, "swim", False) and self.arm_pose is None:      # treading water: sculling arms
            w = math.sin(self.phase * 0.8)
            self.set_arms((-55 + 22 * w, 34), (-55 - 22 * w, 34), (-45 + 15 * w, 0), (-45 - 15 * w, 0)); return
        mv = min(1.0, speed / 1.2)
        sw = a * (0.85 + 0.35 * k)                      # walk ~ +-20 deg, run ~ +-40 deg
        base = -8.0 * k * mv                            # running: arms carried slightly forward
        breathe = 0.0 if mv > 0.05 else math.sin(self.phase * 0.35) * 1.2
        pr, pl = base + sw + breathe, base - sw + breathe
        # elbows: soft bend at rest, more on the forward swing, ~80 deg when running
        er = -10 - 0.45 * max(0.0, -pr) - 70 * k * mv; el = -10 - 0.45 * max(0.0, -pl) - 70 * k * mv
        if self.arm_pose is not None:
            ap = tuple(self.arm_pose) + (None,) * (4 - len(self.arm_pose))
            if ap[0] is not None: pr = ap[0]; er = ap[2] if ap[2] is not None else -8
            if ap[1] is not None: pl = ap[1]; el = ap[3] if ap[3] is not None else -8
        self.set_arms((pr, 3.0 + 3.0 * k), (pl, 3.0 + 3.0 * k), (er, 0), (el, 0))

    # ---- shower: looping, alternating scrub (hair -> left shoulder/arm -> right shoulder/arm), swimsuit stays on
    @staticmethod
    def _mix(a, b, t):
        t = t * t * (3 - 2 * t); return [x + (y - x) * t for x, y in zip(a, b)]

    def scrub(self, dt):
        if self.armR.is_empty(): return
        if self.scrub_t is None: self.scrub_t = 0.0
        t = self.scrub_t = self.scrub_t + dt
        w = math.sin(t * 10.5); w2 = math.sin(t * 10.5 + math.pi)       # quick scrubbing strokes, hands alternate
        # pose vector: armR(p, roll_out), foreR(p, roll_in), armL(p, roll_out), foreL(p, roll_in)
        HAIR = [-4 + 8 * w, 98, 0, 136 + 10 * w, -4 + 8 * w2, 98, 0, 136 + 10 * w2]          # both hands lathering the hair
        NECK_R = [-112 + 8 * w, 38, -118 + 10 * w2, 12, -12, 8, -40, 0]                         # right hand scrubs neck / shoulder
        NECK_L = [-12, 8, -40, 0, -112 + 8 * w2, 38, -118 + 10 * w, 12]                         # left hand scrubs neck / shoulder
        ARM_L = [-62, -30 + 9 * w, -55 + 10 * w2, 30, -35, 70, -5, 0]                          # left arm out, right hand rubs along it
        ARM_R = [-35, 70, -5, 0, -62, -30 + 9 * w2, -55 + 10 * w, 30]                          # right arm out, left hand rubs along it
        seq = [HAIR, NECK_R, ARM_L, HAIR, NECK_L, ARM_R]; seg = 2.4; c = (t / seg) % len(seq); i = int(c); f = c - i
        cur = seq[i]; nxt = seq[(i + 1) % len(seq)]
        v = self._mix(cur, nxt, max(0.0, (f - 0.78) / 0.22))
        self.set_arms((v[0], v[1]), (v[4], v[5]), (v[2], v[3]), (v[6], v[7]))
        self.model.set_r(math.sin(t * 1.3) * 2.0); self.model.set_p(math.sin(t * 0.9) * 1.5)

    # ---- SELMOTES (v1.0.3): selfie facial expressions. A small patch that hugs the face over the mouth carries the
    # skin texture re-projected from the model with a new mouth painted in (SMILE / GOOFY FROWN). NEUTRAL = no patch.
    def set_expression(self, expr="neutral"):
        old = getattr(self, "face_np", None)
        if old is not None and not old.is_empty(): old.remove_node()
        self.face_np = None; self.expression = expr
        if expr == "neutral" or self.ped: return
        bam = BAM.get(self.who, "heroine") + ("" if self.outfit == "default" else "_" + self.outfit)
        base = self.app.BASE; jp = os.path.join(base, "assets", "models", "face_%s.json" % bam)
        if not os.path.exists(jp):
            bam = BAM.get(self.who, "heroine"); jp = os.path.join(base, "assets", "models", "face_%s.json" % bam)
        if not os.path.exists(jp): return
        import json
        from panda3d.core import (GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Geom, GeomNode, TransparencyAttrib,
                                  GeomVertexArrayFormat, InternalName, Material)
        d = _faces.get(jp) or _faces.setdefault(jp, json.load(open(jp)))
        root = self.model.attach_new_node("face_" + expr)
        mt = Material("face"); mt.set_base_color((1, 1, 1, 1)); mt.set_roughness(0.6); mt.set_metallic(0.0)   # the skin shader reads p3d_Material
        af = GeomVertexArrayFormat(); af.add_column(InternalName.get_vertex(), 3, Geom.NT_float32, Geom.C_point)
        af.add_column(InternalName.get_normal(), 3, Geom.NT_float32, Geom.C_normal)
        af.add_column(InternalName.get_color(), 4, Geom.NT_float32, Geom.C_color)
        af.add_column(InternalName.get_texcoord(), 2, Geom.NT_float32, Geom.C_texcoord)
        af.add_column(InternalName.get_tangent(), 4, Geom.NT_float32, Geom.C_vector)      # the skin shader builds a TBN frame
        fmt = GeomVertexFormat.register_format(GeomVertexFormat(af))
        for rn, r in d["regions"].items():
            tn = "face_%s_%s_%s.png" % (bam, expr, rn)
            if not os.path.exists(os.path.join(base, "assets", "tex", tn)): continue
            vd = GeomVertexData("face", fmt, Geom.UH_static)
            wv, wn, wt, wc, wg = (GeomVertexWriter(vd, c) for c in ("vertex", "normal", "texcoord", "color", "tangent"))
            for x, y, z, a, b, c, u, v in r["v"]:
                wv.add_data3(x, y, z); wn.add_data3(a, b, c); wt.add_data2(u, v); wc.add_data4(1, 1, 1, 1); wg.add_data4(0.96, 0.27, 0.0, 1)
            tr = GeomTriangles(Geom.UH_static); n = r["nx"] + 1
            for j in range(r["nz"]):
                for i in range(r["nx"]):
                    k = j * n + i; tr.add_vertices(k, k + 1, k + n + 1); tr.add_vertices(k, k + n + 1, k + n)
            g = Geom(vd); g.add_primitive(tr); gn = GeomNode("face_%s_%s" % (expr, rn)); gn.add_geom(g)
            f = root.attach_new_node(gn)
            t = tex(self.app, tn); t.set_wrap_u(SamplerState.WM_clamp); t.set_wrap_v(SamplerState.WM_clamp)
            f.set_texture(t, 1); f.set_material(mt, 1)
            fs_shaders.apply(f, self.app, gloss=0.22, tex=True, sheen=0.8)
        root.set_two_sided(True); root.set_transparency(TransparencyAttrib.M_alpha); root.set_depth_offset(2)
        root.set_bin("transparent", 4); root.set_depth_write(False)
        self.face_np = root

    def set_chew(self, k):
        """v1.0.4 eating: the mouth opens and closes while chewing (mouth-only open-mouth patch, built once, toggled)"""
        if self.ped: return
        cn = getattr(self, "_chew_np", None)
        if cn is None:
            if k <= 0: return
            keep_np, keep_ex = getattr(self, "face_np", None), getattr(self, "expression", "neutral")
            if keep_np is not None: keep_np.detach_node()
            self.face_np = None; self.set_expression("smile"); cn = self.face_np
            self.face_np = keep_np; self.expression = keep_ex
            if keep_np is not None: keep_np.reparent_to(self.model)
            if cn is None: self._chew_np = NodePath("nochew"); return
            for c in cn.get_children():
                if "mouth" not in c.get_name(): c.remove_node()
            self._chew_np = cn; cn.set_name("chew")
            if getattr(self, "skin_tint", None) is not None:
                cn.set_shader_input("tint", self.skin_tint, 5)
                for gnp in cn.find_all_matches("**/+GeomNode"): gnp.set_shader_input("tint", self.skin_tint, 5)
        if cn.is_empty() or cn.get_num_children() == 0: return
        if k > 0.45 and (getattr(self, "face_np", None) is None): cn.show()
        else: cn.hide()

    def stop_scrub(self):
        self.scrub_t = None; self.model.set_r(0); self.model.set_p(0); self.set_arms((0, 3), (0, 3), (-10, 0), (-10, 0))

    def sync(self, z=0.0):
        # v1.0.3: follow the real walkable height (sidewalk kerb, boardwalk, pier, sloped sand) and ease up/down kerbs so a
        # step is a quick smooth step instead of a pop
        gz = self.g.world.ground_z(self.x, self.y) if hasattr(self.g.world, "ground_z") else (0.15 if self.g.world.on_sidewalk(self.x, self.y) else 0.0)
        cur = getattr(self, "_gz", None)
        # v1.0.4: BUILD structures (ANA's ability since v1.0.4.1) - walls/towers block, low steps and tops can be walked on
        B = getattr(self.g, "builds", None)
        if B is not None and B.items and self.in_car is None:
            self.x, self.y, st = B.resolve(self.x, self.y, cur if cur is not None else gz, 0.33)
            if st is not None: gz = max(gz, st)
        if cur is not None and gz < cur - 0.45: cur = max(gz, cur - 0.32)           # step / fall off a ledge over a few frames
        else: cur = gz if cur is None or abs(gz - cur) > 0.45 else cur + (gz - cur) * 0.45
        self._gz = cur
        # v1.0.4: TSUNAMI - deep water lifts people up: they float / tread water with their head above the surface
        self.swim = False; fz = 0.0
        ts = getattr(self.g, "tsunami", None)
        if ts is not None and self.in_car is None:
            w = ts.level_at(self.x, self.y)
            if w > cur + 1.05:
                self.swim = True; fz = w - 1.22 - cur + 0.05 * math.sin(self.g.time * 2.4 + self.x)
        self.np.set_pos(self.x, self.y, z + cur + fz); self.np.set_h(self.h)

    def knock_down(self, dirx, diry, power):
        self.knock = 2.4
        self.vx += dirx * power; self.vy += diry * power
        self.model.set_p(80); self.model.set_z(0.25)

    def update_knock(self, dt):
        if self.knock > 0:
            self.knock -= dt
            self.x += self.vx * dt; self.y += self.vy * dt
            self.vx *= math.exp(-4 * dt); self.vy *= math.exp(-4 * dt)
            px, py, nx, ny, tag = self.g.world.grid.push_circle(self.x, self.y, 0.35)
            self.x += px; self.y += py
            if self.knock <= 0:
                self.model.set_p(0); self.model.set_z(0); self.vx = self.vy = 0
            return True
        return False

    def seat(self, car, side):
        """place the upper body in a car seat (legs hidden)."""
        self.in_car = car; self.np.reparent_to(car.np)
        sp = car.spec; z = min(-0.55, sp["roof"] - 1.82)
        self.np.set_pos(0.36 * side, -0.15 if car.kind not in ("van", "kei", "ambulance", "policevan", "bus") else 0.9, z); self.np.set_h(0)
        for lg in (self.legL, self.legR):
            if not lg.is_empty(): lg.hide()
        self.model.set_p(0); self.model.set_z(0); self.model.set_r(0)
        if not self.armR.is_empty():     # driver: hands up on the wheel; passenger: hands resting on the lap
            drv = side == 1
            if drv: self.set_arms(*(getattr(self, "wheel_pose", None) or ((-38, 6), (-38, 6), (-48, 8), (-48, 8))))
            else: self.set_arms((-12, 4), (-12, 4), (-62, 6), (-62, 6))
            self.set_grip(drv, drv)

    def unseat(self, x, y, h):
        self.in_car = None; self.np.reparent_to(self.app.render)
        for lg in (self.legL, self.legR):
            if not lg.is_empty(): lg.show(); lg.set_p(0)
        self.set_arms((0, 3), (0, 3), (-10, 0), (-10, 0)); self.set_grip(False, False)
        self.x, self.y, self.h = x, y, h; self.sync()

    def destroy(self):
        self.np.remove_node()


def recolor(np_, c, only=None):
    """v1.0.4: give a garment a new base colour (material override per geom; optional filter on the old base colour)"""
    from panda3d.core import MaterialAttrib, Material
    for gnp in np_.find_all_matches("**/+GeomNode") if np_.node().get_type().get_name() != "GeomNode" else [np_]:
        gn = gnp.node()
        for i in range(gn.get_num_geoms()):
            st = gn.get_geom_state(i); ma = st.get_attrib(MaterialAttrib)
            old = ma.get_material() if ma is not None and ma.get_material() is not None else None
            b = old.get_base_color() if old is not None and old.has_base_color() else (1, 1, 1, 1)
            if only is not None and not only(b): continue
            mt = Material(old) if old is not None else Material("ped")
            mt.set_base_color((c[0], c[1], c[2], 1)); gn.set_geom_state(i, st.set_attrib(MaterialAttrib.make(mt)))
    np_.set_shader_input("tint", (1, 1, 1, 1))


class Ped(Person):
    """sidewalk walker: loops around a block, flees from danger, can speak ambient lines."""
    def __init__(self, game, loop, idx):
        self.loop = loop; self.seg = idx % len(loop); self.t = random.random()
        a = loop[self.seg]; b = loop[(self.seg + 1) % len(loop)]
        x = a[0] + (b[0] - a[0]) * self.t; y = a[1] + (b[1] - a[1]) * self.t
        # v1.0.4: a mix of women and men; neither may look like ANA or DANIEL (see the ped styling in build_model)
        Person.__init__(self, game, "daniel" if random.random() < 0.45 else "ana", x, y, 0.0, ped=True)
        self.speed = random.uniform(1.1, 1.6); self.flee = 0.0; self.dir = 1 if random.random() < 0.5 else -1
        self.talk_cd = random.uniform(2, 10)
        self.offset = random.uniform(-0.8, 0.8)

    def update(self, dt, threat):
        if self.update_knock(dt):
            self.sync(); return
        if threat is not None and self.flee <= 0:
            self.flee = 3.0; self.flee_from = threat
        if self.flee > 0:
            self.flee -= dt
            tx, ty = self.flee_from
            dx, dy = self.x - tx, self.y - ty; d = math.hypot(dx, dy) or 1
            vx, vy = dx / d * 5.0, dy / d * 5.0; sp = 5.0
        else:
            a = self.loop[self.seg]; b = self.loop[(self.seg + self.dir) % len(self.loop)]
            dx, dy = b[0] - self.x, b[1] - self.y; d = math.hypot(dx, dy)
            if d < 1.0:
                self.seg = (self.seg + self.dir) % len(self.loop); d = 1
            vx, vy = dx / d * self.speed, dy / d * self.speed; sp = self.speed
        self.x += vx * dt; self.y += vy * dt
        px, py, nx, ny, tag = self.g.world.grid.push_circle(self.x, self.y, 0.35)
        self.x += px; self.y += py
        if sp > 0.1:
            th = math.degrees(math.atan2(-vx, vy))
            dh = (th - self.h + 180) % 360 - 180
            self.h += dh * min(1, dt * 8)
        self.walk_anim(dt, sp); self.sync()
