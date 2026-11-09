"""vehicles/render/base.py — общая часть рисования техники с орудием: гусеницы, кэши спрайтов, тень,
ствол и главный метод draw. Детали корпуса лежат в hull_parts.py, палитра и Pen в pen.py."""
import math
import pygame

from engine import LRUCache, SHADOW_ALPHA, heading_vector, clamp, Team, PX_PER_M, vec_from_local
from vehicles.chassis.params import (
    TRACK_LINK_M, LIFT_HEIGHT_M, LIFT_K_GEAR, LIFT_K_HULL, LIFT_K_TURRET, LIFT_BASE_K
)
from vehicles.gun.params import (
    BARREL_LEN_STEP_M, BARREL_THICK_STEP_M, BARREL_HIDDEN_M, BARREL_MIN_STEPS
)
from vehicles.render.hull_parts import HullPartsMixin
from vehicles.chassis.running_gear import LEFT, RIGHT
from vehicles.render.pen import (
    Pen, SS, apply_grain, TRACK_BODY, TRACK_LINK,
    TRACK_BROKEN, TRACK_BROKEN_MARK, GUN
)
from vehicles.parts import barrel_parts_for, corners, draw_parts, PartCtx, BAND_ALL

# ==========================================
# КОНСТАНТЫ РИСОВКИ
# ==========================================
BREAK_MARK_REF_LEN = 6.3                 # длина гусеницы, для которой заданы смещения разрывов
BREAK_MARK_OFFSETS = (1.3, 2.9, 4.5)     # м от переднего края гусеницы

SHADOW_HULL_M = (0.25, 0.35)             # смещение тени корпуса, м
SHADOW_TURRET_M = (0.40, 0.55)           # башня выше, поэтому тень дальше

ANGLE_STEPS = 360
ANGLE_STEP = 360.0 / ANGLE_STEPS
ROT_CACHE_BYTES = 48 * 1024 * 1024       # бюджет памяти под кэш повёрнутых поверхностей

REBUILD_TOL = 0.05                       # после остановки зума спрайты пересобираются, если масштаб ушёл дальше этого
PANEL_MUZZLE_OVER_M = 1.2                # в панели танка дульный срез выходит за лоб корпуса не дальше этого, м

TILT_STRIP_PX = 4                        # примерная ширина полоски при рисовании наклона
TILT_STRIPS_MIN, TILT_STRIPS_MAX = 6, 48

def _weight(p):
    """Вес подъёма по положению вдоль направления на контакт: p = -1 дальний край, +1 край контакта."""
    t = clamp(0.5 + 0.5 * p, 0.0, 1.0)
    t = t * t * (3.0 - 2.0 * t)
    return LIFT_BASE_K + (1.0 - LIFT_BASE_K) * t

class _Tilt:
    """Наклон на один кадр: ось полосок (0: X, 1: Y), знак направления на контакт, размах и центр машины."""
    __slots__ = ("axis", "sign", "reach", "cx", "cy")

    def __init__(self, axis, sign, reach, cx, cy):
        self.axis, self.sign, self.reach, self.cx, self.cy = axis, sign, reach, cx, cy

    def at(self, sx, sy, lift_px):
        """Высота подъёма (px) точки экрана (sx, sy) при максимальной высоте lift_px."""
        pos = (sx - self.cx) if self.axis == 0 else (sy - self.cy)
        return lift_px * _weight(self.sign * pos / self.reach)

# ==========================================
# ОБЩИЙ ОТРИСОВЩИК
# ==========================================

class GunVehicleRenderer(HullPartsMixin):
    """Порядок слоёв: тень, корпус, ствол, башня (качающаяся часть), передний слой (хук).
    Наследник обязан задать HULL_HALF_M и реализовать _build_hull и _build_turret."""

    HULL_HALF_M = None
    HAS_TURRET_SPRITE = True

    def __init__(self):
        self._ppm = 0.0
        self._k = 1.0
        self._moving = False
        self._hull_cache = LRUCache(240)
        self._turret_cache = LRUCache(40)
        self._barrel_cache = LRUCache(80)
        self._sil_cache = LRUCache(240)
        self._rot_cache = LRUCache(400)
        self._gear_cache = LRUCache(20)
        self._shadow_buf = None

    # ---------- что обязан сделать наследник ----------

    def _build_hull(self, paint, look, spec):
        raise NotImplementedError

    def _hull_shift_m(self, spec):
        """На сколько метров корпус сдвинут назад от центра спрайта (то же число, что идёт в Pen)."""
        raise NotImplementedError

    def _build_turret(self, team_color, paint, look, emblem, spec):
        raise NotImplementedError

    def _draw_front_layer(self, screen, tank, cx, cy, hull_k, hull_scale, team, paint, look):
        """Хук: детали, которые вращаются вместе с КОРПУСОМ, но рисуются ПОВЕРХ ствола."""
        return

    # ---------- масштаб ----------

    def set_zoom(self, ppm):
        """Вызывается при смене зума: запоминает масштаб и сбрасывает кэши спрайтов."""
        self._ppm = ppm
        for cache in (self._hull_cache, self._turret_cache, self._barrel_cache,
                      self._sil_cache, self._rot_cache, self._gear_cache):
            cache.clear()
        # размер повёрнутой поверхности растёт с зумом, поэтому лимит записей считаем от бюджета памяти
        side = 2.0 * self.HULL_HALF_M * ppm * 1.42
        per_surface = max(1.0, side * side * 4.0)
        limit = int(clamp(ROT_CACHE_BYTES / per_surface, 40, 3000))
        self._rot_cache.limit = limit
        self._sil_cache.limit = max(40, limit // 2)

    def set_view_zoom(self, ppm, moving=False):
        """Плавный зум в партии."""
        if self._ppm <= 0.0 or (not moving and abs(ppm / self._ppm - 1.0) > REBUILD_TOL):
            self.set_zoom(ppm)
        self._k = ppm / self._ppm
        self._moving = moving

    # ---------- главный метод ----------

    def draw(self, screen, camera, tank):
        ppm = self._ppm
        sx, sy = camera.world_to_screen(tank.x, tank.y)
        cx, cy = int(round(sx)), int(round(sy))

        spec = tank.spec
        look = spec.LOOK
        var = spec.HULL_VARIANT
        view_k = self._k
        hs, ts = spec.HULL_SCALE * view_k, spec.TURRET_SCALE * view_k
        bl = int(round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M))
        bt = int(round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M))
        team = tank.team_color
        paint = None if tank.team is Team.PLAYER else team
        emblem = tank.emblem
        broken = (tank.tracks.is_broken(LEFT), tank.tracks.is_broken(RIGHT))

        hull_k = self._bucket(tank.hull_angle)
        turret_k = self._bucket(tank.turret_angle)
        barrel_key = (bl, bt, look.barrel_key, spec.BARREL_KEY)

        # корпус и ходовая не зависят от фазы гусениц: оба слоя берутся из кэша по углу
        gear_rot = self._rotated("gear", (spec.layout.key, broken),
                                 lambda: self._get_gear(spec, *broken), hull_k, hs)
        hull_rot = self._rotated("hull", (paint, look.hull_key, var),
                                 lambda: self._get_hull(paint, look, spec), hull_k, hs)
        barrel_rot = self._rotated("barrel", barrel_key,
                                   lambda: self._get_barrel(bl, bt, look, spec), turret_k, ts)

        fx, fy = heading_vector(turret_k * ANGLE_STEP)
        f = (spec.GUN_FRONT_M + bl * BARREL_LEN_STEP_M / 2.0 - BARREL_HIDDEN_M / 2.0
             - tank.recoil_m) * ppm * ts
        hull_rect = hull_rot.get_rect(center=(cx, cy))
        gear_rect = gear_rot.get_rect(center=(cx, cy))
        barrel_rect = barrel_rot.get_rect(center=(round(cx + fx * f), round(cy + fy * f)))

        # подъём: край контакта выше, дальний край почти на земле (если направление известно)
        lift_px = tank.lift_height() * LIFT_HEIGHT_M * ppm * hs
        lg, lh, lt = (lift_px * k for k in (LIFT_K_GEAR, LIFT_K_HULL, LIFT_K_TURRET))
        lb = lt if self.HAS_TURRET_SPRITE else lh          # у безбашенной техники ствол сидит в лафете корпуса
        tilt = self._make_tilt(tank, camera, cx, cy) if lift_px >= 1.0 else None
        sk = 0.5 if tilt is not None else 1.0              # при наклоне тень уходит в среднем вдвое меньше
        ex, ey = round(lift_px * 0.45 * sk), round(lift_px * 0.55 * sk)   # тень остаётся на земле

        hox, hoy = (round(v * ppm * hs) for v in SHADOW_HULL_M)
        tox, toy = (round(v * ppm * ts) for v in SHADOW_TURRET_M)
        parts = [
            (self._shadow("gear", spec.layout.key, hull_k, hs, gear_rot), gear_rect.move(hox + ex, hoy + ey)),
            (self._shadow("hull", (look.hull_key, var), hull_k, hs, hull_rot), hull_rect.move(hox + ex, hoy + ey)),
            (self._shadow("barrel", barrel_key, turret_k, ts, barrel_rot), barrel_rect.move(tox + ex, toy + ey)),
        ]

        turret_rot = turret_rect = None
        if self.HAS_TURRET_SPRITE:
            turret_key = (team, paint, look.turret_key, emblem, var)
            turret_rot = self._rotated("turret", turret_key,
                                       lambda: self._get_turret(team, paint, look, emblem, spec), turret_k, ts)
            turret_rect = turret_rot.get_rect(center=(cx, cy))
            parts.append((self._shadow("turret", (look.turret_key, var), turret_k, ts, turret_rot),
                          turret_rect.move(tox + ex, toy + ey)))

        union = parts[0][1].unionall([r for _, r in parts[1:]])
        buf = self._ensure_shadow_buf(union.w, union.h)
        buf.fill((0, 0, 0, 0), (0, 0, union.w, union.h))
        for surf, rect in parts:
            buf.blit(surf, (rect.x - union.x, rect.y - union.y))
        screen.blit(buf, union.topleft, area=(0, 0, union.w, union.h))

        self._blit_lifted(screen, gear_rot, gear_rect, lg, tilt)             # тело гусениц под корпусом
        self._draw_track_links(screen, tank, cx, cy, hull_k, hs, spec, broken, lift=(tilt, lg))
        self._blit_lifted(screen, hull_rot, hull_rect, lh, tilt)             # корпус перекрывает края гусениц
        self._blit_lifted(screen, barrel_rot, barrel_rect, lb, tilt)
        if turret_rot is not None:
            screen.blit(turret_rot, turret_rect.move(0, -self._lift_center(tilt, lt, cx, cy)))
        self._draw_front_layer(screen, tank, cx, cy - self._lift_center(tilt, lh, cx, cy),
                               hull_k, hs, team, paint, look)

    # ---------- тень и кэши ----------
    @staticmethod
    def _blacken(surf):
        """Чёрный силуэт: цвет обнуляется, альфа-канал остаётся."""
        out = surf.copy()
        out.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return out

    @staticmethod
    def _make_tilt(tank, camera, cx, cy):
        """Наклон этого кадра или None (направление неизвестно или машина слишком мелкая)."""
        d = tank.lift_dir
        if d is None:
            return None
        spec = tank.spec
        ux, uy = vec_from_local(d[0], d[1], tank.hull_angle)       # направление на контакт в мировых осях
        reach = (spec.COLLISION_HALF_W_PX * abs(d[0]) + spec.COLLISION_HALF_L_PX * abs(d[1])) * camera.zoom
        if reach < 4.0:
            return None
        axis = 0 if abs(ux) >= abs(uy) else 1
        sign = 1.0 if (ux if axis == 0 else uy) >= 0.0 else -1.0
        return _Tilt(axis, sign, reach, cx, cy)

    @staticmethod
    def _lift_center(tilt, lift_px, cx, cy):
        """Подъём слоя, который сдвигается целиком (башня, маска): вес в центре машины."""
        return round(lift_px if tilt is None else tilt.at(cx, cy, lift_px))

    @staticmethod
    def _blit_lifted(screen, surf, rect, lift_px, tilt):
        """Слой с наклоном: полоски поперёк направления на контакт, у контакта выше.
        Горизонтальные полоски ещё растягиваются по высоте, иначе между ними были бы щели."""
        if tilt is None or lift_px < 1.0:
            screen.blit(surf, rect.move(0, -round(lift_px)))
            return
        w, h = surf.get_size()
        size = w if tilt.axis == 0 else h
        n = int(clamp(size // TILT_STRIP_PX, TILT_STRIPS_MIN, TILT_STRIPS_MAX))
        edges = [round(size * i / n) for i in range(n + 1)]
        for i in range(n):
            a, b = edges[i], edges[i + 1]
            if b <= a:
                continue
            if tilt.axis == 0:                                     # вертикальные полоски: просто сдвиг вверх
                lift = tilt.at(rect.x + (a + b) / 2.0, tilt.cy, lift_px)
                screen.blit(surf, (rect.x + a, rect.y - round(lift)), area=(a, 0, b - a, h))
            else:                                                  # горизонтальные: сдвиг и растяжение
                top = rect.y + a - round(tilt.at(tilt.cx, rect.y + a, lift_px))
                bottom = rect.y + b - round(tilt.at(tilt.cx, rect.y + b, lift_px))
                strip = surf.subsurface((0, a, w, b - a))
                height = max(1, bottom - top)
                if height != b - a:
                    strip = pygame.transform.scale(strip, (w, height))
                screen.blit(strip, (rect.x, top))

    def _shadow(self, kind, base_key, bucket, scale, rotated):
        """Тень слоя из уже повёрнутого спрайта."""
        if self._moving and abs(self._k - 1.0) > 1e-4:
            return self._blacken(rotated)
        key = ("sil", kind, base_key, bucket, round(scale, 3))
        return self._sil_cache.get_or_build(key, lambda: self._blacken(rotated))

    @staticmethod
    def _bucket(angle):
        """Номер положения угла (0..ANGLE_STEPS-1)."""
        return round(angle / ANGLE_STEP) % ANGLE_STEPS

    def _rotated(self, kind, base_key, get_base, bucket, scale):
        """Повёрнутая копия спрайта из кэша."""
        k = self._k
        if self._moving and abs(k - 1.0) > 1e-4:
            base = scale / k                                   # масштаб без поправки на зум
            key = (kind, base_key, bucket, round(base, 3))
            surf = self._rot_cache.get_or_build(
                key, lambda: pygame.transform.rotozoom(get_base(), -bucket * ANGLE_STEP, base))
            w, h = surf.get_size()
            return pygame.transform.scale(surf, (max(1, round(w * k)), max(1, round(h * k))))
        key = (kind, base_key, bucket, round(scale, 3))
        return self._rot_cache.get_or_build(
            key, lambda: pygame.transform.rotozoom(get_base(), -bucket * ANGLE_STEP, scale))

    def _ensure_shadow_buf(self, w, h):
        """Буфер тени: пересоздаётся только если нужен больший размер."""
        need = max(w, h)
        if self._shadow_buf is None or self._shadow_buf.get_width() < need:
            size = (need + 63) // 64 * 64
            self._shadow_buf = pygame.Surface((size, size), pygame.SRCALPHA)
            self._shadow_buf.set_alpha(SHADOW_ALPHA)
        return self._shadow_buf

    def _finish(self, surf, offset=(0, 0)):
        """Финальная обработка готового спрайта корпуса, башни или маски: зерно."""
        apply_grain(surf, self._ppm, offset)
        return surf

    def _get_hull(self, paint, look, spec):
        return self._hull_cache.get_or_build(
            (paint, look.hull_key, spec.HULL_VARIANT),
            lambda: self._build_hull(paint, look, spec))

    def _get_turret(self, team_color, paint, look, emblem, spec):
        return self._turret_cache.get_or_build(
            (team_color, paint, look.turret_key, emblem, spec.HULL_VARIANT),
            lambda: self._build_turret(team_color, paint, look, emblem, spec))

    def _get_barrel(self, bl, bt, look, spec):
        return self._barrel_cache.get_or_build(
            (bl, bt, look.barrel_key, spec.BARREL_KEY), lambda: self._build_barrel(bl, bt, look, spec))

    # ---------- общие детали корпуса ----------

    @staticmethod
    def _draw_track_body(pen, layout, side, broken=False):
        """Тело гусеницы без звеньев (звенья бегут отдельно и рисуются прямо на экране).
        side: -1 левая, +1 правая."""
        tw, top, ln = layout.track_w, layout.track_top, layout.track_len
        left = side * layout.track_x - tw / 2
        if not broken:
            pen.rect(TRACK_BODY, left, top, tw, ln, r=0.22)
            return
        pen.rect(TRACK_BROKEN, left, top, tw, ln, r=0.22)
        for off in BREAK_MARK_OFFSETS:                       # разрывы поперёк ленты
            y = top + off * ln / BREAK_MARK_REF_LEN
            pen.line(TRACK_BROKEN_MARK, left + 0.08, y, left + tw - 0.08, y + 0.35, 0.08)

    def _build_gear(self, spec, left_broken, right_broken):
        """Слой ходовой: обе гусеницы. Лежит под корпусом, того же размера, что спрайт корпуса."""
        ppm = self._ppm
        size = 2 * math.ceil(self.HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = Pen(big, ppm * SS, 0.0, self._hull_shift_m(spec))
        layout = spec.layout
        self._draw_track_body(pen, layout, -1, left_broken)
        self._draw_track_body(pen, layout, +1, right_broken)
        return pygame.transform.smoothscale(big, (size, size))

    def _get_gear(self, spec, left_broken=False, right_broken=False):
        return self._gear_cache.get_or_build(
            (spec.layout.key, left_broken, right_broken),
            lambda: self._build_gear(spec, left_broken, right_broken))

    @staticmethod
    def _scaled_layer(surf, k):
        """Копия слоя в масштабе k (rotozoom без поворота сглаживает и держит альфа-канал)."""
        return surf if abs(k - 1.0) < 1e-3 else pygame.transform.rotozoom(surf, 0.0, k)

    def panel_sprite(self, vehicle):
        """Вид сверху без поворота, тени и отката."""
        spec = vehicle.spec
        look = spec.LOOK
        team = vehicle.team_color
        paint = None if vehicle.team is Team.PLAYER else team
        ppm = self._ppm
        hs, ts = spec.HULL_SCALE, spec.TURRET_SCALE

        bl = int(round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M))
        bt = int(round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M))
        f_px = (spec.GUN_FRONT_M + bl * BARREL_LEN_STEP_M / 2.0 - BARREL_HIDDEN_M / 2.0) * ppm * ts

        # слои снизу вверх, как в draw(): ходовая, корпус, ствол, башня, маска
        layers = [(self._get_gear(spec), hs, 0.0),
                  (self._get_hull(paint, look, spec), hs, 0.0),
                  (self._get_barrel(bl, bt, look, spec), ts, f_px)]
        if self.HAS_TURRET_SPRITE:
            layers.append((self._get_turret(team, paint, look, vehicle.emblem, spec), ts, 0.0))
        build_mantlet = getattr(self, "_build_mantlet", None)      # есть у ПТ-САУ и САУ
        if build_mantlet is not None:
            layers.append((build_mantlet(team, paint, look, spec), hs, 0.0))

        scaled = [(self._scaled_layer(surf, k), shift) for surf, k, shift in layers]
        half = 4 + math.ceil(max(scaled[0][0].get_width() / 2.0,
                                 f_px + scaled[2][0].get_height() / 2.0))
        canvas = pygame.Surface((2 * half, 2 * half), pygame.SRCALPHA)
        for surf, shift in scaled:
            canvas.blit(surf, surf.get_rect(center=(half, half - round(shift))))
        return canvas

    def _draw_track_links(self, screen, tank, cx, cy, hull_k, scale, spec, broken, lift=(None, 0.0)):
        """Бегущие звенья целых гусениц: линии прямо на экране. Сбитая гусеница стоит без звеньев.
        lift = (наклон или None, высота подъёма слоя ходовой в px): звенья поднимаются вместе со слоем."""
        k = self._ppm * scale                        # экранных px на метр спрайта
        if TRACK_LINK_M * k < 3.0:                   # на дальнем зуме звенья сливаются
            return
        tilt, lift_px = lift
        layout = spec.layout
        fx, fy = heading_vector(hull_k * ANGLE_STEP)
        rx, ry = -fy, fx                             # вправо от корпуса
        shift = self._hull_shift_m(spec)
        width = max(1, round(0.06 * k))
        y_min = layout.track_top + 0.05
        y_max = layout.track_top + layout.track_len - 0.05

        def pt(x, y):                                # координаты корпуса (м) -> экран с учётом подъёма
            y += shift
            px = cx + (rx * x - fx * y) * k
            py = cy + (ry * x - fy * y) * k
            py -= lift_px if tilt is None else tilt.at(px, py, lift_px)
            return px, py

        for side, offset, bad in ((-1, tank.left_track_offset, broken[0]),
                                  (1, tank.right_track_offset, broken[1])):
            if bad:
                continue
            xc = side * layout.track_x
            xa, xb = xc - layout.track_w / 2 + 0.07, xc + layout.track_w / 2 - 0.07
            y = layout.track_top - TRACK_LINK_M + offset / PX_PER_M   # смещение хранится в px эталона
            y += math.ceil((y_min - y) / TRACK_LINK_M) * TRACK_LINK_M
            while y < y_max:
                pygame.draw.line(screen, TRACK_LINK, pt(xa, y), pt(xb, y), width)
                y += TRACK_LINK_M

    # ---------- ствол (одинаковый у всех) ----------

    def _build_barrel(self, bl, bt, look, spec):
        """Ствол: узкая вертикальная картинка."""
        ppm = self._ppm
        length = bl * BARREL_LEN_STEP_M
        thick = bt * BARREL_THICK_STEP_M
        half = (length + BARREL_HIDDEN_M) / 2.0  # часть уходит под башню
        parts = barrel_parts_for(spec, length, thick, look)

        ext_x, ext_y = thick / 2.0 + 0.15, half
        for p in parts:
            for cx, cy in corners(p):
                ext_x = max(ext_x, abs(cx))
                ext_y = max(ext_y, abs(cy) - 0.01)     # допуск 1 см: округление данных не должно менять размер

        w = max(2, 2 * math.ceil(ext_x * ppm))
        h = max(2, round(2.0 * ext_y * ppm))
        big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
        pen = Pen(big, ppm * SS)

        pen.rect(GUN, -thick / 2, -half, thick, 2.0 * half)                       # ствол
        draw_parts(pen, parts, BAND_ALL, PartCtx(paint=None, look=look, layout=None))

        return pygame.transform.smoothscale(big, (w, h))