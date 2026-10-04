import pygame
import sys
import math


class Game:
    def __init__(self):
        # Инициализация Pygame
        pygame.init()

        # Настройки экрана
        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Top-Down Танк (Физика массы и привода башни)")
        self.clock = pygame.time.Clock()

        # Цвета
        self.BG_COLOR = (120, 170, 120)
        self.TRACK_COLOR = (45, 45, 45)
        self.HULL_COLOR = (85, 107, 47)
        self.TURRET_COLOR = (107, 142, 35)
        self.GUN_COLOR = (100, 100, 100)
        self.HATCH_COLOR = (60, 80, 30)

        # --- Параметры движения ---
        self.tank_x = float(self.width // 2)
        self.tank_y = float(self.height // 2)

        self.hull_angle = 0.0  # Угол корпуса
        self.turret_angle = 0.0  # Угол башни

        # Скорости движения (пикселей/сек)
        self.forward_speed = 110.0  # Движение вперед
        self.backward_speed = 55.0  # Движение назад (в 2 раза медленнее)
        self.turn_speed_penalty = 0.6  # Коэффициент скорости при одновременном повороте (60%)

        # Угловые скорости (градусов/сек)
        self.hull_rotation_speed = 45.0  # Скорость поворота корпуса
        self.turret_rotation_speed = 45.0  # Собственная скорость привода башни

        # Размеры поверхностей
        self.surface_size = (200, 200)

        self.hull_surface = self.create_hull_surface()
        self.turret_surface = self.create_turret_surface()

    def create_hull_surface(self):
        """Отрисовка ходовой части и корпуса."""
        surface = pygame.Surface(self.surface_size, pygame.SRCALPHA)
        cx, cy = self.surface_size[0] // 2, self.surface_size[1] // 2

        pygame.draw.rect(surface, self.TRACK_COLOR, (cx - 45, cy - 55, 20, 110))
        pygame.draw.rect(surface, self.TRACK_COLOR, (cx + 25, cy - 55, 20, 110))

        for track_y in range(cy - 50, cy + 55, 10):
            pygame.draw.line(surface, (20, 20, 20), (cx - 45, track_y), (cx - 26, track_y), 2)
            pygame.draw.line(surface, (20, 20, 20), (cx + 25, track_y), (cx + 44, track_y), 2)

        pygame.draw.rect(surface, self.HULL_COLOR, (cx - 30, cy - 50, 60, 100))
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
        pygame.draw.polygon(surface, (50, 70, 20), turret_points, 2)

        pygame.draw.circle(surface, self.HATCH_COLOR, (cx, cy + 5), 8)
        return surface

    def handle_input(self, dt):
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()

        # --- 1. Вращение корпуса ---
        delta_hull = 0.0
        is_turning = False

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            delta_hull -= self.hull_rotation_speed * dt
            is_turning = True
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            delta_hull += self.hull_rotation_speed * dt
            is_turning = True

        self.hull_angle = (self.hull_angle + delta_hull) % 360

        # Корпус увлекает башню за собой в любом случае
        self.turret_angle = (self.turret_angle + delta_hull) % 360

        # --- 2. Движение танка с учетом замедления ---
        move_dir = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move_dir += 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move_dir -= 1

        if move_dir != 0:
            # Выбираем баcontent базовую скорость (вперед или назад)
            base_speed = self.forward_speed if move_dir > 0 else self.backward_speed

            # Применяем штраф скорости, если танк одновременно поворачивает
            current_speed = base_speed * (self.turn_speed_penalty if is_turning else 1.0)

            rad = math.radians(self.hull_angle)
            self.tank_x += math.sin(rad) * current_speed * dt * move_dir
            self.tank_y -= math.cos(rad) * current_speed * dt * move_dir

        # --- 3. Поворот механизма башни к курсору ---
        if mouse_buttons[0]:  # Зажата ЛКМ
            mx, my = pygame.mouse.get_pos()

            dx = mx - self.tank_x
            dy = my - self.tank_y

            target_angle = math.degrees(math.atan2(dy, dx)) + 90

            # Вычисляем разницу между текущим углом башни и целевым
            angle_diff = (target_angle - self.turret_angle + 180) % 360 - 180

            # Привод башни добавляет до 45°/сек работы собственного мотора
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

        # Отрисовка корпуса
        rotated_hull = pygame.transform.rotate(self.hull_surface, -self.hull_angle)
        hull_rect = rotated_hull.get_rect(center=(int(self.tank_x), int(self.tank_y)))
        self.screen.blit(rotated_hull, hull_rect.topleft)

        # Отрисовка башни
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