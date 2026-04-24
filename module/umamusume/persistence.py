import json
import os
import threading

import bot.base.log as logger
from config import CONFIG

log = logger.get_logger(__name__)

PERSISTENCE_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'career_data.json')
PERSISTENCE_FILE = os.path.normpath(PERSISTENCE_FILE)

PERSIST_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'persist.json')
PERSIST_FILE = os.path.normpath(PERSIST_FILE)

TRAINING_JSON_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'training_analysis.jsonl')
TRAINING_JSON_FILE = os.path.normpath(TRAINING_JSON_FILE)

MAX_DATAPOINTS = 2000
HISTORY_VERSION_FLAG = "aaa"

career_cleared_flag = False
career_data_lock = threading.Lock()


def rebuild_percentile_history(score_history):
    percentiles = []
    for i in range(1, len(score_history)):
        current = score_history[i]
        prev = score_history[:i]
        below_count = sum(1 for s in prev if s < current)
        percentile = below_count / len(prev) * 100
        percentiles.append(percentile)
    return percentiles


def save_career_data(ctx):
    global career_cleared_flag
    try:
        with career_data_lock:
            if career_cleared_flag:
                career_cleared_flag = False
                ctx.cultivate_detail.score_history = []
                ctx.cultivate_detail.percentile_history = []
                log.info("Career data cleared from memory")
                return
            score_history = getattr(ctx.cultivate_detail, 'score_history', [])
            if not score_history:
                return
            scores = score_history[-MAX_DATAPOINTS:]
            stat_only_history = getattr(ctx.cultivate_detail, 'stat_only_history', [])
            stat_only = stat_only_history[-MAX_DATAPOINTS:]
            energy_history = getattr(ctx.cultivate_detail, 'energy_history', [])
            energy = energy_history[-MAX_DATAPOINTS:]
            action_history = getattr(ctx.cultivate_detail, 'action_history', [])
            actions = action_history[-MAX_DATAPOINTS:]
            raw_stat_history = getattr(ctx.cultivate_detail, 'raw_stat_history', [])
            raw_stats = raw_stat_history[-MAX_DATAPOINTS:]
            date_history = getattr(ctx.cultivate_detail, 'date_history', [])
            dates = date_history[-MAX_DATAPOINTS:]
            data = {
                'version': HISTORY_VERSION_FLAG,
                'score_history': scores,
                'stat_only_history': stat_only,
                'energy_history': energy,
                'action_history': actions,
                'raw_stat_history': raw_stats,
                'date_history': dates,
            }
            with open(PERSISTENCE_FILE, 'w') as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
    except Exception as e:
        log.info(f"Failed to save career data: {e}")


def load_career_data(ctx):
    try:
        if not os.path.exists(PERSISTENCE_FILE):
            return False
        with open(PERSISTENCE_FILE, 'r') as f:
            data = json.load(f)
        stored_version = data.get('version', "")
        if stored_version != HISTORY_VERSION_FLAG:
            clear_career_data()
            return False

        required_keys = {'score_history', 'stat_only_history', 'energy_history', 'action_history', 'raw_stat_history', 'date_history'}
        if not required_keys.issubset(data.keys()):
            log.info("Career data format mismatch - clearing old data")
            clear_career_data()
            return False
        score_history = data.get('score_history', [])
        stat_only_history = data.get('stat_only_history', [])
        energy_history = data.get('energy_history', [])
        action_history = data.get('action_history', [])
        raw_stat_history = data.get('raw_stat_history', [])
        date_history = data.get('date_history', [])
        if not score_history:
            return False
        scores = score_history[-MAX_DATAPOINTS:]
        stat_only = stat_only_history[-MAX_DATAPOINTS:]
        energy = energy_history[-MAX_DATAPOINTS:]
        actions = action_history[-MAX_DATAPOINTS:]
        raw_stats = raw_stat_history[-MAX_DATAPOINTS:]
        dates = date_history[-MAX_DATAPOINTS:]
        ctx.cultivate_detail.score_history = scores
        ctx.cultivate_detail.stat_only_history = stat_only
        ctx.cultivate_detail.energy_history = energy
        ctx.cultivate_detail.action_history = actions
        ctx.cultivate_detail.raw_stat_history = raw_stats
        ctx.cultivate_detail.date_history = dates
        ctx.cultivate_detail.percentile_history = rebuild_percentile_history(scores)
        log.info(f"Restored career data: {len(scores)} datapoints")
        return True
    except Exception as e:
        log.info(f"Failed to load career data: {e}")
        return False


def clear_career_data():
    global career_cleared_flag
    try:
        with career_data_lock:
            with open(PERSISTENCE_FILE, 'w') as f:
                json.dump({
                    'version': HISTORY_VERSION_FLAG,
                    'score_history': [], 
                    'stat_only_history': [], 
                    'energy_history': [], 
                    'action_history': [], 
                    'raw_stat_history': [], 
                    'date_history': []
                }, f)
                f.flush()
                os.fsync(f.fileno())
            try:
                if os.path.exists(TRAINING_JSON_FILE):
                    os.remove(TRAINING_JSON_FILE)
            except Exception as le:
                log.info(f"Failed to clear training analysis json: {le}")
            career_cleared_flag = True
        log.info("Career data cleared")
        return True
    except Exception as e:
        log.info(f"Failed to clear career data: {e}")
        return False


def append_training_json(json_str):
    if CONFIG.bot.log_training_data is False:
        return
    try:
        with open(TRAINING_JSON_FILE, 'a', encoding='utf-8') as f:
            f.write(json_str + '\n')
    except Exception as e:
        log.info(f"Failed to append to training json: {e}")


def load_persist():
    try:
        if not os.path.exists(PERSIST_FILE):
            return {}
        with open(PERSIST_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        log.info(f"Failed to load persist.json: {e}")
        return {}


def save_persist(data):
    try:
        with open(PERSIST_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        log.info(f"Failed to save persist.json: {e}")


def mark_buff_used(item_name):
    data = load_persist()
    used = set(data.get('used_buffs', []))
    used.add(item_name)
    data['used_buffs'] = list(used)
    save_persist(data)


def is_buff_used(item_name):
    data = load_persist()
    return item_name in data.get('used_buffs', [])


def get_used_buffs():
    data = load_persist()
    return set(data.get('used_buffs', []))


def clear_used_buffs():
    data = load_persist()
    data['used_buffs'] = []
    save_persist(data)


def get_ignore_cat_food():
    data = load_persist()
    return data.get('ignore_cat_food', False)


def set_ignore_cat_food(flag=True):
    data = load_persist()
    data['ignore_cat_food'] = flag
    save_persist(data)


def clear_ignore_cat_food():
    data = load_persist()
    data.pop('ignore_cat_food', None)
    save_persist(data)


def get_ignore_grilled_carrots():
    data = load_persist()
    return data.get('ignore_grilled_carrots', False)


def set_ignore_grilled_carrots(flag=True):
    data = load_persist()
    data['ignore_grilled_carrots'] = flag
    save_persist(data)


def clear_ignore_grilled_carrots():
    data = load_persist()
    data.pop('ignore_grilled_carrots', None)
    save_persist(data)


def save_afflictions(afflictions):
    data = load_persist()
    data['afflictions'] = list(afflictions)
    save_persist(data)


def load_afflictions():
    data = load_persist()
    return data.get('afflictions', [])


def clear_afflictions():
    data = load_persist()
    data.pop('afflictions', None)
    save_persist(data)


def save_megaphone_state(tier, turns, last_tick_date=-1, used_date=-1):
    data = load_persist()
    data['megaphone_tier'] = tier
    data['megaphone_turns'] = turns
    if last_tick_date != -1:
        data['megaphone_last_tick_date'] = last_tick_date
    if used_date != -1:
        data['megaphone_used_date'] = used_date
    save_persist(data)


def load_megaphone_state():
    data = load_persist()
    tier = data.get('megaphone_tier', 0)
    turns = data.get('megaphone_turns', 0)
    last_tick_date = data.get('megaphone_last_tick_date', -1)
    used_date = data.get('megaphone_used_date', -1)
    return tier, turns, last_tick_date, used_date


def clear_megaphone_state():
    data = load_persist()
    data.pop('megaphone_tier', None)
    data.pop('megaphone_turns', None)
    data.pop('megaphone_last_tick_date', None)
    data.pop('megaphone_used_date', None)
    save_persist(data)


def save_clock_used(count):
    data = load_persist()
    data['clock_used'] = count
    save_persist(data)


def load_clock_used():
    data = load_persist()
    return data.get('clock_used', 0)


def clear_clock_used():
    data = load_persist()
    data.pop('clock_used', None)
    save_persist(data)


def save_run_id(run_id):
    data = load_persist()
    data['run_id'] = run_id
    save_persist(data)


def load_run_id():
    data = load_persist()
    return data.get('run_id', None)


def clear_run_id():
    data = load_persist()
    data.pop('run_id', None)
    save_persist(data)


def save_last_turn(turn):
    data = load_persist()
    data['last_turn'] = turn
    save_persist(data)


def load_last_turn():
    data = load_persist()
    return data.get('last_turn', None)


def clear_last_turn():
    data = load_persist()
    data.pop('last_turn', None)
    save_persist(data)


def get_sanitized_turn(detail, requested_date):
    """
    Ensures turn progression is sequential and persists the state.
    Fixes OCR jumps by capping at last_turn + 1.
    """
    last = getattr(detail, 'last_logged_date', None)
    if last is None:
        try:
            last = load_last_turn()
            detail.last_logged_date = last
        except Exception:
            pass

    # If it's a huge jump forward, cap it at last + 1
    if last is not None and requested_date > last + 1:
        requested_date = last + 1

    # Update the tracker if we moved forward
    if last is None or requested_date > last:
        detail.last_logged_date = requested_date
        try:
            save_last_turn(requested_date)
        except Exception:
            pass

    return requested_date
