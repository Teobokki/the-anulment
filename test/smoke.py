import os, traceback, math
OUT = "/workspace/an_shots"
def shot(name):
    app.graphicsEngine.render_frame(); app.graphicsEngine.render_frame()
    app.win.save_screenshot(__import__("panda3d.core", fromlist=["Filename"]).Filename(OUT + "/" + name + ".png")); print("SHOT", name, flush=True)
seq = []
def step(delay, fn): seq.append((delay, fn))
def s_title():
    shot("1_title")
def s_menu():
    app.show_menu(); 
def s_menu_shot(): shot("1b_menu")
def s_start(): app.new_game(True)
def s_city():
    g = app.game; print("GAME", g is not None, "stage", g.stage, "cut", g.cut is not None, flush=True)
    g.end_cut(); me = g.me(); print("ME", me.x, me.y, flush=True)
def s_city_shot():
    g = app.game; print("FPS", app.clock.get_average_frame_rate(), "gtime", g.time, "cut", g.cut, "lb", g.lb_on, flush=True); shot("2_city")
def s_protest():
    g = app.game; me = g.me(); me.x, me.y, me.h = 14.0, -4.0, 20; me.sync(); g.cam_yaw = 20; g.cam_pos = None; g.cam_mode = 0
    g.send_chat("Give us back our vote! CLN presedinte! Turul doi!")
def s_protest_shot(): shot("3_protest"); print("tts ok", app.game.app.tts.ok, "voice played", getattr(app.game, "voice_played", 0), flush=True)
def s_drive():
    g = app.game; g.cam_mode = 0; g.key_e(); g.end_cut()
    me = g.me(); cs = [c for c in g.cars if c not in g.police]
    print("cars", len(g.cars), "peds", len(g.peds), "stage", g.stage, flush=True)
    c = min(cs, key=lambda c: math.hypot(c.x - me.x, c.y - me.y)); me.x, me.y = c.x + 2.5, c.y; me.sync(); g.key_f()
    print("pcar", g.pcar is not None, "heat", g.heat, "pressure", g.pressure, flush=True)
def s_drive2():
    g = app.game; g.vb["v_up"] = True
def s_drive_shot():
    g = app.game; g.vb.clear(); g.toggle_phone(); g.phone_screen("news"); shot("4_drive_phone"); print("speed", g.pcar and g.pcar.speed, flush=True)
def s_story():
    g = app.game; g.toggle_phone(); g.exit_car(force=True); g.vb.clear()
    for _ in range(4): g.debug_skip()
    print("stage", g.stage, "evidence", g.evidence, "published", g.published, "tip", g.tip, "cut", g.cut, flush=True)
    me = g.me(); me.x, me.y = g.tip; me.sync(); g.after_photo("x"); g.rally_t = 0
    print("posts", g.posts, "tip", g.tip, "news", g.news[-1], flush=True)
    g.add_heat(2)
    print('FPS', app.clock.get_average_frame_rate(), 'gtime', g.time, flush=True)
def s_end():
    g = app.game; print("police", len(g.police), "heat", g.heat, "cut", g.cut and g.cut["which"], flush=True)
    import json; print(open(app.save_path()).read()[:300])
    errs = os.path.join(os.path.dirname(app.save_path()), "error.log")
    print("ERRLOG", open(errs).read()[-3000:] if os.path.exists(errs) else "none", flush=True)
    app.userExit()
plan = [(0.5, s_title), (0.5, s_menu), (0.8, s_menu_shot), (0.3, s_start), (6.0, s_city), (8.0, s_city_shot), (0.3, s_protest), (10.0, s_protest_shot),
        (0.3, s_drive), (0.5, s_drive2), (5.0, s_drive_shot), (0.3, s_story), (4.0, s_end)]
def chain(k):
    if k >= len(plan): return
    d, f = plan[k]
    def run(task):
        try: f()
        except Exception: traceback.print_exc()
        chain(k + 1); return task.done
    app.do_method_later(d, run, "smk%d" % k)
chain(0)
