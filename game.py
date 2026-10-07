"""game.py — окно, главный цикл, связывание частей."""
import math
import random
from enum import Enum, auto

import pygame

from common import PX_PER_M, shortest_angle_diff
from core import Camera, WorldGenerator, CHUNK_SIZE
from tank import Tank, TankSpec
from wall import (Wall, WallManager, PLACE_REPEAT,
                  ROTATE_HANDLE_HIT_PX, ROTATE_DEAD_ZONE_PX, ROTATE_SNAP_DEG)
from controls import Action, MouseOwner, COMBAT_HOLD
from input_handler import InputHandler
from renderer import Renderer
from ui import ConstructorUI, ToolBar, get_font, FONT_SIZE_LABEL
from effects import EffectsSystem
from aim import compute_aim
from hud import TankHud
from armor import TargetSet

class Mode(Enum):
    DRIVE = auto()       # езда и стрельба
    BUILD = auto()       # расстановка стен: танк не управляется
    WALL_EDIT = auto()   # выбрана стена: открыта её панель, можно вращать


class Game:
    MAX_DT = 0.05   # защита от «телепорта» при подвисании окна

    def __init__(self, seed=None):
        pygame.init()
        self.screen = pygame.display.set_mode((1000, 700), pygame.RESIZABLE)
        pygame.display.set_caption("Top-Down Танк (бесконечный мир)")
        self.clock = pygame.time.Clock()

        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        print(f"Seed мира: {self.seed}")

        self.world = WorldGenerator(self.seed)
        self.camera = Camera(*self.screen.get_size())
        self.ui = ConstructorUI(self.screen.get_size())
        self.toolbar = ToolBar()
        self.spec = TankSpec.from_values(self.ui.get_values())
        self.tank = Tank(0.0, 0.0, spec=self.spec)
        self.walls = WallManager()
        self.targets = TargetSet(self.walls)     # всё, во что можно попасть. Враги: self.targets.add(enemy_tank)
        self.ui.on_change = self._on_constructor_change
        self.ui.on_wall_change = self._on_wall_change
        self.toolbar.on_create_wall = self._toggle_build_mode
        self._show_stats()

        self.mode = Mode.DRIVE           # единственный источник правды о режиме
        self.show_debug = False          # отладочные строки (Tab)
        self.turret_follow = True        # башня следит за мышью (Q)
        self.combat = False              # боевое состояние (Alt): включает огонь по ЛКМ и красную линию прицела
        self._rot_state = None           # при вращении стены: [последний угол мыши, накопленный угол стены]

        self.spec.print_specs()
        self.input = InputHandler([self.toolbar, self.ui])
        self.renderer = Renderer(self.world)
        self.effects = EffectsSystem()
        self.hud = TankHud()

    # ==========================================
    # ТАНК
    # ==========================================
    def _on_constructor_change(self, values):
        """Ползунок сдвинут: пересчитываем танк и обновляем панель."""
        self.spec = TankSpec.from_values(values)
        self.tank.spec = self.spec
        self._show_stats()
        self.tank.set_spec(self.spec)

    def _show_stats(self):
        for name, text in {**self.spec.main_stats(), **self.spec.internal_stats()}.items():
            self.ui.set_stat(name, text)

    # ==========================================
    # РЕЖИМЫ
    # ==========================================
    def _set_mode(self, mode, wall=None):
        """Единственное место, где меняется режим. wall нужен только для WALL_EDIT.
        Всё, что зависит от режима (выбранная стена, кнопка, панель, захват мыши), приводится в порядок здесь."""
        if mode == Mode.WALL_EDIT and wall is None:
            mode = Mode.DRIVE
        self.mode = mode
        self._rot_state = None
        self.input.release_mouse(MouseOwner.ROTATE)
        if mode == Mode.BUILD:
            self._set_combat(False)                      # стройка и боевое состояние несовместимы

        self.walls.selected = wall if mode == Mode.WALL_EDIT else None
        self.toolbar.set_active(mode == Mode.BUILD)
        if mode == Mode.WALL_EDIT:
            self.ui.show_wall(self._wall_values(wall))
        else:
            self.ui.show_tank()

    def _set_combat(self, on):
        """Боевое состояние. В режиме стройки включить нельзя. При выключении стрельба обрывается."""
        if on and self.mode == Mode.BUILD:
            return
        self.combat = on
        if not on:
            self.input.release_mouse(MouseOwner.FIRE)

    def _toggle_build_mode(self):
        self._set_mode(Mode.DRIVE if self.mode == Mode.BUILD else Mode.BUILD)

    def _handle_escape(self):
        """Esc закрывает по одному слою: стройка или стена, затем боевое состояние. Из игры не выходит."""
        if self.mode != Mode.DRIVE:
            self._set_mode(Mode.DRIVE)
        elif self.combat:
            self._set_combat(False)

    def _handle_hotkeys(self):
        """Разовые клавиши, меняющие состояние игры."""
        inp = self.input
        if inp.was_pressed(Action.QUIT):
            inp.quit_requested = True
        if inp.was_pressed(Action.TOGGLE_DEBUG):
            self.show_debug = not self.show_debug
        if inp.was_pressed(Action.LOCK_TURRET):
            self.turret_follow = not self.turret_follow
        if inp.was_pressed(Action.TOGGLE_BUILD):
            self._toggle_build_mode()

        if COMBAT_HOLD:
            self._set_combat(Action.COMBAT in inp.held)
        elif inp.was_pressed(Action.COMBAT):
            self._set_combat(not self.combat)

        if inp.was_pressed(Action.CANCEL):
            self._handle_escape()

    # ==========================================
    # СТЕНЫ
    # ==========================================
    def _wall_blocked(self, wall):
        """Нельзя ли поставить стену здесь. Сейчас мешает только танк.
        Чтобы стены не пересекались друг с другом, добавьте проверку пересечения с self.walls.items."""
        return self.tank.hits_obb(wall.obb())

    def _build_preview(self):
        """(призрак, красный ли он) или None, если показывать нечего."""
        if self.mode != Mode.BUILD or not self.input.pointer_in_world:
            return None
        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
        ghost = Wall.default(wx, wy)
        return ghost, self._wall_blocked(ghost)

    def _aim_info(self):
        """Траектория выстрела. Показываем только в режиме DRIVE."""
        if not self.combat or self.mode == Mode.BUILD:
            return None
        return compute_aim(self.tank, self.targets)

    # ---------- клики по миру ----------
    def _handle_world_clicks(self):
        """Клики по миру (интерфейс свои уже забрал). Что значит клик, решает режим."""
        for button, pos in self.input.pop_world_clicks():
            wx, wy = self.camera.screen_to_world(*pos)
            if self.mode == Mode.BUILD:
                self._click_build(button, wx, wy)
            else:
                self._click_play(button, pos, wx, wy)

    def _click_build(self, button, wx, wy):
        """BUILD: ЛКМ ставит стену, ПКМ выходит из стройки."""
        if button == 1:
            wall = Wall.default(wx, wy)
            if not self._wall_blocked(wall):
                self.walls.add(wall)
                if not PLACE_REPEAT:
                    self._set_mode(Mode.DRIVE)
        elif button == 3:
            self._set_mode(Mode.DRIVE)

    def _click_play(self, button, pos, wx, wy):
        """DRIVE и WALL_EDIT.
        ЛКМ: по белой точке вращает стену; иначе в боевом состоянии это огонь, а без него выбор стены.
        ПКМ: выбор стены / снятие выбора (работает всегда)."""
        if button == 1:
            if self._hit_rotate_handle(pos):
                self.input.grab_mouse(MouseOwner.ROTATE, 1)
                self._rot_state = None
            elif self.combat:
                self.input.grab_mouse(MouseOwner.FIRE, 1)
            else:
                self._select_or_drive(wx, wy)
        elif button == 3:
            self._select_or_drive(wx, wy)

    def _select_or_drive(self, wx, wy):
        """Стена под точкой: открыть её настройки. Пустое место: вернуться в DRIVE."""
        wall = self.walls.pick(wx, wy)
        if wall is not None:
            self._set_mode(Mode.WALL_EDIT, wall)
        else:
            self._set_mode(Mode.DRIVE)

    # ---------- параметры и вращение ----------
    @staticmethod
    def _wall_values(wall):
        return {"wall_hp": wall.max_hp, "wall_width_m": wall.width_m, "wall_length_m": wall.length_m}

    def _on_wall_change(self, values):
        """Ползунок стены сдвинут. Если новая стена упёрлась бы в танк, возвращаем прежние значения."""
        wall = self.walls.selected
        if wall is None:
            return
        old = (wall.max_hp, wall.width_m, wall.length_m)
        wall.apply_params(values["wall_hp"], values["wall_width_m"], values["wall_length_m"])
        if self.tank.hits_obb(wall.obb()):
            wall.apply_params(*old)
            self.ui.set_wall_values(self._wall_values(wall))

    def _hit_rotate_handle(self, pos):
        """Попал ли клик в белую точку выбранной стены (расстояние считаем в экранных px)."""
        wall = self.walls.selected
        if wall is None:
            return False
        cx, cy = self.camera.world_to_screen(wall.x, wall.y)
        return math.hypot(pos[0] - cx, pos[1] - cy) <= ROTATE_HANDLE_HIT_PX

    def _update_wall_rotation(self):
        """Пока мышь принадлежит ROTATE, стена поворачивается вслед за направлением мыши от её центра.
        Поворот относительный (нет рывка при захвате), с накоплением угла (можно крутить больше оборота).
        Shift: привязка к шагу ROTATE_SNAP_DEG. Поворот, упирающийся в танк, не применяется."""
        wall = self.walls.selected
        if self.input.mouse_owner != MouseOwner.ROTATE or wall is None:
            self._rot_state = None
            return

        cx, cy = self.camera.world_to_screen(wall.x, wall.y)
        mx, my = self.input.mouse_pos
        dx, dy = mx - cx, my - cy
        if math.hypot(dx, dy) < ROTATE_DEAD_ZONE_PX:
            return                                       # мышь у самого центра: направление неопределённо
        mouse_ang = math.degrees(math.atan2(dx, -dy))    # 0 = вверх, по часовой

        if self._rot_state is None:
            self._rot_state = [mouse_ang, wall.angle]
            return
        last, raw = self._rot_state
        raw += shortest_angle_diff(mouse_ang, last)
        self._rot_state = [mouse_ang, raw]

        new_angle = raw
        if self.input.shift:
            new_angle = round(raw / ROTATE_SNAP_DEG) * ROTATE_SNAP_DEG
        new_angle %= 360.0

        old = wall.angle
        wall.angle = new_angle
        if self.tank.hits_obb(wall.obb()):
            wall.angle = old

    def _apply_hits(self, hits):
        """Снаряд попал в цель: урон = заявленный × доля по правилам armor.py (стена и танк одинаково)."""
        for target, spec, cos_impact, normal, power in hits:
            target.take_hit(spec.penetration * power, spec.damage * power, cos_impact, normal)
        self.walls.remove_dead()
        if self.mode == Mode.WALL_EDIT and self.walls.selected is None:
            self._set_mode(Mode.DRIVE)             # выбранную стену разрушили — возвращаем панель танка

    def _show_wall_stats(self):
        wall = self.walls.selected
        if wall is None:
            return
        self.ui.set_stat("Текущее HP", f"{wall.hp:,.0f} / {wall.max_hp:,.0f}".replace(",", " "))
        self.ui.set_stat("Масса стены", f"{wall.mass_t:,.1f} т".replace(",", " "))
        self.ui.set_stat("Толщина", f"{wall.thickness_m:.2f} м")
        self.ui.set_stat("Эквивалент брони", f"{wall.armor_mm:.0f} мм")
        self.ui.set_stat("Угол", f"{wall.angle:.0f} °")

    # ==========================================
    # ОТЛАДКА И ГЛАВНЫЙ ЦИКЛ
    # ==========================================
    def _debug_lines(self):
        t = self.tank
        owner = self.input.mouse_owner.name if self.input.mouse_owner else "-"
        return [
            f"FPS: {self.clock.get_fps():.0f}",
            f"Zoom: {self.camera.zoom:.2f} (1 m = {PX_PER_M * self.camera.zoom:.0f} px)",
            f"X: {t.x:.0f}  Y: {t.y:.0f}",
            f"Chunk: {int(t.x // CHUNK_SIZE)}, {int(t.y // CHUNK_SIZE)}",
            f"Grass: {self.world.grass_at(t.x, t.y):.2f}",
            f"Hull: {t.hull_angle:.0f}  Turret: {t.turret_angle:.0f}",
            f"Seed: {self.seed}",
            f"Turret follow (Q): {'ON' if self.turret_follow else 'OFF'}",
            f"Reload: {t.reload_left:.1f}s",
            f"Pos (m): {t.x / PX_PER_M:.1f}, {t.y / PX_PER_M:.1f}",
            f"Walls: {len(self.walls.items)}",
            f"Mode: {self.mode.name}  Mouse owner: {owner}",
            f"Combat (Alt): {'ON' if self.combat else 'OFF'}",
            f"Speed: {t.speed_kmh:.1f} km/h",
        ]

    def _draw_hud(self):
        """Левый нижний угол: сводка по танку, а над ней индикаторы боевого состояния и подсказки."""
        y = self.hud.draw(self.screen, self.tank) - 6

        rows = []
        if self.combat:
            rows.append(("БОЕВОЙ РЕЖИМ: ЛКМ — огонь", (240, 80, 80)))
        else:
            rows.append(("Alt — боевой режим, Tab — отладка", (170, 176, 186)))
        if not self.turret_follow:
            rows.append(("Башня зафиксирована (Q)", (240, 210, 70)))

        font = get_font(FONT_SIZE_LABEL)
        for text, color in reversed(rows):
            shadow = font.render(text, True, (0, 0, 0))
            label = font.render(text, True, color)
            y -= label.get_height() + 2
            self.screen.blit(shadow, (11, y + 1))
            self.screen.blit(label, (10, y))

    def run(self):
        while not self.input.quit_requested:
            dt = min(self.clock.tick(60) / 1000.0, self.MAX_DT)

            self.input.process_events()
            self.input.update_zoom_keys(dt)
            steps = self.input.pop_zoom_steps()
            if steps:
                self.camera.zoom_by(steps)

            self.screen = pygame.display.get_surface()      # актуально после изменения размера окна
            w, h = self.screen.get_size()
            if w == 0 or h == 0:
                continue
            self.camera.resize(w, h)
            self.ui.update((w, h))

            self._handle_hotkeys()
            self._handle_world_clicks()
            self._update_wall_rotation()

            command = self.input.read_command(self.camera,
                                              active=self.mode != Mode.BUILD,
                                              follow_mouse=self.turret_follow,
                                              combat=self.combat)
            shot = self.tank.update(command, dt, self.walls.obbs())
            if shot is not None:
                self.effects.spawn_shot(shot, self.tank.spec, self.tank)
            self.camera.center_on(self.tank.x, self.tank.y)
            hits = self.effects.update(dt, self.camera, self.targets)
            self._apply_hits(hits)
            self._show_wall_stats()

            debug = self._debug_lines() if self.show_debug else None
            self.renderer.draw(self.screen, self.camera, self.tank, debug, self.effects,
                               self.walls, self._build_preview(), self._aim_info())
            self.ui.draw(self.screen)
            self.toolbar.draw(self.screen)
            self._draw_hud()
            pygame.display.flip()