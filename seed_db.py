import sqlite3
import os
import logging
from src.utils import utils

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_image(product_name):
    """Helper to load and compress test images from disk for seeding."""
    # Try variations: "spring_mix", "spring mix", and original "Spring Mix"
    variations = [
        product_name.lower().replace(" ", "_"),
        product_name.lower(),
        product_name
    ]
    
    for var in variations:
        for ext in [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]:
            path = os.path.join("images", "test", var + ext)
            if os.path.exists(path):
                logger.info(f"Found image for '{product_name}': {path}")
                return utils.process_image(path)
                
    logger.warning(f"No image found for '{product_name}' (tried variations in images/test/)")
    return None

def seed_database():
    connection = None
    try:
        connection = sqlite3.connect('inventory.db')
        cursor = connection.cursor()

        # 0. Clear existing data (Optional: allows for clean re-seeding)
        cursor.execute("DELETE FROM production_goals")
        cursor.execute("DELETE FROM recipes")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM inventory")

        # 1. Insert Inventory Items
        # Format: (name, category, sub_category, count_on_hand, unit_cost, bundle_count)
        inventory_items = [
            # Hard Goods
            ("Judy Vase", "Hard Good", "Vase", 50, 2.50, 1),
            ("Blue Ceramic Pot", "Hard Good", "Vase", 20, 4.75, 1),
            ("Clear Bud Vase", "Hard Good", "Vase", 100, 1.10, 1),
            # Stems
            ("Red Rose 40cm", "Stem", "Rose", 200, 0.85, 25),
            ("White Lily", "Stem", "Lily", 40, 2.25, 10),
            ("Yellow Tulip", "Stem", "Tulip", 150, 0.65, 10),
            ("Pink Carnation", "Stem", "Carnation", 300, 0.45, 25),
            # Greenery
            ("Leather Leaf", "Greenery", None, 100, 0.50, 10),
            ("Silver Dollar Eucalyptus", "Greenery", "Eucalyptus", 80, 1.20, 10),
            ("Salal", "Greenery", None, 60, 0.75, 10)
        ]
        
        item_ids = {}
        for name, cat, sub_cat, count, cost, bundle in inventory_items:
            cursor.execute('''
                INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, cat, sub_cat, count, cost, bundle))
            item_ids[name] = cursor.lastrowid

        # 2. Insert Products
        # Format: (Name, Price, Stock on Hand)
        products_to_create = [
            ("Dozen Red Roses", 65.00, 0),
            ("Spring Mix", 45.00, 5),
            ("Lily Elegance", 85.00, 0),
            ("Budget Bud Vase", 15.00, 10)
        ]
        
        product_ids = {}
        for name, price, stock in products_to_create:
            img = load_image(name)
            cursor.execute('''
                INSERT INTO products (display_name, selling_price, image_data, active, stock_on_hand)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, price, img, 1, stock))
            product_ids[name] = cursor.lastrowid

        # 3. Insert Recipes
        recipe_items = [
            # Dozen Red Roses
            (product_ids["Dozen Red Roses"], item_ids["Red Rose 40cm"], 12),
            (product_ids["Dozen Red Roses"], item_ids["Leather Leaf"], 2),
            (product_ids["Dozen Red Roses"], item_ids["Judy Vase"], 1),
            # Spring Mix
            (product_ids["Spring Mix"], item_ids["Yellow Tulip"], 10),
            (product_ids["Spring Mix"], item_ids["Pink Carnation"], 5),
            (product_ids["Spring Mix"], item_ids["Salal"], 1),
            (product_ids["Spring Mix"], item_ids["Blue Ceramic Pot"], 1),
            # Lily Elegance
            (product_ids["Lily Elegance"], item_ids["White Lily"], 5),
            (product_ids["Lily Elegance"], item_ids["Silver Dollar Eucalyptus"], 3),
            (product_ids["Lily Elegance"], item_ids["Judy Vase"], 1),
            # Budget Bud Vase
            (product_ids["Budget Bud Vase"], item_ids["Pink Carnation"], 1),
            (product_ids["Budget Bud Vase"], item_ids["Leather Leaf"], 1),
            (product_ids["Budget Bud Vase"], item_ids["Clear Bud Vase"], 1)
        ]
        
        cursor.executemany('''
            INSERT INTO recipes (product_id, item_id, qty_needed)
            VALUES (?, ?, ?)
        ''', recipe_items)

        # 4. Insert Production Goals (Spread across different weeks)
        production_goals = [
            # Week of Feb 2 (Current Week)
            (product_ids["Budget Bud Vase"], '2026-02-05', 25, 10),
            (product_ids["Spring Mix"], '2026-02-06', 10, 2),
            # Week of Feb 9 (Valentine's Prep)
            (product_ids["Dozen Red Roses"], '2026-02-13', 50, 0),
            (product_ids["Dozen Red Roses"], '2026-02-14', 150, 0),
            (product_ids["Lily Elegance"], '2026-02-14', 20, 0),
            (product_ids["Budget Bud Vase"], '2026-02-14', 25, 10),
            (product_ids["Spring Mix"], '2026-02-14', 10, 2),
            # Week of Feb 16 (Post-Valentine's)
            (product_ids["Spring Mix"], '2026-02-18', 15, 0),
            (product_ids["Budget Bud Vase"], '2026-02-20', 30, 0)
        ]

        cursor.executemany('''
            INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled)
            VALUES (?, ?, ?, ?)
        ''', production_goals)

        connection.commit()
        logger.info("Database seeded successfully!")
        logger.info(f"Added {len(inventory_items)} items, {len(products_to_create)} products, and {len(production_goals)} goals.")

    except sqlite3.Error as e:
        logger.error(f"seed_db: Database error: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    seed_database()