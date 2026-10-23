"""vehicles/sprite_base.py — общая часть рисования техники с орудием: гусеницы, кэши спрайтов, тень,
ствол и главный метод draw. Детали корпуса лежат в hull_parts.py, палитра и Pen в sprite_pen.py."""
import math
import pygame

from engine import LRUCache, SHADOW_ALPHA, heading_vector, clamp, Team, PX_PER_M
from .chassis_params import TRACK_LINK_M
from .gun_params import BARREL_LEN_STEP_M, BARREL_THICK_STEP_M, BARREL_HIDDEN_M
from .hull_parts import HullPartsMixin
from .running_gear import LEFT, RIGHT
from .sprite_pen import (Pen, SS, apply_grain, TRACK_BODY, TRACK_LINK, TRACK_BROKEN,
                         TRACK_BROKEN_MARK, GUN, GUN_LIGHT, GUN_DARK)

# ==========================================
# КОНСТАНТЫ РИСОВКИ
# ==========================================
BREAK_MARK_REF_LEN = 6.3                 # длина гусеницы, для которой заданы смещения разрывов
BREAK_MARK_OFFSETS = (1.3, 2.9, 4.5)     # м от переднего края гусеницы

SHADOW_HULL_M = (0.25, 0.35)             # смещение тени корпуса, м
SHADOW_TURRET_M = (0.40, 0.55)           # башня выше, поэтому тень дальше

ANGLE_STEPS = 480
ANGLE_STEP = 360.0 / ANGLE_STEPS
ROT_CACHE_BYTES = 48 * 1024 * 1024       # бюджет памяти под кэш повёрнутых поверхностей

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
        self._rot_cache.limit = int(clamp(ROT_CACHE_BYTES / per_surface, 40, 3000))

    # ---------- главный метод ----------

    def draw(self, screen, camera, tank):
        ppm = self._ppm
        sx, sy = camera.world_to_screen(tank.x, tank.y)
        cx, cy = int(round(sx)), int(round(sy))

        spec = tank.spec
        look = spec.LOOK
        var = spec.HULL_VARIANT
        hs, ts = spec.HULL_SCALE, spec.TURRET_SCALE
        bl = int(round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M))
        bt = int(round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M))
        team = tank.team_color
        paint = None if tank.team is Team.PLAYER else team
        emblem = tank.emblem
        broken = (tank.tracks.is_broken(LEFT), tank.tracks.is_broken(RIGHT))

        hull_k = self._bucket(tank.hull_angle)
        turret_k = self._bucket(tank.turret_angle)
        barrel_key = (bl, bt, look.barrel_key)

        # корпус и ходовая больше не зависят от фазы гусениц: оба слоя берутся из кэша по углу
        gear_rot = self._rotated("gear", (var, broken),
                                 lambda: self._get_gear(spec, *broken), hull_k, hs)
        hull_rot = self._rotated("hull", (paint, look.hull_key, var),
                                 lambda: self._get_hull(paint, look, spec), hull_k, hs)
        barrel_rot = self._rotated("barrel", barrel_key,
                                   lambda: self._get_barrel(bl, bt, look), turret_k, ts)

        fx, fy = heading_vector(turret_k * ANGLE_STEP)
        f = (spec.GUN_FRONT_M + bl * BARREL_LEN_STEP_M / 2.0 - BARREL_HIDDEN_M / 2.0
             - tank.recoil_m) * ppm * ts
        hull_rect = hull_rot.get_rect(center=(cx, cy))
        gear_rect = gear_rot.get_rect(center=(cx, cy))
        barrel_rect = barrel_rot.get_rect(center=(round(cx + fx * f), round(cy + fy * f)))

        hox, hoy = (round(v * ppm * hs) for v in SHADOW_HULL_M)
        tox, toy = (round(v * ppm * ts) for v in SHADOW_TURRET_M)
        sil_hull = self._rotated(
            "sil_hull", (look.hull_key, var),
            lambda: self._get_sil(("hull", look.hull_key, var), self._gear_plus_hull(spec, paint, look)),
            hull_k, hs)
        sil_barrel = self._rotated(
            "sil_barrel", barrel_key,
            lambda: self._get_sil(("barrel", bl, bt, look.barrel_key), self._get_barrel(bl, bt, look)),
            turret_k, ts)
        parts = [
            (sil_hull, sil_hull.get_rect(center=hull_rect.center).move(hox, hoy)),
            (sil_barrel, sil_barrel.get_rect(center=barrel_rect.center).move(tox, toy)),
        ]

        turret_rot = turret_rect = None
        if self.HAS_TURRET_SPRITE:
            turret_key = (team, paint, look.turret_key, emblem, var)
            turret_rot = self._rotated("turret", turret_key,
                                       lambda: self._get_turret(team, paint, look, emblem, spec), turret_k, ts)
            turret_rect = turret_rot.get_rect(center=(cx, cy))
            sil_turret = self._rotated(
                "sil_turret", (look.turret_key, var),
                lambda: self._get_sil(("turret", look.turret_key, var),
                                      self._get_turret(team, paint, look, emblem, spec)),
                turret_k, ts)
            parts.append((sil_turret, sil_turret.get_rect(center=turret_rect.center).move(tox, toy)))

        union = parts[0][1].unionall([r for _, r in parts[1:]])
        buf = self._ensure_shadow_buf(union.w, union.h)
        buf.fill((0, 0, 0, 0), (0, 0, union.w, union.h))
        for surf, rect in parts:
            buf.blit(surf, (rect.x - union.x, rect.y - union.y))
        screen.blit(buf, union.topleft, area=(0, 0, union.w, union.h))

        screen.blit(gear_rot, gear_rect)                      # тело гусениц под корпусом
        self._draw_track_links(screen, tank, cx, cy, hull_k, hs, spec, broken)   # бегущие звенья
        screen.blit(hull_rot, hull_rect)                      # корпус перекрывает внутренние края гусениц
        screen.blit(barrel_rot, barrel_rect)
        if turret_rot is not None:
            screen.blit(turret_rot, turret_rect)
        self._draw_front_layer(screen, tank, cx, cy, hull_k, hs, team, paint, look)

    # ---------- тень и кэши ----------
    @staticmethod
    def _make_silhouette(surface):
        mask = pygame.mask.from_surface(surface)
        return mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))

    @staticmethod
    def _bucket(angle):
        """Номер положения угла (0..ANGLE_STEPS-1)."""
        return round(angle / ANGLE_STEP) % ANGLE_STEPS

    def _rotated(self, kind, base_key, get_base, bucket, scale):
        """Повёрнутая копия спрайта из кэша."""
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

    def _get_sil(self, key, surface):
        return self._sil_cache.get_or_build(key, lambda: self._make_silhouette(surface))

    def _get_hull(self, paint, look, spec):
        return self._hull_cache.get_or_build(
            (paint, look.hull_key, spec.HULL_VARIANT),
            lambda: self._build_hull(paint, look, spec))

    def _get_turret(self, team_color, paint, look, emblem, spec):
        return self._turret_cache.get_or_build(
            (team_color, paint, look.turret_key, emblem, spec.HULL_VARIANT),
            lambda: self._build_turret(team_color, paint, look, emblem, spec))

    def _get_barrel(self, bl, bt, look):
        return self._barrel_cache.get_or_build(
            (bl, bt, look.barrel_key), lambda: self._build_barrel(bl, bt, look))

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
            (spec.HULL_VARIANT, left_broken, right_broken),
            lambda: self._build_gear(spec, left_broken, right_broken))

    def _gear_plus_hull(self, spec, paint, look):
        """Ходовая + корпус одним спрайтом: из него строится силуэт тени. Зовётся только при промахе кэша."""
        surf = self._get_gear(spec).copy()
        surf.blit(self._get_hull(paint, look, spec), (0, 0))
        return surf

    def _draw_track_links(self, screen, tank, cx, cy, hull_k, scale, spec, broken):
        """Бегущие звенья целых гусениц: линии прямо на экране. Сбитая гусеница стоит без звеньев."""
        k = self._ppm * scale                        # экранных px на метр спрайта
        if TRACK_LINK_M * k < 3.0:                   # на дальнем зуме звенья сливаются
            return
        layout = spec.layout
        fx, fy = heading_vector(hull_k * ANGLE_STEP)
        rx, ry = -fy, fx                             # вправо от корпуса
        shift = self._hull_shift_m(spec)
        width = max(1, round(0.06 * k))
        y_min = layout.track_top + 0.05
        y_max = layout.track_top + layout.track_len - 0.05

        def pt(x, y):                                # координаты корпуса (м) -> экран
            y += shift
            return (cx + (rx * x - fx * y) * k, cy + (ry * x - fy * y) * k)

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
    def _build_barrel(self, bl, bt, look):
        """Ствол: узкая вертикальная картинка (дульный срез сверху). Центр — середина видимой длины."""
        ppm = self._ppm
        length = bl * BARREL_LEN_STEP_M
        thick = bt * BARREL_THICK_STEP_M
        half = (length + BARREL_HIDDEN_M) / 2.0  # часть уходит под башню
        w = max(2, 2 * math.ceil((thick + 0.30) * ppm / 2.0))
        h = max(2, round(2.0 * half * ppm))
        big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
        pen = Pen(big, ppm * SS)

        pen.rect(GUN, -thick / 2, -half, thick, 2.0 * half)                       # ствол
        pen.rect(GUN_LIGHT, -(thick + 0.08) / 2, -half + 0.35 * length,
                 thick + 0.08, 0.30, r=0.05)                                      # эжектор
        pen.rect(GUN_DARK, -(thick + 0.06) / 2, -half, thick + 0.06, 0.22)        # дульный срез

        if look.gun > 0:    # дульный тормоз: шире ствола, но в пределах заготовки (запас 0.30 м)
            bw = thick + (0.14 if look.gun == 1 else 0.22)
            pen.rect(GUN_DARK, -bw / 2, -half + 0.25, bw, 0.40, r=0.04)
            for y in (-half + 0.38, -half + 0.52):
                pen.line(GUN_LIGHT, -bw / 2 + 0.03, y, bw / 2 - 0.03, y, 0.04)

        return pygame.transform.smoothscale(big, (w, h))