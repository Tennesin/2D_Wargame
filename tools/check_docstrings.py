"""tools/check_docstrings.py — первая строка docstring должна начинаться с пути от корня проекта.
Запуск: python tools/check_docstrings.py (отчёт) или python tools/check_docstrings.py --fix"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".idea", ".git", "__pycache__", "tools", "tests", "venv", ".venv"}
SKIP_FILES = {"__init__.py", "main.py"}
HEAD = re.compile(r'^"""[\w./]+\.py(?= — )')
fix = "--fix" in sys.argv

bad = 0
for path in sorted(ROOT.rglob("*.py")):
    rel = path.relative_to(ROOT)
    if SKIP_DIRS & set(rel.parts) or path.name in SKIP_FILES:
        continue
    raw = path.read_bytes().decode("utf-8")
    want = rel.as_posix()
    doc = ast.get_docstring(ast.parse(raw), clean=False)
    if doc is not None and doc.startswith(want + " — "):
        continue
    bad += 1
    if doc is None:
        print(f"НЕТ docstring: {want}")
    elif fix and HEAD.match(raw):
        new = HEAD.sub(lambda m: '"""' + want, raw, count=1)
        path.write_bytes(new.encode("utf-8"))
        print(f"исправлено:   {want}")
    else:
        print(f"не совпадает: {want}  ->  {doc.splitlines()[0][:60]}")
print("Проблем:", bad)