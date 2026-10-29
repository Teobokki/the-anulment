"""THE ANULMENT: methods carried over from the earlier EX Inc. gameplay session (traffic, take-a-car, on-foot moves, bubbles,
EX IX camera app with SELMOTES, full map, HUD helpers, chase / follow cameras, driving input, sub-stepped update)."""
import math, os, random, time
from panda3d.core import (Vec3, Point3, TextNode, CardMaker, TransparencyAttrib, Filename, TransformState, TextureStage, KeyboardButton, SamplerState, Texture)
from direct.gui.DirectGui import DirectFrame, DirectButton, DGG
from direct.gui.OnscreenImage import OnscreenImage
import fs_data as D
import fs_ui as U
from fs_vehicle import Car, TRAFFIC_KINDS
from fs_people import Ped
from fs_ai import TrafficAI, PoliceAI, wrap
NAMES = {"miyo": "MIYOYAZU"}


class Base:
    def cars_near(self, x, y, r):
        r2 = r * r
        return [c for c in self.cars if (c.x - x) ** 2 + (c.y - y) ** 2 < r2]

    def walkers(self):
        out = list(self.peds)
        for p in self.chars.values():
            if p.in_car is None and not getattr(p, "benched", False): out.append(p)
        return out

    def player_pos(self):
        if self.pcar: return self.pcar.x, self.pcar.y
        if self.ride: return self.ride["car"].x, self.ride["car"].y
        p = self.me(); return p.x, p.y

    def player_target(self):
        if self.pcar: return self.pcar.x, self.pcar.y, self.pcar.vx, self.pcar.vy
        x, y = self.player_pos(); return x, y, 0.0, 0.0

    def in_view(self, x, y):
        p = self.app.cam.get_relative_point(self.app.render, Point3(x, y, 1))
        return p.y > 0 and abs(p.x) < p.y * 1.1

    def offscreen_road_point(self, min_d=110, max_d=220):
        px, py = self.player_pos(); best = None
        for _ in range(40):
            a = random.uniform(0, 2 * math.pi); d = random.uniform(min_d, max_d)
            x, y, h = self.world.nearest_road_point(px + math.cos(a) * d, py + math.sin(a) * d)
            dd = math.hypot(x - px, y - py)
            if dd < min_d * 0.7: continue
            best = (x, y, h)
            if not self.in_view(x, y): return x, y, h
        return best or self.world.nearest_road_point(px + min_d, py)

    def populate(self):
        px, py = self.player_pos(); w = self.world
        keep = {self.own, self.pcar, self.taxi, self.medic}
        for c in list(self.cars):
            if c in keep or c in self.police or getattr(c, "racer", False) or getattr(c, "friend", False): continue
            if math.hypot(c.x - px, c.y - py) > 175: self.remove_car(c)
        for p in list(self.peds):
            if math.hypot(p.x - px, p.y - py) > 140: p.destroy(); self.peds.remove(p)
        q = self.app.settings.get("quality", 2)
        # v1.0.4 TRAFFIC DENSITY (LOW / NORMAL / HIGH, default HIGH): a busy city - spawned around you out of view, despawned far away
        dens = {"low": 1.0, "normal": 2.0, "high": 4.0}.get(self.app.settings.get("traffic", "high"), 4.0)
        want = int({0: 12, 1: 20, 2: 26}.get(q, 20) * dens)
        traffic = [c for c in self.cars if isinstance(c.ai, TrafficAI)]
        nodes_ = [n for n, (x_, y_) in w.nodes.items() if abs(x_ - px) < 140 and abs(y_ - py) < 140] or list(w.nodes)
        seed = len(traffic) < want * 0.4      # first fill (load / teleport / taxi skip): fill the streets straight away
        for _ in range(40 if seed else (12 if dens > 1.5 else 4)):
            if len(traffic) >= want: break
            node = random.choice(nodes_); nx_, ny_ = w.nodes[node]
            d = math.hypot(nx_ - px, ny_ - py)
            if d > 140 or (not seed and (d < 40 or (self.in_view(nx_, ny_) and d < 95))) or (seed and d < 20): continue
            nb = random.choice(w.adj[node]); bx, by = w.nodes[nb]
            dx, dy = bx - nx_, by - ny_; L = math.hypot(dx, dy); dx /= L; dy /= L
            x, y = nx_ + dx * 14 - dy * 3.0, ny_ + dy * 14 + dx * 3.0
            if self.cars_near(x, y, 9): continue
            c = self.spawn_car(random.choice(TRAFFIC_KINDS), x, y, math.degrees(math.atan2(-dx, dy)))
            c.ai = TrafficAI(self, c, nb, node); c.driver = "ai"; c.asleep = False; c.vx, c.vy = dx * 8, dy * 8
            traffic.append(c)
        parked = sum(1 for c in self.cars if c.ai is None and c.driver is None and c not in keep)
        if parked < {0: 10, 1: 20, 2: 30}.get(q, 20):
            for (x, y, h) in random.sample(w.parking, min(40, len(w.parking))):
                d = math.hypot(x - px, y - py)
                if 50 < d < 190 and not self.cars_near(x, y, 5) and not self.in_view(x, y):
                    self.spawn_car(random.choice(TRAFFIC_KINDS), x, y, h, parked=True); break
        wantp = {0: 6, 1: 12, 2: 18}.get(q, 12)
        for _ in range(6):
            if len(self.peds) >= wantp: break
            loop = random.choice(w.ped_loops)
            cx = sum(p[0] for p in loop) / len(loop); cy = sum(p[1] for p in loop) / len(loop)
            if math.hypot(cx - px, cy - py) > 120: continue
            p = Ped(self, loop, random.randrange(len(loop)))
            dd = math.hypot(p.x - px, p.y - py)
            if dd < 20 or (self.in_view(p.x, p.y) and dd < 50):
                p.destroy(); continue
            self.peds.append(p)

    def down(self, *keys):
        mw = self.app.mouseWatcherNode
        for k in keys:
            if self.vb.get(k): return True
            if k.startswith("v_") or mw is None: continue
            if k == "shift": b = KeyboardButton.shift()
            elif k == "space": b = KeyboardButton.space()
            elif k == "arrow_up": b = KeyboardButton.up()
            elif k == "arrow_down": b = KeyboardButton.down()
            elif k == "arrow_left": b = KeyboardButton.left()
            elif k == "arrow_right": b = KeyboardButton.right()
            else: b = KeyboardButton.ascii_key(k)
            if mw.is_button_down(b): return True
        return False

    def key_h(self):
        if self.chat is not None: return
        self.app.sfx("horn", 0.7)
        if self.pcar:
            for p in self.peds:
                if math.hypot(p.x - self.pcar.x, p.y - self.pcar.y) < 15: p.flee = 2.0; p.flee_from = (self.pcar.x, self.pcar.y)


    def key_r(self):
        if self.camapp: self.cam_flip(); return
        c = self.pcar
        if c is None: return
        x, y, h = self.world.nearest_road_point(c.x, c.y)
        for _ in range(6):
            if len([o for o in self.cars_near(x, y, 4.5) if o is not c]) == 0: break
            f = (-math.sin(math.radians(h)), math.cos(math.radians(h))); x += f[0] * 6; y += f[1] * 6
        c.x, c.y, c.h = x, y, h; c.vx = c.vy = c.w = 0.0; c.wake(); self.cam_pos = None; self.toast("Vehicle reset")


    def enter_car(self, c):
        if c.ai is not None and c.driver == "ai":     # carjack: the driver is ejected and runs off
            ex, ey = c.door_pos(1)
            p = Ped(self, random.choice(self.world.ped_loops), 0); p.x, p.y = ex, ey; p.flee = 4.0; p.flee_from = (c.x, c.y)
            self.peds.append(p); self.say_line(p, "jacked")
            if c.kind == "police": self.add_heat(2, "Stole a police car!")
            elif any(math.hypot(pc.x - c.x, pc.y - c.y) < 60 for pc in self.police): self.add_heat(1, "Carjacking witnessed!")
            if c in self.police: self.police.remove(c)
        if getattr(c, "taxi_driver", None) is not None: c.taxi_driver.destroy(); c.taxi_driver = None
        c.ai = None; c.driver = "player"; c.role = "player"; c.wake(); c.lights_on = False
        self.pcar = c; self.cam_pos = None
        self.me().seat(c, 1); self.buddy().seat(c, -1)
        self.app.sfx("door", 0.6); self.refresh_buttons()

    def exit_car(self, force=False):
        c = self.pcar
        if c.speed > 7 and not force: self.toast("Slow down to get out"); return
        if hasattr(self, "arsenal"): self.arsenal.unequip()
        def free(side):
            x, y = c.door_pos(side)
            px, py, nx, ny, tag = self.world.grid.push_circle(x, y, 0.4)
            return x + px, y + py
        x1, y1 = free(1); x2, y2 = free(-1)
        self.me().unseat(x1, y1, c.h - 90); self.buddy().unseat(x2, y2, c.h + 90)
        c.driver = None; c.throttle = 0; c.steer = 0; c.hand = True; c.nitro = False
        self.pcar = None; self.cam_yaw = c.h; self.cam_pos = None
        self.app.sfx("door", 0.6); self.refresh_buttons()

    def death_screen(self, word, sub):
        """full-screen slow-motion, washed-out grey screen with a big title (BUSTED / CAPITULATED), then respawn."""
        from direct.gui.OnscreenText import OnscreenText
        a = self.app
        if getattr(self, "_ds", None): self._ds_end()
        cm = CardMaker("ds"); cm.set_frame(-3, 3, -1.2, 1.2)
        n = a.aspect2d.attach_new_node(cm.generate()); n.set_color(0.35, 0.35, 0.37, 0.55); n.set_transparency(TransparencyAttrib.M_alpha); n.set_bin("fixed", 0)
        col = (0.95, 0.25, 0.25, 1) if word == "CAPITULATED" else (0.35, 0.65, 1.0, 1)
        t = OnscreenText(parent=a.aspect2d, text=word, pos=(0, 0.02), scale=0.2, fg=col, shadow=(0, 0, 0, 1), font=U.FONT)
        t2 = OnscreenText(parent=a.aspect2d, text=sub, pos=(0, -0.12), scale=0.05, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), font=U.FONT_PLAIN)
        self._ds = [n, t, t2]; self.time_scale = 0.35
        a.task_mgr.do_method_later(2.6, lambda task: self._ds_end(), "fs-ds")

    def _ds_end(self):
        for x in getattr(self, "_ds", None) or []:
            try: x.destroy()
            except Exception:
                try: x.remove_node()
                except Exception: pass
        self._ds = None; self.time_scale = 1.0

    def move_on_foot(self, me, dt):
        f = (1 if self.down("w", "arrow_up", "v_up") else 0) - (1 if self.down("s", "arrow_down", "v_down") else 0)
        s = (1 if self.down("d", "arrow_right", "v_right") else 0) - (1 if self.down("a", "arrow_left", "v_left") else 0)
        run = self.down("shift", "v_nitro"); sp = 0.0
        if getattr(self, "eating", None) is not None and me is self.me(): f = s = 0; run = False      # v1.0.4: stand still while eating
        if self.arsenal.aiming and not self.blocked():
            self.cam_yaw -= s * 110 * dt
            mw = self.app.mouseWatcherNode
            if mw is not None and mw.has_mouse(): self.cam_yaw -= mw.get_mouse_x() * 90 * dt
            me.h = self.cam_yaw; s = 0
        roam = self.home_roam(); blk = (self.blocked() and not roam) or self.camapp is not None
        if (f or s) and not blk and self.phone is None:
            yaw = math.radians(self.cam_yaw)
            fx, fy = -math.sin(yaw), math.cos(yaw); rx, ry = fy, -fx
            dx, dy = fx * f + rx * s, fy * f + ry * s; L = math.hypot(dx, dy) or 1; dx /= L; dy /= L
            sp = 5.8 if run else 2.1
            me.x += dx * sp * dt; me.y += dy * sp * dt
            th = math.degrees(math.atan2(-dx, dy))
            if not self.arsenal.aiming: me.h += wrap(th - me.h) * min(1, dt * 10)
            if f > 0 and not s: self.cam_yaw += wrap(me.h - self.cam_yaw) * min(1, dt * 1.2)
            elif s and not f: self.cam_yaw += wrap(me.h - self.cam_yaw) * min(1, dt * 0.6)
        if roam:                                   # v1.0.3: free roam inside the house - walls + furniture collide
            for _ in range(2):
                px, py, nx, ny, tag = self.world.home_grid.push_circle(me.x, me.y, 0.32); me.x += px; me.y += py
            b = self.world.home_bounds; me.x = max(b[0], min(b[2], me.x)); me.y = max(b[1], min(b[3], me.y))
            me.walk_anim(dt, sp); me.sync(); return
        px, py, nx, ny, tag = self.world.grid.push_circle(me.x, me.y, 0.35); me.x += px; me.y += py
        for c in self.cars_near(me.x, me.y, 5):
            for cx, cy, r, _ in c.circles():
                dx, dy = me.x - cx, me.y - cy; d = math.hypot(dx, dy)
                if 1e-3 < d < r + 0.35:
                    me.x += dx / d * (r + 0.35 - d); me.y += dy / d * (r + 0.35 - d)
        me.x = min(me.x, D.SEA_X - 0.5) if not self.world.on_pier(me.x, me.y) else me.x
        W = D.WORLD; me.x = max(W[0] + 1, min(W[2] - 1, me.x)); me.y = max(W[1] + 1, min(W[3] - 1, me.y))
        me.walk_anim(dt, sp); me.sync()

    def bubble(self, p, txt, en=None):
        """speech bubble: Japanese line on top, the English translation underneath in smaller text"""
        if not self.app.settings.get("subtitles", True): return
        from panda3d.core import TextPropertiesManager, TextProperties
        tpm = TextPropertiesManager.get_global_ptr()
        if not tpm.has_properties("en"):
            tp = TextProperties(); tp.set_text_scale(0.72); tp.set_text_color(0.85, 0.92, 1.0, 1)
            if U.FONT_PLAIN: tp.set_font(U.FONT_PLAIN)
            tpm.set_properties("en", tp)
        tn = TextNode("bub"); tn.set_align(TextNode.A_center)          # wrapped by hand: kinsoku rules for Japanese
        f = self.app.jpfont if en is not None else U.FONT_PLAIN
        if f: tn.set_font(f)
        import textwrap
        body = U.jwrap(txt, 15.0) if en is not None else "\n".join(textwrap.wrap(txt, 26))
        tn.set_text(body + (("\n\1en\1" + "\n".join(textwrap.wrap(en, 34)) + "\2") if en else ""))
        tn.set_card_color(0.05, 0.03, 0.1, 0.78); tn.set_card_as_margin(0.4, 0.4, 0.25, 0.2); tn.set_text_color(1, 1, 1, 1)
        if getattr(p, "bub", None) and not p.bub.is_empty(): p.bub.remove_node()
        b = p.np.attach_new_node(tn); b.set_z(2.35); b.set_scale(0.2); b.set_billboard_point_eye(); b.set_light_off(); b.set_bin("fixed", 50)
        b.set_depth_test(False); b.set_depth_write(False)
        p.bub = b
        self.app.do_method_later(4.5, lambda t, b=b: (b.remove_node() if not b.is_empty() else None) or t.done, "bub")

    def subtitle(self, txt, dur=3.5, en=None):
        """two-line subtitle: Japanese on top, English translation underneath (smaller); plain English lines use one line"""
        if not self.app.settings.get("subtitles", True): return
        self.sub.setText(U.jwrap(txt, 30.0) if en else txt); self.sub_t = dur
        self.sub["font"] = self.app.jpfont if en else U.FONT_PLAIN
        self.sub_en.setText(en or "")

    def pictures_dir(self):
        """%USERPROFILE%\\Pictures\\THE ANULMENT (or ~/Pictures/THE ANULMENT); falls back to the save folder"""
        cands = []
        if os.name == "nt":
            try:
                import ctypes
                from ctypes import wintypes
                class GUID(ctypes.Structure):
                    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
                g = GUID(0x33E28130, 0x4E1E, 0x4676, (ctypes.c_ubyte * 8)(0x83, 0x5A, 0x98, 0x39, 0x5C, 0x3B, 0xC3, 0xBB))  # FOLDERID_Pictures
                pp = ctypes.c_wchar_p()
                if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(pp)) == 0:
                    cands.append(pp.value); ctypes.windll.ole32.CoTaskMemFree(pp)
            except Exception: pass
            if os.environ.get("USERPROFILE"): cands.append(os.path.join(os.environ["USERPROFILE"], "Pictures"))
        cands.append(os.path.join(os.path.expanduser("~"), "Pictures"))
        for c in cands:
            try:
                d = os.path.join(c, "THE ANULMENT"); os.makedirs(d, exist_ok=True)
                if os.access(d, os.W_OK): return d
            except Exception: continue
        d = os.path.join(os.path.dirname(self.app.save_path()), "Pictures"); os.makedirs(d, exist_ok=True); return d

    def add_photo(self, path):
        path = os.path.abspath(path)
        if path not in self.photos: self.photos.append(path)
        self.save()

    def photo_list(self):
        return [p for p in self.photos if os.path.exists(p)]

    def open_camera(self, misto=False):
        if self.phone: self.phone.destroy(); self.phone = None
        if self.ride or (self.blocked() and not self.home_roam()): return
        if hasattr(self, "arsenal"): self.arsenal.unequip()
        me = self.me()
        self.camapp = {"mode": "rear" if self.pcar else "selfie", "t": 0.0, "ang": 0.0, "pitch": 0.0, "flash": 0.0, "expr": "neutral", "misto": misto, "lens": "none"}
        me.set_expression("neutral")
        if self.home: self.home_prompt_off()
        self.cam_prop(); self.cam_ui(); self.app.sfx("click", 0.6); self.refresh_buttons()
        if self.pcar: self.toast("In a car: REAR camera only - selfies work on foot", 3.0)

    def cam_prop(self):
        """the EX IX G10 in ANA / DANIEL's right hand (selfie)"""
        ca = self.camapp; me = self.me()
        if ca.get("prop"): ca["prop"].remove_node(); ca["prop"] = None
        if ca["mode"] != "selfie" or me.in_car is not None: return
        hand = getattr(me, "handR", None)
        if hand is None or hand.is_empty(): return
        from fs_geom import MB
        b = MB("phone_prop"); col = {"ana": (0.12, 0.35, 0.95, 1)}.get(me.who, (0.45, 0.85, 0.25, 1))
        b.box(-0.036, -0.005, -0.075, 0.036, 0.005, 0.075, col)
        b.box(-0.032, 0.0052, -0.07, 0.032, 0.0062, 0.07, (0.3, 0.55, 1.2, 1))           # screen (faces the character)
        b.box(0.014, -0.0065, 0.045, 0.028, -0.005, 0.064, (0.05, 0.05, 0.06, 1))         # lens
        n = b.node(); n.reparent_to(hand); n.set_pos(0, 0, -0.045); ca["prop"] = n

    def cam_ui(self):
        ca = self.camapp
        if ca.get("ui"): ca["ui"].destroy()
        a = self.app; o = ca["ui"] = DirectFrame(parent=a.aspect2d, frameColor=(0, 0, 0, 0)); o.set_bin("gui-popup", 50)
        acc = self.accent(); ar = a.getAspectRatio()
        for sx in (-1, 1):                                  # viewfinder corner brackets
            for sy in (-1, 1):
                x, y = sx * (ar - 0.12), sy * 0.86
                DirectFrame(parent=o, frameColor=(1, 1, 1, 0.85), frameSize=(min(0, -sx * 0.14), max(0, -sx * 0.14), -0.004, 0.004), pos=(x, 0, y))
                DirectFrame(parent=o, frameColor=(1, 1, 1, 0.85), frameSize=(-0.004, 0.004, min(0, -sy * 0.14), max(0, -sy * 0.14)), pos=(x, 0, y))
        for k in (-1, 1):                                   # faint rule-of-thirds grid
            DirectFrame(parent=o, frameColor=(1, 1, 1, 0.12), frameSize=(-ar, ar, -0.002, 0.002), pos=(0, 0, k * 0.333))
            DirectFrame(parent=o, frameColor=(1, 1, 1, 0.12), frameSize=(-0.002, 0.002, -1, 1), pos=(k * ar / 3, 0, 0))
        sel = ca["mode"] == "selfie"
        if ca.get("misto"):
            import fs_misto; fs_misto.cam_extras(self, o)
        else: U.text(o, "CAMERA", (0, 0.88), 0.05, fg=acc)
        U.text(o, ("SELFIE" if sel else "PHOTO") + "   -   EX IX G10", (0, 0.82), 0.032, font=U.FONT_PLAIN, shadow=(0, 0, 0, 0.8))
        T = lambda n: Filename.from_os_specific(os.path.join(self.app.BASE, "assets", "tex", n)).get_fullpath()
        # big round camera-style shutter, centred at the bottom; click it or press Space / Enter
        sh = ca["shutter"] = DirectButton(parent=o, relief=None, pos=(0, 0, -0.74), command=self.cam_shutter,
                                          image=(T("cam_shutter.png"), T("cam_shutter_down.png"), T("cam_shutter_hover.png"), T("cam_shutter.png")),
                                          image_scale=0.115, frameSize=(-0.115, 0.115, -0.115, 0.115), rolloverSound=None, clickSound=None)
        sh.set_transparency(TransparencyAttrib.M_alpha)
        U.text(o, "SNAP" if ca.get("misto") else "TAKE PHOTO", (0, -0.905), 0.045, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 0.9))
        U.text(o, "Space / Enter", (0, -0.955), 0.026, font=U.FONT_PLAIN, fg=(1, 1, 1, 0.8), shadow=(0, 0, 0, 0.9))
        U.button(o, "BACK", (-0.78, -0.76), self.close_camera, w=0.13, h=0.05, scale=0.036, hint="Esc")
        U.button(o, "FLIP", (-0.40, -0.76), self.cam_flip, w=0.13, h=0.05, scale=0.036, edge=acc, hint="R")
        sm = ca["selm_btn"] = DirectButton(parent=o, relief=None, pos=(0.40, 0, -0.73), command=self.cam_selmotes,
                                           image=T("cam_selmotes.png"), image_scale=0.06, frameSize=(-0.065, 0.065, -0.065, 0.065),
                                           rolloverSound=None, clickSound=None)
        sm.set_transparency(TransparencyAttrib.M_alpha)
        U.text(o, "SELMOTES", (0.40, -0.83), 0.036, fg=(1.0, 0.85, 0.25, 1), shadow=(0, 0, 0, 0.9))
        U.text(o, NAMES[self.active] + ": " + {"smile": "SMILE", "neutral": "NEUTRAL", "frown": "GOOFY FROWN"}[ca.get("expr", "neutral")],
               (0.40, -0.875), 0.024, font=U.FONT_PLAIN, fg=(1, 1, 1, 0.85), shadow=(0, 0, 0, 0.9))
        U.text(o, "A / D  angle      W / S  tilt", (0, 0.77), 0.026, font=U.FONT_PLAIN, fg=(1, 1, 1, 0.75), shadow=(0, 0, 0, 0.8))
        if ca.get("picker"): self.cam_selmotes(force=True)

    def cam_selmotes(self, force=False):
        """SELMOTES picker: three facial expressions for the active character (kept on for the photo)"""
        ca = self.camapp
        if not ca: return
        if ca.get("picker_np"): ca["picker_np"].destroy(); ca["picker_np"] = None
        if not force:
            ca["picker"] = not ca.get("picker")
            self.app.sfx("click", 0.5)
        if not ca.get("picker"): return
        pk = ca["picker_np"] = DirectFrame(parent=ca["ui"], frameColor=(0.06, 0.04, 0.12, 0.88), frameSize=(-0.2, 0.2, -0.2, 0.2),
                                          pos=(0.40, 0, -0.38))
        U.text(pk, "SELMOTES", (0, 0.145), 0.038, fg=(1.0, 0.85, 0.25, 1))
        cur = ca.get("expr", "neutral")
        for k, (eid, nm) in enumerate((("smile", "SMILE"), ("neutral", "NEUTRAL"), ("frown", "GOOFY FROWN"))):
            U.button(pk, nm, (0, 0.06 - k * 0.095), self.cam_set_expr, w=0.17, h=0.038, scale=0.03, extra=[eid],
                     edge=(1.0, 0.85, 0.25, 1) if eid == cur else (0.5, 0.5, 0.6, 1), hint=str(k + 1))

    def cam_set_expr(self, eid):
        ca = self.camapp
        if not ca: return
        ca["expr"] = eid; self.me().set_expression(eid); self.app.sfx("click", 0.5)
        self.toast("%s: %s" % (NAMES[self.active], {"smile": "SMILE", "neutral": "NEUTRAL", "frown": "GOOFY FROWN"}[eid]), 1.5)
        self.cam_ui()

    def cam_flip(self):
        ca = self.camapp
        if not ca: return
        if ca["mode"] == "rear" and self.pcar is not None:
            self.toast("Selfie mode is off in a car - get out first"); return
        ca["mode"] = "rear" if ca["mode"] == "selfie" else "selfie"; ca["ang"] = 0.0; ca["pitch"] = 0.0
        self.cam_prop(); self.cam_ui(); self.app.sfx("click", 0.5)

    def close_camera(self):
        ca = self.camapp
        if not ca: return
        for k in ("prop",):
            if ca.get(k): ca[k].remove_node()
        for k in ("ui", "flash_np", "lens_np"):
            if ca.get(k): ca[k].destroy()
        me = self.me(); me.arm_pose = None; me.set_grip(False, False); me.np.show(); me.set_expression("neutral")
        self.camapp = None; self.cam_pos = None; self.app.camLens.set_fov(65)
        if self.home: self.home_panel()
        self.app.sfx("click", 0.5); self.refresh_buttons()

    def cam_shutter(self):
        ca = self.camapp
        if not ca or ca.get("busy"): return
        ca["busy"] = True; a = self.app
        nm = "%s_%s.png" % ("selfie" if ca["mode"] == "selfie" else "photo", time.strftime("%Y%m%d_%H%M%S"))
        path = None
        try:
            if ca.get("misto"):
                import fs_misto; d = fs_misto.snap_dir(self); nm = "snap_" + time.strftime("%Y%m%d_%H%M%S") + ".png"
            else: d = self.pictures_dir()
            path = os.path.join(d, nm)
            k = 1
            while os.path.exists(path): path = os.path.join(d, nm[:-4] + "_%d.png" % k); k += 1
            a.render2d.hide()                               # no HUD / viewfinder in the picture
            a.graphicsEngine.render_frame(); a.graphicsEngine.render_frame()
            ok = a.win.save_screenshot(Filename.from_os_specific(path))
        except Exception as e:
            ok = False; print("camera save failed", e)
        finally:
            a.render2d.show(); ca["busy"] = False
        if ca.get("flash_np"): ca["flash_np"].destroy()
        ca["flash_np"] = DirectFrame(parent=a.render2d, frameColor=(1, 1, 1, 1), frameSize=(-1, 1, -1, 1)); ca["flash_np"].set_bin("gui-popup", 90)
        ca["flash_np"].set_transparency(TransparencyAttrib.M_alpha); ca["flash"] = 0.35
        ca["last"] = path if ok else None
        self.app.sfx("click", 0.9)
        if ok and ca.get("misto"):
            if ca.get("flash_np"): ca["flash_np"].destroy(); ca["flash_np"] = None
            import fs_misto; fs_misto.after_shot(self, path); return
        if ok: self.add_photo(path)
        self.toast(("Saved  -  Pictures/THE ANULMENT/%s" % os.path.basename(path)) if ok else "Couldn't save the photo", 3.0)

    def update_camapp(self, dt):
        ca = self.camapp
        if not ca: return
        self._update_camapp(dt)
        if self.camapp and self.camapp.get("misto"):
            import fs_misto; fs_misto.track_lens(self)      # after the selfie camera has moved this frame

    def _update_camapp(self, dt):
        ca = self.camapp
        ca["t"] += dt; t = ca["t"]; me = self.me(); cam = self.app.camera; lens = self.app.camLens
        if ca.get("flash_np"):
            ca["flash"] -= dt; f = max(0.0, ca["flash"] / 0.35)
            ca["flash_np"]["frameColor"] = (1, 1, 1, f * 0.9)
            if f <= 0: ca["flash_np"].destroy(); ca["flash_np"] = None
        s = (1 if self.down("d", "arrow_right", "v_right") else 0) - (1 if self.down("a", "arrow_left", "v_left") else 0)
        v = (1 if self.down("w", "arrow_up", "v_up") else 0) - (1 if self.down("s", "arrow_down", "v_down") else 0)
        if self.pcar is not None:
            if ca["mode"] == "selfie": ca["mode"] = "rear"; self.cam_prop(); self.cam_ui()
            c = self.pcar; ca["ang"] = max(-70, min(70, ca["ang"] - s * 60 * dt)); ca["pitch"] = max(-25, min(25, ca["pitch"] + v * 40 * dt))
            r = math.radians(c.h + ca["ang"]); fx, fy = -math.sin(r), math.cos(r)
            cam.set_pos(c.x + c.fwd[0] * 0.2, c.y + c.fwd[1] * 0.2, c.spec["roof"] + 0.1); cam.set_hpr(c.h + ca["ang"], ca["pitch"], 0)
            lens.set_fov(66); self.cam_h = c.h; return
        fx0, fy0 = -math.sin(math.radians(me.h)), math.cos(math.radians(me.h))
        face = 1.56
        if ca["mode"] == "selfie":
            ca["ang"] = max(-55, min(55, ca["ang"] + s * 50 * dt)); ca["pitch"] = max(-0.25, min(0.35, ca["pitch"] + v * 0.4 * dt))
            r = math.radians(me.h + 14 + ca["ang"]); fx, fy = -math.sin(r), math.cos(r)
            d = 0.92 if me.who == "ana" else 1.0; cz = face + 0.16 + ca["pitch"]
            cam.set_pos(me.x + fx * d, me.y + fy * d, cz); cam.look_at(me.x + fx0 * 0.05, me.y + fy0 * 0.05, face - 0.12 if not ca.get("misto") else face + 0.02); lens.set_fov(64)
            # pose: right arm out towards the lens holding the phone, left hand waves beside the face
            wv = math.sin(t * 7.0)
            me.set_arms((-78, 14), (-46 + 3 * wv, 30), (-14, 0), (-128 + 14 * wv, 4)); me.set_grip(True, False)
            me.model.set_r(math.sin(t * 1.4) * 1.5)
            pr = ca.get("prop")
            if pr: pr.look_at(self.app.render, Point3(me.x + fx0 * 0.1, me.y + fy0 * 0.1, face)); pr.set_h(pr, 180)
        else:
            me.h = (me.h - s * 70 * dt) % 360; me.sync(); ca["pitch"] = max(-30, min(30, ca["pitch"] + v * 40 * dt))
            me.set_arms((-70, 6), (-70, 6), (-35, 12), (-35, 12)); me.set_grip(True, True)
            fx, fy = fx0, fy0
            cam.set_pos(me.x + fx * 0.42, me.y + fy * 0.42, 1.42); cam.set_hpr(me.h, ca["pitch"], 0); lens.set_fov(66)
        self.cam_h = me.h

    def toggle_map(self):
        if self.overlay and getattr(self, "map_np", None): self.close_overlay(); return
        if self.blocked(): return
        o = self.overlay = DirectFrame(parent=self.app.aspect2d, frameColor=(0, 0, 0, 0.75), frameSize=(-3, 3, -1, 1),
                                       state=DGG.NORMAL)
        o.bind(DGG.B1PRESS, self.map_click)
        S = 0.9; self.map_np = S
        OnscreenImage(parent=o, image=self.map_tex, pos=(0, 0, 0), scale=(S, 1, S))
        xmin, ymin, span = -470.0, -590.0, 1180.0
        def mp(x, y): return ((x - xmin) / span * 2 - 1) * S, ((y - ymin) / span * 2 - 1) * S
        for nm, c, col in self.MAP_LABELS:
            x, y = mp(*c); U.text(o, nm, (x, y), 0.03, fg=col)
        for m in self.markers + self.pois:
            x, y = mp(m["x"], m["y"])
            DirectFrame(parent=o, frameColor=(0, 0, 0, 0.75), frameSize=(-0.024, 0.024, -0.024, 0.024), pos=(x, 0, y))
            U.text(o, self.ICON[m["kind"]], (x, y - 0.013), 0.038, fg=m["col"] + (1,))
            U.text(o, m["name"], (x, y - 0.05), 0.022, fg=m["col"] + (0.95,), font=U.FONT_PLAIN)
        lg = DirectFrame(parent=o, frameColor=(0.04, 0.03, 0.08, 0.9), frameSize=(-0.02, 0.52, -0.06 - 0.052 * len(self.LEGEND), 0.06), pos=(0.98, 0, 0.62))
        U.text(lg, "LEGEND", (0.25, 0.0), 0.04, fg=U.CYAN)
        for i, (ic, txt) in enumerate(self.LEGEND):
            U.text(lg, ic, (0.03, -0.06 - i * 0.052), 0.036, fg=U.GOLD)
            U.text(lg, txt, (0.08, -0.06 - i * 0.052), 0.026, fg=(1, 1, 1, 0.9), font=U.FONT_PLAIN, align=TextNode.A_left)
        if self.waypoint:
            x, y = mp(*self.waypoint); U.text(o, "X", (x, y - 0.015), 0.05, fg=(0.3, 1, 0.4, 1))
        px, py = self.player_pos(); x, y = mp(px, py); U.text(o, "●", (x, y - 0.015), 0.05, fg=(1, 1, 1, 1), font=U.SYM)
        U.text(o, "MAP  -  click to set a waypoint   [M / Esc to close]", (0, -0.96), 0.035, font=U.FONT_PLAIN)
        U.button(o, "CLOSE", (1.15, 0.85), self.close_overlay, w=0.14, h=0.045, scale=0.034, hint="M")
        self.refresh_buttons()

    def map_click(self, ev):
        mw = self.app.mouseWatcherNode
        if mw is None or not mw.has_mouse(): return
        p = self.app.aspect2d.get_relative_point(self.app.render2d, Point3(mw.get_mouse()[0], 0, mw.get_mouse()[1]))
        S = 0.9; xmin, ymin, span = -470.0, -590.0, 1180.0
        if abs(p.x) > S or abs(p.z) > S: return
        x = xmin + (p.x / S + 1) / 2 * span; y = ymin + (p.z / S + 1) / 2 * span
        self.waypoint = (x, y); self.toast("Waypoint set"); self.app.sfx("click", 0.6)
        self.close_overlay(); self.toggle_map()

    def toast(self, txt, dur=2.5):
        self.toast_t.setText(txt); self.toast_k = dur

    def caption(self, a, b, dur=3.0):
        self.cap1.setText(a); self.cap2.setText(b); self.cap_k = dur

    def letterbox(self, on):
        self.lb_on = on

    def fade(self, dur=1.0):
        self.fade_k = dur; self.fade_dur = dur


    def cam_clear(self, tx, ty, x, y, z):
        """pull the camera in front of buildings so it never clips inside geometry."""
        g = self.world.grid
        if not g.segment_blocked(tx, ty, x, y): return x, y
        for f in (0.8, 0.6, 0.45, 0.3, 0.18):
            nx_, ny_ = tx + (x - tx) * f, ty + (y - ty) * f
            if not g.segment_blocked(tx, ty, nx_, ny_): return nx_, ny_
        return tx + (x - tx) * 0.12, ty + (y - ty) * 0.12

    def update_camera(self, dt):
        cam = self.app.camera; lens = self.app.camLens
        self.shake = max(0.0, self.shake - dt * 2.0)
        sh = (random.uniform(-1, 1) * self.shake * 0.25, random.uniform(-1, 1) * self.shake * 0.25)
        fov = 70.0
        if self.garage:
            g = self.garage; c = g["car"]; g["a"] += dt * 14
            r = math.radians(g["a"]); d = 9.5
            x, y = c.x + math.cos(r) * d, c.y + math.sin(r) * d
            cam.set_pos(x, y, 2.4); cam.look_at(c.x, c.y, 0.8); lens.set_fov(50)
            cam.set_h(cam, 14); self.cam_h = cam.get_h(); return
        if self.intro_t > 0:
            me = self.me(); r = math.radians(self.time * 18 + 200); d = 7.0 + self.intro_t * 1.4
            cam.set_pos(me.x + math.cos(r) * d, me.y + math.sin(r) * d, 1.6 + self.intro_t * 0.9)
            cam.look_at(me.x, me.y, 1.4); lens.set_fov(55); self.cam_h = cam.get_h(); return
        if self.ride:
            c = self.ride["car"]; t = self.time
            r = math.radians(c.h + 150 + math.sin(t * 0.15) * 40); d = 10.0
            x, y = self.cam_clear(c.x, c.y, c.x + math.cos(r) * d, c.y + math.sin(r) * d, 3)
            cam.set_pos(x, y, 2.4 + math.sin(t * 0.2) * 0.8); cam.look_at(c.x, c.y, 1.0); lens.set_fov(50); self.cam_h = c.h; return
        if self.pcar:
            c = self.pcar; f = c.fwd; sp = c.speed
            if self.cam_mode == 2:
                cam.set_pos(c.x + f[0] * 0.2, c.y + f[1] * 0.2, c.spec["roof"] + 0.1); cam.set_hpr(c.h, -3, 0)
                lens.set_fov(min(95, 72 + sp * 0.3)); self.cam_h = c.h; return
            dist, hgt = (6.8, 2.3) if self.cam_mode == 0 else (11.0, 3.8)
            dist += min(sp, 70) * 0.03
            # heading follows velocity a bit (drift look)
            vh = math.degrees(math.atan2(-c.vx, c.vy)) if sp > 5 and c.fspeed() > 0 else c.h
            want = c.h + wrap(vh - c.h) * 0.35
            if self.cam_pos is None: self.cam_yaw = want
            self.cam_yaw += wrap(want - self.cam_yaw) * min(1, dt * 4.5)
            r = math.radians(self.cam_yaw); fx, fy = -math.sin(r), math.cos(r)
            x, y = c.x - fx * dist, c.y - fy * dist
            x, y = self.cam_clear(c.x, c.y, x, y, hgt)
            if self.cam_pos is None: self.cam_pos = [x, y]
            k = min(1, dt * 10)
            self.cam_pos[0] += (x - self.cam_pos[0]) * k; self.cam_pos[1] += (y - self.cam_pos[1]) * k
            cam.set_pos(self.cam_pos[0] + sh[0], self.cam_pos[1] + sh[1], hgt + sh[0] * 0.5)
            cam.look_at(c.x + fx * 4, c.y + fy * 4, 0.9)
            fov = 68 + min(28, sp * 0.42) + (6 if c.nitro and c.nitro_amt > 0 else 0)
            self.cur_fov = getattr(self, "cur_fov", fov) + (fov - getattr(self, "cur_fov", fov)) * min(1, dt * 3)
            lens.set_fov(self.cur_fov); self.cam_h = self.cam_yaw; return
        me = self.me()
        dist, hgt = ((4.2, 1.9), (7.0, 3.2), (2.6, 1.7))[self.cam_mode]
        if self.arsenal.aiming:
            dist, hgt = 2.1, 1.75
        if self.cinematic > 0:
            self.cinematic -= dt; dist += self.cinematic * 3; hgt += self.cinematic * 1.5
        r = math.radians(self.cam_yaw); fx, fy = -math.sin(r), math.cos(r)
        x, y = me.x - fx * dist + fy * 0.5, me.y - fy * dist - fx * 0.5
        x, y = self.cam_clear(me.x, me.y, x, y, hgt)
        if self.cam_pos is None: self.cam_pos = [x, y]
        k = min(1, dt * 8)
        self.cam_pos[0] += (x - self.cam_pos[0]) * k; self.cam_pos[1] += (y - self.cam_pos[1]) * k
        cam.set_pos(self.cam_pos[0] + sh[0], self.cam_pos[1] + sh[1], hgt)
        cam.look_at(me.x + fx * 2 + fy * 0.5, me.y + fy * 2 - fx * 0.5, 1.4)
        lens.set_fov(50 if self.arsenal.aiming else 65); self.cam_h = self.cam_yaw

    # ================================================================ main loop
    def control_player(self, dt):
        c = self.pcar
        if c is None: return
        if self.blocked() or self.phone:
            c.throttle = 0; c.steer = 0; c.hand = True; c.nitro = False; return
        up = self.down("w", "arrow_up", "v_up"); dn = self.down("s", "arrow_down", "v_down")
        lf = self.down("a", "arrow_left", "v_left"); rt = self.down("d", "arrow_right", "v_right")
        pad = getattr(self.app, "pad", None)
        thr = (1.0 if up else 0.0) - (1.0 if dn else 0.0); st = (1.0 if lf else 0.0) - (1.0 if rt else 0.0)
        if pad:
            try:
                thr += pad.get("rt", 0) - pad.get("lt", 0); st += -pad.get("lx", 0)
            except Exception: pass
        c.throttle = max(-1.0, min(1.0, thr))
        tgt = max(-1.0, min(1.0, st))
        c.steer += (tgt - c.steer) * min(1, dt * (6 if tgt else 9))
        c.hand = self.down("space", "v_hand"); c.nitro = self.down("shift", "v_nitro")
        if c.asleep and (thr or st): c.wake()
        # automatic unstick: pushing against a wall without moving -> reset
        if c.contact > 0 and abs(c.throttle) > 0.5 and c.speed < 1.0:
            self.stuck_t += dt
            if self.stuck_t > 2.5: self.stuck_t = 0; self.key_r()
        else: self.stuck_t = max(0.0, self.stuck_t - dt)

    def update(self, task):
        # v1.0.3: real-time sub-stepping. Frames slower than 20 fps used to be clamped to a 0.05 s step, so on a busy
        # scene (beach / dense sidewalks) ANA & DANIEL walked in slow motion; now up to 4 sub-steps keep normal speed.
        raw = max(0.0, min(0.2, self.app.clock.get_dt()))
        if self.paused:
            try: self.online.update(1e-4)          # v1.0.5: the session keeps talking while the menu is open
            except Exception as e: self.app.log_error(e)
            return task.cont
        n = max(1, int(math.ceil(raw / 0.05))); dt = raw / n * self.time_scale
        try:
            for _ in range(n): self.step(dt)
        except Exception as e:
            self.app.log_error(e)
        return task.cont
