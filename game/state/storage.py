"""game/state/storage.py — папка игры в Documents и чтение/запись json-файлов."""
import json
import os
import sys

APP_DIR_NAME = "2D Wargame"

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

def read_json(name):
    """Содержимое json-файла из папки игры или None (нет файла, битый файл, нет доступа)."""
    try:
        with open(os.path.join(app_dir(), name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

def write_json(name, data):
    """Записывает json в папку игры. Сначала пишем во временный файл, потом подменяем:
    если игра вылетит посреди записи, старый файл останется целым. Возвращает True при успехе."""
    try:
        path = os.path.join(app_dir(), name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except OSError:
        return False