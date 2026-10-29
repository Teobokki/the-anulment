"""v1.0.0.4 protest crowds.

* Everyone the player can get near is a FULL character (the FIREOUT SHINE Ana / Daniel models, skin, shader and hair,
  untouched): a pool of full actors is moved onto the crowd places nearest the player.
* Everyone further away is an impostor card - a picture of those same full characters rendered offline from 8 sides
  (tools/make_impostors.py -> assets/tex/crowd_atlas.png). A picture has no separate body under the clothes, so it can
  never show skin through clothes or hair. Cards get distance darkness + fog so they read as a crowd."""
import math, random, os
import numpy as np
from panda3d.core import NodePath, CardMaker, Shader, Filename, SamplerState, TransparencyAttrib

# clothing variants (shared with the impostor tool): (top, bottom) per variant, the same list for both bodies
VARIANTS = [((0.35, 0.12, 0.12), (0.1, 0.12, 0.2)), ((0.15, 0.2, 0.35), (0.15, 0.15, 0.16)), ((0.3, 0.3, 0.32), (0.1, 0.12, 0.2)),
            ((0.45, 0.38, 0.25), (0.15, 0.15, 0.16)), ((0.12, 0.25, 0.18), (0.3, 0.28, 0.24)), ((0.6, 0.55, 0.5), (0.1, 0.12, 0.2)),
            ((0.08, 0.08, 0.09), (0.3, 0.28, 0.24)), ((0.85, 0.85, 0.86), (0.15, 0.15, 0.16))]
KINDS = ("ana", "daniel")
ANGLES = 8
CELL = (128, 256)
COLS = len(VARIANTS) * len(KINDS)      # atlas: one column per (kind, variant), one row per view angle
NEAR_R = 40.0                          # nobody inside this radius is a card when an actor is free
POOL = 40

VERT = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix; uniform mat4 p3d_ModelViewMatrix;
attribute vec4 p3d_Vertex; attribute vec2 p3d_MultiTexCoord0;
uniform vec4 cell; varying vec2 uv; varying float vdist;
void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; uv = cell.xy + p3d_MultiTexCoord0 * cell.zw;
  vdist = length((p3d_ModelViewMatrix * p3d_Vertex).xyz); }
"""
FRAG = """#version 120
uniform sampler2D p3d_Texture0; uniform vec3 fogcol; varying vec2 uv; varying float vdist;
void main() { vec4 c = texture2D(p3d_Texture0, uv); if (c.a < 0.5) discard;
  float k = mix(1.0, 0.5, smoothstep(12.0, 70.0, vdist));
  float f = 1.0 - exp(-0.00012 * vdist * vdist);
  gl_FragColor = vec4(mix(c.rgb * k, fogcol, clamp(f, 0.0, 0.85)), 1.0); }
"""


def make_slots(game, rect, n, rnd, avoid=None, face=None):
    x0, y0, x1, y1 = rect; out = []; tries = 0
    while len(out) < n and tries < n * 6:
        tries += 1
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if avoid and any(a[0] <= x <= a[2] and a[1] <= y <= a[3] for a in avoid): continue
        if any((x - s[0]) ** 2 + (y - s[1]) ** 2 < 0.55 ** 2 for s in out[-40:]): continue
        h = (math.degrees(math.atan2(-(face[0] - x), face[1] - y)) if face else rnd.uniform(0, 360)) + rnd.uniform(-25, 25)
        out.append((x, y, h, rnd.randrange(2), rnd.randrange(len(VARIANTS))))
    return out


class Crowd:
    def __init__(self, game, slots, rnd):
        import an_people as AP
        self.g = game; app = game.app; self.app = app
        self.slots = slots; self.S = np.array([(s[0], s[1]) for s in slots], np.float64)
        self.root = NodePath("crowd"); self.root.reparent_to(game.world.root)
        tex = app.loader.load_texture(Filename.from_os_specific(os.path.join(app.BASE, "assets", "tex", "crowd_atlas.png")))
        tex.set_minfilter(SamplerState.FT_linear_mipmap_linear); tex.set_magfilter(SamplerState.FT_linear)
        tex.set_wrap_u(SamplerState.WM_clamp); tex.set_wrap_v(SamplerState.WM_clamp)
        sh = Shader.make(Shader.SL_GLSL, VERT, FRAG)
        self.root.set_shader(sh, 5); self.root.set_texture(tex, 5); self.root.set_shader_input("fogcol", app.fogcol)
        self.root.set_light_off(5); self.root.set_two_sided(True)
        cm = CardMaker("imp"); cm.set_frame(-0.5, 0.5, 0.0, 2.0)
        self.cards = []; self.ang = [-1] * len(slots)
        for i, (x, y, h, k, v) in enumerate(slots):
            c = self.root.attach_new_node(cm.generate()); c.set_pos(x, y, game.world.ground_z(x, y)); c.set_billboard_axis()
            c.set_scale(random.Random(i).uniform(0.95, 1.04)); self.cards.append(c)
        self.col = [(k * len(VARIANTS) + v) for (x, y, h, k, v) in slots]
        # the full actors (half Ana-, half Daniel-bodied), built exactly like FIREOUT SHINE's characters
        self.actors = {0: [], 1: []}; self.slot_of = {}; self.actor_at = {}
        for j in range(POOL):
            kind = j % 2
            p = AP.make_protester(game, -9999, -9999, 0, rnd, female=(kind == 0)); p.np.stash()
            self.actors[kind].append(p); self.slot_of[id(p)] = None
        self.all = self.actors[0] + self.actors[1]
        self.t = 0.0; self.ta = 0.0
        self.update(0.0, force=True)

    def _cell(self, i, a):
        c = self.col[i]; return (c / COLS, 1.0 - (a + 1) / ANGLES, 1.0 / COLS, 1.0 / ANGLES)

    def update(self, dt, force=False):
        self.t -= dt; self.ta -= dt
        me = getattr(self.g, "chars", {}).get("miyo")
        if me is not None: px, py = me.np.get_x(self.app.render), me.np.get_y(self.app.render)
        else: c = self.app.camera.get_pos(self.app.render); px, py = c.x, c.y
        if force or self.t <= 0:
            self.t = 0.35; self._assign(px, py)
        if force or self.ta <= 0:
            self.ta = 0.2; cam = self.app.camera.get_pos(self.app.render)
            for i, (x, y, h, k, v) in enumerate(self.slots):
                if self.actor_at.get(i) is not None: continue
                ch = math.degrees(math.atan2(-(cam.x - x), cam.y - y))
                a = int(round(((h - ch) % 360.0) / (360.0 / ANGLES))) % ANGLES
                if a != self.ang[i]:
                    self.ang[i] = a; self.cards[i].set_shader_input("cell", self._cell(i, a))

    def _assign(self, px, py):
        import an_people as AP
        d2 = (self.S[:, 0] - px) ** 2 + (self.S[:, 1] - py) ** 2
        want = set()
        for kind in (0, 1):
            idx = [i for i in np.argsort(d2) if self.slots[i][3] == kind and d2[i] < NEAR_R * NEAR_R][:len(self.actors[kind])]
            want |= set(int(i) for i in idx)
        for p in self.all:            # free actors whose place is no longer near
            s = self.slot_of[id(p)]
            if s is not None and s not in want:
                self.slot_of[id(p)] = None; self.actor_at[s] = None; self.cards[s].show(); p.np.stash()
        for s in sorted(want, key=lambda i: d2[i]):
            if self.actor_at.get(s) is not None: continue
            kind = self.slots[s][3]; free = [p for p in self.actors[kind] if self.slot_of[id(p)] is None]
            if not free: continue
            p = free[0]; x, y, h, k, v = self.slots[s]; top, bot = VARIANTS[v]
            AP.style(p, top, bot, None)
            p.x, p.y, p.h = x, y, h; p._gz = None; p.np.unstash(); p.sync()
            self.slot_of[id(p)] = s; self.actor_at[s] = p; self.cards[s].hide()

    def active(self):
        return [p for p in self.all if self.slot_of[id(p)] is not None]

    def destroy(self):
        for p in self.all: p.destroy()
        self.root.remove_node()
