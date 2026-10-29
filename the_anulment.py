"""THE ANULMENT - an original story game set in the fictional country of Valdora.
(c)2026 EX Inc./HYPERION DIGITAL (c)2026. All characters, parties, countries and events in this game are fictional."""
import os, sys, json, time, math, random, threading, tempfile, urllib.request, shutil, traceback

APP_NAME = "THE ANULMENT"
APP_VERSION = "1.0.0"
REPO = "Teobokki/the-anulment"
UPDATE_URL = "https://raw.githubusercontent.com/%s/main/latest.json" % REPO
RELEASES_URL = "https://github.com/%s/releases/latest" % REPO
COPYRIGHT = "\u00a92026 EX Inc./HYPERION DIGITAL \u00a92026"
PUBLISHER = "EX Inc./HYPERION DIGITAL"

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("FS_DATA_DIR"):
    DATA = os.environ["FS_DATA_DIR"]
elif os.name == "nt":
    DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
else:
    DATA = os.path.join(os.path.expanduser("~"), ".the-anulment")
os.makedirs(DATA, exist_ok=True)


def log_error(msg):
    if isinstance(msg, BaseException): msg = "".join(traceback.format_exception(type(msg), msg, msg.__traceback__))
    try:
        with open(os.path.join(DATA, "error.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg) + "\n")
    except Exception:
        pass


from panda3d.core import loadPrcFileData, Filename
_icon = os.path.join(BASE, "assets", "icon.ico")
loadPrcFileData("", """
window-title THE ANULMENT
win-size 1280 720
sync-video true
audio-library-name p3openal_audio
textures-power-2 none
framebuffer-multisample 0
notify-level warning
default-directnotify-level warning
load-display pandagl
want-pstats false
gl-coordinate-system default
""")
if os.environ.get("AN_NOAUDIO"):        # headless test machines without a sound device
    loadPrcFileData("", "audio-library-name null")
if os.environ.get("FS_WINSIZE"):       # test/QA override, e.g. FS_WINSIZE=1920x1080
    loadPrcFileData("", "win-size " + os.environ["FS_WINSIZE"].replace("x", " "))
if os.path.exists(_icon):
    loadPrcFileData("", "icon-filename " + Filename.from_os_specific(_icon).get_fullpath())

from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectFrame, DirectSlider, DirectButton, DGG
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui import DirectGuiGlobals
from panda3d.core import (TextNode, TransparencyAttrib, WindowProperties, PTA_LVecBase3f, Texture, PNMImage, SamplerState,
                          AudioSound, CardMaker, Fog, Vec3, TextureStage, ColorBlendAttrib, InputDevice)
import fs_ui as U
import fs_data as D
from fs_world import World


def vtuple(v):
    out = []
    for p in str(v).strip().lstrip("vV").split("."):
        n = "".join(ch for ch in p if ch.isdigit())
        out.append(int(n) if n else 0)
    return tuple((out + [0] * 4)[:4])          # always 4 parts: 1.0.5 == 1.0.5.0 < 1.0.5.1 < 1.0.5.2


def clean_env():
    """Environment for processes we start (Setup, update helper, relaunch). A PyInstaller onefile parent exports
    _PYI_* / _MEIPASS2; a relaunched copy that inherits them reuses the old _MEI folder (old code keeps running and
    Windows shows 'Failed to remove temporary directory'). Strip them and ask the child bootloader to start fresh."""
    env = {k: v for k, v in os.environ.items() if not (k.upper().startswith("_PYI") or k.upper().startswith("_MEIPASS")
                                                        or k.upper() in ("TCL_LIBRARY", "TK_LIBRARY"))}
    mei = getattr(sys, "_MEIPASS", None)
    if mei and "PATH" in env:
        env["PATH"] = os.pathsep.join(x for x in env["PATH"].split(os.pathsep) if not os.path.normcase(x).startswith(os.path.normcase(mei)))
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def is_portable():
    if not getattr(sys, "frozen", False) or not hasattr(sys, "_MEIPASS"):
        return False
    exe = os.path.normcase(os.path.abspath(sys.executable))
    meipass = os.path.normcase(os.path.abspath(sys._MEIPASS))
    if meipass.startswith(os.path.dirname(exe) + os.sep):
        return False
    la = os.environ.get("LOCALAPPDATA")
    if la and exe.startswith(os.path.normcase(os.path.join(la, "Programs", APP_NAME)) + os.sep):
        return False
    return True


def check_update():
    req = urllib.request.Request(UPDATE_URL + "?t=%d" % time.time(), headers={"User-Agent": "THE-ANULMENT/" + APP_VERSION})
    m = json.loads(urllib.request.urlopen(req, timeout=10).read(65536).decode("utf-8"))
    ver = str(m["version"])
    if vtuple(ver) > vtuple(APP_VERSION):
        if is_portable() and m.get("portable_url"):
            return "newer", {"version": ver, "notes": m.get("notes", ""), "link": m["portable_url"], "portable": True}
        return "newer", {"version": ver, "notes": m.get("notes", ""), "link": m.get("installer_url") or m.get("url") or RELEASES_URL}
    return "latest", "You have the latest version (%s)." % APP_VERSION



DEFAULT_SETTINGS = {"traffic": "normal", "master": 0.9, "sfx_volume": 0.8, "music_volume": 0.55, "voice_volume": 0.9, "quality": 1, "rain": True,
                    "buttons": True, "subtitles": True, "fullscreen": False}
FICTION = "All characters, parties, countries and events in this game are fictional."
CREDITS = [
    ("THE ANULMENT", None),
    ("Published by", PUBLISHER),
    ("Starring", "MIYOYAZU"),
    ("Story, design, code, city, vehicles & characters", "EX Inc. - original procedural and scripted assets"),
    ("Engine", "Panda3D (Modified BSD licence)"),
    ("Voice (offline TTS)", "Piper (MIT) - Romanian voice ro_RO-mihai-medium (CC0)"),
    ("Music", "Original score and choir by EX Inc., rendered with FluidSynth + FluidR3_GM SoundFont (MIT)"),
    ("Fonts", "Exo 2 (SIL Open Font License) - DejaVu Sans (Bitstream Vera / DejaVu licence)"),
    (FICTION, None),
    (COPYRIGHT, None),
]
MUSIC = ("title", "city", "investigation", "protest", "family", "finale", "credits")


class App(ShowBase):
    VERSION = APP_VERSION
    BASE = BASE

    def __init__(self):
        ShowBase.__init__(self)
        self.disable_mouse()
        self.log_error = log_error
        self.settings = dict(DEFAULT_SETTINGS)
        try: self.settings.update(json.load(open(os.path.join(DATA, "settings.json"), encoding="utf-8")))
        except Exception: pass
        A = lambda *p: os.path.join(BASE, "assets", *p)
        self.jpfont = U.init_fonts(self.loader, A("ui_font.ttf"), A("ui_plain.ttf"), A("sym_font.ttf"))
        U.SYM = U.JP = self.jpfont
        U.SFX = lambda n: self.sfx(n, 0.5)
        DirectGuiGlobals.setDefaultClickSound(None); DirectGuiGlobals.setDefaultRolloverSound(None)
        DirectGuiGlobals.setDefaultFont(U.FONT_PLAIN) if U.FONT_PLAIN else None
        self.set_background_color(0.02, 0.025, 0.04, 1)
        self.camLens.set_fov(70); self.camLens.set_near_far(0.2, 2400)
        self.campos = PTA_LVecBase3f.empty_array(1); self.campos_np = self.campos
        self.fogcol = Vec3(0.04, 0.05, 0.07); self.fogden = 0.0036
        self.envtex = self.loader.load_texture(Filename.from_os_specific(A("tex", "env.png")))
        img = PNMImage(4, 4, 3); img.fill(0.5, 0.5, 1.0)
        self.flat_nmap = Texture("flatn"); self.flat_nmap.load(img)
        self.render.set_shader_input("dayk", 0.0); self.render.set_shader_input("fogday", Vec3(0.68, 0.79, 0.90))
        self.render.set_shader_input("sundir", Vec3(0.35, -0.45, 0.82))
        self.envday = self.loader.load_texture(Filename.from_os_specific(A("tex", "sky_day.jpg"))); self.render.set_shader_input("envday", self.envday)
        fog = Fog("fog"); fog.set_color(self.fogcol); fog.set_exp_density(self.fogden); self.render.set_fog(fog); self.fog = fog
        self._sfx = {}
        for n in ("engine", "engine_low", "siren", "skid", "wind", "rain", "crash", "bump", "checkpoint", "beep", "go", "click",
                  "busted", "win", "heat", "horn", "door", "switch", "dial", "empty", "cheer"):
            try: self._sfx[n] = self.loader.load_sfx(Filename.from_os_specific(A("sfx", n + ".wav")))
            except Exception: pass
        self.loops = {}
        for n in ("engine", "engine_low", "siren", "skid", "wind", "rain"):
            try:
                s = self.loader.load_sfx(Filename.from_os_specific(A("sfx", n + ".wav"))); s.set_loop(True); s.set_volume(0); self.loops[n] = s
            except Exception: pass
        self.music = {}
        for n in MUSIC:
            try:
                s = self.loader.load_music(Filename.from_os_specific(A("music", n + ".ogg"))); s.set_loop(True); self.music[n] = s
            except Exception as e: log_error(e)
        self.cur_music = None; self._voices = {}; self.radio_k = 0
        from an_tts import TTS
        self.tts = TTS(BASE, log_error)
        self.tex_start = self.loader.load_texture(Filename.from_os_specific(A("start.jpg")))
        self.game = None; self.screen = None; self.overlay = None; self.pause_ui = None; self._upd_result = None
        self.flyover = False; self.fly_t = 0.0; self.stage = None
        self.pad = None; self._setup_gamepad()
        self.apply_fullscreen()
        self.exitFunc = self.on_exit
        self.accept("window-event", self._on_window_event)
        self.filters = None; self.world = None
        self.task_mgr.add(self._frame, "app-frame", sort=50)
        self.show_loading()
        ts = os.environ.get("FS_TESTSCRIPT")
        if ts and not getattr(sys, "frozen", False):
            self.do_method_later(float(os.environ.get("FS_TESTDELAY", "1")),
                                 lambda t: exec(open(ts).read(), {"app": self, "__name__": "fstest"}) or t.done, "fs-test")

    def vol(self, kind):
        return float(self.settings.get("master", 0.9)) * float(self.settings.get(kind, 0.8))

    def sfx(self, name, vol=1.0):
        s = self._sfx.get(name)
        if s:
            s.set_volume(vol * self.vol("sfx_volume")); s.play()

    def voice(self, fn, vol=1.0):
        try:
            s = self._voices.get(fn)
            if s is None:
                p = os.path.join(BASE, "assets", "voice", fn)
                if not os.path.exists(p): return
                s = self._voices[fn] = self.loader.load_sfx(Filename.from_os_specific(p))
            s.set_volume(vol * self.vol("voice_volume")); s.play()
        except Exception as e:
            log_error(e)

    def play_music(self, name):
        if self.cur_music == name: return
        for k, s in self.music.items():
            if k != name: s.stop()
        s = self.music.get(name); self.cur_music = name
        if s:
            s.set_volume(self.vol("music_volume") * 0.6); s.play()
    def save_path(self):
        return os.path.join(DATA, "save.json")

    def has_save(self):
        return os.path.exists(self.save_path())

    def write_save(self, d):
        p = self.save_path(); tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f, indent=1, ensure_ascii=False)
        os.replace(tmp, p)

    def load_save(self):
        try: return json.load(open(self.save_path(), encoding="utf-8"))
        except Exception: return None

    def save_settings(self):
        try:
            json.dump(self.settings, open(os.path.join(DATA, "settings.json"), "w", encoding="utf-8"), indent=1)
        except Exception as e:
            log_error("settings: %r" % e)

    def apply_fullscreen(self):
        wp = WindowProperties()
        if self.settings.get("fullscreen"):
            wp.set_fullscreen(True); wp.set_size(self.pipe.get_display_width(), self.pipe.get_display_height())
        else:
            wp.set_fullscreen(False); wp.set_size(1280, 720)
        if self.win and hasattr(self.win, "request_properties"):
            self.win.request_properties(wp)

    def rain_on(self, on):
        if on and getattr(self, "rain_np", None) is None:
            cm = CardMaker("rain"); cm.set_frame(-2, 2, -1, 1)
            n = self.render2d.attach_new_node(cm.generate()); n.set_transparency(TransparencyAttrib.M_alpha)
            t = self.loader.load_texture(Filename.from_os_specific(os.path.join(BASE, "assets", "tex", "streak.png")))
            n.set_texture(t); n.set_tex_scale(TextureStage.get_default(), 9, 3); n.set_color(0.7, 0.8, 1.0, 0.18); n.set_bin("fixed", 5)
            n.set_attrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one))
            self.rain_np = n
        elif not on and getattr(self, "rain_np", None) is not None:
            self.rain_np.remove_node(); self.rain_np = None

    def _setup_gamepad(self):
        try:
            devs = self.devices.get_devices(InputDevice.DeviceClass.gamepad)
            if devs:
                self.gp = devs[0]; self.attach_input_device(self.gp, prefix="gp")
                self.pad = {}
                for b, k in (("gp-face_a", "f"), ("gp-face_b", "h"), ("gp-face_y", "c"), ("gp-back", "r"), ("gp-start", "escape"),
                             ("gp-face_x", "e"), ("gp-lshoulder", "q"), ("gp-dpad_up", "t")):
                    self.accept(b, lambda k=k: messenger.send(k))
        except Exception as e:
            log_error("gamepad: %r" % e)

    def _poll_pad(self):
        gp = getattr(self, "gp", None)
        if gp is None or self.pad is None: return
        try:
            def ax(a):
                v = gp.find_axis(a); return v.value if v else 0.0
            self.pad["lx"] = ax(InputDevice.Axis.left_x)
            self.pad["rt"] = max(0.0, ax(InputDevice.Axis.right_trigger)); self.pad["lt"] = max(0.0, ax(InputDevice.Axis.left_trigger))
            if self.game:
                self.game.vb["v_hand"] = gp.find_button("rshoulder").pressed
                self.game.vb["v_nitro"] = gp.find_button("face_x").pressed if False else gp.find_button("rstick").pressed
        except Exception:
            pass

    def _on_window_event(self, win):
        if win and win.is_closed():
            self.userExit()

    def on_exit(self):
        if self.game:
            try: self.game.save()
            except Exception as e: log_error("save on exit: %r" % e)

    def clear_screen(self):
        if self.screen:
            self.screen.destroy(); self.screen = None

    def new_screen(self, dim=0.0):
        self.clear_screen()
        self.screen = DirectFrame(parent=self.aspect2d, frameColor=(0, 0, 0, dim), frameSize=(-4, 4, -2, 2))
        return self.screen

    # ---------------------------------------------------------------- boot: splash -> intro flyover -> title
    def _img(self, parent, name, pos=(0, 0), scale=(1, 1), alpha=True):
        im = OnscreenImage(parent=parent, image=Filename.from_os_specific(os.path.join(BASE, "assets", *name.split("/"))).get_fullpath(),
                           pos=(pos[0], 0, pos[1]), scale=(scale[0], 1, scale[1]))
        if alpha: im.set_transparency(TransparencyAttrib.M_alpha)
        return im


    def radio(self, on):
        pass

    def radio_next(self):
        opts = ("city", "investigation", "protest", "family"); self.radio_k = (self.radio_k + 1) % len(opts); self.play_music(opts[self.radio_k])

    def radio_name(self):
        return {"city": "Valdora Nights", "investigation": "The Paper Trail", "protest": "Turul Doi", "family": "Elena", "finale": "The People's Vote",
                "credits": "Anulment (Credits)", "title": "Anulment"}.get(self.cur_music, "")

    def update_audio(self, game, dt):
        L = self.loops; sv = self.vol("sfx_volume")
        c = game.pcar if game else None
        paused = game is None or game.paused
        if c and not paused:
            sp = c.speed; r = min(1.0, sp / 60.0)
            L.get("engine") and (L["engine"].set_volume(sv * (0.25 + 0.35 * r)), L["engine"].set_play_rate(0.6 + 1.2 * r + 0.2 * abs(c.throttle)))
            L.get("engine_low") and L["engine_low"].set_volume(sv * 0.25 * (1 - r))
            L.get("skid") and L["skid"].set_volume(sv * min(0.6, max(0.0, c.drift - 3.0) * 0.08))
            L.get("wind") and L["wind"].set_volume(sv * r * 0.35)
        else:
            for n in ("engine", "engine_low", "skid", "wind"):
                if n in L: L[n].set_volume(0)
        siren = 0.0
        if game and not paused and game.police and game.heat:
            px, py = game.player_pos(); d = min(math.hypot(p.x - px, p.y - py) for p in game.police); siren = max(0.0, 1.0 - d / 140.0)
        if "siren" in L: L["siren"].set_volume(sv * 0.35 * siren)
        if "rain" in L: L["rain"].set_volume(sv * 0.4 if self.settings.get("rain") and (game is None or not paused) else 0)
        for s in L.values():
            if s.status() != AudioSound.PLAYING: s.play()

    def set_night(self):
        try:
            if self.world is not None: self.world.set_daylight(0.0, 0.0)
        except Exception as e: log_error(e)
        self.render.set_shader_input("dayk", 0.0); self.fog.set_color(self.fogcol); self.set_background_color(0.02, 0.025, 0.04, 1)

    def apply_quality(self):
        self.rain_on(bool(self.settings.get("rain", True)))      # no bloom / glow at any quality

    def _frame(self, task):
        cam = self.camera.get_pos(self.render); self.campos.set_element(0, cam)
        if getattr(self, "rain_np", None) is not None:
            self.rain_np.set_tex_offset(TextureStage.get_default(), 0.15 * task.time, 2.2 * task.time)
        self._poll_pad()
        if self.flyover and self.world is not None and self.game is None:
            dt = min(0.05, self.clock.get_dt()); self.fly_t += dt
            self.world.update(dt, self.fly_t); self.update_audio(None, dt)
        return task.cont

    # ---------------------------------------------------------------- boot: loading -> title (the start image) -> menu
    def show_loading(self):
        s = self.new_screen(1.0); self.cover(s)
        U.text(s, "Loading Valdora...", (0, -0.9), 0.045, font=U.FONT_PLAIN)
        def load(task):
            if task.frame < 2: return task.cont
            try: self.world = World(self, int(self.settings.get("quality", 1)))
            except Exception: log_error(traceback.format_exc()); raise
            self.set_night(); self.apply_quality(); self.show_title(); return task.done
        self.task_mgr.add(load, "load-world")

    def cover(self, parent, dim=0.0):
        """the start image, cover-scaled (never stretched); vertical offset keeps the title text and the arrested man's face in view"""
        ar = max(self.getAspectRatio(), 0.5); half = max(ar, 1.0) * 1.0          # square image: width == height
        h = max(ar, 1.0)                                                          # half-height so it covers the full width
        z = (h - 1.0) * 0.55 if h > 1 else 0.0                                     # shift down -> shows image rows ~0.10..0.66 at 16:9
        im = OnscreenImage(parent=parent, image=self.tex_start, pos=(0, 0, -z + 0.0), scale=(h, 1, h))
        im.set_bin("background", 0); im.set_depth_write(False)
        if dim: DirectFrame(parent=parent, frameColor=(0, 0, 0, dim), frameSize=(-ar - 1, ar + 1, -1.2, 1.2))
        return im

    def footer(self, s):
        ar = max(self.getAspectRatio(), 1.0)
        DirectFrame(parent=s, frameColor=(0, 0, 0, 0.72), frameSize=(-ar - 1, ar + 1, -1.2, -0.885))
        U.text(s, COPYRIGHT, (0, -0.935), 0.036, font=U.FONT_PLAIN)
        U.text(s, FICTION, (0, -0.975), 0.024, fg=(1, 1, 1, 0.75), font=U.FONT_PLAIN)
        U.text(s, "v" + APP_VERSION, (-ar + 0.03, -0.955), 0.03, (1, 1, 1, 0.7), TextNode.A_left, font=U.FONT_PLAIN)

    def show_title(self):
        s = self.new_screen(0.0); self.flyover = False; self.play_music("title"); self.cover(s); self.footer(s)
        b = U.button(s, "PRESS START", (0, -0.78), self.show_menu, w=0.3, h=0.055, col=(0.06, 0.07, 0.1, 0.9), edge=U.PINK, scale=0.05)
        self._pp = b
        self.task_mgr.add(self._pulse, "pp-pulse")
        self.buttonThrowers and self.buttonThrowers[0].node().set_button_down_event("fs-anykey")
        self.accept("fs-anykey", self._anykey)

    def _anykey(self, btn):
        if btn.startswith("mouse") or btn.startswith("wheel"): return
        self.show_menu()

    def _pulse(self, task):
        if not getattr(self, "_pp", None) or self._pp.is_empty(): return task.done
        self._pp.set_scale(1 + 0.04 * math.sin(task.time * 4))
        return task.cont

    def show_menu(self):
        """menu in a side panel over the flags (right), clear of the arrested man's face in the centre"""
        self.ignore("fs-anykey"); self._pp = None; self.task_mgr.remove("pp-pulse"); self.play_music("title")
        s = self.new_screen(0.0); self.cover(s); self.footer(s)
        ar = max(self.getAspectRatio(), 1.0); x = ar - 0.36
        U.panel(s, -0.3, 0.3, -0.42, 0.42, pos=(x, -0.4), col=(0.03, 0.035, 0.05, 0.82), edge=U.PINK)
        has = self.has_save()
        items = [("NEW GAME", self.new_game, U.PINK)]
        items.append(("CONTINUE", lambda: self.start_game(), U.PINK) if has else ("CONTINUE", None, (0.4, 0.4, 0.4, 1)))
        items += [("SETTINGS", lambda: self.open_settings(self.show_menu), U.CYAN), ("UPDATES", self.start_update_check, U.CYAN),
                  ("CREDITS", self.show_credits, U.CYAN), ("QUIT", self.userExit, (0.85, 0.3, 0.3, 1))]
        for i, (t, c, col) in enumerate(items):
            U.button(s, t, (x, -0.1 - i * 0.12), c, w=0.25, h=0.045, edge=col, scale=0.038, enabled=c is not None)
        self.accept("escape", self.show_title)

    def new_game(self, force=False):
        if self.has_save() and not force:
            self._dialog("Start a new game?\nYour current save will be replaced.", [("NEW GAME", lambda: (self._close_dialog(), self.new_game(True))), ("CANCEL", self._close_dialog)])
            return
        try:
            if os.path.exists(self.save_path()): shutil.copy(self.save_path(), self.save_path() + ".bak"); os.remove(self.save_path())
        except Exception: pass
        self.start_game()

    def show_credits(self, end=False):
        o = DirectFrame(parent=self.aspect2d, frameColor=(0, 0, 0, 0.88), frameSize=(-4, 4, -2, 2), state=DGG.NORMAL)
        U.panel(o, -1.2, 1.2, -0.9, 0.9)
        U.text(o, "THE END - CHAPTER 1" if end else "CREDITS", (0, 0.78), 0.07, fg=U.PINK)
        z = 0.64
        for a, b in CREDITS:
            U.text(o, a, (0, z), 0.036, fg=U.CYAN if b else (1, 1, 1, 1)); z -= 0.055
            if b: U.text(o, b, (0, z), 0.03, font=U.FONT_PLAIN, wrap=70); z -= 0.075
        if end:
            U.text(o, "More chapters are coming in a future update. Free roam continues.", (0, z - 0.02), 0.032, font=U.FONT_PLAIN, fg=U.GOLD)
            self.play_music("credits")
        U.button(o, "CONTINUE" if end else "BACK", (0, -0.82), o.destroy, w=0.2, h=0.045, scale=0.04)

    def start_game(self):
        self.task_mgr.remove("pp-pulse"); self.ignore("fs-anykey")
        s = self.new_screen(1.0); self.cover(s, 0.6)
        U.text(s, "Valdora, the night after the annulment...", (0, 0.05), 0.06, fg=U.PINK)
        U.text(s, "WASD move / drive   F take a vehicle   E interact   T talk   P phone   M map   B evidence board   Esc menu", (0, -0.1), 0.034, font=U.FONT_PLAIN)
        save = self.load_save()
        def go(task):
            from an_game import Game
            self.flyover = False
            try: self.game = Game(self, save)
            except Exception: log_error(traceback.format_exc()); raise
            self.clear_screen(); self.play_music("city")
            return task.done
        self.do_method_later(0.15, go, "start-game")

    def quit_to_title(self):
        self.hide_pause()
        if self.game: self.game.destroy(); self.game = None
        self.camLens.set_fov(70); self.show_title()

    def show_pause(self):
        if not self.game or self.pause_ui: return
        g = self.game; g.paused = True
        o = self.pause_ui = DirectFrame(parent=self.aspect2d, frameColor=(0, 0, 0, 0.6), frameSize=(-4, 4, -2, 2), state=DGG.NORMAL)
        U.panel(o, -0.45, 0.45, -0.7, 0.62)
        U.text(o, "PAUSED", (0, 0.5), 0.08, fg=U.PINK)
        items = (("RESUME", self.hide_pause), ("MAP", lambda: (self.hide_pause(), g.toggle_map())), ("SAVE", lambda: (g.save(), g.toast("Game saved"))),
                 ("SETTINGS", lambda: self.open_settings(None)), ("CONTROLS", self.show_controls),
                 ("SAVE & QUIT TO TITLE", self.quit_to_title), ("QUIT GAME", self.userExit))
        for i, (t, c) in enumerate(items):
            U.button(o, t, (0, 0.36 - i * 0.13), c, w=0.33, h=0.046, scale=0.038)
        self.accept("escape", self.hide_pause)

    def hide_pause(self):
        if self.pause_ui: self.pause_ui.destroy(); self.pause_ui = None
        if self.game: self.game.paused = False; self.accept("escape", self.game._guard(self.game.key_esc, "escape"))

    def show_controls(self):
        o = DirectFrame(parent=self.aspect2d, frameColor=(0, 0, 0, 0.8), frameSize=(-4, 4, -2, 2), state=DGG.NORMAL)
        U.panel(o, -1.0, 1.0, -0.8, 0.8)
        U.text(o, "CONTROLS", (0, 0.68), 0.07, fg=U.PINK)
        rows = [("W A S D / Arrows", "Walk / drive"), ("Shift", "Run"), ("Space", "Handbrake"), ("F", "Take any vehicle (non-violently) / get out"),
                ("E", "Interact, recover evidence, interview"), ("T  (or CHAT)", "Type English - MIYOYAZU says it (Romanian voice)"),
                ("P", "EX IX G10 phone: CAMERA, MESSAGES, NEWS, MAP, EVIDENCE, RECORDER, SETTINGS"), ("B", "Evidence board"),
                ("M", "Full map (click: waypoint)"), ("C / R / H / L", "Camera view / reset car / horn / lights"), ("Esc", "Menu, close, cancel chat")]
        for k, (a, b) in enumerate(rows):
            U.text(o, a, (-0.3, 0.55 - k * 0.1), 0.034, fg=U.CYAN, align=TextNode.A_right)
            U.text(o, b, (-0.25, 0.55 - k * 0.1), 0.031, align=TextNode.A_left, font=U.FONT_PLAIN)
        U.button(o, "BACK", (0, -0.72), o.destroy, w=0.2, h=0.045, scale=0.04)

    def open_settings(self, back):
        o = DirectFrame(parent=self.aspect2d, frameColor=(0, 0, 0, 0.75), frameSize=(-4, 4, -2, 2), state=DGG.NORMAL)
        U.panel(o, -0.95, 0.95, -0.8, 0.8)
        U.text(o, "SETTINGS", (0, 0.68), 0.07, fg=U.PINK)
        st = self.settings
        def slider(label, key, z):
            t = U.text(o, "", (-0.45, z - 0.012), 0.038, align=TextNode.A_right, font=U.FONT_PLAIN)
            def upd():
                st[key] = round(float(sl["value"]), 2); t.setText("%s  %d%%" % (label, round(st[key] * 100)))
                if self.cur_music and self.cur_music in self.music: self.music[self.cur_music].set_volume(self.vol("music_volume") * 0.6)
            sl = DirectSlider(parent=o, range=(0, 1), value=st.get(key, 0.8), pageSize=0.05, scale=0.38, pos=(0.0, 0, z),
                              frameColor=(0.2, 0.22, 0.28, 1), thumb_frameColor=U.PINK, command=upd)
            upd()
        slider("Master volume", "master", 0.52); slider("Effects", "sfx_volume", 0.42); slider("Music", "music_volume", 0.32); slider("Voice", "voice_volume", 0.22)
        def cyc(label, key, opts, z, after=None):
            def f():
                vals = [v for v, _ in opts]; st[key] = vals[(vals.index(st.get(key, vals[0])) + 1) % len(vals)] if st.get(key) in vals else vals[0]
                b.btn["text"] = "%s: %s" % (label, dict(opts)[st[key]])
                if after: after()
            b = U.button(o, "%s: %s" % (label, dict(opts).get(st.get(key), opts[0][1])), (0, z), f, w=0.45, h=0.042, scale=0.036)
        onoff = [(True, "ON"), (False, "OFF")]
        cyc("Rain", "rain", onoff, 0.08, self.apply_quality)
        cyc("Subtitles", "subtitles", onoff, -0.03)
        cyc("On-screen buttons", "buttons", onoff, -0.14, lambda: self.game and (setattr(self.game, "btn_state", None), self.game.refresh_buttons()))
        cyc("Fullscreen", "fullscreen", onoff, -0.25, self.apply_fullscreen)
        cyc("Traffic density", "traffic", [("low", "LOW"), ("normal", "NORMAL"), ("high", "HIGH")], -0.36)
        cyc("Graphics quality (restart)", "quality", [(0, "LOW"), (1, "MEDIUM"), (2, "HIGH")], -0.47)
        def done():
            self.save_settings(); o.destroy()
            if back: back()
        U.button(o, "DONE", (0, -0.68), done, w=0.2, h=0.05, scale=0.042, edge=U.CYAN)

    def _dialog(self, msg, buttons):
        self._close_dialog()
        o = self.overlay = DirectFrame(parent=self.aspect2d, frameColor=(0, 0, 0, 0.6), frameSize=(-4, 4, -2, 2), state=DGG.NORMAL)
        U.panel(o, -0.9, 0.9, -0.38, 0.38)
        U.text(o, msg, (0, 0.2), 0.045, wrap=34, font=U.FONT_PLAIN)
        n = len(buttons)
        for i, (t, c) in enumerate(buttons):
            U.button(o, t, ((i - (n - 1) / 2) * 0.62, -0.25), c, w=0.28, h=0.05, scale=0.036)

    def _close_dialog(self):
        if self.overlay:
            self.overlay.destroy(); self.overlay = None

    def start_update_check(self):
        self._dialog("Checking for updates...", [])
        def work():
            try: self._upd_result = check_update()
            except Exception as e: self._upd_result = ("error", "Could not check for updates.\n(%s)" % (str(e)[:90]))
        threading.Thread(target=work, daemon=True).start()
        self.task_mgr.add(self._poll_update, "poll-update")

    def _poll_update(self, task):
        r = self._upd_result
        if r is None: return task.cont
        self._upd_result = None
        kind, data = r
        if kind == "newer":
            self._dialog("THE ANULMENT %s is available!\n%s\n\nDownload and install it now?" % (data["version"], data["notes"][:160]),
                         [("DOWNLOAD & INSTALL", lambda: (self.download_portable(data["link"]) if data.get("portable") else self.download_install(data["link"]))),
                          ("NOT NOW", self._close_dialog)])
        else:
            self._dialog(data, [("OK", self._close_dialog)])
        return task.done

    def download_install(self, link):
        if not link.lower().endswith(".exe"):
            self._open_browser(link); return
        self._dialog("Downloading update...", [])
        def work():
            try:
                dst = os.path.join(tempfile.gettempdir(), os.path.basename(link.split("?")[0]) or "THE-ANULMENT-Setup.exe")
                req = urllib.request.Request(link, headers={"User-Agent": "THE-ANULMENT/" + APP_VERSION})
                with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f: shutil.copyfileobj(r, f)
                self._upd_result = ("install", dst)
            except Exception as e:
                self._upd_result = ("dlerror", (link, str(e)[:90]))
        threading.Thread(target=work, daemon=True).start()
        self.task_mgr.add(self._poll_download, "poll-dl")

    def _poll_download(self, task):
        r = self._upd_result
        if r is None: return task.cont
        self._upd_result = None
        if r[0] == "install":
            try:
                import subprocess
                subprocess.Popen([r[1]], env=clean_env(), cwd=tempfile.gettempdir(), close_fds=True,
                                 creationflags=0x00000008 | 0x00000200 if os.name == "nt" else 0)   # detached, outside _MEI
                self.userExit()
            except Exception as e:
                self._dialog("Could not start the installer:\n%s" % e, [("OPEN DOWNLOAD PAGE", lambda: self._open_browser(RELEASES_URL)), ("CLOSE", self._close_dialog)])
        else:
            self._dialog("Download failed.\n%s" % r[1][1], [("OPEN DOWNLOAD PAGE", lambda: self._open_browser(RELEASES_URL)), ("CLOSE", self._close_dialog)])
        return task.done

    def download_portable(self, link):
        exe = os.path.abspath(sys.executable); new = exe + ".new"
        self._dialog("Downloading portable update...", [])
        def work():
            try:
                req = urllib.request.Request(link, headers={"User-Agent": "THE-ANULMENT/" + APP_VERSION})
                with urllib.request.urlopen(req, timeout=60) as r, open(new, "wb") as f: shutil.copyfileobj(r, f)
                with open(new, "rb") as f: ok = f.read(2) == b"MZ"
                if not ok or os.path.getsize(new) < 5_000_000:
                    os.remove(new); raise IOError("downloaded file is not a valid THE ANULMENT executable")
                self._upd_result = ("swap", new)
            except Exception as e:
                try:
                    if os.path.exists(new): os.remove(new)
                except OSError: pass
                self._upd_result = ("dlerror", (link, str(e)[:90]))
        threading.Thread(target=work, daemon=True).start()
        self.task_mgr.add(self._poll_portable, "poll-dl")

    def _poll_portable(self, task):
        r = self._upd_result
        if r is None: return task.cont
        self._upd_result = None
        if r[0] == "swap":
            try: self._launch_swap_helper(os.path.abspath(sys.executable), r[1]); self.userExit()
            except Exception as e:
                log_error("portable update: %r" % e)
                self._dialog("Could not apply the update:\n%s" % str(e)[:90], [("OPEN DOWNLOAD PAGE", lambda: self._open_browser(RELEASES_URL)), ("CLOSE", self._close_dialog)])
        else:
            self._dialog("Download failed.\n%s" % r[1][1], [("OPEN DOWNLOAD PAGE", lambda: self._open_browser(RELEASES_URL)), ("CLOSE", self._close_dialog)])
        return task.done

    def _launch_swap_helper(self, exe, new):
        import subprocess
        pids = [os.getpid()]
        try: pids.append(os.getppid())
        except Exception: pass
        bat = os.path.join(tempfile.gettempdir(), "anulment_update_%d.bat" % os.getpid())
        lines = ["@echo off", "setlocal EnableDelayedExpansion", "set N=0"]
        for p in pids:
            lines += [":w%d" % p, 'tasklist /FI "PID eq %d" 2>NUL | find " %d " >NUL' % (p, p),
                      "if not errorlevel 1 (ping -n 2 127.0.0.1 >NUL & set /a N+=1 & if !N! LSS 120 goto w%d)" % p]
        lines += ["set T=0", ":swap", 'move /Y "%s" "%s" >NUL 2>&1' % (new, exe),
                  "if errorlevel 1 (ping -n 2 127.0.0.1 >NUL & set /a T+=1 & if !T! LSS 60 goto swap)",
                  'start "" "%s"' % exe, '(goto) 2>NUL & del "%~f0"']
        with open(bat, "w", encoding="mbcs" if os.name == "nt" else "utf-8") as f: f.write("\r\n".join(lines) + "\r\n")
        subprocess.Popen(["cmd.exe", "/c", bat], creationflags=0x00000008 | 0x00000200, close_fds=True, cwd=os.path.dirname(exe), env=clean_env(),
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _open_browser(self, url):
        import webbrowser
        webbrowser.open(url); self._close_dialog()



def main():
    try:
        App().run()
    except SystemExit:
        raise
    except Exception:
        log_error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
