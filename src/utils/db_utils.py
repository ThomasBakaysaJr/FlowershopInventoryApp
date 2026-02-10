import sqlite3
import pandas as pd
import os
import logging
from typing import Optional, List, Tuple, Union
import uuid
import io
import csv
from src.utils import utils

logger = logging.getLogger(__name__)

DB_PATH = 'inventory.db'

def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)

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

def log_production(goal_id: int, substitutions: list = None, ignore_recipe: bool = False) -> bool:
    """
    Increments production count and deducts inventory (BOM).
    substitutions: List of (item_id, qty_to_deduct) derived from user selection for generics.
    ignore_recipe: If True, standard recipe items are NOT deducted; only 'substitutions' are used.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 2. Get product_id and current status from the specific goal
        cursor.execute("SELECT product_id, qty_fulfilled, qty_ordered FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        
        if not res:
            logger.error(f"log_production: Goal ID {goal_id} not found.")
            return False
        
        p_id, qty_fulfilled, qty_ordered = res
        logger.debug(f"log_production: goal_id={goal_id}, product_id={p_id}")

        # Update Goal
        cursor.execute("UPDATE production_goals SET qty_fulfilled = qty_fulfilled + 1 WHERE goal_id = ?", (goal_id,))
        
        # Insert Log Entry
        cursor.execute("INSERT INTO production_logs (goal_id, product_id, action_type) VALUES (?, ?, 'MAKE')", (goal_id, p_id))
        
        # 3. Deduct Standard Inventory (Specific Items)
        if not ignore_recipe:
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ? AND requirement_type = 'Specific'", (p_id,))
            specific_items = cursor.fetchall()
            
            for i_id, qty in specific_items:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (qty, i_id))
            
        # 4. Deduct Substitutions (The Dynamic Part)
        if substitutions:
            for sub_item_id, sub_qty in substitutions:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (sub_qty, sub_item_id))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"log_production: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ==========================================
# 📦 BULK INVENTORY OPERATIONS (Count & Cost)
# ==========================================

def export_inventory_csv() -> str:
    """Generates a CSV string of the current inventory for auditing."""
    conn = get_connection()
    try:
        # We export ID so we can match exactly on re-upload
        df = pd.read_sql_query("SELECT item_id, name, category, sub_category, unit_cost, bundle_count, count_on_hand FROM inventory ORDER BY category, name", conn)
        return df.to_csv(index=False)
    except Exception as e:
        logger.error(f"export_inventory_csv: {e}")
        return ""
    finally:
        conn.close()

def process_bulk_inventory_upload(file_obj) -> Tuple[int, List[str]]:
    """Reads a CSV file and updates inventory. Matches by ID first, then Name."""
    conn = get_connection()
    cursor = conn.cursor()
    updated_count = 0
    errors = []
    
    try:
        df = pd.read_csv(file_obj)
        # Normalize headers to lowercase to be user-friendly
        df.columns = [c.lower().strip() for c in df.columns]
        
        if 'name' not in df.columns or 'count_on_hand' not in df.columns:
            return 0, ["CSV missing required columns: 'name', 'count_on_hand'"]
            
        for index, row in df.iterrows():
            try:
                name = str(row['name']).strip()
                
                # Robust casting for Quantity
                try:
                    qty = int(float(row['count_on_hand']))
                except (ValueError, TypeError):
                    qty = 0
                
                # Optional fields (use existing defaults if missing)
                cat = row.get('category', None)
                if pd.isna(cat): cat = None
                
                sub = row.get('sub_category', None)
                if pd.isna(sub): sub = None
                
                # Robust casting for Cost (handle '$' and ',')
                raw_cost = row.get('unit_cost', 0.0)
                try:
                    cost = float(str(raw_cost).replace('$', '').replace(',', '')) if pd.notna(raw_cost) else 0.0
                except (ValueError, TypeError):
                    cost = 0.0
                
                # Robust casting for Bundle Count
                raw_bundle = row.get('bundle_count', 1)
                try:
                    bundle = int(float(raw_bundle)) if pd.notna(raw_bundle) else 1
                except (ValueError, TypeError):
                    bundle = 1

                i_id = row.get('item_id', None)
                if pd.isna(i_id): i_id = None
                else:
                    try:
                        i_id = int(float(i_id))
                    except (ValueError, TypeError):
                        i_id = None
                
                # LOGIC: ID Match -> Update; No ID -> Insert New (No Name Match Overwrite)
                if i_id:
                    cursor.execute("""
                        UPDATE inventory 
                        SET name=?, category=?, sub_category=?, count_on_hand=?, unit_cost=?, bundle_count=?
                        WHERE item_id=?
                    """, (name, cat, sub, qty, cost, bundle, i_id))
                else:
                    cursor.execute("""
                        INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (name, cat, sub, qty, cost, bundle))
                
                updated_count += 1
                
            except Exception as row_e:
                errors.append(f"Row {index + 2} Error: {row_e}")
                
        conn.commit()
        return updated_count, errors
    except Exception as e:
        logger.error(f"process_bulk_inventory_upload: {e}")
        conn.rollback()
        return 0, [str(e)]
    finally:
        conn.close()

# ==========================================
# 🌸 BULK RECIPE OPERATIONS (Catalog)
# ==========================================

def export_products_csv() -> str:
    """Generates a 'Tidy Data' CSV of all products/recipes."""
    conn = get_connection()
    try:
        # We explicitly grab the 'category' column to support One-Offs
        query = """
        SELECT p.product_id, p.display_name as Product, p.selling_price as Price, p.category as Type, p.note as "Product Note",
               r.item_id, 
               COALESCE(i.name, 'Any ' || r.requirement_value, 'Unknown Item') as Ingredient, 
               r.note as Note,
               r.qty_needed as Qty
        FROM products p
        LEFT JOIN recipes r ON p.product_id = r.product_id
        LEFT JOIN inventory i ON r.item_id = i.item_id
        WHERE p.active = 1
        ORDER BY p.display_name
        """
        df = pd.read_sql_query(query, conn)
        return df.to_csv(index=False)
    except Exception as e:
        logger.error(f"export_products_csv: {e}")
        return ""
    finally:
        conn.close()

def _get_local_image_bytes(product_name: str) -> Optional[bytes]:
    """Helper to find and process a local image for a product from images/recipes."""
    image_dir = os.path.join("images", "recipes")
    if not os.path.exists(image_dir):
        return None
        
    candidates = [
        product_name,
        product_name.replace(" ", "_"),
        product_name.lower(),
        product_name.lower().replace(" ", "_")
    ]
    
    for name in candidates:
        for ext in [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]:
            path = os.path.join(image_dir, name + ext)
            if os.path.exists(path):
                try:
                    return utils.process_image(path)
                except Exception as e:
                    logger.warning(f"Failed to process image {path}: {e}")
    return None

def process_bulk_recipe_upload(file_obj) -> Tuple[int, List[str]]:
    """Imports products/recipes. Format: Product, Price, Type, Ingredient, Qty."""
    conn = get_connection()
    cursor = conn.cursor()
    created_count = 0
    errors = []
    
    try:
        df = pd.read_csv(file_obj)
        df.columns = [c.lower().strip() for c in df.columns]
        
        required = ['product', 'qty']
        if not all(col in df.columns for col in required):
            return 0, [f"CSV missing required columns: {required}"]
            
        # Group by Product Name so we process the whole recipe at once
        grouped = df.groupby('product')
        
        for product_name, group in grouped:
            try:
                # 1. Product Details (from first row)
                first_row = group.iloc[0]
                
                # Check for Product ID
                p_id_val = first_row.get('product_id')
                target_p_id = None
                if pd.notna(p_id_val):
                    try:
                        target_p_id = int(float(p_id_val))
                    except (ValueError, TypeError): pass

                raw_price = first_row.get('price', 0.0)
                try:
                    price = float(str(raw_price).replace('$', '').replace(',', '')) if pd.notna(raw_price) else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                # This handles your "One-Off" vs "Standard" logic
                cat = first_row.get('type', 'Standard') 
                if pd.isna(cat): cat = 'Standard'
                
                # Product Note
                prod_note = str(first_row.get('product note', '')).strip() or None
                
                # 2. Build Recipe List
                recipe_items = []
                for _, row in group.iterrows():
                    try:
                        qty = int(float(row['qty']))
                    except (ValueError, TypeError):
                        qty = 0
                        
                    if qty <= 0: continue
                    
                    item_id = None
                    req_type = 'Specific'
                    req_val = None
                    note = str(row.get('note', '')).strip() or None
                    ing_name = str(row.get('ingredient', '')).strip()
                    
                    # Strategy 1: Lookup by ID (Preferred)
                    if 'item_id' in row and pd.notna(row['item_id']):
                        try:
                            tid = int(float(row['item_id']))
                            cursor.execute("SELECT item_id FROM inventory WHERE item_id = ?", (tid,))
                            res = cursor.fetchone()
                            if res: item_id = res[0]
                        except (ValueError, TypeError): pass
                    
                    # Strategy 2: Lookup by Name (Fallback)
                    if item_id is None and ing_name:
                        cursor.execute("SELECT item_id FROM inventory WHERE name = ? COLLATE NOCASE", (ing_name,))
                        res = cursor.fetchone()
                        if res: item_id = res[0]
                    
                    # Strategy 3: Generic Detection (e.g. "Any Rose")
                    if item_id is None and ing_name.lower().startswith("any "):
                        req_type = 'Category'
                        req_val = ing_name[4:].strip()
                    
                    if item_id is None:
                        # Only raise error if it's not a valid Generic
                        if req_type == 'Specific':
                            id_ref = row.get('item_id', 'N/A')
                            raise ValueError(f"Ingredient not found in Inventory (Name: '{ing_name}', ID: {id_ref}).")
                    
                    recipe_items.append((item_id, qty, req_type, req_val, note))
                
                if not recipe_items:
                    errors.append(f"Skipped '{product_name}': No valid ingredients.")
                    continue

                # 3. Create or Update Product based on ID
                prod_exists = False
                if target_p_id:
                    cursor.execute("SELECT 1 FROM products WHERE product_id = ?", (target_p_id,))
                    if cursor.fetchone():
                        prod_exists = True
                
                # Try to find local image
                new_image_bytes = _get_local_image_bytes(product_name)
                
                if prod_exists:
                    # UPDATE (Immutable Pattern)
                    # 1. Fetch existing data to preserve (Image, Stock, Variants)
                    cursor.execute("SELECT image_data, stock_on_hand, variant_group_id, variant_type FROM products WHERE product_id = ?", (target_p_id,))
                    existing_data = cursor.fetchone()
                    old_img = existing_data[0] if existing_data else None
                    old_stock = existing_data[1] if existing_data else 0
                    old_group_id = existing_data[2] if existing_data and existing_data[2] else str(uuid.uuid4())
                    old_variant_type = existing_data[3] if existing_data and existing_data[3] else 'STD'
                    
                    # Determine final image: New local image takes precedence, otherwise keep old
                    final_img = new_image_bytes if new_image_bytes else old_img
                    
                    # 2. Archive Old
                    cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (target_p_id,))
                    
                    # 3. Create New (New Price/Cat, Old Image/Stock, Preserved Variant Info)
                    cursor.execute("INSERT INTO products (display_name, selling_price, image_data, active, stock_on_hand, category, note, variant_group_id, variant_type) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)", 
                                   (product_name, price, final_img, old_stock, cat, prod_note, old_group_id, old_variant_type))
                    new_id = cursor.lastrowid
                    
                    # 4. Insert Recipes
                    for item_id, q, r_type, r_val, note in recipe_items:
                        cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) VALUES (?, ?, ?, ?, ?, ?)", (new_id, item_id, q, r_type, r_val, note))
                else:
                    # INSERT (New Product)
                    new_group_id = str(uuid.uuid4())
                    cursor.execute("INSERT INTO products (display_name, selling_price, image_data, category, active, stock_on_hand, note, variant_group_id, variant_type) VALUES (?, ?, ?, ?, 1, 0, ?, ?, 'STD')", 
                                   (product_name, price, new_image_bytes, cat, prod_note, new_group_id))
                    new_id = cursor.lastrowid
                    for item_id, q, r_type, r_val, note in recipe_items:
                        cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) VALUES (?, ?, ?, ?, ?, ?)", (new_id, item_id, q, r_type, r_val, note))
                
                created_count += 1
                
            except Exception as prod_e:
                errors.append(f"Error processing '{product_name}': {prod_e}")
        
        conn.commit()
        return created_count, errors
    except Exception as e:
        logger.error(f"process_bulk_recipe_upload: {e}")
        conn.rollback()
        return 0, [str(e)]
    finally:
        conn.close()

def update_product_recipe(
    current_product_id: int,
    new_name: str,
    recipe_items: List[Union[Tuple[int, int], dict]], 
    image_bytes: Optional[bytes] = None, 
    new_price: Optional[float] = None,
    rollover_stock: bool = True,
    variant_group_id: Optional[str] = None,
    category: str = "Standard",
    migrate_goals: bool = False,
    goal_date: Optional[str] = None,
    goal_qty: int = 0,
    note: Optional[str] = None
) -> bool:
    """Archives the old product and creates a new version with updated details."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Find the current product to get its current data
        cursor.execute("SELECT selling_price, image_data, display_name, stock_on_hand, note, variant_group_id, variant_type FROM products WHERE product_id = ?", (current_product_id,))
        res = cursor.fetchone()
        if not res:
            return False
        
        old_price, old_image_data, old_name, current_stock, old_note, old_group_id, old_variant_type = res
        
        # 2. Determine new values (use old ones if not provided)
        final_price = new_price if new_price is not None else old_price
        final_image = image_bytes if image_bytes is not None else old_image_data
        final_name = new_name.strip()
        final_note = note if note is not None else old_note
        
        # Preserve variant info unless explicitly overwritten (which usually doesn't happen in simple edits)
        final_group_id = variant_group_id if variant_group_id else (old_group_id if old_group_id else str(uuid.uuid4()))
        
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
        final_stock = current_stock if rollover_stock else 0
        cursor.execute("INSERT INTO products (display_name, selling_price, image_data, active, stock_on_hand, category, note, variant_group_id, variant_type) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)",
                       (final_name, final_price, final_image, final_stock, category, final_note, final_group_id, old_variant_type or 'STD'))
        new_p_id = cursor.lastrowid
        
        # 5. Insert new recipe items
        for item in recipe_items:
            # Handle both old format (tuple) and new format (dict)
            if isinstance(item, tuple):
                item_id, qty = item
                req_type, req_val = 'Specific', None
                note = None
            elif isinstance(item, dict):
                item_id = item.get('id') or item.get('item_id')
                qty = item.get('qty')
                req_type = item.get('type', 'Specific')
                req_val = item.get('val') or item.get('value')
                note = item.get('note')

            cursor.execute("""INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) 
                              VALUES (?, ?, ?, ?, ?, ?)""", (new_p_id, item_id, qty, req_type, req_val, note))
        
        # 6. Migrate Goals (if requested)
        if migrate_goals:
            cursor.execute("UPDATE production_goals SET product_id = ? WHERE product_id = ? AND qty_fulfilled < qty_ordered", (new_p_id, current_product_id))
            logger.info(f"update_product_recipe: Migrated unfulfilled goals from {current_product_id} to {new_p_id}")
        
        # 7. Add New Goal (if requested)
        if goal_date and goal_qty > 0:
            d_str = goal_date.strftime('%Y-%m-%d') if hasattr(goal_date, 'strftime') else str(goal_date)
            cursor.execute("INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled) VALUES (?, ?, ?, 0)", 
                           (new_p_id, d_str, goal_qty))
            logger.info(f"update_product_recipe: Added new goal for '{final_name}' (Qty: {goal_qty}, Due: {d_str})")

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
        goal_p_id = res[0] # Current Goal Product ID (for Stock returns)
        
        # Find latest log entry SPECIFICALLY for this goal
        cursor.execute("SELECT log_id, action_type, product_id FROM production_logs WHERE goal_id = ? ORDER BY log_id DESC LIMIT 1", (goal_id,))
        log_res = cursor.fetchone()
        
        if log_res:
            l_id, action_type, log_p_id = log_res
            logger.info(f"undo_production: Reverting production for goal_id {goal_id}, log_id {l_id}")
            
            # If this was a PACK action (Cooler -> Order), we must return to Cooler, not Raw Inventory
            if action_type == 'PACK':
                cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (l_id,))
                cursor.execute("UPDATE production_goals SET qty_fulfilled = qty_fulfilled - 1 WHERE goal_id = ?", (goal_id,))
                # Return to the CURRENT Goal's product stock (handles migration correctly)
                cursor.execute("UPDATE products SET stock_on_hand = stock_on_hand + 1 WHERE product_id = ?", (goal_p_id,))
                conn.commit()
                return True
            
            # Delete the log entry
            cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (l_id,))
            
            # Decrement the goal
            cursor.execute("UPDATE production_goals SET qty_fulfilled = qty_fulfilled - 1 WHERE goal_id = ?", (goal_id,))
            
            # Add back to Inventory (Bill of Materials) 
            # CRITICAL: Use log_p_id (Original Version) to restore correct ingredients
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (log_p_id,))
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

def fulfill_goal(goal_id: int, qty: int = 1) -> int:
    """Decrements stock_on_hand and increments qty_fulfilled for a goal (Cooler -> Order)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        qty = int(qty) # Ensure integer for range() and SQL
        
        # Check stock, product_id, and category
        # UPDATED: Also fetch goal status to clamp qty
        cursor.execute("""
            SELECT p.stock_on_hand, p.product_id, p.category, pg.qty_ordered, pg.qty_fulfilled
            FROM production_goals pg
            JOIN products p ON pg.product_id = p.product_id
            WHERE pg.goal_id = ?
        """, (goal_id,))
        res = cursor.fetchone()
        
        if not res: return 0
        stock, p_id, category, ordered, fulfilled = res
        
        needed = max(0, ordered - fulfilled)
        
        # Robustness: Clamp qty to what is available and what is needed
        # This prevents over-drafting stock and over-fulfilling goals
        actual_qty = min(qty, stock, needed)
        
        if actual_qty <= 0:
            logger.warning(f"fulfill_goal: Cannot pack (Requested: {qty}, Stock: {stock}, Needed: {needed})")
            return 0
            
        # 1. Update Product Stock (Remove from Cooler)
        cursor.execute("UPDATE products SET stock_on_hand = stock_on_hand - ? WHERE product_id = ?", (actual_qty, p_id))
        
        # 2. Update Goal (Mark as Fulfilled)
        cursor.execute("UPDATE production_goals SET qty_fulfilled = qty_fulfilled + ? WHERE goal_id = ?", (actual_qty, goal_id))
        
        # 3. Log it (Multiple entries for granular undo)
        logs = [(goal_id, p_id, 'PACK') for _ in range(actual_qty)]
        cursor.executemany("INSERT INTO production_logs (goal_id, product_id, action_type) VALUES (?, ?, ?)", logs)
        
        # 4. Auto-Archive One-Offs if complete
        if category == 'One-Off':
            # Check if stock is depleted
            # Note: We just decremented stock, so we check the new value
            new_stock = stock - actual_qty
            
            # Check for any remaining unfulfilled goals
            cursor.execute("SELECT COUNT(*) FROM production_goals WHERE product_id = ? AND qty_fulfilled < qty_ordered", (p_id,))
            pending_goals = cursor.fetchone()[0]
            
            if new_stock <= 0 and pending_goals == 0:
                logger.info(f"fulfill_goal: Auto-archiving completed One-Off product {p_id}")
                cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (p_id,))

        conn.commit()
        return actual_qty
    except sqlite3.Error as e:
        logger.error(f"fulfill_goal: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

def undo_fulfillment(goal_id: int) -> bool:
    """Reverts a fulfillment: increments stock_on_hand, decrements qty_fulfilled."""
    # This is functionally similar to undo_production but restores to STOCK, not INVENTORY.
    # Since undo_production restores to INVENTORY (BOM), we need this specific function for the Cooler Model.
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Get product_id
        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        if not res: return False
        p_id = res[0]
        
        # Find latest log for this goal
        cursor.execute("SELECT log_id FROM production_logs WHERE goal_id = ? ORDER BY log_id DESC LIMIT 1", (goal_id,))
        log_res = cursor.fetchone()
        
        if not log_res: return False
        log_id = log_res[0]
        
        # 1. Delete Log
        cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (log_id,))
        
        # 2. Revert Goal
        cursor.execute("UPDATE production_goals SET qty_fulfilled = qty_fulfilled - 1 WHERE goal_id = ?", (goal_id,))
        
        # 3. Return to Stock (Put back in Cooler)
        cursor.execute("UPDATE products SET stock_on_hand = stock_on_hand + 1 WHERE product_id = ?", (p_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"undo_fulfillment: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_all_recipes() -> pd.DataFrame:
    """Fetches all active product recipes with ingredient details."""
    conn = get_connection()
    try:
        query = """
        SELECT p.product_id, p.display_name as Product, p.selling_price as Price, p.image_data, p.active, p.stock_on_hand, p.category, p.note as ProductNote, p.variant_type,
               r.item_id, 
               COALESCE(i.name, 'Any ' || r.requirement_value, 'Unknown Item') as Ingredient, 
               r.qty_needed as Qty,
               r.note as Note
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

def get_forecast_initial_data(start_date, end_date) -> pd.DataFrame:
    """Fetches all active products + archived ones with goals, aggregating expected qty."""
    conn = get_connection()
    try:
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

        query = """
        SELECT p.product_id, p.display_name as Product, p.active, COALESCE(SUM(MAX(0, pg.qty_ordered - pg.qty_fulfilled)), 0) as Expected
        FROM products p
        LEFT JOIN production_goals pg ON p.product_id = pg.product_id AND pg.due_date BETWEEN ? AND ?
        WHERE p.active = 1 OR pg.goal_id IS NOT NULL
        GROUP BY p.product_id
        ORDER BY p.display_name ASC
        """
        df = pd.read_sql_query(query, conn, params=(s_date, e_date))
        return df
    except Exception as e:
        logger.error(f"get_forecast_initial_data: {e}")
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
            
            # Strategy 0: ID-based Update (Format: ID, Name..., bundle count X, count= Y, loss= Z)
            if line[0].isdigit() and "count=" in line:
                try:
                    parts = [p.strip() for p in line.split(',')]
                    item_id = int(parts[0])

                    # make sure this item exists in inventory
                    cursor.execute("SELECT 1 FROM inventory WHERE item_id = ?", (item_id,))
                    if not cursor.fetchone():
                        raise ValueError(f"Item ID {item_id} not found in inventory.")
                    
                    bundle_count = 1
                    count_val = None
                    loss_val = 0
                    
                    for part in parts:
                        lower = part.lower()
                        if "bundle_count=" in lower:
                            val = lower.split("bundle_count=")[1].strip()
                            if val: bundle_count = int(val)
                        elif "count=" in lower:
                            val = lower.split("count=")[1].strip()
                            if val: count_val = int(val)
                        elif "loss=" in lower:
                            val = lower.split("loss=")[1].strip()
                            if val: loss_val = int(val)
                    
                    if count_val is not None:
                        final_count = max(0, (count_val * bundle_count) - loss_val)
                        cursor.execute("UPDATE inventory SET count_on_hand = ? WHERE item_id = ?", (final_count, item_id))
                        
                        cursor.execute("SELECT name FROM inventory WHERE item_id = ?", (item_id,))
                        res = cursor.fetchone()
                        name = res[0] if res else f"Item {item_id}"
                        updated_items.append(f"{name} (New Stock: {final_count})")
                    continue
                except Exception as e:
                    errors.append(f"Error parsing ID line '{line}': {e}")
                    continue

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
    recipe_items: List[Union[Tuple[int, int], dict]],
    category: str = "Standard",
    goal_date: Optional[str] = None,
    goal_qty: int = 0, 
    note: Optional[str] = None,
    variant_group_id: Optional[str] = None,
    variant_type: str = "STD"
) -> bool:
    """Creates a new product and its associated recipe in a single transaction."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Generate a group ID if one wasn't provided (treats this as a standalone product/group of 1)
        if not variant_group_id:
            variant_group_id = str(uuid.uuid4())

        # 1. Insert Product
        cursor.execute("INSERT INTO products (display_name, selling_price, image_data, active, category, note, variant_group_id, variant_type) VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                       (name, selling_price, image_bytes, category, note, variant_group_id, variant_type))
        product_id = cursor.lastrowid
        
        # 2. Insert Recipe Items
        for item in recipe_items:
            # Handle both old format (tuple) and new format (dict)
            if isinstance(item, tuple):
                item_id, qty = item
                req_type, req_val = 'Specific', None
                note = None
            elif isinstance(item, dict):
                item_id = item.get('id') or item.get('item_id')
                qty = item.get('qty')
                req_type = item.get('type', 'Specific')
                req_val = item.get('val') or item.get('value')
                note = item.get('note')

            cursor.execute("""
                INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) 
                VALUES (?, ?, ?, ?, ?, ?)""", (product_id, item_id, qty, req_type, req_val, note))
        
        # 3. Insert Goal (if provided)
        if goal_date and goal_qty > 0:
            d_str = goal_date.strftime('%Y-%m-%d') if hasattr(goal_date, 'strftime') else str(goal_date)
            cursor.execute("INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled) VALUES (?, ?, ?, 0)", 
                           (product_id, d_str, goal_qty))
            logger.info(f"create_new_product: Added initial goal for '{name}' (Qty: {goal_qty}, Due: {d_str})")

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

def check_product_variant(product_name: str, variant_type: str) -> bool:
    """Checks if a specific variant of a product already exists and is active."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM products WHERE display_name = ? COLLATE NOCASE AND variant_type = ? AND active = 1", (product_name, variant_type))
        exists = cursor.fetchone() is not None
        return exists
    except Exception as e:
        logger.error(f"check_product_variant: Error checking {product_name} ({variant_type}): {e}")
        return False
    finally:
        conn.close()

def get_product_group_id(product_name: str) -> Optional[str]:
    """Fetches the variant_group_id for an active product."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT variant_group_id FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1", (product_name,))
        res = cursor.fetchone()
        return res[0] if res else None
    except Exception as e:
        logger.error(f"get_product_group_id: Error fetching group ID for {product_name}: {e}")
        return None
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
        cursor.execute("SELECT product_id, selling_price, image_data, display_name, stock_on_hand, category, note, variant_group_id, variant_type FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1", (product_name,))
        res = cursor.fetchone()
        if not res:
            return None
        
        p_id, price, img, db_name, stock, category, note, group_id, v_type = res
        
        # Get Recipe Items
        cursor.execute("""
            SELECT r.item_id, i.name, r.qty_needed, r.requirement_type, r.requirement_value, r.note
            FROM recipes r
            LEFT JOIN inventory i ON r.item_id = i.item_id
            WHERE r.product_id = ?
        """, (p_id,))
        
        recipe_items = []
        for row in cursor.fetchall():
            # If specific item name is None, use the generic requirement value (e.g. "Any Rose")
            if row[1]:
                name = row[1]
            elif row[4]:
                name = f"Any {row[4]}"
            else:
                name = "Unknown Item"
            recipe_items.append({
                "item_id": row[0], 
                "name": name, 
                "qty": row[2],
                "type": row[3],
                "val": row[4],
                "note": row[5]
            })
        
        # Get Variants (Siblings)
        variants = []
        if group_id:
            cursor.execute("""
                SELECT product_id, display_name, variant_type 
                FROM products 
                WHERE variant_group_id = ? AND active = 1 
                ORDER BY CASE variant_type WHEN 'STD' THEN 1 WHEN 'DLX' THEN 2 WHEN 'PRM' THEN 3 ELSE 4 END
            """, (group_id,))
            for vid, vname, vtype in cursor.fetchall():
                variants.append({"product_id": vid, "name": vname, "type": vtype})

        return {
            "product_id": p_id,
            "name": db_name,
            "price": price,
            "image_data": img,
            "recipe": recipe_items,
            "stock_on_hand": stock,
            "category": category,
            "note": note,
            "variant_group_id": group_id,
            "variant_type": v_type,
            "variants": variants
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
    conn = get_connection()
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

def add_inventory_item(name: str, category: str, sub_category: str, count: int, cost: float, bundle_count: int) -> bool:
    """Adds a new inventory item. Returns False if name exists."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check duplicate
        cursor.execute("SELECT 1 FROM inventory WHERE name = ? COLLATE NOCASE", (name,))
        if cursor.fetchone():
            logger.warning(f"add_inventory_item: Duplicate name '{name}'")
            return False

        cursor.execute("""
            INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, category, sub_category, count, cost, bundle_count))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"add_inventory_item: {e}")
        return False
    finally:
        conn.close()

def get_production_goals_range(start_date, end_date) -> pd.DataFrame:
    """Fetches production goals falling within a specific date range."""
    conn = get_connection()
    try:
        # Ensure strings for SQLite comparison
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)
        
        query = """
        SELECT pg.goal_id, p.product_id, p.display_name as Product, p.image_data, p.active, p.stock_on_hand, p.note, p.variant_type, pg.due_date, pg.qty_ordered, pg.qty_fulfilled
        FROM production_goals pg
        JOIN products p ON pg.product_id = p.product_id
        WHERE pg.due_date BETWEEN ? AND ?
        ORDER BY pg.due_date ASC, p.display_name ASC
        """
        df = pd.read_sql_query(query, conn, params=(s_date, e_date))
        return df
    except Exception as e:
        logger.error(f"get_production_goals_range: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def get_active_and_scheduled_products(start_date, end_date) -> pd.DataFrame:
    """Returns products that are Active OR have goals in the date range (for dropdowns)."""
    conn = get_connection()
    try:
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

        query = """
        SELECT DISTINCT p.product_id, p.display_name 
        FROM products p
        WHERE p.active = 1
        OR p.product_id IN (
            SELECT product_id FROM production_goals 
            WHERE due_date BETWEEN ? AND ?
        )
        ORDER BY p.display_name ASC
        """
        df = pd.read_sql_query(query, conn, params=(s_date, e_date))
        return df
    except Exception as e:
        logger.error(f"get_active_and_scheduled_products: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def get_production_requirements(start_date, end_date) -> pd.DataFrame:
    """Fetches products with their current stock and aggregated requirements for the date range."""
    conn = get_connection()
    try:
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)
        
        query = """
        SELECT 
            p.product_id, 
            p.display_name as Product, 
            p.image_data, 
            p.active, 
            MAX(p.stock_on_hand) as stock_on_hand,
            MAX(p.note) as note,
            MAX(p.variant_type) as variant_type,
            COALESCE(SUM(MAX(0, pg.qty_ordered - pg.qty_fulfilled)), 0) as required_qty
        FROM products p
        LEFT JOIN production_goals pg ON p.product_id = pg.product_id AND pg.due_date BETWEEN ? AND ?
        WHERE p.active = 1 OR pg.goal_id IS NOT NULL
        GROUP BY p.product_id
        ORDER BY p.display_name ASC
        """
        df = pd.read_sql_query(query, conn, params=(s_date, e_date))
        return df
    except Exception as e:
        logger.error(f"get_production_requirements: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def produce_stock(product_id: int, substitutions: list = None, ignore_recipe: bool = False) -> bool:
    """Increments stock_on_hand and deducts inventory (BOM). Logs with goal_id=NULL."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Update Product Stock
        cursor.execute("UPDATE products SET stock_on_hand = stock_on_hand + 1 WHERE product_id = ?", (product_id,))
        
        if cursor.rowcount == 0:
            logger.warning(f"produce_stock: No product found with ID {product_id}")
            return False
        
        # 2. Log it (goal_id is NULL for stock production)
        cursor.execute("INSERT INTO production_logs (goal_id, product_id, action_type) VALUES (NULL, ?, 'STOCK')", (product_id,))
        
        # 3. Deduct Inventory
        if not ignore_recipe:
            # Only deduct Specific items automatically
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ? AND requirement_type = 'Specific'", (product_id,))
            specific_items = cursor.fetchall()
            
            for i_id, qty in specific_items:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (qty, i_id))
            
        # 4. Deduct Substitutions (Generic Items)
        if substitutions:
            for sub_item_id, sub_qty in substitutions:
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (sub_qty, sub_item_id))
            
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"produce_stock: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def undo_stock_production(product_id: int) -> bool:
    """Decrements stock_on_hand and restores inventory. Reverts last log where goal_id is NULL."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Find latest log for this product with NULL goal_id (meaning it was a stock production)
        cursor.execute("SELECT log_id, action_type FROM production_logs WHERE product_id = ? AND goal_id IS NULL ORDER BY log_id DESC LIMIT 1", (product_id,))
        res = cursor.fetchone()
        
        if not res:
            return False
        
        log_id, action_type = res

        # Safety: Never undo a PACK action here (it implies a deleted goal, not stock production)
        if action_type == 'PACK':
            logger.warning(f"undo_stock_production: Skipped PACK log {log_id}. This log should have been deleted when its goal was removed.")
            return False
        
        # 1. Delete Log
        cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (log_id,))
        
        # 2. Decrement Stock
        cursor.execute("UPDATE products SET stock_on_hand = stock_on_hand - 1 WHERE product_id = ?", (product_id,))
        
        if cursor.rowcount == 0:
            logger.warning(f"undo_stock_production: No product found with ID {product_id}")
            return False

        # 3. Restore Inventory
        cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (product_id,))
        recipe_items = cursor.fetchall()
        
        for i_id, qty in recipe_items:
            cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand + ? WHERE item_id = ?", (qty, i_id))
            
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"undo_stock_production: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_active_product_options() -> pd.DataFrame:
    """Returns a simple list of active products for dropdowns."""
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT product_id, display_name FROM products WHERE active = 1 ORDER BY display_name", conn)
    except Exception as e:
        logger.error(f"get_active_product_options: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def add_production_goal(product_id: int, due_date: str, qty_ordered: int) -> bool:
    """Adds a new production goal."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled) VALUES (?, ?, ?, 0)", 
                       (product_id, due_date, qty_ordered))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"add_production_goal: {e}")
        return False
    finally:
        conn.close()

def delete_production_goal(goal_id: int) -> bool:
    """Removes a goal. Any items ALREADY made for this goal are returned to General Stock."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Check if we have any progress on this goal
        cursor.execute("SELECT product_id, qty_fulfilled FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        
        if res:
            p_id, made_count = res
            
            # 2. If items were made, move them to 'Stock On Hand' (Back to Cooler)
            if made_count > 0:
                logger.info(f"delete_production_goal: Returning {made_count} items to stock for product {p_id}")
                cursor.execute("UPDATE products SET stock_on_hand = stock_on_hand + ? WHERE product_id = ?", (made_count, p_id))
                
                # 3. Handle Logs
                # A. 'PACK' logs (Stock -> Goal) should be DELETED. Reversing the goal means putting them back in stock, effectively cancelling the move.
                cursor.execute("DELETE FROM production_logs WHERE goal_id = ? AND action_type = 'PACK'", (goal_id,))
                # B. 'MAKE' logs (Inventory -> Goal) should be DETACHED. They become valid "Stock Production" history.
                cursor.execute("UPDATE production_logs SET goal_id = NULL WHERE goal_id = ? AND action_type != 'PACK'", (goal_id,))
        
        # 4. Delete the goal itself
        cursor.execute("DELETE FROM production_goals WHERE goal_id = ?", (goal_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"delete_production_goal: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_recipe_requirements(product_id: int) -> dict:
    """
    Analyzes a recipe to see if it has 'Category' requirements that need user input.
    Returns: {
        'has_generics': bool,
        'specific_items': [(item_id, qty), ...],
        'generic_items': [{'category': 'Rose', 'qty': 12}, ...]
    }
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT item_id, qty_needed, requirement_type, requirement_value 
            FROM recipes WHERE product_id = ?
        """, (product_id,))
        
        rows = cursor.fetchall()
        result = {'has_generics': False, 'specific_items': [], 'generic_items': []}
        
        for item_id, qty, req_type, req_val in rows:
            if req_type == 'Category':
                result['has_generics'] = True
                result['generic_items'].append({'category': req_val, 'qty': qty})
            else:
                result['specific_items'].append((item_id, qty))
                
        return result
    except sqlite3.Error as e:
        logger.error(f"get_recipe_requirements: {e}")
        return {'has_generics': False, 'specific_items': [], 'generic_items': []}
    finally:
        conn.close()

def get_items_by_category(category: str) -> pd.DataFrame:
    """Returns a DataFrame of inventory items matching a specific sub_category."""
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT item_id, name, count_on_hand FROM inventory WHERE sub_category = ? COLLATE NOCASE", 
            conn, 
            params=(category,)
        )
    except Exception as e:
        logger.error(f"get_items_by_category: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def get_forecast_generic_requirements(start_date, end_date):
    """Returns aggregated demand for generic categories within a date range."""
    conn = get_connection()
    try:
        # Ensure strings for SQLite comparison
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

        query = """
            SELECT 
                r.requirement_value as Category,
                SUM((g.qty_ordered - g.qty_fulfilled) * r.qty_needed) as Needed
            FROM production_goals g
            JOIN recipes r ON g.product_id = r.product_id
            WHERE g.due_date BETWEEN ? AND ?
              AND r.requirement_type = 'Category'
              AND (g.qty_ordered - g.qty_fulfilled) > 0
            GROUP BY r.requirement_value
        """
        return pd.read_sql_query(query, conn, params=(s_date, e_date))
    except Exception as e:
        logger.error(f"get_forecast_generic_requirements: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def update_goal_quantity(goal_id: int, new_qty: int) -> dict:
    """Updates the target quantity and reports if we are now over-fulfilled."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check current progress
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        current_made = res[0] if res else 0
        
        cursor.execute("UPDATE production_goals SET qty_ordered = ? WHERE goal_id = ?", (new_qty, goal_id))
        conn.commit()
        
        return {
            "success": True, 
            "overage": max(0, current_made - new_qty)
        }
    except sqlite3.Error as e:
        logger.error(f"update_goal_quantity: {e}")
        return {"success": False, "overage": 0}
    finally:
        conn.close()

def release_overage_to_stock(goal_id: int, qty_to_release: int) -> bool:
    """Moves items from 'Goal Progress' to 'General Stock' (Cooler)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Get Product ID
        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        p_id = cursor.fetchone()[0]
        
        # 2. Decrease Goal Progress
        cursor.execute("UPDATE production_goals SET qty_fulfilled = qty_fulfilled - ? WHERE goal_id = ?", (qty_to_release, goal_id))
        
        # 3. Increase General Stock
        cursor.execute("UPDATE products SET stock_on_hand = stock_on_hand + ? WHERE product_id = ?", (qty_to_release, p_id))
        
        # 4. Handle Logs (LIFO)
        # Identify the specific logs affected by this release
        cursor.execute("SELECT log_id, action_type FROM production_logs WHERE goal_id = ? ORDER BY log_id DESC LIMIT ?", (goal_id, qty_to_release))
        logs = cursor.fetchall()
        
        pack_ids = [str(row[0]) for row in logs if row[1] == 'PACK']
        make_ids = [str(row[0]) for row in logs if row[1] != 'PACK']
        
        if pack_ids:
            # Delete PACK logs (Reversing the move from Cooler -> Goal)
            cursor.execute(f"DELETE FROM production_logs WHERE log_id IN ({','.join(pack_ids)})")
            
        if make_ids:
            # Detach MAKE logs (Converting Goal Production -> Stock Production)
            cursor.execute(f"UPDATE production_logs SET goal_id = NULL, action_type = 'STOCK' WHERE log_id IN ({','.join(make_ids)})")
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"release_overage_to_stock: {e}")
        return False
    finally:
        conn.close()
