import traceback, random
from panda3d.core import Filename, Vec3
from fs_people import Ped, Person
OUT = "/workspace/an_shots/sheet/"
def shot(n):
    app.campos.set_element(0, app.camera.get_pos(app.render)); app.graphicsEngine.render_frame(); app.graphicsEngine.render_frame(); app.win.save_screenshot(Filename(OUT + n + ".png"))
def s0(): app.new_game(True)
def s1():
    g = app.game; g.end_cut(); g.cut = {"shots": [(0, "x", None, ("", ""), None)], "t": 0, "i": 0, "next": 99, "end": 9e9, "which": "test"}
    g.update_cut = lambda dt: None; g.hud.hide(); g.mm_root.hide()
    p = Person(g, "daniel", 320, -150, 0); p.sync()
    cam = app.camera; cam.set_pos(320, -150 + 1.2, 1.6); cam.look_at(320, -150, 1.55); app.camLens.set_fov(40)
    shot("f_plain")
    sk = p.model.find("**/skin")
    print("SKIN", sk, [ (c.get_name()) for c in p.model.find_all_matches("**/+GeomNode")])
    print("TEX", sk.find_all_textures(), sk.get_texture())
    sk.set_shader_input("use_nmap", 0.0, 20); shot("f_nonmap")
    sk.set_shader_input("gloss", 0.0, 20); shot("f_nogloss")
    sk.set_shader_input("use_tex", 0.0, 20); shot("f_notex")
    for c in p.model.find_all_matches("**/+GeomNode"):
        if c.get_name() != "skin": c.hide()
    shot("f_only")
    sk.set_shader_off(30); sk.set_texture_off(30); sk.set_light_off(30); shot("f_noshader")
    from panda3d.core import RenderModeAttrib
    sk.set_render_mode_wireframe(30); shot("f_wire")
    cam.set_pos(321.2, -150 + 0.2, 1.6); cam.look_at(320, -150, 1.55); shot("f_side")
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
