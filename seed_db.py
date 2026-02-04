import sqlite3

def seed_database():
    connection = sqlite3.connect('inventory.db')
    cursor = connection.cursor()

    # 0. Clear existing data (Optional: allows for clean re-seeding)
    cursor.execute("DELETE FROM production_goals")
    cursor.execute("DELETE FROM recipes")
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM inventory")

    # 1. Insert Inventory Items
    # Format: (name, category, sub_category, count_on_hand, unit_cost)
    inventory_items = [
        ("Judy Vase", "Hard Good", "Vase", 50, 2.50),
        ("Red Rose 40cm", "Stem", "Rose", 200, 0.85),
        ("Leather Leaf", "Greenery", None, 100, 0.50)
    ]
    
    item_ids = {}
    for name, cat, sub_cat, count, cost in inventory_items:
        cursor.execute('''
            INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, cat, sub_cat, count, cost))
        item_ids[name] = cursor.lastrowid

    # 2. Insert Product (The "Dozen Red Roses" arrangement)
    cursor.execute('''
        INSERT INTO products (display_name, selling_price, active)
        VALUES (?, ?, ?)
    ''', ("Dozen Red Roses", 65.00, 1))
    product_id = cursor.lastrowid

    # 3. Insert Recipe (Linking the items to the product)
    # We need 12 roses, 1 leather leaf (bulk), and 1 vase
    recipe_items = [
        (product_id, item_ids["Red Rose 40cm"], 12),
        (product_id, item_ids["Leather Leaf"], 1),
        (product_id, item_ids["Judy Vase"], 1)
    ]
    
    cursor.executemany('''
        INSERT INTO recipes (product_id, item_id, qty_needed)
        VALUES (?, ?, ?)
    ''', recipe_items)

    # 4. Insert Production Goals for Valentine's Period
    production_goals = [
        (product_id, '2026-02-13', 5, 0),
        (product_id, '2026-02-14', 20, 0),
        (product_id, '2026-02-15', 10, 0)
    ]

    cursor.executemany('''
        INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_made)
        VALUES (?, ?, ?, ?)
    ''', production_goals)

    connection.commit()
    connection.close()
    print("Database seeded successfully!")
    print(f"Added {len(inventory_items)} items, 1 product, and 3 production goals.")

if __name__ == "__main__":
    seed_database()