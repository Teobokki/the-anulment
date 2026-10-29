"""THE ANULMENT characters: everyone uses the THE ANULMENT character pipeline (ANA / DANIEL meshes, the SAME skin_c / skin_n
textures and skin shading), restyled per role. Far crowds use decimated copies flattened into one node (LOD)."""
import math, random, os
from panda3d.core import NodePath, CardMaker, TransparencyAttrib, Filename, TextNode
import fs_shaders
from fs_people import Person, recolor
from fs_miyo import blob_mesh
from fs_geom import MB


def _att(parent, n):
    from panda3d.core import NodePath
    if isinstance(n, NodePath): n.reparent_to(parent); return n
    return parent.attach_new_node(n)

# natural skin-tone variety: separate copies of the SAME Ana / Daniel skin textures (texture data, no shader tint on the skin)
TONES = [("", (1.0, 1.0, 1.0)), ("_t1", (0.88, 0.80, 0.70)), ("_t2", (0.66, 0.53, 0.43)), ("_t3", (0.48, 0.37, 0.30))]


def skin_tex_name(who, k):
    return ("skin_c_daniel" if who == "daniel" else "skin_c") + TONES[k][0] + ".png"


def skin_tone(p, k, arms=True):
    """give a full character one of the natural skin tones; the skin keeps Ana / Daniel's realistic skin shading, untinted"""
    from fs_people import tex, HAND_TINT
    app = p.app; m = p.model; t = tex(app, skin_tex_name(p.who, k)); f = TONES[k][1]
    nodes = [m.find("**/skin")] + ((list(m.find_all_matches("**/arm*/**/+GeomNode")) + list(m.find_all_matches("**/fore*/**/+GeomNode"))) if arms else [])
    for n in nodes:
        if n.is_empty(): continue
        nm = str(n)
        if "sleeve" in nm or "fingers" in nm or "fist" in nm or "tank" in nm: continue
        n.set_texture(t, 3); n.set_shader_input("tint", (1, 1, 1, 1), 3)
    hb = HAND_TINT if p.who != "daniel" else (1, 1, 1, 1)
    for n in list(m.find_all_matches("**/fingers*")) + list(m.find_all_matches("**/fist*")):   # untextured hands match the skin
        n.set_shader_input("tint", (hb[0] * f[0], hb[1] * f[1], hb[2] * f[2], 1), 3)
    p.skin_k = k


def style(p, top, bottom, hair, tone=None, slim=1.0, scale=1.0, morph=None, sleeves=False):
    m = p.model
    if sleeves:     # long sleeves: upper + lower arms take the top's colour
        for n in list(m.find_all_matches('**/arm*')) + list(m.find_all_matches('**/fore*')):
            if n.is_empty(): continue
            for g in ([n] if n.node().is_geom_node() else []) + list(n.find_all_matches("**/+GeomNode")):
                gnm = g.get_name()
                if "fingers" in gnm or "fist" in gnm: continue      # v1.0.0.2: hands stay skin (they were painted sleeve-grey)
                g.set_texture_off(2); g.set_shader_input('use_tex', 0.0); recolor(g, top)
    for n in [m.find("**/tank")] + list(m.find_all_matches("**/sleeve*")) + list(m.find_all_matches("**/tank.*")):
        if not n.is_empty(): n.set_texture_off(2); n.set_shader_input("use_tex", 0.0); recolor(n, top)
    st = m.find("**/straps")
    if not st.is_empty(): recolor(st, top)
    ch = m.find("**/choker")
    if not ch.is_empty(): ch.remove_node()
    tr = m.find("**/trousers")
    if not tr.is_empty():
        from panda3d.core import MaterialAttrib
        g0 = tr if tr.node().get_type().get_name() == "GeomNode" else tr.find("**/+GeomNode")
        ma = g0.node().get_geom_state(0).get_attrib(MaterialAttrib)
        ob = ma.get_material().get_base_color() if ma is not None else (0.6, 0.07, 0.06, 1)
        recolor(tr, bottom)
        for lg in (p.legL, p.legR):
            if not lg.is_empty(): recolor(lg, bottom, only=lambda b, ob=ob: abs(b[0] - ob[0]) + abs(b[1] - ob[1]) + abs(b[2] - ob[2]) < 0.06)
    hr = m.find("**/hair")
    if not hr.is_empty():
        import an_hair      # v1.0.0.2: real hair colour on the strands + scalp shell (tint computed per model)
        hr.set_shader_input("tint", an_hair.hair_tint(p.who, hair))
    if tone:
        for n in [m.find("**/skin")] + list(m.find_all_matches("**/arm*")) + list(m.find_all_matches("**/fore*")) + \
                 list(m.find_all_matches("**/fingers*")) + list(m.find_all_matches("**/fist*")):
            if not n.is_empty() and "sleeve" not in n.get_name(): n.set_shader_input("tint", tone)
    m.set_scale(slim * scale, slim * scale, scale)
    if morph:
        m.set_shader_input("morph", morph, 3); m.set_shader_input("morph_on", 1.0, 3)


def add_blob(p, name, blobs, col, gloss=0.2):
    """v1.0.0.2: hood / collar / cap / helmet pieces get the same lit cloth shading as the clothes (they were flat unlit
    shapes: a black disc behind MIYOYAZU's neck, a glowing white disc on CLN, a black ball over the riot police faces)"""
    from panda3d.core import Material
    n = _att(p.model, blob_mesh(name, blobs, col))
    mt = Material(name); mt.set_base_color((1, 1, 1, 1)); mt.set_roughness(0.7); mt.set_metallic(0.0); n.set_material(mt, 3)
    fs_shaders.apply(n, p.app, gloss=gloss, sheen=0.5); n.set_texture_off(3)
    return n


def make_miyo(game, x, y, h):
    """MIYOYAZU: slim young man (mid-20s), grey hoodie with the hood down, dark jeans, trainers, short dark hair"""
    p = Person(game, "daniel", x, y, h)
    style(p, (0.2, 0.205, 0.215), (0.06, 0.08, 0.14), (0.035, 0.026, 0.022), slim=0.93, morph=(0.97, 0.98, 1.0, 0.95), sleeves=True)
    add_blob(p, "hood", [(0, 0.075, 1.43, 0.15, 0.075, 0.06), (0, 0.095, 1.37, 0.13, 0.06, 0.06)], (0.17, 0.175, 0.185, 1))   # hood down
    add_blob(p, "pocket", [(0, -0.13, 1.0, 0.13, 0.035, 0.06)], (0.16, 0.165, 0.175, 1))
    return p


def make_cln(game, x, y, h):
    """CLN: older, dignified family man - grey hair, dark coat"""
    p = Person(game, "daniel", x, y, h)
    style(p, (0.13, 0.14, 0.13), (0.12, 0.12, 0.13), (0.40, 0.39, 0.38), morph=(1.04, 1.02, 1.0, 1.07), sleeves=True)
    add_blob(p, "collar", [(0, 0.035, 1.44, 0.105, 0.06, 0.035)], (0.12, 0.13, 0.12, 1))      # coat collar (behind the neck)
    return p


def make_family(game, kind, x, y, h):
    if kind == "wife":
        p = Person(game, "ana", x, y, h); style(p, (0.42, 0.12, 0.16), (0.12, 0.12, 0.14), (0.14, 0.085, 0.05), morph=(1.02, 1.0, 1.0, 1.0))
    else:
        p = Person(game, "daniel" if kind == "son" else "ana", x, y, h)
        style(p, (0.2, 0.35, 0.6) if kind == "son" else (0.8, 0.6, 0.2), (0.15, 0.17, 0.25), (0.07, 0.045, 0.03), scale=0.7, morph=(1.08, 1.04, 1.0, 0.92))
    return p


def make_cop(game, x, y, h, female=None, riot=False, rnd=None):
    """fictional POLIȚIA VALDOREI officer: invented navy uniform, invented hi-vis band, peaked cap or riot helmet, invented badge"""
    rnd = rnd or random
    female = (rnd.random() < 0.4) if female is None else female
    p = Person(game, "ana" if female else "daniel", x, y, h)
    k = rnd.uniform(-1, 1)
    style(p, (0.06, 0.09, 0.2), (0.05, 0.07, 0.15), rnd.choice(__import__("an_hair").NATURAL_HAIR[:4]),
          morph=(rnd.uniform(0.96, 1.06), rnd.uniform(0.97, 1.04), rnd.uniform(0.98, 1.03), rnd.uniform(0.95, 1.08)), sleeves=True)
    skin_tone(p, rnd.choice((0, 0, 1, 1, 2, 3)), arms=False)
    z0 = 1.16 if not female else 1.13
    band = MB("hiviz"); r = 0.19 if not female else 0.17
    for a in range(16):
        a0, a1 = a / 16 * 6.283, (a + 1) / 16 * 6.283
        P = lambda aa, z: (math.cos(aa) * r * 1.05, math.sin(aa) * r * 0.75 - 0.04, z)
        band.quad(P(a0, z0), P(a1, z0), P(a1, z0 + 0.06), P(a0, z0 + 0.06), (0.85, 1.0, 0.15, 1))
    b = _att(p.model, band.node()); b.set_shader_off(1); b.set_light_off(1); b.set_two_sided(True); b.set_color_scale(0.8, 0.8, 0.8, 1)
    hz = 1.68 if not female else 1.66
    if riot:
        add_blob(p, "helmet", [(0, 0.035, hz - 0.015, 0.128, 0.135, 0.105), (0, 0.06, hz - 0.075, 0.115, 0.09, 0.05)], (0.08, 0.1, 0.16, 1), 0.7)   # shell above the brow + neck guard
        sh = MB("shield"); sh.box(-0.3, -0.33, 0.35, 0.3, -0.31, 1.45, (0.7, 0.8, 0.9, 1))
        s = _att(p.model, sh.node()); s.set_transparency(TransparencyAttrib.M_alpha); s.set_alpha_scale(0.45); s.set_shader_off(1)
        s.set_light_off(1); s.set_color_scale(0.6, 0.65, 0.75, 0.45); s.set_bin("transparent", 10); s.set_depth_write(False)
        tn = TextNode("st"); tn.set_text("POLIȚIA"); tn.set_align(TextNode.A_center); tn.set_text_color(1, 1, 1, 0.9)
        t = s.attach_new_node(tn); t.set_pos(0, -0.335, 1.15); t.set_scale(0.1); t.set_h(180)
    else:
        add_blob(p, "cap", [(0, 0.01, hz - 0.02, 0.12, 0.125, 0.05), (0, -0.09, hz - 0.055, 0.1, 0.07, 0.012)], (0.05, 0.07, 0.14, 1), 0.4)
    cm = CardMaker("badge"); cm.set_frame(-0.035, 0.035, -0.035, 0.035)
    bd = p.model.attach_new_node(cm.generate()); bd.set_pos(0.08, -0.12 if not female else -0.14, 1.32); bd.set_h(180)
    bd.set_texture(game.world.T("police_badge.png", repeat=False)); bd.set_transparency(TransparencyAttrib.M_alpha); bd.set_shader_off(1); bd.set_light_off(1)
    p.is_cop = True
    return p


def make_protester(game, x, y, h, rnd):
    female = rnd.random() < 0.5
    p = Person(game, "ana" if female else "daniel", x, y, h)
    k = rnd.uniform(-1, 1)
    style(p, rnd.choice([(0.35, 0.12, 0.12), (0.15, 0.2, 0.35), (0.3, 0.3, 0.32), (0.45, 0.38, 0.25), (0.12, 0.25, 0.18), (0.6, 0.55, 0.5)]),
          rnd.choice([(0.1, 0.12, 0.2), (0.15, 0.15, 0.16), (0.3, 0.28, 0.24)]), rnd.choice(__import__("an_hair").EVERYDAY_HAIR),
          morph=(rnd.uniform(0.95, 1.07), rnd.uniform(0.97, 1.04), rnd.uniform(0.97, 1.03), rnd.uniform(0.94, 1.08)))
    skin_tone(p, rnd.choice((0, 0, 1, 1, 2, 3)))
    p.prop_kind = rnd.choice(["placard", "placard", "flag", "phone", "candle"])
    hand = p.handR if not p.handR.is_empty() else p.model
    if p.prop_kind in ("placard", "flag"):
        mb = MB("stick"); mb.box(-0.012, -0.012, -0.1, 0.012, 0.012, 1.1, (0.35, 0.25, 0.15, 1))
        st = _att(hand, mb.node()); st.set_shader_off(1)
        cm = CardMaker("pl")
        if p.prop_kind == "placard":
            i = rnd.randrange(4); cm.set_frame(-0.32, 0.32, 0.75, 1.35); cm.set_uv_range((i / 4.0, 0), ((i + 1) / 4.0, 1))
            tex = game.world.T("placards.png", repeat=False)
        else:
            cm.set_frame(0, 0.75, 0.75, 1.25); tex = game.world.T("flag.jpg", repeat=False)
        c = st.attach_new_node(cm.generate()); c.set_texture(tex); c.set_two_sided(True); c.set_shader_off(1); c.set_light_off(1); c.set_color_scale(0.62, 0.62, 0.62, 1)
    else:
        mb = MB("light")
        if p.prop_kind == "phone": mb.box(-0.03, -0.006, -0.02, 0.03, 0.006, 0.1, (1.6, 1.6, 1.5, 1))
        else: mb.box(-0.018, -0.018, -0.02, 0.018, 0.018, 0.1, (0.95, 0.9, 0.85, 1)); mb.box(-0.008, -0.008, 0.1, 0.008, 0.008, 0.14, (2.0, 1.4, 0.5, 1))
        n = _att(hand, mb.node()); n.set_shader_off(1); n.set_light_off(1)
    p.beat = rnd.uniform(0, 6.28)
    return p


_lod = {}


def _tuck_skin(m):
    """the decimated body skin sits under the decimated clothes: pull it in below the neck so it never pokes through"""
    from panda3d.core import GeomVertexRewriter
    g = m.find("**/skin")
    if g.is_empty(): return
    if g.node().get_type().get_name() != "GeomNode": g = g.find("**/+GeomNode")
    gn = g.node()
    for i in range(gn.get_num_geoms()):
        vd = gn.modify_geom(i).modify_vertex_data(); rw = GeomVertexRewriter(vd, "vertex")
        while not rw.is_at_end():
            v = rw.get_data3()
            if v[2] < 1.36: rw.set_data3(v[0] * 0.86, v[1] * 0.86 + 0.0, v[2])
            else: rw.set_data3(v)
SKIN_AVG = {"ana": (0.725, 0.518, 0.406), "daniel": (0.707, 0.544, 0.459)}     # mean of skin_c / skin_c_daniel


def _lod_hair(m, kind):
    """v1.0.0.2: the decimated strand hair broke into spikes at a distance -> simple opaque hair shapes instead"""
    from fs_people import fix_uv
    fix_uv(m)       # UVs in the default column, so the skin texture works under the character shader
    for h in m.find_all_matches("**/hair"): h.remove_node()
    if kind == "daniel":
        bl = [(0.0, 0.035, 1.635, 0.098, 0.103, 0.072)]
    else:
        bl = [(0.0, 0.035, 1.635, 0.103, 0.104, 0.07), (0.0, 0.06, 1.55, 0.108, 0.075, 0.09)]
    _att(m, blob_mesh("hair", bl, (1, 1, 1, 1)))


# the LOD meshes keep Ana / Daniel's UVs in the glTF column 'texcoord.0'; the default stage reads 'texcoord'
from panda3d.core import TextureStage, InternalName
_SKIN_TS = TextureStage("skin_lod"); _SKIN_TS.set_texcoord_name(InternalName.get_texcoord_name("0"))
def crowd_lod(game, rect, n, rnd, avoid=None, face=None):
    """far crowd: n decimated characters, coloured per part, flattened into a single static node (one draw call per state)"""
    app = game.app; root = NodePath("crowd"); skinroot = NodePath("crowd_skin")
    for k in ("daniel", "heroine"):
        if k not in _lod:
            _lod[k] = app.loader.load_model(Filename.from_os_specific(os.path.join(app.BASE, "assets", "models", "lod_%s.bam" % k)))
            _lod[k].clear_texture(); _tuck_skin(_lod[k]); _lod_hair(_lod[k], k)
    x0, y0, x1, y1 = rect; cnt = 0; tries = 0
    pl = game.world.T("placards.png", repeat=False); skt = {}
    signs = NodePath("signs"); lights = NodePath("lights")
    while cnt < n and tries < n * 6:
        tries += 1
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if avoid and any(a[0] <= x <= a[2] and a[1] <= y <= a[3] for a in avoid): continue
        kind = rnd.choice(("daniel", "heroine")); m = _lod[kind].copy_to(root)
        h = (math.degrees(math.atan2(-(face[0] - x), face[1] - y)) if face else rnd.uniform(0, 360)) + rnd.uniform(-25, 25) + 180
        m.set_pos(x, y, game.world.ground_z(x, y)); m.set_h(h); s = rnd.uniform(0.92, 1.05); m.set_scale(s)
        dk = 1.0       # v1.0.0.2: lit by the character shader now (was unlit flat colour)
        top = rnd.choice([(0.35, 0.12, 0.12), (0.15, 0.2, 0.35), (0.3, 0.3, 0.32), (0.45, 0.38, 0.25), (0.12, 0.25, 0.18), (0.6, 0.55, 0.5), (0.08, 0.08, 0.09)])
        bot = rnd.choice([(0.1, 0.12, 0.2), (0.15, 0.15, 0.16), (0.3, 0.28, 0.24)]); hair = rnd.choice(__import__("an_hair").EVERYDAY_HAIR)
        tk = rnd.choice((0, 0, 1, 1, 2, 3)); f = TONES[tk][1]; who = "daniel" if kind == "daniel" else "ana"
        for c in m.find_all_matches("**/+GeomNode"):
            nm = c.get_name(); pn = c.get_parent().get_name()
            if nm.startswith("skin"):          # textured skin, untinted (night exposure only)
                # v1.0.0.2: far figures get the skin texture's average colour (lit, no texture): the decimated meshes'
                # UVs stretched the texture into stripes along the arms
                sc = SKIN_AVG[who]; c.set_texture_off(3); c.set_color(sc[0] * f[0], sc[1] * f[1], sc[2] * f[2], 1, 3)
                continue
            if "fingers" in nm:
                c.set_texture_off(3); sc = SKIN_AVG[who]; c.set_color(sc[0] * f[0], sc[1] * f[1], sc[2] * f[2], 1, 3); continue
            col = hair if "hair" in nm else top if ("tank" in nm or "sleeve" in nm or "belt" in nm) else bot
            c.set_texture_off(3); c.set_color(col[0] * dk, col[1] * dk, col[2] * dk, 1, 3)
        if rnd.random() < 0.18:      # placard over the heads
            cm = CardMaker("pl"); i = rnd.randrange(4); cm.set_frame(-0.32, 0.32, 1.75, 2.3); cm.set_uv_range((i / 4.0, 0), ((i + 1) / 4.0, 1))
            q = signs.attach_new_node(cm.generate()); q.set_pos(x, y, 0); q.set_h(h + 180)
        elif rnd.random() < 0.15:    # phone light / candle
            mb = MB("l"); mb.box(-0.03, -0.03, 1.45, 0.03, 0.03, 1.55, (1.5, 1.45, 1.3, 1) if rnd.random() < 0.6 else (1.8, 1.2, 0.5, 1))
            q = _att(lights, mb.node()); q.set_pos(x, y, 0); q.set_h(h)
        cnt += 1
    from panda3d.core import Material
    mt = Material("crowd"); mt.set_base_color((1, 1, 1, 1)); mt.set_roughness(0.7); mt.set_metallic(0.0)
    for r_, tx in ((root, False), (skinroot, True)):
        r_.set_material(mt, 10); r_.set_light_off(1); r_.flatten_strong()
        fs_shaders.apply(r_, app, gloss=0.15, tex=tx, sheen=0.6); r_.set_two_sided(False)
    skinroot.reparent_to(root)
    lights.set_shader_off(2); lights.set_light_off(2); lights.flatten_strong(); lights.reparent_to(root)
    signs.set_texture(pl); signs.set_two_sided(True); signs.set_light_off(1); signs.set_shader_off(1); signs.set_color_scale(0.55, 0.55, 0.55, 1); signs.flatten_strong()
    signs.reparent_to(root)
    root.reparent_to(game.world.root)
    return root
