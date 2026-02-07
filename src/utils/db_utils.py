import sqlite3
import pandas as pd
import os
import logging
from typing import Optional, List, Tuple, Union

logger = logging.getLogger(__name__)

DB_PATH = 'inventory.db'

def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)

def get_weekly_production_goals() -> pd.DataFrame:
    """Groups production goals by the start of the week for easier planning."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    
    conn = None
    try:
        conn = get_connection()
        query = """
        SELECT pg.goal_id, p.product_id, p.display_name as Product, p.image_data, p.active, pg.due_date, pg.qty_ordered, pg.qty_made
        FROM production_goals pg
        JOIN products p ON pg.product_id = p.product_id
        """
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            return df

        # Convert to datetime and group by week (starting Monday)
        df['due_date'] = pd.to_datetime(df['due_date'])
        df['week_start_dt'] = df['due_date'].dt.to_period('W').apply(lambda r: r.start_time)
        df['Week Starting'] = df['week_start_dt'].dt.strftime('%b %d, %Y')
        df['week_start_iso'] = df['week_start_dt'].dt.strftime('%Y-%m-%d')
        
        return df.sort_values(['week_start_iso', 'due_date', 'Product'])
    except Exception as e:
        logger.error(f"get_weekly_production_goals: Error fetching goals: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()

def get_inventory() -> pd.DataFrame:
    try:
        if not os.path.exists(DB_PATH):
            return pd.DataFrame()
        conn = get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM inventory", conn)
            return df
        except Exception as e:
            logger.error(f"get_inventory: Error executing query: {e}")
            return pd.DataFrame()  
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"get_inventory: Error fetching inventory: {e}")
        return pd.DataFrame()

def log_production(goal_id: int) -> bool:
    """Increments production count and deducts inventory (BOM)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 2. Get product_id and current status from the specific goal
        cursor.execute("SELECT product_id, qty_made, qty_ordered FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        
        if not res:
            logger.error(f"log_production: Goal ID {goal_id} not found.")
            return False
        
        p_id, qty_made, qty_ordered = res
        logger.debug(f"log_production: goal_id={goal_id}, product_id={p_id}")

        # Update Goal
        cursor.execute("UPDATE production_goals SET qty_made = qty_made + 1 WHERE goal_id = ?", (goal_id,))
        
        # Insert Log Entry
        cursor.execute("INSERT INTO production_logs (goal_id, product_id) VALUES (?, ?)", (goal_id, p_id))
        
        # 3. Deduct Inventory (Bill of Materials)
        cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (p_id,))
        recipe_items = cursor.fetchall()
        
        if not recipe_items:
            logger.warning(f"log_production: No recipe found for product_id {p_id}")
            
        for i_id, qty in recipe_items:
            cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (qty, i_id))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"log_production: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_product_recipe(
    current_product_id: int,
    new_name: str,
    recipe_items: List[Tuple[int, int]], 
    image_bytes: Optional[bytes] = None, 
    new_price: Optional[float] = None
) -> bool:
    """Archives the old product and creates a new version with updated details."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Find the current product to get its current data
        cursor.execute("SELECT selling_price, image_data, display_name FROM products WHERE product_id = ?", (current_product_id,))
        res = cursor.fetchone()
        if not res:
            return False
        
        old_price, old_image_data, old_name = res
        
        # 2. Determine new values (use old ones if not provided)
        final_price = new_price if new_price is not None else old_price
        final_image = image_bytes if image_bytes is not None else old_image_data
        final_name = new_name.strip()
        
        # If renaming, check if the target name already exists and is active. If so, archive it too.
        if final_name.lower() != old_name.lower():
             cursor.execute("SELECT product_id FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1", (final_name,))
             target_res = cursor.fetchone()
             if target_res:
                 cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (target_res[0],))
                 logger.info(f"update_product_recipe: Archived existing target product '{final_name}' (ID: {target_res[0]}) to allow overwrite.")
        
        # 3. Archive the old product
        cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (current_product_id,))
        
        # 4. Create new product version
        cursor.execute("INSERT INTO products (display_name, selling_price, image_data, active) VALUES (?, ?, ?, 1)",
                       (final_name, final_price, final_image))
        new_p_id = cursor.lastrowid
        
        # 5. Insert new recipe items
        for item_id, qty in recipe_items:
            cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (?, ?, ?)", 
                           (new_p_id, item_id, qty))
        
        logger.info(f"update_product_recipe: Archived old version and created new version (ID: {new_p_id}) for '{final_name}'")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"update_product_recipe: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_product(product_id: int) -> bool:
    """Soft deletes a product by marking it inactive."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (product_id,))
        logger.info(f"delete_product: Soft deleted product_id {product_id}")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"delete_product: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def undo_production(goal_id: int) -> bool:
    """Decrements production count and adds back inventory (BOM)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Get product_id from the goal to know what to restore
        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        if not res:
            return False
        p_id = res[0]
        
        # Find latest log entry SPECIFICALLY for this goal
        cursor.execute("SELECT log_id FROM production_logs WHERE goal_id = ? ORDER BY log_id DESC LIMIT 1", (goal_id,))
        log_res = cursor.fetchone()
        
        if log_res:
            l_id = log_res[0]
            logger.info(f"undo_production: Reverting production for goal_id {goal_id}, log_id {l_id}")
            
            # Delete the log entry
            cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (l_id,))
            
            # Decrement the goal
            cursor.execute("UPDATE production_goals SET qty_made = qty_made - 1 WHERE goal_id = ?", (goal_id,))
            
            # Add back to Inventory (Bill of Materials)
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (p_id,))
            recipe_items = cursor.fetchall()
            
            for i_id, qty in recipe_items:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand + ? WHERE item_id = ?", (qty, i_id))
            
            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"undo_production: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_all_recipes() -> pd.DataFrame:
    """Fetches all active product recipes with ingredient details."""
    conn = get_connection()
    try:
        query = """
        SELECT p.product_id, p.display_name as Product, p.selling_price as Price, p.image_data, p.active, i.name as Ingredient, r.qty_needed as Qty
        FROM products p
        LEFT JOIN recipes r ON p.product_id = r.product_id
        LEFT JOIN inventory i ON r.item_id = i.item_id
        ORDER BY p.display_name ASC
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"get_all_recipes: Error fetching recipes: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def process_clipboard_update(text_data: str) -> Tuple[List[str], List[str]]:
    """Parses lines like 'Rose 50' or 'Vase, 10' to update inventory counts."""
    conn = get_connection()
    updated_items = []
    errors = []
    
    try:
        cursor = conn.cursor()
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
                
        logger.info(f"process_clipboard_update: Processed batch. Updated: {len(updated_items)}, Errors: {len(errors)}")
        conn.commit()
    except Exception as e:
        logger.error(f"process_clipboard_update: Error: {e}")
        errors.append(f"System Error: {e}")
        conn.rollback()
    finally:
        conn.close()
        
    return updated_items, errors

def create_new_product(
    name: str, 
    selling_price: float, 
    image_bytes: Optional[bytes], 
    recipe_items: List[Tuple[int, int]]
) -> bool:
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
        
        logger.info(f"create_new_product: Created new product '{name}' (ID: {product_id})")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"create_new_product: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_product_exists(product_name: str) -> bool:
    """Checks if a product name already exists (case-insensitive) and is active."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1", (product_name,))
        exists = cursor.fetchone() is not None
        return exists
    except Exception as e:
        logger.error(f"check_product_exists: Error checking product {product_name}: {e}")
        return False
    finally:
        conn.close()

def get_product_image(product_name: str) -> Optional[bytes]:
    """Fetches the thumbnail for a specific active product."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT image_data FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1", (product_name,))
        res = cursor.fetchone()
        return res[0] if res else None
    except Exception as e:
        logger.error(f"get_product_image: Error fetching image for {product_name}: {e}")
        return None
    finally:
        conn.close()

def get_product_details(product_name: str) -> Optional[dict]:
    """Fetches full details for a product, including all recipe items."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Get Product Info
        cursor.execute("SELECT product_id, selling_price, image_data, display_name FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1", (product_name,))
        res = cursor.fetchone()
        if not res:
            return None
        
        p_id, price, img, db_name = res
        
        # Get Recipe Items
        cursor.execute("""
            SELECT r.item_id, i.name, r.qty_needed 
            FROM recipes r
            JOIN inventory i ON r.item_id = i.item_id
            WHERE r.product_id = ?
        """, (p_id,))
        
        recipe_items = [{"item_id": row[0], "name": row[1], "qty": row[2]} for row in cursor.fetchall()]
        
        return {
            "product_id": p_id,
            "name": db_name,
            "price": price,
            "image_data": img,
            "recipe": recipe_items
        }
    except Exception as e:
        logger.error(f"get_product_details: Error: {e}")
        return None
    finally:
        conn.close()

def update_inventory_cost(item_id: int, new_cost: float) -> bool:
    """Updates the unit cost for a specific inventory item."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE inventory SET unit_cost = ? WHERE item_id = ?", (new_cost, item_id))
        logger.info(f"update_inventory_cost: Updated cost for item_id {item_id} to {new_cost}")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"update_inventory_cost: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_item_details(item_id, count, cost, bundle_count):
    """Updates count, cost, and bundle_count for an inventory item."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE inventory SET count_on_hand = ?, unit_cost = ?, bundle_count = ? WHERE item_id = ?", (count, cost, bundle_count, item_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"update_item_details: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
