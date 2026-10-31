"""game/match/control/hits.py — попадания снарядов, линия прицела, уведомления о боях."""
import math

from engine import TargetType
from vehicles import TRACK_SIDES
from combat import compute_aim, splash_damage, module_hit, blast_damage, frag_armor_factor

SPLASH_ORIGIN_PUSH_PX = 3.0      # на сколько px точка взрыва отодвигается от грани, в которую попал снаряд

class CombatController:
    def __init__(self, ctx, modes):
        self.tank = ctx.fleet.player
        self.walls = ctx.walls
        self.terrain = ctx.terrain
        self.modes = modes
        self.fleet = ctx.fleet
        self.notifier = ctx.notifier
        self.effects = ctx.effects
        self.targets = ctx.targets
        self.settings = ctx.settings
        self.match_stats = ctx.match_stats

    def update(self, dt):
        hits, ricochets, misses, blasts = self.effects.update(dt, self.targets)
        for owner, target in ricochets:
            self.notifier.on_ricochet(owner, target)
        for owner in misses:
            self.notifier.on_miss(owner)
        self._apply_hits(hits)
        self._apply_blasts(blasts)

    def _apply_hits(self, impacts):
        """Попадание: прямой урон по правилам armor.py (стена и танк одинаково), затем взрыв, если он есть."""
        if not impacts:
            return
        for im in impacts:
            if im.target is not None:
                self._direct_hit(im)
            if im.stats.aoe_radius_px > 0.0:
                self._splash(im)
        self.walls.remove_dead()
        self.fleet.remove_dead()

    def _direct_hit(self, im):
        stats, target = im.stats, im.target
        full_pen = stats.penetration * im.power
        full_dmg = stats.damage * im.power
        mh = module_hit(target, full_pen, full_dmg, stats, im.cos, im.x, im.y)
        pen = mh.pen                                      # остаток пробития после гусеницы или экрана
        res = target.hit_result(pen, im.cos, im.normal)
        hp_before = getattr(target, "hp", 0.0)
        dealt = target.take_hit(pen, full_dmg, im.cos, im.normal, stats.splash_frac)
        is_vehicle = target.target_type is TargetType.VEHICLE
        if is_vehicle:
            self.match_stats.on_damage(im.owner, target, hp_before - target.hp, "shot", direct=True)
        if mh.module is not None and mh.pen < full_pen:
            self.notifier.on_module_absorb(im.owner, target, mh.module, full_pen - mh.pen)
        self.notifier.on_hit(im.owner, target, im.normal, res, dealt)
        if is_vehicle and target.alive:
            self._hit_tracks(im, target, mh, full_pen, full_dmg)
            if stats.stun_s > 0.0:                       # оглушает только прямое попадание, осколки нет
                target.apply_stun(stats.stun_s)
                self.notifier.on_stun(im.owner, target)

    def _hit_tracks(self, im, target, mh, full_pen, full_dmg):
        """Урон гусеницам при прямом попадании: гусеница, в которую попали, плюс (для ФГ и HESH)
        ближайшая к взрыву. Если это одна и та же гусеница, берётся бо́льший из двух уронов."""
        damage = {}
        if mh.module in TRACK_SIDES:
            damage[mh.module] = mh.track_damage
        if im.stats.splash_frac > 0.0:
            side, frag = self._frag_track_damage(im, target, full_pen, full_dmg)
            damage[side] = max(damage.get(side, 0.0), frag)
        for side, amount in damage.items():
            if target.damage_track(side, amount):
                self.notifier.on_track_broken(im.owner, target, side)

    @staticmethod
    def _frag_track_damage(im, target, pen, base):
        """(сторона, урон) осколков по ЕДИНСТВЕННОЙ, ближайшей к взрыву гусенице.
        Расстояние считается до прямоугольника гусеницы, а не до корпуса."""
        side, dist = target.nearest_track(im.x, im.y)
        k = frag_armor_factor(target.spec.track_mm, pen)
        return side, splash_damage(base, im.stats.splash_frac * k, dist, im.stats.aoe_radius_px)

    # ---------- взрывы САУ ----------
    def _apply_blasts(self, blasts):
        """Падение снарядов САУ: урон по площади, оглушение, поломка стен."""
        if not blasts:
            return
        for blast in blasts:
            self._blast(blast)
        self.walls.remove_dead()
        self.fleet.remove_dead()

    def _blast(self, blast):
        """Арт-обстрел бьёт сквозь стены и камни (преграды не проверяются)."""
        stats = blast.stats
        shooter = None if self.settings.friendly_fire else blast.owner
        for target, dist in self.targets.in_circle(blast.x, blast.y, stats.outer_radius_px, ignore=shooter):
            if target.target_type is TargetType.WALL:
                dealt, stunned = blast_damage(stats, dist, None, stats.wall_k)
                stunned = False                                  # стены не оглушаются
            else:
                dealt, stunned = blast_damage(stats, dist, target.armor_facing(blast.x, blast.y))
            if dealt <= 0.0:
                continue
            real = min(dealt, target.hp)
            target.take_damage(dealt)
            if target.target_type is TargetType.VEHICLE:
                self.match_stats.on_damage(blast.owner, target, real, "shot")
            if stunned:
                target.apply_stun(stats.stun_s)
            if target.target_type is TargetType.VEHICLE and target.alive:
                side = target.track_under(blast.x, blast.y)
                if side is not None and target.tracks.break_track(side):
                    self.notifier.on_track_broken(blast.owner, target, side)
            self.notifier.on_artillery(blast.owner, target, dealt, stunned)

    # ---------- осколки ----------
    def _splash(self, im):
        """Осколки по всем целям в радиусе, кроме прямой цели."""
        stats = im.stats
        base = stats.damage * im.power
        pen = stats.penetration * im.power
        ox, oy = self._splash_origin(im)
        shooter = None if self.settings.friendly_fire else im.owner
        for target, dist in self.targets.in_circle(im.x, im.y, stats.aoe_radius_px, ignore=shooter):
            if target is im.target:
                continue
            if not self._splash_reaches(ox, oy, target):
                continue
            if target.target_type is TargetType.VEHICLE:
                side, frag = self._frag_track_damage(im, target, pen, base)
                if frag > 0.0 and target.damage_track(side, frag):
                    self.notifier.on_track_broken(im.owner, target, side)
            k = self._frag_k(target, im.x, im.y, pen)
            dealt = splash_damage(base, stats.splash_frac * k, dist, stats.aoe_radius_px)
            if dealt <= 0.0:
                continue
            real = min(dealt, target.hp)
            target.take_damage(dealt)
            if target.target_type is TargetType.VEHICLE:
                self.match_stats.on_damage(im.owner, target, real, "shot")
            self.notifier.on_splash(im.owner, target, dealt)

    @staticmethod
    def _frag_k(target, x, y, pen):
        """Множитель осколков по броне ближайшей к взрыву грани. Стены и прочее без брони: 1.0."""
        facing = getattr(target, "facing_normal", None)
        if facing is None:
            return 1.0
        armor = target.frag_nominal_armor(facing(x, y))
        return 1.0 if armor is None else frag_armor_factor(armor, pen)

    @staticmethod
    def _splash_origin(im):
        """Точка, из которой идут лучи осколков: взрыв, чуть отодвинутый от грани, в которую попали."""
        if im.normal is None:
            return im.x, im.y
        return (im.x + im.normal[0] * SPLASH_ORIGIN_PUSH_PX,
                im.y + im.normal[1] * SPLASH_ORIGIN_PUSH_PX)

    @staticmethod
    def _probe_points(target):
        """Пробные точки цели: центр и четыре угла её прямоугольника (у танка корпус, у стены сама стена)."""
        get_obb = getattr(target, "hull_obb", None) or target.obb
        cx, cy, hw, hl, ang = get_obb()
        rad = math.radians(ang)
        c, s = math.cos(rad), math.sin(rad)
        points = [(cx, cy)]
        for su in (-1.0, 1.0):
            for sv in (-1.0, 1.0):
                u, v = su * hw, sv * hl
                points.append((cx + u * c - v * s, cy + u * s + v * c))
        return points

    def _splash_reaches(self, ox, oy, target):
        """Дошли ли осколки до цели: хотя бы одна пробная точка видна из точки взрыва."""
        for px, py in self._probe_points(target):
            if not self._solid_between(ox, oy, px, py, target):
                return True
        return False

    def _solid_between(self, ox, oy, px, py, target):
        """Есть ли на пути от (ox, oy) до (px, py) стена или камень (кроме самой цели).
        Берётся ближайшая преграда: если первой на пути стоит сама цель, путь свободен."""
        best_obj, best_t = None, None
        hit = self.walls.raycast(ox, oy, px, py)
        if hit is not None:
            best_obj, best_t = hit[0], hit[1]
        hit = self.terrain.raycast(ox, oy, px, py)
        if hit is not None and (best_t is None or hit[1] < best_t):
            best_obj = hit[0]
        return best_obj is not None and best_obj is not target

    def aim_info(self):
        """Траектория выстрела."""
        if not self.tank.alive:
            return None
        if not self.modes.combat:
            return None
        return compute_aim(self.tank, self.targets)