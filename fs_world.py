"""THE ANULMENT (from THE ANULMENT) world: Valdora, a fictional capital at night: procedural neon city (6 districts) + Hikari Beach. Geometry, collision, road graph, minimap."""
import math, random, json, os
from panda3d.core import (NodePath, TransparencyAttrib, Texture, SamplerState, PNMImage, ColorBlendAttrib, TextureStage,
                          Vec3, Point3, LColor, CullFaceAttrib, DepthWriteAttrib, BillboardEffect, TextNode)
from fs_geom import MB
import fs_data as D

C = D.PITCH
NODES_X = [D.CITY_MIN + i * C for i in range(D.N_BLOCKS + 1)]
HW = D.ROAD_W / 2


def block_rect(i, j):
    return (NODES_X[i] + HW, NODES_X[j] + HW, NODES_X[i + 1] - HW, NODES_X[j + 1] - HW)


class Grid:
    """spatial hash of static obstacles: rects (x0,y0,x1,y1) and circles (x,y,r)."""
    def __init__(self, cell=50.0):
        self.cell = cell; self.cells = {}

    def _keys(self, x0, y0, x1, y1):
        c = self.cell
        for ix in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for iy in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                yield (ix, iy)

    def add_rect(self, r, tag="b"):
        for k in self._keys(*r):
            self.cells.setdefault(k, []).append(("r", r, tag))

    def add_circle(self, x, y, rad, tag="p"):
        for k in self._keys(x - rad, y - rad, x + rad, y + rad):
            self.cells.setdefault(k, []).append(("c", (x, y, rad), tag))

    def near(self, x, y, r=4.0):
        out = []; seen = set()
        for k in self._keys(x - r, y - r, x + r, y + r):
            for o in self.cells.get(k, ()):
                if id(o) not in seen:
                    seen.add(id(o)); out.append(o)
        return out

    def push_circle(self, x, y, rad):
        """returns (dx, dy, nx, ny, hit_tag) total push-out for a circle; nx,ny = last contact normal"""
        px = py = 0.0; nx = ny = 0.0; tag = None
        for kind, o, tg in self.near(x, y, rad + 1.0):
            if kind == "r":
                x0, y0, x1, y1 = o
                cx = min(max(x, x0), x1); cy = min(max(y, y0), y1)
                dx, dy = x - cx, y - cy; d2 = dx * dx + dy * dy
                if d2 < rad * rad:
                    if d2 > 1e-8:
                        d = math.sqrt(d2); pen = rad - d; ux, uy = dx / d, dy / d
                    else:   # centre inside the rect: push out along the shallowest axis
                        cand = [(x - x0, -1, 0), (x1 - x, 1, 0), (y - y0, 0, -1), (y1 - y, 0, 1)]
                        m = min(cand); pen = m[0] + rad; ux, uy = m[1], m[2]
                    px += ux * pen; py += uy * pen; nx, ny = ux, uy; tag = tg
                    x += ux * pen; y += uy * pen
            else:
                ox, oy, orad = o
                dx, dy = x - ox, y - oy; d2 = dx * dx + dy * dy; rr = rad + orad
                if d2 < rr * rr:
                    d = math.sqrt(d2) or 1e-4; pen = rr - d; ux, uy = dx / d, dy / d
                    px += ux * pen; py += uy * pen; nx, ny = ux, uy; tag = tg
                    x += ux * pen; y += uy * pen
        return px, py, nx, ny, tag

    def segment_blocked(self, x0, y0, x1, y1):
        """line of sight test against rect obstacles (buildings only)."""
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 6.0))
        for k in range(1, n):
            t = k / n; x = x0 + (x1 - x0) * t; y = y0 + (y1 - y0) * t
            for kind, o, tg in self.cells.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))), ()):
                if kind == "r" and tg == "b" and o[0] <= x <= o[2] and o[1] <= y <= o[3]:
                    return True
        return False


class World:
    def __init__(self, app, quality=2):
        self.app = app; self.q = quality
        self.root = app.render.attach_new_node("world")
        self.grid = Grid()
        self.rng = random.Random(2026)
        self.signs_meta = {"h": [], "v": []}   # THE ANULMENT: no neon signs in Valdora
        self.tex = {}
        self.anim = []          # (nodepath, kind)
        self.nodes = {}; self.edges = []; self.build_graph()
        self.parking = []       # (x, y, heading_deg)
        self.ped_loops = []     # list of polyline loops on sidewalks
        self.dunes = []         # raised sand mounds (x0, y0, x1, y1) at z 0.05 - used for on-foot ground height
        self.signposts = []
        self.build()

    # ---------------------------------------------------------------- textures
    def T(self, name, repeat=True, mip=True):
        if name in self.tex:
            return self.tex[name]
        from panda3d.core import Filename
        t = self.app.loader.load_texture(Filename.from_os_specific(os.path.join(self.app.BASE, "assets", "tex", name)))
        if repeat:
            t.set_wrap_u(SamplerState.WM_repeat); t.set_wrap_v(SamplerState.WM_repeat)
        else:
            t.set_wrap_u(SamplerState.WM_clamp); t.set_wrap_v(SamplerState.WM_clamp)
        if mip:
            t.set_minfilter(SamplerState.FT_linear_mipmap_linear); t.set_anisotropic_degree(4)
        self.tex[name] = t
        return t

    # ---------------------------------------------------------------- road graph
    def build_graph(self):
        N = D.N_BLOCKS
        for i in range(N + 1):
            for j in range(N + 1):
                self.nodes[(i, j)] = (NODES_X[i], NODES_X[j])
        for i in range(N + 1):
            for j in range(N + 1):
                if i < N: self.edges.append(((i, j), (i + 1, j), D.ROAD_W))
                if j < N: self.edges.append(((i, j), (i, j + 1), D.ROAD_W))
        bx = D.BEACH_ROAD_X
        for k in range(N + 1):
            self.nodes[("b", k)] = (bx, NODES_X[k])
            if k < N: self.edges.append((("b", k), ("b", k + 1), D.BEACH_ROAD_W))
        for k in (0, 4, 8):
            self.edges.append(((N, k), ("b", k), D.BEACH_ROAD_W))
        self.adj = {}
        for a, b, w in self.edges:
            self.adj.setdefault(a, []).append(b); self.adj.setdefault(b, []).append(a)

    def nearest_node(self, x, y):
        return min(self.nodes, key=lambda k: (self.nodes[k][0] - x) ** 2 + (self.nodes[k][1] - y) ** 2)

    def road_half_width(self, a, b):
        return (D.BEACH_ROAD_W if ("b" in (a[0], b[0]) or (a[0] == D.N_BLOCKS and b[0] == "b")) else D.ROAD_W) / 2

    def nearest_road_point(self, x, y):
        """closest point on any road centre-line + heading along it (deg)."""
        best = None
        for a, b, w in self.edges:
            ax, ay = self.nodes[a]; bx, by = self.nodes[b]
            dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
            px, py = ax + dx * t, ay + dy * t
            d = (px - x) ** 2 + (py - y) ** 2
            if best is None or d < best[0]:
                best = (d, px, py, math.degrees(math.atan2(-dx, dy)))
        return best[1], best[2], best[3]

    def on_road(self, x, y):
        for a, b, w in self.edges:
            ax, ay = self.nodes[a]; bx, by = self.nodes[b]
            if min(ax, bx) - w / 2 <= x <= max(ax, bx) + w / 2 and min(ay, by) - w / 2 <= y <= max(ay, by) + w / 2:
                return True
        return False

    def surface(self, x, y):
        if x > D.SEA_X and not self.on_pier(x, y):
            return "water"
        if D.SAND[0] < x <= D.SEA_X and not self.in_lot(x, y) and not self.on_pier(x, y) and not self.in_stadium(x, y):
            return "sand"
        return "road"

    def on_sidewalk(self, x, y):
        if x < D.CITY_MIN + HW or x > D.CITY_MAX - HW or y < D.CITY_MIN + HW or y > D.CITY_MAX - HW:
            return False
        i = int((x - D.CITY_MIN) // C); j = int((y - D.CITY_MIN) // C)
        if not (0 <= i < D.N_BLOCKS and 0 <= j < D.N_BLOCKS): return False
        x0, y0, x1, y1 = block_rect(i, j)
        return x0 <= x <= x1 and y0 <= y <= y1

    def ground_z(self, x, y):
        """walkable surface height for people on foot (v1.0.3: feet follow the boardwalk, pier deck, sloped sand, dunes and kerbs
        instead of sinking into them)."""
        if self.on_pier(x, y): return 0.3
        if self.on_sidewalk(x, y): return 0.15
        if D.BOARDWALK[0] <= x <= D.BOARDWALK[1] and -440 <= y <= 440: return 0.2
        if self.in_lot(x, y): return 0.04
        if D.STADIUM[0] <= x <= D.STADIUM[2] and D.STADIUM[1] <= y <= D.STADIUM[3]: return 0.04     # v1.0.5 SFC 27 stadium
        if D.SAND[0] < x <= D.SEA_X + 4:
            z = 0.02 - 0.17 * (x - D.SAND[0]) / (D.SEA_X + 4 - D.SAND[0])
            for x0, y0, x1, y1 in self.dunes:
                if x0 <= x <= x1 and y0 <= y <= y1: return max(z, 0.05)
            return z
        return 0.0

    @staticmethod
    def in_stadium(x, y, pad=0.0):
        r = D.STADIUM
        return r[0] - pad <= x <= r[2] + pad and r[1] - pad <= y <= r[3] + pad

    def on_pier(self, x, y):
        return 560 <= x <= 690 and 140 <= y <= 156

    def in_lot(self, x, y):
        r = D.DRIFT_ZONE["rect"]
        return r[0] <= x <= r[2] and r[1] <= y <= r[3]

    # ---------------------------------------------------------------- build
    def build(self):
        rng = self.rng
        self.mb = {}           # (chunk, material) -> MB
        self.aviation = []; self.nflags = 0; self.flag_poles = []; self.flag_spots = []
        self.mirror = {}       # material -> MB (reflection copies)
        self.build_ground()
        for i in range(D.N_BLOCKS):
            for j in range(D.N_BLOCKS):
                self.build_block(i, j)
        self.build_highway()
        self.build_beach()
        self.build_home()
        self.build_bounds()
        self.build_skyline()
        self.flush()
        self.build_flags()
        self.build_sky()

    def M(self, mat, chunk=(0, 0)):
        k = (chunk, mat)
        if k not in self.mb:
            self.mb[k] = MB("%s_%s" % (mat, chunk))
        return self.mb[k]

    def MR(self, mat):
        if mat not in self.mirror:
            self.mirror[mat] = MB("mirror_" + mat)
        return self.mirror[mat]

    @staticmethod
    def chunk(x, y):
        return (int(math.floor(x / 200.0)), int(math.floor(y / 200.0)))

    def build_ground(self):
        # roads: segments between intersections + intersection squares (asphalt, alpha -> wet reflections)
        road = self.M("asphalt"); mk = self.M("marking")
        uvs = lambda x, y: (x / 12.0, y / 12.0)
        def flat(mb, x0, y0, x1, y1, z, col=(1, 1, 1, 1), uvf=None):
            u = uvf or (lambda x, y: (x / 12.0, y / 12.0))
            mb.quad((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), col, (u(x0, y0), u(x1, y0), u(x1, y1), u(x0, y1)), n=(0, 0, 1))
        for key, (x, y) in self.nodes.items():
            w = (D.BEACH_ROAD_W if key[0] == "b" else D.ROAD_W) / 2
            flat(road, x - w, y - w, x + w, y + w, 0.0)
        for a, b, w in self.edges:
            (ax, ay), (bx, by) = self.nodes[a], self.nodes[b]
            hw = w / 2
            if ax == bx:
                y0, y1 = min(ay, by) + hw, max(ay, by) - hw
                flat(road, ax - hw, y0, ax + hw, y1, 0.0)
                # lane markings: centre double line + dashed lane lines
                flat(mk, ax - 0.35, y0, ax - 0.15, y1, 0.02); flat(mk, ax + 0.15, y0, ax + 0.35, y1, 0.02)
                if w > 20:
                    for s in (-1, 1):
                        yy = y0 + 4
                        while yy < y1 - 6:
                            flat(mk, ax + s * 5.4 - 0.1, yy, ax + s * 5.4 + 0.1, yy + 4, 0.02); yy += 10
                self.crosswalks(ax, y0, 0, hw); self.crosswalks(ax, y1, 1, hw)
            else:
                x0, x1 = min(ax, bx) + hw, max(ax, bx) - hw
                flat(road, x0, ay - hw, x1, ay + hw, 0.0)
                flat(mk, x0, ay - 0.35, x1, ay - 0.15, 0.02); flat(mk, x0, ay + 0.15, x1, ay + 0.35, 0.02)
                if w > 20:
                    for s in (-1, 1):
                        xx = x0 + 4
                        while xx < x1 - 6:
                            flat(mk, xx, ay + s * 5.4 - 0.1, xx + 4, ay + s * 5.4 + 0.1, 0.02); xx += 10
                self.crosswalks(x0, ay, 2, hw); self.crosswalks(x1, ay, 3, hw)
        # scramble crossing diagonals at the central intersection (0,0)
        for s in (-1, 1):
            for k in range(-7, 8):
                t = k * 1.4
                cx, cy = t, s * t
                ang = math.radians(45 if s > 0 else -45)
                self.M("marking").obox(cx, cy, 0.025, 0.4, 2.0, 0.026, ang, (1, 1, 1, 1))
        # parking strip markings + parking spots along city roads
        for a, b, w in self.edges:
            if w < 20 or a[0] == "b" or b[0] == "b":
                continue
            (ax, ay), (bx, by) = self.nodes[a], self.nodes[b]
            horiz = ay == by
            L = abs(bx - ax) if horiz else abs(by - ay)
            for s in (-1, 1):
                if self.rng.random() < 0.35:
                    continue
                n = 0
                for k in range(3):
                    t = 25 + k * 18 + self.rng.uniform(-2, 2)
                    if t > L - 22:
                        break
                    if horiz:
                        x = min(ax, bx) + t; y = ay + s * 9.2; h = -90 if s < 0 else 90
                    else:
                        x = ax + s * 9.2; y = min(ay, by) + t; h = 0 if s < 0 else 180
                    self.parking.append((x, y, h))
        # sidewalks (block rims), raised kerb
        sw = self.M("sidewalk")
        for i in range(D.N_BLOCKS):
            for j in range(D.N_BLOCKS):
                x0, y0, x1, y1 = block_rect(i, j)
                u = lambda x, y: (x / 4.0, y / 4.0)
                flat(sw, x0, y0, x1, y1, 0.15, (0.85, 0.85, 0.9, 1), u)
                k = self.M("kerb")
                k.box(x0, y0, 0, x1, y1, 0.15, (0.5, 0.5, 0.55, 1), top=False)
                # pedestrian loop on the sidewalk
                m = 2.0
                self.ped_loops.append([(x0 + m, y0 + m), (x1 - m, y0 + m), (x1 - m, y1 - m), (x0 + m, y1 - m)])
        # outer verge beyond ring roads (dark ground)
        g = self.M("ground")
        W = D.WORLD
        flat(g, -900, -900, 900, -411, -0.02, (0.06, 0.06, 0.08, 1)); flat(g, -900, 411, 900, 900, -0.02, (0.06, 0.06, 0.08, 1))
        flat(g, -900, -411, -411, 411, -0.02, (0.06, 0.06, 0.08, 1))

    def crosswalks(self, x, y, side, hw):
        mk = self.M("marking")
        if side in (0, 1):      # road runs along y; crossing stripes across x at y
            yy = y + (1.0 if side == 0 else -5.0)
            k = -hw + 1.0
            while k < hw - 1:
                mk.quad((x + k, yy, 0.02), (x + k + 0.6, yy, 0.02), (x + k + 0.6, yy + 4, 0.02), (x + k, yy + 4, 0.02), (1, 1, 1, 1), n=(0, 0, 1)); k += 1.2
        else:
            xx = x + (1.0 if side == 2 else -5.0)
            k = -hw + 1.0
            while k < hw - 1:
                mk.quad((xx, y + k, 0.02), (xx + 4, y + k, 0.02), (xx + 4, y + k + 0.6, 0.02), (xx, y + k + 0.6, 0.02), (1, 1, 1, 1), n=(0, 0, 1)); k += 1.2

    # ---------------------------------------------------------------- buildings
    def build_block(self, i, j):
        rng = self.rng
        x0, y0, x1, y1 = block_rect(i, j)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        dist = D.district_at(cx, cy)
        sw = D.SIDEWALK
        bx0, by0, bx1, by1 = x0 + sw, y0 + sw, x1 - sw, y1 - sw
        ch = self.chunk(cx, cy)
        self.street_props(x0, y0, x1, y1, ch, dist)
        if dist in ("akari", "sakura", "kurogane"): self.power_lines(x0 + 2, y0 + 1, x1 - 2, y1, ch)
        if (i, j) == D.TOWER_BLOCK:
            self.grid.add_rect((bx0 + 20, by0 + 20, bx1 - 20, by1 - 20), "b")
            self.build_tower(cx, cy, ch); self.park(bx0, by0, bx1, by1, ch); return
        if (i, j) == D.GARAGE_BLOCK:
            self.grid.add_rect((bx0, by0, bx1, by1), "b")
            self.build_garage(bx0, by0, bx1, by1, ch); return
        self.grid.add_rect((bx0, by0, bx1, by1), "b")
        # lots
        nx = rng.choice([1, 2, 2, 3]); ny = rng.choice([1, 2, 2, 3])
        if dist == "kurogane": nx, ny = rng.choice([1, 2]), rng.choice([1, 2])
        lw = (bx1 - bx0) / nx; lh = (by1 - by0) / ny
        hr = {"crossing": (22, 48), "akari": (16, 34), "kurogane": (10, 22), "tower": (18, 40), "sakura": (12, 26)}[dist]   # Valdora: grey blocks
        for a in range(nx):
            for b in range(ny):
                lx0, ly0 = bx0 + a * lw + 0.6, by0 + b * lh + 0.6
                lx1, ly1 = lx0 + lw - 1.2, ly0 + lh - 1.2
                h = rng.uniform(*hr)
                if dist == "crossing" and abs(cx) < 120 and abs(cy) < 120: h *= 1.15
                self.building(lx0, ly0, lx1, ly1, h, dist, ch, edge=(a == 0, b == 0, a == nx - 1, b == ny - 1), bx=(bx0, by0, bx1, by1))
        # giant video boards around the scramble crossing
        if dist == "crossing" and abs(cx) < 100 and abs(cy) < 100:
            fx = bx0 if cx > 0 else bx1; fy = by0 if cy > 0 else by1
            self.videoboard(fx, fy, cx, cy, ch)

    def building(self, x0, y0, x1, y1, h, dist, ch, edge, bx):
        rng = self.rng
        if h > 70: fac = rng.choice(["facade0", "facade4", "facade0", "facade3"])
        elif h > 30: fac = rng.choice(["facade1", "facade2", "facade3", "facade4"])
        else: fac = rng.choice(["facade5", "facade2", "facade1", "facade5"])
        if dist == "kurogane": fac = rng.choice(["facade1", "facade3"])
        if False:
            fac = "facade6"; h *= rng.uniform(1.15, 1.45)        # slim modern glass tower
        tint = rng.choice([(1, 1, 1), (0.92, 0.96, 1.08), (1.06, 0.98, 0.92), (0.88, 0.88, 0.95)])
        col = (tint[0], tint[1], tint[2], 1)
        mb = self.M(fac, ch)
        def uv(face, w, hh):
            o = rng.random()
            return ((o, 4.0 / 28), (o + w / 32.0, 4.0 / 28), (o + w / 32.0, hh / 28.0), (o, hh / 28.0))
        mb.box(x0, y0, 4.0, x1, y1, h, col, top=False, uvs=lambda f, w, hh: ((0, 0), (w / 32.0, 0), (w / 32.0, (hh) / 28.0), (0, (hh) / 28.0)))
        # mirror copy of facades (reflection on the wet asphalt)
        if self.q >= 2 and h > 0:
            m = self.MR(fac)
            m.box(x0, y0, -h, x1, y1, -4.0, (col[0] * 0.55, col[1] * 0.55, col[2] * 0.6, 1), top=False,
                  uvs=lambda f, w, hh: ((0, h / 28.0), (w / 32.0, h / 28.0), (w / 32.0, 4.0 / 28), (0, 4.0 / 28)))
        # user artwork flag: big hanging banner on a street-facing facade, or a rooftop flag on a pole (~8-15 citywide)
        if self.nflags < 15 and h > 22 and rng.random() < 0.10 and dist != "beach":
            self.nflags += 1
            if rng.random() < 0.5:
                fm = self.M("flag", ch); S = min(10.0, (x1 - x0) * 0.6, (y1 - y0) * 0.6); zb = min(h - S - 3, 14.0 + rng.uniform(0, 10))
                cx_, cy_ = (x0 + x1) / 2, (y0 + y1) / 2
                face = rng.choice([f for f, on in zip("wsen", edge) if on] or ["s"])
                if face == "s": p = ((cx_ - S / 2, y0 - 0.2, zb), (cx_ + S / 2, y0 - 0.2, zb), (cx_ + S / 2, y0 - 0.2, zb + S), (cx_ - S / 2, y0 - 0.2, zb + S))
                elif face == "n": p = ((cx_ + S / 2, y1 + 0.2, zb), (cx_ - S / 2, y1 + 0.2, zb), (cx_ - S / 2, y1 + 0.2, zb + S), (cx_ + S / 2, y1 + 0.2, zb + S))
                elif face == "w": p = ((x0 - 0.2, cy_ + S / 2, zb), (x0 - 0.2, cy_ - S / 2, zb), (x0 - 0.2, cy_ - S / 2, zb + S), (x0 - 0.2, cy_ + S / 2, zb + S))
                else: p = ((x1 + 0.2, cy_ - S / 2, zb), (x1 + 0.2, cy_ + S / 2, zb), (x1 + 0.2, cy_ + S / 2, zb + S), (x1 + 0.2, cy_ - S / 2, zb + S))
                fm.quad(*p, col=(0.92, 0.92, 0.92, 1))
                self.flag_spots.append(((p[0][0] + p[2][0]) / 2, (p[0][1] + p[2][1]) / 2, zb + S / 2))
            else:
                fx, fy = x0 + 3, y0 + 3
                self.M("flat", ch).box(fx - 0.12, fy - 0.12, h, fx + 0.12, fy + 0.12, h + 13, (0.75, 0.75, 0.78, 1))
                self.flag_poles.append((fx, fy, h + 12.8, rng.uniform(0, 6.28)))
                self.flag_spots.append((fx, fy, h + 10))
        # roof cap + rooftop details
        self.M("flat", ch).quad((x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h), (0.05, 0.05, 0.07, 1), n=(0, 0, 1))
        self.roof_details(x0, y0, x1, y1, h, ch, fac)
        if h > 45 and rng.random() < 0.6 and min(x1 - x0, y1 - y0) > 14:     # setback crown / stepped tower
            ix, iy = (x1 - x0) * rng.uniform(0.15, 0.25), (y1 - y0) * rng.uniform(0.15, 0.25)
            h2 = h + rng.uniform(10, 35)
            mb.box(x0 + ix, y0 + iy, h, x1 - ix, y1 - iy, h2, col, top=False,
                   uvs=lambda f, w, hh: ((0, h / 28.0), (w / 32.0, h / 28.0), (w / 32.0, h2 / 28.0), (0, h2 / 28.0)))
            self.M("flat", ch).quad((x0 + ix, y0 + iy, h2), (x1 - ix, y0 + iy, h2), (x1 - ix, y1 - iy, h2), (x0 + ix, y1 - iy, h2), (0.05, 0.05, 0.07, 1), n=(0, 0, 1))
            self.roof_details(x0 + ix, y0 + iy, x1 - ix, y1 - iy, h2, ch, fac)
        # street level: awnings + paper lanterns on street-facing fronts
        if False:
            aw = self.M("flat", ch); e = self.M("emit", ch)
            for (on, fx0, fy0, fx1, fy1, nx, ny) in ((edge[1], x0, y0, x1, y0, 0, -1), (edge[3], x0, y1, x1, y1, 0, 1),
                                                     (edge[0], x0, y0, x0, y1, -1, 0), (edge[2], x1, y0, x1, y1, 1, 0)):
                if not on: continue
                L = math.hypot(fx1 - fx0, fy1 - fy0); n = max(1, int(L // 7))
                for k in range(n):
                    if rng.random() < 0.35: continue
                    t0, t1 = (k + 0.1) / n, (k + 0.9) / n
                    ax, ay = fx0 + (fx1 - fx0) * t0, fy0 + (fy1 - fy0) * t0; bx_, by_ = fx0 + (fx1 - fx0) * t1, fy0 + (fy1 - fy0) * t1
                    c = rng.choice(D.NEON)
                    aw.box(min(ax, bx_, ax + nx * 1.4), min(ay, by_, ay + ny * 1.4), 3.6, max(ax, bx_, ax + nx * 1.4), max(ay, by_, ay + ny * 1.4), 3.9,
                           (c[0] * 0.55, c[1] * 0.55, c[2] * 0.55, 1))
                    if dist == "akari" and rng.random() < 0.5:   # red paper lanterns
                        for lt in (t0, t1):
                            lx, ly = fx0 + (fx1 - fx0) * lt + nx * 1.0, fy0 + (fy1 - fy0) * lt + ny * 1.0
                            e.box(lx - 0.25, ly - 0.25, 2.9, lx + 0.25, ly + 0.25, 3.5, (2.2, 0.35, 0.2, 1))
                            self.glow(lx, ly, 3.2, 1.6, (1.0, 0.3, 0.15))
        sf = self.M("shopfront", ch)
        sf.box(x0, y0, 0.15, x1, y1, 4.0, (1, 1, 1, 1), top=False, uvs=lambda f, w, hh: ((0, 0), (w / 32.0, 0), (w / 32.0, 1), (0, 1)))
        if False:
            nc = rng.choice(D.NEON); e = self.M("emit", ch)
            t = 0.25
            for (ax, ay, bx_, by_) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
                e.quad((ax, ay, h + 0.1), (bx_, by_, h + 0.1), (bx_, by_, h + 0.1 + t), (ax, ay, h + 0.1 + t), (nc[0] * 2, nc[1] * 2, nc[2] * 2, 1))
        # rooftop billboard
        if h < 60 and rng.random() < 0.35 and dist != "kurogane":
            self.sign_h(x0 + (x1 - x0) * 0.5, y0 + (y1 - y0) * 0.5, h + 1.0, min(x1 - x0, 24), 6.0, rng.choice([0, 90]), ch, frame=True)
        # facade signs facing streets
        if dist in ("crossing", "akari", "tower") or (dist == "sakura" and rng.random() < 0.5):
            nsig = {"akari": 12, "crossing": 10, "tower": 5, "sakura": 4}[dist]
            faces = []
            if edge[0]: faces.append(("w", x0, (y0 + y1) / 2, y1 - y0))
            if edge[2]: faces.append(("e", x1, (y0 + y1) / 2, y1 - y0))
            if edge[1]: faces.append(("s", (x0 + x1) / 2, y0, x1 - x0))
            if edge[3]: faces.append(("n", (x0 + x1) / 2, y1, x1 - x0))
            for _ in range(nsig):
                if not faces: break
                f, fx, fy, L = rng.choice(faces)
                off = rng.uniform(-L / 2 + 3, L / 2 - 3)
                zz = rng.uniform(6, min(h - 6, 40)) if h > 14 else 5.0
                if rng.random() < 0.55:   # vertical blade sign protruding from the facade
                    self.sign_v(f, fx, fy, off, zz, ch)
                else:
                    self.sign_flat(f, fx, fy, off, rng.uniform(4.6, 5.5) if rng.random() < 0.5 else zz, ch)

    def roof_details(self, x0, y0, x1, y1, h, ch, fac):
        """AC units, water tanks, antennas, helipads and red aviation lights."""
        rng = self.rng; mb = self.M("flat", ch); w, d = x1 - x0, y1 - y0
        for _ in range(rng.randint(2, 6)):           # AC units
            ax, ay = rng.uniform(x0 + 1.5, x1 - 3), rng.uniform(y0 + 1.5, y1 - 3)
            mb.box(ax, ay, h, ax + 1.6, ay + 1.0, h + 1.1, (0.32, 0.33, 0.36, 1))
        if rng.random() < 0.5:                        # water tank on legs
            tx, ty = rng.uniform(x0 + 3, x1 - 5), rng.uniform(y0 + 3, y1 - 5)
            mb.box(tx, ty, h, tx + 2.6, ty + 2.6, h + 1.4, (0.2, 0.2, 0.22, 1))
            mb.box(tx - 0.2, ty - 0.2, h + 1.4, tx + 2.8, ty + 2.8, h + 4.2, (0.55, 0.5, 0.45, 1))
        if h > 60 and rng.random() < 0.35 and min(w, d) > 22:   # helipad
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            mb.box(cx - 9, cy - 9, h, cx + 9, cy + 9, h + 0.4, (0.16, 0.17, 0.2, 1))
            e = self.M("emit", ch)
            for sx in (-1, 1): e.box(cx + sx * 3 - 0.4, cy - 4, h + 0.4, cx + sx * 3 + 0.4, cy + 4, h + 0.45, (1.6, 1.6, 1.6, 1))
            e.box(cx - 3, cy - 0.4, h + 0.4, cx + 3, cy + 0.4, h + 0.45, (1.6, 1.6, 1.6, 1))
        if rng.random() < 0.55:                        # antenna
            ax, ay = rng.uniform(x0 + 2, x1 - 2), rng.uniform(y0 + 2, y1 - 2); ah = rng.uniform(5, 16)
            mb.box(ax - 0.12, ay - 0.12, h, ax + 0.12, ay + 0.12, h + ah, (0.5, 0.5, 0.55, 1))
            self.glow(ax, ay, h + ah + 0.2, 2.2, (1.0, 0.08, 0.05)); self.aviation.append((ax, ay, h + ah + 0.2))
        if h > 50:                                     # corner aviation lights
            for (cx_, cy_) in ((x0, y0), (x1, y1)):
                self.glow(cx_, cy_, h + 0.6, 2.4, (1.0, 0.1, 0.06)); self.aviation.append((cx_, cy_, h + 0.6))

    def power_lines(self, x0, y0, x1, y1, ch):
        """utility poles with sagging tangled wires along a block edge (old-town streets)."""
        mb = self.M("flat", ch); y = y0 + 1.2
        xs = [x0 + 4 + k * 22 for k in range(int((x1 - x0 - 8) // 22) + 1)]
        for x in xs:
            mb.box(x - 0.18, y - 0.18, 0, x + 0.18, y + 0.18, 10.5, (0.42, 0.42, 0.44, 1)); self.grid.add_circle(x, y, 0.25, "p")
            mb.box(x - 1.2, y - 0.1, 9.4, x + 1.2, y + 0.1, 9.6, (0.3, 0.3, 0.32, 1))
            mb.box(x - 0.4, y - 0.4, 8.0, x + 0.4, y + 0.4, 8.9, (0.25, 0.25, 0.27, 1))   # transformer
        for a, b in zip(xs, xs[1:]):
            for k, off in enumerate((-1.0, -0.3, 0.4, 1.0)):
                zt = 9.5 - k * 0.25; n = 6
                for i in range(n):
                    t0, t1 = i / n, (i + 1) / n
                    za = zt - 1.1 * 4 * t0 * (1 - t0); zb = zt - 1.1 * 4 * t1 * (1 - t1)
                    xa, xb = a + (b - a) * t0, a + (b - a) * t1
                    mb.quad((xa, y + off * 0.3, za), (xb, y + off * 0.3, zb), (xb, y + off * 0.3, zb + 0.05), (xa, y + off * 0.3, za + 0.05), (0.04, 0.04, 0.05, 1), n=(0, -1, 0))

    def _uv_rect(self, r):
        u0, v0, u1, v1, st = r
        return ((u0, v0), (u1, v0), (u1, v1), (u0, v1))

    def sign_v(self, face, fx, fy, off, z, ch):
        return
        r = self.rng.choice(self.signs_meta["v"]); uv = self._uv_rect(r)
        w, hgt, dep = 1.5, 6.0, 1.6
        mb = self.M("signs", ch)
        n = {"w": (-1, 0), "e": (1, 0), "s": (0, -1), "n": (0, 1)}[face]
        if face in ("w", "e"):
            x, y = fx + n[0] * (0.2 + dep / 2), fy + off
            # blade: two faces parallel to the street direction (visible from both travel directions)
            for s in (-1, 1):
                xa = x + s * 0.12
                pts = [(xa - dep / 2 * n[0] * -1, y, z), (xa, y, z)]
            p0 = (fx + n[0] * 0.2, y, z); p1 = (fx + n[0] * (0.2 + dep), y, z)
            for sgn in (-1, 1):
                yy = y + sgn * 0.1
                a, b = (p0[0], yy), (p1[0], yy)
                if sgn > 0: a, b = b, a
                mb.quad((a[0], a[1], z), (b[0], b[1], z), (b[0], b[1], z + hgt), (a[0], a[1], z + hgt), (1.6, 1.6, 1.6, 1), ((uv[0][0], uv[0][1]), (uv[1][0], uv[0][1]), (uv[1][0], uv[2][1]), (uv[0][0], uv[2][1])))
                if self.q >= 2:
                    self.MR("signs").quad((a[0], a[1], -z), (b[0], b[1], -z), (b[0], b[1], -z - hgt), (a[0], a[1], -z - hgt), (0.8, 0.8, 0.8, 1), ((uv[0][0], uv[0][1]), (uv[1][0], uv[0][1]), (uv[1][0], uv[2][1]), (uv[0][0], uv[2][1])))
        else:
            x, y = fx + off, fy
            p0 = (x, fy + n[1] * 0.2); p1 = (x, fy + n[1] * (0.2 + dep))
            for sgn in (-1, 1):
                xx = x + sgn * 0.1
                a, b = (xx, p0[1]), (xx, p1[1])
                if sgn < 0: a, b = b, a
                mb.quad((a[0], a[1], z), (b[0], b[1], z), (b[0], b[1], z + hgt), (a[0], a[1], z + hgt), (1.6, 1.6, 1.6, 1), ((uv[0][0], uv[0][1]), (uv[1][0], uv[0][1]), (uv[1][0], uv[2][1]), (uv[0][0], uv[2][1])))
                if self.q >= 2:
                    self.MR("signs").quad((a[0], a[1], -z), (b[0], b[1], -z), (b[0], b[1], -z - hgt), (a[0], a[1], -z - hgt), (0.8, 0.8, 0.8, 1), ((uv[0][0], uv[0][1]), (uv[1][0], uv[0][1]), (uv[1][0], uv[2][1]), (uv[0][0], uv[2][1])))
        self.M("trim", ch).box(min(p0[0], p1[0]) - 0.08, min(p0[1], p1[1]) - 0.08, z - 0.15, max(p0[0], p1[0]) + 0.08, max(p0[1], p1[1]) + 0.08, z, (0.1, 0.1, 0.12, 1))

    def sign_flat(self, face, fx, fy, off, z, ch):
        return
        r = self.rng.choice(self.signs_meta["h"]); uv = self._uv_rect(r)
        w, hgt = 8.0, 2.0
        mb = self.M("signs", ch); d = 0.3
        if face == "s":   pts = [(fx + off - w / 2, fy - d), (fx + off + w / 2, fy - d)]
        elif face == "n": pts = [(fx + off + w / 2, fy + d), (fx + off - w / 2, fy + d)]
        elif face == "w": pts = [(fx - d, fy + off + w / 2), (fx - d, fy + off - w / 2)]
        else:             pts = [(fx + d, fy + off - w / 2), (fx + d, fy + off + w / 2)]
        (ax, ay), (bx, by) = pts
        mb.quad((ax, ay, z), (bx, by, z), (bx, by, z + hgt), (ax, ay, z + hgt), (1.6, 1.6, 1.6, 1), uv)
        if self.q >= 2:
            self.MR("signs").quad((ax, ay, -z), (bx, by, -z), (bx, by, -z - hgt), (ax, ay, -z - hgt), (0.8, 0.8, 0.8, 1), uv)

    def sign_h(self, cx, cy, z, w, hgt, ang, ch, frame=False):
        return
        r = self.rng.choice(self.signs_meta["h"]); uv = self._uv_rect(r)
        mb = self.M("signs", ch)
        hgt = w / 4.0
        if ang == 0:
            for s in (-1, 1):
                a, b = (cx - w / 2, cy + s * 0.15), (cx + w / 2, cy + s * 0.15)
                if s > 0: a, b = b, a
                mb.quad((a[0], a[1], z + 2), (b[0], b[1], z + 2), (b[0], b[1], z + 2 + hgt), (a[0], a[1], z + 2 + hgt), (1.5, 1.5, 1.5, 1), uv)
        else:
            for s in (-1, 1):
                a, b = (cx + s * 0.15, cy + w / 2), (cx + s * 0.15, cy - w / 2)
                if s > 0: a, b = b, a
                mb.quad((a[0], a[1], z + 2), (b[0], b[1], z + 2), (b[0], b[1], z + 2 + hgt), (a[0], a[1], z + 2 + hgt), (1.5, 1.5, 1.5, 1), uv)
        if frame:
            self.M("trim", ch).box(cx - 0.2, cy - 0.2, z, cx + 0.2, cy + 0.2, z + 2, (0.1, 0.1, 0.12, 1))

    def videoboard(self, fx, fy, cx, cy, ch):
        return
        # big screen on the corner facing the crossing
        z0, z1 = 18.0, 34.0; w = 26.0
        sx = 1 if cx > 0 else -1; sy = 1 if cy > 0 else -1
        x = fx - sx * 0.6; y0 = fy + sy * 4; y1 = y0 + sy * w
        if sx > 0: a, b = (x, y1), (x, y0)
        else: a, b = (x, y0), (x, y1)
        if sy < 0: a, b = b, a
        mb = MB("videoboard")
        mb.quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1), (1.3, 1.3, 1.3, 1))
        np_ = mb.node(); np_.reparent_to(self.root); np_.set_texture(self.T("videoboard.jpg", repeat=False)); np_.set_light_off(); np_.set_two_sided(True)
        self.anim.append((np_, "video"))
        self.M("trim", ch).box(min(a[0], b[0]) - 0.3, min(a[1], b[1]) - 0.3, z0 - 0.5, max(a[0], b[0]) + 0.3, max(a[1], b[1]) + 0.3, z0, (0.05, 0.05, 0.06, 1))

    def street_props(self, x0, y0, x1, y1, ch, dist):
        rng = self.rng
        pole = self.M("trim", ch); e = self.M("emit", ch)
        # street lights every ~30 m on each sidewalk edge
        for (ax, ay, bx, by, nx, ny) in ((x0, y0, x1, y0, 0, -1), (x1, y0, x1, y1, 1, 0), (x1, y1, x0, y1, 0, 1), (x0, y1, x0, y0, -1, 0)):
            L = math.hypot(bx - ax, by - ay); n = int(L // 30)
            for k in range(1, n + 1):
                t = k / (n + 1); px = ax + (bx - ax) * t - nx * 0.8; py = ay + (by - ay) * t - ny * 0.8
                pole.box(px - 0.12, py - 0.12, 0, px + 0.12, py + 0.12, 8.0, (0.15, 0.15, 0.17, 1))
                hx, hy = px + nx * 2.0, py + ny * 2.0
                pole.box(min(px, hx) - 0.1, min(py, hy) - 0.1, 7.8, max(px, hx) + 0.1, max(py, hy) + 0.1, 8.0, (0.15, 0.15, 0.17, 1))
                e.box(hx - 0.4, hy - 0.4, 7.6, hx + 0.4, hy + 0.4, 7.8, (2.2, 1.9, 1.5, 1), bottom=True)
                self.grid.add_circle(px, py, 0.3, "p")
                self.glow(hx, hy, 7.4, 3.2, (1.0, 0.75, 0.45))
                self.ground_pool(hx, hy, 6.0, (1.0, 0.7, 0.4, 0.22))
        # vending machines (glowing boxes)
        if False:
            for _ in range(2):
                side = rng.randrange(4)
                if side == 0: px, py = rng.uniform(x0 + 6, x1 - 6), y0 + D.SIDEWALK + 0.5; ang = 0
                elif side == 1: px, py = x1 - D.SIDEWALK - 0.5, rng.uniform(y0 + 6, y1 - 6); ang = 90
                elif side == 2: px, py = rng.uniform(x0 + 6, x1 - 6), y1 - D.SIDEWALK - 0.5; ang = 0
                else: px, py = x0 + D.SIDEWALK + 0.5, rng.uniform(y0 + 6, y1 - 6); ang = 90
                c = rng.choice([(0.9, 0.95, 1.3), (1.3, 0.4, 0.4), (0.4, 1.0, 1.3)])
                e.box(px - 0.5, py - 0.5, 0.15, px + 0.5, py + 0.5, 2.0, (c[0], c[1], c[2], 1))
        # trees in the residential district
        if dist == "sakura":
            for k in range(4):
                px = x0 + 10 + k * (x1 - x0 - 20) / 3; py = y0 + 1.6
                self.tree(px, py, ch, pink=False)

    def tree(self, x, y, ch, pink=False, palm=False, pine=False):
        t = self.M("flat", ch)
        if palm:
            h = self.rng.uniform(7, 10); lean = self.rng.uniform(-1.2, 1.2)
            segs = 6
            for k in range(segs):
                z0, z1 = h * k / segs, h * (k + 1) / segs
                ox0, ox1 = lean * (k / segs) ** 2, lean * ((k + 1) / segs) ** 2
                r = 0.22 - 0.02 * k / segs
                t.box(x + ox0 - r, y - r, z0, x + ox1 + r, y + r, z1, (0.30, 0.22, 0.15, 1))
            cx = x + lean
            for k in range(8):
                a = k * math.pi / 4 + self.rng.uniform(-0.2, 0.2); L = 3.6
                ex, ey = cx + math.cos(a) * L, y + math.sin(a) * L
                px_, py_ = -math.sin(a) * 0.5, math.cos(a) * 0.5
                t.quad((cx - px_, y - py_, h), (cx + px_, y + py_, h), (ex + px_ * 0.2, ey + py_ * 0.2, h - 1.6), (ex - px_ * 0.2, ey - py_ * 0.2, h - 1.6), (0.10, 0.32, 0.14, 1))
                t.quad((cx + px_, y + py_, h), (cx - px_, y - py_, h), (ex - px_ * 0.2, ey - py_ * 0.2, h - 1.6), (ex + px_ * 0.2, ey + py_ * 0.2, h - 1.6), (0.08, 0.26, 0.12, 1))
            self.grid.add_circle(x, y, 0.4, "p")
            return
        if pine:
            t.box(x - 0.25, y - 0.25, 0, x + 0.25, y + 0.25, 4.5, (0.25, 0.18, 0.12, 1))
            for k, (z, r) in enumerate(((3.5, 2.6), (5.0, 2.0), (6.3, 1.3))):
                t.box(x - r, y - r * 0.8, z, x + r, y + r * 0.8, z + 0.9, (0.06, 0.20, 0.10, 1))
            self.grid.add_circle(x, y, 0.4, "p")
            return
        t.box(x - 0.18, y - 0.18, 0.15, x + 0.18, y + 0.18, 3.0, (0.25, 0.18, 0.14, 1))
        c = (1.0, 0.55, 0.75, 1) if pink else (0.12, 0.3, 0.15, 1)
        t.box(x - 1.6, y - 1.6, 2.6, x + 1.6, y + 1.6, 5.0, c)
        t.box(x - 1.1, y - 1.1, 5.0, x + 1.1, y + 1.1, 5.8, c)
        self.grid.add_circle(x, y, 0.3, "p")

    def glow(self, x, y, z, size, col):
        if not hasattr(self, "_glow"):
            self._glow = MB("glows")
        g = self._glow; s = size / 2
        c = (col[0], col[1], col[2], 1)
        g.quad((x - s, y, z - s), (x + s, y, z - s), (x + s, y, z + s), (x - s, y, z + s), c, n=(0, -1, 0))
        g.quad((x, y - s, z - s), (x, y + s, z - s), (x, y + s, z + s), (x, y - s, z + s), c, n=(1, 0, 0))

    def ground_pool(self, x, y, r, col):
        if not hasattr(self, "_pools"):
            self._pools = MB("pools")
        self._pools.quad((x - r, y - r, 0.05), (x + r, y - r, 0.05), (x + r, y + r, 0.05), (x - r, y + r, 0.05), col, n=(0, 0, 1))

    def park(self, x0, y0, x1, y1, ch):
        g = self.M("flat", ch)
        g.quad((x0, y0, 0.16), (x1, y0, 0.16), (x1, y1, 0.16), (x0, y1, 0.16), (0.05, 0.12, 0.07, 1), n=(0, 0, 1))
        for k in range(10):
            a = k / 10 * 2 * math.pi
            self.tree((x0 + x1) / 2 + math.cos(a) * 30, (y0 + y1) / 2 + math.sin(a) * 30, ch)

    def build_tower(self, cx, cy, ch):
        """新光タワー: original lattice tower (red/white bands, warm lights)."""
        mb = self.M("flat", ch); e = self.M("emit", ch)
        H = 165.0; levels = 22
        def half(z):
            return 16.0 * (1 - z / H) ** 1.6 + 1.0
        for k in range(levels):
            z0 = H * 0.8 * k / levels; z1 = H * 0.8 * (k + 1) / levels
            h0, h1 = half(z0), half(z1)
            col = (0.50, 0.50, 0.52, 1) if (k // 2) % 2 == 0 else (0.62, 0.62, 0.64, 1)   # TVV tower: grey concrete/steel
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.box(cx + sx * h0 - 0.6, cy + sy * h0 - 0.6, z0, cx + sx * h1 + 0.6, cy + sy * h1 + 0.6, z1, col, top=False)
            # horizontal ring beams + diagonal braces
            for s in (-1, 1):
                mb.box(cx - h1, cy + s * h1 - 0.3, z1 - 0.4, cx + h1, cy + s * h1 + 0.3, z1, col)
                mb.box(cx + s * h1 - 0.3, cy - h1, z1 - 0.4, cx + s * h1 + 0.3, cy + h1, z1, col)
            # light strings on the legs
            for sx in (-1, 1):
                for sy in (-1, 1):
                    e.box(cx + sx * h1 - 0.15, cy + sy * h1 - 0.15, z1 - 0.2, cx + sx * h1 + 0.15, cy + sy * h1 + 0.15, z1 + 0.2, (2.2, 1.3, 0.5, 1))
        # observation decks
        for zd, r in ((60.0, 9.0), (110.0, 5.0)):
            mb.box(cx - r, cy - r, zd, cx + r, cy + r, zd + 5, (0.9, 0.9, 0.95, 1))
            e.box(cx - r - 0.1, cy - r - 0.1, zd + 2, cx + r + 0.1, cy + r + 0.1, zd + 3.2, (1.8, 1.5, 0.9, 1))
        mb.box(cx - 0.6, cy - 0.6, H * 0.8, cx + 0.6, cy + 0.6, H, (0.9, 0.2, 0.1, 1))
        e.box(cx - 0.9, cy - 0.9, H, cx + 0.9, cy + 0.9, H + 1.5, (3, 0.3, 0.2, 1))
        self.glow(cx, cy, H + 0.8, 10, (1, 0.2, 0.1))
        self.tower_top = (cx, cy, H)
        # tower name sign
        self.sign_h(cx, cy - 10.2, 54, 18, 4, 0, ch)

    def build_garage(self, x0, y0, x1, y1, ch):
        """FRGARAGE: low workshop with roller doors + big neon name sign facing the road (north side)."""
        mb = self.M("flat", ch); e = self.M("emit", ch)
        h = 12.0
        mb.box(x0, y0, 0, x1, y1, h, (0.12, 0.12, 0.15, 1))
        for k in range(3):
            dx = x0 + 14 + k * 18
            mb.box(dx, y1 - 0.2, 0.15, dx + 12, y1 + 0.05, 6.5, (0.3, 0.3, 0.34, 1))
            e.box(dx - 0.2, y1 + 0.05, 6.5, dx + 12.2, y1 + 0.25, 6.8, (0.3, 2.0, 2.4, 1))
        self.garage_sign = (x0 + (x1 - x0) / 2, y1 + 0.35, 8.0)
        e.box(x0, y1 - 0.1, h, x1, y1 + 0.1, h + 0.3, (2.4, 0.4, 1.4, 1))

    def build_highway(self):
        """elevated expressway (首都高-style, original) above the road x=-200, decorative with light streak traffic."""
        x = -200.0; z = 14.0; hw = 9.0
        mb = self.M("flat", (-1, 0)); e = self.M("emit", (-1, 0))
        y = -440.0
        mb.box(x - hw, -440, z, x + hw, 440, z + 1.2, (0.22, 0.22, 0.25, 1), bottom=True)
        mb.box(x - hw, -440, z + 1.2, x - hw + 0.4, 440, z + 2.6, (0.3, 0.3, 0.33, 1))
        mb.box(x + hw - 0.4, -440, z + 1.2, x + hw, 440, z + 2.6, (0.3, 0.3, 0.33, 1))
        e.box(x - hw - 0.05, -440, z + 2.5, x - hw + 0.05, 440, z + 2.7, (0.3, 1.6, 2.2, 1))
        e.box(x + hw - 0.05, -440, z + 2.5, x + hw + 0.05, 440, z + 2.7, (0.3, 1.6, 2.2, 1))
        yy = -430.0
        while yy < 430:
            near = min(abs(yy - n) for n in NODES_X)
            if near > 16:
                for s in (-1, 1):
                    px = x + s * (HW + 2.0)
                    mb.box(px - 0.7, yy - 0.7, 0, px + 0.7, yy + 0.7, z, (0.28, 0.28, 0.3, 1))
                    self.grid.add_circle(px, yy, 1.0, "p")
                mb.box(x - HW - 2.7, yy - 0.8, z - 1.5, x + HW + 2.7, yy + 0.8, z, (0.28, 0.28, 0.3, 1))
                self.glow(x - hw + 1, yy, z + 4.0, 2.0, (0.7, 0.9, 1.0))
            yy += 28
        # light-streak traffic on the deck (animated texture-less boxes)
        lanes = MB("hwcars")
        for k in range(40):
            yy = -440 + k * 22 + self.rng.uniform(0, 10); s = -1 if k % 2 else 1
            lx = x + s * 3.5
            c = (2.5, 2.3, 2.0, 1) if s > 0 else (2.5, 0.2, 0.2, 1)
            lanes.box(lx - 0.8, yy, z + 1.4, lx + 0.8, yy + 3.5, z + 2.4, c)
        self.hwcars = lanes.node(); self.hwcars.reparent_to(self.root); self.hwcars.set_light_off()
        self.anim.append((self.hwcars, "hw"))

    def build_beach(self):
        ch = (2, 0)
        g = self.M("flat", ch); sw = self.M("sidewalk", ch)
        # promenade grass strip between the city ring road and the coast road
        g.quad((411, -440, 0.01), (452, -440, 0.01), (452, 440, 0.01), (411, 440, 0.01), (0.05, 0.10, 0.06, 1), n=(0, 0, 1))
        # boardwalk
        bw = self.M("wood", ch)
        for k in range(-44, 44):
            y0 = k * 10
            bw.quad((D.BOARDWALK[0], y0, 0.2), (D.BOARDWALK[1], y0, 0.2), (D.BOARDWALK[1], y0 + 9.8, 0.2), (D.BOARDWALK[0], y0 + 9.8, 0.2), (0.38, 0.25, 0.16, 1), n=(0, 0, 1))
        g.quad((468, -440, 0.01), (D.SAND[0], -440, 0.01), (D.SAND[0], 440, 0.01), (468, 440, 0.01), (0.2, 0.18, 0.15, 1), n=(0, 0, 1))
        # sand with a soft gradient to the waterline
        s = self.M("sand", ch)
        s.quad((D.SAND[0], -440, 0.02), (D.SEA_X + 4, -440, -0.15), (D.SEA_X + 4, 440, -0.15), (D.SAND[0], 440, 0.02),
               ((0.55, 0.47, 0.36, 1), (0.30, 0.27, 0.24, 1), (0.30, 0.27, 0.24, 1), (0.55, 0.47, 0.36, 1)), n=(0, 0, 1))
        # drift lot (asphalt) with neon edge
        r = D.DRIFT_ZONE["rect"]; a = self.M("asphalt", ch)
        a.quad((r[0], r[1], 0.04), (r[2], r[1], 0.04), (r[2], r[3], 0.04), (r[0], r[3], 0.04), (1, 1, 1, 1),
               ((r[0] / 12, r[1] / 12), (r[2] / 12, r[1] / 12), (r[2] / 12, r[3] / 12), (r[0] / 12, r[3] / 12)), n=(0, 0, 1))
        e = self.M("emit", ch)
        for (ax, ay, bx, by) in ((r[0], r[1], r[2], r[1]), (r[2], r[1], r[2], r[3]), (r[2], r[3], r[0], r[3]), (r[0], r[3], r[0], r[1])):
            e.box(min(ax, bx) - 0.15, min(ay, by) - 0.15, 0.04, max(ax, bx) + 0.15, max(ay, by) + 0.15, 0.12, (2.4, 0.3, 1.6, 1))
        # pier
        pw = self.M("wood", ch)
        pw.box(560, 140, -0.6, 690, 156, 0.3, (0.32, 0.22, 0.14, 1))
        for k in range(0, 130, 12):
            pw.box(560 + k, 139.5, -3, 561 + k, 140.5, 1.3, (0.25, 0.17, 0.1, 1)); pw.box(560 + k, 155.5, -3, 561 + k, 156.5, 1.3, (0.25, 0.17, 0.1, 1))
            self.glow(560.5 + k, 140, 1.6, 1.4, (1.0, 0.8, 0.5)); self.glow(560.5 + k, 156, 1.6, 1.4, (1.0, 0.8, 0.5))
        self.grid.add_rect((560, 139.0, 690, 139.6), "w"); self.grid.add_rect((560, 156.4, 690, 157.0), "w")
        # sea
        sea = MB("sea")
        sea.quad((D.SEA_X, -2000, -0.3), (3000, -2000, -0.3), (3000, 2000, -0.3), (D.SEA_X, 2000, -0.3), (1, 1, 1, 1),
                 ((0, 0), (300, 0), (300, 400), (0, 400)), n=(0, 0, 1))
        self.sea = sea.node(); self.sea.reparent_to(self.root)
        sh = MB("shallow")
        sh.quad((D.SEA_X - 2, -2000, -0.22), (D.SEA_X + 70, -2000, -0.22), (D.SEA_X + 70, 2000, -0.22), (D.SEA_X - 2, 2000, -0.22),
                ((0.25, 0.95, 0.85, 0.9), (0.10, 0.55, 0.70, 0.0), (0.10, 0.55, 0.70, 0.0), (0.25, 0.95, 0.85, 0.9)), n=(0, 0, 1))
        self.shallow = sh.node(); self.shallow.reparent_to(self.root)
        # palms + pines + beach huts with neon (海の家-style, original names)
        rng = self.rng
        for y in range(-430, 431, 22):
            if -316 < y < -276: continue          # ANA & DANIEL'S HOUSE plot
            self.tree(440 + rng.uniform(-6, 6), y + rng.uniform(-4, 4), ch, palm=True)
            if rng.random() < 0.6:
                tx_, ty_, pl_ = rng.uniform(490, 580), y + rng.uniform(-8, 8), rng.random() < 0.7
                if not self.in_stadium(tx_, ty_, 4): self.tree(tx_, ty_, ch, palm=pl_, pine=True)
        for k, y in enumerate((-160, -40, 60, 260, 360)):
            x0 = 486; x1 = 506
            g.box(x0, y, 0, x1, y + 14, 4.5, (0.55, 0.42, 0.3, 1))
            g.box(x0 - 1, y - 1, 4.5, x1 + 1, y + 15, 5.0, (0.2, 0.3, 0.45, 1))
            self.grid.add_rect((x0, y, x1, y + 14), "b")
            self.sign_flat("w", x0, y + 7, 0, 3.0, ch)
            self.glow(x0 - 0.5, y + 2, 3.0, 2.0, (1.0, 0.6, 0.3))
        # lifeguard towers
        for y in (-300, 100, 320):
            g.box(560, y, 0, 563, y + 3, 3.5, (0.9, 0.9, 0.9, 1)); g.box(559.5, y - 0.5, 3.5, 563.5, y + 3.5, 4.5, (0.9, 0.2, 0.15, 1))
            self.grid.add_rect((560, y, 563, y + 3), "b")
        # --- extra beach life: dune mounds, umbrellas + loungers, more neon huts, boardwalk lamps, shoreline foam, parked cars
        for k in range(60):
            dx, dy = rng.uniform(482, 590), rng.uniform(-420, 420)
            if r[0] - 4 < dx < r[2] + 4 and r[1] - 4 < dy < r[3] + 4: continue
            if self.in_stadium(dx, dy, 20): continue
            w_, l_ = rng.uniform(6, 16), rng.uniform(8, 22); c0 = rng.uniform(0.47, 0.6)
            s.quad((dx - w_, dy - l_, 0.05), (dx + w_, dy - l_, 0.05), (dx + w_, dy + l_, 0.05), (dx - w_, dy + l_, 0.05), (c0, c0 * 0.86, c0 * 0.66, 1), n=(0, 0, 1))
            self.dunes.append((dx - w_, dy - l_, dx + w_, dy + l_))
        cols = [(0.95, 0.2, 0.3), (0.2, 0.6, 1.0), (1.0, 0.85, 0.2), (0.3, 0.9, 0.5), (1.0, 0.5, 0.1), (0.8, 0.3, 0.9)]
        for k in range(70):
            ux, uy = rng.uniform(515, 592), rng.uniform(-420, 420)
            if r[0] - 6 < ux < r[2] + 6 and r[1] - 6 < uy < r[3] + 6: continue
            if 130 < uy < 166: continue
            if self.in_stadium(ux, uy, 3): continue
            c = rng.choice(cols)
            g.box(ux - 0.05, uy - 0.05, 0, ux + 0.05, uy + 0.05, 2.3, (0.9, 0.9, 0.9, 1))
            g.box(ux - 1.3, uy - 1.3, 2.2, ux + 1.3, uy + 1.3, 2.45, (c[0], c[1], c[2], 1))
            g.box(ux - 0.9, uy - 0.4, 2.45, ux + 0.9, uy + 0.4, 2.55, (1, 1, 1, 1))
            for sx in (-1, 1):
                g.box(ux + sx * 1.1 - 0.35, uy + 1.4, 0, ux + sx * 1.1 + 0.35, uy + 3.2, 0.35, (0.95, 0.95, 0.92, 1))
            self.grid.add_circle(ux, uy, 0.15, "p")
        for k, y in enumerate((-410, -330, -100, 0, 160, 210, 310, 410)):
            x0 = 486; x1 = 504; c = cols[k % len(cols)]
            g.box(x0, y, 0, x1, y + 12, 4.0, (0.85, 0.82, 0.75, 1))
            g.box(x0 - 2.2, y, 3.0, x0, y + 12, 3.25, (c[0], c[1], c[2], 1))       # awning toward the boardwalk
            self.grid.add_rect((x0, y, x1, y + 12), "b")
            self.sign_flat("w", x0, y + 6, 0, 3.6, ch)
            e.box(x0 - 0.12, y + 0.5, 0.4, x0 - 0.05, y + 11.5, 2.6, (1.6, 1.4, 1.0, 1))   # lit shop window
            self.glow(x0 - 1.5, y + 6, 2.6, 3.0, (c[0], c[1], c[2]))
        for y in range(-430, 431, 25):
            g.box(469.0, y - 0.1, 0.2, 469.2, y + 0.1, 4.2, (0.2, 0.2, 0.22, 1))
            e.box(468.8, y - 0.3, 4.2, 469.4, y + 0.3, 4.5, (2.0, 1.7, 1.2, 1)); self.glow(469.1, y, 4.2, 2.6, (1.0, 0.75, 0.45))
            self.grid.add_circle(469.1, y, 0.2, "p")
        foam = self.M("emit", ch)
        for k in range(3):
            x = D.SEA_X - 1.5 + k * 3.5
            foam.quad((x, -440, -0.05 + k * 0.01), (x + 1.2, -440, -0.05 + k * 0.01), (x + 1.2, 440, -0.05 + k * 0.01), (x, 440, -0.05 + k * 0.01), (0.7, 0.8, 0.85, 1), n=(0, 0, 1))
        for y in range(-400, 401, 14):
            if rng.random() < 0.5: self.parking.append((D.BEACH_ROAD_X + 5.5, y + 0.0, 0.0 if rng.random() < 0.5 else 180.0))
        # beach ped loop along the boardwalk
        self.ped_loops.append([(472, -400), (476, -400), (476, 400), (472, 400)])
        self.ped_loops.append([(520, -200), (560, -200), (560, 160), (520, 160)])
        self.ped_loops.append([(512, -400), (596, -400), (596, -250), (512, -250)])
        self.ped_loops.append([(512, 304), (596, 304), (596, 400), (512, 400)])
        # v1.0.5: SHINE SFC 27 STADIUM (pitch, stands, goals, gate) - fs_sfc builds it into the beach chunk
        pass   # (no stadium in Valdora)

    def build_bounds(self):
        W = D.WORLD
        for r in ((W[0] - 20, W[1] - 20, W[0], W[3] + 20), (W[0] - 20, W[1] - 20, W[2] + 20, W[1]),
                  (W[0] - 20, W[3], W[2] + 20, W[3] + 20), (W[2], W[1] - 20, W[2] + 20, W[3] + 20)):
            self.grid.add_rect(r, "w")
        e = self.M("emit", (9, 9)); mb = self.M("flat", (9, 9))
        for (x0, y0, x1, y1) in ((W[0] - 1, W[1], W[0], W[3]), (W[0], W[1] - 1, 452, W[1]), (W[0], W[3], 452, W[3] + 1)):
            mb.box(x0, y0, 0, x1, y1, 1.0, (0.4, 0.4, 0.45, 1))
            e.box(x0, y0, 1.0, x1, y1, 1.15, (2.0, 0.5, 0.2, 1))
        # ring road ends: block coast road ends
        for y in (W[1], W[3]):
            pass

    def build_home(self):
        """ANA & DANIEL'S HOUSE: modern 2-storey Japanese home with carport + an off-map interior set."""
        ch = (2, 0); g = self.M("flat", ch); e = self.M("emit", ch); w = self.M("wood", ch)
        g.quad((413, -306, 0.03), (452, -306, 0.03), (452, -280, 0.03), (413, -280, 0.03), (0.10, 0.16, 0.09, 1), n=(0, 0, 1))   # lawn
        g.quad((429, -299, 0.05), (452, -299, 0.05), (452, -290, 0.05), (429, -290, 0.05), (0.42, 0.42, 0.44, 1), n=(0, 0, 1))   # driveway
        g.quad((429, -288.2, 0.05), (452, -288.2, 0.05), (452, -286.6, 0.05), (429, -286.6, 0.05), (0.62, 0.60, 0.56, 1), n=(0, 0, 1))  # path
        g.box(415, -302, 0, 429, -287, 3.4, (0.90, 0.89, 0.86, 1))                          # white ground floor
        w.box(414, -303, 3.4, 431, -291, 6.7, (0.30, 0.20, 0.13, 1))                         # cantilevered timber upper floor
        g.box(413.6, -303.4, 6.7, 431.4, -290.6, 7.0, (0.16, 0.16, 0.18, 1))                 # roof slab
        g.box(415, -290, 6.6, 429, -287, 6.8, (0.16, 0.16, 0.18, 1))
        e.box(429.0, -301.5, 0.5, 429.12, -292.5, 2.9, (1.5, 1.15, 0.75, 1))                 # living-room glazing (warm)
        e.box(431.0, -302.2, 4.1, 431.12, -294.0, 5.9, (0.75, 0.95, 1.5, 1))                 # bedroom glazing (cool)
        w.box(429.0, -289.6, 0, 429.25, -288.2, 2.4, (0.20, 0.12, 0.07, 1))                  # front door
        e.box(429.3, -290.2, 2.5, 429.4, -287.6, 2.62, (2.4, 0.5, 1.6, 1))                    # pink neon strip over the door
        self.glow(429.6, -288.9, 2.6, 2.2, (1.0, 0.4, 0.8)); self.glow(429.6, -297, 3.0, 4.0, (1.0, 0.7, 0.4))
        g.box(431, -299.5, 2.9, 447, -289.5, 3.15, (0.28, 0.28, 0.30, 1))                    # carport roof
        for py in (-299.2, -289.8):
            g.box(446.6, py - 0.15, 0, 446.9, py + 0.15, 2.9, (0.75, 0.75, 0.78, 1)); self.grid.add_circle(446.75, py, 0.25, "p")
        e.box(432, -295.0, 2.85, 446, -294.7, 2.9, (1.6, 1.5, 1.3, 1))                      # carport light bar
        g.box(413, -305.0, 0, 431, -304.6, 1.2, (0.55, 0.53, 0.5, 1)); g.box(412.6, -305, 0, 413, -280, 1.2, (0.55, 0.53, 0.5, 1))
        self.tree(419, -283, ch); self.tree(424, -283.5, ch)
        self.grid.add_rect((414, -303, 429.3, -287), "b"); self.grid.add_rect((412.6, -305, 431, -304.6), "w")
        self.home_sign = (429.5, -288.9, 3.4)
        # ---- interior set (living room + kitchen + bedroom), lit warm, neon city in the window
        X, Y = D.HOME_INT; m = MB("home_int")
        m.quad((X - 7, Y - 5, 0), (X + 7, Y - 5, 0), (X + 7, Y + 5, 0), (X - 7, Y + 5, 0), (0.42, 0.28, 0.17, 1), n=(0, 0, 1))      # oak floor
        m.box(X - 7.2, Y + 5, 0, X + 7.2, Y + 5.2, 3.2, (0.86, 0.84, 0.80, 1)); m.box(X - 7.2, Y - 5.2, 0, X + 7.2, Y - 5, 3.2, (0.86, 0.84, 0.80, 1))
        m.box(X - 7.2, Y - 5, 0, X - 7, Y + 5, 3.2, (0.80, 0.78, 0.74, 1)); m.box(X + 7, Y - 5, 0, X + 7.2, Y + 5, 3.2, (0.80, 0.78, 0.74, 1))
        m.quad((X - 7, Y - 5, 3.2), (X - 7, Y + 5, 3.2), (X + 7, Y + 5, 3.2), (X + 7, Y - 5, 3.2), (0.7, 0.68, 0.65, 1), n=(0, 0, -1))  # ceiling
        m.box(X - 1.6, Y - 5, 0, X - 1.45, Y + 1.5, 3.2, (0.82, 0.80, 0.76, 1))               # partition: bedroom on the left
        m.quad((X - 6, Y - 1, 0.01), (X + 4, Y - 1, 0.01), (X + 4, Y + 3, 0.01), (X - 6, Y + 3, 0.01), (0.30, 0.32, 0.38, 1), n=(0, 0, 1))  # rug
        # sofa + coffee table + TV
        m.box(X - 0.5, Y + 2.0, 0, X + 3.0, Y + 3.0, 0.45, (0.12, 0.45, 0.48, 1)); m.box(X - 0.5, Y + 2.75, 0.45, X + 3.0, Y + 3.0, 1.0, (0.12, 0.45, 0.48, 1))
        m.box(X - 0.7, Y + 2.0, 0, X - 0.5, Y + 3.0, 0.7, (0.10, 0.40, 0.43, 1)); m.box(X + 3.0, Y + 2.0, 0, X + 3.2, Y + 3.0, 0.7, (0.10, 0.40, 0.43, 1))
        m.box(X + 0.4, Y + 0.6, 0, X + 2.1, Y + 1.3, 0.42, (0.20, 0.13, 0.08, 1))
        m.box(X - 0.2, Y - 4.95, 0, X + 2.7, Y - 4.5, 0.55, (0.08, 0.08, 0.09, 1))
        m.box(X + 0.0, Y - 4.9, 0.9, X + 2.5, Y - 4.8, 2.3, (0.02, 0.02, 0.03, 1))
        m.quad((X + 0.08, Y - 4.79, 0.98), (X + 2.42, Y - 4.79, 0.98), (X + 2.42, Y - 4.79, 2.22), (X + 0.08, Y - 4.79, 2.22),
               ((0.3, 0.5, 1.6, 1), (1.4, 0.3, 1.1, 1), (1.6, 0.6, 0.9, 1), (0.4, 0.9, 1.6, 1)), n=(0, 1, 0))           # TV picture
        m.quad((X + 2.42, Y - 4.785, 0.98), (X + 0.08, Y - 4.785, 0.98), (X + 0.08, Y - 4.785, 2.22), (X + 2.42, Y - 4.785, 2.22),
               ((1.6, 0.6, 0.9, 1), (0.3, 0.5, 1.6, 1), (0.4, 0.9, 1.6, 1), (1.4, 0.3, 1.1, 1)), n=(0, 1, 0))           # v1.0.3: picture faces the room
        # kitchen along the right wall
        m.box(X + 5.3, Y - 4.6, 0, X + 6.95, Y + 1.0, 0.92, (0.93, 0.93, 0.92, 1)); m.box(X + 5.25, Y - 4.65, 0.92, X + 6.98, Y + 1.05, 0.97, (0.22, 0.22, 0.24, 1))
        m.box(X + 6.4, Y - 4.6, 1.6, X + 6.95, Y + 1.0, 2.4, (0.93, 0.93, 0.92, 1)); m.box(X + 5.3, Y + 1.3, 0, X + 6.95, Y + 2.3, 2.1, (0.70, 0.72, 0.75, 1))
        m.box(X + 3.6, Y - 2.6, 0, X + 4.6, Y - 0.6, 0.92, (0.25, 0.16, 0.10, 1))            # island
        for k in range(3): m.box(X + 3.3, Y - 2.4 + k * 0.7, 0, X + 3.55, Y - 2.15 + k * 0.7, 0.7, (0.1, 0.1, 0.1, 1))
        # bedroom: bed + wardrobe
        m.box(X - 6.9, Y - 3.6, 0, X - 4.6, Y - 0.6, 0.35, (0.20, 0.13, 0.08, 1)); m.box(X - 6.85, Y - 3.55, 0.35, X - 4.65, Y - 0.65, 0.6, (0.95, 0.95, 0.93, 1))
        m.box(X - 6.0, Y - 3.5, 0.6, X - 4.7, Y - 0.7, 0.68, (0.85, 0.32, 0.30, 1)); m.box(X - 6.9, Y - 3.6, 0.35, X - 6.75, Y - 0.6, 1.3, (0.20, 0.13, 0.08, 1))
        m.box(X - 6.7, Y - 3.3, 0.6, X - 6.2, Y - 2.3, 0.78, (1, 1, 1, 1)); m.box(X - 6.7, Y - 1.9, 0.6, X - 6.2, Y - 0.9, 0.78, (1, 1, 1, 1))
        m.box(X - 4.3, Y - 4.95, 0, X - 1.9, Y - 4.3, 2.4, (0.26, 0.17, 0.10, 1))             # WARDROBE
        m.box(X - 3.13, Y - 4.31, 0.2, X - 3.07, Y - 4.29, 2.2, (0.1, 0.06, 0.04, 1))
        m.box(X - 3.3, Y - 4.3, 1.1, X - 3.2, Y - 4.22, 1.4, (0.8, 0.7, 0.4, 1)); m.box(X - 3.0, Y - 4.3, 1.1, X - 2.9, Y - 4.22, 1.4, (0.8, 0.7, 0.4, 1))
        # lamps
        m.box(X + 3.6, Y + 2.5, 0, X + 3.7, Y + 2.6, 1.6, (0.1, 0.1, 0.1, 1)); m.box(X + 3.4, Y + 2.3, 1.6, X + 3.9, Y + 2.8, 1.95, (2.2, 1.7, 1.1, 1))
        m.box(X - 1.0, Y - 1.0, 3.12, X + 1.0, Y + 1.0, 3.2, (2.0, 1.8, 1.5, 1)); m.box(X - 6.0, Y - 2.6, 3.12, X - 5.0, Y - 1.6, 3.2, (1.8, 1.5, 1.2, 1))
        # bathroom corner: walk-in shower (tiled wall, tray, chrome frame, rain head)
        m.box(X - 6.99, Y + 1.0, 0, X - 6.95, Y + 2.9, 2.6, (0.55, 0.75, 0.82, 1))
        m.box(X - 7.0, Y + 1.0, 0, X - 5.3, Y + 1.06, 2.6, (0.55, 0.75, 0.82, 1))
        m.box(X - 6.95, Y + 1.06, 0, X - 5.35, Y + 2.85, 0.07, (0.95, 0.95, 0.96, 1))
        for (px, py) in ((X - 5.35, Y + 2.85), (X - 5.35, Y + 1.06)): m.box(px - 0.03, py - 0.03, 0, px + 0.03, py + 0.03, 2.4, (0.85, 0.86, 0.9, 1))
        m.box(X - 6.95, Y + 2.82, 2.37, X - 5.32, Y + 2.88, 2.43, (0.85, 0.86, 0.9, 1)); m.box(X - 5.38, Y + 1.06, 2.37, X - 5.32, Y + 2.88, 2.43, (0.85, 0.86, 0.9, 1))
        m.box(X - 6.4, Y + 1.7, 2.3, X - 5.9, Y + 2.2, 2.36, (0.8, 0.8, 0.85, 1)); m.box(X - 6.95, Y + 1.92, 1.6, X - 6.2, Y + 1.98, 2.33, (0.8, 0.8, 0.85, 1))
        self.shower_pos = (X - 6.15, Y + 1.95)
        # v1.0.3 free roam: front door (inside), a laptop on the coffee table, collision + camera walls + interaction spots
        m.box(X + 3.4, Y - 5.0, 0, X + 4.6, Y - 4.9, 2.25, (0.30, 0.19, 0.11, 1))                 # front door (inside)
        m.box(X + 3.45, Y - 4.92, 0, X + 4.55, Y - 4.88, 2.2, (0.36, 0.23, 0.13, 1))
        m.box(X + 4.35, Y - 4.9, 1.0, X + 4.45, Y - 4.82, 1.1, (0.85, 0.75, 0.4, 1))               # handle
        m.box(X + 3.3, Y - 4.95, 2.3, X + 4.7, Y - 4.88, 2.38, (2.4, 0.5, 1.6, 1))                 # pink neon over the door
        m.box(X + 1.0, Y + 0.80, 0.42, X + 1.6, Y + 1.15, 0.44, (0.15, 0.15, 0.17, 1))             # laptop base
        m.quad((X + 1.0, Y + 1.15, 0.44), (X + 1.6, Y + 1.15, 0.44), (X + 1.6, Y + 1.22, 0.80), (X + 1.0, Y + 1.22, 0.80),
               (0.4, 0.8, 1.6, 1), n=(0, -1, 0.2))                                                   # laptop screen (glows)
        from fs_world import Grid as _G
        hg = self.home_grid = _G(cell=4.0)
        walls = [(X - 7.3, Y + 4.95, X + 7.3, Y + 5.4), (X - 7.3, Y - 5.4, X + 7.3, Y - 4.95), (X - 7.4, Y - 5.4, X - 6.95, Y + 5.4),
                 (X + 6.95, Y - 5.4, X + 7.4, Y + 5.4), (X - 1.62, Y - 5.0, X - 1.43, Y + 1.5),                       # outer walls + bedroom partition
                 (X - 7.0, Y + 0.98, X - 5.3, Y + 1.08), (X - 5.40, Y + 1.06, X - 5.30, Y + 2.85),                    # shower tile wall + glass
                 (X + 5.3, Y - 4.65, X + 7.0, Y + 1.05), (X + 5.3, Y + 1.3, X + 7.0, Y + 2.3), (X - 4.3, Y - 5.0, X - 1.9, Y - 4.3)]   # kitchen, fridge, wardrobe
        furn = [(X - 0.7, Y + 2.0, X + 3.2, Y + 3.0), (X + 0.4, Y + 0.6, X + 2.1, Y + 1.3), (X - 0.2, Y - 5.0, X + 2.7, Y - 4.5),
                (X + 3.6, Y - 2.6, X + 4.6, Y - 0.6), (X + 3.25, Y - 2.45, X + 3.6, Y - 0.65), (X - 6.9, Y - 3.6, X - 4.6, Y - 0.6),
                (X + 3.55, Y + 2.45, X + 3.75, Y + 2.65)]
        for r in walls + furn: hg.add_rect(r, "b")
        self.home_cam_rects = walls                       # tall things the camera must not pass through
        self.home_bounds = (X - 6.85, Y - 4.85, X + 6.85, Y + 4.85)
        # (id, label, x, y, radius)  - walk up to one and press E / click the button
        self.home_spots = [("shower", "SHOWER", X - 6.1, Y + 2.3, 1.1), ("wardrobe", "WARDROBE", X - 3.1, Y - 3.7, 1.2),
                           ("sleep", "SLEEP", X - 4.1, Y - 2.1, 1.1), ("save", "SAVE GAME", X + 0.75, Y + 0.25, 0.7), ("laptop", "USE LAPTOP", X + 1.75, Y + 0.25, 0.7),
                           ("tv", "WATCH TV", X + 1.25, Y - 3.6, 1.2), ("eat", "EAT SNACK", X + 4.65, Y + 1.8, 1.0),
                           ("leave", "LEAVE HOME", X + 4.0, Y - 4.25, 1.1)]
        self.home_int = m.node(); self.home_int.reparent_to(self.root); self.home_int.set_light_off(); self.home_int.set_color_scale(0.92, 0.92, 0.92, 1)   # v1.0.4: no washed-out walls
        gl = MB("shower_glass")
        gl.quad((X - 5.35, Y + 1.06, 0.07), (X - 5.35, Y + 2.85, 0.07), (X - 5.35, Y + 2.85, 2.4), (X - 5.35, Y + 1.06, 2.4), (0.75, 0.9, 1.0, 0.16), n=(1, 0, 0))
        g2 = gl.node(); g2.reparent_to(self.home_int); g2.set_transparency(TransparencyAttrib.M_alpha); g2.set_two_sided(True); g2.set_depth_write(False); g2.set_bin("transparent", 20)
        # big window on the back wall with the neon city at night
        wm = MB("home_win")
        wm.quad((X - 1.0, Y + 4.98, 0.9), (X - 6.6, Y + 4.98, 0.9), (X - 6.6, Y + 4.98, 2.8), (X - 1.0, Y + 4.98, 2.8), (1.4, 1.4, 1.5, 1),
                ((0, 0.1), (1.4, 0.1), (1.4, 0.6), (0, 0.6)), n=(0, -1, 0))
        wm.quad((X + 4.8, Y + 4.98, 0.9), (X - 0.4, Y + 4.98, 0.9), (X - 0.4, Y + 4.98, 2.8), (X + 4.8, Y + 4.98, 2.8), (1.4, 1.4, 1.5, 1),
                ((0.3, 0.1), (1.6, 0.1), (1.6, 0.6), (0.3, 0.6)), n=(0, -1, 0))
        self.home_win = wm.node(); self.home_win.reparent_to(self.home_int); self.home_win.set_texture(self.T("facade0.png"), 1)
        self.home_win.set_two_sided(True); self.home_int.hide()

    def build_skyline(self):
        """distant (non-collidable) skyline around the playable area."""
        rng = self.rng
        for k in range(160):
            a = rng.uniform(0, 2 * math.pi)
            if -0.7 < math.cos(a) and math.cos(a) > 0.55 and abs(math.sin(a)) < 0.8:
                continue     # leave the sea view open to the east
            r = rng.uniform(620, 900)
            x, y = math.cos(a) * r, math.sin(a) * r
            if x > 380: continue
            glass = rng.random() < 0.6
            w = rng.uniform(16, 34) if glass else rng.uniform(25, 60); h = rng.uniform(140, 340) if glass else rng.uniform(60, 200)
            fac = "facade6" if glass else "facade%d" % rng.randrange(4)
            UV = lambda f, ww, hh: ((0, 0), (ww / 32.0, 0), (ww / 32.0, hh / 28.0), (0, hh / 28.0))
            hb = h * rng.uniform(0.6, 0.8) if glass else h
            self.M(fac, (8, 8)).box(x - w / 2, y - w / 2, 0, x + w / 2, y + w / 2, hb, (0.7, 0.7, 0.85, 1) if not glass else (1, 1, 1, 1), top=False, uvs=UV)
            if glass:     # setback upper section + crown
                w2 = w * rng.uniform(0.6, 0.8)
                self.M(fac, (8, 8)).box(x - w2 / 2, y - w2 / 2, hb, x + w2 / 2, y + w2 / 2, h, (1, 1, 1, 1), top=False, uvs=UV)
                self.M("flat", (8, 8)).box(x - w / 2, y - w / 2, hb - 0.5, x + w / 2, y + w / 2, hb + 0.6, (0.75, 0.78, 0.82, 1))
                self.M("flat", (8, 8)).box(x - w2 / 2 - 0.4, y - w2 / 2 - 0.4, h, x + w2 / 2 + 0.4, y + w2 / 2 + 0.4, h + 6, (0.8, 0.83, 0.88, 1))
                if rng.random() < 0.5: self.M("flat", (8, 8)).box(x - 0.5, y - 0.5, h + 6, x + 0.5, y + 0.5, h + 26, (0.7, 0.7, 0.75, 1))
            if rng.random() < 0.4:
                nc = rng.choice(D.NEON)
                self.M("emit", (8, 8)).box(x - w / 2 - 0.2, y - w / 2 - 0.2, h, x + w / 2 + 0.2, y + w / 2 + 0.2, h + 0.6, (nc[0] * 2, nc[1] * 2, nc[2] * 2, 1))
            if rng.random() < 0.5:
                self.glow(x, y, h + 3, 6, (1, 0.1, 0.1))

    def flush(self):
        texmap = {"asphalt": "asphalt.png", "sidewalk": "sidewalk.png", "facade0": "facade0.png", "facade1": "facade1.png",
                  "facade2": "facade2.png", "facade3": "facade3.png", "facade4": "facade4.png", "facade5": "facade5.png", "facade6": "facade6.png", "shopfront": "shopfront.png", "signs": "signs.png", "flag": "flag.jpg"}
        self.fac_nodes = []; self.emit_nodes = []; self.ground_np = None; self.shop_nps = []
        self.static = self.root.attach_new_node("static")
        self.static.set_light_off()
        ground = self.root.attach_new_node("ground")
        for (ch, mat), mb in self.mb.items():
            if not len(mb):
                continue
            np_ = mb.node()
            if mat in texmap:
                np_.set_texture(self.T(texmap[mat], repeat=mat != "signs"))
            if mat == "asphalt":
                np_.reparent_to(ground); np_.set_transparency(TransparencyAttrib.M_alpha); np_.set_bin("transparent", 1)
                np_.set_depth_write(True)
            elif mat == "marking":
                np_.reparent_to(ground); np_.set_color_scale(0.75, 0.75, 0.78, 1); np_.set_bin("transparent", 2)
                np_.set_transparency(TransparencyAttrib.M_alpha); np_.set_alpha_scale(0.8); np_.set_depth_offset(1)
            elif mat in ("sidewalk", "kerb", "sand", "wood", "ground"):
                np_.reparent_to(ground)
            else:
                np_.reparent_to(self.static)
            if mat in ("signs", "emit", "flag"):
                np_.set_two_sided(mat in ("signs", "flag"))
            if mat.startswith("facade"): self.fac_nodes.append((np_, mat))
            if mat in ("signs", "emit"): self.emit_nodes.append(np_)
            if mat == "shopfront": self.shop_nps.append(np_)
            if mat == "flag":
                np_.set_texture(self.T("flag.jpg", repeat=False))
        # reflections (mirrored world under the translucent asphalt)
        self.refl = self.root.attach_new_node("reflections")
        for mat, mb in self.mirror.items():
            if not len(mb):
                continue
            np_ = mb.node(); np_.reparent_to(self.refl)
            if mat.startswith("facade"): self.fac_nodes.append((np_, mat))
            if mat in texmap:
                np_.set_texture(self.T(texmap[mat], repeat=mat != "signs"))
            np_.set_two_sided(True)
        self.refl.set_light_off(); self.refl.set_bin("background", 5); self.refl.set_color_scale(0.85, 0.8, 0.95, 1)
        ground.set_light_off(); self.ground_np = ground
        # glows (additive, no depth write)
        for nm in ("_glow", "_pools"):
            if hasattr(self, nm):
                np_ = getattr(self, nm).node(); np_.reparent_to(self.root)
                self.glow_nodes = getattr(self, "glow_nodes", []) + [np_]
                np_.set_texture(self.T("glow.png", repeat=False)); np_.set_light_off()
                np_.set_attrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one))
                np_.set_depth_write(False); np_.set_bin("fixed", 10); np_.set_two_sided(True)
                if False and nm == "_glow" and self.q >= 2:     # v1.0.4: no mirrored halos either
                    m = np_.copy_to(self.refl); m.set_sz(-1); m.set_color_scale(0.5, 0.5, 0.5, 1)
        # the sea: dark water with a moving shimmer
        self.sea.set_texture(self.T("asphalt.png")); self.sea.set_color_scale(0.12, 0.2, 0.35, 1); self.sea.set_light_off()
        self.sea.set_transparency(TransparencyAttrib.M_alpha); self.sea.set_bin("transparent", 0)
        self.shallow.set_light_off(); self.shallow.set_transparency(TransparencyAttrib.M_alpha); self.shallow.set_bin("transparent", 0)
        self.shallow.set_depth_write(False); self.shallow.set_color_scale(0.25, 0.3, 0.4, 1)
        self.root.flatten_light()
        if self.q < 2:
            self.refl.hide()

    def build_flags(self):
        self.flags = []
        tex = self.T("flag.jpg", repeat=False)
        for (x, y, z, ph) in self.flag_poles:
            root = self.root.attach_new_node("flag"); root.set_pos(x, y, z)
            segs = []
            for k in range(8):
                mb = MB("flagseg"); u0, u1 = k / 8, (k + 1) / 8; w = 6.0 / 8
                mb.quad((0, 0, -6), (w, 0, -6), (w, 0, 0), (0, 0, 0), (0.95, 0.95, 0.95, 1), uv=((u0, 0), (u1, 0), (u1, 1), (u0, 1)), n=(0, -1, 0))
                n = mb.node(); n.reparent_to(segs[-1] if segs else root)
                if segs: n.set_x(w)
                n.set_texture(tex); n.set_two_sided(True); n.set_light_off(); segs.append(n)
            self.flags.append((root, segs, ph))

    def build_sky(self):
        from panda3d.core import Filename
        sky = self.app.loader.load_model("models/misc/sphere") if False else None
        # sky dome: inward-facing sphere made procedurally
        mb = MB("sky"); R = 1500.0; nu, nv = 32, 12
        for i in range(nu):
            for j in range(nv):
                a0, a1 = i / nu * 2 * math.pi, (i + 1) / nu * 2 * math.pi
                b0, b1 = -0.15 + j / nv * (math.pi / 2 + 0.15), -0.15 + (j + 1) / nv * (math.pi / 2 + 0.15)
                def P(a, b): return (R * math.cos(b) * math.cos(a), R * math.cos(b) * math.sin(a), R * math.sin(b))
                def U(a, b): return (a / (2 * math.pi), 0.5 + b / math.pi)
                mb.quad(P(a0, b0), P(a0, b1), P(a1, b1), P(a1, b0), (1, 1, 1, 1), (U(a0, b0), U(a0, b1), U(a1, b1), U(a1, b0)))
        self.sky = mb.node(); self.sky.reparent_to(self.app.camera)
        self.sky.set_compass(); self.sky.set_bin("background", 0); self.sky.set_depth_write(False); self.sky.set_light_off()
        self.sky.set_fog_off(); self.sky.set_texture(self.T("sky.jpg", repeat=True)); self.sky.set_two_sided(True)
        # daytime dome (blue sky + cumulus), cross-faded over the night sky by the day/night cycle
        self.sky_day = self.sky.copy_to(self.app.camera); self.sky_day.set_compass(); self.sky_day.set_bin("background", 1)
        self.sky_day.set_texture(self.T("sky_day.jpg", repeat=True), 1); self.sky_day.set_transparency(TransparencyAttrib.M_alpha)
        self.sky_day.set_scale(0.98); self.sky_day.set_alpha_scale(0.0); self.sky_day.hide(); self.dayk = 0.0; self._dayfac = None

    def set_daylight(self, k, warm=0.0):
        """k: 0 night .. 1 full day. warm: golden-hour tint amount. Neon/windows glow at night, reduced by day."""
        from panda3d.core import TextureStage
        self.dayk = k
        if k > 0.01:
            self.sky_day.show(); self.sky_day.set_alpha_scale(min(1.0, k * 1.15))
            self.sky_day.set_color_scale(1.0, 1.0 - 0.18 * warm, 1.0 - 0.38 * warm, min(1.0, k * 1.15))
        else:
            self.sky_day.hide()
        day = k > 0.45
        if day != self._dayfac:
            self._dayfac = day
            for np_, mat in self.fac_nodes:
                np_.set_texture(self.T(mat + ("_day" if day else "") + ".png", repeat=True), 1)
        b = 1.0 + 0.45 * k          # v1.0.4: daylight no longer over-brightens walls / shopfronts to white
        for np_, mat in self.fac_nodes:
            f_ = (1.0 if day else 1.0 + 0.4 * k) / b; np_.set_color_scale(f_, f_, f_, 1)
        self.static.set_color_scale(b, b * (1 - 0.08 * warm), b * (1 - 0.2 * warm), 1)
        for np_ in self.emit_nodes:
            e = (1.0 - 0.45 * k) * (1.0 - 0.3 * k); np_.set_color_scale(e / b, e / b, e / b, 1)    # signs: plain emissive, dimmer by day
        for sn in getattr(self, "shop_nps", []):
            sh = 0.86 / b; sn.set_color_scale(sh, sh, sh, 1)          # v1.0.4: lit shop windows no longer blow out to white
        if self.ground_np is not None:
            g = 1.0 + 0.9 * k; self.ground_np.set_color_scale(g, g * (1 - 0.05 * warm), g * (1 - 0.12 * warm) * (1 + 0.05 * k), 1)
        if getattr(self, "refl", None) is not None:
            r_ = 0.85 * (1 - 0.6 * k); self.refl.set_color_scale(r_, r_ * 0.95, r_ * 1.1, 1)
        if getattr(self, "glow_nodes", None):
            for gn in self.glow_nodes:     # v1.0.4: halo sprites are off; ground light pools stay subtle and only at night
                a_ = (1.0 - k) * (0.0 if gn.get_name() == "glows" else 0.45); gn.set_alpha_scale(a_); gn.set_color_scale(1, 1, 1, a_)
                if a_ <= 0.01: gn.hide()
                else: gn.show()
        if self.sea:
            self.sea.set_color_scale(0.12 + 0.0 * k, 0.2 + 0.32 * k, 0.35 + 0.33 * k, 1)
            self.shallow.set_color_scale(0.25 + 0.75 * k, 0.3 + 0.7 * k, 0.4 + 0.6 * k, 1)

    def update(self, dt, t):
        for np_, kind in self.anim:
            if kind == "hw":
                np_.set_y((t * 30.0) % 22.0)
            elif kind == "video":
                k = 0.85 + 0.15 * math.sin(t * 3.0)
                np_.set_color_scale(k, k, k * 1.05, 1)
        for root, segs, ph in getattr(self, "flags", []):
            root.set_h(25 * math.sin(t * 0.3 + ph))
            for k, sg in enumerate(segs[1:]):
                sg.set_h(9 * math.sin(t * 2.6 - k * 0.8 + ph))
        if getattr(self, "sky_day", None) is not None and not self.sky_day.is_hidden():
            from panda3d.core import TextureStage
            self.sky_day.set_tex_offset(TextureStage.get_default(), (t * 0.0008) % 1, 0)     # clouds drift slowly
        if self.sea:
            from panda3d.core import TextureStage
            self.sea.set_tex_offset(TextureStage.get_default(), (t * 0.01) % 1, (t * 0.004) % 1)

    # ---------------------------------------------------------------- minimap image
    def map_image(self, size=1024):
        """returns (PNMImage, (xmin, ymin, scale))"""
        xmin, ymin, span = -470.0, -590.0, 1180.0
        img = PNMImage(size, size, 4)
        img.fill(0.03, 0.03, 0.06); img.alpha_fill(0.92)
        s = size / span
        def rect(x0, y0, x1, y1, c, a=1.0):
            X0 = int((x0 - xmin) * s); X1 = int((x1 - xmin) * s); Y0 = int(size - (y1 - ymin) * s); Y1 = int(size - (y0 - ymin) * s)
            for X in range(max(0, X0), min(size, X1)):
                for Y in range(max(0, Y0), min(size, Y1)):
                    if a >= 1: img.set_xel(X, Y, *c)
                    else:
                        o = img.get_xel(X, Y); img.set_xel(X, Y, o[0] * (1 - a) + c[0] * a, o[1] * (1 - a) + c[1] * a, o[2] * (1 - a) + c[2] * a)
        rect(D.SEA_X, -600, 720, 600, (0.03, 0.10, 0.20))
        rect(D.SAND[0], -440, D.SEA_X, 440, (0.30, 0.26, 0.18))
        rect(D.STADIUM[0], D.STADIUM[1], D.STADIUM[2], D.STADIUM[3], (0.55, 0.57, 0.62))          # v1.0.5 SFC 27 stadium
        rect(520, 178, 588, 287, (0.18, 0.48, 0.16))
        rect(411, -440, 452, 440, (0.06, 0.12, 0.07))
        for i in range(D.N_BLOCKS):
            for j in range(D.N_BLOCKS):
                x0, y0, x1, y1 = block_rect(i, j)
                dc = D.DISTRICT[D.district_at((x0 + x1) / 2, (y0 + y1) / 2)][3]
                rect(x0, y0, x1, y1, (0.10 + dc[0] * 0.18, 0.10 + dc[1] * 0.18, 0.12 + dc[2] * 0.18))
        for a, b, w in self.edges:
            (ax, ay), (bx, by) = self.nodes[a], self.nodes[b]
            hw = w / 2
            rect(min(ax, bx) - hw, min(ay, by) - hw, max(ax, bx) + hw, max(ay, by) + hw, (0.55, 0.55, 0.62))
        r = D.DRIFT_ZONE["rect"]; rect(r[0], r[1], r[2], r[3], (0.45, 0.45, 0.5))
        rect(560, 140, 690, 156, (0.4, 0.3, 0.2))
        rect(-209, -440, -191, 440, (0.40, 0.70, 0.85), 0.35)
        return img, (xmin, ymin, s)
