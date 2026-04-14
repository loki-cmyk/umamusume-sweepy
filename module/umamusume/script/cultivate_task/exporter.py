import json
from enum import Enum
from module.umamusume.asset.race_data import get_races_for_period, RACE_LIST

EXCLUDE_FIELDS = {
    # Large/Complex Objects
    "scenario",
    "turn_info_history",
    "expect_attribute",

    # Growing History Tables (very long in later turns)
    "score_history",
    "percentile_history",
    "stat_only_history",

    # Configuration / Constant Lists (repetitive every turn)
    "extra_race_list",
    "learn_skill_list",
    "learn_skill_blacklist",
    "tactic_list",
    "tactic_actions",
    "extra_weight",
    "spirit_explosion",
    "event_overrides",
    "pal_thresholds",
    "pal_friendship_score",
    "npc_score_value",
    "base_score",
    "stat_value_multiplier",
    "wit_special_multiplier",
    "score_value",
    "hint_boost_characters",
    "friendship_score_groups",

    # Other large/static fields
    "learned_skill_names",
    "event_tried_selectors",

    # UI / Coordinate / Interaction Data (irrelevant for turn strategy)
    "center",
    "mant_shop_ratio",
    "mant_shop_drag_ratio",
    "mant_shop_first_gy",
}

def export_cultivate_context(ctx):
    """
    Serializes the current cultivation context into a JSON string.
    Includes turn info, upcoming races, and the relevant parts of cultivate_detail.
    Excludes large configuration and history lists to keep the payload efficient.
    """
    detail = ctx.cultivate_detail
    turn_info = detail.turn_info
    date = turn_info.date
    upcoming_races = []
    # Search for the next 3 turns for scheduled races
    extra_races = getattr(detail, 'extra_race_list', []) or []
    for current_search_date in range(date + 1, min(date + 4, 76)):
        rids = get_races_for_period(current_search_date)
        for rid in rids:
            if rid in extra_races:
                race_entry = RACE_LIST.get(rid)
                name = race_entry[1] if race_entry else "Unknown Race"
                upcoming_races.append({
                    "date": current_search_date,
                    "race_id": rid,
                    "name": name
                })

    # Build the final payload
    payload = {
        "turn_counter": date,
        "upcoming_races": upcoming_races,
        "detail": to_dict(detail)
    }

    return json.dumps(payload, ensure_ascii=False)

def to_dict(obj, seen=None):
    """
    Recursively converts an object into a dictionary representation.
    Handles Enums, nested objects, lists, and dicts while applying EXCLUDE_FIELDS.
    """
    if seen is None:
        seen = set()

    # Handle basic types
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj

    # Handle Enums (return the name of the constant)
    if isinstance(obj, Enum):
        return obj.name

    # Handle Collections
    if isinstance(obj, (list, tuple)):
        return [to_dict(item, seen) for item in obj]

    if isinstance(obj, dict):
        return {str(k): to_dict(v, seen) for k, v in obj.items() if k not in EXCLUDE_FIELDS}

    # Handle Objects
    if id(obj) in seen:
        return "<circular reference>"

    # Exclude logic for specific classes/fields
    if hasattr(obj, "__class__"):
        cls_name = obj.__class__.__name__
        # Exclude scenario objects as they are too complex
        if "Scenario" in cls_name:
            return f"<Scenario Object: {cls_name}>"

    seen.add(id(obj))

    try:
        res = {}
        # Use __dict__ or vars() to get instance attributes
        # Some objects might not have __dict__ (like those with __slots__)
        items = vars(obj).items() if hasattr(obj, "__dict__") else []
        if not items and hasattr(obj, "__slots__"):
            items = [(s, getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s)]

        for k, v in items:
            # Exclude specified fields
            if k in EXCLUDE_FIELDS:
                continue
            res[k] = to_dict(v, seen)

        return res
    except (TypeError, AttributeError):
        # Fallback for complex objects that can't be introspected easily
        return str(obj)
