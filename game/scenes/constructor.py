"""game/scenes/constructor.py — конструктор: настройка техники (ОБТ или ПТ-САУ) без езды, стрельбы и стен."""
import os
import traceback

import pygame

from engine import PX_PER_M, VehicleCommand, VehicleKind, clamp, get_text, FONT_SIZE_LABEL
from inputs import InputHandler, Action
from ui import SidePanel, Button, ACTIVE_BUTTON_COLORS
from ui.theme import PANEL_WIDTH
from vehicles import (
    GUN_TUNE_PARAMS, damage_range, pen_range, remap, VEHICLE_TYPES, RENDERERS,
    make_vehicle, caliber_range_for, NOSE_FLAT, NOSE_PIKE, NOSE_MIN_FRONT_MM,
    estimate_mass, sloped_nose_for_mass
)
from world import Camera
from ..panels import PanelMode, PANEL_OF, build_tank_panel, build_td_panel
from .base import Scene
from tools.tank_snapshot import save_snapshot

BG = (36, 40, 46)
PREVIEW_ZOOM_STEPS = 8          # на сколько ступеней приблизить камеру относительно стандартной
DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step

KIND_BTN_W, KIND_BTN_H = 100, 36    # кнопки выбора типа техники (левый нижний угол)
KIND_GAP = 8
KIND_MARGIN = 10

class ConstructorScene(Scene):
    def __init__(self, session, on_play, on_menu, on_quit):
        self.session = session
        self.on_play = on_play
        self.on_menu = on_menu
        self.on_quit = on_quit

        size = pygame.display.get_surface().get_size()

        # --- камера: техника по центру свободной (левой) части экрана ---
        self.camera = Camera(*size)
        self.camera.zoom_by(PREVIEW_ZOOM_STEPS)
        self.camera.center_on(PANEL_WIDTH / 2 / self.camera.zoom, 0.0)

        # --- интерфейс: панель каждого типа техники, показана панель выбранного ---
        kind = session.kind
        self._mode = PANEL_OF[kind]
        self._profile = VEHICLE_TYPES[kind].gun_profile
        self.ui = SidePanel(size, {PanelMode.TANK: build_tank_panel(), PanelMode.TD: build_td_panel()},
                            self._mode, start_open=True)

        # коридоры урона и пробития зависят от калибра и профиля: СНАЧАЛА границы, ПОТОМ значения
        values = session.values[kind]
        self._cal = self._want_cal = values["gun_caliber_mm"]
        values = self._apply_class_rules(values)
        self._cal = values["gun_caliber_mm"]
        self._ranges = (damage_range(self._cal, self._profile), pen_range(self._cal, self._profile))
        self.ui.set_range(self._mode, "gun_damage", *self._ranges[0])
        self.ui.set_range(self._mode, "gun_penetration", *self._ranges[1])
        self.ui.set_values(self._mode, values)
        values = session.values[kind] = self._apply_nose_rules(values)
        self._sync_tune_t(values)
        for mode in (PanelMode.TANK, PanelMode.TD):
            self.ui.set_on_change(mode, self._on_change)
        self.input = InputHandler([self.ui])

        # --- машина-превью ---
        self.vehicle = make_vehicle(kind, session.spec())
        self.renderer = self._make_renderer(kind)

        # --- кнопки ---
        self.play_button = Button((10, 10, 150, 36), "В бой")
        self.menu_button = Button((10, 52, 150, 36), "В меню")
        self.mbt_button = Button((KIND_MARGIN, 0, KIND_BTN_W, KIND_BTN_H), VEHICLE_TYPES[VehicleKind.MBT].label)
        self.td_button = Button((KIND_MARGIN + KIND_BTN_W + KIND_GAP, 0, KIND_BTN_W, KIND_BTN_H),
                                VEHICLE_TYPES[VehicleKind.TD].label)
        self._place_kind_buttons(size)

        self._show_stats()
        self._toast = None                 # всплывающее сообщение: [текст, цвет, секунд осталось]

    # ---------- тип техники ----------
    def _make_renderer(self, kind):
        renderer = RENDERERS[VEHICLE_TYPES[kind].renderer_key]()
        renderer.set_zoom(PX_PER_M * self.camera.zoom)
        return renderer

    def _place_kind_buttons(self, size):
        y = size[1] - KIND_MARGIN - KIND_BTN_H
        self.mbt_button.rect.y = y
        self.td_button.rect.y = y

    def _set_kind(self, kind):
        """Переключение ОБТ / ПТ-САУ. Порядок важен: сначала границы ползунков, потом значения,
        иначе set_value обрежет их по старому диапазону."""
        if kind is self.session.kind:
            return
        self.session.kind = kind
        self._mode = PANEL_OF[kind]
        self._profile = VEHICLE_TYPES[kind].gun_profile
        values = self.session.values[kind]
        self._cal = self._want_cal = values["gun_caliber_mm"]
        values = self._apply_class_rules(values)
        self._cal = values["gun_caliber_mm"]
        self._ranges = (damage_range(self._cal, self._profile), pen_range(self._cal, self._profile))
        self.ui.set_range(self._mode, "gun_damage", *self._ranges[0])
        self.ui.set_range(self._mode, "gun_penetration", *self._ranges[1])
        self.ui.show(self._mode, values)
        values = self.session.values[kind] = self._apply_nose_rules(values)
        self._sync_tune_t(values)
        self.vehicle = make_vehicle(kind, self.session.spec())
        self.renderer = self._make_renderer(kind)
        self._show_stats()

    # ---------- конструктор ----------
    def _on_change(self, values):
        values = self._apply_class_rules(values)       # сначала подрезаем калибр по классу
        cal = values["gun_caliber_mm"]
        if cal != self._cal:
            values = self._change_caliber(cal, values)
        else:
            self._sync_tune_t(values)
        values = self._apply_nose_rules(values)
        self.session.values[self.session.kind] = dict(values)
        self.vehicle.set_spec(self.session.spec())
        self._show_stats()

    def _sync_tune_t(self, values):
        """Запомнить относительное положение (0..1) ползунков урона и пробития внутри текущих коридоров."""
        d_rng, p_rng = self._ranges
        self._tune_t = (remap(values["gun_damage"], d_rng, (0.0, 1.0)),
                        remap(values["gun_penetration"], p_rng, (0.0, 1.0)))

    def _apply_nose_rules(self, values):
        """Правило носа."""
        values = dict(values)
        allowed = values["front_armor_mm"] > NOSE_MIN_FRONT_MM

        if self.session.kind is VehicleKind.MBT:
            mass = estimate_mass(values["gun_caliber_mm"], values["front_armor_mm"],
                                 values["side_armor_mm"], values["rear_armor_mm"],
                                 values["engine_power_hp"], values.get("front_screen_mm", 0.0))
            sloped = sloped_nose_for_mass(mass)
            self.ui.set_choice_options(self._mode, "front_nose",
                                       [(NOSE_FLAT, NOSE_RU[NOSE_FLAT].capitalize()),
                                        (sloped, NOSE_RU[sloped].capitalize())])
            if values["front_nose"] != NOSE_FLAT:
                values["front_nose"] = sloped            # масса перешагнула 90 т: щучий <-> клин

        if not allowed:
            values["front_nose"] = NOSE_FLAT
        self.ui.set_enabled(self._mode, "front_nose", allowed)
        self.ui.set_values(self._mode, values)
        return values

    def _apply_class_rules(self, values):
        """Калибр зависит от тяжести корпуса (броня и мощность). Для ПТ-САУ правило не действует.
        _want_cal: калибр, который игрок выбрал сам; границы могут его временно срезать,
        а при возврате диапазона он восстанавливается."""
        if self.session.kind is not VehicleKind.MBT:
            return values
        values = dict(values)
        if values["gun_caliber_mm"] != self._cal:          # калибр двинул сам игрок
            self._want_cal = values["gun_caliber_mm"]
        lo, hi = caliber_range_for(values["front_armor_mm"], values["side_armor_mm"],
                                   values["rear_armor_mm"], values["engine_power_hp"])
        values["gun_caliber_mm"] = clamp(self._want_cal, lo, hi)
        self.ui.set_range(self._mode, "gun_caliber_mm", lo, hi)
        self.ui.set_values(self._mode, {"gun_caliber_mm": values["gun_caliber_mm"]})
        return values

    def _change_caliber(self, cal, values):
        """Калибр изменился: новые границы урона и пробития (с учётом профиля), значения по сохранённому уровню."""
        self._cal = cal
        d_rng, p_rng = damage_range(cal, self._profile), pen_range(cal, self._profile)
        self._ranges = (d_rng, p_rng)
        t_d, t_p = self._tune_t

        values = dict(values)
        values["gun_damage"] = remap(t_d, (0.0, 1.0), d_rng, DMG_STEP)
        values["gun_penetration"] = remap(t_p, (0.0, 1.0), p_rng, PEN_STEP)

        self.ui.set_range(self._mode, "gun_damage", *d_rng)
        self.ui.set_range(self._mode, "gun_penetration", *p_rng)
        self.ui.set_values(self._mode, values)
        return values

    def _show_stats(self):
        spec = self.vehicle.spec
        for name, text in {**spec.main_stats(), **spec.internal_stats()}.items():
            self.ui.set_stat(self._mode, name, text)

    # ---------- снимок для разбора внешнего вида ----------
    def _save_snapshot(self):
        """LCtrl + LShift + V: текстовый снимок всего, что нарисовано для текущей техники."""
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
                if self.play_button.collidepoint(pos):
                    self.on_play()
                    return
                if self.menu_button.collidepoint(pos):
                    self.on_menu()
                    return
                if self.mbt_button.collidepoint(pos):
                    self._set_kind(VehicleKind.MBT)
                elif self.td_button.collidepoint(pos):
                    self._set_kind(VehicleKind.TD)
        if self.input.was_pressed(Action.CANCEL):
            self.on_menu()
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
        self.play_button.draw(screen, mouse, colors=ACTIVE_BUTTON_COLORS)
        self.menu_button.draw(screen, mouse)
        is_mbt = self.session.kind is VehicleKind.MBT
        self.mbt_button.draw(screen, mouse, colors=ACTIVE_BUTTON_COLORS if is_mbt else None)
        self.td_button.draw(screen, mouse, colors=None if is_mbt else ACTIVE_BUTTON_COLORS)