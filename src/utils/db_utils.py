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
        SELECT p.product_id, p.display_name as Product, p.image_data, p.active, pg.due_date, pg.qty_ordered, pg.qty_made
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
        
        summary = df.groupby(['week_start_iso', 'Week Starting', 'product_id', 'Product', 'active']).agg({
            'qty_ordered': 'sum',
            'qty_made': 'sum',
            'image_data': 'first'
        }).reset_index()
        
        return summary
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

def log_production(p_id: int, week_start_str: Optional[str] = None) -> bool:
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
        
        cursor.execute(query, params)
        goal_res = cursor.fetchone()
        
        logger.debug(f"log_production: p_id={p_id}, week_start_str={week_start_str}, result={goal_res}")

        if goal_res:
            g_id = goal_res[0]
            logger.info(f"log_production: Logging production for product_id {p_id} under goal_id {g_id}")
            cursor.execute("UPDATE production_goals SET qty_made = qty_made + 1 WHERE goal_id = ?", (g_id,))
            
            # Insert Log Entry
            cursor.execute("INSERT INTO production_logs (goal_id, product_id) VALUES (?, ?)", (g_id, p_id))
            
            # 3. Deduct Inventory (Bill of Materials)
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (p_id,))
            recipe_items = cursor.fetchall()
            
            if not recipe_items:
                logger.warning(f"log_production: No recipe found for product_id {p_id}")
                
            for i_id, qty in recipe_items:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (qty, i_id))
            
            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"log_production: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_product_recipe(
    product_name: str, 
    recipe_items: List[Tuple[int, int]], 
    image_bytes: Optional[bytes] = None, 
    new_price: Optional[float] = None
) -> bool:
    """Archives the old product and creates a new version with updated details."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Find the current active product to get its ID and current data
        cursor.execute("SELECT product_id, selling_price, image_data FROM products WHERE display_name = ? AND active = 1 COLLATE NOCASE", (product_name,))
        res = cursor.fetchone()
        if not res:
            return False
        
        old_p_id, old_price, old_image_data = res
        
        # 2. Determine new values (use old ones if not provided)
        final_price = new_price if new_price is not None else old_price
        final_image = image_bytes if image_bytes is not None else old_image_data
        
        # 3. Archive the old product
        cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (old_p_id,))
        
        # 4. Create new product version
        cursor.execute("INSERT INTO products (display_name, selling_price, image_data, active) VALUES (?, ?, ?, 1)",
                       (product_name, final_price, final_image))
        new_p_id = cursor.lastrowid
        
        # 5. Insert new recipe items
        for item_id, qty in recipe_items:
            cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (?, ?, ?)", 
                           (new_p_id, item_id, qty))
        
        logger.info(f"update_product_recipe: Archived old version and created new version (ID: {new_p_id}) for '{product_name}'")
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

def undo_production(p_id: int, week_start_str: Optional[str] = None) -> bool:
    """Decrements production count and adds back inventory (BOM)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Find latest log entry for this product (linked to goal)
        query = """
            SELECT l.log_id, l.goal_id 
            FROM production_logs l
            JOIN production_goals pg ON l.goal_id = pg.goal_id
            WHERE l.product_id = ?
        """
        params = [p_id]

        if week_start_str:
            # Filter by the specific week selected in the UI
            start_date = pd.to_datetime(week_start_str).date()
            end_date = start_date + pd.Timedelta(days=6)
            query += " AND pg.due_date BETWEEN ? AND ?"
            params.extend([str(start_date), str(end_date)])

        # Order by Log ID DESC to undo the absolute most recent action
        query += " ORDER BY l.log_id DESC LIMIT 1"
        
        cursor.execute(query, params)
        log_res = cursor.fetchone()
        
        if log_res:
            l_id, g_id = log_res
            logger.info(f"undo_production: Reverting production for product_id {p_id}, log_id {l_id}")
            
            # Delete the log entry
            cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (l_id,))
            
            # Decrement the goal
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
