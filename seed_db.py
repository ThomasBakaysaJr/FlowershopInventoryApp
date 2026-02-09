import sqlite3
import os
import logging
import pandas as pd
import random
import glob
from datetime import date, timedelta
from src.utils import utils
from src.utils import db_utils

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SEED_DIR = "seed_data"
INVENTORY_FILE = os.path.join(SEED_DIR, "default_inventory.csv")
RECIPES_IMG_DIR = os.path.join(SEED_DIR, "images")

def ensure_seed_data():
    """Ensures the seed directory and default inventory file exist."""
    if not os.path.exists(SEED_DIR):
        os.makedirs(SEED_DIR)
        logger.info(f"Created seed directory: {SEED_DIR}")
    
    if not os.path.exists(INVENTORY_FILE):
        # Create a robust default inventory
        data = [
            # Hard Goods
            {"name": "Judy Vase", "category": "Hard Good", "sub_category": "Vase", "count_on_hand": 50, "unit_cost": 2.50, "bundle_count": 1},
            {"name": "Blue Ceramic Pot", "category": "Hard Good", "sub_category": "Vase", "count_on_hand": 20, "unit_cost": 4.75, "bundle_count": 1},
            {"name": "Clear Bud Vase", "category": "Hard Good", "sub_category": "Vase", "count_on_hand": 100, "unit_cost": 1.10, "bundle_count": 1},
            {"name": "Rustic Basket", "category": "Hard Good", "sub_category": "Basket", "count_on_hand": 15, "unit_cost": 3.50, "bundle_count": 1},
            {"name": "Floral Foam Block", "category": "Hard Good", "sub_category": "Supply", "count_on_hand": 200, "unit_cost": 0.75, "bundle_count": 1},
            # Stems
            {"name": "Red Rose 40cm", "category": "Stem", "sub_category": "Rose", "count_on_hand": 200, "unit_cost": 0.85, "bundle_count": 25},
            {"name": "White Rose 50cm", "category": "Stem", "sub_category": "Rose", "count_on_hand": 150, "unit_cost": 0.95, "bundle_count": 25},
            {"name": "Pink Rose 40cm", "category": "Stem", "sub_category": "Rose", "count_on_hand": 180, "unit_cost": 0.85, "bundle_count": 25},
            {"name": "White Lily", "category": "Stem", "sub_category": "Lily", "count_on_hand": 40, "unit_cost": 2.25, "bundle_count": 10},
            {"name": "Pink Oriental Lily", "category": "Stem", "sub_category": "Lily", "count_on_hand": 30, "unit_cost": 2.50, "bundle_count": 10},
            {"name": "Yellow Tulip", "category": "Stem", "sub_category": "Tulip", "count_on_hand": 150, "unit_cost": 0.65, "bundle_count": 10},
            {"name": "Purple Tulip", "category": "Stem", "sub_category": "Tulip", "count_on_hand": 120, "unit_cost": 0.65, "bundle_count": 10},
            {"name": "Pink Carnation", "category": "Stem", "sub_category": "Carnation", "count_on_hand": 300, "unit_cost": 0.45, "bundle_count": 25},
            {"name": "White Carnation", "category": "Stem", "sub_category": "Carnation", "count_on_hand": 250, "unit_cost": 0.45, "bundle_count": 25},
            {"name": "Blue Hydrangea", "category": "Stem", "sub_category": "Hydrangea", "count_on_hand": 20, "unit_cost": 3.50, "bundle_count": 1},
            {"name": "White Hydrangea", "category": "Stem", "sub_category": "Hydrangea", "count_on_hand": 25, "unit_cost": 3.25, "bundle_count": 1},
            {"name": "Sunflower", "category": "Stem", "sub_category": "Sunflower", "count_on_hand": 60, "unit_cost": 1.25, "bundle_count": 5},
            # Greenery
            {"name": "Leather Leaf", "category": "Greenery", "sub_category": None, "count_on_hand": 100, "unit_cost": 0.50, "bundle_count": 10},
            {"name": "Silver Dollar Eucalyptus", "category": "Greenery", "sub_category": "Eucalyptus", "count_on_hand": 80, "unit_cost": 1.20, "bundle_count": 10},
            {"name": "Baby Blue Eucalyptus", "category": "Greenery", "sub_category": "Eucalyptus", "count_on_hand": 70, "unit_cost": 1.10, "bundle_count": 10},
            {"name": "Salal", "category": "Greenery", "sub_category": None, "count_on_hand": 60, "unit_cost": 0.75, "bundle_count": 10},
            {"name": "Ruscus", "category": "Greenery", "sub_category": None, "count_on_hand": 50, "unit_cost": 0.80, "bundle_count": 10}
        ]
        df = pd.DataFrame(data)
        df.to_csv(INVENTORY_FILE, index=False)
        logger.info(f"Created default inventory file at {INVENTORY_FILE}")

def get_product_names_and_images():
    """Scans the recipes image directory for products."""
    products = []
    
    # Ensure directory exists
    if not os.path.exists(RECIPES_IMG_DIR):
        # Fallback to test images if recipe dir doesn't exist
        test_dir = os.path.join("images", "test")
        if os.path.exists(test_dir):
            search_dir = test_dir
        else:
            logger.warning(f"No image directories found ({RECIPES_IMG_DIR} or {test_dir}). Using default names.")
            return [("Dozen Red Roses", None), ("Spring Mix", None), ("Lily Elegance", None), ("Budget Bud Vase", None)]
    else:
        search_dir = RECIPES_IMG_DIR

    files = glob.glob(os.path.join(search_dir, "*"))
    for f in files:
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            name = os.path.splitext(os.path.basename(f))[0]
            clean_name = name.replace("_", " ").title()
            products.append((clean_name, f))
    
    if not products:
        return [("Dozen Red Roses", None), ("Spring Mix", None), ("Lily Elegance", None), ("Budget Bud Vase", None)]
    
    return products

def seed_database():
    ensure_seed_data()
    
    # 0. Clear existing data
    connection = sqlite3.connect('inventory.db')
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM production_logs")
        cursor.execute("DELETE FROM production_goals")
        cursor.execute("DELETE FROM recipes")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM inventory")
        
        # Reset sequences
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='inventory'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='products'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='recipes'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='production_goals'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='production_logs'")
        connection.commit()
    except sqlite3.Error as e:
        logger.error(f"seed_db: Database clearing error: {e}")
        connection.close()
        return
    finally:
        connection.close()

    # 1. Insert Inventory Items via Bulk Upload
    logger.info(f"Loading inventory from {INVENTORY_FILE}...")
    count, errors = db_utils.process_bulk_inventory_upload(INVENTORY_FILE)
    if errors:
        logger.error(f"Bulk upload errors: {errors}")
    
    # 2. Load Products & Goals (Requires re-connection)
    connection = sqlite3.connect('inventory.db')
    cursor = connection.cursor()
    try:
        # Re-fetch item IDs map
        cursor.execute("SELECT name, item_id FROM inventory")
        rows = cursor.fetchall()
        item_ids = {row[0]: row[1] for row in rows}
        all_item_ids = [row[1] for row in rows]

        # 2. Insert Products & Random Recipes
        products_found = get_product_names_and_images()
        product_ids = {}
        
        for name, img_path in products_found:
            # Load image
            img_bytes = None
            if img_path:
                img_bytes = utils.process_image(img_path)
            
            # Random Price between 30 and 150
            price = round(random.uniform(30.0, 150.0), 2)
            
            cursor.execute('''
                INSERT INTO products (display_name, selling_price, image_data, active, stock_on_hand)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, price, img_bytes, 1, random.randint(0, 5)))
            
            p_id = cursor.lastrowid
            product_ids[name] = p_id
            
            # Generate Random Recipe
            # Mix items by ID
            if all_item_ids:
                num_ingredients = random.randint(3, 8)
                ingredients = random.sample(all_item_ids, min(len(all_item_ids), num_ingredients))
                
                for ing_id in ingredients:
                    qty = random.randint(1, 12)
                    # Randomly add a note
                    note = random.choice([None, None, None, "Short stems", "Remove guard petals", "Reflex petals"])
                    cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed, note) VALUES (?, ?, ?, ?)", (p_id, ing_id, qty, note))

        # 3. Generate Random Production Goals
        today = date.today()
        goals_to_insert = []
        
        for p_name, p_id in product_ids.items():
            # Create 0 to 3 goals for each product
            num_goals = random.randint(0, 3)
            for _ in range(num_goals):
                # Random date in next 30 days
                days_ahead = random.randint(1, 30)
                due_date = today + timedelta(days=days_ahead)
                
                qty_ordered = random.randint(5, 50)
                qty_fulfilled = random.randint(0, qty_ordered) # Some progress
                
                goals_to_insert.append((p_id, due_date.strftime('%Y-%m-%d'), qty_ordered, qty_fulfilled))
        
        cursor.executemany('''
            INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled)
            VALUES (?, ?, ?, ?)
        ''', goals_to_insert)

        connection.commit()
        logger.info("Database seeded successfully with robust random data!")
        logger.info(f"Added {len(item_ids)} inventory items, {len(product_ids)} products, and {len(goals_to_insert)} goals.")

    except sqlite3.Error as e:
        logger.error(f"seed_db: Database error: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    print("🌱 Seeding database...")
    seed_database()
    print("✅ Seeding complete! Check logs/app.log for details.")
