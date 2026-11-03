import functools
import json
import os
import sys

APP_DIR_NAME = "2D Wargame"
MAPS_SUBDIR = "maps"

@functools.lru_cache(maxsize=None)
def documents_dir():
    """Папка «Документы» пользователя. На Windows спрашиваем у системы: она может быть перенесена
    (например, в OneDrive), и тогда простой путь ~/Documents окажется неверным.
    Результат кэшируется: ответ системы за время работы не меняется."""
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            # 5 = CSIDL_PERSONAL («Документы»)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")

_ready = set()      # пути, которые уже созданы в этом запуске

def _folder(subdir=None):
    """Папка игры или её подпапка. makedirs вызывается один раз на путь, а не на каждое обращение."""
    path = os.path.join(documents_dir(), APP_DIR_NAME)
    if subdir:
        path = os.path.join(path, subdir)
    if path not in _ready:
        os.makedirs(path, exist_ok=True)
        _ready.add(path)
    return path

def app_dir():
    """Папка игры Documents/2D Wargame; создаётся, если её ещё нет."""
    return _folder()

def read_json(name, subdir=None):
    """Содержимое json-файла или None (нет файла, битый файл, нет доступа)."""
    try:
        with open(os.path.join(_folder(subdir), name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

def write_json(name, data, subdir=None, indent=2):
    """Записывает json. Сначала пишем во временный файл, потом подменяем:
    если игра вылетит посреди записи, старый файл останется целым. indent=None: компактно
    (для карт). Возвращает True при успехе."""
    tmp = None
    try:
        path = os.path.join(_folder(subdir), name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            if indent is None:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            else:
                json.dump(data, f, ensure_ascii=False, indent=indent)
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError):
        if tmp is not None:
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False

def list_files(subdir=None, ext=".json"):
    """Имена файлов папки с нужным расширением, по алфавиту."""
    try:
        return sorted(n for n in os.listdir(_folder(subdir)) if n.lower().endswith(ext))
    except OSError:
        return []

def file_stat(name, subdir=None):
    """(время изменения, размер) файла или None, если его нет."""
    try:
        st = os.stat(os.path.join(_folder(subdir), name))
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None

def delete_file(name, subdir=None):
    """Удалить файл. True, если удалён."""
    try:
        os.remove(os.path.join(_folder(subdir), name))
        return True
    except OSError:
        return False