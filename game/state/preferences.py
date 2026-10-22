"""game/state/preferences.py — пользовательские настройки, которые переживают смену сцен.
Сейчас только список допустимых архетипов вражеских танков."""
from ai import ARCHETYPES

class Preferences:
    def __init__(self):
        self._enabled = set(ARCHETYPES)

    def is_enabled(self, key):
        return key in self._enabled

    def is_locked(self, key):
        """Нельзя отключить: это последний включённый архетип."""
        return key in self._enabled and len(self._enabled) == 1

    def toggle(self, key):
        """Переключить архетип. Неизвестные ключи игнорируются; последний включённый не отключается."""
        if key not in ARCHETYPES:
            return
        if key in self._enabled:
            if len(self._enabled) > 1:
                self._enabled.discard(key)
        else:
            self._enabled.add(key)

    def enabled_keys(self):
        """Множество включённых ключей (всегда не пустое)."""
        return set(self._enabled)