"""game/state/session.py — данные, которые переживают смену сцен: выбранный тип техники и настройки каждого типа."""
import random

from engine import VehicleKind, WORLD_DEFAULT_M
from vehicles import VEHICLE_TYPES, default_tuning, FRONT_SCREEN, NOSE_FLAT, SPECIAL_HEAT
from .preferences import Preferences
from .settings import GameSettings
from .stats import Career
from world import build_natural
from .maps import MapStore

class Session:
    def __init__(self):
        self.kind = VehicleKind.MBT
        self.map_w_m = WORLD_DEFAULT_M   # размер карты по X, м (задаётся в «Новой игре»)
        self.map_h_m = WORLD_DEFAULT_M   # по Y, м
        # значения ползунков для КАЖДОГО типа отдельно: при переключении кнопок настройки не теряются
        self.values = {kind: self._defaults(t) for kind, t in VEHICLE_TYPES.items() if t.playable}
        self.prefs = Preferences()       # настройки меню: живут, пока открыто приложение
        self.settings = GameSettings()   # настройки меню «Настройки»
        self.career = Career()           # накопленная статистика и рекорды (файл stats.json)
        self.maps = MapStore()           # хранилище карт (папка maps/), список кэшируется
        self.map_file = None             # None: случайная карта по сиду; иначе имя файла в maps/
        self.map_seed = self._roll_seed()
        self._seed_spent = False         # True: партия на этом сиде уже сыграна, нужен новый

    @staticmethod
    def _defaults(vtype):
        values = {key: p.default for key, p in vtype.params.items()}
        dmg, pen = default_tuning(values["gun_caliber_mm"], vtype.gun_profile)
        values["gun_damage"] = dmg
        values["gun_penetration"] = pen
        values["special_ammo"] = SPECIAL_HEAT
        values["front_screen_mm"] = FRONT_SCREEN.default
        values["front_nose"] = NOSE_FLAT
        return values

    def spec(self):
        """Спецификация выбранной техники по текущим значениям."""
        t = VEHICLE_TYPES[self.kind]
        return t.spec_cls.from_values(self.values[self.kind])

    @staticmethod
    def _roll_seed():
        return random.randrange(1, 1_000_000)

    def fresh_seed(self):
        """Новый сид для превью случайной карты."""
        self.map_seed = self._roll_seed()
        self._seed_spent = False

    def prepare_seed(self):
        """При открытии «Новой игры»: если на прошлом сиде уже играли, берём новый."""
        if self._seed_spent:
            self.fresh_seed()

    def make_map(self, seed=None):
        """Карта для новой партии: выбранный файл или случайная по map_seed.
        seed: принудительный сид (отладка), действует только для случайной карты."""
        if self.map_file is not None:
            data = self.maps.load(self.map_file)
            if data is not None:
                return data
            self.map_file = None                      # файл пропал или повреждён: вернёмся к случайной
        if seed is not None:
            self.map_seed = seed
        self._seed_spent = True
        return build_natural(self.map_seed, self.map_w_m, self.map_h_m)