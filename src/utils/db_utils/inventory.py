import sqlite3
import pandas as pd
import logging
from typing import List, Tuple

from ._core import get_connection, filter_dataframe_by_terms  # noqa: F401 (re-exported via __init__)

logger = logging.getLogger(__name__)


def get_inventory() -> pd.DataFrame:
    import os
    from ._core import DB_PATH
    try:
        if not os.path.exists(DB_PATH):
            return pd.DataFrame()
        conn = get_connection()
        try:
            return pd.read_sql_query("SELECT * FROM inventory", conn)
        except Exception as e:
            logger.error(f"get_inventory: Error executing query: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"get_inventory: Error fetching inventory: {e}")
        return pd.DataFrame()


def update_item_details(item_id, count, cost, bundle_count, track_inventory=None):
    """Updates count, cost, bundle_count, and optionally track_inventory for an item."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if track_inventory is None:
            cursor.execute(
                "UPDATE inventory SET count_on_hand = ?, unit_cost = ?, bundle_count = ? WHERE item_id = ?",
                (count, cost, bundle_count, item_id),
            )
        else:
            cursor.execute(
                "UPDATE inventory SET count_on_hand = ?, unit_cost = ?, bundle_count = ?, track_inventory = ? WHERE item_id = ?",
                (count, cost, bundle_count, int(track_inventory), item_id),
            )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"update_item_details: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def update_inventory_cost(item_id: int, new_cost: float) -> bool:
    """Updates the unit cost for a specific inventory item."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
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


def add_inventory_item(name: str, category: str, sub_category: str, count: int, cost: float, bundle_count: int, track_inventory: int = 1) -> bool:
    """Adds a new inventory item. Returns False if name already exists."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM inventory WHERE name = ? COLLATE NOCASE", (name,))
        if cursor.fetchone():
            logger.warning(f"add_inventory_item: Duplicate name '{name}'")
            return False
        cursor.execute(
            "INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, category, sub_category, count, cost, bundle_count, int(track_inventory)),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"add_inventory_item: {e}")
        return False
    finally:
        conn.close()


def get_inventory_categories() -> List[str]:
    """Returns distinct main categories from the inventory."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT category FROM inventory WHERE category IS NOT NULL AND category != '' ORDER BY category"
        )
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"get_inventory_categories: {e}")
        return []
    finally:
        conn.close()


def get_items_by_category(category: str, tracked_only: bool = False) -> pd.DataFrame:
    """Returns inventory items whose category OR sub_category matches.

    When tracked_only=True, only items with track_inventory=1 are returned
    (used by the Category picker modal so the user isn't asked to pick
    between items the system doesn't count anyway).
    """
    conn = get_connection()
    try:
        if tracked_only:
            query = (
                "SELECT item_id, name, count_on_hand FROM inventory "
                "WHERE (category = ? OR sub_category = ?) COLLATE NOCASE AND track_inventory = 1"
            )
        else:
            query = (
                "SELECT item_id, name, count_on_hand FROM inventory "
                "WHERE (category = ? OR sub_category = ?) COLLATE NOCASE"
            )
        return pd.read_sql_query(query, conn, params=(category, category))
    except Exception as e:
        logger.error(f"get_items_by_category: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def export_inventory_csv() -> str:
    """Generates a CSV string of the current inventory for auditing."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT item_id, name, category, sub_category, unit_cost, bundle_count, count_on_hand, track_inventory FROM inventory ORDER BY category, name",
            conn,
        )
        return df.to_csv(index=False)
    except Exception as e:
        logger.error(f"export_inventory_csv: {e}")
        return ""
    finally:
        conn.close()


def process_bulk_inventory_upload(file_obj) -> Tuple[int, List[str]]:
    """Reads a CSV and updates inventory counts/costs. Matches by ID first, then inserts.

    The CSV may include an optional `track_inventory` column (0/1 or true/false).
    When absent, new items use the `default_track_inventory` setting as the default;
    existing items keep their current flag.
    """
    try:
        df = pd.read_csv(file_obj)
        df.columns = [c.lower().strip() for c in df.columns]
        if 'name' not in df.columns or 'count_on_hand' not in df.columns:
            return 0, ["CSV missing required columns: 'name', 'count_on_hand'"]
    except Exception as e:
        logger.error(f"process_bulk_inventory_upload: CSV Error: {e}")
        return 0, [str(e)]

    # Default for new rows when the column is missing or blank.
    from src.utils import settings_utils
    default_track = 1 if settings_utils.load_settings().get('default_track_inventory', False) else 0
    has_track_col = 'track_inventory' in df.columns

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        updated_count = 0
        errors = []

        for index, row in df.iterrows():
            try:
                name = str(row['name']).strip()

                try:
                    qty = int(float(row['count_on_hand']))
                except (ValueError, TypeError):
                    qty = 0

                cat = row.get('category', None)
                if pd.isna(cat):
                    cat = None

                sub = row.get('sub_category', None)
                if pd.isna(sub):
                    sub = None

                raw_cost = row.get('unit_cost', 0.0)
                try:
                    cost = float(str(raw_cost).replace('$', '').replace(',', '')) if pd.notna(raw_cost) else 0.0
                except (ValueError, TypeError):
                    cost = 0.0

                raw_bundle = row.get('bundle_count', 1)
                try:
                    bundle = int(float(raw_bundle)) if pd.notna(raw_bundle) else 1
                except (ValueError, TypeError):
                    bundle = 1

                i_id = row.get('item_id', None)
                if pd.isna(i_id):
                    i_id = None
                else:
                    try:
                        i_id = int(float(i_id))
                    except (ValueError, TypeError):
                        i_id = None

                row_track = None
                if has_track_col:
                    raw_track = row.get('track_inventory', None)
                    if pd.notna(raw_track):
                        s = str(raw_track).strip().lower()
                        if s in ('1', 'true', 'yes', 'y', 't'):
                            row_track = 1
                        elif s in ('0', 'false', 'no', 'n', 'f'):
                            row_track = 0
                        else:
                            try:
                                row_track = 1 if int(float(s)) else 0
                            except (ValueError, TypeError):
                                row_track = None

                if i_id:
                    if row_track is None:
                        cursor.execute(
                            "UPDATE inventory SET name=?, category=?, sub_category=?, count_on_hand=?, unit_cost=?, bundle_count=? WHERE item_id=?",
                            (name, cat, sub, qty, cost, bundle, i_id),
                        )
                    else:
                        cursor.execute(
                            "UPDATE inventory SET name=?, category=?, sub_category=?, count_on_hand=?, unit_cost=?, bundle_count=?, track_inventory=? WHERE item_id=?",
                            (name, cat, sub, qty, cost, bundle, row_track, i_id),
                        )
                    if cursor.rowcount == 0:
                        track = row_track if row_track is not None else default_track
                        cursor.execute(
                            "INSERT INTO inventory (item_id, name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (i_id, name, cat, sub, qty, cost, bundle, track),
                        )
                else:
                    track = row_track if row_track is not None else default_track
                    cursor.execute(
                        "INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (name, cat, sub, qty, cost, bundle, track),
                    )

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


def clear_inventory() -> bool:
    """Deletes all items from the inventory table."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inventory")
        conn.commit()
        logger.info("clear_inventory: All inventory items deleted.")
        return True
    except sqlite3.Error as e:
        logger.error(f"clear_inventory: {e}")
        conn.rollback()
        return False
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
            if not line:
                continue

            # Strategy 0: ID-based update (Format: ID, Name..., bundle_count=X, count=Y, loss=Z)
            if line[0].isdigit() and "count=" in line:
                try:
                    parts = [p.strip() for p in line.split(',')]
                    item_id = int(parts[0])

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
                            if val:
                                bundle_count = int(val)
                        elif "count=" in lower:
                            val = lower.split("count=")[1].strip()
                            if val:
                                count_val = int(val)
                        elif "loss=" in lower:
                            val = lower.split("loss=")[1].strip()
                            if val:
                                loss_val = int(val)

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

            # Strategy 1: Comma-separated (Name, Sub-Cat, Qty)
            if ',' in line:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2 and parts[-1].isdigit():
                    name = parts[0]
                    qty = int(parts[-1])

            # Strategy 2: Whitespace-separated (Name Qty)
            if name is None:
                parts = line.rsplit(None, 1)
                if len(parts) == 2 and parts[1].isdigit():
                    name = parts[0].strip().rstrip(',')
                    qty = int(parts[1])

            if name and qty is not None:
                cursor.execute("SELECT item_id FROM inventory WHERE name = ? COLLATE NOCASE", (name,))
                row = cursor.fetchone()
                if row:
                    cursor.execute("UPDATE inventory SET count_on_hand = ? WHERE item_id = ?", (qty, row[0]))
                    updated_items.append(f"{name}")
                else:
                    errors.append(f"Unknown: {name}")
            else:
                errors.append(f"Invalid format: {line}")

        logger.info(f"process_clipboard_update: Updated: {len(updated_items)}, Errors: {len(errors)}")
        conn.commit()
    except Exception as e:
        logger.error(f"process_clipboard_update: Error: {e}")
        errors.append(f"System Error: {e}")
        conn.rollback()
    finally:
        conn.close()

    return updated_items, errors
