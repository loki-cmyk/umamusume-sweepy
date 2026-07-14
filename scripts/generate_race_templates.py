import os
import shutil
import re
import argparse
import cv2
import numpy as np

# Resolve path relative to this script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

def load_id_to_name(schedule_path):
    id_to_name = {}
    if not os.path.exists(schedule_path):
        print(f"Error: {schedule_path} not found.")
        return id_to_name
        
    with open(schedule_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.splitlines()
    csv_mode = False
    for line in lines:
        if "RAW CSV LINES FOR race.csv" in line:
            csv_mode = True
            continue
        if csv_mode:
            parts = line.strip().split(",")
            if len(parts) >= 4:
                try:
                    race_id = int(parts[1])
                    race_name = parts[3]
                    id_to_name[race_id] = race_name
                except ValueError:
                    pass
    return id_to_name

def shave_white_edges(img, threshold=235):
    # Check top, bottom, left, and right borders of the BGR image.
    # If the border contains a high percentage of white/near-white pixels, shave it off.
    h, w, _ = img.shape
    t, b, l, r = 0, h, 0, w
    
    while t < b:
        top_row = img[t, l:r]
        white_count = np.sum((top_row[:, 0] >= threshold) & (top_row[:, 1] >= threshold) & (top_row[:, 2] >= threshold))
        if white_count > 0.1 * (r - l):
            t += 1
        else:
            break
            
    while b > t:
        bottom_row = img[b-1, l:r]
        white_count = np.sum((bottom_row[:, 0] >= threshold) & (bottom_row[:, 1] >= threshold) & (bottom_row[:, 2] >= threshold))
        if white_count > 0.1 * (r - l):
            b -= 1
        else:
            break
            
    while l < r:
        left_col = img[t:b, l]
        white_count = np.sum((left_col[:, 0] >= threshold) & (left_col[:, 1] >= threshold) & (left_col[:, 2] >= threshold))
        if white_count > 0.1 * (b - t):
            l += 1
        else:
            break
            
    while r > l:
        right_col = img[t:b, r-1]
        white_count = np.sum((right_col[:, 0] >= threshold) & (right_col[:, 1] >= threshold) & (right_col[:, 2] >= threshold))
        if white_count > 0.1 * (b - t):
            r -= 1
        else:
            break
            
    return img[t:b, l:r]

def main():
    parser = argparse.ArgumentParser(description="Crop race banners and output transparent templates and ID templates.")
    parser.add_argument(
        "--schedule_path",
        default=os.path.join(PROJECT_ROOT, "scratch", "new_races_schedule.txt"),
        help="Path to the schedule file containing mapped IDs and names."
    )
    parser.add_argument(
        "--races_dir",
        default=os.path.join(PROJECT_ROOT, "scratch", "races"),
        help="Path to the directory containing screenshotted images."
    )
    parser.add_argument(
        "--ref_path",
        default=os.path.join(PROJECT_ROOT, "races", "Akamatsu Sho.png"),
        help="Path to the reference comparison image to copy the alpha mask from."
    )
    
    args = parser.parse_args()
    
    processed_dir = os.path.join(args.races_dir, "processed")
    ref_image_path = args.ref_path
    
    # Clean output contents to avoid Win32 directory lock PermissionErrors
    if os.path.exists(processed_dir):
        print(f"Cleaning processed directory contents: {processed_dir}")
        for filename in os.listdir(processed_dir):
            file_path = os.path.join(processed_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"  Warning: could not delete {file_path}: {e}")
    else:
        os.makedirs(processed_dir, exist_ok=True)
        
    # Load reference alpha mask
    if not os.path.exists(ref_image_path):
        print(f"Error: Reference image {ref_image_path} not found.")
        return
    ref_img = cv2.imread(ref_image_path, cv2.IMREAD_UNCHANGED)
    if ref_img is None or ref_img.shape[2] != 4:
        print("Error: Could not load reference image.")
        return
    ref_alpha = ref_img[:, :, 3]
    ref_h, ref_w = ref_alpha.shape
    
    id_to_name = load_id_to_name(args.schedule_path)
    print(f"Loaded {len(id_to_name)} race mappings.")
    
    files = sorted([f for f in os.listdir(args.races_dir) if f.endswith(".png")])
    print(f"Found {len(files)} screenshot files to process.")
    
    for f in files:
        race_id_str = os.path.splitext(f)[0]
        try:
            race_id = int(race_id_str)
        except ValueError:
            continue
            
        race_name = id_to_name.get(race_id)
        if not race_name:
            continue
            
        img_path = os.path.join(args.races_dir, f)
        img = cv2.imread(img_path)
        if img is None:
            continue
            
        h, w, c = img.shape
        print(f"\nProcessing {f} ({race_name}): size={w}x{h}")
        
        # Crop card from row screenshots
        if w > 500:
            left_half = img[:, :int(w * 0.4)]
            gray = cv2.cvtColor(left_half, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            card_box = None
            for cnt in contours:
                cx, cy, cw, ch = cv2.boundingRect(cnt)
                if 170 <= cw <= 185 and 90 <= ch <= 105:
                    card_box = (cx, cy, cw, ch)
                    break
            
            if card_box:
                cx, cy, cw, ch = card_box
                print(f"  Detected card boundary box: x={cx}, y={cy}, w={cw}, h={ch}")
                card_img = img[cy:cy+ch, cx:cx+cw]
            else:
                cx, cy, cw, ch = 20, 26, 179, 97
                cy = min(cy, h - 97)
                cx = min(cx, w - 179)
                card_img = img[cy:cy+97, cx:cx+179]
                print(f"  Contour not found. Fallback crop box: x={cx}, y={cy}, w=179, h=97")
                
            shaved_img = shave_white_edges(card_img)
            print(f"  Shaved white edges: {card_img.shape[1]}x{card_img.shape[0]} -> {shaved_img.shape[1]}x{shaved_img.shape[0]}")
            card_img = shaved_img
        else:
            card_img = img
            
        # Save cropped BGR card
        card_dest_path = os.path.join(processed_dir, f)
        cv2.imwrite(card_dest_path, card_img)
        print(f"  Saved card template to: {card_dest_path}")
        
        # Resize to 161x80 and apply reference alpha mask
        resized_card = cv2.resize(card_img, (ref_w, ref_h), interpolation=cv2.INTER_AREA)
        bgra = cv2.merge([resized_card[:, :, 0], resized_card[:, :, 1], resized_card[:, :, 2], ref_alpha])
        
        safe_race_name = re.sub(r'[\\/*?:"<>|]', "", race_name)
        alpha_dest_path = os.path.join(processed_dir, f"{safe_race_name}.png")
        cv2.imwrite(alpha_dest_path, bgra)
        print(f"  Saved alpha card (resized & ref-masked) to: {alpha_dest_path}")

    print("\nReprocessing complete!")

if __name__ == "__main__":
    main()
