"""builds assets/tex/crowd_atlas.png: every crowd clothing variant on the FULL Ana / Daniel characters, 8 view angles"""
import traceback, os, math
import numpy as np
from PIL import Image
from panda3d.core import (FrameBufferProperties, WindowProperties, GraphicsPipe, GraphicsOutput, Texture, OrthographicLens,
                          NodePath, Camera, PNMImage)
import an_crowd as C, an_people as AP
from fs_people import Person
SS = 2
def s0(): app.new_game(True)
def s1():
    try:
        g = app.game; W, H = C.CELL[0] * SS, C.CELL[1] * SS
        fb = FrameBufferProperties(); fb.set_rgba_bits(8, 8, 8, 8); fb.set_depth_bits(24)
        buf = app.graphicsEngine.make_output(app.pipe, "imp", -2, fb, WindowProperties.size(W, H), GraphicsPipe.BF_refuse_window, app.win.get_gsg(), app.win)
        tex = Texture(); buf.add_render_texture(tex, GraphicsOutput.RTM_copy_ram); buf.set_clear_color_active(True); buf.set_clear_color((0, 0, 0, 0))
        scene = NodePath("impscene"); scene.set_shader_input("fogden", 0.0, 100)
        from panda3d.core import Vec3
        scene.set_shader_input("dayk", 0.0); scene.set_shader_input("fogday", Vec3(0.68, 0.79, 0.90)); scene.set_shader_input("sundir", Vec3(0.35, -0.45, 0.82))
        scene.set_shader_input("envday", app.envday)
        lens = OrthographicLens(); lens.set_film_size(1.0, 2.0); lens.set_near_far(1, 30)
        camn = Camera("impcam", lens); cam = scene.attach_new_node(camn); cam.set_pos(0, -10, 1.0); cam.look_at(0, 0, 1.0)
        dr = buf.make_display_region(); dr.set_camera(cam)
        atlas = Image.new("RGBA", (C.CELL[0] * C.COLS, C.CELL[1] * C.ANGLES), (0, 0, 0, 0))
        for ki, kind in enumerate(C.KINDS):
            for vi, (top, bot) in enumerate(C.VARIANTS):
                p = Person(g, kind, 0, 0, 0); AP.style(p, top, bot, None); p.np.reparent_to(scene)
                for a in range(C.ANGLES):
                    p.np.set_pos(0, 0, 0); p.np.set_h(180 + a * 360.0 / C.ANGLES)
                    app.campos.set_element(0, cam.get_pos(app.render) if False else cam.get_pos(scene))
                    app.graphicsEngine.render_frame(); app.graphicsEngine.render_frame()
                    img = PNMImage(); tex.store(img)
                    fn = "/tmp/imp_tmp.png"; img.write(fn); im = Image.open(fn).convert("RGBA").resize(C.CELL, Image.LANCZOS)
                    col = ki * len(C.VARIANTS) + vi
                    atlas.paste(im, (col * C.CELL[0], a * C.CELL[1]))
                p.destroy()
                print("variant", kind, vi, flush=True)
        atlas.save(os.path.join(app.BASE, "assets", "tex", "crowd_atlas.png")); print("ATLAS saved", atlas.size, flush=True)
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
