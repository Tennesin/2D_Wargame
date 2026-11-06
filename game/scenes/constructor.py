"""game/scenes/constructor.py — конструктор: настройка техники (ОБТ или ПТ-САУ) без езды, стрельбы и стен."""
import os
import traceback
import pygame

from engine import PX_PER_M, VehicleCommand, clamp
from inputs import InputHandler, Action
from ui import SidePanel, Button, ACTIVE_BUTTON_COLORS
from ui.theme import PANEL_WIDTH
from vehicles import (
    GUN_TUNE_PARAMS, damage_range, pen_range, remap, VEHICLE_TYPES, RENDERERS,
    make_vehicle, NOSE_FLAT, NOSE_MIN_FRONT_MM, NOSE_RU, SPECIAL_HEAT, HESH_MIN_CAL_MM,
    length_range
)
from world import Camera
from ..content import texts
from ..content.panels import build_vehicle_panels
from .base import Scene
try:
    from tools.tank_snapshot import save_snapshot
except ImportError:
    save_snapshot = None

BG = (36, 40, 46)
PREVIEW_ZOOM_STEPS = 8          # на сколько ступеней приблизить камеру относительно стандартной
DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step
LEN_STEP = GUN_TUNE_PARAMS["gun_length_cal"].step

KIND_BTN_W, KIND_BTN_H = 100, 36    # кнопки выбора типа техники (левый нижний угол)
KIND_GAP = 8
KIND_MARGIN = 10

class ConstructorScene(Scene):
    BACKGROUND = False
    def __init__(self, session, on_back, on_quit):
        self.session = session
        self.on_back = on_back
        self.on_quit = on_quit

        size = pygame.display.get_surface().get_size()

        # --- камера: техника по центру свободной (левой) части экрана ---
        self.camera = Camera(*size)
        self.camera.zoom_by(PREVIEW_ZOOM_STEPS)
        self.camera.center_on(PANEL_WIDTH / 2 / self.camera.zoom, 0.0)

        # --- интерфейс: по панели на каждый играбельный тип техники ---
        kind = session.kind
        panels = build_vehicle_panels()
        self.ui = SidePanel(size, panels, kind, start_open=True)
        for k in panels:
            self.ui.set_on_change(k, self._on_change)
        self.input = InputHandler([self.ui])

        # --- кнопки ---
        self.back_button = Button((10, 10, 150, 36), texts.BACK)
        self.kind_buttons = [(k, Button((0, 0, KIND_BTN_W, KIND_BTN_H), VEHICLE_TYPES[k].label))
                             for k in panels]
        self._toast = None  # всплывающее сообщение: [текст, цвет, секунд осталось]

        # --- выбранная техника: границы ползунков, значения, превью, характеристики ---
        self._load_kind(kind)

    # ---------- тип техники ----------
    def _make_renderer(self, kind):
        renderer = RENDERERS[kind]()
        renderer.set_zoom(PX_PER_M * self.camera.zoom)
        return renderer

    def _place_kind_buttons(self, size):
        y = size[1] - KIND_MARGIN - KIND_BTN_H
        x = KIND_MARGIN
        for _, btn in self.kind_buttons:
            btn.rect.topleft = (x, y)
            x += KIND_BTN_W + KIND_GAP

    def _set_kind(self, kind):
        """Переключение ОБТ / ПТ-САУ кнопками."""
        if kind is self.session.kind:
            return
        self._load_kind(kind)

    def _load_kind(self, kind):
        """Единая загрузка типа техники."""
        self.session.kind = kind
        self._vtype = VEHICLE_TYPES[kind]
        self._mode = kind                      # режим панели = вид техники
        self._profile = self._vtype.gun_profile

        values = self.session.values[kind]
        self._cal = self._want_cal = values["gun_caliber_mm"]
        values = self._apply_class_rules(values)
        self._cal = values["gun_caliber_mm"]
        self._len = clamp(values["gun_length_cal"], *length_range(self._cal))
        values = self._apply_gun_rules(values)         # коридоры и положения ползунков под загруженные значения
        self.ui.show(self._mode, values)

        values = self.session.values[kind] = self._apply_ammo_rules(self._apply_nose_rules(values))
        self.vehicle = make_vehicle(kind, self.session.spec())
        self.renderer = self._make_renderer(kind)
        self._show_stats()

    # ---------- конструктор ----------
    def _on_change(self, values):
        values = self._apply_class_rules(values)
        values = self._apply_gun_rules(values)
        values = self._apply_ammo_rules(self._apply_nose_rules(values))
        self.session.values[self.session.kind] = dict(values)
        self.vehicle.set_spec(self.session.spec())
        self._show_stats()

    def _apply_nose_rules(self, values):
        """Скошенный нос доступен при лобовой броне больше порога."""
        hook = self._vtype.sloped_nose
        if hook is None:
            return values
        values = dict(values)
        sloped = hook(values)
        self.ui.set_choice_options(self._mode, "front_nose",
                                   [(NOSE_FLAT, NOSE_RU[NOSE_FLAT].capitalize()),
                                    (sloped, NOSE_RU[sloped].capitalize())])
        if values["front_nose"] != NOSE_FLAT:
            values["front_nose"] = sloped
        allowed = values["front_armor_mm"] > NOSE_MIN_FRONT_MM
        if not allowed:
            values["front_nose"] = NOSE_FLAT
        self.ui.set_enabled(self._mode, "front_nose", allowed)
        self.ui.set_values(self._mode, values)
        return values

    def _apply_ammo_rules(self, values):
        """HESH доступен только от HESH_MIN_CAL_MM: ниже порога переключатель заблокирован и стоит КС."""
        values = dict(values)
        allowed = values["gun_caliber_mm"] >= HESH_MIN_CAL_MM
        if not allowed:
            values["special_ammo"] = SPECIAL_HEAT
        self.ui.set_enabled(self._mode, "special_ammo", allowed)
        self.ui.set_values(self._mode, values)
        return values

    def _apply_class_rules(self, values):
        """Допустимый калибр задаёт хук типа техники."""
        hook = self._vtype.caliber_limits
        if hook is None:
            return values
        values = dict(values)
        if values["gun_caliber_mm"] != self._cal:          # калибр двинул сам игрок
            self._want_cal = values["gun_caliber_mm"]
        lo, hi = hook(values)
        values["gun_caliber_mm"] = clamp(self._want_cal, lo, hi)
        self.ui.set_range(self._mode, "gun_caliber_mm", lo, hi)
        self.ui.set_values(self._mode, {"gun_caliber_mm": values["gun_caliber_mm"]})
        return values

    def _apply_gun_rules(self, values):
        """Коридоры орудия: калибр -> длина -> урон, пробитие."""
        values = dict(values)
        cal = values["gun_caliber_mm"]
        cal_changed = cal != self._cal

        len_rng = length_range(cal)
        if cal_changed:
            length = remap(self._len_t, (0.0, 1.0), len_rng, LEN_STEP)
        else:
            length = clamp(values["gun_length_cal"], *len_rng)
        derived = cal_changed or length != self._len

        d_rng = damage_range(cal, self._profile)
        p_rng = pen_range(cal, self._profile, length)
        if derived:
            dmg = remap(self._tune_t[0], (0.0, 1.0), d_rng, DMG_STEP)
            pen = remap(self._tune_t[1], (0.0, 1.0), p_rng, PEN_STEP)
        else:
            dmg = clamp(values["gun_damage"], *d_rng)
            pen = clamp(values["gun_penetration"], *p_rng)
            self._tune_t = (remap(dmg, d_rng, (0.0, 1.0)), remap(pen, p_rng, (0.0, 1.0)))
        if not cal_changed:
            self._len_t = remap(length, len_rng, (0.0, 1.0))

        self._cal, self._len = cal, length
        values.update(gun_length_cal=length, gun_damage=dmg, gun_penetration=pen)

        m = self._mode
        self.ui.set_range(m, "gun_length_cal", *len_rng)
        self.ui.set_range(m, "gun_damage", *d_rng)
        self.ui.set_range(m, "gun_penetration", *p_rng)
        self.ui.set_values(m, values)
        return values

    def _show_stats(self):
        spec = self.vehicle.spec
        for name, text in {**spec.main_stats(), **spec.internal_stats()}.items():
            self.ui.set_stat(self._mode, name, text)

    # ---------- снимок для разбора внешнего вида ----------
    def _save_snapshot(self):
        """LCtrl + LShift + V: текстовый снимок всего, что нарисовано для текущей техники."""
        if save_snapshot is None:
            self._toast = ["Снимки недоступны в этой сборке", (240, 200, 70), 3.0]
            return
        try:
            path = save_snapshot(self.vehicle, self.renderer)
        except Exception:
            traceback.print_exc()
            self._toast = ["Снимок НЕ сохранён: подробности в консоли", (240, 80, 70), 5.0]
            return
        print(f"Снимок техники: {path}")
        self._toast = [f"Снимок сохранён: {os.path.basename(path)}", (110, 220, 110), 4.0]

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
        self._place_kind_buttons(size)
        self.input.pop_zoom_steps()

        for button, pos in self.input.pop_world_clicks():
            if button == 1:
                if self.back_button.collidepoint(pos):
                    self.on_back()
                    return
                for kind, btn in self.kind_buttons:
                    if btn.collidepoint(pos):
                        self._set_kind(kind)
                        break
        if self.input.was_pressed(Action.CANCEL):
            self.on_back()
            return
        if (self.input.was_pressed(Action.SNAPSHOT)
                and self.input.lctrl and self.input.lshift):
            self._save_snapshot()
        if self._toast is not None:
            self._toast[2] -= dt
            if self._toast[2] <= 0.0:
                self._toast = None

        # орудие превью следит за мышью (у ПТ-САУ в пределах УГН); ездить и стрелять нельзя
        aim = None
        if self.input.pointer_in_world:
            aim = self.camera.screen_to_world(*self.input.mouse_pos)
        self.vehicle.update(VehicleCommand(aim_point=aim), dt)

    def draw(self, screen):
        screen.fill(BG)
        self.renderer.draw(screen, self.camera, self.vehicle)
        mouse = self.input.mouse_pos
        self.ui.draw(screen, mouse)
        self.back_button.draw(screen, mouse)
        for kind, btn in self.kind_buttons:
            btn.draw(screen, mouse, colors=ACTIVE_BUTTON_COLORS if kind is self.session.kind else None)