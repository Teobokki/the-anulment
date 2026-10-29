"""AI drivers: traffic (left-hand traffic lanes), racers, police pursuit, taxi / emergency responders."""
import math, random
from collections import deque


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def graph_path(world, a, b):
    """BFS over the road graph (node keys) -> list of node keys from a to b."""
    if a == b:
        return [a]
    prev = {a: None}; q = deque([a])
    while q:
        n = q.popleft()
        if n == b: break
        for m in world.adj.get(n, ()):
            if m not in prev:
                prev[m] = n; q.append(m)
    if b not in prev:
        return [a]
    out = [b]
    while out[-1] != a:
        out.append(prev[out[-1]])
    return out[::-1]


def lane_points(world, nodes, lane=3.0, inset=11.0):
    pts = []
    for k in range(len(nodes) - 1):
        ax, ay = world.nodes[nodes[k]]; bx, by = world.nodes[nodes[k + 1]]
        dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1; dx /= L; dy /= L
        lx, ly = -dy, dx     # left (Japan drives on the left)
        ins = min(inset, L / 3)
        pts.append((ax + dx * ins + lx * lane, ay + dy * ins + ly * lane))
        pts.append((bx - dx * ins + lx * lane, by - dy * ins + ly * lane))
    return pts


def steer_to(car, tx, ty, target_speed, brake_dist=None):
    dx, dy = tx - car.x, ty - car.y
    hd = math.degrees(math.atan2(-dx, dy))
    dh = wrap(hd - car.h)
    v = car.fspeed()
    if abs(dh) > 100 and v < 6:          # target behind: reverse-turn
        car.steer = max(-1, min(1, dh / 30.0)); car.throttle = -0.7; car.hand = False
        return dh
    car.steer = max(-1.0, min(1.0, -dh / 22.0))
    ts = target_speed * (1.0 - min(0.65, abs(dh) / 110.0))
    car.throttle = max(-1.0, min(1.0, (ts - v) * 0.35))
    car.hand = abs(dh) > 55 and v > 18
    return dh


class PathFollower:
    def __init__(self, pts, loop=False):
        self.pts = pts; self.i = 0; self.loop = loop

    def target(self, car, reach=9.0):
        while self.i < len(self.pts):
            tx, ty = self.pts[self.i]
            if math.hypot(tx - car.x, ty - car.y) < reach:
                self.i += 1
                if self.i >= len(self.pts) and self.loop: self.i = 0
            else:
                break
        if self.i >= len(self.pts):
            return None
        return self.pts[self.i]

    def corner_ahead(self, car):
        """angle of the upcoming turn and distance to it"""
        if self.i + 1 >= len(self.pts): return 0.0, 999.0
        ax, ay = self.pts[self.i]; bx, by = self.pts[self.i + 1]
        h1 = math.degrees(math.atan2(-(ax - car.x), ay - car.y)); h2 = math.degrees(math.atan2(-(bx - ax), by - ay))
        return abs(wrap(h2 - h1)), math.hypot(ax - car.x, ay - car.y)


class TrafficAI:
    def __init__(self, game, car, start_node, prev=None):
        self.g = game; self.car = car; self.cur = start_node; self.prev = prev
        self.speed = random.uniform(11, 15); self.nodes = [start_node]; self.extend(); self.wait = 0.0
        self.pf = PathFollower(lane_points(game.world, self.nodes))

    def extend(self):
        w = self.g.world
        while len(self.nodes) < 5:
            n = self.nodes[-1]; p = self.nodes[-2] if len(self.nodes) > 1 else self.prev
            opts = [m for m in w.adj[n] if m != p] or list(w.adj[n])
            self.nodes.append(random.choice(opts))

    def update(self, dt):
        c = self.car
        t = self.pf.target(c)
        if t is None or self.pf.i > len(self.pf.pts) - 3:
            keep = self.nodes[-2:]; self.nodes = keep; self.extend()
            self.pf = PathFollower(lane_points(self.g.world, self.nodes)); t = self.pf.target(c)
            if t is None: return
        ang, dist = self.pf.corner_ahead(c)
        ts = self.speed if (ang < 30 or dist > 30) else 7.0
        # keep distance from whatever is ahead (cars, the player on foot)
        f = c.fwd
        sig = getattr(self.g, "signals", None)
        if sig is not None:                      # v1.0.4: stop at the line on red
            st = sig.must_stop(c)
            if st is not None: ts = min(ts, max(0.0, st * 0.8))
        self.block = getattr(self, "block", 0.0)
        for o in self.g.cars_near(c.x, c.y, 18):
            if o is c: continue
            dx, dy = o.x - c.x, o.y - c.y; fwd = dx * f[0] + dy * f[1]; lat = abs(dx * f[1] - dy * f[0])
            of = o.fwd; same = of[0] * f[0] + of[1] * f[1] > 0.5
            if same:
                if 0 < fwd < 16 and lat < 2.6: ts = min(ts, max(0.0, (fwd - 7.0) * 1.2))
            elif 0 < fwd < 9 and lat < 2.2 and self.block < 3.0:     # crossing car right in front: brief yield, never gridlock
                ts = min(ts, max(0.0, (fwd - 5.0) * 1.0))
        self.block = self.block + dt if ts < 0.5 and c.fspeed() < 0.5 else max(0.0, self.block - dt * 2)
        for p in self.g.walkers():
            dx, dy = p.x - c.x, p.y - c.y; fwd = dx * f[0] + dy * f[1]; lat = abs(dx * f[1] - dy * f[0])
            if 0 < fwd < 14 and lat < 2.2:
                ts = 0.0
        steer_to(c, t[0], t[1], ts)
        if ts == 0.0:
            c.throttle = -1.0 if c.fspeed() > 0.3 else 0.0


class RacerAI:
    def __init__(self, game, car, pts, skill=1.0):
        self.g = game; self.car = car; self.pf = PathFollower(pts, loop=True); self.skill = skill; self.offset = random.uniform(-3, 3)

    def update(self, dt):
        c = self.car
        t = self.pf.target(c, reach=12.0)
        if t is None: return
        ang, dist = self.pf.corner_ahead(c)
        vmax = c.spec["vmax"] * 0.92 * self.skill
        # rubber band: keep the race close
        ts = vmax * self.g.rubber_band(self)
        if ang > 35:
            corner_v = 13.0 + 10.0 * self.skill
            v = c.fspeed()
            if dist < (v * v - corner_v * corner_v) / (2 * 18.0) + 14:
                ts = corner_v
        steer_to(c, t[0] + self.offset * 0.3, t[1] + self.offset * 0.3, ts)
        c.nitro = ang < 10 and dist > 80 and random.random() < 0.02 * self.skill


class PoliceAI:
    def __init__(self, game, car):
        self.g = game; self.car = car; self.pf = None; self.repath = 0.0; self.seen = False

    def update(self, dt):
        c = self.car; tx, ty, tvx, tvy = self.g.player_target()
        d = math.hypot(tx - c.x, ty - c.y)
        self.seen = d < 110 and not self.g.world.grid.segment_blocked(c.x, c.y, tx, ty)
        if self.seen and d < 70:
            lead = min(1.0, d / 30.0)
            steer_to(c, tx + tvx * lead * 0.6, ty + tvy * lead * 0.6, c.spec["vmax"] * (0.9 if d > 15 else 0.6))
            c.nitro = d > 40
            return
        self.repath -= dt
        if self.pf is None or self.repath <= 0:
            w = self.g.world
            a = w.nearest_node(c.x + c.fwd[0] * 15, c.y + c.fwd[1] * 15); b = w.nearest_node(tx, ty)
            nodes = graph_path(w, a, b)
            self.pf = PathFollower([w.nodes[n] for n in nodes] + [(tx, ty)]); self.repath = 2.0
        t = self.pf.target(c, reach=12.0)
        if t is None:
            t = (tx, ty)
        ang, dist = self.pf.corner_ahead(c)
        ts = c.spec["vmax"] * 0.85
        if ang > 35 and dist < 45: ts = 17.0
        steer_to(c, t[0], t[1], ts)


class ResponderAI:
    """taxi / ambulance: drive fast to a point (via graph), then stop near it."""
    def __init__(self, game, car, dest, fast=True):
        self.g = game; self.car = car; self.dest = dest; self.pf = None; self.arrived = False; self.fast = fast; self.t = 0.0
        self.route()

    def route(self):
        w = self.g.world; c = self.car
        a = w.nearest_node(c.x, c.y); b = w.nearest_node(*self.dest)
        nodes = graph_path(w, a, b)
        self.pf = PathFollower(lane_points(w, nodes) + [self.road_point(self.dest)])

    def road_point(self, p):
        x, y, h = self.g.world.nearest_road_point(*p)
        return (x, y)

    def update(self, dt):
        c = self.car; self.t += dt
        if self.arrived:
            c.throttle = -1.0 if c.fspeed() > 0.3 else 0.0; c.steer = 0; c.hand = c.fspeed() < 0.5
            return
        t = self.pf.target(c, reach=8.0)
        if t is None:
            self.arrived = True; return
        ang, dist = self.pf.corner_ahead(c)
        mul = getattr(self, "mul", 1.0)           # v1.0.4: the JP TAXI driver drives ~1.4x too fast and cuts corners
        ts = (30.0 if self.fast else 14.0) * mul
        if ang > 35 and dist < 40: ts = 13.0 * (1.0 + (mul - 1.0) * 0.6)
        if self.pf.i >= len(self.pf.pts) - 1:
            ts = min(ts, max(3.0, dist * 0.5))
            if dist < 6: self.arrived = True
        # yield to cars ahead
        f = c.fwd
        for o in self.g.cars_near(c.x, c.y, 14):
            if o is c: continue
            dx, dy = o.x - c.x, o.y - c.y; fw = dx * f[0] + dy * f[1]; lat = abs(dx * f[1] - dy * f[0])
            if 0 < fw < 12 and lat < 2.4: ts = min(ts, 4.0 if mul <= 1.0 else 9.0)
        steer_to(c, t[0], t[1], ts)
        if mul > 1.0: c.steer = max(-1.0, min(1.0, c.steer + 0.12 * math.sin(self.t * 1.7)))      # a bit distracted: weaves
