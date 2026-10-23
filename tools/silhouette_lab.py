"""tools/silhouette_lab.py — лаборатория силуэтов классов корпуса.
Рисует настоящим TankRenderer.draw через настоящую Camera.

Клавиши:
  M      режим: цвет / чёрная заливка / чёрная заливка одной длины (без ствола)
  Z      масштаб: ~10, ~19, ~38 px/м
  B      слепой тест вкл/выкл (перемешивает и убирает подписи)
  N      перемешать заново (в слепом тесте)
  Пробел показать ответ
  S      сохранить скриншот в tools/baseline/
  Esc    выход
"""
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame
pygame.init()

W, H = 1200, 800
COL_W = W // 3
CELL = (COL_W - 8, 540)                 # размер одной ячейки с танком
TOP = 60                                # верх ячеек
PANEL_Y = TOP + CELL[1] + 8             # верх панели метрик
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Лаборатория силуэтов")

from engine import PX_PER_M, get_text, FONT_SIZE_LABEL, FONT_SIZE_HEADER
from vehicles import Tank, TankSpec, TankRenderer, TANK_PARAMS
from vehicles.chassis.hulls import HULL_CLASS_RU
from world import Camera, ZOOM_LEVELS

# ==========================================
# НАСТРОЙКИ
# ==========================================
ZOOMS = (0, 7, 15)                      # уровни ZOOM_LEVELS: ~10, ~19, ~38 px/м
METRIC_ZOOM = ZOOMS[-1]                 # на каком зуме меряем габариты
BARREL_SHIFT_WORLD_PX = 150.0           # камера смотрит чуть выше танка: ствол смотрит вверх
KEY = (255, 0, 255)                     # фон для выделения силуэта
KEY_THRESHOLD = (100, 100, 100, 255)    # тень (alpha 80) отличается от фона меньше, чем на 100
GROUND = (70, 100, 70)
MASK_BG = (232, 232, 236)
PANEL_BG = (28, 31, 36)
C_TEXT = (230, 230, 230)
C_DIM = (150, 156, 166)
C_OK = (90, 200, 90)
C_BAD = (230, 80, 70)
ASPECT_MIN_DIFF = 0.15                  # критерий приёмки: отношение длины к ширине различается минимум на 15%

MODE_NAMES = ("Цвет", "Чёрная заливка", "Чёрная заливка, одна длина (корпус и башня, без ствола)")

_ref = {k: p.default for k, p in TANK_PARAMS.items()}
PRESETS = [
    ("Лёгкий (тест)", {**_ref, "front_armor_mm": 150, "side_armor_mm": 30,
                       "rear_armor_mm": 20, "engine_power_hp": 2000}),
    ("Средний (эталон)", dict(_ref)),
    ("Тяжёлый (тест)", {**_ref, "front_armor_mm": 500, "side_armor_mm": 375,
                        "rear_armor_mm": 250, "engine_power_hp": 800}),
]

# ==========================================
# РЕНДЕРЕР БЕЗ СТВОЛА (для сравнения пропорций корпуса)
# ==========================================
class LabRenderer(TankRenderer):
    def __init__(self, hide_barrel):
        super().__init__()
        self.hide_barrel = hide_barrel

    def _build_barrel(self, bl, bt, look):
        if self.hide_barrel:
            return pygame.Surface((4, 4), pygame.SRCALPHA)     # прозрачная заглушка
        return super()._build_barrel(bl, bt, look)

# ==========================================
# ПОМОЩНИКИ
# ==========================================
def tank_mask(surface):
    """Маска танка: всё, что не фон и не тень."""
    mask = pygame.mask.from_threshold(surface, KEY, KEY_THRESHOLD)
    mask.invert()
    return mask

def bbox(mask):
    rects = mask.get_bounding_rects()
    if not rects:
        return pygame.Rect(0, 0, 1, 1)
    return rects[0].unionall(rects[1:])

def draw_text(text, size, color, pos):
    screen.blit(get_text(text, size, color), pos)

# ==========================================
# ЛАБОРАТОРИЯ
# ==========================================
class Lab:
    def __init__(self):
        self.names = [name for name, _ in PRESETS]
        self.tanks = [Tank(0.0, 0.0, spec=TankSpec.from_values(values)) for _, values in PRESETS]
        self.rends = {False: LabRenderer(False), True: LabRenderer(True)}
        self._rend_ppm = {False: None, True: None}
        self.renders = {}                # (idx, level, без_ствола, фон) -> Surface
        self.cells = {}                  # (режим, idx, level) -> готовая ячейка
        self._metrics = None

        self.mode = 0
        self.zoom_i = 1
        self.blind = False
        self.reveal = False
        self.order = [0, 1, 2]           # какой танк в какой колонке

    # ---------- рендер настоящим кодом игры ----------
    def render(self, idx, level, hide_barrel, bg):
        key = (idx, level, hide_barrel, bg)
        surf = self.renders.get(key)
        if surf is not None:
            return surf
        cam = Camera(*CELL)
        cam.zoom_by(level - cam.zoom_level)
        cam.center_on(0.0, 0.0 if hide_barrel else -BARREL_SHIFT_WORLD_PX)
        ppm = PX_PER_M * cam.zoom
        rend = self.rends[hide_barrel]
        if self._rend_ppm[hide_barrel] != ppm:         # set_zoom сбрасывает кэши спрайтов
            rend.set_zoom(ppm)
            self._rend_ppm[hide_barrel] = ppm
        surf = pygame.Surface(CELL)
        surf.fill(bg)
        rend.draw(surf, cam, self.tanks[idx])
        self.renders[key] = surf
        return surf

    def _hull_mask(self, idx, level):
        """Маска, рамка и чёрный силуэт корпуса с башней (без ствола)."""
        mask = tank_mask(self.render(idx, level, True, KEY))
        sil = mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))
        return mask, bbox(mask), sil

    # ---------- ячейки ----------
    def cell(self, idx, level):
        if self.mode == 0:
            return self.render(idx, level, False, GROUND)

        key = (self.mode, idx, level)
        cell = self.cells.get(key)
        if cell is not None:
            return cell

        cell = pygame.Surface(CELL)
        cell.fill(MASK_BG)
        if self.mode == 1:
            mask = tank_mask(self.render(idx, level, False, KEY))
            cell.blit(mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0)), (0, 0))
        else:
            _, rect, sil = self._hull_mask(idx, level)
            target = self._hull_mask(1, level)[1].h        # длина среднего танка на этом зуме
            k = target / rect.h
            crop = sil.subsurface(rect).copy()
            size = (max(1, round(rect.w * k)), max(1, round(rect.h * k)))
            crop = pygame.transform.smoothscale(crop, size)
            cell.blit(crop, crop.get_rect(center=(CELL[0] // 2, CELL[1] // 2)))
        self.cells[key] = cell
        return cell

    # ---------- метрики ----------
    def metrics(self):
        """(ширина м, длина м, длина/ширина) по каждому танку, корпус с башней без ствола."""
        if self._metrics is None:
            ppm = PX_PER_M * ZOOM_LEVELS[METRIC_ZOOM]
            out = []
            for idx in range(len(self.tanks)):
                rect = self._hull_mask(idx, METRIC_ZOOM)[1]
                w, ln = rect.w / ppm, rect.h / ppm
                out.append((w, ln, ln / w))
            self._metrics = out
        return self._metrics

    # ---------- управление ----------
    def shuffle(self):
        old = list(self.order)
        while self.order == old:
            random.shuffle(self.order)
        self.reveal = False

    def toggle_blind(self):
        self.blind = not self.blind
        if self.blind:
            self.shuffle()
        else:
            self.order = [0, 1, 2]
            self.reveal = False

    def hidden(self):
        return self.blind and not self.reveal

    # ---------- рисование ----------
    def draw(self):
        screen.fill(PANEL_BG)
        level = ZOOMS[self.zoom_i]
        ppm = PX_PER_M * ZOOM_LEVELS[level]
        draw_text(f"Режим: {MODE_NAMES[self.mode]}    Масштаб: {ppm:.0f} px/м"
                  + ("    СЛЕПОЙ ТЕСТ" if self.blind else ""), FONT_SIZE_HEADER, C_TEXT, (10, 8))
        draw_text("M режим | Z масштаб | B слепой тест | N перемешать | Пробел ответ | S скриншот | Esc выход",
                  FONT_SIZE_LABEL, C_DIM, (10, 34))

        for slot, idx in enumerate(self.order):
            x = slot * COL_W + 4
            screen.blit(self.cell(idx, level), (x, TOP))
            if self.hidden():
                label = f"№{slot + 1}"
            else:
                spec = self.tanks[idx].spec
                label = (f"{self.names[idx]}: класс {HULL_CLASS_RU[spec.HULL_CLASS]}, "
                         f"раскладка {spec.layout.key}")
            draw_text(label, FONT_SIZE_LABEL, C_TEXT, (x + 6, TOP + 6))
            pygame.draw.rect(screen, (70, 76, 86), (x, TOP, CELL[0], CELL[1]), 1)

        self._draw_panel()

    def _draw_panel(self):
        y = PANEL_Y
        if self.hidden():
            draw_text("Какой танк лёгкий, средний, тяжёлый? Нажмите Пробел, чтобы проверить.",
                      FONT_SIZE_LABEL, C_DIM, (10, y))
            return
        m = self.metrics()
        draw_text(f"Габариты (корпус и башня, без ствола, измерено на {PX_PER_M * ZOOM_LEVELS[METRIC_ZOOM]:.0f} px/м):",
                  FONT_SIZE_LABEL, C_DIM, (10, y))
        y += 22
        for idx, (w, ln, a) in enumerate(m):
            draw_text(f"{self.names[idx]}: ширина {w:.2f} м, длина {ln:.2f} м, длина/ширина = {a:.2f}",
                      FONT_SIZE_LABEL, C_TEXT, (10, y))
            y += 20
        y += 6
        for i, j in ((0, 1), (1, 2), (0, 2)):
            a, b = m[i][2], m[j][2]
            diff = abs(a - b) / max(a, b)
            ok = diff >= ASPECT_MIN_DIFF
            draw_text(f"Отношение сторон: {self.names[i]} и {self.names[j]} различаются на {diff * 100:.0f}% "
                      f"(нужно не меньше {ASPECT_MIN_DIFF * 100:.0f}%): {'ок' if ok else 'мало'}",
                      FONT_SIZE_LABEL, C_OK if ok else C_BAD, (10, y))
            y += 20

    def save_screenshot(self):
        folder = os.path.join(ROOT, "tools", "baseline")
        os.makedirs(folder, exist_ok=True)
        level = ZOOMS[self.zoom_i]
        path = os.path.join(folder, f"lab_mode{self.mode}_z{level}.png")
        pygame.image.save(screen, path)
        print(f"Сохранено: {path}")

def main():
    lab = Lab()
    clock = pygame.time.Clock()
    print("Критерии приёмки силуэтов (на 19 px/м):\n"
          " - чёрные заливки одной длины различимы без подписей (слепой тест);\n"
          " - классы различаются минимум по трём каналам из вашего списка;\n"
          f" - отношение длины к ширине различается минимум на {ASPECT_MIN_DIFF * 100:.0f}%;\n"
          " - самые мелкие значимые детали не меньше 0.4-0.5 м.")
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_m:
                    lab.mode = (lab.mode + 1) % len(MODE_NAMES)
                elif e.key == pygame.K_z:
                    lab.zoom_i = (lab.zoom_i + 1) % len(ZOOMS)
                elif e.key == pygame.K_b:
                    lab.toggle_blind()
                elif e.key == pygame.K_n and lab.blind:
                    lab.shuffle()
                elif e.key == pygame.K_SPACE:
                    lab.reveal = not lab.reveal
                elif e.key == pygame.K_s:
                    lab.save_screenshot()
        lab.draw()
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()

main()