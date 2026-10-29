"""THE ANULMENT gameplay: MIYOYAZU in Valdora. Chapter 1 'The Annulled Vote' (investigation, protest, interview, evidence board,
pressure meter, endless free roam with tips, rallies and news), traffic you can take (non-violently), police pursuit (follow + box in, no shooting), protest crowds with
live chanting, EX IX G10 phone, T text chat spoken by the offline Romanian Piper voice, minimap + full map, save / load."""
import math, os, random, time, json, threading
from panda3d.core import (Point3, TextNode, CardMaker, TransparencyAttrib, Filename, Texture, SamplerState, AudioSound, NodePath)
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectEntry, DirectSlider, DGG
from direct.gui.OnscreenImage import OnscreenImage
import fs_data as D
import fs_ui as U
from fs_vehicle import Car, collide_cars, TRAFFIC_COLS
from fs_people import Ped
from fs_ai import TrafficAI, PoliceAI, wrap
from fs_geom import MB
import an_people as AP
from an_base import Base, NAMES

SPAWN = (152.0, -88.0, 180.0)
PROTEST = {"rect": (-38.0, -38.0, 38.0, 8.0), "c": (0.0, -12.0)}          # the crossing in front of the court
COURT = (50.0, 12.0)                                                         # court portico (south face of block 4,4)
CLUES = {   # id: (x, y, kind, label)
    "ev_memo":   (32.0, 13.2, "photo", "Dropped court memo on the steps"),
    "ev_ballots": (-150.0, -86.0, "photo", "Tally sheets at the Patriots' Front stall"),
    "ev_email":  (250.0, 114.0, "recover", "Laptop left at the internet café"),
}
AIDE = (-112.0, 150.0)       # prosecutors' aide (interview)
EV_NAMES = {"ev_memo": "COURT MEMO", "ev_ballots": "TALLY SHEETS", "ev_email": "VALMONT EMAIL", "ev_recording": "AIDE INTERVIEW"}
OBJ = ["Go to the protest outside the Constitutional Court", "Find evidence: photograph or recover 3 clues", "Interview the prosecutors' aide",
       "Open the EVIDENCE BOARD (B) and publish the truth", "Free roam: follow tips (?), photograph and post them, join the rallies"]
TIP_NEWS = ["A reader's photo spreads online: more questions about the annulment.", "Your post is shared 40,000 times. TVV calls it 'disinformation'.",
            "Students join the candle vigil after your latest post.", "The Coalition refuses to comment on the leaked photo.",
            "Prosecutors' office 'reviewing' new images published by MIYOYAZU.", "Taxi drivers honk in support as the post goes viral."]
RALLY_NEWS = ["RALLY: tens of thousands gather at the Constitutional Court - peaceful, with candles.", "RALLY: the diaspora marches in support of the second round.",
              "RALLY: farmers drive tractors into Valdora, chanting TURUL DOI ÎNAPOI!", "RALLY: pensioners and students side by side outside the court."]
RESTRICTED = [(20.0, 11.0, 80.0, 16.0, "COURT STEPS")]
MESSAGES = [("IOANA (blogger)", "They annulled the vote. CLN won 61% and they just... erased it. Come to the court, everyone is going."),
            ("UNKNOWN NUMBER", "Look for a memo near the court steps. It was drafted BEFORE the hearing."),
            ("PATRIOTS' FRONT", "Our volunteers kept every tally sheet. Find our stall by the old town."),
            ("IOANA (blogger)", "A café near the TV tower: a Coalition staffer left his laptop there. The emails are still open."),
            ("ELENA (CLN's wife)", "Thank you for not looking away. The children ask when their father is coming home.")]
NEWS = [("TVV STATE NEWS", "Court protects democracy from 'dangerous' candidate. Reform Alliance and Coalition welcome the ruling."),
        ("TVV STATE NEWS", "Analysts: the annulment was 'a technical necessity' requested by our partners in Valmont."),
        ("VALDORA FREE BLOG", "Hundreds of thousands in the squares. 'Give us back our vote!' Peaceful, with candles."),
        ("VALDORA FREE BLOG", "Only the Patriots' Front stands with CLN - and state TV calls them extremists.")]
LIES = [("'The ruling was written after the hearing, as the law requires.'", "ev_memo"),
        ("'The count was full of fraud. The tally sheets were invalid.'", "ev_ballots"),
        ("'Nobody outside Valdora had any say in this.'", "ev_email")]


class Stub:
    aiming = False
    def update(self, *a): pass
    def unequip(self): pass
    def seat(self, *a): pass
    def unseat(self, *a): pass
    def destroy(self): pass


class Game(Base):
    MAP_LABELS = [("CONSTITUTIONAL COURT", (50, 40), (1, 0.85, 0.4, 1)), ("PROTEST", (0, -20), (1, 0.6, 0.3, 1)), ("YOUR FLAT", SPAWN[:2], (0.7, 0.9, 1, 1)),
                  ("PROSECUTORS", AIDE, (0.8, 0.8, 1, 1)), ("TVV TOWER", (150, 150), (0.8, 0.8, 0.85, 1)), ("OLD TOWN", (-280, -280), (0.75, 0.6, 0.45, 1)),
                  ("LAKE SHORE", (540, 0), (0.4, 0.7, 0.9, 1))]
    ICON = {"obj": "◆", "clue": "?", "zone": "●"}
    LEGEND = [("◆", "Objective"), ("?", "Clue"), ("●", "Protest (no cars)"), ("■", "Police")]

    def __init__(self, app, save):
        global SPAWN
        self.app = app; self.world = app.world; self.time = 0.0
        sd = save or {}
        self.stage = int(sd.get("stage", 0)); self.evidence = [e for e in sd.get("evidence", []) if e in EV_NAMES]
        self.pressure = float(sd.get("pressure", 0)); self.chat_hist = list(sd.get("chat", []))[-8:]; self.photos = list(sd.get("photos", []))
        self.msgs = int(sd.get("msgs", 1)); self.published = bool(sd.get("published", sd.get("ended", False)))
        if self.published: self.stage = max(self.stage, 4)
        self.posts = int(sd.get("posts", 0)); self.news = [tuple(n) for n in sd.get("news", []) if isinstance(n, (list, tuple)) and len(n) == 2][-6:]
        self.tip = tuple(sd["tip"]) if isinstance(sd.get("tip"), list) and len(sd["tip"]) == 2 else None
        self.tip_t = 5.0; self.rally_t = float(sd.get("rally_t", 120.0)); self.swell = 0.0
        self.cars = []; self.peds = []; self.police = []; self.cops = []; self.paused = False; self.overlay = None; self.phone = None
        self.heat = 0; self.heat_t = 0.0; self.escape_t = 0.0; self.bust_t = 0.0; self.cam_mode = 0; self.vb = {}
        self.cam_yaw = SPAWN[2]; self.cam_pos = None; self.shake = 0.0; self.sub_t = 0.0; self.cinematic = 0.0; self.lb_on = False; self.lb_k = 0.0
        self.waypoint = None; self.stuck_t = 0.0; self.pop_t = 0.0; self.intro_t = 0.0; self.camapp = None; self.cut = None; self.chat = None
        self.ride = self.taxi = self.medic = self.own = self.garage = self.home = self.eating = None; self.arsenal = Stub(); self._stub = Stub()
        self.time_scale = 1.0; self.cam_h = None; self.online = Stub(); self.markers = []; self.pois = []; self.question_cd = 0.0; self.tts_q = []; self.tts_busy = False; self.board = None
        try:
            vx, vy = min((pt for lp in self.world.ped_loops for pt in lp), key=lambda q: math.hypot(q[0] - 60, q[1] + 60))
            SPAWN = (float(vx), float(vy), math.degrees(math.atan2(vx - PROTEST["c"][0], -(vy - PROTEST["c"][1]))) % 360)
        except Exception as e: app.log_error(e)
        x, y, h = sd.get("pos", SPAWN) if isinstance(sd.get("pos"), list) and len(sd.get("pos")) == 3 else SPAWN
        self.chars = {"miyo": AP.make_miyo(self, x, y, h)}; self.active = "miyo"; self.cam_yaw = h
        self.pcar = None
        self.world.adj = {k: [m for m in v if m != (4, 4)] for k, v in self.world.adj.items() if k != (4, 4)}     # traffic never enters the protest
        self.world.adj[(4, 4)] = [(3, 4), (5, 4), (4, 3), (4, 5)]
        from fs_signals import Signals
        self.signals = Signals(self)
        self.build_scene(); self.build_hud(); self.bind_keys()
        self.chant = app.loader.load_sfx(Filename.from_os_specific(os.path.join(app.BASE, "assets", "sfx", "chant_live.ogg")))
        self.chant.set_loop(True); self.chant.set_volume(0); self.chant.play()
        app.task_mgr.add(self.update, "game-update", sort=10)
        self.update_objective()
        if self.stage == 0 and not save:
            self.start_cut("intro")

    # ------------------------------------------------------------------ scene: court, barriers, crowd, police, family
    def build_scene(self):
        w = self.world; rnd = random.Random(26)
        root = self.scene = w.root.attach_new_node("anulment")
        mb = MB("court"); cx, cy = COURT
        mb.box(cx - 32, cy - 0.6, 0.15, cx + 32, cy + 3.5, 1.0, (0.62, 0.6, 0.56, 1))            # steps
        mb.box(cx - 32, cy + 3.5, 0, cx + 32, cy + 4.5, 2.0, (0.6, 0.58, 0.54, 1))
        for k in range(10):
            px = cx - 27 + k * 6; mb.box(px - 0.7, cy + 1.5, 1.0, px + 0.7, cy + 2.9, 15.0, (0.78, 0.76, 0.72, 1)); w.grid.add_circle(px, cy + 2.2, 0.9, "p")
        mb.box(cx - 31, cy + 0.8, 15.0, cx + 31, cy + 4.5, 17.5, (0.74, 0.72, 0.68, 1))
        for k in range(8):   # pediment steps
            mb.box(cx - 30 + k * 3.6, cy + 1.0, 17.5 + k * 0.8, cx + 30 - k * 3.6, cy + 4.5, 18.3 + k * 0.8, (0.72, 0.7, 0.66, 1))
        n = mb.node(); n.reparent_to(root); n.set_light_off(); n.set_color_scale(0.62, 0.62, 0.66, 1)
        w.grid.add_rect((cx - 32, cy + 3.5, cx + 32, cy + 6), "b")
        tn = TextNode("courtsign"); tn.set_text("CURTEA CONSTITUȚIONALĂ A VALDOREI"); tn.set_align(TextNode.A_center); tn.set_font(U.FONT)
        tn.set_text_color(0.95, 0.88, 0.62, 1); s = root.attach_new_node(tn); s.set_pos(cx, cy + 0.7, 15.8); s.set_scale(1.5); s.set_light_off()
        # crowd barriers on the four approaches to the protest (gaps let people through, not cars)
        bm = MB("barriers")
        for (bx, by, ax) in ((0, 46, "x"), (0, -46, "x"), (46, 0, "y"), (-46, 0, "y")):
            for k in range(-5, 6):
                if ax == "x": x0, y0, x1, y1 = bx + k * 2.2 - 0.9, by - 0.1, bx + k * 2.2 + 0.9, by + 0.1
                else: x0, y0, x1, y1 = bx - 0.1, by + k * 2.2 - 0.9, bx + 0.1, by + k * 2.2 + 0.9
                bm.box(x0, y0, 0, x1, y1, 1.1, (0.55, 0.56, 0.58, 1), top=True)
                w.grid.add_rect((x0, y0, x1, y1), "w")
        bn = bm.node(); bn.reparent_to(root); bn.set_light_off(); bn.set_color_scale(0.6, 0.6, 0.62, 1)
        # barrier line in front of the court where the police hold a (peaceful) shield line
        self.crowd = AP.crowd_lod(self, (-36, -36, 36, 6), 260, rnd, avoid=[(-6, -12, 6, 0)], face=COURT)
        self.crowd2 = AP.crowd_lod(self, (-90, -9, -50, 9), 70, rnd, face=(0, 0))
        self.near = []
        for k in range(10):
            a = rnd.uniform(0, 6.28); r = rnd.uniform(4, 12)
            p = AP.make_protester(self, PROTEST["c"][0] + math.cos(a) * r, PROTEST["c"][1] + math.sin(a) * r * 0.6, 0, rnd)
            p.h = math.degrees(math.atan2(-(COURT[0] - p.x), COURT[1] - p.y)); p.sync(); self.near.append(p)
        self.cops = []
        for k in range(8):
            p = AP.make_cop(self, 24 + k * 3.2, 9.0, 180, riot=True, rnd=rnd); p.sync(); p.post = (p.x, p.y); self.cops.append(p)
        for k, (x, y) in enumerate(((60, 9.5), (14, 9.5), (-112, 146), (300, -120), (-60, -112), (110, 60))):
            p = AP.make_cop(self, x, y, rnd.uniform(0, 360), rnd=rnd); p.sync(); p.post = (x, y); p.patrol = k >= 2; self.cops.append(p)
        self.aide = AP.make_cop(self, AIDE[0], AIDE[1], 90, rnd=rnd)   # replaced below with civilian styling
        self.aide.destroy(); self.aide = AP.make_family(self, "wife", AIDE[0], AIDE[1], 90); AP.style(self.aide, (0.2, 0.2, 0.22), (0.12, 0.12, 0.14), (0.6, 0.5, 0.4)); self.aide.sync()
        for x, y, h in ((60, 2.0, 0), (-60, 2.0, 0)):
            c = self.spawn_car("policevan", x, y, 90 if x > 0 else -90, parked=True); c.lights_on = True; c.static_cop = True
        self.clue_np = {}
        for cid, (x, y, kind, lbl) in CLUES.items():
            m = MB("clue"); m.box(x - 0.25, y - 0.18, 0.15, x + 0.25, y + 0.18, 0.2 if kind == "photo" else 0.6, (1.6, 1.55, 1.4, 1))
            if kind == "recover": m.box(x - 0.6, y - 0.4, 0, x + 0.6, y + 0.4, 0.55, (0.3, 0.22, 0.15, 1))
            n = m.node(); n.reparent_to(root); n.set_light_off(); self.clue_np[cid] = n
        rings = MB("rings"); self.ring_np = None
        tick = self.clue_np

    def spawn_car(self, kind, x, y, h, role="traffic", parked=False, paint=None):
        paint = paint or random.choice(TRAFFIC_COLS)
        if kind in ("police", "policevan"): paint = (0.92, 0.92, 0.94)
        if kind == "taxi": paint = (0.95, 0.78, 0.12)
        if kind == "bus": paint = (0.85, 0.3, 0.12)
        c = Car(self, kind, x, y, h, paint, "", parked, role); self.cars.append(c); return c

    def remove_car(self, c):
        if c in self.cars: self.cars.remove(c)
        if c in self.police: self.police.remove(c)
        if self.chars["miyo"].in_car is c: self.chars["miyo"].unseat(c.x + 3, c.y, c.h)
        c.destroy()

    def me(self): return self.chars["miyo"]
    def buddy(self): return self._stub
    def home_roam(self): return False
    def home_prompt_off(self): pass
    def home_panel(self): pass
    def accent(self): return (0.55, 0.75, 1.0, 1)
    def blocked(self):
        return self.paused or self.overlay is not None or self.cut is not None or self.camapp is not None or self.chat is not None or self.board is not None

    # ------------------------------------------------------------------ input
    def bind_keys(self):
        a = self.app
        for k, f in (("f", self.key_f), ("e", self.key_e), ("c", self.key_c), ("r", self.key_r), ("h", self.key_h), ("m", self.toggle_map),
                     ("t", self.open_chat), ("p", self.toggle_phone), ("escape", self.key_esc), ("b", self.toggle_board), ("l", self.key_lights),
                     ("enter", self.key_enter), ("space", self.key_space), ("1", lambda: self.key_num(0)),
                     ("2", lambda: self.key_num(1)), ("3", lambda: self.key_num(2))):
            a.accept(k, self._guard(f, k))
        import sys
        if os.environ.get("AN_DEBUG") and not getattr(sys, "frozen", False): a.accept("f9", self.debug_skip)      # dev builds only

    def _guard(self, f, k):
        def h():
            if self.chat is not None and k not in ("escape", "enter"): return
            f()
        return h

    def unbind(self):
        for k in ("f", "e", "c", "r", "h", "m", "t", "p", "escape", "b", "l", "enter", "space", "f9", "1", "2", "3"): self.app.ignore(k)

    def key_num(self, k):
        if self.camapp and self.camapp.get("picker"): self.cam_set_expr(("smile", "neutral", "frown")[k])
        elif self.overlay is not None and getattr(self.overlay, "choose", None): self.overlay.choose(k)

    def key_c(self):
        if self.blocked(): return
        self.cam_mode = (self.cam_mode + 1) % 3; self.cam_pos = None

    def key_space(self):
        if self.camapp: self.cam_shutter()

    def key_enter(self):
        if self.chat is not None: return
        if self.camapp: self.cam_shutter(); return
        if self.cut: self.cut["t"] = max(self.cut["t"], self.cut["next"])

    def key_lights(self):
        if self.pcar: self.pcar.lights_on = not self.pcar.lights_on; self.toast("Headlights " + ("ON" if self.pcar.lights_on else "OFF"))

    def key_esc(self):
        if self.chat is not None: self.close_chat(); return
        if self.camapp: self.close_camera(); return
        if self.phone: self.toggle_phone(); return
        if self.board: self.toggle_board(); return
        if self.overlay: self.close_overlay(); return
        if self.cut: self.end_cut(); return
        self.app.show_pause()

    def close_overlay(self):
        if self.overlay: self.overlay.destroy(); self.overlay = None
        self.map_np = None; self.refresh_buttons()

    def key_f(self):
        if self.blocked(): return
        if self.pcar: self.exit_car(); return
        me = self.me(); best = None
        for c in self.cars_near(me.x, me.y, 8):
            d = math.hypot(c.x - me.x, c.y - me.y)
            if d < c.spec["hl"] + 2.3 and (best is None or d < best[0]): best = (d, c)
        if best: self.take_car(best[1])

    def take_car(self, c):
        """take ANY vehicle, non-violently: the driver gets out and runs off shouting"""
        if c.ai is not None and c.driver == "ai":
            ex, ey = c.door_pos(1)
            p = Ped(self, random.choice(self.world.ped_loops), 0); p.x, p.y = ex, ey; p.flee = 5.0; p.flee_from = (c.x, c.y); self.peds.append(p)
            line = random.choice(["Hei! Mașina mea!", "Ajutor! Poliția!", "Nu se poate! Mașina mea!"])
            self.bubble(p, line); self.speak(line, p, vol=0.8)
        police = c.kind in ("police", "policevan")
        self.add_pressure(25 if police else 8, "Took a POLICE vehicle!" if police else "Took a vehicle")
        self.add_heat(2 if police else (1 if any(math.hypot(o.x - c.x, o.y - c.y) < 70 for o in self.police) or random.random() < 0.35 else 0))
        if c in self.police: self.police.remove(c)
        c.ai = None; c.driver = "player"; c.role = "player"; c.wake(); c.lights_on = True; c.static_cop = False
        self.pcar = c; self.cam_pos = None; self.me().seat(c, 1)
        self.app.sfx("door", 0.6); self.refresh_buttons(); self.app.radio(True)

    def exit_car(self, force=False):
        c = self.pcar
        if c is None: return
        if c.speed > 7 and not force: self.toast("Slow down to get out"); return
        x, y = c.door_pos(1); px, py, *_ = self.world.grid.push_circle(x, y, 0.4)
        self.me().unseat(x + px, y + py, c.h - 90)
        c.driver = None; c.throttle = 0; c.steer = 0; c.hand = True
        self.pcar = None; self.cam_yaw = c.h; self.cam_pos = None; self.app.sfx("door", 0.6); self.refresh_buttons(); self.app.radio(False)

    def key_e(self):
        if self.blocked(): return
        me = self.me(); x, y = self.player_pos()
        for cid, (cx, cy, kind, lbl) in CLUES.items():
            if kind == "recover" and cid not in self.evidence and math.hypot(cx - x, cy - y) < 3.0 and self.stage >= 1:
                self.add_evidence(cid); self.subtitle("MIYOYAZU: The inbox is still open... Valmont. 'Funds follow compliance.'", 5); return
        if self.stage >= 2 and math.hypot(AIDE[0] - x, AIDE[1] - y) < 3.5 and "ev_recording" not in self.evidence:
            self.interview(); return
        if self.stage == 0 and math.hypot(x - PROTEST["c"][0], y - PROTEST["c"][1]) < 30: self.advance(); return

    # ------------------------------------------------------------------ story
    def update_objective(self):
        self.stage = min(self.stage, len(OBJ) - 1)
        tgt = None
        if self.stage == 0: tgt = PROTEST["c"]
        elif self.stage == 1:
            left = [c for c in CLUES if c not in self.evidence]
            if not left: self.stage = 2; return self.update_objective()
            x, y = self.player_pos(); c = min(left, key=lambda k: math.hypot(CLUES[k][0] - x, CLUES[k][1] - y)); tgt = CLUES[c][:2]
        elif self.stage == 2: tgt = AIDE
        elif self.stage >= 4: tgt = self.tip
        self.objective = tgt
        self.markers = [{"id": "obj", "x": tgt[0], "y": tgt[1], "name": "OBJECTIVE", "col": (1.0, 0.82, 0.3), "kind": "obj"}] if tgt else []
        self.pois = [{"id": "zone", "x": PROTEST["c"][0], "y": PROTEST["c"][1], "name": "PROTEST", "col": (1.0, 0.55, 0.25), "kind": "zone"}]
        if self.stage >= 1:
            self.pois += [{"id": c, "x": v[0], "y": v[1], "name": v[3], "col": (0.6, 1.0, 0.6), "kind": "clue"} for c, v in CLUES.items() if c not in self.evidence]
        if self.stage >= 4 and self.tip:
            self.pois.append({"id": "tip", "x": self.tip[0], "y": self.tip[1], "name": "TIP", "col": (0.6, 1.0, 0.6), "kind": "clue"})
        if hasattr(self, "obj_t"):
            self.obj_t.setText(("VALDORA  -  POSTS %d" % self.posts if self.stage >= 4 else "CHAPTER 1  -  THE ANNULLED VOTE") + "\n" + OBJ[self.stage])
        if hasattr(self, "mm_icons"): self.rebuild_mm_icons()

    def advance(self):
        if self.stage == 0: self.stage = 1; self.start_cut("arrest"); self.msgs = max(self.msgs, 4)
        elif self.stage == 1: self.stage = 2
        elif self.stage == 2: self.stage = 3; self.msgs = 5
        elif self.stage == 3: self.publish_truth()
        self.update_objective(); self.save()

    def add_evidence(self, cid):
        if cid in self.evidence: return
        self.evidence.append(cid); self.app.sfx("checkpoint", 0.7)
        self.toast("EVIDENCE: %s  (%d/4)" % (EV_NAMES[cid], len(self.evidence)), 3.5)
        if cid in self.clue_np: self.clue_np[cid].hide()
        if self.stage == 1 and all(c in self.evidence for c in CLUES): self.advance()
        self.update_objective(); self.save()

    def debug_skip(self):
        """F9 (debug): skip ahead one story step"""
        if self.stage == 1:
            for c in CLUES: self.add_evidence(c) if c not in self.evidence else None
        elif self.stage == 2: self.evidence.append("ev_recording") if "ev_recording" not in self.evidence else None; self.advance()
        else: self.advance()
        self.toast("DEBUG: skipped to step %d" % self.stage)

    def add_pressure(self, n, why=""):
        self.pressure = max(0.0, min(100.0, self.pressure + n))
        if why: self.toast("%s   PRESSURE %d%%" % (why, self.pressure))
        if self.pressure >= 100: self.warned("You attracted too much attention.")

    def add_heat(self, n):
        if n <= 0: return
        old = self.heat; self.heat = min(3, self.heat + n); self.escape_t = 0
        if self.heat > old: self.app.sfx("heat", 0.6); self.toast("POLIȚIA VALDOREI is following you - lose them!")

    def warned(self, why):
        """caught / too much pressure: a warning and a respawn at your flat (no violence)"""
        if self.pcar: self.exit_car(force=True)
        self.heat = 0; self.bust_t = 0; self.pressure = 40.0
        self.death_screen("WARNING", "Poliția Valdorei: %s Released with a warning." % why); self.app.sfx("busted", 0.7)
        me = self.me(); me.x, me.y = SPAWN[0], SPAWN[1]; me.h = SPAWN[2]; me.sync(); self.cam_pos = None
        for c in list(self.police): self.remove_car(c)
        self.fade(1.0); self.save()

    def interview(self):
        """interview: the aide makes three claims; catch each lie with the right evidence (RECORDER records it)"""
        o = self.overlay = DirectFrame(parent=self.app.aspect2d, frameColor=(0, 0, 0, 0.55), frameSize=(-3, 3, -1, 1), state=DGG.NORMAL)
        U.panel(o, -1.05, 1.05, -0.62, 0.62, edge=(0.9, 0.3, 0.3, 1))
        U.text(o, "INTERVIEW  -  PROSECUTORS' AIDE        [REC ●]", (0, 0.5), 0.05, fg=(1, 0.5, 0.45, 1), font=U.SYM)
        st = {"i": 0, "ok": 0}
        q = U.text(o, "", (0, 0.3), 0.045, font=U.FONT_PLAIN, wrap=38); res = U.text(o, "", (0, -0.5), 0.035, font=U.FONT_PLAIN, fg=U.CYAN, wrap=50)
        btns = []
        def show():
            for b in btns: b.destroy()
            btns.clear()
            if st["i"] >= len(LIES):
                q.setText("AIDE: ...Fine. We were told the charge before there was a case. Turn that thing off.")
                self.add_evidence("ev_recording"); self.speak("Bine. Ni s-a spus acuzația înainte să existe un dosar.", self.aide)
                btns.append(U.button(o, "DONE", (0, -0.3), lambda: (self.close_overlay(), self.advance()), w=0.2, h=0.05, scale=0.04)); return
            q.setText("AIDE: " + LIES[st["i"]][0] + "\n\nPresent evidence:")
            for k, cid in enumerate(c for c in CLUES):
                if cid not in self.evidence: continue
                btns.append(U.button(o, EV_NAMES[cid], (-0.6 + k * 0.6, -0.15), pick, w=0.26, h=0.05, scale=0.032, extra=[cid], hint=str(k + 1)))
        def pick(cid):
            if cid == LIES[st["i"]][1]:
                res.setText("That's a lie - and the %s proves it." % EV_NAMES[cid]); self.app.sfx("checkpoint", 0.5); st["i"] += 1
            else:
                res.setText("Wrong evidence. The aide smirks.  PRESSURE +10"); self.add_pressure(10); self.app.sfx("empty", 0.6)
            show()
        o.choose = lambda k: pick(list(CLUES)[k]) if k < len(CLUES) and list(CLUES)[k] in self.evidence and st["i"] < len(LIES) else None
        show(); self.refresh_buttons()

    def toggle_board(self):
        if self.board: self.board.destroy(); self.board = None; self.refresh_buttons(); return
        if self.blocked(): return
        o = self.board = DirectFrame(parent=self.app.aspect2d, frameColor=(0, 0, 0, 0.7), frameSize=(-3, 3, -1, 1), state=DGG.NORMAL)
        OnscreenImage(parent=o, image=self.world.T("board_cork.jpg", repeat=False), scale=(1.3, 1, 0.82))
        U.text(o, "EVIDENCE BOARD", (0, 0.72), 0.06, fg=(1, 0.9, 0.7, 1))
        pos = {"ev_memo": (-0.85, 0.35), "ev_ballots": (0.85, 0.35), "ev_email": (-0.85, -0.35), "ev_recording": (0.85, -0.35)}
        U.text(o, "CLN\nwon round one\n61.4%", (0, 0.02), 0.05, fg=(0.1, 0.1, 0.1, 1), font=U.FONT)
        mb = MB("string")
        for cid, (x, y) in pos.items():
            if cid in self.evidence:     # red string from each clue to the centre
                dx, dy = -x, -y; L = math.hypot(dx, dy); nx, ny = -dy / L * 0.006, dx / L * 0.006
                mb.quad((x - nx, 0, y - ny), (x + nx, 0, y + ny), (nx, 0, ny), (-nx, 0, -ny), (0.85, 0.05, 0.05, 1))
        sn = mb.node(); sn.reparent_to(o); sn.set_two_sided(True)
        for cid, (x, y) in pos.items():
            if cid in self.evidence:
                OnscreenImage(parent=o, image=self.world.T(cid + ".png", repeat=False), pos=(x, 0, y), scale=(0.3, 1, 0.225))
            else:
                DirectFrame(parent=o, frameColor=(0.2, 0.15, 0.1, 0.6), frameSize=(-0.3, 0.3, -0.225, 0.225), pos=(x, 0, y)); U.text(o, "? missing", (x, y), 0.04)
        U.text(o, "Links: memo + email + ledger of orders from VALMONT -> Reform Alliance & the Coalition -> court, prosecutors, state TV.", (0, -0.7), 0.03, font=U.FONT_PLAIN, wrap=70)
        if len(self.evidence) >= 4 and self.stage == 3 and not self.published:
            U.button(o, "PUBLISH THE TRUTH", (0.0, -0.82), lambda: (self.toggle_board(), self.publish_truth()), w=0.34, h=0.05, scale=0.04, edge=(1, 0.8, 0.3, 1))
        U.button(o, "CLOSE", (1.1, 0.75), self.toggle_board, w=0.12, h=0.04, scale=0.03, hint="B")
        self.refresh_buttons()

    # ------------------------------------------------------------------ cutscenes (letterbox, scripted cameras, captions)
    def start_cut(self, which):
        if self.pcar: self.exit_car(force=True)
        self.close_overlay(); self.letterbox(True)
        me = self.me()
        if which == "intro":
            shots = [(0.0, "orbit", None, ("VALDORA", "The night after the Constitutional Court annulled the first round."), "city"),
                     (4.5, "court", None, ("CLN won by a landslide.", "Now he is banned, charged - and the city is in the streets."), None),
                     (9.0, "player", None, ("MIYOYAZU", "Blogger. Ordinary citizen. Nobody's agent."), None)]
            self.cut = {"shots": shots, "t": 0.0, "i": -1, "next": 0.0, "end": 13.5, "which": which}
        elif which == "arrest":
            self.cln = AP.make_cln(self, 50, 12.5, 180); self.cln.sync()
            esc = [AP.make_cop(self, 48.8, 12.5, 180, female=False), AP.make_cop(self, 51.2, 12.5, 180, female=True)]
            fam = [AP.make_family(self, "wife", 72, 6.5, 225), AP.make_family(self, "son", 70.8, 6.8, 220), AP.make_family(self, "daughter", 73.0, 7.2, 230)]
            for p in esc + fam: p.sync()
            self.cut_people = esc + fam
            shots = [(0.0, "court", None, ("CONSTITUTIONAL COURT", "Prosecutors raid CLN's office. He is led out in handcuffs."), "family"),
                     (4.0, "cln", None, ("CLN", "\"Do not be afraid. Stay peaceful. The truth does not need violence.\""), None),
                     (8.5, "family", None, ("His wife Elena and their children watch from the barrier.", ""), None),
                     (12.0, "crowd", None, ("The crowd answers.", "CLN PREȘEDINTE!  -  TURUL DOI ÎNAPOI!"), "protest")]
            self.cut = {"shots": shots, "t": 0.0, "i": -1, "next": 0.0, "end": 16.0, "which": which}
            self.cheer()
        self.refresh_buttons()

    def update_cut(self, dt):
        c = self.cut; c["t"] += dt; cam = self.app.camera; t = c["t"]
        shots = c["shots"]
        while c["i"] + 1 < len(shots) and t >= shots[c["i"] + 1][0]:
            c["i"] += 1; s = shots[c["i"]]; self.caption(s[3][0], s[3][1], 4.4)
            if s[4]: self.app.play_music(s[4])
            c["next"] = shots[c["i"] + 1][0] if c["i"] + 1 < len(shots) else c["end"]
        kind = shots[c["i"]][1]; st = t - shots[c["i"]][0]; me = self.me()
        if kind == "orbit":
            r = math.radians(st * 8 + 200); cam.set_pos(math.cos(r) * 70, -60 + math.sin(r) * 30, 22 - st); cam.look_at(0, 10, 8)
        elif kind == "court":
            cam.set_pos(-10 + st * 2, -30, 4 + st * 0.4); cam.look_at(COURT[0], COURT[1], 7)
        elif kind == "player":
            cam.set_pos(me.x + 3.0 - st * 0.2, me.y - 3.0, 1.7); cam.look_at(me.x, me.y, 1.45)
        elif kind == "cln" and getattr(self, "cln", None):
            p = self.cln
            if c["which"] == "arrest":
                p.y = 12.5 - min(st, 4.0) * 1.2; p.walk_anim(dt, 1.2 if st < 4 else 0); p.set_arms((-30, 2), (-30, 2), (-60, -14), (-60, -14)); p.sync()
                for k, e in enumerate(self.cut_people[:2]): e.x = p.x + (-1.0 if k == 0 else 1.0); e.y = p.y; e.walk_anim(dt, 1.2 if st < 4 else 0); e.sync()
            cam.set_pos(p.x + 1.6, p.y - 3.4, 1.65); cam.look_at(p.x, p.y, 1.5)
        elif kind == "family":
            f = self.cut_people[-3]; cam.set_pos(f.x - 2.5, f.y - 2.8, 1.6); cam.look_at(f.x + 0.5, f.y, 1.35)
        elif kind == "crowd":
            cam.set_pos(-4 + st * 1.5, -34, 3.5 + st * 0.3); cam.look_at(0, 0, 2.0)
        self.app.camLens.set_fov(45); self.cam_h = cam.get_h()
        if t >= c["end"]: self.end_cut()

    def end_cut(self):
        c = self.cut
        if not c: return
        self.cut = None; self.letterbox(False); self.cam_pos = None; self.caption("", "", 0.1)
        if c["which"] == "arrest":
            for p in getattr(self, "cut_people", [])[:2]: p.destroy()
            if getattr(self, "cln", None): self.cln.destroy(); self.cln = None
            self.cut_people = self.cut_people[2:]
            self.toast("New messages on your EX IX G10 (P)", 4)
        self.app.play_music("city"); self.refresh_buttons()

    def publish_truth(self):
        """PUBLISH THE TRUTH: no ending - the news and the streets react, the chant swells, free roam goes on forever"""
        if self.published: return
        self.published = True; self.stage = 4; self.msgs = 5
        self.add_news("VALDORA FREE BLOG", "MIYOYAZU publishes the memo, the tally sheets, the Valmont email and the aide's recording.")
        self.add_news("TVV STATE NEWS", "State TV interrupts its programme: 'unverified documents' circulate online.")
        self.caption("THE TRUTH IS OUT", "Your post reaches millions. Valdora answers in the streets.", 5.0)
        self.swell = 40.0; self.cheer(); self.app.sfx("checkpoint", 0.8)
        self.new_tip(); self.update_objective(); self.save()

    def add_news(self, src, txt):
        self.news = (self.news + [(src, txt)])[-6:]

    def new_tip(self):
        """endless side activity: a new spot to photograph and post (somewhere on the sidewalks of Valdora)"""
        pts = [pt for lp in self.world.ped_loops for pt in lp if abs(pt[0]) < 420 and abs(pt[1]) < 420]
        x, y = self.player_pos()
        far = [pt for pt in pts if 60 < math.hypot(pt[0] - x, pt[1] - y) < 260] or pts
        self.tip = tuple(float(v) for v in random.choice(far)); self.toast("NEW TIP on your EX IX G10: something to photograph (?)", 4)
        self.update_objective()

    def update_side(self, dt):
        """endless free roam: tips to photograph + post, and random protest rallies with the chant swelling"""
        self.swell = max(0.0, self.swell - dt)
        if self.stage < 1 or self.cut: return
        self.rally_t -= dt
        if self.rally_t <= 0:
            self.rally_t = random.uniform(150, 260); self.swell = 30.0
            txt = random.choice(RALLY_NEWS); self.add_news("VALDORA FREE BLOG", txt); self.toast(txt, 5); self.cheer()
        if self.stage >= 4 and self.tip is None:
            self.tip_t -= dt
            if self.tip_t <= 0: self.new_tip()

    def cheer(self):
        self.app.sfx("cheer", 0.9)
        for p in self.near: p.cheer = 2.5

    # ------------------------------------------------------------------ TEXT CHAT spoken by the offline Romanian Piper voice
    def open_chat(self):
        if self.chat is not None or self.cut or self.paused: return
        a = self.app; o = self.chat = DirectFrame(parent=a.a2dBottomCenter, frameColor=(0.02, 0.03, 0.05, 0.85), frameSize=(-0.9, 0.9, -0.06, 0.06), pos=(0, 0, 0.5))
        U.text(o, "SAY (English, max 200)  -  Enter: speak   Esc: cancel", (0, 0.08), 0.03, font=U.FONT_PLAIN, fg=U.CYAN)
        e = DirectEntry(parent=o, initialText="", width=34, numLines=1, scale=0.045, pos=(-0.86, 0, -0.015), frameColor=(0.08, 0.09, 0.12, 1),
                        text_fg=(1, 1, 1, 1), entryFont=U.FONT_PLAIN, focus=1, command=self.send_chat, focusOutCommand=lambda: None)
        o.ent = e
        for k, line in enumerate(reversed(self.chat_hist[-4:])):
            U.text(o, line, (0, 0.13 + k * 0.045), 0.03, font=U.FONT_PLAIN, fg=(1, 1, 1, 0.7 - k * 0.12))
        self.refresh_buttons()

    def close_chat(self):
        if self.chat is not None: self.chat.destroy(); self.chat = None
        self.refresh_buttons()

    def send_chat(self, text):
        text = (text or "").strip()[:200]
        self.close_chat()
        if not text: return
        self.chat_hist = (self.chat_hist + [text])[-8:]
        me = self.me(); self.bubble(me, text); self.subtitle("MIYOYAZU: " + text, 4 + len(text) / 25.0)
        self.speak(text, me)
        lo = text.lower()
        if "cln" in lo or "turul doi" in lo:
            x, y = self.player_pos()
            if math.hypot(x - PROTEST["c"][0], y - PROTEST["c"][1]) < 90: self.cheer(); self.toast("The crowd cheers!")

    def speak(self, text, who=None, vol=1.0):
        """queue a line for the offline Piper ro_RO voice; synthesised in a thread, played from the speaker's position"""
        if len(self.tts_q) > 4: self.tts_q.pop(0)
        self.tts_q.append((text, who, vol))

    def update_tts(self):
        if self.tts_busy or not self.tts_q: return
        text, who, vol = self.tts_q.pop(0); self.tts_busy = True
        def work():
            try: self._tts_out = (self.app.tts.synth(text), who, vol)
            except Exception as e: self.app.log_error(e); self._tts_out = (None, who, vol)
        threading.Thread(target=work, daemon=True).start()

    def poll_tts(self):
        out = getattr(self, "_tts_out", None)
        if out is None: return
        self._tts_out = None; self.tts_busy = False; path, who, vol = out
        if not path: return
        try:
            s = self.app.loader.load_sfx(Filename.from_os_specific(path))
            x, y = self.player_pos(); d = math.hypot(who.x - x, who.y - y) if who is not None else 0
            s.set_volume(max(0.15, 1.0 - d / 30.0) * vol * self.app.vol("voice_volume"))
            if who is not None and d > 1:   # stereo position relative to the camera
                p = self.app.cam.get_relative_point(self.app.render, Point3(who.x, who.y, 1.6)); s.set_balance(max(-1, min(1, p.x / max(1.0, abs(p.y) + 1))))
            s.play(); self.last_voice = s; self.voice_played = getattr(self, "voice_played", 0) + 1
        except Exception as e: self.app.log_error(e)

    # ------------------------------------------------------------------ phone: EX IX G10
    def toggle_phone(self):
        if self.phone: self.phone.destroy(); self.phone = None; self.app.sfx("click", 0.5); self.refresh_buttons(); return
        if self.blocked(): return
        self.phone_screen("boot" if not getattr(self, "_booted", False) else "home"); self._booted = True; self.app.sfx("click", 0.6)

    def phone_screen(self, which):
        if self.phone: self.phone.destroy()
        T = lambda n: Filename.from_os_specific(os.path.join(self.app.BASE, "assets", "tex", n)).get_fullpath()
        PH = 1.22; k = PH / 1170.0; PW = 585 * k
        sx0, sy1 = (43 - 292.5) * k, (585 - 43) * k; sw, sh = 479 * k, 1054 * k; cx = sx0 + sw / 2; top = sy1
        drv = self.pcar is not None
        root = DirectFrame(parent=self.app.a2dBottomRight, frameColor=(0, 0, 0, 0), pos=((-0.86 if drv else -0.06) - PW / 2, 0, PH / 2 + 0.04))
        root.set_bin("gui-popup", 60); self.phone = root; root.which = which
        OnscreenImage(parent=root, image=T("phone_boot.png" if which == "boot" else "phone_wall.png"), pos=(cx, 0, top - sh / 2), scale=(sw / 2, 1, sh / 2))
        img = OnscreenImage(parent=root, image=T("phone_g10.png"), scale=(PW / 2, 1, PH / 2)); img.set_transparency(TransparencyAttrib.M_alpha)
        W = lambda t, y, sc, fg=(1, 1, 1, 1), wrap=None, x=None, al=TextNode.A_center: U.text(root, t, (cx if x is None else x, top - y), sc, fg=fg, font=U.FONT_PLAIN, wrap=wrap, align=al)
        if which == "boot":
            self.app.do_method_later(1.1, lambda t: (self.phone_screen("home") if self.phone is root else None) or t.done, "boot"); return
        bat = max(5, 100 - int(self.time / 60)); W(time.strftime("%H:%M"), 0.075, 0.032, x=sx0 + 0.04, al=TextNode.A_left); W("%d%%" % bat, 0.075, 0.032, x=sx0 + sw - 0.04, al=TextNode.A_right)
        def btn(lbl, fn, y, w=0.2): U.button(root, lbl, (cx, top - y), fn, w=w, h=0.04, scale=0.03, edge=self.accent())
        if which == "home":
            W("EX IX G10", 0.16, 0.05, fg=self.accent())
            apps = [("camera", "CAMERA", self.open_camera), ("messages", "MESSAGES", lambda: self.phone_screen("messages")), ("news", "NEWS", lambda: self.phone_screen("news")),
                    ("map", "MAP", lambda: (self.toggle_phone(), self.toggle_map())), ("evidence", "EVIDENCE", lambda: self.phone_screen("evidence")),
                    ("recorder", "RECORDER", lambda: self.phone_screen("recorder")), ("settings", "SETTINGS", lambda: (self.toggle_phone(), self.app.open_settings(None)))]
            for n, (ic, lbl, fn) in enumerate(apps):
                x = cx + ((n % 3) - 1) * 0.15; yo = (n // 3) * 0.17
                b = DirectButton(parent=root, image=T("app_%s.png" % ic), image_scale=0.05, relief=None, pos=(x, 0, top - 0.32 - yo), command=fn)
                b.set_transparency(TransparencyAttrib.M_alpha); U.text(root, lbl, (x, top - 0.405 - yo), 0.024, font=U.FONT_PLAIN)
            btn("CLOSE", self.toggle_phone, 0.95)
        elif which == "messages":
            W("MESSAGES", 0.15, 0.045, fg=self.accent())
            for k, (frm, txt) in enumerate(MESSAGES[:self.msgs]):
                W(frm, 0.23 + k * 0.14, 0.026, fg=U.GOLD); W(txt, 0.26 + k * 0.14, 0.021, wrap=19)
            btn("BACK", lambda: self.phone_screen("home"), 0.95)
        elif which == "news":
            W("NEWS", 0.15, 0.045, fg=self.accent())
            for k, (src, txt) in enumerate((list(reversed(self.news)) + NEWS)[:4]):
                W(src, 0.24 + k * 0.16, 0.026, fg=(1, 0.5, 0.45, 1) if "TVV" in src else (0.5, 1, 0.6, 1)); W(txt, 0.27 + k * 0.16, 0.021, wrap=19)
            btn("BACK", lambda: self.phone_screen("home"), 0.95)
        elif which == "evidence":
            W("EVIDENCE  %d/4" % len(self.evidence), 0.15, 0.04, fg=self.accent())
            for k, cid in enumerate(self.evidence):
                OnscreenImage(parent=root, image=T(cid + ".png"), pos=(cx + ((k % 2) - 0.5) * 0.2, 0, top - 0.3 - (k // 2) * 0.17), scale=(0.09, 1, 0.0675))
            if not self.evidence: W("Photograph clues with CAMERA", 0.3, 0.026, wrap=18)
            btn("OPEN BOARD", lambda: (self.toggle_phone(), self.toggle_board()), 0.75); btn("BACK", lambda: self.phone_screen("home"), 0.95)
        elif which == "recorder":
            W("RECORDER", 0.15, 0.045, fg=self.accent())
            W("aide_interview.m4a  4:12" if "ev_recording" in self.evidence else "No recordings yet.\nInterviews are recorded\nautomatically.", 0.3, 0.026, wrap=18)
            btn("BACK", lambda: self.phone_screen("home"), 0.95)
        self.refresh_buttons()

    def add_photo(self, path):
        Base.add_photo(self, path); self.after_photo(path)

    def after_photo(self, path):
        """photos of clues count as evidence; in free roam a photo of a tip is posted"""
        if self.stage < 1: return
        x, y = self.player_pos()
        if self.stage >= 4 and self.tip and math.hypot(self.tip[0] - x, self.tip[1] - y) < 12:
            self.posts += 1; self.tip = None; self.tip_t = 20.0
            self.add_news("VALDORA FREE BLOG", random.choice(TIP_NEWS)); self.toast("POSTED  -  %d posts. The crowd grows." % self.posts, 4)
            self.swell = max(self.swell, 15.0); self.cheer(); self.update_objective(); self.save(); return
        for cid, (cx, cy, kind, lbl) in CLUES.items():
            if kind == "photo" and cid not in self.evidence and math.hypot(cx - x, cy - y) < 9:
                self.add_evidence(cid); return

    # ------------------------------------------------------------------ HUD
    def build_hud(self):
        a = self.app; self.hud = a.aspect2d.attach_new_node("hud")
        img, _ = self.world.map_image(1024)
        t = Texture("map"); t.load(img); t.set_wrap_u(SamplerState.WM_border_color); t.set_wrap_v(SamplerState.WM_border_color)
        t.set_border_color((0.02, 0.02, 0.05, 1)); t.set_minfilter(SamplerState.FT_linear); self.map_tex = t
        self.mm_root = a.a2dTopRight.attach_new_node("mm"); self.mm_root.set_pos(-0.33, 0, -0.36); M = 0.27; self.mm_M = M
        self._mmf = DirectFrame(parent=self.mm_root, frameColor=(0, 0, 0, 0)); U.panel(self._mmf, -M, M, -M, M, col=(0, 0, 0, 0), edge=U.CYAN, ew=0.008)
        cm = CardMaker("mm"); cm.set_frame(-M, M, -M, M); self.mm = self.mm_root.attach_new_node(cm.generate()); self.mm.set_texture(t)
        self.mm_dots = []
        for _ in range(60):
            d = DirectFrame(parent=self.mm_root, frameColor=(1, 1, 1, 1), frameSize=(-0.01, 0.01, -0.01, 0.01)); d.hide(); self.mm_dots.append(d)
        self.mm_icons = []; self.rebuild_mm_icons()
        U.text(self.mm_root, "▲", (0, -0.016), 0.045, fg=(1, 1, 1, 1), font=U.SYM)
        self.dist_lbl = U.text(self.mm_root, "VALDORA", (0, -M - 0.05), 0.034, fg=U.CYAN)
        tl = a.a2dTopLeft
        self.obj_t = U.text(tl, "", (0.06, -0.2), 0.036, fg=(1, 0.9, 0.7, 1), align=TextNode.A_left, font=U.FONT_PLAIN)
        U.text(tl, "PRESSURE", (0.06, -0.33), 0.03, fg=(1, 0.6, 0.5, 1), align=TextNode.A_left)
        self.pr_bar = U.bar(tl, (0.25, -0.32), 0.4, 0.012, 0.0, col=(1.0, 0.4, 0.3, 1))
        self.stars_t = U.text(tl, "", (0.06, -0.4), 0.034, fg=(0.5, 0.7, 1, 1), align=TextNode.A_left)
        br = a.a2dBottomRight
        self.speed_t = U.text(br, "", (-0.48, 0.64), 0.1, align=TextNode.A_right); self.kmh_t = U.text(br, "", (-0.46, 0.64), 0.035, fg=U.CYAN, align=TextNode.A_left)
        self.radio_t = U.text(br, "", (-0.3, 0.58), 0.028, fg=(0.8, 0.85, 1, 1), font=U.FONT_PLAIN)
        self.prompt = U.text(a.aspect2d, "", (0, -0.55), 0.045)
        self.sub = U.text(a.a2dBottomCenter, "", (0, 0.36), 0.044, font=U.FONT_PLAIN, wrap=40, shadow=(0, 0, 0, 1))
        self.sub_en = U.text(a.a2dBottomCenter, "", (0, 0.305), 0.032, fg=(0.8, 0.9, 1.0, 1), font=U.FONT_PLAIN, wrap=46, shadow=(0, 0, 0, 1))
        self.toast_t = U.text(a.aspect2d, "", (0, 0.62), 0.042, fg=U.CYAN); self.toast_k = 0.0
        self.cap1 = U.text(a.aspect2d, "", (0, 0.05), 0.09); self.cap2 = U.text(a.aspect2d, "", (0, -0.05), 0.042, fg=U.CYAN, font=U.FONT_PLAIN, wrap=44); self.cap_k = 0.0
        cmb = CardMaker("lb"); cmb.set_frame(-3, 3, 0, 0.16)
        self.lb_top = a.aspect2d.attach_new_node(cmb.generate()); self.lb_top.set_color(0, 0, 0, 1); self.lb_top.set_z(1.0)
        self.lb_bot = a.aspect2d.attach_new_node(cmb.generate()); self.lb_bot.set_color(0, 0, 0, 1); self.lb_bot.set_r(180); self.lb_bot.set_z(-1.0)
        cmf = CardMaker("fade"); cmf.set_frame(-3, 3, -1, 1)
        self.fade_np = a.aspect2d.attach_new_node(cmf.generate()); self.fade_np.set_color(0, 0, 0, 0); self.fade_np.set_transparency(TransparencyAttrib.M_alpha)
        self.fade_np.set_bin("fixed", 100); self.fade_k = 0.0
        self.btn_root = None; self.btn_state = None; self.btn_nodes = []; self.refresh_buttons()

    def rebuild_mm_icons(self):
        for ic in self.mm_icons: ic.destroy()
        self.mm_icons = [U.text(self.mm_root, self.ICON[m["kind"]], (0, 0), 0.034, fg=m["col"] + (1,), font=U.SYM) for m in self.markers + self.pois]

    def hold(self, key):
        return (lambda: self.vb.__setitem__(key, True)), (lambda: self.vb.__setitem__(key, False))

    def refresh_buttons(self):
        st = (self.pcar is not None, self.phone is not None, self.overlay is not None, self.camapp is not None, self.chat is not None, self.board is not None,
              self.cut is not None, self.app.settings.get("buttons", True))
        if st == self.btn_state: return
        self.btn_state = st
        for n in self.btn_nodes: n.destroy()
        self.btn_nodes = []; self.vb.clear()
        a = self.app
        if not a.settings.get("buttons", True) or self.camapp or self.cut: return
        tl = DirectFrame(parent=a.a2dTopLeft, frameColor=(0, 0, 0, 0)); self.btn_nodes.append(tl)
        sm = dict(w=0.1, h=0.04, scale=0.028)
        for k, (lbl, fn, hk) in enumerate((("MENU", self.key_esc, "Esc"), ("MAP", self.toggle_map, "M"), ("PHONE", self.toggle_phone, "P"), ("CHAT", self.open_chat, "T"), ("BOARD", self.toggle_board, "B"))):
            U.button(tl, lbl, (0.13 + k * 0.22, -0.07), fn, hint=hk, **sm)
        if self.phone or self.overlay or self.board or self.chat: return
        br = DirectFrame(parent=a.a2dBottomRight, frameColor=(0, 0, 0, 0)); self.btn_nodes.append(br)
        bw = dict(w=0.115, h=0.045, scale=0.028); c1, c2 = -0.42, -0.16; rows = [0.08, 0.2, 0.32, 0.44]
        if self.pcar:
            p, r = self.hold("v_hand"); U.button(br, "HANDBRAKE", (c1, rows[0]), None, hint="Space", press=p, release=r, **bw)
            U.button(br, "EXIT", (c2, rows[0]), self.key_f, hint="F", **bw); U.button(br, "HORN", (c1, rows[1]), self.key_h, hint="H", **bw)
            U.button(br, "LIGHTS", (c2, rows[1]), self.key_lights, hint="L", **bw); U.button(br, "RADIO", (c1, rows[2]), self.app.radio_next, hint="", **bw)
            U.button(br, "RESET", (c2, rows[2]), self.key_r, hint="R", **bw)
        else:
            U.button(br, "TAKE VEHICLE", (c2, rows[0]), self.key_f, hint="F", **bw)
            p, r = self.hold("v_nitro"); U.button(br, "RUN", (c1, rows[0]), None, hint="Shift", press=p, release=r, **bw)
            U.button(br, "INTERACT", (c2, rows[1]), self.key_e, hint="E", edge=U.GOLD, **bw); U.button(br, "CAMERA", (c1, rows[1]), self.open_camera, hint="", **bw)
        bl = DirectFrame(parent=a.a2dBottomLeft, frameColor=(0, 0, 0, 0)); self.btn_nodes.append(bl)
        pd = dict(w=0.065, h=0.065, scale=0.045, font=U.SYM)
        for key, lbl, pos, hint in (("v_up", "▲", (0.25, 0.37), "W"), ("v_down", "▼", (0.25, 0.1), "S"), ("v_left", "◀", (0.11, 0.1), "A"), ("v_right", "▶", (0.39, 0.1), "D")):
            p, r = self.hold(key); U.button(bl, lbl, pos, None, hint=hint, press=p, release=r, **pd)

    def update_hud(self, dt):
        px, py = self.player_pos()
        self.toast_k -= dt; self.cap_k -= dt; self.sub_t -= dt
        if self.toast_k <= 0: self.toast_t.setText("")
        if self.cap_k <= 0: self.cap1.setText(""); self.cap2.setText("")
        if self.sub_t <= 0: self.sub.setText(""); self.sub_en.setText("")
        self.lb_k += ((1.0 if self.lb_on else 0.0) - self.lb_k) * min(1, dt * 3)
        self.lb_top.set_z(1.0 - 0.16 * self.lb_k); self.lb_bot.set_z(-1.0 + 0.16 * self.lb_k)
        if self.fade_k > 0:
            self.fade_k -= dt; k = self.fade_k / self.fade_dur; self.fade_np.set_color(0, 0, 0, max(0, min(1, (1.0 - abs(k * 2 - 1)) * 1.6)))
        else: self.fade_np.set_color(0, 0, 0, 0)
        hud_on = self.camapp is None and self.cut is None
        for n in (self.mm_root, self.obj_t, self.pr_bar[0], self.stars_t): n.show() if hud_on else n.hide()
        yaw = self.cam_h if self.cam_h is not None else self.cam_yaw
        span = 1180.0; z = 0.16; xmin, ymin = -470.0, -590.0
        from panda3d.core import TransformState, TextureStage
        ts = TransformState.make_pos2d(((px - xmin) / span, (py - ymin) / span)).compose(TransformState.make_rotate2d(yaw)).compose(
            TransformState.make_scale2d(z)).compose(TransformState.make_pos2d((-0.5, -0.5)))
        self.mm.set_tex_transform(TextureStage.get_default(), ts)
        M = self.mm_M; r = math.radians(yaw); cs, sn = math.cos(r), math.sin(r); k = 0
        def proj(x, y):
            dx, dy = x - px, y - py; return (dx * cs + dy * sn) / (span * z) * 2 * M, (-dx * sn + dy * cs) / (span * z) * 2 * M
        def dot(x, y, col, sz=0.01, clamp=False):
            nonlocal k
            if k >= len(self.mm_dots): return
            X, Y = proj(x, y)
            if abs(X) > M - 0.012 or abs(Y) > M - 0.012:
                if not clamp: return
                X = max(-M + 0.012, min(M - 0.012, X)); Y = max(-M + 0.012, min(M - 0.012, Y))
            d = self.mm_dots[k]; k += 1; d.show(); d.set_pos(X, 0, Y); d["frameColor"] = col; d["frameSize"] = (-sz, sz, -sz, sz)
        blink = int(self.time * 4) % 2
        for c in self.police: dot(c.x, c.y, (0.3, 0.45, 1.0, 1) if blink else (1, 0.25, 0.25, 1), 0.013, clamp=self.heat > 0)
        for c in self.cars:
            if c not in self.police and c is not self.pcar: dot(c.x, c.y, (0.65, 0.65, 0.7, 0.9), 0.006)
        for p in self.cops: dot(p.x, p.y, (0.35, 0.5, 1.0, 1), 0.006)
        for i in range(k, len(self.mm_dots)): self.mm_dots[i].hide()
        for m, ic in zip(self.markers + self.pois, self.mm_icons):
            X, Y = proj(m["x"], m["y"]); lim = M - 0.022
            if abs(X) > lim or abs(Y) > lim: s_ = lim / max(abs(X), abs(Y)); X *= s_; Y *= s_
            ic.setPos(X, Y - 0.011)
        self.pr_bar[1].set_sx(max(0.001, self.pressure / 100.0))
        self.stars_t.setText(("POLICE PURSUIT  " + "■" * self.heat + ("   BOXING YOU IN..." if self.bust_t > 0.6 else "")) if self.heat else "")
        self.stars_t["font"] = U.SYM
        c = self.pcar
        self.speed_t.setText("%d" % (c.speed * 3.6) if c else ""); self.kmh_t.setText("km/h" if c else "")
        self.radio_t.setText(("RADIO VALDORA FM: " + self.app.radio_name()) if c else "")
        me = self.me(); pr = ""
        if not self.blocked() and c is None:
            for cid, (cx, cy, kind, lbl) in CLUES.items():
                if cid not in self.evidence and self.stage >= 1 and math.hypot(cx - px, cy - py) < (3 if kind == "recover" else 9):
                    pr = "[E] RECOVER THE EMAILS" if kind == "recover" else "CLUE: take a photo with the phone CAMERA"
            if self.stage >= 2 and math.hypot(AIDE[0] - px, AIDE[1] - py) < 3.5 and "ev_recording" not in self.evidence: pr = "[E] INTERVIEW THE AIDE"
            if self.stage == 0 and math.hypot(px - PROTEST["c"][0], py - PROTEST["c"][1]) < 30: pr = "[E] JOIN THE PROTEST"
            if self.stage >= 4 and self.tip and math.hypot(self.tip[0] - px, self.tip[1] - py) < 12: pr = "TIP: take a photo with the phone CAMERA to post it"
            if not pr and any(math.hypot(o.x - me.x, o.y - me.y) < o.spec["hl"] + 2.3 for o in self.cars_near(me.x, me.y, 8)): pr = "[F] TAKE VEHICLE"
        self.prompt.setText(pr)
        self.refresh_buttons()

    # ------------------------------------------------------------------ simulation
    def update_police(self, dt):
        px, py = self.player_pos()
        if self.heat > 0:
            want = 1 + self.heat; self.heat_t -= dt
            if len([c for c in self.police if isinstance(c.ai, PoliceAI)]) < want and self.heat_t <= 0:
                self.heat_t = 3.0; x, y, h = self.offscreen_road_point(80, 150)
                c = self.spawn_car(random.choice(("police", "police", "policevan")), x, y, h, role="police")
                self.police.append(c); c.ai = PoliceAI(self, c); c.lights_on = True; c.driver = "ai"; c.asleep = False
            seen = any(isinstance(c.ai, PoliceAI) and c.ai.seen for c in self.police)
            if seen: self.escape_t = max(0.0, self.escape_t - dt * 2)
            else:
                self.escape_t += dt
                if self.escape_t > 6.0 + self.heat * 2.5: self.heat = 0; self.toast("You lost the police."); self.app.sfx("win", 0.5)
            close = sum(1 for c in self.police if c is not self.pcar and math.hypot(c.x - px, c.y - py) < 8.0)
            sp = self.pcar.speed if self.pcar else 0.0
            if close and sp < 3.0: self.bust_t += dt * (1 + 0.5 * close)
            else: self.bust_t = max(0.0, self.bust_t - dt)
            if self.bust_t > 2.8: self.warned("You were boxed in and stopped.")
        else:
            for c in list(self.police):
                if c is self.pcar: self.police.remove(c); continue
                c.lights_on = False
                if isinstance(c.ai, PoliceAI): c.ai = TrafficAI(self, c, self.world.nearest_node(c.x, c.y))
                if math.hypot(c.x - px, c.y - py) > 160: self.remove_car(c)

    def update_people(self, dt):
        threats = [c for c in self.cars if c.speed > 3]
        for p in list(self.peds):
            thr = None
            for c in threats:
                d = math.hypot(p.x - c.x, p.y - c.y)
                if d < 9: thr = (c.x, c.y)
                if d < 3.0:    # pedestrians dodge vehicles (side-step out of the way, nobody is hit)
                    f = c.fwd; side = 1 if (p.x - c.x) * f[1] - (p.y - c.y) * f[0] > 0 else -1
                    p.x += f[1] * side * 6 * dt; p.y -= f[0] * side * 6 * dt
            p.update(dt, thr)
        me = self.me()
        if self.pcar is None and me.in_car is None and self.cut is None:
            self.move_on_foot(me, dt)
            for c in threats:       # the player is never hit either: cars brake and push you aside gently
                for cx, cy, r, _ in c.circles():
                    dx, dy = me.x - cx, me.y - cy; d = math.hypot(dx, dy)
                    if 1e-3 < d < r + 0.45: me.x += dx / d * (r + 0.45 - d); me.y += dy / d * (r + 0.45 - d)
        t = self.time; beat = t * 104 / 60.0 * math.pi
        for p in self.near:   # near-LOD protesters: chant on the beat, raise placards, cheer
            ch = getattr(p, "cheer", 0.0); p.cheer = max(0.0, ch - dt)
            a = -150 if ch > 0 else (-95 + 25 * math.sin(beat + p.beat))
            p.set_arms((a, 8), (-20 + 10 * math.sin(beat), 4), (-20, 0), (-30, 0)); p.model.set_z(0.04 * max(0, math.sin(beat * (2 if ch else 1) + p.beat)))
        for p in self.cops:
            if getattr(p, "patrol", False):
                p.ph = getattr(p, "ph", random.uniform(0, 6)) + dt * 0.25
                tx, ty = p.post[0] + math.cos(p.ph) * 8, p.post[1] + math.sin(p.ph) * 3
                dx, dy = tx - p.x, ty - p.y; d = math.hypot(dx, dy)
                if d > 0.2: p.x += dx / d * 1.2 * dt; p.y += dy / d * 1.2 * dt; p.h += wrap(math.degrees(math.atan2(-dx, dy)) - p.h) * min(1, dt * 5)
                p.walk_anim(dt, 1.2); p.sync()
        # restricted areas: officers question you (pressure up) and send you back
        self.question_cd -= dt
        if self.pcar is None:
            for x0, y0, x1, y1, nm in RESTRICTED:
                if x0 <= me.x <= x1 and y0 <= me.y <= y1 and self.question_cd <= 0:
                    self.question_cd = 6.0; cop = min(self.cops, key=lambda c: math.hypot(c.x - me.x, c.y - me.y))
                    line = "Stați! Zonă restricționată. Actele, vă rog."
                    self.bubble(cop, line); self.speak(line, cop); self.subtitle("POLICE: Stop! Restricted area. Your papers, please.", 4)
                    self.add_pressure(12, "Questioned by police at the %s" % nm); me.y -= 3.5; me.sync()

    def update_audio_local(self, dt):
        x, y = self.player_pos(); d = math.hypot(x - PROTEST["c"][0], y - PROTEST["c"][1])
        sw = min(1.0, self.swell / 10.0)        # rallies / PUBLISH: the chant swells and carries further
        v = max(0.0, min(1.0, 1.15 + 0.35 * sw - d / (140.0 + 160.0 * sw))) * self.app.vol("sfx_volume") * (0.0 if self.paused else 1.0)
        self.chant.set_volume(v)
        p = self.app.cam.get_relative_point(self.app.render, Point3(PROTEST["c"][0], PROTEST["c"][1], 2))
        self.chant.set_balance(max(-0.8, min(0.8, p.x / max(5.0, abs(p.y) + 5))))
        if self.chant.status() != AudioSound.PLAYING: self.chant.play()
        if self.cut is None and not self.pcar:
            want = "protest" if d < 70 else ("investigation" if self.stage in (1, 2) else "city")
            if self.app.cur_music != want and self.app.cur_music not in ("credits",): self.app.play_music(want)

    def step(self, dt):
        self.time += dt
        if self.cut: self.update_cut(dt)
        else: self.control_player(dt)
        px, py = self.player_pos()
        for c in self.cars:
            if c.ai is not None and not c.dead:
                if math.hypot(c.x - px, c.y - py) < 260: c.ai.update(dt)
                else: c.throttle = 0
        for c in list(self.cars): c.step(dt)
        collide_cars(self.cars, self)
        for c in self.cars: c.sync(dt)
        self.update_people(dt); self.update_police(dt); self.signals.update(dt)
        self.pop_t -= dt
        if self.pop_t <= 0:
            self.pop_t = 0.5; self.populate()
            for c in list(self.cars):     # the protest crossing is closed to traffic
                if abs(c.x) < 50 and abs(c.y) < 50 and c is not self.pcar and not getattr(c, "static_cop", False) and c not in self.police: self.remove_car(c)
        self.world.update(dt, self.time)
        if not self.cut: self.update_camera(dt)
        self.update_camapp(dt); self.update_hud(dt); self.update_audio_local(dt); self.app.update_audio(self, dt)
        self.update_tts(); self.poll_tts(); self.update_side(dt)
        self.pressure = max(0.0, self.pressure - dt * 0.15)
        self.save_t = getattr(self, "save_t", 30.0) - dt
        if self.save_t <= 0: self.save_t = 30.0; self.save()

    def on_impact(self, car, imp, other):
        if car is self.pcar or other is self.pcar:
            self.shake = min(1.0, self.shake + imp / 25.0); self.app.sfx("crash" if imp > 9 else "bump", min(1.0, imp / 18.0))
            if other is not None and imp > 5 and (other.kind in ("police", "policevan") or car.kind in ("police", "policevan")): self.add_heat(1)

    def on_car_water(self, car):
        if car is self.pcar:
            car.x, car.y, car.h = D.BEACH_ROAD_X - 3, max(-380, min(380, car.y)), 0; car.vx = car.vy = car.w = 0; self.cam_pos = None

    def say_line(self, p, group=None): pass

    # ------------------------------------------------------------------ persistence
    def save(self):
        me = self.me()
        d = {"stage": self.stage, "evidence": self.evidence, "pressure": round(self.pressure, 1), "chat": self.chat_hist[-8:], "photos": self.photos[-50:],
             "msgs": self.msgs, "published": self.published, "posts": self.posts, "news": [list(n) for n in self.news],
             "tip": list(self.tip) if self.tip else None, "rally_t": round(self.rally_t, 1), "pos": [round(me.x, 2), round(me.y, 2), round(me.h, 1)] if self.pcar is None and self.cut is None else list(SPAWN),
             "version": self.app.VERSION}
        try: self.app.write_save(d)
        except Exception as e: self.app.log_error(e)

    def destroy(self):
        self.save(); self.app.task_mgr.remove("game-update"); self.unbind(); self.signals.destroy(); self.chant.stop()
        self._ds_end() if getattr(self, "_ds", None) else None
        for c in list(self.cars): c.destroy()
        for p in self.peds + self.near + self.cops + list(self.chars.values()) + getattr(self, "cut_people", []): p.destroy()
        for n in (self.scene, self.crowd, self.crowd2, self.hud, self.mm_root, self.lb_top, self.lb_bot, self.fade_np): n.remove_node()
        for o in [self.overlay, self.phone, self.board, self.chat, self._mmf, self.pr_bar[0]] + self.btn_nodes:
            if o: o.destroy()
        for t in (self.obj_t, self.stars_t, self.speed_t, self.kmh_t, self.radio_t, self.prompt, self.sub, self.sub_en, self.toast_t, self.cap1, self.cap2, self.dist_lbl) + tuple(self.mm_icons):
            t.destroy()
