"""game.py — окно, главный цикл, связывание частей."""
import random

import pygame

from core import Camera, Tank, WorldGenerator, CHUNK_SIZE
from input_handler import InputHandler
from renderer import Renderer

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
        self.tank = Tank(0.0, 0.0)
        self.camera = Camera(*self.screen.get_size())
        self.input = InputHandler()
        self.renderer = Renderer(self.world)

    def _debug_lines(self):
        t = self.tank
        return [
            f"FPS: {self.clock.get_fps():.0f}",
            f"X: {t.x:.0f}  Y: {t.y:.0f}",
            f"Chunk: {int(t.x // CHUNK_SIZE)}, {int(t.y // CHUNK_SIZE)}",
            f"Grass: {self.world.grass_at(t.x, t.y):.2f}",
            f"Hull: {t.hull_angle:.0f}  Turret: {t.turret_angle:.0f}",
            f"Seed: {self.seed}",
        ]

    def run(self):
        while not self.input.quit_requested:
            dt = min(self.clock.tick(60) / 1000.0, self.MAX_DT)

            self.input.process_events()

            self.screen = pygame.display.get_surface()      # актуально после изменения размера окна
            w, h = self.screen.get_size()
            if w == 0 or h == 0:
                continue
            self.camera.resize(w, h)

            command = self.input.read_command(self.camera)
            self.tank.update(command, dt)
            self.camera.center_on(self.tank.x, self.tank.y)

            debug = self._debug_lines() if self.input.show_debug else None
            self.renderer.draw(self.screen, self.camera, self.tank, debug)
            pygame.display.flip()