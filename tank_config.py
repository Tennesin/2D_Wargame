# tank_config.py
# Конфигурационный файл и физическая модель характеристик танка

# ==========================================
# 1. ОСНОВНЫЕ ВХОДНЫЕ ПАРАМЕТРЫ
# ==========================================
ENGINE_POWER_HP = 1000.0  # Мощность двигателя (л.с.)
GUN_CALIBER_MM = 125.0    # Калибр орудия (мм)

# Толщины брони в миллиметрах
FRONT_ARMOR_THICKNESS_MM = 340.0  # Лобовая броня
SIDE_ARMOR_THICKNESS_MM = 110.0   # Бортовая броня
REAR_ARMOR_THICKNESS_MM = 65.0    # Кормовая броня

# ==========================================
# 2. ФИЗИЧЕСКИЕ И ГЕОМЕТРИЧЕСКИЕ КОНСТАНТЫ
# ==========================================
STEEL_DENSITY_TONS_M3 = 7.85  # Плотность броневой стали (тонн / м³)

# Условные площади броневых плит (в м²)
FRONT_ARMOR_AREA_M2 = 2.2  # Площадь лобовой проекции
SIDE_ARMOR_AREA_M2 = 7.5   # Увеличенная площадь длинных бортов (суммарно 2 борта)
REAR_ARMOR_AREA_M2 = 1.2   # Уменьшенная площадь узкой кормовой плиты

# ==========================================
# 3. РАСЧЕТ МАССЫ КОМПОНЕНТОВ (в тоннах)
# ==========================================
FRONT_ARMOR_MASS = (FRONT_ARMOR_THICKNESS_MM / 1000.0) * FRONT_ARMOR_AREA_M2 * STEEL_DENSITY_TONS_M3  # ~4.32 т
SIDE_ARMOR_MASS = (SIDE_ARMOR_THICKNESS_MM / 1000.0) * SIDE_ARMOR_AREA_M2 * STEEL_DENSITY_TONS_M3    # ~5.89 т
REAR_ARMOR_MASS = (REAR_ARMOR_THICKNESS_MM / 1000.0) * REAR_ARMOR_AREA_M2 * STEEL_DENSITY_TONS_M3    # ~0.47 т

TRACKS_MASS = 5.0      # Гусеницы и ходовая
BASE_HULL_MASS = 13.0  # Каркас корпуса и МТО

# Вес корпуса в сборе
HULL_MASS = FRONT_ARMOR_MASS + SIDE_ARMOR_MASS + REAR_ARMOR_MASS + TRACKS_MASS + BASE_HULL_MASS

TURRET_MASS = 12.0     # Башня
GUN_MASS = 2.5 * ((GUN_CALIBER_MM / 125.0) ** 2)  # Орудие

TOTAL_TANK_MASS = HULL_MASS + TURRET_MASS + GUN_MASS

# ==========================================
# 4. ФОРМУЛЫ МОБИЛЬНОСТИ И ДИНАМИКИ
# ==========================================
POWER_TO_WEIGHT_RATIO = ENGINE_POWER_HP / TOTAL_TANK_MASS

FORWARD_SPEED_PX = POWER_TO_WEIGHT_RATIO * 5.5
BACKWARD_SPEED_PX = FORWARD_SPEED_PX * 0.5
TURN_SPEED_PENALTY = 0.65

HULL_ROTATION_SPEED = POWER_TO_WEIGHT_RATIO * 1.95
TURRET_ROTATION_SPEED = 650.0 / (TURRET_MASS + GUN_MASS)


def print_tank_specs():
    print("=" * 50)
    print("           ХАРАКТЕРИСТИКИ ТАНКА (CONFIG)")
    print("=" * 50)
    print(f"Мощность двигателя:    {ENGINE_POWER_HP:.0f} л.с.")
    print(f"Калибр орудия:         {GUN_CALIBER_MM:.0f} мм")
    print("-" * 50)
    print(f"Масса лобовой брони:   {FRONT_ARMOR_MASS:.2f} т (толщина {FRONT_ARMOR_THICKNESS_MM:.0f} мм)")
    print(f"Масса бортовой брони:  {SIDE_ARMOR_MASS:.2f} т (толщина {SIDE_ARMOR_THICKNESS_MM:.0f} мм)")
    print(f"Масса кормовой брони:  {REAR_ARMOR_MASS:.2f} т (толщина {REAR_ARMOR_THICKNESS_MM:.0f} мм)")
    print(f"Масса гусениц/ходовой: {TRACKS_MASS:.2f} т")
    print(f"Масса корпуса (всего): {HULL_MASS:.2f} т")
    print(f"Масса башни:           {TURRET_MASS:.2f} т")
    print(f"Масса орудия:          {GUN_MASS:.2f} т")
    print("-" * 50)
    print(f"ОБЩАЯ МАССА ТАНКА:     {TOTAL_TANK_MASS:.2f} тонн")
    print(f"Удельная мощность:     {POWER_TO_WEIGHT_RATIO:.2f} л.с./т")
    print("-" * 50)
    print(f"Скорость вперед:       {FORWARD_SPEED_PX:.1f} px/s")
    print(f"Скорость назад:        {BACKWARD_SPEED_PX:.1f} px/s")
    print(f"Поворот корпуса:       {HULL_ROTATION_SPEED:.1f} deg/s")
    print(f"Поворот башни:         {TURRET_ROTATION_SPEED:.1f} deg/s")
    print("=" * 50)