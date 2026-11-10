"""vehicles/gun/vehicle_specific.py — базовая спецификация техники с орудием."""
import math

from engine import PX_PER_M, clamp, AmmoKind
from ..chassis.hulls import NOSE_FLAT
from ..chassis.params import COLLISION_MARGIN_PX, FRONT_SCREEN, SCREEN_LOOK_STEPS
from ..chassis.spec import ChassisSpec
from ..chassis.screens import equivalent_armor
from ..parts.screens import screens_of
from ..parts.design import PartsDesign
from ..parts.model import SURFACE_BARREL
from ..cost import raw_cost, round_cost
from ..look import Look, level
from .barrel import length_pen_k, length_cost_k
from .params import REF_L_CAL
from .ammo import SPECIAL_HEAT, ammo_stats

class GunVehicleSpec(ChassisSpec):
    """Подкласс обязан задать атрибуты класса PARAMS и LOOK_*_RATIO, а до вызова __init__
    выставить self.cal."""

    PARAMS = None               # словарь Param: ключи gun_caliber_mm, front_armor_mm, ...
    LOOK_FRONT_RATIO = None     # пороги уровней оформления (доли от эталонного ползунка)
    LOOK_SIDE_RATIO = None
    LOOK_GUN_RATIO = None
    LOOK_SPEED_RATIO = None
    DESIGN_KWARGS = {}          # {ключ в values: имя аргумента конструктора}: дизайн техники (у ОБТ: башня)
    TURRET_MASS_K = 1.0         # во сколько раз масса башни отличается от эталонной (идёт в цену)

    def __init__(self, body, front, side, rear, power, payload_t, screen_mm, make_gun, parts_design=None):
        """make_gun(size_k) -> GunSpec: создаёт орудие, когда шасси уже посчитано."""
        self.parts_design = PartsDesign.from_data(parts_design)
        screens = screens_of(body.layout, self.parts_design, screen_mm)
        super().__init__(body, front, side, rear, power, payload_t=payload_t,
                         screen_mm=screen_mm, screens=screens)
        self.PARTS_KEY = self.parts_design.key
        self.BARREL_KEY = self.parts_design.surface_key(SURFACE_BARREL)
        self.gun = make_gun(self.size_k)
        self._calc_reach()
        self._calc_economy()
        self._calc_look()

    # ---------- входы и фабрики ----------
    @classmethod
    def _fit_inputs(cls, cal, front, side, rear, power, screen, unbounded):
        """Привести входы к границам ползунков типа. unbounded=True: верхних границ нет (боты)."""
        p = cls.PARAMS
        return (p["gun_caliber_mm"].fit(cal, unbounded),
                p["front_armor_mm"].fit(front, unbounded),
                p["side_armor_mm"].fit(side, unbounded),
                p["rear_armor_mm"].fit(rear, unbounded),
                p["engine_power_hp"].fit(power, unbounded),
                clamp(float(screen), FRONT_SCREEN.min, FRONT_SCREEN.max))

    @classmethod
    def from_values(cls, v, unbounded=False):
        """v — словарь значений ползунков."""
        design = {kw: v[key] for key, kw in cls.DESIGN_KWARGS.items() if key in v}
        return cls(
            v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"], v["rear_armor_mm"],
            v["engine_power_hp"], damage=v.get("gun_damage"), penetration=v.get("gun_penetration"),
            screen=v.get("front_screen_mm", 0.0), nose=v.get("front_nose", NOSE_FLAT),
            special_ammo=v.get("special_ammo", SPECIAL_HEAT), unbounded=unbounded,
            gun_length=v.get("gun_length_cal"), **design)

    @classmethod
    def from_config(cls):
        """Техника из стартовых значений (PARAMS[...].default)."""
        p = cls.PARAMS
        return cls(p["gun_caliber_mm"].default, p["front_armor_mm"].default, p["side_armor_mm"].default,
                   p["rear_armor_mm"].default, p["engine_power_hp"].default)

    # ---------- то, что требует и шасси, и орудие ----------
    def _calc_reach(self):
        """Радиус, в который попадает всё, что машина может задеть за кадр, и который нужен для
        отсечения по экрану. Ствол в столкновениях не участвует, но на экране его надо дорисовать."""
        t = self.TURRET_SCALE * PX_PER_M
        barrel_end = (self.GUN_FRONT_M + self.BARREL_LEN_M) * t
        barrel_half_w = (self.BARREL_THICK_M + 0.08) * t / 2.0
        barrel_reach = math.hypot(barrel_end, barrel_half_w)
        self.REACH_PX = max(self.HULL_REACH_PX, barrel_reach) + COLLISION_MARGIN_PX

    def _calc_economy(self):
        """Цена по формуле танка."""
        prof = self.profile
        length = self.gun.length_cal if self.gun.length_cal is not None else REF_L_CAL
        f_add, s_add = equivalent_armor(self.layout, self.screens)
        raw = raw_cost(self.cal, self.front + f_add, self.side + s_add, self.rear, self.power,
                       self.damage_k, self.pen_k * length_pen_k(length),
                       prof.dmg_mult(self.cal), prof.pen_mult(self.cal), length_cost_k(length),
                       self.TURRET_MASS_K)
        self.cost = round_cost(raw)

    def _calc_look(self):
        p = self.PARAMS
        self.LOOK = Look(
            front=level(self.front / p["front_armor_mm"].default, self.LOOK_FRONT_RATIO),
            side=level(self.side / p["side_armor_mm"].default, self.LOOK_SIDE_RATIO),
            gun=level(self.cal / p["gun_caliber_mm"].default, self.LOOK_GUN_RATIO),
            speed=level(self.q_pw, self.LOOK_SPEED_RATIO),
            screen=level(self.screen_mm, SCREEN_LOOK_STEPS),
        )

    @property
    def screens_text(self):
        if not self.screens:
            return "нет"
        front = sum(1 for s in self.screens if s.face == "front")
        return f"лоб {front}, борта {len(self.screens) - front}; {self.m_screens:.1f} т"

    # ==========================================
    # СВОЙСТВА ОРУДИЯ
    # ==========================================
    @property
    def hesh(self): return self.gun.hesh
    @property
    def profile(self): return self.gun.profile
    @property
    def ammo_kinds(self): return self.gun.ammo_kinds
    @property
    def TURRET_ARC_DEG(self): return self.gun.TURRET_ARC_DEG
    @property
    def GUN_FRONT_M(self): return self.gun.GUN_FRONT_M

    # --- башня, наводка, характеристики орудия ---
    @property
    def q_gun(self): return self.gun.q_gun
    @property
    def l_cal(self): return self.gun.l_cal
    @property
    def i_turret(self): return self.gun.i_turret
    @property
    def turret_turn(self): return self.gun.turret_turn
    @property
    def turret_alpha(self): return self.gun.turret_alpha
    @property
    def damage(self): return self.gun.damage
    @property
    def penetration(self): return self.gun.penetration
    @property
    def damage_k(self): return self.gun.damage_k
    @property
    def pen_k(self): return self.gun.pen_k
    @property
    def reload(self): return self.gun.reload
    @property
    def dps(self): return self.gun.dps

    # --- размеры спрайта орудия ---
    @property
    def TURRET_SCALE(self): return self.gun.TURRET_SCALE
    @property
    def BARREL_LEN_M(self): return self.gun.BARREL_LEN_M
    @property
    def BARREL_THICK_M(self): return self.gun.BARREL_THICK_M

    # --- снаряд ---
    @property
    def MUZZLE_DIST_PX(self): return self.gun.MUZZLE_DIST_PX
    @property
    def SHELL_SPEED_PX(self): return self.gun.SHELL_SPEED_PX
    @property
    def SHELL_RANGE_PX(self): return self.gun.SHELL_RANGE_PX
    @property
    def SHELL_LEN_PX(self): return self.gun.SHELL_LEN_PX
    @property
    def SHELL_THICK_PX(self): return self.gun.SHELL_THICK_PX
    @property
    def normalization_deg(self): return ammo_stats(self, AmmoKind.AP).normalization_deg

    # --- эффекты выстрела и взрыва ---
    @property
    def RECOIL_DEPTH_M(self): return self.gun.RECOIL_DEPTH_M
    @property
    def RECOIL_TIME(self): return self.gun.RECOIL_TIME
    @property
    def RECOIL_RISE_S(self): return self.gun.RECOIL_RISE_S
    @property
    def RECOIL_FALL_S(self): return self.gun.RECOIL_FALL_S
    @property
    def FLASH_SIZE_PX(self): return self.gun.FLASH_SIZE_PX
    @property
    def FLASH_TIME(self): return self.gun.FLASH_TIME
    @property
    def SMOKE_TIME(self): return self.gun.SMOKE_TIME
    @property
    def SMOKE_STREAKS(self): return self.gun.SMOKE_STREAKS
    @property
    def SMOKE_REACH_PX(self): return self.gun.SMOKE_REACH_PX
    @property
    def SMOKE_WIDTH_PX(self): return self.gun.SMOKE_WIDTH_PX
    @property
    def BLAST_SIZE_PX(self): return self.gun.BLAST_SIZE_PX
    @property
    def BLAST_TIME(self): return self.gun.BLAST_TIME
    @property
    def BLAST_DIRT_COUNT(self): return self.gun.BLAST_DIRT_COUNT
    @property
    def SCORCH_RADIUS_PX(self): return self.gun.SCORCH_RADIUS_PX
    @property
    def SCORCH_TIME(self): return self.gun.SCORCH_TIME