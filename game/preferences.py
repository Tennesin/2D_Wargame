"""game/preferences.py — пользовательские настройки, которые переживают смену сцен.
Сейчас только список допустимых архетипов вражеских танков."""
from ai import ARCHETYPES

LOCKED = ("universal",)      # эти архетипы нельзя выключить

class Preferences:
    def __init__(self):
        self._enabled = set(ARCHETYPES)          # по умолчанию включены все

    def is_locked(self, key):
        return key in LOCKED

    def is_enabled(self, key):
        return key in LOCKED or key in self._enabled

    def toggle(self, key):
        """Переключить архетип. Заблокированные и неизвестные ключи игнорируются."""
        if key in LOCKED or key not in ARCHETYPES:
            return
        if key in self._enabled:
            self._enabled.discard(key)
        else:
            self._enabled.add(key)

    def enabled_keys(self):
        """Множество включённых ключей (заблокированные входят всегда)."""
        return {key for key in ARCHETYPES if self.is_enabled(key)}