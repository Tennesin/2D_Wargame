"""game/state/settings.py — игровые и технические настройки: меняются в меню «Настройки», живут всё время работы приложения.
Последние сохранённые значения лежат в Documents/2D Wargame/settings.json."""
from engine import Param, round_to
from . import storage

FPS_CHOICES = (30, 60, 90, 120, 144, 240)
ROUND_TIME = Param("Время раунда", "с", 20, 120, 45, 5)

SETTINGS_FILE = "settings.json"
FORMAT_VERSION = 1                                       # пригодится, если формат файла когда-нибудь изменится

class GameSettings:
    def __init__(self):
        self.fps_limit = 60                              # лимит кадров в секунду
        self.show_fps = False                            # счётчик FPS в бою без нажатия Tab
        self.rock_hurts_tank = False                     # урон самой технике от тарана камня
        self.friendly_fire = False                       # осколки по своим, урон при таране между ботами
        self.round_time_s = float(ROUND_TIME.default)    # время до закрытия раунда, с

        self._load()
        self._saved = self.to_dict()                     # то, что считается «сохранённым»

    # ---------- словарь <-> поля ----------
    def to_dict(self):
        return {
            "version": FORMAT_VERSION,
            "fps_limit": self.fps_limit,
            "show_fps": self.show_fps,
            "rock_hurts_tank": self.rock_hurts_tank,
            "friendly_fire": self.friendly_fire,
            "round_time_s": float(self.round_time_s),
        }

    def _load(self):
        """Читает файл. Каждое поле проверяется отдельно: испорченное или отсутствующее значение
        просто остаётся по умолчанию, остальные подхватываются."""
        data = storage.read_json(SETTINGS_FILE)
        if not isinstance(data, dict):
            return
        fps = data.get("fps_limit")
        if fps in FPS_CHOICES:
            self.fps_limit = fps
        for name in ("show_fps", "rock_hurts_tank", "friendly_fire"):
            value = data.get(name)
            if isinstance(value, bool):
                setattr(self, name, value)
        t = data.get("round_time_s")
        if isinstance(t, (int, float)) and not isinstance(t, bool):
            t = round_to(ROUND_TIME.fit(t), ROUND_TIME.step)       # под границы и шаг ползунка
            self.round_time_s = float(ROUND_TIME.fit(t))

    # ---------- сохранение ----------
    def is_saved(self):
        """Совпадают ли текущие настройки с теми, что сохранены (в файле)."""
        return self.to_dict() == self._saved

    def save(self):
        """Записывает текущие настройки в файл. Возвращает True при успехе."""
        data = self.to_dict()
        if storage.write_json(SETTINGS_FILE, data):
            self._saved = data
            return True
        return False