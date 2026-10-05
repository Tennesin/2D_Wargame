"""game.py — окно, главный цикл, связывание частей."""
import math
import random
import pygame

from common import PX_PER_M, shortest_angle_diff
from core import Camera, WorldGenerator, CHUNK_SIZE
from tank import Tank, TankSpec
from wall import (Wall, WallManager, PLACE_REPEAT,
                  ROTATE_HANDLE_HIT_PX, ROTATE_DEAD_ZONE_PX, ROTATE_SNAP_DEG)
from input_handler import InputHandler
from renderer import Renderer
from ui import ConstructorUI, ToolBar
from effects import EffectsSystem
from aim import compute_aim

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
        self.ui.on_change = self._on_constructor_change
        self.ui.on_wall_change = self._on_wall_change
        self.toolbar.on_create_wall = self._toggle_build_mode
        self._show_stats()
        self._rotating = False           # тянут ли сейчас белую точку выбранной стены
        self._rot_state = None           # [последний угол мыши, накопленный угол стены]
        self.spec.print_specs()
        self.input = InputHandler([self.toolbar, self.ui])
        self.renderer = Renderer(self.world)
        self.effects = EffectsSystem()

    # ==========================================
    # ТАНК
    # ==========================================
    def _on_constructor_change(self, values):
        """Ползунок сдвинут: пересчитываем танк и обновляем панель."""
        self.spec = TankSpec.from_values(values)
        self.tank.spec = self.spec
        self._show_stats()

    def _show_stats(self):
        for name, text in {**self.spec.main_stats(), **self.spec.internal_stats()}.items():
            self.ui.set_stat(name, text)

    # ==========================================
    # СТЕНЫ
    # ==========================================
    def _toggle_build_mode(self):
        self._set_build_mode(not self.input.build_mode)

    def _set_build_mode(self, on):
        self.input.build_mode = on
        self.toolbar.set_active(on)
        if on:
            self._select_wall(None)          # на время стройки панель стены не нужна

    def _wall_blocked(self, wall):
        """Нельзя ли поставить стену здесь. Сейчас мешает только танк.
        Чтобы стены не пересекались друг с другом, добавьте:
        or any(wall_rect_overlap(wall.rect(), r) for r in self.walls.rects())"""
        return self.tank.hits_obb(wall.obb())

    def _build_preview(self):
        """(призрак, красный ли он) или None, если показывать нечего."""
        if not self.input.build_mode or self.input.ui_captures_mouse():
            return None
        wx, wy = self.camera.screen_to_world(*pygame.mouse.get_pos())
        ghost = Wall.default(wx, wy)
        return ghost, self._wall_blocked(ghost)

    def _aim_info(self):
        """Траектория выстрела. Показываем только когда не открыты режимы стройки и стены."""
        if self.input.build_mode or self.walls.selected is not None:
            return None
        return compute_aim(self.tank, self.walls)

    def _handle_world_clicks(self):
        """Клики по миру. В режиме стройки: ЛКМ ставит стену, ПКМ выбирает стену.
        Вне стройки: ЛКМ по белой точке выбранной стены начинает поворот, ПКМ выбирает стену."""
        for button, pos in self.input.pop_world_clicks():
            wx, wy = self.camera.screen_to_world(*pos)
            if self.input.build_mode:
                if button == 1:
                    wall = Wall.default(wx, wy)
                    if not self._wall_blocked(wall):
                        self.walls.add(wall)
                        if not PLACE_REPEAT:
                            self._set_build_mode(False)
                elif button == 3:
                    self._select_wall(self.walls.pick(wx, wy))
            else:
                if button == 1 and self._hit_rotate_handle(pos):
                    self._rotating = True
                    self._rot_state = None
                elif button == 3:
                    self._select_wall(self.walls.pick(wx, wy))

    def _handle_escape(self):
        """Esc закрывает по одному слою: стройка -> выбранная стена -> выход из игры."""
        if self.input.build_mode:
            self._set_build_mode(False)
        elif self.walls.selected is not None:
            self._select_wall(None)
        else:
            self.input.quit_requested = True

    def _select_wall(self, wall):
        self.walls.selected = wall
        self._rotating = False
        self._rot_state = None
        if wall is None:
            self.ui.show_tank()
        else:
            self.ui.show_wall(self._wall_values(wall))

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
        """Пока ЛКМ зажата на белой точке, стена поворачивается вслед за направлением мыши от её центра.
        Поворот относительный (нет рывка при захвате), с накоплением угла (можно крутить больше оборота).
        Shift — привязка к шагу ROTATE_SNAP_DEG. Поворот, упирающийся в танк, не применяется."""
        if not self._rotating:
            return
        wall = self.walls.selected
        if wall is None or not pygame.mouse.get_pressed()[0]:
            self._rotating = False
            self._rot_state = None
            return

        cx, cy = self.camera.world_to_screen(wall.x, wall.y)
        mx, my = pygame.mouse.get_pos()
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
        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            new_angle = round(raw / ROTATE_SNAP_DEG) * ROTATE_SNAP_DEG
        new_angle %= 360.0

        old = wall.angle
        wall.angle = new_angle
        if self.tank.hits_obb(wall.obb()):
            wall.angle = old

    def _apply_hits(self, hits):
        """Снаряд попал в стену: пробил (пробитие >= эквивалента брони) — урон, иначе ничего."""
        for wall, spec, cos_impact in hits:
            wall.take_hit(spec.penetration, spec.damage, cos_impact)
        self.walls.remove_dead()
        if self.ui.mode == "wall" and self.walls.selected is None:
            self.ui.show_tank()                    # выбранную стену разрушили — возвращаем панель танка

    def _show_wall_stats(self):
        wall = self.walls.selected
        if wall is None:
            return
        self.ui.set_stat("Текущее HP", f"{wall.hp:,.0f} / {wall.max_hp:,.0f}".replace(",", " "))
        self.ui.set_stat("Толщина", f"{wall.thickness_m:.2f} м")
        self.ui.set_stat("Эквивалент брони", f"{wall.armor_mm:.0f} мм")
        self.ui.set_stat("Угол", f"{wall.angle:.0f} °")

    # ==========================================
    # ОТЛАДКА И ГЛАВНЫЙ ЦИКЛ
    # ==========================================
    def _debug_lines(self):
        t = self.tank
        return [
            f"FPS: {self.clock.get_fps():.0f}",
            f"Zoom: {self.camera.zoom:.2f} (1 m = {PX_PER_M * self.camera.zoom:.0f} px)",
            f"X: {t.x:.0f}  Y: {t.y:.0f}",
            f"Chunk: {int(t.x // CHUNK_SIZE)}, {int(t.y // CHUNK_SIZE)}",
            f"Grass: {self.world.grass_at(t.x, t.y):.2f}",
            f"Hull: {t.hull_angle:.0f}  Turret: {t.turret_angle:.0f}",
            f"Seed: {self.seed}",
            f"Turret follow (Q): {'ON' if self.input.turret_follow else 'OFF'}",
            f"Reload: {t.reload_left:.1f}s",
            f"Pos (m): {t.x / PX_PER_M:.1f}, {t.y / PX_PER_M:.1f}",
            f"Walls: {len(self.walls.items)}",
        ]

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

            if self.input.pop_escape():
                self._handle_escape()
            self._handle_world_clicks()
            self._update_wall_rotation()

            command = self.input.read_command(self.camera)
            if self._rotating:
                command.fire = False
            shot = self.tank.update(command, dt, self.walls.obbs())
            if shot is not None:
                self.effects.spawn_shot(shot, self.tank.spec)
            self.camera.center_on(self.tank.x, self.tank.y)
            hits = self.effects.update(dt, self.camera, self.walls)
            self._apply_hits(hits)
            self._show_wall_stats()

            debug = self._debug_lines() if self.input.show_debug else None
            self.renderer.draw(self.screen, self.camera, self.tank, debug, self.effects,
                               self.walls, self._build_preview(), self._aim_info())
            self.ui.draw(self.screen)
            self.toolbar.draw(self.screen)
            pygame.display.flip()