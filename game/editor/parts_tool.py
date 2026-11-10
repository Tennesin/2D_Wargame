"""game/editor/parts_tool.py — инструмент «Детали» конструктора: ставит, выбирает, двигает, вращает, отражает
и удаляет детали выбранной поверхности (корпус или башня). Дизайн неизменяемый, поэтому отмена и повтор
это стеки прежних значений. О панели и палитре не знает: связь через колбэки on_design и on_state."""
import math
from dataclasses import replace

from engine import clamp
from vehicles.chassis.params import SCREEN_MM_MIN, FRONT_SCREEN
from vehicles.chassis.screens import mount_edges as hull_edges
from vehicles.parts.screens import (
    SHEET_KINDS, snap_hull, snap_turret, accept, coverage, max_length,
    turret_edges, turret_free, auto_screen_parts
)
from inputs import MouseOwner
from structures import ROTATE_SNAP_DEG
from vehicles.gun.params import BARREL_HIDDEN_M, BARREL_LEN_STEP_M
from vehicles.parts import (
    PART_TYPES, PartsDesign, AUTO_DESIGN, LIMITS, SURFACE_HULL, SURFACE_BARREL, fits, anchors,
    freeze_auto, z_of, center, contains, with_center, reshaped, new_part, extent_m, anchor_part,
    SURFACE_TURRET, resolve
)
from vehicles.parts.model import ANCHOR_HULL
from . import gizmo

GRID_M = 0.05                # шаг привязки центра детали
PICK_PX = 7.0                # допуск выбора, экранные px
UNDO_MAX = 100

class Frame:
    """Связь «метры поверхности <-> пиксели экрана» для одной поверхности."""
    __slots__ = ("cx", "cy", "k", "oy")

    def __init__(self, cx, cy, k, oy):
        self.cx, self.cy, self.k, self.oy = cx, cy, k, oy

    def to_screen(self, u, v):
        return self.cx + u * self.k, self.cy + (v + self.oy) * self.k

    def to_surface(self, px, py):
        return (px - self.cx) / self.k, (py - self.cy) / self.k - self.oy

class PartsTool:
    def __init__(self, camera, input_handler, on_design=None, on_state=None):
        self.camera = camera
        self.input = input_handler
        self.on_design = on_design        # колбэк(PartsDesign): дизайн изменился (сохранить и пересобрать технику)
        self.on_state = on_state          # колбэк(): изменилось что угодно (обновить панель и палитру)
        self.vehicle = None
        self.kind = "mbt"                 # ключ авто-набора (DESIGN_KIND рендерера)
        self.surfaces = (SURFACE_HULL,)
        self.surface = SURFACE_HULL
        self.design = AUTO_DESIGN
        self.undo = []
        self.redo = []
        self.selected = None              # индекс детали в ручном списке поверхности
        self.armed = None                 # тип из палитры, который ставится кликом
        self.active = False
        self._drag = None
        self._size_gesture = False        # идёт перетаскивание ползунка размера (один шаг отмены)

    # ==========================================
    # ПРИВЯЗКА И СОСТОЯНИЕ
    # ==========================================
    def bind(self, vehicle, kind, data, surfaces):
        """Новая техника: дизайн берётся из сохранённых данных, история сбрасывается."""
        self._end_drag()
        self.vehicle = vehicle
        self.kind = kind
        self.surfaces = tuple(surfaces)
        self.surface = self.surfaces[0]
        self.design = PartsDesign.from_data(data)
        self.undo.clear()
        self.redo.clear()
        self.selected = None
        self.armed = None

    def set_active(self, on):
        self.active = bool(on)
        if not on:
            self._end_drag()
            self.armed = None
            self.selected = None
        self._state()

    @property
    def spec(self):
        return self.vehicle.spec

    @property
    def manual(self):
        return self.design.get(self.surface)

    @property
    def is_manual(self):
        return self.manual is not None

    @property
    def can_undo(self):
        return bool(self.undo)

    @property
    def can_redo(self):
        return bool(self.redo)

    @property
    def drag_mode(self):
        return None if self._drag is None else self._drag["mode"]

    def _state(self):
        if self.on_state is not None:
            self.on_state()

    def _design_changed(self):
        if self.on_design is not None:
            self.on_design(self.design)
        self._state()

    # ==========================================
    # ДЕТАЛИ ПОВЕРХНОСТИ
    # ==========================================
    def entries(self):
        """[(индекс, деталь в абсолютных метрах)] ручного списка. Деталь с неизвестным якорем пропускается."""
        lst = self.manual
        if lst is None or self.vehicle is None:
            return []
        table = anchors(self.spec, self.surface)
        out = []
        for i, p in enumerate(lst):
            if p.anchor != ANCHOR_HULL:
                base = table.get(p.anchor)
                if base is None:
                    continue
                p = replace(p, x=p.x + base[0], y=p.y + base[1], anchor=ANCHOR_HULL)
            out.append((i, p))
        return out

    def selected_part(self):
        if self.selected is None:
            return None
        for i, p in self.entries():
            if i == self.selected:
                return p
        return None

    def is_fit(self, p):
        return fits(p, self.spec, self.surface)

    def count(self):
        return 0 if self.manual is None else len(self.manual)

    def unfit_count(self):
        return sum(1 for i, p in self.entries() if not self._fit(p, i))

    def _frozen_list(self):
        """Авто-набор текущей поверхности как список деталей (для перехода в «Вручную»)."""
        return tuple(freeze_auto(self.kind, self.spec).get(self.surface) or ())

    # ==========================================
    # ГЕОМЕТРИЯ ЭКРАНА
    # ==========================================
    def frame(self):
        """Корпус: центр спрайта = ось орудия."""
        v = self.vehicle
        spec = v.spec
        sx, sy = self.camera.world_to_screen(v.x, v.y)
        ppm = PX_PER_M * self.camera.zoom
        if self.surface == SURFACE_HULL:
            return Frame(round(sx), round(sy), ppm * spec.HULL_SCALE, spec.layout.axis_fwd_m)
        if self.surface == SURFACE_BARREL:
            length = round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M) * BARREL_LEN_STEP_M
            mid = spec.GUN_FRONT_M + length / 2.0 - BARREL_HIDDEN_M / 2.0     # как f в GunVehicleRenderer.draw
            return Frame(round(sx), round(sy), ppm * spec.TURRET_SCALE, -mid)
        return Frame(round(sx), round(sy), ppm * spec.TURRET_SCALE, 0.0)

    def gizmo_geom(self):
        """(x, y центра на экране, радиус дуг, угол детали) выбранной детали или None."""
        p = self.selected_part()
        if p is None:
            return None
        fr = self.frame()
        sx, sy = fr.to_screen(*center(p))
        return sx, sy, gizmo.arc_radius(extent_m(p) * fr.k), p.angle

    def pick(self, px, py):
        """Индекс верхней детали под точкой экрана или None."""
        fr = self.frame()
        u, v = fr.to_surface(px, py)
        tol = max(0.06, PICK_PX / fr.k)
        best, best_key = None, None
        for i, p in self.entries():
            if contains(p, u, v, tol):
                key = (z_of(p), i)
                if best_key is None or key > best_key:
                    best, best_key = i, key
        return best

    def _candidate(self, pos):
        """Новая деталь выбранного типа под курсором (центр привязан к сетке)."""
        if self.armed is None:
            return None
        u, v = self.frame().to_surface(*pos)
        if self.armed == "screen":
            return snap_hull(self.spec.layout, u, v)
        if self.armed == "turret_screen":
            return snap_turret(self.spec.layout.turret_style, u, v)
        if not self.input.ctrl:
            u, v = round_to(u, GRID_M), round_to(v, GRID_M)
        return new_part(self.armed, self.surface, u, v)

    def ghost(self):
        """(призрак, можно ли поставить) или None."""
        if (not self.active or self.vehicle is None or self.armed is None or self._drag is not None
                or not self.input.pointer_in_world):
            return None
        pos = self.input.mouse_pos
        if self.pick(*pos) is not None:
            return None
        part = self._candidate(pos)
        if part is None:
            return None
        ok = self._fit(part) and self.count() < LIMITS[self.surface]
        return part, ok

    # ==========================================
    # КЛИКИ
    # ==========================================
    def click(self, button, pos):
        """ЛКМ: рукоятка выбранной детали, выбор детали, постановка. ПКМ: снять выбор."""
        if not self.active or self.vehicle is None:
            return
        if button == 3:
            self.escape()
            return
        if button != 1:
            return
        geom = self.gizmo_geom()
        if geom is not None:
            mode = gizmo.hit(*geom, pos)
            sel = self.selected_part()
            if mode == "rotate" and sel is not None and sel.kind in SHEET_KINDS:
                mode = None
        i = self.pick(*pos)
        if i is not None:
            self.selected = i
            self._state()
            return
        if self.armed is not None:
            self._place(pos)
        elif self.selected is not None:
            self.selected = None
            self._state()

    def escape(self):
        """Esc или ПКМ: по одному слою. True, если было что снимать."""
        if self._drag is not None:
            self._end_drag()
            return True
        if self.armed is not None:
            self.armed = None
            self._state()
            return True
        if self.selected is not None:
            self.selected = None
            self._state()
            return True
        return False

    # ==========================================
    # ПЕРЕТАСКИВАНИЕ И ВРАЩЕНИЕ
    # ==========================================
    def _grab(self, mode, pos, geom):
        owner = MouseOwner.MOVE if mode == "move" else MouseOwner.ROTATE
        if not self.input.grab_mouse(owner, 1):
            return False
        p = self.selected_part()
        if p is None:
            self.input.release_mouse(owner)
            return False
        if mode == "move":
            u, v = self.frame().to_surface(*pos)
            cx, cy = center(p)
            self._drag = {"mode": "move", "off": (cx - u, cy - v), "fresh": True}
        else:
            phi = math.degrees(math.atan2(pos[1] - geom[1], pos[0] - geom[0]))
            self._drag = {"mode": "rotate", "phi": phi, "angle": p.angle, "fresh": True}
        return True

    def _end_drag(self):
        self._drag = None
        self.input.release_mouse(MouseOwner.MOVE)
        self.input.release_mouse(MouseOwner.ROTATE)

    def update_drag(self):
        """Каждый кадр на вкладке. Пока мышь принадлежит MOVE или ROTATE, деталь следует за мышью."""
        if self.input.mouse_owner is not MouseOwner.UI:
            self._size_gesture = False
        d = self._drag
        if d is None:
            return
        owner = MouseOwner.MOVE if d["mode"] == "move" else MouseOwner.ROTATE
        p = self.selected_part()
        if self.input.mouse_owner is not owner or p is None:
            self._drag = None
            return
        mx, my = self.input.mouse_pos
        if d["mode"] == "move":
            u, v = self.frame().to_surface(mx, my)
            if p.kind in SHEET_KINDS:
                new = self._slide(p, u, v)
            else:
                tx, ty = d["off"][0] + u, d["off"][1] + v
                if not self.input.ctrl:
                    tx, ty = round_to(tx, GRID_M), round_to(ty, GRID_M)
                new = with_center(p, tx, ty)
            if new is None or new == p or not self._fit(new, self.selected):
                return
        else:
            geom = self.gizmo_geom()
            if geom is None:
                return
            phi = math.degrees(math.atan2(my - geom[1], mx - geom[0]))
            angle = d["angle"] + shortest_angle_diff(phi, d["phi"])
            if self.input.shift:
                angle = round_to(angle, ROTATE_SNAP_DEG)
            new = reshaped(p, angle=angle % 360.0)
            if new == p or (self.is_fit(p, self.selected) and not self._fit(new, self.selected)):
                return                                   # в неподходящее положение не вращаем
        self._replace_selected(new, d["fresh"])
        d["fresh"] = False

    def _sheets(self, kind, exclude=None):
        return [q for i, q in self.entries() if q.kind == kind and i != exclude]

    def _fit(self, p, index=None):
        """Помещается ли деталь. Листы экранов ещё проверяются на охват и пересечения."""
        if p.kind == "screen":
            return any(q is p for q, *_ in accept(self.spec.layout, self._sheets("screen", index) + [p]))
        if p.kind == "turret_screen":
            return (fits(p, self.spec, self.surface)
                    and turret_free(self.spec.layout.turret_style, self._sheets("turret_screen", index), p))
        return fits(p, self.spec, self.surface)

    def is_fit(self, p, index=None):
        return self._fit(p, index)

    def _slide(self, p, u, v):
        """Лист едет вдоль кромок за курсором (может перейти на соседнюю кромку)."""
        if p.kind == "screen":
            return snap_hull(self.spec.layout, u, v, p.w, p.mm)
        return snap_turret(self.spec.layout.turret_style, u, v, p.w)

    def mount_edges(self):
        """Кромки для подсветки: лист выбран или взят из палитры."""
        sel = self.selected_part()
        kinds = {self.armed, None if sel is None else sel.kind}
        if "screen" in kinds and self.surface == SURFACE_HULL:
            return hull_edges(self.spec.layout)
        if "turret_screen" in kinds and self.surface == SURFACE_TURRET:
            return turret_edges(self.spec.layout.turret_style)
        return ()

    def screen_coverage(self):
        """{группа: (занято, длина)} по листам корпуса (авто или ручного набора)."""
        layout, hull = self.spec.layout, self.design.hull
        parts = (auto_screen_parts(layout, self.spec.screen_mm) if hull is None
                 else [p for p in resolve(hull, self.spec, SURFACE_HULL) if p.kind == "screen"])
        return coverage(layout, parts)

    def max_length(self, p, index=None):
        return max_length(self.spec.layout, self._sheets("screen", index), p)

    def set_thickness(self, mm):
        """Толщина выбранного экрана: число (своя) или None (общая шкала). Один жест ползунка = один шаг отмены."""
        p = self.selected_part()
        if p is None or p.kind != "screen":
            return
        own = None if mm is None else clamp(float(mm), SCREEN_MM_MIN, FRONT_SCREEN.max)
        if own == p.mm:
            return
        fresh = not self._size_gesture
        self._size_gesture = True
        self._replace_selected(replace(p, mm=own), fresh)

    # ==========================================
    # ИЗМЕНЕНИЯ ДИЗАЙНА
    # ==========================================
    def _commit(self, design, record=True):
        """Применить новый дизайн. Он пропускается через сериализацию: инструмент видит то же, что файл
        и рендерер (округление, границы типов). record: записать прежний дизайн в историю."""
        design = PartsDesign.from_data(design.to_data())
        if record:
            self.undo.append(self.design)
            del self.undo[:-UNDO_MAX]
            self.redo.clear()
        self.design = design
        self._design_changed()

    def _replace_selected(self, part, record):
        lst = list(self.manual)
        part = anchor_part(replace(part, anchor=ANCHOR_HULL), self.spec, self.surface)
        lst[self.selected] = part
        self._commit(self.design.with_parts(self.surface, lst), record)

    def _place(self, pos):
        part = self._candidate(pos)
        if part is None or not self._fit(part): return
        lst = self.manual
        if lst is None:                                   # авто-набор замораживается вместе с постановкой
            lst = self._frozen_list()
        if len(lst) >= LIMITS[self.surface]:
            return
        lst = list(lst) + [anchor_part(part, self.spec, self.surface)]
        self.selected = len(lst) - 1
        self._commit(self.design.with_parts(self.surface, lst))

    def delete_selected(self):
        lst = self.manual
        if lst is None or self.selected is None or not (0 <= self.selected < len(lst)):
            return
        lst = list(lst)
        del lst[self.selected]
        self.selected = None
        self._commit(self.design.with_parts(self.surface, lst))

    def mirror_selected(self):
        p = self.selected_part()
        if p is not None:
            self._replace_selected(reshaped(p, mirror=not p.mirror), True)

    def set_size(self, w, h):
        """Ползунки панели. Размер меняется вокруг центра. Один жест ползунка = один шаг отмены."""
        p = self.selected_part()
        if p is None:
            return
        pt = PART_TYPES[p.kind]
        nw = p.w if (w is None or pt.w_range is None) else min(max(w, pt.w_range[0]), pt.w_range[1])
        nh = p.h if (h is None or pt.h_range is None) else min(max(h, pt.h_range[0]), pt.h_range[1])
        if abs(nw - p.w) < 1e-6 and abs(nh - p.h) < 1e-6:
            self._state()                                  # вернуть ползунок на место
            return
        new = reshaped(p, w=round(nw, 4), h=round(nh, 4))
        if self.is_fit(p, self.selected) and not self._fit(new, self.selected):
            self._state()                                  # не лезет: ползунок возвращаем
            return
        fresh = not self._size_gesture
        self._size_gesture = True
        self._replace_selected(new, fresh)

    def set_manual(self, on):
        """Авто <-> Вручную (замораживает авто-набор или возвращает авто). Отменяется."""
        if on == self.is_manual:
            return
        self.selected = None
        self._commit(self.design.with_parts(self.surface, self._frozen_list() if on else None))

    def set_surface(self, surface):
        if surface not in self.surfaces or surface == self.surface:
            return
        self._end_drag()
        self.surface = surface
        self.selected = None
        if self.armed is not None and surface not in PART_TYPES[self.armed].surfaces:
            self.armed = None
        self._state()

    def arm(self, kind):
        self.armed = kind
        if kind is not None:
            self.selected = None
        self._state()

    def undo_step(self):
        if self.undo:
            self.redo.append(self.design)
            self.design = self.undo.pop()
            self.selected = None
            self._design_changed()

    def redo_step(self):
        if self.redo:
            self.undo.append(self.design)
            self.design = self.redo.pop()
            self.selected = None
            self._design_changed()