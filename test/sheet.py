import traceback, math, os, random
from panda3d.core import Filename
import an_people as AP
from fs_people import Ped
OUT = "/workspace/an_shots/sheet/"; os.makedirs(OUT, exist_ok=True)
def shot(n):
    app.campos.set_element(0, app.camera.get_pos(app.render)); app.graphicsEngine.render_frame(); app.graphicsEngine.render_frame(); app.win.save_screenshot(Filename(OUT + n + ".png"))
def s0(): app.new_game(True)
def s1():
    try:
        g = app.game; g.end_cut(); g.cut = {"shots": [(0, "x", None, ("", ""), None)], "t": 0, "i": 0, "next": 99, "end": 9e9, "which": "test"}
        g.update_cut = lambda dt: None; g.hud.hide(); g.mm_root.hide()
        for n in g.btn_nodes: n.hide()
        rnd = random.Random(3)
        L = [("MIYOYAZU", g.me()), ("CLN", AP.make_cln(g, 0, 0, 0)), ("WIFE", AP.make_family(g, "wife", 0, 0, 0)), ("SON", AP.make_family(g, "son", 0, 0, 0)),
             ("DAUGHTER", AP.make_family(g, "daughter", 0, 0, 0)), ("AIDE", g.aide)]
        prot = {}
        for p in g.near: prot.setdefault((p.who, getattr(p, "skin_k", 0)), p)
        for (who, k), p in sorted(prot.items()): L.append(("PROT %s t%d" % (who, k), p))
        cops = {}
        for p in g.cops: cops.setdefault((p.who, p.model.find("**/helmet").is_empty()), p)
        for (who, cap), p in sorted(cops.items()): L.append(("COP %s %s" % (who, "cap" if cap else "riot"), p))
        loop = random.choice(g.world.ped_loops); pe = Ped(g, loop, 0); L.append(("PED", pe))
        pe2 = Ped(g, loop, 1); L.append(("DRIVER/PED2", pe2))
        g._sheet = L; print("N", len(L), [n for n, _ in L], flush=True)
    except Exception: traceback.print_exc()
idx = [0]
def s2():
    g = app.game; L = g._sheet
    for k, (n, p) in enumerate(L):
        p.x, p.y, p.h = 320 + k * 6.0, -150.0, 0; p.flee = 0; p.sync()
        p.patrol = False
    for k, (n, p) in enumerate(L):
        cam = app.camera; cam.set_pos(p.x + 0.0, p.y + 2.3, 1.45); cam.look_at(p.x, p.y, 1.25); app.camLens.set_fov(42)
        shot("%02d" % k)
        cam.set_pos(p.x + 0.0, p.y - 2.3, 1.55); cam.look_at(p.x, p.y, 1.3); shot("%02d_back" % k)
    open(OUT + "names.txt", "w").write("\n".join(n for n, _ in L))
def s3():
    cam = app.camera; cam.set_pos(0, -46, 3.0); cam.look_at(0, -20, 1.2); app.camLens.set_fov(40); shot("crowd_far")
    cam.set_pos(-20, -30, 1.7); cam.look_at(-15, -25, 1.3); app.camLens.set_fov(45); shot("crowd_close")
    app.userExit()
seq = [(1, s0), (8, s1), (2, s2), (1, s3)]
def chain(k):
    if k >= len(seq): return
    d, f = seq[k]
    def run(t):
        try: f()
        except Exception: traceback.print_exc()
        chain(k + 1); return t.done
    app.do_method_later(d, run, "sh%d" % k)
chain(0)
