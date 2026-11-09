"""game/scenes/constructor.py — конструктор: настройка техники (ОБТ или ПТ-САУ) без езды, стрельбы и стен."""
import math
import os
import traceback
import pygame

from engine import PX_PER_M, VehicleCommand, AlphaLayer, clamp
from inputs import InputHandler, Action
from ui import SidePanel, Button, ACTIVE_BUTTON_COLORS, ActionButton, PartPalette
from ui.theme import PANEL_WIDTH
from vehicles import (
    GUN_TUNE_PARAMS, damage_range, pen_range, remap, VEHICLE_TYPES, RENDERERS,
    make_vehicle, NOSE_FLAT, NOSE_MIN_FRONT_MM, NOSE_RU, SPECIAL_HEAT,
    HESH_MIN_CAL_MM, length_range
)
from world import Camera
from ..content import texts
from ..content.panels import build_vehicle_panels
from .base import Scene
from vehicles.parts import PART_TYPES, center
from ..content.panels.vehicle import (
    PARTS_SURFACE_RU, PARTS_BTN_MIRROR, PARTS_BTN_DELETE, PARTS_BTN_UNDO, PARTS_BTN_REDO,
    PARTS_STAT_SEL, PARTS_STAT_ALL,
)
from ..editor import PartsTool, PartsOverlay, make_part_icons
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
HIGHLIGHT = (255, 220, 80)       # подсветка выбранного модуля в превью

PALETTE_X, PALETTE_W = 10, 200       # левая колонка палитры (вкладка «Детали»)
PALETTE_TOP = 56                     # под кнопкой «Назад»
PALETTE_BOTTOM = 56                  # над кнопками типа техники
PARTS_ZOOM_START = 17                # ступень зума при входе на вкладку «Детали»
PARTS_ZOOM_MIN, PARTS_ZOOM_MAX = 13, 20

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

        # --- интерфейс: панели «Сборка» (и «Дизайн» у ОБТ) на каждый играбельный тип ---
        kind = session.kind
        panels = build_vehicle_panels()
        self.ui = SidePanel(size, panels, (kind, "build"), start_open=True)
        for mode in panels:
            self.ui.set_on_change(mode, self._on_change)
        self.palette = PartPalette()
        self.palette.on_pick = self._on_palette_pick
        self.input = InputHandler([self.ui, self.palette])
        self._icons = make_part_icons()
        self._zoom_saved = None
        self.parts = PartsTool(self.camera, self.input,
                               on_design=self._on_parts_design, on_state=self._refresh_parts_panel)
        self.parts_overlay = PartsOverlay()
        self._parts_buttons = {}
        self._bind_parts_buttons(panels)

        # --- кнопки ---
        self.back_button = Button((10, 10, 150, 36), texts.BACK)
        kinds = [k for k, vt in VEHICLE_TYPES.items() if vt.playable]
        self.kind_buttons = [(k, Button((0, 0, KIND_BTN_W, KIND_BTN_H), VEHICLE_TYPES[k].label))
                             for k in kinds]
        self._toast = None  # всплывающее сообщение: [текст, цвет, секунд осталось]
        self._alpha = AlphaLayer()
        self.tab = "build"

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
        if self.tab == "parts":
            self._leave_parts_view()
        self.session.kind = kind
        self._vtype = VEHICLE_TYPES[kind]
        self._mode = (kind, "build")
        self._design_mode = (kind, "design")
        self._parts_mode = (kind, "parts")
        self._has_design = self._design_mode in self.ui.panels
        self._has_parts = self._parts_mode in self.ui.panels
        self.tab = "build"
        self._profile = self._vtype.gun_profile

        values = self.session.values[kind]
        self._cal = self._want_cal = values["gun_caliber_mm"]
        values = self._apply_class_rules(values)
        self._cal = values["gun_caliber_mm"]
        self._len = clamp(values["gun_length_cal"], *length_range(self._cal))
        values = self._apply_gun_rules(values)
        values = self._apply_ammo_rules(self._apply_nose_rules(values))
        values = self._apply_design_rules(values)

        self.session.values[kind] = values
        self.ui.show(self._mode, {**values, "tab": "build"})
        self.vehicle = make_vehicle(kind, self.session.spec())
        self.renderer = self._make_renderer(kind)
        self._bind_parts(kind)
        self._apply_camera_offset()
        self._show_stats()

    # ---------- конструктор ----------
    def _on_change(self, values):
        tab = values.get("tab")
        if tab is not None and tab != self.tab:
            self._set_tab(tab)
            return
        if self.tab == "parts":
            self._on_parts_panel(values)
            return
        kind = self.session.kind
        merged = {**self.session.values[kind], **{k: v for k, v in values.items() if k != "tab"}}
        if self.tab == "build":
            merged = self._apply_class_rules(merged)
            merged = self._apply_gun_rules(merged)
        merged = self._apply_ammo_rules(self._apply_nose_rules(merged))
        merged = self._apply_design_rules(merged)
        self.session.values[kind] = dict(merged)
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

    def _apply_design_rules(self, values):
        """Границы ползунков дизайна задаёт хук типа техники (design_rules)."""
        if not self._has_design:
            return values
        values = dict(values)
        for key, (lo, hi) in self._vtype.design_rules(values).items():
            values[key] = clamp(values[key], lo, hi)
            self.ui.set_range(self._design_mode, key, lo, hi)
        self.ui.set_values(self._design_mode, {k: values[k] for k in self._vtype.design_defaults})
        return values

    def _set_tab(self, tab):
        """Переключение «Сборка» / «Дизайн» / «Детали»."""
        if tab == self.tab:
            return
        if (tab == "design" and not self._has_design) or (tab == "parts" and not self._has_parts):
            return
        if self.tab == "parts":
            self._leave_parts_view()
        self.tab = tab
        mode = {"build": self._mode, "design": self._design_mode, "parts": self._parts_mode}[tab]
        self.ui.show(mode, {**self.session.values[self.session.kind], "tab": tab})
        if tab == "parts":
            self._enter_parts_view()
        self._apply_camera_offset()

    # ---------- вкладка «Детали» ----------
    def _bind_parts_buttons(self, panels):
        """Кнопки панели «Детали» находятся по подписи и получают действия инструмента."""
        actions = {PARTS_BTN_MIRROR: self.parts.mirror_selected, PARTS_BTN_DELETE: self.parts.delete_selected,
                   PARTS_BTN_UNDO: self.parts.undo_step, PARTS_BTN_REDO: self.parts.redo_step}
        self._parts_buttons = {}
        for mode, panel in panels.items():
            if mode[1] != "parts":
                continue
            for item in panel.items:
                if isinstance(item, ActionButton) and item.button.label in actions:
                    item.callback = actions[item.button.label]
                    self._parts_buttons.setdefault(mode, {})[item.button.label] = item

    def _bind_parts(self, kind):
        """Инструмент получает новую технику; список поверхностей зависит от рендерера."""
        if not self._has_parts:
            return
        renderer_cls = RENDERERS[kind]
        surfaces = ["hull"] + (["turret"] if renderer_cls.HAS_TURRET_SPRITE else [])
        self.parts.bind(self.vehicle, renderer_cls.DESIGN_KIND,
                        self.session.values[kind].get("parts_design"), surfaces)
        self.ui.set_choice_options(self._parts_mode, "parts_surface",
                                   [(s, PARTS_SURFACE_RU[s]) for s in surfaces])
        self._sync_palette()
        self._refresh_parts_panel()

    def _sync_palette(self):
        surface = self.parts.surface
        self.palette.set_items([(key, pt.label, self._icons.get(key))
                                for key, pt in PART_TYPES.items() if surface in pt.surfaces])

    def _on_palette_pick(self, key):
        self.parts.arm(key)

    def _enter_parts_view(self):
        self._zoom_saved = self.camera.zoom_level
        self.camera.zoom_by(PARTS_ZOOM_START - self.camera.zoom_level)
        self.renderer.set_zoom(PX_PER_M * self.camera.zoom)
        self.vehicle.turret_rel_angle = 0.0                  # башня стоит прямо: детали рисуются без поворота
        self.vehicle.turret_rate = 0.0
        self.palette.visible = True
        self.parts.set_active(True)
        self._refresh_parts_panel()

    def _leave_parts_view(self):
        self.parts.set_active(False)
        self.palette.visible = False
        if self._zoom_saved is not None:
            self.camera.zoom_by(self._zoom_saved - self.camera.zoom_level)
            self.renderer.set_zoom(PX_PER_M * self.camera.zoom)
            self._zoom_saved = None

    def _apply_camera_offset(self):
        """Техника стоит по центру свободной области: справа панель, на вкладке «Детали» слева ещё и палитра."""
        left = PALETTE_X * 2 + PALETTE_W if self.tab == "parts" else 0
        self.camera.center_on((PANEL_WIDTH - left) / 2 / self.camera.zoom, 0.0)

    def _zoom_preview(self, steps):
        cam = self.camera
        target = max(PARTS_ZOOM_MIN, min(PARTS_ZOOM_MAX, cam.zoom_level + int(steps)))
        if target == cam.zoom_level:
            return
        cam.zoom_by(target - cam.zoom_level)
        self.renderer.set_zoom(PX_PER_M * cam.zoom)
        self._apply_camera_offset()

    def _layout_palette(self, size):
        self.palette.layout(pygame.Rect(PALETTE_X, PALETTE_TOP, PALETTE_W,
                                        max(0, size[1] - PALETTE_TOP - PALETTE_BOTTOM)))

    def _on_parts_panel(self, values):
        """Панель «Детали»: поверхность, режим, размер. Меняется что-то одно за раз."""
        t = self.parts
        surface = values.get("parts_surface")
        if surface is not None and surface != t.surface:
            t.set_surface(surface)
            self._sync_palette()
            return
        mode = values.get("parts_mode")
        if mode is not None and (mode == "manual") != t.is_manual:
            t.set_manual(mode == "manual")
            return
        t.set_size(values.get("part_w"), values.get("part_h"))

    def _on_parts_design(self, design):
        """Дизайн изменился: сохраняем в сессию и пересобираем технику. Боты остаются на «Авто»."""
        kind = self.session.kind
        self.session.values[kind]["parts_design"] = None if design.is_auto else design.to_data()
        self.vehicle.set_spec(self.session.spec())
        self._show_stats()

    @staticmethod
    def _slider_range(rng):
        """Границы типа детали -> границы ползунка с шагом 0.05. Нет границы: мёртвый ползунок 0..0.05."""
        if rng is None:
            return 0.0, 0.05
        lo = math.ceil(rng[0] / 0.05 - 1e-9) * 0.05
        hi = math.floor(rng[1] / 0.05 + 1e-9) * 0.05
        lo, hi = round(lo, 3), round(hi, 3)
        return (lo, hi) if hi > lo else (lo, round(lo + 0.05, 3))

    def _refresh_parts_panel(self):
        """Панель и палитра показывают состояние инструмента."""
        if not getattr(self, "_has_parts", False) or self.parts.vehicle is None:
            return
        t, ui, mode = self.parts, self.ui, self._parts_mode
        ui.set_values(mode, {"parts_surface": t.surface, "parts_mode": "manual" if t.is_manual else "auto"})
        self.palette.set_selected(t.armed)

        p = t.selected_part()
        if p is None:
            for name in PARTS_STAT_SEL:
                ui.set_stat(mode, name, "—")
            ui.set_range(mode, "part_w", 0.0, 0.05)
            ui.set_range(mode, "part_h", 0.0, 0.05)
            ui.set_values(mode, {"part_w": 0.0, "part_h": 0.0})
        else:
            pt = PART_TYPES[p.kind]
            cx, cy = center(p)
            ui.set_stat(mode, "Тип", pt.label)
            ui.set_stat(mode, "Центр", f"{cx:.2f}; {cy:.2f} м")
            ui.set_stat(mode, "Угол", f"{p.angle:.0f} °" + (", отражена" if p.mirror else ""))
            ui.set_stat(mode, "Размер", f"{p.w:.2f} × {p.h:.2f} м")
            ui.set_stat(mode, "Положение", "помещается" if t.is_fit(p) else "не помещается")
            ui.set_range(mode, "part_w", *self._slider_range(pt.w_range))
            ui.set_range(mode, "part_h", *self._slider_range(pt.h_range))
            ui.set_values(mode, {"part_w": p.w, "part_h": p.h})

        ui.set_stat(mode, "Режим", "Вручную" if t.is_manual else "Авто")
        ui.set_stat(mode, "Деталей", str(t.count()) if t.is_manual else "—")
        ui.set_stat(mode, "Не помещаются", str(t.unfit_count()) if t.is_manual else "—")

        buttons = self._parts_buttons.get(mode, {})
        states = {PARTS_BTN_MIRROR: p is not None, PARTS_BTN_DELETE: p is not None,
                  PARTS_BTN_UNDO: t.can_undo, PARTS_BTN_REDO: t.can_redo}
        for label, enabled in states.items():
            if label in buttons:
                buttons[label].button.enabled = enabled

    def _parts_hotkeys(self):
        inp, t = self.input, self.parts
        if inp.was_pressed(Action.DELETE_WALL):
            t.delete_selected()
        if inp.was_pressed(Action.MIRROR):
            t.mirror_selected()
        if inp.ctrl:
            if inp.was_pressed(Action.UNDO):
                t.redo_step() if inp.shift else t.undo_step()
            if inp.was_pressed(Action.REDO):
                t.redo_step()
        t.update_drag()

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
        stats = {**spec.main_stats(), **spec.internal_stats()}
        modes = [self._mode] + ([self._design_mode] if self._has_design else [])
        for mode in modes:
            for name, text in stats.items():
                self.ui.set_stat(mode, name, text)

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
        in_parts = self.tab == "parts"
        steps = self.input.pop_zoom_steps()
        if in_parts:
            self._layout_palette(size)
            if steps:
                self._zoom_preview(steps)

        for button, pos in self.input.pop_world_clicks():
            if button == 1:
                if self.back_button.collidepoint(pos):
                    self.on_back()
                    return
                hit = next((k for k, btn in self.kind_buttons if btn.collidepoint(pos)), None)
                if hit is not None:
                    self._set_kind(hit)
                    in_parts = self.tab == "parts"
                    continue
            if in_parts:
                self.parts.click(button, pos)

        if self.input.was_pressed(Action.CANCEL):
            if not (in_parts and self.parts.escape()):      # на вкладке «Детали» Esc сначала снимает выбор
                self.on_back()
                return
        if in_parts:
            self._parts_hotkeys()
        if (self.input.was_pressed(Action.SNAPSHOT)
                and self.input.lctrl and self.input.lshift):
            self._save_snapshot()
        if self._toast is not None:
            self._toast[2] -= dt
            if self._toast[2] <= 0.0:
                self._toast = None

        # орудие превью следит за мышью (у ПТ-САУ в пределах УГН); на вкладке «Детали» башня стоит прямо
        aim = None
        if not in_parts and self.input.pointer_in_world:
            aim = self.camera.screen_to_world(*self.input.mouse_pos)
        self.vehicle.update(VehicleCommand(aim_point=aim), dt)

    def draw(self, screen):
        screen.fill(BG)
        self.renderer.draw(screen, self.camera, self.vehicle)
        if self.tab == "design":
            self._draw_turret_highlight(screen)
        elif self.tab == "parts":
            self.parts_overlay.draw(screen, self.parts)
        mouse = self.input.mouse_pos
        self.ui.draw(screen, mouse)
        self.palette.draw(screen, mouse)
        self.back_button.draw(screen, mouse)
        for kind, btn in self.kind_buttons:
            btn.draw(screen, mouse, colors=ACTIVE_BUTTON_COLORS if kind is self.session.kind else None)

    def _draw_turret_highlight(self, screen):
        """Кольцо вокруг оси башни и крестик в центре корпуса (виден эффект сдвига оси)."""
        v = self.vehicle
        z = self.camera.zoom
        cx, cy = self.camera.world_to_screen(v.x, v.y)
        r = max(8, round(1.7 * v.spec.TURRET_SCALE * PX_PER_M * z))
        area = pygame.Rect(round(cx) - r - 3, round(cy) - r - 3, 2 * r + 6, 2 * r + 6).clip(screen.get_rect())
        if area.w > 0 and area.h > 0:
            layer = self._alpha.begin(area.size)
            center = (round(cx) - area.x, round(cy) - area.y)
            pygame.draw.circle(layer, (*HIGHLIGHT, 40), center, r)
            pygame.draw.circle(layer, (*HIGHLIGHT, 220), center, r, 2)
            screen.blit(layer, area.topleft)
        hx, hy = self.camera.world_to_screen(*v.hull_obb()[:2])
        hx, hy = round(hx), round(hy)
        pygame.draw.line(screen, HIGHLIGHT, (hx - 7, hy), (hx + 7, hy), 2)
        pygame.draw.line(screen, HIGHLIGHT, (hx, hy - 7), (hx, hy + 7), 2)