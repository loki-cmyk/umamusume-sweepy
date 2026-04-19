import json
import os

_TIER_LABELS = {
    1: "COACH",
    2: "MOTIV",
    3: "EMPOW",
}

def analyze_jsonl(file_path):
    print(f"{'Turn':<6} | {'Mega':<7} | {'Action':<15} | {'Score':<8} | {'Items Used':<42} | {'Status'}")
    print("-" * 115)
    training_types = ["Speed", "Stamina", "Power", "Guts", "Wit"]

    higher_stats_turns = []
    missed_high_trains = []
    near_miss_megaphones = []
    megaphone_activations = []   # (turn, name, tier, active_on_turns)

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
            except:
                continue

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

            max_score = max(scores)
            max_index = scores.index(max_score)
            max_train_type = training_types[max_index]
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

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    jsonl_path = os.path.join(script_dir, "training_analysis.jsonl")

    if not os.path.exists(jsonl_path):
        print(f"Error: {jsonl_path} not found.")
        print("Please ensure 'log_training_data: true' is set in config.yaml and run the bot to generate the training log.")
    else:
        analyze_jsonl(jsonl_path)

