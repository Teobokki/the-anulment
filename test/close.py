import traceback, os, random, sys
from panda3d.core import Filename
import an_people as AP
OUT = os.environ.get("CLOSE_OUT", "/workspace/an_shots/close/"); os.makedirs(OUT, exist_ok=True)
def shot(n):
    app.campos.set_element(0, app.camera.get_pos(app.render)); app.graphicsEngine.render_frame(); app.graphicsEngine.render_frame()
    app.win.save_screenshot(Filename(OUT + n + ".png")); print("SHOT", n, flush=True)
def s0(): app.new_game(True)
def s1():
    try:
        g = app.game; g.end_cut(); g.cut = {"shots": [(0, "x", None, ("", ""), None)], "t": 0, "i": 0, "next": 99, "end": 9e9, "which": "test"}
        g.update_cut = lambda dt: None; g.hud.hide(); g.mm_root.hide()
        for n in g.btn_nodes: n.hide()
        print("LENS near/far", app.camLens.get_near(), app.camLens.get_far(), "depth bits", app.win.get_fb_properties().get_depth_bits(), flush=True)
        X, Y = 420.0, -150.0
        # far-crowd (LOD) figures exactly like the user's screenshot: a pair, seen from behind
        for j, seed in enumerate((0, 5)):
            rnd = random.Random(seed); xx = X - 0.35 + 0.7 * j
            AP.crowd_lod(g, (xx, Y, xx + 0.001, Y + 0.001), 1, rnd, face=(xx, Y + 50))
        # full characters side by side (protesters on both bodies, white tops)
        a = AP.make_protester(g, X + 4, Y, 0, random.Random(1)); d = AP.make_protester(g, X + 5, Y, 0, random.Random(2))
        for p in (a, d): AP.style(p, (0.85, 0.85, 0.86), (0.15, 0.15, 0.16), (0.03, 0.024, 0.021)); p.h = 0; p.sync()
        for u in a.model.find_all_matches("**/tank.under"):
            print("UNDER", u, u.get_net_state(), "use_tex", u.get_shader_input("use_tex"), flush=True)
            print("UNDERGEOM", u.node().get_geom_state(0), flush=True)
        if os.environ.get("HIDE_UNDER"):
            for p_ in (a, d): p_.model.find_all_matches("**/tank.under").hide()
        lens = app.camLens; lens.set_fov(55)
        cam = app.camera
        for nm, px in (("lod", X), ("full", X + 4.5)):
            cam.set_pos(px - 0.2, Y - 1.5, 1.75); cam.look_at(px, Y, 1.35); shot(nm + "_back")
            cam.set_pos(px - 2.0, Y + 0.1, 1.6); cam.look_at(px, Y, 1.3); shot(nm + "_side")
            cam.set_pos(px + 0.2, Y + 1.8, 1.6); cam.look_at(px, Y, 1.3); shot(nm + "_front")
    except Exception: traceback.print_exc()
    app.userExit()
seq = [(1, s0), (8, s1)]
def chain(k):
    if k >= len(seq): return
    d, f = seq[k]
    def run(t):
        try: f()
        except Exception: traceback.print_exc()
        chain(k + 1); return t.done
    app.do_method_later(d, run, "sh%d" % k)
chain(0)
