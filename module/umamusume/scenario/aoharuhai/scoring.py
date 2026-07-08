from module.umamusume.constants.scoring_constants import (
    DEFAULT_SCORE_VALUE, DEFAULT_SPIRIT_EXPLOSION, DEFAULT_PURPLE_SPIRIT_EXPLOSION,
    DEFAULT_SPECIAL_WEIGHTS, DEFAULT_WIT_SPECIAL_MULTIPLIER
)
from module.umamusume.constants.game_constants import JUNIOR_YEAR_END, CLASSIC_YEAR_END


def compute_aoharu_bonuses(ctx, idx, support_card_info_list, date, period_idx, current_energy):
    special_count = 0
    spirit_count = 0
    purple_spirit_count = 0
    for sc in (support_card_info_list or []):
        try:
            stc = int(getattr(sc, 'special_training_count', 1 if getattr(sc, 'can_incr_special_training', False) else 0))
        except Exception:
            stc = 1 if getattr(sc, 'can_incr_special_training', False) else 0
        if stc > 0:
            special_count += stc
        if getattr(sc, 'purple_spirit_explosion', False):
            purple_spirit_count += 1
        elif getattr(sc, 'spirit_explosion', False):
            spirit_count += 1

    additive = 0.0
    multiplier = 1.0
    formula_parts = []
    mult_parts = []

    sv = getattr(ctx.cultivate_detail, 'score_value', DEFAULT_SCORE_VALUE)
    try:
        arr = sv[period_idx]
    except Exception:
        arr = []
    try:
        w_special = arr[4]
    except Exception:
        w_special = DEFAULT_SPECIAL_WEIGHTS[period_idx if 0 <= period_idx < len(DEFAULT_SPECIAL_WEIGHTS) else 0]

    special_bonus = 0.0
    if special_count > 0:
        special_bonus = float(w_special) * special_count
        if idx == 4:
            wsm = getattr(ctx.cultivate_detail, 'wit_special_multiplier', DEFAULT_WIT_SPECIAL_MULTIPLIER)
            if not isinstance(wsm, (list, tuple)) or len(wsm) < 2:
                wsm = DEFAULT_WIT_SPECIAL_MULTIPLIER
            wit_special_mult = 1.0
            if date <= JUNIOR_YEAR_END:
                wit_special_mult = float(wsm[0])
            elif date <= CLASSIC_YEAR_END:
                wit_special_mult = float(wsm[1])
            special_bonus *= wit_special_mult
            if wit_special_mult != 1.0:
                mult_parts.append(f"witspc:x{wit_special_mult:.2f}")
        additive += special_bonus

    se_config = getattr(ctx.cultivate_detail, 'spirit_explosion', DEFAULT_SPIRIT_EXPLOSION)
    if isinstance(se_config, list) and se_config and isinstance(se_config[0], list):
        se_weights = se_config[period_idx]
    else:
        se_weights = se_config

    pse_config = getattr(ctx.cultivate_detail, 'purple_spirit_explosion', DEFAULT_PURPLE_SPIRIT_EXPLOSION)
    if isinstance(pse_config, list) and pse_config and isinstance(pse_config[0], list):
        pse_weights = pse_config[period_idx]
    else:
        pse_weights = pse_config

    try:
        se_w = float(se_weights[idx]) if isinstance(se_weights, (list, tuple)) and len(se_weights) == 5 else 0.0
    except Exception:
        se_w = 0.0

    try:
        pse_w = float(pse_weights[idx]) if isinstance(pse_weights, (list, tuple)) and len(pse_weights) == 5 else 0.0
    except Exception:
        pse_w = 0.0

    if current_energy is not None and idx != 4:
        if current_energy >= 90:
            if se_w != 0.0:
                se_w *= 1.1
            if pse_w != 0.0:
                pse_w *= 1.1
        elif 40 <= current_energy <= 50:
            if se_w != 0.0:
                se_w *= 0.9
            if pse_w != 0.0:
                pse_w *= 0.9

    spirit_bonus = 0.0
    if spirit_count > 0 and se_w != 0.0:
        spirit_bonus = se_w * spirit_count
        additive += spirit_bonus

    purple_spirit_bonus = 0.0
    if purple_spirit_count > 0 and pse_w != 0.0:
        purple_spirit_bonus = pse_w * purple_spirit_count
        additive += purple_spirit_bonus

    if idx == 4 and current_energy is not None:
        if 10 <= current_energy <= 80:
            if spirit_count > 0 and se_w != 0.0:
                additive += se_w * 1.37
            if purple_spirit_count > 0 and pse_w != 0.0:
                additive += pse_w * 1.37

    if special_bonus > 0:
        formula_parts.append(f"special({special_count}):+{special_bonus:.3f}")
    if spirit_bonus > 0:
        formula_parts.append(f"spirit({spirit_count}):+{spirit_bonus:.3f}")
    if purple_spirit_bonus > 0:
        formula_parts.append(f"purple_spirit({purple_spirit_count}):+{purple_spirit_bonus:.3f}")

    return (additive, multiplier, formula_parts, mult_parts)
