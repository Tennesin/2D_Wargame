"""tools/project_snapshot.py — снимок проекта 2D Wargame для передачи в чат.
Что делает:
  1. копирует все .py как .txt (с той же структурой папок) и картинки;
  2. пишет СКЕЛЕТ.txt: дерево проекта;
  3. пишет СКЕЛЕТ_ПРОДВИНУТЫЙ.txt: дерево со строками, классами и общей статистикой.
Запуск: python tools/project_snapshot.py"""
import ast
import os
import shutil

PROJECT_NAME = "2D Wargame"

# Куда складывать снимок. ВНИМАНИЕ: папка очищается при каждом запуске, поэтому
# указывай отдельную папку, в которой нет ничего нужного.
# По умолчанию: рядом с папкой проекта.
MAIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = r"d:\Akmal\Personal\AI developed Mini-games\2D_Wargame\temporary"

# Папки верхнего уровня, которые попадают в снимок (вложенные берутся автоматически)
ALLOWED_SUBDIRS = {"engine", "combat", "world", "vehicles", "structures",
                   "inputs", "ui", "game", "assets"}

# Папки, которые пропускаем на любой глубине
IGNORED_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "venv", ".venv"}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff")

# ==========================================
# ОБХОД ПРОЕКТА (один для всех частей скрипта)
# ==========================================

def walk_project():
    """Как os.walk, но с фильтром папок: на верхнем уровне только ALLOWED_SUBDIRS,
    на любом уровне без IGNORED_DIRS. Папки и файлы отсортированы."""
    for root, dirs, files in os.walk(MAIN_DIR):
        dirs[:] = sorted(d for d in dirs
                         if d not in IGNORED_DIRS and (root != MAIN_DIR or d in ALLOWED_SUBDIRS))
        yield root, dirs, sorted(files)

def is_python(name):
    return name.endswith(".py")

def is_image(name):
    return name.lower().endswith(IMAGE_EXTENSIONS)

# ==========================================
# АНАЛИЗ ФАЙЛОВ
# ==========================================

def analyze_python_file(filepath):
    """Возвращает (количество строк, список имён классов) для .py файла."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        loc = len(content.splitlines())
        tree = ast.parse(content, filename=filepath)
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        return loc, classes
    except Exception:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f), []
        except Exception:
            return 0, []

def get_file_size_str(path):
    size = os.path.getsize(path)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"

def collect_statistics():
    """Суммарно: (строки, классы, папки внутри проекта, картинки)."""
    total_loc = total_classes = total_dirs = total_images = 0
    for root, dirs, files in walk_project():
        total_dirs += len(dirs)
        for name in files:
            if is_python(name) and not skip_script(root, name):
                loc, classes = analyze_python_file(os.path.join(root, name))
                total_loc += loc
                total_classes += len(classes)
            elif is_image(name):
                total_images += 1
    return total_loc, total_classes, total_dirs, total_images

def skip_script(root, name):
    """Сам скрипт в снимок не включаем (на случай, если его положили в корень)."""
    return root == MAIN_DIR and name == os.path.basename(__file__)

# ==========================================
# 1. КОПИРОВАНИЕ ФАЙЛОВ
# ==========================================

def copy_files():
    # старый снимок удаляем целиком, чтобы не оставалось файлов от удалённых модулей
    # очищаем только содержимое папки, а саму папку не удаляем:
    # Windows не даёт удалить папку, если она открыта в Проводнике или редакторе
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for entry in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, entry)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                os.remove(path)
            except OSError:
                pass

    for root, _, files in walk_project():
        rel = os.path.relpath(root, MAIN_DIR)
        target_dir = OUTPUT_DIR if rel == "." else os.path.join(OUTPUT_DIR, rel)

        for name in files:
            if skip_script(root, name):
                continue
            src = os.path.join(root, name)

            if is_python(name):
                os.makedirs(target_dir, exist_ok=True)
                dst = os.path.join(target_dir, os.path.splitext(name)[0] + ".txt")
                with open(src, "r", encoding="utf-8") as f_in:
                    content = f_in.read()
                with open(dst, "w", encoding="utf-8") as f_out:
                    f_out.write(content)
                print(f"Создан: {dst}")
            elif is_image(name):
                os.makedirs(target_dir, exist_ok=True)
                dst = os.path.join(target_dir, name)
                shutil.copyfile(src, dst)
                print(f"Скопировано изображение: {dst}")

# ==========================================
# 2. ДЕРЕВО (СКЕЛЕТ)
# ==========================================

def build_tree(dir_path, prefix="", is_last=True, is_root=False, show_lines=False):
    """Псевдографическое дерево. show_lines=True: у .py файлов строки и классы,
    у картинок размер файла."""
    lines = []
    name = os.path.basename(dir_path) or dir_path
    if is_root:
        lines.append(f"{name}/")
    else:
        lines.append(f"{prefix}{'└── ' if is_last else '├── '}{name}/")

    subdirs, py_files, image_files = [], [], []
    try:
        for entry in os.listdir(dir_path):
            full = os.path.join(dir_path, entry)
            if os.path.isdir(full):
                if entry in IGNORED_DIRS:
                    continue
                if dir_path == MAIN_DIR and entry not in ALLOWED_SUBDIRS:
                    continue
                subdirs.append(entry)
            elif os.path.isfile(full):
                if is_python(entry) and not skip_script(dir_path, entry):
                    py_files.append(entry)
                elif is_image(entry):
                    image_files.append(entry)
    except PermissionError:
        pass

    subdirs.sort()
    py_files.sort()
    image_files.sort()

    child_prefix = "" if is_root else prefix + ("    " if is_last else "│   ")
    items = subdirs + py_files + image_files          # сначала папки, потом .py, потом картинки

    for i, item in enumerate(items):
        last = i == len(items) - 1
        if item in subdirs:
            lines.extend(build_tree(os.path.join(dir_path, item), child_prefix, last,
                                    is_root=False, show_lines=show_lines))
            continue

        connector = "└── " if last else "├── "
        path = os.path.join(dir_path, item)
        if not show_lines:
            lines.append(f"{child_prefix}{connector}{item}")
        elif item in py_files:
            loc, classes = analyze_python_file(path)
            classes_str = f" | Классы: {', '.join(classes)}" if classes else ""
            lines.append(f"{child_prefix}{connector}{item} [{loc} стр.{classes_str}]")
        else:
            lines.append(f"{child_prefix}{connector}{item} [{get_file_size_str(path)}]")
    return lines

def write_skeletons():
    # обычный СКЕЛЕТ
    path = os.path.join(OUTPUT_DIR, "СКЕЛЕТ.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(build_tree(MAIN_DIR, is_root=True)) + "\n")
    print(f"Файл-скелет создан: {path}")

    # СКЕЛЕТ_ПРОДВИНУТЫЙ со статистикой в начале
    loc, classes, dirs, images = collect_statistics()
    header = [
        f"ПРОЕКТ: {PROJECT_NAME}",
        "СУММАРНЫЕ ДАННЫЕ:",
        f"Всего строк: {loc}",
        f"Всего классов: {classes}",
        f"Внутренних папок: {dirs}",
        f"Количество изображений: {images}",
        "",
    ]
    path = os.path.join(OUTPUT_DIR, "СКЕЛЕТ_ПРОДВИНУТЫЙ.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(header + build_tree(MAIN_DIR, is_root=True, show_lines=True)) + "\n")
    print(f"Подробный файл-скелет создан: {path}")

def main():
    print(f"Проект: {MAIN_DIR}")
    print(f"Снимок: {OUTPUT_DIR}")
    copy_files()
    write_skeletons()
    print("Готово.")

if __name__ == "__main__":
    main()