"""vehicles/spg/spec.py — характеристики САУ: шасси + безбашенное орудие (ArtyGunSpec) + параметры выстрела."""
from engine import AmmoKind, ArtilleryStats, PX_PER_M, clamp, fmt_num, lerp, round_to
from ..chassis.hulls import NOSE_FLAT, NOSE_RU
from ..chassis.params import ENGINE_T_PER_HP, HP_STEP
from ..chassis.spec import ChassisBody, armor_masses
from ..gun.params import (
    REF_L_CAL, BARREL_VISIBLE_K, GUN_ARM_BASE_M, GUN_ARM_BARREL_K,
    TURRET_INERTIA_EXP, TURRET_POWER_EXP,
)
from ..gun.spec import GunSpec
from ..gun.vehicle_specific import GunVehicleSpec
from .economy import spg_raw_cost
from .layout import SPG_LAYOUT
from .params import (
    SPG_PARAMS, SPG_REF_CAL, SPG_FIXED_MASS_T, SPG_GUN_MASS_T, SPG_GUN_MASS_EXP, SPG_MOUNT_K,
    SPG_FRONT_AREA_M2, SPG_SIDE_AREA_M2, SPG_REAR_AREA_M2, SPG_SIZE_ARMOR_K,
    SPG_HP_REF, SPG_HP_EXP, SPG_HP_MIN, SPG_HP_MAX,
    SPG_MOUNT_FWD_M, SPG_GUN_FRONT_M, SPG_BARREL_VIS_REF_M, SPG_SUPPORT_CAL,
    SPG_CASE_CAL_EXP, SPG_CASE_K_LIMITS, SPG_ARC_MAX_DEG, SPG_ARC_MIN_DEG,
    SPG_TRAVERSE_REF, SPG_TRAVERSE_MIN, SPG_TRAVERSE_MAX, SPG_SPINUP_REF,
    SPG_RANGE_M, SPG_DEAD_K, SPG_RELOAD_S, SPG_RELOAD_CURVE,
    SPG_DAMAGE_REF, SPG_DAMAGE_CAL_EXP, SPG_DAMAGE_SIZE_EXP, SPG_STUN_REF_S, SPG_STUN_SIZE_EXP,
    SPG_RADIUS_REF_M, SPG_RADIUS_SIZE_EXP, SPG_INNER_K,
    SPG_SPEED_REF_MS, SPG_SPEED_CAL_EXP, SPG_SPEED_SIZE_EXP, SPG_FLIGHT_MAX_S,
    SPG_EDGE_K, SPG_WALL_K, SPG_ARMOR_REF_MM,
    SPG_LOOK_FRONT_RATIO, SPG_LOOK_SIDE_RATIO, SPG_LOOK_GUN_RATIO, SPG_LOOK_SPEED_RATIO,
)

_CAL = SPG_PARAMS["gun_caliber_mm"]
_FRONT = SPG_PARAMS["front_armor_mm"]
_SIDE = SPG_PARAMS["side_armor_mm"]
_REAR = SPG_PARAMS["rear_armor_mm"]
_POWER = SPG_PARAMS["engine_power_hp"]
_AREAS = (SPG_FRONT_AREA_M2, SPG_SIDE_AREA_M2, SPG_REAR_AREA_M2)

# ==========================================
# 1. ФОРМУЛЫ, ЗАВИСЯЩИЕ ТОЛЬКО ОТ КАЛИБРА
# ==========================================

def spg_gun_mass(cal):
    """Масса орудия, т (калибр в кубе: крупный калибр заметно тяжелит машину)."""
    return SPG_GUN_MASS_T * (cal / SPG_REF_CAL) ** SPG_GUN_MASS_EXP

def spg_arc_deg(cal):
    """Полный сектор наводки, градусы, кратный 2° (чтобы «±» выводился целым числом)."""
    t = clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)
    return 2.0 * round(lerp(SPG_ARC_MAX_DEG, SPG_ARC_MIN_DEG, t) / 2.0)

# ==========================================
# 2. ЭТАЛОН И ШАССИ
# ==========================================
_REF_GUN_MASS = spg_gun_mass(_CAL.default)
_REF_FILLING = SPG_FIXED_MASS_T + _REF_GUN_MASS * (1.0 + SPG_MOUNT_K) + ENGINE_T_PER_HP * _POWER.default
_REF_ARMOR0 = sum(armor_masses(_AREAS, _FRONT.default, _SIDE.default, _REAR.default, 1.0))
_REF_MASS = _REF_FILLING + _REF_ARMOR0

SPG_BODY = ChassisBody(
    fixed_t=SPG_FIXED_MASS_T, engine_t_per_hp=ENGINE_T_PER_HP, areas_m2=_AREAS,
    ref_filling_t=_REF_FILLING + SPG_SIZE_ARMOR_K * _REF_ARMOR0,   # масса для габарита: у эталона size_k = 1
    ref_mass_t=_REF_MASS, ref_power_hp=_POWER.default,
    ref_armor_share=_REF_ARMOR0 / _REF_MASS, hp_ref=SPG_HP_REF,
    coll_half_w_m=SPG_LAYOUT.coll_half_w_m, coll_half_l_m=SPG_LAYOUT.coll_half_l_m,
    coll_shift_m=SPG_LAYOUT.coll_shift_m,
    layout=SPG_LAYOUT, size_armor_k=SPG_SIZE_ARMOR_K)

_REF_BARREL_M = _CAL.default * REF_L_CAL / 1000.0 * BARREL_VISIBLE_K
_REF_GUN_INERTIA = _REF_GUN_MASS * (GUN_ARM_BASE_M + GUN_ARM_BARREL_K * _REF_BARREL_M) ** 2

# ==========================================
# 3. ОРУДИЕ БЕЗ БАШНИ
# ==========================================

class ArtyGunSpec(GunSpec):
    """Орудие САУ: наводка в узком секторе, стрельба фугасом по точке на земле.
    Вспышка, дым, откат и размеры спрайта считает родитель (GunSpec) по калибру."""

    TURRET_SCALE_RANGE = (1.0, 1.0)    # масштаб орудия = масштаб корпуса (visual_k)

    def __init__(self, cal, size_k, power, m_gun, m_mount, arc_deg, visual_k):
        self._size_k = size_k          # нужен _calc_gun и _calc_shot, а родитель его не хранит
        super().__init__(cal, size_k, power, m_gun, m_mount, front_m=SPG_GUN_FRONT_M, arc_deg=arc_deg,
                         barrel_ref_m=SPG_BARREL_VIS_REF_M, visual_k=visual_k)
        self.ammo_kinds = (AmmoKind.HE,)   # САУ стреляет только фугасами

    def _calc_turret(self, size_k, power, m_gun, m_turret):
        """Вращается только орудие (инерция по его массе), наводка медленная."""
        barrel_len = self.cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K
        arm = GUN_ARM_BASE_M * size_k + GUN_ARM_BARREL_K * barrel_len
        self.i_turret = m_gun * arm ** 2
        i_rel = self.i_turret / _REF_GUN_INERTIA
        self.turret_turn = clamp(
            SPG_TRAVERSE_REF * (power / _POWER.default) ** TURRET_POWER_EXP * i_rel ** -TURRET_INERTIA_EXP,
            SPG_TRAVERSE_MIN, SPG_TRAVERSE_MAX)
        self.turret_alpha = self.turret_turn / (SPG_SPINUP_REF * i_rel ** 0.5)

    def _calc_gun(self, damage, penetration):
        """Урон в зоне максимума и перезарядка. Пробития нет: фугас бьёт по площади."""
        kc = self.cal / SPG_REF_CAL
        t = clamp((self.cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)
        self.damage = round_to(SPG_DAMAGE_REF * kc ** SPG_DAMAGE_CAL_EXP
                               * self._size_k ** SPG_DAMAGE_SIZE_EXP, 10.0)
        self.penetration = 0.0
        self.damage_k = self.pen_k = 1.0
        self.reload = round(SPG_RELOAD_S[0] + (SPG_RELOAD_S[1] - SPG_RELOAD_S[0]) * t ** SPG_RELOAD_CURVE, 1)
        self.dps = self.damage / self.reload

    def _calc_shot(self):
        super()._calc_shot()           # визуальные части выстрела и взрыва по калибру
        cal, sk = self.cal, self._size_k
        kc = cal / SPG_REF_CAL
        t = clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)

        range_m = round_to(lerp(SPG_RANGE_M[0], SPG_RANGE_M[1], t), 5.0)
        range_px = range_m * PX_PER_M
        dead_px = range_px * SPG_DEAD_K
        speed_ms = max(SPG_SPEED_REF_MS * kc ** SPG_SPEED_CAL_EXP * sk ** SPG_SPEED_SIZE_EXP,
                       range_m / SPG_FLIGHT_MAX_S)
        outer_px = SPG_RADIUS_REF_M * kc * sk ** SPG_RADIUS_SIZE_EXP * PX_PER_M
        stun_s = SPG_STUN_REF_S * kc * sk ** SPG_STUN_SIZE_EXP

        self.RANGE_MIN_PX = dead_px
        self.RANGE_MAX_PX = range_px
        self.SHELL_RANGE_PX = range_px                 # то же имя, что у остальных орудий
        self.SHELL_SPEED_PX = speed_ms * PX_PER_M
        self.shell_stats = ArtilleryStats(
            damage=self.damage, inner_radius_px=outer_px * SPG_INNER_K, outer_radius_px=outer_px,
            speed_px=speed_ms * PX_PER_M, reload=self.reload, stun_s=stun_s,
            range_min_px=dead_px, range_max_px=range_px, caliber_mm=cal,
            edge_k=SPG_EDGE_K, wall_k=SPG_WALL_K, armor_ref_mm=SPG_ARMOR_REF_MM)

# ==========================================
# 4. САУ
# ==========================================

class SPGSpec(GunVehicleSpec):
    PARAMS = SPG_PARAMS
    LOOK_FRONT_RATIO = SPG_LOOK_FRONT_RATIO
    LOOK_SIDE_RATIO = SPG_LOOK_SIDE_RATIO
    LOOK_GUN_RATIO = SPG_LOOK_GUN_RATIO
    LOOK_SPEED_RATIO = SPG_LOOK_SPEED_RATIO

    def __init__(self, cal, front, side, rear, power, unbounded=False):
        """unbounded принимается ради общего интерфейса, но игнорируется: границы САУ жёсткие
        (это правило класса: броня до 50 мм, калибр до 255 мм, у ботов тоже)."""
        cal, front, side, rear, power, _ = self._fit_inputs(cal, front, side, rear, power, 0.0, False)
        self.cal = cal                          # его читает расчёт оформления
        self.nose = NOSE_FLAT                   # его читает Vehicle.describe
        self.m_gun = spg_gun_mass(cal)
        self.m_mount = self.m_gun * SPG_MOUNT_K
        self.MOUNT_FWD_M = SPG_MOUNT_FWD_M
        self.SUPPORT = 2 if cal >= SPG_SUPPORT_CAL else 1
        self.CASE_K = round(clamp((cal / SPG_REF_CAL) ** SPG_CASE_CAL_EXP, *SPG_CASE_K_LIMITS), 1)

        def make_gun(size_k):
            return ArtyGunSpec(cal, size_k, power, self.m_gun, self.m_mount,
                               arc_deg=spg_arc_deg(cal), visual_k=self.HULL_SCALE)

        super().__init__(SPG_BODY, front, side, rear, power, self.m_gun + self.m_mount, 0.0, make_gun)
        self.HULL_VARIANT = (round(self.MOUNT_FWD_M / 0.1), self.SUPPORT, self.CASE_K,
                             round(self.TURRET_ARC_DEG), NOSE_FLAT)

    @classmethod
    def from_values(cls, v, unbounded=False):
        """v — словарь значений ползунков (у САУ только пять ключей)."""
        return cls(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                   v["rear_armor_mm"], v["engine_power_hp"], unbounded=unbounded)

    # ---------- свои расчёты вместо базовых ----------
    def _calc_hp(self):
        """Здоровье по массе начинки, но в пределах 400-700."""
        raw = SPG_HP_REF * (self.filling / _REF_FILLING) ** SPG_HP_EXP
        self.hp = clamp(max(HP_STEP, round_to(raw, HP_STEP)), SPG_HP_MIN, SPG_HP_MAX)

    def _calc_economy(self):
        self.cost = max(1000, round_to(spg_raw_cost(self.cal, self.front, self.side,
                                                    self.rear, self.power), 500))

    # ---------- орудие ----------
    @property
    def shell_stats(self): return self.gun.shell_stats
    @property
    def RANGE_MIN_PX(self): return self.gun.RANGE_MIN_PX
    @property
    def RANGE_MAX_PX(self): return self.gun.RANGE_MAX_PX

    # ---------- вывод ----------
    def main_stats(self):
        g = self.shell_stats
        return {
            "Стоимость": fmt_num(self.cost),
            "HP": fmt_num(self.hp),
            "Масса": f"{self.mass:.1f} т",
            "Габарит (size_k)": f"{self.size_k:.2f}",
            "Макс. скорость": f"{self.v_max:.0f} км/ч",
            "Поворот корпуса": f"{self.hull_turn:.0f} °/с",
            "УГН": f"±{self.TURRET_ARC_DEG / 2.0:.0f} °",
            "Нос корпуса": NOSE_RU[self.nose],
            "Урон взрыва": f"{g.damage:.0f}",
            "Дальность": f"{g.range_max_px / PX_PER_M:.0f} м",
            "Мёртвая зона": f"{g.range_min_px / PX_PER_M:.0f} м",
            "Радиус взрыва": f"{g.outer_radius_px / PX_PER_M:.1f} м",
            "Зона максимума": f"{g.inner_radius_px / PX_PER_M:.1f} м",
            "Оглушение": f"{g.stun_s:.1f} с",
            "Скорость снаряда": f"{g.speed_px / PX_PER_M:.0f} м/с",
            "Полёт на макс. дальность": f"{g.range_max_px / g.speed_px:.1f} с",
            "Перезарядка": f"{g.reload:.1f} с",
        }

    def internal_stats(self):
        return {
            "Удельная мощность": f"{self.pw:.1f} л.с./т",
            "Масса орудия": f"{self.m_gun:.1f} т",
            "Бронированность": f"{self.q_arm:.2f}",
            "Масштаб корпуса": f"{self.HULL_SCALE:.2f}",
            "Угл. разгон корпуса": f"{self.hull_alpha:.0f} °/с²",
            "Наводка орудия": f"{self.turret_turn:.0f} °/с",
        }