import sqlite3
import pandas as pd
import os

DB_PATH = 'inventory.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_weekly_production_goals():
    """Groups production goals by the start of the week for easier planning."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    
    conn = get_connection()
    query = """
    SELECT p.product_id, p.display_name as Product, p.image_data, pg.due_date as Due, pg.qty_ordered, pg.qty_made
    FROM production_goals pg
    JOIN products p ON pg.product_id = p.product_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return df

    # Convert to datetime and group by week (starting Monday)
    df['Due'] = pd.to_datetime(df['Due'])
    df['week_start_dt'] = df['Due'].dt.to_period('W').apply(lambda r: r.start_time)
    df['Week Starting'] = df['week_start_dt'].dt.strftime('%b %d, %Y')
    df['week_start_iso'] = df['week_start_dt'].dt.strftime('%Y-%m-%d')
    
    summary = df.groupby(['week_start_iso', 'Week Starting', 'product_id', 'Product']).agg({
        'qty_ordered': 'sum',
        'qty_made': 'sum',
        'image_data': 'first'
    }).reset_index()
    
    return summary

def get_inventory():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    return df

def log_production(p_id, week_start_str=None):
    """Increments production count and deducts inventory (BOM)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 2. Find earliest incomplete goal for this product
        query = """
            SELECT goal_id FROM production_goals 
            WHERE product_id = ? AND qty_made < qty_ordered 
        """
        params = [p_id]

        if week_start_str:
            # Filter by the specific week selected in the UI
            start_date = pd.to_datetime(week_start_str).date()
            end_date = start_date + pd.Timedelta(days=6)
            query += " AND due_date BETWEEN ? AND ?"
            params.extend([str(start_date), str(end_date)])

        query += " ORDER BY due_date ASC LIMIT 1"
        
        cursor.execute(query, params)
        goal_res = cursor.fetchone()
        
        if goal_res:
            g_id = goal_res[0]
            cursor.execute("UPDATE production_goals SET qty_made = qty_made + 1 WHERE goal_id = ?", (g_id,))
            
            # 3. Deduct Inventory (Bill of Materials)
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (p_id,))
            recipe_items = cursor.fetchall()
            
            if not recipe_items:
                print(f"Warning: No recipe found for product_id {p_id}")
                
            for i_id, qty in recipe_items:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (qty, i_id))
            
            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_product_recipe(product_name, ingredients_df, image_bytes=None, new_price=None):
    """Updates a product's image, recipe ingredients, and optionally price."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Get Product ID
        cursor.execute("SELECT product_id FROM products WHERE display_name = ?", (product_name,))
        res = cursor.fetchone()
        if not res:
            return False
        p_id = res[0]

        # Update Image if provided
        if image_bytes:
            cursor.execute("UPDATE products SET image_data = ? WHERE product_id = ?", (image_bytes, p_id))
            
        # Update Price if provided
        if new_price is not None:
            cursor.execute("UPDATE products SET selling_price = ? WHERE product_id = ?", (new_price, p_id))

        # Update Recipe: Clear old -> Insert new
        cursor.execute("DELETE FROM recipes WHERE product_id = ?", (p_id,))

        for _, row in ingredients_df.iterrows():
            ing_name = row['Ingredient']
            qty = row['Qty']
            
            # Find item_id (Case-insensitive lookup)
            cursor.execute("SELECT item_id FROM inventory WHERE name = ? COLLATE NOCASE", (ing_name,))
            item_res = cursor.fetchone()
            
            if item_res:
                item_id = item_res[0]
                cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (?, ?, ?)", 
                               (p_id, item_id, qty))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_product(product_name):
    """Deletes a product and its associated recipe."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT product_id FROM products WHERE display_name = ?", (product_name,))
        res = cursor.fetchone()
        if not res:
            return False
        p_id = res[0]

        # Delete from dependent tables
        cursor.execute("DELETE FROM recipes WHERE product_id = ?", (p_id,))
        cursor.execute("DELETE FROM production_goals WHERE product_id = ?", (p_id,))
        cursor.execute("DELETE FROM products WHERE product_id = ?", (p_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def undo_production(p_id, week_start_str=None):
    """Decrements production count and adds back inventory (BOM)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Find latest goal with progress for this product
        query = """
            SELECT goal_id FROM production_goals 
            WHERE product_id = ? AND qty_made > 0 
        """
        params = [p_id]

        if week_start_str:
            # Filter by the specific week selected in the UI
            start_date = pd.to_datetime(week_start_str).date()
            end_date = start_date + pd.Timedelta(days=6)
            query += " AND due_date BETWEEN ? AND ?"
            params.extend([str(start_date), str(end_date)])

        # Order by DESC to undo the most recent one first
        query += " ORDER BY due_date DESC LIMIT 1"
        
        cursor.execute(query, params)
        goal_res = cursor.fetchone()
        
        if goal_res:
            g_id = goal_res[0]
            cursor.execute("UPDATE production_goals SET qty_made = qty_made - 1 WHERE goal_id = ?", (g_id,))
            
            # Add back to Inventory (Bill of Materials)
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (p_id,))
            recipe_items = cursor.fetchall()
            
            for i_id, qty in recipe_items:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand + ? WHERE item_id = ?", (qty, i_id))
            
            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_all_recipes():
    """Fetches all active product recipes with ingredient details."""
    conn = get_connection()
    query = """
    SELECT p.product_id, p.display_name as Product, p.selling_price as Price, p.image_data, i.name as Ingredient, r.qty_needed as Qty
    FROM products p
    JOIN recipes r ON p.product_id = r.product_id
    JOIN inventory i ON r.item_id = i.item_id
    WHERE p.active = 1
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def process_clipboard_update(text_data):
    """Parses lines like 'Rose 50' or 'Vase, 10' to update inventory counts."""
    conn = get_connection()
    cursor = conn.cursor()
    updated_items = []
    errors = []
    
    for line in text_data.strip().split('\n'):
        line = line.strip()
        if not line: continue
        
        name = None
        qty = None

        # Strategy 1: Comma Separated (New Format: Name, Sub-Cat, Qty)
        if ',' in line:
            parts = [p.strip() for p in line.split(',')]
            # We expect at least Name and Qty (e.g. "Name, Qty" or "Name, Sub, Qty")
            if len(parts) >= 2 and parts[-1].isdigit():
                name = parts[0]
                qty = int(parts[-1])
        
        # Strategy 2: Whitespace Separated (Old Format: Name Qty)
        if name is None:
            parts = line.rsplit(None, 1)
            if len(parts) == 2 and parts[1].isdigit():
                name = parts[0].strip().rstrip(',')
                qty = int(parts[1])

        if name and qty is not None:
            # Case-insensitive lookup to find the item
            cursor.execute("SELECT item_id FROM inventory WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            
            if row:
                cursor.execute("UPDATE inventory SET count_on_hand = ? WHERE item_id = ?", (qty, row[0]))
                updated_items.append(f"{name}")
            else:
                errors.append(f"Unknown: {name}")
        else:
            errors.append(f"Invalid format: {line}")
            
    conn.commit()
    conn.close()
    return updated_items, errors

def create_new_product(name, selling_price, image_bytes, recipe_items):
    """Creates a new product and its associated recipe in a single transaction."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Insert Product
        cursor.execute("INSERT INTO products (display_name, selling_price, image_data, active) VALUES (?, ?, ?, 1)",
                       (name, selling_price, image_bytes))
        product_id = cursor.lastrowid
        
        # 2. Insert Recipe Items
        for item_id, qty in recipe_items:
            cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (?, ?, ?)",
                           (product_id, item_id, qty))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_product_exists(product_name):
    """Checks if a product name already exists (case-insensitive)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM products WHERE display_name = ? COLLATE NOCASE", (product_name,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_product_image(product_name):
    """Fetches the thumbnail for a specific product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT image_data FROM products WHERE display_name = ? COLLATE NOCASE", (product_name,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def update_inventory_cost(item_id, new_cost):
    """Updates the unit cost for a specific inventory item."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE inventory SET unit_cost = ? WHERE item_id = ?", (new_cost, item_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
