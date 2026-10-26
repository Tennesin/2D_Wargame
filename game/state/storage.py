"""game/state/storage.py — папка игры в Documents и чтение/запись json-файлов (в том числе в подпапках)."""
import json
import os
import sys

APP_DIR_NAME = "2D Wargame"
MAPS_SUBDIR = "maps"

def documents_dir():
    """Папка «Документы» пользователя. На Windows спрашиваем у системы: она может быть перенесена
    (например, в OneDrive), и тогда простой путь ~/Documents окажется неверным."""
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

def app_dir():
    """Папка игры Documents/2D Wargame; создаётся, если её ещё нет."""
    path = os.path.join(documents_dir(), APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path

def _folder(subdir=None):
    """Папка игры или её подпапка (создаётся при необходимости)."""
    path = app_dir() if not subdir else os.path.join(app_dir(), subdir)
    os.makedirs(path, exist_ok=True)
    return path

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
    try:
        path = os.path.join(_folder(subdir), name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            if indent is None:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            else:
                json.dump(data, f, ensure_ascii=False, indent=indent)
        os.replace(tmp, path)
        return True
    except OSError:
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