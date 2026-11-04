"""game/match/control/ram.py — таран: удар танка о камень или другой танк, толчок и урон."""
import math

from combat import (resolve_ram, resolve_ram_2d, can_push, ram_damage,
                    RESTITUTION_ROCK, RESTITUTION_TANK, MIN_CLOSING_MS)
from engine import PX_PER_M, obb_contact

CONTACT_PAD_PX = 8.0         # на сколько px раздуваем корпус, чтобы поймать касание (физика останавливает танк вплотную)
DAMAGE_COOLDOWN_S = 0.5      # пока не прошло, та же пара танков повторно урон не получает
NORMAL_MEMORY_S = 0.3        # сколько помним нормаль пары (против прыжков нормали при ударе углом)

class RamController:
    def __init__(self, ctx):
        self.ctx = ctx
        self.fleet = ctx.fleet
        self.walls = ctx.walls
        self.terrain = ctx.terrain
        self.notifier = ctx.notifier
        self.settings = ctx.settings
        self._cooldown = {}
        self._normals = {}               # пара -> [nx, ny, секунд до забывания]
        self.match_stats = ctx.match_stats
        self.last = None                 # последний удар танков (его показывает отладка и ram_lab)

    # ---------- каждый кадр (после обновления всех танков) ----------
    def update(self, dt):
        self._cooldown = {k: t - dt for k, t in self._cooldown.items() if t - dt > 0.0}
        self._normals = {k: [m[0], m[1], m[2] - dt] for k, m in self._normals.items() if m[2] - dt > 0.0}
        if self.last is not None:
            self.last["age"] += dt

        done = set()                     # пары, уже разобранные в этом кадре
        for tank in self.fleet.vehicles:
            if tank.alive and tank.impact_kmh is not None:
                self._ram_rocks(tank)
                self._ram_tanks(tank, done)

        self.terrain.rocks.update(dt, self._obbs_near)
        for tank in self.fleet.vehicles:
            if tank.alive and (tank.push_vx or tank.push_vy):
                tank.update_push(dt, self.ctx.obstacles_for(tank), self.terrain)

        self.fleet.remove_dead()                             # кто погиб от тарана

    # ---------- камни (пока по старой одномерной модели) ----------
    def _ram_rocks(self, tank):
        for rock, nx, ny in self.terrain.rocks.pushables_touching(tank.hull_obb(), CONTACT_PAD_PX):
            if not can_push(tank.mass_t, rock.mass_t):
                continue                                     # слишком тяжёлый: остаётся глухим препятствием
            vx, vy = tank.velocity_px(tank.impact_kmh)
            u1 = (vx * nx + vy * ny) / PX_PER_M              # м/с вдоль нормали
            u2 = (rock.vx * nx + rock.vy * ny) / PX_PER_M
            if u1 - u2 < MIN_CLOSING_MS:
                continue
            res = resolve_ram(tank.mass_t, u1, rock.mass_t, u2, RESTITUTION_ROCK)
            tank.apply_impulse(nx, ny, res.u1 - u1)
            k = (res.u2 - u2) * PX_PER_M
            self.terrain.rocks.push(rock, rock.vx + nx * k, rock.vy + ny * k)
            if self.settings.rock_hurts_tank:
                dmg = ram_damage(abs(res.u1 - u1), tank.zone_at((nx, ny)))
                tank.take_damage(dmg)
                if tank is self.fleet.player and dmg > 0.0:
                    self.notifier.on_rock_ram(dmg)

    # ---------- танки ----------
    def _ram_tanks(self, a, done):
        hx, hy, hw, hl, ang = a.hull_obb()
        padded = (hx, hy, hw + CONTACT_PAD_PX, hl + CONTACT_PAD_PX, ang)
        for b in self.fleet.vehicles:
            if b is a or not b.alive:
                continue
            key = frozenset((id(a), id(b)))
            if key in done:
                continue
            mem = self._normals.get(key)
            contact = obb_contact(padded, b.hull_obb(), None if mem is None else (mem[0], mem[1]))
            if contact is None:
                continue
            done.add(key)
            self._normals[key] = [contact.nx, contact.ny, NORMAL_MEMORY_S]
            self._collide(key, a, b, contact)

    def _collide(self, key, a, b, c):
        """Один удар двух корпусов: импульс в точке контакта меняет скорость и вращение обоих."""
        ca, cb = a.hull_obb()[:2], b.hull_obb()[:2]          # центры хитбоксов: это центры масс
        r1 = ((c.px - ca[0]) / PX_PER_M, (c.py - ca[1]) / PX_PER_M)
        r2 = ((c.px - cb[0]) / PX_PER_M, (c.py - cb[1]) / PX_PER_M)
        va = a.velocity_px(a.impact_kmh)                     # скорость ДО гашения, если был удар
        vb = b.velocity_px(b.impact_kmh)
        v1 = (va[0] / PX_PER_M, va[1] / PX_PER_M)
        v2 = (vb[0] / PX_PER_M, vb[1] / PX_PER_M)

        res = resolve_ram_2d(a.mass_t, a.inertia_t_m2, v1, math.radians(a.hull_rate), r1,
                             b.mass_t, b.inertia_t_m2, v2, math.radians(b.hull_rate), r2,
                             (c.nx, c.ny), RESTITUTION_TANK)
        if res is None:
            return                                           # скользящее касание или расходятся

        a.apply_velocity_change(res.dv1[0], res.dv1[1], res.dw1)
        b.apply_velocity_change(res.dv2[0], res.dv2[1], res.dw2)

        zone_a = a.zone_at_point(c.px, c.py)                 # грань определяем по точке, а не по нормали
        zone_b = b.zone_at_point(c.px, c.py)
        dv_a, dv_b = res.jn / a.mass_t, res.jn / b.mass_t    # на сколько м/с изменилась скорость центра
        dmg_a = ram_damage(dv_a, zone_a)
        dmg_b = ram_damage(dv_b, zone_b)
        self.last = {
            "x": c.px, "y": c.py, "nx": c.nx, "ny": c.ny, "age": 0.0,
            "a": a.label, "b": b.label, "closing": res.closing, "e": res.restitution,
            "jn": res.jn, "jt": res.jt, "dv_a": dv_a, "dv_b": dv_b,
            "dw_a": math.degrees(res.dw1), "dw_b": math.degrees(res.dw2),
            "dmg_a": dmg_a, "dmg_b": dmg_b, "zone_a": zone_a, "zone_b": zone_b,
        }
        self._damage(key, a, b, dmg_a, dmg_b, zone_a, zone_b)

    def _damage(self, key, a, b, dmg_a, dmg_b, zone_a, zone_b):
        if a.team is b.team and not self.settings.friendly_fire:
            return                                           # свои своих тараном не ранят: только толчок
        if self._cooldown.get(key, 0.0) > 0.0:
            return
        self._cooldown[key] = DAMAGE_COOLDOWN_S
        real_a, real_b = min(dmg_a, a.hp), min(dmg_b, b.hp)
        a.take_damage(dmg_a)
        b.take_damage(dmg_b)
        self.match_stats.on_damage(b, a, real_a, "ram")
        self.match_stats.on_damage(a, b, real_b, "ram")
        self.notifier.on_ram(a, b, dmg_a, dmg_b, zone_a, zone_b)

    # ---------- помощник для камней ----------
    def _obbs_near(self, x, y, radius):
        """Стены и корпуса танков рядом с точкой: всё, что может остановить скользящий камень."""
        result = self.walls.obbs_near(x, y, radius)
        for t in self.fleet.vehicles:
            if t.alive:
                reach = radius + t.reach_px()
                if (t.x - x) ** 2 + (t.y - y) ** 2 <= reach * reach:
                    result.append(t.hull_obb())
        return result