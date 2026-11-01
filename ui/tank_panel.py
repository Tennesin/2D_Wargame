"""ui/tank_panel.py — панель танка у правого нижнего угла: слева силуэт, справа полоска-разделитель
и колонка иконок. О танках не знает: силуэт приходит снаружи готовым (объект с полем surface)."""
import pygame

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

def panel_rect(size):
    """Прямоугольник панели для окна size. Его же читает UpgradeBar, чтобы встать левее."""
    w, h = size
    return pygame.Rect(w - EDGE_MARGIN - PANEL_SIDE, h - BOTTOM_MARGIN - PANEL_SIDE,
                       PANEL_SIDE, PANEL_SIDE)

class TankPanel:
    def __init__(self):
        self.rect = pygame.Rect(0, 0, PANEL_SIDE, PANEL_SIDE)
        self.icon_col = pygame.Rect(0, 0, ICON_COL_W, PANEL_SIDE)   # колонка иконок (этапы 4 и 6)
        self.silhouette = None          # объект с полем surface (vehicles.Silhouette) или None
        self.silhouette_pos = (0, 0)    # левый верхний угол силуэта на экране (нужен гусеницам на этапе 3)
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

    def _relayout(self):
        self.rect = panel_rect(self._size)
        self.icon_col = pygame.Rect(self.rect.right - ICON_COL_W, self.rect.y, ICON_COL_W, PANEL_SIDE)
        if self.silhouette is not None:
            w, h = self.silhouette.surface.get_size()
            cx = self.rect.x + (PANEL_SIDE - ICON_COL_W) // 2     # центр левой области
            self.silhouette_pos = (cx - w // 2, self.rect.centery - h // 2)

    # ---------- интерфейс слоя ----------
    def covers(self, pos):
        return self.rect.collidepoint(pos)

    def cancel_drag(self):
        pass

    def handle_event(self, event, mouse_pos):
        """Любые клики по панели поглощаем: выстрела в мир не будет."""
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)

    # ---------- рисование ----------
    def draw(self, screen, mouse_pos):
        draw_plate(screen, self.rect, alpha=205, radius=8)
        x = self.icon_col.left
        pygame.draw.line(screen, PANEL_BORDER, (x, self.rect.y + DIVIDER_INSET),
                         (x, self.rect.bottom - DIVIDER_INSET), 1)
        if self.silhouette is not None:
            screen.blit(self.silhouette.surface, self.silhouette_pos)