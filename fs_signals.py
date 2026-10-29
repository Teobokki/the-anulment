"""v1.0.4 traffic signals: every city junction gets four signal poles (red / green heads for both axes) on a shared
26 s cycle.  AI traffic stops at the stop line on red, queues behind the cars in front, and goes on green."""
import math
from panda3d.core import NodePath
import fs_data as D
from fs_miyo import box_mesh, shade

CYCLE = 26.0


def phase(t):
    """'ns' = traffic moving along y has green, 'ew' = along x, None = all-red clearance"""
    u = t % CYCLE
    if u < 11.0: return "ns"
    if u < 13.0: return None
    if u < 24.0: return "ew"
    return None


class Signals:
    def __init__(self, game):
        self.g = game; w = game.world
        self.junctions = [p for n, p in w.nodes.items() if len(w.adj.get(n, [])) >= 3 and n[0] != "b"]
        self.jset = set((round(x), round(y)) for x, y in self.junctions)
        root = self.root = NodePath(game.world.root if hasattr(game.world, "root") else game.app.render).attach_new_node("signals")
        poles, lamps = [], {k: [] for k in ("ns_r", "ns_g", "ew_r", "ew_g")}
        hw = D.ROAD_W / 2 + 1.4; dark = (0.16, 0.17, 0.18, 1)
        for (nx, ny) in self.junctions:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    x, y = nx + sx * hw, ny + sy * hw
                    poles.append((x - 0.09, y - 0.09, 0, x + 0.09, y + 0.09, 4.6, dark))
                    # head facing traffic that moves along y and arrives from the -sy side of this corner (it faces -sy)
                    hy = y - sy * 0.25
                    poles.append((x - 0.22, hy - 0.12, 3.9, x + 0.22, hy + 0.12, 4.5, dark))
                    fy = hy - sy * 0.125; d = -sy * 0.03
                    lamps["ns_r"].append((x - 0.18, min(fy, fy + d), 4.28, x - 0.02, max(fy, fy + d), 4.44, (1, 1, 1, 1)))
                    lamps["ns_g"].append((x + 0.02, min(fy, fy + d), 4.28, x + 0.18, max(fy, fy + d), 4.44, (1, 1, 1, 1)))
                    # head facing traffic that moves along x (faces -sx)
                    hx = x - sx * 0.25
                    poles.append((hx - 0.12, y - 0.22, 3.2, hx + 0.12, y + 0.22, 3.8, dark))
                    fx = hx - sx * 0.125; d = -sx * 0.03
                    lamps["ew_r"].append((min(fx, fx + d), y - 0.18, 3.58, max(fx, fx + d), y - 0.02, 3.74, (1, 1, 1, 1)))
                    lamps["ew_g"].append((min(fx, fx + d), y + 0.02, 3.58, max(fx, fx + d), y + 0.18, 3.74, (1, 1, 1, 1)))
        pn = root.attach_new_node(box_mesh("signal_poles", poles)); shade(pn, game.app, 0.25)
        self.lamp = {}
        for k, bx in lamps.items():
            n = root.attach_new_node(box_mesh("signal_" + k, bx)); n.set_light_off(1); n.set_shader_off(1)
            self.lamp[k] = n
        self.state = "?"; self.update(0)

    def update(self, dt):
        ph = phase(self.g.time)
        if ph == self.state: return
        self.state = ph
        on_r, off_r, on_g, off_g = (1.0, 0.18, 0.15, 1.0), (0.25, 0.06, 0.05, 1), (0.2, 1.0, 0.55, 1), (0.04, 0.16, 0.08, 1)
        self.lamp["ns_g"].set_color_scale(on_g if ph == "ns" else off_g); self.lamp["ns_r"].set_color_scale(off_r if ph == "ns" else on_r)
        self.lamp["ew_g"].set_color_scale(on_g if ph == "ew" else off_g); self.lamp["ew_r"].set_color_scale(off_r if ph == "ew" else on_r)

    def must_stop(self, c):
        """distance to the stop line if this car is approaching a red light, else None"""
        f = c.fwd; ph = phase(self.g.time)
        axis = "ns" if abs(f[1]) > abs(f[0]) else "ew"
        if ph == axis: return None
        P = D.PITCH; ax_, ay_ = c.x + f[0] * 28, c.y + f[1] * 28
        nx, ny = round(ax_ / P) * P, round(ay_ / P) * P
        if (nx, ny) not in self.jset: return None
        dx, dy = nx - c.x, ny - c.y
        fwd = dx * f[0] + dy * f[1]; lat = abs(dx * f[1] - dy * f[0])
        if lat < 12 and 15.5 < fwd < 40: return fwd - 17.5
        return None

    def destroy(self):
        self.root.remove_node()
