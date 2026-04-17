import bot.base.log as logger
from bot.recog.image_matcher import image_match
from module.umamusume.asset.template import (
    REF_MANT_RACE_TRY_AGAIN,
    REF_MANT_RACE_TRY_AGAIN_DISABLED,
)

log = logger.get_logger(__name__)


def _get_current_race_id(ctx) -> int:
    """Safely retrieve the race_id from the current turn operation, or 0 if unavailable."""
    try:
        return ctx.cultivate_detail.turn_info.turn_operation.race_id
    except Exception:
        return 0


def _check_race_outcome(ctx, img):
    """
    Check whether the post-race screen shows a win or a loss by matching the
    'Try Again' button template variants:
      - REF_MANT_RACE_TRY_AGAIN_DISABLED  →  button is greyed out  →  race WON
      - REF_MANT_RACE_TRY_AGAIN           →  button is active      →  race LOST
    Logs the outcome along with the current race_id (if set).
    """
    try:
        race_id = _get_current_race_id(ctx)
        race_id_str = str(race_id) if race_id else "<unknown>"

        if image_match(img, REF_MANT_RACE_TRY_AGAIN_DISABLED).find_match:
            log.info(f"Race win detected — race_id={race_id_str}")
            return

        if image_match(img, REF_MANT_RACE_TRY_AGAIN).find_match:
            log.info(f"Race loss detected — race_id={race_id_str}")
            if race_id:
                mant_cfg = getattr(getattr(ctx.task.detail, 'scenario_config', None), 'mant_config', None)
                retry_list = getattr(mant_cfg, 'retry_race_list', []) if mant_cfg is not None else []
                if race_id in retry_list:
                    log.info(f"Race {race_id} is in retry list")
    except Exception as exc:
        log.debug(f"Race outcome template check failed: {exc}")


def mant_after_hook(ctx, img):
    from module.umamusume.context import detected_portraits_log
    from module.umamusume.persistence import set_ignore_cat_food, set_ignore_grilled_carrots

    favor = detected_portraits_log.get("President Akikawa", {}).get("favor", 0)
    if favor >= 2:
        set_ignore_cat_food(True)

    all_rainbow = True
    for info in detected_portraits_log.values():
        if not info.get('is_npc', False):
            if info.get('favor', 0) < 4:
                all_rainbow = False
                break
    if all_rainbow and detected_portraits_log:
        set_ignore_grilled_carrots(True)

    try:
        from module.umamusume.scenario.mant.race_reward_items import check_and_detect_race_reward_items
        screen = getattr(ctx, 'current_screen', None)
        if screen is not None:
            check_and_detect_race_reward_items(screen, img, ctx)
    except Exception:
        pass

    _check_race_outcome(ctx, img)

    return False
