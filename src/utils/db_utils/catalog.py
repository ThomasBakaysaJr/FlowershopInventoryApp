import sqlite3
import pandas as pd
import os
import logging
import uuid
from typing import Optional, List, Tuple, Union

from ._core import get_connection
from src.utils import utils

logger = logging.getLogger(__name__)


def _get_local_image_bytes(product_name: str) -> Optional[bytes]:
    """Finds and processes a local image for a product from images/recipes/."""
    image_dir = os.path.join("images", "recipes")
    if not os.path.exists(image_dir):
        return None

    candidates = [
        product_name,
        product_name.replace(" ", "_"),
        product_name.lower(),
        product_name.lower().replace(" ", "_"),
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


def get_all_recipes() -> pd.DataFrame:
    """Fetches all active product recipes with ingredient details."""
    conn = get_connection()
    try:
        query = """
        SELECT p.product_id, p.display_name as Product, p.selling_price as Price, p.active, p.stock_on_hand, p.category, p.note as ProductNote, p.variant_type,
               r.item_id,
               COALESCE(i.name, 'Any ' || r.requirement_value, 'Unknown Item') as Ingredient,
               r.qty_needed as Qty,
               r.note as Note
        FROM products p
        LEFT JOIN recipes r ON p.product_id = r.product_id
        LEFT JOIN inventory i ON r.item_id = i.item_id
        ORDER BY p.display_name ASC
        """
        return pd.read_sql_query(query, conn)
    except Exception as e:
        logger.error(f"get_all_recipes: Error fetching recipes: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_active_product_options() -> pd.DataFrame:
    """Returns a simple list of active products for dropdowns."""
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT product_id, display_name FROM products WHERE active = 1 ORDER BY display_name",
            conn,
        )
    except Exception as e:
        logger.error(f"get_active_product_options: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_recipe_requirements(product_id: int) -> dict:
    """
    Analyzes a recipe and returns what the production flow needs to ask the user for.

    Category-type recipe lines are only included when the category has at least one
    tracked (track_inventory=1) candidate item — otherwise the user has nothing
    meaningful to pick from (the deduction logic skips untracked items anyway), so
    the modal is suppressed and production proceeds silently.

    Returns: {
        'has_generics': bool,      # True only if any Category line has tracked candidates
        'specific_items': list,    # [(item_id, qty), ...] — unaffected by tracking
        'generic_items': list,     # [{'category': str, 'qty': int, 'note': str}, ...]
                                   # Only categories that resolve to ≥1 tracked item
    }
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT item_id, qty_needed, requirement_type, requirement_value, note FROM recipes WHERE product_id = ?",
            (product_id,),
        )
        rows = cursor.fetchall()
        result = {'has_generics': False, 'specific_items': [], 'generic_items': []}
        generic_map = {}

        for item_id, qty, req_type, req_val, note in rows:
            if req_type == 'Category':
                cat = req_val
                if cat in generic_map:
                    generic_map[cat]['qty'] += qty
                    if note:
                        prev = generic_map[cat]['note']
                        generic_map[cat]['note'] = f"{prev}; {note}" if prev else note
                else:
                    generic_map[cat] = {'category': cat, 'qty': qty, 'note': note}
            else:
                result['specific_items'].append((item_id, qty))

        # Include only categories that have at least one tracked candidate.
        tracked_generics = []
        for cat, entry in generic_map.items():
            cursor.execute(
                "SELECT 1 FROM inventory WHERE (category = ? OR sub_category = ?) "
                "COLLATE NOCASE AND track_inventory = 1 LIMIT 1",
                (cat, cat),
            )
            if cursor.fetchone():
                tracked_generics.append(entry)

        result['generic_items'] = tracked_generics
        result['has_generics'] = bool(tracked_generics)
        return result
    except sqlite3.Error as e:
        logger.error(f"get_recipe_requirements: {e}")
        return {'has_generics': False, 'specific_items': [], 'generic_items': []}
    finally:
        conn.close()


def get_product_details(product_name: str) -> Optional[dict]:
    """Fetches full details for a product including all recipe items and variants."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT product_id, selling_price, image_data, display_name, stock_on_hand, category, note, variant_group_id, variant_type FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1",
            (product_name,),
        )
        res = cursor.fetchone()
        if not res:
            return None

        p_id, price, img, db_name, stock, category, note, group_id, v_type = res

        cursor.execute(
            """
            SELECT r.item_id, i.name, r.qty_needed, r.requirement_type, r.requirement_value, r.note
            FROM recipes r
            LEFT JOIN inventory i ON r.item_id = i.item_id
            WHERE r.product_id = ?
            """,
            (p_id,),
        )

        recipe_items = []
        for row in cursor.fetchall():
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
                "note": row[5],
            })

        variants = []
        if group_id:
            cursor.execute(
                """
                SELECT product_id, display_name, variant_type
                FROM products
                WHERE variant_group_id = ? AND active = 1
                ORDER BY CASE variant_type WHEN 'STD' THEN 1 WHEN 'DLX' THEN 2 WHEN 'PRM' THEN 3 ELSE 4 END
                """,
                (group_id,),
            )
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
            "variants": variants,
        }
    except Exception as e:
        logger.error(f"get_product_details: Error: {e}")
        return None
    finally:
        conn.close()


def get_product_image(product_name: str) -> Optional[bytes]:
    """Fetches the thumbnail for a specific active product by name."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT image_data FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1",
            (product_name,),
        )
        res = cursor.fetchone()
        return res[0] if res else None
    except Exception as e:
        logger.error(f"get_product_image: Error fetching image for {product_name}: {e}")
        return None
    finally:
        conn.close()


def get_product_image_by_id(product_id: int) -> Optional[bytes]:
    """Fetches the image for a specific product ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT image_data FROM products WHERE product_id = ?", (product_id,))
        res = cursor.fetchone()
        return res[0] if res else None
    except Exception as e:
        logger.error(f"get_product_image_by_id: {e}")
        return None
    finally:
        conn.close()


def get_product_group_id(product_name: str) -> Optional[str]:
    """Fetches the variant_group_id for an active product."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT variant_group_id FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1",
            (product_name,),
        )
        res = cursor.fetchone()
        return res[0] if res else None
    except Exception as e:
        logger.error(f"get_product_group_id: Error fetching group ID for {product_name}: {e}")
        return None
    finally:
        conn.close()


def check_product_exists(product_name: str) -> bool:
    """Checks if a product name already exists (case-insensitive) and is active."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1",
            (product_name,),
        )
        return cursor.fetchone() is not None
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
        cursor.execute(
            "SELECT 1 FROM products WHERE display_name = ? COLLATE NOCASE AND variant_type = ? AND active = 1",
            (product_name, variant_type),
        )
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"check_product_variant: Error checking {product_name} ({variant_type}): {e}")
        return False
    finally:
        conn.close()


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
    variant_type: str = "STD",
) -> bool:
    """Creates a new product and its associated recipe in a single transaction."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if not variant_group_id:
            variant_group_id = str(uuid.uuid4())

        cursor.execute(
            "INSERT INTO products (display_name, selling_price, image_data, active, category, note, variant_group_id, variant_type) VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
            (name, selling_price, image_bytes, category, note, variant_group_id, variant_type),
        )
        product_id = cursor.lastrowid

        for item in recipe_items:
            if isinstance(item, tuple):
                item_id, qty = item
                req_type, req_val = 'Specific', None
                item_note = None
            elif isinstance(item, dict):
                item_id = item.get('id') or item.get('item_id')
                qty = item.get('qty')
                req_type = item.get('type', 'Specific')
                req_val = item.get('val') or item.get('value')
                item_note = item.get('note')
            else:
                continue

            cursor.execute(
                "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) VALUES (?, ?, ?, ?, ?, ?)",
                (product_id, item_id, qty, req_type, req_val, item_note),
            )

        if goal_date and goal_qty > 0:
            d_str = goal_date.strftime('%Y-%m-%d') if hasattr(goal_date, 'strftime') else str(goal_date)
            cursor.execute(
                "INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled) VALUES (?, ?, ?, 0)",
                (product_id, d_str, goal_qty),
            )
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


def update_product_recipe(
    current_product_id: int,
    new_name: str,
    recipe_items: List[Union[Tuple[int, int], dict]],
    image_bytes: Optional[bytes] = None,
    new_price: Optional[float] = None,
    rollover_stock: bool = True,
    variant_group_id: Optional[str] = None,
    category: Optional[str] = None,
    migrate_goals: bool = False,
    goal_date: Optional[str] = None,
    goal_qty: int = 0,
    note: Optional[str] = None,
) -> bool:
    """Archives the old product and creates a new version with updated details."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT selling_price, image_data, display_name, stock_on_hand, note, variant_group_id, variant_type, category FROM products WHERE product_id = ?",
            (current_product_id,),
        )
        res = cursor.fetchone()
        if not res:
            return False

        old_price, old_image_data, old_name, current_stock, old_note, old_group_id, old_variant_type, old_category = res

        final_price = new_price if new_price is not None else old_price
        final_image = image_bytes if image_bytes is not None else old_image_data
        final_name = new_name.strip()
        final_note = note if note is not None else old_note
        final_category = category if category is not None else old_category
        final_group_id = variant_group_id if variant_group_id else (old_group_id if old_group_id else str(uuid.uuid4()))

        if final_name.lower() != old_name.lower():
            cursor.execute(
                "SELECT product_id FROM products WHERE display_name = ? COLLATE NOCASE AND active = 1",
                (final_name,),
            )
            target_res = cursor.fetchone()
            if target_res:
                cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (target_res[0],))
                logger.info(f"update_product_recipe: Archived existing '{final_name}' (ID: {target_res[0]}) to allow overwrite.")

        cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (current_product_id,))

        final_stock = current_stock if rollover_stock else 0
        cursor.execute(
            "INSERT INTO products (display_name, selling_price, image_data, active, stock_on_hand, category, note, variant_group_id, variant_type) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)",
            (final_name, final_price, final_image, final_stock, final_category, final_note, final_group_id, old_variant_type or 'STD'),
        )
        new_p_id = cursor.lastrowid

        for item in recipe_items:
            if isinstance(item, tuple):
                item_id, qty = item
                req_type, req_val = 'Specific', None
                item_note = None
            elif isinstance(item, dict):
                item_id = item.get('id') or item.get('item_id')
                qty = item.get('qty')
                req_type = item.get('type', 'Specific')
                req_val = item.get('val') or item.get('value')
                item_note = item.get('note')
            else:
                continue

            cursor.execute(
                "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) VALUES (?, ?, ?, ?, ?, ?)",
                (new_p_id, item_id, qty, req_type, req_val, item_note),
            )

        if migrate_goals:
            cursor.execute(
                "UPDATE production_goals SET product_id = ? WHERE product_id = ? AND qty_fulfilled < qty_ordered",
                (new_p_id, current_product_id),
            )
            logger.info(f"update_product_recipe: Migrated unfulfilled goals from {current_product_id} to {new_p_id}")

        if goal_date and goal_qty > 0:
            d_str = goal_date.strftime('%Y-%m-%d') if hasattr(goal_date, 'strftime') else str(goal_date)
            cursor.execute(
                "INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled) VALUES (?, ?, ?, 0)",
                (new_p_id, d_str, goal_qty),
            )
            logger.info(f"update_product_recipe: Added new goal for '{final_name}' (Qty: {goal_qty}, Due: {d_str})")

        logger.info(f"update_product_recipe: Created new version (ID: {new_p_id}) for '{final_name}'")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"update_product_recipe: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def delete_product(product_id: int) -> bool:
    """Soft-deletes a product by marking it inactive."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
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


def export_products_csv() -> str:
    """Generates a tidy CSV of all active products/recipes."""
    conn = get_connection()
    try:
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


def process_bulk_recipe_upload(file_obj) -> Tuple[int, List[str]]:
    """Imports products/recipes from CSV. Format: Product, Price, Type, Ingredient, Qty."""
    try:
        df = pd.read_csv(file_obj)
        df.columns = [c.lower().strip() for c in df.columns]
        required = ['product', 'qty']
        if not all(col in df.columns for col in required):
            return 0, [f"CSV missing required columns: {required}"]
    except Exception as e:
        logger.error(f"process_bulk_recipe_upload: CSV Error: {e}")
        return 0, [str(e)]

    conn = get_connection()
    created_count = 0
    errors = []
    batch_groups = {}

    try:
        cursor = conn.cursor()
        grouped = df.groupby('product')

        for product_name, group in grouped:
            try:
                first_row = group.iloc[0]

                p_id_val = first_row.get('product_id')
                target_p_id = None
                if pd.notna(p_id_val):
                    try:
                        target_p_id = int(float(p_id_val))
                    except (ValueError, TypeError):
                        pass

                raw_price = first_row.get('price', 0.0)
                try:
                    price = float(str(raw_price).replace('$', '').replace(',', '')) if pd.notna(raw_price) else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                cat = first_row.get('type', None)
                if pd.isna(cat):
                    cat = None

                prod_note = str(first_row.get('product note', '')).strip() or None

                recipe_items = []
                for _, row in group.iterrows():
                    try:
                        qty = int(float(row['qty']))
                    except (ValueError, TypeError):
                        qty = 0

                    if qty <= 0:
                        continue

                    item_id = None
                    req_type = 'Specific'
                    req_val = None
                    item_note = str(row.get('note', '')).strip() or None
                    ing_name = str(row.get('ingredient', '')).strip()

                    if 'item_id' in row and pd.notna(row['item_id']):
                        try:
                            tid = int(float(row['item_id']))
                            cursor.execute("SELECT item_id FROM inventory WHERE item_id = ?", (tid,))
                            res = cursor.fetchone()
                            if res:
                                item_id = res[0]
                        except (ValueError, TypeError):
                            pass

                    if item_id is None and ing_name:
                        cursor.execute("SELECT item_id FROM inventory WHERE name = ? COLLATE NOCASE", (ing_name,))
                        res = cursor.fetchone()
                        if res:
                            item_id = res[0]

                    if item_id is None:
                        req_type = 'Category'
                        if ing_name.lower().startswith("any "):
                            req_val = ing_name[4:].strip()
                        else:
                            req_val = ing_name.strip()

                    recipe_items.append((item_id, qty, req_type, req_val, item_note))

                if not recipe_items:
                    errors.append(f"Skipped '{product_name}': No valid ingredients.")
                    continue

                prod_exists = False
                if target_p_id:
                    cursor.execute("SELECT 1 FROM products WHERE product_id = ?", (target_p_id,))
                    if cursor.fetchone():
                        prod_exists = True

                new_image_bytes = _get_local_image_bytes(product_name)

                if prod_exists:
                    cursor.execute(
                        "SELECT image_data, stock_on_hand, variant_group_id, variant_type, category FROM products WHERE product_id = ?",
                        (target_p_id,),
                    )
                    existing_data = cursor.fetchone()
                    old_img = existing_data[0] if existing_data else None
                    old_stock = existing_data[1] if existing_data else 0
                    old_group_id = existing_data[2] if existing_data and existing_data[2] else str(uuid.uuid4())
                    old_variant_type = existing_data[3] if existing_data and existing_data[3] else 'STD'
                    old_category = existing_data[4] if existing_data else 'Standard'

                    final_img = new_image_bytes if new_image_bytes else old_img
                    final_cat = cat if cat is not None else old_category

                    cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (target_p_id,))
                    cursor.execute(
                        "INSERT INTO products (display_name, selling_price, image_data, active, stock_on_hand, category, note, variant_group_id, variant_type) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)",
                        (product_name, price, final_img, old_stock, final_cat, prod_note, old_group_id, old_variant_type),
                    )
                    new_id = cursor.lastrowid

                    for i_id, q, r_type, r_val, r_note in recipe_items:
                        cursor.execute(
                            "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) VALUES (?, ?, ?, ?, ?, ?)",
                            (new_id, i_id, q, r_type, r_val, r_note),
                        )
                else:
                    final_cat = cat if cat is not None else 'Standard'

                    words = product_name.split()
                    last_word = words[-1].lower() if words else ""
                    variant_type = "STD"
                    suffix_map = {"standard": "STD", "deluxe": "DLX", "premium": "PRM"}

                    if last_word in suffix_map:
                        variant_type = suffix_map[last_word]
                        base_name = " ".join(words[:-1]).strip()
                    else:
                        base_name = product_name.strip()

                    if base_name in batch_groups:
                        new_group_id = batch_groups[base_name]
                    else:
                        cursor.execute(
                            "SELECT variant_group_id FROM products WHERE display_name LIKE ? AND active = 1 LIMIT 1",
                            (base_name + "%",),
                        )
                        existing_grp = cursor.fetchone()
                        if existing_grp and existing_grp[0]:
                            new_group_id = existing_grp[0]
                        else:
                            new_group_id = str(uuid.uuid4())
                        batch_groups[base_name] = new_group_id

                    if target_p_id:
                        cursor.execute(
                            "INSERT INTO products (product_id, display_name, selling_price, image_data, category, active, stock_on_hand, note, variant_group_id, variant_type) VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?)",
                            (target_p_id, product_name, price, new_image_bytes, final_cat, prod_note, new_group_id, variant_type),
                        )
                        new_id = target_p_id
                    else:
                        cursor.execute(
                            "INSERT INTO products (display_name, selling_price, image_data, category, active, stock_on_hand, note, variant_group_id, variant_type) VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?)",
                            (product_name, price, new_image_bytes, final_cat, prod_note, new_group_id, variant_type),
                        )
                        new_id = cursor.lastrowid

                    for i_id, q, r_type, r_val, r_note in recipe_items:
                        cursor.execute(
                            "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value, note) VALUES (?, ?, ?, ?, ?, ?)",
                            (new_id, i_id, q, r_type, r_val, r_note),
                        )

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


def clear_products() -> bool:
    """Deletes all products, recipes, and associated goals/logs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM production_logs")
        cursor.execute("DELETE FROM production_goals")
        cursor.execute("DELETE FROM recipes")
        cursor.execute("DELETE FROM products")
        conn.commit()
        logger.info("clear_products: All products, recipes, goals, and logs deleted.")
        return True
    except sqlite3.Error as e:
        logger.error(f"clear_products: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
