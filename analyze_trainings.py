import os
import sys
import sqlite3
import argparse

STAT_KEYS = ["speed", "stamina", "power", "guts", "wits"]

def get_db_connection():
    db_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'module', 'umamusume', 'db', 'cultivate_data.db'))
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        print("Please run the bot to generate cultivation history first.")
        sys.exit(1)
    return sqlite3.connect(db_path)

def print_runs_summary(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, scenario_type, total_turns, final_speed, final_stamina, final_power, final_guts, final_wits, final_sp, started_at
        FROM runs
        ORDER BY started_at DESC
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("No cultivation runs found in database.")
        return None
        
    print("\n" + "="*80)
    print(f"{'CULTIVATION RUNS HISTORY':^80}")
    print("="*80)
    print(f"{'Run ID':<15} | {'Scenario':<12} | {'Turns':<5} | {'Speed':<5} | {'Stam':<5} | {'Power':<5} | {'Guts':<5} | {'Wits':<5} | {'Total':<5} | {'Started At'}")
    print("-" * 110)
    
    for r in rows:
        rid, scenario, turns, spd, sta, pwr, gut, wit, sp, started = r
        short_id = rid[:13] + ".." if len(rid) > 15 else rid
        turns_str = str(turns) if turns is not None else "-"
        
        if spd is not None and sta is not None and pwr is not None and gut is not None and wit is not None:
            tot = spd + sta + pwr + gut + wit
            stat_cols = f"{spd:<5} | {sta:<5} | {pwr:<5} | {gut:<5} | {wit:<5} | {tot:<5}"
        else:
            stat_cols = f"{'-':<5} | {'-':<5} | {'-':<5} | {'-':<5} | {'-':<5} | {'-':<5}"
            
        print(f"{short_id:<15} | {scenario:<12} | {turns_str:<5} | {stat_cols} | {started}")
        
    return rows[0][0]  # return latest run ID

def print_run_details(conn, run_id):
    cursor = conn.cursor()
    cursor.execute("SELECT scenario_type, started_at FROM runs WHERE id = ?", (run_id,))
    run_info = cursor.fetchone()
    if not run_info:
        print(f"Run {run_id} not found.")
        return
        
    print("\n" + "="*90)
    print(f"DETAILED ANALYSIS FOR RUN: {run_id} ({run_info[0]} | {run_info[1]})")
    print("="*90)
    print(f"{'Turn':<5} | {'Action Chosen':<22} | {'Score':<8} | {'Greedy Action':<22} | {'Stats Gain':<10} | {'Status'}")
    print("-" * 110)
    
    cursor.execute("""
        SELECT date, action, max_score, chosen_stats, max_stats, greedy_type, is_override, override_reason,
               pre_speed, post_speed, pre_stamina, post_stamina, pre_power, post_power,
               pre_guts, post_guts, pre_wits, post_wits, pre_sp, post_sp
        FROM training_analysis
        WHERE run_id = ?
        ORDER BY date ASC
    """, (run_id,))
    rows = cursor.fetchall()
    
    higher_stats_turns = []
    override_reasons = {}
    total_training_turns = 0
    total_overrides = 0
    
    for r in rows:
        date, action, max_score, chosen_stats, max_stats, greedy_type, is_override, override_reason, \
        pre_spd, post_spd, pre_sta, post_sta, pre_pwr, post_pwr, pre_gut, post_gut, pre_wit, post_wit, pre_sp, post_sp = r
        
        # Calculate actual delta if post-stats are filled
        delta_str = "-"
        if post_spd is not None and post_spd > 0:
            spd_d = post_spd - pre_spd
            sta_d = post_sta - pre_sta
            pwr_d = post_pwr - pre_pwr
            gut_d = post_gut - pre_gut
            wit_d = post_wit - pre_wit
            total_d = spd_d + sta_d + pwr_d + gut_d + wit_d
            delta_str = f"+{total_d}"
            
        score_str = f"{max_score:.4f}" if max_score is not None else "-"
        greedy_desc = greedy_type if greedy_type else "-"
        
        # Formulate status
        status = "OK"
        is_training = "TRAINING_TYPE_" in action or action in ["Speed", "Stamina", "Power", "Guts", "Wit", "Intelligence"]
        
        if is_training:
            total_training_turns += 1
            if is_override:
                total_overrides += 1
                status = f"OVERRIDE ({override_reason})"
                override_reasons[override_reason] = override_reasons.get(override_reason, 0) + 1
                
                # Check if higher raw stats were available
                if max_stats is not None and chosen_stats is not None and max_stats > chosen_stats + 0.1:
                    higher_stats_turns.append((date, action, chosen_stats, greedy_type, max_stats))
                    
        else:
            status = "Non-Training"
            
        action_disp = action.replace("TURN_OPERATION_TYPE_", "").replace("TRAINING_TYPE_", "").title()
        greedy_disp = greedy_desc.replace("TRAINING_TYPE_", "").title() if greedy_desc != "-" else "-"
        
        print(f"{date:<5} | {action_disp:<22} | {score_str:<8} | {greedy_disp:<22} | {delta_str:<10} | {status}")
        
    print("\n" + "="*40)
    print("RUN OVERALL STATS")
    print("="*40)
    print(f"  Total training decisions: {total_training_turns}")
    print(f"  Total scorer overrides:   {total_overrides} ({((total_overrides/total_training_turns)*100 if total_training_turns > 0 else 0):.1f}%)")
    
    if override_reasons:
        print("  Overrides by reason:")
        for rsn, cnt in sorted(override_reasons.items(), key=lambda x: -x[1]):
            print(f"    - {rsn:<20}: {cnt:>2} ({(cnt/total_overrides*100):.1f}%)")
            
    if higher_stats_turns:
        print(f"\n  Turns where higher raw stats were available but override selected different training: {len(higher_stats_turns)}")
        for date, act, c_stats, gr_type, m_stats in higher_stats_turns[:10]:
            print(f"    - Turn {date:<2}: Chose {act} (+{c_stats:.0f} stats) but {gr_type} offered +{m_stats:.0f}")
        if len(higher_stats_turns) > 10:
            print(f"    ... and {len(higher_stats_turns)-10} more turns.")

def print_decision_quality_correlation(conn):
    cursor = conn.cursor()
    
    # Query all completed runs
    cursor.execute("""
        SELECT r.id, r.total_turns, r.final_speed, r.final_stamina, r.final_power, r.final_guts, r.final_wits, r.final_sp
        FROM runs r
        WHERE r.final_speed IS NOT NULL
    """)
    runs = cursor.fetchall()
    if len(runs) < 2:
        return
        
    run_results = []
    for r in runs:
        rid, turns, spd, sta, pwr, gut, wit, sp = r
        total_stats = spd + sta + pwr + gut + wit
        
        # Get count of total training and overrides for this run
        cursor.execute("""
            SELECT COUNT(*), SUM(is_override)
            FROM training_analysis
            WHERE run_id = ? AND (action LIKE '%TRAINING%' OR action IN ('Speed', 'Stamina', 'Power', 'Guts', 'Wit', 'Intelligence'))
        """, (rid,))
        total_trains, overrides = cursor.fetchone()
        
        if total_trains and total_trains > 0:
            overrides = overrides if overrides is not None else 0
            greedy_pct = ((total_trains - overrides) / total_trains) * 100
            run_results.append({
                "rid": rid,
                "greedy_pct": greedy_pct,
                "total_stats": total_stats,
                "overrides": overrides
            })
            
    if not run_results:
        return
        
    print("\n" + "="*80)
    print(f"{'DECISION QUALITY & OUTCOMES CORRELATION':^80}")
    print("="*80)
    print(f"{'Run ID':<15} | {'Greedy Pick %':<15} | {'Overrides Count':<18} | {'Final Stats Total'}")
    print("-" * 70)
    
    for res in run_results:
        short_id = res["rid"][:13] + ".." if len(res["rid"]) > 15 else res["rid"]
        print(f"{short_id:<15} | {res['greedy_pct']:<15.1f}% | {res['overrides']:<18} | {res['total_stats']}")
        
    # Analyze trend
    sorted_by_greedy = sorted(run_results, key=lambda x: x["greedy_pct"])
    sorted_by_stats = sorted(run_results, key=lambda x: x["total_stats"])
    print(f"\n  Highest Greedy%: {sorted_by_greedy[-1]['greedy_pct']:.1f}% -> {sorted_by_greedy[-1]['total_stats']} total stats")
    print(f"  Lowest Greedy%:  {sorted_by_greedy[0]['greedy_pct']:.1f}% -> {sorted_by_greedy[0]['total_stats']} total stats")
    print(f"  Best Final Run:  {sorted_by_stats[-1]['total_stats']} stats (Greedy: {sorted_by_stats[-1]['greedy_pct']:.1f}%)")
    
    # Simple correlation hint
    if len(run_results) >= 3:
        high_greedy = sorted_by_greedy[len(sorted_by_greedy)//2:]
        low_greedy = sorted_by_greedy[:len(sorted_by_greedy)//2]
        avg_high = sum(r["total_stats"] for r in high_greedy) / len(high_greedy)
        avg_low = sum(r["total_stats"] for r in low_greedy) / len(low_greedy)
        diff = avg_high - avg_low
        
        print("\n" + "="*40)
        print("SUGGESTED ACTIONS")
        print("="*40)
        if diff > 30:
            print(f"  [SUGGESTION] Runs with higher Greedy% (stat maximizing) averaged +{diff:.0f} more stats.")
            print("  This suggests the Scorer's overrides might be hurting your builds.")
            print("  Consider reducing non-stat weights (e.g., support card / hint bonuses) in settings.")
        elif diff < -30:
            print(f"  [SUGGESTION] Runs with more overrides (cautious/specialized play) averaged +{-diff:.0f} more stats.")
            print("  This suggests the current override weights are highly effective. Keep them!")
        else:
            print("  [INFO] Greedy percentage does not show strong correlation with final stats.")
            print("  Variance and RNG dominate the outcomes. Current override weights are neutral.")

def main():
    parser = argparse.ArgumentParser(description="Analyze cultivation decisions from SQLite database.")
    parser.add_argument("--run-id", type=str, help="Specify a specific run ID to analyze.")
    parser.add_argument("--list", action="store_true", help="Only list the runs history and exit.")
    args = parser.parse_args()
    
    conn = get_db_connection()
    try:
        latest_run_id = print_runs_summary(conn)
        if args.list:
            return
            
        selected_run = args.run_id if args.run_id else latest_run_id
        if selected_run:
            print_run_details(conn, selected_run)
            print_decision_quality_correlation(conn)
        else:
            print("\nNo runs found in database to analyze details.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
