"""ui/tank_panel.py — панель танка у правого нижнего угла: слева силуэт с модулями (гусеницы), справа
полоска-разделитель и колонка иконок (снаряд и проходимость). Красные углы при оглушении.
О танках не знает: силуэт и состояние модулей приходят снаружи."""
import math
from typing import NamedTuple
import pygame

from engine import clamp, get_text
from .ammo_icons import make_ammo_icon
from .plate import draw_plate
from .theme import PANEL_BORDER, TEXT_DIM

PANEL_SIDE = 172             # сторона квадрата = высота колонки ячеек улучшений (3 * 52 + 2 * 8)
PANEL_RADIUS = 8             # скругление плашки
EDGE_MARGIN = 10             # от правого края окна
BOTTOM_MARGIN = 10           # от нижнего края окна
ICON_COL_W = 46              # колонка иконок справа внутри квадрата
PAD = 8                      # отступ силуэта от краёв своей области
SIL_PAD_V = 14               # вертикальный запас под силуэт: ствол целиком и контур не касаются плашки
DIVIDER_INSET = 12           # полоска не доходит до верха и низа квадрата
LOCK_COLOR = (255, 150, 40)            # подброс: стрелять нельзя
LOCK_RING_PAD = 5

# размер области, в которую вписывается силуэт (его строит vehicles.build_silhouette)
SILHOUETTE_BOX = (PANEL_SIDE - ICON_COL_W - 2 * PAD, PANEL_SIDE - 2 * SIL_PAD_V)

# --- модули на силуэте (гусеницы) ---
MODULE_OK = "ok"
MODULE_BROKEN = "broken"
MODULE_REPAIR = "repair"
MODULE_RADIUS_M = 0.22                 # скругление гусеницы, м корпуса (как в рендерере)
C_BROKEN = (225, 55, 45)
C_BROKEN_EDGE = (90, 15, 12)
C_REPAIR_BASE = (120, 100, 25)         # ремонт: фон
C_REPAIR = (255, 215, 60)              # ремонт: заливка прогресса
C_REPAIR_EDGE = (90, 70, 10)

# --- колонка иконок ---
ICON_SLOT = 34                         # сторона слота иконки
ICON_FROM_EDGE = 44                    # центр верхнего слота от верха квадрата
BULLET_SIZE = (34, 20)                 # иконка снаряда до поворота (остриём вправо)
BULLET_DIM_ALPHA = 85                  # режим стрельбы выключен: почти прозрачная
GLOW_COLOR = (255, 215, 70)
GLOW_PAD = 6                           # запас под свечение вокруг иконки
GLOW_SHRINK = 3                        # во сколько раз уменьшаем перед растяжением: так получается размытие

# --- проходимость «>>» ---
TERRAIN_PLAIN = "plain"
TERRAIN_WATER = "water"
TERRAIN_MUD = "mud"
TERRAIN_COLORS = {TERRAIN_PLAIN: (200, 205, 212),
                  TERRAIN_WATER: (90, 170, 230),
                  TERRAIN_MUD: (160, 120, 75)}
SPEED_EDGE = (20, 22, 26)
SPEED_FROM_EDGE = 52                   # центр значка «>>» от низа квадрата (ниже остаётся место под подпись)
PERCENT_SIZE = 14

# --- оглушение: красные углы ---
STUN_RADIUS = 64                       # на сколько px красное свечение заходит от угла
STUN_COLOR = (230, 40, 35)
STUN_MAX_ALPHA = 200                   # прозрачность в самом углу
STUN_CURVE = 1.6                       # чем больше, тем быстрее свечение гаснет к центру
STUN_FADE_IN_S = 0.12
STUN_FADE_OUT_S = 0.3                  # плавное затухание в конце оглушения
STUN_PULSE_HZ = 2.0
STUN_PULSE_DEPTH = 0.25                # на сколько падает яркость в провале пульса

class ModuleView(NamedTuple):
    rect: tuple                        # (u0, v0, u1, v1) в метрах корпуса (u вправо, v назад)
    state: str                         # MODULE_OK / MODULE_BROKEN / MODULE_REPAIR
    progress: float = 0.0              # для MODULE_REPAIR: доля ремонта 0..1

def panel_rect(size):
    """Прямоугольник панели для окна size. Его же читает UpgradeBar, чтобы встать левее."""
    w, h = size
    return pygame.Rect(w - EDGE_MARGIN - PANEL_SIDE, h - BOTTOM_MARGIN - PANEL_SIDE,
                       PANEL_SIDE, PANEL_SIDE)

# ==========================================
# ЗАГОТОВКИ (строятся один раз)
# ==========================================

def _make_stun_glow():
    """Квадрат панели с красным свечением в четырёх углах. Строится из одной четверти (отражениями),
    затем обрезается по скруглению плашки, чтобы красное не вылезало за её углы."""
    r = STUN_RADIUS
    quarter = pygame.Surface((r, r), pygame.SRCALPHA)
    for y in range(r):
        for x in range(r):
            d = math.hypot(x + 0.5, y + 0.5) / r
            if d < 1.0:
                alpha = round(STUN_MAX_ALPHA * (1.0 - d) ** STUN_CURVE)
                quarter.set_at((x, y), (*STUN_COLOR, alpha))

    side = PANEL_SIDE
    glow = pygame.Surface((side, side), pygame.SRCALPHA)
    glow.blit(quarter, (0, 0))
    glow.blit(pygame.transform.flip(quarter, True, False), (side - r, 0))
    glow.blit(pygame.transform.flip(quarter, False, True), (0, side - r))
    glow.blit(pygame.transform.flip(quarter, True, True), (side - r, side - r))

    mask = pygame.Surface((side, side), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=PANEL_RADIUS)
    glow.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)       # вне скругления альфа станет 0
    return glow

def _make_speed_icon(color):
    """Значок «>>»: два шеврона. Рисуется в 4 раза крупнее и сжимается, чтобы края были гладкими."""
    ss = 4
    size = ICON_SLOT
    big = pygame.Surface((size * ss, size * ss), pygame.SRCALPHA)
    w, h, th, gap = 11 * ss, 22 * ss, 5 * ss, 9 * ss
    x0 = (size * ss - (w + gap)) / 2.0
    y0 = (size * ss - h) / 2.0
    chevron = [(0, 0), (th, 0), (w, h / 2.0), (th, h), (0, h), (w - th, h / 2.0)]
    for dx in (0, gap):
        poly = [(x0 + dx + px, y0 + py) for px, py in chevron]
        pygame.draw.polygon(big, color, poly)
        pygame.draw.polygon(big, SPEED_EDGE, poly, ss)
    return pygame.transform.smoothscale(big, (size, size))

class TankPanel:
    def __init__(self):
        self.rect = pygame.Rect(0, 0, PANEL_SIDE, PANEL_SIDE)
        self.icon_col = pygame.Rect(0, 0, ICON_COL_W, PANEL_SIDE)
        self.bullet_slot = pygame.Rect(0, 0, ICON_SLOT, ICON_SLOT)
        self.speed_slot = pygame.Rect(0, 0, ICON_SLOT, ICON_SLOT)
        self.silhouette = None          # объект Silhouette (vehicles) или None
        self.silhouette_pos = (0, 0)    # левый верхний угол силуэта на экране

        self.modules = ()               # [ModuleView, ...]: ставит TankPanelLink каждый кадр
        self.ammo = None                # текущий снаряд (AmmoKind) или None
        self.firing = False             # включён ли боевой режим
        self.stun_left = 0.0            # сколько секунд осталось оглушения
        self.lift_left = 0.0            # сколько секунд осталось подброса (стрельба заблокирована)
        self.lift_total = 0.0
        self.terrain = TERRAIN_PLAIN    # TERRAIN_PLAIN / TERRAIN_WATER / TERRAIN_MUD
        self.speed_pct = 100            # влияние местности на скорость, %

        self._bullets = {}              # снаряд -> (бледная иконка, яркая иконка, свечение)
        self._speed_icons = {}          # вид местности -> значок «>>»
        self._stun_glow = _make_stun_glow()
        self._stun_since = 0            # момент (мс), когда началось текущее оглушение
        self._size = None
        self.update(pygame.display.get_surface().get_size())

    # ---------- состояние ----------
    def update(self, size):
        """Раскладка пересчитывается только при смене размера окна."""
        if size != self._size:
            self._size = size
            self._relayout()

    def set_silhouette(self, silhouette):
        self.silhouette = silhouette
        self._relayout()

    def set_modules(self, modules):
        self.modules = modules

    def set_weapon(self, ammo, firing):
        self.ammo = ammo
        self.firing = firing

    def set_lift(self, left, total):
        self.lift_left = left
        self.lift_total = total

    def _draw_lock(self, screen):
        """Перечёркнутое кольцо вокруг иконки снаряда с дугой оставшегося времени."""
        if self.lift_left <= 0.0 or self.lift_total <= 0.0:
            return
        cx, cy = self.bullet_slot.center
        r = ICON_SLOT // 2 + LOCK_RING_PAD
        frac = clamp(self.lift_left / self.lift_total, 0.0, 1.0)
        rect = pygame.Rect(cx - r, cy - r, 2 * r, 2 * r)
        pygame.draw.circle(screen, (90, 55, 20), (cx, cy), r, 2)
        pygame.draw.arc(screen, LOCK_COLOR, rect, math.pi / 2, math.pi / 2 + 2.0 * math.pi * frac, 3)
        d = round(r * 0.7)
        pygame.draw.line(screen, LOCK_COLOR, (cx - d, cy + d), (cx + d, cy - d), 3)

    def set_stun(self, seconds_left):
        """Сколько секунд осталось оглушения (0: нет). Начало оглушения запоминаем для плавного появления."""
        if seconds_left > 0.0 and self.stun_left <= 0.0:
            self._stun_since = pygame.time.get_ticks()
        self.stun_left = seconds_left

    def set_terrain(self, kind, k):
        """kind: TERRAIN_*, k: множитель скорости от местности (0..1)."""
        self.terrain = kind
        self.speed_pct = round(k * 100.0)

    def _relayout(self):
        self.rect = panel_rect(self._size)
        self.icon_col = pygame.Rect(self.rect.right - ICON_COL_W, self.rect.y, ICON_COL_W, PANEL_SIDE)
        cx = self.icon_col.centerx
        self.bullet_slot.center = (cx, self.rect.y + ICON_FROM_EDGE)
        self.speed_slot.center = (cx, self.rect.bottom - SPEED_FROM_EDGE)
        if self.silhouette is not None:
            w, h = self.silhouette.surface.get_size()
            sx = self.rect.x + (PANEL_SIDE - ICON_COL_W) // 2     # центр левой области
            self.silhouette_pos = (sx - w // 2, self.rect.centery - h // 2)

    # ---------- интерфейс слоя ----------
    def covers(self, pos):
        return self.rect.collidepoint(pos)

    def cancel_drag(self):
        pass

    def handle_event(self, event, mouse_pos):
        """Любые клики по панели поглощаем: выстрела в мир не будет."""
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)

    # ---------- иконка снаряда ----------
    def _bullet(self, kind):
        """(бледная иконка, яркая иконка, свечение) для снаряда kind. Строится один раз."""
        cached = self._bullets.get(kind)
        if cached is not None:
            return cached
        icon = pygame.transform.rotate(make_ammo_icon(kind, BULLET_SIZE), 90)    # остриё вверх
        w, h = icon.get_size()

        dim = icon.copy()
        dim.set_alpha(BULLET_DIM_ALPHA)

        # свечение: форма иконки одним жёлтым цветом (цвет «пустых» пикселей тот же, чтобы края
        # не темнели при размытии), затем уменьшение и растяжение обратно
        size = (w + 2 * GLOW_PAD, h + 2 * GLOW_PAD)
        flat = pygame.mask.from_surface(icon).to_surface(setcolor=(*GLOW_COLOR, 255),
                                                         unsetcolor=(*GLOW_COLOR, 0))
        glow = pygame.Surface(size, pygame.SRCALPHA)
        glow.fill((*GLOW_COLOR, 0))
        glow.blit(flat, (GLOW_PAD, GLOW_PAD))
        small = pygame.transform.smoothscale(glow, (max(1, size[0] // GLOW_SHRINK),
                                                    max(1, size[1] // GLOW_SHRINK)))
        glow = pygame.transform.smoothscale(small, size)

        self._bullets[kind] = (dim, icon, glow)
        return self._bullets[kind]

    # ---------- рисование ----------
    def draw(self, screen, mouse_pos):
        draw_plate(screen, self.rect, alpha=205, radius=PANEL_RADIUS)
        self._draw_stun(screen)
        x = self.icon_col.left
        pygame.draw.line(screen, PANEL_BORDER, (x, self.rect.y + DIVIDER_INSET),
                         (x, self.rect.bottom - DIVIDER_INSET), 1)
        if self.silhouette is not None:
            screen.blit(self.silhouette.surface, self.silhouette_pos)
            self._draw_modules(screen)
        self._draw_bullet(screen)
        self._draw_lock(screen)
        self._draw_speed(screen)

    def _draw_stun(self, screen):
        """Красные углы, пока техника оглушена: плавное появление, лёгкая пульсация, затухание в конце."""
        if self.stun_left <= 0.0:
            return
        age = (pygame.time.get_ticks() - self._stun_since) / 1000.0
        k = min(1.0, age / STUN_FADE_IN_S, self.stun_left / STUN_FADE_OUT_S)
        if k <= 0.0:
            return
        phase = 2.0 * math.pi * STUN_PULSE_HZ * pygame.time.get_ticks() / 1000.0
        pulse = 1.0 - STUN_PULSE_DEPTH * (0.5 + 0.5 * math.sin(phase))
        self._stun_glow.set_alpha(round(255 * k * pulse))
        screen.blit(self._stun_glow, self.rect.topleft)

    def _draw_modules(self, screen):
        """Сломанные и ремонтируемые гусеницы поверх силуэта. Целые не рисуем: они уже в силуэте."""
        sil = self.silhouette
        ox, oy = self.silhouette_pos
        radius = max(1, round(MODULE_RADIUS_M * sil.px_per_m))
        for m in self.modules:
            if m.state == MODULE_OK:
                continue
            u0, v0, u1, v1 = m.rect
            x0, y0 = sil.hull_point(u0, v0)
            x1, y1 = sil.hull_point(u1, v1)
            left, top = round(ox + x0), round(oy + y0)
            r = pygame.Rect(left, top, max(1, round(ox + x1) - left), max(1, round(oy + y1) - top))
            if m.state == MODULE_BROKEN:
                pygame.draw.rect(screen, C_BROKEN, r, border_radius=radius)
                pygame.draw.rect(screen, C_BROKEN_EDGE, r, 1, border_radius=radius)
                continue
            pygame.draw.rect(screen, C_REPAIR_BASE, r, border_radius=radius)
            fill_h = round(r.h * clamp(m.progress, 0.0, 1.0))
            if fill_h > 0:                                    # яркая заливка растёт снизу вверх
                old = screen.get_clip()
                screen.set_clip(pygame.Rect(r.x, r.bottom - fill_h, r.w, fill_h))
                pygame.draw.rect(screen, C_REPAIR, r, border_radius=radius)
                screen.set_clip(old)
            pygame.draw.rect(screen, C_REPAIR_EDGE, r, 1, border_radius=radius)

    def _draw_bullet(self, screen):
        if self.ammo is None:
            return
        dim, bright, glow = self._bullet(self.ammo)
        center = self.bullet_slot.center
        if self.firing:
            rect = glow.get_rect(center=center)
            screen.blit(glow, rect)
            screen.blit(glow, rect)                           # дважды: размытое свечение иначе слишком слабое
            screen.blit(bright, bright.get_rect(center=center))
        else:
            screen.blit(dim, dim.get_rect(center=center))

    def _draw_speed(self, screen):
        """Значок «>>» цвета местности и процент скорости под ним."""
        icon = self._speed_icons.get(self.terrain)
        if icon is None:
            icon = self._speed_icons[self.terrain] = _make_speed_icon(TERRAIN_COLORS[self.terrain])
        screen.blit(icon, icon.get_rect(center=self.speed_slot.center))
        color = TEXT_DIM if self.terrain == TERRAIN_PLAIN else TERRAIN_COLORS[self.terrain]
        label = get_text(f"{self.speed_pct}%", PERCENT_SIZE, color)
        screen.blit(label, label.get_rect(midtop=(self.speed_slot.centerx, self.speed_slot.bottom + 1)))