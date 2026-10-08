"""engine/cache.py — кэш с вытеснением давно не использованных записей."""
from collections import OrderedDict

class LRUCache:
    """Кэш с вытеснением давно не использованных записей. limit=None: без ограничения
    (тогда размер можно подрезать вручную через trim(limit))."""

    def __init__(self, limit=None):
        self.limit = limit
        self._data = OrderedDict()

    def get(self, key):
        """Значение или None; найденная запись становится «свежей»."""
        value = self._data.get(key)
        if value is not None:
            self._data.move_to_end(key)
        return value

    def put(self, key, value):
        self._data[key] = value
        self._data.move_to_end(key)
        self.trim()

    def get_or_build(self, key, builder):
        """Взять из кэша или вызвать builder() и сохранить результат."""
        value = self.get(key)
        if value is None:
            value = builder()
            self.put(key, value)
        return value

    def trim(self, limit=None):
        """Выбросить самые старые записи, пока их больше limit (по умолчанию self.limit)."""
        if limit is None:
            limit = self.limit
        if limit is None:
            return
        while len(self._data) > limit:
            self._data.popitem(last=False)

    def clear(self):
        self._data.clear()

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data