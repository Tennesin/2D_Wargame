"""combat/artillery.py — правила урона фугаса САУ по площади. Только формулы.
Кого задело и что с этим делать, решает game/match/control/hits.py."""

def armor_k(armor_mm, ref_mm):
    """Во сколько раз броня ослабляет урон в кольце: 1 / (1 + броня / опорная). None: без ослабления."""
    if armor_mm is None or ref_mm <= 0.0:
        return 1.0
    return 1.0 / (1.0 + max(0.0, armor_mm) / ref_mm)

def blast_damage(stats, dist, armor_mm=None, k=1.0):
    """Урон взрыва цели, чья ближайшая точка в dist px от центра."""
    outer, inner = stats.outer_radius_px, stats.inner_radius_px
    if dist >= outer:
        return 0.0, False
    stunned = dist <= inner
    if stunned:
        falloff = 1.0
    else:
        t = (dist - inner) / max(outer - inner, 1e-9)
        falloff = 1.0 - (1.0 - stats.edge_k) * t
    return stats.damage * falloff * armor_k(armor_mm, stats.armor_ref_mm) * k, stunned