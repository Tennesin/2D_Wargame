"""ui/tank_panel.py — панель танка у правого нижнего угла: слева силуэт с модулями (гусеницы), справа
полоска-разделитель и колонка иконок. О танках не знает: силуэт и состояние модулей приходят снаружи."""
from typing import NamedTuple

import pygame

from engine import clamp
from .ammo_icons import make_ammo_icon
from .plate import draw_plate
from .theme import PANEL_BORDER

PANEL_SIDE = 172             # сторона квадрата = высота колонки ячеек улучшений (3 * 52 + 2 * 8)
EDGE_MARGIN = 10             # от правого края окна
BOTTOM_MARGIN = 10           # от нижнего края окна
ICON_COL_W = 46              # колонка иконок справа внутри квадрата
PAD = 8                      # отступ силуэта от краёв своей области
DIVIDER_INSET = 12           # полоска не доходит до верха и низа квадрата

# размер области, в которую вписывается силуэт (его строит vehicles.build_silhouette)
SILHOUETTE_BOX = (PANEL_SIDE - ICON_COL_W - 2 * PAD, PANEL_SIDE - 2 * PAD)

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
ICON_FROM_EDGE = 44                    # центр верхнего слота от верха квадрата (нижнего: от низа)
BULLET_SIZE = (34, 20)                 # иконка снаряда до поворота (остриём вправо)
BULLET_DIM_ALPHA = 85                  # режим стрельбы выключен: почти прозрачная
GLOW_COLOR = (255, 215, 70)
GLOW_PAD = 6                           # запас под свечение вокруг иконки
GLOW_SHRINK = 3                        # во сколько раз уменьшаем перед растяжением: так получается размытие

class ModuleView(NamedTuple):
    rect: tuple                        # (u0, v0, u1, v1) в метрах корпуса (u вправо, v назад)
    state: str                         # MODULE_OK / MODULE_BROKEN / MODULE_REPAIR
    progress: float = 0.0              # для MODULE_REPAIR: доля ремонта 0..1

def panel_rect(size):
    """Прямоугольник панели для окна size. Его же читает UpgradeBar, чтобы встать левее."""
    w, h = size
    return pygame.Rect(w - EDGE_MARGIN - PANEL_SIDE, h - BOTTOM_MARGIN - PANEL_SIDE,
                       PANEL_SIDE, PANEL_SIDE)

class TankPanel:
    def __init__(self):
        self.rect = pygame.Rect(0, 0, PANEL_SIDE, PANEL_SIDE)
        self.icon_col = pygame.Rect(0, 0, ICON_COL_W, PANEL_SIDE)
        self.bullet_slot = pygame.Rect(0, 0, ICON_SLOT, ICON_SLOT)
        self.speed_slot = pygame.Rect(0, 0, ICON_SLOT, ICON_SLOT)     # «>>»: появится на этапе 6
        self.silhouette = None          # объект Silhouette (vehicles) или None
        self.silhouette_pos = (0, 0)    # левый верхний угол силуэта на экране

        self.modules = ()               # [ModuleView, ...]: ставит TankPanelLink каждый кадр
        self.ammo = None                # текущий снаряд (AmmoKind) или None
        self.firing = False             # включён ли боевой режим

        self._bullets = {}              # снаряд -> (бледная иконка, яркая иконка, свечение)
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

    def _relayout(self):
        self.rect = panel_rect(self._size)
        self.icon_col = pygame.Rect(self.rect.right - ICON_COL_W, self.rect.y, ICON_COL_W, PANEL_SIDE)
        cx = self.icon_col.centerx
        self.bullet_slot.center = (cx, self.rect.y + ICON_FROM_EDGE)
        self.speed_slot.center = (cx, self.rect.bottom - ICON_FROM_EDGE)
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
        draw_plate(screen, self.rect, alpha=205, radius=8)
        x = self.icon_col.left
        pygame.draw.line(screen, PANEL_BORDER, (x, self.rect.y + DIVIDER_INSET),
                         (x, self.rect.bottom - DIVIDER_INSET), 1)
        if self.silhouette is not None:
            screen.blit(self.silhouette.surface, self.silhouette_pos)
            self._draw_modules(screen)
        self._draw_bullet(screen)

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
            r = pygame.Rect(round(ox + x0), round(oy + y0), max(1, round(x1 - x0)), max(1, round(y1 - y0)))
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