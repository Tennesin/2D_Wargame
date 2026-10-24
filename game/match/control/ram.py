"""game/match/control/ram.py — таран: удар танка о камень или другой танк, толчок и урон.
Танк только отмечает «я врезался» (impact_kmh); что именно он задел и что из этого вышло, решаем здесь."""
from combat import (resolve_ram, can_push, ram_damage,
                    RESTITUTION_ROCK, RESTITUTION_TANK, MIN_CLOSING_MS)
from engine import PX_PER_M, obb_contact

CONTACT_PAD_PX = 8.0         # на сколько px раздуваем корпус, чтобы поймать касание (физика останавливает танк вплотную)
DAMAGE_COOLDOWN_S = 0.5      # пока не прошло, та же пара танков повторно урон не получает

class RamController:
    def __init__(self, ctx):
        self.ctx = ctx
        self.fleet = ctx.fleet
        self.walls = ctx.walls
        self.terrain = ctx.terrain
        self.notifier = ctx.notifier
        self.settings = ctx.settings
        self._cooldown = {}

    # ---------- каждый кадр (после обновления всех танков) ----------
    def update(self, dt):
        self._cooldown = {k: t - dt for k, t in self._cooldown.items() if t - dt > 0.0}

        done = set()                     # пары, уже разобранные в этом кадре
        for tank in self.fleet.vehicles:
            if tank.alive and tank.impact_kmh is not None:
                self._ram_rocks(tank)
                self._ram_tanks(tank, done)

        self.terrain.rocks.update(dt, self._obbs_near)
        for tank in self.fleet.vehicles:
            if tank.alive:
                tank.update_push(dt, self.ctx.obstacles_for(tank), self.terrain)

        self.fleet.remove_dead()                             # кто погиб от тарана

    # ---------- камни ----------
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
                tank.take_damage(ram_damage(abs(res.u1 - u1), tank.zone_at((nx, ny))))

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
            contact = obb_contact(padded, b.hull_obb())
            if contact is None:
                continue
            done.add(key)
            _, nx, ny = contact                              # нормаль от a к b: по ней определяется грань

            vax, vay = a.velocity_px(a.impact_kmh)           # скорость ДО гашения, если был удар
            vbx, vby = b.velocity_px(b.impact_kmh)
            u1 = (vax * nx + vay * ny) / PX_PER_M
            u2 = (vbx * nx + vby * ny) / PX_PER_M
            if u1 - u2 < MIN_CLOSING_MS:
                continue                                     # скользящее касание или расходятся

            res = resolve_ram(a.mass_t, u1, b.mass_t, u2, RESTITUTION_TANK)
            dv_a, dv_b = abs(res.u1 - u1), abs(res.u2 - u2)
            a.apply_impulse(nx, ny, res.u1 - u1)
            b.apply_impulse(nx, ny, res.u2 - u2)
            self._damage(key, a, b, nx, ny, dv_a, dv_b)

    def _damage(self, key, a, b, nx, ny, dv_a, dv_b):
        if a.team is b.team and not self.settings.friendly_fire:
            return                                           # свои своих тараном не ранят: только толчок
        if self._cooldown.get(key, 0.0) > 0.0:
            return
        self._cooldown[key] = DAMAGE_COOLDOWN_S
        zone_a = a.zone_at((nx, ny))                         # внешняя нормаль грани a смотрит на b
        zone_b = b.zone_at((-nx, -ny))                       # а у b — на a
        dmg_a = ram_damage(dv_a, zone_a)
        dmg_b = ram_damage(dv_b, zone_b)
        a.take_damage(dmg_a)
        b.take_damage(dmg_b)
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