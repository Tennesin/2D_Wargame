"""combat/splash.py — урон осколками фугаса по площади. Только формула."""

SPLASH_EDGE_K = 0.25     # какая доля урона остаётся на самой границе радиуса (в центре 1.0)

def splash_damage(damage, min_frac, dist, radius):
    """Урон цели на расстоянии dist от центра взрыва. Броня не учитывается:
    это гарантированный минимум фугаса. За пределами радиуса 0."""
    if radius <= 0.0 or dist >= radius:
        return 0.0
    k = 1.0 - (1.0 - SPLASH_EDGE_K) * dist / radius
    return damage * min_frac * k