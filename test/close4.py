import traceback, os, math
from panda3d.core import Filename
import an_people as AP
OUT = os.environ.get("CLOSE_OUT", "/workspace/an_shots/close4/"); os.makedirs(OUT, exist_ok=True)
def shot(n):
    app.campos.set_element(0, app.camera.get_pos(app.render)); app.graphicsEngine.render_frame(); app.graphicsEngine.render_frame()
    app.win.save_screenshot(Filename(OUT + n + ".png")); print("SHOT", n, flush=True)
def s0(): app.new_game(True)
def s1():
    try:
        g = app.game; g.end_cut(); g.cut = {"shots": [(0, "x", None, ("", ""), None)], "t": 0, "i": 0, "next": 99, "end": 9e9, "which": "test"}
        g.update_cut = lambda dt: None; g.hud.hide(); g.mm_root.hide()
        for n in g.btn_nodes: n.hide()
        me = g.me(); me.x, me.y = 4.0, -22.0; me.sync()
        cs = g.crowd_sys; cs.update(0, force=True); act = cs.active()
        print("ACTIVE", len(act), "slots", len(cs.slots), flush=True)
        import numpy as np
        d = sorted(act, key=lambda p: math.hypot(p.x - me.x, p.y - me.y))
        print("nearest full actor dists", [round(math.hypot(p.x - me.x, p.y - me.y), 1) for p in d[:3]], "farthest full", round(math.hypot(d[-1].x - me.x, d[-1].y - me.y), 1), flush=True)
        # radius covered by full actors: the nearest card
        dc = [math.hypot(s[0] - me.x, s[1] - me.y) for i, s in enumerate(cs.slots) if cs.actor_at.get(i) is None]
        print("nearest impostor card at %.1f m" % min(dc), flush=True)
        me.np.hide()
        a = next(p for p in d if p.who == "ana"); b = next(p for p in d if p.who == "daniel")
        # stand the pair side by side like the user's screenshot
        b.x, b.y, b.h = a.x + 0.75, a.y, a.h; b._gz = None; b.sync()
        cx, cy = a.x + 0.37, a.y; h = math.radians(a.h); fx, fy = -math.sin(h), math.cos(h)
        cam = app.camera; app.camLens.set_fov(55)
        cam.set_pos(cx - fx * 1.6, cy - fy * 1.6, 1.75); cam.look_at(cx, cy, 1.3); shot("pair_back")
        cam.set_pos(cx - fx * 1.0 + fy * 1.2, cy - fy * 1.0 - fx * 1.2, 1.6); cam.look_at(cx, cy, 1.3); shot("pair_back34")
        cam.set_pos(cx + fy * 2.2, cy - fx * 2.2, 1.6); cam.look_at(cx, cy, 1.3); shot("pair_side")
        cam.set_pos(cx + fx * 1.8, cy + fy * 1.8, 1.6); cam.look_at(cx, cy, 1.3); shot("pair_front")
        cam.set_pos(a.x - fx * 0.9, a.y - fy * 0.9, 1.65); cam.look_at(a.x, a.y, 1.45); shot("ana_back_1m")
        cam.set_pos(b.x - fx * 0.9, b.y - fy * 0.9, 1.65); cam.look_at(b.x, b.y, 1.45); shot("daniel_back_1m")
        app.camLens.set_fov(60); cam.set_pos(me.x, me.y - 3, 1.8); cam.look_at(me.x + 2, me.y + 15, 1.2); shot("crowd_in")
        cam.set_pos(0, -60, 4.0); cam.look_at(0, -15, 1.0); shot("crowd_far")
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
