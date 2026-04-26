import json
import os

_TIER_LABELS = {
    1: "COACH",
    2: "MOTIV",
    3: "EMPOW",
}

STAT_KEYS = ["speed", "stamina", "power", "guts", "wits"]
MAX_STAT_GAIN_THRESHOLD = 300  # Total stat gain > 300 is likely an OCR error


def analyze_jsonl(file_path):
    print(f"{'Turn':<6} | {'Mega':<7} | {'Action':<15} | {'Score':<8} | {'Items Used':<42} | {'Status'}")
    print("-" * 115)
    training_types = ["Speed", "Stamina", "Power", "Guts", "Wit"]

    higher_stats_turns = []
    missed_high_trains = []
    near_miss_megaphones = []
    megaphone_activations = []   # (turn, name, tier, active_on_turns)

    # New data structures for per-run analysis
    run_snapshots = {}   # run_id -> [snapshot_data, ...]
    run_post_stats = {}  # run_id -> {turn: post_stats_dict, ...}
    run_summaries = {}   # run_id -> summary_dict
    legacy_snapshots = []  # entries without run_id (backward compat)

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
            except:
                continue

            entry_type = data.get("type")

            # Handle post_stats entries
            if entry_type == "post_stats":
                rid = data.get("run_id")
                if rid:
                    if rid not in run_post_stats:
                        run_post_stats[rid] = {}
                    run_post_stats[rid][data.get("turn")] = data.get("post_stats", {})
                continue

            # Handle run_summary entries
            if entry_type == "run_summary":
                rid = data.get("run_id")
                if rid:
                    run_summaries[rid] = data
                continue

            # Everything else is a turn snapshot (type="turn_snapshot" or legacy entries without type)
            rid = data.get("run_id")
            if rid:
                if rid not in run_snapshots:
                    run_snapshots[rid] = []
                run_snapshots[rid].append(data)
            else:
                legacy_snapshots.append(data)

            # === Existing per-turn analysis (unchanged) ===
            turn = data.get("turn_counter")
            detail = data.get("detail", {})
            turn_info = detail.get("turn_info", {})
            scores = turn_info.get("cached_computed_scores", [])
            operation = turn_info.get("turn_operation", {})
            op_type = operation.get("turn_operation_type")
            chosen_train = operation.get("training_type")

            # Megaphone state from the top-level megaphone_status block
            mega_status = data.get("megaphone_status")  # None if not active
            mega_active = mega_status is not None
            mega_label = ""
            if mega_active:
                tier = mega_status.get("tier", 0)
                mega_label = _TIER_LABELS.get(tier, f"T{tier}")
                # Record activation: first turn the megaphone appears in a new window
                active_turns = mega_status.get("active_on_turns", [])
                if active_turns and turn == active_turns[0]:
                    megaphone_activations.append((
                        turn,
                        mega_status.get("name", "Megaphone"),
                        tier,
                        active_turns,
                    ))

            # Megaphone near-miss metrics (still on turn_info from the scorer)
            mega_perc = turn_info.get("megaphone_percentile")
            mega_thresh = turn_info.get("megaphone_threshold")

            # Inventory check for megaphones available but not active
            owned_items = detail.get("mant_owned_items", [])
            owned_map = {n: q for n, q in owned_items}
            has_megas = any("Megaphone" in n for n, q in owned_map.items() if q > 0)

            # Extract used items
            used_items = [k.replace("_used", "").replace("_", " ").title()
                          for k, v in turn_info.items()
                          if k.endswith("_used") and v is True and k != "energy_item_used"]
            items_str = ", ".join(used_items) if used_items else "-"
            mega_used_this_turn = any("Megaphone" in item for item in used_items)

            # Stats calculation
            trainings = turn_info.get("training_info_list", [])
            stat_sums = []
            for t_info in trainings:
                res = t_info.get("stat_results", {})
                stat_sums.append(sum(res.values()))

            if not scores:
                continue

            max_score = max(scores[:5])
            max_index = scores.index(max_score)
            max_train_type = training_types[max_index] if max_index < len(training_types) else "Unknown"
            max_train_stats = stat_sums[max_index] if max_index < len(stat_sums) else 0

            chosen_index = -1
            if chosen_train == "TRAINING_TYPE_SPEED": chosen_index = 0
            elif chosen_train == "TRAINING_TYPE_STAMINA": chosen_index = 1
            elif chosen_train == "TRAINING_TYPE_POWER": chosen_index = 2
            elif chosen_train == "TRAINING_TYPE_WILL": chosen_index = 3
            elif chosen_train == "TRAINING_TYPE_INTELLIGENCE": chosen_index = 4

            status = ""
            current_score = 0
            stats_msg = ""
            mega_msg = ""

            if op_type == "TURN_OPERATION_TYPE_TRAINING" or (op_type == "TURN_OPERATION_TYPE_REST" and chosen_train == "TRAINING_TYPE_INTELLIGENCE"):
                if chosen_index != -1 and chosen_index < len(stat_sums):
                    current_score = scores[chosen_index]
                    current_stats = stat_sums[chosen_index]
                    max_stats = max(stat_sums)
                    max_stats_index = stat_sums.index(max_stats)
                    max_stats_type = training_types[max_stats_index]

                    if max_stats > current_stats + 0.1:
                        stats_msg = f"Higher Stats available: {max_stats_type} ({max_stats})"
                        higher_stats_turns.append((turn, training_types[chosen_index], current_stats, max_stats_type, max_stats))

                    # Check for megaphone near-misses (had megas available but didn't fire)
                    if not mega_active and not mega_used_this_turn and has_megas and mega_perc is not None and mega_thresh is not None:
                        if mega_perc < mega_thresh and mega_perc > mega_thresh - 15:
                            mega_msg = f"MEGA NEAR MISS: {mega_perc:.1f}/{mega_thresh:.1f}"
                            near_miss_megaphones.append((turn, training_types[chosen_index], current_stats, mega_perc, mega_thresh))
                else:
                    status = "TRAINING TYPE MISMATCH"
            else:
                # Not a training turn
                if max_score > 0.6:
                    status = f"HIGH TRAINING MISSED ({max_train_type}: {max_score:.2f}, Stats: {max_train_stats})"
                    missed_high_trains.append((turn, op_type, max_train_type, max_score, max_train_stats))

            if stats_msg:
                status = f"{status} | {stats_msg}" if status else stats_msg
            if mega_msg:
                status = f"{status} | {mega_msg}" if status else mega_msg

            action_desc = training_types[chosen_index].upper() if chosen_index != -1 else op_type.replace("TURN_OPERATION_TYPE_", "")
            print(f"{turn:<6} | {mega_label:<7} | {action_desc:<15} | {current_score:<8.4f} | {items_str:<42} | {status}")

    # === Existing Summary ===
    print("\n" + "="*30)
    print("SUMMARY")

    print(f"\nMegaphone Activations: {len(megaphone_activations)}")
    for t, name, tier, active_turns in megaphone_activations:
        label = _TIER_LABELS.get(tier, f"T{tier}")
        turns_str = ", ".join(str(x) for x in active_turns)
        print(f"  Turn {t}: [{label}] {name} — active on turns: {turns_str}")

    print(f"\nMegaphone Near-Misses (available but percentile < threshold): {len(near_miss_megaphones)}")
    for t, c, c_stats, mp, mt in near_miss_megaphones:
        print(f"  Turn {t}: {c} stats {c_stats}. Percentile {mp:.1f} missed threshold {mt:.1f}")

    print(f"\nHigher Raw Stats Available but not chosen: {len(higher_stats_turns)}")
    for t, c, c_stats, m, m_stats in higher_stats_turns:
        print(f"  Turn {t}: Chose {c} (Total Stats: {c_stats}) but {m} had {m_stats}")

    print(f"\nHigh-Value Trainings Missed (score > 0.6): {len(missed_high_trains)}")
    for t, op, m, ms, s in missed_high_trains:
        print(f"  Turn {t}: {op} taken instead of {m} (Score: {ms:.4f}, Stats: {s})")

    # === New: Per-Run Summary ===
    if run_summaries:
        print("\n" + "="*60)
        print("PER-RUN SUMMARIES")
        print("="*60)
        print(f"{'Run ID':<12} | {'Scenario':<12} | {'Turns':<6} | {'Speed':<6} | {'Stam':<6} | {'Power':<6} | {'Guts':<6} | {'Wits':<6} | {'Total':<6}")
        print("-" * 90)
        for rid, summary in run_summaries.items():
            fs = summary.get("final_stats", {})
            scenario = summary.get("scenario", "?")
            total_turns = summary.get("total_turns", "?")
            spd = fs.get("speed", 0)
            sta = fs.get("stamina", 0)
            pwr = fs.get("power", 0)
            gut = fs.get("guts", 0)
            wit = fs.get("wits", 0)
            total = spd + sta + pwr + gut + wit
            short_id = rid[:10] + ".." if len(rid) > 12 else rid
            print(f"{short_id:<12} | {scenario:<12} | {total_turns:<6} | {spd:<6} | {sta:<6} | {pwr:<6} | {gut:<6} | {wit:<6} | {total:<6}")

    # === New: Per-Turn Stat Delta Analysis ===
    if run_snapshots and run_post_stats:
        print("\n" + "="*60)
        print("STAT DELTA ANALYSIS (pre vs post)")
        print("="*60)

        total_deltas = 0
        total_matched = 0
        total_unmatched = 0
        all_deltas = []

        for rid in run_snapshots:
            post_data = run_post_stats.get(rid, {})
            if not post_data:
                continue

            snapshots = run_snapshots[rid]
            short_id = rid[:10] + ".." if len(rid) > 12 else rid
            run_deltas = []

            for snap in snapshots:
                turn = snap.get("turn_counter")
                pre = snap.get("pre_stats")
                post = post_data.get(turn)

                if pre is None or post is None:
                    continue

                delta = {}
                delta_total = 0
                for key in STAT_KEYS:
                    d = post.get(key, 0) - pre.get(key, 0)
                    delta[key] = d
                    delta_total += d

                # Get what training was chosen
                detail = snap.get("detail", {})
                ti = detail.get("turn_info", {})
                op = ti.get("turn_operation", {})
                op_type = op.get("turn_operation_type", "")
                chosen_train = op.get("training_type", "")

                if delta_total > MAX_STAT_GAIN_THRESHOLD:
                    print(f"  WARNING: Run {short_id} Turn {turn} has impossible stat gain (+{delta_total}). Ignoring outlier.")
                    continue

                run_deltas.append({
                    "turn": turn,
                    "delta": delta,
                    "delta_total": delta_total,
                    "op_type": op_type,
                    "chosen_train": chosen_train,
                })
                total_deltas += 1

            if run_deltas:
                training_deltas = [d for d in run_deltas if d["op_type"] == "TURN_OPERATION_TYPE_TRAINING"]
                if training_deltas:
                    avg_delta = sum(d["delta_total"] for d in training_deltas) / len(training_deltas)
                    max_delta = max(d["delta_total"] for d in training_deltas)
                    min_delta = min(d["delta_total"] for d in training_deltas)
                    print(f"\n  Run {short_id}: {len(training_deltas)} training turns")
                    print(f"    Avg stat gain per training: {avg_delta:.1f}")
                    print(f"    Best turn: +{max_delta}  |  Worst turn: +{min_delta}")

                    # Show turns with zero or negative deltas (possible OCR errors or events)
                    zero_turns = [d for d in training_deltas if d["delta_total"] <= 0]
                    if zero_turns:
                        print(f"    WARNING: {len(zero_turns)} training turn(s) with zero/negative stat gain:")
                        for d in zero_turns:
                            print(f"      Turn {d['turn']}: {d['delta']} (chose {d['chosen_train']})")

                    all_deltas.extend(training_deltas)

        if all_deltas:
            overall_avg = sum(d["delta_total"] for d in all_deltas) / len(all_deltas)
            print(f"\n  Overall: {len(all_deltas)} training decisions across {len(run_snapshots)} run(s)")
            print(f"  Average stat gain per training: {overall_avg:.1f}")

    # === New: Decision Quality Per Run ===
    if run_snapshots and run_summaries:
        print("\n" + "="*60)
        print("DECISION QUALITY CORRELATION")
        print("="*60)
        print("Compares greedy-optimal picks vs scorer picks and final outcomes.\n")

        run_results = []
        for rid in run_snapshots:
            summary = run_summaries.get(rid)
            if not summary:
                continue

            snapshots = run_snapshots[rid]
            greedy_picks = 0
            scorer_overrides = 0
            total_training_turns = 0

            for snap in snapshots:
                detail = snap.get("detail", {})
                ti = detail.get("turn_info", {})
                op = ti.get("turn_operation", {})
                op_type = op.get("turn_operation_type", "")

                if op_type != "TURN_OPERATION_TYPE_TRAINING":
                    continue

                total_training_turns += 1
                chosen_train = op.get("training_type", "")
                trainings = ti.get("training_info_list", [])

                # Find which training had highest raw stats
                stat_sums = []
                for t_info in trainings:
                    res = t_info.get("stat_results", {})
                    stat_sums.append(sum(res.values()))

                if not stat_sums:
                    continue

                max_stat_idx = stat_sums.index(max(stat_sums))
                type_names = ["TRAINING_TYPE_SPEED", "TRAINING_TYPE_STAMINA", "TRAINING_TYPE_POWER",
                              "TRAINING_TYPE_WILL", "TRAINING_TYPE_INTELLIGENCE"]
                greedy_type = type_names[max_stat_idx] if max_stat_idx < len(type_names) else ""

                if chosen_train == greedy_type:
                    greedy_picks += 1
                else:
                    scorer_overrides += 1

            fs = summary.get("final_stats", {})
            total_stats = sum(fs.get(k, 0) for k in STAT_KEYS)
            greedy_pct = (greedy_picks / total_training_turns * 100) if total_training_turns > 0 else 0

            run_results.append({
                "rid": rid,
                "greedy_pct": greedy_pct,
                "total_stats": total_stats,
                "training_turns": total_training_turns,
                "overrides": scorer_overrides,
            })

        if run_results:
            print(f"{'Run ID':<12} | {'Greedy %':<9} | {'Overrides':<10} | {'Train Turns':<12} | {'Final Stats':<12}")
            print("-" * 65)
            for r in run_results:
                short_id = r["rid"][:10] + ".." if len(r["rid"]) > 12 else r["rid"]
                print(f"{short_id:<12} | {r['greedy_pct']:<9.1f} | {r['overrides']:<10} | {r['training_turns']:<12} | {r['total_stats']:<12}")

            if len(run_results) >= 2:
                # Check if higher greedy % correlates with higher final stats
                sorted_by_greedy = sorted(run_results, key=lambda x: x["greedy_pct"])
                sorted_by_stats = sorted(run_results, key=lambda x: x["total_stats"])
                print(f"\n  Highest greedy%: {sorted_by_greedy[-1]['greedy_pct']:.1f}% -> {sorted_by_greedy[-1]['total_stats']} total stats")
                print(f"  Lowest greedy%:  {sorted_by_greedy[0]['greedy_pct']:.1f}% -> {sorted_by_greedy[0]['total_stats']} total stats")
                print(f"  Best final stats: {sorted_by_stats[-1]['total_stats']} (greedy: {sorted_by_stats[-1]['greedy_pct']:.1f}%)")
                print(f"  Worst final stats: {sorted_by_stats[0]['total_stats']} (greedy: {sorted_by_stats[0]['greedy_pct']:.1f}%)")
        else:
            print("  No completed runs with both snapshots and summaries found.")

    # === New: Weight Sensitivity Report ===
    if run_snapshots and run_summaries:
        print("\n" + "="*60)
        print("WEIGHT SENSITIVITY REPORT")
        print("="*60)
        print("Shows how often scorer deviates from raw stat maximization\n")

        override_reasons = {
            "support_card_bonus": 0,
            "energy_management": 0,
            "hint_bonus": 0,
            "failure_rate": 0,
            "target_cap": 0,
            "period_weight": 0,
            "other": 0,
        }
        total_overrides = 0

        for rid in run_snapshots:
            for snap in run_snapshots[rid]:
                detail = snap.get("detail", {})
                ti = detail.get("turn_info", {})
                op = ti.get("turn_operation", {})
                op_type = op.get("turn_operation_type", "")

                if op_type != "TURN_OPERATION_TYPE_TRAINING":
                    continue

                chosen_train = op.get("training_type", "")
                trainings = ti.get("training_info_list", [])
                scores = ti.get("cached_computed_scores", [])

                stat_sums = []
                for t_info in trainings:
                    res = t_info.get("stat_results", {})
                    stat_sums.append(sum(res.values()))

                if not stat_sums or not scores or len(scores) < 5:
                    continue

                max_stat_idx = stat_sums.index(max(stat_sums))
                type_names = ["TRAINING_TYPE_SPEED", "TRAINING_TYPE_STAMINA", "TRAINING_TYPE_POWER",
                              "TRAINING_TYPE_WILL", "TRAINING_TYPE_INTELLIGENCE"]
                greedy_type = type_names[max_stat_idx] if max_stat_idx < len(type_names) else ""

                if chosen_train == greedy_type:
                    continue

                total_overrides += 1

                # Try to identify why the scorer deviated
                chosen_idx = type_names.index(chosen_train) if chosen_train in type_names else -1
                if chosen_idx == -1:
                    override_reasons["other"] += 1
                    continue

                chosen_ti = trainings[chosen_idx] if chosen_idx < len(trainings) else {}
                greedy_ti = trainings[max_stat_idx] if max_stat_idx < len(trainings) else {}

                # Check for support card differences
                chosen_sc = len(chosen_ti.get("support_card_info_list", []))
                greedy_sc = len(greedy_ti.get("support_card_info_list", []))
                if chosen_sc > greedy_sc:
                    override_reasons["support_card_bonus"] += 1
                elif chosen_ti.get("has_hint", False) and not greedy_ti.get("has_hint", False):
                    override_reasons["hint_bonus"] += 1
                elif (greedy_ti.get("failure_rate", 0) or 0) > (chosen_ti.get("failure_rate", 0) or 0):
                    override_reasons["failure_rate"] += 1
                elif abs(chosen_ti.get("energy_change", 0) or 0) > abs(greedy_ti.get("energy_change", 0) or 0):
                    override_reasons["energy_management"] += 1
                elif chosen_idx == 4:  # Wit chosen over higher stats
                    override_reasons["energy_management"] += 1
                else:
                    override_reasons["other"] += 1

        if total_overrides > 0:
            print(f"  Total scorer overrides of greedy-optimal: {total_overrides}")
            for reason, count in sorted(override_reasons.items(), key=lambda x: -x[1]):
                if count > 0:
                    pct = count / total_overrides * 100
                    print(f"    {reason:<25}: {count:>4} ({pct:.1f}%)")
        else:
            print("  No scorer overrides detected (scorer always picked highest raw stats).")

    # === Suggested Actions ===
    if run_summaries and run_snapshots:
        print("\n" + "="*60)
        print("SUGGESTED ACTIONS")
        print("="*60)

        suggestions = []
        num_runs = len(run_summaries)

        if num_runs < 5:
            suggestions.append(
                f"[DATA] Only {num_runs} completed run(s). Collect at least 5 runs before "
                "drawing conclusions — RNG variance is too high with fewer runs."
            )

        # Analyze greedy correlation if we have enough runs
        if 'run_results' in dir() or (run_snapshots and run_summaries):
            try:
                if len(run_results) >= 3:
                    # Compute simple correlation: do higher greedy% runs have higher stats?
                    sorted_by_greedy = sorted(run_results, key=lambda x: x["greedy_pct"])
                    top_half = sorted_by_greedy[len(sorted_by_greedy)//2:]
                    bot_half = sorted_by_greedy[:len(sorted_by_greedy)//2]

                    if top_half and bot_half:
                        avg_stats_high_greedy = sum(r["total_stats"] for r in top_half) / len(top_half)
                        avg_stats_low_greedy = sum(r["total_stats"] for r in bot_half) / len(bot_half)
                        diff = avg_stats_high_greedy - avg_stats_low_greedy

                        if diff > 50:
                            suggestions.append(
                                f"[WEIGHTS] Runs with higher greedy% averaged {diff:.0f} more total stats. "
                                "The scorer's overrides are HURTING performance. Consider reducing "
                                "the following in Advanced Options → Score Value:"
                            )
                            # Give specific advice based on override reasons
                            if total_overrides > 0:
                                top_reason = max(override_reasons, key=override_reasons.get)
                                top_pct = override_reasons[top_reason] / total_overrides * 100
                                if top_reason == "support_card_bonus":
                                    suggestions.append(
                                        f"  → Support card bonuses cause {top_pct:.0f}% of overrides. "
                                        "Lower the 'Blue Friendship' (1st) and 'Green Friendship' (2nd) "
                                        "values in Score Value for the affected periods."
                                    )
                                elif top_reason == "hint_bonus":
                                    suggestions.append(
                                        f"  → Hint bonuses cause {top_pct:.0f}% of overrides. "
                                        "Lower the 'Hint' (4th) value in Score Value for the "
                                        "affected periods."
                                    )
                                elif top_reason == "failure_rate":
                                    suggestions.append(
                                        f"  → Failure rate avoidance causes {top_pct:.0f}% of overrides. "
                                        "The scorer is being too cautious about training failures. "
                                        "This is not adjustable via the UI — the penalty formula "
                                        "(fr/28)^2 in training_select.py could be softened."
                                    )
                                elif top_reason == "energy_management":
                                    suggestions.append(
                                        f"  → Energy management causes {top_pct:.0f}% of overrides. "
                                        "Lower the 'Energy Change (+/-)' (3rd) value in Score Value "
                                        "for the affected periods. Also check if your rest threshold "
                                        "is too high."
                                    )
                        elif diff < -50:
                            suggestions.append(
                                f"[OK] Runs with more scorer overrides averaged {-diff:.0f} more total stats. "
                                "The scorer's overrides are HELPING. Your current weights are working well — "
                                "no changes needed."
                            )
                        else:
                            suggestions.append(
                                f"[NEUTRAL] No meaningful correlation between greedy% and final stats "
                                f"(difference: {diff:+.0f}). The scorer overrides neither help nor hurt. "
                                "RNG dominates — weight tuning won't have a big impact."
                            )

                    # Check override rate
                    avg_greedy = sum(r["greedy_pct"] for r in run_results) / len(run_results)
                    if avg_greedy > 85:
                        suggestions.append(
                            f"[INFO] Scorer agrees with greedy-optimal {avg_greedy:.0f}% of the time. "
                            "The non-stat weights rarely change the outcome."
                        )
                    elif avg_greedy < 50:
                        suggestions.append(
                            f"[WARNING] Scorer only picks greedy-optimal {avg_greedy:.0f}% of the time. "
                            "Non-stat weights are heavily influencing decisions. If final stats are "
                            "suffering, this is likely the cause."
                        )
            except Exception:
                pass

        # Stat delta suggestions
        if run_post_stats:
            all_zero_delta_count = 0
            all_training_count = 0
            for rid in run_snapshots:
                post_data = run_post_stats.get(rid, {})
                for snap in run_snapshots[rid]:
                    turn = snap.get("turn_counter")
                    pre = snap.get("pre_stats")
                    post = post_data.get(turn)
                    detail = snap.get("detail", {})
                    ti = detail.get("turn_info", {})
                    op = ti.get("turn_operation", {})
                    if op.get("turn_operation_type") != "TURN_OPERATION_TYPE_TRAINING":
                        continue
                    all_training_count += 1
                    if pre and post:
                        delta_total = sum(post.get(k, 0) - pre.get(k, 0) for k in STAT_KEYS)
                        if delta_total <= 0:
                            all_zero_delta_count += 1

            if all_training_count > 0 and all_zero_delta_count > 0:
                zero_pct = all_zero_delta_count / all_training_count * 100
                if zero_pct > 10:
                    suggestions.append(
                        f"[BUG] {zero_pct:.0f}% of training turns show zero or negative stat gains. "
                        "This likely indicates OCR misreads or events overriding stats between turns. "
                        "Investigate these turns in the per-turn log above."
                    )
                elif zero_pct > 3:
                    suggestions.append(
                        f"[INFO] {all_zero_delta_count} training turn(s) ({zero_pct:.1f}%) show "
                        "zero/negative stat gains. A few are normal (events can reduce stats), "
                        "but if this number grows, check OCR accuracy."
                    )

        if not suggestions:
            suggestions.append("[OK] No issues detected. Collect more runs for higher-confidence analysis.")

        for s in suggestions:
            # Replace arrow with compatible characters for Windows CP1252
            # Move outside f-string to avoid backslash restriction in older Python versions
            safe_s = s.replace('\u2192', '->')
            print(f"\n  {safe_s}")
        print()


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    jsonl_path = os.path.join(script_dir, "training_analysis.jsonl")

    if not os.path.exists(jsonl_path):
        print(f"Error: {jsonl_path} not found.")
        print("Please ensure 'log_training_data: true' is set in config.yaml and run the bot to generate the training log.")
    else:
        analyze_jsonl(jsonl_path)

