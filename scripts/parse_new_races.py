import os
import argparse
import re
from bs4 import BeautifulSoup

# Resolve paths relative to the script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Update this as needed to add new races when they're added to global
races_to_find = [
    "Kawasaki Kinen",
    "Zen-Nippon Junior Yushun",
    "Kashiwa Kinen",
    "Mile Championship Nambu Hai",
    "Ladies' Prelude",
    "Tokyo Hai",
    "Empress Hai",
    "Kanto Oaks",
    "Diolite Kinen",
    "Sazanka TV Hai",
    "TCK Jo-o Hai",
    "Tokyo Sprint",
    "Sparking Lady Cup",
    "Marine Cup",
    "Queen Sho",
    "Mercury Cup",
    "Cluster Cup"
]

name_mappings = {
    "Mile Championship Nambu Hai": "M.C. Nambu Hai"
}

month_offsets = {
    "Jan": 1, "Feb": 3, "Mar": 5, "Apr": 7, "May": 9, "Jun": 11,
    "Jul": 13, "Aug": 15, "Sep": 17, "Oct": 19, "Nov": 21, "Dec": 23
}

year_bases = {
    "Junior C.": 0,
    "Classic C.": 24,
    "Senior C.": 48
}

def calculate_turn_index(year_str, date_str):
    y_base = 0
    for key, val in year_bases.items():
        if key in year_str:
            y_base = val
            break
            
    m_offset = 1
    for key, val in month_offsets.items():
        if key in date_str:
            m_offset = val
            break
            
    timing_offset = 0
    if "Late" in date_str:
        timing_offset = 1
        
    return y_base + m_offset + timing_offset

def map_year(year_str):
    if "Junior" in year_str:
        return "Junior Year"
    elif "Classic" in year_str:
        return "Classic Year"
    elif "Senior" in year_str:
        return "Senior Year"
    return "Unknown Year"

def map_grade(ribbon_src):
    if not ribbon_src:
        return "OP"
    filename = os.path.basename(ribbon_src)
    if "ribbon_05" in filename:
        return "G1"
    elif "ribbon_04" in filename:
        return "G2"
    elif "ribbon_03" in filename:
        return "G3"
    elif "ribbon_02" in filename:
        return "OP"
    elif "ribbon_01" in filename:
        return "PRE-OP"
    return "OP"

def main():
    parser = argparse.ArgumentParser(description="Parse new races from Uma Musume GameTora HTML and generate CSV schedule format.")
    parser.add_argument(
        "--html_path",
        required=True,
        help="Path to the source GameTora Race List HTML file."
    )
    parser.add_argument(
        "--output_path",
        default=os.path.join(PROJECT_ROOT, "scratch", "new_races_schedule.txt"),
        help="Path where the parsed schedule table and CSV rows will be written."
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.html_path):
        print(f"Error: HTML file {args.html_path} does not exist.")
        return

    print(f"Reading HTML file: {args.html_path}")
    with open(args.html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    print("Parsing races...")
    all_divs = soup.find_all("div")
    extracted_data = []
    
    for race_name in races_to_find:
        search_name = name_mappings.get(race_name, race_name)
        found = False
        for div in all_divs:
            if div.get_text(strip=True) == search_name:
                parent_title = div.parent
                
                curr = parent_title
                row_container = None
                while curr:
                    if curr.name == "div" and any(c in (curr.get("class") or []) for c in ["gQcuhN", "sc-be4f7062-1"]):
                        row_container = curr
                        break
                    curr = curr.parent

                if not row_container:
                    curr = parent_title
                    for _ in range(4):
                        if curr.parent:
                            curr = curr.parent
                            details_sibling = curr.find(class_=lambda x: x and "blcBPQ" in x)
                            if details_sibling:
                                row_container = curr
                                break
                                
                if row_container:
                    details_block = row_container.find(class_=lambda x: x and "blcBPQ" in x)
                    if details_block:
                        cols = details_block.find_all(class_=lambda x: x and "fIVcVk" in x)
                        ribbon_img = row_container.find("img", src=lambda x: x and "grade_ribbon" in x)
                        ribbon_src = ribbon_img["src"] if ribbon_img else ""
                        
                        col_divs = []
                        col_alts = []
                        for col in cols:
                            col_divs.append([d.get_text(strip=True) for d in col.find_all("div")])
                            col_alts.append([img["alt"] for img in col.find_all("img") if img.get("alt")])
                        
                        html_year = col_divs[0][0] if len(col_divs) > 0 and len(col_divs[0]) > 0 else "Senior C."
                        html_date = col_divs[0][1] if len(col_divs) > 0 and len(col_divs[0]) > 1 else "Early Feb"
                        
                        surface = col_divs[1][0] if len(col_divs) > 1 and len(col_divs[1]) > 0 else "Dirt"
                        track = col_divs[1][1] if len(col_divs) > 1 and len(col_divs[1]) > 1 else "Kawasaki"
                        direction = col_alts[1][0] if len(col_alts) > 1 and len(col_alts[1]) > 0 else ""
                        
                        dist_type = col_divs[2][0] if len(col_divs) > 2 and len(col_divs[2]) > 0 else "Medium"
                        distance_str = col_divs[2][1] if len(col_divs) > 2 and len(col_divs[2]) > 1 else "2100 m"
                        distance = distance_str.replace(" m", "").strip()
                        
                        turn_idx = calculate_turn_index(html_year, html_date)
                        csv_date_str = f"{map_year(html_year)} {html_date}"
                        csv_grade = map_grade(ribbon_src)
                        
                        csv_dist_type = dist_type
                        if dist_type == "Short":
                            csv_dist_type = "Sprint"
                            
                        if track == "Varies":
                            direction = ""
                            distance = ""
                            csv_dist_type = ""
                            
                        extracted_data.append({
                            "turn_idx": turn_idx,
                            "date_str": csv_date_str,
                            "name": race_name,
                            "grade": csv_grade,
                            "track": track,
                            "surface": surface,
                            "distance": distance,
                            "direction": direction,
                            "distance_type": csv_dist_type
                        })
                        found = True
                        break
        
        if not found:
            print(f"WARNING: Race '{race_name}' not found.")

    extracted_data.sort(key=lambda r: r["turn_idx"])
    for idx, r in enumerate(extracted_data):
        r["race_id"] = 2388 + idx

    print(f"Writing parsed schedule to: {args.output_path}")
    with open(args.output_path, "w", encoding="utf-8") as f:
        f.write("=========================================================================\n")
        f.write("Race templates/images used for matching are stored in:\n")
        f.write("resource/umamusume/race\n")
        f.write("=========================================================================\n\n")
        
        f.write("TABLE REPRESENTATION OF NEW RACES (MATCHING race.csv COLUMNS):\n\n")
        f.write(f"{'Turn':<5} | {'ID':<5} | {'Date String':<22} | {'Race Name':<30} | {'Grade':<5} | {'Track':<10} | {'Surface':<7} | {'Dist':<5} | {'Dir':<5} | {'Type':<6}\n")
        f.write("-" * 115 + "\n")
        
        for r in extracted_data:
            f.write(f"{r['turn_idx']:<5} | {r['race_id']:<5} | {r['date_str']:<22} | {r['name']:<30} | {r['grade']:<5} | {r['track']:<10} | {r['surface']:<7} | {r['distance']:<5} | {r['direction']:<5} | {r['distance_type']:<6}\n")
            
        f.write("\n" + "=" * 115 + "\n\n")
        f.write("RAW CSV LINES FOR race.csv (Copy and paste directly):\n\n")
        
        for r in extracted_data:
            csv_line = f"{r['turn_idx']},{r['race_id']},{r['date_str']},{r['name']},,{r['grade']},{r['track']},{r['surface']},{r['distance']},{r['direction']},,{r['distance_type']}\n"
            f.write(csv_line)
            
    print("Schedule parsing completed successfully!")

if __name__ == "__main__":
    main()
