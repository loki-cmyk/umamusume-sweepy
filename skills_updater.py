import json
from bs4 import BeautifulSoup
import re
import os
import sys

# Predefined mapping dictionary from old (JSON) names to new (HTML/Global) names.
# This maps fan-translated or older names to the official Global names.
MAPPING = {
    # Passive/Common Skills
    "Exchange Races": "Collaborative Graded Races",
    "Exchange Races Demon": "Collaborative Graded Races Demon",
    "Skillful Step": "Solid Steps",
    "Mud Play": "Muddy",
    "Gambling Spirit": "Risk-Taker",
    "Short-Distance Racing Passion": "Sprint Race Enthusiast",
    "Self-Assured": "Confident",
    "Inquisitive Mind": "Adventurer",
    "Nocturnal": "Night Races",
    "Tight Turns": "Sharp Turns",
    "Kawasaki Racetrack": "Kawasaki Racecourse",
    "Funabashi Racetrack": "Funabashi Racecourse",
    "Morioka Racetrack": "Morioka Racecourse",
    
    # Dirt / Active Skills
    "Dirt Racing Passion": "Dirt Race Enthusiast",
    "Pressing Feeling": "Oppression",
    "Cloud of Dust": "Dust Cloud",
    "Full of Zeal": "Got the Spirit!",
    "Rapid Ascent": "Rapid Gain",
    
    # Blessings
    "Blessing of the Sun": "Sun's Blessing",
    "Blessing of the Land": "Earth's Blessing",
    "Blessing of the Ocean": "Sea's Blessing",
    
    # Scenario / Hero Skills
    "Voltage Hero": "Energetic Hero",
    "Sunrise Hero": "Sunny Hero",
    "Outside Hero": "Outer Hero",
    "Linkage Hero": "Friendly Hero",
    "Inside Hero": "Inner Hero",
    "Spurt Hero": "Dashing Hero",
    
    # Others / Evolved / Upgrades
    "Halfway to a Dream": "On the Way to Our Dream",
    "Eyes on the Horizon": "Eyes on the Goal",
    "Eager": "Comeback",
    "Steady Advance": "Steady Gait",
    "True Worth": "My True Strength",
    "Early Bird": "Goin' First",
    "Mold Breaker": "Break the Mold",
    "Devil-May-Care": "Scramble",
}

def clean_name(name):
    # Strip circle, double-circle, cross, and question mark suffixes
    cleaned = re.sub(r'\s*[○◎×?？]\s*$', '', name)
    return cleaned.strip()

def detect_page_rarity(soup):
    # Check which rarity filter is currently checked on GameTora page
    if soup.find('input', id='r_normal', checked=True) or soup.find('input', id='r_normal', checked='checked'):
        return "Normal"
    if soup.find('input', id='r_rare', checked=True) or soup.find('input', id='r_rare', checked='checked'):
        return "Rare"
    if soup.find('input', id='r_unique', checked=True) or soup.find('input', id='r_unique', checked='checked'):
        return "Unique"
    return "All"

def get_row_rarity(row, page_rarity):
    # Evolved skills are character-specific and marked as Evolved in the JSON database
    if "evolved skill" in row.text.lower():
        return "Evolved"
        
    if page_rarity != "All":
        return page_rarity
        
    img = row.find('img')
    if not img:
        return "Normal"
        
    img_src = img.get('src', '')
    # Extract number from src, e.g. "10012_JX1K.png" -> "10012"
    match = re.search(r'(\d+)_\w+\.png$', img_src)
    if match:
        icon_id = match.group(1)
        # Rare skills end with '2' (e.g. 10012, 20012)
        if icon_id.endswith('2'):
            return "Rare"
        # Unique skills end with '3' (e.g. 20013)
        elif icon_id.endswith('3'):
            return "Unique"
        # Special Unique/Evolved icon range
        elif len(icon_id) > 5 and icon_id.startswith('101'):
            return "Unique"
            
    # Default to Normal
    return "Normal"

def parse_html_skills(html_path):
    print(f"Reading HTML file: {html_path}...")
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    soup = BeautifulSoup(html_content, 'html.parser')
    page_rarity = detect_page_rarity(soup)
    print(f"Detected page skill rarity filter: {page_rarity}")
    
    rows = soup.find_all('div', class_=lambda c: c and 'skills_table_row' in c)
    print(f"Found {len(rows)} skill rows in the HTML document.")
    
    extracted_skills = []
    
    for row in rows:
        name_div = row.find('div', class_=lambda c: c and 'jpname' in c)
        desc_div = row.find('div', class_=lambda c: c and 'desc' in c)
        
        if not name_div:
            continue
            
        raw_name = name_div.text.strip()
        desc = desc_div.text.strip() if desc_div else ""
        desc = re.sub(r'\s+', ' ', desc).strip()
        
        base_name = clean_name(raw_name)
        row_rarity = get_row_rarity(row, page_rarity)
        
        is_double_circle = raw_name.endswith('◎')
        
        skill_entry = {
            "name": base_name,
            "raw_name": raw_name,
            "description": desc,
            "rarity": row_rarity
        }
        
        existing_idx = next((i for i, x in enumerate(extracted_skills) if x["name"] == base_name and x["rarity"] == row_rarity), None)
        if existing_idx is not None:
            if not is_double_circle:
                extracted_skills[existing_idx] = skill_entry
        else:
            extracted_skills.append(skill_entry)
            
    print(f"Extracted {len(extracted_skills)} unique skills from HTML.")
    return extracted_skills

def name_to_id(name):
    # Convert name to skill_id format (starts with A_ followed by cleaned name)
    # Strip common punctuation: !, ?, ,, ., ♡, #, ()
    clean = re.sub(r"[!,?？.♡#()]", "", name)
    clean = clean.replace("'", "") # strip apostrophes
    # Replace spaces and other symbols with underscores
    clean = re.sub(r'[\s_]+', '_', clean)
    return "A_" + clean

def is_debuff_skill(name, description):
    if name.endswith('×'):
        return True
    desc_lower = description.lower()
    # Check if description specifies slowing down or decreasing stats/speed
    if "decrease" in desc_lower and "decrease fatigue" not in desc_lower and "decrease chance" not in desc_lower and "decrease the chance" not in desc_lower:
        return True
    if "slow down" in desc_lower or "intimidate" in desc_lower:
        return True
    return False

def guess_skill_type(description):
    desc_lower = description.lower()
    if "recover" in desc_lower or "fatigue" in desc_lower:
        return "Recovery"
    if "acceleration" in desc_lower:
        return "Acceleration"
    if "velocity" in desc_lower or "speed" in desc_lower:
        return "Speed"
    if any(k in desc_lower for k in ["performance", "bracket", "track", "ground", "rain", "sun", "snow", "cloud", "weather"]):
        return "Passive"
    return "Others"

def update_skills_json(json_path, extracted_skills):
    print(f"Loading skills database from: {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        skills_db = json.load(f)
        
    updated_count = 0
    id_updates = {}
    
    # Compile a set of mappings including suffix versions dynamically
    expanded_mappings = {}
    for old, new in MAPPING.items():
        expanded_mappings[old] = new
        for suffix in [" Demon", " Averseness"]:
            expanded_mappings[old + suffix] = new + suffix
            
    for item in skills_db:
        old_name = item.get('name', '').strip()
        old_id = item.get('skill_id', '').strip()
        
        matched_name = None
        if old_name in expanded_mappings:
            matched_name = expanded_mappings[old_name]
            
        search_names = [old_name.lower()]
        if matched_name:
            search_names.append(matched_name.lower())
            
        html_match = None
        for sname in search_names:
            html_match = next((x for x in extracted_skills if x["name"].lower() == sname), None)
            if html_match:
                break
                
        # Determine the target new name and rarity
        target_name = old_name
        target_rarity = item.get('rarity')
        
        if html_match:
            target_name = html_match["name"]
            target_rarity = html_match["rarity"]
        elif old_name in expanded_mappings:
            target_name = expanded_mappings[old_name]
            
        # If name, rarity, or ID changed, update the item
        changed = False
        if old_name != target_name:
            item['name'] = target_name
            print(f"Updated name: '{old_name}' -> '{target_name}'")
            changed = True
            
        if item.get('rarity') != target_rarity:
            old_rarity = item.get('rarity')
            item['rarity'] = target_rarity
            print(f"Updated rarity for '{target_name}': '{old_rarity}' -> '{target_rarity}'")
            changed = True
            
        # Update skill_id if name changed
        if old_name != target_name and old_id:
            new_id = name_to_id(target_name)
            if old_id != new_id:
                item['skill_id'] = new_id
                print(f"Updated skill_id: '{old_id}' -> '{new_id}'")
                id_updates[old_id] = new_id
                changed = True
                
        if changed:
            updated_count += 1
            
    # Fix references in prerequisites and prerequisite_of
    if id_updates:
        print(f"Updating references in prerequisites and prerequisite_of for {len(id_updates)} ID changes...")
        ref_updates_count = 0
        for item in skills_db:
            # Update prerequisites
            prereqs = item.get('prerequisites', [])
            if prereqs:
                new_prereqs = []
                for pid in prereqs:
                    if pid in id_updates:
                        new_prereqs.append(id_updates[pid])
                        ref_updates_count += 1
                    else:
                        new_prereqs.append(pid)
                item['prerequisites'] = new_prereqs
                
            # Update prerequisite_of
            prereq_of = item.get('prerequisite_of', [])
            if prereq_of:
                new_prereq_of = []
                for pid in prereq_of:
                    if pid in id_updates:
                        new_prereq_of.append(id_updates[pid])
                        ref_updates_count += 1
                    else:
                        new_prereq_of.append(pid)
                item['prerequisite_of'] = new_prereq_of
        print(f"Updated {ref_updates_count} prerequisite references in database.")
        
    # Collect all existing skill names (case-insensitive) to prevent duplicates
    existing_names = set()
    for item in skills_db:
        existing_names.add(item.get('name', '').strip().lower())
        
    # Check for missing skills in HTML
    added_count = 0
    for html_skill in extracted_skills:
        name = html_skill['name']
        desc = html_skill['description']
        rarity = html_skill['rarity']
        
        # Check if already exists
        if name.lower() not in existing_names:
            # Skip if it is a debuff skill
            if is_debuff_skill(name, desc):
                print(f"Skipping debuff skill: '{name}'")
                continue
                
            # Guess type and create new entry
            skill_type = guess_skill_type(desc)
            new_id = name_to_id(name)
            
            new_item = {
                "skill_id": new_id,
                "name": name,
                "tier": "A",
                "skill_type": skill_type,
                "prerequisite_of": [],
                "prerequisites": [],
                "description": desc,
                "purchase_option": "Direct",
                "rarity": rarity
            }
            
            # Detect distance/strategy constraints
            desc_clean = desc.lower()
            if "(sprint" in desc_clean or "sprint/" in desc_clean or "sprint・" in desc_clean:
                new_item["distance"] = "Sprint"
            elif "(mile" in desc_clean or "mile/" in desc_clean or "mile・" in desc_clean:
                new_item["distance"] = "Mile"
            elif "(medium" in desc_clean or "medium/" in desc_clean or "medium・" in desc_clean:
                new_item["distance"] = "Medium"
            elif "(long" in desc_clean or "long/" in desc_clean or "long・" in desc_clean:
                new_item["distance"] = "Long"
                
            if "front runner" in desc_clean:
                new_item["strategy"] = "Front Runner"
            elif "pace chaser" in desc_clean:
                new_item["strategy"] = "Pace Chaser"
            elif "late surger" in desc_clean:
                new_item["strategy"] = "Late Surger"
            elif "end closer" in desc_clean:
                new_item["strategy"] = "End Closer"
                
            skills_db.append(new_item)
            existing_names.add(name.lower())
            print(f"Added new skill: '{name}' (Rarity: {rarity}, Type: {skill_type})")
            added_count += 1
            
    print(f"Total new skills added: {added_count}")
                
    if updated_count > 0 or id_updates or added_count > 0:
        print(f"Writing database back to {json_path}...")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(skills_db, f, indent=2, ensure_ascii=False)
    else:
        print("No skill updates or additions were required.")
        
    return updated_count + added_count

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    html_path = os.path.join("scratch", "Skill List _ Uma Musume _ GameTora.htm")
    output_extracted_path = os.path.join("scratch", "extracted_skills.json")
    skills_json_path = os.path.join("web", "src", "assets", "umamusume_final_skills_fixed.json")
    
    if not os.path.exists(html_path):
        print(f"Error: HTML file not found at {html_path}")
        return
        
    if not os.path.exists(skills_json_path):
        print(f"Error: JSON database file not found at {skills_json_path}")
        return
        
    extracted_skills = parse_html_skills(html_path)
    
    print(f"Saving extracted skills list to {output_extracted_path}...")
    with open(output_extracted_path, 'w', encoding='utf-8') as f:
        json.dump(extracted_skills, f, indent=2, ensure_ascii=False)
        
    print("Updating the JSON database...")
    update_count = update_skills_json(skills_json_path, extracted_skills)
    
    print(f"Done! Successfully updated {update_count} skills.")

if __name__ == '__main__':
    main()
