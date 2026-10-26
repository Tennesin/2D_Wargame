"""game/scenes/map_editor.py — редактор карт: каркас сцены (камера, панель инструментов, сохранение, выход).
Инструменты (стена, камень, ландшафт) подключаются через _tool_click и панели режимов MAP_*."""
import math
from types import SimpleNamespace

import pygame

from combat import EffectsSystem
from engine import (WORLD, PX_PER_M, AlphaLayer, get_text,
                    FONT_SIZE_LABEL, FONT_SIZE_HEADER)
from inputs import InputHandler, Action
from structures import WallManager
from ui import SidePanel, ACTIVE_BUTTON_COLORS, DELETE_BUTTON_COLORS
from world import Camera, TerrainMap, WorldGenerator, START_CLEAR_M
from world.mapdata import DEFAULT_NAME, MAX_NAME_LEN

from .base import Scene
from ..content import texts
from ..content.panels import (PanelMode, build_editor_panels, TOOL_MODE,
                              STAT_NAME, STAT_SIZE, STAT_ROCKS, STAT_WALLS, STAT_FILE)
from ..editor import EditorBar, Dialog, load_walls, collect_walls
from ..match.control.camera import CameraController
from ..view.world_renderer import Renderer

START_ZOOM = 0.12
EDIT_ZOOM_MIN, EDIT_ZOOM_MAX = 0.04, 0.5      # дальше 0.04 вода строится слишком большим числом блоков
PAN_SPEED_PX = 700.0                          # скорость перемещения клавишами, экранных px в секунду
PAN_FAST_K = 2.5                              # со Shift быстрее

START_COLOR = (255, 220, 80)
C_GOOD = (110, 220, 110)
C_BAD = (240, 80, 70)
C_DIM = (170, 176, 186)

class _NoFleet:
    """Пустая «техника»: Renderer рисует всё, что лежит в fleet.vehicles."""
    vehicles = ()

def _short(text, limit=24):
    return text if len(text) <= limit else text[:limit - 1] + "…"

class MapEditorScene(Scene):
    BACKGROUND = False
    FREE_BACKGROUND = True           # фон меню в редакторе не нужен: освобождаем его память

    def __init__(self, session, map_data, on_exit, on_quit):
        """map_data: новая (file is None) или загруженная карта. on_exit(): вернуться в список карт."""
        self.session = session
        self.store = session.maps
        self.map = map_data
        self.on_exit = on_exit
        self.on_quit = on_quit
        self.dirty = False                   # есть ли изменения после последнего сохранения
        self.tool = "wall"
        self._toast = None                   # [текст, цвет, секунд осталось]

        # --- мир: камера, местность, стены, рисование ---
        WORLD.set_size(map_data.width_m, map_data.length_m)    # камера и рендереры читают границы отсюда
        size = pygame.display.get_surface().get_size()
        self.camera = Camera(*size)
        self.camera.zoom_min, self.camera.zoom_max = EDIT_ZOOM_MIN, EDIT_ZOOM_MAX
        self.camera.set_zoom(START_ZOOM)
        self.camera.center_on(0.0, 0.0)

        self.terrain = TerrainMap(map_data)
        self.walls = WallManager()
        load_walls(map_data, self.walls)
        ctx = SimpleNamespace(terrain=self.terrain, fleet=_NoFleet(), walls=self.walls,
                              effects=EffectsSystem())
        self.renderer = Renderer(WorldGenerator(map_data.seed), ctx)
        self.renderer.preload(self.camera)

        # --- интерфейс и ввод (первым слоем стоит модальное окно) ---
        self.dialog = Dialog()
        self.bar = EditorBar(self._request_save, self._request_exit)
        self.ui = SidePanel(size, build_editor_panels(), TOOL_MODE[self.tool], start_open=True)
        for mode in TOOL_MODE.values():
            self.ui.set_on_change(mode, self._on_panel_change)
        self.input = InputHandler([self.dialog, self.bar, self.ui])
        self.camera_ctrl = CameraController(self.camera, self.input)
        self.camera_ctrl.set_free(True)      # танка нет: камера всегда свободна
        self._alpha = AlphaLayer()
        self._refresh_stats()

    # ==========================================
    # СОСТОЯНИЕ
    # ==========================================
    def _needs_save(self):
        """Новую карту сохранить можно всегда, сохранённую только если она менялась."""
        return self.dirty or self.map.file is None

    def mark_dirty(self):
        """Инструменты вызывают это после любой правки карты."""
        if not self.dirty:
            self.dirty = True
            self._refresh_stats()

    def _say(self, text, color=C_DIM, seconds=3.0):
        self._toast = [text, color, seconds]

    def _refresh_stats(self):
        m = self.map
        title = m.name + (" *" if self._needs_save() else "")
        values = {STAT_NAME: _short(title), STAT_SIZE: f"{m.width_m}×{m.length_m} м",
                  STAT_ROCKS: str(len(m.rocks)), STAT_WALLS: str(len(self.walls.items)),
                  STAT_FILE: _short(m.file) if m.file else "не сохранена"}
        for mode in TOOL_MODE.values():
            for name, value in values.items():
                self.ui.set_stat(mode, name, value)

    def _sync_map(self):
        """Собирает данные живых объектов обратно в MapData перед записью.
        Камни и ландшафт редактируются прямо в map (этапы 7 и 8), стены живут в WallManager."""
        self.map.walls = collect_walls(self.walls)

    # ==========================================
    # ПАНЕЛЬ И ИНСТРУМЕНТЫ
    # ==========================================
    def _on_panel_change(self, values):
        tool = values.get("tool")
        if tool in TOOL_MODE and tool != self.tool:
            self.tool = tool
            self.ui.show(TOOL_MODE[tool], {"tool": tool})

    def _tool_click(self, button, pos):
        """Клик по миру: ЛКМ (button=1) или чистый ПКМ без перетаскивания (button=3).
        Сюда подключаются инструменты: смотрите self.tool ("wall", "rock", "land")."""
        wx, wy = self.camera.screen_to_world(*pos)

    # ==========================================
    # СОХРАНЕНИЕ И ВЫХОД
    # ==========================================
    def _request_save(self, then=None):
        """then: что сделать после успешной записи (например, выйти)."""
        if self.dialog.active:
            return
        if not self._needs_save() and then is None:
            self._say(texts.EDITOR_NOTHING)
            return
        if self.map.file is None:
            self._ask_name("" if self.map.name == DEFAULT_NAME else self.map.name, then)
        else:
            self._write(self.map.file, then)

    def _ask_name(self, initial, then):
        self.dialog.open(
            texts.EDITOR_SAVE_TITLE, texts.EDITOR_SAVE_ASK,
            [(texts.EDITOR_SAVE, lambda name: self._save_named(name, then), ACTIVE_BUTTON_COLORS, True),
             (texts.EDITOR_CANCEL, None, None, False)],
            text=initial, max_len=MAX_NAME_LEN)

    def _save_named(self, name, then):
        file = self.store.file_for_name(name)
        if self.store.exists(file):
            self.dialog.open(
                texts.EDITOR_OVERWRITE_TITLE, texts.EDITOR_OVERWRITE_ASK.format(name=name),
                [(texts.EDITOR_REPLACE, lambda: self._commit(name, file, then), DELETE_BUTTON_COLORS, False),
                 (texts.EDITOR_OTHER_NAME, lambda: self._ask_name(name, then), None, False),
                 (texts.EDITOR_CANCEL, None, None, False)],
                default=1)
        else:
            self._commit(name, None, then)

    def _commit(self, name, file, then):
        """file=None: новый файл со свободным именем; иначе перезапись этого файла."""
        self.map.name = (name.strip() or DEFAULT_NAME)[:MAX_NAME_LEN]
        self._write(file, then)

    def _write(self, file, then):
        self._sync_map()
        saved = self.store.save(self.map, file)
        if saved is None:
            self._say(texts.EDITOR_SAVE_FAILED, C_BAD, 5.0)
            return
        self.dirty = False
        self._say(texts.EDITOR_SAVED.format(file=saved), C_GOOD)
        self._refresh_stats()
        if then is not None:
            then()

    def _request_exit(self, then=None):
        """then: куда идти после выхода (по умолчанию в список карт; при закрытии окна: завершить приложение)."""
        if self.dialog.active:
            return
        leave = then or self.on_exit
        if not self._needs_save():
            leave()
            return
        self.dialog.open(
            texts.EDITOR_LEAVE_TITLE, texts.EDITOR_LEAVE_ASK.format(name=self.map.name),
            [(texts.EDITOR_SAVE, lambda: self._request_save(then=leave), ACTIVE_BUTTON_COLORS, False),
             (texts.EDITOR_LEAVE_DROP, leave, DELETE_BUTTON_COLORS, False),
             (texts.EDITOR_CANCEL, None, None, False)],
            default=0)

    # ==========================================
    # КАДР
    # ==========================================
    def update(self, dt):
        self.input.process_events()
        if self.input.quit_requested:
            self.input.quit_requested = False
            self._request_exit(self.on_quit)
            return

        size = pygame.display.get_surface().get_size()
        if 0 in size:
            return
        self.camera_ctrl.update_view(dt, size)
        self.ui.update(size)
        self.bar.save_button.enabled = self._needs_save()

        if self.dialog.active:
            self.input.pop_world_clicks()            # на всякий случай: под окном мир не живёт
        else:
            self._handle_hotkeys()
            self._pan_keys(dt)
            self._handle_clicks()

        if self._toast is not None:
            self._toast[2] -= dt
            if self._toast[2] <= 0.0:
                self._toast = None

    def _handle_hotkeys(self):
        inp = self.input
        if inp.was_pressed(Action.SAVE) and inp.lctrl:
            self._request_save()
        if inp.was_pressed(Action.CANCEL):
            self._request_exit()

    def _pan_keys(self, dt):
        """WASD и стрелки двигают камеру (с зажатым Ctrl не двигают: это Ctrl+S)."""
        inp = self.input
        if inp.lctrl:
            return
        held = inp.held
        dx = float(Action.RIGHT in held) - float(Action.LEFT in held)
        dy = float(Action.BACKWARD in held) - float(Action.FORWARD in held)
        if dx == 0.0 and dy == 0.0:
            return
        k = PAN_SPEED_PX * (PAN_FAST_K if inp.shift else 1.0) * dt / self.camera.zoom
        k /= math.hypot(dx, dy)
        self.camera.move_by(dx * k, dy * k)

    def _handle_clicks(self):
        """ПКМ при свободной камере может оказаться перетаскиванием, поэтому «чистый» клик приходит позже."""
        for button, pos in self.input.pop_world_clicks():
            if button == 3:
                self.camera_ctrl.begin_pan(pos)
            else:
                self._tool_click(button, pos)
        tap = self.camera_ctrl.update_pan()
        if tap is not None:
            self._tool_click(3, tap)

    # ==========================================
    # РИСОВАНИЕ
    # ==========================================
    def draw(self, screen):
        self.renderer.draw(screen, self.camera)
        self._draw_start_zone(screen)
        mouse = self.input.mouse_pos
        self.ui.draw(screen, mouse)
        self.bar.draw(screen, mouse)
        self._draw_status(screen)
        self.dialog.draw(screen, mouse)

    @staticmethod
    def _label(screen, text, size, color, **anchor):
        label = get_text(text, size, color)
        rect = label.get_rect(**anchor)
        screen.blit(get_text(text, size, (0, 0, 0)), rect.move(1, 1))
        screen.blit(label, rect)

    def _draw_start_zone(self, screen):
        """Круг вокруг центра карты: здесь будет стоять игрок, поэтому камней, стен и глубокой воды тут быть не должно."""
        cx, cy = self.camera.world_to_screen(0.0, 0.0)
        r = round(START_CLEAR_M * PX_PER_M * self.camera.zoom)
        if r < 3:
            return
        cx, cy = round(cx), round(cy)
        rect = pygame.Rect(cx - r - 3, cy - r - 3, 2 * r + 6, 2 * r + 6).clip(screen.get_rect())
        if rect.w <= 0 or rect.h <= 0:
            return
        layer = self._alpha.begin(rect.size)
        center = (cx - rect.x, cy - rect.y)
        pygame.draw.circle(layer, (*START_COLOR, 40), center, r)
        pygame.draw.circle(layer, (*START_COLOR, 210), center, r, 2)
        screen.blit(layer, rect.topleft)
        if r >= 24:
            self._label(screen, texts.EDITOR_START, FONT_SIZE_LABEL, START_COLOR, midtop=(cx, cy - r - 22))

    def _draw_status(self, screen):
        w, h = screen.get_size()
        free_w = self.ui.panel_rect.left if self.ui.is_open else w
        title = self.map.name + (" *" if self._needs_save() else "")
        self._label(screen, title, FONT_SIZE_HEADER, (235, 235, 235), midtop=(free_w // 2, 10))

        if self.input.pointer_in_world:
            wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
            coords = f"X: {wx / PX_PER_M:.0f} м   Y: {wy / PX_PER_M:.0f} м"
        else:
            coords = "X: —   Y: —"
        info = f"{coords}   Масштаб ×{self.camera.zoom:.2f}"
        self._label(screen, info, FONT_SIZE_LABEL, (210, 214, 220), bottomleft=(10, h - 30))
        self._label(screen, texts.EDITOR_HINT, FONT_SIZE_LABEL, C_DIM, bottomleft=(10, h - 8))

        if self._toast is not None:
            text, color, _ = self._toast
            self._label(screen, text, FONT_SIZE_HEADER, color, midtop=(free_w // 2, 42))