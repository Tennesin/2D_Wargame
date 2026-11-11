"""game/match/control/ram.py — таран: контакты техники со всем твёрдым (танки, стены, камни, граница мира),
единый солвер, давление, урон по энергии, подброс."""
import math

from combat import (resolve_ram_2d, can_push, press_velocity, ram_energy_kj, ram_damage_kj,
                    RESTITUTION_TANK, RESTITUTION_ROCK, RESTITUTION_WALL,
                    RAM_SAFE_KJ, WALL_DMG_PER_KJ, STATIC_DYNAMIC_SHARE, TRACK_EDGE_K, TRACK_MID_K)
from combat.ram import SAFE_DV_MS
from engine import PX_PER_M, WORLD, obb_contact, obb_poly_contact
from vehicles.chassis.params import LIFT_FULL_DV_MS, LIFT_STATIC_K, PRESS_HOLD_S
from world import WorldBoundary
from .contacts import Rec, TankBody, WallBody, EdgeBody, RockBody

PASSES = 3                   # проходов солвера за кадр
CONTACT_PAD_PX = 8.0         # на сколько px раздуваем корпус, чтобы поймать касание
DAMAGE_COOLDOWN_S = 0.5      # пока не прошло, та же пара повторно урон не получает
NORMAL_MEMORY_S = 0.3        # сколько помним нормаль пары (против прыжков нормали при ударе углом)
SEP_SLOP_PX = 1.5            # такое пересечение терпим
SEP_K = 0.4                  # какую долю пересечения исправляем за кадр
SEP_MAX_PX = 12.0            # и не больше стольких px за кадр

def _vel_n(body, nx, ny):
    vx, vy = body.velocity()
    return vx * nx + vy * ny

def _shares(a, b):
    """Доли энергии удара, которые достаются телам a и b: (доля a, доля b)."""
    if b.static:
        return STATIC_DYNAMIC_SHARE, 1.0 - STATIC_DYNAMIC_SHARE
    if a.static:
        return 1.0 - STATIC_DYNAMIC_SHARE, STATIC_DYNAMIC_SHARE
    ia, ib = 1.0 / a.mass, 1.0 / b.mass              # легче тело: больше ему достаётся
    return ia / (ia + ib), ib / (ia + ib)

class RamController:
    def __init__(self, ctx):
        self.ctx = ctx
        self.fleet = ctx.fleet
        self.walls = ctx.walls
        self.terrain = ctx.terrain
        self.notifier = ctx.notifier
        self.settings = ctx.settings
        self.match_stats = ctx.match_stats
        self._cooldown = {}
        self._normals = {}               # пара -> [nx, ny, секунд до забывания]
        self.last = None                 # последний удар (его показывает отладка и ram_lab)
        self.on_shake = None             # колбэк(сила 0..1): тряска камеры игрока (ставит Match)

    # ==========================================
    # КАДР
    # ==========================================
    def update(self, dt):
        self._cooldown = {k: t - dt for k, t in self._cooldown.items() if t - dt > 0.0}
        self._normals = {k: [m[0], m[1], m[2] - dt] for k, m in self._normals.items() if m[2] - dt > 0.0}
        if self.last is not None:
            self.last["age"] += dt

        for v in self.fleet.vehicles:                        # 1) толчки (при упоре запоминают contact_push)
            if v.alive and v.has_push:
                v.update_push(dt, self.ctx.obstacles_for(v), self.terrain)

        contacts = self._collect()                           # 2) контакты
        for p in range(PASSES):                              # 3) солвер
            for rec in contacts:
                self._resolve(rec, p == 0, dt)
        for rec in contacts:                                 # 4) последствия и выталкивание
            if rec.first is not None:
                self._after_impact(rec)
            self._separate(rec)
        for v in self.fleet.vehicles:
            v.contact_push = None
            v.contact_spin = None
        for v in self.fleet.vehicles:
            v.contact_push = None
            v.contact_spin = None
            if v.alive:
                v.keep_in_world(WORLD.half_w_px, WORLD.half_h_px)

        self.terrain.rocks.update(dt, self._obbs_near)
        self.walls.remove_dead()
        self.fleet.remove_dead()

    # ==========================================
    # СБОР КОНТАКТОВ
    # ==========================================
    def _contact(self, a, b, padded, other_obb):
        key = frozenset((id(a.obj), id(b.obj)))
        mem = self._normals.get(key)
        c = obb_contact(padded, other_obb, None if mem is None else (mem[0], mem[1]))
        if c is not None:
            self._normals[key] = [c.nx, c.ny, NORMAL_MEMORY_S]
        return c

    def _collect(self):
        recs = []
        vehicles = [v for v in self.fleet.vehicles if v.alive]
        for i, v in enumerate(vehicles):
            a = TankBody(v)
            x, y, hw, hl, ang = v.hull_obb()
            padded = (x, y, hw + CONTACT_PAD_PX, hl + CONTACT_PAD_PX, ang)
            reach = v.reach_px()

            for w in vehicles[i + 1:]:                       # танк с танком
                lim = reach + w.reach_px()
                if (w.x - v.x) ** 2 + (w.y - v.y) ** 2 > lim * lim:
                    continue
                if not (v.has_impact or w.has_impact or v.hits_obb(w.hull_obb())):
                    continue                                 # без удара и без пересечения контакт не нужен
                b = TankBody(w)
                c = self._contact(a, b, padded, w.hull_obb())
                if c is not None:
                    recs.append(Rec(a, b, c, RESTITUTION_TANK))

            if not v.has_impact:                             # со статикой считаем только упёршихся
                continue
            for wall in self.walls.near_walls(v.x, v.y, reach):
                if wall.alive:
                    b = WallBody(wall)
                    c = self._contact(a, b, padded, wall.obb())
                    if c is not None:
                        recs.append(Rec(a, b, c, RESTITUTION_WALL))
            for p in self.terrain.patches_near(v.x, v.y, reach):
                if not p.kind.solid:
                    continue
                best = None
                for tri in p.tris:
                    c = obb_poly_contact(padded, tri)
                    if c is not None and (best is None or c.depth > best.depth):
                        best = c
                if best is not None:
                    b = RockBody(p, self.terrain.rocks, can_push(v.mass_t, p.mass_t))
                    recs.append(Rec(a, b, best, RESTITUTION_ROCK))
            if abs(v.x) + reach > WORLD.half_w_px or abs(v.y) + reach > WORLD.half_h_px:
                for band in WorldBoundary.bands():
                    b = EdgeBody(band)
                    c = self._contact(a, b, padded, band)
                    if c is not None:
                        recs.append(Rec(a, b, c, RESTITUTION_WALL))
        return recs

    # ==========================================
    # СОЛВЕР
    # ==========================================
    def _resolve(self, rec, first, dt):
        a, b, c = rec.a, rec.b, rec.c
        ax, ay = a.center()
        bx, by = b.center()
        r1 = ((c.px - ax) / PX_PER_M, (c.py - ay) / PX_PER_M)
        r2 = ((c.px - bx) / PX_PER_M, (c.py - by) / PX_PER_M)
        e = rec.e0 if first else 0.0                         # упругость только в первом проходе
        res = resolve_ram_2d(a.mass, a.inertia, a.velocity(), a.omega(), r1,
                             b.mass, b.inertia, b.velocity(), b.omega(), r2, (c.nx, c.ny), e)
        if res is None:
            if first:
                self._press(rec, dt)                         # нет удара: может быть давление
            return
        a.apply(res.dv1[0], res.dv1[1], res.dw1)
        b.apply(res.dv2[0], res.dv2[1], res.dw2)
        if a.kind == "tank" and b.kind == "tank":
            soft = max(a.v.push_ramp_s(), b.v.push_ramp_s())
            a.v.start_soft_contact(soft)                     # пока партнёр разгоняется, упор не гасит ход
            b.v.start_soft_contact(soft)
        rec.energy += ram_energy_kj(res)
        rec.dv_a = max(rec.dv_a, res.jn / a.mass)            # у статики mass = inf: получится 0
        rec.dv_b = max(rec.dv_b, res.jn / b.mass)
        if rec.first is None:
            rec.first = res

    def _press(self, rec, dt):
        """Контакт без удара: тот, у кого тяги больше, толкает другого, если хватает запаса над сопротивлением."""
        a, b, c = rec.a, rec.b, rec.c
        fa = a.thrust(c.nx, c.ny)
        fb = b.thrust(-c.nx, -c.ny)
        if fa <= 0.0 and fb <= 0.0:
            return
        if fa >= fb:
            pusher, pushed, nx, ny, net = a, b, c.nx, c.ny, fa - fb
        else:
            pusher, pushed, nx, ny, net = b, a, -c.nx, -c.ny, fb - fa
        if pushed.static or pushed.kind == "rock":
            return                                           # стену и камень «давлением» не двигаем
        vp, vq = _vel_n(pusher, nx, ny), _vel_n(pushed, nx, ny)
        if vp - vq < -0.1:
            return                                           # уже расходятся
        resist = pushed.resist(nx, ny)
        v_new = press_velocity(net, resist, pusher.mass, pushed.mass, vp, vq, dt)
        pusher.shove(nx, ny, v_new - vp)      # толкающий всегда упирается
        pusher.hold(PRESS_HOLD_S)
        if net > resist:                      # толкаемого "ведём" только если его реально двигают
            pushed.shove(nx, ny, v_new - vq)
            pushed.hold(PRESS_HOLD_S)

    # ==========================================
    # ВЫТАЛКИВАНИЕ ИЗ ПЕРЕСЕЧЕНИЯ
    # ==========================================
    def _separate(self, rec):
        a, b, c = rec.a, rec.b, rec.c
        pen = c.depth - CONTACT_PAD_PX - SEP_SLOP_PX
        if pen <= 0.0:
            return
        pen = min(pen, SEP_MAX_PX) * SEP_K
        wa = 0.0 if a.static else 1.0 / a.mass
        wb = 0.0 if (b.static or b.kind == "rock") else 1.0 / b.mass
        s = wa + wb
        if s == 0.0:
            return
        for body, k in ((a, -wa / s), (b, wb / s)):
            if body.kind == "tank" and k != 0.0:
                v = body.v
                v.separate(c.nx * pen * k, c.ny * pen * k, self.walls.obbs_near(v.x, v.y, v.reach_px()))

    # ==========================================
    # ПОСЛЕДСТВИЯ УДАРА
    # ==========================================
    def _after_impact(self, rec):
        a, b, c = rec.a, rec.b, rec.c
        friendly = (a.kind == "tank" and b.kind == "tank"
                    and a.v.team is b.v.team and not self.settings.friendly_fire)
        key = frozenset((id(a.obj), id(b.obj)))
        dmg = [0.0, 0.0]
        if not friendly and self._cooldown.get(key, 0.0) <= 0.0:
            self._cooldown[key] = DAMAGE_COOLDOWN_S
            sa, sb = _shares(a, b)
            dmg = [self._hurt(a, b, rec.energy * sa, c), self._hurt(b, a, rec.energy * sb, c)]
        self._record(rec, dmg)
        self._notify(a, b, c, dmg)
        if not friendly:
            self._shock(rec)

    def _hurt(self, body, other, kj, c):
        """Урон телу body от доли kj энергии. Возвращает HP, которое списано."""
        if body.kind == "wall":
            dmg = max(0.0, kj - RAM_SAFE_KJ) * WALL_DMG_PER_KJ
            if dmg > 0.0:
                body.wall.take_damage(dmg)
            return dmg
        if body.kind != "tank":
            return 0.0                                       # камни и граница неуязвимы
        if other.kind == "edge" or (other.kind == "rock" and not self.settings.rock_hurts_tank):
            return 0.0
        v = body.v
        dmg = ram_damage_kj(kj, v.armor_at_point(c.px, c.py))
        if dmg <= 0.0:
            return 0.0
        real = min(dmg, v.hp)
        v.take_damage(dmg)
        src = other.v if other.kind == "tank" else None
        self.match_stats.on_damage(src, v, real, "ram")      # при src = None статистика получение не считает
        self._hit_track(v, src, dmg, c)
        return dmg

    def _hit_track(self, v, src, dmg, c):
        """Часть урона уходит в гусеницу, по которой пришёлся контакт (в край сильнее, чем в середину)."""
        side = v.track_under(c.px, c.py)
        if side is None:
            return
        k = TRACK_EDGE_K if v.track_at(c.px, c.py) else TRACK_MID_K
        if v.damage_track(side, dmg * k):
            self.notifier.on_track_broken(src, v, side)
            self.match_stats.on_track_broken(src, v)

    def _notify(self, a, b, c, dmg):
        if a.kind == "tank" and b.kind == "tank":
            self.notifier.on_ram(a.v, b.v, dmg[0], dmg[1],
                                 a.v.zone_at_point(c.px, c.py), b.v.zone_at_point(c.px, c.py))
        elif a.kind == "tank" and b.kind == "wall":
            self.notifier.on_ram_static(a.v, dmg[0], dmg[1], "Стена")
        elif a.kind == "tank" and b.kind == "rock" and a.v is self.fleet.player and dmg[0] > 0.0:
            self.notifier.on_rock_ram(dmg[0])

    def _shock(self, rec):
        """Подброс стороной удара, пыль и тряска. Удар о статику подбрасывает слабее (LIFT_STATIC_K)."""
        a, b, c = rec.a, rec.b, rec.c
        player = self.fleet.player
        shake, top = 0.0, 0.0
        for body, other, dv in ((a, b, rec.dv_a), (b, a, rec.dv_b)):
            if body.kind != "tank":
                continue
            bx, by = body.center()
            dx, dy = c.px - bx, c.py - by                    # от центра этой машины к точке удара
            ln = math.hypot(dx, dy)
            direction = (dx / ln, dy / ln) if ln > 1.0 else None
            if other.static:
                dv *= LIFT_STATIC_K
            top = max(top, dv)
            if body.v.apply_lift(dv, direction) and (body.v is player or other.obj is player):
                self.notifier.on_lift(body.v)
            if body.v is player and dv > SAFE_DV_MS:
                shake = min(1.0, dv / LIFT_FULL_DV_MS)
        dust = min(1.0, top / LIFT_FULL_DV_MS)
        if dust > 0.25:
            self.ctx.effects.spawn_dust(c.px, c.py, dust)
        if shake > 0.0 and self.on_shake is not None:
            self.on_shake(shake)

    def _record(self, rec, dmg):
        """Данные последнего удара для отладки и ram_lab (ключи те же, что раньше)."""
        a, b, c, res = rec.a, rec.b, rec.c, rec.first
        self.last = {
            "x": c.px, "y": c.py, "nx": c.nx, "ny": c.ny, "age": 0.0,
            "a": a.v.label if a.kind == "tank" else a.kind,
            "b": b.v.label if b.kind == "tank" else b.kind,
            "closing": res.closing, "e": res.restitution, "jn": res.jn, "jt": res.jt,
            "dv_a": rec.dv_a, "dv_b": rec.dv_b,
            "dw_a": math.degrees(res.dw1), "dw_b": math.degrees(res.dw2),
            "dmg_a": dmg[0], "dmg_b": dmg[1],
            "zone_a": a.v.zone_at_point(c.px, c.py) if a.kind == "tank" else "-",
            "zone_b": b.v.zone_at_point(c.px, c.py) if b.kind == "tank" else "-",
        }

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