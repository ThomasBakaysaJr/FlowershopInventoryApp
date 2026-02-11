import os
import glob
import logging
import uuid
from src.utils import db_utils, utils

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

IMAGE_DIR = os.path.join("images", "recipes")

def seed_from_images():
    """
    Scans images/recipes and creates products for any images that don't 
    already have an active product in the database.
    """
    if not os.path.exists(IMAGE_DIR):
        print(f"❌ Directory not found: {IMAGE_DIR}")
        print("Please create 'images/recipes' and add your product images there.")
        return

    print(f"📂 Scanning {IMAGE_DIR} for new products...")
    print(f"   (Absolute path: {os.path.abspath(IMAGE_DIR)})")
    
    files = glob.glob(os.path.join(IMAGE_DIR, "*"))
    print(f"   Found {len(files)} files.")
    if len(files) == 0:
        print("⚠️  No files found. Please ensure your images are in the 'images/recipes' folder.")

    count = 0
    skipped = 0
    errors = 0
    
    # --- PASS 1: SCAN AND GROUP ---
    # Structure: { "Base Name": { "files": [(variant_type, filepath), ...], "image_bytes": b'...' } }
    product_groups = {}
    
    suffix_map = {
        "standard": "STD",
        "deluxe": "DLX",
        "premium": "PRM"
    }
    
    for f in files:
        # Only process images
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Derive name from filename
            filename = os.path.basename(f)
            name_base = os.path.splitext(filename)[0]
            # Clean up name: "Red_Rose_Bouquet" -> "Red Rose Bouquet"
            clean_name = name_base.replace("_", " ").title()
            
            # Determine Variant Type based on suffix
            words = clean_name.split()
            last_word = words[-1].lower() if words else ""
            
            variant_type = "STD"
            base_name = clean_name
            
            if last_word in suffix_map:
                variant_type = suffix_map[last_word]
                # Remove the suffix from the base name for grouping
                base_name = " ".join(words[:-1])
            
            # Safety: If filename was just "Standard.jpg", base_name becomes empty. Revert.
            if not base_name.strip():
                base_name = clean_name
            
            if base_name not in product_groups:
                product_groups[base_name] = []
            
            # Check if this variant type is already taken in this group
            # (e.g. prevent having both "Red Rose" and "Red Rose Standard" as STD)
            if any(v['type'] == variant_type for v in product_groups[base_name]):
                print(f"⚠️  Skipping '{clean_name}' (Variant '{variant_type}' already exists for '{base_name}')")
                skipped += 1
                continue
                
            product_groups[base_name].append({
                "file": f,
                "type": variant_type,
                "full_name": clean_name # We keep the specific name (e.g. "Red Rose Deluxe")
            })

    print(f"🧩 Found {len(product_groups)} unique product families.")

    # --- PASS 2: PROCESS AND INSERT ---
    
    for base_name, variants in product_groups.items():
        # Generate a shared Group ID for this family
        # First, check if a Standard version already exists in the DB to link to
        existing_group_id = None
        potential_std_names = [base_name, f"{base_name} Standard"]
        
        for n in potential_std_names:
            gid = db_utils.get_product_group_id(n)
            if gid:
                existing_group_id = gid
                break
        
        # Use existing ID if found, otherwise generate new
        group_id = existing_group_id if existing_group_id else str(uuid.uuid4())
        
        for v in variants:
            p_name = v['full_name']
            v_type = v['type']
            f_path = v['file']
            
            # 1. Check for Duplicates
            if db_utils.check_product_variant(p_name, v_type):
                 print(f"⚠️  Skipping '{p_name}' (Already active)")
                 skipped += 1
                 continue

            # 2. Process Image
            try:
                image_bytes = utils.process_image(f_path)
            except Exception as e:
                logger.error(f"Failed to process image {f_path}: {e}")
                print(f"❌ Failed to process image for '{p_name}'")
                errors += 1
                continue

            # 3. Create Product
            success = db_utils.create_new_product(
                name=p_name,
                selling_price=0.0,
                image_bytes=image_bytes,
                recipe_items=[], # Empty recipe
                category="Standard",
                note="Imported via uni_seed.py",
                variant_group_id=group_id,
                variant_type=v_type
            )
            
            if success:
                print(f"✅ Created '{p_name}' [{v_type}]")
                count += 1
            else:
                print(f"❌ Failed to create '{p_name}' (DB Error)")
                print(f"   Check logs/app.log for details.")
                errors += 1

    print("-" * 40)
    print(f"🎉 Finished! Created: {count} | Skipped: {skipped} | Errors: {errors}")

if __name__ == "__main__":
    seed_from_images()