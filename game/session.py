"""game/session.py — данные, которые переживают смену сцен (сейчас: настройки танка)."""
from vehicles import TankSpec, TANK_PARAMS

class Session:
    def __init__(self):
        # значения ползунков конструктора: {ключ: число}; стартуем со значений по умолчанию
        self.tank_values = {key: p.default for key, p in TANK_PARAMS.items()}

    def tank_spec(self):
        """Спецификация танка по текущим значениям."""
        return TankSpec.from_values(self.tank_values)