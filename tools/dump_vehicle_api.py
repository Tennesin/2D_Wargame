"""tools/dump_vehicle_api.py — список имён класса Vehicle: сравнение до и после разреза.
Запуск из корня проекта: python -m tools.dump_vehicle_api before.txt"""
import sys

from vehicles import Vehicle

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "vehicle_api.txt"
    names = sorted(n for n in dir(Vehicle) if not n.startswith("__"))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(names) + "\n")
    print(f"{len(names)} имён записано в {path}")

if __name__ == "__main__":
    main()