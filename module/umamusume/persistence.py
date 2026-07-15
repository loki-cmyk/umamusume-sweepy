import json
import os
import threading

import bot.base.log as logger

log = logger.get_logger(__name__)

PERSISTENCE_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'career_data.json')
PERSISTENCE_FILE = os.path.normpath(PERSISTENCE_FILE)

PERSIST_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'persist.json')
PERSIST_FILE = os.path.normpath(PERSIST_FILE)



MAX_DATAPOINTS = 10000

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


def migrate_json_to_sqlite(db):
    """One-time migration from legacy career_data.json into the given CultivateDatabase."""
    try:
        if not os.path.exists(PERSISTENCE_FILE):
            return
        
        log.info("Legacy career_data.json detected, starting migration to SQLite...")
        with open(PERSISTENCE_FILE, 'r') as f:
            data = json.load(f)
            
        # Extract histories
        score_history = data.get('score_history', [])
        stat_only_history = data.get('stat_only_history', [])
        energy_history = data.get('energy_history', [])
        action_history = data.get('action_history', [])
        raw_stat_history = data.get('raw_stat_history', [])
        date_history = data.get('date_history', [])
        
        min_len = min(len(score_history), len(stat_only_history), len(energy_history), len(raw_stat_history), len(date_history))
        if min_len > 0:
            legacy_run_index = 0
            current_run_id = f"legacy_migration_run_{legacy_run_index}"
            db.ensure_run_exists(current_run_id, scenario_type="migrated")
            
            for i in range(min_len):
                score = score_history[i]
                stat_only = stat_only_history[i]
                energy = energy_history[i]
                raw_stat = raw_stat_history[i]
                date = date_history[i]
                action = action_history[i] if i < len(action_history) else "unknown"
                
                # Detect start of a new legacy run when turn date resets/decreases
                if i > 0 and date < date_history[i-1]:
                    legacy_run_index += 1
                    current_run_id = f"legacy_migration_run_{legacy_run_index}"
                    db.ensure_run_exists(current_run_id, scenario_type="migrated")
                
                db.save_training_entry(
                    run_id=current_run_id,
                    date=date,
                    score=score,
                    stat_only=stat_only,
                    energy=energy,
                    raw_stat=raw_stat,
                    action=action,
                    scenario_type="migrated"
                )
            log.info(f"Successfully migrated {min_len} datapoints to SQLite across {legacy_run_index + 1} runs")
            
        # Delete the legacy JSON file upon successful migration
        try:
            os.remove(PERSISTENCE_FILE)
            log.info("Deleted legacy career_data.json file")
        except Exception as e:
            log.warning(f"Failed to remove legacy career_data.json file: {e}")
            
    except Exception as e:
        log.error(f"Error during legacy career data migration: {e}")


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
                
            db = ctx.cultivate_detail.db
            score_history = getattr(ctx.cultivate_detail, 'score_history', [])
            stat_only_history = getattr(ctx.cultivate_detail, 'stat_only_history', [])
            energy_history = getattr(ctx.cultivate_detail, 'energy_history', [])
            raw_stat_history = getattr(ctx.cultivate_detail, 'raw_stat_history', [])
            date_history = getattr(ctx.cultivate_detail, 'date_history', [])
            action_history = getattr(ctx.cultivate_detail, 'action_history', [])
            
            # Get the length of history loaded on startup
            loaded_len = getattr(ctx.cultivate_detail, 'loaded_history_len', 0)
            # Get the count of turns we have already saved in this run
            saved_count = getattr(ctx.cultivate_detail, 'saved_turns_count', 0)
            
            # We can only save indices where all lists are complete
            min_len = min(len(score_history), len(stat_only_history), len(energy_history), len(raw_stat_history), len(date_history))
            
            run_id = getattr(ctx.cultivate_detail, 'run_id', 'unknown_run')
            scenario_type = "unknown"
            try:
                scenario_type = ctx.cultivate_detail.scenario.scenario_type().name
            except Exception:
                pass
                
            for i in range(loaded_len + saved_count, min_len):
                score = score_history[i]
                stat_only = stat_only_history[i]
                energy = energy_history[i]
                raw_stat = raw_stat_history[i]
                date = date_history[i]
                action = action_history[i] if i < len(action_history) else "unknown"
                
                db.save_training_entry(
                    run_id=run_id,
                    date=date,
                    score=score,
                    stat_only=stat_only,
                    energy=energy,
                    raw_stat=raw_stat,
                    action=action,
                    scenario_type=scenario_type
                )
                saved_count += 1
                
            ctx.cultivate_detail.saved_turns_count = saved_count
    except Exception as e:
        log.info(f"Failed to save career data: {e}")


def load_career_data(ctx):
    try:
        db = ctx.cultivate_detail.db
        # Run legacy migration first
        migrate_json_to_sqlite(db)
        
        # Load from SQLite
        recent = db.get_recent_history(MAX_DATAPOINTS)
        scores = recent['score_history']
        stat_only = recent['stat_only_history']
        energy = recent['energy_history']
        actions = recent['action_history']
        raw_stats = recent['raw_stat_history']
        dates = recent['date_history']
        
        if not scores:
            ctx.cultivate_detail.score_history = []
            ctx.cultivate_detail.stat_only_history = []
            ctx.cultivate_detail.energy_history = []
            ctx.cultivate_detail.action_history = []
            ctx.cultivate_detail.raw_stat_history = []
            ctx.cultivate_detail.date_history = []
            ctx.cultivate_detail.percentile_history = []
            ctx.cultivate_detail.loaded_history_len = 0
            ctx.cultivate_detail.saved_turns_count = 0
            return False
            
        ctx.cultivate_detail.score_history = scores
        ctx.cultivate_detail.stat_only_history = stat_only
        ctx.cultivate_detail.energy_history = energy
        ctx.cultivate_detail.action_history = actions
        ctx.cultivate_detail.raw_stat_history = raw_stats
        ctx.cultivate_detail.date_history = dates
        ctx.cultivate_detail.percentile_history = rebuild_percentile_history(scores)
        
        ctx.cultivate_detail.loaded_history_len = len(scores)
        ctx.cultivate_detail.saved_turns_count = 0
        
        log.info(f"Restored career data: {len(scores)} datapoints")
        return True
    except Exception as e:
        log.info(f"Failed to load career data: {e}")
        return False


def clear_career_data():
    global career_cleared_flag
    try:
        with career_data_lock:
            from module.umamusume.database import get_database
            db = get_database()
            try:
                db.clear_all_data()
            finally:
                db.close()

            career_cleared_flag = True
        log.info("Career data cleared")
        return True
    except Exception as e:
        log.info(f"Failed to clear career data: {e}")
        return False




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
    data['megaphone_last_tick_date'] = last_tick_date
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


def save_contests_tried(contests):
    data = load_persist()
    data['contests_tried'] = list(contests)
    save_persist(data)


def load_contests_tried():
    data = load_persist()
    return set(data.get('contests_tried', []))


def clear_contests_tried():
    data = load_persist()
    data.pop('contests_tried', None)
    save_persist(data)

