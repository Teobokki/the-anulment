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


def style(p, top, bottom, hair, tone=None, slim=1.0, scale=1.0, morph=None, sleeves=False):
    m = p.model
    if sleeves:     # long sleeves: upper + lower arms take the top's colour
        for n in list(m.find_all_matches('**/arm*')) + list(m.find_all_matches('**/fore*')):
            if not n.is_empty(): n.set_texture_off(2); n.set_shader_input('use_tex', 0.0); recolor(n, top)
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
    if not hr.is_empty(): hr.set_shader_input("tint", tuple(hair) + (1,))
    if tone:
        for n in [m.find("**/skin")] + list(m.find_all_matches("**/arm*")) + list(m.find_all_matches("**/fore*")) + \
                 list(m.find_all_matches("**/fingers*")) + list(m.find_all_matches("**/fist*")):
            if not n.is_empty() and "sleeve" not in n.get_name(): n.set_shader_input("tint", tone)
    m.set_scale(slim * scale, slim * scale, scale)
    if morph:
        m.set_shader_input("morph", morph, 3); m.set_shader_input("morph_on", 1.0, 3)


def add_blob(p, name, blobs, col, gloss=0.2):
    n = _att(p.model, blob_mesh(name, blobs, col)); n.set_shader_off(2); n.set_color_scale(col[0] * 1.6, col[1] * 1.6, col[2] * 1.6, 1); return n


def make_miyo(game, x, y, h):
    """MIYOYAZU: slim young man (mid-20s), grey hoodie with the hood down, dark jeans, trainers, short dark hair"""
    p = Person(game, "daniel", x, y, h)
    style(p, (0.2, 0.205, 0.215), (0.06, 0.08, 0.14), (0.45, 0.4, 0.38), slim=0.93, morph=(0.97, 0.98, 1.0, 0.95), sleeves=True)
    add_blob(p, "hood", [(0, 0.075, 1.43, 0.15, 0.075, 0.06), (0, 0.095, 1.37, 0.13, 0.06, 0.06)], (0.17, 0.175, 0.185, 1))   # hood down
    add_blob(p, "pocket", [(0, -0.13, 1.0, 0.13, 0.035, 0.06)], (0.16, 0.165, 0.175, 1))
    return p


def make_cln(game, x, y, h):
    """CLN: older, dignified family man - grey hair, dark coat"""
    p = Person(game, "daniel", x, y, h)
    style(p, (0.13, 0.14, 0.13), (0.12, 0.12, 0.13), (2.6, 2.6, 2.7), tone=(1.02, 0.98, 0.95, 1), morph=(1.04, 1.02, 1.0, 1.07), sleeves=True)
    add_blob(p, "collar", [(0, -0.02, 1.42, 0.16, 0.12, 0.05)], (0.85, 0.85, 0.88, 1))
    return p


def make_family(game, kind, x, y, h):
    if kind == "wife":
        p = Person(game, "ana", x, y, h); style(p, (0.42, 0.12, 0.16), (0.12, 0.12, 0.14), (1.4, 1.0, 0.7), morph=(1.02, 1.0, 1.0, 1.0))
    else:
        p = Person(game, "daniel" if kind == "son" else "ana", x, y, h)
        style(p, (0.2, 0.35, 0.6) if kind == "son" else (0.8, 0.6, 0.2), (0.15, 0.17, 0.25), (0.8, 0.6, 0.45), scale=0.7, morph=(1.08, 1.04, 1.0, 0.92))
    return p


def make_cop(game, x, y, h, female=None, riot=False, rnd=None):
    """fictional POLIȚIA VALDOREI officer: invented navy uniform, invented hi-vis band, peaked cap or riot helmet, invented badge"""
    rnd = rnd or random
    female = (rnd.random() < 0.4) if female is None else female
    p = Person(game, "ana" if female else "daniel", x, y, h)
    k = rnd.uniform(-1, 1)
    style(p, (0.06, 0.09, 0.2), (0.05, 0.07, 0.15), (0.6 + 0.4 * rnd.random(),) * 3, tone=(1 + 0.04 * k, 1 + 0.03 * k, 1 + 0.03 * k, 1),
          morph=(rnd.uniform(0.96, 1.06), rnd.uniform(0.97, 1.04), rnd.uniform(0.98, 1.03), rnd.uniform(0.95, 1.08)), sleeves=True)
    z0 = 1.16 if not female else 1.13
    band = MB("hiviz"); r = 0.19 if not female else 0.17
    for a in range(16):
        a0, a1 = a / 16 * 6.283, (a + 1) / 16 * 6.283
        P = lambda aa, z: (math.cos(aa) * r * 1.05, math.sin(aa) * r * 0.75 - 0.04, z)
        band.quad(P(a0, z0), P(a1, z0), P(a1, z0 + 0.06), P(a0, z0 + 0.06), (0.85, 1.0, 0.15, 1))
    b = _att(p.model, band.node()); b.set_shader_off(1); b.set_light_off(1); b.set_two_sided(True); b.set_color_scale(0.8, 0.8, 0.8, 1)
    hz = 1.68 if not female else 1.66
    if riot:
        add_blob(p, "helmet", [(0, 0.02, hz - 0.04, 0.135, 0.15, 0.13)], (0.08, 0.1, 0.16, 1), 0.7)
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
          rnd.choice([(0.1, 0.12, 0.2), (0.15, 0.15, 0.16), (0.3, 0.28, 0.24)]), rnd.choice([(0.5, 0.45, 0.4), (1.4, 1.0, 0.7), (2.4, 2.4, 2.5), (0.9, 0.6, 0.4)]),
          tone=(1 + 0.04 * k, 1 + 0.035 * k, 1 + 0.04 * k, 1), morph=(rnd.uniform(0.95, 1.07), rnd.uniform(0.97, 1.04), rnd.uniform(0.97, 1.03), rnd.uniform(0.94, 1.08)))
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
def crowd_lod(game, rect, n, rnd, avoid=None, face=None):
    """far crowd: n decimated characters, coloured per part, flattened into a single static node (one draw call per state)"""
    app = game.app; root = NodePath("crowd")
    for k in ("daniel", "heroine"):
        if k not in _lod:
            _lod[k] = app.loader.load_model(Filename.from_os_specific(os.path.join(app.BASE, "assets", "models", "lod_%s.bam" % k)))
            _lod[k].clear_texture(); _lod[k].set_texture_off(1)
    x0, y0, x1, y1 = rect; cnt = 0; tries = 0
    pl = game.world.T("placards.png", repeat=False)
    signs = NodePath("signs")
    while cnt < n and tries < n * 6:
        tries += 1
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if avoid and any(a[0] <= x <= a[2] and a[1] <= y <= a[3] for a in avoid): continue
        m = _lod[rnd.choice(("daniel", "heroine"))].copy_to(root)
        h = (math.degrees(math.atan2(-(face[0] - x), face[1] - y)) if face else rnd.uniform(0, 360)) + rnd.uniform(-25, 25) + 180
        m.set_pos(x, y, game.world.ground_z(x, y)); m.set_h(h); s = rnd.uniform(0.92, 1.05); m.set_scale(s)
        dk = 0.55
        tone = rnd.choice([(0.85, 0.66, 0.55), (0.78, 0.6, 0.48), (0.9, 0.72, 0.62), (0.7, 0.52, 0.42)])
        top = rnd.choice([(0.35, 0.12, 0.12), (0.15, 0.2, 0.35), (0.3, 0.3, 0.32), (0.45, 0.38, 0.25), (0.12, 0.25, 0.18), (0.6, 0.55, 0.5), (0.08, 0.08, 0.09)])
        bot = rnd.choice([(0.1, 0.12, 0.2), (0.15, 0.15, 0.16), (0.3, 0.28, 0.24)]); hair = rnd.choice([(0.08, 0.06, 0.05), (0.3, 0.2, 0.12), (0.55, 0.55, 0.56), (0.15, 0.1, 0.07)])
        for c in m.find_all_matches("**/+GeomNode"):
            nm = c.get_name()
            col = hair if "hair" in nm else top if ("tank" in nm or "sleeve" in nm or "belt" in nm) else bot if ("trouser" in nm or "leg" in nm) else tone
            c.set_color(col[0] * dk, col[1] * dk, col[2] * dk, 1, 1)
        if rnd.random() < 0.18:      # placard over the heads
            cm = CardMaker("pl"); i = rnd.randrange(4); cm.set_frame(-0.32, 0.32, 1.75, 2.3); cm.set_uv_range((i / 4.0, 0), ((i + 1) / 4.0, 1))
            q = signs.attach_new_node(cm.generate()); q.set_pos(x, y, 0); q.set_h(h + 180)
        elif rnd.random() < 0.15:    # phone light / candle
            mb = MB("l"); mb.box(-0.03, -0.03, 1.45, 0.03, 0.03, 1.55, (1.5, 1.45, 1.3, 1) if rnd.random() < 0.6 else (1.8, 1.2, 0.5, 1))
            q = mb.node(); q.reparent_to(root); q.set_pos(x, y, 0); q.set_h(h)
        cnt += 1
    root.set_light_off(1); root.set_shader_off(1); root.flatten_strong()
    signs.set_texture(pl); signs.set_two_sided(True); signs.set_light_off(1); signs.set_shader_off(1); signs.set_color_scale(0.55, 0.55, 0.55, 1); signs.flatten_strong()
    signs.reparent_to(root)
    root.reparent_to(game.world.root)
    return root
