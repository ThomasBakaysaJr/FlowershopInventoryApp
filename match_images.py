import sqlite3
import os
import re

# ================= CONFIGURATION =================
DB_PATH = 'inventory.db'
IMAGE_FOLDER = 'images/recipes'
# =================================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_text(text):
    """Standardizes text for comparison (lowercase, singular, no colors)."""
    text = text.lower()
    text = text.replace('.jpeg', '').replace('.jpg', '').replace('.png', '')
    text = text.replace('roses', 'rose')
    text = text.replace("designer", "designers")
    text = text.replace("dreaming", "dreamin")
    text = text.replace("cupid", "cupid's")
    text = text.replace("delxue", "deluxe") # Fix common typo
    
    # Remove leading numbers if they are single digits (e.g. "1 Rose" -> "Rose")
    text = re.sub(r'^\d\s+', '', text)
    
    return text.strip()

def get_variant_from_name(name):
    name = name.lower()
    if 'premium' in name: return 'PRM'
    if 'deluxe' in name: return 'DLX'
    if 'standard' in name: return 'STD'
    return 'GENERIC'

def get_base_name(text):
    """Removes colors and variant keywords to find the 'Core' product name."""
    text = normalize_text(text)
    
    # Remove Keywords
    remove_words = [
        'standard', 'deluxe', 'premium',
        'red', 'pink', 'yellow', 'white', 'lavender', 'orange', 'bicolor', 'aggie', 'mix',
        'one-off'
    ]
    
    tokens = text.split()
    clean_tokens = [t for t in tokens if t not in remove_words]
    return " ".join(clean_tokens)

def match_images_smart():
    if not os.path.exists(IMAGE_FOLDER):
        print(f"❌ Error: Folder '{IMAGE_FOLDER}' not found.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Load Data
    cursor.execute("SELECT product_id, display_name FROM products WHERE active = 1")
    products = cursor.fetchall()
    
    images = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    print(f"📦 Processing {len(products)} products against {len(images)} images...")
    
    updates = 0
    
    # 2. Iterate Products (Ensure every product tries to find a match)
    for prod in products:
        p_id = prod['product_id']
        p_name = prod['display_name']
        
        p_base = get_base_name(p_name)
        p_variant = get_variant_from_name(p_name)
        
        # Find all candidate images (images that match the base name)
        candidates = []
        for img in images:
            img_base = get_base_name(img)
            
            # Check if Image Base is a subset/match of Product Base
            # e.g. Image "18 Rose" matches Product "18 Rose"
            if img_base == p_base:
                candidates.append(img)
            # Fallback: Fuzzy containment (e.g. "Kissed by Sun" matches "Kissed by the Sun")
            elif set(img_base.split()).issubset(set(p_base.split())):
                 candidates.append(img)

        if not candidates:
            # print(f"  Start: No candidates for {p_name}") # Uncomment for debugging
            continue

        # 3. Select Best Match Logic
        selected_image = None
        
        # Helper to find specific variant in candidates
        def find_variant_image(variant_keyword):
            for img in candidates:
                if variant_keyword in img.lower():
                    return img
            return None
        
        # Helper to find generic image (no variant keywords)
        def find_generic_image():
            for img in candidates:
                if 'standard' not in img.lower() and 'deluxe' not in img.lower() and 'premium' not in img.lower():
                    return img
            return None

        # Priority Waterfall
        if p_variant == 'PRM':
            # Try Premium -> Deluxe -> Standard -> Generic
            selected_image = find_variant_image('premium') or \
                             find_variant_image('deluxe') or \
                             find_variant_image('standard') or \
                             find_generic_image()
                             
        elif p_variant == 'DLX':
            # Try Deluxe -> Standard -> Generic -> Premium (unlikely but safe fallback)
            selected_image = find_variant_image('deluxe') or \
                             find_variant_image('standard') or \
                             find_generic_image() or \
                             find_variant_image('premium')
                             
        else: # STD or Other
            # Try Standard -> Generic -> Deluxe (upgrade preview?)
            selected_image = find_variant_image('standard') or \
                             find_generic_image() or \
                             find_variant_image('deluxe')

        # 4. Apply Update
        if selected_image:
            try:
                with open(os.path.join(IMAGE_FOLDER, selected_image), 'rb') as f:
                    blob = f.read()
                cursor.execute("UPDATE products SET image_data = ? WHERE product_id = ?", (blob, p_id))
                updates += 1
                # print(f"✅ Matched {p_name} -> {selected_image}")
            except Exception as e:
                print(f"❌ Error reading {selected_image}: {e}")

    conn.commit()
    conn.close()
    print(f"\n🎉 Success! Updated {updates} products with images.")

if __name__ == "__main__":
    match_images_smart()