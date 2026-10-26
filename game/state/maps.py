"""game/state/maps.py — хранилище карт: список, загрузка, сохранение, удаление.
Файлы лежат в Documents/2D Wargame/maps/, одна карта = один json."""
import re
from typing import NamedTuple

from world import MapData
from . import storage

SUBDIR = storage.MAPS_SUBDIR
MAX_STEM = 60
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

def safe_stem(name):
    """Имя файла без расширения: без запрещённых в Windows символов и зарезервированных имён."""
    stem = _BAD_CHARS.sub("", str(name)).strip(" .")[:MAX_STEM].strip(" .")
    if not stem:
        return "Карта"
    if stem.lower() in _RESERVED:
        return stem + "_"
    return stem

class MapInfo(NamedTuple):
    file: str
    name: str
    width_m: int
    length_m: int
    mode: str

class MapStore:
    def __init__(self):
        self._info = {}            # файл -> ((mtime, size), MapInfo или None)

    # ---------- список ----------
    def list(self):
        """Все читаемые карты по имени. Файл разбирается заново, только если он изменился."""
        fresh, result = {}, []
        for file in storage.list_files(SUBDIR):
            stat = storage.file_stat(file, SUBDIR)
            if stat is None:
                continue
            cached = self._info.get(file)
            if cached is not None and cached[0] == stat:
                info = cached[1]
            else:
                md = self.load(file)
                info = None if md is None else MapInfo(file, md.name, md.width_m, md.length_m, md.mode)
            fresh[file] = (stat, info)
            if info is not None:
                result.append(info)
        self._info = fresh
        result.sort(key=lambda i: i.name.lower())
        return result

    # ---------- файлы ----------
    def exists(self, file):
        return storage.file_stat(file, SUBDIR) is not None

    def file_for_name(self, name):
        """Файл, в который попадёт карта с таким именем (для вопроса «перезаписать?»)."""
        return safe_stem(name) + ".json"

    def unique_file(self, name):
        """Свободное имя файла: «Имя.json», «Имя (2).json», ..."""
        stem = safe_stem(name)
        file, n = stem + ".json", 2
        while self.exists(file):
            file = f"{stem} ({n}).json"
            n += 1
        return file

    def load(self, file):
        """MapData или None (нет файла, битый файл, неизвестная версия)."""
        md = MapData.from_dict(storage.read_json(file, SUBDIR))
        if md is not None:
            md.file = file
        return md

    def save(self, md, file=None):
        """Сохранить карту. file=None: новый файл со свободным именем; иначе перезапись этого файла.
        Возвращает имя файла или None при ошибке записи."""
        if file is None:
            file = self.unique_file(md.name)
        if not storage.write_json(file, md.to_dict(), SUBDIR, indent=None):
            return None
        md.file = file
        self._info.pop(file, None)
        return file

    def delete(self, file):
        self._info.pop(file, None)
        return storage.delete_file(file, SUBDIR)