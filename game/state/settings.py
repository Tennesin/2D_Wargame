"""game/state/settings.py — игровые и технические настройки: меняются в меню «Настройки», живут всё время работы приложения."""
from engine import Param

FPS_CHOICES = (30, 60, 90, 120, 144, 240)
ROUND_TIME = Param("Время раунда", "с", 20, 120, 45, 5)

class GameSettings:
    def __init__(self):
        self.fps_limit = 60                              # лимит кадров в секунду
        self.show_fps = False                            # счётчик FPS в бою без нажатия Tab
        self.rock_hurts_tank = False                     # урон самой технике от тарана камня
        self.friendly_fire = False                       # осколки по своим, урон при таране между ботами
        self.round_time_s = float(ROUND_TIME.default)    # время до закрытия раунда, с