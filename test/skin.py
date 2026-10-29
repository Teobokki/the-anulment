import traceback, math
from panda3d.core import Filename
OUT = "/workspace/an_shots/"
def shot(n):
    app.graphicsEngine.render_frame(); app.graphicsEngine.render_frame(); app.win.save_screenshot(Filename(OUT + n + ".png")); print("SHOT", n, flush=True)
plan = []
def s0(): app.new_game(True)
def s1():
    g = app.game; g.end_cut(); g.cut = {"shots": [(0, "x", None, ("", ""), None)], "t": 0, "i": 0, "next": 99, "end": 999, "which": "test"}
    g.update_cut = lambda dt: None
    for k, p in enumerate(g.near[:4]): print("near", k, p.who, p.x, p.y, flush=True)
def s2():
    g = app.game; p = g.near[0]; q = g.near[1]
    for k, pp in enumerate(g.near[:3]):
        pp.x, pp.y, pp.h = -1.2 + k * 1.2, -20.0, 180; pp.sync()
    cam = app.camera; cam.set_pos(0, -24.2, 1.6); cam.look_at(0, -20, 1.3); app.camLens.set_fov(45)
    shot("skin_close")
def s3():
    cam = app.camera; cam.set_pos(0, -60, 4.0); cam.look_at(0, -20, 1.2); app.camLens.set_fov(40); shot("skin_far")
    app.userExit()
seq = [(1, s0), (8, s1), (3, s2), (2, s3)]
def chain(k):
    if k >= len(seq): return
    d, f = seq[k]
    def run(t):
        try: f()
        except Exception: traceback.print_exc()
        chain(k + 1); return t.done
    app.do_method_later(d, run, "sk%d" % k)
chain(0)
