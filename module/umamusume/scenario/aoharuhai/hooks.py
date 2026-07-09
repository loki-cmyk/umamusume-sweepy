import time
import sys
from bot.recog.image_matcher import image_match
from module.umamusume.asset.template import (
    REF_AOHARU_RACE, REF_SELECT_OPP2, REF_ALL_RES, REF_RACE_END, REF_RACE_END2,
    REF_TEAM_SHOWDOWN, REF_NEXT, REF_ROUND_1, REF_ROUND_2, REF_ROUND_3, REF_ROUND_4,
    REF_AOHARUHAI_TEAM_NAME_0, REF_AOHARUHAI_TEAM_NAME_1, REF_AOHARUHAI_TEAM_NAME_2,
    REF_AOHARUHAI_TEAM_NAME_3, REF_RACE_TRY_AGAIN, REF_TRY_AGAIN_POP_UP, REF_BEGIN_SHOWDOWN, REF_UNITY_FINALS,
    REF_RACE_UNITY_ZENITH
)
import bot.base.log as logger

log = logger.get_logger(__name__)


def aoharuhai_after_hook(ctx, img):
    if image_match(img, REF_AOHARU_RACE).find_match:
        try:
            cd = getattr(getattr(ctx, 'cultivate_detail', None), 'event_cooldown_until', 0)
            if isinstance(cd, (int, float)) and time.time() < cd:
                return True
        except Exception:
            pass

        try:
            h, w = img.shape[:2]
            team_roi_x1, team_roi_y1, team_roi_x2, team_roi_y2 = 70, 315, 162, 811
            team_roi_x1 = max(0, min(w, team_roi_x1))
            team_roi_x2 = max(team_roi_x1, min(w, team_roi_x2))
            team_roi_y1 = max(0, min(h, team_roi_y1))
            team_roi_y2 = max(team_roi_y1, min(h, team_roi_y2))
            team_roi = img[team_roi_y1:team_roi_y2, team_roi_x1:team_roi_x2]
            
            for team_tpl in [REF_AOHARUHAI_TEAM_NAME_0, REF_AOHARUHAI_TEAM_NAME_1, 
                             REF_AOHARUHAI_TEAM_NAME_2, REF_AOHARUHAI_TEAM_NAME_3]:
                if image_match(team_roi, team_tpl).find_match:
                    log.info("Team name selection screen detected, skipping auto-click")
                    return True
        except Exception:
            pass
        
        try:
            ti = getattr(getattr(ctx, 'cultivate_detail', None), 'turn_info', None)
            roi = img[343:389, 443:485]
            refs = [REF_ROUND_1, REF_ROUND_2, REF_ROUND_3, REF_ROUND_4]
            found = False
            for i, tpl in enumerate(refs):
                try:
                    if image_match(roi, tpl).find_match:
                        if ti is not None:
                            ti.aoharu_race_index = i
                        found = True
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if not found and image_match(img, REF_UNITY_FINALS).find_match:
            ti.aoharu_race_index = 4
            log.info("Unity Finals detected.")
        ctx.ctrl.click(344, 1091, 'Aoharu race')
        return True

    if image_match(img, REF_SELECT_OPP2).find_match:
        try:
            sc = getattr(ctx.task.detail, 'scenario_config', None)
            aoharu_cfg = getattr(sc, 'aoharu_config', None)
            ti = getattr(getattr(ctx, 'cultivate_detail', None), 'turn_info', None)
            idx = getattr(ti, 'aoharu_race_index', None)
            prs = getattr(aoharu_cfg, 'preliminary_round_selections', None)
            if isinstance(idx, int) and isinstance(prs, (list, tuple)) and 0 <= idx < len(prs):
                sel = prs[idx]
                if sel == 1:
                    log.info("Selected opponent #1")
                    ctx.ctrl.click(339, 278, 'Select opponent #1')
                    time.sleep(0.5)
                elif sel == 2:
                    log.info("Selected opponent #2")
                    ctx.ctrl.click(335, 574, 'Select opponent #2')
                    time.sleep(0.5)
                elif sel == 3:
                    log.info("Selected opponent #3")
                    ctx.ctrl.click(339, 830, 'Select opponent #3')
                    time.sleep(0.5)
        except Exception:
            pass
        ctx.ctrl.click(355, 1082, 'Click Select Opponent button')
        time.sleep(0.5)
        ctx.ctrl.click(522, 930, 'Select Begin Showdown')
        time.sleep(0.17)
        ctx.ctrl.click(522, 930, 'Select Begin Showdown (retry)')
        return True

    if image_match(img, REF_ALL_RES).find_match:
        ctx.ctrl.click(536, 1211, 'Select All Results button')
        return True

    from module.umamusume.script.cultivate_task.helpers import handle_clock_retry
    if handle_clock_retry(ctx, img):
        return True

    if image_match(img, REF_RACE_END).find_match:
        time.sleep(0.5)
        ctx.ctrl.click(351, 1112, 'Close race result panel')
        return True

    race_end2_res = image_match(img, REF_RACE_END2)
    if race_end2_res.find_match:
        cx, cy = race_end2_res.center_point
        time.sleep(0.5)
        ctx.ctrl.click(cx, cy, 'Close race result panel')
        return True

    if image_match(img, REF_BEGIN_SHOWDOWN).find_match:
        time.sleep(0.5)
        ctx.ctrl.click(522, 930, 'Select Begin Showdown')
        return True

    if image_match(img, REF_RACE_UNITY_ZENITH).find_match:
        log.info("Starting final race (Zenith)")
        ctx.ctrl.click(354, 961, 'Team Zenith Race button')
        time.sleep(0.5)
        ctx.ctrl.click(522, 930, 'Select Opponent')
        return True

    # Fallback in case image mathing on Team Zenith fails
    if image_match(img[0:33, 0:180], REF_TEAM_SHOWDOWN).find_match:
        ti = getattr(getattr(ctx, 'cultivate_detail', None), 'turn_info', None)
        idx = getattr(ti, 'aoharu_race_index', None)
        if idx == 4:
            log.info("Starting final race (fallback)")
            ctx.ctrl.click(354, 961, 'Team Zenith Race button')
            time.sleep(0.5)
            ctx.ctrl.click(522, 930, 'Select Opponent')
        return True

    if image_match(img[1097:1124, 327:393], REF_NEXT).find_match:
        ctx.ctrl.click(360, 1112, 'Click Next')
        return True

    return False
