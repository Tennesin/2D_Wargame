import pygame
import sys
import math

import tank_config


class Game:
    def __init__(self):
        pygame.init()

        tank_config.print_tank_specs()

        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Top-Down Танк (Исправленная геометрия брони)")
        self.clock = pygame.time.Clock()

        # Палитра
        self.BG_COLOR = (120, 170, 120)
        self.TRACK_COLOR = (45, 45, 45)

        self.FRONT_ARMOR_COLOR = (115, 140, 60)  # Лоб
        self.SIDE_ARMOR_COLOR = (85, 107, 47)  # Борта
        self.REAR_ARMOR_COLOR = (65, 80, 35)  # Корма
        self.DECK_COLOR = (95, 118, 52)  # Палуба
        self.ARMOR_OUTLINE_COLOR = (35, 48, 18)  # Стыки
        self.ENGINE_GRILL_COLOR = (30, 40, 20)  # Жалюзи МТО

        self.TURRET_COLOR = (120, 150, 40)
        self.GUN_COLOR = (100, 100, 100)
        self.HATCH_COLOR = (60, 80, 30)

        # Позиция
        self.tank_x = float(self.width // 2)
        self.tank_y = float(self.height // 2)

        self.hull_angle = 0.0
        self.turret_angle = 0.0

        # Динамика из конфигурации
        self.forward_speed = tank_config.FORWARD_SPEED_PX
        self.backward_speed = tank_config.BACKWARD_SPEED_PX
        self.turn_speed_penalty = tank_config.TURN_SPEED_PENALTY

        self.hull_rotation_speed = tank_config.HULL_ROTATION_SPEED
        self.turret_rotation_speed = tank_config.TURRET_ROTATION_SPEED

        self.surface_size = (200, 200)

        self.hull_surface = self.create_hull_surface()
        self.turret_surface = self.create_turret_surface()

    def create_hull_surface(self):
        """
        Отрисовка корпуса с продленными бортами и зажатой между ними кормой.
        """
        surface = pygame.Surface(self.surface_size, pygame.SRCALPHA)
        cx, cy = self.surface_size[0] // 2, self.surface_size[1] // 2

        # 1. Гусеницы
        pygame.draw.rect(surface, self.TRACK_COLOR, (cx - 45, cy - 55, 20, 110))
        pygame.draw.rect(surface, self.TRACK_COLOR, (cx + 25, cy - 55, 20, 110))

        for track_y in range(cy - 50, cy + 55, 10):
            pygame.draw.line(surface, (20, 20, 20), (cx - 45, track_y), (cx - 26, track_y), 2)
            pygame.draw.line(surface, (20, 20, 20), (cx + 25, track_y), (cx + 44, track_y), 2)

        # 2. Центральная палуба
        pygame.draw.rect(surface, self.DECK_COLOR, (cx - 20, cy - 25, 40, 50))

        # 3. Лобовая броня (без изменений)
        front_armor_points = [
            (cx - 30, cy - 25),
            (cx - 24, cy - 50),
            (cx + 24, cy - 50),
            (cx + 30, cy - 25)
        ]
        pygame.draw.polygon(surface, self.FRONT_ARMOR_COLOR, front_armor_points)
        pygame.draw.polygon(surface, self.ARMOR_OUTLINE_COLOR, front_armor_points, 2)

        # 4. Бортовая броня (ПРОДЛЕНА до самого конца корпуса: высота 75px)
        # Левый борт
        left_side_rect = (cx - 30, cy - 25, 10, 75)
        pygame.draw.rect(surface, self.SIDE_ARMOR_COLOR, left_side_rect)
        pygame.draw.rect(surface, self.ARMOR_OUTLINE_COLOR, left_side_rect, 2)

        # Правый борт
        right_side_rect = (cx + 20, cy - 25, 10, 75)
        pygame.draw.rect(surface, self.SIDE_ARMOR_COLOR, right_side_rect)
        pygame.draw.rect(surface, self.ARMOR_OUTLINE_COLOR, right_side_rect, 2)

        # 5. Кормовая броня (ЗАЖАТА МЕЖДУ БОРТАМИ: ширина 40px)
        rear_armor_rect = (cx - 20, cy + 25, 40, 25)
        pygame.draw.rect(surface, self.REAR_ARMOR_COLOR, rear_armor_rect)
        pygame.draw.rect(surface, self.ARMOR_OUTLINE_COLOR, rear_armor_rect, 2)

        # Решетки МТО (вписаны в новые границы кормы)
        pygame.draw.rect(surface, self.ENGINE_GRILL_COLOR, (cx - 15, cy + 30, 12, 12))
        pygame.draw.rect(surface, self.ENGINE_GRILL_COLOR, (cx + 3, cy + 30, 12, 12))
        for y_line in range(cy + 33, cy + 40, 3):
            pygame.draw.line(surface, (15, 20, 10), (cx - 14, y_line), (cx - 4, y_line), 1)
            pygame.draw.line(surface, (15, 20, 10), (cx + 4, y_line), (cx + 14, y_line), 1)

        return surface

    def create_turret_surface(self):
        """Отрисовка орудия и башни."""
        surface = pygame.Surface(self.surface_size, pygame.SRCALPHA)
        cx, cy = self.surface_size[0] // 2, self.surface_size[1] // 2

        pygame.draw.rect(surface, self.GUN_COLOR, (cx - 5, cy - 90, 10, 70))
        pygame.draw.rect(surface, (70, 70, 70), (cx - 7, cy - 95, 14, 15))

        turret_points = [
            (cx - 16, cy - 25),
            (cx + 16, cy - 25),
            (cx + 28, cy + 25),
            (cx - 28, cy + 25)
        ]
        pygame.draw.polygon(surface, self.TURRET_COLOR, turret_points)
        pygame.draw.polygon(surface, self.ARMOR_OUTLINE_COLOR, turret_points, 2)

        pygame.draw.circle(surface, self.HATCH_COLOR, (cx, cy + 5), 8)
        pygame.draw.circle(surface, self.ARMOR_OUTLINE_COLOR, (cx, cy + 5), 8, 1)

        return surface

    def handle_input(self, dt):
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()

        delta_hull = 0.0
        is_turning = False

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            delta_hull -= self.hull_rotation_speed * dt
            is_turning = True
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            delta_hull += self.hull_rotation_speed * dt
            is_turning = True

        self.hull_angle = (self.hull_angle + delta_hull) % 360
        self.turret_angle = (self.turret_angle + delta_hull) % 360

        move_dir = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move_dir += 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move_dir -= 1

        if move_dir != 0:
            base_speed = self.forward_speed if move_dir > 0 else self.backward_speed
            current_speed = base_speed * (self.turn_speed_penalty if is_turning else 1.0)

            rad = math.radians(self.hull_angle)
            self.tank_x += math.sin(rad) * current_speed * dt * move_dir
            self.tank_y -= math.cos(rad) * current_speed * dt * move_dir

        if mouse_buttons[0]:
            mx, my = pygame.mouse.get_pos()

            dx = mx - self.tank_x
            dy = my - self.tank_y

            target_angle = math.degrees(math.atan2(dy, dx)) + 90
            angle_diff = (target_angle - self.turret_angle + 180) % 360 - 180

            max_turret_rotation = self.turret_rotation_speed * dt

            if abs(angle_diff) <= max_turret_rotation:
                self.turret_angle = target_angle
            else:
                self.turret_angle += math.copysign(max_turret_rotation, angle_diff)

            self.turret_angle %= 360

    def check_boundaries(self):
        margin = 95
        self.tank_x = max(margin, min(self.width - margin, self.tank_x))
        self.tank_y = max(margin, min(self.height - margin, self.tank_y))

    def draw(self):
        self.screen.fill(self.BG_COLOR)

        rotated_hull = pygame.transform.rotate(self.hull_surface, -self.hull_angle)
        hull_rect = rotated_hull.get_rect(center=(int(self.tank_x), int(self.tank_y)))
        self.screen.blit(rotated_hull, hull_rect.topleft)

        rotated_turret = pygame.transform.rotate(self.turret_surface, -self.turret_angle)
        turret_rect = rotated_turret.get_rect(center=(int(self.tank_x), int(self.tank_y)))
        self.screen.blit(rotated_turret, turret_rect.topleft)

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            self.handle_input(dt)
            self.check_boundaries()
            self.draw()

        pygame.quit()
        sys.exit()