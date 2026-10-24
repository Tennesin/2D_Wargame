"""game/state/session.py — данные, которые переживают смену сцен: выбранный тип техники и настройки каждого типа."""
from engine import VehicleKind, WORLD_DEFAULT_M
from vehicles import VEHICLE_TYPES, default_tuning, FRONT_SCREEN, NOSE_FLAT, SPECIAL_HEAT
from .preferences import Preferences
from .settings import GameSettings

class Session:
    def __init__(self):
        self.kind = VehicleKind.MBT
        self.map_w_m = WORLD_DEFAULT_M   # размер карты по X, м (задаётся в «Новой игре»)
        self.map_h_m = WORLD_DEFAULT_M   # по Y, м
        # значения ползунков для КАЖДОГО типа отдельно: при переключении кнопок настройки не теряются
        self.values = {kind: self._defaults(t) for kind, t in VEHICLE_TYPES.items() if t.playable}
        self.prefs = Preferences()       # настройки меню: живут, пока открыто приложение
        self.settings = GameSettings()   # настройки меню «Настройки»

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