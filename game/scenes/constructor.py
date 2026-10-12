"""game/scenes/constructor.py — конструктор: настройка танка без езды, стрельбы и стен."""
import pygame

from engine import PX_PER_M, VehicleCommand
from inputs import InputHandler, Action
from ui import SidePanel, Button, ACTIVE_BUTTON_COLORS
from ui.theme import PANEL_WIDTH
from vehicles import Tank, TankRenderer, GUN_TUNE_PARAMS, damage_range, pen_range, remap
from world import Camera
from ..panels import PanelMode, build_tank_panel
from .base import Scene

BG = (36, 40, 46)
PREVIEW_ZOOM_STEPS = 8          # на сколько ступеней приблизить камеру относительно стандартной
DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step

class ConstructorScene(Scene):
    def __init__(self, session, on_play, on_menu, on_quit):
        self.session = session
        self.on_play = on_play           # начать игру
        self.on_menu = on_menu           # вернуться в меню
        self.on_quit = on_quit

        size = pygame.display.get_surface().get_size()

        # --- камера: танк по центру свободной (левой) части экрана ---
        self.camera = Camera(*size)
        self.camera.zoom_by(PREVIEW_ZOOM_STEPS)
        self.camera.center_on(PANEL_WIDTH / 2 / self.camera.zoom, 0.0)

        # --- интерфейс: одна панель, всегда открыта, без красной кнопки ---
        self.ui = SidePanel(size, {PanelMode.TANK: build_tank_panel()}, PanelMode.TANK,
                            start_open=True)

        # коридоры урона и пробития зависят от калибра: СНАЧАЛА границы, ПОТОМ значения
        self._cal = session.tank_values["gun_caliber_mm"]
        self._ranges = (damage_range(self._cal), pen_range(self._cal))
        self.ui.set_range(PanelMode.TANK, "gun_damage", *self._ranges[0])
        self.ui.set_range(PanelMode.TANK, "gun_penetration", *self._ranges[1])
        self.ui.set_values(PanelMode.TANK, session.tank_values)   # вернуть прошлые настройки
        self._sync_tune_t(session.tank_values)
        self.ui.set_on_change(PanelMode.TANK, self._on_change)
        self.input = InputHandler([self.ui])

        # --- танк-превью ---
        self.tank = Tank(0.0, 0.0, spec=session.tank_spec())
        self.renderer = TankRenderer()
        self.renderer.set_zoom(PX_PER_M * self.camera.zoom)

        # --- кнопки ---
        self.play_button = Button((10, 10, 150, 36), "В бой")
        self.menu_button = Button((10, 52, 150, 36), "В меню")

        self._show_stats()

    # ---------- конструктор ----------
    def _on_change(self, values):
        """Ползунок сдвинут: при смене калибра пересчитываем коридоры, затем запоминаем значения
        в сессии и пересчитываем танк."""
        cal = values["gun_caliber_mm"]
        if cal != self._cal:
            values = self._change_caliber(cal, values)
        else:
            self._sync_tune_t(values)               # игрок двигал урон/пробитие сам: запоминаем уровень
        self.session.tank_values = dict(values)
        self.tank.set_spec(self.session.tank_spec())
        self._show_stats()

    def _sync_tune_t(self, values):
        """Запомнить относительное положение (0..1) ползунков урона и пробития внутри текущих коридоров."""
        d_rng, p_rng = self._ranges
        self._tune_t = (remap(values["gun_damage"], d_rng, (0.0, 1.0)),
                        remap(values["gun_penetration"], p_rng, (0.0, 1.0)))

    def _change_caliber(self, cal, values):
        """Калибр изменился: новые границы урона и пробития, значения по сохранённому уровню.
        Возвращает обновлённый словарь значений."""
        self._cal = cal
        d_rng, p_rng = damage_range(cal), pen_range(cal)
        self._ranges = (d_rng, p_rng)
        t_d, t_p = self._tune_t

        values = dict(values)
        values["gun_damage"] = remap(t_d, (0.0, 1.0), d_rng, DMG_STEP)
        values["gun_penetration"] = remap(t_p, (0.0, 1.0), p_rng, PEN_STEP)

        self.ui.set_range(PanelMode.TANK, "gun_damage", *d_rng)          # сначала границы
        self.ui.set_range(PanelMode.TANK, "gun_penetration", *p_rng)
        self.ui.set_values(PanelMode.TANK, values)                      # потом значения
        return values

    def _show_stats(self):
        spec = self.tank.spec
        for name, text in {**spec.main_stats(), **spec.internal_stats()}.items():
            self.ui.set_stat(PanelMode.TANK, name, text)

    # ---------- кадр ----------
    def update(self, dt):
        self.input.process_events()
        if self.input.quit_requested:
            self.on_quit()
            return

        size = pygame.display.get_surface().get_size()
        if 0 in size:
            return
        self.camera.resize(*size)
        self.ui.update(size)
        self.input.pop_zoom_steps()          # зум здесь не нужен: выбрасываем накопленное

        for button, pos in self.input.pop_world_clicks():   # клики, которые не забрала панель
            if button == 1:
                if self.play_button.collidepoint(pos):
                    self.on_play()
                    return
                if self.menu_button.collidepoint(pos):
                    self.on_menu()
                    return
        if self.input.was_pressed(Action.CANCEL):
            self.on_menu()
            return

        # башня превью следит за мышью; ездить и стрелять нельзя
        aim = None
        if self.input.pointer_in_world:
            aim = self.camera.screen_to_world(*self.input.mouse_pos)
        self.tank.update(VehicleCommand(aim_point=aim), dt)

    def draw(self, screen):
        screen.fill(BG)
        self.renderer.draw(screen, self.camera, self.tank)
        mouse = self.input.mouse_pos
        self.ui.draw(screen, mouse)
        self.play_button.draw(screen, mouse, colors=ACTIVE_BUTTON_COLORS)
        self.menu_button.draw(screen, mouse)