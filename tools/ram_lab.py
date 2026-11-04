"""tools/ram_lab.py — лаборатория тарана: два танка, выбор массы, скорости, угла и точки удара.
Запуск из корня проекта: python -m tools.ram_lab          (окно)
                         python -m tools.ram_lab --table  (таблица без окна)
Управление в окне:
  1 2 3 — класс массы танка A (лёгкий, средний, тяжёлый);  4 5 6 — то же для B
  Вверх/Вниз — скорость A, км/ч;  Влево/Вправо — смещение точки удара (м)
  Q/E — поворот B на 15°;  Z/X — скорость B вдоль его курса
  H — A держит газ;  T — замедленная съёмка;  Space — пауза;  R — заново;  Esc — выход"""
import math
import sys
from types import SimpleNamespace

import pygame

from ai import Bot
from combat import resolve_ram_2d, RESTITUTION_TANK
from engine import (PX_PER_M, WORLD, Team, VehicleKind, VehicleCommand, FONT_SIZE_LABEL,
                    get_text, heading_vector, obb_contact)
from game.match.context import GameContext
from game.match.control.ram import RamController
from game.match.fleet import Fleet
from structures import WallManager
from vehicles import TankSpec, make_vehicle
from world import Camera, TerrainMap, build_empty

# (калибр, лоб, борт, корма, мощность): разные массы и классы корпуса
CLASSES = [("лёгкий", (75, 40, 30, 20, 2000)),
           ("средний", (125, 375, 85, 55, 1650)),
           ("тяжёлый", (150, 500, 375, 250, 800))]
START_DIST_PX = 1800.0       # A стартует на таком расстоянии слева от B
SLOW_K = 0.2

class _Null:
    """Заглушка для notifier и match_stats: любые вызовы ничего не делают."""
    def __getattr__(self, name):
        return lambda *a, **k: None

def _make(index, team, color=(200, 40, 40)):
    return make_vehicle(VehicleKind.MBT, TankSpec(*CLASSES[index][1]), team=team, team_color=color)

class Lab:
    def __init__(self, size):
        WORLD.set_size(250, 250)
        self.terrain = TerrainMap(build_empty("lab", 250, 250))
        self.walls = WallManager()
        self.cam = Camera(*size)
        self.cam.set_zoom(0.2)
        self.cam.center_on(0.0, 0.0)
        self.class_a, self.class_b = 1, 1
        self.speed_a, self.speed_b = 30.0, 0.0
        self.lateral, self.angle_b = 0.0, 0.0
        self.hold, self.paused, self.slow = False, False, False
        self.reset()

    def reset(self):
        self.a = _make(self.class_a, Team.PLAYER)
        self.b = _make(self.class_b, Team.BOTS, (200, 60, 60))
        self.a.x, self.a.y = -START_DIST_PX, self.lateral * PX_PER_M
        self.a.hull_angle, self.a.speed_kmh = 90.0, self.speed_a
        self.b.x = self.b.y = 0.0
        self.b.hull_angle, self.b.speed_kmh = self.angle_b % 360.0, self.speed_b
        self.fleet = Fleet(self.a)
        self.fleet.bots = [Bot(self.b, None)]
        self.ctx = GameContext(
            camera=self.cam, terrain=self.terrain, walls=self.walls, fleet=self.fleet,
            effects=_Null(), targets=None, notifier=_Null(),
            settings=SimpleNamespace(rock_hurts_tank=False, friendly_fire=True), match_stats=_Null())
        self.ram = RamController(self.ctx)

    # ---------- ввод ----------
    def key(self, k):
        """False: выйти."""
        if k == pygame.K_ESCAPE:
            return False
        if k == pygame.K_SPACE:
            self.paused = not self.paused
            return True
        if k == pygame.K_t:
            self.slow = not self.slow
            return True
        if k == pygame.K_h:
            self.hold = not self.hold
        elif pygame.K_1 <= k <= pygame.K_3:
            self.class_a = k - pygame.K_1
        elif pygame.K_4 <= k <= pygame.K_6:
            self.class_b = k - pygame.K_4
        elif k == pygame.K_LEFT:
            self.lateral -= 0.5
        elif k == pygame.K_RIGHT:
            self.lateral += 0.5
        elif k == pygame.K_UP:
            self.speed_a += 5.0
        elif k == pygame.K_DOWN:
            self.speed_a = max(0.0, self.speed_a - 5.0)
        elif k == pygame.K_q:
            self.angle_b -= 15.0
        elif k == pygame.K_e:
            self.angle_b += 15.0
        elif k == pygame.K_z:
            self.speed_b -= 5.0
        elif k == pygame.K_x:
            self.speed_b += 5.0
        elif k != pygame.K_r:
            return True
        self.reset()
        return True

    # ---------- кадр ----------
    def step(self, dt):
        for v in self.fleet.vehicles:                        # как в Match: сначала боты, потом игрок
            throttle = 1.0 if (self.hold and v is self.a) else 0.0
            self.ctx.step_vehicle(v, VehicleCommand(throttle=throttle), dt)
        self.ram.update(dt)

    def _hull(self, screen, v, color):
        cx, cy, hw, hl, ang = v.hull_obb()
        fx, fy = heading_vector(ang)
        rx, ry = -fy, fx
        pts = [self.cam.world_to_screen(cx + rx * sx * hw + fx * sy * hl, cy + ry * sx * hw + fy * sy * hl)
               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        pygame.draw.polygon(screen, color, pts, 2)
        c = self.cam.world_to_screen(cx, cy)
        pygame.draw.line(screen, color, c, self.cam.world_to_screen(cx + fx * hl, cy + fy * hl), 4)
        vx, vy = v.velocity_px()
        pygame.draw.line(screen, (240, 240, 240), c, self.cam.world_to_screen(cx + vx * 0.5, cy + vy * 0.5), 1)

    def draw(self, screen):
        screen.fill((36, 40, 46))
        self._hull(screen, self.b, (210, 80, 70))
        self._hull(screen, self.a, (80, 150, 230))
        last = self.ram.last
        if last is not None:
            sx, sy = self.cam.world_to_screen(last["x"], last["y"])
            pygame.draw.circle(screen, (255, 70, 60), (round(sx), round(sy)), 7, 2)
            pygame.draw.line(screen, (255, 220, 60), (sx, sy), (sx + last["nx"] * 50, sy + last["ny"] * 50), 2)

        lines = [
            "1-3 / 4-6 класс A / B | Вверх/Вниз скорость A | Влево/Вправо точка удара | Q/E угол B | "
            "Z/X скорость B | H газ | T замедление | R заново",
            f"A: {CLASSES[self.class_a][0]}  {self.a.mass_t:.1f} т  I={self.a.inertia_t_m2:.0f}  "
            f"v0={self.speed_a:.0f} км/ч  смещение {self.lateral:+.1f} м",
            f"B: {CLASSES[self.class_b][0]}  {self.b.mass_t:.1f} т  I={self.b.inertia_t_m2:.0f}  "
            f"угол {self.angle_b % 360:.0f}°  v0={self.speed_b:.0f} км/ч",
            f"A: v={self.a.speed_kmh:.1f} км/ч  push={math.hypot(self.a.push_vx, self.a.push_vy) / PX_PER_M:.1f} м/с  "
            f"hull_rate={self.a.hull_rate:.0f}°/с  hp={self.a.hp:.0f}",
            f"B: v={self.b.speed_kmh:.1f} км/ч  push={math.hypot(self.b.push_vx, self.b.push_vy) / PX_PER_M:.1f} м/с  "
            f"hull_rate={self.b.hull_rate:.0f}°/с  hp={self.b.hp:.0f}",
        ]
        if last is not None:
            lines += [
                f"Удар: сближение {last['closing']:.1f} м/с  e={last['e']:.2f}  jn={last['jn']:.0f}  jt={last['jt']:.0f}",
                f"dv A/B: {last['dv_a']:.1f}/{last['dv_b']:.1f} м/с   dw A/B: {last['dw_a']:.0f}/{last['dw_b']:.0f} °/с",
                f"урон A/B: {last['dmg_a']:.0f}/{last['dmg_b']:.0f}   грани: {last['zone_a']}/{last['zone_b']}",
            ]
        for i, text in enumerate(lines):
            screen.blit(get_text(text, FONT_SIZE_LABEL, (230, 230, 230)), (10, 10 + i * 20))

# ==========================================
# ТАБЛИЦА БЕЗ ОКНА
# ==========================================
def table(speed_kmh=30.0):
    """A едет в борт стоящему B (углы 90° и 0°). Строки: смещение точки удара вдоль борта B."""
    WORLD.set_size(250, 250)
    pairs = ((1, 1), (2, 0), (0, 2))
    for ia, ib in pairs:
        a, b = _make(ia, Team.PLAYER), _make(ib, Team.BOTS)
        sa, sb = a.spec, b.spec
        print(f"\nA: {CLASSES[ia][0]} {a.mass_t:.1f} т (I={a.inertia_t_m2:.0f}), "
              f"B: {CLASSES[ib][0]} {b.mass_t:.1f} т (I={b.inertia_t_m2:.0f}), v={speed_kmh:.0f} км/ч")
        print(f"{'смещ,м':>7} {'jn':>8} {'dvA':>6} {'dvB':>6} {'dwA°/с':>8} {'dwB°/с':>8} {'e':>5}")
        for lat in (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0):
            ax = -sb.COLLISION_HALF_W_PX - sa.COLLISION_HALF_L_PX - 5.0
            ay = lat * PX_PER_M
            a_obb = (ax, ay, sa.COLLISION_HALF_W_PX + 8.0, sa.COLLISION_HALF_L_PX + 8.0, 90.0)
            b_obb = (0.0, 0.0, sb.COLLISION_HALF_W_PX, sb.COLLISION_HALF_L_PX, 0.0)
            c = obb_contact(a_obb, b_obb)
            if c is None:
                print(f"{lat:7.1f}   нет контакта")
                continue
            r1 = ((c.px - ax) / PX_PER_M, (c.py - ay) / PX_PER_M)
            r2 = (c.px / PX_PER_M, c.py / PX_PER_M)
            res = resolve_ram_2d(a.mass_t, a.inertia_t_m2, (speed_kmh / 3.6, 0.0), 0.0, r1,
                                 b.mass_t, b.inertia_t_m2, (0.0, 0.0), 0.0, r2,
                                 (c.nx, c.ny), RESTITUTION_TANK)
            if res is None:
                print(f"{lat:7.1f}   нет сближения")
                continue
            print(f"{lat:7.1f} {res.jn:8.0f} {res.jn / a.mass_t:6.2f} {res.jn / b.mass_t:6.2f} "
                  f"{math.degrees(res.dw1):8.1f} {math.degrees(res.dw2):8.1f} {res.restitution:5.2f}")

def main():
    if "--table" in sys.argv:
        table()
        return
    pygame.init()
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption("ram_lab")
    clock = pygame.time.Clock()
    lab = Lab(screen.get_size())
    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and not lab.key(e.key):
                running = False
        screen = pygame.display.get_surface()
        lab.cam.resize(*screen.get_size())
        if not lab.paused:
            lab.step(dt * (SLOW_K if lab.slow else 1.0))
        lab.draw(screen)
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()